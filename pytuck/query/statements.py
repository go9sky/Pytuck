"""
SQLAlchemy 2.0 风格的 Statement API

提供 select, insert, update, delete 语句构建器
"""

from typing import Any, Dict, List, Optional, Tuple, Type, Generic, TYPE_CHECKING, Union
from abc import ABC, abstractmethod

from ..common.types import T
from ..common.exceptions import QueryError
from ..core.orm import PSEUDO_PK_NAME

if TYPE_CHECKING:
    from ..core.orm import PureBaseModel, Column
    from .builder import BinaryExpression
    from ..core.storage import Storage


class Statement(Generic[T], ABC):
    """
    Statement abstract base class.

    All SQL-style statement builders (Select, Insert, Update, Delete) inherit from this class.
    Statements are executed through Session.execute() method.

    Attributes:
        model_class: The model class this statement operates on
    """

    def __init__(self, model_class: Type[T]) -> None:
        self.model_class = model_class

    @abstractmethod
    def _execute(self, storage: 'Storage') -> Any:
        """执行语句（由 Session.execute 调用）"""
        pass


class Select(Statement[T]):
    """
    SELECT statement builder for querying records.

    Supports method chaining for building complex queries with conditions,
    ordering, and pagination.

    Example:
        stmt = select(User).where(User.age >= 18).order_by('name').limit(10)
        result = session.execute(stmt)
        users = result.all()

        # Multi-column ordering (priority: first to last)
        stmt = select(User).order_by('age', desc=True).order_by('name')

    Attributes:
        model_class: The model class to query
        _where_clauses: List of query conditions (BinaryExpression)
        _order_by_fields: List of (field_name, desc) tuples for multi-column ordering
        _limit_value: Maximum number of records to return
        _offset_value: Number of records to skip
    """

    def __init__(self, model_class: Type[T]) -> None:
        super().__init__(model_class)
        self._where_clauses: List['BinaryExpression'] = []
        self._order_by_fields: List[Tuple[str, bool]] = []  # [(field, desc), ...]
        self._limit_value: Optional[int] = None
        self._offset_value: int = 0

    def where(self, *expressions: 'BinaryExpression') -> 'Select[T]':
        """添加 WHERE 条件（表达式语法）"""
        self._where_clauses.extend(expressions)
        return self

    def filter_by(self, **kwargs: Any) -> 'Select[T]':
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
        from .builder import BinaryExpression

        # 为每个 kwargs 创建等值表达式
        for field_name, value in kwargs.items():
            # 获取 Column 对象
            if field_name in self.model_class.__columns__:
                column = self.model_class.__columns__[field_name]
                # 创建等值表达式
                expr = BinaryExpression(column, '=', value)
                self._where_clauses.append(expr)
            else:
                raise QueryError(
                    f"Column '{field_name}' not found in {self.model_class.__name__}",
                    column_name=field_name
                )

        return self

    def order_by(self, field: str, desc: bool = False) -> 'Select[T]':
        """
        添加排序字段

        支持多列排序，多次调用时按调用顺序确定排序优先级。

        Args:
            field: 排序字段名
            desc: 是否降序，默认 False（升序）

        Returns:
            Select 对象（链式调用）

        Example:
            # 单列排序
            stmt = select(User).order_by('age')

            # 多列排序（先按 age 降序，再按 name 升序）
            stmt = select(User).order_by('age', desc=True).order_by('name')
        """
        self._order_by_fields.append((field, desc))
        return self

    def limit(self, n: int) -> 'Select[T]':
        """限制返回数量"""
        self._limit_value = n
        return self

    def offset(self, n: int) -> 'Select[T]':
        """偏移"""
        self._offset_value = n
        return self

    def _execute(self, storage: 'Storage') -> List[Dict[str, Any]]:
        """执行查询，返回记录字典列表"""
        from .builder import Condition

        # 转换 BinaryExpression 为 Condition
        conditions = [expr.to_condition() for expr in self._where_clauses]

        # 查询
        table_name = self.model_class.__tablename__
        assert table_name is not None, f"Model {self.model_class.__name__} must have __tablename__ defined"
        records = storage.query(table_name, conditions)

        # 多列排序（从后往前排序，确保优先级正确）
        if self._order_by_fields:
            # 反向遍历，先按低优先级排序，再按高优先级排序
            # 利用 Python 排序的稳定性，最终实现多列排序
            for field, desc in reversed(self._order_by_fields):
                # 使用工厂函数 make_sort_key 来正确捕获循环变量 field
                # 这避免了闭包中常见的"后期绑定"问题
                def make_sort_key(f: str) -> Any:
                    def sort_key(r: dict) -> Any:
                        return r.get(f) if r.get(f) is not None else ''
                    return sort_key
                records.sort(key=make_sort_key(field), reverse=desc)

        # 偏移和限制
        if self._offset_value > 0:
            records = records[self._offset_value:]
        if self._limit_value is not None:
            records = records[:self._limit_value]

        return records


class Insert(Statement[T]):
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

    def __init__(self, model_class: Type[T]) -> None:
        super().__init__(model_class)
        self._values: Dict[str, Any] = {}

    def values(self, **kwargs: Any) -> 'Insert[T]':
        """设置要插入的值"""
        self._values.update(kwargs)
        return self

    def _execute(self, storage: 'Storage') -> Any:
        """执行插入，返回插入的主键"""
        table_name = self.model_class.__tablename__
        assert table_name is not None, f"Model {self.model_class.__name__} must have __tablename__ defined"

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


class Update(Statement[T]):
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

    def __init__(self, model_class: Type[T]) -> None:
        super().__init__(model_class)
        self._where_clauses: List['BinaryExpression'] = []
        self._values: Dict[str, Any] = {}

    def where(self, *expressions: 'BinaryExpression') -> 'Update[T]':
        """添加 WHERE 条件"""
        self._where_clauses.extend(expressions)
        return self

    def values(self, **kwargs: Any) -> 'Update[T]':
        """设置要更新的值"""
        self._values.update(kwargs)
        return self

    def _execute(self, storage: 'Storage') -> int:
        """执行更新，返回受影响的行数"""
        from .builder import Condition

        table_name = self.model_class.__tablename__
        assert table_name is not None, f"Model {self.model_class.__name__} must have __tablename__ defined"
        pk_name = self.model_class.__primary_key__

        # 优化：检测主键等于查询，直接访问而非全表扫描
        pk_value = None
        if pk_name and len(self._where_clauses) == 1:
            expr = self._where_clauses[0]
            if expr.column.name == pk_name and expr.operator in ('=', '=='):
                pk_value = expr.value

        # 验证值
        validated_values: Dict[str, Any] = {}
        for col_name, value in self._values.items():
            if col_name in self.model_class.__columns__:
                column = self.model_class.__columns__[col_name]
                validated_values[col_name] = column.validate(value)

        if pk_value is not None:
            # 主键直接查询（O(1)）
            from ..common.exceptions import RecordNotFoundError
            try:
                storage.update(table_name, pk_value, validated_values)
                return 1
            except RecordNotFoundError:
                # 记录不存在，返回 0（符合 SQL UPDATE 语义）
                return 0
            # 其他异常（如数据库错误）向上传播
        else:
            # 条件查询
            conditions = [expr.to_condition() for expr in self._where_clauses]
            records = storage.query(table_name, conditions)

            count = 0
            for record in records:
                # 获取主键或 rowid
                if pk_name:
                    pk = record[pk_name]
                else:
                    # 无主键模型：使用内部 rowid
                    pk = record.get(PSEUDO_PK_NAME)
                    if pk is None:
                        raise QueryError(
                            "Cannot update record without primary key or rowid",
                            details={'table': table_name}
                        )
                storage.update(table_name, pk, validated_values)
                count += 1

            return count


class Delete(Statement[T]):
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

    def __init__(self, model_class: Type[T]) -> None:
        super().__init__(model_class)
        self._where_clauses: List['BinaryExpression'] = []

    def where(self, *expressions: 'BinaryExpression') -> 'Delete[T]':
        """添加 WHERE 条件"""
        self._where_clauses.extend(expressions)
        return self

    def _execute(self, storage: 'Storage') -> int:
        """执行删除，返回受影响的行数"""
        from .builder import Condition

        table_name = self.model_class.__tablename__
        assert table_name is not None, f"Model {self.model_class.__name__} must have __tablename__ defined"
        pk_name = self.model_class.__primary_key__

        # 优化：检测主键等于查询，直接访问而非全表扫描
        pk_value = None
        if pk_name and len(self._where_clauses) == 1:
            expr = self._where_clauses[0]
            if expr.column.name == pk_name and expr.operator in ('=', '=='):
                pk_value = expr.value

        if pk_value is not None:
            # 主键直接删除（O(1)）
            from ..common.exceptions import RecordNotFoundError
            try:
                storage.delete(table_name, pk_value)
                return 1
            except RecordNotFoundError:
                # 记录不存在，返回 0（符合 SQL DELETE 语义）
                return 0
            # 其他异常（如数据库错误）向上传播
        else:
            # 条件查询
            conditions = [expr.to_condition() for expr in self._where_clauses]
            records = storage.query(table_name, conditions)

            count = 0
            for record in records:
                # 获取主键或 rowid
                if pk_name:
                    pk = record[pk_name]
                else:
                    # 无主键模型：使用内部 rowid
                    pk = record.get(PSEUDO_PK_NAME)
                    if pk is None:
                        raise QueryError(
                            "Cannot delete record without primary key or rowid",
                            details={'table': table_name}
                        )
                storage.delete(table_name, pk)
                count += 1

            return count


# ==================== 顶层工厂函数 ====================

def select(model_class: Type[T]) -> Select[T]:
    """创建 SELECT 语句"""
    return Select(model_class)


def insert(model_class: Type[T]) -> Insert[T]:
    """创建 INSERT 语句"""
    return Insert(model_class)


def update(model_class: Type[T]) -> Update[T]:
    """创建 UPDATE 语句"""
    return Update(model_class)


def delete(model_class: Type[T]) -> Delete[T]:
    """创建 DELETE 语句"""
    return Delete(model_class)
