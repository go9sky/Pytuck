"""
Pytuck 类型系统

定义数据类型编码和编解码器
"""

from abc import ABC, abstractmethod
from enum import IntEnum
from typing import Any, Type
import struct

from .exceptions import SerializationError


class TypeCode(IntEnum):
    """类型编码"""
    INT = 1
    STR = 2
    FLOAT = 3
    BOOL = 4
    BYTES = 5


class TypeCodec(ABC):
    """类型编解码器抽象基类"""

    @abstractmethod
    def encode(self, value: Any) -> bytes:
        """编码值为字节"""
        pass

    @abstractmethod
    def decode(self, data: bytes) -> tuple[Any, int]:
        """解码字节为值，返回(值, 消耗的字节数)"""
        pass


class IntCodec(TypeCodec):
    """整型编解码器"""

    def encode(self, value: Any) -> bytes:
        if value is None:
            return b''
        if not isinstance(value, int):
            raise SerializationError(f"Expected int, got {type(value)}")
        return struct.pack('<q', value)  # 8 bytes, signed long long, little-endian

    def decode(self, data: bytes) -> tuple[int, int]:
        if len(data) < 8:
            raise SerializationError(f"Not enough data to decode int (need 8 bytes, got {len(data)})")
        value = struct.unpack('<q', data[:8])[0]
        return value, 8


class StrCodec(TypeCodec):
    """字符串编解码器"""

    def encode(self, value: Any) -> bytes:
        if value is None:
            return b''
        if not isinstance(value, str):
            raise SerializationError(f"Expected str, got {type(value)}")
        encoded = value.encode('utf-8')
        length = len(encoded)
        return struct.pack('<H', length) + encoded  # 2 bytes length + data

    def decode(self, data: bytes) -> tuple[str, int]:
        if len(data) < 2:
            raise SerializationError(f"Not enough data to decode str length")
        length = struct.unpack('<H', data[:2])[0]
        if len(data) < 2 + length:
            raise SerializationError(f"Not enough data to decode str (need {2 + length}, got {len(data)})")
        value = data[2:2+length].decode('utf-8')
        return value, 2 + length


class FloatCodec(TypeCodec):
    """浮点型编解码器"""

    def encode(self, value: Any) -> bytes:
        if value is None:
            return b''
        if not isinstance(value, (float, int)):
            raise SerializationError(f"Expected float, got {type(value)}")
        return struct.pack('<d', float(value))  # 8 bytes, double, little-endian

    def decode(self, data: bytes) -> tuple[float, int]:
        if len(data) < 8:
            raise SerializationError(f"Not enough data to decode float (need 8 bytes, got {len(data)})")
        value = struct.unpack('<d', data[:8])[0]
        return value, 8


class BoolCodec(TypeCodec):
    """布尔型编解码器"""

    def encode(self, value: Any) -> bytes:
        if value is None:
            return b''
        if not isinstance(value, bool):
            raise SerializationError(f"Expected bool, got {type(value)}")
        return struct.pack('<?', value)  # 1 byte

    def decode(self, data: bytes) -> tuple[bool, int]:
        if len(data) < 1:
            raise SerializationError(f"Not enough data to decode bool")
        value = struct.unpack('<?', data[:1])[0]
        return value, 1


class BytesCodec(TypeCodec):
    """字节型编解码器"""

    def encode(self, value: Any) -> bytes:
        if value is None:
            return b''
        if not isinstance(value, bytes):
            raise SerializationError(f"Expected bytes, got {type(value)}")
        length = len(value)
        return struct.pack('<I', length) + value  # 4 bytes length + data

    def decode(self, data: bytes) -> tuple[bytes, int]:
        if len(data) < 4:
            raise SerializationError(f"Not enough data to decode bytes length")
        length = struct.unpack('<I', data[:4])[0]
        if len(data) < 4 + length:
            raise SerializationError(f"Not enough data to decode bytes (need {4 + length}, got {len(data)})")
        value = data[4:4+length]
        return value, 4 + length


class TypeRegistry:
    """类型注册表"""

    _codecs = {
        int: (TypeCode.INT, IntCodec()),
        str: (TypeCode.STR, StrCodec()),
        float: (TypeCode.FLOAT, FloatCodec()),
        bool: (TypeCode.BOOL, BoolCodec()),
        bytes: (TypeCode.BYTES, BytesCodec()),
    }

    _type_code_to_type = {
        TypeCode.INT: int,
        TypeCode.STR: str,
        TypeCode.FLOAT: float,
        TypeCode.BOOL: bool,
        TypeCode.BYTES: bytes,
    }

    @classmethod
    def get_codec(cls, col_type: Type) -> tuple[TypeCode, TypeCodec]:
        """获取类型的编解码器"""
        if col_type not in cls._codecs:
            raise SerializationError(f"Unsupported type: {col_type}")
        return cls._codecs[col_type]

    @classmethod
    def get_type_from_code(cls, type_code: TypeCode) -> Type:
        """根据类型编码获取Python类型"""
        if type_code not in cls._type_code_to_type:
            raise SerializationError(f"Unknown type code: {type_code}")
        return cls._type_code_to_type[type_code]

    @classmethod
    def register(cls, py_type: Type, type_code: TypeCode, codec: TypeCodec) -> None:
        """注册自定义类型"""
        cls._codecs[py_type] = (type_code, codec)
        cls._type_code_to_type[type_code] = py_type
