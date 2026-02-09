"""
Pytuck 数据库连接器抽象基类

提供统一的数据库操作接口，支持多种关系型数据库
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Tuple, Optional

from ..common.options import ConnectorOptions
from ..common.exceptions import UnsupportedOperationError
from ..common.typing import ColumnTypes


class DatabaseConnector(ABC):
    """
    通用数据库连接器抽象基类

    提供统一的数据库操作接口，支持：
    - 连接管理（connect/close）
    - 表结构读取（get_table_names/get_table_schema）
    - 数据读写（get_table_data/insert_records）
    - SQL 执行（execute/executemany）

    子类实现指南：
    1. 设置 DB_TYPE 类变量标识数据库类型
    2. 如需第三方依赖，设置 REQUIRED_DEPENDENCIES
    3. 设置 TYPE_TO_SQL 和 SQL_TO_TYPE 类型映射
    4. 实现所有抽象方法

    Example:
        class DuckDBConnector(DatabaseConnector):
            DB_TYPE = 'duckdb'
            REQUIRED_DEPENDENCIES = ['duckdb']
            ...
    """

    # 数据库类型标识
    DB_TYPE: str = ''

    # 所需第三方依赖（用于可用性检查）
    REQUIRED_DEPENDENCIES: List[str] = []

    # Python 类型到 SQL 类型的映射
    TYPE_TO_SQL: Dict[ColumnTypes, str] = {}

    # SQL 类型到 Python 类型的映射
    SQL_TO_TYPE: Dict[str, ColumnTypes] = {}

    def __init__(self, db_path: str, options: ConnectorOptions):
        """
        初始化连接器

        Args:
            db_path: 数据库文件路径或连接字符串
            options: 强类型的连接器配置选项
        """
        self.db_path = db_path
        self.options = options

    @abstractmethod
    def connect(self) -> None:
        """建立数据库连接"""
        pass

    @abstractmethod
    def close(self) -> None:
        """关闭数据库连接"""
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        """检查是否已连接"""
        pass

    @abstractmethod
    def get_table_names(self, exclude_system: bool = True) -> List[str]:
        """
        获取所有表名

        Args:
            exclude_system: 是否排除系统表和 Pytuck 元数据表

        Returns:
            表名列表
        """
        pass

    @abstractmethod
    def table_exists(self, table_name: str) -> bool:
        """
        检查表是否存在

        Args:
            table_name: 表名

        Returns:
            表是否存在
        """
        pass

    @abstractmethod
    def get_table_schema(self, table_name: str) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        """
        获取表结构

        Args:
            table_name: 表名

        Returns:
            (columns, primary_key) 元组
            - columns: 列信息列表
              [{'name': str, 'type': type, 'nullable': bool, 'primary_key': bool}, ...]
            - primary_key: 主键列名，如果没有主键则为 None
        """
        pass

    @abstractmethod
    def get_table_data(self, table_name: str) -> List[Dict[str, Any]]:
        """
        获取表中所有数据

        Args:
            table_name: 表名

        Returns:
            记录列表，每条记录是一个字典
        """
        pass

    @abstractmethod
    def execute(self, sql: str, params: tuple = ()) -> Any:
        """
        执行 SQL 语句

        Args:
            sql: SQL 语句
            params: 参数元组

        Returns:
            游标对象
        """
        pass

    @abstractmethod
    def executemany(self, sql: str, params_list: List[tuple]) -> None:
        """
        批量执行 SQL 语句

        Args:
            sql: SQL 语句
            params_list: 参数元组列表
        """
        pass

    @abstractmethod
    def create_table(
        self,
        table_name: str,
        columns: List[Dict[str, Any]],
        primary_key: Optional[str]
    ) -> None:
        """
        创建表

        Args:
            table_name: 表名
            columns: 列定义列表
                [{'name': str, 'type': type, 'nullable': bool, 'primary_key': bool}, ...]
            primary_key: 主键列名（可选，无主键表传 None）
        """
        pass

    @abstractmethod
    def drop_table(self, table_name: str) -> None:
        """
        删除表

        Args:
            table_name: 表名
        """
        pass

    @abstractmethod
    def insert_records(
        self,
        table_name: str,
        columns: List[str],
        records: List[Dict[str, Any]]
    ) -> None:
        """
        批量插入记录

        Args:
            table_name: 表名
            columns: 列名列表
            records: 记录列表
        """
        pass

    @abstractmethod
    def commit(self) -> None:
        """提交事务"""
        pass

    @classmethod
    def is_available(cls) -> bool:
        """
        检查依赖是否可用

        Returns:
            所有依赖都可用返回 True
        """
        for dep in cls.REQUIRED_DEPENDENCIES:
            try:
                __import__(dep)
            except ImportError:
                return False
        return True

    def __enter__(self) -> 'DatabaseConnector':
        """上下文管理器入口"""
        self.connect()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """上下文管理器退出"""
        self.close()

    # ==========================================================================
    # 原生 SQL CRUD 接口（用于支持直接数据库操作的后端）
    # ==========================================================================

    def supports_crud(self) -> bool:
        """
        是否支持直接 CRUD 操作

        返回 True 表示连接器支持 insert_row, update_row, delete_row 等方法，
        可绕过内存执行直接操作数据库。

        Returns:
            默认返回 False，子类可覆盖
        """
        return False

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
            插入记录的主键值

        Raises:
            UnsupportedOperationError: 如果连接器不支持直接 CRUD
        """
        raise UnsupportedOperationError(
            message="Direct CRUD not supported",
            details={"connector": self.__class__.__name__}
        )

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

        Raises:
            UnsupportedOperationError: 如果连接器不支持直接 CRUD
        """
        raise UnsupportedOperationError(
            message="Direct CRUD not supported",
            details={"connector": self.__class__.__name__}
        )

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

        Raises:
            UnsupportedOperationError: 如果连接器不支持直接 CRUD
        """
        raise UnsupportedOperationError(
            message="Direct CRUD not supported",
            details={"connector": self.__class__.__name__}
        )

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

        Raises:
            UnsupportedOperationError: 如果连接器不支持直接 CRUD
        """
        raise UnsupportedOperationError(
            message="Direct CRUD not supported",
            details={"connector": self.__class__.__name__}
        )

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
            where_clause: WHERE 子句（不含 WHERE 关键字），如 '"age" > ?'
            params: WHERE 子句的参数
            columns: 要查询的列名列表，None 表示所有列
            order_by: ORDER BY 子句（不含 ORDER BY 关键字）
            limit: 最大返回行数
            offset: 跳过的行数

        Returns:
            记录字典列表

        Raises:
            UnsupportedOperationError: 如果连接器不支持直接 CRUD
        """
        raise UnsupportedOperationError(
            message="Direct CRUD not supported",
            details={"connector": self.__class__.__name__}
        )

    def begin_transaction(self) -> None:
        """
        开始事务

        默认实现为空，子类可根据需要覆盖
        """
        pass

    def rollback_transaction(self) -> None:
        """
        回滚事务

        默认实现为空，子类可根据需要覆盖
        """
        pass

    def commit_transaction(self) -> None:
        """
        提交事务

        默认实现为空，子类可根据需要覆盖
        """
        pass
