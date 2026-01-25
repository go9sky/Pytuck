"""
Schema 同步功能测试
"""
import tempfile
from pathlib import Path
from typing import Type

import pytest

from pytuck import (
    Storage,
    Session,
    Column,
    declarative_base,
    PureBaseModel,
    CRUDBaseModel,
    SyncOptions,
    SyncResult,
    SchemaError,
)


class TestSyncOptions:
    """SyncOptions dataclass 测试"""

    def test_default_values(self) -> None:
        """测试默认值"""
        opts = SyncOptions()
        assert opts.sync_table_comment is True
        assert opts.sync_column_comments is True
        assert opts.add_new_columns is True
        assert opts.drop_missing_columns is False
        assert opts.update_column_types is False

    def test_custom_values(self) -> None:
        """测试自定义值"""
        opts = SyncOptions(
            sync_table_comment=False,
            add_new_columns=False,
            drop_missing_columns=True
        )
        assert opts.sync_table_comment is False
        assert opts.add_new_columns is False
        assert opts.drop_missing_columns is True


class TestSyncResult:
    """SyncResult dataclass 测试"""

    def test_has_changes_false(self) -> None:
        """测试无变更"""
        result = SyncResult(table_name='test')
        assert result.has_changes is False

    def test_has_changes_true_comment(self) -> None:
        """测试表备注更新"""
        result = SyncResult(table_name='test', table_comment_updated=True)
        assert result.has_changes is True

    def test_has_changes_true_columns(self) -> None:
        """测试列添加"""
        result = SyncResult(table_name='test', columns_added=['new_col'])
        assert result.has_changes is True


class TestTableLayerMethods:
    """Table 层方法测试"""

    def test_add_column_nullable(self) -> None:
        """测试添加可空列"""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / 'test.db'
            db = Storage(file_path=str(db_path))
            Base: Type[PureBaseModel] = declarative_base(db)

            class User(Base):
                __tablename__ = 'users'
                id = Column(int, primary_key=True)
                name = Column(str)

            # 插入数据
            session = Session(db)
            from pytuck import insert
            session.execute(insert(User).values(name='Alice'))
            session.commit()

            # 添加新列
            table = db.get_table('users')
            new_col = Column(int, nullable=True, name='age')
            table.add_column(new_col)

            # 验证列已添加
            assert 'age' in table.columns

            # 验证现有记录的新列值为 None
            record = table.get(1)
            assert record['age'] is None

            db.close()

    def test_add_column_with_default(self) -> None:
        """测试添加带默认值的列"""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / 'test.db'
            db = Storage(file_path=str(db_path))
            Base: Type[PureBaseModel] = declarative_base(db)

            class User(Base):
                __tablename__ = 'users'
                id = Column(int, primary_key=True)
                name = Column(str)

            # 插入数据
            session = Session(db)
            from pytuck import insert
            session.execute(insert(User).values(name='Alice'))
            session.commit()

            # 添加带默认值的列
            table = db.get_table('users')
            new_col = Column(str, nullable=False, default='active', name='status')
            table.add_column(new_col, default_value='active')

            # 验证现有记录的新列值为默认值
            record = table.get(1)
            assert record['status'] == 'active'

            db.close()

    def test_add_column_non_nullable_no_default_raises(self) -> None:
        """测试添加非空列无默认值报错"""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / 'test.db'
            db = Storage(file_path=str(db_path))
            Base: Type[PureBaseModel] = declarative_base(db)

            class User(Base):
                __tablename__ = 'users'
                id = Column(int, primary_key=True)
                name = Column(str)

            # 插入数据
            session = Session(db)
            from pytuck import insert
            session.execute(insert(User).values(name='Alice'))
            session.commit()

            # 尝试添加非空列无默认值
            table = db.get_table('users')
            new_col = Column(int, nullable=False, name='age')

            with pytest.raises(SchemaError):
                table.add_column(new_col)

            db.close()

    def test_drop_column(self) -> None:
        """测试删除列"""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / 'test.db'
            db = Storage(file_path=str(db_path))
            Base: Type[PureBaseModel] = declarative_base(db)

            class User(Base):
                __tablename__ = 'users'
                id = Column(int, primary_key=True)
                name = Column(str)
                age = Column(int, nullable=True)

            # 插入数据
            session = Session(db)
            from pytuck import insert
            session.execute(insert(User).values(name='Alice', age=20))
            session.commit()

            # 删除列
            table = db.get_table('users')
            table.drop_column('age')

            # 验证列已删除
            assert 'age' not in table.columns

            # 验证记录中也已删除
            record = table.get(1)
            assert 'age' not in record

            db.close()

    def test_drop_primary_key_raises(self) -> None:
        """测试删除主键列报错"""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / 'test.db'
            db = Storage(file_path=str(db_path))
            Base: Type[PureBaseModel] = declarative_base(db)

            class User(Base):
                __tablename__ = 'users'
                id = Column(int, primary_key=True)
                name = Column(str)

            table = db.get_table('users')

            with pytest.raises(SchemaError):
                table.drop_column('id')

            db.close()

    def test_update_comment(self) -> None:
        """测试更新表备注"""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / 'test.db'
            db = Storage(file_path=str(db_path))
            Base: Type[PureBaseModel] = declarative_base(db)

            class User(Base):
                __tablename__ = 'users'
                id = Column(int, primary_key=True)
                name = Column(str)

            table = db.get_table('users')
            table.update_comment('用户信息表')

            assert table.comment == '用户信息表'

            db.close()

    def test_update_column_comment(self) -> None:
        """测试更新列备注"""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / 'test.db'
            db = Storage(file_path=str(db_path))
            Base: Type[PureBaseModel] = declarative_base(db)

            class User(Base):
                __tablename__ = 'users'
                id = Column(int, primary_key=True)
                name = Column(str)

            table = db.get_table('users')
            table.update_column_comment('name', '用户名')

            assert table.columns['name'].comment == '用户名'

            db.close()


class TestStorageLayerMethods:
    """Storage 层方法测试"""

    def test_sync_table_schema_add_columns(self) -> None:
        """测试同步表结构 - 添加新列"""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / 'test.db'
            db = Storage(file_path=str(db_path))
            Base: Type[PureBaseModel] = declarative_base(db)

            class User(Base):
                __tablename__ = 'users'
                id = Column(int, primary_key=True)
                name = Column(str)

            # 插入数据
            session = Session(db)
            from pytuck import insert
            session.execute(insert(User).values(name='Alice'))
            session.commit()

            # 模拟第二次启动，模型增加了新列
            new_columns = [
                Column(int, primary_key=True, name='id'),
                Column(str, name='name'),
                Column(int, nullable=True, name='age'),
                Column(str, nullable=True, name='email')
            ]

            result = db.sync_table_schema('users', new_columns, '用户表')

            assert result.has_changes is True
            assert 'age' in result.columns_added
            assert 'email' in result.columns_added
            assert result.table_comment_updated is True

            # 验证列已添加
            table = db.get_table('users')
            assert 'age' in table.columns
            assert 'email' in table.columns

            db.close()

    def test_sync_table_schema_update_comments(self) -> None:
        """测试同步表结构 - 更新备注"""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / 'test.db'
            db = Storage(file_path=str(db_path))
            Base: Type[PureBaseModel] = declarative_base(db)

            class User(Base):
                __tablename__ = 'users'
                __table_comment__ = '旧备注'
                id = Column(int, primary_key=True)
                name = Column(str, comment='旧名称备注')

            # 同步更新备注
            new_columns = [
                Column(int, primary_key=True, name='id'),
                Column(str, comment='新名称备注', name='name')
            ]

            result = db.sync_table_schema('users', new_columns, '新表备注')

            assert result.table_comment_updated is True
            assert 'name' in result.column_comments_updated

            table = db.get_table('users')
            assert table.comment == '新表备注'
            assert table.columns['name'].comment == '新名称备注'

            db.close()

    def test_sync_table_schema_drop_columns(self) -> None:
        """测试同步表结构 - 删除列"""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / 'test.db'
            db = Storage(file_path=str(db_path))
            Base: Type[PureBaseModel] = declarative_base(db)

            class User(Base):
                __tablename__ = 'users'
                id = Column(int, primary_key=True)
                name = Column(str)
                age = Column(int, nullable=True)

            # 插入数据
            session = Session(db)
            from pytuck import insert
            session.execute(insert(User).values(name='Alice', age=20))
            session.commit()

            # 新模型没有 age 列
            new_columns = [
                Column(int, primary_key=True, name='id'),
                Column(str, name='name')
            ]

            # 默认不删除
            result = db.sync_table_schema('users', new_columns)
            assert 'age' not in result.columns_dropped

            # 启用删除
            opts = SyncOptions(drop_missing_columns=True)
            result = db.sync_table_schema('users', new_columns, options=opts)
            assert 'age' in result.columns_dropped

            table = db.get_table('users')
            assert 'age' not in table.columns

            db.close()

    def test_drop_table(self) -> None:
        """测试删除表"""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / 'test.db'
            db = Storage(file_path=str(db_path))
            Base: Type[PureBaseModel] = declarative_base(db)

            class User(Base):
                __tablename__ = 'users'
                id = Column(int, primary_key=True)
                name = Column(str)

            assert 'users' in db.tables

            db.drop_table('users')

            assert 'users' not in db.tables

            db.close()

    def test_rename_table(self) -> None:
        """测试重命名表"""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / 'test.db'
            db = Storage(file_path=str(db_path))
            Base: Type[PureBaseModel] = declarative_base(db)

            class User(Base):
                __tablename__ = 'users'
                id = Column(int, primary_key=True)
                name = Column(str)

            # 插入数据
            session = Session(db)
            from pytuck import insert
            session.execute(insert(User).values(name='Alice'))
            session.commit()

            db.rename_table('users', 'user_accounts')

            assert 'users' not in db.tables
            assert 'user_accounts' in db.tables

            # 验证数据仍然存在
            table = db.get_table('user_accounts')
            record = table.get(1)
            assert record['name'] == 'Alice'

            db.close()


class TestSessionLayerMethods:
    """Session 层方法测试"""

    def test_sync_schema_with_model(self) -> None:
        """测试 Session.sync_schema 方法"""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / 'test.db'
            db = Storage(file_path=str(db_path))
            Base: Type[PureBaseModel] = declarative_base(db)

            class User(Base):
                __tablename__ = 'users'
                __table_comment__ = '用户表'
                id = Column(int, primary_key=True)
                name = Column(str, comment='用户名')

            session = Session(db)
            result = session.sync_schema(User)

            # 第一次同步不应有变更
            assert result.has_changes is False

            db.close()

    def test_add_column_via_session(self) -> None:
        """测试通过 Session 添加列"""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / 'test.db'
            db = Storage(file_path=str(db_path))
            Base: Type[PureBaseModel] = declarative_base(db)

            class User(Base):
                __tablename__ = 'users'
                id = Column(int, primary_key=True)
                name = Column(str)

            session = Session(db)

            # 通过模型类添加列
            session.add_column(User, Column(int, nullable=True, name='age'))

            table = db.get_table('users')
            assert 'age' in table.columns

            # 通过表名添加列
            session.add_column('users', Column(str, nullable=True, name='email'))
            assert 'email' in table.columns

            db.close()

    def test_drop_column_via_session(self) -> None:
        """测试通过 Session 删除列"""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / 'test.db'
            db = Storage(file_path=str(db_path))
            Base: Type[PureBaseModel] = declarative_base(db)

            class User(Base):
                __tablename__ = 'users'
                id = Column(int, primary_key=True)
                name = Column(str)
                age = Column(int, nullable=True)

            session = Session(db)
            session.drop_column(User, 'age')

            table = db.get_table('users')
            assert 'age' not in table.columns

            db.close()


class TestDeclarativeBaseSyncSchema:
    """declarative_base sync_schema 参数测试"""

    def test_sync_schema_on_existing_table(self) -> None:
        """测试对已存在表的自动同步"""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / 'test.db'

            # 第一次：创建表
            db = Storage(file_path=str(db_path))
            Base: Type[PureBaseModel] = declarative_base(db)

            class UserV1(Base):
                __tablename__ = 'users'
                id = Column(int, primary_key=True)
                name = Column(str)

            session = Session(db)
            from pytuck import insert
            session.execute(insert(UserV1).values(name='Alice'))
            session.commit()
            db.close()

            # 第二次：加载已有数据库，模型增加了新列
            db2 = Storage(file_path=str(db_path))
            Base2: Type[PureBaseModel] = declarative_base(db2, sync_schema=True)

            class UserV2(Base2):
                __tablename__ = 'users'
                __table_comment__ = '用户表'
                id = Column(int, primary_key=True)
                name = Column(str, comment='用户名')
                age = Column(int, nullable=True, comment='年龄')

            # 验证新列已添加
            table = db2.get_table('users')
            assert 'age' in table.columns
            assert table.comment == '用户表'
            assert table.columns['name'].comment == '用户名'

            # 验证原有数据仍存在
            record = table.get(1)
            assert record['name'] == 'Alice'
            assert record['age'] is None

            db2.close()

    def test_sync_schema_with_options(self) -> None:
        """测试带选项的自动同步"""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / 'test.db'

            # 第一次：创建表
            db = Storage(file_path=str(db_path))
            Base: Type[PureBaseModel] = declarative_base(db)

            class UserV1(Base):
                __tablename__ = 'users'
                id = Column(int, primary_key=True)
                name = Column(str, comment='原始备注')

            db.close()

            # 第二次：禁用备注同步
            db2 = Storage(file_path=str(db_path))
            opts = SyncOptions(sync_column_comments=False)
            Base2: Type[PureBaseModel] = declarative_base(db2, sync_schema=True, sync_options=opts)

            class UserV2(Base2):
                __tablename__ = 'users'
                id = Column(int, primary_key=True)
                name = Column(str, comment='新备注')

            # 验证备注未更新
            table = db2.get_table('users')
            assert table.columns['name'].comment == '原始备注'

            db2.close()

    def test_crud_base_with_sync_schema(self) -> None:
        """测试 CRUDBaseModel 的自动同步"""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / 'test.db'

            # 第一次：创建表
            db = Storage(file_path=str(db_path))
            Base: Type[CRUDBaseModel] = declarative_base(db, crud=True)

            class UserV1(Base):
                __tablename__ = 'users'
                id = Column(int, primary_key=True)
                name = Column(str)

            UserV1.create(name='Alice')
            db.close()

            # 第二次：加载已有数据库
            db2 = Storage(file_path=str(db_path))
            Base2: Type[CRUDBaseModel] = declarative_base(db2, crud=True, sync_schema=True)

            class UserV2(Base2):
                __tablename__ = 'users'
                id = Column(int, primary_key=True)
                name = Column(str)
                email = Column(str, nullable=True)

            # 验证新列已添加
            table = db2.get_table('users')
            assert 'email' in table.columns

            # 验证原有数据仍存在
            user = UserV2.get(1)
            assert user is not None
            assert user.name == 'Alice'

            db2.close()


class TestPytuckViewAPI:
    """Pytuck-view 场景测试（纯表名 API）"""

    def test_storage_add_column_by_table_name(self) -> None:
        """测试通过表名添加列"""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / 'test.db'
            db = Storage(file_path=str(db_path))
            Base: Type[PureBaseModel] = declarative_base(db)

            class User(Base):
                __tablename__ = 'users'
                id = Column(int, primary_key=True)
                name = Column(str)

            # Pytuck-view 调用方式（无需模型类）
            db.add_column('users', Column(int, nullable=True, name='age'))

            table = db.get_table('users')
            assert 'age' in table.columns

            db.close()

    def test_storage_sync_table_schema_by_table_name(self) -> None:
        """测试通过表名同步表结构"""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / 'test.db'
            db = Storage(file_path=str(db_path))
            Base: Type[PureBaseModel] = declarative_base(db)

            class User(Base):
                __tablename__ = 'users'
                id = Column(int, primary_key=True)
                name = Column(str)

            # 插入数据
            session = Session(db)
            from pytuck import insert
            session.execute(insert(User).values(name='Alice'))
            session.commit()

            # Pytuck-view 调用方式（提供列定义）
            new_columns = [
                Column(int, primary_key=True, name='id'),
                Column(str, comment='用户名', name='name'),
                Column(int, nullable=True, name='age')
            ]
            result = db.sync_table_schema('users', new_columns, comment='用户信息表')

            assert result.has_changes is True
            assert 'age' in result.columns_added

            db.close()

    def test_storage_update_column_by_table_name(self) -> None:
        """测试通过表名更新列"""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / 'test.db'
            db = Storage(file_path=str(db_path))
            Base: Type[PureBaseModel] = declarative_base(db)

            class User(Base):
                __tablename__ = 'users'
                id = Column(int, primary_key=True)
                name = Column(str)

            # 更新列备注
            db.update_column('users', 'name', comment='用户名')

            table = db.get_table('users')
            assert table.columns['name'].comment == '用户名'

            db.close()
