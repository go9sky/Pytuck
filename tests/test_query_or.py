"""
测试 OR/AND/NOT 逻辑查询功能

测试 or_(), and_(), not_() 函数在各种场景下的正确性。
"""
from pathlib import Path
from typing import Type

import pytest

from pytuck import (
    Storage, declarative_base, Session, Column,
    PureBaseModel, CRUDBaseModel,
    select, insert, update, delete,
    or_, and_, not_,
    QueryError,
)


class TestOrFunction:
    """测试 or_() 函数"""

    def test_simple_or_query(self, tmp_path: Path) -> None:
        """测试简单的 OR 查询"""
        db = Storage(file_path=str(tmp_path / 'test.db'), in_memory=True)
        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)
            age = Column(int)
            vip = Column(bool, default=False)

        session = Session(db)

        # 插入测试数据
        session.execute(insert(User).values(name='Alice', age=25, vip=False))
        session.execute(insert(User).values(name='Bob', age=17, vip=True))
        session.execute(insert(User).values(name='Charlie', age=30, vip=False))
        session.execute(insert(User).values(name='Diana', age=16, vip=False))
        session.commit()

        # 测试 OR 查询：age >= 18 或者 vip == True
        stmt = select(User).where(or_(User.age >= 18, User.vip == True))
        result = session.execute(stmt)
        users = result.all()

        names = {u.name for u in users}
        assert names == {'Alice', 'Bob', 'Charlie'}  # Diana 不符合任一条件

        db.close()

    def test_or_with_multiple_conditions(self, tmp_path: Path) -> None:
        """测试多个条件的 OR"""
        db = Storage(file_path=str(tmp_path / 'test.db'), in_memory=True)
        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            role = Column(str)

        session = Session(db)

        session.execute(insert(User).values(role='admin'))
        session.execute(insert(User).values(role='moderator'))
        session.execute(insert(User).values(role='editor'))
        session.execute(insert(User).values(role='viewer'))
        session.commit()

        # 多个条件的 OR
        stmt = select(User).where(or_(
            User.role == 'admin',
            User.role == 'moderator',
            User.role == 'editor'
        ))
        result = session.execute(stmt)
        users = result.all()

        roles = {u.role for u in users}
        assert roles == {'admin', 'moderator', 'editor'}

        db.close()

    def test_or_requires_at_least_two_expressions(self) -> None:
        """测试 or_() 需要至少 2 个表达式"""
        with pytest.raises(QueryError, match="at least 2 expressions"):
            or_()  # type: ignore

        # 使用一个临时模型来创建表达式
        from pytuck.core.orm import Column as OrmColumn
        col = OrmColumn(int)
        col.name = 'test'
        from pytuck.query.builder import BinaryExpression
        expr = BinaryExpression(col, '=', 1)

        with pytest.raises(QueryError, match="at least 2 expressions"):
            or_(expr)


class TestAndFunction:
    """测试 and_() 函数"""

    def test_explicit_and_query(self, tmp_path: Path) -> None:
        """测试显式 AND 查询"""
        db = Storage(file_path=str(tmp_path / 'test.db'), in_memory=True)
        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            active = Column(bool)
            verified = Column(bool)

        session = Session(db)

        session.execute(insert(User).values(active=True, verified=True))
        session.execute(insert(User).values(active=True, verified=False))
        session.execute(insert(User).values(active=False, verified=True))
        session.execute(insert(User).values(active=False, verified=False))
        session.commit()

        # 显式 AND
        stmt = select(User).where(and_(User.active == True, User.verified == True))
        result = session.execute(stmt)
        users = result.all()

        assert len(users) == 1
        assert users[0].active is True
        assert users[0].verified is True

        db.close()

    def test_and_requires_at_least_two_expressions(self) -> None:
        """测试 and_() 需要至少 2 个表达式"""
        with pytest.raises(QueryError, match="at least 2 expressions"):
            and_()  # type: ignore


class TestNotFunction:
    """测试 not_() 函数"""

    def test_simple_not_query(self, tmp_path: Path) -> None:
        """测试简单的 NOT 查询"""
        db = Storage(file_path=str(tmp_path / 'test.db'), in_memory=True)
        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)
            banned = Column(bool, default=False)

        session = Session(db)

        session.execute(insert(User).values(name='Alice', banned=False))
        session.execute(insert(User).values(name='Bob', banned=True))
        session.execute(insert(User).values(name='Charlie', banned=False))
        session.commit()

        # NOT 查询：未被封禁的用户
        stmt = select(User).where(not_(User.banned == True))
        result = session.execute(stmt)
        users = result.all()

        names = {u.name for u in users}
        assert names == {'Alice', 'Charlie'}

        db.close()

    def test_not_with_or(self, tmp_path: Path) -> None:
        """测试 NOT 与 OR 组合"""
        db = Storage(file_path=str(tmp_path / 'test.db'), in_memory=True)
        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)
            banned = Column(bool, default=False)
            deleted = Column(bool, default=False)

        session = Session(db)

        session.execute(insert(User).values(name='Alice', banned=False, deleted=False))
        session.execute(insert(User).values(name='Bob', banned=True, deleted=False))
        session.execute(insert(User).values(name='Charlie', banned=False, deleted=True))
        session.execute(insert(User).values(name='Diana', banned=True, deleted=True))
        session.commit()

        # NOT (banned OR deleted)
        stmt = select(User).where(not_(or_(User.banned == True, User.deleted == True)))
        result = session.execute(stmt)
        users = result.all()

        names = {u.name for u in users}
        assert names == {'Alice'}  # 只有 Alice 既没被封禁也没被删除

        db.close()


class TestNestedLogicalExpressions:
    """测试嵌套逻辑表达式"""

    def test_or_with_and(self, tmp_path: Path) -> None:
        """测试 OR 与 AND 嵌套"""
        db = Storage(file_path=str(tmp_path / 'test.db'), in_memory=True)
        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)
            role = Column(str)
            age = Column(int)
            verified = Column(bool, default=False)

        session = Session(db)

        session.execute(insert(User).values(name='Admin', role='admin', age=30, verified=False))
        session.execute(insert(User).values(name='Young', role='user', age=20, verified=False))
        session.execute(insert(User).values(name='Verified', role='user', age=22, verified=True))
        session.execute(insert(User).values(name='OldUnverified', role='user', age=25, verified=False))
        session.commit()

        # role == 'admin' OR (age >= 21 AND verified == True)
        stmt = select(User).where(or_(
            User.role == 'admin',
            and_(User.age >= 21, User.verified == True)
        ))
        result = session.execute(stmt)
        users = result.all()

        names = {u.name for u in users}
        assert names == {'Admin', 'Verified'}

        db.close()

    def test_multiple_conditions_with_or(self, tmp_path: Path) -> None:
        """测试多参数 where 与 OR 组合"""
        db = Storage(file_path=str(tmp_path / 'test.db'), in_memory=True)
        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            active = Column(bool)
            age = Column(int)
            score = Column(int)

        session = Session(db)

        session.execute(insert(User).values(active=True, age=20, score=80))
        session.execute(insert(User).values(active=True, age=15, score=95))
        session.execute(insert(User).values(active=False, age=25, score=90))
        session.execute(insert(User).values(active=True, age=17, score=70))
        session.commit()

        # active == True AND (age >= 18 OR score >= 90)
        stmt = select(User).where(
            User.active == True,
            or_(User.age >= 18, User.score >= 90)
        )
        result = session.execute(stmt)
        users = result.all()

        # 匹配：(active=True, age=20, score=80) 和 (active=True, age=15, score=95)
        assert len(users) == 2

        db.close()


class TestUpdateDeleteWithOr:
    """测试 UPDATE 和 DELETE 语句的 OR 支持"""

    def test_update_with_or(self, tmp_path: Path) -> None:
        """测试 UPDATE 语句的 OR 条件"""
        db = Storage(file_path=str(tmp_path / 'test.db'), in_memory=True)
        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            role = Column(str)
            active = Column(bool, default=True)

        session = Session(db)

        session.execute(insert(User).values(role='guest', active=True))
        session.execute(insert(User).values(role='expired', active=True))
        session.execute(insert(User).values(role='user', active=True))
        session.commit()

        # 更新 guest 或 expired 用户为 inactive
        stmt = update(User).where(or_(
            User.role == 'guest',
            User.role == 'expired'
        )).values(active=False)
        result = session.execute(stmt)
        session.commit()

        assert result.rowcount() == 2

        # 验证
        stmt = select(User).where(User.active == False)
        result = session.execute(stmt)
        inactive_users = result.all()
        roles = {u.role for u in inactive_users}
        assert roles == {'guest', 'expired'}

        db.close()

    def test_delete_with_or(self, tmp_path: Path) -> None:
        """测试 DELETE 语句的 OR 条件"""
        db = Storage(file_path=str(tmp_path / 'test.db'), in_memory=True)
        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            expired = Column(bool, default=False)
            banned = Column(bool, default=False)

        session = Session(db)

        session.execute(insert(User).values(expired=False, banned=False))
        session.execute(insert(User).values(expired=True, banned=False))
        session.execute(insert(User).values(expired=False, banned=True))
        session.execute(insert(User).values(expired=True, banned=True))
        session.commit()

        # 删除过期或被封禁的用户
        stmt = delete(User).where(or_(User.expired == True, User.banned == True))
        result = session.execute(stmt)
        session.commit()

        assert result.rowcount() == 3

        # 验证只剩一个用户
        stmt = select(User)
        result = session.execute(stmt)
        remaining = result.all()
        assert len(remaining) == 1
        assert remaining[0].expired is False
        assert remaining[0].banned is False

        db.close()


class TestActiveRecordModeOr:
    """测试 Active Record 模式下的 OR 支持"""

    def test_filter_with_or(self, tmp_path: Path) -> None:
        """测试 Model.filter() 与 OR"""
        db = Storage(file_path=str(tmp_path / 'test.db'), in_memory=True)
        Base: Type[CRUDBaseModel] = declarative_base(db, crud=True)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)
            age = Column(int)
            vip = Column(bool, default=False)

        # 创建测试数据
        User.create(name='Alice', age=25, vip=False)
        User.create(name='Bob', age=17, vip=True)
        User.create(name='Charlie', age=30, vip=False)
        User.create(name='Diana', age=16, vip=False)

        # 使用 filter 与 OR
        users = User.filter(or_(User.age >= 18, User.vip == True)).all()

        names = {u.name for u in users}
        assert names == {'Alice', 'Bob', 'Charlie'}

        db.close()


class TestQueryBuilderOr:
    """测试 Query 构建器的 OR 支持"""

    def test_query_filter_with_or(self, tmp_path: Path) -> None:
        """测试 Query.filter() 与 OR"""
        db = Storage(file_path=str(tmp_path / 'test.db'), in_memory=True)
        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)
            age = Column(int)

        session = Session(db)

        session.execute(insert(User).values(name='Alice', age=25))
        session.execute(insert(User).values(name='Bob', age=17))
        session.execute(insert(User).values(name='Charlie', age=30))
        session.commit()

        from pytuck.query.builder import Query

        query = Query(User, db)
        users = query.filter(or_(User.age >= 25, User.name == 'Bob')).all()

        names = {u.name for u in users}
        assert names == {'Alice', 'Bob', 'Charlie'}

        db.close()


class TestEdgeCases:
    """测试边界情况"""

    def test_empty_result_with_or(self, tmp_path: Path) -> None:
        """测试 OR 查询返回空结果"""
        db = Storage(file_path=str(tmp_path / 'test.db'), in_memory=True)
        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            age = Column(int)

        session = Session(db)

        session.execute(insert(User).values(age=25))
        session.execute(insert(User).values(age=30))
        session.commit()

        # 不会匹配任何记录
        stmt = select(User).where(or_(User.age < 10, User.age > 100))
        result = session.execute(stmt)
        users = result.all()

        assert len(users) == 0

        db.close()

    def test_or_with_filter_by(self, tmp_path: Path) -> None:
        """测试 OR 与 filter_by 混合使用"""
        db = Storage(file_path=str(tmp_path / 'test.db'), in_memory=True)
        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)
            active = Column(bool)
            age = Column(int)

        session = Session(db)

        session.execute(insert(User).values(name='Alice', active=True, age=25))
        session.execute(insert(User).values(name='Bob', active=True, age=17))
        session.execute(insert(User).values(name='Charlie', active=False, age=30))
        session.commit()

        # 先用 filter_by，再用 where 添加 OR
        stmt = select(User).filter_by(active=True).where(or_(User.age >= 18, User.name == 'Bob'))
        result = session.execute(stmt)
        users = result.all()

        names = {u.name for u in users}
        assert names == {'Alice', 'Bob'}

        db.close()

    def test_chained_or_expressions(self, tmp_path: Path) -> None:
        """测试链式 OR 表达式"""
        db = Storage(file_path=str(tmp_path / 'test.db'), in_memory=True)
        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            a = Column(bool, default=False)
            b = Column(bool, default=False)
            c = Column(bool, default=False)

        session = Session(db)

        # 只有 a 为 True
        session.execute(insert(User).values(a=True, b=False, c=False))
        # 只有 b 为 True
        session.execute(insert(User).values(a=False, b=True, c=False))
        # 只有 c 为 True
        session.execute(insert(User).values(a=False, b=False, c=True))
        # 全部为 False
        session.execute(insert(User).values(a=False, b=False, c=False))
        session.commit()

        # OR(a, b, c)
        stmt = select(User).where(or_(User.a == True, User.b == True, User.c == True))
        result = session.execute(stmt)
        users = result.all()

        assert len(users) == 3  # 除了全部为 False 的那条

        db.close()
