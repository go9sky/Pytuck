"""
Pytuck 查询构建器

提供链式查询API
"""

from typing import Any, List, Optional, Type, TYPE_CHECKING, Union

if TYPE_CHECKING:
    from .orm import PureBaseModel, Column
    from .storage import Storage


class Condition:
    """查询条件"""

    def __init__(self, field: str, operator: str, value: Any):
        """
        初始化条件

        Args:
            field: 字段名
            operator: 操作符 ('=', '>', '<', '>=', '<=', '!=', 'IN')
            value: 比较值
        """
        self.field = field
        self.operator = operator
        self.value = value

    def evaluate(self, record: dict) -> bool:
        """
        评估条件是否满足

        Args:
            record: 记录字典

        Returns:
            条件是否满足
        """
        if self.field not in record:
            return False

        field_value = record[self.field]

        if self.operator == '=':
            return field_value == self.value
        elif self.operator == '>':
            return field_value > self.value
        elif self.operator == '<':
            return field_value < self.value
        elif self.operator == '>=':
            return field_value >= self.value
        elif self.operator == '<=':
            return field_value <= self.value
        elif self.operator == '!=':
            return field_value != self.value
        elif self.operator == 'IN':
            return field_value in self.value
        else:
            raise ValueError(f"Unsupported operator: {self.operator}")

    def __repr__(self) -> str:
        return f"Condition({self.field} {self.operator} {self.value})"


class BinaryExpression:
    """
    二元表达式：表示 Column 和值之间的比较操作

    由 Column 的魔术方法返回，用于构建查询条件。
    例如：Student.age >= 18 会创建 BinaryExpression(Student.age, '>=', 18)
    """

    def __init__(self, column: 'Column', operator: str, value: Any):
        """
        初始化二元表达式

        Args:
            column: Column 对象
            operator: 操作符 ('=', '>', '<', '>=', '<=', '!=', 'IN')
            value: 比较值
        """
        self.column = column
        self.operator = operator
        self.value = value

    def to_condition(self) -> Condition:
        """转换为 Condition 对象"""
        return Condition(self.column.name, self.operator, self.value)

    def __repr__(self) -> str:
        return f"BinaryExpression({self.column.name} {self.operator} {self.value})"


class Query:
    """查询构建器（支持链式调用）"""

    def __init__(self, model_class: Type['PureBaseModel'], storage: Optional['Storage'] = None):
        """
        初始化查询构建器

        Args:
            model_class: 模型类
            storage: Storage 实例（新 API 需要，旧 API 兼容）
        """
        self.model_class = model_class
        self.storage = storage  # 新 API：通过参数传入
        self._conditions: List[Condition] = []
        self._order_by_field: Optional[str] = None
        self._order_desc: bool = False
        self._limit_value: Optional[int] = None
        self._offset_value: int = 0

    def filter(self, *expressions: BinaryExpression) -> 'Query':
        """
        添加过滤条件（只支持表达式语法）

        用法：
            query.filter(Student.age >= 20, Student.name == 'Alice')

        Args:
            *expressions: BinaryExpression 对象

        Returns:
            Query 对象（链式调用）

        Example:
            # 单条件
            query.filter(Student.age >= 20)

            # 多条件（AND）
            query.filter(Student.age >= 20, Student.name == 'Alice')

            # 链式调用
            query.filter(Student.age >= 20).filter(Student.score > 85).all()
        """
        # 只处理 BinaryExpression 对象
        for expr in expressions:
            if isinstance(expr, BinaryExpression):
                condition = expr.to_condition()
                self._conditions.append(condition)
            else:
                raise TypeError(
                    f"Expected BinaryExpression, got {type(expr).__name__}. "
                    f"Use Model.column >= value syntax."
                )

        return self

    def filter_by(self, **kwargs) -> 'Query':
        """
        添加过滤条件（简单等值查询，SQLAlchemy 风格）

        用于简单的等值匹配，语法更简洁。对于复杂查询，使用 filter() 配合表达式。

        Args:
            **kwargs: 字段名=值 的等值条件

        Returns:
            Query 对象（链式调用）

        Example:
            # 简单等值查询（推荐 filter_by）
            query.filter_by(name='Bob', active=True)

            # 复杂表达式查询（使用 filter）
            query.filter(Student.age >= 20, Student.name != 'Alice')
        """
        for field, value in kwargs.items():
            # 仅支持等值条件
            condition = Condition(field, '=', value)
            self._conditions.append(condition)
        return self

    def order_by(self, field: str, desc: bool = False) -> 'Query':
        """
        排序

        Args:
            field: 排序字段
            desc: 是否降序

        Returns:
            查询构建器（链式调用）
        """
        self._order_by_field = field
        self._order_desc = desc
        return self

    def limit(self, n: int) -> 'Query':
        """
        限制返回数量

        Args:
            n: 限制数量

        Returns:
            查询构建器（链式调用）
        """
        self._limit_value = n
        return self

    def offset(self, n: int) -> 'Query':
        """
        偏移

        Args:
            n: 偏移量

        Returns:
            查询构建器（链式调用）
        """
        self._offset_value = n
        return self

    def first(self) -> Optional['PureBaseModel']:
        """
        返回第一条记录

        Returns:
            模型实例或None
        """
        original_limit = self._limit_value
        self._limit_value = 1

        results = self.all()

        self._limit_value = original_limit

        return results[0] if results else None

    def all(self) -> List['PureBaseModel']:
        """
        执行查询并返回所有结果

        Returns:
            模型实例列表
        """
        records = self._execute()

        # 获取主键名（支持新旧两种风格）
        pk_name = (
            getattr(self.model_class, '__primary_key__', None) or
            getattr(self.model_class, '_primary_key', 'id')
        )

        # 转换为模型实例
        instances = []
        for record in records:
            instance = self.model_class(**record)

            # 兼容旧 API 的属性
            if hasattr(instance, '_loaded_from_db'):
                instance._loaded_from_db = True
            if hasattr(instance, '_pk_value'):
                instance._pk_value = record.get(pk_name)

            instances.append(instance)

        return instances

    def count(self) -> int:
        """
        返回满足条件的记录数

        Returns:
            记录数
        """
        records = self._execute()
        return len(records)

    def _execute(self) -> List[dict]:
        """
        执行查询（内部方法）

        Returns:
            记录字典列表
        """
        # 获取 storage 实例（新 API 优先，兼容旧 API）
        storage: Optional['Storage'] = (
            self.storage or
            getattr(self.model_class, '__storage__', None) or
            getattr(self.model_class, '_db', None)
        )

        if not storage:
            raise ValueError(f"No database configured for {self.model_class.__name__}")

        # 获取表名（支持新旧两种风格）
        table_name: Optional[str] = (
            getattr(self.model_class, '__tablename__', None) or
            getattr(self.model_class, '_table_name', None)
        )

        if not table_name:
            raise ValueError(f"No table name defined for {self.model_class.__name__}")

        # 从存储引擎查询
        records: List[dict] = storage.query(table_name, self._conditions)

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

    def __repr__(self) -> str:
        return f"Query({self.model_class.__name__}, conditions={len(self._conditions)})"
