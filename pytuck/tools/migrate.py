"""
Pytuck 数据迁移工具

提供在不同存储引擎之间迁移数据的功能，以及从外部数据库导入数据的功能
"""

from typing import Any, Dict, List, Optional

from ..backends import get_backend
from ..common.exceptions import MigrationError
from ..core.storage import Table
from ..core.orm import Column
from ..common.options import BackendOptions, ConnectorOptions, get_default_backend_options, get_default_connector_options
from .adapters import get_source_adapter, get_available_source_types


def migrate_engine(
    source_path: str,
    source_engine: str,
    target_path: str,
    target_engine: str,
    *,
    overwrite: bool = False,
    source_options: Optional[BackendOptions] = None,
    target_options: Optional[BackendOptions] = None
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
        source_options: 源引擎的强类型配置选项
        target_options: 目标引擎的强类型配置选项

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
    # 提供默认选项
    if source_options is None:
        source_options = get_default_backend_options(source_engine)
    if target_options is None:
        target_options = get_default_backend_options(target_engine)

    # 获取源后端
    try:
        source_backend = get_backend(source_engine, source_path, source_options)
    except ValueError as e:
        raise MigrationError(f"无法创建源引擎 '{source_engine}': {e}")

    # 检查源文件是否存在
    if not source_backend.exists():
        raise FileNotFoundError(f"源文件不存在: {source_path}")

    # 获取目标后端
    try:
        target_backend = get_backend(target_engine, target_path, target_options)
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


def import_from_database(
    source_path: str,
    target_path: str,
    target_engine: str = 'binary',
    *,
    source_type: str = 'sqlite',
    tables: Optional[List[str]] = None,
    primary_key_map: Optional[Dict[str, str]] = None,
    exclude_tables: Optional[List[str]] = None,
    schema_only: bool = False,
    overwrite: bool = False,
    source_options: Optional[ConnectorOptions] = None,
    target_options: Optional[BackendOptions] = None
) -> Dict[str, Any]:
    """
    从外部关系型数据库导入数据到 Pytuck 格式

    支持从普通的 SQLite 数据库（非 Pytuck 格式）导入数据，
    自动分析表结构并转换为 Pytuck 兼容格式。

    Args:
        source_path: 源数据库文件路径
        target_path: 目标 Pytuck 数据文件路径
        target_engine: 目标引擎名称 ('binary', 'json', 'csv', 'sqlite', 'excel', 'xml')
        source_type: 源数据库类型 ('sqlite')，可扩展支持其他数据库
        tables: 要导入的表名列表，None 表示导入全部
        primary_key_map: 表名到主键列名的映射，用于指定没有主键的表的主键
        exclude_tables: 要排除的表名列表
        schema_only: 仅导入表结构，不导入数据
        overwrite: 是否覆盖已存在的目标文件
        source_options: 源数据库连接的强类型配置选项
        target_options: 目标引擎的强类型配置选项

    Returns:
        导入统计信息字典:
        {
            'tables': 导入的表数量,
            'records': 导入的总记录数,
            'source_type': 源数据库类型,
            'target_engine': 目标引擎名称,
            'source_path': 源路径,
            'target_path': 目标路径,
            'table_details': {
                'table_name': {'records': N, 'columns': [...], 'primary_key': 'pk_col'}
            }
        }

    Raises:
        MigrationError: 导入过程中发生错误
        FileNotFoundError: 源文件不存在
        FileExistsError: 目标文件已存在且 overwrite=False
        ValueError: 不支持的数据库类型

    Example:
        from pytuck.tools.migrate import import_from_database

        # 从普通 SQLite 导入到 Pytuck JSON 格式
        result = import_from_database(
            source_path='external.db',
            target_path='data.json',
            target_engine='json'
        )
        print(f"导入完成: {result['tables']} 个表, {result['records']} 条记录")

        # 指定主键和排除表
        result = import_from_database(
            source_path='external.db',
            target_path='data.db',
            target_engine='binary',
            primary_key_map={'users': 'user_id'},
            exclude_tables=['sqlite_sequence'],
            overwrite=True
        )

        # 仅导入表结构
        result = import_from_database(
            source_path='external.db',
            target_path='schema.json',
            target_engine='json',
            schema_only=True
        )
    """
    import os

    # 提供默认选项
    if source_options is None:
        source_options = get_default_connector_options(source_type)
    if target_options is None:
        target_options = get_default_backend_options(target_engine)
    primary_key_map = primary_key_map or {}
    exclude_tables = exclude_tables or []

    # 检查源文件是否存在
    if not os.path.exists(source_path):
        raise FileNotFoundError(f"源数据库文件不存在: {source_path}")

    # 获取目标后端并检查是否已存在
    try:
        target_backend = get_backend(target_engine, target_path, target_options)
    except ValueError as e:
        raise MigrationError(f"无法创建目标引擎 '{target_engine}': {e}")

    if target_backend.exists() and not overwrite:
        raise FileExistsError(
            f"目标文件已存在: {target_path}。"
            f"设置 overwrite=True 以覆盖。"
        )

    # 获取源数据库适配器
    try:
        adapter = get_source_adapter(source_type, source_path, source_options)
    except ValueError as e:
        raise MigrationError(str(e))

    pytuck_tables: Dict[str, Table] = {}
    total_records = 0
    table_details: Dict[str, Dict[str, Any]] = {}

    try:
        with adapter:
            # 获取要导入的表
            all_table_names = adapter.get_table_names()

            if tables:
                # 只导入指定的表
                import_table_names = [t for t in tables if t in all_table_names]
            else:
                # 导入全部表，排除指定的表
                import_table_names = [t for t in all_table_names if t not in exclude_tables]

            if not import_table_names:
                raise MigrationError("没有找到要导入的表")

            # 处理每个表
            for table_name in import_table_names:
                columns_info, detected_pk = adapter.get_table_schema(table_name)

                # 确定主键：优先使用 primary_key_map，其次使用检测到的主键
                pk = primary_key_map.get(table_name) or detected_pk
                need_rowid = pk is None

                if need_rowid:
                    # 没有主键，自动创建 _rowid 列
                    pk = '_rowid'
                    columns_info.insert(0, {
                        'name': '_rowid',
                        'type': int,
                        'nullable': False,
                        'primary_key': True
                    })

                # 创建 Column 列表
                columns: List[Column] = []
                for col_info in columns_info:
                    col = Column(
                        col_info['name'],
                        col_info['type'],
                        nullable=col_info.get('nullable', True),
                        primary_key=col_info.get('primary_key', False),
                        index=False  # 默认不创建索引
                    )
                    columns.append(col)

                # 创建 Table
                assert pk is not None, f"Primary key not found for table {table_name}"
                table = Table(table_name, columns, pk)

                # 导入数据
                record_count = 0
                if not schema_only:
                    rows = adapter.get_table_data(table_name)
                    for i, row in enumerate(rows, 1):
                        # 转换为可变字典
                        record = dict(row)

                        if need_rowid:
                            record['_rowid'] = i

                        # 获取主键值
                        assert pk is not None, f"Primary key not found for table {table_name}"
                        pk_value = record[pk]
                        table.data[pk_value] = record

                        # 更新 next_id（如果主键是整数）
                        if isinstance(pk_value, int):
                            table.next_id = max(table.next_id, pk_value + 1)

                    record_count = len(rows)
                    total_records += record_count

                pytuck_tables[table_name] = table
                table_details[table_name] = {
                    'records': record_count,
                    'columns': [c.name for c in columns],
                    'primary_key': pk,
                    'auto_rowid': need_rowid
                }

    except Exception as e:
        if isinstance(e, (MigrationError, FileNotFoundError, FileExistsError)):
            raise
        raise MigrationError(f"从源数据库读取数据失败: {e}")

    # 如果需要覆盖，先删除目标文件
    if target_backend.exists() and overwrite:
        target_backend.delete()

    # 保存到目标
    try:
        target_backend.save(pytuck_tables)
    except Exception as e:
        raise MigrationError(f"保存数据到目标文件失败: {e}")

    return {
        'tables': len(pytuck_tables),
        'records': total_records,
        'source_type': source_type,
        'target_engine': target_engine,
        'source_path': source_path,
        'target_path': target_path,
        'table_details': table_details
    }
