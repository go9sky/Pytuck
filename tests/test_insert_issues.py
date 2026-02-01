"""
测试 insert/delete 相关问题修复

问题来源: pytuck-view 开发反馈
- 问题 1：主键重复应抛出 DuplicateKeyError
- 问题 2：insert 返回值应为用户提供的主键
- 问题 3：insert 后立即 delete 应成功
"""

from pathlib import Path
from typing import Type

import pytest

from pytuck import Storage, Column, PureBaseModel, declarative_base, DuplicateKeyError
from pytuck.common.options import SqliteBackendOptions


class TestDuplicateKeyError:
    """测试主键冲突异常"""

    def test_duplicate_key_memory_mode(self, tmp_path: Path) -> None:
        """内存模式下重复主键抛出 DuplicateKeyError"""
        db_file = tmp_path / 'test_dup_memory.sqlite'
        options = SqliteBackendOptions(use_native_sql=False)
        db = Storage(file_path=str(db_file), engine='sqlite', backend_options=options)
        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        # 插入第一条记录
        pk1 = db.insert('users', {'id': 1, 'name': 'Alice'})
        assert pk1 == 1

        # 插入相同主键应抛出异常
        with pytest.raises(DuplicateKeyError) as exc_info:
            db.insert('users', {'id': 1, 'name': 'Bob'})

        assert exc_info.value.table_name == 'users'
        assert exc_info.value.pk == 1

        db.close()

    def test_duplicate_key_native_sql_mode(self, tmp_path: Path) -> None:
        """Native SQL 模式下重复主键抛出 DuplicateKeyError"""
        db_file = tmp_path / 'test_dup_native.sqlite'
        # 默认使用 native SQL 模式
        db = Storage(file_path=str(db_file), engine='sqlite')
        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        # 验证确实是 native SQL 模式
        assert db.is_native_sql_mode is True

        # 插入第一条记录
        pk1 = db.insert('users', {'id': 1, 'name': 'Alice'})
        assert pk1 == 1

        # 插入相同主键应抛出 DuplicateKeyError（而非 sqlite3.IntegrityError）
        with pytest.raises(DuplicateKeyError) as exc_info:
            db.insert('users', {'id': 1, 'name': 'Bob'})

        assert exc_info.value.table_name == 'users'
        assert exc_info.value.pk == 1

        db.close()

    def test_duplicate_key_string_pk(self, tmp_path: Path) -> None:
        """字符串主键冲突测试"""
        db_file = tmp_path / 'test_dup_string_pk.sqlite'
        db = Storage(file_path=str(db_file), engine='sqlite')
        Base: Type[PureBaseModel] = declarative_base(db)

        class Product(Base):
            __tablename__ = 'products'
            sku = Column(str, primary_key=True)
            name = Column(str)

        # 插入第一条记录
        pk1 = db.insert('products', {'sku': 'ABC-123', 'name': 'Widget'})
        assert pk1 == 'ABC-123'

        # 插入相同主键应抛出异常
        with pytest.raises(DuplicateKeyError) as exc_info:
            db.insert('products', {'sku': 'ABC-123', 'name': 'Another Widget'})

        assert exc_info.value.table_name == 'products'
        assert exc_info.value.pk == 'ABC-123'

        db.close()


class TestInsertReturnValue:
    """测试 insert 返回值"""

    def test_insert_returns_user_string_pk(self, tmp_path: Path) -> None:
        """插入用户指定的字符串主键，返回该字符串"""
        db_file = tmp_path / 'test_return_string_pk.sqlite'
        db = Storage(file_path=str(db_file), engine='sqlite')
        Base: Type[PureBaseModel] = declarative_base(db)

        class Product(Base):
            __tablename__ = 'products'
            sku = Column(str, primary_key=True)
            name = Column(str)

        # 插入记录
        pk = db.insert('products', {'sku': 'XYZ-789', 'name': 'Gadget'})

        # 返回值应该是用户提供的字符串主键
        assert pk == 'XYZ-789'
        assert isinstance(pk, str)

        db.close()

    def test_insert_returns_user_int_pk(self, tmp_path: Path) -> None:
        """插入用户指定的 int 主键，返回该 int"""
        db_file = tmp_path / 'test_return_int_pk.sqlite'
        db = Storage(file_path=str(db_file), engine='sqlite')
        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        # 插入指定主键的记录
        pk = db.insert('users', {'id': 100, 'name': 'Alice'})

        # 返回值应该是用户提供的主键值
        assert pk == 100

        db.close()

    def test_insert_returns_auto_increment_pk(self, tmp_path: Path) -> None:
        """自增主键返回 lastrowid"""
        db_file = tmp_path / 'test_return_auto_pk.sqlite'
        db = Storage(file_path=str(db_file), engine='sqlite')
        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        # 不指定主键，让数据库自动生成
        pk1 = db.insert('users', {'name': 'Alice'})
        pk2 = db.insert('users', {'name': 'Bob'})

        # 返回值应该是自增的主键值
        assert pk1 == 1
        assert pk2 == 2

        db.close()


class TestInsertThenDelete:
    """测试 insert + delete 联动"""

    def test_insert_then_delete_string_pk(self, tmp_path: Path) -> None:
        """插入字符串主键后立即删除"""
        db_file = tmp_path / 'test_insert_delete_string.sqlite'
        db = Storage(file_path=str(db_file), engine='sqlite')
        Base: Type[PureBaseModel] = declarative_base(db)

        class Product(Base):
            __tablename__ = 'products'
            sku = Column(str, primary_key=True)
            name = Column(str)

        # 插入记录
        pk = db.insert('products', {'sku': 'DEL-001', 'name': 'To Delete'})
        assert pk == 'DEL-001'

        # 验证记录存在
        record = db.select('products', pk)
        assert record['sku'] == 'DEL-001'
        assert record['name'] == 'To Delete'

        # 使用返回的主键值删除
        db.delete('products', pk)

        # 验证记录已被删除
        from pytuck.common.exceptions import RecordNotFoundError
        with pytest.raises(RecordNotFoundError):
            db.select('products', pk)

        db.close()

    def test_insert_then_delete_auto_pk(self, tmp_path: Path) -> None:
        """插入自增主键后立即删除"""
        db_file = tmp_path / 'test_insert_delete_auto.sqlite'
        db = Storage(file_path=str(db_file), engine='sqlite')
        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        # 插入记录（自增主键）
        pk = db.insert('users', {'name': 'To Delete'})
        assert pk == 1

        # 验证记录存在
        record = db.select('users', pk)
        assert record['name'] == 'To Delete'

        # 使用返回的主键值删除
        db.delete('users', pk)

        # 验证记录已被删除
        from pytuck.common.exceptions import RecordNotFoundError
        with pytest.raises(RecordNotFoundError):
            db.select('users', pk)

        db.close()

    def test_insert_then_delete_user_int_pk(self, tmp_path: Path) -> None:
        """插入用户指定的 int 主键后立即删除"""
        db_file = tmp_path / 'test_insert_delete_user_int.sqlite'
        db = Storage(file_path=str(db_file), engine='sqlite')
        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        # 插入记录（用户指定的 int 主键）
        pk = db.insert('users', {'id': 999, 'name': 'To Delete'})
        assert pk == 999

        # 验证记录存在
        record = db.select('users', pk)
        assert record['id'] == 999
        assert record['name'] == 'To Delete'

        # 使用返回的主键值删除
        db.delete('users', pk)

        # 验证记录已被删除
        from pytuck.common.exceptions import RecordNotFoundError
        with pytest.raises(RecordNotFoundError):
            db.select('users', pk)

        db.close()
