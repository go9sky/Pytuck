"""
Pytuck 关系预取（prefetch）测试

测试 prefetch 的特性：
- 一对多批量预取
- 多对一批量预取
- Select.options 集成
- 边界条件
- CRUD 模式
- 缓存一致性
"""

import os
import sys
import unittest
from typing import Type, List, Optional

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pytuck import (
    Storage, declarative_base, Column, Session,
    CRUDBaseModel, PureBaseModel, prefetch,
    select, insert,
)
from pytuck.core.orm import Relationship


class TestPrefetchOneToMany(unittest.TestCase):
    """一对多预取测试"""

    def setUp(self) -> None:
        self.db = Storage(in_memory=True)
        Base: Type[CRUDBaseModel] = declarative_base(self.db, crud=True)

        class Order(Base):
            __tablename__ = 'orders'
            id = Column(int, primary_key=True)
            user_id = Column(int)
            amount = Column(float)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)
            orders: List[Order] = Relationship(Order, foreign_key='user_id')  # type: ignore

        self.User = User
        self.Order = Order

        # 插入测试数据
        self.alice = User.create(name='Alice')
        self.bob = User.create(name='Bob')
        self.charlie = User.create(name='Charlie')  # 无订单

        Order.create(user_id=self.alice.id, amount=100.0)
        Order.create(user_id=self.alice.id, amount=200.0)
        Order.create(user_id=self.bob.id, amount=300.0)

    def tearDown(self) -> None:
        self.db.close()

    def test_prefetch_one_to_many(self) -> None:
        """测试一对多批量预取"""
        users = self.User.all()
        prefetch(users, 'orders')

        # Alice 有 2 个订单
        alice = [u for u in users if u.name == 'Alice'][0]
        self.assertEqual(len(alice.orders), 2)
        amounts = sorted([o.amount for o in alice.orders])
        self.assertEqual(amounts, [100.0, 200.0])

        # Bob 有 1 个订单
        bob = [u for u in users if u.name == 'Bob'][0]
        self.assertEqual(len(bob.orders), 1)
        self.assertEqual(bob.orders[0].amount, 300.0)

        # Charlie 无订单
        charlie = [u for u in users if u.name == 'Charlie'][0]
        self.assertEqual(len(charlie.orders), 0)

    def test_prefetch_multiple_owners(self) -> None:
        """测试多个 owner 各自获得正确的关联数据"""
        users = self.User.all()
        prefetch(users, 'orders')

        for user in users:
            orders = user.orders
            for order in orders:
                self.assertEqual(order.user_id, user.id)

    def test_prefetch_then_access_relationship(self) -> None:
        """测试预取后访问关系属性不再触发额外查询"""
        users = self.User.all()
        prefetch(users, 'orders')

        # 访问缓存的关系 — 应直接返回缓存的值
        for user in users:
            cache_key = '_cached_orders'
            self.assertTrue(hasattr(user, cache_key))
            # 第二次访问也应该返回相同的缓存
            orders1 = user.orders
            orders2 = user.orders
            self.assertIs(orders1, orders2)


class TestPrefetchManyToOne(unittest.TestCase):
    """多对一预取测试"""

    def setUp(self) -> None:
        self.db = Storage(in_memory=True)
        Base: Type[CRUDBaseModel] = declarative_base(self.db, crud=True)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        class Order(Base):
            __tablename__ = 'orders'
            id = Column(int, primary_key=True)
            user_id = Column(int)
            amount = Column(float)
            user: Optional[User] = Relationship(User, foreign_key='user_id')  # type: ignore

        self.User = User
        self.Order = Order

        alice = User.create(name='Alice')
        bob = User.create(name='Bob')

        Order.create(user_id=alice.id, amount=100.0)
        Order.create(user_id=alice.id, amount=200.0)
        Order.create(user_id=bob.id, amount=300.0)
        Order.create(user_id=None, amount=400.0)  # 无关联用户

    def tearDown(self) -> None:
        self.db.close()

    def test_prefetch_many_to_one(self) -> None:
        """测试多对一批量预取"""
        orders = self.Order.all()
        prefetch(orders, 'user')

        for order in orders:
            if order.user_id is not None:
                self.assertIsNotNone(order.user)
                self.assertEqual(order.user.id, order.user_id)
            else:
                self.assertIsNone(order.user)

    def test_prefetch_many_to_one_dedup(self) -> None:
        """测试多对一预取去重（多个订单指向同一用户）"""
        orders = self.Order.all()
        prefetch(orders, 'user')

        # Alice 的两个订单应各自有 user 属性
        alice_orders = [o for o in orders if o.user is not None and o.user.name == 'Alice']
        self.assertEqual(len(alice_orders), 2)

    def test_prefetch_many_to_one_null_fk(self) -> None:
        """测试外键为 None 的情况"""
        orders = self.Order.all()
        prefetch(orders, 'user')

        null_fk_orders = [o for o in orders if o.user_id is None]
        self.assertEqual(len(null_fk_orders), 1)
        self.assertIsNone(null_fk_orders[0].user)


class TestPrefetchSelectOptions(unittest.TestCase):
    """Select.options 集成测试"""

    def setUp(self) -> None:
        self.db = Storage(in_memory=True)
        Base: Type[PureBaseModel] = declarative_base(self.db)

        class Order(Base):
            __tablename__ = 'orders'
            id = Column(int, primary_key=True)
            user_id = Column(int)
            amount = Column(float)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)
            orders: List[Order] = Relationship(Order, foreign_key='user_id')  # type: ignore

        self.User = User
        self.Order = Order
        self.session = Session(self.db)

        # 插入数据
        self.session.execute(insert(User).values(name='Alice'))
        self.session.execute(insert(User).values(name='Bob'))
        self.session.commit()

        self.session.execute(insert(Order).values(user_id=1, amount=100.0))
        self.session.execute(insert(Order).values(user_id=1, amount=200.0))
        self.session.execute(insert(Order).values(user_id=2, amount=300.0))
        self.session.commit()

    def tearDown(self) -> None:
        self.db.close()

    def test_select_options_prefetch(self) -> None:
        """测试 select().options(prefetch('orders'))"""
        stmt = select(self.User).options(prefetch('orders'))
        result = self.session.execute(stmt)
        users = result.all()

        self.assertEqual(len(users), 2)

        alice = [u for u in users if u.name == 'Alice'][0]
        self.assertEqual(len(alice.orders), 2)

        bob = [u for u in users if u.name == 'Bob'][0]
        self.assertEqual(len(bob.orders), 1)

    def test_select_options_with_where(self) -> None:
        """测试 select().where().options(prefetch())"""
        stmt = select(self.User).where(self.User.name == 'Alice').options(prefetch('orders'))
        result = self.session.execute(stmt)
        users = result.all()

        self.assertEqual(len(users), 1)
        self.assertEqual(users[0].name, 'Alice')
        self.assertEqual(len(users[0].orders), 2)


class TestPrefetchSession(unittest.TestCase):
    """通过 Session 路径的完整测试"""

    def setUp(self) -> None:
        self.db = Storage(in_memory=True)
        Base: Type[PureBaseModel] = declarative_base(self.db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        class Order(Base):
            __tablename__ = 'orders'
            id = Column(int, primary_key=True)
            user_id = Column(int)
            amount = Column(float)
            user: Optional[User] = Relationship(User, foreign_key='user_id')  # type: ignore

        # 添加一对多关系
        User.orders = Relationship(Order, foreign_key='user_id')
        User.__relationships__['orders'] = User.orders  # type: ignore
        User.orders.__set_name__(User, 'orders')

        self.User = User
        self.Order = Order
        self.session = Session(self.db)

        # 插入数据
        self.session.execute(insert(User).values(name='Alice'))
        self.session.execute(insert(User).values(name='Bob'))
        self.session.commit()

        self.session.execute(insert(Order).values(user_id=1, amount=100.0))
        self.session.execute(insert(Order).values(user_id=1, amount=200.0))
        self.session.execute(insert(Order).values(user_id=2, amount=300.0))
        self.session.commit()

    def tearDown(self) -> None:
        self.db.close()

    def test_session_prefetch_one_to_many(self) -> None:
        """通过 Session + Select 的一对多预取"""
        users = self.session.execute(select(self.User)).all()
        prefetch(users, 'orders')

        alice = [u for u in users if u.name == 'Alice'][0]
        self.assertEqual(len(alice.orders), 2)

        bob = [u for u in users if u.name == 'Bob'][0]
        self.assertEqual(len(bob.orders), 1)

    def test_session_prefetch_many_to_one(self) -> None:
        """通过 Session + Select 的多对一预取"""
        orders = self.session.execute(select(self.Order)).all()
        prefetch(orders, 'user')

        for order in orders:
            self.assertIsNotNone(order.user)
            self.assertEqual(order.user.id, order.user_id)


class TestPrefetchEdgeCases(unittest.TestCase):
    """边界条件测试"""

    def setUp(self) -> None:
        self.db = Storage(in_memory=True)
        Base: Type[CRUDBaseModel] = declarative_base(self.db, crud=True)

        class Order(Base):
            __tablename__ = 'orders'
            id = Column(int, primary_key=True)
            user_id = Column(int)
            amount = Column(float)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)
            orders: List[Order] = Relationship(Order, foreign_key='user_id')  # type: ignore

        self.User = User
        self.Order = Order

    def tearDown(self) -> None:
        self.db.close()

    def test_prefetch_empty_list(self) -> None:
        """空实例列表不报错"""
        prefetch([], 'orders')  # 不应抛出异常

    def test_prefetch_no_matching_records(self) -> None:
        """无匹配记录时缓存为空列表"""
        user = self.User.create(name='Lonely')
        users = [user]
        prefetch(users, 'orders')

        self.assertEqual(user.orders, [])

    def test_prefetch_invalid_relationship_name(self) -> None:
        """无效关系名抛出 ValueError"""
        user = self.User.create(name='Alice')
        with self.assertRaises(ValueError) as ctx:
            prefetch([user], 'nonexistent')
        self.assertIn('nonexistent', str(ctx.exception))

    def test_prefetch_already_cached(self) -> None:
        """预取覆盖已有缓存"""
        user = self.User.create(name='Alice')
        self.Order.create(user_id=user.id, amount=100.0)

        # 手动设置缓存
        setattr(user, '_cached_orders', ['fake_cache'])

        # 预取应覆盖
        prefetch([user], 'orders')
        self.assertNotEqual(user.orders, ['fake_cache'])
        self.assertEqual(len(user.orders), 1)
        self.assertEqual(user.orders[0].amount, 100.0)

    def test_prefetch_no_args(self) -> None:
        """无参数调用 prefetch 抛出 ValueError"""
        with self.assertRaises(ValueError):
            prefetch()  # type: ignore

    def test_prefetch_missing_rel_names(self) -> None:
        """只传实例不传关系名抛出 ValueError"""
        user = self.User.create(name='Alice')
        with self.assertRaises(ValueError):
            prefetch([user])  # type: ignore

    def test_prefetch_returns_prefetch_option(self) -> None:
        """字符串参数返回 PrefetchOption"""
        result = prefetch('orders')
        from pytuck.core.prefetch import PrefetchOption
        self.assertIsInstance(result, PrefetchOption)
        self.assertEqual(result.rel_names, ('orders',))

    def test_prefetch_option_multiple_rels(self) -> None:
        """多个关系名的 PrefetchOption"""
        result = prefetch('orders', 'profile')
        from pytuck.core.prefetch import PrefetchOption
        self.assertIsInstance(result, PrefetchOption)
        self.assertEqual(result.rel_names, ('orders', 'profile'))


class TestPrefetchMultipleRelationships(unittest.TestCase):
    """多关系预取测试"""

    def setUp(self) -> None:
        self.db = Storage(in_memory=True)
        Base: Type[CRUDBaseModel] = declarative_base(self.db, crud=True)

        class Order(Base):
            __tablename__ = 'orders'
            id = Column(int, primary_key=True)
            user_id = Column(int)
            amount = Column(float)

        class Profile(Base):
            __tablename__ = 'profiles'
            id = Column(int, primary_key=True)
            user_id = Column(int)
            bio = Column(str)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)
            orders: List[Order] = Relationship(Order, foreign_key='user_id')  # type: ignore
            profiles: List[Profile] = Relationship(Profile, foreign_key='user_id')  # type: ignore

        self.User = User
        self.Order = Order
        self.Profile = Profile

        alice = User.create(name='Alice')
        Order.create(user_id=alice.id, amount=100.0)
        Order.create(user_id=alice.id, amount=200.0)
        Profile.create(user_id=alice.id, bio='Hello World')

    def tearDown(self) -> None:
        self.db.close()

    def test_prefetch_multiple_relationships(self) -> None:
        """同时预取多个关系"""
        users = self.User.all()
        prefetch(users, 'orders', 'profiles')

        alice = users[0]
        self.assertEqual(len(alice.orders), 2)
        self.assertEqual(len(alice.profiles), 1)
        self.assertEqual(alice.profiles[0].bio, 'Hello World')


class TestPrefetchCRUDMode(unittest.TestCase):
    """CRUDBaseModel 预取测试"""

    def setUp(self) -> None:
        self.db = Storage(in_memory=True)
        Base: Type[CRUDBaseModel] = declarative_base(self.db, crud=True)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        class Order(Base):
            __tablename__ = 'orders'
            id = Column(int, primary_key=True)
            user_id = Column(int)
            amount = Column(float)
            user: Optional[User] = Relationship(User, foreign_key='user_id')  # type: ignore

        # 添加一对多关系
        User.orders = Relationship(Order, foreign_key='user_id')
        User.__relationships__['orders'] = User.orders  # type: ignore
        User.orders.__set_name__(User, 'orders')

        self.User = User
        self.Order = Order

        alice = User.create(name='Alice')
        bob = User.create(name='Bob')
        Order.create(user_id=alice.id, amount=100.0)
        Order.create(user_id=alice.id, amount=200.0)
        Order.create(user_id=bob.id, amount=300.0)

    def tearDown(self) -> None:
        self.db.close()

    def test_crud_prefetch_one_to_many(self) -> None:
        """CRUDBaseModel 的一对多预取"""
        users = self.User.all()
        prefetch(users, 'orders')

        for user in users:
            if user.name == 'Alice':
                self.assertEqual(len(user.orders), 2)
            elif user.name == 'Bob':
                self.assertEqual(len(user.orders), 1)

    def test_crud_prefetch_many_to_one(self) -> None:
        """CRUDBaseModel 的多对一预取"""
        orders = self.Order.all()
        prefetch(orders, 'user')

        for order in orders:
            self.assertIsNotNone(order.user)
            self.assertEqual(order.user.id, order.user_id)


class TestPrefetchStringTargetModel(unittest.TestCase):
    """字符串目标模型预取测试（通过表名引用）"""

    def setUp(self) -> None:
        self.db = Storage(in_memory=True)
        Base: Type[CRUDBaseModel] = declarative_base(self.db, crud=True)

        class Order(Base):
            __tablename__ = 'orders'
            id = Column(int, primary_key=True)
            user_id = Column(int)
            amount = Column(float)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)
            # 使用字符串引用目标模型（表名）
            orders: List[Order] = Relationship('orders', foreign_key='user_id')  # type: ignore

        self.User = User
        self.Order = Order

        alice = User.create(name='Alice')
        Order.create(user_id=alice.id, amount=100.0)
        Order.create(user_id=alice.id, amount=200.0)

    def tearDown(self) -> None:
        self.db.close()

    def test_prefetch_with_string_target(self) -> None:
        """字符串目标模型的预取"""
        users = self.User.all()
        prefetch(users, 'orders')

        self.assertEqual(len(users[0].orders), 2)


class TestPrefetchSomeWithNoRelated(unittest.TestCase):
    """部分实例无关联数据"""

    def setUp(self) -> None:
        self.db = Storage(in_memory=True)
        Base: Type[CRUDBaseModel] = declarative_base(self.db, crud=True)

        class Order(Base):
            __tablename__ = 'orders'
            id = Column(int, primary_key=True)
            user_id = Column(int)
            amount = Column(float)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)
            orders: List[Order] = Relationship(Order, foreign_key='user_id')  # type: ignore

        self.User = User
        self.Order = Order

        alice = User.create(name='Alice')
        User.create(name='Bob')  # 无订单
        User.create(name='Charlie')  # 无订单
        Order.create(user_id=alice.id, amount=100.0)

    def tearDown(self) -> None:
        self.db.close()

    def test_some_with_no_related(self) -> None:
        """部分实例无关联数据"""
        users = self.User.all()
        prefetch(users, 'orders')

        alice = [u for u in users if u.name == 'Alice'][0]
        bob = [u for u in users if u.name == 'Bob'][0]
        charlie = [u for u in users if u.name == 'Charlie'][0]

        self.assertEqual(len(alice.orders), 1)
        self.assertEqual(len(bob.orders), 0)
        self.assertEqual(len(charlie.orders), 0)


if __name__ == '__main__':
    unittest.main()
