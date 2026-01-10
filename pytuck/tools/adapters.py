"""
Pytuck 外部数据库源适配器

提供从外部关系型数据库导入数据的适配器接口。

此模块是对 connectors 模块的薄包装层，提供向后兼容的别名。
实际实现位于 pytuck.connectors 模块。
"""

from typing import Any, List, Optional

from ..connectors import (
    DatabaseConnector,
    SQLiteConnector,
    get_connector,
    CONNECTORS,
)
from ..common.options import ConnectorOptions


# 向后兼容别名
DatabaseSourceAdapter = DatabaseConnector
"""外部数据库源适配器基类（DatabaseConnector 的别名）"""

SQLiteSourceAdapter = SQLiteConnector
"""SQLite 数据库源适配器（SQLiteConnector 的别名）"""

# 适配器注册表（指向 CONNECTORS）
ADAPTERS = CONNECTORS


def get_source_adapter(
    source_type: str,
    source_path: str,
    options: Optional[ConnectorOptions] = None
) -> DatabaseConnector:
    """
    获取数据库源适配器实例

    这是 get_connector() 的别名，保持向后兼容。

    Args:
        source_type: 数据库类型（'sqlite', 等）
        source_path: 数据库路径或连接字符串
        options: 强类型的连接器配置选项

    Returns:
        适配器实例

    Raises:
        ValueError: 不支持的数据库类型
    """
    return get_connector(source_type, source_path, options)


def get_available_source_types() -> List[str]:
    """
    获取所有可用的数据库源类型

    Returns:
        可用类型列表
    """
    return list(CONNECTORS.keys())
