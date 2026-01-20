"""
Pytuck Session API 测试

测试 SQLAlchemy 2.0 风格的 Session + Statement API：
- declarative_base() 创建纯模型基类
- Session 管理所有 CRUD 操作
- execute() 风格的 IO 操作
- select, insert, update, delete 语句构建器
- 查询表达式和 filter_by 语法
"""

import os
import sys
import unittest
from typing import Type

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pytuck import (
    Storage, Session, Column,
    declarative_base, PureBaseModel,
    select, insert, update, delete,
)


class TestSessionAPI(unittest.TestCase):
    """Session API 基础测试"""

    def setUp(self) -> None:
        """测试前设置"""
        self.db = Storage(in_memory=True)
        self.Base: Type[PureBaseModel] = declarative_base(self.db)

        class User(self.Base):
            __tablename__ = 'users'
            id = Column('id', int, primary_key=True)
            name = Column('name', str, nullable=False)
            age = Column('age', int)
            email = Column('email', str, nullable=True)

        self.User = User
        self.session = Session(self.db)

    def tearDown(self) -> None:
        """测试后清理"""
        self.session.close()
        self.db.close()

    def test_insert_single(self) -> None:
        """测试插入单条记录"""
        stmt = insert(self.User).values(name='Alice', age=20, email='alice@example.com')
        result = self.session.execute(stmt)
        self.session.commit()

        self.assertIsNotNone(result.inserted_primary_key)
        self.assertEqual(result.inserted_primary_key, 1)

    def test_insert_batch(self) -> None:
        """测试批量插入"""
        data = [
            {'name': 'Alice', 'age': 20},
            {'name': 'Bob', 'age': 25},
            {'name': 'Charlie', 'age': 19},
        ]

        for item in data:
            stmt = insert(self.User).values(**item)
            self.session.execute(stmt)
        self.session.commit()

        # 验证插入
        stmt = select(self.User)
        result = self.session.execute(stmt)
        users = result.scalars().all()
        self.assertEqual(len(users), 3)

    def test_select_all(self) -> None:
        """测试查询所有记录"""
        # 插入数据
        for name, age in [('Alice', 20), ('Bob', 25), ('Charlie', 19)]:
            stmt = insert(self.User).values(name=name, age=age)
            self.session.execute(stmt)
        self.session.commit()

        # 查询所有
        stmt = select(self.User)
        result = self.session.execute(stmt)
        users = result.scalars().all()

        self.assertEqual(len(users), 3)
        self.assertEqual([u.name for u in users], ['Alice', 'Bob', 'Charlie'])

    def test_select_where(self) -> None:
        """测试 where 条件查询"""
        # 插入数据
        for name, age in [('Alice', 20), ('Bob', 25), ('Charlie', 19)]:
            stmt = insert(self.User).values(name=name, age=age)
            self.session.execute(stmt)
        self.session.commit()

        # where 查询（年龄 >= 20）
        stmt = select(self.User).where(self.User.age >= 20)
        result = self.session.execute(stmt)
        adults = result.scalars().all()

        self.assertEqual(len(adults), 2)
        self.assertIn('Alice', [u.name for u in adults])
        self.assertIn('Bob', [u.name for u in adults])

    def test_select_filter_by(self) -> None:
        """测试 filter_by 等值查询"""
        # 插入数据
        stmt = insert(self.User).values(name='Alice', age=20, email='alice@example.com')
        self.session.execute(stmt)
        self.session.commit()

        # filter_by 查询
        stmt = select(self.User).filter_by(name='Alice')
        result = self.session.execute(stmt)
        alice = result.scalars().first()

        self.assertIsNotNone(alice)
        self.assertEqual(alice.name, 'Alice')
        self.assertEqual(alice.age, 20)

    def test_select_mixed_where_filter_by(self) -> None:
        """测试混合 where 和 filter_by"""
        # 插入数据
        for name, age in [('Alice', 20), ('Bob', 25), ('Alice', 30)]:
            stmt = insert(self.User).values(name=name, age=age)
            self.session.execute(stmt)
        self.session.commit()

        # 混合查询
        stmt = select(self.User).filter_by(name='Alice').where(self.User.age >= 25)
        result = self.session.execute(stmt)
        users = result.scalars().all()

        self.assertEqual(len(users), 1)
        self.assertEqual(users[0].age, 30)

    def test_select_multiple_conditions(self) -> None:
        """测试多条件查询（AND）"""
        # 插入数据
        for name, age in [('Alice', 20), ('Bob', 25), ('Charlie', 30)]:
            stmt = insert(self.User).values(name=name, age=age)
            self.session.execute(stmt)
        self.session.commit()

        # 多条件查询
        stmt = select(self.User).where(self.User.age >= 20, self.User.age < 30)
        result = self.session.execute(stmt)
        users = result.scalars().all()

        self.assertEqual(len(users), 2)
        self.assertEqual({u.name for u in users}, {'Alice', 'Bob'})

    def test_select_order_by(self) -> None:
        """测试排序查询"""
        # 插入数据
        for name, age in [('Charlie', 30), ('Alice', 20), ('Bob', 25)]:
            stmt = insert(self.User).values(name=name, age=age)
            self.session.execute(stmt)
        self.session.commit()

        # 按年龄升序
        stmt = select(self.User).order_by('age')
        result = self.session.execute(stmt)
        users = result.scalars().all()
        self.assertEqual([u.name for u in users], ['Alice', 'Bob', 'Charlie'])

        # 按年龄降序
        stmt = select(self.User).order_by('age', desc=True)
        result = self.session.execute(stmt)
        users = result.scalars().all()
        self.assertEqual([u.name for u in users], ['Charlie', 'Bob', 'Alice'])

    def test_select_limit_offset(self) -> None:
        """测试限制和偏移"""
        # 插入数据
        for i in range(5):
            stmt = insert(self.User).values(name=f'User{i}', age=20 + i)
            self.session.execute(stmt)
        self.session.commit()

        # Limit
        stmt = select(self.User).limit(2)
        result = self.session.execute(stmt)
        users = result.scalars().all()
        self.assertEqual(len(users), 2)

        # Offset
        stmt = select(self.User).offset(2)
        result = self.session.execute(stmt)
        users = result.scalars().all()
        self.assertEqual(len(users), 3)

        # Limit + Offset
        stmt = select(self.User).offset(1).limit(2)
        result = self.session.execute(stmt)
        users = result.scalars().all()
        self.assertEqual(len(users), 2)
        self.assertEqual(users[0].name, 'User1')

    def test_update_single(self) -> None:
        """测试更新单条记录"""
        # 插入数据
        stmt = insert(self.User).values(name='Alice', age=20)
        self.session.execute(stmt)
        self.session.commit()

        # 更新
        stmt = update(self.User).where(self.User.name == 'Alice').values(age=21)
        result = self.session.execute(stmt)
        self.session.commit()

        self.assertEqual(result.rowcount(), 1)

        # 验证更新
        stmt = select(self.User).filter_by(name='Alice')
        result = self.session.execute(stmt)
        alice = result.scalars().first()
        self.assertEqual(alice.age, 21)

    def test_update_batch(self) -> None:
        """测试批量更新"""
        # 插入数据
        for name, age in [('Alice', 18), ('Bob', 25), ('Charlie', 19)]:
            stmt = insert(self.User).values(name=name, age=age)
            self.session.execute(stmt)
        self.session.commit()

        # 批量更新
        stmt = update(self.User).where(self.User.age < 20).values(age=20)
        result = self.session.execute(stmt)
        self.session.commit()

        self.assertEqual(result.rowcount(), 2)  # Alice 和 Charlie

    def test_delete_single(self) -> None:
        """测试删除单条记录"""
        # 插入数据
        for name in ['Alice', 'Bob', 'Charlie']:
            stmt = insert(self.User).values(name=name, age=20)
            self.session.execute(stmt)
        self.session.commit()

        # 删除
        stmt = delete(self.User).where(self.User.name == 'Bob')
        result = self.session.execute(stmt)
        self.session.commit()

        self.assertEqual(result.rowcount(), 1)

        # 验证删除
        stmt = select(self.User)
        result = self.session.execute(stmt)
        users = result.scalars().all()
        self.assertEqual(len(users), 2)
        self.assertEqual({u.name for u in users}, {'Alice', 'Charlie'})

    def test_delete_batch(self) -> None:
        """测试批量删除"""
        # 插入数据
        for name, age in [('Alice', 20), ('Bob', 25), ('Charlie', 30)]:
            stmt = insert(self.User).values(name=name, age=age)
            self.session.execute(stmt)
        self.session.commit()

        # 批量删除
        stmt = delete(self.User).where(self.User.age >= 25)
        result = self.session.execute(stmt)
        self.session.commit()

        self.assertEqual(result.rowcount(), 2)  # Bob 和 Charlie


class TestResultFormats(unittest.TestCase):
    """Result 对象格式测试"""

    def setUp(self) -> None:
        """测试前设置"""
        self.db = Storage(in_memory=True)
        Base: Type[PureBaseModel] = declarative_base(self.db)

        class User(Base):
            __tablename__ = 'users'
            id = Column('id', int, primary_key=True)
            name = Column('name', str)
            age = Column('age', int)

        self.User = User
        self.session = Session(self.db)

        # 插入测试数据
        for name, age in [('Alice', 20), ('Bob', 25)]:
            stmt = insert(User).values(name=name, age=age)
            self.session.execute(stmt)
        self.session.commit()

    def tearDown(self) -> None:
        """测试后清理"""
        self.session.close()
        self.db.close()

    def test_scalars_all(self) -> None:
        """测试 scalars().all() - 返回模型实例列表"""
        stmt = select(self.User)
        result = self.session.execute(stmt)
        users = result.scalars().all()

        self.assertEqual(len(users), 2)
        self.assertIsInstance(users[0], self.User)
        self.assertEqual(users[0].name, 'Alice')

    def test_scalars_first(self) -> None:
        """测试 scalars().first() - 返回第一个实例"""
        stmt = select(self.User).where(self.User.name == 'Alice')
        result = self.session.execute(stmt)
        alice = result.scalars().first()

        self.assertIsNotNone(alice)
        self.assertEqual(alice.name, 'Alice')
        self.assertEqual(alice.age, 20)

    def test_scalars_one(self) -> None:
        """测试 scalars().one() - 必须恰好一条"""
        stmt = select(self.User).where(self.User.name == 'Alice')
        result = self.session.execute(stmt)
        alice = result.scalars().one()

        self.assertEqual(alice.name, 'Alice')

        # 测试多条记录抛出异常
        stmt = select(self.User)
        result = self.session.execute(stmt)
        with self.assertRaises(ValueError):
            result.scalars().one()

    def test_all_rows(self) -> None:
        """测试 all() - 返回 Row 对象列表"""
        stmt = select(self.User)
        result = self.session.execute(stmt)
        rows = result.all()

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0].name, 'Alice')
        self.assertEqual(rows[0]['name'], 'Alice')

    def test_fetchall(self) -> None:
        """测试 fetchall() - 返回字典列表"""
        stmt = select(self.User)
        result = self.session.execute(stmt)
        dicts = result.fetchall()

        self.assertEqual(len(dicts), 2)
        self.assertIsInstance(dicts[0], dict)
        self.assertEqual(dicts[0]['name'], 'Alice')


class TestRelations(unittest.TestCase):
    """关联关系测试"""

    def setUp(self) -> None:
        """测试前设置"""
        self.db = Storage(in_memory=True)
        Base: Type[PureBaseModel] = declarative_base(self.db)

        class Class(Base):
            __tablename__ = 'classes'
            id = Column('id', int, primary_key=True)
            name = Column('name', str, nullable=False)

        class Student(Base):
            __tablename__ = 'students'
            id = Column('id', int, primary_key=True)
            name = Column('name', str, nullable=False)
            age = Column('age', int)
            class_id = Column('class_id', int, foreign_key=('classes', 'id'))

        self.Class = Class
        self.Student = Student
        self.session = Session(self.db)

    def tearDown(self) -> None:
        """测试后清理"""
        self.session.close()
        self.db.close()

    def test_foreign_key_insert(self) -> None:
        """测试外键插入"""
        # 插入班级
        stmt = insert(self.Class).values(name='Class A')
        result = self.session.execute(stmt)
        class_id = result.inserted_primary_key
        self.session.commit()

        # 插入学生
        stmt = insert(self.Student).values(name='Alice', age=20, class_id=class_id)
        self.session.execute(stmt)
        self.session.commit()

        # 验证
        stmt = select(self.Student)
        result = self.session.execute(stmt)
        students = result.scalars().all()
        self.assertEqual(len(students), 1)
        self.assertEqual(students[0].class_id, class_id)

    def test_join_query(self) -> None:
        """测试关联查询（手动 JOIN）"""
        # 插入数据
        stmt = insert(self.Class).values(name='Class A')
        result = self.session.execute(stmt)
        class_a_id = result.inserted_primary_key
        self.session.commit()

        stmt = insert(self.Class).values(name='Class B')
        result = self.session.execute(stmt)
        class_b_id = result.inserted_primary_key
        self.session.commit()

        for name, class_id in [('Alice', class_a_id), ('Bob', class_a_id), ('Charlie', class_b_id)]:
            stmt = insert(self.Student).values(name=name, age=20, class_id=class_id)
            self.session.execute(stmt)
        self.session.commit()

        # 查询 Class A 的学生
        stmt = select(self.Student).where(self.Student.class_id == class_a_id)
        result = self.session.execute(stmt)
        students = result.scalars().all()

        self.assertEqual(len(students), 2)
        self.assertEqual({s.name for s in students}, {'Alice', 'Bob'})


if __name__ == '__main__':
    unittest.main()
