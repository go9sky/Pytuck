"""
Result - 查询结果包装器

提供 SQLAlchemy 2.0 风格的结果处理接口
"""

from typing import Any, Dict, List, Optional, Type, Union, TYPE_CHECKING

if TYPE_CHECKING:
    from .orm import PureBaseModel


class Row:
    """
    Row object representing a single database record.

    Provides multiple access patterns for record data:
    - Index access: row[0], row[1]
    - Field name access: row['name'], row['age']
    - Attribute access: row.name, row.age

    Example:
        result = session.execute(stmt)
        row = result.first()
        print(row.name)       # Attribute access
        print(row['name'])    # Key access
        print(row[0])         # Index access

    Attributes:
        _data: The underlying record dictionary
        _model_class: The model class this row represents
    """

    def __init__(self, data: Dict[str, Any], model_class: Type['PureBaseModel']):
        self._data = data
        self._model_class = model_class

    def __getitem__(self, key: Union[int, str]) -> Any:
        """支持索引和字段名访问"""
        if isinstance(key, int):
            # 索引访问：row[0]
            return list(self._data.values())[key]
        else:
            # 字段名访问：row['name']
            return self._data[key]

    def __getattr__(self, name: str) -> Any:
        """支持属性访问：row.name"""
        if name.startswith('_'):
            raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")
        return self._data.get(name)

    def _asdict(self) -> Dict[str, Any]:
        """转换为字典"""
        return self._data.copy()

    def __repr__(self) -> str:
        return f"Row({self._data})"


class ScalarResult:
    """
    Scalar result for accessing query results as model instances.

    Returned by Result.scalars(), provides methods to retrieve
    query results as model instances rather than raw Row objects.

    Example:
        result = session.execute(stmt)
        users = result.scalars().all()    # List of User instances
        user = result.scalars().first()   # Single User or None
        user = result.scalars().one()     # Single User, raises if not exactly one

    Attributes:
        _records: List of record dictionaries
        _model_class: The model class to instantiate
    """

    def __init__(self, records: List[Dict[str, Any]], model_class: Type['PureBaseModel']):
        self._records = records
        self._model_class = model_class

    def all(self) -> List['PureBaseModel']:
        """返回所有模型实例"""
        instances: List['PureBaseModel'] = []
        for record in self._records:
            instance = self._model_class(**record)
            instances.append(instance)
        return instances

    def first(self) -> Optional['PureBaseModel']:
        """返回第一个模型实例"""
        if not self._records:
            return None
        return self._model_class(**self._records[0])

    def one(self) -> 'PureBaseModel':
        """返回唯一的模型实例（必须恰好一条）"""
        if len(self._records) == 0:
            raise ValueError("Expected one result, got 0")
        if len(self._records) > 1:
            raise ValueError(f"Expected one result, got {len(self._records)}")
        return self._model_class(**self._records[0])

    def one_or_none(self) -> Optional['PureBaseModel']:
        """返回唯一的模型实例或 None（最多一条）"""
        if len(self._records) == 0:
            return None
        if len(self._records) > 1:
            raise ValueError(f"Expected at most one result, got {len(self._records)}")
        return self._model_class(**self._records[0])


class Result:
    """
    Query result wrapper for SELECT operations.

    Provides SQLAlchemy 2.0 style result handling with multiple access methods:
    - scalars(): Get results as model instances
    - all(): Get all results as Row objects
    - first(): Get first result as Row
    - one(): Get exactly one result (raises if 0 or >1)
    - fetchall(): Get raw dictionary list

    Example:
        result = session.execute(select(User).where(User.age >= 18))

        # As model instances
        users = result.scalars().all()

        # As Row objects
        rows = result.all()

        # As dictionaries
        dicts = result.fetchall()

    Attributes:
        _records: List of record dictionaries from query
        _model_class: The model class for this result
        _operation: Operation type ('select', 'insert', 'update', 'delete')
    """

    def __init__(self, records: List[Dict[str, Any]], model_class: Type['PureBaseModel'], operation: str = 'select'):
        """
        Args:
            records: 查询结果（字典列表）
            model_class: 模型类
            operation: 操作类型 ('select', 'insert', 'update', 'delete')
        """
        self._records = records
        self._model_class = model_class
        self._operation = operation

    def scalars(self) -> ScalarResult:
        """返回标量结果（模型实例）"""
        return ScalarResult(self._records, self._model_class)

    def all(self) -> List[Row]:
        """返回所有 Row 对象"""
        return [Row(record, self._model_class) for record in self._records]

    def first(self) -> Optional[Row]:
        """返回第一个 Row 对象"""
        if not self._records:
            return None
        return Row(self._records[0], self._model_class)

    def one(self) -> Row:
        """返回唯一的 Row 对象（必须恰好一条）"""
        if len(self._records) == 0:
            raise ValueError("Expected one result, got 0")
        if len(self._records) > 1:
            raise ValueError(f"Expected one result, got {len(self._records)}")
        return Row(self._records[0], self._model_class)

    def fetchall(self) -> List[Dict[str, Any]]:
        """返回字典列表"""
        return self._records.copy()

    def rowcount(self) -> int:
        """返回受影响的行数（用于 INSERT/UPDATE/DELETE）"""
        if self._operation == 'select':
            return len(self._records)
        # 对于 CUD 操作，_records 实际存储的是受影响的行数
        return self._records if isinstance(self._records, int) else 0


class CursorResult(Result):
    """
    Result wrapper for CUD (Create/Update/Delete) operations.

    Unlike Result which wraps SELECT queries, CursorResult is returned
    for INSERT, UPDATE, and DELETE operations. It provides:
    - rowcount(): Number of affected rows
    - inserted_primary_key: The primary key of inserted record (INSERT only)

    Note: Methods like scalars(), all(), first() will raise NotImplementedError
    since CUD operations don't return record data.

    Example:
        # INSERT
        result = session.execute(insert(User).values(name='Alice'))
        new_id = result.inserted_primary_key

        # UPDATE/DELETE
        result = session.execute(update(User).where(...).values(...))
        affected = result.rowcount()

    Attributes:
        _affected_rows: Number of rows affected by the operation
        _inserted_pk: Primary key of inserted record (INSERT only)
    """

    def __init__(self, affected_rows: int, model_class: Type['PureBaseModel'], operation: str, inserted_pk: Any = None):
        """
        Args:
            affected_rows: 受影响的行数
            model_class: 模型类
            operation: 操作类型
            inserted_pk: 插入的主键（仅 INSERT）
        """
        super().__init__([], model_class, operation)
        self._affected_rows = affected_rows
        self._inserted_pk = inserted_pk

    def rowcount(self) -> int:
        """返回受影响的行数"""
        return self._affected_rows

    @property
    def inserted_primary_key(self) -> Any:
        """返回插入的主键（仅 INSERT）"""
        return self._inserted_pk

    def scalars(self) -> ScalarResult:
        raise NotImplementedError(f"scalars() not supported for {self._operation} operation")

    def all(self) -> List[Row]:
        raise NotImplementedError(f"all() not supported for {self._operation} operation")

    def first(self) -> Optional[Row]:
        raise NotImplementedError(f"first() not supported for {self._operation} operation")
