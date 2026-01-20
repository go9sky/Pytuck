"""
Pytuck 配置选项 dataclass 定义

该模块定义了所有后端和连接器的配置选项，替代原有的 **kwargs 参数。
"""
from dataclasses import dataclass
from typing import Optional, Union, Dict


@dataclass(slots=True)
class JsonBackendOptions:
    """JSON 后端配置选项"""
    indent: int = 2  # 缩进空格数
    ensure_ascii: bool = False  # 是否强制 ASCII 编码
    impl: Optional[str] = None  # 指定JSON库名：'orjson', 'ujson', 'json'等


@dataclass(slots=True)
class CsvBackendOptions:
    """CSV 后端配置选项"""
    encoding: str = 'utf-8'  # 字符编码
    delimiter: str = ','  # 字段分隔符
    indent: Optional[int] = None  # json元数据缩进空格数（无缩进时为 None）


@dataclass(slots=True)
class SqliteBackendOptions:
    """SQLite 后端配置选项"""
    check_same_thread: bool = True  # 检查同一线程
    timeout: Optional[float] = None  # 连接超时时间


@dataclass(slots=True)
class ExcelBackendOptions:
    """Excel 后端配置选项"""
    read_only: bool = False  # 只读，只读情况下显著提升读取性能，但不可修改数据


@dataclass(slots=True)
class XmlBackendOptions:
    """XML 后端配置选项"""
    encoding: str = 'utf-8'  # 字符编码
    pretty_print: bool = True  # 是否格式化输出


@dataclass(slots=True)
class BinaryBackendOptions:
    """Binary 后端配置选项"""
    lazy_load: bool = False  # 是否懒加载（只加载 schema 和索引，按需读取数据）


# Backend 选项联合类型
BackendOptions = Union[
    JsonBackendOptions,
    CsvBackendOptions,
    SqliteBackendOptions,
    ExcelBackendOptions,
    XmlBackendOptions,
    BinaryBackendOptions
]


@dataclass(slots=True)
class SqliteConnectorOptions:
    """SQLite 连接器配置选项"""
    check_same_thread: bool = True  # 检查同一线程
    timeout: Optional[float] = None  # 连接超时时间
    isolation_level: Optional[str] = None  # 事务隔离级别


# Connector 选项联合类型
ConnectorOptions = Union[SqliteConnectorOptions]


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
