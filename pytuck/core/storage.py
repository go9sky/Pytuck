"""
Pytuck 存储引擎

提供数据存储和查询功能
"""

import copy
from pathlib import Path
from typing import Any, Dict, List, Iterator, Tuple, Optional, Generator, TYPE_CHECKING
from contextlib import contextmanager

from ..common.options import BackendOptions
from .orm import Column
from .index import HashIndex
from ..query import Condition
from ..common.exceptions import (
    TableNotFoundError,
    RecordNotFoundError,
    DuplicateKeyError,
    ColumnNotFoundError,
    TransactionError
)

if TYPE_CHECKING:
    from ..backends.base import StorageBackend
    from ..backends.binary_backend import BinaryBackend


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

    def __init__(
        self,
        name: str,
        columns: List[Column],
        primary_key: str = 'id',
        comment: Optional[str] = None
    ):
        """
        初始化表

        Args:
            name: 表名
            columns: 列定义列表
            primary_key: 主键字段名
            comment: 表备注/注释
        """
        self.name = name
        self.columns: Dict[str, Column] = {col.name: col for col in columns}
        self.primary_key = primary_key
        self.comment = comment
        self.data: Dict[Any, Dict[str, Any]] = {}  # {pk: record}
        self.indexes: Dict[str, HashIndex] = {}  # {column_name: HashIndex}
        self.next_id = 1

        # 懒加载支持
        self._pk_offsets: Optional[Dict[Any, int]] = None  # {pk: file_offset}
        self._data_file: Optional[Path] = None  # 数据文件路径
        self._backend: Optional[Any] = None  # Binary 后端引用（用于读取记录）
        self._lazy_loaded: bool = False  # 是否为懒加载模式

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
        获取记录（支持懒加载）

        Args:
            pk: 主键值

        Returns:
            记录字典

        Raises:
            RecordNotFoundError: 记录不存在
        """
        # 已加载的数据直接返回
        if pk in self.data:
            return self.data[pk].copy()

        # 懒加载模式：从文件读取
        if self._lazy_loaded and self._pk_offsets is not None:
            if pk not in self._pk_offsets:
                raise RecordNotFoundError(self.name, pk)

            # 从文件读取记录
            record = self._read_record_from_file(pk)
            return record

        raise RecordNotFoundError(self.name, pk)

    def _read_record_from_file(self, pk: Any) -> Dict[str, Any]:
        """
        从文件读取单条记录（懒加载模式）

        Args:
            pk: 主键值

        Returns:
            记录字典
        """
        if self._backend is None or self._pk_offsets is None:
            raise RecordNotFoundError(self.name, pk)

        offset = self._pk_offsets[pk]

        if self._data_file is None:
            raise RecordNotFoundError(self.name, pk)
        with open(self._data_file, 'rb') as f:
            f.seek(offset)
            # 使用 backend 的 _read_record 方法读取记录
            _, record = self._backend._read_record(f, self.columns)

        return record

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
        engine: str = 'binary',
        auto_flush: bool = False,
        backend_options: Optional[BackendOptions] = None,
    ):
        """
        初始化存储引擎

        Args:
            file_path: 数据文件路径（None表示纯内存）
            in_memory: 是否纯内存模式
            engine: 后端引擎名称（'binary', 'json', 'csv', 'sqlite', 'excel', 'xml'）
            auto_flush: 是否自动刷新到磁盘
            backend_options: 强类型的后端配置选项对象（JsonBackendOptions, CsvBackendOptions等）
        """
        self.file_path = file_path
        self.in_memory: bool = in_memory or (file_path is None)
        self.engine_name = engine
        self.auto_flush = auto_flush
        self.tables: Dict[str, Table] = {}
        self._dirty = False

        # 事务管理属性
        self._in_transaction: bool = False
        self._transaction_snapshot: Optional[TransactionSnapshot] = None
        self._transaction_dirty_flag: bool = False

        # WAL 相关属性
        self._use_wal: bool = False  # 是否启用 WAL 模式
        self._wal_threshold: int = 1000  # WAL 条目数阈值，超过则自动 checkpoint
        self._wal_entry_count: int = 0  # 当前 WAL 条目数

        # 初始化后端
        self.backend: Optional[StorageBackend] = None
        if not self.in_memory and file_path:
            # 如果没有提供选项，使用默认选项
            if backend_options is None:
                from ..common.options import get_default_backend_options
                backend_options = get_default_backend_options(engine)

            from ..backends import get_backend
            self.backend = get_backend(engine, file_path, backend_options)

            # 如果文件存在，自动加载
            if self.backend.exists():
                self.tables = self.backend.load()
                self._dirty = False

                # 对于 binary 引擎，检查是否为 v4 格式并回放 WAL
                if engine == 'binary':
                    self._init_wal_mode()

    def create_table(
        self,
        name: str,
        columns: List[Column],
        comment: Optional[str] = None
    ) -> None:
        """
        创建表

        Args:
            name: 表名
            columns: 列定义列表
            comment: 表备注/注释

        Raises:
            ValueError: 表已存在
        """
        if name in self.tables:
            # 表已存在，跳过
            return

        # 查找主键
        primary_key = 'id'
        has_pk_column = False
        for col in columns:
            if col.primary_key:
                primary_key = col.name
                has_pk_column = True
                break

        # 如果没有定义主键列，自动添加默认的 id 列
        if not has_pk_column:
            id_column = Column('id', int, primary_key=True)
            columns = [id_column] + list(columns)

        table = Table(name, columns, primary_key, comment)
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

        # 使用 WAL 模式时，写入 WAL
        if self._use_wal:
            # 获取完整记录（包含自动生成的主键）
            record = table.data.get(pk, data)
            self._write_wal(1, table_name, pk, record, table.columns)  # 1 = INSERT
        elif self.auto_flush:
            # 非 WAL 模式：自动刷新到磁盘（如果启用）
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

        # 使用 WAL 模式时，写入 WAL
        if self._use_wal:
            # 获取更新后的完整记录
            record = table.data.get(pk)
            if record:
                self._write_wal(2, table_name, pk, record, table.columns)  # 2 = UPDATE
        elif self.auto_flush:
            self.flush()

    def delete(self, table_name: str, pk: Any) -> None:
        """
        删除记录

        Args:
            table_name: 表名
            pk: 主键值
        """
        table = self.get_table(table_name)

        # 先记录列信息（WAL 需要）
        columns = table.columns if self._use_wal else None

        table.delete(pk)
        self._dirty = True

        # 使用 WAL 模式时，写入 WAL
        if self._use_wal and columns:
            self._write_wal(3, table_name, pk)  # 3 = DELETE
        elif self.auto_flush:
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

    def query(self,
              table_name: str,
              conditions: List[Condition],
              limit: Optional[int] = None,
              offset: int = 0,
              order_by: Optional[str] = None,
              order_desc: bool = False) -> List[Dict[str, Any]]:
        """
        查询多条记录

        Args:
            table_name: 表名
            conditions: 查询条件列表
            limit: 限制返回记录数（None 表示无限制）
            offset: 跳过的记录数
            order_by: 排序字段名
            order_desc: 是否降序排列

        Returns:
            记录字典列表
        """
        table = self.get_table(table_name)

        # 优化：使用多索引联合查询（取所有匹配索引结果的交集）
        candidate_pks = None
        remaining_conditions = []

        for condition in conditions:
            if condition.operator == '=' and condition.field in table.indexes:
                # 使用索引查询
                index = table.indexes[condition.field]
                pks = index.lookup(condition.value)

                if candidate_pks is None:
                    candidate_pks = pks
                else:
                    # 取交集，缩小候选集
                    candidate_pks = candidate_pks.intersection(pks)
            else:
                # 无索引的条件保留后续过滤
                remaining_conditions.append(condition)

        # 如果没有使用索引，全表扫描（需要评估所有条件）
        if candidate_pks is None:
            candidate_pks = set(table.data.keys())
            remaining_conditions = conditions  # 没有索引时，所有条件都需要评估

        # 过滤记录（只需评估未使用索引的条件）
        results = []
        for pk in candidate_pks:
            if pk in table.data:
                record = table.data[pk]
                # 评估剩余条件（索引已匹配的条件无需再次评估）
                if all(cond.evaluate(record) for cond in remaining_conditions):
                    results.append(record.copy())

        # 排序
        if order_by and order_by in table.columns:
            def sort_key(record):
                value = record.get(order_by)
                # 处理 None 值，将其排在最后
                if value is None:
                    return (1, 0) if not order_desc else (0, 0)
                return (0, value) if not order_desc else (1, value)

            try:
                results.sort(key=sort_key, reverse=order_desc)
            except TypeError:
                # 如果比较失败（比如混合类型），按字符串排序
                results.sort(key=lambda r: str(r.get(order_by, '')), reverse=order_desc)

        # 分页
        if offset > 0:
            results = results[offset:]
        if limit is not None and limit > 0:
            results = results[:limit]

        return results

    def query_table_data(self,
                        table_name: str,
                        limit: Optional[int] = None,
                        offset: int = 0,
                        order_by: Optional[str] = None,
                        order_desc: bool = False,
                        filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        查询表数据（专为 Web UI 设计）

        Args:
            table_name: 表名
            limit: 限制返回记录数
            offset: 跳过的记录数
            order_by: 排序字段名
            order_desc: 是否降序排列
            filters: 过滤条件字典 {field: value}

        Returns:
            {
                'records': List[Dict[str, Any]],  # 实际数据行
                'total_count': int,               # 总记录数（应用过滤后）
                'has_more': bool,                 # 是否还有更多数据
                'schema': List[Dict],             # 列结构信息
            }
        """
        if table_name not in self.tables:
            raise TableNotFoundError(f"Table '{table_name}' not found")

        table = self.get_table(table_name)

        # 尝试使用后端分页（如果支持）
        if self.backend and self.backend.supports_server_side_pagination():

            # 转换过滤条件为简化格式
            backend_conditions: List[Dict[str, Any]] = []
            if filters:
                for field, value in filters.items():
                    if field in table.columns:
                        backend_conditions.append({'field': field, 'operator': '=', 'value': value})

            try:
                # 使用后端分页
                result = self.backend.query_with_pagination(
                    table_name=table_name,
                    conditions=backend_conditions,
                    limit=limit,
                    offset=offset,
                    order_by=order_by,
                    order_desc=order_desc
                )

                # 获取表结构信息
                schema = [col.to_dict() for col in table.columns.values()]

                return {
                    'records': result.get('records', []),
                    'total_count': result.get('total_count', 0),
                    'has_more': result.get('has_more', False),
                    'schema': schema
                }
            except NotImplementedError:
                # 后端不支持，回退到内存分页
                pass

        # 使用内存分页（默认方式）
        # 构建查询条件
        conditions: List[Condition] = []
        if filters:
            for field, value in filters.items():
                if field in table.columns:
                    conditions.append(Condition(field, '=', value))

        # 先查询总数（不分页）
        total_records = self.query(table_name, conditions)
        total_count = len(total_records)

        # 再进行分页查询
        records = self.query(
            table_name=table_name,
            conditions=conditions,
            limit=limit,
            offset=offset,
            order_by=order_by,
            order_desc=order_desc
        )

        # 获取表结构信息
        schema = [col.to_dict() for col in table.columns.values()]

        # 判断是否还有更多数据
        has_more = False
        if limit is not None:
            has_more = (offset + len(records)) < total_count

        return {
            'records': records,
            'total_count': total_count,
            'has_more': has_more,
            'schema': schema
        }

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

    def _init_wal_mode(self) -> None:
        """
        初始化 WAL 模式

        检查是否为 v4 格式的 binary 文件，如果是则启用 WAL 模式并回放未提交的 WAL。
        """
        from ..backends.binary_backend import BinaryBackend

        if not isinstance(self.backend, BinaryBackend):
            return

        backend: 'BinaryBackend' = self.backend

        # 检查是否有活跃的 v4 header
        if backend._active_header is not None:
            self._use_wal = True

            # 回放未提交的 WAL
            if backend.has_pending_wal():
                count = backend.replay_wal(self.tables)
                if count > 0:
                    self._dirty = True

    def _get_binary_backend(self) -> Optional['BinaryBackend']:
        """获取 binary 后端（如果是的话）"""
        from ..backends.binary_backend import BinaryBackend

        if isinstance(self.backend, BinaryBackend):
            return self.backend
        return None

    def _write_wal(
        self,
        op_type: int,
        table_name: str,
        pk: Any,
        record: Optional[Dict[str, Any]] = None,
        columns: Optional[Dict[str, 'Column']] = None
    ) -> bool:
        """
        写入 WAL 条目

        Args:
            op_type: 操作类型 (1=INSERT, 2=UPDATE, 3=DELETE)
            table_name: 表名
            pk: 主键值
            record: 记录数据
            columns: 列定义

        Returns:
            是否成功写入 WAL
        """
        if not self._use_wal:
            return False

        backend = self._get_binary_backend()
        if backend is None:
            return False

        from ..backends.binary_backend import WALOpType

        # 转换操作类型
        wal_op = WALOpType(op_type)

        # 写入 WAL
        backend.append_wal_entry(wal_op, table_name, pk, record, columns)
        self._wal_entry_count += 1

        # 检查是否需要自动 checkpoint
        if self._wal_entry_count >= self._wal_threshold:
            self._checkpoint()

        return True

    def _checkpoint(self) -> None:
        """执行 checkpoint，将内存数据写入磁盘并清空 WAL"""
        if self.backend:
            self.backend.save(self.tables)
            self._wal_entry_count = 0
            self._dirty = False

    def flush(self) -> None:
        """强制写入磁盘"""
        if self.backend and self._dirty:
            self.backend.save(self.tables)
            self._dirty = False
            # 重置 WAL 计数器（checkpoint 会清空 WAL）
            self._wal_entry_count = 0

            # 首次保存 binary 引擎后，启用 WAL 模式
            if self.engine_name == 'binary' and not self._use_wal:
                self._init_wal_mode()

    def close(self) -> None:
        """关闭数据库"""
        self.flush()

    def __repr__(self) -> str:
        return f"Storage(tables={len(self.tables)}, in_memory={self.in_memory})"
