"""
Pytuck Active Record 模式测试

测试 CRUDBaseModel 的功能：
- declarative_base(db, crud=True) 创建 Active Record 基类
- create, save, delete, refresh 方法
- get, filter, filter_by, all 查询方法
- 链式查询和排序
"""

import os
import sys
import unittest
from typing import Type

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pytuck import Storage, declarative_base, Column, CRUDBaseModel


class TestActiveRecordBasic(unittest.TestCase):
    """Active Record 基础功能测试"""

    def setUp(self) -> None:
        """测试前设置"""
        self.db = Storage(in_memory=True)
        Base: Type[CRUDBaseModel] = declarative_base(self.db, crud=True)

        class User(Base):
            __tablename__ = 'users'
            id = Column('id', int, primary_key=True)
            name = Column('name', str, nullable=False)
            age = Column('age', int)
            email = Column('email', str, nullable=True)

        self.User = User

    def tearDown(self) -> None:
        """测试后清理"""
        self.db.close()

    def test_create(self) -> None:
        """测试 create 方法"""
        user = self.User.create(name='Alice', age=20, email='alice@example.com')

        self.assertIsNotNone(user.id)
        self.assertEqual(user.name, 'Alice')
        self.assertEqual(user.age, 20)
        self.assertEqual(user.email, 'alice@example.com')

    def test_save_new(self) -> None:
        """测试 save 新记录"""
        user = self.User(name='Bob', age=25)
        user.save()

        self.assertIsNotNone(user.id)

        # 验证保存
        loaded = self.User.get(user.id)
        self.assertEqual(loaded.name, 'Bob')

    def test_save_update(self) -> None:
        """测试 save 更新记录"""
        user = self.User.create(name='Alice', age=20)
        original_id = user.id

        # 修改并保存
        user.age = 21
        user.email = 'alice@example.com'
        user.save()

        # 验证更新
        self.assertEqual(user.id, original_id)
        loaded = self.User.get(user.id)
        self.assertEqual(loaded.age, 21)
        self.assertEqual(loaded.email, 'alice@example.com')

    def test_delete(self) -> None:
        """测试 delete 方法"""
        user = self.User.create(name='Alice', age=20)
        user_id = user.id

        # 删除
        user.delete()

        # 验证删除
        loaded = self.User.get(user_id)
        self.assertIsNone(loaded)

    def test_refresh(self) -> None:
        """测试 refresh 方法"""
        user = self.User.create(name='Alice', age=20)

        # 通过另一个实例修改
        user2 = self.User.get(user.id)
        user2.age = 25
        user2.save()

        # 刷新原实例
        user.refresh()
        self.assertEqual(user.age, 25)


class TestActiveRecordQuery(unittest.TestCase):
    """Active Record 查询功能测试"""

    def setUp(self) -> None:
        """测试前设置"""
        self.db = Storage(in_memory=True)
        Base: Type[CRUDBaseModel] = declarative_base(self.db, crud=True)

        class User(Base):
            __tablename__ = 'users'
            id = Column('id', int, primary_key=True)
            name = Column('name', str, nullable=False)
            age = Column('age', int)
            active = Column('active', bool)

        self.User = User

        # 插入测试数据
        self.User.create(name='Alice', age=20, active=True)
        self.User.create(name='Bob', age=25, active=False)
        self.User.create(name='Charlie', age=19, active=True)
        self.User.create(name='David', age=30, active=True)

    def tearDown(self) -> None:
        """测试后清理"""
        self.db.close()

    def test_get(self) -> None:
        """测试 get 按主键查询"""
        user = self.User.get(1)

        self.assertIsNotNone(user)
        self.assertEqual(user.name, 'Alice')
        self.assertEqual(user.id, 1)

        # 不存在的记录
        user = self.User.get(999)
        self.assertIsNone(user)

    def test_all(self) -> None:
        """测试 all 获取所有记录"""
        users = self.User.all()

        self.assertEqual(len(users), 4)
        self.assertEqual({u.name for u in users}, {'Alice', 'Bob', 'Charlie', 'David'})

    def test_filter(self) -> None:
        """测试 filter 条件查询"""
        # 单条件
        users = self.User.filter(self.User.age >= 25).all()
        self.assertEqual(len(users), 2)
        self.assertEqual({u.name for u in users}, {'Bob', 'David'})

        # 多条件（链式）
        users = self.User.filter(self.User.age >= 20).filter(self.User.age < 30).all()
        self.assertEqual(len(users), 2)
        self.assertEqual({u.name for u in users}, {'Alice', 'Bob'})

    def test_filter_by(self) -> None:
        """测试 filter_by 等值查询"""
        # 单条件
        users = self.User.filter_by(name='Alice').all()
        self.assertEqual(len(users), 1)
        self.assertEqual(users[0].name, 'Alice')

        # 多条件
        users = self.User.filter_by(active=True).all()
        self.assertEqual(len(users), 3)

    def test_first(self) -> None:
        """测试 first 返回第一条"""
        user = self.User.filter(self.User.age >= 0).first()
        self.assertIsNotNone(user)
        self.assertEqual(user.name, 'Alice')  # 第一条记录

        # 无结果
        user = self.User.filter(self.User.age > 100).first()
        self.assertIsNone(user)

    def test_count(self) -> None:
        """测试 count 统计"""
        count = self.User.filter(self.User.active == True).count()
        self.assertEqual(count, 3)

        count = self.User.filter(self.User.age >= 25).count()
        self.assertEqual(count, 2)

    def test_order_by(self) -> None:
        """测试 order_by 排序"""
        # 升序
        users = self.User.filter(self.User.age >= 0).order_by('age').all()
        self.assertEqual([u.name for u in users], ['Charlie', 'Alice', 'Bob', 'David'])

        # 降序
        users = self.User.filter(self.User.age >= 0).order_by('age', desc=True).all()
        self.assertEqual([u.name for u in users], ['David', 'Bob', 'Alice', 'Charlie'])

    def test_limit(self) -> None:
        """测试 limit 限制数量"""
        users = self.User.filter(self.User.age >= 0).limit(2).all()
        self.assertEqual(len(users), 2)

    def test_offset(self) -> None:
        """测试 offset 偏移"""
        users = self.User.filter(self.User.age >= 0).offset(2).all()
        self.assertEqual(len(users), 2)

    def test_chain_query(self) -> None:
        """测试链式查询"""
        users = (self.User
                 .filter(self.User.active == True)
                 .filter(self.User.age >= 20)
                 .order_by('age')
                 .limit(2)
                 .all())

        self.assertEqual(len(users), 2)
        self.assertEqual(users[0].name, 'Alice')
        self.assertEqual(users[1].name, 'David')


class TestActiveRecordComparison(unittest.TestCase):
    """Active Record 比较操作符测试"""

    def setUp(self) -> None:
        """测试前设置"""
        self.db = Storage(in_memory=True)
        Base: Type[CRUDBaseModel] = declarative_base(self.db, crud=True)

        class User(Base):
            __tablename__ = 'users'
            id = Column('id', int, primary_key=True)
            name = Column('name', str)
            age = Column('age', int)

        self.User = User

        # 插入测试数据
        for name, age in [('Alice', 20), ('Bob', 25), ('Charlie', 30)]:
            self.User.create(name=name, age=age)

    def tearDown(self) -> None:
        """测试后清理"""
        self.db.close()

    def test_eq(self) -> None:
        """测试 == 操作符"""
        users = self.User.filter(self.User.age == 25).all()
        self.assertEqual(len(users), 1)
        self.assertEqual(users[0].name, 'Bob')

    def test_ne(self) -> None:
        """测试 != 操作符"""
        users = self.User.filter(self.User.name != 'Alice').all()
        self.assertEqual(len(users), 2)
        self.assertEqual({u.name for u in users}, {'Bob', 'Charlie'})

    def test_gt(self) -> None:
        """测试 > 操作符"""
        users = self.User.filter(self.User.age > 25).all()
        self.assertEqual(len(users), 1)
        self.assertEqual(users[0].name, 'Charlie')

    def test_ge(self) -> None:
        """测试 >= 操作符"""
        users = self.User.filter(self.User.age >= 25).all()
        self.assertEqual(len(users), 2)
        self.assertEqual({u.name for u in users}, {'Bob', 'Charlie'})

    def test_lt(self) -> None:
        """测试 < 操作符"""
        users = self.User.filter(self.User.age < 25).all()
        self.assertEqual(len(users), 1)
        self.assertEqual(users[0].name, 'Alice')

    def test_le(self) -> None:
        """测试 <= 操作符"""
        users = self.User.filter(self.User.age <= 25).all()
        self.assertEqual(len(users), 2)
        self.assertEqual({u.name for u in users}, {'Alice', 'Bob'})

    def test_in(self) -> None:
        """测试 IN 操作符"""
        users = self.User.filter(self.User.age.in_([20, 30])).all()
        self.assertEqual(len(users), 2)
        self.assertEqual({u.name for u in users}, {'Alice', 'Charlie'})


class TestActiveRecordToDict(unittest.TestCase):
    """Active Record to_dict 方法测试"""

    def setUp(self) -> None:
        """测试前设置"""
        self.db = Storage(in_memory=True)
        Base: Type[CRUDBaseModel] = declarative_base(self.db, crud=True)

        class User(Base):
            __tablename__ = 'users'
            id = Column('id', int, primary_key=True)
            name = Column('name', str)
            age = Column('age', int)
            email = Column('email', str, nullable=True)

        self.User = User

    def tearDown(self) -> None:
        """测试后清理"""
        self.db.close()

    def test_to_dict(self) -> None:
        """测试 to_dict 转换为字典"""
        user = self.User.create(name='Alice', age=20, email='alice@example.com')
        user_dict = user.to_dict()

        self.assertIsInstance(user_dict, dict)
        self.assertEqual(user_dict['name'], 'Alice')
        self.assertEqual(user_dict['age'], 20)
        self.assertEqual(user_dict['email'], 'alice@example.com')
        self.assertIn('id', user_dict)

    def test_to_dict_with_none(self) -> None:
        """测试 to_dict 包含 None 值"""
        user = self.User.create(name='Bob', age=25, email=None)
        user_dict = user.to_dict()

        self.assertIsNone(user_dict['email'])


if __name__ == '__main__':
    unittest.main()
