"""
Query 高级功能测试

测试方法：
- 边界值法：offset/limit 边界条件
- 组合测试：多种条件组合
- 场景设计：链式调用

覆盖范围：
- offset/limit 组合
- 多列排序
- 链式调用
- 复杂查询条件
"""

import pytest
from typing import Type

from pytuck import (
    Storage, Session, Column, declarative_base,
    PureBaseModel, select, insert,
)


class TestOffsetLimit:
    """offset/limit 组合测试"""

    def test_limit_only(self, tmp_path):
        """只使用 limit"""
        db_path = tmp_path / "test.db"
        db = Storage(file_path=str(db_path))

        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        session = Session(db)
        for i in range(10):
            session.execute(insert(User).values(id=i+1, name=f'User{i}'))
        session.commit()

        result = session.execute(select(User).limit(3))
        users = result.all()

        assert len(users) == 3

        session.close()
        db.close()

    def test_offset_only(self, tmp_path):
        """只使用 offset"""
        db_path = tmp_path / "test.db"
        db = Storage(file_path=str(db_path))

        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        session = Session(db)
        for i in range(10):
            session.execute(insert(User).values(id=i+1, name=f'User{i}'))
        session.commit()

        result = session.execute(select(User).offset(5))
        users = result.all()

        assert len(users) == 5  # 剩余 5 条

        session.close()
        db.close()

    def test_offset_with_limit(self, tmp_path):
        """offset 和 limit 组合"""
        db_path = tmp_path / "test.db"
        db = Storage(file_path=str(db_path))

        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        session = Session(db)
        for i in range(10):
            session.execute(insert(User).values(id=i+1, name=f'User{i}'))
        session.commit()

        result = session.execute(select(User).offset(2).limit(3))
        users = result.all()

        assert len(users) == 3

        session.close()
        db.close()

    def test_offset_exceeds_total(self, tmp_path):
        """offset 超过总数"""
        db_path = tmp_path / "test.db"
        db = Storage(file_path=str(db_path))

        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        session = Session(db)
        for i in range(5):
            session.execute(insert(User).values(id=i+1, name=f'User{i}'))
        session.commit()

        result = session.execute(select(User).offset(10))
        users = result.all()

        assert len(users) == 0

        session.close()
        db.close()

    def test_limit_zero(self, tmp_path):
        """limit 为 0"""
        db_path = tmp_path / "test.db"
        db = Storage(file_path=str(db_path))

        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        session = Session(db)
        session.execute(insert(User).values(id=1, name='Alice'))
        session.commit()

        result = session.execute(select(User).limit(0))
        users = result.all()

        assert len(users) == 0

        session.close()
        db.close()

    def test_limit_larger_than_total(self, tmp_path):
        """limit 大于总数"""
        db_path = tmp_path / "test.db"
        db = Storage(file_path=str(db_path))

        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        session = Session(db)
        for i in range(3):
            session.execute(insert(User).values(id=i+1, name=f'User{i}'))
        session.commit()

        result = session.execute(select(User).limit(100))
        users = result.all()

        assert len(users) == 3

        session.close()
        db.close()


class TestOrderBy:
    """排序测试"""

    def test_order_by_single_column_asc(self, tmp_path):
        """单列升序排序"""
        db_path = tmp_path / "test.db"
        db = Storage(file_path=str(db_path))

        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)
            age = Column(int)

        session = Session(db)
        session.execute(insert(User).values(id=1, name='Charlie', age=30))
        session.execute(insert(User).values(id=2, name='Alice', age=25))
        session.execute(insert(User).values(id=3, name='Bob', age=35))
        session.commit()

        result = session.execute(select(User).order_by('age'))
        users = result.all()

        assert users[0].age == 25
        assert users[1].age == 30
        assert users[2].age == 35

        session.close()
        db.close()

    def test_order_by_single_column_desc(self, tmp_path):
        """单列降序排序"""
        db_path = tmp_path / "test.db"
        db = Storage(file_path=str(db_path))

        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)
            age = Column(int)

        session = Session(db)
        session.execute(insert(User).values(id=1, name='Charlie', age=30))
        session.execute(insert(User).values(id=2, name='Alice', age=25))
        session.execute(insert(User).values(id=3, name='Bob', age=35))
        session.commit()

        result = session.execute(select(User).order_by('age', desc=True))
        users = result.all()

        assert users[0].age == 35
        assert users[1].age == 30
        assert users[2].age == 25

        session.close()
        db.close()

    def test_order_by_two_columns(self, tmp_path):
        """多列排序"""
        db_path = tmp_path / "test.db"
        db = Storage(file_path=str(db_path))

        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)
            department = Column(str)
            age = Column(int)

        session = Session(db)
        session.execute(insert(User).values(id=1, name='Alice', department='IT', age=30))
        session.execute(insert(User).values(id=2, name='Bob', department='HR', age=25))
        session.execute(insert(User).values(id=3, name='Charlie', department='IT', age=25))
        session.execute(insert(User).values(id=4, name='David', department='HR', age=35))
        session.commit()

        # 先按部门升序，再按年龄升序
        result = session.execute(
            select(User).order_by('department').order_by('age')
        )
        users = result.all()

        # HR 部门先，然后是 IT 部门
        # HR: Bob(25), David(35)
        # IT: Charlie(25), Alice(30)
        assert users[0].name == 'Bob'
        assert users[1].name == 'David'
        assert users[2].name == 'Charlie'
        assert users[3].name == 'Alice'

        session.close()
        db.close()

    def test_order_by_mixed_asc_desc(self, tmp_path):
        """混合升降序排序"""
        db_path = tmp_path / "test.db"
        db = Storage(file_path=str(db_path))

        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)
            department = Column(str)
            age = Column(int)

        session = Session(db)
        session.execute(insert(User).values(id=1, name='Alice', department='IT', age=30))
        session.execute(insert(User).values(id=2, name='Bob', department='HR', age=25))
        session.execute(insert(User).values(id=3, name='Charlie', department='IT', age=25))
        session.execute(insert(User).values(id=4, name='David', department='HR', age=35))
        session.commit()

        # 先按部门升序，再按年龄降序
        result = session.execute(
            select(User).order_by('department').order_by('age', desc=True)
        )
        users = result.all()

        # HR: David(35), Bob(25)
        # IT: Alice(30), Charlie(25)
        assert users[0].name == 'David'
        assert users[1].name == 'Bob'
        assert users[2].name == 'Alice'
        assert users[3].name == 'Charlie'

        session.close()
        db.close()

    def test_order_by_with_filter(self, tmp_path):
        """排序与过滤组合"""
        db_path = tmp_path / "test.db"
        db = Storage(file_path=str(db_path))

        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)
            age = Column(int)

        session = Session(db)
        session.execute(insert(User).values(id=1, name='Alice', age=30))
        session.execute(insert(User).values(id=2, name='Bob', age=25))
        session.execute(insert(User).values(id=3, name='Charlie', age=35))
        session.execute(insert(User).values(id=4, name='David', age=28))
        session.commit()

        # 过滤 age >= 28，按 age 升序
        result = session.execute(
            select(User).where(User.age >= 28).order_by('age')
        )
        users = result.all()

        assert len(users) == 3
        assert users[0].name == 'David'  # 28
        assert users[1].name == 'Alice'  # 30
        assert users[2].name == 'Charlie'  # 35

        session.close()
        db.close()


class TestQueryChaining:
    """链式调用测试"""

    def test_filter_filter_chaining(self, tmp_path):
        """多个 filter 链式调用（AND 语义）"""
        db_path = tmp_path / "test.db"
        db = Storage(file_path=str(db_path))

        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)
            age = Column(int)
            active = Column(bool)

        session = Session(db)
        session.execute(insert(User).values(id=1, name='Alice', age=30, active=True))
        session.execute(insert(User).values(id=2, name='Bob', age=25, active=True))
        session.execute(insert(User).values(id=3, name='Charlie', age=35, active=False))
        session.execute(insert(User).values(id=4, name='David', age=28, active=True))
        session.commit()

        # 多个 where 条件（AND）
        result = session.execute(
            select(User).where(User.age >= 25).where(User.active == True)
        )
        users = result.all()

        # Alice(30, True), Bob(25, True), David(28, True)
        assert len(users) == 3
        names = [u.name for u in users]
        assert 'Charlie' not in names

        session.close()
        db.close()

    def test_filter_order_limit_offset(self, tmp_path):
        """filter + order + limit + offset 组合"""
        db_path = tmp_path / "test.db"
        db = Storage(file_path=str(db_path))

        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)
            age = Column(int)

        session = Session(db)
        for i in range(10):
            session.execute(insert(User).values(id=i+1, name=f'User{i}', age=20+i))
        session.commit()

        # age >= 23，按 age 降序，跳过 2 个，取 3 个
        result = session.execute(
            select(User)
            .where(User.age >= 23)
            .order_by('age', desc=True)
            .offset(2)
            .limit(3)
        )
        users = result.all()

        # age >= 23: 23,24,25,26,27,28,29 (7 人)
        # 降序: 29,28,27,26,25,24,23
        # offset(2): 27,26,25,24,23
        # limit(3): 27,26,25
        assert len(users) == 3
        assert users[0].age == 27
        assert users[1].age == 26
        assert users[2].age == 25

        session.close()
        db.close()

    def test_method_order_independence(self, tmp_path):
        """方法调用顺序应该不影响结果"""
        db_path = tmp_path / "test.db"
        db = Storage(file_path=str(db_path))

        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)
            age = Column(int)

        session = Session(db)
        for i in range(5):
            session.execute(insert(User).values(id=i+1, name=f'User{i}', age=20+i))
        session.commit()

        # 顺序 1: where -> order_by -> limit
        result1 = session.execute(
            select(User).where(User.age >= 22).order_by('age').limit(2)
        )
        users1 = result1.all()

        # 顺序 2: limit -> where -> order_by
        result2 = session.execute(
            select(User).limit(2).where(User.age >= 22).order_by('age')
        )
        users2 = result2.all()

        # 结果应该相同
        assert len(users1) == len(users2)
        for u1, u2 in zip(users1, users2):
            assert u1.age == u2.age

        session.close()
        db.close()


class TestComplexQueries:
    """复杂查询测试"""

    def test_in_operator(self, tmp_path):
        """IN 操作符"""
        db_path = tmp_path / "test.db"
        db = Storage(file_path=str(db_path))

        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)
            department = Column(str)

        session = Session(db)
        session.execute(insert(User).values(id=1, name='Alice', department='IT'))
        session.execute(insert(User).values(id=2, name='Bob', department='HR'))
        session.execute(insert(User).values(id=3, name='Charlie', department='Finance'))
        session.execute(insert(User).values(id=4, name='David', department='IT'))
        session.commit()

        # 使用 IN 操作符
        result = session.execute(
            select(User).where(User.department.in_(['IT', 'HR']))
        )
        users = result.all()

        assert len(users) == 3
        departments = [u.department for u in users]
        assert 'Finance' not in departments

        session.close()
        db.close()

    def test_not_equal_operator(self, tmp_path):
        """不等于操作符"""
        db_path = tmp_path / "test.db"
        db = Storage(file_path=str(db_path))

        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)
            status = Column(str)

        session = Session(db)
        session.execute(insert(User).values(id=1, name='Alice', status='active'))
        session.execute(insert(User).values(id=2, name='Bob', status='inactive'))
        session.execute(insert(User).values(id=3, name='Charlie', status='active'))
        session.commit()

        result = session.execute(
            select(User).where(User.status != 'inactive')
        )
        users = result.all()

        assert len(users) == 2
        for u in users:
            assert u.status == 'active'

        session.close()
        db.close()

    def test_greater_less_operators(self, tmp_path):
        """大于小于操作符"""
        db_path = tmp_path / "test.db"
        db = Storage(file_path=str(db_path))

        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)
            score = Column(int)

        session = Session(db)
        session.execute(insert(User).values(id=1, name='Alice', score=85))
        session.execute(insert(User).values(id=2, name='Bob', score=90))
        session.execute(insert(User).values(id=3, name='Charlie', score=75))
        session.execute(insert(User).values(id=4, name='David', score=95))
        session.commit()

        # score > 80 AND score < 95
        result = session.execute(
            select(User).where(User.score > 80).where(User.score < 95)
        )
        users = result.all()

        assert len(users) == 2
        scores = [u.score for u in users]
        assert 85 in scores
        assert 90 in scores

        session.close()
        db.close()

    def test_first_on_ordered_query(self, tmp_path):
        """排序后取第一个"""
        db_path = tmp_path / "test.db"
        db = Storage(file_path=str(db_path))

        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)
            score = Column(int)

        session = Session(db)
        session.execute(insert(User).values(id=1, name='Alice', score=85))
        session.execute(insert(User).values(id=2, name='Bob', score=90))
        session.execute(insert(User).values(id=3, name='Charlie', score=95))
        session.commit()

        # 获取分数最高的用户
        result = session.execute(
            select(User).order_by('score', desc=True)
        )
        top_user = result.first()

        assert top_user is not None
        assert top_user.name == 'Charlie'
        assert top_user.score == 95

        session.close()
        db.close()
