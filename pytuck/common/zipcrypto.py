"""
Pytuck ZipCrypto 加密模块 - 纯 Python 实现

实现 PKZIP 传统加密算法（ZipCrypto），用于创建带密码保护的 ZIP 文件。

安全性说明：
    ZipCrypto 是一种较弱的加密算法，仅适合防止普通用户随意查看。
    如需高安全性，请使用 Binary 后端的加密功能（支持 ChaCha20）。
"""

import os
from typing import List, Tuple


def _make_crc_table() -> List[int]:
    """生成 ZipCrypto 使用的 CRC32 查找表"""
    crc_table = []
    for n in range(256):
        c = n
        for _ in range(8):
            if c & 1:
                c = 0xEDB88320 ^ (c >> 1)
            else:
                c = c >> 1
        crc_table.append(c)
    return crc_table


# 预计算的 CRC 表
_CRC_TABLE = _make_crc_table()


def _crc32_byte(crc: int, byte: int) -> int:
    """
    使用单个字节更新 CRC32 值

    这是 ZipCrypto 标准使用的 CRC32 计算方法。

    Args:
        crc: 当前 CRC 值
        byte: 要处理的字节

    Returns:
        更新后的 CRC 值
    """
    return _CRC_TABLE[(crc ^ byte) & 0xFF] ^ (crc >> 8)


class ZipCryptoEncryptor:
    """
    ZipCrypto 加密器

    实现 PKZIP 传统加密算法，用于加密 ZIP 文件条目。

    Example:
        >>> encryptor = ZipCryptoEncryptor(b"password")
        >>> ciphertext = encryptor.encrypt(b"hello world", crc32=0x12345678)
    """

    def __init__(self, password: bytes) -> None:
        """
        初始化 ZipCrypto 加密器

        Args:
            password: 密码（bytes 类型）
        """
        self._keys = [0x12345678, 0x23456789, 0x34567890]
        # 使用密码初始化 keys
        for byte in password:
            self._update_keys(byte)

    def _update_keys(self, byte: int) -> None:
        """
        使用一个字节更新内部 keys 状态

        Args:
            byte: 输入字节（0-255）
        """
        self._keys[0] = _crc32_byte(self._keys[0], byte)
        self._keys[1] = ((self._keys[1] + (self._keys[0] & 0xFF)) * 134775813 + 1) & 0xFFFFFFFF
        self._keys[2] = _crc32_byte(self._keys[2], (self._keys[1] >> 24) & 0xFF)

    def _stream_byte(self) -> int:
        """
        生成一个伪随机密钥流字节

        Returns:
            密钥流字节（0-255）
        """
        temp = (self._keys[2] | 2) & 0xFFFF
        return ((temp * (temp ^ 1)) >> 8) & 0xFF

    def _encrypt_byte(self, plaintext_byte: int) -> int:
        """
        加密单个字节

        Args:
            plaintext_byte: 明文字节

        Returns:
            密文字节
        """
        stream = self._stream_byte()
        ciphertext_byte = plaintext_byte ^ stream
        self._update_keys(plaintext_byte)
        return ciphertext_byte

    def encrypt(self, plaintext: bytes, crc32: int) -> bytes:
        """
        加密数据（包含 12 字节加密头）

        Args:
            plaintext: 明文数据
            crc32: 原始数据的 CRC32 值（用于生成加密头）

        Returns:
            加密后的数据（12 字节加密头 + 加密数据）
        """
        # 生成 12 字节加密头
        # 前 11 字节是随机数据，最后 1 字节是 CRC32 的高字节（用于密码校验）
        header = bytearray(os.urandom(11))
        header.append((crc32 >> 24) & 0xFF)

        # 加密头
        encrypted_header = bytearray()
        for byte in header:
            encrypted_header.append(self._encrypt_byte(byte))

        # 加密数据
        encrypted_data = bytearray()
        for byte in plaintext:
            encrypted_data.append(self._encrypt_byte(byte))

        return bytes(encrypted_header) + bytes(encrypted_data)


class ZipCryptoDecryptor:
    """
    ZipCrypto 解密器

    用于解密 ZipCrypto 加密的数据。
    注意：Python 标准库 zipfile 已支持 ZipCrypto 解密，此类主要用于测试和特殊场景。
    """

    def __init__(self, password: bytes) -> None:
        """
        初始化 ZipCrypto 解密器

        Args:
            password: 密码（bytes 类型）
        """
        self._keys = [0x12345678, 0x23456789, 0x34567890]
        # 使用密码初始化 keys
        for byte in password:
            self._update_keys(byte)

    def _update_keys(self, byte: int) -> None:
        """使用一个字节更新内部 keys 状态"""
        self._keys[0] = _crc32_byte(self._keys[0], byte)
        self._keys[1] = ((self._keys[1] + (self._keys[0] & 0xFF)) * 134775813 + 1) & 0xFFFFFFFF
        self._keys[2] = _crc32_byte(self._keys[2], (self._keys[1] >> 24) & 0xFF)

    def _stream_byte(self) -> int:
        """生成一个伪随机密钥流字节"""
        temp = (self._keys[2] | 2) & 0xFFFF
        return ((temp * (temp ^ 1)) >> 8) & 0xFF

    def _decrypt_byte(self, ciphertext_byte: int) -> int:
        """
        解密单个字节

        Args:
            ciphertext_byte: 密文字节

        Returns:
            明文字节
        """
        stream = self._stream_byte()
        plaintext_byte = ciphertext_byte ^ stream
        self._update_keys(plaintext_byte)
        return plaintext_byte

    def decrypt(self, ciphertext: bytes) -> Tuple[bytes, int]:
        """
        解密数据（包含 12 字节加密头）

        Args:
            ciphertext: 密文数据（12 字节加密头 + 加密数据）

        Returns:
            Tuple[明文数据, 加密头中的 CRC 校验字节]
        """
        if len(ciphertext) < 12:
            raise ValueError("Ciphertext too short (missing encryption header)")

        # 解密 12 字节头
        header = bytearray()
        for byte in ciphertext[:12]:
            header.append(self._decrypt_byte(byte))

        # 最后一个字节是 CRC 校验
        crc_check = header[11]

        # 解密数据
        plaintext = bytearray()
        for byte in ciphertext[12:]:
            plaintext.append(self._decrypt_byte(byte))

        return bytes(plaintext), crc_check
