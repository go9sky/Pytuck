"""
Pytuck 加密 ZIP 写入器 - 纯 Python 实现

支持创建带 ZipCrypto 密码保护的 ZIP 文件，兼容所有主流解压工具。
"""

import binascii
import struct
import time
import zlib
from pathlib import Path
from typing import List, Optional, Tuple, Union

from .zipcrypto import ZipCryptoEncryptor


class _ZipEntry:
    """ZIP 文件条目信息"""

    def __init__(
        self,
        filename: str,
        data: bytes,
        compressed_data: bytes,
        crc32: int,
        compress_type: int,
        encrypted: bool,
        local_header_offset: int
    ) -> None:
        self.filename = filename
        self.data = data
        self.compressed_data = compressed_data
        self.crc32 = crc32
        self.compress_type = compress_type
        self.encrypted = encrypted
        self.local_header_offset = local_header_offset


class EncryptedZipFile:
    """
    支持 ZipCrypto 加密的 ZIP 文件写入器

    创建带密码保护的 ZIP 文件，生成的文件可被 WinRAR、7-Zip 等工具解压。

    Example:
        >>> with EncryptedZipFile("data.zip", password="secret") as zf:
        ...     zf.writestr("file.txt", b"hello world")

    Note:
        ZipCrypto 是一种较弱的加密算法，仅适合防止普通用户随意查看。
    """

    # ZIP 文件签名常量
    LOCAL_FILE_HEADER_SIG = 0x04034B50
    CENTRAL_DIR_HEADER_SIG = 0x02014B50
    END_OF_CENTRAL_DIR_SIG = 0x06054B50

    # 压缩方法
    COMPRESS_STORED = 0
    COMPRESS_DEFLATED = 8

    def __init__(
        self,
        path: Union[str, Path],
        password: Optional[str] = None,
        compression: int = 8  # 默认使用 DEFLATE 压缩
    ) -> None:
        """
        初始化加密 ZIP 写入器

        Args:
            path: ZIP 文件路径
            password: 加密密码（可选，为 None 时不加密）
            compression: 压缩方法（0=存储, 8=DEFLATE）
        """
        self.path = Path(path)
        self.password = password.encode('utf-8') if password else None
        self.compression = compression
        self._entries: List[_ZipEntry] = []
        self._file = open(self.path, 'wb')
        self._closed = False

    def __enter__(self) -> 'EncryptedZipFile':
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:  # type: ignore
        self.close()

    @staticmethod
    def _get_dos_datetime() -> Tuple[int, int]:
        """
        获取当前时间的 DOS 格式表示

        Returns:
            Tuple[dos_time, dos_date]
        """
        t = time.localtime()
        dos_time = (t.tm_hour << 11) | (t.tm_min << 5) | (t.tm_sec // 2)
        dos_date = ((t.tm_year - 1980) << 9) | (t.tm_mon << 5) | t.tm_mday
        return dos_time, dos_date

    def _compress_data(self, data: bytes) -> Tuple[bytes, int]:
        """
        压缩数据

        Args:
            data: 原始数据

        Returns:
            Tuple[压缩后的数据, 压缩方法]
        """
        if self.compression == self.COMPRESS_DEFLATED:
            # 使用 DEFLATE 压缩
            compress_obj = zlib.compressobj(
                zlib.Z_DEFAULT_COMPRESSION,
                zlib.DEFLATED,
                -zlib.MAX_WBITS  # 原始 deflate，不带 zlib 头
            )
            compressed = compress_obj.compress(data) + compress_obj.flush()
            # 如果压缩后更大，使用存储方式
            if len(compressed) < len(data):
                return compressed, self.COMPRESS_DEFLATED
        return data, self.COMPRESS_STORED

    def writestr(self, name: str, data: bytes) -> None:
        """
        写入一个文件条目

        Args:
            name: 文件名（在 ZIP 中的路径）
            data: 文件内容
        """
        if self._closed:
            raise ValueError("Cannot write to closed EncryptedZipFile")

        # 计算 CRC32（基于原始未压缩数据）
        crc32 = binascii.crc32(data) & 0xFFFFFFFF

        # 压缩数据
        compressed_data, compress_type = self._compress_data(data)

        # 记录 local header 偏移
        local_header_offset = self._file.tell()

        # 获取 DOS 时间
        dos_time, dos_date = self._get_dos_datetime()

        # 文件名编码
        filename_bytes = name.encode('utf-8')

        # 确定标志位
        flag_bits = 0
        if self.password:
            flag_bits |= 0x0001  # 加密标志

        # 如果加密，对压缩后的数据进行加密
        if self.password:
            encryptor = ZipCryptoEncryptor(self.password)
            encrypted_data = encryptor.encrypt(compressed_data, crc32)
            file_data = encrypted_data
        else:
            file_data = compressed_data

        # 写入 Local File Header
        # 格式: signature(4) + version(2) + flags(2) + compression(2) +
        #       time(2) + date(2) + crc32(4) + compressed_size(4) +
        #       uncompressed_size(4) + filename_len(2) + extra_len(2)
        local_header = struct.pack(
            '<IHHHHHIIIHH',
            self.LOCAL_FILE_HEADER_SIG,
            20,  # version needed to extract (2.0)
            flag_bits,
            compress_type,
            dos_time,
            dos_date,
            crc32,
            len(file_data),  # compressed size (包含加密头)
            len(data),  # uncompressed size
            len(filename_bytes),
            0  # extra field length
        )

        self._file.write(local_header)
        self._file.write(filename_bytes)
        self._file.write(file_data)

        # 记录条目信息
        entry = _ZipEntry(
            filename=name,
            data=data,
            compressed_data=file_data,
            crc32=crc32,
            compress_type=compress_type,
            encrypted=bool(self.password),
            local_header_offset=local_header_offset
        )
        self._entries.append(entry)

    def close(self) -> None:
        """关闭 ZIP 文件，写入 Central Directory 和 End of Central Directory"""
        if self._closed:
            return

        self._closed = True

        # 记录 Central Directory 开始位置
        central_dir_offset = self._file.tell()

        dos_time, dos_date = self._get_dos_datetime()

        # 写入所有 Central Directory Headers
        for entry in self._entries:
            filename_bytes = entry.filename.encode('utf-8')

            flag_bits = 0
            if entry.encrypted:
                flag_bits |= 0x0001

            # Central Directory File Header
            # 格式: signature(4) + version_made_by(2) + version_needed(2) +
            #       flags(2) + compression(2) + time(2) + date(2) + crc32(4) +
            #       compressed_size(4) + uncompressed_size(4) + filename_len(2) +
            #       extra_len(2) + comment_len(2) + disk_start(2) + internal_attr(2) +
            #       external_attr(4) + local_header_offset(4)
            central_header = struct.pack(
                '<IHHHHHHIIIHHHHHII',
                self.CENTRAL_DIR_HEADER_SIG,
                20,  # version made by
                20,  # version needed to extract
                flag_bits,
                entry.compress_type,
                dos_time,
                dos_date,
                entry.crc32,
                len(entry.compressed_data),
                len(entry.data),
                len(filename_bytes),
                0,  # extra field length
                0,  # file comment length
                0,  # disk number start
                0,  # internal file attributes
                0,  # external file attributes
                entry.local_header_offset
            )

            self._file.write(central_header)
            self._file.write(filename_bytes)

        # 计算 Central Directory 大小
        central_dir_size = self._file.tell() - central_dir_offset

        # 写入 End of Central Directory Record
        # 格式: signature(4) + disk_num(2) + disk_with_cd(2) +
        #       num_entries_disk(2) + num_entries_total(2) +
        #       cd_size(4) + cd_offset(4) + comment_len(2)
        eocd = struct.pack(
            '<IHHHHIIH',
            self.END_OF_CENTRAL_DIR_SIG,
            0,  # disk number
            0,  # disk number with central directory
            len(self._entries),  # number of entries on this disk
            len(self._entries),  # total number of entries
            central_dir_size,
            central_dir_offset,
            0  # comment length
        )

        self._file.write(eocd)
        self._file.close()
