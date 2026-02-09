"""
Session 高级功能测试

覆盖 Session 的以下功能：
- 脏跟踪（dirty tracking）
- merge() 操作
- Identity Map 高级场景
- 自动提交模式（autocommit）
"""

from typing import Type

import pytest

from pytuck import Storage, declarative_base, Session, Column
from pytuck import PureBaseModel, select, insert


# ---------- 脏跟踪 ----------


class TestDirtyTracking:
    """测试 Session 的自动脏跟踪功能"""

    def _setup(self) -> tuple:
        """创建内存数据库和模型"""
        db = Storage(in_memory=True)
        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'dt_users'
            id = Column(int, primary_key=True)
            name = Column(str)
            age = Column(int, nullable=True)

        session = Session(db)
        return db, session, User

    def test_attribute_change_marks_dirty(self) -> None:
        """修改 Column 属性后，实例进入 _dirty_objects"""
        db, session, User = self._setup()
        # 插入一条记录
        stmt = insert(User).values(name='Alice', age=20)
        session.execute(stmt)
        session.commit()

        # 通过 get 获取（注册到 identity map）
        user = session.get(User, 1)
        assert user is not None
        assert user not in session._dirty_objects

        # 修改属性
        user.name = 'Bob'
        assert user in session._dirty_objects

        db.close()

    def test_flush_clears_dirty(self) -> None:
        """flush 后 _dirty_objects 清空"""
        db, session, User = self._setup()
        stmt = insert(User).values(name='Alice', age=20)
        session.execute(stmt)
        session.commit()

        user = session.get(User, 1)
        assert user is not None
        user.name = 'Bob'
        assert len(session._dirty_objects) == 1

        session.flush()
        assert len(session._dirty_objects) == 0

        db.close()

    def test_multiple_changes_single_dirty_entry(self) -> None:
        """多次修改同一实例只标记一次"""
        db, session, User = self._setup()
        stmt = insert(User).values(name='Alice', age=20)
        session.execute(stmt)
        session.commit()

        user = session.get(User, 1)
        assert user is not None
        user.name = 'Bob'
        user.age = 25
        user.name = 'Charlie'

        # 只应该出现一次
        count = sum(1 for obj in session._dirty_objects if obj is user)
        assert count == 1

        db.close()

    def test_non_column_attr_not_tracked(self) -> None:
        """非 Column 属性修改不触发脏标记"""
        db, session, User = self._setup()
        stmt = insert(User).values(name='Alice', age=20)
        session.execute(stmt)
        session.commit()

        user = session.get(User, 1)
        assert user is not None
        # 设置非 Column 属性
        user.custom_attr = 'test'
        assert user not in session._dirty_objects

        db.close()

    def test_dirty_tracking_updates_database(self) -> None:
        """脏跟踪修改后 commit 能正确更新数据库"""
        db, session, User = self._setup()
        stmt = insert(User).values(name='Alice', age=20)
        session.execute(stmt)
        session.commit()

        user = session.get(User, 1)
        assert user is not None
        user.name = 'Updated'
        session.commit()

        # 验证数据库已更新
        user2 = session.get(User, 1)
        assert user2 is not None
        assert user2.name == 'Updated'

        db.close()


# ---------- merge ----------


class TestMerge:
    """测试 Session.merge() 操作"""

    def _setup(self) -> tuple:
        """创建内存数据库和模型"""
        db = Storage(in_memory=True)
        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'merge_users'
            id = Column(int, primary_key=True)
            name = Column(str)
            age = Column(int, nullable=True)

        session = Session(db)
        return db, session, User

    def test_merge_existing_in_identity_map(self) -> None:
        """merge 已在 identity map 中的对象，同步属性"""
        db, session, User = self._setup()
        stmt = insert(User).values(name='Alice', age=20)
        session.execute(stmt)
        session.commit()

        # 先通过 get 加载到 identity map
        existing = session.get(User, 1)
        assert existing is not None

        # 创建一个 detached 对象
        external = User(id=1, name='Updated', age=30)

        # merge 应该返回 identity map 中的对象
        merged = session.merge(external)
        assert merged is existing  # 应该是同一个对象
        assert merged is not external
        assert merged.name == 'Updated'
        assert merged.age == 30

        db.close()

    def test_merge_existing_in_db_not_in_map(self) -> None:
        """merge pk 在 DB 中但不在 identity map 中"""
        db, session, User = self._setup()
        stmt = insert(User).values(name='Alice', age=20)
        session.execute(stmt)
        session.commit()

        # 不通过 get 加载，identity map 中不存在
        # 直接 merge 一个 detached 对象
        external = User(id=1, name='Updated', age=30)
        merged = session.merge(external)

        # 应该从 DB 加载并更新
        assert merged is not external  # 应该是从 DB 加载的新对象
        assert merged.name == 'Updated'
        assert merged.age == 30

        db.close()

    def test_merge_new_object(self) -> None:
        """merge 无 pk 的新对象，视为 add"""
        db, session, User = self._setup()

        new_user = User(name='NewUser', age=25)
        merged = session.merge(new_user)

        # 没有 pk，应该被当作新对象
        assert merged is new_user
        assert new_user in session._new_objects

        db.close()

    def test_merge_returns_managed_instance(self) -> None:
        """merge 返回 identity map 中的实例"""
        db, session, User = self._setup()
        stmt = insert(User).values(name='Alice', age=20)
        session.execute(stmt)
        session.commit()

        existing = session.get(User, 1)
        assert existing is not None

        external = User(id=1, name='Bob')
        merged = session.merge(external)

        # 返回的应该是 identity map 中的实例
        assert merged is existing
        assert merged is not external

        db.close()

    def test_merge_updates_attributes(self) -> None:
        """确保 merge 同步属性到已有实例"""
        db, session, User = self._setup()
        stmt = insert(User).values(name='Alice', age=20)
        session.execute(stmt)
        session.commit()

        existing = session.get(User, 1)
        assert existing is not None
        assert existing.name == 'Alice'

        external = User(id=1, name='Changed', age=99)
        session.merge(external)

        assert existing.name == 'Changed'
        assert existing.age == 99

        db.close()

    def test_merge_nonexistent_pk(self) -> None:
        """merge 一个 DB 中不存在的 pk，应作为新对象处理"""
        db, session, User = self._setup()

        external = User(id=999, name='Ghost', age=0)
        merged = session.merge(external)

        # DB 中不存在，应被 add
        assert merged is external
        assert external in session._new_objects

        db.close()


# ---------- Identity Map 高级场景 ----------


class TestIdentityMapAdvanced:
    """测试 Identity Map 高级场景"""

    def _setup(self) -> tuple:
        """创建内存数据库和模型"""
        db = Storage(in_memory=True)
        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'idmap_users'
            id = Column(int, primary_key=True)
            name = Column(str)

        session = Session(db)
        return db, session, User

    def test_get_returns_same_instance(self) -> None:
        """多次 get 返回引用相同的对象"""
        db, session, User = self._setup()
        stmt = insert(User).values(name='Alice')
        session.execute(stmt)
        session.commit()

        user1 = session.get(User, 1)
        user2 = session.get(User, 1)
        assert user1 is user2

        db.close()

    def test_query_returns_identity_mapped(self) -> None:
        """查询结果使用 identity map 中的实例"""
        db, session, User = self._setup()
        stmt = insert(User).values(name='Alice')
        session.execute(stmt)
        session.commit()

        # 先通过 get 加载
        user_from_get = session.get(User, 1)
        assert user_from_get is not None

        # 再通过查询获取
        stmt = select(User).where(User.id == 1)
        result = session.execute(stmt)
        user_from_query = result.first()

        # 应该是同一个对象
        assert user_from_query is user_from_get

        db.close()

    def test_rollback_clears_identity_map(self) -> None:
        """rollback 后 identity map 清空"""
        db, session, User = self._setup()
        stmt = insert(User).values(name='Alice')
        session.execute(stmt)
        session.commit()

        user = session.get(User, 1)
        assert user is not None
        assert len(session._identity_map) > 0

        session.rollback()
        assert len(session._identity_map) == 0

        db.close()

    def test_no_pk_model_identity_map(self) -> None:
        """无主键模型使用 rowid 作为 identity key"""
        db = Storage(in_memory=True)
        Base: Type[PureBaseModel] = declarative_base(db)

        class Log(Base):
            __tablename__ = 'idmap_logs'
            message = Column(str)

        session = Session(db)

        log = Log(message='hello')
        session.add(log)
        session.flush()

        # 应该有 _pytuck_rowid 并注册到 identity map
        assert hasattr(log, '_pytuck_rowid')
        assert len(session._identity_map) == 1

        db.close()

    def test_identity_map_after_flush(self) -> None:
        """flush 后新对象注册到 identity map"""
        db, session, User = self._setup()

        user = User(name='Alice')
        session.add(user)
        assert len(session._identity_map) == 0  # flush 前不在 map 中

        session.flush()
        assert len(session._identity_map) == 1  # flush 后在 map 中
        assert user.id is not None  # pk 已被设置

        db.close()


# ---------- 自动提交 ----------


class TestAutocommit:
    """测试 Session 自动提交模式"""

    def _setup(self) -> tuple:
        """创建内存数据库和模型"""
        db = Storage(in_memory=True)
        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'autocommit_users'
            id = Column(int, primary_key=True)
            name = Column(str)

        session = Session(db, autocommit=True)
        return db, session, User

    def test_add_auto_commits(self) -> None:
        """autocommit=True 时 add 自动提交"""
        db, session, User = self._setup()

        user = User(name='Alice')
        session.add(user)

        # 应该已经被持久化
        assert user.id is not None
        assert len(session._new_objects) == 0  # 已 flush 清空

        db.close()

    def test_delete_auto_commits(self) -> None:
        """autocommit=True 时 delete 自动提交"""
        db, session, User = self._setup()

        user = User(name='Alice')
        session.add(user)
        pk = user.id

        session.delete(user)
        assert len(session._deleted_objects) == 0  # 已 flush 清空

        # 验证数据库中已删除
        record = db.get_table('autocommit_users').data
        assert pk not in record

        db.close()


# ---------- begin() 上下文管理器 ----------


class TestSessionBegin:
    """测试 Session.begin() 事务上下文"""

    def _setup(self) -> tuple:
        """创建内存数据库和模型"""
        db = Storage(in_memory=True)
        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'begin_users'
            id = Column(int, primary_key=True)
            name = Column(str)
            age = Column(int, nullable=True)

        session = Session(db)
        return db, session, User

    def test_begin_success_commits(self) -> None:
        """begin() 上下文成功退出时自动 flush"""
        db, session, User = self._setup()

        user = User(name='Alice')
        with session.begin():
            session.add(user)

        # 应该已经 flush
        assert len(session._new_objects) == 0
        assert user.id is not None

        db.close()

    def test_begin_exception_rollbacks(self) -> None:
        """begin() 上下文异常时回滚"""
        db, session, User = self._setup()

        user = User(name='Alice')
        with pytest.raises(ValueError):
            with session.begin():
                session.add(user)
                raise ValueError("test error")

        # 应该已经 rollback
        assert len(session._new_objects) == 0
        assert len(session._identity_map) == 0

        db.close()
