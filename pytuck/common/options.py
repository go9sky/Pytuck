"""
Pytuck 配置选项 dataclass 定义

该模块定义了所有后端和连接器的配置选项，替代原有的 **kwargs 参数。
"""
from dataclasses import dataclass
from typing import Optional, Union, Dict, Literal


@dataclass(slots=True)
class SqliteConnectorOptions:
    """SQLite 连接器配置选项"""
    check_same_thread: bool = True  # 检查同一线程
    timeout: Optional[float] = None  # 连接超时时间
    isolation_level: Optional[str] = None  # 事务隔离级别


# Connector 选项联合类型
ConnectorOptions = Union[SqliteConnectorOptions]


@dataclass(slots=True)
class JsonBackendOptions:
    """JSON 后端配置选项"""
    indent: Optional[int] = None  # 缩进空格数
    ensure_ascii: bool = False  # 是否强制 ASCII 编码
    impl: Optional[str] = None  # 指定JSON库名：'orjson', 'ujson', 'json' 等


@dataclass(slots=True)
class CsvBackendOptions:
    """CSV 后端配置选项"""
    encoding: str = 'utf-8-sig'  # 字符编码（默认带 BOM，兼容 Excel）
    delimiter: str = ','  # 字段分隔符
    indent: Optional[int] = None  # json元数据缩进空格数（无缩进时为 None）


@dataclass(slots=True)
class SqliteBackendOptions(SqliteConnectorOptions):
    """SQLite 后端配置选项"""
    use_native_sql: bool = True  # 使用原生 SQL 模式，直接执行 SQL 而非全量加载/保存


@dataclass(slots=True)
class ExcelBackendOptions:
    """Excel 后端配置选项"""
    read_only: bool = False  # 只读，只读情况下显著提升读取性能，但不可修改数据
    hide_metadata_sheets: bool = True  # 是否隐藏元数据工作表（_metadata 和 _pytuck_tables），默认隐藏

    # 行号映射选项
    row_number_mapping: Optional[Literal['as_pk', 'field']] = None
    # None: 不做任何映射（默认）
    # 'as_pk': 将 Excel 行号作为主键值
    # 'field': 将 Excel 行号写入指定字段

    row_number_field_name: str = 'row_num'
    # 当 row_number_mapping == 'field' 时使用的目标字段名

    row_number_override: bool = False
    # 是否在存在 _pytuck_tables（即 Pytuck 自有 schema）时强制应用行号映射

    persist_row_number: bool = False
    # 是否在保存时将行号写入文件（仅对 mapping == 'field' 有意义）


@dataclass(slots=True)
class XmlBackendOptions:
    """XML 后端配置选项"""
    encoding: str = 'utf-8'  # 字符编码
    pretty_print: bool = True  # 是否格式化输出


@dataclass(slots=True)
class BinaryBackendOptions:
    """Binary 后端配置选项"""
    lazy_load: bool = False  # 是否懒加载（只加载 schema 和索引，按需读取数据）

    # 加密选项（v4 新增）
    encryption: Optional[Literal['low', 'medium', 'high']] = None  # 加密等级: 'low' | 'medium' | 'high' | None
    password: Optional[str] = None    # 加密密码（仅 encryption 非 None 时生效）


# Backend 选项联合类型
BackendOptions = Union[
    JsonBackendOptions,
    CsvBackendOptions,
    SqliteBackendOptions,
    ExcelBackendOptions,
    XmlBackendOptions,
    BinaryBackendOptions
]


# 默认选项获取函数
def get_default_backend_options(engine: str) -> BackendOptions:
    """根据引擎类型返回默认选项"""
    defaults: Dict[str, BackendOptions] = {
        'json': JsonBackendOptions(),
        'csv': CsvBackendOptions(),
        'sqlite': SqliteBackendOptions(),
        'excel': ExcelBackendOptions(),
        'xml': XmlBackendOptions(),
        'binary': BinaryBackendOptions()
    }
    return defaults.get(engine, BinaryBackendOptions())


def get_default_connector_options(db_type: str) -> ConnectorOptions:
    """根据连接器类型返回默认选项"""
    defaults: Dict[str, ConnectorOptions] = {
        'sqlite': SqliteConnectorOptions()
    }
    return defaults.get(db_type, SqliteConnectorOptions())
