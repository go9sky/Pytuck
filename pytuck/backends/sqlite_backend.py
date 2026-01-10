"""
Pytuck SQLite存储引擎

使用内置sqlite3数据库，支持SQL查询和ACID特性
"""

import sqlite3
import json
import os
from typing import Any, Dict, Type, TYPE_CHECKING
from datetime import datetime
from .base import StorageBackend
from ..exceptions import SerializationError

if TYPE_CHECKING:
    from ..storage import Table


class SQLiteBackend(StorageBackend):
    """SQLite format storage engine (built-in, ACID)"""

    ENGINE_NAME = 'sqlite'
    REQUIRED_DEPENDENCIES = []  # 内置 sqlite3

    # 类型映射
    TYPE_MAPPING: Dict[Type, str] = {
        int: 'INTEGER',
        str: 'TEXT',
        float: 'REAL',
        bool: 'INTEGER',  # 0/1
        bytes: 'BLOB'
    }

    def save(self, tables: Dict[str, 'Table']) -> None:
        """保存所有表数据到SQLite数据库"""
        try:
            conn = sqlite3.connect(self.file_path)
            cursor = conn.cursor()

            # 创建元数据表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS _pytuck_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS _pytuck_tables (
                    table_name TEXT PRIMARY KEY,
                    primary_key TEXT,
                    next_id INTEGER,
                    columns TEXT
                )
            ''')

            # 保存版本信息
            cursor.execute("INSERT OR REPLACE INTO _pytuck_metadata VALUES (?, ?)",
                         ('version', '0.1.0'))
            cursor.execute("INSERT OR REPLACE INTO _pytuck_metadata VALUES (?, ?)",
                         ('timestamp', datetime.now().isoformat()))

            # 为每个表创建 SQL 表并保存数据
            for table_name, table in tables.items():
                self._save_table(cursor, table_name, table)

            conn.commit()
            conn.close()

        except Exception as e:
            raise SerializationError(f"Failed to save to SQLite: {e}")

    def load(self) -> Dict[str, 'Table']:
        """从SQLite数据库加载所有表数据"""
        if not self.exists():
            raise FileNotFoundError(f"SQLite database not found: {self.file_path}")

        try:
            conn = sqlite3.connect(self.file_path)
            cursor = conn.cursor()

            # 读取所有表
            cursor.execute('SELECT table_name, primary_key, next_id, columns FROM _pytuck_tables')
            table_rows = cursor.fetchall()

            tables = {}
            for table_name, primary_key, next_id, columns_json in table_rows:
                table = self._load_table(cursor, table_name, primary_key, next_id, columns_json)
                tables[table_name] = table

            conn.close()
            return tables

        except Exception as e:
            raise SerializationError(f"Failed to load from SQLite: {e}")

    def exists(self) -> bool:
        """检查数据库文件是否存在"""
        return os.path.exists(self.file_path)

    def delete(self) -> None:
        """删除数据库文件"""
        if self.exists():
            os.remove(self.file_path)

    def _save_table(self, cursor: sqlite3.Cursor, table_name: str, table: 'Table') -> None:
        """保存单个表"""
        # 保存表元数据
        columns_json = json.dumps([
            {
                'name': col.name,
                'type': col.col_type.__name__,
                'nullable': col.nullable,
                'primary_key': col.primary_key,
                'index': col.index
            }
            for col in table.columns.values()
        ])

        cursor.execute('''
            INSERT OR REPLACE INTO _pytuck_tables
            (table_name, primary_key, next_id, columns)
            VALUES (?, ?, ?, ?)
        ''', (table_name, table.primary_key, table.next_id, columns_json))

        # 删除旧表（如果存在）
        cursor.execute(f'DROP TABLE IF EXISTS `{table_name}`')

        # 创建新表
        col_defs = []
        for col_name, col in table.columns.items():
            sql_type = self.TYPE_MAPPING[col.col_type]
            constraints = []

            if col.primary_key:
                if col.col_type == int:
                    # INTEGER PRIMARY KEY 自动是 ROWID 别名，支持自增
                    constraints.append('PRIMARY KEY AUTOINCREMENT')
                else:
                    constraints.append('PRIMARY KEY')
            elif not col.nullable:
                constraints.append('NOT NULL')

            col_def = f'`{col_name}` {sql_type}'
            if constraints:
                col_def += ' ' + ' '.join(constraints)
            col_defs.append(col_def)

        create_sql = f'CREATE TABLE `{table_name}` ({", ".join(col_defs)})'
        cursor.execute(create_sql)

        # 创建索引
        for col_name, col in table.columns.items():
            if col.index and not col.primary_key:
                index_name = f'idx_{table_name}_{col_name}'
                cursor.execute(f'CREATE INDEX `{index_name}` ON `{table_name}`(`{col_name}`)')

        # 插入数据
        if len(table.data) > 0:
            columns = list(table.columns.keys())
            placeholders = ','.join(['?'] * len(columns))
            insert_sql = f'INSERT INTO `{table_name}` ({",".join([f"`{c}`" for c in columns])}) VALUES ({placeholders})'

            for record in table.data.values():
                values = []
                for col_name in columns:
                    value = record.get(col_name)
                    # 处理 bool -> int
                    if isinstance(value, bool):
                        value = 1 if value else 0
                    values.append(value)

                cursor.execute(insert_sql, values)

    def _load_table(self, cursor: sqlite3.Cursor, table_name: str, primary_key: str, next_id: int, columns_json: str) -> 'Table':
        """加载单个表"""
        from ..storage import Table
        from ..orm import Column

        # 重建列定义
        columns_data = json.loads(columns_json)
        columns = []

        for col_data in columns_data:
            # 类型名转类型
            type_map = {
                'int': int,
                'str': str,
                'float': float,
                'bool': bool,
                'bytes': bytes,
            }
            col_type = type_map.get(col_data['type'], str)

            column = Column(
                col_data['name'],
                col_type,
                nullable=col_data['nullable'],
                primary_key=col_data['primary_key'],
                index=col_data.get('index', False)
            )
            columns.append(column)

        # 创建表对象
        table = Table(table_name, columns, primary_key)
        table.next_id = next_id

        # 加载数据
        cursor.execute(f'SELECT * FROM `{table_name}`')
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

            conn = sqlite3.connect(self.file_path)
            cursor = conn.cursor()

            # 读取版本信息
            metadata = {
                'engine': 'sqlite',
                'file_size': file_size,
                'modified': modified_time
            }

            try:
                cursor.execute("SELECT value FROM _pytuck_metadata WHERE key = 'version'")
                row = cursor.fetchone()
                if row:
                    metadata['version'] = row[0]

                cursor.execute("SELECT value FROM _pytuck_metadata WHERE key = 'timestamp'")
                row = cursor.fetchone()
                if row:
                    metadata['timestamp'] = row[0]

                cursor.execute("SELECT COUNT(*) FROM _pytuck_tables")
                row = cursor.fetchone()
                if row:
                    metadata['table_count'] = row[0]
            except:
                pass

            conn.close()
            return metadata

        except:
            return {}
