"""
懒加载测试

覆盖 pytuck/backends/backend_binary.py 的懒加载功能：
- 启用懒加载后表标记为 _lazy_loaded
- 懒加载模式下按主键查询单条记录
- 索引字段在懒加载下工作
- 全表数据加载（populate_tables_with_data）
- 加密模式下懒加载被禁用
- 多表懒加载
"""

from pathlib import Path
from typing import Type

import pytest

from pytuck import Storage, declarative_base, Session, Column
from pytuck import PureBaseModel, insert, select
from pytuck.common.options import BinaryBackendOptions
from pytuck.backends.backend_binary import BinaryBackend


# ---------- 懒加载基础测试 ----------


class TestLazyLoadBasic:
    """懒加载基础功能测试"""

    def _create_and_populate(self, temp_dir: Path) -> Path:
        """创建并填充数据库文件，返回路径"""
        db_path = temp_dir / 'lazy.db'
        db = Storage(
            file_path=str(db_path),
            engine='binary',
            backend_options=BinaryBackendOptions()
        )
        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)
            age = Column(int, nullable=True)

        session = Session(db)
        session.execute(insert(User).values(name='Alice', age=20))
        session.execute(insert(User).values(name='Bob', age=25))
        session.execute(insert(User).values(name='Charlie', age=30))
        session.commit()
        db.flush()
        db.close()

        return db_path

    def test_lazy_load_enabled(self, temp_dir: Path) -> None:
        """启用懒加载后 table._lazy_loaded=True"""
        db_path = self._create_and_populate(temp_dir)

        backend = BinaryBackend(str(db_path), BinaryBackendOptions(lazy_load=True))
        tables = backend.load()

        assert 'users' in tables
        table = tables['users']
        assert table._lazy_loaded is True
        # 懒加载模式下 data 应该为空
        assert len(table.data) == 0
        # 但 pk_offsets 应该有数据
        assert table._pk_offsets is not None
        assert len(table._pk_offsets) == 3

    def test_lazy_load_query_single(self, temp_dir: Path) -> None:
        """懒加载模式下按主键查询单条记录"""
        db_path = self._create_and_populate(temp_dir)

        backend = BinaryBackend(str(db_path), BinaryBackendOptions(lazy_load=True))
        tables = backend.load()
        table = tables['users']

        # 通过 get 按需加载
        record = table.get(1)
        assert record['name'] == 'Alice'
        assert record['age'] == 20

        record2 = table.get(2)
        assert record2['name'] == 'Bob'
        assert record2['age'] == 25

    def test_lazy_load_query_nonexistent(self, temp_dir: Path) -> None:
        """懒加载下查询不存在的主键"""
        from pytuck.common.exceptions import RecordNotFoundError

        db_path = self._create_and_populate(temp_dir)

        backend = BinaryBackend(str(db_path), BinaryBackendOptions(lazy_load=True))
        tables = backend.load()
        table = tables['users']

        with pytest.raises(RecordNotFoundError):
            table.get(999)

    def test_lazy_load_with_index(self, temp_dir: Path) -> None:
        """索引字段在懒加载下被恢复"""
        db_path = temp_dir / 'lazy_idx.db'
        db = Storage(
            file_path=str(db_path),
            engine='binary',
            backend_options=BinaryBackendOptions()
        )
        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str, index=True)

        session = Session(db)
        session.execute(insert(User).values(name='Alice'))
        session.execute(insert(User).values(name='Bob'))
        session.execute(insert(User).values(name='Alice'))
        session.commit()
        db.flush()
        db.close()

        # 懒加载打开
        backend = BinaryBackend(str(db_path), BinaryBackendOptions(lazy_load=True))
        tables = backend.load()
        table = tables['users']

        # 索引应该被恢复
        assert 'name' in table.indexes
        alice_pks = table.indexes['name'].lookup('Alice')
        assert len(alice_pks) == 2

    def test_lazy_load_supports_flag(self, temp_dir: Path) -> None:
        """supports_lazy_loading 返回正确值"""
        backend_lazy = BinaryBackend('test.db', BinaryBackendOptions(lazy_load=True))
        assert backend_lazy.supports_lazy_loading() is True

        backend_normal = BinaryBackend('test.db', BinaryBackendOptions(lazy_load=False))
        assert backend_normal.supports_lazy_loading() is False


# ---------- 填充数据测试 ----------


class TestPopulateTablesWithData:
    """populate_tables_with_data 测试"""

    def test_populate_fills_all_records(self, temp_dir: Path) -> None:
        """populate 后 table.data 包含所有记录"""
        db_path = temp_dir / 'lazy_populate.db'
        db = Storage(
            file_path=str(db_path),
            engine='binary',
            backend_options=BinaryBackendOptions()
        )
        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        session = Session(db)
        session.execute(insert(User).values(name='Alice'))
        session.execute(insert(User).values(name='Bob'))
        session.commit()
        db.flush()
        db.close()

        # 懒加载打开
        backend = BinaryBackend(str(db_path), BinaryBackendOptions(lazy_load=True))
        tables = backend.load()

        # 数据未加载
        assert len(tables['users'].data) == 0

        # populate
        backend.populate_tables_with_data(tables)

        # 数据已加载
        assert len(tables['users'].data) == 2
        names = {r['name'] for r in tables['users'].data.values()}
        assert names == {'Alice', 'Bob'}

    def test_populate_idempotent(self, temp_dir: Path) -> None:
        """多次 populate 幂等"""
        db_path = temp_dir / 'lazy_idem.db'
        db = Storage(
            file_path=str(db_path),
            engine='binary',
            backend_options=BinaryBackendOptions()
        )
        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        session = Session(db)
        session.execute(insert(User).values(name='Alice'))
        session.commit()
        db.flush()
        db.close()

        backend = BinaryBackend(str(db_path), BinaryBackendOptions(lazy_load=True))
        tables = backend.load()

        backend.populate_tables_with_data(tables)
        assert len(tables['users'].data) == 1

        # 再次 populate 应该幂等
        backend.populate_tables_with_data(tables)
        assert len(tables['users'].data) == 1

    def test_populate_non_lazy_noop(self, temp_dir: Path) -> None:
        """非懒加载模式下 populate 是 no-op"""
        db_path = temp_dir / 'non_lazy.db'
        db = Storage(
            file_path=str(db_path),
            engine='binary',
            backend_options=BinaryBackendOptions()
        )
        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        session = Session(db)
        session.execute(insert(User).values(name='Alice'))
        session.commit()
        db.flush()
        db.close()

        # 非懒加载模式
        backend = BinaryBackend(str(db_path), BinaryBackendOptions(lazy_load=False))
        tables = backend.load()
        assert len(tables['users'].data) == 1  # 数据已加载

        # populate 是 no-op
        backend.populate_tables_with_data(tables)
        assert len(tables['users'].data) == 1


# ---------- 加密与懒加载交互 ----------


class TestLazyLoadWithEncryption:
    """加密模式下懒加载行为测试"""

    def test_encryption_disables_lazy_load(self, temp_dir: Path) -> None:
        """加密模式下懒加载被禁用，数据全量加载"""
        db_path = temp_dir / 'enc_lazy.db'
        db = Storage(
            file_path=str(db_path),
            engine='binary',
            backend_options=BinaryBackendOptions(
                encryption='low', password='test'
            )
        )
        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        session = Session(db)
        session.execute(insert(User).values(name='Alice'))
        session.execute(insert(User).values(name='Bob'))
        session.commit()
        db.flush()
        db.close()

        # 即使指定 lazy_load=True，加密文件也应该全量加载
        backend = BinaryBackend(
            str(db_path),
            BinaryBackendOptions(
                lazy_load=True, encryption='low', password='test'
            )
        )
        tables = backend.load()
        table = tables['users']

        # 加密时应该全量加载，不是懒加载
        assert not getattr(table, '_lazy_loaded', False)
        assert len(table.data) == 2


# ---------- 多表懒加载 ----------


class TestLazyLoadMultipleTables:
    """多表懒加载测试"""

    def test_multiple_tables_lazy(self, temp_dir: Path) -> None:
        """多表都能独立懒加载"""
        db_path = temp_dir / 'lazy_multi.db'
        db = Storage(
            file_path=str(db_path),
            engine='binary',
            backend_options=BinaryBackendOptions()
        )
        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        class Product(Base):
            __tablename__ = 'products'
            id = Column(int, primary_key=True)
            title = Column(str)

        session = Session(db)
        session.execute(insert(User).values(name='Alice'))
        session.execute(insert(User).values(name='Bob'))
        session.execute(insert(Product).values(title='Widget'))
        session.commit()
        db.flush()
        db.close()

        # 懒加载
        backend = BinaryBackend(str(db_path), BinaryBackendOptions(lazy_load=True))
        tables = backend.load()

        assert 'users' in tables
        assert 'products' in tables

        # 两个表都应该是懒加载状态
        assert tables['users']._lazy_loaded is True
        assert tables['products']._lazy_loaded is True

        # 按需读取
        assert tables['users'].get(1)['name'] == 'Alice'
        assert tables['products'].get(1)['title'] == 'Widget'
