"""
CSV 后端 ZIP 加密功能测试

测试方法：
- 等价类划分：加密/非加密、正确密码/错误密码
- 场景设计：完整的加密保存和加载流程
- 边界测试：空表、大数据量、多表场景

覆盖范围：
- 带密码保存和加载
- 错误密码处理
- 加密 ZIP 无密码时的错误处理
- probe() 检测加密状态
- get_metadata() 处理加密情况
- 向后兼容：无密码时行为不变
"""

import pytest
import zipfile
from pathlib import Path
from typing import Type

from pytuck import (
    Storage, Session, Column, declarative_base,
    PureBaseModel, CRUDBaseModel, select, insert,
    EncryptionError, SerializationError
)
from pytuck.common.options import CsvBackendOptions
from pytuck.backends.backend_csv import CSVBackend


class TestCsvEncryptionBasic:
    """CSV 加密基本功能测试"""

    def test_save_and_load_with_password(self, tmp_path: Path) -> None:
        """带密码保存和加载"""
        db_path = tmp_path / "encrypted.zip"
        password = "test_password_123"

        # 创建带密码的存储
        options = CsvBackendOptions(password=password)
        db = Storage(file_path=str(db_path), engine='csv', backend_options=options)

        Base: Type[CRUDBaseModel] = declarative_base(db, crud=True)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)
            age = Column(int, nullable=True)

        # 插入数据
        User.create(id=1, name='Alice', age=25)
        User.create(id=2, name='Bob', age=30)
        db.flush()
        db.close()

        # 验证文件已加密
        with zipfile.ZipFile(str(db_path), 'r') as zf:
            encrypted = any((info.flag_bits & 0x1) != 0 for info in zf.infolist())
            assert encrypted, "ZIP file should be encrypted"

        # 使用相同密码读取
        options2 = CsvBackendOptions(password=password)
        db2 = Storage(file_path=str(db_path), engine='csv', backend_options=options2)

        Base2: Type[CRUDBaseModel] = declarative_base(db2, crud=True)

        class User2(Base2):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)
            age = Column(int, nullable=True)

        # 验证数据
        users = User2.all()
        assert len(users) == 2
        assert users[0].name == 'Alice'
        assert users[1].name == 'Bob'

        db2.close()

    def test_load_with_wrong_password(self, tmp_path: Path) -> None:
        """错误密码应抛出 EncryptionError"""
        db_path = tmp_path / "encrypted.zip"
        correct_password = "correct_password"
        wrong_password = "wrong_password"

        # 创建加密存储
        options = CsvBackendOptions(password=correct_password)
        db = Storage(file_path=str(db_path), engine='csv', backend_options=options)

        Base: Type[CRUDBaseModel] = declarative_base(db, crud=True)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        User.create(id=1, name='Alice')
        db.flush()
        db.close()

        # 使用错误密码读取 - Storage 构造时会触发 load()，所以异常在这里抛出
        options2 = CsvBackendOptions(password=wrong_password)
        with pytest.raises((EncryptionError, SerializationError)):
            Storage(file_path=str(db_path), engine='csv', backend_options=options2)

    def test_load_encrypted_without_password(self, tmp_path: Path) -> None:
        """加密 ZIP 无密码时应抛出 EncryptionError"""
        db_path = tmp_path / "encrypted.zip"
        password = "test_password"

        # 创建加密存储
        options = CsvBackendOptions(password=password)
        db = Storage(file_path=str(db_path), engine='csv', backend_options=options)

        Base: Type[CRUDBaseModel] = declarative_base(db, crud=True)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        User.create(id=1, name='Alice')
        db.flush()
        db.close()

        # 不提供密码读取 - Storage 构造时会触发 load()，所以异常在这里抛出
        options2 = CsvBackendOptions()  # 无密码
        with pytest.raises(EncryptionError) as exc_info:
            Storage(file_path=str(db_path), engine='csv', backend_options=options2)

        assert "encrypted" in str(exc_info.value).lower()


class TestCsvEncryptionProbe:
    """CSV 加密 probe() 功能测试"""

    def test_probe_encrypted_file(self, tmp_path: Path) -> None:
        """probe() 应检测到加密状态"""
        db_path = tmp_path / "encrypted.zip"
        password = "test_password"

        # 创建加密存储
        options = CsvBackendOptions(password=password)
        db = Storage(file_path=str(db_path), engine='csv', backend_options=options)

        Base: Type[CRUDBaseModel] = declarative_base(db, crud=True)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        User.create(id=1, name='Alice')
        db.flush()
        db.close()

        # probe 检测
        is_csv, info = CSVBackend.probe(str(db_path))
        assert is_csv is True
        assert info is not None
        assert info.get('encrypted') is True
        assert info.get('requires_password') is True
        assert info.get('engine') == 'csv'

    def test_probe_unencrypted_file(self, tmp_path: Path) -> None:
        """probe() 对未加密文件应返回 encrypted=False 或不包含该字段"""
        db_path = tmp_path / "unencrypted.zip"

        # 创建未加密存储
        options = CsvBackendOptions()
        db = Storage(file_path=str(db_path), engine='csv', backend_options=options)

        Base: Type[CRUDBaseModel] = declarative_base(db, crud=True)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        User.create(id=1, name='Alice')
        db.flush()
        db.close()

        # probe 检测
        is_csv, info = CSVBackend.probe(str(db_path))
        assert is_csv is True
        assert info is not None
        assert info.get('encrypted') is not True


class TestCsvEncryptionMetadata:
    """CSV 加密 get_metadata() 功能测试"""

    def test_get_metadata_encrypted_with_password(self, tmp_path: Path) -> None:
        """加密文件使用正确密码获取 metadata"""
        db_path = tmp_path / "encrypted.zip"
        password = "test_password"

        # 创建加密存储
        options = CsvBackendOptions(password=password)
        db = Storage(file_path=str(db_path), engine='csv', backend_options=options)

        Base: Type[CRUDBaseModel] = declarative_base(db, crud=True)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        User.create(id=1, name='Alice')
        db.flush()
        db.close()

        # 使用密码获取 metadata
        backend = CSVBackend(str(db_path), CsvBackendOptions(password=password))
        metadata = backend.get_metadata()

        assert metadata.get('engine') == 'csv'
        assert metadata.get('encrypted') is True
        assert 'tables' in metadata

    def test_get_metadata_encrypted_without_password(self, tmp_path: Path) -> None:
        """加密文件无密码时 get_metadata 返回有限信息"""
        db_path = tmp_path / "encrypted.zip"
        password = "test_password"

        # 创建加密存储
        options = CsvBackendOptions(password=password)
        db = Storage(file_path=str(db_path), engine='csv', backend_options=options)

        Base: Type[CRUDBaseModel] = declarative_base(db, crud=True)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        User.create(id=1, name='Alice')
        db.flush()
        db.close()

        # 无密码获取 metadata
        backend = CSVBackend(str(db_path), CsvBackendOptions())
        metadata = backend.get_metadata()

        assert metadata.get('engine') == 'csv'
        assert metadata.get('encrypted') is True
        assert metadata.get('requires_password') is True


class TestCsvEncryptionBackwardCompatibility:
    """CSV 加密向后兼容性测试"""

    def test_no_password_default_behavior(self, tmp_path: Path) -> None:
        """无密码时行为与原来一致"""
        db_path = tmp_path / "unencrypted.zip"

        # 创建未加密存储
        options = CsvBackendOptions()
        db = Storage(file_path=str(db_path), engine='csv', backend_options=options)

        Base: Type[CRUDBaseModel] = declarative_base(db, crud=True)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)
            email = Column(str, nullable=True)

        User.create(id=1, name='Alice', email='alice@example.com')
        User.create(id=2, name='Bob', email='bob@example.com')
        db.flush()
        db.close()

        # 验证文件未加密
        with zipfile.ZipFile(str(db_path), 'r') as zf:
            encrypted = any((info.flag_bits & 0x1) != 0 for info in zf.infolist())
            assert not encrypted, "ZIP file should not be encrypted"

        # 读取未加密文件
        db2 = Storage(file_path=str(db_path), engine='csv', backend_options=CsvBackendOptions())

        Base2: Type[CRUDBaseModel] = declarative_base(db2, crud=True)

        class User2(Base2):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)
            email = Column(str, nullable=True)

        users = User2.all()
        assert len(users) == 2
        db2.close()


class TestCsvEncryptionMultiTable:
    """CSV 加密多表测试"""

    def test_multiple_tables_encrypted(self, tmp_path: Path) -> None:
        """多表加密存储"""
        db_path = tmp_path / "multi_table.zip"
        password = "multi_table_password"

        # 创建加密存储
        options = CsvBackendOptions(password=password)
        db = Storage(file_path=str(db_path), engine='csv', backend_options=options)

        Base: Type[CRUDBaseModel] = declarative_base(db, crud=True)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        class Product(Base):
            __tablename__ = 'products'
            id = Column(int, primary_key=True)
            title = Column(str)
            price = Column(float)

        class Order(Base):
            __tablename__ = 'orders'
            id = Column(int, primary_key=True)
            user_id = Column(int)
            product_id = Column(int)

        # 插入数据
        User.create(id=1, name='Alice')
        User.create(id=2, name='Bob')
        Product.create(id=1, title='Book', price=19.99)
        Product.create(id=2, title='Pen', price=2.99)
        Order.create(id=1, user_id=1, product_id=1)
        Order.create(id=2, user_id=2, product_id=2)

        db.flush()
        db.close()

        # 读取
        db2 = Storage(file_path=str(db_path), engine='csv', backend_options=CsvBackendOptions(password=password))

        Base2: Type[CRUDBaseModel] = declarative_base(db2, crud=True)

        class User2(Base2):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        class Product2(Base2):
            __tablename__ = 'products'
            id = Column(int, primary_key=True)
            title = Column(str)
            price = Column(float)

        class Order2(Base2):
            __tablename__ = 'orders'
            id = Column(int, primary_key=True)
            user_id = Column(int)
            product_id = Column(int)

        assert len(User2.all()) == 2
        assert len(Product2.all()) == 2
        assert len(Order2.all()) == 2

        db2.close()


class TestCsvEncryptionEdgeCases:
    """CSV 加密边界情况测试"""

    def test_empty_password_is_no_encryption(self, tmp_path: Path) -> None:
        """空字符串密码等同于无密码"""
        db_path = tmp_path / "empty_password.zip"

        # 空字符串密码
        options = CsvBackendOptions(password="")
        db = Storage(file_path=str(db_path), engine='csv', backend_options=options)

        Base: Type[CRUDBaseModel] = declarative_base(db, crud=True)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        User.create(id=1, name='Alice')
        db.flush()
        db.close()

        # 验证文件未加密（空字符串在布尔上下文中为 False）
        with zipfile.ZipFile(str(db_path), 'r') as zf:
            encrypted = any((info.flag_bits & 0x1) != 0 for info in zf.infolist())
            assert not encrypted

    def test_unicode_password(self, tmp_path: Path) -> None:
        """Unicode 密码支持"""
        db_path = tmp_path / "unicode_password.zip"
        password = "密码123中文テスト"

        # 创建加密存储
        options = CsvBackendOptions(password=password)
        db = Storage(file_path=str(db_path), engine='csv', backend_options=options)

        Base: Type[CRUDBaseModel] = declarative_base(db, crud=True)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        User.create(id=1, name='测试用户')
        db.flush()
        db.close()

        # 使用相同密码读取
        db2 = Storage(file_path=str(db_path), engine='csv', backend_options=CsvBackendOptions(password=password))

        Base2: Type[CRUDBaseModel] = declarative_base(db2, crud=True)

        class User2(Base2):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        users = User2.all()
        assert len(users) == 1
        assert users[0].name == '测试用户'

        db2.close()

    def test_large_data_encrypted(self, tmp_path: Path) -> None:
        """大数据量加密"""
        db_path = tmp_path / "large_data.zip"
        password = "large_data_password"

        options = CsvBackendOptions(password=password)
        db = Storage(file_path=str(db_path), engine='csv', backend_options=options)

        Base: Type[CRUDBaseModel] = declarative_base(db, crud=True)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)
            description = Column(str, nullable=True)

        # 插入大量数据
        for i in range(100):
            User.create(
                id=i + 1,
                name=f'User_{i}',
                description=f'Description for user {i} ' * 10  # 较长的描述
            )

        db.flush()
        db.close()

        # 读取验证
        db2 = Storage(file_path=str(db_path), engine='csv', backend_options=CsvBackendOptions(password=password))

        Base2: Type[CRUDBaseModel] = declarative_base(db2, crud=True)

        class User2(Base2):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)
            description = Column(str, nullable=True)

        users = User2.all()
        assert len(users) == 100
        assert users[0].name == 'User_0'
        assert users[99].name == 'User_99'

        db2.close()
