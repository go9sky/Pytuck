"""
Pytuck 存储引擎

提供数据存储和查询功能
"""

import copy
from typing import Any, Dict, List, Iterator, Tuple, Optional, Generator, TYPE_CHECKING
from contextlib import contextmanager

from .orm import Column
from .index import HashIndex
from .query import Condition
from .exceptions import (
    TableNotFoundError,
    RecordNotFoundError,
    DuplicateKeyError,
    ColumnNotFoundError,
    TransactionError
)

if TYPE_CHECKING:
    from .backends.base import StorageBackend


class TransactionSnapshot:
    """
    事务快照类

    用于存储事务开始时的数据状态，支持回滚操作。
    采用深拷贝策略确保数据隔离。
    """

    def __init__(self, tables: Dict[str, 'Table']):
        """
        创建快照

        Args:
            tables: 当前所有表的字典 {table_name: Table}
        """
        self.table_snapshots: Dict[str, dict] = {}

        # 深拷贝所有表的关键状态
        for table_name, table in tables.items():
            self.table_snapshots[table_name] = {
                'data': copy.deepcopy(table.data),
                'indexes': copy.deepcopy(table.indexes),
                'next_id': table.next_id
            }

    def restore(self, tables: Dict[str, 'Table']) -> None:
        """
        恢复快照到表对象

        Args:
            tables: 要恢复的表字典
        """
        for table_name, snapshot in self.table_snapshots.items():
            if table_name in tables:
                table = tables[table_name]
                # 直接替换引用（快照已经是深拷贝）
                table.data = snapshot['data']
                table.indexes = snapshot['indexes']
                table.next_id = snapshot['next_id']


class Table:
    """表管理"""

    def __init__(self, name: str, columns: List[Column], primary_key: str = 'id'):
        """
        初始化表

        Args:
            name: 表名
            columns: 列定义列表
            primary_key: 主键字段名
        """
        self.name = name
        self.columns: Dict[str, Column] = {col.name: col for col in columns}
        self.primary_key = primary_key
        self.data: Dict[Any, Dict[str, Any]] = {}  # {pk: record}
        self.indexes: Dict[str, HashIndex] = {}  # {column_name: HashIndex}
        self.next_id = 1

        # 自动为标记了index的列创建索引
        for col in columns:
            if col.index:
                self.build_index(col.name)

    def insert(self, record: Dict[str, Any]) -> Any:
        """
        插入记录

        Args:
            record: 记录字典

        Returns:
            主键值

        Raises:
            DuplicateKeyError: 主键重复
        """
        # 处理主键
        pk = record.get(self.primary_key)
        if pk is None:
            # 自动生成主键（仅支持int类型）
            if self.primary_key in self.columns:
                pk_column = self.columns[self.primary_key]
                if pk_column.col_type == int:
                    pk = self.next_id
                    self.next_id += 1
                    record[self.primary_key] = pk
                else:
                    raise ValueError(f"Primary key '{self.primary_key}' must be provided")
        else:
            # 检查主键是否已存在
            if pk in self.data:
                raise DuplicateKeyError(self.name, pk)

        # 验证和处理所有字段
        validated_record = {}
        for col_name, column in self.columns.items():
            value = record.get(col_name)
            validated_value = column.validate(value)
            validated_record[col_name] = validated_value

        # 存储记录
        self.data[pk] = validated_record

        # 更新索引
        for col_name, index in self.indexes.items():
            value = validated_record.get(col_name)
            if value is not None:
                index.insert(value, pk)

        # 更新next_id
        if isinstance(pk, int) and pk >= self.next_id:
            self.next_id = pk + 1

        return pk

    def update(self, pk: Any, record: Dict[str, Any]) -> None:
        """
        更新记录

        Args:
            pk: 主键值
            record: 新数据

        Raises:
            RecordNotFoundError: 记录不存在
        """
        if pk not in self.data:
            raise RecordNotFoundError(self.name, pk)

        old_record = self.data[pk]

        # 验证和处理字段
        validated_record = old_record.copy()
        for col_name, value in record.items():
            if col_name in self.columns:
                column = self.columns[col_name]
                validated_record[col_name] = column.validate(value)

        # 更新索引（先删除旧值，再插入新值）
        for col_name, index in self.indexes.items():
            old_value = old_record.get(col_name)
            new_value = validated_record.get(col_name)

            if old_value != new_value:
                if old_value is not None:
                    index.remove(old_value, pk)
                if new_value is not None:
                    index.insert(new_value, pk)

        # 存储记录
        self.data[pk] = validated_record

    def delete(self, pk: Any) -> None:
        """
        删除记录

        Args:
            pk: 主键值

        Raises:
            RecordNotFoundError: 记录不存在
        """
        if pk not in self.data:
            raise RecordNotFoundError(self.name, pk)

        record = self.data[pk]

        # 更新索引
        for col_name, index in self.indexes.items():
            value = record.get(col_name)
            if value is not None:
                index.remove(value, pk)

        # 删除记录
        del self.data[pk]

    def get(self, pk: Any) -> Dict[str, Any]:
        """
        获取记录

        Args:
            pk: 主键值

        Returns:
            记录字典

        Raises:
            RecordNotFoundError: 记录不存在
        """
        if pk not in self.data:
            raise RecordNotFoundError(self.name, pk)

        return self.data[pk].copy()

    def scan(self) -> Iterator[Tuple[Any, Dict[str, Any]]]:
        """
        扫描所有记录

        Yields:
            (主键, 记录字典)
        """
        for pk, record in self.data.items():
            yield pk, record.copy()

    def build_index(self, column_name: str) -> None:
        """
        为列创建索引

        Args:
            column_name: 列名

        Raises:
            ColumnNotFoundError: 列不存在
        """
        if column_name not in self.columns:
            raise ColumnNotFoundError(self.name, column_name)

        if column_name in self.indexes:
            # 索引已存在
            return

        # 创建索引
        index = HashIndex(column_name)

        # 为现有数据建立索引
        for pk, record in self.data.items():
            value = record.get(column_name)
            if value is not None:
                index.insert(value, pk)

        self.indexes[column_name] = index

    def __repr__(self) -> str:
        return f"Table(name='{self.name}', records={len(self.data)}, indexes={len(self.indexes)})"


class Storage:
    """存储引擎"""

    def __init__(
        self,
        file_path: Optional[str] = None,
        in_memory: bool = False,
        engine: str = 'binary',  # 新增：引擎选择
        auto_flush: bool = False,  # 新增：自动刷新
        **backend_options  # 新增：后端特定选项
    ):
        """
        初始化存储引擎

        Args:
            file_path: 数据文件路径（None表示纯内存）
            in_memory: 是否纯内存模式
            engine: 后端引擎名称（'binary', 'json', 'csv', 'sqlite', 'excel', 'xml'）
            auto_flush: 是否自动刷新到磁盘
            **backend_options: 传递给后端的额外选项
                - binary: 无特殊选项
                - json: indent=2 (美化输出)
                - csv: encoding='utf-8'
                - sqlite: check_same_thread=False
        """
        self.file_path = file_path
        self.in_memory = in_memory or (file_path is None)
        self.engine_name = engine
        self.auto_flush = auto_flush
        self.tables: Dict[str, Table] = {}
        self.current_transaction = None
        self._dirty = False

        # 事务管理属性
        self._in_transaction: bool = False
        self._transaction_snapshot: Optional[TransactionSnapshot] = None
        self._transaction_dirty_flag: bool = False

        # 初始化后端
        self.backend = None
        if not self.in_memory and file_path:
            from .backends import get_backend
            self.backend = get_backend(engine, file_path, **backend_options)

            # 如果文件存在，自动加载
            if self.backend.exists():
                self.tables = self.backend.load()
                self._dirty = False

    def create_table(self, name: str, columns: List[Column]) -> None:
        """
        创建表

        Args:
            name: 表名
            columns: 列定义列表

        Raises:
            ValueError: 表已存在
        """
        if name in self.tables:
            # 表已存在，跳过
            return

        # 查找主键
        primary_key = 'id'
        for col in columns:
            if col.primary_key:
                primary_key = col.name
                break

        table = Table(name, columns, primary_key)
        self.tables[name] = table
        self._dirty = True

        if self.auto_flush:
            self.flush()

    def drop_table(self, name: str) -> None:
        """
        删除表

        Args:
            name: 表名

        Raises:
            TableNotFoundError: 表不存在
        """
        if name not in self.tables:
            raise TableNotFoundError(name)

        del self.tables[name]
        self._dirty = True

        if self.auto_flush:
            self.flush()

    def get_table(self, name: str) -> Table:
        """
        获取表

        Args:
            name: 表名

        Returns:
            表对象

        Raises:
            TableNotFoundError: 表不存在
        """
        if name not in self.tables:
            raise TableNotFoundError(name)

        return self.tables[name]

    def insert(self, table_name: str, data: Dict[str, Any]) -> Any:
        """
        插入记录

        Args:
            table_name: 表名
            data: 数据字典

        Returns:
            主键值
        """
        table = self.get_table(table_name)
        pk = table.insert(data)
        self._dirty = True

        # 自动刷新到磁盘（如果启用）
        if self.auto_flush:
            self.flush()

        return pk

    def update(self, table_name: str, pk: Any, data: Dict[str, Any]) -> None:
        """
        更新记录

        Args:
            table_name: 表名
            pk: 主键值
            data: 新数据
        """
        table = self.get_table(table_name)
        table.update(pk, data)
        self._dirty = True

        if self.auto_flush:
            self.flush()

    def delete(self, table_name: str, pk: Any) -> None:
        """
        删除记录

        Args:
            table_name: 表名
            pk: 主键值
        """
        table = self.get_table(table_name)
        table.delete(pk)
        self._dirty = True

        if self.auto_flush:
            self.flush()

    def select(self, table_name: str, pk: Any) -> Dict[str, Any]:
        """
        查询单条记录

        Args:
            table_name: 表名
            pk: 主键值

        Returns:
            记录字典
        """
        table = self.get_table(table_name)
        return table.get(pk)

    def query(self, table_name: str, conditions: List[Condition]) -> List[Dict[str, Any]]:
        """
        查询多条记录

        Args:
            table_name: 表名
            conditions: 查询条件列表

        Returns:
            记录字典列表
        """
        table = self.get_table(table_name)

        # 优化：使用索引
        candidate_pks = None

        for condition in conditions:
            if condition.operator == '=' and condition.field in table.indexes:
                # 使用索引查询
                index = table.indexes[condition.field]
                pks = index.lookup(condition.value)

                if candidate_pks is None:
                    candidate_pks = pks
                else:
                    # 取交集
                    candidate_pks = candidate_pks.intersection(pks)

                break  # 只使用一个索引（简化实现）

        # 如果没有使用索引，全表扫描
        if candidate_pks is None:
            candidate_pks = set(table.data.keys())

        # 过滤记录
        results = []
        for pk in candidate_pks:
            if pk in table.data:
                record = table.data[pk]
                # 评估所有条件
                if all(cond.evaluate(record) for cond in conditions):
                    results.append(record.copy())

        return results

    @contextmanager
    def transaction(self) -> Generator['Storage', None, None]:
        """
        事务上下文管理器

        提供内存级事务支持：
        - 自动回滚：异常时自动恢复到事务开始前的状态
        - 单层事务：不支持嵌套
        - 内存事务：事务期间禁用 auto_flush

        Example:
            with storage.transaction():
                storage.insert('users', {'name': 'Alice'})
                storage.insert('users', {'name': 'Bob'})

        Raises:
            TransactionError: 尝试嵌套事务时
        """
        # 1. 检查嵌套事务
        if self._in_transaction:
            raise TransactionError("Nested transactions are not supported")

        # 2. 进入事务状态
        self._in_transaction = True
        self._transaction_snapshot = TransactionSnapshot(self.tables)
        self._transaction_dirty_flag = self._dirty

        # 3. 临时禁用 auto_flush
        old_auto_flush = self.auto_flush
        self.auto_flush = False

        try:
            # 4. 执行事务体
            yield self

            # 5. 提交成功：恢复 auto_flush 并刷新
            if old_auto_flush:
                self.flush()

        except Exception:
            # 6. 回滚：恢复快照和状态
            if self._transaction_snapshot:
                self._transaction_snapshot.restore(self.tables)
            self._dirty = self._transaction_dirty_flag
            raise

        finally:
            # 7. 清理：恢复状态
            self.auto_flush = old_auto_flush
            self._transaction_snapshot = None
            self._in_transaction = False

    def flush(self) -> None:
        """强制写入磁盘"""
        if self.backend and self._dirty:
            self.backend.save(self.tables)
            self._dirty = False

    def close(self) -> None:
        """关闭数据库"""
        self.flush()

    def __repr__(self) -> str:
        return f"Storage(tables={len(self.tables)}, in_memory={self.in_memory})"
