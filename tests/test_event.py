"""
Pytuck 事件钩子系统测试

测试 Model 级和 Storage 级事件的注册、触发、移除等功能。
"""

import tempfile
from pathlib import Path
from typing import Any, List, Type

import pytest

from pytuck import Storage, declarative_base, Session, Column, event
from pytuck import PureBaseModel, CRUDBaseModel
from pytuck import insert, select, update, delete
from pytuck.core.event import EventManager, MODEL_EVENTS, STORAGE_EVENTS, ALL_EVENTS


@pytest.fixture(autouse=True)
def clear_events() -> None:
    """每个测试前后清除所有事件监听器"""
    event.clear()
    yield  # type: ignore[misc]
    event.clear()


@pytest.fixture
def session_setup(temp_dir: Path):
    """创建 Session 模式的测试环境"""
    db = Storage(file_path=str(temp_dir / 'test.db'), engine='json')
    Base: Type[PureBaseModel] = declarative_base(db)

    class User(Base):
        __tablename__ = 'users'
        id = Column(int, primary_key=True)
        name = Column(str)
        age = Column(int)

    session = Session(db)
    return db, User, session


@pytest.fixture
def crud_setup(temp_dir: Path):
    """创建 CRUD 模式的测试环境"""
    db = Storage(file_path=str(temp_dir / 'test.db'), engine='json')
    Base: Type[CRUDBaseModel] = declarative_base(db, crud=True)

    class Item(Base):
        __tablename__ = 'items'
        id = Column(int, primary_key=True)
        name = Column(str)
        price = Column(float)

    return db, Item


# ============================================================================
# 基础注册与触发（Session 模式）
# ============================================================================


class TestSessionInsertEvents:
    """Session 模式下 insert 事件测试"""

    def test_before_insert(self, session_setup: Any) -> None:
        """before_insert 回调在插入前被调用"""
        db, User, session = session_setup
        called: List[Any] = []

        event.listen(User, 'before_insert', lambda inst: called.append(inst))

        user = User(name='Alice', age=25)
        session.add(user)
        session.commit()

        assert len(called) == 1
        assert called[0] is user

    def test_after_insert(self, session_setup: Any) -> None:
        """after_insert 回调在插入后被调用，实例已有 pk"""
        db, User, session = session_setup
        pks: List[Any] = []

        def on_after_insert(inst: Any) -> None:
            pks.append(getattr(inst, 'id'))

        event.listen(User, 'after_insert', on_after_insert)

        user = User(name='Bob', age=30)
        session.add(user)
        session.commit()

        assert len(pks) == 1
        assert pks[0] is not None  # pk 已被赋值

    def test_before_insert_modify_instance(self, session_setup: Any) -> None:
        """before_insert 回调中可以修改实例字段"""
        db, User, session = session_setup

        def set_default_age(inst: Any) -> None:
            if getattr(inst, 'age') is None:
                inst.age = 18

        event.listen(User, 'before_insert', set_default_age)

        user = User(name='Charlie')
        session.add(user)
        session.commit()

        # 验证回调修改生效
        assert user.age == 18

        # 验证数据库中也是修改后的值
        result = session.execute(select(User).where(User.name == 'Charlie'))
        found = result.first()
        assert found is not None
        assert found.age == 18


class TestSessionUpdateEvents:
    """Session 模式下 update 事件测试"""

    def test_before_update(self, session_setup: Any) -> None:
        """before_update 回调在更新前被调用"""
        db, User, session = session_setup
        called: List[Any] = []

        user = User(name='Alice', age=25)
        session.add(user)
        session.commit()

        event.listen(User, 'before_update', lambda inst: called.append('before'))

        user.age = 26
        session.commit()

        assert 'before' in called

    def test_after_update(self, session_setup: Any) -> None:
        """after_update 回调在更新后被调用"""
        db, User, session = session_setup
        called: List[Any] = []

        user = User(name='Alice', age=25)
        session.add(user)
        session.commit()

        event.listen(User, 'after_update', lambda inst: called.append('after'))

        user.age = 26
        session.commit()

        assert 'after' in called


class TestSessionDeleteEvents:
    """Session 模式下 delete 事件测试"""

    def test_before_delete(self, session_setup: Any) -> None:
        """before_delete 回调在删除前被调用"""
        db, User, session = session_setup
        called: List[Any] = []

        user = User(name='Alice', age=25)
        session.add(user)
        session.commit()

        event.listen(User, 'before_delete', lambda inst: called.append(inst))

        session.delete(user)
        session.commit()

        assert len(called) == 1
        assert called[0] is user

    def test_after_delete(self, session_setup: Any) -> None:
        """after_delete 回调在删除后被调用"""
        db, User, session = session_setup
        called: List[Any] = []

        user = User(name='Alice', age=25)
        session.add(user)
        session.commit()

        event.listen(User, 'after_delete', lambda inst: called.append('deleted'))

        session.delete(user)
        session.commit()

        assert 'deleted' in called


# ============================================================================
# 装饰器注册
# ============================================================================


class TestDecoratorRegistration:
    """装饰器方式注册事件测试"""

    def test_listens_for_decorator(self, session_setup: Any) -> None:
        """@event.listens_for 装饰器注册"""
        db, User, session = session_setup
        called: List[str] = []

        @event.listens_for(User, 'before_insert')
        def on_before_insert(inst: Any) -> None:
            called.append('decorated')

        user = User(name='Alice', age=25)
        session.add(user)
        session.commit()

        assert called == ['decorated']

    def test_decorator_returns_original_function(self, session_setup: Any) -> None:
        """装饰器返回原始函数"""
        db, User, session = session_setup

        @event.listens_for(User, 'before_insert')
        def my_handler(inst: Any) -> None:
            pass

        # 装饰器应该返回原始函数
        assert my_handler.__name__ == 'my_handler'


# ============================================================================
# 多个监听器
# ============================================================================


class TestMultipleListeners:
    """多个监听器测试"""

    def test_multiple_listeners_all_called(self, session_setup: Any) -> None:
        """同一事件的多个监听器全部被调用"""
        db, User, session = session_setup
        order: List[int] = []

        event.listen(User, 'before_insert', lambda inst: order.append(1))
        event.listen(User, 'before_insert', lambda inst: order.append(2))
        event.listen(User, 'before_insert', lambda inst: order.append(3))

        user = User(name='Alice', age=25)
        session.add(user)
        session.commit()

        assert order == [1, 2, 3]

    def test_multiple_events_on_same_model(self, session_setup: Any) -> None:
        """同一模型的不同事件互不影响"""
        db, User, session = session_setup
        events: List[str] = []

        event.listen(User, 'before_insert', lambda inst: events.append('before_insert'))
        event.listen(User, 'after_insert', lambda inst: events.append('after_insert'))

        user = User(name='Alice', age=25)
        session.add(user)
        session.commit()

        assert events == ['before_insert', 'after_insert']


# ============================================================================
# 移除监听器
# ============================================================================


class TestRemoveListener:
    """移除监听器测试"""

    def test_remove_listener(self, session_setup: Any) -> None:
        """event.remove() 后回调不再被调用"""
        db, User, session = session_setup
        called: List[str] = []

        def handler(inst: Any) -> None:
            called.append('called')

        event.listen(User, 'before_insert', handler)
        event.remove(User, 'before_insert', handler)

        user = User(name='Alice', age=25)
        session.add(user)
        session.commit()

        assert called == []

    def test_remove_nonexistent_listener(self, session_setup: Any) -> None:
        """移除不存在的监听器不报错"""
        db, User, session = session_setup

        def handler(inst: Any) -> None:
            pass

        # 不应抛出异常
        event.remove(User, 'before_insert', handler)


# ============================================================================
# Storage 级事件
# ============================================================================


class TestStorageEvents:
    """Storage 级事件测试"""

    def test_before_flush(self, session_setup: Any) -> None:
        """before_flush 在写入磁盘前触发"""
        db, User, session = session_setup
        called: List[str] = []

        event.listen(db, 'before_flush', lambda s: called.append('before_flush'))

        user = User(name='Alice', age=25)
        session.add(user)
        session.commit()
        db.flush()

        assert 'before_flush' in called

    def test_after_flush(self, session_setup: Any) -> None:
        """after_flush 在写入磁盘后触发"""
        db, User, session = session_setup
        called: List[str] = []

        event.listen(db, 'after_flush', lambda s: called.append('after_flush'))

        user = User(name='Alice', age=25)
        session.add(user)
        session.commit()
        db.flush()

        assert 'after_flush' in called

    def test_flush_event_order(self, session_setup: Any) -> None:
        """before_flush 在 after_flush 之前触发"""
        db, User, session = session_setup
        order: List[str] = []

        event.listen(db, 'before_flush', lambda s: order.append('before'))
        event.listen(db, 'after_flush', lambda s: order.append('after'))

        user = User(name='Alice', age=25)
        session.add(user)
        session.commit()
        db.flush()

        assert order == ['before', 'after']

    def test_flush_not_triggered_when_not_dirty(self, session_setup: Any) -> None:
        """数据未修改时 flush 不触发事件"""
        db, User, session = session_setup

        # 先 flush 清除初始 dirty 状态（declarative_base 创建表会标记 dirty）
        db.flush()

        called: List[str] = []
        event.listen(db, 'before_flush', lambda s: called.append('flush'))

        # 没有任何数据操作，直接 flush
        db.flush()

        assert called == []


# ============================================================================
# CRUDBaseModel 路径
# ============================================================================


class TestCRUDModelEvents:
    """Active Record 模式事件测试"""

    def test_crud_save_triggers_insert_events(self, crud_setup: Any) -> None:
        """save() 新建时触发 insert 事件"""
        db, Item = crud_setup
        events: List[str] = []

        event.listen(Item, 'before_insert', lambda inst: events.append('before_insert'))
        event.listen(Item, 'after_insert', lambda inst: events.append('after_insert'))

        item = Item(name='Widget', price=9.99)
        item.save()

        assert events == ['before_insert', 'after_insert']

    def test_crud_save_triggers_update_events(self, crud_setup: Any) -> None:
        """save() 更新时触发 update 事件"""
        db, Item = crud_setup
        events: List[str] = []

        item = Item(name='Widget', price=9.99)
        item.save()

        event.listen(Item, 'before_update', lambda inst: events.append('before_update'))
        event.listen(Item, 'after_update', lambda inst: events.append('after_update'))

        item.price = 19.99
        item.save()

        assert events == ['before_update', 'after_update']

    def test_crud_delete_triggers_delete_events(self, crud_setup: Any) -> None:
        """delete() 触发 delete 事件"""
        db, Item = crud_setup
        events: List[str] = []

        item = Item(name='Widget', price=9.99)
        item.save()

        event.listen(Item, 'before_delete', lambda inst: events.append('before_delete'))
        event.listen(Item, 'after_delete', lambda inst: events.append('after_delete'))

        item.delete()

        assert events == ['before_delete', 'after_delete']

    def test_crud_before_insert_modify_instance(self, crud_setup: Any) -> None:
        """CRUD 模式下 before_insert 回调可以修改字段"""
        db, Item = crud_setup

        def set_default_price(inst: Any) -> None:
            if getattr(inst, 'price') is None:
                inst.price = 0.0

        event.listen(Item, 'before_insert', set_default_price)

        item = Item(name='FreeItem')
        item.save()

        assert item.price == 0.0


# ============================================================================
# 清理功能
# ============================================================================


class TestClearListeners:
    """清除监听器测试"""

    def test_clear_all(self, session_setup: Any) -> None:
        """event.clear() 清除所有监听器"""
        db, User, session = session_setup
        called: List[str] = []

        event.listen(User, 'before_insert', lambda inst: called.append('model'))
        event.listen(db, 'before_flush', lambda s: called.append('storage'))

        event.clear()

        user = User(name='Alice', age=25)
        session.add(user)
        session.commit()
        db.flush()

        assert called == []

    def test_clear_model_target(self, session_setup: Any) -> None:
        """event.clear(ModelClass) 只清除该模型的监听器"""
        db, User, session = session_setup
        called: List[str] = []

        event.listen(User, 'before_insert', lambda inst: called.append('user'))
        event.listen(db, 'before_flush', lambda s: called.append('flush'))

        event.clear(User)

        user = User(name='Alice', age=25)
        session.add(user)
        session.commit()
        db.flush()

        # User 的事件被清除，Storage 事件仍然触发
        assert 'user' not in called
        assert 'flush' in called

    def test_clear_storage_target(self, session_setup: Any) -> None:
        """event.clear(storage) 只清除该 Storage 的监听器"""
        db, User, session = session_setup
        called: List[str] = []

        event.listen(User, 'before_insert', lambda inst: called.append('user'))
        event.listen(db, 'before_flush', lambda s: called.append('flush'))

        event.clear(db)

        user = User(name='Alice', age=25)
        session.add(user)
        session.commit()
        db.flush()

        # Storage 的事件被清除，User 事件仍然触发
        assert 'user' in called
        assert 'flush' not in called


# ============================================================================
# 无效事件名
# ============================================================================


class TestInvalidEventName:
    """无效事件名测试"""

    def test_invalid_event_name_raises(self, session_setup: Any) -> None:
        """注册无效事件名抛出 ValueError"""
        db, User, session = session_setup

        with pytest.raises(ValueError, match="Unknown event"):
            event.listen(User, 'invalid_event', lambda inst: None)

    def test_invalid_storage_event_name_raises(self, session_setup: Any) -> None:
        """Storage 级无效事件名抛出 ValueError"""
        db, User, session = session_setup

        with pytest.raises(ValueError, match="Unknown event"):
            event.listen(db, 'before_save', lambda s: None)


# ============================================================================
# 无监听器时正常运行
# ============================================================================


class TestNoListeners:
    """无监听器时正常运行测试"""

    def test_session_operations_without_listeners(self, session_setup: Any) -> None:
        """未注册监听器时 Session 操作正常"""
        db, User, session = session_setup

        # insert
        user = User(name='Alice', age=25)
        session.add(user)
        session.commit()
        assert user.id is not None

        # update
        user.age = 26
        session.commit()

        # delete
        session.delete(user)
        session.commit()

        # flush
        db.flush()

    def test_crud_operations_without_listeners(self, crud_setup: Any) -> None:
        """未注册监听器时 CRUD 操作正常"""
        db, Item = crud_setup

        item = Item(name='Widget', price=9.99)
        item.save()
        assert item.id is not None

        item.price = 19.99
        item.save()

        item.delete()

        db.flush()


# ============================================================================
# EventManager 单元测试
# ============================================================================


class TestEventManagerUnit:
    """EventManager 内部逻辑单元测试"""

    def test_model_events_set(self) -> None:
        """MODEL_EVENTS 包含正确的事件名"""
        assert MODEL_EVENTS == {
            'before_insert', 'after_insert',
            'before_update', 'after_update',
            'before_delete', 'after_delete',
        }

    def test_storage_events_set(self) -> None:
        """STORAGE_EVENTS 包含正确的事件名"""
        assert STORAGE_EVENTS == {
            'before_flush', 'after_flush',
        }

    def test_all_events_is_union(self) -> None:
        """ALL_EVENTS 是 MODEL_EVENTS 和 STORAGE_EVENTS 的并集"""
        assert ALL_EVENTS == MODEL_EVENTS | STORAGE_EVENTS

    def test_dispatch_model_no_listeners(self) -> None:
        """无监听器时 dispatch_model 不报错"""
        em = EventManager()

        class FakeModel:
            pass

        # 不应抛出异常
        em.dispatch_model(FakeModel, 'before_insert', FakeModel())

    def test_dispatch_storage_no_listeners(self) -> None:
        """无监听器时 dispatch_storage 不报错"""
        em = EventManager()

        class FakeStorage:
            pass

        # 不应抛出异常
        em.dispatch_storage(FakeStorage(), 'before_flush')


# ============================================================================
# 完整生命周期测试
# ============================================================================


class TestFullLifecycle:
    """完整生命周期事件顺序测试"""

    def test_session_full_lifecycle_events(self, session_setup: Any) -> None:
        """Session 模式下完整 CRUD 生命周期的事件顺序"""
        db, User, session = session_setup
        events: List[str] = []

        for evt_name in ['before_insert', 'after_insert',
                         'before_update', 'after_update',
                         'before_delete', 'after_delete']:
            event.listen(User, evt_name, lambda inst, e=evt_name: events.append(e))

        # Insert
        user = User(name='Alice', age=25)
        session.add(user)
        session.commit()

        assert events == ['before_insert', 'after_insert']
        events.clear()

        # Update
        user.age = 26
        session.commit()

        assert events == ['before_update', 'after_update']
        events.clear()

        # Delete
        session.delete(user)
        session.commit()

        assert events == ['before_delete', 'after_delete']

    def test_crud_full_lifecycle_events(self, crud_setup: Any) -> None:
        """CRUD 模式下完整生命周期的事件顺序"""
        db, Item = crud_setup
        events: List[str] = []

        for evt_name in ['before_insert', 'after_insert',
                         'before_update', 'after_update',
                         'before_delete', 'after_delete']:
            event.listen(Item, evt_name, lambda inst, e=evt_name: events.append(e))

        # Insert via save
        item = Item(name='Widget', price=9.99)
        item.save()

        assert events == ['before_insert', 'after_insert']
        events.clear()

        # Update via save
        item.price = 19.99
        item.save()

        assert events == ['before_update', 'after_update']
        events.clear()

        # Delete
        item.delete()

        assert events == ['before_delete', 'after_delete']
