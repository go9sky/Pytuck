"""
Pytuck SQLite存储引擎

使用内置sqlite3数据库，支持SQL查询和ACID特性
"""

import json
import os
from typing import Any, Dict, TYPE_CHECKING
from datetime import datetime

from .base import StorageBackend
from ..connectors.sqlite_connector import SQLiteConnector
from ..common.exceptions import SerializationError
from .versions import get_format_version

from ..common.options import SqliteBackendOptions, SqliteConnectorOptions

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

    def __init__(self, file_path: str, options: SqliteBackendOptions):
        """
        初始化 SQLite 后端

        Args:
            file_path: SQLite 数据库文件路径
            options: SQLite 后端配置选项
        """
        super().__init__(file_path, options)

    def save(self, tables: Dict[str, 'Table']) -> None:
        """保存所有表数据到SQLite数据库"""
        try:
            # 创建连接器，使用默认选项
            connector_options = SqliteConnectorOptions()
            connector = SQLiteConnector(self.file_path, connector_options)
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
            connector_options = SqliteConnectorOptions()
            connector = SQLiteConnector(self.file_path, connector_options)
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
        return os.path.exists(self.file_path)

    def delete(self) -> None:
        """删除数据库文件"""
        if self.exists():
            os.remove(self.file_path)

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
            records = list(table.data.values())
            connector.insert_records(table_name, columns, records)

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

        # 重建列定义
        columns_data = json.loads(columns_json)
        columns = []

        type_map = {
            'int': int,
            'str': str,
            'float': float,
            'bool': bool,
            'bytes': bytes,
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
                # 处理 int -> bool
                column = table.columns[col_name]
                if column.col_type == bool and isinstance(value, int):
                    value = bool(value)
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
            file_size = os.path.getsize(self.file_path)
            modified_time = os.path.getmtime(self.file_path)

            metadata: Dict[str, Any] = {
                'engine': 'sqlite',
                'file_size': file_size,
                'modified': modified_time
            }

            # 创建连接器，使用默认选项
            connector_options = SqliteConnectorOptions()
            connector = SQLiteConnector(self.file_path, connector_options)
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
