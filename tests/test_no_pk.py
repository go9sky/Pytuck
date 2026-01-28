"""
无主键模式测试

测试 Pytuck 全库无主键支持：
- 无主键模型的定义和创建
- 无主键表的 CRUD 操作
- 复合主键检测
- flush 后对象刷新
- refresh 方法
"""

from pathlib import Path
from typing import Type

import pytest

from pytuck import Storage, Session, Column, PureBaseModel, declarative_base
from pytuck import select, insert, update, delete
from pytuck.core.orm import PSEUDO_PK_NAME
from pytuck.common.exceptions import SchemaError


class TestNoPrimaryKey:
    """无主键模式测试"""

    def test_create_table_without_pk(self, tmp_path: Path) -> None:
        """无主键模型可以正常创建表"""
        db_file = tmp_path / 'test.db'
        db = Storage(file_path=str(db_file), engine='binary')
        Base: Type[PureBaseModel] = declarative_base(db)

        class Log(Base):
            __tablename__ = 'logs'
            # 无主键
            message = Column(str)
            level = Column(str)

        # 验证模型没有主键
        assert Log.__primary_key__ is None

        # 验证表创建成功
        assert 'logs' in db.tables
        table = db.tables['logs']
        assert table.primary_key is None

        db.close()

    def test_insert_and_query_no_pk(self, tmp_path: Path) -> None:
        """无主键表可以插入和查询"""
        db_file = tmp_path / 'test.db'
        db = Storage(file_path=str(db_file), engine='binary')
        Base: Type[PureBaseModel] = declarative_base(db)

        class Log(Base):
            __tablename__ = 'logs'
            message = Column(str)
            level = Column(str)

        session = Session(db)

        # 插入多条记录
        session.execute(insert(Log).values(message='First message', level='INFO'))
        session.execute(insert(Log).values(message='Second message', level='WARNING'))
        session.execute(insert(Log).values(message='Third message', level='ERROR'))
        session.commit()

        # 查询所有记录
        result = session.execute(select(Log))
        logs = result.all()

        assert len(logs) == 3
        messages = [log.message for log in logs]
        assert 'First message' in messages
        assert 'Second message' in messages
        assert 'Third message' in messages

        # 条件查询
        result = session.execute(select(Log).where(Log.level == 'ERROR'))
        error_logs = result.all()
        assert len(error_logs) == 1
        assert error_logs[0].message == 'Third message'

        session.close()
        db.close()

    def test_update_no_pk(self, tmp_path: Path) -> None:
        """无主键表可以更新"""
        db_file = tmp_path / 'test.db'
        db = Storage(file_path=str(db_file), engine='binary')
        Base: Type[PureBaseModel] = declarative_base(db)

        class Log(Base):
            __tablename__ = 'logs'
            message = Column(str)
            level = Column(str)

        session = Session(db)

        # 插入记录
        session.execute(insert(Log).values(message='Test message', level='INFO'))
        session.commit()

        # 条件更新
        count = session.execute(
            update(Log).where(Log.level == 'INFO').values(level='DEBUG')
        ).rowcount()
        session.commit()

        assert count == 1

        # 验证更新成功
        result = session.execute(select(Log))
        log = result.first()
        assert log is not None
        assert log.level == 'DEBUG'

        session.close()
        db.close()

    def test_delete_no_pk(self, tmp_path: Path) -> None:
        """无主键表可以删除"""
        db_file = tmp_path / 'test.db'
        db = Storage(file_path=str(db_file), engine='binary')
        Base: Type[PureBaseModel] = declarative_base(db)

        class Log(Base):
            __tablename__ = 'logs'
            message = Column(str)
            level = Column(str)

        session = Session(db)

        # 插入多条记录
        session.execute(insert(Log).values(message='Keep', level='INFO'))
        session.execute(insert(Log).values(message='Delete', level='ERROR'))
        session.commit()

        # 条件删除
        count = session.execute(
            delete(Log).where(Log.level == 'ERROR')
        ).rowcount()
        session.commit()

        assert count == 1

        # 验证删除成功
        result = session.execute(select(Log))
        logs = result.all()
        assert len(logs) == 1
        assert logs[0].message == 'Keep'

        session.close()
        db.close()

    def test_identity_map_no_pk(self, tmp_path: Path) -> None:
        """无主键模型的 identity map 正常工作"""
        db_file = tmp_path / 'test.db'
        db = Storage(file_path=str(db_file), engine='binary')
        Base: Type[PureBaseModel] = declarative_base(db)

        class Log(Base):
            __tablename__ = 'logs'
            message = Column(str)

        session = Session(db)

        # 通过 add 插入
        log = Log(message='Test')
        session.add(log)
        session.commit()

        # 验证实例有内部 rowid
        assert hasattr(log, '_pytuck_rowid')
        assert log._pytuck_rowid is not None

        # 再次查询，应该返回相同实例（identity map）
        result = session.execute(select(Log))
        queried_log = result.first()
        assert queried_log is log  # 同一个对象

        session.close()
        db.close()

    def test_get_returns_none_for_no_pk(self, tmp_path: Path) -> None:
        """Session.get() 对无主键模型返回 None"""
        db_file = tmp_path / 'test.db'
        db = Storage(file_path=str(db_file), engine='binary')
        Base: Type[PureBaseModel] = declarative_base(db)

        class Log(Base):
            __tablename__ = 'logs'
            message = Column(str)

        session = Session(db)
        session.execute(insert(Log).values(message='Test'))
        session.commit()

        # get() 对无主键模型应返回 None
        result = session.get(Log, 1)
        assert result is None

        session.close()
        db.close()


class TestMultiplePrimaryKeys:
    """复合主键检测测试"""

    def test_multiple_pk_raises_error(self, tmp_path: Path) -> None:
        """定义多个主键列应抛出 SchemaError"""
        db_file = tmp_path / 'test.db'
        db = Storage(file_path=str(db_file), engine='binary')
        Base: Type[PureBaseModel] = declarative_base(db)

        with pytest.raises(SchemaError) as excinfo:
            class BadModel(Base):
                __tablename__ = 'bad_table'
                id1 = Column(int, primary_key=True)
                id2 = Column(int, primary_key=True)
                name = Column(str)

        assert 'multiple primary keys' in str(excinfo.value).lower()

        db.close()


class TestRefreshAfterFlush:
    """flush 后刷新测试"""

    def test_refresh_after_insert(self, tmp_path: Path) -> None:
        """插入后实例属性应反映数据库值"""
        db_file = tmp_path / 'test.db'
        db = Storage(file_path=str(db_file), engine='binary')
        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)
            score = Column(int, default=100)

        session = Session(db)

        # 创建实例（不设置 id 和 score）
        user = User(name='Alice')
        session.add(user)
        session.flush()

        # flush 后应该有 id（自动生成）
        assert user.id == 1

        # 注意：由于 flush 已经从数据库读取，默认值已经应用
        # （如果模型定义了 default，但这里 score 没有在创建时设置）

        session.close()
        db.close()

    def test_refresh_method(self, tmp_path: Path) -> None:
        """session.refresh() 应刷新实例属性"""
        db_file = tmp_path / 'test.db'
        db = Storage(file_path=str(db_file), engine='binary')
        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        session = Session(db)

        # 插入一条记录
        user = User(name='Alice')
        session.add(user)
        session.commit()

        # 直接修改数据库（模拟外部修改）
        db.update('users', user.id, {'name': 'Bob'})

        # refresh 前，实例仍是旧值
        assert user.name == 'Alice'

        # refresh 后，实例应该反映数据库值
        session.refresh(user)
        assert user.name == 'Bob'

        session.close()
        db.close()

    def test_refresh_no_pk_model(self, tmp_path: Path) -> None:
        """无主键模型也可以 refresh"""
        db_file = tmp_path / 'test.db'
        db = Storage(file_path=str(db_file), engine='binary')
        Base: Type[PureBaseModel] = declarative_base(db)

        class Log(Base):
            __tablename__ = 'logs'
            message = Column(str)

        session = Session(db)

        # 插入
        log = Log(message='Original')
        session.add(log)
        session.commit()

        # 直接修改数据库
        rowid = log._pytuck_rowid
        db.update('logs', rowid, {'message': 'Modified'})

        # refresh 后应该反映新值
        session.refresh(log)
        assert log.message == 'Modified'

        session.close()
        db.close()


class TestPseudoPkNameConstant:
    """PSEUDO_PK_NAME 常量测试"""

    def test_pseudo_pk_name_value(self) -> None:
        """PSEUDO_PK_NAME 常量应为 '_pytuck_rowid'"""
        assert PSEUDO_PK_NAME == '_pytuck_rowid'

    def test_query_returns_pseudo_pk(self, tmp_path: Path) -> None:
        """无主键表查询结果中包含 PSEUDO_PK_NAME"""
        db_file = tmp_path / 'test.db'
        db = Storage(file_path=str(db_file), engine='binary')
        Base: Type[PureBaseModel] = declarative_base(db)

        class Log(Base):
            __tablename__ = 'logs'
            message = Column(str)

        session = Session(db)
        session.execute(insert(Log).values(message='Test'))
        session.commit()

        # 直接查询 Storage，应该包含 PSEUDO_PK_NAME
        records = db.query('logs', [])
        assert len(records) == 1
        assert PSEUDO_PK_NAME in records[0]

        session.close()
        db.close()
