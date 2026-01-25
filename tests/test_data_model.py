"""
Pytuck 数据模型独立性测试

测试数据模型作为独立数据容器的特性：
- Session 关闭后仍可访问
- Storage 关闭后仍可访问
- 模型序列化（to_dict, JSON）
- 多个 Session 独立性
"""

import os
import sys
import json
import unittest
from typing import Type

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pytuck import Storage, declarative_base, Session, Column, PureBaseModel, select, insert


class TestSessionCloseAccess(unittest.TestCase):
    """Session 关闭后访问测试"""

    def setUp(self) -> None:
        """测试前设置"""
        self.db = Storage(in_memory=True)
        Base: Type[PureBaseModel] = declarative_base(self.db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)
            age = Column(int)

        self.User = User
        self.session = Session(self.db)

        # 插入测试数据
        stmt = insert(self.User).values(name='Alice', age=20)
        self.session.execute(stmt)
        self.session.commit()

    def tearDown(self) -> None:
        """测试后清理"""
        self.db.close()

    def test_access_after_session_close(self) -> None:
        """测试 Session 关闭后仍可访问对象"""
        # 查询数据
        stmt = select(self.User).where(self.User.name == 'Alice')
        user = self.session.execute(stmt).first()

        # 验证查询成功
        self.assertIsNotNone(user)
        self.assertEqual(user.name, 'Alice')
        self.assertEqual(user.age, 20)

        # 关闭 Session
        self.session.close()

        # Session 关闭后仍可访问
        self.assertEqual(user.name, 'Alice')
        self.assertEqual(user.age, 20)
        self.assertIsNotNone(user.id)

    def test_to_dict_after_session_close(self) -> None:
        """测试 Session 关闭后 to_dict() 仍可用"""
        stmt = select(self.User).where(self.User.name == 'Alice')
        user = self.session.execute(stmt).first()

        # 关闭 Session
        self.session.close()

        # to_dict() 仍可用
        user_dict = user.to_dict()
        self.assertEqual(user_dict['name'], 'Alice')
        self.assertEqual(user_dict['age'], 20)

    def test_multiple_objects_after_close(self) -> None:
        """测试 Session 关闭后访问多个对象"""
        # 插入更多数据
        for name, age in [('Bob', 25), ('Charlie', 30)]:
            stmt = insert(self.User).values(name=name, age=age)
            self.session.execute(stmt)
        self.session.commit()

        # 查询所有
        stmt = select(self.User)
        users = self.session.execute(stmt).all()
        self.assertEqual(len(users), 3)

        # 关闭 Session
        self.session.close()

        # 所有对象仍可访问
        names = [u.name for u in users]
        self.assertEqual(names, ['Alice', 'Bob', 'Charlie'])


class TestStorageCloseAccess(unittest.TestCase):
    """Storage 关闭后访问测试"""

    def test_access_after_storage_close(self) -> None:
        """测试 Storage 关闭后仍可访问对象"""
        db = Storage(in_memory=True)
        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)
            age = Column(int)

        session = Session(db)

        # 插入数据
        stmt = insert(User).values(name='Alice', age=20)
        session.execute(stmt)
        session.commit()

        # 查询数据
        stmt = select(User).where(User.name == 'Alice')
        user = session.execute(stmt).first()

        # 验证查询成功
        self.assertIsNotNone(user)
        self.assertEqual(user.name, 'Alice')

        # 关闭 Session 和 Storage
        session.close()
        db.close()

        # Storage 关闭后仍可访问
        self.assertEqual(user.name, 'Alice')
        self.assertEqual(user.age, 20)
        self.assertEqual(user.to_dict()['name'], 'Alice')


class TestModelSerialization(unittest.TestCase):
    """模型序列化测试"""

    def setUp(self) -> None:
        """测试前设置"""
        self.db = Storage(in_memory=True)
        Base: Type[PureBaseModel] = declarative_base(self.db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)
            age = Column(int)
            email = Column(str, nullable=True)

        self.User = User
        self.session = Session(self.db)

        # 插入测试数据
        stmt = insert(self.User).values(name='Alice', age=20, email='alice@example.com')
        self.session.execute(stmt)
        self.session.commit()

    def tearDown(self) -> None:
        """测试后清理"""
        self.session.close()
        self.db.close()

    def test_to_dict(self) -> None:
        """测试 to_dict() 序列化"""
        stmt = select(self.User).where(self.User.name == 'Alice')
        user = self.session.execute(stmt).first()

        user_dict = user.to_dict()
        self.assertIsInstance(user_dict, dict)
        self.assertEqual(user_dict['name'], 'Alice')
        self.assertEqual(user_dict['age'], 20)
        self.assertEqual(user_dict['email'], 'alice@example.com')
        self.assertIn('id', user_dict)

    def test_json_serialization(self) -> None:
        """测试 JSON 序列化"""
        stmt = select(self.User).where(self.User.name == 'Alice')
        user = self.session.execute(stmt).first()

        # 序列化为 JSON
        user_json = json.dumps(user.to_dict())
        self.assertIsInstance(user_json, str)

        # 反序列化
        user_data = json.loads(user_json)
        self.assertEqual(user_data['name'], 'Alice')
        self.assertEqual(user_data['age'], 20)

    def test_list_serialization(self) -> None:
        """测试列表序列化"""
        # 插入更多数据
        for name, age in [('Bob', 25), ('Charlie', 30)]:
            stmt = insert(self.User).values(name=name, age=age, email=f'{name.lower()}@example.com')
            self.session.execute(stmt)
        self.session.commit()

        # 查询所有
        stmt = select(self.User)
        users = self.session.execute(stmt).all()

        # 序列化列表
        users_list = [u.to_dict() for u in users]
        self.assertEqual(len(users_list), 3)

        # JSON 序列化
        users_json = json.dumps(users_list)
        self.assertIsInstance(users_json, str)

        # 反序列化
        users_data = json.loads(users_json)
        self.assertEqual(len(users_data), 3)
        self.assertEqual(users_data[0]['name'], 'Alice')


class TestMultiSessionIndependence(unittest.TestCase):
    """多 Session 独立性测试"""

    def setUp(self) -> None:
        """测试前设置"""
        self.db = Storage(in_memory=True)
        Base: Type[PureBaseModel] = declarative_base(self.db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)
            age = Column(int)

        self.User = User

        # 插入测试数据
        session = Session(self.db)
        stmt = insert(self.User).values(name='Alice', age=20)
        session.execute(stmt)
        session.commit()
        session.close()

    def tearDown(self) -> None:
        """测试后清理"""
        self.db.close()

    def test_multiple_sessions_independent(self) -> None:
        """测试多个 Session 独立操作"""
        # Session 1：查询数据
        session1 = Session(self.db)
        stmt = select(self.User).where(self.User.name == 'Alice')
        user1 = session1.execute(stmt).first()
        self.assertEqual(user1.name, 'Alice')
        session1.close()

        # Session 2：查询同一数据
        session2 = Session(self.db)
        stmt = select(self.User).where(self.User.name == 'Alice')
        user2 = session2.execute(stmt).first()
        self.assertEqual(user2.name, 'Alice')
        session2.close()

        # 两个 Session 关闭后，数据仍可访问且独立
        self.assertEqual(user1.name, 'Alice')
        self.assertEqual(user2.name, 'Alice')

    def test_session_close_does_not_affect_others(self) -> None:
        """测试 Session 关闭不影响其他对象"""
        # Session 1：查询数据
        session1 = Session(self.db)
        stmt = select(self.User)
        users1 = session1.execute(stmt).all()

        # Session 2：查询数据
        session2 = Session(self.db)
        stmt = select(self.User)
        users2 = session2.execute(stmt).all()

        # 关闭 Session 1
        session1.close()

        # Session 2 的数据仍可访问
        self.assertEqual(len(users2), 1)
        self.assertEqual(users2[0].name, 'Alice')

        # Session 1 的数据也仍可访问
        self.assertEqual(len(users1), 1)
        self.assertEqual(users1[0].name, 'Alice')

        session2.close()


class TestModelAsDataContainer(unittest.TestCase):
    """模型作为数据容器测试"""

    def setUp(self) -> None:
        """测试前设置"""
        self.db = Storage(in_memory=True)
        Base: Type[PureBaseModel] = declarative_base(self.db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)
            age = Column(int)

        self.User = User
        self.session = Session(self.db)

    def tearDown(self) -> None:
        """测试后清理"""
        self.session.close()
        self.db.close()

    def test_pass_model_to_function(self) -> None:
        """测试模型对象可以作为参数传递"""
        def process_user(user: PureBaseModel) -> dict:
            """处理用户数据"""
            return {
                'name': user.name.upper(),
                'age': user.age + 1
            }

        # 插入数据
        stmt = insert(self.User).values(name='Alice', age=20)
        self.session.execute(stmt)
        self.session.commit()

        # 查询数据
        stmt = select(self.User).where(self.User.name == 'Alice')
        user = self.session.execute(stmt).first()

        # 关闭 Session
        self.session.close()

        # 传递给函数处理
        result = process_user(user)
        self.assertEqual(result['name'], 'ALICE')
        self.assertEqual(result['age'], 21)

    def test_store_models_in_list(self) -> None:
        """测试模型对象可以存储在列表中"""
        # 插入数据
        for name, age in [('Alice', 20), ('Bob', 25), ('Charlie', 30)]:
            stmt = insert(self.User).values(name=name, age=age)
            self.session.execute(stmt)
        self.session.commit()

        # 查询所有
        stmt = select(self.User)
        users = self.session.execute(stmt).all()

        # 关闭 Session
        self.session.close()

        # 存储在列表中并操作
        user_list = list(users)
        self.assertEqual(len(user_list), 3)

        # 列表操作
        filtered = [u for u in user_list if u.age >= 25]
        self.assertEqual(len(filtered), 2)
        self.assertEqual(filtered[0].name, 'Bob')

    def test_model_as_api_response(self) -> None:
        """测试模型可以作为 API 响应对象"""
        # 插入数据
        stmt = insert(self.User).values(name='Alice', age=20)
        self.session.execute(stmt)
        self.session.commit()

        # 查询数据
        stmt = select(self.User).where(self.User.name == 'Alice')
        user = self.session.execute(stmt).first()

        # 关闭 Session（模拟请求结束）
        self.session.close()

        # 转换为 API 响应格式
        response = {
            'status': 'success',
            'data': user.to_dict()
        }

        self.assertEqual(response['status'], 'success')
        self.assertEqual(response['data']['name'], 'Alice')
        self.assertEqual(response['data']['age'], 20)


if __name__ == '__main__':
    unittest.main()
