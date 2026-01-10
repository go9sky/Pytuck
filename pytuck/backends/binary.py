"""
Pytuck 二进制存储引擎

默认的持久化引擎，使用自定义二进制格式，无外部依赖
"""

import struct
import os
import tempfile
from typing import Any, Dict, TYPE_CHECKING, BinaryIO

if TYPE_CHECKING:
    from ..storage import Table

from .base import StorageBackend
from ..exceptions import SerializationError
from ..types import TypeRegistry, TypeCode
from ..orm import Column


class BinaryBackend(StorageBackend):
    """Binary format storage engine (default, no dependencies)"""

    ENGINE_NAME = 'binary'
    REQUIRED_DEPENDENCIES = []

    # 文件格式常量
    MAGIC_NUMBER = b'LTDB'
    VERSION = 1
    FILE_HEADER_SIZE = 64

    def save(self, tables: Dict[str, 'Table']) -> None:
        """保存所有表数据到二进制文件"""
        # 原子性写入：先写临时文件，再重命名
        temp_path = self.file_path + '.tmp'

        try:
            with open(temp_path, 'wb') as f:
                # 写入文件头
                self._write_file_header(f, len(tables))

                # 写入所有表
                for table_name, table in tables.items():
                    self._write_table(f, table)

            # 原子性重命名
            if os.path.exists(self.file_path):
                os.remove(self.file_path)
            os.rename(temp_path, self.file_path)

        except Exception as e:
            # 清理临时文件
            if os.path.exists(temp_path):
                os.remove(temp_path)
            raise SerializationError(f"Failed to save binary file: {e}")

    def load(self) -> Dict[str, 'Table']:
        """从二进制文件加载所有表数据"""
        if not self.exists():
            raise FileNotFoundError(f"Binary file not found: {self.file_path}")

        try:
            with open(self.file_path, 'rb') as f:
                # 读取文件头
                table_count = self._read_file_header(f)

                # 读取所有表
                tables = {}
                for _ in range(table_count):
                    table = self._read_table(f)
                    tables[table.name] = table

                return tables

        except Exception as e:
            raise SerializationError(f"Failed to load binary file: {e}")

    def exists(self) -> bool:
        """检查文件是否存在"""
        return os.path.exists(self.file_path)

    def delete(self) -> None:
        """删除文件"""
        if self.exists():
            os.remove(self.file_path)

    def _write_file_header(self, f: BinaryIO, table_count: int) -> None:
        """
        写入文件头（64字节）

        格式：
        - Magic Number: b'PYDB' (4 bytes)
        - Version: 1 (2 bytes)
        - Table Count: N (4 bytes)
        - Checksum: CRC32 (4 bytes)
        - Reserved: (50 bytes)
        """
        header = bytearray(self.FILE_HEADER_SIZE)

        # Magic Number
        header[0:4] = self.MAGIC_NUMBER

        # Version
        struct.pack_into('<H', header, 4, self.VERSION)

        # Table Count
        struct.pack_into('<I', header, 6, table_count)

        # Checksum (占位，后续可实现)
        struct.pack_into('<I', header, 10, 0)

        # Reserved (50 bytes, 填充0)

        f.write(header)

    def _read_file_header(self, f: BinaryIO) -> int:
        """读取文件头，返回表数量"""
        header = f.read(self.FILE_HEADER_SIZE)

        if len(header) < self.FILE_HEADER_SIZE:
            raise SerializationError("Invalid file header size")

        # 验证 Magic Number
        magic = header[0:4]
        if magic != self.MAGIC_NUMBER:
            raise SerializationError(f"Invalid magic number: {magic}")

        # 读取 Version
        version = struct.unpack('<H', header[4:6])[0]
        if version != self.VERSION:
            raise SerializationError(f"Unsupported version: {version}")

        # 读取 Table Count
        table_count = struct.unpack('<I', header[6:10])[0]

        return table_count

    def _write_table(self, f: BinaryIO, table: 'Table') -> None:
        """
        写入单个表

        格式：
        - Table Name Length (2 bytes)
        - Table Name (UTF-8)
        - Primary Key Length (2 bytes)
        - Primary Key (UTF-8)
        - Column Count (2 bytes)
        - Next ID (8 bytes)
        - Columns Data
        - Record Count (4 bytes)
        - Records Data
        """
        # Table Name
        table_name_bytes = table.name.encode('utf-8')
        f.write(struct.pack('<H', len(table_name_bytes)))
        f.write(table_name_bytes)

        # Primary Key
        pk_bytes = table.primary_key.encode('utf-8')
        f.write(struct.pack('<H', len(pk_bytes)))
        f.write(pk_bytes)

        # Column Count
        f.write(struct.pack('<H', len(table.columns)))

        # Next ID
        f.write(struct.pack('<Q', table.next_id))

        # Columns
        for col_name, column in table.columns.items():
            self._write_column(f, column)

        # Record Count
        f.write(struct.pack('<I', len(table.data)))

        # Records
        for pk, record in table.data.items():
            self._write_record(f, pk, record, table.columns)

    def _read_table(self, f: BinaryIO) -> 'Table':
        """读取单个表"""
        from ..storage import Table
        from ..orm import Column

        # Table Name
        name_len = struct.unpack('<H', f.read(2))[0]
        table_name = f.read(name_len).decode('utf-8')

        # Primary Key
        pk_len = struct.unpack('<H', f.read(2))[0]
        primary_key = f.read(pk_len).decode('utf-8')

        # Column Count
        col_count = struct.unpack('<H', f.read(2))[0]

        # Next ID
        next_id = struct.unpack('<Q', f.read(8))[0]

        # Columns
        columns = []
        for _ in range(col_count):
            column = self._read_column(f)
            columns.append(column)

        # 创建 Table 对象
        table = Table(table_name, columns, primary_key)
        table.next_id = next_id

        # Record Count
        record_count = struct.unpack('<I', f.read(4))[0]

        # Records
        for _ in range(record_count):
            pk, record = self._read_record(f, table.columns)
            table.data[pk] = record

        # 重建索引（清除构造函数创建的空索引）
        for col_name, column in table.columns.items():
            if column.index:
                # 删除空索引，重新构建
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

    def _read_column(self, f: BinaryIO) -> Column:
        """读取列定义"""
        from ..orm import Column

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

        return Column(
            col_name,
            col_type,
            nullable=nullable,
            primary_key=primary_key,
            index=index
        )

    def _write_record(self, f: BinaryIO, pk: Any, record: Dict[str, Any], columns: Dict[str, Column]) -> None:
        """
        写入单条记录

        格式：
        - Record Length (4 bytes) - 整条记录的字节数（不含此字段）
        - Primary Key (variable)
        - Field Count (2 bytes)
        - Fields (variable)
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
            # Column Index (通过名称查找)
            col_idx = list(columns.keys()).index(col_name)
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
        record = {}
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

        file_size = os.path.getsize(self.file_path)
        modified_time = os.path.getmtime(self.file_path)

        return {
            'engine': 'binary',
            'file_size': file_size,
            'modified': modified_time,
        }
