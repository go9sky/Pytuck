"""
懒加载后端迁移测试

测试 migrate_engine() 在后端使用懒加载模式时的数据迁移功能：
- SQLite 原生模式：load() 只加载 schema，data 为空
- Binary 懒加载模式：load() 只加载 schema 和索引，data 为空
- migrate_engine() 应能正确填充数据并迁移
"""

from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Type

import pytest

from pytuck import Storage, Session, Column, PureBaseModel, declarative_base
from pytuck import insert
from pytuck.tools.migrate import migrate_engine
from pytuck.common.options import SqliteBackendOptions, BinaryBackendOptions


class TestMigrateSqliteNativeToJson:
    """测试 SQLite 原生模式迁移到 JSON"""

    def test_migrate_sqlite_native_to_json(self, tmp_path: Path) -> None:
        """SQLite 原生模式迁移到 JSON，数据应正确迁移"""
        sqlite_file = tmp_path / 'source.sqlite'
        json_file = tmp_path / 'target.json'

        # 1. 使用兼容模式创建数据
        opts = SqliteBackendOptions(use_native_sql=False)
        db = Storage(file_path=str(sqlite_file), engine='sqlite', backend_options=opts)
        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)
            age = Column(int)

        session = Session(db)
        session.execute(insert(User).values(name='Alice', age=25))
        session.execute(insert(User).values(name='Bob', age=30))
        session.commit()
        db.flush()
        db.close()

        # 2. 使用原生模式重新打开，验证 table.data 为空
        opts_native = SqliteBackendOptions(use_native_sql=True)
        db_native = Storage(file_path=str(sqlite_file), engine='sqlite', backend_options=opts_native)
        assert db_native.tables['users'].data == {}, "原生模式下 table.data 应该为空"
        db_native.close()

        # 3. 执行迁移（使用默认选项，即原生模式）
        result = migrate_engine(
            source_path=str(sqlite_file),
            source_engine='sqlite',
            target_path=str(json_file),
            target_engine='json'
        )

        # 4. 验证迁移结果
        assert result['tables'] == 1
        assert result['records'] == 2

        # 5. 验证 JSON 数据
        db_json = Storage(file_path=str(json_file), engine='json')
        assert len(db_json.tables['users'].data) == 2

        users_data = list(db_json.tables['users'].data.values())
        names = [u['name'] for u in users_data]
        assert 'Alice' in names
        assert 'Bob' in names

        db_json.close()


class TestMigrateChainWithNativeSqlite:
    """测试完整迁移链条"""

    def test_migrate_chain(self, tmp_path: Path) -> None:
        """完整迁移链条：SQLite(native) -> JSON -> CSV -> Binary -> SQLite"""
        sqlite_file = tmp_path / 'source.sqlite'
        json_file = tmp_path / 'target.json'
        csv_file = tmp_path / 'target.zip'
        binary_file = tmp_path / 'target.db'
        sqlite_target = tmp_path / 'target.sqlite'

        # 1. 使用兼容模式创建数据
        opts = SqliteBackendOptions(use_native_sql=False)
        db = Storage(file_path=str(sqlite_file), engine='sqlite', backend_options=opts)
        Base: Type[PureBaseModel] = declarative_base(db)

        class Person(Base):
            __tablename__ = 'people'
            id = Column(int, primary_key=True)
            name = Column(str)
            score = Column(float)

        session = Session(db)
        session.execute(insert(Person).values(name='Alice', score=95.5))
        session.execute(insert(Person).values(name='Bob', score=88.0))
        session.execute(insert(Person).values(name='Charlie', score=92.3))
        session.commit()
        db.flush()
        db.close()

        # 2. SQLite(native) -> JSON
        result = migrate_engine(
            source_path=str(sqlite_file),
            source_engine='sqlite',
            target_path=str(json_file),
            target_engine='json'
        )
        assert result['records'] == 3

        # 3. JSON -> CSV
        result = migrate_engine(
            source_path=str(json_file),
            source_engine='json',
            target_path=str(csv_file),
            target_engine='csv'
        )
        assert result['records'] == 3

        # 4. CSV -> Binary
        result = migrate_engine(
            source_path=str(csv_file),
            source_engine='csv',
            target_path=str(binary_file),
            target_engine='binary'
        )
        assert result['records'] == 3

        # 5. Binary -> SQLite
        result = migrate_engine(
            source_path=str(binary_file),
            source_engine='binary',
            target_path=str(sqlite_target),
            target_engine='sqlite'
        )
        assert result['records'] == 3

        # 6. 验证最终数据（使用兼容模式打开以验证数据）
        opts_compat = SqliteBackendOptions(use_native_sql=False)
        db_final = Storage(file_path=str(sqlite_target), engine='sqlite', backend_options=opts_compat)
        assert len(db_final.tables['people'].data) == 3

        people_data = list(db_final.tables['people'].data.values())
        names = [p['name'] for p in people_data]
        assert set(names) == {'Alice', 'Bob', 'Charlie'}

        db_final.close()


class TestMigrateSqliteNativeEmptyTable:
    """测试空表迁移"""

    def test_migrate_empty_table(self, tmp_path: Path) -> None:
        """空表迁移应正确处理"""
        sqlite_file = tmp_path / 'source.sqlite'
        json_file = tmp_path / 'target.json'

        # 1. 创建空表（无数据）
        opts = SqliteBackendOptions(use_native_sql=False)
        db = Storage(file_path=str(sqlite_file), engine='sqlite', backend_options=opts)
        Base: Type[PureBaseModel] = declarative_base(db)

        class EmptyTable(Base):
            __tablename__ = 'empty'
            id = Column(int, primary_key=True)
            value = Column(str)

        # 不插入任何数据，只创建表结构
        db.flush()
        db.close()

        # 2. 执行迁移
        result = migrate_engine(
            source_path=str(sqlite_file),
            source_engine='sqlite',
            target_path=str(json_file),
            target_engine='json'
        )

        # 3. 验证迁移结果
        assert result['tables'] == 1
        assert result['records'] == 0

        # 4. 验证 JSON 数据
        db_json = Storage(file_path=str(json_file), engine='json')
        assert 'empty' in db_json.tables
        assert len(db_json.tables['empty'].data) == 0

        db_json.close()


class TestMigrateSqliteNativeWithTypes:
    """测试各种数据类型的迁移"""

    def test_migrate_with_types(self, tmp_path: Path) -> None:
        """各种数据类型应正确迁移"""
        sqlite_file = tmp_path / 'source.sqlite'
        json_file = tmp_path / 'target.json'

        # 1. 创建包含多种类型的数据
        opts = SqliteBackendOptions(use_native_sql=False)
        db = Storage(file_path=str(sqlite_file), engine='sqlite', backend_options=opts)
        Base: Type[PureBaseModel] = declarative_base(db)

        class TypedRecord(Base):
            __tablename__ = 'typed'
            id = Column(int, primary_key=True)
            name = Column(str)
            score = Column(float)
            active = Column(bool)
            created = Column(datetime)
            birth_date = Column(date)
            duration = Column(timedelta)
            tags = Column(list)
            metadata = Column(dict)

        session = Session(db)

        now = datetime(2025, 1, 24, 12, 30, 0)
        today = date(2025, 1, 24)
        delta = timedelta(hours=2, minutes=30)

        session.execute(insert(TypedRecord).values(
            name='Alice',
            score=95.5,
            active=True,
            created=now,
            birth_date=today,
            duration=delta,
            tags=['python', 'database'],
            metadata={'level': 'senior', 'projects': 5}
        ))
        session.commit()
        db.flush()
        db.close()

        # 2. 执行迁移
        result = migrate_engine(
            source_path=str(sqlite_file),
            source_engine='sqlite',
            target_path=str(json_file),
            target_engine='json'
        )

        assert result['records'] == 1

        # 3. 验证 JSON 数据
        db_json = Storage(file_path=str(json_file), engine='json')
        record = list(db_json.tables['typed'].data.values())[0]

        assert record['name'] == 'Alice'
        assert record['score'] == 95.5
        assert record['active'] is True
        assert record['created'] == now
        assert record['birth_date'] == today
        assert record['duration'] == delta
        assert record['tags'] == ['python', 'database']
        assert record['metadata'] == {'level': 'senior', 'projects': 5}

        db_json.close()


class TestMigrateSqliteNativeMultipleTables:
    """测试多表迁移"""

    def test_migrate_multiple_tables(self, tmp_path: Path) -> None:
        """多表迁移应正确处理"""
        sqlite_file = tmp_path / 'source.sqlite'
        json_file = tmp_path / 'target.json'

        # 1. 创建多个表
        opts = SqliteBackendOptions(use_native_sql=False)
        db = Storage(file_path=str(sqlite_file), engine='sqlite', backend_options=opts)
        Base: Type[PureBaseModel] = declarative_base(db)

        class Users(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        class Products(Base):
            __tablename__ = 'products'
            id = Column(int, primary_key=True)
            title = Column(str)
            price = Column(float)

        class Orders(Base):
            __tablename__ = 'orders'
            id = Column(int, primary_key=True)
            user_id = Column(int)
            product_id = Column(int)

        session = Session(db)
        session.execute(insert(Users).values(name='Alice'))
        session.execute(insert(Users).values(name='Bob'))
        session.execute(insert(Products).values(title='Widget', price=9.99))
        session.execute(insert(Products).values(title='Gadget', price=19.99))
        session.execute(insert(Orders).values(user_id=1, product_id=1))
        session.execute(insert(Orders).values(user_id=2, product_id=2))
        session.execute(insert(Orders).values(user_id=1, product_id=2))
        session.commit()
        db.flush()
        db.close()

        # 2. 执行迁移
        result = migrate_engine(
            source_path=str(sqlite_file),
            source_engine='sqlite',
            target_path=str(json_file),
            target_engine='json'
        )

        # 3. 验证迁移结果
        assert result['tables'] == 3
        assert result['records'] == 7  # 2 users + 2 products + 3 orders

        # 4. 验证 JSON 数据
        db_json = Storage(file_path=str(json_file), engine='json')
        assert 'users' in db_json.tables
        assert 'products' in db_json.tables
        assert 'orders' in db_json.tables

        assert len(db_json.tables['users'].data) == 2
        assert len(db_json.tables['products'].data) == 2
        assert len(db_json.tables['orders'].data) == 3

        db_json.close()


class TestMigrateBinaryLazyLoadToJson:
    """测试 Binary 懒加载模式迁移到 JSON"""

    def test_migrate_binary_lazy_to_json(self, tmp_path: Path) -> None:
        """Binary 懒加载模式迁移到 JSON，数据应正确迁移"""
        binary_file = tmp_path / 'source.db'
        json_file = tmp_path / 'target.json'

        # 1. 创建 Binary 数据库（正常模式）
        db = Storage(file_path=str(binary_file), engine='binary')
        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)
            age = Column(int)

        session = Session(db)
        session.execute(insert(User).values(name='Alice', age=25))
        session.execute(insert(User).values(name='Bob', age=30))
        session.commit()
        db.flush()
        db.close()

        # 2. 使用懒加载模式重新打开，验证 table.data 为空
        opts_lazy = BinaryBackendOptions(lazy_load=True)
        db_lazy = Storage(file_path=str(binary_file), engine='binary', backend_options=opts_lazy)
        assert db_lazy.tables['users'].data == {}, "懒加载模式下 table.data 应该为空"
        db_lazy.close()

        # 3. 执行迁移（使用懒加载模式）
        result = migrate_engine(
            source_path=str(binary_file),
            source_engine='binary',
            target_path=str(json_file),
            target_engine='json',
            source_options=opts_lazy
        )

        # 4. 验证迁移结果
        assert result['tables'] == 1
        assert result['records'] == 2

        # 5. 验证 JSON 数据
        db_json = Storage(file_path=str(json_file), engine='json')
        assert len(db_json.tables['users'].data) == 2

        users_data = list(db_json.tables['users'].data.values())
        names = [u['name'] for u in users_data]
        assert 'Alice' in names
        assert 'Bob' in names

        db_json.close()


class TestMigrateBinaryLazyLoadMultipleTables:
    """测试 Binary 懒加载模式多表迁移"""

    def test_migrate_multiple_tables(self, tmp_path: Path) -> None:
        """多表迁移应正确处理"""
        binary_file = tmp_path / 'source.db'
        json_file = tmp_path / 'target.json'

        # 1. 创建多个表
        db = Storage(file_path=str(binary_file), engine='binary')
        Base: Type[PureBaseModel] = declarative_base(db)

        class Users(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        class Products(Base):
            __tablename__ = 'products'
            id = Column(int, primary_key=True)
            title = Column(str)
            price = Column(float)

        session = Session(db)
        session.execute(insert(Users).values(name='Alice'))
        session.execute(insert(Users).values(name='Bob'))
        session.execute(insert(Products).values(title='Widget', price=9.99))
        session.execute(insert(Products).values(title='Gadget', price=19.99))
        session.commit()
        db.flush()
        db.close()

        # 2. 使用懒加载模式迁移
        opts_lazy = BinaryBackendOptions(lazy_load=True)
        result = migrate_engine(
            source_path=str(binary_file),
            source_engine='binary',
            target_path=str(json_file),
            target_engine='json',
            source_options=opts_lazy
        )

        # 3. 验证迁移结果
        assert result['tables'] == 2
        assert result['records'] == 4  # 2 users + 2 products

        # 4. 验证 JSON 数据
        db_json = Storage(file_path=str(json_file), engine='json')
        assert 'users' in db_json.tables
        assert 'products' in db_json.tables

        assert len(db_json.tables['users'].data) == 2
        assert len(db_json.tables['products'].data) == 2

        db_json.close()


class TestMigrateBinaryLazyLoadChain:
    """测试 Binary 懒加载模式迁移链条"""

    def test_migrate_chain(self, tmp_path: Path) -> None:
        """完整迁移链条：Binary(lazy) -> JSON -> SQLite"""
        binary_file = tmp_path / 'source.db'
        json_file = tmp_path / 'target.json'
        sqlite_file = tmp_path / 'target.sqlite'

        # 1. 创建 Binary 数据库
        db = Storage(file_path=str(binary_file), engine='binary')
        Base: Type[PureBaseModel] = declarative_base(db)

        class Person(Base):
            __tablename__ = 'people'
            id = Column(int, primary_key=True)
            name = Column(str)
            score = Column(float)

        session = Session(db)
        session.execute(insert(Person).values(name='Alice', score=95.5))
        session.execute(insert(Person).values(name='Bob', score=88.0))
        session.execute(insert(Person).values(name='Charlie', score=92.3))
        session.commit()
        db.flush()
        db.close()

        # 2. Binary(lazy) -> JSON
        opts_lazy = BinaryBackendOptions(lazy_load=True)
        result = migrate_engine(
            source_path=str(binary_file),
            source_engine='binary',
            target_path=str(json_file),
            target_engine='json',
            source_options=opts_lazy
        )
        assert result['records'] == 3

        # 3. JSON -> SQLite
        result = migrate_engine(
            source_path=str(json_file),
            source_engine='json',
            target_path=str(sqlite_file),
            target_engine='sqlite'
        )
        assert result['records'] == 3

        # 4. 验证最终数据（使用兼容模式打开以验证数据）
        opts_compat = SqliteBackendOptions(use_native_sql=False)
        db_final = Storage(file_path=str(sqlite_file), engine='sqlite', backend_options=opts_compat)
        assert len(db_final.tables['people'].data) == 3

        people_data = list(db_final.tables['people'].data.values())
        names = [p['name'] for p in people_data]
        assert set(names) == {'Alice', 'Bob', 'Charlie'}

        db_final.close()

