"""
Column.name 与属性名映射的全面测试

测试方法：
- 等价类划分：Column.name 相同/不同于属性名
- 场景设计：写入、读取、更新、删除、重载等完整流程
- 错误推断：可能遗漏映射的代码路径
"""

from pathlib import Path
from typing import Type

import pytest

from pytuck import Storage, Session, Column, PureBaseModel, CRUDBaseModel, declarative_base
from pytuck import select, insert, update, delete


class TestStatementAPIColumnNameMapping:
    """Statement API (insert/update/delete) 的 Column.name 映射"""

    def test_insert_statement_with_column_name(self, tmp_path: Path) -> None:
        """insert(Model).values() 使用 Column.name 正确写入"""
        db_file = tmp_path / 'test.db'
        db = Storage(file_path=str(db_file), engine='binary')
        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            user_name = Column(str, name='User Name')  # 属性名与列名不同

        session = Session(db)

        # 通过 Statement API 插入
        session.execute(insert(User).values(id=1, user_name='Alice'))
        session.commit()

        # 验证数据正确写入（直接查询存储层）
        records = db.query('users', [])
        assert len(records) == 1
        assert records[0]['User Name'] == 'Alice'  # 存储使用 Column.name

        session.close()
        db.close()

    def test_update_statement_with_column_name(self, tmp_path: Path) -> None:
        """update(Model).values() 使用 Column.name 正确更新"""
        db_file = tmp_path / 'test.db'
        db = Storage(file_path=str(db_file), engine='binary')
        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            user_name = Column(str, name='User Name')

        session = Session(db)

        # 插入初始数据
        session.execute(insert(User).values(id=1, user_name='Alice'))
        session.commit()

        # 通过 Statement API 更新
        session.execute(update(User).where(User.id == 1).values(user_name='Bob'))
        session.commit()

        # 验证更新成功
        records = db.query('users', [])
        assert records[0]['User Name'] == 'Bob'

        session.close()
        db.close()

    def test_update_statement_by_condition_with_column_name(self, tmp_path: Path) -> None:
        """update(Model).where(条件).values() 按条件更新时正确映射"""
        db_file = tmp_path / 'test.db'
        db = Storage(file_path=str(db_file), engine='binary')
        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            user_name = Column(str, name='User Name')
            status = Column(str, name='Status Code')

        session = Session(db)

        # 插入多条数据
        session.execute(insert(User).values(id=1, user_name='Alice', status='active'))
        session.execute(insert(User).values(id=2, user_name='Bob', status='active'))
        session.execute(insert(User).values(id=3, user_name='Charlie', status='inactive'))
        session.commit()

        # 按条件更新
        count = session.execute(
            update(User).where(User.status == 'active').values(status='updated')
        ).rowcount()
        session.commit()

        assert count == 2

        # 验证更新成功
        records = db.query('users', [])
        updated_count = sum(1 for r in records if r['Status Code'] == 'updated')
        assert updated_count == 2

        session.close()
        db.close()

    def test_delete_statement_with_column_name(self, tmp_path: Path) -> None:
        """delete(Model).where() 使用 Column.name 正确匹配"""
        db_file = tmp_path / 'test.db'
        db = Storage(file_path=str(db_file), engine='binary')
        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            user_name = Column(str, name='User Name')

        session = Session(db)

        # 插入数据
        session.execute(insert(User).values(id=1, user_name='Alice'))
        session.execute(insert(User).values(id=2, user_name='Bob'))
        session.commit()

        # 通过 Statement API 删除
        count = session.execute(delete(User).where(User.user_name == 'Alice')).rowcount()
        session.commit()

        assert count == 1

        # 验证删除成功
        records = db.query('users', [])
        assert len(records) == 1
        assert records[0]['User Name'] == 'Bob'

        session.close()
        db.close()

    def test_select_statement_with_column_name(self, tmp_path: Path) -> None:
        """select(Model).where() 使用 Column.name 正确查询"""
        db_file = tmp_path / 'test.db'
        db = Storage(file_path=str(db_file), engine='binary')
        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            user_name = Column(str, name='User Name')

        session = Session(db)

        # 插入数据
        session.execute(insert(User).values(id=1, user_name='Alice'))
        session.execute(insert(User).values(id=2, user_name='Bob'))
        session.commit()

        # 通过 Statement API 查询
        result = session.execute(select(User).where(User.user_name == 'Alice'))
        users = result.all()

        assert len(users) == 1
        assert users[0].user_name == 'Alice'

        session.close()
        db.close()


class TestColumnNamePersistenceRoundTrip:
    """Column.name 的持久化往返测试"""

    def test_write_close_reopen_read(self, tmp_path: Path) -> None:
        """写入 -> 关闭 -> 重新打开 -> 读取"""
        db_file = tmp_path / 'test.db'

        # 第一次：写入数据
        db = Storage(file_path=str(db_file), engine='binary')
        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            user_name = Column(str, name='User Name')

        session = Session(db)
        session.execute(insert(User).values(id=1, user_name='Alice'))
        session.commit()
        session.close()
        db.close()

        # 第二次：重新打开并读取
        db2 = Storage(file_path=str(db_file), engine='binary')
        Base2: Type[PureBaseModel] = declarative_base(db2)

        class User2(Base2):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            user_name = Column(str, name='User Name')

        session2 = Session(db2)

        # 使用 Session.get() 读取
        user = session2.get(User2, 1)
        assert user is not None
        assert user.user_name == 'Alice'

        # 使用 select 读取
        result = session2.execute(select(User2))
        users = result.all()
        assert len(users) == 1
        assert users[0].user_name == 'Alice'

        session2.close()
        db2.close()

    def test_cross_definition_compatibility(self, tmp_path: Path) -> None:
        """跨定义兼容：不同属性名，相同 Column.name"""
        db_file = tmp_path / 'test.db'

        # 版本1：使用 user_name 作为属性名
        db = Storage(file_path=str(db_file), engine='binary')
        Base: Type[PureBaseModel] = declarative_base(db)

        class UserV1(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            user_name = Column(str, name='display_name')

        session = Session(db)
        session.execute(insert(UserV1).values(id=1, user_name='Alice'))
        session.commit()
        session.close()
        db.close()

        # 版本2：使用 display_name 作为属性名（Column.name 相同）
        db2 = Storage(file_path=str(db_file), engine='binary')
        Base2: Type[PureBaseModel] = declarative_base(db2)

        class UserV2(Base2):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            display_name = Column(str, name='display_name')  # 不同属性名，相同列名

        session2 = Session(db2)

        # 应该能正确读取
        user = session2.get(UserV2, 1)
        assert user is not None
        assert user.display_name == 'Alice'

        session2.close()
        db2.close()

    def test_multiple_columns_with_custom_names(self, tmp_path: Path) -> None:
        """多个列都有自定义 Column.name"""
        db_file = tmp_path / 'test.db'
        db = Storage(file_path=str(db_file), engine='binary')
        Base: Type[PureBaseModel] = declarative_base(db)

        class Product(Base):
            __tablename__ = 'products'
            id = Column(int, primary_key=True, name='Product ID')
            product_name = Column(str, name='Product Name')
            unit_price = Column(float, name='Unit Price')
            stock_qty = Column(int, name='Stock Quantity')

        session = Session(db)

        # 插入
        session.execute(insert(Product).values(
            id=1,
            product_name='Widget',
            unit_price=9.99,
            stock_qty=100
        ))
        session.commit()

        # 验证存储层使用 Column.name
        records = db.query('products', [])
        assert 'Product ID' in records[0]
        assert 'Product Name' in records[0]
        assert 'Unit Price' in records[0]
        assert 'Stock Quantity' in records[0]
        assert records[0]['Product Name'] == 'Widget'
        assert records[0]['Unit Price'] == 9.99

        # 验证读取使用属性名
        user = session.get(Product, 1)
        assert user is not None
        assert user.product_name == 'Widget'
        assert user.unit_price == 9.99
        assert user.stock_qty == 100

        session.close()
        db.close()


class TestColumnNameEdgeCases:
    """Column.name 边界情况"""

    def test_column_name_with_spaces(self, tmp_path: Path) -> None:
        """Column.name 包含空格"""
        db_file = tmp_path / 'test.db'
        db = Storage(file_path=str(db_file), engine='binary')
        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            first_name = Column(str, name='First Name')
            last_name = Column(str, name='Last Name')

        session = Session(db)

        session.execute(insert(User).values(id=1, first_name='John', last_name='Doe'))
        session.commit()

        user = session.get(User, 1)
        assert user is not None
        assert user.first_name == 'John'
        assert user.last_name == 'Doe'

        session.close()
        db.close()

    def test_column_name_with_special_chars(self, tmp_path: Path) -> None:
        """Column.name 包含特殊字符（中文、标点等）"""
        db_file = tmp_path / 'test.db'
        db = Storage(file_path=str(db_file), engine='binary')
        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            user_name = Column(str, name='用户名')
            email = Column(str, name='电子邮箱@地址')

        session = Session(db)

        session.execute(insert(User).values(id=1, user_name='张三', email='test@example.com'))
        session.commit()

        # 验证存储层使用中文列名
        records = db.query('users', [])
        assert '用户名' in records[0]
        assert '电子邮箱@地址' in records[0]

        # 验证读取正常
        user = session.get(User, 1)
        assert user is not None
        assert user.user_name == '张三'
        assert user.email == 'test@example.com'

        session.close()
        db.close()

    def test_column_name_none_uses_attr_name(self, tmp_path: Path) -> None:
        """Column.name 为 None 时使用属性名"""
        db_file = tmp_path / 'test.db'
        db = Storage(file_path=str(db_file), engine='binary')
        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            username = Column(str)  # name 未指定，应该使用 'username'

        session = Session(db)

        session.execute(insert(User).values(id=1, username='alice'))
        session.commit()

        # 验证存储层使用属性名作为列名
        records = db.query('users', [])
        assert 'username' in records[0]
        assert records[0]['username'] == 'alice'

        session.close()
        db.close()


class TestCRUDBaseModelColumnNameMapping:
    """Active Record 模式的 Column.name 映射"""

    def test_create_with_column_name(self, tmp_path: Path) -> None:
        """CRUDBaseModel.create() 使用 Column.name 正确写入"""
        db_file = tmp_path / 'test.db'
        db = Storage(file_path=str(db_file), engine='binary')
        Base: Type[CRUDBaseModel] = declarative_base(db, crud=True)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            user_name = Column(str, name='User Name')

        user = User.create(user_name='Alice')

        # 验证存储层使用 Column.name
        records = db.query('users', [])
        assert records[0]['User Name'] == 'Alice'

        db.close()

    def test_save_with_column_name(self, tmp_path: Path) -> None:
        """CRUDBaseModel.save() 使用 Column.name 正确更新"""
        db_file = tmp_path / 'test.db'
        db = Storage(file_path=str(db_file), engine='binary')
        Base: Type[CRUDBaseModel] = declarative_base(db, crud=True)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            user_name = Column(str, name='User Name')

        user = User.create(user_name='Alice')
        user.user_name = 'Bob'
        user.save()

        # 验证更新成功
        records = db.query('users', [])
        assert records[0]['User Name'] == 'Bob'

        db.close()

    def test_get_with_column_name(self, tmp_path: Path) -> None:
        """CRUDBaseModel.get() 使用 Column.name 正确读取"""
        db_file = tmp_path / 'test.db'
        db = Storage(file_path=str(db_file), engine='binary')
        Base: Type[CRUDBaseModel] = declarative_base(db, crud=True)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            user_name = Column(str, name='User Name')

        User.create(user_name='Alice')

        user = User.get(1)
        assert user is not None
        assert user.user_name == 'Alice'

        db.close()

    def test_filter_with_column_name(self, tmp_path: Path) -> None:
        """CRUDBaseModel.filter() 使用 Column.name 正确查询"""
        db_file = tmp_path / 'test.db'
        db = Storage(file_path=str(db_file), engine='binary')
        Base: Type[CRUDBaseModel] = declarative_base(db, crud=True)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            user_name = Column(str, name='User Name')

        User.create(user_name='Alice')
        User.create(user_name='Bob')

        users = User.filter(User.user_name == 'Alice').all()
        assert len(users) == 1
        assert users[0].user_name == 'Alice'

        db.close()

    def test_filter_by_with_column_name(self, tmp_path: Path) -> None:
        """CRUDBaseModel.filter_by() 使用 Column.name 正确查询"""
        db_file = tmp_path / 'test.db'
        db = Storage(file_path=str(db_file), engine='binary')
        Base: Type[CRUDBaseModel] = declarative_base(db, crud=True)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            user_name = Column(str, name='User Name')

        User.create(user_name='Alice')
        User.create(user_name='Bob')

        users = User.filter_by(user_name='Alice').all()
        assert len(users) == 1
        assert users[0].user_name == 'Alice'

        db.close()


class TestSessionAddColumnNameMapping:
    """Session.add() 的 Column.name 映射"""

    def test_session_add_with_column_name(self, tmp_path: Path) -> None:
        """Session.add() + flush 使用 Column.name 正确写入"""
        db_file = tmp_path / 'test.db'
        db = Storage(file_path=str(db_file), engine='binary')
        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            user_name = Column(str, name='User Name')

        session = Session(db)

        user = User(user_name='Alice')
        session.add(user)
        session.flush()

        # 验证存储层使用 Column.name
        records = db.query('users', [])
        assert records[0]['User Name'] == 'Alice'

        session.close()
        db.close()

    def test_session_add_update_with_column_name(self, tmp_path: Path) -> None:
        """Session.add() 后更新属性，再 flush"""
        db_file = tmp_path / 'test.db'
        db = Storage(file_path=str(db_file), engine='binary')
        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            user_name = Column(str, name='User Name')

        session = Session(db)

        user = User(user_name='Alice')
        session.add(user)
        session.flush()

        # 更新后再 flush
        user.user_name = 'Bob'
        session.flush()

        # 验证更新成功
        records = db.query('users', [])
        assert records[0]['User Name'] == 'Bob'

        session.close()
        db.close()


class TestPrimaryKeyColumnNameMapping:
    """主键列的 Column.name 映射"""

    def test_pk_with_custom_column_name(self, tmp_path: Path) -> None:
        """主键列使用自定义 Column.name"""
        db_file = tmp_path / 'test.db'
        db = Storage(file_path=str(db_file), engine='binary')
        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            user_id = Column(int, primary_key=True, name='User ID')
            user_name = Column(str, name='User Name')

        session = Session(db)

        session.execute(insert(User).values(user_id=1, user_name='Alice'))
        session.commit()

        # 验证存储层使用 Column.name
        records = db.query('users', [])
        assert 'User ID' in records[0]
        assert records[0]['User ID'] == 1

        # 验证 Session.get() 正常工作
        user = session.get(User, 1)
        assert user is not None
        assert user.user_id == 1
        assert user.user_name == 'Alice'

        session.close()
        db.close()

    def test_update_by_pk_with_custom_column_name(self, tmp_path: Path) -> None:
        """通过自定义 Column.name 的主键更新"""
        db_file = tmp_path / 'test.db'
        db = Storage(file_path=str(db_file), engine='binary')
        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            user_id = Column(int, primary_key=True, name='User ID')
            user_name = Column(str, name='User Name')

        session = Session(db)

        session.execute(insert(User).values(user_id=1, user_name='Alice'))
        session.commit()

        # 通过主键条件更新
        session.execute(update(User).where(User.user_id == 1).values(user_name='Bob'))
        session.commit()

        # 验证更新成功
        user = session.get(User, 1)
        assert user is not None
        assert user.user_name == 'Bob'

        session.close()
        db.close()

    def test_delete_by_pk_with_custom_column_name(self, tmp_path: Path) -> None:
        """通过自定义 Column.name 的主键删除"""
        db_file = tmp_path / 'test.db'
        db = Storage(file_path=str(db_file), engine='binary')
        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            user_id = Column(int, primary_key=True, name='User ID')
            user_name = Column(str, name='User Name')

        session = Session(db)

        session.execute(insert(User).values(user_id=1, user_name='Alice'))
        session.execute(insert(User).values(user_id=2, user_name='Bob'))
        session.commit()

        # 通过主键条件删除
        count = session.execute(delete(User).where(User.user_id == 1)).rowcount()
        session.commit()

        assert count == 1

        # 验证删除成功
        result = session.execute(select(User))
        users = result.all()
        assert len(users) == 1
        assert users[0].user_name == 'Bob'

        session.close()
        db.close()
