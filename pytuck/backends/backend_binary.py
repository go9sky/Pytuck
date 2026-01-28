"""
Pytuck 二进制存储引擎

默认的持久化引擎，使用自定义二进制格式，无外部依赖
"""

import io
import json
import os
import struct
import zlib
from dataclasses import dataclass, field
from enum import IntEnum
from pathlib import Path
from typing import Any, Dict, List, Set, Union, TYPE_CHECKING, BinaryIO, Tuple, Optional, Iterator

if TYPE_CHECKING:
    from ..core.storage import Table

from .base import StorageBackend
from ..common.exceptions import SerializationError, EncryptionError
from ..core.types import TypeRegistry, TypeCode
from ..core.orm import Column
from ..core.index import HashIndex
from .versions import get_format_version

from ..common.options import BinaryBackendOptions
from ..common.crypto import (
    CryptoProvider, get_cipher, get_encryption_level_code, get_encryption_level_name,
    ENCRYPTION_LEVELS, CipherType
)


# ============== v4 数据结构定义 ==============

class WALOpType(IntEnum):
    """WAL 操作类型"""
    INSERT = 1
    UPDATE = 2
    DELETE = 3


@dataclass
class HeaderV4:
    """v4 文件头结构 (128 bytes)"""
    magic: bytes = b'PTK4'
    version: int = 4
    generation: int = 0
    schema_offset: int = 0
    schema_size: int = 0
    data_offset: int = 0
    data_size: int = 0
    index_offset: int = 0
    index_size: int = 0
    wal_offset: int = 0
    wal_size: int = 0
    checkpoint_lsn: int = 0
    flags: int = 0
    crc32: int = 0
    # 加密元数据（存储在 reserved 区域）
    salt: bytes = field(default_factory=lambda: b'\x00' * 16)
    key_check: bytes = field(default_factory=lambda: b'\x00' * 4)

    # Header 布局常量
    HEADER_SIZE = 128
    MAGIC_V4 = b'PTK4'

    # flags 位定义
    FLAG_INDEX_COMPRESSED = 0x01    # bit 0: 索引区已压缩
    FLAG_ENCRYPTION_ENABLED = 0x02  # bit 1: 加密已启用
    FLAG_ENCRYPTION_LEVEL_MASK = 0x0C  # bit 2-3: 加密等级 (00=none, 01=low, 10=medium, 11=high)
    FLAG_ENCRYPTION_LEVEL_SHIFT = 2

    def pack(self) -> bytes:
        """序列化为 128 字节"""
        buf = bytearray(self.HEADER_SIZE)

        # Magic (4B)
        buf[0:4] = self.magic

        # Version (2B)
        struct.pack_into('<H', buf, 4, self.version)

        # Generation (8B)
        struct.pack_into('<Q', buf, 6, self.generation)

        # Schema offset/size (8B + 8B)
        struct.pack_into('<Q', buf, 14, self.schema_offset)
        struct.pack_into('<Q', buf, 22, self.schema_size)

        # Data offset/size (8B + 8B)
        struct.pack_into('<Q', buf, 30, self.data_offset)
        struct.pack_into('<Q', buf, 38, self.data_size)

        # Index offset/size (8B + 8B)
        struct.pack_into('<Q', buf, 46, self.index_offset)
        struct.pack_into('<Q', buf, 54, self.index_size)

        # WAL offset/size (8B + 8B)
        struct.pack_into('<Q', buf, 62, self.wal_offset)
        struct.pack_into('<Q', buf, 70, self.wal_size)

        # Checkpoint LSN (8B)
        struct.pack_into('<Q', buf, 78, self.checkpoint_lsn)

        # Flags (4B)
        struct.pack_into('<I', buf, 86, self.flags)

        # 计算 CRC32（对前 90 字节计算）
        crc = zlib.crc32(buf[:90]) & 0xFFFFFFFF
        struct.pack_into('<I', buf, 90, crc)

        # 加密元数据（reserved 区域 94-127）
        # Salt (16B) at offset 94
        buf[94:110] = self.salt[:16].ljust(16, b'\x00')
        # Key check (4B) at offset 110
        buf[110:114] = self.key_check[:4].ljust(4, b'\x00')
        # Remaining reserved (14B) at offset 114-127 stays zero

        return bytes(buf)

    @classmethod
    def unpack(cls, data: bytes) -> 'HeaderV4':
        """从 128 字节反序列化"""
        if len(data) < cls.HEADER_SIZE:
            raise SerializationError(f"Header too short: {len(data)} bytes")

        header = cls()
        header.magic = data[0:4]
        header.version = struct.unpack('<H', data[4:6])[0]
        header.generation = struct.unpack('<Q', data[6:14])[0]
        header.schema_offset = struct.unpack('<Q', data[14:22])[0]
        header.schema_size = struct.unpack('<Q', data[22:30])[0]
        header.data_offset = struct.unpack('<Q', data[30:38])[0]
        header.data_size = struct.unpack('<Q', data[38:46])[0]
        header.index_offset = struct.unpack('<Q', data[46:54])[0]
        header.index_size = struct.unpack('<Q', data[54:62])[0]
        header.wal_offset = struct.unpack('<Q', data[62:70])[0]
        header.wal_size = struct.unpack('<Q', data[70:78])[0]
        header.checkpoint_lsn = struct.unpack('<Q', data[78:86])[0]
        header.flags = struct.unpack('<I', data[86:90])[0]
        header.crc32 = struct.unpack('<I', data[90:94])[0]

        # 加密元数据
        header.salt = data[94:110]
        header.key_check = data[110:114]

        return header

    def verify_crc(self, data: bytes) -> bool:
        """验证 CRC32"""
        expected = zlib.crc32(data[:90]) & 0xFFFFFFFF
        return self.crc32 == expected

    def is_encrypted(self) -> bool:
        """检查是否启用加密"""
        return (self.flags & self.FLAG_ENCRYPTION_ENABLED) != 0

    def get_encryption_level(self) -> Optional[str]:
        """获取加密等级名称"""
        if not self.is_encrypted():
            return None
        level_code = (self.flags & self.FLAG_ENCRYPTION_LEVEL_MASK) >> self.FLAG_ENCRYPTION_LEVEL_SHIFT
        return get_encryption_level_name(level_code)

    def set_encryption(self, level: str, salt: bytes, key_check: bytes) -> None:
        """设置加密标志和元数据"""
        level_code = get_encryption_level_code(level)
        self.flags |= self.FLAG_ENCRYPTION_ENABLED
        self.flags = (self.flags & ~self.FLAG_ENCRYPTION_LEVEL_MASK) | (level_code << self.FLAG_ENCRYPTION_LEVEL_SHIFT)
        self.salt = salt
        self.key_check = key_check


@dataclass
class WALEntry:
    """WAL 日志条目"""
    lsn: int
    op_type: WALOpType
    table_name: str
    pk_bytes: bytes
    record_bytes: bytes = b''

    def pack(self) -> bytes:
        """序列化 WAL 条目"""
        buf = bytearray()

        # LSN (8B)
        buf += struct.pack('<Q', self.lsn)

        # Op type (1B)
        buf += struct.pack('B', self.op_type)

        # Table name (2B len + data)
        name_bytes = self.table_name.encode('utf-8')
        buf += struct.pack('<H', len(name_bytes))
        buf += name_bytes

        # PK bytes (2B len + data)
        buf += struct.pack('<H', len(self.pk_bytes))
        buf += self.pk_bytes

        # Record bytes (4B len + data)
        buf += struct.pack('<I', len(self.record_bytes))
        buf += self.record_bytes

        # CRC32 (4B)
        crc = zlib.crc32(buf) & 0xFFFFFFFF
        buf += struct.pack('<I', crc)

        # Entry length at beginning (4B)
        entry_data = struct.pack('<I', len(buf)) + buf

        return bytes(entry_data)

    @classmethod
    def unpack(cls, data: bytes) -> Tuple['WALEntry', int]:
        """
        从字节反序列化

        Returns:
            Tuple[WALEntry, bytes_consumed]
        """
        if len(data) < 4:
            raise SerializationError("WAL entry too short")

        entry_len = struct.unpack('<I', data[0:4])[0]
        if len(data) < 4 + entry_len:
            raise SerializationError("Incomplete WAL entry")

        entry_data = data[4:4 + entry_len]

        # 验证 CRC
        crc_stored = struct.unpack('<I', entry_data[-4:])[0]
        crc_calc = zlib.crc32(entry_data[:-4]) & 0xFFFFFFFF
        if crc_stored != crc_calc:
            raise SerializationError("WAL entry CRC mismatch")

        offset = 0

        # LSN
        lsn = struct.unpack('<Q', entry_data[offset:offset + 8])[0]
        offset += 8

        # Op type
        op_type = WALOpType(entry_data[offset])
        offset += 1

        # Table name
        name_len = struct.unpack('<H', entry_data[offset:offset + 2])[0]
        offset += 2
        table_name = entry_data[offset:offset + name_len].decode('utf-8')
        offset += name_len

        # PK bytes
        pk_len = struct.unpack('<H', entry_data[offset:offset + 2])[0]
        offset += 2
        pk_bytes = entry_data[offset:offset + pk_len]
        offset += pk_len

        # Record bytes
        rec_len = struct.unpack('<I', entry_data[offset:offset + 4])[0]
        offset += 4
        record_bytes = entry_data[offset:offset + rec_len]

        entry = cls(
            lsn=lsn,
            op_type=op_type,
            table_name=table_name,
            pk_bytes=pk_bytes,
            record_bytes=record_bytes
        )

        return entry, 4 + entry_len


class BinaryBackend(StorageBackend):
    """Binary format storage engine (default, no dependencies)"""

    ENGINE_NAME = 'binary'
    REQUIRED_DEPENDENCIES = []

    # 文件格式常量
    MAGIC_NUMBER = b'PYTK'
    FORMAT_VERSION = get_format_version('binary')
    FILE_HEADER_SIZE = 64

    # v4 格式常量
    MAGIC_V4 = b'PTK4'
    HEADER_SIZE_V4 = 128  # 双 header，每个 128 字节
    DUAL_HEADER_SIZE = 256  # 两个 header 的总大小

    def __init__(self, file_path: Union[str, Path], options: BinaryBackendOptions):
        """
        初始化 Binary 后端

        Args:
            file_path: 二进制文件路径
            options: Binary 后端配置选项
        """
        assert isinstance(options, BinaryBackendOptions), "options must be an instance of BinaryBackendOptions"
        super().__init__(file_path, options)
        # 类型安全：将 options 转为具体的 BinaryBackendOptions 类型
        self.options: BinaryBackendOptions = options

        # v4 运行时状态
        self._active_header: Optional[HeaderV4] = None
        self._active_slot: int = 0  # 0 = Header A, 1 = Header B
        self._current_lsn: int = 0
        self._file_handle: Optional[BinaryIO] = None

        # WAL 缓冲（减少 I/O 次数）
        self._wal_buffer: List[WALEntry] = []
        self._wal_buffer_size: int = 0  # 缓冲区字节大小
        self._wal_flush_threshold: int = 32 * 1024  # 32KB 阈值

    def save(self, tables: Dict[str, 'Table']) -> None:
        """保存所有表数据到二进制文件（v4 格式：双Header + 增量写入支持）"""
        # 清空 WAL 缓冲区（checkpoint 会包含所有数据）
        self._wal_buffer.clear()
        self._wal_buffer_size = 0

        # 对于新文件或全量保存，使用 checkpoint
        self._checkpoint_v4(tables)

    def _checkpoint_v4(self, tables: Dict[str, 'Table']) -> None:
        """
        执行 v4 checkpoint（全量写入）

        v4 文件布局:
        - Header A (128B)
        - Header B (128B)
        - Schema Region（不加密）
        - Data Region（可加密）
        - Index Region（可加密）
        """
        temp_path = self.file_path.parent / (self.file_path.name + '.tmp')

        # 收集所有表的 pk_offsets 和索引数据
        all_table_index_data: Dict[str, Dict[str, Any]] = {}

        # 加密设置
        encryption_level = self.options.encryption
        cipher: Optional[CipherType] = None
        salt = b'\x00' * 16
        key_check = b'\x00' * 4

        if encryption_level:
            if not self.options.password:
                raise EncryptionError("加密需要提供密码")
            if encryption_level not in ENCRYPTION_LEVELS:
                raise EncryptionError(f"无效的加密等级: {encryption_level}，必须是 {ENCRYPTION_LEVELS} 之一")

            # 生成随机盐并派生密钥
            salt = os.urandom(16)
            key = CryptoProvider.derive_key(self.options.password, salt, encryption_level)
            key_check = CryptoProvider.compute_key_check(key)
            cipher = get_cipher(encryption_level, key)

        try:
            with open(temp_path, 'wb') as f:
                # 1. 预留双 Header 空间（256 字节）
                f.write(b'\x00' * self.DUAL_HEADER_SIZE)

                # 2. 写入 Schema 区（不加密，保持可探测性）
                schema_offset = f.tell()
                for table_name, table in tables.items():
                    self._write_table_schema(f, table)
                schema_size = f.tell() - schema_offset

                # 3. 写入数据区（记录每条记录的偏移）
                data_offset = f.tell()
                # 先写入到内存缓冲区
                import io
                data_buffer = io.BytesIO()
                for table_name, table in tables.items():
                    pk_offsets = self._write_table_data(data_buffer, table)
                    all_table_index_data[table_name] = {
                        'pk_offsets': pk_offsets,
                        'indexes': table.indexes
                    }
                data_bytes = data_buffer.getvalue()

                # 如果启用加密，加密数据区
                if cipher:
                    data_bytes = cipher.encrypt(data_bytes)

                f.write(data_bytes)
                data_size = len(data_bytes)

                # 4. 写入索引区（使用压缩，可加密）
                index_offset = f.tell()
                compressed_index = self._write_index_region_compressed(all_table_index_data)

                # 如果启用加密，加密索引区
                if cipher:
                    compressed_index = cipher.encrypt(compressed_index)

                f.write(compressed_index)
                index_size = len(compressed_index)

                # 5. 创建并写入 v4 Header
                new_generation = 1
                if self._active_header:
                    new_generation = self._active_header.generation + 1

                # flags: bit 0 = 索引区已压缩
                flags = HeaderV4.FLAG_INDEX_COMPRESSED

                header = HeaderV4(
                    magic=self.MAGIC_V4,
                    version=4,
                    generation=new_generation,
                    schema_offset=schema_offset,
                    schema_size=schema_size,
                    data_offset=data_offset,
                    data_size=data_size,
                    index_offset=index_offset,
                    index_size=index_size,
                    wal_offset=0,
                    wal_size=0,
                    checkpoint_lsn=self._current_lsn,
                    flags=flags
                )

                # 如果启用加密，设置加密标志和元数据
                if encryption_level:
                    header.set_encryption(encryption_level, salt, key_check)

                # 写入 Header A（slot 0）
                f.seek(0)
                f.write(header.pack())

                # 写入 Header B（slot 1）作为备份
                f.seek(self.HEADER_SIZE_V4)
                f.write(header.pack())

            # 原子性重命名
            temp_path.replace(self.file_path)

            # 更新运行时状态
            self._active_header = header
            self._active_slot = 0

        except Exception as e:
            # 清理临时文件
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except FileNotFoundError:
                    pass
            raise SerializationError(f"Failed to save binary file: {e}")

    def load(self) -> Dict[str, 'Table']:
        """从二进制文件加载所有表数据（v4 格式，支持懒加载）"""
        if not self.exists():
            raise FileNotFoundError(f"Binary file not found: {self.file_path}")

        try:
            with open(self.file_path, 'rb') as f:
                # 检测文件格式版本
                magic = f.read(4)
                f.seek(0)

                if magic == self.MAGIC_V4:
                    return self._load_v4(f)
                else:
                    raise SerializationError(
                        f"不支持的文件格式: {magic!r}，请使用 v4 格式（PTK4）"
                    )

        except EncryptionError:
            # 加密异常直接抛出，不包装
            raise
        except Exception as e:
            raise SerializationError(f"Failed to load binary file: {e}")

    def _load_v4(self, f: BinaryIO) -> Dict[str, 'Table']:
        """加载 v4 格式文件"""
        # 读取双 Header
        header_a = HeaderV4.unpack(f.read(self.HEADER_SIZE_V4))
        header_b = HeaderV4.unpack(f.read(self.HEADER_SIZE_V4))

        # 选择有效的 Header（generation 更大且 CRC 正确的）
        f.seek(0)
        header_a_data = f.read(self.HEADER_SIZE_V4)
        f.seek(self.HEADER_SIZE_V4)
        header_b_data = f.read(self.HEADER_SIZE_V4)

        header_a_valid = header_a.magic == self.MAGIC_V4 and header_a.verify_crc(header_a_data)
        header_b_valid = header_b.magic == self.MAGIC_V4 and header_b.verify_crc(header_b_data)

        if header_a_valid and header_b_valid:
            # 选择 generation 更大的
            if header_a.generation >= header_b.generation:
                header = header_a
                self._active_slot = 0
            else:
                header = header_b
                self._active_slot = 1
        elif header_a_valid:
            header = header_a
            self._active_slot = 0
        elif header_b_valid:
            header = header_b
            self._active_slot = 1
        else:
            raise SerializationError("Both headers are corrupted")

        self._active_header = header
        self._current_lsn = header.checkpoint_lsn

        # 检查加密状态
        cipher: Optional[CipherType] = None
        if header.is_encrypted():
            # 文件已加密，需要密码
            if not self.options.password:
                raise EncryptionError("文件已加密，需要提供密码")

            encryption_level = header.get_encryption_level()
            if not encryption_level:
                raise EncryptionError("无法识别加密等级")

            # 派生密钥
            key = CryptoProvider.derive_key(
                self.options.password, header.salt, encryption_level
            )

            # 验证密钥
            if not CryptoProvider.verify_key(key, header.key_check):
                raise EncryptionError("密码错误")

            # 创建解密器
            cipher = get_cipher(encryption_level, key)

        # 读取 Schema 区（不加密）
        f.seek(header.schema_offset)
        tables_schema = []
        # 需要知道表数量，从 schema 区逐个读取直到到达 data_offset
        while f.tell() < header.data_offset:
            schema = self._read_table_schema(f)
            tables_schema.append(schema)

        # 读取索引区
        index_data: Dict[str, Dict[str, Any]] = {}
        if header.index_offset > 0 and header.index_size > 0:
            f.seek(header.index_offset)
            # 检查 flags 判断索引区是否压缩
            is_compressed = (header.flags & HeaderV4.FLAG_INDEX_COMPRESSED) != 0

            if cipher:
                # 读取加密的索引区数据并解密
                encrypted_index = f.read(header.index_size)
                decrypted_index = cipher.decrypt(encrypted_index)
                index_data = self._parse_index_region(decrypted_index, compressed=is_compressed)
            else:
                index_data = self._read_index_region(f, compressed=is_compressed)

        tables = {}

        # 懒加载模式（加密时不支持懒加载，因为需要完整解密数据区）
        if self.options.lazy_load and index_data and not cipher:
            for schema in tables_schema:
                table = self._create_lazy_table(schema, index_data, header.data_offset)
                tables[table.name] = table
        else:
            if cipher:
                # 加密模式：读取并解密整个数据区
                f.seek(header.data_offset)
                encrypted_data = f.read(header.data_size)
                decrypted_data = cipher.decrypt(encrypted_data)
                data_stream = io.BytesIO(decrypted_data)

                for schema in tables_schema:
                    table = self._read_table_data(data_stream, schema, index_data)
                    tables[table.name] = table
            else:
                # 完整加载模式
                f.seek(header.data_offset)
                for schema in tables_schema:
                    table = self._read_table_data(f, schema, index_data)
                    tables[table.name] = table

        return tables

    def _create_lazy_table(
        self,
        schema: Dict[str, Any],
        index_data: Dict[str, Dict[str, Any]],
        data_offset: int
    ) -> 'Table':
        """
        创建懒加载表（只加载 schema 和索引，不加载数据）

        Args:
            schema: 表结构信息
            index_data: 从索引区读取的索引数据
            data_offset: 数据区在文件中的起始偏移量

        Returns:
            懒加载的 Table 对象
        """
        from ..core.storage import Table

        table_name = schema['table_name']

        # 创建 Table 对象（不加载数据）
        table = Table(
            table_name,
            schema['columns'],
            schema['primary_key'],
            comment=schema.get('table_comment')
        )
        table.next_id = schema['next_id']

        # 设置懒加载属性
        table._lazy_loaded = True
        table._data_file = self.file_path
        table._backend = self

        # 从索引区获取数据，并修正偏移量为绝对偏移
        table_idx_data = index_data.get(table_name, {})
        relative_pk_offsets = table_idx_data.get('pk_offsets', {})
        # 将相对偏移量转换为绝对偏移量
        table._pk_offsets = {
            pk: relative_offset + data_offset
            for pk, relative_offset in relative_pk_offsets.items()
        }

        # 恢复索引
        idx_maps = table_idx_data.get('indexes', {})
        for col_name, idx_map in idx_maps.items():
            if col_name in table.indexes:
                del table.indexes[col_name]
            index = HashIndex(col_name)
            index.map = idx_map
            table.indexes[col_name] = index

        return table

    def exists(self) -> bool:
        """检查文件是否存在"""
        return self.file_path.exists()

    def delete(self) -> None:
        """删除文件"""
        if self.file_path.exists():
            self.file_path.unlink()

    def supports_lazy_loading(self) -> bool:
        """
        检查是否启用了懒加载模式

        Returns:
            True 如果 options.lazy_load=True
        """
        return self.options.lazy_load

    def populate_tables_with_data(self, tables: Dict[str, 'Table']) -> None:
        """
        填充懒加载表的数据（用于迁移场景）

        在懒加载模式下，load() 只加载 schema 和索引，此方法用于
        在需要时（如迁移）填充实际数据。

        Args:
            tables: 需要填充数据的表字典
        """
        if not self.options.lazy_load:
            return  # 非懒加载模式，数据已在 load() 时加载

        for table in tables.values():
            if table.data:  # 已有数据，跳过
                continue

            if not getattr(table, '_lazy_loaded', False):
                continue

            pk_offsets = getattr(table, '_pk_offsets', None)
            if pk_offsets is None:
                continue

            # 通过 get() 逐条加载数据
            for pk in pk_offsets:
                record = table.get(pk)
                table.data[pk] = record

    # ============== WAL 操作方法 ==============

    def append_wal_entry(
        self,
        op_type: WALOpType,
        table_name: str,
        pk: Any,
        record: Optional[Dict[str, Any]] = None,
        columns: Optional[Dict[str, 'Column']] = None
    ) -> int:
        """
        追加 WAL 条目到缓冲区

        Args:
            op_type: 操作类型 (INSERT/UPDATE/DELETE)
            table_name: 表名
            pk: 主键值
            record: 记录数据（INSERT/UPDATE 时需要）
            columns: 列定义（用于序列化）

        Returns:
            新的 LSN
        """
        # 序列化 PK
        pk_bytes = self._serialize_index_value(pk)

        # 序列化记录（如果有）
        record_bytes = b''
        if record is not None and columns is not None:
            record_bytes = self._serialize_record_bytes(pk, record, columns)

        # 创建 WAL 条目
        self._current_lsn += 1
        entry = WALEntry(
            lsn=self._current_lsn,
            op_type=op_type,
            table_name=table_name,
            pk_bytes=pk_bytes,
            record_bytes=record_bytes
        )

        # 添加到缓冲区
        entry_bytes = entry.pack()
        self._wal_buffer.append(entry)
        self._wal_buffer_size += len(entry_bytes)

        # 如果缓冲区达到阈值，刷新到磁盘
        if self._wal_buffer_size >= self._wal_flush_threshold:
            self.flush_wal_buffer()

        return self._current_lsn

    def flush_wal_buffer(self) -> None:
        """将 WAL 缓冲区刷新到磁盘"""
        if not self._wal_buffer:
            return

        # 序列化所有条目
        all_bytes = bytearray()
        for entry in self._wal_buffer:
            all_bytes.extend(entry.pack())

        with open(self.file_path, 'r+b') as f:
            # 读取当前 header
            if self._active_header is None:
                f.seek(0)
                header_data = f.read(self.HEADER_SIZE_V4)
                self._active_header = HeaderV4.unpack(header_data)

            # 计算 WAL 写入位置
            if self._active_header.wal_offset == 0:
                # 首次写 WAL，在文件末尾
                f.seek(0, 2)  # 移到文件末尾
                wal_offset = f.tell()
            else:
                # 追加到现有 WAL
                wal_offset = self._active_header.wal_offset
                f.seek(wal_offset + self._active_header.wal_size)

            # 写入所有 WAL 条目
            f.write(all_bytes)
            f.flush()

            # 更新 header 中的 WAL 信息
            new_wal_size = self._active_header.wal_size + len(all_bytes)
            if self._active_header.wal_offset == 0:
                self._active_header.wal_offset = wal_offset

            self._active_header.wal_size = new_wal_size
            self._active_header.checkpoint_lsn = self._current_lsn

            # 更新 header（写入当前活跃槽）
            header_bytes = self._active_header.pack()
            f.seek(self._active_slot * self.HEADER_SIZE_V4)
            f.write(header_bytes)
            f.flush()

        # 清空缓冲区
        self._wal_buffer.clear()
        self._wal_buffer_size = 0

    def _serialize_record_bytes(
        self,
        pk: Any,
        record: Dict[str, Any],
        columns: Dict[str, 'Column']
    ) -> bytes:
        """
        序列化记录为字节

        Args:
            pk: 主键值
            record: 记录数据
            columns: 列定义

        Returns:
            序列化后的字节
        """
        buf = bytearray()

        # 预构建列索引映射
        col_idx_map = {col.name: idx for idx, col in enumerate(columns.values())}

        # Primary Key
        pk_col = None
        for col in columns.values():
            if col.primary_key:
                pk_col = col
                break

        if pk_col:
            type_code, codec = TypeRegistry.get_codec(pk_col.col_type)
            pk_bytes = codec.encode(pk)
            buf += struct.pack('<H', len(pk_bytes))
            buf += pk_bytes

        # Field Count
        field_count = len(record)
        buf += struct.pack('<H', field_count)

        # Fields
        for col_name, value in record.items():
            if col_name not in columns:
                continue
            column = columns[col_name]

            # Column Index
            col_idx = col_idx_map.get(col_name, 0)
            buf += struct.pack('<H', col_idx)

            # Type Code
            type_code, codec = TypeRegistry.get_codec(column.col_type)
            buf += struct.pack('B', type_code)

            # Value
            if value is None:
                buf += struct.pack('<I', 0)
            else:
                value_bytes = codec.encode(value)
                buf += struct.pack('<I', len(value_bytes))
                buf += value_bytes

        return bytes(buf)

    def read_wal_entries(self) -> Iterator[WALEntry]:
        """
        读取所有 WAL 条目（包括磁盘和缓冲区）

        Yields:
            WALEntry 对象
        """
        # 首先读取磁盘上的 WAL
        if self.exists():
            with open(self.file_path, 'rb') as f:
                # 读取 header
                header_data = f.read(self.HEADER_SIZE_V4)
                if len(header_data) >= self.HEADER_SIZE_V4:
                    header = HeaderV4.unpack(header_data)

                    if header.wal_offset > 0 and header.wal_size > 0:
                        # 读取 WAL 区域
                        f.seek(header.wal_offset)
                        wal_data = f.read(header.wal_size)

                        # 解析 WAL 条目
                        offset = 0
                        while offset < len(wal_data):
                            try:
                                entry, consumed = WALEntry.unpack(wal_data[offset:])
                                yield entry
                                offset += consumed
                            except SerializationError:
                                # CRC 错误或数据损坏，停止读取
                                break

        # 然后返回缓冲区中的条目
        for entry in self._wal_buffer:
            yield entry

    def replay_wal(self, tables: Dict[str, 'Table']) -> int:
        """
        回放 WAL 到内存中的表

        Args:
            tables: 表字典

        Returns:
            回放的条目数量
        """
        count = 0

        for entry in self.read_wal_entries():
            table = tables.get(entry.table_name)
            if table is None:
                continue

            # 反序列化 PK
            pk = self._deserialize_index_value(entry.pk_bytes)

            if entry.op_type == WALOpType.DELETE:
                # 删除操作
                if pk in table.data:
                    old_record = table.data[pk]
                    del table.data[pk]
                    # 更新索引
                    for col_name, idx in table.indexes.items():
                        if col_name in old_record:
                            idx.remove(old_record[col_name], pk)

            elif entry.op_type in (WALOpType.INSERT, WALOpType.UPDATE):
                # 插入或更新操作
                if entry.record_bytes:
                    record = self._deserialize_record_bytes(
                        entry.record_bytes,
                        table.columns
                    )
                    table.data[pk] = record

                    # 更新索引
                    for col_name, idx in table.indexes.items():
                        if col_name in record:
                            idx.insert(record[col_name], pk)

            count += 1
            self._current_lsn = max(self._current_lsn, entry.lsn)

        return count

    def _deserialize_record_bytes(
        self,
        data: bytes,
        columns: Dict[str, 'Column']
    ) -> Dict[str, Any]:
        """
        反序列化记录字节

        Args:
            data: 序列化的字节
            columns: 列定义

        Returns:
            记录字典
        """
        record = {}
        offset = 0

        # 列列表（按顺序）
        col_list = list(columns.values())

        # Primary Key Length + Data
        pk_len = struct.unpack('<H', data[offset:offset + 2])[0]
        offset += 2
        # pk_bytes = data[offset:offset + pk_len]  # PK 在记录中不存储
        offset += pk_len

        # Field Count
        field_count = struct.unpack('<H', data[offset:offset + 2])[0]
        offset += 2

        # Fields
        for _ in range(field_count):
            # Column Index
            col_idx = struct.unpack('<H', data[offset:offset + 2])[0]
            offset += 2

            # Type Code
            type_code = TypeCode(data[offset])
            offset += 1

            # Value Length
            value_len = struct.unpack('<I', data[offset:offset + 4])[0]
            offset += 4

            if value_len == 0:
                value = None
            else:
                value_bytes = data[offset:offset + value_len]
                offset += value_len
                _, codec = TypeRegistry.get_codec_by_code(type_code)
                value, _ = codec.decode(value_bytes)

            # 获取列名
            if col_idx < len(col_list):
                col_name = col_list[col_idx].name
                record[col_name] = value

        return record

    def has_pending_wal(self) -> bool:
        """检查是否有未 checkpoint 的 WAL（包括缓冲区）"""
        # 先检查内存缓冲区
        if self._wal_buffer:
            return True

        if not self.exists():
            return False

        with open(self.file_path, 'rb') as f:
            header_data = f.read(self.HEADER_SIZE_V4)
            if len(header_data) < self.HEADER_SIZE_V4:
                return False

            header = HeaderV4.unpack(header_data)
            return header.wal_size > 0

    def _write_table_schema(self, f: BinaryIO, table: 'Table') -> None:
        """
        写入单个表的 Schema（元数据）

        格式：
        - Table Name Length (2 bytes)
        - Table Name (UTF-8)
        - Primary Key Length (2 bytes)
        - Primary Key (UTF-8) - 空字符串表示无主键
        - Table Comment Length (2 bytes)
        - Table Comment (UTF-8)
        - Column Count (2 bytes)
        - Next ID (8 bytes)
        - Columns Data
        """
        # Table Name
        table_name_bytes = table.name.encode('utf-8')
        f.write(struct.pack('<H', len(table_name_bytes)))
        f.write(table_name_bytes)

        # Primary Key（None 用空字符串表示）
        pk_str = table.primary_key if table.primary_key else ''
        pk_bytes = pk_str.encode('utf-8')
        f.write(struct.pack('<H', len(pk_bytes)))
        if pk_bytes:
            f.write(pk_bytes)

        # Table Comment
        comment_bytes = (table.comment or '').encode('utf-8')
        f.write(struct.pack('<H', len(comment_bytes)))
        if comment_bytes:
            f.write(comment_bytes)

        # Column Count
        f.write(struct.pack('<H', len(table.columns)))

        # Next ID
        f.write(struct.pack('<Q', table.next_id))

        # Columns
        for col_name, column in table.columns.items():
            self._write_column(f, column)

    def _read_table_schema(self, f: BinaryIO) -> Dict[str, Any]:
        """读取单个表的 Schema，返回 schema 字典"""
        # Table Name
        name_len = struct.unpack('<H', f.read(2))[0]
        table_name = f.read(name_len).decode('utf-8')

        # Primary Key（空字符串表示无主键）
        pk_len = struct.unpack('<H', f.read(2))[0]
        primary_key: Optional[str] = f.read(pk_len).decode('utf-8') if pk_len > 0 else None
        if primary_key == '':
            primary_key = None

        # Table Comment
        comment_len = struct.unpack('<H', f.read(2))[0]
        table_comment = f.read(comment_len).decode('utf-8') if comment_len > 0 else None

        # Column Count
        col_count = struct.unpack('<H', f.read(2))[0]

        # Next ID
        next_id = struct.unpack('<Q', f.read(8))[0]

        # Columns
        columns = []
        for _ in range(col_count):
            column = self._read_column(f)
            columns.append(column)

        return {
            'table_name': table_name,
            'primary_key': primary_key,
            'table_comment': table_comment,
            'next_id': next_id,
            'columns': columns
        }

    def _write_table_data(self, f: BinaryIO, table: 'Table') -> Dict[Any, int]:
        """
        写入单个表的数据（记录 pk_offsets）

        格式：
        - Record Count (4 bytes)
        - Records Data

        Returns:
            pk_offsets: 主键到文件偏移的映射
        """
        pk_offsets: Dict[Any, int] = {}

        # Record Count
        f.write(struct.pack('<I', len(table.data)))

        # 预先构建列名到索引的映射和编解码器缓存
        col_idx_map = {name: idx for idx, name in enumerate(table.columns.keys())}

        # 缓存编解码器（避免重复查找）
        codec_cache: Dict[str, tuple] = {}
        pk_col = None
        pk_codec = None
        for col in table.columns.values():
            assert col.name is not None, "Column name must be set"
            type_code, codec = TypeRegistry.get_codec(col.col_type)
            codec_cache[col.name] = (type_code, codec)
            if col.primary_key:
                pk_col = col
                pk_codec = codec

        # 批量写入缓冲区
        buf = bytearray()
        base_offset = f.tell()
        buf_offset = 0

        # Records（使用批量缓冲）
        for pk, record in table.data.items():
            pk_offsets[pk] = base_offset + buf_offset

            # 构建单条记录
            record_data = bytearray()

            # Primary Key
            if pk_codec:
                pk_bytes = pk_codec.encode(pk)
                record_data.extend(pk_bytes)

            # Field Count
            record_data.extend(struct.pack('<H', len(record)))

            # Fields
            for col_name, value in record.items():
                col_idx = col_idx_map[col_name]
                record_data.extend(struct.pack('<H', col_idx))

                if value is None:
                    record_data.extend(b'\xff\x00')  # NULL: type=0xFF, len=0
                else:
                    type_code, codec = codec_cache[col_name]
                    value_bytes = codec.encode(value)
                    record_data.extend(struct.pack('<BI', type_code, len(value_bytes)))
                    record_data.extend(value_bytes)

            # 添加到缓冲区
            record_len = len(record_data)
            buf.extend(struct.pack('<I', record_len))
            buf.extend(record_data)
            buf_offset += 4 + record_len

            # 缓冲区超过 1MB 时刷新
            if len(buf) > 1024 * 1024:
                f.write(buf)
                base_offset = f.tell()
                buf_offset = 0
                buf.clear()

        # 写入剩余数据
        if buf:
            f.write(buf)

        return pk_offsets

    def _read_table_data(
        self,
        f: BinaryIO,
        schema: Dict[str, Any],
        index_data: Dict[str, Dict[str, Any]]
    ) -> 'Table':
        """
        根据 schema 读取表数据（从索引区恢复索引）

        Args:
            f: 文件句柄
            schema: 表结构信息
            index_data: 从索引区读取的索引数据

        Returns:
            Table 对象
        """
        from ..core.storage import Table

        table_name = schema['table_name']

        # 创建 Table 对象
        table = Table(
            table_name,
            schema['columns'],
            schema['primary_key'],
            comment=schema.get('table_comment')
        )
        table.next_id = schema['next_id']

        # 构建 columns 字典用于记录读取
        columns_dict = {col.name: col for col in schema['columns']}
        col_list = list(columns_dict.values())

        # 缓存编解码器
        codec_cache: Dict[int, tuple] = {}
        pk_col = None
        pk_codec = None
        for col in col_list:
            type_code, codec = TypeRegistry.get_codec(col.col_type)
            codec_cache[type_code] = (col.col_type, codec)
            if col.primary_key:
                pk_col = col
                pk_codec = codec

        # Record Count
        record_count_bytes = f.read(4)
        if len(record_count_bytes) < 4:
            raise SerializationError(f"读取表 {table_name} 的记录数失败：文件意外结束")
        record_count = struct.unpack('<I', record_count_bytes)[0]

        for _ in range(record_count):
            # Record Length
            rec_len_bytes = f.read(4)
            if len(rec_len_bytes) < 4:
                raise SerializationError(f"读取表 {table_name} 的记录长度失败：文件意外结束")
            record_len = struct.unpack('<I', rec_len_bytes)[0]

            # Record Data
            record_data = f.read(record_len)
            if len(record_data) < record_len:
                raise SerializationError(f"读取表 {table_name} 的记录数据失败：文件意外结束")

            # 解析记录
            pos = 0

            # Primary Key
            if pk_codec:
                pk, consumed = pk_codec.decode(record_data[pos:])
                pos += consumed

            # Field Count
            field_count = struct.unpack('<H', record_data[pos:pos+2])[0]
            pos += 2

            # Fields
            record: Dict[str, Any] = {}
            for _ in range(field_count):
                # Column Index
                col_idx = struct.unpack('<H', record_data[pos:pos+2])[0]
                pos += 2

                # Type Code
                raw_type_code: int = record_data[pos]
                pos += 1

                if raw_type_code == 0xFF:
                    # NULL value
                    pos += 1  # 跳过长度字节（值为 0）
                    value = None
                else:
                    # Value Length
                    value_len = struct.unpack('<I', record_data[pos:pos+4])[0]
                    pos += 4
                    value_bytes = record_data[pos:pos+value_len]
                    pos += value_len

                    # 解码值
                    if raw_type_code in codec_cache:
                        _, codec = codec_cache[raw_type_code]
                        value, _ = codec.decode(value_bytes)
                    else:
                        _, codec = TypeRegistry.get_codec_by_code(TypeCode(raw_type_code))
                        value, _ = codec.decode(value_bytes)

                # 获取列名
                if col_idx < len(col_list):
                    col_name = col_list[col_idx].name
                    record[col_name] = value

            table.data[pk] = record

        # 从索引区恢复索引（如果有）
        table_idx_data = index_data.get(table_name, {})
        idx_maps = table_idx_data.get('indexes', {})

        if idx_maps:
            # 从持久化数据恢复索引
            for col_name, idx_map in idx_maps.items():
                if col_name in table.indexes:
                    del table.indexes[col_name]
                index = HashIndex(col_name)
                index.map = idx_map
                table.indexes[col_name] = index
        else:
            # 没有索引区数据，重建索引
            for col_name, column in table.columns.items():
                if column.index:
                    if col_name in table.indexes:
                        del table.indexes[col_name]
                    table.build_index(col_name)

        return table

    def _write_column(self, f: BinaryIO, column: 'Column') -> None:
        """
        写入列定义

        格式：
        - Column Name Length (2 bytes)
        - Column Name (UTF-8)
        - Type Code (1 byte)
        - Flags (1 byte): nullable, primary_key, index
        - Column Comment Length (2 bytes)
        - Column Comment (UTF-8)
        """
        # Column Name
        assert column.name is not None, "Column name must be set"
        col_name_bytes = column.name.encode('utf-8')
        f.write(struct.pack('<H', len(col_name_bytes)))
        f.write(col_name_bytes)

        # Type Code
        type_code, _ = TypeRegistry.get_codec(column.col_type)
        f.write(struct.pack('B', type_code))

        # Flags (bit field)
        flags = 0
        if column.nullable:
            flags |= 0x01
        if column.primary_key:
            flags |= 0x02
        if column.index:
            flags |= 0x04
        f.write(struct.pack('B', flags))

        # Column Comment
        comment_bytes = (column.comment or '').encode('utf-8')
        f.write(struct.pack('<H', len(comment_bytes)))
        if comment_bytes:
            f.write(comment_bytes)

    def _read_column(self, f: BinaryIO) -> Column:
        """读取列定义"""
        from ..core.orm import Column

        # Column Name
        name_len = struct.unpack('<H', f.read(2))[0]
        col_name = f.read(name_len).decode('utf-8')

        # Type Code
        type_code = TypeCode(struct.unpack('B', f.read(1))[0])
        col_type = TypeRegistry.get_type_from_code(type_code)

        # Flags
        flags = struct.unpack('B', f.read(1))[0]
        nullable = bool(flags & 0x01)
        primary_key = bool(flags & 0x02)
        index = bool(flags & 0x04)

        # Column Comment
        comment_len = struct.unpack('<H', f.read(2))[0]
        comment = f.read(comment_len).decode('utf-8') if comment_len > 0 else None

        return Column(
            col_type,
            name=col_name,
            nullable=nullable,
            primary_key=primary_key,
            index=index,
            comment=comment
        )

    def _write_record(
        self,
        f: BinaryIO,
        pk: Any,
        record: Dict[str, Any],
        columns: Dict[str, Column],
        col_idx_map: Dict[str, int]
    ) -> None:
        """
        写入单条记录

        格式：
            - Record Length (4 bytes) - 整条记录的字节数（不含此字段）
            - Primary Key (variable)
            - Field Count (2 bytes)
            - Fields (variable)

        Args:
            f: 文件句柄
            pk: 主键值
            record: 记录字典
            columns: 列定义字典
            col_idx_map: 预构建的列名到索引的映射
        """
        # 先在内存中构建记录数据
        record_data = bytearray()

        # Primary Key
        pk_col = None
        for col in columns.values():
            if col.primary_key:
                pk_col = col
                break

        if pk_col:
            _, codec = TypeRegistry.get_codec(pk_col.col_type)
            pk_bytes = codec.encode(pk)
            record_data.extend(pk_bytes)

        # Field Count
        record_data.extend(struct.pack('<H', len(record)))

        # Fields
        for col_name, value in record.items():
            # Column Index（使用预构建的映射，O(1) 查找）
            col_idx = col_idx_map[col_name]
            record_data.extend(struct.pack('<H', col_idx))

            # Value
            column = columns[col_name]
            if value is None:
                # NULL value: 类型码 0xFF，长度 0
                record_data.extend(struct.pack('BB', 0xFF, 0))
            else:
                type_code, codec = TypeRegistry.get_codec(column.col_type)
                value_bytes = codec.encode(value)
                # 类型码 + 长度 + 数据
                record_data.extend(struct.pack('<BI', type_code, len(value_bytes)))
                record_data.extend(value_bytes)

        # 写入记录长度和数据
        f.write(struct.pack('<I', len(record_data)))
        f.write(record_data)

    def _read_record(self, f: BinaryIO, columns: Dict[str, Column]) -> tuple:
        """读取单条记录，返回 (pk, record_dict)"""
        # Record Length
        record_len = struct.unpack('<I', f.read(4))[0]
        record_data = f.read(record_len)

        offset = 0

        # Primary Key
        pk_col = None
        for col in columns.values():
            if col.primary_key:
                pk_col = col
                break

        if pk_col:
            _, codec = TypeRegistry.get_codec(pk_col.col_type)
            pk, consumed = codec.decode(record_data[offset:])
            offset += consumed
        else:
            pk = None

        # Field Count
        field_count = struct.unpack('<H', record_data[offset:offset+2])[0]
        offset += 2

        # Fields
        record: Dict[str, Any] = {}
        col_names = list(columns.keys())

        for _ in range(field_count):
            # Column Index
            col_idx = struct.unpack('<H', record_data[offset:offset+2])[0]
            offset += 2

            col_name = col_names[col_idx]
            column = columns[col_name]

            # Type Code
            type_code = struct.unpack('B', record_data[offset:offset+1])[0]
            offset += 1

            if type_code == 0xFF:
                # NULL value
                record[col_name] = None
                offset += 1  # Skip length byte
            else:
                # Value Length
                value_len = struct.unpack('<I', record_data[offset:offset+4])[0]
                offset += 4

                # Value Data
                value_data = record_data[offset:offset+value_len]
                offset += value_len

                # Decode
                _, codec = TypeRegistry.get_codec(column.col_type)
                value, _ = codec.decode(value_data)
                record[col_name] = value

        return pk, record

    def get_metadata(self) -> Dict[str, Any]:
        """获取元数据"""
        if not self.exists():
            return {}

        file_stat = self.file_path.stat()
        file_size = file_stat.st_size
        modified_time = file_stat.st_mtime

        return {
            'engine': 'binary',
            'file_size': file_size,
            'modified': modified_time,
        }

    @classmethod
    def probe(cls, file_path: Union[str, Path]) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        轻量探测文件是否为 Binary 引擎格式

        通过检查文件头的魔数和版本号来识别 Binary 格式文件。
        只读取前 64 字节文件头，非常快速。

        Returns:
            Tuple[bool, Optional[Dict]]: (是否匹配, 元数据信息或None)
        """
        try:
            file_path = Path(file_path).expanduser()
            if not file_path.exists():
                return False, {'error': 'file_not_found'}

            # 检查文件大小是否足够包含魔数
            file_stat = file_path.stat()
            file_size = file_stat.st_size
            if file_size < 4:
                return False, {'error': 'file_too_small'}

            # 读取并检查文件头
            with open(file_path, 'rb') as f:
                magic = f.read(4)

                # 检查 v4 格式 (PTK4)
                if magic == cls.MAGIC_V4:
                    if file_size < cls.DUAL_HEADER_SIZE:
                        return False, {'error': 'file_too_small_for_v4'}

                    return True, {
                        'engine': 'binary',
                        'format_version': 4,
                        'file_size': file_size,
                        'modified': file_stat.st_mtime,
                        'confidence': 'high'
                    }

                # 检查旧版格式 (PYTK)
                if magic == cls.MAGIC_NUMBER:
                    if file_size < cls.FILE_HEADER_SIZE:
                        return False, {'error': 'file_too_small'}

                    f.seek(0)
                    header = f.read(cls.FILE_HEADER_SIZE)

                    # 检查版本号
                    try:
                        version = struct.unpack('<H', header[4:6])[0]
                    except struct.error:
                        return False, {'error': 'invalid_version_format'}

                    # 读取表数量
                    try:
                        table_count = struct.unpack('<I', header[6:10])[0]
                    except struct.error:
                        return False, {'error': 'invalid_table_count_format'}

                    # 成功识别为 Binary 格式
                    return True, {
                        'engine': 'binary',
                        'format_version': version,
                        'table_count': table_count,
                        'file_size': file_size,
                        'modified': file_stat.st_mtime,
                        'confidence': 'high'
                    }

                return False, None  # 不是错误，只是不匹配

        except Exception as e:
            return False, {'error': f'probe_exception: {str(e)}'}

    # ========== 索引区读写方法 ==========

    def _write_index_region_compressed(
        self,
        all_table_data: Dict[str, Dict[str, Any]]
    ) -> bytes:
        """
        构建压缩的索引区数据

        Returns:
            压缩后的索引区字节数据
        """
        buf = bytearray()

        # Index Format Version (固定 2 字节)
        buf += struct.pack('<H', 1)

        # Table Count (4 bytes)
        buf += struct.pack('<I', len(all_table_data))

        for table_name, table_data in all_table_data.items():
            # Table Name
            name_bytes = table_name.encode('utf-8')
            buf += struct.pack('<H', len(name_bytes))
            buf += name_bytes

            # PK Offsets
            pk_offsets = table_data.get('pk_offsets', {})
            buf += struct.pack('<I', len(pk_offsets))
            for pk, offset in pk_offsets.items():
                pk_bytes = self._serialize_index_value(pk)
                buf += struct.pack('<H', len(pk_bytes))
                buf += pk_bytes
                buf += struct.pack('<Q', offset)

            # Indexes
            indexes = table_data.get('indexes', {})
            buf += struct.pack('<H', len(indexes))

            for col_name, index in indexes.items():
                # Column Name
                col_bytes = col_name.encode('utf-8')
                buf += struct.pack('<H', len(col_bytes))
                buf += col_bytes

                # 获取索引映射
                idx_map = index.map if hasattr(index, 'map') else {}

                # Entry Count
                buf += struct.pack('<I', len(idx_map))

                for value, pk_set in idx_map.items():
                    # Value
                    value_bytes = self._serialize_index_value(value)
                    buf += struct.pack('<H', len(value_bytes))
                    buf += value_bytes

                    # PK List
                    pk_list = list(pk_set)
                    buf += struct.pack('<I', len(pk_list))
                    for pk in pk_list:
                        pk_bytes = self._serialize_index_value(pk)
                        buf += struct.pack('<H', len(pk_bytes))
                        buf += pk_bytes

        # 使用 zlib 压缩
        compressed = zlib.compress(bytes(buf), level=6)
        return compressed

    def _write_index_region(
        self,
        f: BinaryIO,
        all_table_data: Dict[str, Dict[str, Any]]
    ) -> None:
        """
        写入索引区（批量写入优化，固定宽度整数）

        格式（v1，使用固定宽度整数）：
        - Index Format Version (2 bytes): 值为 1
        - Table Count (4 bytes)
        - For each table:
            - Table Name Length (2 bytes) + Name
            - PK Offsets Count (4 bytes)
            - PK Offsets: [(pk_bytes_len 2 bytes, pk_bytes, offset 8 bytes), ...]
            - Index Count (2 bytes)
            - For each index:
                - Column Name Length (2 bytes) + Name
                - Entry Count (4 bytes)
                - Entries: [(value_bytes_len 2 bytes, value_bytes, pk_count 4 bytes, [pk_bytes...]), ...]
        """
        buf = bytearray()

        # Index Format Version (固定 2 字节)
        buf += struct.pack('<H', 1)

        # Table Count (4 bytes)
        buf += struct.pack('<I', len(all_table_data))

        for table_name, table_data in all_table_data.items():
            # Table Name
            name_bytes = table_name.encode('utf-8')
            buf += struct.pack('<H', len(name_bytes))
            buf += name_bytes

            # PK Offsets
            pk_offsets = table_data.get('pk_offsets', {})
            buf += struct.pack('<I', len(pk_offsets))
            for pk, offset in pk_offsets.items():
                pk_bytes = self._serialize_index_value(pk)
                buf += struct.pack('<H', len(pk_bytes))
                buf += pk_bytes
                buf += struct.pack('<Q', offset)

            # Indexes
            indexes = table_data.get('indexes', {})
            buf += struct.pack('<H', len(indexes))

            for col_name, index in indexes.items():
                # Column Name
                col_bytes = col_name.encode('utf-8')
                buf += struct.pack('<H', len(col_bytes))
                buf += col_bytes

                # 获取索引映射（HashIndex 的 map 属性）
                idx_map = index.map if hasattr(index, 'map') else {}

                # Entry Count
                buf += struct.pack('<I', len(idx_map))

                for value, pk_set in idx_map.items():
                    # Value
                    value_bytes = self._serialize_index_value(value)
                    buf += struct.pack('<H', len(value_bytes))
                    buf += value_bytes

                    # PK Set
                    pk_list = list(pk_set)
                    buf += struct.pack('<I', len(pk_list))
                    for pk in pk_list:
                        pk_bytes = self._serialize_index_value(pk)
                        buf += struct.pack('<H', len(pk_bytes))
                        buf += pk_bytes

        # 一次性写入
        f.write(buf)

    def _read_index_region(
        self,
        f: BinaryIO,
        compressed: bool = False
    ) -> Dict[str, Dict[str, Any]]:
        """
        读取索引区（批量读取 + 固定宽度整数）

        Args:
            f: 文件句柄
            compressed: 索引区是否已压缩

        Returns:
            {table_name: {'pk_offsets': {...}, 'indexes': {...}}}
        """
        # 一次性读取整个索引区数据
        raw_data = f.read()
        if not raw_data or len(raw_data) < 2:
            return {}

        # 如果是压缩数据，先解压
        if compressed:
            try:
                data = zlib.decompress(raw_data)
            except zlib.error:
                # 解压失败，尝试作为未压缩数据处理
                data = raw_data
        else:
            data = raw_data

        result: Dict[str, Dict[str, Any]] = {}

        # Index Format Version (固定 2 字节)
        idx_version = struct.unpack('<H', data[0:2])[0]
        if idx_version != 1:
            # 只支持 v1 格式
            return {}

        offset = 2

        # Table Count (4 bytes)
        table_count = struct.unpack('<I', data[offset:offset+4])[0]
        offset += 4

        for _ in range(table_count):
            # Table Name
            name_len = struct.unpack('<H', data[offset:offset+2])[0]
            offset += 2
            table_name = data[offset:offset+name_len].decode('utf-8')
            offset += name_len

            # PK Offsets
            pk_count = struct.unpack('<I', data[offset:offset+4])[0]
            offset += 4
            pk_offsets: Dict[Any, int] = {}
            for _ in range(pk_count):
                pk_len = struct.unpack('<H', data[offset:offset+2])[0]
                offset += 2
                pk = self._deserialize_index_value(data[offset:offset+pk_len])
                offset += pk_len
                file_offset = struct.unpack('<Q', data[offset:offset+8])[0]
                offset += 8
                pk_offsets[pk] = file_offset

            # Indexes
            idx_count = struct.unpack('<H', data[offset:offset+2])[0]
            offset += 2
            indexes: Dict[str, Dict[Any, Set[Any]]] = {}

            for _ in range(idx_count):
                # Column Name
                col_len = struct.unpack('<H', data[offset:offset+2])[0]
                offset += 2
                col_name = data[offset:offset+col_len].decode('utf-8')
                offset += col_len

                # Entry Count
                entry_count = struct.unpack('<I', data[offset:offset+4])[0]
                offset += 4
                idx_map: Dict[Any, Set[Any]] = {}

                for _ in range(entry_count):
                    # Value
                    val_len = struct.unpack('<H', data[offset:offset+2])[0]
                    offset += 2
                    value = self._deserialize_index_value(data[offset:offset+val_len])
                    offset += val_len

                    # PK Set
                    pk_list_len = struct.unpack('<I', data[offset:offset+4])[0]
                    offset += 4
                    pk_set: Set[Any] = set()
                    for _ in range(pk_list_len):
                        pk_len = struct.unpack('<H', data[offset:offset+2])[0]
                        offset += 2
                        pk = self._deserialize_index_value(data[offset:offset+pk_len])
                        offset += pk_len
                        pk_set.add(pk)

                    idx_map[value] = pk_set

                indexes[col_name] = idx_map

            result[table_name] = {
                'pk_offsets': pk_offsets,
                'indexes': indexes
            }

        return result

    def _parse_index_region(
        self,
        raw_data: bytes,
        compressed: bool = False
    ) -> Dict[str, Dict[str, Any]]:
        """
        解析索引区数据（从 bytes 解析，用于解密后的数据）

        Args:
            raw_data: 索引区原始数据（可能是压缩或加密后解密的）
            compressed: 数据是否已压缩

        Returns:
            {table_name: {'pk_offsets': {...}, 'indexes': {...}}}
        """
        if not raw_data or len(raw_data) < 2:
            return {}

        # 如果是压缩数据，先解压
        if compressed:
            try:
                data = zlib.decompress(raw_data)
            except zlib.error:
                # 解压失败，尝试作为未压缩数据处理
                data = raw_data
        else:
            data = raw_data

        result: Dict[str, Dict[str, Any]] = {}

        # Index Format Version (固定 2 字节)
        idx_version = struct.unpack('<H', data[0:2])[0]
        if idx_version != 1:
            # 只支持 v1 格式
            return {}

        offset = 2

        # Table Count (4 bytes)
        table_count = struct.unpack('<I', data[offset:offset+4])[0]
        offset += 4

        for _ in range(table_count):
            # Table Name
            name_len = struct.unpack('<H', data[offset:offset+2])[0]
            offset += 2
            table_name = data[offset:offset+name_len].decode('utf-8')
            offset += name_len

            # PK Offsets
            pk_count = struct.unpack('<I', data[offset:offset+4])[0]
            offset += 4
            pk_offsets: Dict[Any, int] = {}
            for _ in range(pk_count):
                pk_len = struct.unpack('<H', data[offset:offset+2])[0]
                offset += 2
                pk = self._deserialize_index_value(data[offset:offset+pk_len])
                offset += pk_len
                file_offset = struct.unpack('<Q', data[offset:offset+8])[0]
                offset += 8
                pk_offsets[pk] = file_offset

            # Indexes
            idx_count = struct.unpack('<H', data[offset:offset+2])[0]
            offset += 2
            indexes: Dict[str, Dict[Any, Set[Any]]] = {}

            for _ in range(idx_count):
                # Column Name
                col_len = struct.unpack('<H', data[offset:offset+2])[0]
                offset += 2
                col_name = data[offset:offset+col_len].decode('utf-8')
                offset += col_len

                # Entry Count
                entry_count = struct.unpack('<I', data[offset:offset+4])[0]
                offset += 4
                idx_map: Dict[Any, Set[Any]] = {}

                for _ in range(entry_count):
                    # Value
                    val_len = struct.unpack('<H', data[offset:offset+2])[0]
                    offset += 2
                    value = self._deserialize_index_value(data[offset:offset+val_len])
                    offset += val_len

                    # PK Set
                    pk_list_len = struct.unpack('<I', data[offset:offset+4])[0]
                    offset += 4
                    pk_set: Set[Any] = set()
                    for _ in range(pk_list_len):
                        pk_len = struct.unpack('<H', data[offset:offset+2])[0]
                        offset += 2
                        pk = self._deserialize_index_value(data[offset:offset+pk_len])
                        offset += pk_len
                        pk_set.add(pk)

                    idx_map[value] = pk_set

                indexes[col_name] = idx_map

            result[table_name] = {
                'pk_offsets': pk_offsets,
                'indexes': indexes
            }

        return result

    # ========== 高效值序列化（避免 JSON 开销） ==========

    def _serialize_index_value(self, value: Any) -> bytes:
        """
        高效序列化值（msgpack 风格）

        类型码：
        - 0x00: None
        - 0x01: bool
        - 0x02: int (1 byte, -128 ~ 127)
        - 0x03: int (2 bytes)
        - 0x04: int (4 bytes)
        - 0x05: int (8 bytes)
        - 0x06: float (8 bytes)
        - 0x07: str (short, <= 255 bytes)
        - 0x08: str (long, <= 65535 bytes)
        - 0xFF: JSON fallback
        """
        if value is None:
            return b'\x00'
        elif isinstance(value, bool):
            return b'\x01\x01' if value else b'\x01\x00'
        elif isinstance(value, int):
            if -128 <= value <= 127:
                return b'\x02' + struct.pack('<b', value)
            elif -32768 <= value <= 32767:
                return b'\x03' + struct.pack('<h', value)
            elif -2147483648 <= value <= 2147483647:
                return b'\x04' + struct.pack('<i', value)
            else:
                return b'\x05' + struct.pack('<q', value)
        elif isinstance(value, float):
            return b'\x06' + struct.pack('<d', value)
        elif isinstance(value, str):
            utf8 = value.encode('utf-8')
            if len(utf8) <= 255:
                return b'\x07' + struct.pack('<B', len(utf8)) + utf8
            else:
                return b'\x08' + struct.pack('<H', len(utf8)) + utf8
        else:
            # 回退到 JSON（罕见情况）
            json_bytes = json.dumps(value).encode('utf-8')
            return b'\xFF' + struct.pack('<H', len(json_bytes)) + json_bytes

    def _deserialize_index_value(self, data: bytes) -> Any:
        """
        反序列化值

        Args:
            data: 完整的序列化数据

        Returns:
            反序列化后的值
        """
        if not data:
            return None

        type_code = data[0]

        if type_code == 0x00:
            return None
        elif type_code == 0x01:
            return data[1] == 1
        elif type_code == 0x02:
            return struct.unpack('<b', data[1:2])[0]
        elif type_code == 0x03:
            return struct.unpack('<h', data[1:3])[0]
        elif type_code == 0x04:
            return struct.unpack('<i', data[1:5])[0]
        elif type_code == 0x05:
            return struct.unpack('<q', data[1:9])[0]
        elif type_code == 0x06:
            return struct.unpack('<d', data[1:9])[0]
        elif type_code == 0x07:
            length = data[1]
            return data[2:2+length].decode('utf-8')
        elif type_code == 0x08:
            length = struct.unpack('<H', data[1:3])[0]
            return data[3:3+length].decode('utf-8')
        elif type_code == 0xFF:
            length = struct.unpack('<H', data[1:3])[0]
            return json.loads(data[3:3+length].decode('utf-8'))
        else:
            raise SerializationError(f"Unknown type code: {type_code}")
