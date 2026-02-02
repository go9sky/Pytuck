"""
Result/CursorResult 行为测试

测试方法：
- 边界值法：空结果集、单条、多条
- 等价类划分：SELECT 与 CUD 操作
- 错误推断：不支持的操作调用

覆盖范围：
- Result 的 all/first/one/one_or_none/rowcount 方法
- CursorResult 的 rowcount/inserted_primary_key 属性
- 空结果集行为
- 迭代行为
- 非 SELECT 操作的限制
"""

import pytest
from typing import Type

from pytuck import (
    Storage, Session, Column, declarative_base,
    PureBaseModel, select, insert, update, delete,
    Result, CursorResult,
    QueryError, UnsupportedOperationError,
)


class TestResultEmptyBehavior:
    """空结果集行为测试"""

    def test_all_returns_empty_list(self, tmp_path):
        """all() 返回空列表"""
        db_path = tmp_path / "test.db"
        db = Storage(file_path=str(db_path))

        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        session = Session(db)
        result = session.execute(select(User))

        assert result.all() == []
        assert isinstance(result.all(), list)

        session.close()
        db.close()

    def test_first_returns_none(self, tmp_path):
        """first() 返回 None"""
        db_path = tmp_path / "test.db"
        db = Storage(file_path=str(db_path))

        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        session = Session(db)
        result = session.execute(select(User))

        assert result.first() is None

        session.close()
        db.close()

    def test_one_raises_on_empty(self, tmp_path):
        """one() 在空结果时抛出 QueryError"""
        db_path = tmp_path / "test.db"
        db = Storage(file_path=str(db_path))

        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        session = Session(db)
        result = session.execute(select(User))

        with pytest.raises(QueryError) as exc_info:
            result.one()

        assert "Expected one result, got 0" in str(exc_info.value)

        session.close()
        db.close()

    def test_one_or_none_returns_none(self, tmp_path):
        """one_or_none() 返回 None"""
        db_path = tmp_path / "test.db"
        db = Storage(file_path=str(db_path))

        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        session = Session(db)
        result = session.execute(select(User))

        assert result.one_or_none() is None

        session.close()
        db.close()

    def test_rowcount_on_empty(self, tmp_path):
        """空结果集的 rowcount() 返回 0"""
        db_path = tmp_path / "test.db"
        db = Storage(file_path=str(db_path))

        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        session = Session(db)
        result = session.execute(select(User))

        assert result.rowcount() == 0

        session.close()
        db.close()


class TestResultSingleRecord:
    """单条记录结果测试"""

    def test_all_returns_single_item_list(self, tmp_path):
        """all() 返回单元素列表"""
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

        result = session.execute(select(User))
        users = result.all()

        assert len(users) == 1
        assert users[0].name == 'Alice'

        session.close()
        db.close()

    def test_first_returns_instance(self, tmp_path):
        """first() 返回模型实例"""
        db_path = tmp_path / "test.db"
        db = Storage(file_path=str(db_path))

        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        session = Session(db)
        session.execute(insert(User).values(id=1, name='Bob'))
        session.commit()

        result = session.execute(select(User))
        user = result.first()

        assert user is not None
        assert user.name == 'Bob'

        session.close()
        db.close()

    def test_one_returns_instance(self, tmp_path):
        """one() 返回唯一的模型实例"""
        db_path = tmp_path / "test.db"
        db = Storage(file_path=str(db_path))

        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        session = Session(db)
        session.execute(insert(User).values(id=1, name='Charlie'))
        session.commit()

        result = session.execute(select(User))
        user = result.one()

        assert user.name == 'Charlie'

        session.close()
        db.close()

    def test_one_or_none_returns_instance(self, tmp_path):
        """one_or_none() 返回唯一的模型实例"""
        db_path = tmp_path / "test.db"
        db = Storage(file_path=str(db_path))

        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        session = Session(db)
        session.execute(insert(User).values(id=1, name='David'))
        session.commit()

        result = session.execute(select(User))
        user = result.one_or_none()

        assert user is not None
        assert user.name == 'David'

        session.close()
        db.close()


class TestResultMultipleRecords:
    """多条记录结果测试"""

    def test_all_returns_multiple(self, tmp_path):
        """all() 返回多条记录"""
        db_path = tmp_path / "test.db"
        db = Storage(file_path=str(db_path))

        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        session = Session(db)
        session.execute(insert(User).values(id=1, name='Alice'))
        session.execute(insert(User).values(id=2, name='Bob'))
        session.execute(insert(User).values(id=3, name='Charlie'))
        session.commit()

        result = session.execute(select(User))
        users = result.all()

        assert len(users) == 3
        names = [u.name for u in users]
        assert 'Alice' in names
        assert 'Bob' in names
        assert 'Charlie' in names

        session.close()
        db.close()

    def test_first_returns_first(self, tmp_path):
        """first() 返回第一条记录"""
        db_path = tmp_path / "test.db"
        db = Storage(file_path=str(db_path))

        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        session = Session(db)
        session.execute(insert(User).values(id=1, name='First'))
        session.execute(insert(User).values(id=2, name='Second'))
        session.commit()

        result = session.execute(select(User))
        user = result.first()

        assert user is not None
        # 第一条记录（可能按插入顺序或主键顺序）
        assert user.name in ['First', 'Second']

        session.close()
        db.close()

    def test_one_raises_on_multiple(self, tmp_path):
        """one() 在多条结果时抛出 QueryError"""
        db_path = tmp_path / "test.db"
        db = Storage(file_path=str(db_path))

        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        session = Session(db)
        session.execute(insert(User).values(id=1, name='Alice'))
        session.execute(insert(User).values(id=2, name='Bob'))
        session.commit()

        result = session.execute(select(User))

        with pytest.raises(QueryError) as exc_info:
            result.one()

        assert "Expected one result, got 2" in str(exc_info.value)

        session.close()
        db.close()

    def test_one_or_none_raises_on_multiple(self, tmp_path):
        """one_or_none() 在多条结果时抛出 QueryError"""
        db_path = tmp_path / "test.db"
        db = Storage(file_path=str(db_path))

        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        session = Session(db)
        session.execute(insert(User).values(id=1, name='Alice'))
        session.execute(insert(User).values(id=2, name='Bob'))
        session.commit()

        result = session.execute(select(User))

        with pytest.raises(QueryError) as exc_info:
            result.one_or_none()

        assert "Expected at most one result, got 2" in str(exc_info.value)

        session.close()
        db.close()

    def test_rowcount_on_multiple(self, tmp_path):
        """多条记录的 rowcount()"""
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

        result = session.execute(select(User))
        assert result.rowcount() == 5

        session.close()
        db.close()


class TestCursorResultBehavior:
    """CursorResult 行为测试"""

    def test_rowcount_on_insert(self, tmp_path):
        """INSERT 的 rowcount"""
        db_path = tmp_path / "test.db"
        db = Storage(file_path=str(db_path))

        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        session = Session(db)
        result = session.execute(insert(User).values(id=1, name='Alice'))

        assert result.rowcount() == 1

        session.close()
        db.close()

    def test_rowcount_on_update(self, tmp_path):
        """UPDATE 的 rowcount"""
        db_path = tmp_path / "test.db"
        db = Storage(file_path=str(db_path))

        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        session = Session(db)
        session.execute(insert(User).values(id=1, name='Alice'))
        session.execute(insert(User).values(id=2, name='Alice'))
        session.execute(insert(User).values(id=3, name='Bob'))
        session.commit()

        result = session.execute(
            update(User).where(User.name == 'Alice').values(name='Updated')
        )

        assert result.rowcount() == 2

        session.close()
        db.close()

    def test_rowcount_on_delete(self, tmp_path):
        """DELETE 的 rowcount"""
        db_path = tmp_path / "test.db"
        db = Storage(file_path=str(db_path))

        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        session = Session(db)
        session.execute(insert(User).values(id=1, name='Alice'))
        session.execute(insert(User).values(id=2, name='Bob'))
        session.execute(insert(User).values(id=3, name='Charlie'))
        session.commit()

        result = session.execute(delete(User).where(User.id <= 2))

        assert result.rowcount() == 2

        session.close()
        db.close()

    def test_rowcount_on_no_match(self, tmp_path):
        """没有匹配时的 rowcount"""
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

        # 更新不存在的记录
        result = session.execute(
            update(User).where(User.name == 'NonExistent').values(name='New')
        )

        assert result.rowcount() == 0

        session.close()
        db.close()

    def test_inserted_primary_key(self, tmp_path):
        """INSERT 返回插入的主键"""
        db_path = tmp_path / "test.db"
        db = Storage(file_path=str(db_path))

        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        session = Session(db)
        result = session.execute(insert(User).values(id=42, name='Alice'))

        assert result.inserted_primary_key == 42

        session.close()
        db.close()

    def test_inserted_primary_key_auto_increment(self, tmp_path):
        """自增主键的 inserted_primary_key"""
        db_path = tmp_path / "test.db"
        db = Storage(file_path=str(db_path))

        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        session = Session(db)

        # 不指定 id，使用自增
        result = session.execute(insert(User).values(name='Alice'))
        pk1 = result.inserted_primary_key

        result = session.execute(insert(User).values(name='Bob'))
        pk2 = result.inserted_primary_key

        # 主键应该递增
        assert pk1 is not None
        assert pk2 is not None
        assert pk2 > pk1

        session.close()
        db.close()


class TestCursorResultUnsupportedOperations:
    """CursorResult 不支持的操作测试"""

    def test_all_raises_on_insert(self, tmp_path):
        """INSERT 结果调用 all() 抛出异常"""
        db_path = tmp_path / "test.db"
        db = Storage(file_path=str(db_path))

        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        session = Session(db)
        result = session.execute(insert(User).values(id=1, name='Alice'))

        with pytest.raises(UnsupportedOperationError):
            result.all()

        session.close()
        db.close()

    def test_first_raises_on_update(self, tmp_path):
        """UPDATE 结果调用 first() 抛出异常"""
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

        result = session.execute(
            update(User).where(User.id == 1).values(name='Bob')
        )

        with pytest.raises(UnsupportedOperationError):
            result.first()

        session.close()
        db.close()

    def test_one_raises_on_delete(self, tmp_path):
        """DELETE 结果调用 one() 抛出异常"""
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

        result = session.execute(delete(User).where(User.id == 1))

        with pytest.raises(UnsupportedOperationError):
            result.one()

        session.close()
        db.close()

    def test_one_or_none_raises_on_insert(self, tmp_path):
        """INSERT 结果调用 one_or_none() 抛出异常"""
        db_path = tmp_path / "test.db"
        db = Storage(file_path=str(db_path))

        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        session = Session(db)
        result = session.execute(insert(User).values(id=1, name='Alice'))

        with pytest.raises(UnsupportedOperationError):
            result.one_or_none()

        session.close()
        db.close()


class TestResultIdentityMap:
    """Result 与 identity map 交互测试"""

    def test_same_instance_from_identity_map(self, tmp_path):
        """同一主键返回相同实例（identity map）"""
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

        # 第一次查询
        result1 = session.execute(select(User).where(User.id == 1))
        user1 = result1.first()

        # 第二次查询
        result2 = session.execute(select(User).where(User.id == 1))
        user2 = result2.first()

        # 应该是同一个实例
        assert user1 is user2

        session.close()
        db.close()

    def test_all_called_multiple_times(self, tmp_path):
        """多次调用 all() 返回相同实例"""
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

        result = session.execute(select(User))

        # 多次调用 all()
        users1 = result.all()
        users2 = result.all()

        # 由于 identity map，应该是同一个实例
        assert users1[0] is users2[0]

        session.close()
        db.close()
