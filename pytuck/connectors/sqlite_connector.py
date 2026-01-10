"""
SQLite 数据库连接器

提供 SQLite 数据库的统一操作接口
"""

import sqlite3
from typing import Any, Dict, List, Tuple, Optional, Type

from .base import DatabaseConnector
from ..common.options import SqliteConnectorOptions


class SQLiteConnector(DatabaseConnector):
    """
    SQLite 数据库连接器

    使用 Python 内置的 sqlite3 模块，无需额外依赖。

    特性：
    - 自动设置 row_factory 为 sqlite3.Row
    - 支持所有 DatabaseConnector 接口
    - 自动过滤 sqlite_ 系统表和 _pytuck_ 元数据表

    Example:
        with SQLiteConnector('data.db') as conn:
            tables = conn.get_table_names()
            for table in tables:
                data = conn.get_table_data(table)
    """

    DB_TYPE = 'sqlite'
    REQUIRED_DEPENDENCIES: List[str] = []  # sqlite3 是内置模块

    TYPE_TO_SQL: Dict[Type, str] = {
        int: 'INTEGER',
        str: 'TEXT',
        float: 'REAL',
        bool: 'INTEGER',
        bytes: 'BLOB',
    }

    SQL_TO_TYPE: Dict[str, Type] = {
        # 整数类型
        'INTEGER': int,
        'INT': int,
        'SMALLINT': int,
        'BIGINT': int,
        'TINYINT': int,
        # 浮点类型
        'REAL': float,
        'FLOAT': float,
        'DOUBLE': float,
        'NUMERIC': float,
        'DECIMAL': float,
        # 字符串类型
        'TEXT': str,
        'VARCHAR': str,
        'CHAR': str,
        'NVARCHAR': str,
        'NCHAR': str,
        'CLOB': str,
        # 二进制类型
        'BLOB': bytes,
        # 布尔类型
        'BOOLEAN': bool,
        'BOOL': bool,
    }

    def __init__(self, db_path: str, options: SqliteConnectorOptions):
        """
        初始化 SQLite 连接器

        Args:
            db_path: SQLite 数据库文件路径
            options: SQLite 连接器配置选项
        """
        super().__init__(db_path, options)
        self.conn: Optional[sqlite3.Connection] = None

    def connect(self) -> None:
        """连接到 SQLite 数据库"""
        # 构建连接参数，只包含非None的值
        connect_kwargs: Dict[str, Any] = {
            'check_same_thread': self.options.check_same_thread,
        }

        if self.options.timeout is not None:
            connect_kwargs['timeout'] = self.options.timeout

        if self.options.isolation_level is not None:
            connect_kwargs['isolation_level'] = self.options.isolation_level

        self.conn = sqlite3.connect(self.db_path, **connect_kwargs)
        self.conn.row_factory = sqlite3.Row

    def close(self) -> None:
        """关闭连接"""
        if self.conn is not None:
            self.conn.close()
            self.conn = None

    def is_connected(self) -> bool:
        """检查是否已连接"""
        return self.conn is not None

    def get_table_names(self, exclude_system: bool = True) -> List[str]:
        """
        获取所有表名

        Args:
            exclude_system: 是否排除系统表（sqlite_*）和 Pytuck 元数据表（_pytuck_*）
        """
        if self.conn is None:
            raise RuntimeError("数据库未连接，请先调用 connect()")

        cursor = self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        tables = [row[0] for row in cursor.fetchall()]

        if exclude_system:
            tables = [
                t for t in tables
                if not t.startswith('sqlite_') and not t.startswith('_pytuck_')
            ]

        return tables

    def table_exists(self, table_name: str) -> bool:
        """检查表是否存在"""
        if self.conn is None:
            raise RuntimeError("数据库未连接，请先调用 connect()")

        cursor = self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,)
        )
        return cursor.fetchone() is not None

    def get_table_schema(self, table_name: str) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        """
        获取表结构

        Returns:
            (columns, primary_key) 元组
        """
        if self.conn is None:
            raise RuntimeError("数据库未连接，请先调用 connect()")

        # 先验证表存在
        if not self.table_exists(table_name):
            raise ValueError(f"表 '{table_name}' 不存在")

        cursor = self.conn.execute(f"PRAGMA table_info('{table_name}')")
        columns: List[Dict[str, Any]] = []
        primary_key: Optional[str] = None
        pk_columns: List[str] = []  # 收集所有主键列

        for row in cursor.fetchall():
            # PRAGMA table_info 返回: cid, name, type, notnull, dflt_value, pk
            col_name = row[1]
            col_type_str = (row[2] or '').upper()
            not_null = row[3] == 1
            is_pk = row[5] >= 1  # pk 列：0 表示非主键，>=1 表示主键顺序

            # 类型映射
            py_type: Type = str  # 默认类型
            for sql_type, mapped_type in self.SQL_TO_TYPE.items():
                if sql_type in col_type_str:
                    py_type = mapped_type
                    break

            # 先收集主键列，稍后只标记第一个
            if is_pk:
                pk_columns.append(col_name)

            columns.append({
                'name': col_name,
                'type': py_type,
                'nullable': not not_null,
                'primary_key': False  # 先都设为 False，后面再修正
            })

        # Pytuck 只支持单主键，取第一个主键列
        if pk_columns:
            primary_key = pk_columns[0]
            # 只标记第一个主键列为 primary_key=True
            for col in columns:
                if col['name'] == primary_key:
                    col['primary_key'] = True
                    break

        return columns, primary_key

    def get_table_data(self, table_name: str) -> List[Dict[str, Any]]:
        """获取表中所有数据"""
        if self.conn is None:
            raise RuntimeError("数据库未连接，请先调用 connect()")

        # 先验证表存在
        if not self.table_exists(table_name):
            raise ValueError(f"表 '{table_name}' 不存在")

        cursor = self.conn.execute(f"SELECT * FROM '{table_name}'")
        return [dict(row) for row in cursor.fetchall()]

    def execute(self, sql: str, params: tuple = ()) -> Any:
        """执行 SQL 语句"""
        if self.conn is None:
            raise RuntimeError("数据库未连接，请先调用 connect()")
        return self.conn.execute(sql, params)

    def executemany(self, sql: str, params_list: List[tuple]) -> None:
        """批量执行 SQL 语句"""
        if self.conn is None:
            raise RuntimeError("数据库未连接，请先调用 connect()")
        self.conn.executemany(sql, params_list)

    def create_table(
        self,
        table_name: str,
        columns: List[Dict[str, Any]],
        primary_key: str
    ) -> None:
        """创建表"""
        if self.conn is None:
            raise RuntimeError("数据库未连接，请先调用 connect()")

        col_defs = []
        for col in columns:
            sql_type = self.TYPE_TO_SQL.get(col['type'], 'TEXT')
            constraints = []

            if col.get('primary_key'):
                if col['type'] == int:
                    constraints.append('PRIMARY KEY AUTOINCREMENT')
                else:
                    constraints.append('PRIMARY KEY')
            elif not col.get('nullable', True):
                constraints.append('NOT NULL')

            col_def = f"`{col['name']}` {sql_type}"
            if constraints:
                col_def += ' ' + ' '.join(constraints)
            col_defs.append(col_def)

        sql = f"CREATE TABLE `{table_name}` ({', '.join(col_defs)})"
        self.conn.execute(sql)

    def drop_table(self, table_name: str) -> None:
        """删除表"""
        if self.conn is None:
            raise RuntimeError("数据库未连接，请先调用 connect()")
        self.conn.execute(f"DROP TABLE IF EXISTS `{table_name}`")

    def insert_records(
        self,
        table_name: str,
        columns: List[str],
        records: List[Dict[str, Any]]
    ) -> None:
        """批量插入记录"""
        if self.conn is None:
            raise RuntimeError("数据库未连接，请先调用 connect()")

        if not records:
            return

        placeholders = ','.join(['?'] * len(columns))
        col_names = ','.join([f"`{c}`" for c in columns])
        sql = f"INSERT INTO `{table_name}` ({col_names}) VALUES ({placeholders})"

        values_list = []
        for record in records:
            values = []
            for col in columns:
                value = record.get(col)
                # SQLite 用 INTEGER 存储布尔值
                if isinstance(value, bool):
                    value = 1 if value else 0
                values.append(value)
            values_list.append(tuple(values))

        self.conn.executemany(sql, values_list)

    def commit(self) -> None:
        """提交事务"""
        if self.conn is not None:
            self.conn.commit()
