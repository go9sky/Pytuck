"""
引擎元数据规范测试

测试方法：
- 白盒测试：验证各引擎的元数据存储位置和格式
- 场景设计：创建表、验证元数据

覆盖范围：
- 各引擎元数据存储位置验证
- 元数据内容完整性验证
"""

import pytest
import json
import zipfile
import sqlite3
from typing import Type

from pytuck import (
    Storage, Session, Column, declarative_base,
    PureBaseModel, insert,
)


class TestMetadataStorageFormat:
    """各引擎元数据存储格式验证"""

    def test_json_metadata_location(self, tmp_path):
        """JSON 引擎元数据在 tables 字段"""
        db_path = tmp_path / "test.json"
        db = Storage(file_path=str(db_path), engine='json')

        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        session = Session(db)
        session.execute(insert(User).values(id=1, name='Alice'))
        session.commit()
        db.close()

        # 验证 JSON 文件结构
        with open(db_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # JSON 引擎的元数据直接在 tables 字段中
        assert 'tables' in data
        assert 'users' in data['tables']

        # 验证表元数据内容
        table_meta = data['tables']['users']
        assert 'primary_key' in table_meta
        assert 'columns' in table_meta

    def test_csv_metadata_location(self, tmp_path):
        """CSV 引擎元数据在 _metadata.json"""
        db_path = tmp_path / "test.zip"
        db = Storage(file_path=str(db_path), engine='csv')

        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        session = Session(db)
        session.execute(insert(User).values(id=1, name='Alice'))
        session.commit()
        db.close()

        # 验证 ZIP 文件结构
        with zipfile.ZipFile(str(db_path), 'r') as zf:
            namelist = zf.namelist()
            assert '_metadata.json' in namelist

            # 读取元数据
            with zf.open('_metadata.json') as f:
                meta_data = json.loads(f.read().decode('utf-8'))

        assert 'tables' in meta_data
        assert 'users' in meta_data['tables']

    def test_sqlite_metadata_location(self, tmp_path):
        """SQLite 引擎元数据在 _pytuck_tables 表"""
        db_path = tmp_path / "test.sqlite"
        db = Storage(file_path=str(db_path), engine='sqlite')

        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        session = Session(db)
        session.execute(insert(User).values(id=1, name='Alice'))
        session.commit()
        db.close()

        # 验证 SQLite 数据库结构
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        # 检查 _pytuck_tables 表存在
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='_pytuck_tables'"
        )
        result = cursor.fetchone()
        assert result is not None

        # 检查 users 表的元数据存在
        cursor.execute("SELECT * FROM _pytuck_tables WHERE table_name = 'users'")
        result = cursor.fetchone()
        assert result is not None

        conn.close()

    def test_binary_metadata_in_file(self, tmp_path):
        """二进制引擎元数据在文件头"""
        db_path = tmp_path / "test.db"
        db = Storage(file_path=str(db_path), engine='binary')

        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        session = Session(db)
        session.execute(insert(User).values(id=1, name='Alice'))
        session.commit()
        db.close()

        # 验证文件存在且非空
        assert db_path.exists()
        assert db_path.stat().st_size > 0

        # 重新打开验证元数据完整
        db2 = Storage(file_path=str(db_path), engine='binary')
        table = db2.get_table('users')
        assert table is not None
        assert table.primary_key == 'id'
        db2.close()

    def test_excel_metadata_location(self, tmp_path):
        """Excel 引擎元数据在 _pytuck_tables 工作表"""
        try:
            import openpyxl
        except ImportError:
            pytest.skip("openpyxl not installed")

        db_path = tmp_path / "test.xlsx"
        db = Storage(file_path=str(db_path), engine='excel')

        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        session = Session(db)
        session.execute(insert(User).values(id=1, name='Alice'))
        session.commit()
        db.close()

        # 验证 Excel 文件结构
        wb = openpyxl.load_workbook(str(db_path))
        assert '_pytuck_tables' in wb.sheetnames
        wb.close()


class TestMetadataContent:
    """元数据内容完整性"""

    def test_metadata_contains_table_name(self, tmp_path):
        """元数据包含表名"""
        db_path = tmp_path / "test.json"
        db = Storage(file_path=str(db_path), engine='json')

        Base: Type[PureBaseModel] = declarative_base(db)

        class Product(Base):
            __tablename__ = 'products'
            id = Column(int, primary_key=True)
            name = Column(str)

        session = Session(db)
        session.execute(insert(Product).values(id=1, name='Widget'))
        session.commit()
        db.close()

        with open(db_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        assert 'products' in data['tables']

    def test_metadata_contains_primary_key(self, tmp_path):
        """元数据包含主键信息"""
        db_path = tmp_path / "test.json"
        db = Storage(file_path=str(db_path), engine='json')

        Base: Type[PureBaseModel] = declarative_base(db)

        class Product(Base):
            __tablename__ = 'products'
            product_id = Column(int, primary_key=True)
            name = Column(str)

        session = Session(db)
        session.execute(insert(Product).values(product_id=1, name='Widget'))
        session.commit()
        db.close()

        with open(db_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        table_meta = data['tables']['products']
        assert table_meta['primary_key'] == 'product_id'

    def test_metadata_contains_columns_schema(self, tmp_path):
        """元数据包含列信息"""
        db_path = tmp_path / "test.json"
        db = Storage(file_path=str(db_path), engine='json')

        Base: Type[PureBaseModel] = declarative_base(db)

        class Product(Base):
            __tablename__ = 'products'
            id = Column(int, primary_key=True)
            name = Column(str)
            price = Column(float)
            active = Column(bool)

        session = Session(db)
        session.execute(insert(Product).values(id=1, name='Widget', price=9.99, active=True))
        session.commit()
        db.close()

        with open(db_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        table_meta = data['tables']['products']
        columns = table_meta['columns']

        # 验证列存在
        column_names = [col['name'] for col in columns]
        assert 'id' in column_names
        assert 'name' in column_names
        assert 'price' in column_names
        assert 'active' in column_names

    def test_metadata_contains_next_id(self, tmp_path):
        """元数据包含 next_id（自增计数）"""
        db_path = tmp_path / "test.json"
        db = Storage(file_path=str(db_path), engine='json')

        Base: Type[PureBaseModel] = declarative_base(db)

        class Product(Base):
            __tablename__ = 'products'
            id = Column(int, primary_key=True)
            name = Column(str)

        session = Session(db)
        # 不指定 id，使用自增
        session.execute(insert(Product).values(name='Widget1'))
        session.execute(insert(Product).values(name='Widget2'))
        session.execute(insert(Product).values(name='Widget3'))
        session.commit()
        db.close()

        with open(db_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        table_meta = data['tables']['products']
        # next_id 应该大于已插入的记录数
        assert 'next_id' in table_meta
        assert table_meta['next_id'] >= 4  # 已插入 3 条


class TestMetadataPersistence:
    """元数据持久化测试"""

    def test_metadata_survives_reopen(self, tmp_path):
        """重新打开后元数据保留"""
        db_path = tmp_path / "test.json"

        # 第一次创建
        db = Storage(file_path=str(db_path), engine='json')
        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        session = Session(db)
        session.execute(insert(User).values(id=1, name='Alice'))
        session.commit()
        db.close()

        # 第二次打开
        db2 = Storage(file_path=str(db_path), engine='json')
        Base2: Type[PureBaseModel] = declarative_base(db2)

        class User2(Base2):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        # 验证表和数据存在
        table = db2.get_table('users')
        assert table is not None
        assert table.primary_key == 'id'

        session2 = Session(db2)
        from pytuck import select
        result = session2.execute(select(User2))
        users = result.all()
        assert len(users) == 1
        assert users[0].name == 'Alice'

        session2.close()
        db2.close()

    def test_multiple_tables_metadata(self, tmp_path):
        """多表元数据"""
        db_path = tmp_path / "test.json"
        db = Storage(file_path=str(db_path), engine='json')

        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        class Product(Base):
            __tablename__ = 'products'
            id = Column(int, primary_key=True)
            title = Column(str)

        class Order(Base):
            __tablename__ = 'orders'
            id = Column(int, primary_key=True)
            total = Column(float)

        session = Session(db)
        session.execute(insert(User).values(id=1, name='Alice'))
        session.execute(insert(Product).values(id=1, title='Widget'))
        session.execute(insert(Order).values(id=1, total=99.99))
        session.commit()
        db.close()

        # 验证所有表的元数据都存在
        with open(db_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        tables = data['tables']
        assert 'users' in tables
        assert 'products' in tables
        assert 'orders' in tables
