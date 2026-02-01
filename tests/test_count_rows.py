"""
测试 Storage.count_rows() 方法

验证获取表行数的功能在各种模式下正常工作
"""

from pathlib import Path
from typing import Type

import pytest

from pytuck import Storage, Column, PureBaseModel, declarative_base, TableNotFoundError
from pytuck.common.options import SqliteBackendOptions


class TestCountRows:
    """测试 count_rows 方法"""

    def test_count_rows_empty_table(self, tmp_path: Path) -> None:
        """空表返回 0"""
        db_file = tmp_path / 'test_empty.sqlite'
        db = Storage(file_path=str(db_file), engine='sqlite')
        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        # 空表应返回 0
        count = db.count_rows('users')
        assert count == 0

        db.close()

    def test_count_rows_with_data(self, tmp_path: Path) -> None:
        """有数据的表返回正确行数"""
        db_file = tmp_path / 'test_with_data.sqlite'
        db = Storage(file_path=str(db_file), engine='sqlite')
        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        # 插入 5 条记录
        for i in range(5):
            db.insert('users', {'name': f'User {i}'})

        # 应返回 5
        count = db.count_rows('users')
        assert count == 5

        db.close()

    def test_count_rows_native_sql_mode(self, tmp_path: Path) -> None:
        """Native SQL 模式下正确返回行数"""
        db_file = tmp_path / 'test_native.sqlite'
        # 默认使用 native SQL 模式
        db = Storage(file_path=str(db_file), engine='sqlite')
        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        # 验证是 native SQL 模式
        assert db.is_native_sql_mode is True

        # 插入 3 条记录
        db.insert('users', {'name': 'Alice'})
        db.insert('users', {'name': 'Bob'})
        db.insert('users', {'name': 'Charlie'})

        count = db.count_rows('users')
        assert count == 3

        db.close()

    def test_count_rows_memory_mode(self, tmp_path: Path) -> None:
        """内存模式下正确返回行数"""
        db_file = tmp_path / 'test_memory.sqlite'
        options = SqliteBackendOptions(use_native_sql=False)
        db = Storage(file_path=str(db_file), engine='sqlite', backend_options=options)
        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        # 验证是内存模式
        assert db.is_native_sql_mode is False

        # 插入 3 条记录
        db.insert('users', {'name': 'Alice'})
        db.insert('users', {'name': 'Bob'})
        db.insert('users', {'name': 'Charlie'})

        count = db.count_rows('users')
        assert count == 3

        db.close()

    def test_count_rows_after_insert(self, tmp_path: Path) -> None:
        """插入后行数增加"""
        db_file = tmp_path / 'test_insert.sqlite'
        db = Storage(file_path=str(db_file), engine='sqlite')
        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        # 初始为 0
        assert db.count_rows('users') == 0

        # 插入一条
        db.insert('users', {'name': 'Alice'})
        assert db.count_rows('users') == 1

        # 再插入一条
        db.insert('users', {'name': 'Bob'})
        assert db.count_rows('users') == 2

        db.close()

    def test_count_rows_after_delete(self, tmp_path: Path) -> None:
        """删除后行数减少"""
        db_file = tmp_path / 'test_delete.sqlite'
        db = Storage(file_path=str(db_file), engine='sqlite')
        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        # 插入 3 条记录
        pk1 = db.insert('users', {'name': 'Alice'})
        db.insert('users', {'name': 'Bob'})
        db.insert('users', {'name': 'Charlie'})
        assert db.count_rows('users') == 3

        # 删除一条
        db.delete('users', pk1)
        assert db.count_rows('users') == 2

        db.close()

    def test_count_rows_table_not_found(self, tmp_path: Path) -> None:
        """表不存在时抛出 TableNotFoundError"""
        db_file = tmp_path / 'test_not_found.sqlite'
        db = Storage(file_path=str(db_file), engine='sqlite')

        with pytest.raises(TableNotFoundError):
            db.count_rows('nonexistent_table')

        db.close()

    def test_count_rows_multiple_tables(self, tmp_path: Path) -> None:
        """多表场景下各表计数独立"""
        db_file = tmp_path / 'test_multi.sqlite'
        db = Storage(file_path=str(db_file), engine='sqlite')
        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        class Product(Base):
            __tablename__ = 'products'
            id = Column(int, primary_key=True)
            name = Column(str)

        # 插入不同数量的记录
        for i in range(3):
            db.insert('users', {'name': f'User {i}'})

        for i in range(5):
            db.insert('products', {'name': f'Product {i}'})

        # 验证各表计数独立
        assert db.count_rows('users') == 3
        assert db.count_rows('products') == 5

        db.close()
