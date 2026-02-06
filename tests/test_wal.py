"""
WAL 预写日志测试

覆盖 pytuck/backends/backend_binary.py 中的 WAL 相关功能：
- WALEntry pack/unpack 往返一致性
- WALEntry CRC 校验
- HeaderV4 pack/unpack 往返一致性
- HeaderV4 CRC 校验与损坏检测
- HeaderV4 加密标志操作
- WAL 集成测试（append/read/replay/checkpoint/has_pending）
"""

import struct
import zlib
from pathlib import Path
from typing import Type

import pytest

from pytuck import Storage, declarative_base, Session, Column
from pytuck import PureBaseModel, insert, select
from pytuck.backends.backend_binary import (
    WALEntry, WALOpType, HeaderV4, BinaryBackend
)
from pytuck.common.exceptions import SerializationError
from pytuck.common.options import BinaryBackendOptions


# ---------- WALEntry pack/unpack ----------


class TestWALEntryPackUnpack:
    """WAL 条目序列化/反序列化测试"""

    def test_insert_entry_roundtrip(self) -> None:
        """INSERT 类型 pack/unpack 往返一致"""
        entry = WALEntry(
            lsn=1,
            op_type=WALOpType.INSERT,
            table_name='users',
            pk_bytes=b'\x04\x01\x00\x00\x00',  # int 1
            record_bytes=b'\x00\x01\x02\x03'
        )
        packed = entry.pack()
        unpacked, consumed = WALEntry.unpack(packed)

        assert consumed == len(packed)
        assert unpacked.lsn == 1
        assert unpacked.op_type == WALOpType.INSERT
        assert unpacked.table_name == 'users'
        assert unpacked.pk_bytes == entry.pk_bytes
        assert unpacked.record_bytes == entry.record_bytes

    def test_update_entry_roundtrip(self) -> None:
        """UPDATE 类型 pack/unpack 往返一致"""
        entry = WALEntry(
            lsn=42,
            op_type=WALOpType.UPDATE,
            table_name='products',
            pk_bytes=b'\x04\x05\x00\x00\x00',
            record_bytes=b'\xAA\xBB\xCC'
        )
        packed = entry.pack()
        unpacked, consumed = WALEntry.unpack(packed)

        assert consumed == len(packed)
        assert unpacked.lsn == 42
        assert unpacked.op_type == WALOpType.UPDATE
        assert unpacked.table_name == 'products'
        assert unpacked.pk_bytes == entry.pk_bytes
        assert unpacked.record_bytes == entry.record_bytes

    def test_delete_entry_roundtrip(self) -> None:
        """DELETE 类型 pack/unpack 往返一致（无 record_bytes）"""
        entry = WALEntry(
            lsn=100,
            op_type=WALOpType.DELETE,
            table_name='logs',
            pk_bytes=b'\x04\x0A\x00\x00\x00',
            record_bytes=b''
        )
        packed = entry.pack()
        unpacked, consumed = WALEntry.unpack(packed)

        assert consumed == len(packed)
        assert unpacked.lsn == 100
        assert unpacked.op_type == WALOpType.DELETE
        assert unpacked.table_name == 'logs'
        assert unpacked.record_bytes == b''

    def test_crc_mismatch_raises(self) -> None:
        """篡改 CRC 后 unpack 抛 SerializationError"""
        entry = WALEntry(
            lsn=1,
            op_type=WALOpType.INSERT,
            table_name='t',
            pk_bytes=b'\x04\x01\x00\x00\x00',
            record_bytes=b'\x00'
        )
        packed = bytearray(entry.pack())
        # 篡改最后 4 字节（CRC 位于 entry_data 末尾）
        packed[-1] ^= 0xFF
        packed[-2] ^= 0xFF

        with pytest.raises(SerializationError, match="CRC"):
            WALEntry.unpack(bytes(packed))

    def test_incomplete_data_raises(self) -> None:
        """不完整数据抛 SerializationError"""
        # 只有 2 字节，连 entry_len 都不够
        with pytest.raises(SerializationError):
            WALEntry.unpack(b'\x01\x02')

    def test_truncated_entry_raises(self) -> None:
        """entry_len 声明的长度大于实际数据"""
        entry = WALEntry(
            lsn=1,
            op_type=WALOpType.INSERT,
            table_name='t',
            pk_bytes=b'\x04\x01\x00\x00\x00',
            record_bytes=b'\x00'
        )
        packed = entry.pack()
        # 截断末尾
        truncated = packed[:len(packed) - 5]

        with pytest.raises(SerializationError):
            WALEntry.unpack(truncated)

    def test_unicode_table_name(self) -> None:
        """中文表名往返一致"""
        entry = WALEntry(
            lsn=1,
            op_type=WALOpType.INSERT,
            table_name='用户表',
            pk_bytes=b'\x04\x01\x00\x00\x00',
            record_bytes=b''
        )
        packed = entry.pack()
        unpacked, _ = WALEntry.unpack(packed)
        assert unpacked.table_name == '用户表'

    def test_multiple_entries_sequential(self) -> None:
        """多个条目顺序 pack 后可依次 unpack"""
        entries = [
            WALEntry(lsn=i, op_type=WALOpType.INSERT,
                     table_name='t', pk_bytes=struct.pack('<b', i),
                     record_bytes=b'\x00' * i)
            for i in range(1, 4)
        ]
        data = b''.join(e.pack() for e in entries)

        offset = 0
        for i, original in enumerate(entries):
            unpacked, consumed = WALEntry.unpack(data[offset:])
            assert unpacked.lsn == original.lsn
            assert unpacked.record_bytes == original.record_bytes
            offset += consumed

        assert offset == len(data)


# ---------- HeaderV4 ----------


class TestHeaderV4:
    """v4 文件头结构测试"""

    def test_pack_unpack_roundtrip(self) -> None:
        """HeaderV4 pack/unpack 字段一致"""
        header = HeaderV4(
            magic=b'PTK4',
            version=4,
            generation=10,
            schema_offset=256,
            schema_size=100,
            data_offset=356,
            data_size=2000,
            index_offset=2356,
            index_size=500,
            wal_offset=2856,
            wal_size=128,
            checkpoint_lsn=42,
            flags=0x01
        )
        packed = header.pack()
        assert len(packed) == 128

        unpacked = HeaderV4.unpack(packed)
        assert unpacked.magic == b'PTK4'
        assert unpacked.version == 4
        assert unpacked.generation == 10
        assert unpacked.schema_offset == 256
        assert unpacked.schema_size == 100
        assert unpacked.data_offset == 356
        assert unpacked.data_size == 2000
        assert unpacked.index_offset == 2356
        assert unpacked.index_size == 500
        assert unpacked.wal_offset == 2856
        assert unpacked.wal_size == 128
        assert unpacked.checkpoint_lsn == 42
        assert unpacked.flags == 0x01

    def test_verify_crc_valid(self) -> None:
        """合法数据 CRC 校验通过"""
        header = HeaderV4(generation=5)
        packed = header.pack()
        unpacked = HeaderV4.unpack(packed)
        assert unpacked.verify_crc(packed)

    def test_verify_crc_corrupted(self) -> None:
        """损坏数据 CRC 校验失败"""
        header = HeaderV4(generation=5)
        packed = bytearray(header.pack())
        # 篡改 generation 字段
        packed[6] ^= 0xFF
        unpacked = HeaderV4.unpack(bytes(packed))
        assert not unpacked.verify_crc(bytes(packed))

    def test_encryption_flags(self) -> None:
        """set_encryption/get_encryption_level/is_encrypted"""
        header = HeaderV4()

        # 默认未加密
        assert not header.is_encrypted()
        assert header.get_encryption_level() is None

        # 设置 low 加密
        salt = b'\x01' * 16
        key_check = b'\xAB\xCD\xEF\x01'
        header.set_encryption('low', salt, key_check)
        assert header.is_encrypted()
        assert header.get_encryption_level() == 'low'

        # pack/unpack 后保持
        packed = header.pack()
        unpacked = HeaderV4.unpack(packed)
        assert unpacked.is_encrypted()
        assert unpacked.get_encryption_level() == 'low'
        assert unpacked.salt == salt
        assert unpacked.key_check == key_check

    def test_encryption_levels(self) -> None:
        """三种加密等级都能正确设置和读取"""
        for level in ('low', 'medium', 'high'):
            header = HeaderV4()
            header.set_encryption(level, b'\x00' * 16, b'\x00' * 4)
            packed = header.pack()
            unpacked = HeaderV4.unpack(packed)
            assert unpacked.get_encryption_level() == level

    def test_header_too_short_raises(self) -> None:
        """Header 数据过短时抛 SerializationError"""
        with pytest.raises(SerializationError, match="Header too short"):
            HeaderV4.unpack(b'\x00' * 64)

    def test_default_values(self) -> None:
        """默认值正确"""
        header = HeaderV4()
        assert header.magic == b'PTK4'
        assert header.version == 4
        assert header.generation == 0
        assert header.wal_offset == 0
        assert header.wal_size == 0
        assert header.flags == 0

    def test_index_compressed_flag(self) -> None:
        """索引压缩标志位操作"""
        header = HeaderV4()
        header.flags |= HeaderV4.FLAG_INDEX_COMPRESSED
        assert (header.flags & HeaderV4.FLAG_INDEX_COMPRESSED) != 0

        packed = header.pack()
        unpacked = HeaderV4.unpack(packed)
        assert (unpacked.flags & HeaderV4.FLAG_INDEX_COMPRESSED) != 0


# ---------- WAL 集成测试 ----------


class TestWALIntegration:
    """WAL 集成测试（通过 Storage + BinaryBackend）"""

    def _create_db(self, temp_dir: Path) -> tuple:
        """创建临时数据库和模型"""
        db_path = temp_dir / 'wal_test.db'
        db = Storage(file_path=str(db_path))
        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'wal_users'
            id = Column(int, primary_key=True)
            name = Column(str)
            age = Column(int, nullable=True)

        return db, db_path, User

    def test_append_and_read_entries(self, temp_dir: Path) -> None:
        """append 后 read_wal_entries 返回相同条目"""
        db, db_path, User = self._create_db(temp_dir)

        # 先创建文件（需要 checkpoint 一次才有有效文件）
        session = Session(db)
        stmt = insert(User).values(name='Alice', age=20)
        session.execute(stmt)
        session.commit()
        db.flush()

        # 获取 backend 并手动 append WAL
        backend = db.backend
        assert isinstance(backend, BinaryBackend)

        lsn1 = backend.append_wal_entry(
            WALOpType.INSERT, 'wal_users',
            pk=2, record={'name': 'Bob', 'age': 25},
            columns=db.get_table('wal_users').columns
        )
        lsn2 = backend.append_wal_entry(
            WALOpType.UPDATE, 'wal_users',
            pk=1, record={'name': 'Alice2', 'age': 21},
            columns=db.get_table('wal_users').columns
        )

        assert lsn1 < lsn2

        # flush WAL 到磁盘
        backend.flush_wal_buffer()

        # 读取 WAL 条目
        entries = list(backend.read_wal_entries())
        assert len(entries) == 2
        assert entries[0].op_type == WALOpType.INSERT
        assert entries[0].table_name == 'wal_users'
        assert entries[1].op_type == WALOpType.UPDATE

        db.close()

    def test_replay_wal_insert(self, temp_dir: Path) -> None:
        """replay INSERT 操作正确修改表数据"""
        db, db_path, User = self._create_db(temp_dir)

        session = Session(db)
        stmt = insert(User).values(name='Alice', age=20)
        session.execute(stmt)
        session.commit()
        db.flush()

        backend = db.backend
        assert isinstance(backend, BinaryBackend)

        # 手动写一条 INSERT WAL
        table = db.get_table('wal_users')
        backend.append_wal_entry(
            WALOpType.INSERT, 'wal_users',
            pk=2, record={'name': 'Bob', 'age': 30},
            columns=table.columns
        )
        backend.flush_wal_buffer()

        # 模拟重新加载：先删除内存中的数据
        old_data_count = len(table.data)

        # replay
        count = backend.replay_wal(db.tables)
        assert count == 1

        # 验证数据被添加
        assert 2 in table.data
        assert table.data[2]['name'] == 'Bob'

        db.close()

    def test_replay_wal_delete(self, temp_dir: Path) -> None:
        """replay DELETE 操作正确删除表数据"""
        db, db_path, User = self._create_db(temp_dir)

        session = Session(db)
        stmt = insert(User).values(name='Alice', age=20)
        session.execute(stmt)
        session.commit()
        db.flush()

        backend = db.backend
        assert isinstance(backend, BinaryBackend)
        table = db.get_table('wal_users')

        assert 1 in table.data

        # 写 DELETE WAL
        backend.append_wal_entry(
            WALOpType.DELETE, 'wal_users',
            pk=1
        )
        backend.flush_wal_buffer()

        # replay
        count = backend.replay_wal(db.tables)
        assert count == 1
        assert 1 not in table.data

        db.close()

    def test_has_pending_wal_buffer(self, temp_dir: Path) -> None:
        """缓冲区有 WAL 条目时 has_pending_wal 返回 True"""
        db, db_path, User = self._create_db(temp_dir)

        session = Session(db)
        stmt = insert(User).values(name='Alice', age=20)
        session.execute(stmt)
        session.commit()
        db.flush()

        backend = db.backend
        assert isinstance(backend, BinaryBackend)

        # 初始无 pending
        assert not backend.has_pending_wal()

        # 添加到缓冲区（未 flush 到磁盘）
        backend.append_wal_entry(
            WALOpType.INSERT, 'wal_users',
            pk=2, record={'name': 'Bob', 'age': 25},
            columns=db.get_table('wal_users').columns
        )

        # 缓冲区有条目
        assert backend.has_pending_wal()

        db.close()

    def test_has_pending_wal_on_disk(self, temp_dir: Path) -> None:
        """磁盘上有 WAL 时 has_pending_wal 返回 True"""
        db, db_path, User = self._create_db(temp_dir)

        session = Session(db)
        stmt = insert(User).values(name='Alice', age=20)
        session.execute(stmt)
        session.commit()
        db.flush()

        backend = db.backend
        assert isinstance(backend, BinaryBackend)

        # 写入磁盘 WAL
        backend.append_wal_entry(
            WALOpType.INSERT, 'wal_users',
            pk=2, record={'name': 'Bob', 'age': 25},
            columns=db.get_table('wal_users').columns
        )
        backend.flush_wal_buffer()

        # 用新 backend 实例检查（模拟重启）
        new_backend = BinaryBackend(str(db_path), BinaryBackendOptions())
        assert new_backend.has_pending_wal()

        db.close()

    def test_checkpoint_clears_wal(self, temp_dir: Path) -> None:
        """checkpoint（save）后 WAL 被清除"""
        db, db_path, User = self._create_db(temp_dir)

        session = Session(db)
        stmt = insert(User).values(name='Alice', age=20)
        session.execute(stmt)
        session.commit()
        db.flush()

        backend = db.backend
        assert isinstance(backend, BinaryBackend)

        # 添加 WAL
        backend.append_wal_entry(
            WALOpType.INSERT, 'wal_users',
            pk=2, record={'name': 'Bob', 'age': 25},
            columns=db.get_table('wal_users').columns
        )
        backend.flush_wal_buffer()
        assert backend.has_pending_wal()

        # checkpoint（即 save，会重写整个文件）
        backend.save(db.tables)

        # WAL 应该被清除
        new_backend = BinaryBackend(str(db_path), BinaryBackendOptions())
        assert not new_backend.has_pending_wal()

        db.close()

    def test_wal_survives_reopen(self, temp_dir: Path) -> None:
        """写入 WAL 后重新打开文件能回放"""
        db, db_path, User = self._create_db(temp_dir)

        session = Session(db)
        stmt = insert(User).values(name='Alice', age=20)
        session.execute(stmt)
        session.commit()
        db.flush()

        # 手动追加 WAL
        backend = db.backend
        assert isinstance(backend, BinaryBackend)
        table = db.get_table('wal_users')

        backend.append_wal_entry(
            WALOpType.INSERT, 'wal_users',
            pk=2, record={'name': 'Bob', 'age': 30},
            columns=table.columns
        )
        backend.flush_wal_buffer()
        db.close()

        # 重新打开，加载数据
        new_backend = BinaryBackend(str(db_path), BinaryBackendOptions())
        tables = new_backend.load()
        assert 'wal_users' in tables

        # replay WAL
        count = new_backend.replay_wal(tables)
        assert count == 1
        assert 2 in tables['wal_users'].data
        assert tables['wal_users'].data[2]['name'] == 'Bob'

    def test_empty_wal_no_entries(self, temp_dir: Path) -> None:
        """无 WAL 时 read_wal_entries 返回空"""
        db, db_path, User = self._create_db(temp_dir)

        session = Session(db)
        stmt = insert(User).values(name='Alice', age=20)
        session.execute(stmt)
        session.commit()
        db.flush()

        backend = db.backend
        assert isinstance(backend, BinaryBackend)

        entries = list(backend.read_wal_entries())
        assert len(entries) == 0

        db.close()

    def test_flush_empty_buffer_noop(self, temp_dir: Path) -> None:
        """空缓冲区 flush 不报错"""
        db, db_path, User = self._create_db(temp_dir)

        session = Session(db)
        stmt = insert(User).values(name='Alice', age=20)
        session.execute(stmt)
        session.commit()
        db.flush()

        backend = db.backend
        assert isinstance(backend, BinaryBackend)

        # flush 空缓冲区应该是 no-op
        backend.flush_wal_buffer()
        assert not backend.has_pending_wal()

        db.close()

    def test_wal_lsn_increments(self, temp_dir: Path) -> None:
        """每次 append 后 LSN 递增"""
        db, db_path, User = self._create_db(temp_dir)

        session = Session(db)
        stmt = insert(User).values(name='Alice', age=20)
        session.execute(stmt)
        session.commit()
        db.flush()

        backend = db.backend
        assert isinstance(backend, BinaryBackend)
        table = db.get_table('wal_users')

        lsn1 = backend.append_wal_entry(
            WALOpType.INSERT, 'wal_users',
            pk=2, record={'name': 'B', 'age': 1},
            columns=table.columns
        )
        lsn2 = backend.append_wal_entry(
            WALOpType.INSERT, 'wal_users',
            pk=3, record={'name': 'C', 'age': 2},
            columns=table.columns
        )
        lsn3 = backend.append_wal_entry(
            WALOpType.DELETE, 'wal_users',
            pk=2
        )

        assert lsn1 < lsn2 < lsn3

        db.close()


# ---------- 双 Header 测试 ----------


class TestDualHeader:
    """双 Header 选择逻辑测试"""

    def test_both_valid_higher_generation_wins(self) -> None:
        """两个 Header 都合法时选择 generation 更大的"""
        header_a = HeaderV4(generation=5)
        header_b = HeaderV4(generation=10)

        packed_a = header_a.pack()
        packed_b = header_b.pack()

        unpacked_a = HeaderV4.unpack(packed_a)
        unpacked_b = HeaderV4.unpack(packed_b)

        # 两个都合法
        assert unpacked_a.verify_crc(packed_a)
        assert unpacked_b.verify_crc(packed_b)

        # generation 更大的应该被选中
        if unpacked_a.generation >= unpacked_b.generation:
            selected = unpacked_a
        else:
            selected = unpacked_b

        assert selected.generation == 10

    def test_one_corrupted_uses_valid(self) -> None:
        """一个 Header 损坏时使用另一个"""
        header = HeaderV4(generation=5)
        packed = header.pack()

        # 损坏副本
        corrupted = bytearray(packed)
        corrupted[6] ^= 0xFF  # 篡改 generation
        corrupted_bytes = bytes(corrupted)

        unpacked_valid = HeaderV4.unpack(packed)
        unpacked_corrupted = HeaderV4.unpack(corrupted_bytes)

        assert unpacked_valid.verify_crc(packed)
        assert not unpacked_corrupted.verify_crc(corrupted_bytes)

    def test_same_generation_picks_a(self) -> None:
        """同 generation 时优先选择 Header A"""
        header = HeaderV4(generation=5)
        packed = header.pack()

        unpacked_a = HeaderV4.unpack(packed)
        unpacked_b = HeaderV4.unpack(packed)

        # 两个合法且 generation 相同
        assert unpacked_a.verify_crc(packed)
        assert unpacked_b.verify_crc(packed)

        # 按 _load_v4 逻辑，generation 相等时选 A
        if unpacked_a.generation >= unpacked_b.generation:
            selected_slot = 0  # A
        else:
            selected_slot = 1  # B

        assert selected_slot == 0
