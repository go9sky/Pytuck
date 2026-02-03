"""
错误恢复测试

测试方法：
- 错误推断法：文件损坏、I/O 失败等异常情况
- 场景设计：事务失败后的恢复

覆盖范围：
- 文件损坏处理
- 事务回滚恢复
- 上下文管理器异常处理
"""

import pytest
import json
from typing import Type

from pytuck import (
    Storage, Session, Column, declarative_base,
    PureBaseModel, select, insert, update, delete,
    SerializationError, TransactionError,
)


class TestFileCorruption:
    """文件损坏恢复测试"""

    def test_corrupted_json_file(self, tmp_path):
        """损坏的 JSON 文件"""
        db_path = tmp_path / "test.json"

        # 写入损坏的 JSON
        with open(db_path, 'w') as f:
            f.write("{invalid json content")

        # 尝试打开应该抛出异常
        with pytest.raises(Exception):  # 可能是 SerializationError 或 json.JSONDecodeError
            Storage(file_path=str(db_path), engine='json')

    def test_empty_file_json(self, tmp_path):
        """空的 JSON 文件抛出 SerializationError"""
        db_path = tmp_path / "test.json"

        # 创建空文件
        db_path.touch()

        # 空 JSON 文件应该抛出 SerializationError
        with pytest.raises(SerializationError):
            Storage(file_path=str(db_path), engine='json')

    def test_truncated_binary_file(self, tmp_path):
        """截断的二进制文件"""
        db_path = tmp_path / "test.db"

        # 先创建正常数据库
        db = Storage(file_path=str(db_path), engine='binary')

        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        session = Session(db)
        session.execute(insert(User).values(id=1, name='Alice'))
        session.commit()
        db.close()

        # 读取并截断文件
        with open(db_path, 'rb') as f:
            content = f.read()

        # 写入截断的内容（只保留一半）
        with open(db_path, 'wb') as f:
            f.write(content[:len(content)//2])

        # 尝试打开截断的文件应该失败
        with pytest.raises(Exception):
            Storage(file_path=str(db_path), engine='binary')


class TestTransactionRecovery:
    """事务行为测试

    注意：当前实现中，rollback() 只清除 Session 的 pending 对象，
    不会撤销已经 execute 到 Storage 内存中的数据。
    这些测试验证的是实际行为，而非理想的 ACID 事务。
    """

    def test_rollback_clears_pending(self, tmp_path):
        """回滚清除 pending 对象"""
        db_path = tmp_path / "test.db"
        db = Storage(file_path=str(db_path))

        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        session = Session(db)

        # 使用 session.add() 添加对象（这会放入 pending）
        user = User(id=1, name='Alice')
        session.add(user)

        # 回滚应该清除 pending
        session.rollback()

        # 提交后应该没有数据
        session.commit()
        result = session.execute(select(User))
        users = result.all()

        assert len(users) == 0

        session.close()
        db.close()

    def test_context_manager_exception_clears_pending(self, tmp_path):
        """上下文管理器中异常清除 pending"""
        db_path = tmp_path / "test.db"
        db = Storage(file_path=str(db_path))

        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        # 在上下文管理器中添加对象并抛出异常
        try:
            with Session(db) as session:
                user = User(id=1, name='Alice')
                session.add(user)
                raise ValueError("Simulated error")
        except ValueError:
            pass

        # 验证数据没有被持久化
        session2 = Session(db)
        result = session2.execute(select(User))
        users = result.all()

        # pending 对象应该被清除，所以没有数据
        assert len(users) == 0

        session2.close()
        db.close()

    def test_commit_persists_data(self, tmp_path):
        """commit() 将数据持久化"""
        db_path = tmp_path / "test.db"
        db = Storage(file_path=str(db_path))

        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        session = Session(db)

        # 插入数据并提交
        session.execute(insert(User).values(id=1, name='Alice'))
        session.commit()

        # 验证数据已持久化
        result = session.execute(select(User))
        users = result.all()

        assert len(users) == 1
        assert users[0].name == 'Alice'

        session.close()
        db.close()

    def test_execute_affects_storage_immediately(self, tmp_path):
        """execute() 立即影响 Storage 内存"""
        db_path = tmp_path / "test.db"
        db = Storage(file_path=str(db_path))

        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        session = Session(db)

        # execute 直接写入 Storage 内存
        session.execute(insert(User).values(id=1, name='Alice'))

        # 未 commit 也能查询到（因为在同一 Storage 内存中）
        result = session.execute(select(User))
        users = result.all()

        assert len(users) == 1
        assert users[0].name == 'Alice'

        session.close()
        db.close()


class TestStorageRecovery:
    """Storage 恢复测试"""

    def test_close_without_flush(self, tmp_path):
        """关闭 Storage 自动 flush"""
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
        db.close()  # close() 应该自动 flush

        # 重新打开，验证数据已持久化
        db2 = Storage(file_path=str(db_path))

        Base2: Type[PureBaseModel] = declarative_base(db2)

        class User2(Base2):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        session2 = Session(db2)
        result = session2.execute(select(User2))
        users = result.all()

        assert len(users) == 1
        assert users[0].name == 'Alice'

        session2.close()
        db2.close()

    def test_reopen_after_crash_simulation(self, tmp_path):
        """模拟崩溃后重新打开（未 flush）"""
        db_path = tmp_path / "test.db"
        db = Storage(file_path=str(db_path), auto_flush=True)

        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        session = Session(db)
        session.execute(insert(User).values(id=1, name='Alice'))
        session.commit()  # auto_flush=True，commit 后自动写入

        # 不调用 close()，直接重新打开（模拟崩溃）
        db2 = Storage(file_path=str(db_path))

        Base2: Type[PureBaseModel] = declarative_base(db2)

        class User2(Base2):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        session2 = Session(db2)
        result = session2.execute(select(User2))
        users = result.all()

        # auto_flush=True 时数据应该已持久化
        assert len(users) == 1
        assert users[0].name == 'Alice'

        session2.close()
        db2.close()


class TestSessionRecovery:
    """Session 恢复测试"""

    def test_session_after_storage_close(self, tmp_path):
        """Storage 关闭后 Session 操作"""
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

        # 先关闭 session，再关闭 storage
        session.close()
        db.close()

        # 尝试在关闭后使用 session 应该失败或返回空
        # （具体行为取决于实现）

    def test_new_session_after_commit(self, tmp_path):
        """提交后创建新 Session 可以看到数据"""
        db_path = tmp_path / "test.db"
        db = Storage(file_path=str(db_path))

        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        # 第一个 session 插入数据
        session1 = Session(db)
        session1.execute(insert(User).values(id=1, name='Alice'))
        session1.commit()
        session1.close()

        # 第二个 session 应该能看到数据
        session2 = Session(db)
        result = session2.execute(select(User))
        users = result.all()

        assert len(users) == 1
        assert users[0].name == 'Alice'

        session2.close()
        db.close()
