"""
Pytuck SQLite存储引擎

使用内置sqlite3数据库，支持SQL查询和ACID特性
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, TYPE_CHECKING, Tuple
from datetime import datetime

from .base import StorageBackend
from ..connectors.sqlite_connector import SQLiteConnector
from ..common.exceptions import SerializationError
from .versions import get_format_version

from ..common.options import SqliteBackendOptions

if TYPE_CHECKING:
    from ..core.storage import Table


class SQLiteBackend(StorageBackend):
    """SQLite format storage engine (built-in, ACID)

    使用 SQLiteConnector 进行底层数据库操作，
    添加 Pytuck 特有的元数据管理。
    """

    ENGINE_NAME = 'sqlite'
    REQUIRED_DEPENDENCIES = []  # 内置 sqlite3
    FORMAT_VERSION = get_format_version('sqlite')

    def __init__(self, file_path: Union[str, Path], options: SqliteBackendOptions):
        """
        初始化 SQLite 后端

        Args:
            file_path: SQLite 数据库文件路径
            options: SQLite 后端配置选项
        """
        assert isinstance(options, SqliteBackendOptions), "options must be an instance of SqliteBackendOptions"
        super().__init__(file_path, options)
        # 类型安全：将 options 转为具体的 SqliteBackendOptions 类型
        self.options: SqliteBackendOptions = options

    def save(self, tables: Dict[str, 'Table']) -> None:
        """保存所有表数据到SQLite数据库"""
        try:
            # 创建连接器
            connector = SQLiteConnector(str(self.file_path), self.options)
            with connector:
                # 创建元数据表
                self._ensure_metadata_tables(connector)

                # 保存版本信息
                connector.execute(
                    "INSERT OR REPLACE INTO _pytuck_metadata VALUES (?, ?)",
                    ('format_version', str(self.FORMAT_VERSION))
                )
                connector.execute(
                    "INSERT OR REPLACE INTO _pytuck_metadata VALUES (?, ?)",
                    ('timestamp', datetime.now().isoformat())
                )

                # 为每个表创建 SQL 表并保存数据
                for table_name, table in tables.items():
                    self._save_table(connector, table_name, table)

                connector.commit()

        except Exception as e:
            raise SerializationError(f"Failed to save to SQLite: {e}")

    def load(self) -> Dict[str, 'Table']:
        """从SQLite数据库加载所有表数据"""
        if not self.exists():
            raise FileNotFoundError(f"SQLite database not found: {self.file_path}")

        try:
            # 创建连接器，使用默认选项
            connector = SQLiteConnector(str(self.file_path), self.options)
            with connector:
                # 检查是否是 Pytuck 格式
                if not connector.table_exists('_pytuck_tables'):
                    raise SerializationError(
                        f"'{self.file_path}' 不是 Pytuck 格式的 SQLite 数据库。"
                        f"如需从普通 SQLite 导入，请使用 pytuck.tools.import_from_database()"
                    )

                # 读取所有表
                cursor = connector.execute(
                    'SELECT table_name, primary_key, next_id, comment, columns FROM _pytuck_tables'
                )
                table_rows = cursor.fetchall()

                tables = {}
                for table_name, primary_key, next_id, table_comment, columns_json in table_rows:
                    table = self._load_table(
                        connector, table_name, primary_key, next_id, table_comment, columns_json
                    )
                    tables[table_name] = table

                return tables

        except SerializationError:
            raise
        except Exception as e:
            raise SerializationError(f"Failed to load from SQLite: {e}")

    def exists(self) -> bool:
        """检查数据库文件是否存在"""
        return self.file_path.exists()

    def delete(self) -> None:
        """删除数据库文件"""
        if self.exists():
            self.file_path.unlink()

    def _ensure_metadata_tables(self, connector: SQLiteConnector) -> None:
        """确保元数据表存在"""
        connector.execute('''
            CREATE TABLE IF NOT EXISTS _pytuck_metadata (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')

        connector.execute('''
            CREATE TABLE IF NOT EXISTS _pytuck_tables (
                table_name TEXT PRIMARY KEY,
                primary_key TEXT,
                next_id INTEGER,
                comment TEXT,
                columns TEXT
            )
        ''')

    def _save_table(
        self,
        connector: SQLiteConnector,
        table_name: str,
        table: 'Table'
    ) -> None:
        """保存单个表"""
        # 保存表元数据
        columns_json = json.dumps([
            {
                'name': col.name,
                'type': col.col_type.__name__,
                'nullable': col.nullable,
                'primary_key': col.primary_key,
                'index': col.index,
                'comment': col.comment
            }
            for col in table.columns.values()
        ])

        connector.execute('''
            INSERT OR REPLACE INTO _pytuck_tables
            (table_name, primary_key, next_id, comment, columns)
            VALUES (?, ?, ?, ?, ?)
        ''', (table_name, table.primary_key, table.next_id, table.comment, columns_json))

        # 删除旧表（如果存在）
        connector.drop_table(table_name)

        # 创建新表
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
                index_name = f'idx_{table_name}_{col_name}'
                connector.execute(
                    f'CREATE INDEX `{index_name}` ON `{table_name}`(`{col_name}`)'
                )

        # 插入数据
        if len(table.data) > 0:
            columns = list(table.columns.keys())
            # 序列化记录中的特殊类型
            serialized_records = []
            for record in table.data.values():
                serialized_record = self._serialize_record_for_sqlite(record, table.columns)
                serialized_records.append(serialized_record)
            connector.insert_records(table_name, columns, serialized_records)

    def _serialize_record_for_sqlite(
        self,
        record: Dict[str, Any],
        columns: Dict[str, Any]
    ) -> Dict[str, Any]:
        """序列化记录以适应 SQLite 存储"""
        from datetime import datetime, date, timedelta

        result: Dict[str, Any] = {}
        for key, value in record.items():
            if value is None:
                result[key] = None
            elif isinstance(value, timedelta):
                # timedelta 转总秒数
                result[key] = value.total_seconds()
            elif isinstance(value, (list, dict)):
                # list/dict 转 JSON 字符串
                result[key] = json.dumps(value, ensure_ascii=False)
            elif isinstance(value, datetime):
                # datetime 转 ISO 格式字符串
                result[key] = value.isoformat()
            elif isinstance(value, date):
                # date 转 ISO 格式字符串
                result[key] = value.isoformat()
            else:
                result[key] = value
        return result

    def _load_table(
        self,
        connector: SQLiteConnector,
        table_name: str,
        primary_key: str,
        next_id: int,
        table_comment: str,
        columns_json: str
    ) -> 'Table':
        """加载单个表"""
        from ..core.storage import Table
        from ..core.orm import Column
        from datetime import datetime, date, timedelta

        # 重建列定义
        columns_data = json.loads(columns_json)
        columns = []

        type_map = {
            'int': int,
            'str': str,
            'float': float,
            'bool': bool,
            'bytes': bytes,
            'datetime': datetime,
            'date': date,
            'timedelta': timedelta,
            'list': list,
            'dict': dict,
        }

        for col_data in columns_data:
            col_type = type_map.get(col_data['type'], str)

            column = Column(
                col_data['name'],
                col_type,
                nullable=col_data['nullable'],
                primary_key=col_data['primary_key'],
                index=col_data.get('index', False),
                comment=col_data.get('comment')
            )
            columns.append(column)

        # 创建表对象
        table = Table(table_name, columns, primary_key, comment=table_comment)
        table.next_id = next_id

        # 加载数据
        cursor = connector.execute(f'SELECT * FROM `{table_name}`')
        rows = cursor.fetchall()
        col_names = [desc[0] for desc in cursor.description]

        for row in rows:
            record = {}
            for col_name, value in zip(col_names, row):
                # 处理类型转换
                column = table.columns[col_name]
                if value is not None:
                    if column.col_type == bool and isinstance(value, int):
                        value = bool(value)
                    elif column.col_type == datetime and isinstance(value, str):
                        value = datetime.fromisoformat(value)
                    elif column.col_type == date and isinstance(value, str):
                        value = date.fromisoformat(value)
                    elif column.col_type == timedelta:
                        if isinstance(value, (int, float)):
                            value = timedelta(seconds=float(value))
                        elif isinstance(value, str):
                            value = timedelta(seconds=float(value))
                    elif column.col_type == list and isinstance(value, str):
                        value = json.loads(value)
                    elif column.col_type == dict and isinstance(value, str):
                        value = json.loads(value)
                record[col_name] = value

            pk = record[primary_key]
            table.data[pk] = record

        # 重建索引
        for col_name, column in table.columns.items():
            if column.index:
                if col_name in table.indexes:
                    del table.indexes[col_name]
                table.build_index(col_name)

        return table

    def get_metadata(self) -> Dict[str, Any]:
        """获取元数据"""
        if not self.exists():
            return {}

        try:
            file_stat = self.file_path.stat()
            file_size = file_stat.st_size
            modified_time = file_stat.st_mtime

            metadata: Dict[str, Any] = {
                'engine': 'sqlite',
                'file_size': file_size,
                'modified': modified_time
            }

            # 创建连接器，使用默认选项
            connector = SQLiteConnector(str(self.file_path), self.options)
            with connector:
                try:
                    cursor = connector.execute(
                        "SELECT value FROM _pytuck_metadata WHERE key = 'version'"
                    )
                    row = cursor.fetchone()
                    if row:
                        metadata['version'] = row[0]

                    cursor = connector.execute(
                        "SELECT value FROM _pytuck_metadata WHERE key = 'timestamp'"
                    )
                    row = cursor.fetchone()
                    if row:
                        metadata['timestamp'] = row[0]

                    cursor = connector.execute(
                        "SELECT COUNT(*) FROM _pytuck_tables"
                    )
                    row = cursor.fetchone()
                    if row:
                        metadata['table_count'] = row[0]
                except Exception:
                    pass

            return metadata

        except Exception:
            return {}

    def supports_server_side_pagination(self) -> bool:
        """SQLite 支持服务端分页"""
        return True

    def query_with_pagination(self,
                             table_name: str,
                             conditions: List[Dict[str, Any]],
                             limit: Optional[int] = None,
                             offset: int = 0,
                             order_by: Optional[str] = None,
                             order_desc: bool = False) -> Dict[str, Any]:
        """
        使用 SQL LIMIT/OFFSET 实现后端分页

        Args:
            table_name: 表名
            conditions: 查询条件列表 [{'field': 'name', 'operator': '=', 'value': 'Alice'}]
            limit: 限制返回记录数
            offset: 跳过的记录数
            order_by: 排序字段名
            order_desc: 是否降序排列

        Returns:
            {
                'records': List[Dict[str, Any]],
                'total_count': int,
                'has_more': bool,
            }
        """
        if not self.exists():
            return {'records': [], 'total_count': 0, 'has_more': False}

        try:
            # 创建连接器
            connector = SQLiteConnector(str(self.file_path), self.options)

            with connector:
                # 检查表是否存在（不要添加反引号）
                if not connector.table_exists(table_name):
                    return {'records': [], 'total_count': 0, 'has_more': False}

                # 构建 WHERE 子句
                where_clause = ""
                params = []
                if conditions:
                    where_parts = []
                    for condition in conditions:
                        field = condition['field']
                        operator = condition.get('operator', '=')
                        value = condition['value']

                        if operator == '=':
                            where_parts.append(f"`{field}` = ?")
                            params.append(value)
                        # 可以扩展更多操作符

                    if where_parts:
                        where_clause = "WHERE " + " AND ".join(where_parts)

                # 构建 ORDER BY 子句
                order_clause = ""
                if order_by:
                    direction = "DESC" if order_desc else "ASC"
                    order_clause = f"ORDER BY `{order_by}` {direction}"

                # 构建 LIMIT/OFFSET 子句
                limit_clause = ""
                if limit is not None:
                    limit_clause = f"LIMIT {limit}"
                    if offset > 0:
                        limit_clause += f" OFFSET {offset}"

                # 查询总数
                count_sql = f"SELECT COUNT(*) FROM `{table_name}` {where_clause}"
                cursor = connector.execute(count_sql, params)
                total_count = cursor.fetchone()[0] if cursor else 0

                # 查询数据
                data_sql = f"SELECT * FROM `{table_name}` {where_clause} {order_clause} {limit_clause}"
                cursor = connector.execute(data_sql, params)
                rows = cursor.fetchall()
                col_names = [desc[0] for desc in cursor.description] if cursor.description else []

                # 转换为字典格式
                records = []
                for row in rows:
                    record = {}
                    for col_name, value in zip(col_names, row):
                        record[col_name] = value
                    records.append(record)

                # 判断是否还有更多数据
                has_more = False
                if limit is not None:
                    has_more = (offset + len(records)) < total_count

                return {
                    'records': records,
                    'total_count': total_count,
                    'has_more': has_more
                }

        except Exception as e:
            # 如果出错，回退到 NotImplementedError，让 Storage 使用内存分页
            raise NotImplementedError(f"SQLite pagination failed: {e}")

    @classmethod
    def probe(cls, file_path: Union[str, Path]) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        轻量探测文件是否为 SQLite 引擎格式

        通过检查 SQLite 数据库是否包含 _pytuck_tables 表来识别。
        使用只读模式连接并设置超时以确保安全和性能。

        Returns:
            Tuple[bool, Optional[Dict]]: (是否匹配, 元数据信息或None)
        """
        try:
            file_path = Path(file_path).expanduser()
            if not file_path.exists():
                return False, {'error': 'file_not_found'}

            # 获取文件信息
            file_stat = file_path.stat()
            file_size = file_stat.st_size

            # 空文件不可能是有效的 SQLite
            if file_size == 0:
                return False, {'error': 'empty_file'}

            # 尝试连接 SQLite 数据库（只读模式，1秒超时）
            try:
                import sqlite3

                # 使用只读模式连接
                conn_str = f'file:{file_path}?mode=ro'
                conn = sqlite3.connect(conn_str, uri=True, timeout=1.0)
                conn.row_factory = sqlite3.Row

                try:
                    # 检查是否存在 _pytuck_tables 表
                    cursor = conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table' AND name='_pytuck_tables'"
                    )
                    result = cursor.fetchone()

                    if not result:
                        return False, None  # 是有效的 SQLite，但不是 Pytuck 格式

                    # 尝试获取元数据
                    format_version = None
                    timestamp = None
                    table_count = 0

                    try:
                        # 获取格式版本
                        cursor = conn.execute(
                            "SELECT value FROM _pytuck_metadata WHERE key='format_version'"
                        )
                        version_result = cursor.fetchone()
                        if version_result:
                            format_version = version_result[0]

                        # 获取时间戳
                        cursor = conn.execute(
                            "SELECT value FROM _pytuck_metadata WHERE key='timestamp'"
                        )
                        timestamp_result = cursor.fetchone()
                        if timestamp_result:
                            timestamp = timestamp_result[0]

                        # 获取表数量
                        cursor = conn.execute("SELECT COUNT(*) FROM _pytuck_tables")
                        count_result = cursor.fetchone()
                        if count_result:
                            table_count = count_result[0]

                    except sqlite3.Error:
                        # 元数据表可能不存在或损坏，但仍然是 Pytuck 格式
                        pass

                    # 成功识别为 SQLite 格式
                    return True, {
                        'engine': 'sqlite',
                        'format_version': format_version,
                        'table_count': table_count,
                        'file_size': file_size,
                        'modified': file_stat.st_mtime,
                        'timestamp': timestamp,
                        'confidence': 'high'
                    }

                finally:
                    conn.close()

            except sqlite3.DatabaseError:
                return False, {'error': 'invalid_sqlite_file'}
            except sqlite3.OperationalError as e:
                if 'database is locked' in str(e).lower():
                    return False, {'error': 'database_locked'}
                else:
                    return False, {'error': f'sqlite_error: {str(e)}'}

        except Exception as e:
            return False, {'error': f'probe_exception: {str(e)}'}
