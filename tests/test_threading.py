"""
多线程测试（单进程）

测试方法：
- 场景设计：单进程内多线程读写
- 错误推断：线程安全边界情况

覆盖范围：
- 多线程并发读取
- 多线程并发写入
- Session 线程隔离
- auto_flush 多线程行为

注意：本库只支持单进程操作，不支持多进程并发访问。
"""

import pytest
import threading
import time
from typing import Type, List
from concurrent.futures import ThreadPoolExecutor, as_completed

from pytuck import (
    Storage, Session, Column, declarative_base,
    PureBaseModel, select, insert, update, delete,
)


class TestMultiThreadedRead:
    """多线程读取测试（单进程）"""

    def test_concurrent_read_same_table(self, tmp_path):
        """多线程并发读取同一表"""
        db_path = tmp_path / "test.db"
        db = Storage(file_path=str(db_path))

        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        # 插入测试数据
        session = Session(db)
        for i in range(10):
            session.execute(insert(User).values(id=i+1, name=f'User{i}'))
        session.commit()
        session.close()

        # 多线程并发读取
        results: List[int] = []
        errors: List[Exception] = []

        def read_users():
            try:
                s = Session(db)
                result = s.execute(select(User))
                count = len(result.all())
                results.append(count)
                s.close()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=read_users) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert all(r == 10 for r in results), f"Inconsistent results: {results}"

        db.close()

    def test_concurrent_read_different_tables(self, tmp_path):
        """多线程并发读取不同表"""
        db_path = tmp_path / "test.db"
        db = Storage(file_path=str(db_path))

        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        class Product(Base):
            __tablename__ = 'products'
            id = Column(int, primary_key=True)
            title = Column(str)

        # 插入测试数据
        session = Session(db)
        for i in range(5):
            session.execute(insert(User).values(id=i+1, name=f'User{i}'))
            session.execute(insert(Product).values(id=i+1, title=f'Product{i}'))
        session.commit()
        session.close()

        # 多线程并发读取不同表
        user_counts: List[int] = []
        product_counts: List[int] = []
        errors: List[Exception] = []

        def read_users():
            try:
                s = Session(db)
                result = s.execute(select(User))
                user_counts.append(len(result.all()))
                s.close()
            except Exception as e:
                errors.append(e)

        def read_products():
            try:
                s = Session(db)
                result = s.execute(select(Product))
                product_counts.append(len(result.all()))
                s.close()
            except Exception as e:
                errors.append(e)

        threads = []
        for _ in range(3):
            threads.append(threading.Thread(target=read_users))
            threads.append(threading.Thread(target=read_products))

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert all(c == 5 for c in user_counts)
        assert all(c == 5 for c in product_counts)

        db.close()

    def test_thread_local_session_isolation(self, tmp_path):
        """每个线程 Session 的数据操作是隔离的"""
        db_path = tmp_path / "test.db"
        db = Storage(file_path=str(db_path))

        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        # 插入初始数据
        session = Session(db)
        session.execute(insert(User).values(id=1, name='Alice'))
        session.commit()
        session.close()

        # 验证每个线程可以独立创建和使用 Session
        results: List[str] = []
        errors: List[Exception] = []

        def use_session(thread_id: int):
            try:
                s = Session(db)
                result = s.execute(select(User).where(User.id == 1))
                user = result.first()
                results.append(f"thread{thread_id}:{user.name}")
                s.close()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=use_session, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Errors: {errors}"
        assert len(results) == 5
        assert all('Alice' in r for r in results)

        db.close()


class TestMultiThreadedWrite:
    """多线程写入测试（单进程）"""

    def test_concurrent_insert_different_records(self, tmp_path):
        """多线程并发插入不同记录"""
        db_path = tmp_path / "test.db"
        db = Storage(file_path=str(db_path))

        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        errors: List[Exception] = []

        def insert_user(user_id: int):
            try:
                s = Session(db)
                s.execute(insert(User).values(id=user_id, name=f'User{user_id}'))
                s.commit()
                s.close()
            except Exception as e:
                errors.append(e)

        # 使用 ThreadPoolExecutor 并发插入
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(insert_user, i) for i in range(1, 11)]
            for f in as_completed(futures):
                f.result()  # 触发异常（如果有）

        # 验证所有记录都插入成功
        session = Session(db)
        result = session.execute(select(User))
        users = result.all()
        session.close()

        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert len(users) == 10

        db.close()

    def test_sequential_write_after_read(self, tmp_path):
        """读取后顺序写入"""
        db_path = tmp_path / "test.db"
        db = Storage(file_path=str(db_path))

        Base: Type[PureBaseModel] = declarative_base(db)

        class Counter(Base):
            __tablename__ = 'counters'
            id = Column(int, primary_key=True)
            value = Column(int)

        # 初始化计数器
        session = Session(db)
        session.execute(insert(Counter).values(id=1, value=0))
        session.commit()
        session.close()

        errors: List[Exception] = []
        lock = threading.Lock()

        def increment():
            try:
                with lock:  # 使用锁确保顺序访问
                    s = Session(db)
                    result = s.execute(select(Counter).where(Counter.id == 1))
                    counter = result.first()
                    new_value = counter.value + 1
                    s.execute(
                        update(Counter).where(Counter.id == 1).values(value=new_value)
                    )
                    s.commit()
                    s.close()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=increment) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # 验证计数器值
        session = Session(db)
        result = session.execute(select(Counter).where(Counter.id == 1))
        counter = result.first()
        session.close()

        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert counter.value == 5

        db.close()


class TestAutoFlushThreading:
    """auto_flush 多线程测试"""

    def test_auto_flush_true_sequential_write(self, tmp_path):
        """auto_flush=True 顺序写入行为

        注意：auto_flush=True 不支持多线程并发写入，因为文件锁会导致冲突。
        应该使用 auto_flush=False 并在最后统一 flush()。
        """
        db_path = tmp_path / "test.db"
        db = Storage(file_path=str(db_path), auto_flush=True)

        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        # 顺序插入（非并发）
        for i in range(1, 6):
            s = Session(db)
            s.execute(insert(User).values(id=i, name=f'User{i}'))
            s.commit()
            s.close()

        db.close()

        # 重新打开验证数据持久化
        db2 = Storage(file_path=str(db_path))
        Base2: Type[PureBaseModel] = declarative_base(db2)

        class User2(Base2):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        session = Session(db2)
        result = session.execute(select(User2))
        users = result.all()
        session.close()
        db2.close()

        assert len(users) == 5

    def test_auto_flush_false_multi_thread(self, tmp_path):
        """auto_flush=False 多线程行为"""
        db_path = tmp_path / "test.db"
        db = Storage(file_path=str(db_path), auto_flush=False)

        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        errors: List[Exception] = []

        def insert_user(user_id: int):
            try:
                s = Session(db)
                s.execute(insert(User).values(id=user_id, name=f'User{user_id}'))
                s.commit()  # auto_flush=False，只提交到内存
                s.close()
            except Exception as e:
                errors.append(e)

        # 并发插入
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(insert_user, i) for i in range(1, 6)]
            for f in as_completed(futures):
                f.result()

        # 验证内存中有数据
        session = Session(db)
        result = session.execute(select(User))
        users = result.all()
        session.close()

        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert len(users) == 5

        # 手动 flush 后关闭
        db.flush()
        db.close()


class TestThreadSafety:
    """线程安全边界测试"""

    def test_multiple_sessions_same_storage(self, tmp_path):
        """多个 Session 共享同一个 Storage"""
        db_path = tmp_path / "test.db"
        db = Storage(file_path=str(db_path))

        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        # 创建多个 Session
        sessions = [Session(db) for _ in range(5)]

        # 使用第一个 Session 插入数据
        sessions[0].execute(insert(User).values(id=1, name='Alice'))
        sessions[0].commit()

        # 其他 Session 应该能看到数据
        for s in sessions[1:]:
            result = s.execute(select(User))
            users = result.all()
            assert len(users) == 1
            assert users[0].name == 'Alice'

        # 关闭所有 Session
        for s in sessions:
            s.close()

        db.close()

    def test_rapid_open_close_sessions(self, tmp_path):
        """快速打开关闭 Session"""
        db_path = tmp_path / "test.db"
        db = Storage(file_path=str(db_path))

        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        # 插入初始数据
        session = Session(db)
        session.execute(insert(User).values(id=1, name='Alice'))
        session.commit()
        session.close()

        errors: List[Exception] = []

        def rapid_session():
            try:
                for _ in range(10):
                    s = Session(db)
                    result = s.execute(select(User))
                    users = result.all()
                    assert len(users) >= 1
                    s.close()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=rapid_session) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Errors occurred: {errors}"

        db.close()
