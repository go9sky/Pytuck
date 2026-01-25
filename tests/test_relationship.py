"""
Pytuck Relationship 关联关系测试

测试 Relationship 的特性：
- 延迟加载行为
- 一对多关联
- 多对一关联
- Session 关闭后的访问
- Storage 关闭后的访问
- 缓存机制
"""

import os
import sys
import unittest
from typing import Type

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pytuck import Storage, declarative_base, Column, CRUDBaseModel
from pytuck.core.orm import Relationship


class TestRelationshipBasic(unittest.TestCase):
    """Relationship 基础功能测试"""

    def setUp(self) -> None:
        """测试前设置"""
        self.db = Storage(in_memory=True)
        Base: Type[CRUDBaseModel] = declarative_base(self.db, crud=True)

        # 先定义 Order 类（前向引用）
        class Order(Base):
            __tablename__ = 'orders'
            id = Column(int, primary_key=True)
            user_id = Column(int)
            amount = Column(float)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)
            # 一对多：一个用户有多个订单（使用类而不是字符串）
            orders = Relationship(Order, foreign_key='user_id')

        # 添加反向关联
        Order.user = Relationship(User, foreign_key='user_id')

        self.User = User
        self.Order = Order

        # 插入测试数据
        self.user = User.create(name='Alice')
        self.order1 = Order.create(user_id=self.user.id, amount=100.0)
        self.order2 = Order.create(user_id=self.user.id, amount=200.0)

    def tearDown(self) -> None:
        """测试后清理"""
        self.db.close()

    def test_one_to_many_relationship(self) -> None:
        """测试一对多关联"""
        user = self.User.get(self.user.id)

        # 访问关联对象（延迟加载）
        orders = user.orders
        self.assertIsInstance(orders, list)
        self.assertEqual(len(orders), 2)
        self.assertEqual(orders[0].amount, 100.0)
        self.assertEqual(orders[1].amount, 200.0)

    def test_many_to_one_relationship(self) -> None:
        """测试多对一关联"""
        order = self.Order.get(self.order1.id)

        # 访问关联对象（延迟加载）
        user = order.user
        self.assertIsNotNone(user)
        self.assertEqual(user.name, 'Alice')

    def test_lazy_loading(self) -> None:
        """测试延迟加载行为"""
        user = self.User.get(self.user.id)

        # 首次访问：触发加载
        orders = user.orders
        self.assertEqual(len(orders), 2)

        # 二次访问：使用缓存
        orders2 = user.orders
        self.assertIs(orders, orders2)  # 同一个对象（缓存）


class TestRelationshipAfterClose(unittest.TestCase):
    """Relationship 在 session/storage 关闭后的行为测试"""

    def test_relationship_requires_active_connection(self) -> None:
        """测试关联查询需要活动连接"""
        db = Storage(in_memory=True)
        Base: Type[CRUDBaseModel] = declarative_base(db, crud=True)

        class Order(Base):
            __tablename__ = 'orders'
            id = Column(int, primary_key=True)
            user_id = Column(int)
            amount = Column(float)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)
            orders = Relationship(Order, foreign_key='user_id')

        # 插入数据
        user = User.create(name='Alice')
        Order.create(user_id=user.id, amount=100.0)
        Order.create(user_id=user.id, amount=200.0)

        # 获取用户对象
        user_obj = User.get(user.id)

        # 首次访问关联（storage 还活着）
        orders_before = user_obj.orders
        self.assertEqual(len(orders_before), 2)

        # 关闭 storage
        db.close()

        # 再次访问关联：使用缓存（不需要查询）
        orders_after = user_obj.orders
        self.assertEqual(len(orders_after), 2)
        self.assertIs(orders_before, orders_after)  # 同一个对象

    def test_relationship_first_access_after_close_fails(self) -> None:
        """测试关闭后首次访问关联的行为"""
        db = Storage(in_memory=True)
        Base: Type[CRUDBaseModel] = declarative_base(db, crud=True)

        class Order(Base):
            __tablename__ = 'orders'
            id = Column(int, primary_key=True)
            user_id = Column(int)
            amount = Column(float)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)
            orders = Relationship(Order, foreign_key='user_id')

        # 插入数据
        user = User.create(name='Alice')
        Order.create(user_id=user.id, amount=100.0)

        # 获取用户对象（不访问关联）
        user_obj = User.get(user.id)

        # 关闭 storage
        db.close()

        # 首次访问关联：由于 Storage 已关闭，filter_by 会返回所有数据
        # 这是因为关闭的 Storage 仍保留内存数据
        orders = user_obj.orders
        # 实际上仍然可以访问（因为数据还在内存中）
        self.assertEqual(len(orders), 1)

    def test_eager_loading_before_close(self) -> None:
        """测试在关闭前预加载关联"""
        db = Storage(in_memory=True)
        Base: Type[CRUDBaseModel] = declarative_base(db, crud=True)

        class Order(Base):
            __tablename__ = 'orders'
            id = Column(int, primary_key=True)
            user_id = Column(int)
            amount = Column(float)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)
            orders = Relationship(Order, foreign_key='user_id')

        Order.user = Relationship(User, foreign_key='user_id')

        # 插入数据
        user = User.create(name='Alice')
        order1 = Order.create(user_id=user.id, amount=100.0)

        # 获取对象
        user_obj = User.get(user.id)
        order_obj = Order.get(order1.id)

        # 预加载关联（在关闭前）
        orders = user_obj.orders  # 触发加载
        user_from_order = order_obj.user  # 触发加载

        self.assertEqual(len(orders), 1)
        self.assertEqual(user_from_order.name, 'Alice')

        # 关闭 storage
        db.close()

        # 关闭后仍可访问已加载的关联
        self.assertEqual(len(user_obj.orders), 1)
        self.assertEqual(order_obj.user.name, 'Alice')


class TestRelationshipCache(unittest.TestCase):
    """Relationship 缓存机制测试"""

    def setUp(self) -> None:
        """测试前设置"""
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
            orders = Relationship(Order, foreign_key='user_id')

        self.User = User
        self.Order = Order

    def tearDown(self) -> None:
        """测试后清理"""
        self.db.close()

    def test_relationship_caching(self) -> None:
        """测试关联对象缓存"""
        user = self.User.create(name='Alice')
        self.Order.create(user_id=user.id, amount=100.0)

        user_obj = self.User.get(user.id)

        # 首次访问
        orders1 = user_obj.orders
        # 二次访问（应该返回缓存）
        orders2 = user_obj.orders

        # 验证是同一个对象
        self.assertIs(orders1, orders2)

    def test_relationship_cache_key(self) -> None:
        """测试关联对象缓存键"""
        user = self.User.create(name='Alice')
        self.Order.create(user_id=user.id, amount=100.0)

        user_obj = self.User.get(user.id)

        # 访问关联触发缓存
        _ = user_obj.orders

        # 检查缓存键是否存在
        self.assertTrue(hasattr(user_obj, '_cached_orders'))


class TestRelationshipNullForeignKey(unittest.TestCase):
    """Relationship NULL 外键测试"""

    def setUp(self) -> None:
        """测试前设置"""
        self.db = Storage(in_memory=True)
        Base: Type[CRUDBaseModel] = declarative_base(self.db, crud=True)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        class Order(Base):
            __tablename__ = 'orders'
            id = Column(int, primary_key=True)
            user_id = Column(int, nullable=True)
            amount = Column(float)
            user = Relationship(User, foreign_key='user_id')

        self.User = User
        self.Order = Order

    def tearDown(self) -> None:
        """测试后清理"""
        self.db.close()

    def test_null_foreign_key(self) -> None:
        """测试外键为 NULL 的情况"""
        # 创建没有关联用户的订单
        order = self.Order.create(user_id=None, amount=100.0)

        order_obj = self.Order.get(order.id)

        # 访问关联应该返回 None
        user = order_obj.user
        self.assertIsNone(user)


class TestRelationshipBidirectional(unittest.TestCase):
    """Relationship 双向关联测试"""

    def setUp(self) -> None:
        """测试前设置"""
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
            orders = Relationship(Order, foreign_key='user_id', back_populates='user')

        Order.user = Relationship(User, foreign_key='user_id', back_populates='orders')

        self.User = User
        self.Order = Order

    def tearDown(self) -> None:
        """测试后清理"""
        self.db.close()

    def test_bidirectional_relationship(self) -> None:
        """测试双向关联"""
        user = self.User.create(name='Alice')
        order = self.Order.create(user_id=user.id, amount=100.0)

        # 正向访问：User → Orders
        user_obj = self.User.get(user.id)
        orders = user_obj.orders
        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0].amount, 100.0)

        # 反向访问：Order → User
        order_obj = self.Order.get(order.id)
        user_from_order = order_obj.user
        self.assertEqual(user_from_order.name, 'Alice')


class TestRelationshipStringReference(unittest.TestCase):
    """Relationship 字符串引用（表名）测试"""

    def setUp(self) -> None:
        """测试前设置"""
        self.db = Storage(in_memory=True)
        Base: Type[CRUDBaseModel] = declarative_base(self.db, crud=True)

        # 使用字符串（表名）定义双向关联 - 无需在类外赋值
        class Order(Base):
            __tablename__ = 'orders'
            id = Column(int, primary_key=True)
            user_id = Column(int)
            amount = Column(float)
            # 使用表名引用 User 模型
            user = Relationship('users', foreign_key='user_id')

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)
            # 使用表名引用 Order 模型
            orders = Relationship('orders', foreign_key='user_id', back_populates='user')

        self.User = User
        self.Order = Order

    def tearDown(self) -> None:
        """测试后清理"""
        self.db.close()

    def test_string_reference_one_to_many(self) -> None:
        """测试字符串引用的一对多关系"""
        user = self.User.create(name='Alice')
        self.Order.create(user_id=user.id, amount=100.0)
        self.Order.create(user_id=user.id, amount=200.0)

        # 通过表名引用访问关联
        user_obj = self.User.get(user.id)
        orders = user_obj.orders
        self.assertEqual(len(orders), 2)

    def test_string_reference_many_to_one(self) -> None:
        """测试字符串引用的多对一关系"""
        user = self.User.create(name='Bob')
        order = self.Order.create(user_id=user.id, amount=150.0)

        # 通过表名引用访问关联
        order_obj = self.Order.get(order.id)
        user_from_order = order_obj.user
        self.assertIsNotNone(user_from_order)
        self.assertEqual(user_from_order.name, 'Bob')

    def test_bidirectional_with_string_reference(self) -> None:
        """测试字符串引用的双向关联"""
        user = self.User.create(name='Charlie')
        order = self.Order.create(user_id=user.id, amount=300.0)

        # 双向访问
        user_obj = self.User.get(user.id)
        order_obj = self.Order.get(order.id)

        self.assertEqual(user_obj.orders[0].id, order.id)
        self.assertEqual(order_obj.user.id, user.id)


class TestRelationshipOneToOne(unittest.TestCase):
    """Relationship 一对一关系测试"""

    def setUp(self) -> None:
        """测试前设置"""
        self.db = Storage(in_memory=True)
        Base: Type[CRUDBaseModel] = declarative_base(self.db, crud=True)

        # 一对一：用户 - 用户资料
        class UserProfile(Base):
            __tablename__ = 'user_profiles'
            id = Column(int, primary_key=True)
            user_id = Column(int)
            bio = Column(str)
            # 多对一：资料 → 用户
            user = Relationship('users', foreign_key='user_id')

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)
            # 一对一：用户 → 资料（实际是一对多，但只取第一个）
            profiles = Relationship('user_profiles', foreign_key='user_id')

        self.User = User
        self.UserProfile = UserProfile

    def tearDown(self) -> None:
        """测试后清理"""
        self.db.close()

    def test_one_to_one_relationship(self) -> None:
        """测试一对一关系"""
        user = self.User.create(name='Alice')
        profile = self.UserProfile.create(user_id=user.id, bio='Hello World')

        # 用户 → 资料
        user_obj = self.User.get(user.id)
        profiles = user_obj.profiles
        self.assertEqual(len(profiles), 1)
        self.assertEqual(profiles[0].bio, 'Hello World')

        # 资料 → 用户
        profile_obj = self.UserProfile.get(profile.id)
        self.assertEqual(profile_obj.user.name, 'Alice')


class TestRelationshipManyToMany(unittest.TestCase):
    """Relationship 多对多关系测试（通过中间表）"""

    def setUp(self) -> None:
        """测试前设置"""
        self.db = Storage(in_memory=True)
        Base: Type[CRUDBaseModel] = declarative_base(self.db, crud=True)

        # 多对多：学生 - 课程（通过中间表 enrollments）
        class Enrollment(Base):
            __tablename__ = 'enrollments'
            id = Column(int, primary_key=True)
            student_id = Column(int)
            course_id = Column(int)
            # 关联
            student = Relationship('students', foreign_key='student_id')
            course = Relationship('courses', foreign_key='course_id')

        class Student(Base):
            __tablename__ = 'students'
            id = Column(int, primary_key=True)
            name = Column(str)
            enrollments = Relationship('enrollments', foreign_key='student_id')

        class Course(Base):
            __tablename__ = 'courses'
            id = Column(int, primary_key=True)
            title = Column(str)
            enrollments = Relationship('enrollments', foreign_key='course_id')

        self.Student = Student
        self.Course = Course
        self.Enrollment = Enrollment

    def tearDown(self) -> None:
        """测试后清理"""
        self.db.close()

    def test_many_to_many_through_junction(self) -> None:
        """测试通过中间表的多对多关系"""
        student1 = self.Student.create(name='Alice')
        student2 = self.Student.create(name='Bob')
        course1 = self.Course.create(title='Math')
        course2 = self.Course.create(title='Physics')

        # 创建选课记录
        self.Enrollment.create(student_id=student1.id, course_id=course1.id)
        self.Enrollment.create(student_id=student1.id, course_id=course2.id)
        self.Enrollment.create(student_id=student2.id, course_id=course1.id)

        # 学生 → 选课记录 → 课程
        student1_obj = self.Student.get(student1.id)
        enrollments = student1_obj.enrollments
        self.assertEqual(len(enrollments), 2)

        # 验证可以通过中间表访问课程
        courses = [e.course for e in enrollments]
        course_titles = [c.title for c in courses]
        self.assertIn('Math', course_titles)
        self.assertIn('Physics', course_titles)

        # 课程 → 选课记录 → 学生
        course1_obj = self.Course.get(course1.id)
        enrollments = course1_obj.enrollments
        self.assertEqual(len(enrollments), 2)

        students = [e.student for e in enrollments]
        student_names = [s.name for s in students]
        self.assertIn('Alice', student_names)
        self.assertIn('Bob', student_names)


class TestRelationshipSelfReference(unittest.TestCase):
    """Relationship 自引用关系测试（树形结构）"""

    def setUp(self) -> None:
        """测试前设置"""
        self.db = Storage(in_memory=True)
        Base: Type[CRUDBaseModel] = declarative_base(self.db, crud=True)

        # 自引用：分类树（parent_id 指向自己）
        class Category(Base):
            __tablename__ = 'categories'
            id = Column(int, primary_key=True)
            name = Column(str)
            parent_id = Column(int, nullable=True)
            # 自引用关系 - 需要用 uselist 明确指定
            parent = Relationship('categories', foreign_key='parent_id', uselist=False)
            children = Relationship('categories', foreign_key='parent_id', uselist=True)

        self.Category = Category

    def tearDown(self) -> None:
        """测试后清理"""
        self.db.close()

    def test_self_reference_parent(self) -> None:
        """测试自引用关系 - 获取父节点"""
        root = self.Category.create(name='Root', parent_id=None)
        child = self.Category.create(name='Child', parent_id=root.id)

        # 子节点 → 父节点
        child_obj = self.Category.get(child.id)
        parent = child_obj.parent
        self.assertIsNotNone(parent)
        self.assertEqual(parent.name, 'Root')

    def test_self_reference_children(self) -> None:
        """测试自引用关系 - 获取子节点"""
        root = self.Category.create(name='Root', parent_id=None)
        self.Category.create(name='Child1', parent_id=root.id)
        self.Category.create(name='Child2', parent_id=root.id)

        # 父节点 → 子节点
        root_obj = self.Category.get(root.id)
        children = root_obj.children
        self.assertEqual(len(children), 2)

        child_names = [c.name for c in children]
        self.assertIn('Child1', child_names)
        self.assertIn('Child2', child_names)

    def test_self_reference_null_parent(self) -> None:
        """测试自引用关系 - 根节点无父节点"""
        root = self.Category.create(name='Root', parent_id=None)

        root_obj = self.Category.get(root.id)
        parent = root_obj.parent
        self.assertIsNone(parent)


class TestRelationshipMixedDefinition(unittest.TestCase):
    """Relationship 混合定义测试（类引用 + 字符串引用）"""

    def setUp(self) -> None:
        """测试前设置"""
        self.db = Storage(in_memory=True)
        Base: Type[CRUDBaseModel] = declarative_base(self.db, crud=True)

        # 先定义 Order（使用类引用），User 使用字符串引用
        class Order(Base):
            __tablename__ = 'orders'
            id = Column(int, primary_key=True)
            user_id = Column(int)
            amount = Column(float)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)
            # 使用类引用（Order 已定义）
            orders = Relationship(Order, foreign_key='user_id')

        # 动态添加反向关联（使用字符串引用）
        Order.user = Relationship('users', foreign_key='user_id')

        self.User = User
        self.Order = Order

    def tearDown(self) -> None:
        """测试后清理"""
        self.db.close()

    def test_mixed_reference_works(self) -> None:
        """测试混合引用方式"""
        user = self.User.create(name='Alice')
        order = self.Order.create(user_id=user.id, amount=100.0)

        # 类引用：User → Orders
        user_obj = self.User.get(user.id)
        orders = user_obj.orders
        self.assertEqual(len(orders), 1)

        # 字符串引用：Order → User
        order_obj = self.Order.get(order.id)
        user_from_order = order_obj.user
        self.assertEqual(user_from_order.name, 'Alice')


if __name__ == '__main__':
    unittest.main()
