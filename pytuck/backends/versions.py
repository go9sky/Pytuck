"""
存储引擎格式版本定义

各引擎的格式版本独立于库版本管理，便于向后兼容检测。
版本号为整数，每次格式变更时递增。
"""

# 各引擎的当前格式版本
ENGINE_FORMAT_VERSIONS = {
    'binary': 3,   # v3: 添加表和列 comment 支持
    'csv': 3,      # v3: 添加表和列 comment 支持
    'excel': 3,    # v3: 添加表和列 comment 支持
    'json': 2,     # v2: 添加表和列 comment 支持
    'sqlite': 2,   # v2: 添加表和列 comment 支持
    'xml': 2,      # v2: 添加表和列 comment 支持
}


def get_format_version(engine_name: str) -> int:
    """
    获取指定引擎的格式版本

    Args:
        engine_name: 引擎名称

    Returns:
        格式版本号
    """
    return ENGINE_FORMAT_VERSIONS.get(engine_name, 1)
