"""
Pytuck 数据库连接器模块

提供统一的数据库连接和操作接口，用于：
- Storage 后端（如 SQLiteBackend）
- 数据迁移工具（import_from_database）

支持的数据库类型：
- sqlite: SQLite 数据库（内置，无需额外依赖）
- duckdb: DuckDB 数据库（未来扩展）
"""

from typing import Any, Dict, Type, Optional

from .base import DatabaseConnector
from .sqlite_connector import SQLiteConnector
from ..common.options import ConnectorOptions, get_default_connector_options


# 连接器注册表
CONNECTORS: Dict[str, Type[DatabaseConnector]] = {
    'sqlite': SQLiteConnector,
    # 未来扩展：
    # 'duckdb': DuckDBConnector,
    # 'mysql': MySQLConnector,
}


def get_connector(db_type: str, db_path: str, options: Optional[ConnectorOptions] = None) -> DatabaseConnector:
    """
    获取数据库连接器实例

    Args:
        db_type: 数据库类型（'sqlite' 等）
        db_path: 数据库路径或连接字符串
        options: 强类型的连接器配置选项

    Returns:
        连接器实例（未连接状态，需调用 connect() 或使用 with 语句）

    Raises:
        ValueError: 不支持的数据库类型

    Example:
        from pytuck.common.options import SqliteConnectorOptions

        # 使用上下文管理器
        opts = SqliteConnectorOptions(check_same_thread=False)
        with get_connector('sqlite', 'data.db', opts) as conn:
            tables = conn.get_table_names()

        # 手动管理连接
        conn = get_connector('sqlite', 'data.db')
        conn.connect()
        try:
            tables = conn.get_table_names()
        finally:
            conn.close()
    """
    if db_type not in CONNECTORS:
        available = ', '.join(CONNECTORS.keys())
        raise ValueError(f"不支持的数据库类型: '{db_type}'。可用类型: {available}")

    # 如果没有提供选项，使用默认选项
    if options is None:
        options = get_default_connector_options(db_type)

    connector_class = CONNECTORS[db_type]
    return connector_class(db_path, options)


def get_available_connectors() -> Dict[str, bool]:
    """
    获取所有连接器及其可用状态

    Returns:
        连接器类型到可用状态的字典
        {
            'sqlite': True,   # 始终可用
            'duckdb': False,  # 需要 duckdb 包
        }
    """
    return {
        db_type: connector_class.is_available()
        for db_type, connector_class in CONNECTORS.items()
    }


__all__ = [
    'DatabaseConnector',
    'SQLiteConnector',
    'get_connector',
    'get_available_connectors',
    'CONNECTORS',
]
