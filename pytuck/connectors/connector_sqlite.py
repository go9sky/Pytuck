"""
SQLite 数据库连接器

提供 SQLite 数据库的统一操作接口
"""

import json
import sqlite3
from datetime import datetime, date, timedelta
from typing import Any, Dict, List, Tuple, Optional, Type

from .base import DatabaseConnector
from ..common.options import SqliteConnectorOptions
from ..common.exceptions import DatabaseConnectionError, TableNotFoundError
from ..core.types import TypeRegistry


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
        # 基础类型
        int: 'INTEGER',
        str: 'TEXT',
        float: 'REAL',
        bool: 'INTEGER',
        bytes: 'BLOB',
        # 扩展类型（Pytuck 支持的全部 10 种类型）
        datetime: 'TEXT',    # ISO 8601 字符串存储
        date: 'TEXT',        # ISO 8601 字符串存储
        timedelta: 'REAL',   # 秒数存储（浮点数）
        list: 'TEXT',        # JSON 字符串存储
        dict: 'TEXT',        # JSON 字符串存储
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
        # 时间类型（用于外部 SQLite 数据库类型推断）
        'DATETIME': datetime,
        'DATE': date,
        'TIMESTAMP': datetime,
        'TIME': str,  # Pytuck 暂不支持 time 类型，用 str
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
            raise DatabaseConnectionError("数据库未连接，请先调用 connect()")

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
            raise DatabaseConnectionError("数据库未连接，请先调用 connect()")

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
            raise DatabaseConnectionError("数据库未连接，请先调用 connect()")

        # 先验证表存在
        if not self.table_exists(table_name):
            raise TableNotFoundError(table_name)

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
            raise DatabaseConnectionError("数据库未连接，请先调用 connect()")

        # 先验证表存在
        if not self.table_exists(table_name):
            raise TableNotFoundError(table_name)

        cursor = self.conn.execute(f"SELECT * FROM '{table_name}'")
        return [dict(row) for row in cursor.fetchall()]

    def execute(self, sql: str, params: tuple = ()) -> Any:
        """执行 SQL 语句"""
        if self.conn is None:
            raise DatabaseConnectionError("数据库未连接，请先调用 connect()")
        return self.conn.execute(sql, params)

    def executemany(self, sql: str, params_list: List[tuple]) -> None:
        """批量执行 SQL 语句"""
        if self.conn is None:
            raise DatabaseConnectionError("数据库未连接，请先调用 connect()")
        self.conn.executemany(sql, params_list)

    def create_table(
        self,
        table_name: str,
        columns: List[Dict[str, Any]],
        primary_key: str
    ) -> None:
        """创建表"""
        if self.conn is None:
            raise DatabaseConnectionError("数据库未连接，请先调用 connect()")

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
            raise DatabaseConnectionError("数据库未连接，请先调用 connect()")
        self.conn.execute(f"DROP TABLE IF EXISTS `{table_name}`")

    def insert_records(
        self,
        table_name: str,
        columns: List[str],
        records: List[Dict[str, Any]]
    ) -> None:
        """批量插入记录"""
        if self.conn is None:
            raise DatabaseConnectionError("数据库未连接，请先调用 connect()")

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

    # ==========================================================================
    # 原生 SQL CRUD 实现
    # ==========================================================================

    def supports_crud(self) -> bool:
        """SQLite 支持直接 CRUD 操作"""
        return True

    def insert_row(
        self,
        table_name: str,
        data: Dict[str, Any],
        pk_column: str
    ) -> Any:
        """
        插入一行数据

        Args:
            table_name: 表名
            data: 列名到值的映射
            pk_column: 主键列名

        Returns:
            插入记录的主键值（lastrowid）
        """
        if self.conn is None:
            raise DatabaseConnectionError("数据库未连接，请先调用 connect()")

        columns = list(data.keys())
        col_names = ', '.join([f'`{c}`' for c in columns])
        placeholders = ', '.join(['?' for _ in columns])
        sql = f'INSERT INTO `{table_name}` ({col_names}) VALUES ({placeholders})'

        # 序列化参数
        params = tuple(self._serialize_value(v) for v in data.values())

        cursor = self.conn.execute(sql, params)
        return cursor.lastrowid

    def update_row(
        self,
        table_name: str,
        pk_column: str,
        pk_value: Any,
        data: Dict[str, Any]
    ) -> int:
        """
        更新一行数据

        Args:
            table_name: 表名
            pk_column: 主键列名
            pk_value: 主键值
            data: 要更新的列名到值的映射

        Returns:
            影响的行数
        """
        if self.conn is None:
            raise DatabaseConnectionError("数据库未连接，请先调用 connect()")

        set_clause = ', '.join([f'`{k}` = ?' for k in data.keys()])
        sql = f'UPDATE `{table_name}` SET {set_clause} WHERE `{pk_column}` = ?'

        params = tuple(self._serialize_value(v) for v in data.values())
        params = params + (self._serialize_value(pk_value),)

        cursor = self.conn.execute(sql, params)
        return cursor.rowcount

    def delete_row(
        self,
        table_name: str,
        pk_column: str,
        pk_value: Any
    ) -> int:
        """
        删除一行数据

        Args:
            table_name: 表名
            pk_column: 主键列名
            pk_value: 主键值

        Returns:
            影响的行数
        """
        if self.conn is None:
            raise DatabaseConnectionError("数据库未连接，请先调用 connect()")

        sql = f'DELETE FROM `{table_name}` WHERE `{pk_column}` = ?'
        cursor = self.conn.execute(sql, (self._serialize_value(pk_value),))
        return cursor.rowcount

    def select_by_pk(
        self,
        table_name: str,
        pk_column: str,
        pk_value: Any,
        columns: Optional[List[str]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        按主键查询一行

        Args:
            table_name: 表名
            pk_column: 主键列名
            pk_value: 主键值
            columns: 要查询的列名列表，None 表示所有列

        Returns:
            匹配的记录字典，未找到返回 None
        """
        if self.conn is None:
            raise DatabaseConnectionError("数据库未连接，请先调用 connect()")

        if columns:
            cols = ', '.join([f'`{c}`' for c in columns])
        else:
            cols = '*'

        sql = f'SELECT {cols} FROM `{table_name}` WHERE `{pk_column}` = ?'
        cursor = self.conn.execute(sql, (self._serialize_value(pk_value),))
        row = cursor.fetchone()

        if row is None:
            return None

        col_names = [desc[0] for desc in cursor.description]
        return dict(zip(col_names, row))

    def query_rows(
        self,
        table_name: str,
        where_clause: Optional[str] = None,
        params: Tuple[Any, ...] = (),
        columns: Optional[List[str]] = None,
        order_by: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        条件查询多行

        Args:
            table_name: 表名
            where_clause: WHERE 子句（不含 WHERE 关键字）
            params: WHERE 子句的参数
            columns: 要查询的列名列表，None 表示所有列
            order_by: ORDER BY 子句（不含 ORDER BY 关键字）
            limit: 最大返回行数
            offset: 跳过的行数

        Returns:
            记录字典列表
        """
        if self.conn is None:
            raise DatabaseConnectionError("数据库未连接，请先调用 connect()")

        if columns:
            cols = ', '.join([f'`{c}`' for c in columns])
        else:
            cols = '*'

        sql = f'SELECT {cols} FROM `{table_name}`'

        if where_clause:
            sql += f' WHERE {where_clause}'
        if order_by:
            sql += f' ORDER BY {order_by}'
        if limit is not None:
            sql += f' LIMIT {limit}'
        if offset is not None:
            sql += f' OFFSET {offset}'

        cursor = self.conn.execute(sql, params)
        col_names = [desc[0] for desc in cursor.description]
        return [dict(zip(col_names, row)) for row in cursor.fetchall()]

    def begin_transaction(self) -> None:
        """开始事务"""
        if self.conn is None:
            raise DatabaseConnectionError("数据库未连接，请先调用 connect()")
        self.conn.execute('BEGIN')

    def rollback_transaction(self) -> None:
        """回滚事务"""
        if self.conn is not None:
            self.conn.rollback()

    def commit_transaction(self) -> None:
        """提交事务"""
        if self.conn is not None:
            self.conn.commit()

    def _serialize_value(self, value: Any) -> Any:
        """
        序列化值为 SQLite 兼容格式

        Args:
            value: 要序列化的值

        Returns:
            SQLite 兼容的值
        """
        if value is None:
            return None

        if isinstance(value, bool):
            return 1 if value else 0

        if isinstance(value, (datetime, date, timedelta)):
            return TypeRegistry.serialize_for_text(value, type(value))

        if isinstance(value, (list, dict)):
            return json.dumps(value, ensure_ascii=False)

        # int, str, float, bytes 原样返回
        return value
