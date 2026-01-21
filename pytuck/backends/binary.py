"""
Pytuck 二进制存储引擎

默认的持久化引擎，使用自定义二进制格式，无外部依赖
"""

import json
import struct
from pathlib import Path
from typing import Any, Dict, List, Set, Union, TYPE_CHECKING, BinaryIO, Tuple, Optional

if TYPE_CHECKING:
    from ..core.storage import Table

from .base import StorageBackend
from ..common.exceptions import SerializationError
from ..core.types import TypeRegistry, TypeCode
from ..core.orm import Column
from ..core.index import HashIndex
from .versions import get_format_version

from ..common.options import BinaryBackendOptions


class BinaryBackend(StorageBackend):
    """Binary format storage engine (default, no dependencies)"""

    ENGINE_NAME = 'binary'
    REQUIRED_DEPENDENCIES = []

    # 文件格式常量
    MAGIC_NUMBER = b'PYTK'
    FORMAT_VERSION = get_format_version('binary')
    FILE_HEADER_SIZE = 64

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

    def save(self, tables: Dict[str, 'Table']) -> None:
        """保存所有表数据到二进制文件（v3 格式：含索引区）"""
        # 原子性写入：先写临时文件，再重命名
        temp_path = self.file_path.parent / (self.file_path.name + '.tmp')

        # 收集所有表的 pk_offsets 和索引数据
        all_table_index_data: Dict[str, Dict[str, Any]] = {}

        try:
            with open(temp_path, 'wb') as f:
                # 1. 预留文件头位置（稍后回填索引区偏移）
                header_pos = f.tell()
                f.write(b'\x00' * self.FILE_HEADER_SIZE)

                # 2. 写入 Schema 区（所有表的元数据）
                for table_name, table in tables.items():
                    self._write_table_schema(f, table)

                # 3. 写入数据区（记录每条记录的偏移）
                for table_name, table in tables.items():
                    pk_offsets = self._write_table_data_v3(f, table)
                    all_table_index_data[table_name] = {
                        'pk_offsets': pk_offsets,
                        'indexes': table.indexes
                    }

                # 4. 写入索引区
                index_region_offset = f.tell()
                self._write_index_region(f, all_table_index_data)
                index_region_size = f.tell() - index_region_offset

                # 5. 回填文件头（包含索引区信息）
                f.seek(header_pos)
                self._write_file_header_v3(f, len(tables), index_region_offset, index_region_size)

            # 原子性重命名
            temp_path.replace(self.file_path)

        except Exception as e:
            # 清理临时文件
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except FileNotFoundError:
                    pass
            raise SerializationError(f"Failed to save binary file: {e}")

    def load(self) -> Dict[str, 'Table']:
        """从二进制文件加载所有表数据（支持 v3 格式和懒加载）"""
        if not self.exists():
            raise FileNotFoundError(f"Binary file not found: {self.file_path}")

        try:
            with open(self.file_path, 'rb') as f:
                # 读取文件头（v3 格式包含索引区信息）
                table_count, index_offset, index_size = self._read_file_header_v3(f)

                # 读取 Schema 区（所有表的元数据）
                tables_schema = []
                for _ in range(table_count):
                    schema = self._read_table_schema(f)
                    tables_schema.append(schema)

                # 读取索引区（如果存在）
                index_data: Dict[str, Dict[str, Any]] = {}
                if index_offset > 0 and index_size > 0:
                    current_pos = f.tell()
                    f.seek(index_offset)
                    index_data = self._read_index_region(f)
                    f.seek(current_pos)

                tables = {}

                # 懒加载模式：只加载 schema 和索引，不加载数据
                if self.options.lazy_load and index_data:
                    for schema in tables_schema:
                        table = self._create_lazy_table(schema, index_data)
                        tables[table.name] = table
                else:
                    # 完整加载模式：读取所有数据
                    for schema in tables_schema:
                        table = self._read_table_data_v3(f, schema, index_data)
                        tables[table.name] = table

                return tables

        except Exception as e:
            raise SerializationError(f"Failed to load binary file: {e}")

    def _create_lazy_table(
        self,
        schema: Dict[str, Any],
        index_data: Dict[str, Dict[str, Any]]
    ) -> 'Table':
        """
        创建懒加载表（只加载 schema 和索引，不加载数据）

        Args:
            schema: 表结构信息
            index_data: 从索引区读取的索引数据

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

        # 从索引区获取数据
        table_idx_data = index_data.get(table_name, {})
        table._pk_offsets = table_idx_data.get('pk_offsets', {})

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

    def _write_file_header(self, f: BinaryIO, table_count: int) -> None:
        """向后兼容：旧版文件头写入（已弃用，仅供参考）"""
        self._write_file_header_v3(f, table_count, 0, 0)

    def _write_file_header_v3(
        self,
        f: BinaryIO,
        table_count: int,
        index_offset: int,
        index_size: int
    ) -> None:
        """
        写入文件头（64字节，v3 格式）

        格式：
        - Magic Number: b'PYTK' (4 bytes)
        - Version: 3 (2 bytes)
        - Table Count: N (4 bytes)
        - Index Region Offset (8 bytes)
        - Index Region Size (8 bytes)
        - Checksum: CRC32 (4 bytes，占位）
        - Reserved: (34 bytes)
        """
        header = bytearray(self.FILE_HEADER_SIZE)

        # Magic Number
        header[0:4] = self.MAGIC_NUMBER

        # Version
        struct.pack_into('<H', header, 4, self.FORMAT_VERSION)

        # Table Count
        struct.pack_into('<I', header, 6, table_count)

        # Index Region Offset (8 bytes)
        struct.pack_into('<Q', header, 10, index_offset)

        # Index Region Size (8 bytes)
        struct.pack_into('<Q', header, 18, index_size)

        # Checksum (占位)
        struct.pack_into('<I', header, 26, 0)

        # Reserved (34 bytes, 30-63，填充0)

        f.write(header)

    def _read_file_header(self, f: BinaryIO) -> int:
        """向后兼容：旧版文件头读取"""
        table_count, _, _ = self._read_file_header_v3(f)
        return table_count

    def _read_file_header_v3(self, f: BinaryIO) -> Tuple[int, int, int]:
        """
        读取文件头（v3 格式）

        Returns:
            Tuple[table_count, index_offset, index_size]
        """
        header = f.read(self.FILE_HEADER_SIZE)

        if len(header) < self.FILE_HEADER_SIZE:
            raise SerializationError("Invalid file header size")

        # 验证 Magic Number
        magic = header[0:4]
        if magic != self.MAGIC_NUMBER:
            raise SerializationError(f"Invalid magic number: {magic!r}")

        # 读取 Version
        version = struct.unpack('<H', header[4:6])[0]
        if version < 2:
            raise SerializationError(f"Unsupported old version: {version}, please migrate to v3")
        if version > self.FORMAT_VERSION:
            raise SerializationError(f"Unsupported future version: {version}")

        # 读取 Table Count
        table_count = struct.unpack('<I', header[6:10])[0]

        # 读取 Index Region 信息（v3+）
        index_offset = 0
        index_size = 0
        if version >= 3:
            index_offset = struct.unpack('<Q', header[10:18])[0]
            index_size = struct.unpack('<Q', header[18:26])[0]

        return table_count, index_offset, index_size

    def _write_table_schema(self, f: BinaryIO, table: 'Table') -> None:
        """
        写入单个表的 Schema（元数据）

        格式：
        - Table Name Length (2 bytes)
        - Table Name (UTF-8)
        - Primary Key Length (2 bytes)
        - Primary Key (UTF-8)
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

        # Primary Key
        pk_bytes = table.primary_key.encode('utf-8')
        f.write(struct.pack('<H', len(pk_bytes)))
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

        # Primary Key
        pk_len = struct.unpack('<H', f.read(2))[0]
        primary_key = f.read(pk_len).decode('utf-8')

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

    def _write_table_data(self, f: BinaryIO, table: 'Table') -> None:
        """
        写入单个表的数据

        格式：
        - Record Count (4 bytes)
        - Records Data
        """
        # Record Count
        f.write(struct.pack('<I', len(table.data)))

        # 预先构建列名到索引的映射，避免每条记录都 O(n) 查找
        col_idx_map = {name: idx for idx, name in enumerate(table.columns.keys())}

        # Records
        for pk, record in table.data.items():
            self._write_record(f, pk, record, table.columns, col_idx_map)

    def _write_table_data_v3(self, f: BinaryIO, table: 'Table') -> Dict[Any, int]:
        """
        写入单个表的数据（v3 格式，记录 pk_offsets）

        格式：
        - Record Count (4 bytes)
        - Records Data

        Returns:
            pk_offsets: 主键到文件偏移的映射
        """
        pk_offsets: Dict[Any, int] = {}

        # Record Count
        f.write(struct.pack('<I', len(table.data)))

        # 预先构建列名到索引的映射，避免每条记录都 O(n) 查找
        col_idx_map = {name: idx for idx, name in enumerate(table.columns.keys())}

        # Records（记录每条记录的偏移位置）
        for pk, record in table.data.items():
            pk_offsets[pk] = f.tell()  # 记录当前偏移
            self._write_record(f, pk, record, table.columns, col_idx_map)

        return pk_offsets

    def _read_table_data(self, f: BinaryIO, schema: Dict[str, Any]) -> 'Table':
        """根据 schema 读取表数据，返回 Table 对象"""
        from ..core.storage import Table

        # 创建 Table 对象
        table = Table(
            schema['table_name'],
            schema['columns'],
            schema['primary_key'],
            comment=schema.get('table_comment')
        )
        table.next_id = schema['next_id']

        # 构建 columns 字典用于记录读取
        columns_dict = {col.name: col for col in schema['columns']}

        # Record Count
        record_count = struct.unpack('<I', f.read(4))[0]

        # Records
        for _ in range(record_count):
            pk, record = self._read_record(f, columns_dict)
            table.data[pk] = record

        # 重建索引（清除构造函数创建的空索引）
        for col_name, column in table.columns.items():
            if column.index:
                if col_name in table.indexes:
                    del table.indexes[col_name]
                table.build_index(col_name)

        return table

    def _read_table_data_v3(
        self,
        f: BinaryIO,
        schema: Dict[str, Any],
        index_data: Dict[str, Dict[str, Any]]
    ) -> 'Table':
        """
        根据 schema 读取表数据（v3 格式，从索引区恢复索引）

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

        # Record Count
        record_count = struct.unpack('<I', f.read(4))[0]

        # Records
        for _ in range(record_count):
            pk, record = self._read_record(f, columns_dict)
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
            col_name,
            col_type,
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
                _, codec = TypeRegistry.get_codec(column.col_type)
                value_bytes = codec.encode(value)
                # 类型码 + 长度 + 数据
                type_code, _ = TypeRegistry.get_codec(column.col_type)
                record_data.extend(struct.pack('B', type_code))
                record_data.extend(struct.pack('<I', len(value_bytes)))
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

            # 检查文件大小是否足够包含文件头
            file_stat = file_path.stat()
            file_size = file_stat.st_size
            if file_size < cls.FILE_HEADER_SIZE:
                return False, {'error': 'file_too_small'}

            # 读取并检查文件头
            with open(file_path, 'rb') as f:
                header = f.read(cls.FILE_HEADER_SIZE)

            if len(header) < cls.FILE_HEADER_SIZE:
                return False, {'error': 'header_incomplete'}

            # 检查魔数
            magic = header[0:4]
            if magic != cls.MAGIC_NUMBER:
                return False, None  # 不是错误，只是不匹配

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

        except Exception as e:
            return False, {'error': f'probe_exception: {str(e)}'}

    # ========== 索引区读写方法（v3 格式） ==========

    def _write_index_region(
        self,
        f: BinaryIO,
        all_table_data: Dict[str, Dict[str, Any]]
    ) -> None:
        """
        写入索引区（批量写入优化）

        格式（v2，使用 varint）：
        - Index Format Version (2 bytes): 值为 2
        - Table Count (varint)
        - For each table:
            - Table Name Length (varint) + Name
            - PK Offsets Count (varint)
            - PK Offsets: [(pk_bytes_len varint, pk_bytes, offset varint), ...]
            - Index Count (varint)
            - For each index:
                - Column Name Length (varint) + Name
                - Entry Count (varint)
                - Entries: [(value_bytes_len varint, value_bytes, pk_count varint, [pk_bytes...]), ...]
        """
        buf = bytearray()

        # Index Format Version (固定 2 字节，便于快速识别版本)
        buf += struct.pack('<H', 2)

        # Table Count (varint)
        buf += self._pack_varint(len(all_table_data))

        for table_name, table_data in all_table_data.items():
            # Table Name
            name_bytes = table_name.encode('utf-8')
            buf += self._pack_varint(len(name_bytes))
            buf += name_bytes

            # PK Offsets
            pk_offsets = table_data.get('pk_offsets', {})
            buf += self._pack_varint(len(pk_offsets))
            for pk, offset in pk_offsets.items():
                pk_bytes = self._serialize_index_value(pk)
                buf += self._pack_varint(len(pk_bytes))
                buf += pk_bytes
                buf += self._pack_varint(offset)

            # Indexes
            indexes = table_data.get('indexes', {})
            buf += self._pack_varint(len(indexes))

            for col_name, index in indexes.items():
                # Column Name
                col_bytes = col_name.encode('utf-8')
                buf += self._pack_varint(len(col_bytes))
                buf += col_bytes

                # 获取索引映射（HashIndex 的 map 属性）
                idx_map = index.map if hasattr(index, 'map') else {}

                # Entry Count
                buf += self._pack_varint(len(idx_map))

                for value, pk_set in idx_map.items():
                    # Value
                    value_bytes = self._serialize_index_value(value)
                    buf += self._pack_varint(len(value_bytes))
                    buf += value_bytes

                    # PK Set
                    pk_list = list(pk_set)
                    buf += self._pack_varint(len(pk_list))
                    for pk in pk_list:
                        pk_bytes = self._serialize_index_value(pk)
                        buf += self._pack_varint(len(pk_bytes))
                        buf += pk_bytes

        # 一次性写入
        f.write(buf)

    def _read_index_region(self, f: BinaryIO) -> Dict[str, Dict[str, Any]]:
        """
        读取索引区（批量读取 + varint 编码）

        Returns:
            {table_name: {'pk_offsets': {...}, 'indexes': {...}}}
        """
        # 一次性读取整个索引区数据
        data = f.read()
        if not data or len(data) < 2:
            return {}

        result: Dict[str, Dict[str, Any]] = {}

        # Index Format Version (固定 2 字节)
        idx_version = struct.unpack('<H', data[0:2])[0]
        if idx_version != 2:
            # 只支持 v2 格式
            return {}

        offset = 2

        # Table Count (varint)
        table_count, consumed = self._unpack_varint(data, offset)
        offset += consumed

        for _ in range(table_count):
            # Table Name
            name_len, consumed = self._unpack_varint(data, offset)
            offset += consumed
            table_name = data[offset:offset+name_len].decode('utf-8')
            offset += name_len

            # PK Offsets
            pk_count, consumed = self._unpack_varint(data, offset)
            offset += consumed
            pk_offsets: Dict[Any, int] = {}
            for _ in range(pk_count):
                pk_len, consumed = self._unpack_varint(data, offset)
                offset += consumed
                pk = self._deserialize_index_value(data[offset:offset+pk_len])
                offset += pk_len
                file_offset, consumed = self._unpack_varint(data, offset)
                offset += consumed
                pk_offsets[pk] = file_offset

            # Indexes
            idx_count, consumed = self._unpack_varint(data, offset)
            offset += consumed
            indexes: Dict[str, Dict[Any, Set[Any]]] = {}

            for _ in range(idx_count):
                # Column Name
                col_len, consumed = self._unpack_varint(data, offset)
                offset += consumed
                col_name = data[offset:offset+col_len].decode('utf-8')
                offset += col_len

                # Entry Count
                entry_count, consumed = self._unpack_varint(data, offset)
                offset += consumed
                idx_map: Dict[Any, Set[Any]] = {}

                for _ in range(entry_count):
                    # Value
                    val_len, consumed = self._unpack_varint(data, offset)
                    offset += consumed
                    value = self._deserialize_index_value(data[offset:offset+val_len])
                    offset += val_len

                    # PK Set
                    pk_list_len, consumed = self._unpack_varint(data, offset)
                    offset += consumed
                    pk_set: Set[Any] = set()
                    for _ in range(pk_list_len):
                        pk_len, consumed = self._unpack_varint(data, offset)
                        offset += consumed
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

    # ========== Varint 变长整数编码 ==========

    # 预计算常见小整数的 varint 编码（0-255）
    _VARINT_CACHE = [bytes([i]) if i < 128 else bytes([(i & 0x7F) | 0x80, i >> 7]) for i in range(256)]

    def _pack_varint(self, n: int) -> bytes:
        """
        变长整数编码（类似 protobuf varint，带缓存优化）

        编码规则：
        - 每个字节使用 7 位存储数据，最高位为继续标志
        - 最高位为 1 表示后面还有字节，为 0 表示结束
        - 支持非负整数

        Args:
            n: 非负整数

        Returns:
            编码后的字节串
        """
        # 快速路径：使用预计算缓存（覆盖大多数长度字段）
        if n < 256:
            return self._VARINT_CACHE[n]

        # 慢速路径：动态计算
        out = bytearray()
        while n >= 128:
            out.append((n & 0x7F) | 0x80)
            n >>= 7
        out.append(n)
        return bytes(out)

    def _unpack_varint(self, data: bytes, offset: int = 0) -> Tuple[int, int]:
        """
        反序列化变长整数

        Args:
            data: 字节数据
            offset: 起始偏移

        Returns:
            Tuple[int, int]: (解码的值, 消耗的字节数)
        """
        result = 0
        shift = 0
        pos = offset
        while True:
            if pos >= len(data):
                raise SerializationError("Varint overflow: unexpected end of data")
            byte = data[pos]
            result |= (byte & 0x7F) << shift
            pos += 1
            if byte < 128:
                break
            shift += 7
            if shift > 63:
                raise SerializationError("Varint overflow: value too large")
        return result, pos - offset

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
