"""
Binary 引擎加密测试

覆盖 pytuck/backends/backend_binary.py 的三级加密功能：
- low (XOR 混淆)
- medium (LCG 流密码)
- high (ChaCha20)
- 错误密码检测
- 无密码访问加密文件
- 加密后数据完整性
- 多表加密
"""

from pathlib import Path
from typing import Type

import pytest

from pytuck import Storage, declarative_base, Session, Column
from pytuck import PureBaseModel, insert, select
from pytuck.common.exceptions import EncryptionError
from pytuck.common.options import BinaryBackendOptions


# ---------- 各加密等级测试 ----------


class TestBinaryEncryptionLow:
    """low 等级（XOR 混淆）加密测试"""

    def test_save_and_load_low(self, temp_dir: Path) -> None:
        """low 等级加密写入读取"""
        db_path = temp_dir / 'enc_low.db'
        db = Storage(
            file_path=str(db_path),
            engine='binary',
            backend_options=BinaryBackendOptions(
                encryption='low', password='secret123'
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

        # 重新打开并读取
        db2 = Storage(
            file_path=str(db_path),
            engine='binary',
            backend_options=BinaryBackendOptions(
                encryption='low', password='secret123'
            )
        )
        table = db2.get_table('users')
        assert len(table.data) == 2
        names = {r['name'] for r in table.data.values()}
        assert names == {'Alice', 'Bob'}
        db2.close()

    def test_wrong_password_low(self, temp_dir: Path) -> None:
        """low 等级错误密码报错"""
        db_path = temp_dir / 'enc_low_wrong.db'
        db = Storage(
            file_path=str(db_path),
            engine='binary',
            backend_options=BinaryBackendOptions(
                encryption='low', password='correct'
            )
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

        # 用错误密码打开
        with pytest.raises(EncryptionError, match="密码错误"):
            Storage(
                file_path=str(db_path),
                engine='binary',
                backend_options=BinaryBackendOptions(
                    encryption='low', password='wrong'
                )
            )


class TestBinaryEncryptionMedium:
    """medium 等级（LCG 流密码）加密测试"""

    def test_save_and_load_medium(self, temp_dir: Path) -> None:
        """medium 等级加密写入读取"""
        db_path = temp_dir / 'enc_medium.db'
        db = Storage(
            file_path=str(db_path),
            engine='binary',
            backend_options=BinaryBackendOptions(
                encryption='medium', password='mypass'
            )
        )
        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)
            age = Column(int, nullable=True)

        session = Session(db)
        session.execute(insert(User).values(name='Charlie', age=30))
        session.commit()
        db.flush()
        db.close()

        db2 = Storage(
            file_path=str(db_path),
            engine='binary',
            backend_options=BinaryBackendOptions(
                encryption='medium', password='mypass'
            )
        )
        table = db2.get_table('users')
        assert len(table.data) == 1
        record = list(table.data.values())[0]
        assert record['name'] == 'Charlie'
        assert record['age'] == 30
        db2.close()

    def test_wrong_password_medium(self, temp_dir: Path) -> None:
        """medium 等级错误密码报错"""
        db_path = temp_dir / 'enc_medium_wrong.db'
        db = Storage(
            file_path=str(db_path),
            engine='binary',
            backend_options=BinaryBackendOptions(
                encryption='medium', password='correct'
            )
        )
        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        session = Session(db)
        session.execute(insert(User).values(name='Test'))
        session.commit()
        db.flush()
        db.close()

        with pytest.raises(EncryptionError, match="密码错误"):
            Storage(
                file_path=str(db_path),
                engine='binary',
                backend_options=BinaryBackendOptions(
                    encryption='medium', password='wrong'
                )
            )


class TestBinaryEncryptionHigh:
    """high 等级（ChaCha20）加密测试"""

    def test_save_and_load_high(self, temp_dir: Path) -> None:
        """high 等级加密写入读取"""
        db_path = temp_dir / 'enc_high.db'
        db = Storage(
            file_path=str(db_path),
            engine='binary',
            backend_options=BinaryBackendOptions(
                encryption='high', password='strongpass!@#'
            )
        )
        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        session = Session(db)
        session.execute(insert(User).values(name='Dave'))
        session.execute(insert(User).values(name='Eve'))
        session.execute(insert(User).values(name='Frank'))
        session.commit()
        db.flush()
        db.close()

        db2 = Storage(
            file_path=str(db_path),
            engine='binary',
            backend_options=BinaryBackendOptions(
                encryption='high', password='strongpass!@#'
            )
        )
        table = db2.get_table('users')
        assert len(table.data) == 3
        names = {r['name'] for r in table.data.values()}
        assert names == {'Dave', 'Eve', 'Frank'}
        db2.close()

    def test_wrong_password_high(self, temp_dir: Path) -> None:
        """high 等级错误密码报错"""
        db_path = temp_dir / 'enc_high_wrong.db'
        db = Storage(
            file_path=str(db_path),
            engine='binary',
            backend_options=BinaryBackendOptions(
                encryption='high', password='correct'
            )
        )
        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        session = Session(db)
        session.execute(insert(User).values(name='Test'))
        session.commit()
        db.flush()
        db.close()

        with pytest.raises(EncryptionError, match="密码错误"):
            Storage(
                file_path=str(db_path),
                engine='binary',
                backend_options=BinaryBackendOptions(
                    encryption='high', password='wrong'
                )
            )


# ---------- 通用加密测试 ----------


class TestBinaryEncryptionCommon:
    """通用加密行为测试"""

    def test_load_without_password_raises(self, temp_dir: Path) -> None:
        """加密文件无密码时报错"""
        db_path = temp_dir / 'enc_nopass.db'
        db = Storage(
            file_path=str(db_path),
            engine='binary',
            backend_options=BinaryBackendOptions(
                encryption='low', password='secret'
            )
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

        # 不提供密码打开加密文件
        with pytest.raises(EncryptionError, match="密码"):
            Storage(
                file_path=str(db_path),
                engine='binary',
                backend_options=BinaryBackendOptions()
            )

    def test_unencrypted_no_password_ok(self, temp_dir: Path) -> None:
        """非加密文件无密码正常"""
        db_path = temp_dir / 'no_enc.db'
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

        # 不提供密码正常打开
        db2 = Storage(
            file_path=str(db_path),
            engine='binary',
            backend_options=BinaryBackendOptions()
        )
        table = db2.get_table('users')
        assert len(table.data) == 1
        db2.close()

    def test_encrypted_data_integrity(self, temp_dir: Path) -> None:
        """加密后数据完整性（多类型字段）"""
        db_path = temp_dir / 'enc_integrity.db'
        db = Storage(
            file_path=str(db_path),
            engine='binary',
            backend_options=BinaryBackendOptions(
                encryption='high', password='test'
            )
        )
        Base: Type[PureBaseModel] = declarative_base(db)

        class Record(Base):
            __tablename__ = 'records'
            id = Column(int, primary_key=True)
            text = Column(str)
            number = Column(int, nullable=True)
            decimal = Column(float, nullable=True)
            flag = Column(bool, nullable=True)

        session = Session(db)
        session.execute(insert(Record).values(
            text='Hello World', number=42, decimal=3.14, flag=True
        ))
        session.execute(insert(Record).values(
            text='中文测试', number=-100, decimal=0.0, flag=False
        ))
        session.execute(insert(Record).values(
            text='', number=None, decimal=None, flag=None
        ))
        session.commit()
        db.flush()
        db.close()

        # 重新加载并验证所有字段
        db2 = Storage(
            file_path=str(db_path),
            engine='binary',
            backend_options=BinaryBackendOptions(
                encryption='high', password='test'
            )
        )
        table = db2.get_table('records')
        assert len(table.data) == 3

        r1 = table.data[1]
        assert r1['text'] == 'Hello World'
        assert r1['number'] == 42
        assert abs(r1['decimal'] - 3.14) < 0.001
        assert r1['flag'] is True

        r2 = table.data[2]
        assert r2['text'] == '中文测试'
        assert r2['number'] == -100
        assert r2['decimal'] == 0.0
        assert r2['flag'] is False

        r3 = table.data[3]
        assert r3['text'] == ''
        assert r3['number'] is None
        assert r3['decimal'] is None
        assert r3['flag'] is None

        db2.close()

    def test_encrypted_multiple_tables(self, temp_dir: Path) -> None:
        """多表加密"""
        db_path = temp_dir / 'enc_multi.db'
        db = Storage(
            file_path=str(db_path),
            engine='binary',
            backend_options=BinaryBackendOptions(
                encryption='medium', password='multi'
            )
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
            price = Column(float, nullable=True)

        session = Session(db)
        session.execute(insert(User).values(name='Alice'))
        session.execute(insert(User).values(name='Bob'))
        session.execute(insert(Product).values(title='Widget', price=9.99))
        session.execute(insert(Product).values(title='Gadget', price=19.99))
        session.execute(insert(Product).values(title='Free', price=0.0))
        session.commit()
        db.flush()
        db.close()

        # 重新打开验证
        db2 = Storage(
            file_path=str(db_path),
            engine='binary',
            backend_options=BinaryBackendOptions(
                encryption='medium', password='multi'
            )
        )
        users = db2.get_table('users')
        products = db2.get_table('products')

        assert len(users.data) == 2
        assert len(products.data) == 3

        user_names = {r['name'] for r in users.data.values()}
        assert user_names == {'Alice', 'Bob'}

        product_titles = {r['title'] for r in products.data.values()}
        assert product_titles == {'Widget', 'Gadget', 'Free'}

        db2.close()

    def test_encrypted_with_index(self, temp_dir: Path) -> None:
        """加密文件的索引也能正确恢复"""
        db_path = temp_dir / 'enc_index.db'
        db = Storage(
            file_path=str(db_path),
            engine='binary',
            backend_options=BinaryBackendOptions(
                encryption='low', password='idx'
            )
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

        db2 = Storage(
            file_path=str(db_path),
            engine='binary',
            backend_options=BinaryBackendOptions(
                encryption='low', password='idx'
            )
        )
        table = db2.get_table('users')
        assert len(table.data) == 3

        # 索引应该被恢复
        assert 'name' in table.indexes
        alice_pks = table.indexes['name'].lookup('Alice')
        assert len(alice_pks) == 2

        db2.close()

    def test_encryption_no_password_save_raises(self, temp_dir: Path) -> None:
        """指定加密但不提供密码时保存报错"""
        db_path = temp_dir / 'enc_nopass_save.db'

        with pytest.raises(EncryptionError, match="密码"):
            db = Storage(
                file_path=str(db_path),
                engine='binary',
                backend_options=BinaryBackendOptions(
                    encryption='high', password=None
                )
            )
            Base: Type[PureBaseModel] = declarative_base(db)

            class User(Base):
                __tablename__ = 'users'
                id = Column(int, primary_key=True)
                name = Column(str)

            session = Session(db)
            session.execute(insert(User).values(name='Test'))
            session.commit()
            db.flush()
