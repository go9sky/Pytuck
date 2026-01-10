"""
Pytuck 数据迁移工具

提供在不同存储引擎之间迁移数据的功能
"""

from typing import Any, Dict, Optional

from ..backends import get_backend
from ..exceptions import MigrationError


def migrate_engine(
    source_path: str,
    source_engine: str,
    target_path: str,
    target_engine: str,
    *,
    overwrite: bool = False,
    source_options: Optional[Dict[str, Any]] = None,
    target_options: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    在不同存储引擎之间迁移数据

    将数据从一个存储引擎迁移到另一个存储引擎。
    支持的引擎: binary, json, csv, sqlite, excel, xml

    Args:
        source_path: 源数据文件路径
        source_engine: 源引擎名称 ('binary', 'json', 'csv', 'sqlite', 'excel', 'xml')
        target_path: 目标数据文件路径
        target_engine: 目标引擎名称
        overwrite: 是否覆盖已存在的目标文件（默认 False）
        source_options: 源引擎的额外选项
        target_options: 目标引擎的额外选项

    Returns:
        迁移统计信息字典:
        {
            'tables': 迁移的表数量,
            'records': 迁移的总记录数,
            'source_engine': 源引擎名称,
            'target_engine': 目标引擎名称
        }

    Raises:
        MigrationError: 迁移过程中发生错误
        FileNotFoundError: 源文件不存在
        FileExistsError: 目标文件已存在且 overwrite=False

    Example:
        from pytuck.tools.migrate import migrate_engine

        # 从二进制迁移到 JSON
        result = migrate_engine(
            source_path='data.db',
            source_engine='binary',
            target_path='data.json',
            target_engine='json'
        )
        print(f"迁移完成: {result['tables']} 个表, {result['records']} 条记录")

        # 从 JSON 迁移到 SQLite（覆盖已存在的文件）
        migrate_engine(
            source_path='data.json',
            source_engine='json',
            target_path='data.sqlite',
            target_engine='sqlite',
            overwrite=True
        )
    """
    source_options = source_options or {}
    target_options = target_options or {}

    # 获取源后端
    try:
        source_backend = get_backend(source_engine, source_path, **source_options)
    except ValueError as e:
        raise MigrationError(f"无法创建源引擎 '{source_engine}': {e}")

    # 检查源文件是否存在
    if not source_backend.exists():
        raise FileNotFoundError(f"源文件不存在: {source_path}")

    # 获取目标后端
    try:
        target_backend = get_backend(target_engine, target_path, **target_options)
    except ValueError as e:
        raise MigrationError(f"无法创建目标引擎 '{target_engine}': {e}")

    # 检查目标文件是否已存在
    if target_backend.exists() and not overwrite:
        raise FileExistsError(
            f"目标文件已存在: {target_path}。"
            f"设置 overwrite=True 以覆盖。"
        )

    # 如果需要覆盖，先删除目标文件
    if target_backend.exists() and overwrite:
        target_backend.delete()

    # 加载源数据
    try:
        tables = source_backend.load()
    except Exception as e:
        raise MigrationError(f"从源文件加载数据失败: {e}")

    # 统计记录数
    total_records = sum(len(table.data) for table in tables.values())

    # 保存到目标
    try:
        target_backend.save(tables)
    except Exception as e:
        raise MigrationError(f"保存数据到目标文件失败: {e}")

    # 返回统计信息
    return {
        'tables': len(tables),
        'records': total_records,
        'source_engine': source_engine,
        'target_engine': target_engine,
        'source_path': source_path,
        'target_path': target_path
    }


def get_available_engines() -> Dict[str, bool]:
    """
    获取所有可用的存储引擎及其状态

    Returns:
        引擎名称到可用状态的字典
        {
            'binary': True,   # 始终可用
            'json': True,     # 始终可用
            'csv': True,      # 始终可用
            'sqlite': True,   # 始终可用
            'excel': False,   # 需要 openpyxl
            'xml': False      # 需要 lxml
        }

    Example:
        from pytuck.tools.migrate import get_available_engines

        engines = get_available_engines()
        for name, available in engines.items():
            status = "✓" if available else "✗"
            print(f"{status} {name}")
    """
    from ..backends.binary import BinaryBackend
    from ..backends.json_backend import JSONBackend
    from ..backends.csv_backend import CSVBackend
    from ..backends.sqlite_backend import SQLiteBackend
    from ..backends.excel_backend import ExcelBackend
    from ..backends.xml_backend import XMLBackend

    return {
        'binary': BinaryBackend.is_available(),
        'json': JSONBackend.is_available(),
        'csv': CSVBackend.is_available(),
        'sqlite': SQLiteBackend.is_available(),
        'excel': ExcelBackend.is_available(),
        'xml': XMLBackend.is_available()
    }
