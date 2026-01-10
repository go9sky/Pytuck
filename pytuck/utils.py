"""
Pytuck 工具函数
"""

import hashlib
from typing import Any


def compute_hash(value: Any) -> int:
    """计算值的哈希值（用于索引）"""
    if value is None:
        return 0

    if isinstance(value, (int, float)):
        return hash(value)
    elif isinstance(value, str):
        return hash(value)
    elif isinstance(value, bytes):
        return int(hashlib.md5(value).hexdigest()[:16], 16)
    elif isinstance(value, bool):
        return hash(value)
    else:
        return hash(str(value))


def compute_checksum(data: bytes) -> int:
    """计算数据的校验和（CRC32）"""
    import zlib
    return zlib.crc32(data) & 0xffffffff


def pad_bytes(data: bytes, length: int, pad_char: bytes = b'\x00') -> bytes:
    """填充字节到指定长度"""
    if len(data) >= length:
        return data[:length]
    return data + pad_char * (length - len(data))


def unpad_bytes(data: bytes, pad_char: bytes = b'\x00') -> bytes:
    """移除填充字节"""
    return data.rstrip(pad_char)
