"""
Pytuck 异常定义
"""

from typing import Any


class PytuckException(Exception):
    """Pytuck 基础异常类"""


class TableNotFoundError(PytuckException):
    """表不存在异常"""
    def __init__(self, table_name: str):
        self.table_name = table_name
        super().__init__(f"Table '{table_name}' not found")


class RecordNotFoundError(PytuckException):
    """记录不存在异常"""
    def __init__(self, table_name: str, pk: Any):
        self.table_name = table_name
        self.pk = pk
        super().__init__(f"Record with primary key '{pk}' not found in table '{table_name}'")


class DuplicateKeyError(PytuckException):
    """主键重复异常"""
    def __init__(self, table_name: str, pk: Any):
        self.table_name = table_name
        self.pk = pk
        super().__init__(f"Duplicate primary key '{pk}' in table '{table_name}'")


class TransactionError(PytuckException):
    """事务异常"""


class SerializationError(PytuckException):
    """序列化/反序列化异常"""


class ValidationError(PytuckException):
    """数据验证异常"""


class ColumnNotFoundError(PytuckException):
    """列不存在异常"""
    def __init__(self, table_name: str, column_name: str):
        self.table_name = table_name
        self.column_name = column_name
        super().__init__(f"Column '{column_name}' not found in table '{table_name}'")


class PytuckIndexError(PytuckException):
    """索引异常"""


class MigrationError(PytuckException):
    """数据迁移异常"""


class EncryptionError(PytuckException):
    """加密/解密异常"""
