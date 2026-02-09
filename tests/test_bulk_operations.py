"""
批量操作（bulk_insert / bulk_update）测试

测试 Session 和 CRUDBaseModel 层的批量插入和批量更新 API。
"""

import pytest
from typing import Any, Dict, List, Type

from pytuck import (
    Storage, declarative_base, Session, Column,
    PureBaseModel, CRUDBaseModel, select, event
)
from pytuck.common.exceptions import (
    DuplicateKeyError, ValidationError, RecordNotFoundError
)


# ============== Fixtures ==============

@pytest.fixture
def db() -> Storage:
    """内存数据库"""
    return Storage()


@pytest.fixture
def pure_base(db: Storage) -> Type[PureBaseModel]:
    """纯模型基类"""
    return declarative_base(db)


@pytest.fixture
def crud_base(db: Storage) -> Type[CRUDBaseModel]:
    """CRUD 模型基类"""
    return declarative_base(db, crud=True)


# ============== A. Session.bulk_insert ==============

class TestSessionBulkInsert:

    def test_bulk_insert_basic(self, db: Storage, pure_base: Type[PureBaseModel]) -> None:
        """批量插入，验证记录正确写入"""
        class User(pure_base):  # type: ignore[valid-type]
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)
            age = Column(int)

        session = Session(db)
        users = [User(name='Alice', age=20), User(name='Bob', age=22)]
        session.bulk_insert(users)

        # 验证可以查询到
        result = session.execute(select(User)).all()
        assert len(result) == 2

    def test_bulk_insert_returns_pks(self, db: Storage, pure_base: Type[PureBaseModel]) -> None:
        """返回主键列表"""
        class User(pure_base):  # type: ignore[valid-type]
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        session = Session(db)
        users = [User(name='Alice'), User(name='Bob')]
        pks = session.bulk_insert(users)

        assert len(pks) == 2
        assert pks[0] == 1
        assert pks[1] == 2

    def test_bulk_insert_sets_pk_on_instances(self, db: Storage, pure_base: Type[PureBaseModel]) -> None:
        """实例自动获得 pk"""
        class User(pure_base):  # type: ignore[valid-type]
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        session = Session(db)
        users = [User(name='Alice'), User(name='Bob')]
        session.bulk_insert(users)

        assert users[0].id == 1
        assert users[1].id == 2

    def test_bulk_insert_with_auto_pk(self, db: Storage, pure_base: Type[PureBaseModel]) -> None:
        """自动主键分配"""
        class User(pure_base):  # type: ignore[valid-type]
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        session = Session(db)
        # 先插入一条
        session.bulk_insert([User(name='First')])
        # 再批量插入
        users = [User(name='Alice'), User(name='Bob')]
        pks = session.bulk_insert(users)

        assert pks[0] == 2
        assert pks[1] == 3

    def test_bulk_insert_with_manual_pk(self, db: Storage, pure_base: Type[PureBaseModel]) -> None:
        """手动指定主键"""
        class User(pure_base):  # type: ignore[valid-type]
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        session = Session(db)
        users = [User(id=10, name='Alice'), User(id=20, name='Bob')]
        pks = session.bulk_insert(users)

        assert pks == [10, 20]
        assert users[0].id == 10
        assert users[1].id == 20

    def test_bulk_insert_mixed_pk(self, db: Storage, pure_base: Type[PureBaseModel]) -> None:
        """部分手动部分自动"""
        class User(pure_base):  # type: ignore[valid-type]
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        session = Session(db)
        users = [User(id=5, name='Alice'), User(name='Bob'), User(id=10, name='Charlie')]
        pks = session.bulk_insert(users)

        assert pks[0] == 5
        assert isinstance(pks[1], int)  # 自动分配
        assert pks[2] == 10

    def test_bulk_insert_empty_list(self, db: Storage, pure_base: Type[PureBaseModel]) -> None:
        """空列表返回空列表"""
        session = Session(db)
        pks = session.bulk_insert([])
        assert pks == []

    def test_bulk_insert_duplicate_pk_raises(self, db: Storage, pure_base: Type[PureBaseModel]) -> None:
        """主键重复报错"""
        class User(pure_base):  # type: ignore[valid-type]
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        session = Session(db)
        # 先插入一条
        session.bulk_insert([User(id=1, name='Alice')])

        # 再插入重复主键
        with pytest.raises(DuplicateKeyError):
            session.bulk_insert([User(id=1, name='Bob')])

    def test_bulk_insert_different_model_raises(self, db: Storage, pure_base: Type[PureBaseModel]) -> None:
        """不同模型类报错"""
        class User(pure_base):  # type: ignore[valid-type]
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        class Product(pure_base):  # type: ignore[valid-type]
            __tablename__ = 'products'
            id = Column(int, primary_key=True)
            title = Column(str)

        session = Session(db)
        with pytest.raises(ValidationError):
            session.bulk_insert([User(name='Alice'), Product(title='Phone')])  # type: ignore[list-item]

    def test_bulk_insert_validates_fields(self, db: Storage, pure_base: Type[PureBaseModel]) -> None:
        """字段验证正常工作"""
        class User(pure_base):  # type: ignore[valid-type]
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)
            age = Column(int)

        session = Session(db)
        # int 字段传入字符串应被验证/转换
        users = [User(name='Alice', age='25')]  # type: ignore[arg-type]
        session.bulk_insert(users)

        result = session.execute(select(User)).all()
        assert result[0].age == 25  # 应被转换为 int

    def test_bulk_insert_with_default_values(self, db: Storage, pure_base: Type[PureBaseModel]) -> None:
        """默认值正常填充"""
        class User(pure_base):  # type: ignore[valid-type]
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)
            status = Column(str, default='active')

        session = Session(db)
        users = [User(name='Alice')]
        session.bulk_insert(users)

        result = session.execute(select(User)).all()
        assert result[0].status == 'active'

    def test_bulk_insert_index_maintained(self, db: Storage, pure_base: Type[PureBaseModel]) -> None:
        """索引正确维护"""
        class User(pure_base):  # type: ignore[valid-type]
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str, index=True)
            age = Column(int, index='sorted')

        session = Session(db)
        users = [User(name='Alice', age=20), User(name='Bob', age=22)]
        session.bulk_insert(users)

        # 通过索引查询验证
        result = session.execute(select(User).where(User.name == 'Alice')).all()
        assert len(result) == 1
        assert result[0].name == 'Alice'

        result = session.execute(select(User).where(User.age > 21)).all()
        assert len(result) == 1
        assert result[0].name == 'Bob'

    def test_bulk_insert_with_commit(self, db: Storage, pure_base: Type[PureBaseModel]) -> None:
        """与 commit 正确配合"""
        class User(pure_base):  # type: ignore[valid-type]
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        session = Session(db)
        users = [User(name='Alice'), User(name='Bob')]
        session.bulk_insert(users)
        session.commit()  # 不应报错

        result = session.execute(select(User)).all()
        assert len(result) == 2

    def test_bulk_insert_immediate_execution(self, db: Storage, pure_base: Type[PureBaseModel]) -> None:
        """调用后立即可查询到记录（无需 commit）"""
        class User(pure_base):  # type: ignore[valid-type]
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        session = Session(db)
        users = [User(name='Alice'), User(name='Bob')]
        session.bulk_insert(users)

        # 未 commit 也可查询
        result = session.execute(select(User)).all()
        assert len(result) == 2


# ============== B. Session.bulk_update ==============

class TestSessionBulkUpdate:

    def test_bulk_update_basic(self, db: Storage, pure_base: Type[PureBaseModel]) -> None:
        """批量更新，验证记录正确更新"""
        class User(pure_base):  # type: ignore[valid-type]
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)
            age = Column(int)

        session = Session(db)
        users = [User(name='Alice', age=20), User(name='Bob', age=22)]
        session.bulk_insert(users)

        # 修改后批量更新
        users[0].age = 21
        users[1].age = 23
        session.bulk_update(users)

        result = session.execute(select(User).where(User.id == 1)).all()
        assert result[0].age == 21
        result = session.execute(select(User).where(User.id == 2)).all()
        assert result[0].age == 23

    def test_bulk_update_returns_count(self, db: Storage, pure_base: Type[PureBaseModel]) -> None:
        """返回更新行数"""
        class User(pure_base):  # type: ignore[valid-type]
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        session = Session(db)
        users = [User(name='Alice'), User(name='Bob'), User(name='Charlie')]
        session.bulk_insert(users)

        for u in users:
            u.name = u.name + '_updated'  # type: ignore[operator]
        count = session.bulk_update(users)
        assert count == 3

    def test_bulk_update_empty_list(self, db: Storage, pure_base: Type[PureBaseModel]) -> None:
        """空列表返回 0"""
        session = Session(db)
        count = session.bulk_update([])
        assert count == 0

    def test_bulk_update_nonexistent_raises(self, db: Storage, pure_base: Type[PureBaseModel]) -> None:
        """不存在的记录报错"""
        class User(pure_base):  # type: ignore[valid-type]
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        session = Session(db)
        user = User(id=999, name='Ghost')
        user._loaded_from_db = True  # type: ignore[attr-defined]
        with pytest.raises(RecordNotFoundError):
            session.bulk_update([user])

    def test_bulk_update_validates_fields(self, db: Storage, pure_base: Type[PureBaseModel]) -> None:
        """字段验证正常工作"""
        class User(pure_base):  # type: ignore[valid-type]
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)
            age = Column(int)

        session = Session(db)
        users = [User(name='Alice', age=20)]
        session.bulk_insert(users)

        users[0].age = '25'  # type: ignore[assignment]
        session.bulk_update(users)

        result = session.execute(select(User)).all()
        assert result[0].age == 25  # 应被转换为 int

    def test_bulk_update_index_maintained(self, db: Storage, pure_base: Type[PureBaseModel]) -> None:
        """索引正确维护（old/new 值变化）"""
        class User(pure_base):  # type: ignore[valid-type]
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str, index=True)
            age = Column(int, index='sorted')

        session = Session(db)
        users = [User(name='Alice', age=20), User(name='Bob', age=30)]
        session.bulk_insert(users)

        # 修改索引列
        users[0].age = 35
        users[1].name = 'Bobby'
        session.bulk_update(users)

        # 验证索引更新
        result = session.execute(select(User).where(User.age > 30)).all()
        assert len(result) == 1
        assert result[0].name == 'Alice'

        result = session.execute(select(User).where(User.name == 'Bobby')).all()
        assert len(result) == 1

    def test_bulk_update_with_commit(self, db: Storage, pure_base: Type[PureBaseModel]) -> None:
        """与 commit 正确配合"""
        class User(pure_base):  # type: ignore[valid-type]
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        session = Session(db)
        users = [User(name='Alice')]
        session.bulk_insert(users)

        users[0].name = 'Alice_updated'
        session.bulk_update(users)
        session.commit()  # 不应报错

    def test_bulk_update_full_fields(self, db: Storage, pure_base: Type[PureBaseModel]) -> None:
        """更新全部字段"""
        class User(pure_base):  # type: ignore[valid-type]
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)
            age = Column(int)
            email = Column(str)

        session = Session(db)
        users = [User(name='Alice', age=20, email='alice@test.com')]
        session.bulk_insert(users)

        users[0].name = 'Alice_new'
        users[0].age = 25
        users[0].email = 'new@test.com'
        session.bulk_update(users)

        result = session.execute(select(User)).all()
        assert result[0].name == 'Alice_new'
        assert result[0].age == 25
        assert result[0].email == 'new@test.com'


# ============== C. CRUDBaseModel.bulk_insert / bulk_update ==============

class TestCRUDBulkOperations:

    def test_crud_bulk_insert(self, db: Storage, crud_base: Type[CRUDBaseModel]) -> None:
        """Active Record 模式批量插入"""
        class User(crud_base):  # type: ignore[valid-type]
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)
            age = Column(int)

        users = [User(name='Alice', age=20), User(name='Bob', age=22)]
        pks = User.bulk_insert(users)

        assert len(pks) == 2
        assert users[0].id == 1
        assert users[1].id == 2

        # 验证可查询
        all_users = User.all()
        assert len(all_users) == 2

    def test_crud_bulk_update(self, db: Storage, crud_base: Type[CRUDBaseModel]) -> None:
        """Active Record 模式批量更新"""
        class User(crud_base):  # type: ignore[valid-type]
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)
            age = Column(int)

        users = [User(name='Alice', age=20), User(name='Bob', age=22)]
        User.bulk_insert(users)

        users[0].age = 21
        users[1].age = 23
        count = User.bulk_update(users)
        assert count == 2

        # 验证更新
        alice = User.get(1)
        assert alice is not None
        assert alice.age == 21


# ============== D. 事件 ==============

class TestBulkEvents:

    def test_bulk_insert_events(self, db: Storage, pure_base: Type[PureBaseModel]) -> None:
        """before/after_bulk_insert 事件触发"""
        class User(pure_base):  # type: ignore[valid-type]
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        events_log: List[str] = []

        @event.listens_for(User, 'before_bulk_insert')
        def on_before(instances: list) -> None:
            events_log.append(f'before:{len(instances)}')

        @event.listens_for(User, 'after_bulk_insert')
        def on_after(instances: list) -> None:
            events_log.append(f'after:{len(instances)}')

        session = Session(db)
        users = [User(name='Alice'), User(name='Bob')]
        session.bulk_insert(users)

        assert events_log == ['before:2', 'after:2']

        # 清理
        event.clear(User)

    def test_bulk_update_events(self, db: Storage, pure_base: Type[PureBaseModel]) -> None:
        """before/after_bulk_update 事件触发"""
        class User(pure_base):  # type: ignore[valid-type]
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        events_log: List[str] = []

        @event.listens_for(User, 'before_bulk_update')
        def on_before(instances: list) -> None:
            events_log.append(f'before:{len(instances)}')

        @event.listens_for(User, 'after_bulk_update')
        def on_after(instances: list) -> None:
            events_log.append(f'after:{len(instances)}')

        session = Session(db)
        users = [User(name='Alice'), User(name='Bob')]
        session.bulk_insert(users)

        users[0].name = 'Alice_updated'
        session.bulk_update(users)

        assert events_log == ['before:2', 'after:2']

        # 清理
        event.clear(User)

    def test_bulk_insert_no_single_events(self, db: Storage, pure_base: Type[PureBaseModel]) -> None:
        """不触发逐条 before/after_insert"""
        class User(pure_base):  # type: ignore[valid-type]
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        single_events: List[str] = []

        @event.listens_for(User, 'before_insert')
        def on_single_before(instance: Any) -> None:
            single_events.append('before_insert')

        @event.listens_for(User, 'after_insert')
        def on_single_after(instance: Any) -> None:
            single_events.append('after_insert')

        session = Session(db)
        users = [User(name='Alice'), User(name='Bob')]
        session.bulk_insert(users)

        # 逐条事件不应被触发
        assert single_events == []

        # 清理
        event.clear(User)


# ============== E. 事务 ==============

class TestBulkTransaction:

    def test_bulk_insert_in_transaction(self, db: Storage, pure_base: Type[PureBaseModel]) -> None:
        """事务中批量插入"""
        class User(pure_base):  # type: ignore[valid-type]
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        session = Session(db)
        with session.begin():
            users = [User(name='Alice'), User(name='Bob')]
            session.bulk_insert(users)

        result = session.execute(select(User)).all()
        assert len(result) == 2

    def test_bulk_insert_transaction_rollback(self, db: Storage, pure_base: Type[PureBaseModel]) -> None:
        """事务回滚恢复"""
        class User(pure_base):  # type: ignore[valid-type]
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        session = Session(db)

        try:
            with session.begin():
                users = [User(name='Alice'), User(name='Bob')]
                session.bulk_insert(users)
                raise ValueError("Rollback!")
        except ValueError:
            pass

        # 事务回滚，数据应不存在
        result = session.execute(select(User)).all()
        assert len(result) == 0

    def test_bulk_update_in_transaction(self, db: Storage, pure_base: Type[PureBaseModel]) -> None:
        """事务中批量更新"""
        class User(pure_base):  # type: ignore[valid-type]
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)
            age = Column(int)

        session = Session(db)
        users = [User(name='Alice', age=20), User(name='Bob', age=22)]
        session.bulk_insert(users)

        with session.begin():
            users[0].age = 21
            users[1].age = 23
            session.bulk_update(users)

        result = session.execute(select(User).where(User.id == 1)).all()
        assert result[0].age == 21


# ============== F. 边界 ==============

class TestBulkEdgeCases:

    def test_bulk_insert_with_no_pk_model(self, db: Storage, pure_base: Type[PureBaseModel]) -> None:
        """无主键模型批量插入"""
        class Log(pure_base):  # type: ignore[valid-type]
            __tablename__ = 'logs'
            message = Column(str)
            level = Column(str)

        session = Session(db)
        logs = [Log(message='info msg', level='info'), Log(message='error msg', level='error')]
        pks = session.bulk_insert(logs)

        assert len(pks) == 2
        result = session.execute(select(Log)).all()
        assert len(result) == 2

    def test_bulk_insert_large_batch(self, db: Storage, pure_base: Type[PureBaseModel]) -> None:
        """大批量插入（1000+ 条）"""
        class User(pure_base):  # type: ignore[valid-type]
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        session = Session(db)
        users = [User(name=f'User_{i}') for i in range(1000)]
        pks = session.bulk_insert(users)

        assert len(pks) == 1000
        assert pks[0] == 1
        assert pks[-1] == 1000

        result = session.execute(select(User)).all()
        assert len(result) == 1000

    def test_bulk_insert_with_none_values(self, db: Storage, pure_base: Type[PureBaseModel]) -> None:
        """包含 None 值"""
        class User(pure_base):  # type: ignore[valid-type]
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)
            age = Column(int, nullable=True)

        session = Session(db)
        users = [User(name='Alice', age=None), User(name='Bob', age=25)]
        pks = session.bulk_insert(users)

        assert len(pks) == 2

    def test_bulk_insert_with_sorted_index(self, db: Storage, pure_base: Type[PureBaseModel]) -> None:
        """SortedIndex 列的批量插入"""
        class User(pure_base):  # type: ignore[valid-type]
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)
            age = Column(int, index='sorted')

        session = Session(db)
        users = [User(name='Alice', age=30), User(name='Bob', age=20), User(name='Charlie', age=25)]
        session.bulk_insert(users)

        # 使用有序索引查询
        result = session.execute(select(User).where(User.age >= 25).order_by('age')).all()
        assert len(result) == 2
        assert result[0].name == 'Charlie'
        assert result[1].name == 'Alice'
