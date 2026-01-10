"""
SQLAlchemy 2.0 风格的 Statement API

提供 select, insert, update, delete 语句构建器
"""

from typing import Any, Dict, List, Optional, Type, TYPE_CHECKING, Union
from abc import ABC, abstractmethod

if TYPE_CHECKING:
    from .orm import PureBaseModel, Column
    from .query import BinaryExpression
    from .storage import Storage


class Statement(ABC):
    """
    Statement abstract base class.

    All SQL-style statement builders (Select, Insert, Update, Delete) inherit from this class.
    Statements are executed through Session.execute() method.

    Attributes:
        model_class: The model class this statement operates on
    """

    def __init__(self, model_class: Type['PureBaseModel']):
        self.model_class = model_class

    @abstractmethod
    def _execute(self, storage: 'Storage') -> Any:
        """执行语句（由 Session.execute 调用）"""
        pass


class Select(Statement):
    """
    SELECT statement builder for querying records.

    Supports method chaining for building complex queries with conditions,
    ordering, and pagination.

    Example:
        stmt = select(User).where(User.age >= 18).order_by('name').limit(10)
        result = session.execute(stmt)
        users = result.scalars().all()

    Attributes:
        model_class: The model class to query
        _where_clauses: List of query conditions (BinaryExpression)
        _order_by_field: Field name for ordering
        _order_desc: Whether to sort in descending order
        _limit_value: Maximum number of records to return
        _offset_value: Number of records to skip
    """

    def __init__(self, model_class: Type['PureBaseModel']):
        super().__init__(model_class)
        self._where_clauses: List['BinaryExpression'] = []
        self._order_by_field: Optional[str] = None
        self._order_desc: bool = False
        self._limit_value: Optional[int] = None
        self._offset_value: int = 0

    def where(self, *expressions: 'BinaryExpression') -> 'Select':
        """添加 WHERE 条件（表达式语法）"""
        self._where_clauses.extend(expressions)
        return self

    def filter_by(self, **kwargs: Any) -> 'Select':
        """
        添加 WHERE 条件（简单等值查询，SQLAlchemy 风格）

        用于简单的等值匹配，语法更简洁。对于复杂查询，使用 where() 配合表达式。

        Args:
            **kwargs: 字段名=值 的等值条件

        Returns:
            Select 对象（链式调用）

        Example:
            # 简单等值查询（推荐 filter_by）
            stmt = select(User).filter_by(name='Bob', active=True)

            # 复杂表达式查询（使用 where）
            stmt = select(User).where(User.age >= 20, User.name != 'Alice')
        """
        from .query import BinaryExpression

        # 为每个 kwargs 创建等值表达式
        for field_name, value in kwargs.items():
            # 获取 Column 对象
            if field_name in self.model_class.__columns__:
                column = self.model_class.__columns__[field_name]
                # 创建等值表达式
                expr = BinaryExpression(column, '=', value)
                self._where_clauses.append(expr)
            else:
                raise ValueError(f"Column '{field_name}' not found in {self.model_class.__name__}")

        return self

    def order_by(self, field: str, desc: bool = False) -> 'Select':
        """排序"""
        self._order_by_field = field
        self._order_desc = desc
        return self

    def limit(self, n: int) -> 'Select':
        """限制返回数量"""
        self._limit_value = n
        return self

    def offset(self, n: int) -> 'Select':
        """偏移"""
        self._offset_value = n
        return self

    def _execute(self, storage: 'Storage') -> List[Dict[str, Any]]:
        """执行查询，返回记录字典列表"""
        from .query import Condition

        # 转换 BinaryExpression 为 Condition
        conditions = [expr.to_condition() for expr in self._where_clauses]

        # 查询
        table_name = self.model_class.__tablename__
        records = storage.query(table_name, conditions)

        # 排序
        if self._order_by_field:
            records.sort(
                key=lambda r: r.get(self._order_by_field),
                reverse=self._order_desc
            )

        # 偏移和限制
        if self._offset_value > 0:
            records = records[self._offset_value:]
        if self._limit_value is not None:
            records = records[:self._limit_value]

        return records


class Insert(Statement):
    """
    INSERT statement builder for creating new records.

    Example:
        stmt = insert(User).values(name='Alice', age=20)
        result = session.execute(stmt)
        new_id = result.inserted_primary_key

    Attributes:
        model_class: The model class to insert into
        _values: Dictionary of column names to values
    """

    def __init__(self, model_class: Type['PureBaseModel']):
        super().__init__(model_class)
        self._values: Dict[str, Any] = {}

    def values(self, **kwargs: Any) -> 'Insert':
        """设置要插入的值"""
        self._values.update(kwargs)
        return self

    def _execute(self, storage: 'Storage') -> Any:
        """执行插入，返回插入的主键"""
        table_name = self.model_class.__tablename__

        # 验证和转换值
        validated_data: Dict[str, Any] = {}
        for col_name, column in self.model_class.__columns__.items():
            if col_name in self._values:
                validated_data[col_name] = column.validate(self._values[col_name])
            elif column.default is not None:
                validated_data[col_name] = column.default

        # 插入
        pk = storage.insert(table_name, validated_data)
        return pk


class Update(Statement):
    """
    UPDATE statement builder for modifying existing records.

    Example:
        stmt = update(User).where(User.id == 1).values(age=21)
        result = session.execute(stmt)
        affected = result.rowcount()

    Attributes:
        model_class: The model class to update
        _where_clauses: List of conditions to match records
        _values: Dictionary of column names to new values
    """

    def __init__(self, model_class: Type['PureBaseModel']):
        super().__init__(model_class)
        self._where_clauses: List['BinaryExpression'] = []
        self._values: Dict[str, Any] = {}

    def where(self, *expressions: 'BinaryExpression') -> 'Update':
        """添加 WHERE 条件"""
        self._where_clauses.extend(expressions)
        return self

    def values(self, **kwargs: Any) -> 'Update':
        """设置要更新的值"""
        self._values.update(kwargs)
        return self

    def _execute(self, storage: 'Storage') -> int:
        """执行更新，返回受影响的行数"""
        from .query import Condition

        table_name = self.model_class.__tablename__
        conditions = [expr.to_condition() for expr in self._where_clauses]

        # 查询符合条件的记录
        records = storage.query(table_name, conditions)

        # 验证值
        validated_values: Dict[str, Any] = {}
        for col_name, value in self._values.items():
            if col_name in self.model_class.__columns__:
                column = self.model_class.__columns__[col_name]
                validated_values[col_name] = column.validate(value)

        # 更新每条记录
        pk_name = self.model_class.__primary_key__
        count = 0
        for record in records:
            pk = record[pk_name]
            storage.update(table_name, pk, validated_values)
            count += 1

        return count


class Delete(Statement):
    """
    DELETE statement builder for removing records.

    Example:
        stmt = delete(User).where(User.id == 1)
        result = session.execute(stmt)
        affected = result.rowcount()

    Attributes:
        model_class: The model class to delete from
        _where_clauses: List of conditions to match records for deletion
    """

    def __init__(self, model_class: Type['PureBaseModel']):
        super().__init__(model_class)
        self._where_clauses: List['BinaryExpression'] = []

    def where(self, *expressions: 'BinaryExpression') -> 'Delete':
        """添加 WHERE 条件"""
        self._where_clauses.extend(expressions)
        return self

    def _execute(self, storage: 'Storage') -> int:
        """执行删除，返回受影响的行数"""
        from .query import Condition

        table_name = self.model_class.__tablename__
        conditions = [expr.to_condition() for expr in self._where_clauses]

        # 查询符合条件的记录
        records = storage.query(table_name, conditions)

        # 删除每条记录
        pk_name = self.model_class.__primary_key__
        count = 0
        for record in records:
            pk = record[pk_name]
            storage.delete(table_name, pk)
            count += 1

        return count


# ==================== 顶层工厂函数 ====================

def select(model_class: Type['PureBaseModel']) -> Select:
    """创建 SELECT 语句"""
    return Select(model_class)


def insert(model_class: Type['PureBaseModel']) -> Insert:
    """创建 INSERT 语句"""
    return Insert(model_class)


def update(model_class: Type['PureBaseModel']) -> Update:
    """创建 UPDATE 语句"""
    return Update(model_class)


def delete(model_class: Type['PureBaseModel']) -> Delete:
    """创建 DELETE 语句"""
    return Delete(model_class)
