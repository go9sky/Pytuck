"""
Pytuck 存储引擎

提供数据存储和查询功能
"""

import copy
from pathlib import Path
from typing import Any, Dict, List, Iterator, Tuple, Optional, Generator, Type, TYPE_CHECKING
from contextlib import contextmanager

from ..common.options import BackendOptions, SyncOptions, SyncResult
from ..common.utils import validate_sql_identifier
from .orm import Column, PSEUDO_PK_NAME
from .index import HashIndex
from ..query import Condition
from ..common.exceptions import (
    TableNotFoundError,
    RecordNotFoundError,
    DuplicateKeyError,
    ColumnNotFoundError,
    TransactionError,
    ValidationError,
    SchemaError
)

if TYPE_CHECKING:
    from ..backends.base import StorageBackend
    from ..backends.backend_binary import BinaryBackend


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
        primary_key: Optional[str] = None,
        comment: Optional[str] = None
    ):
        """
        初始化表

        Args:
            name: 表名
            columns: 列定义列表
            primary_key: 主键字段名（None 表示无主键，使用隐式 rowid）
            comment: 表备注/注释
        """
        self.name = name
        self.columns: Dict[str, Column] = {}
        for col in columns:
            assert col.name is not None, "Column name must be set"
            self.columns[col.name] = col
        self.primary_key = primary_key  # None 表示无主键
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
                assert col.name is not None, "Column name must be set"
                self.build_index(col.name)

    def insert(self, record: Dict[str, Any]) -> Any:
        """
        插入记录

        Args:
            record: 记录字典

        Returns:
            主键值（用户主键或隐式 rowid）

        Raises:
            DuplicateKeyError: 主键重复
        """
        # 处理主键
        if self.primary_key and self.primary_key in self.columns:
            # 有用户主键
            pk = record.get(self.primary_key)
            if pk is None:
                # 自动生成主键（仅支持int类型）
                pk_column = self.columns[self.primary_key]
                if pk_column.col_type == int:
                    pk = self.next_id
                    self.next_id += 1
                    record[self.primary_key] = pk
                else:
                    raise ValidationError(
                        f"Primary key '{self.primary_key}' must be provided",
                        table_name=self.name,
                        column_name=self.primary_key
                    )
            else:
                # 检查主键是否已存在
                if pk in self.data:
                    raise DuplicateKeyError(self.name, pk)
        else:
            # 无用户主键：使用内部 rowid
            pk = self.next_id
            self.next_id += 1
            # 不将 pk 写入 record（隐式主键不作为列存在）

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

        Raises:
            RecordNotFoundError: 当记录不存在时
        """
        # 内部状态检查：这些是程序错误，不是用户错误
        assert self._backend is not None, "Backend must be set for lazy loading"
        assert self._pk_offsets is not None, "PK offsets must be set for lazy loading"
        assert self._data_file is not None, "Data file must be set for lazy loading"

        # 检查 pk 是否存在（这是真正的"记录未找到"情况）
        if pk not in self._pk_offsets:
            raise RecordNotFoundError(self.name, pk)

        offset = self._pk_offsets[pk]

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

    # ========== Schema 操作方法 ==========

    def add_column(self, column: Column, default_value: Any = None) -> None:
        """
        添加列到表

        Args:
            column: 列定义
            default_value: 为现有记录填充的默认值（优先于 column.default）

        Raises:
            SchemaError: 列已存在或非空列无默认值
        """
        assert column.name is not None, "Column name must be set"
        col_name = column.name  # 创建局部变量，类型为 str

        if col_name in self.columns:
            raise SchemaError(f"Column '{col_name}' already exists in table '{self.name}'")

        # 检查非空约束：如果表中有数据，新增非空列必须有默认值
        has_data = len(self.data) > 0
        fill_value = default_value if default_value is not None else column.default

        if has_data and not column.nullable and fill_value is None:
            raise SchemaError(
                f"Cannot add non-nullable column '{col_name}' to table '{self.name}' "
                "without default value when table has existing data"
            )

        # 添加到 columns
        self.columns[col_name] = column

        # 为现有记录填充默认值
        if has_data:
            for record in self.data.values():
                if col_name not in record:
                    record[col_name] = fill_value

        # 如果需要索引，构建索引
        if column.index:
            self.build_index(col_name)

    def drop_column(self, column_name: str) -> None:
        """
        从表中删除列

        Args:
            column_name: 列名

        Raises:
            ColumnNotFoundError: 列不存在
            SchemaError: 试图删除主键列
        """
        if column_name not in self.columns:
            raise ColumnNotFoundError(self.name, column_name)
        if column_name == self.primary_key:
            raise SchemaError(f"Cannot drop primary key column '{column_name}'")

        # 从 columns 中移除
        del self.columns[column_name]

        # 从所有记录中移除该列
        for record in self.data.values():
            record.pop(column_name, None)

        # 移除索引
        if column_name in self.indexes:
            del self.indexes[column_name]

    def update_comment(self, comment: Optional[str]) -> None:
        """
        更新表备注

        Args:
            comment: 新的备注（None 表示清空）
        """
        self.comment = comment

    def update_column_comment(self, column_name: str, comment: Optional[str]) -> None:
        """
        更新列备注

        Args:
            column_name: 列名
            comment: 新的备注（None 表示清空）

        Raises:
            ColumnNotFoundError: 列不存在
        """
        if column_name not in self.columns:
            raise ColumnNotFoundError(self.name, column_name)
        self.columns[column_name].comment = comment

    def update_column_index(self, column_name: str, index: bool) -> None:
        """
        更新列的索引设置

        Args:
            column_name: 列名
            index: 是否创建索引

        Raises:
            ColumnNotFoundError: 列不存在
        """
        if column_name not in self.columns:
            raise ColumnNotFoundError(self.name, column_name)

        column = self.columns[column_name]
        old_index = column.index
        column.index = index

        if index and not old_index:
            # 需要创建索引
            self.build_index(column_name)
        elif not index and old_index:
            # 需要删除索引
            if column_name in self.indexes:
                del self.indexes[column_name]

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

        # 原生 SQL 模式相关属性
        self._native_sql_mode: bool = False  # 是否启用原生 SQL 模式
        self._connector: Optional[Any] = None  # 数据库连接器（原生 SQL 模式）

        # 模型注册表（表名 -> 模型类，用于 Relationship 解析）
        self._model_registry: Dict[str, Type] = {}

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

            # 检测并初始化原生 SQL 模式
            self._init_native_sql_mode()

    # ==================== 模型注册表方法 ====================

    def _register_model(self, table_name: str, model_cls: Type) -> None:
        """
        注册模型类（按表名）

        Args:
            table_name: 表名
            model_cls: 模型类
        """
        self._model_registry[table_name] = model_cls

    def _get_model_by_table(self, table_name: str) -> Optional[Type]:
        """
        根据表名获取模型类

        Args:
            table_name: 表名

        Returns:
            模型类，如果不存在返回 None
        """
        return self._model_registry.get(table_name)

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

        # 查找主键（可能为 None，表示无主键）
        primary_key = None
        for col in columns:
            if col.primary_key:
                primary_key = col.name
                break

        # 允许无主键（使用隐式 rowid）
        # 注意：无主键时，primary_key 为 None

        table = Table(name, columns, primary_key, comment)
        self.tables[name] = table
        self._dirty = True

        # 原生 SQL 模式：立即创建数据库表
        if self._native_sql_mode and self._connector:
            self._create_table_native_sql(name, table)

        if self.auto_flush:
            self.flush()

    def _create_table_native_sql(self, table_name: str, table: Table) -> None:
        """
        原生 SQL 模式下创建数据库表

        Args:
            table_name: 表名
            table: Table 对象
        """
        assert self._connector is not None, "Connector must not be None in native SQL mode"
        connector = self._connector

        # 确保元数据表存在
        if self.backend and hasattr(self.backend, '_ensure_metadata_tables'):
            self.backend._ensure_metadata_tables(connector)

        # 创建数据表
        if not connector.table_exists(table_name):
            columns_def = [
                {
                    'name': col.name,
                    'type': col.col_type,
                    'nullable': col.nullable,
                    'primary_key': col.primary_key
                }
                for col in table.columns.values()
            ]
            connector.create_table(table_name, columns_def, table.primary_key)

            # 创建索引
            for col_name, col in table.columns.items():
                if col.index and not col.primary_key:
                    # 验证标识符安全性
                    validate_sql_identifier(table_name)
                    validate_sql_identifier(col_name)
                    index_name = f'idx_{table_name}_{col_name}'
                    connector.execute(
                        f'CREATE INDEX IF NOT EXISTS `{index_name}` ON `{table_name}`(`{col_name}`)'
                    )

            connector.commit()

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

    # ========== Schema 操作方法 ==========

    def sync_table_schema(
        self,
        table_name: str,
        columns: List[Column],
        comment: Optional[str] = None,
        options: Optional[SyncOptions] = None
    ) -> SyncResult:
        """
        同步表结构（轻量迁移）

        根据给定的列定义同步已存在表的 schema，包括：
        - 同步表备注
        - 同步列备注
        - 添加新列
        - 删除缺失列（可选）

        Args:
            table_name: 表名
            columns: 新的列定义列表
            comment: 表备注
            options: 同步选项

        Returns:
            SyncResult: 同步结果（包含变更详情）

        Raises:
            TableNotFoundError: 表不存在
            SchemaError: 新增必填列无默认值时
        """
        if table_name not in self.tables:
            raise TableNotFoundError(table_name)

        opts = options or SyncOptions()
        table = self.tables[table_name]
        result = SyncResult(table_name=table_name)

        # 构建新列名到列的映射
        new_columns_map: Dict[str, Column] = {}
        for col in columns:
            assert col.name is not None, "Column name must be set"
            new_columns_map[col.name] = col
        old_columns_set = set(table.columns.keys())
        new_columns_set = set(new_columns_map.keys())

        # 1. 同步表备注
        if opts.sync_table_comment and table.comment != comment:
            table.update_comment(comment)
            result.table_comment_updated = True

        # 2. 添加新列
        if opts.add_new_columns:
            columns_to_add = new_columns_set - old_columns_set
            for col_name in columns_to_add:
                col = new_columns_map[col_name]
                # 原生 SQL 模式
                if self._native_sql_mode and self._connector:
                    self._add_column_native_sql(table_name, col)
                table.add_column(col)
                result.columns_added.append(col_name)

        # 3. 删除缺失列（危险操作，默认禁用）
        if opts.drop_missing_columns:
            columns_to_drop = old_columns_set - new_columns_set - {table.primary_key}
            for col_name in columns_to_drop:
                # 原生 SQL 模式
                if self._native_sql_mode and self._connector:
                    self._drop_column_native_sql(table_name, col_name)
                table.drop_column(col_name)
                result.columns_dropped.append(col_name)

        # 4. 同步列备注
        if opts.sync_column_comments:
            for col_name in old_columns_set & new_columns_set:
                old_col = table.columns[col_name]
                new_col = new_columns_map[col_name]
                if old_col.comment != new_col.comment:
                    table.update_column_comment(col_name, new_col.comment)
                    result.column_comments_updated.append(col_name)

        # 标记脏数据
        if result.has_changes:
            self._dirty = True
            if self.auto_flush:
                self.flush()

        return result

    def drop_table(self, table_name: str) -> None:
        """
        删除表（包括所有数据）

        Args:
            table_name: 表名

        Raises:
            TableNotFoundError: 表不存在
        """
        if table_name not in self.tables:
            raise TableNotFoundError(table_name)

        # 原生 SQL 模式
        if self._native_sql_mode and self._connector:
            self._drop_table_native_sql(table_name)

        del self.tables[table_name]
        self._dirty = True

        if self.auto_flush:
            self.flush()

    def rename_table(self, old_name: str, new_name: str) -> None:
        """
        重命名表

        Args:
            old_name: 原表名
            new_name: 新表名

        Raises:
            TableNotFoundError: 原表不存在
            SchemaError: 新表名已存在
        """
        if old_name not in self.tables:
            raise TableNotFoundError(old_name)
        if new_name in self.tables:
            raise SchemaError(f"Table '{new_name}' already exists")

        # 原生 SQL 模式
        if self._native_sql_mode and self._connector:
            self._rename_table_native_sql(old_name, new_name)

        table = self.tables.pop(old_name)
        table.name = new_name
        self.tables[new_name] = table
        self._dirty = True

        if self.auto_flush:
            self.flush()

    def update_table_comment(self, table_name: str, comment: Optional[str]) -> None:
        """
        更新表备注

        Args:
            table_name: 表名
            comment: 新备注

        Raises:
            TableNotFoundError: 表不存在
        """
        table = self.get_table(table_name)
        table.update_comment(comment)
        self._dirty = True

        if self.auto_flush:
            self.flush()

    def add_column(
        self,
        table_name: str,
        column: Column,
        default_value: Any = None
    ) -> None:
        """
        向表添加列

        Args:
            table_name: 表名
            column: 列定义
            default_value: 为现有记录填充的默认值

        Raises:
            TableNotFoundError: 表不存在
            SchemaError: 列已存在或非空列无默认值
        """
        table = self.get_table(table_name)

        # 原生 SQL 模式
        if self._native_sql_mode and self._connector:
            self._add_column_native_sql(table_name, column, default_value)

        table.add_column(column, default_value)
        self._dirty = True

        if self.auto_flush:
            self.flush()

    def drop_column(self, table_name: str, column_name: str) -> None:
        """
        从表中删除列

        Args:
            table_name: 表名
            column_name: 列名

        Raises:
            TableNotFoundError: 表不存在
            ColumnNotFoundError: 列不存在
            SchemaError: 试图删除主键列
        """
        table = self.get_table(table_name)

        # 原生 SQL 模式
        if self._native_sql_mode and self._connector:
            self._drop_column_native_sql(table_name, column_name)

        table.drop_column(column_name)
        self._dirty = True

        if self.auto_flush:
            self.flush()

    def update_column(
        self,
        table_name: str,
        column_name: str,
        comment: Any = ...,
        index: Any = ...
    ) -> None:
        """
        更新列属性

        Args:
            table_name: 表名
            column_name: 列名
            comment: 新备注（... 表示不修改）
            index: 是否创建索引（... 表示不修改）

        Raises:
            TableNotFoundError: 表不存在
            ColumnNotFoundError: 列不存在
        """
        table = self.get_table(table_name)

        if comment is not ...:
            table.update_column_comment(column_name, comment)
            self._dirty = True

        if index is not ...:
            table.update_column_index(column_name, index)
            self._dirty = True

        if self._dirty and self.auto_flush:
            self.flush()

    # ========== 原生 SQL 模式的 Schema 操作 ==========

    def _add_column_native_sql(
        self,
        table_name: str,
        column: Column,
        default_value: Any = None
    ) -> None:
        """在原生 SQL 模式下添加列"""
        if not self._connector:
            return

        # 验证标识符安全性
        validate_sql_identifier(table_name)
        if column.name:
            validate_sql_identifier(column.name)

        sql_type = self._get_sql_type(column.col_type)
        sql = f'ALTER TABLE "{table_name}" ADD COLUMN "{column.name}" {sql_type}'

        if not column.nullable:
            sql += ' NOT NULL'

        fill_value = default_value if default_value is not None else column.default
        if fill_value is not None:
            sql += f' DEFAULT {self._format_sql_value(fill_value)}'

        self._connector.execute(sql)
        self._connector.commit()

    def _drop_column_native_sql(self, table_name: str, column_name: str) -> None:
        """在原生 SQL 模式下删除列（需要 SQLite 3.35+）"""
        if not self._connector:
            return

        # 验证标识符安全性
        validate_sql_identifier(table_name)
        validate_sql_identifier(column_name)

        sql = f'ALTER TABLE "{table_name}" DROP COLUMN "{column_name}"'
        self._connector.execute(sql)
        self._connector.commit()

    def _drop_table_native_sql(self, table_name: str) -> None:
        """在原生 SQL 模式下删除表"""
        if not self._connector:
            return

        # 验证标识符安全性
        validate_sql_identifier(table_name)

        sql = f'DROP TABLE IF EXISTS "{table_name}"'
        self._connector.execute(sql)
        self._connector.commit()

    def _rename_table_native_sql(self, old_name: str, new_name: str) -> None:
        """在原生 SQL 模式下重命名表"""
        if not self._connector:
            return

        # 验证标识符安全性
        validate_sql_identifier(old_name)
        validate_sql_identifier(new_name)

        sql = f'ALTER TABLE "{old_name}" RENAME TO "{new_name}"'
        self._connector.execute(sql)
        self._connector.commit()

    def _get_sql_type(self, col_type: Type) -> str:
        """获取 Python 类型对应的 SQLite 类型"""
        from datetime import datetime, date, timedelta

        type_mapping = {
            int: 'INTEGER',
            float: 'REAL',
            str: 'TEXT',
            bool: 'INTEGER',
            bytes: 'BLOB',
            datetime: 'TEXT',
            date: 'TEXT',
            timedelta: 'TEXT',
            list: 'TEXT',
            dict: 'TEXT',
        }
        return type_mapping.get(col_type, 'TEXT')

    def _format_sql_value(self, value: Any) -> str:
        """格式化 SQL 值"""
        if value is None:
            return 'NULL'
        elif isinstance(value, bool):
            return '1' if value else '0'
        elif isinstance(value, (int, float)):
            return str(value)
        elif isinstance(value, str):
            escaped = value.replace("'", "''")
            return f"'{escaped}'"
        else:
            escaped = str(value).replace("'", "''")
            return f"'{escaped}'"

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

        # 原生 SQL 模式：直接执行 SQL
        if self._native_sql_mode and self._connector:
            return self._insert_native_sql(table_name, table, data)

        # 内存模式
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

    def _insert_native_sql(self, table_name: str, table: Table, data: Dict[str, Any]) -> Any:
        """
        原生 SQL 插入

        Args:
            table_name: 表名
            table: Table 对象
            data: 数据字典

        Returns:
            主键值
        """
        assert self._connector is not None, "Connector must not be None in native SQL mode"
        connector = self._connector

        # 验证和处理所有字段
        validated_record: Dict[str, Any] = {}
        for col_name, column in table.columns.items():
            value = data.get(col_name)
            validated_value = column.validate(value)
            validated_record[col_name] = validated_value

        # 使用连接器插入
        pk = connector.insert_row(table_name, validated_record, table.primary_key)

        # 更新 next_id
        if pk is not None and isinstance(pk, int) and pk >= table.next_id:
            table.next_id = pk + 1
            self._dirty = True  # 需要保存 schema

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

        # 原生 SQL 模式：直接执行 SQL
        if self._native_sql_mode and self._connector:
            self._update_native_sql(table_name, table, pk, data)
            return

        # 内存模式
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

    def _update_native_sql(self, table_name: str, table: Table, pk: Any, data: Dict[str, Any]) -> None:
        """
        原生 SQL 更新

        Args:
            table_name: 表名
            table: Table 对象
            pk: 主键值
            data: 新数据
        """
        assert self._connector is not None, "Connector must not be None in native SQL mode"
        connector = self._connector

        # 验证字段
        validated_data: Dict[str, Any] = {}
        for col_name, value in data.items():
            if col_name in table.columns:
                column = table.columns[col_name]
                validated_data[col_name] = column.validate(value)

        # 使用连接器更新
        connector.update_row(table_name, table.primary_key, pk, validated_data)

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

        # 原生 SQL 模式：直接执行 SQL
        if self._native_sql_mode and self._connector:
            self._connector.delete_row(table_name, table.primary_key, pk)
            if self.auto_flush:
                self.flush()
            return

        # 内存模式
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
            pk: 主键值（用户主键或内部 rowid）

        Returns:
            记录字典
        """
        table = self.get_table(table_name)

        # 原生 SQL 模式：直接执行 SQL
        if self._native_sql_mode and self._connector:
            # 无主键表使用 rowid 查询
            pk_col = table.primary_key if table.primary_key else 'rowid'
            result = self._connector.select_by_pk(table_name, pk_col, pk)
            if result is None:
                raise RecordNotFoundError(table_name, pk)
            # 反序列化
            return self._deserialize_record(result, table.columns)

        # 内存模式
        record = table.get(pk)
        record_copy = record.copy()
        # 无主键表：注入内部 rowid
        if not table.primary_key:
            record_copy[PSEUDO_PK_NAME] = pk
        return record_copy

    def _deserialize_record(self, record: Dict[str, Any], columns: Dict[str, Column]) -> Dict[str, Any]:
        """
        反序列化记录

        Args:
            record: 原始记录
            columns: 列定义

        Returns:
            反序列化后的记录
        """
        from datetime import datetime, date, timedelta
        from .types import TypeRegistry
        import json

        result: Dict[str, Any] = {}
        for col_name, value in record.items():
            if col_name in columns and value is not None:
                column = columns[col_name]
                col_type = column.col_type

                if col_type == bool and isinstance(value, int):
                    value = bool(value)
                elif col_type in (datetime, date, timedelta):
                    value = TypeRegistry.deserialize_from_text(value, col_type)
                elif col_type in (list, dict) and isinstance(value, str):
                    value = json.loads(value)

            result[col_name] = value

        return result

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

        # 原生 SQL 模式：直接执行 SQL
        if self._native_sql_mode and self._connector:
            return self._query_native_sql(table_name, table, conditions, limit, offset, order_by, order_desc)

        # 内存模式
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
                    record_copy = record.copy()
                    # 无主键表：注入内部 rowid
                    if not table.primary_key:
                        record_copy[PSEUDO_PK_NAME] = pk
                    results.append(record_copy)

        # 排序
        if order_by and order_by in table.columns:
            def sort_key(record: Dict[str, Any]) -> tuple:
                """
                排序键函数

                排序规则：
                - None 值在升序时排在最后，降序时排在最前
                - 使用元组 (优先级, 值) 实现：优先级 0 表示有值，1 表示 None
                """
                value = record.get(order_by)
                # 处理 None 值：升序时 None 排在最后 (1, 0)，降序时排在最前 (0, 0)
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

    def _query_native_sql(
        self,
        table_name: str,
        table: Table,
        conditions: List[Condition],
        limit: Optional[int],
        offset: int,
        order_by: Optional[str],
        order_desc: bool
    ) -> List[Dict[str, Any]]:
        """
        原生 SQL 查询

        Args:
            table_name: 表名
            table: Table 对象
            conditions: 查询条件列表
            limit: 限制返回记录数
            offset: 跳过的记录数
            order_by: 排序字段名
            order_desc: 是否降序排列

        Returns:
            记录字典列表
        """
        assert self._connector is not None, "Connector must not be None in native SQL mode"
        connector = self._connector

        # 构建 WHERE 子句
        where_parts: List[str] = []
        params: List[Any] = []

        for condition in conditions:
            op = self._convert_operator(condition.operator)
            where_parts.append(f'`{condition.field}` {op} ?')
            params.append(condition.value)

        where_clause = ' AND '.join(where_parts) if where_parts else None

        # 构建 ORDER BY 子句
        order_by_clause = None
        if order_by:
            direction = 'DESC' if order_desc else 'ASC'
            order_by_clause = f'`{order_by}` {direction}'

        # 执行查询
        rows = connector.query_rows(
            table_name,
            where_clause=where_clause,
            params=tuple(params),
            order_by=order_by_clause,
            limit=limit,
            offset=offset if offset > 0 else None
        )

        # 反序列化
        results = [self._deserialize_record(row, table.columns) for row in rows]
        return results

    def _convert_operator(self, op: str) -> str:
        """转换操作符为 SQL 操作符"""
        op_map = {
            '==': '=',
            'eq': '=',
            'ne': '!=',
            'lt': '<',
            'le': '<=',
            'gt': '>',
            'ge': '>=',
        }
        return op_map.get(op, op)

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
        from ..backends.backend_binary import BinaryBackend

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

    def _init_native_sql_mode(self) -> None:
        """
        初始化原生 SQL 模式

        检查后端是否支持原生 SQL 模式，如果支持则获取连接器。
        """
        if self.backend is None:
            return

        # 检查后端是否支持原生 SQL 模式
        if hasattr(self.backend, 'use_native_sql') and self.backend.use_native_sql:
            self._native_sql_mode = True
            # 获取连接器
            if hasattr(self.backend, 'get_connector'):
                self._connector = self.backend.get_connector()

    @property
    def is_native_sql_mode(self) -> bool:
        """是否启用原生 SQL 模式"""
        return self._native_sql_mode

    def _get_binary_backend(self) -> Optional['BinaryBackend']:
        """获取 binary 后端（如果是的话）"""
        from ..backends.backend_binary import BinaryBackend

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

        from ..backends.backend_binary import WALOpType

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

        # 关闭原生 SQL 模式的后端连接
        if self._native_sql_mode and self.backend:
            if hasattr(self.backend, 'close'):
                self.backend.close()
            self._connector = None

    def __repr__(self) -> str:
        return f"Storage(tables={len(self.tables)}, in_memory={self.in_memory})"
