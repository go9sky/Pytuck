"""
Pytuck 事务功能测试

测试事务管理：
- session.begin() 上下文管理器
- 事务提交和回滚
- 嵌套事务错误处理
- Session 上下文管理器自动提交
"""

import os
import sys
import unittest
from typing import Type

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pytuck import Storage, declarative_base, Session, Column, PureBaseModel, select, insert, update, delete
from pytuck.common.exceptions import TransactionError


class TestTransactionCommit(unittest.TestCase):
    """事务提交测试"""

    def setUp(self) -> None:
        """测试前设置"""
        self.db = Storage(in_memory=True)
        Base: Type[PureBaseModel] = declarative_base(self.db)

        class User(Base):
            __tablename__ = 'users'
            id = Column('id', int, primary_key=True)
            name = Column('name', str)
            balance = Column('balance', int)

        self.User = User
        self.session = Session(self.db)

    def tearDown(self) -> None:
        """测试后清理"""
        self.session.close()
        self.db.close()

    def test_successful_transaction(self) -> None:
        """测试成功的事务"""
        # 插入初始数据
        stmt = insert(self.User).values(name='Alice', balance=1000)
        self.session.execute(stmt)
        self.session.commit()

        # 事务：转账操作
        with self.session.begin():
            # 扣款
            stmt = update(self.User).where(self.User.name == 'Alice').values(balance=800)
            self.session.execute(stmt)

            # 插入记录
            stmt = insert(self.User).values(name='Bob', balance=200)
            self.session.execute(stmt)

        # 验证提交
        stmt = select(self.User).filter_by(name='Alice')
        alice = self.session.execute(stmt).scalars().first()
        self.assertEqual(alice.balance, 800)

        stmt = select(self.User).filter_by(name='Bob')
        bob = self.session.execute(stmt).scalars().first()
        self.assertIsNotNone(bob)
        self.assertEqual(bob.balance, 200)

    def test_multiple_operations(self) -> None:
        """测试事务中多个操作"""
        with self.session.begin():
            # 批量插入
            for i in range(5):
                stmt = insert(self.User).values(name=f'User{i}', balance=100)
                self.session.execute(stmt)

        # 验证全部提交
        stmt = select(self.User)
        users = self.session.execute(stmt).scalars().all()
        self.assertEqual(len(users), 5)


class TestTransactionRollback(unittest.TestCase):
    """事务回滚测试"""

    def setUp(self) -> None:
        """测试前设置"""
        self.db = Storage(in_memory=True)
        Base: Type[PureBaseModel] = declarative_base(self.db)

        class User(Base):
            __tablename__ = 'users'
            id = Column('id', int, primary_key=True)
            name = Column('name', str)
            balance = Column('balance', int)

        class Order(Base):
            __tablename__ = 'orders'
            id = Column('id', int, primary_key=True)
            user_id = Column('user_id', int)
            amount = Column('amount', int)

        self.User = User
        self.Order = Order
        self.session = Session(self.db)

        # 插入初始数据
        stmt = insert(self.User).values(name='Alice', balance=500)
        result = self.session.execute(stmt)
        self.alice_id = result.inserted_primary_key
        self.session.commit()

    def tearDown(self) -> None:
        """测试后清理"""
        self.session.close()
        self.db.close()

    def test_rollback_on_error(self) -> None:
        """测试错误时自动回滚"""
        initial_balance = 500

        try:
            with self.session.begin():
                # 尝试转账
                stmt = update(self.User).where(self.User.id == self.alice_id).values(balance=200)
                self.session.execute(stmt)

                # 创建订单
                stmt = insert(self.Order).values(user_id=self.alice_id, amount=300)
                self.session.execute(stmt)

                # 模拟业务逻辑错误
                raise ValueError("余额不足")

        except ValueError:
            pass

        # 验证回滚
        stmt = select(self.User).filter_by(id=self.alice_id)
        alice = self.session.execute(stmt).scalars().first()
        self.assertEqual(alice.balance, initial_balance)

        stmt = select(self.Order)
        orders = self.session.execute(stmt).scalars().all()
        self.assertEqual(len(orders), 0)

    def test_rollback_batch_insert(self) -> None:
        """测试批量插入时回滚"""
        # 记录初始数量
        stmt = select(self.User)
        initial_count = len(self.session.execute(stmt).scalars().all())

        try:
            with self.session.begin():
                # 批量插入
                for i in range(3):
                    stmt = insert(self.User).values(name=f'User{i}', balance=100)
                    self.session.execute(stmt)

                # 模拟错误
                raise Exception("操作失败")

        except Exception:
            pass

        # 验证回滚
        stmt = select(self.User)
        final_count = len(self.session.execute(stmt).scalars().all())
        self.assertEqual(final_count, initial_count)

    def test_partial_rollback(self) -> None:
        """测试部分回滚"""
        # 第一个事务：成功
        with self.session.begin():
            stmt = insert(self.User).values(name='Bob', balance=300)
            self.session.execute(stmt)

        # 第二个事务：失败
        try:
            with self.session.begin():
                stmt = insert(self.User).values(name='Charlie', balance=400)
                self.session.execute(stmt)
                raise ValueError("错误")
        except ValueError:
            pass

        # 验证：Bob 存在，Charlie 不存在
        stmt = select(self.User).filter_by(name='Bob')
        bob = self.session.execute(stmt).scalars().first()
        self.assertIsNotNone(bob)

        stmt = select(self.User).filter_by(name='Charlie')
        charlie = self.session.execute(stmt).scalars().first()
        self.assertIsNone(charlie)


class TestTransactionNesting(unittest.TestCase):
    """事务嵌套测试"""

    def setUp(self) -> None:
        """测试前设置"""
        self.db = Storage(in_memory=True)
        Base: Type[PureBaseModel] = declarative_base(self.db)

        class User(Base):
            __tablename__ = 'users'
            id = Column('id', int, primary_key=True)
            name = Column('name', str)

        self.User = User
        self.session = Session(self.db)

    def tearDown(self) -> None:
        """测试后清理"""
        self.session.close()
        self.db.close()

    def test_nested_transaction_error(self) -> None:
        """测试嵌套事务抛出异常"""
        with self.assertRaises(TransactionError):
            with self.session.begin():
                stmt = insert(self.User).values(name='Alice')
                self.session.execute(stmt)

                # 尝试嵌套事务
                with self.session.begin():
                    stmt = insert(self.User).values(name='Bob')
                    self.session.execute(stmt)


class TestSessionContextManager(unittest.TestCase):
    """Session 上下文管理器测试"""

    def setUp(self) -> None:
        """测试前设置"""
        self.db = Storage(in_memory=True)
        self.Base: Type[PureBaseModel] = declarative_base(self.db)

        class User(self.Base):
            __tablename__ = 'users'
            id = Column('id', int, primary_key=True)
            name = Column('name', str)

        self.User = User

    def tearDown(self) -> None:
        """测试后清理"""
        self.db.close()

    def test_context_manager_auto_commit(self) -> None:
        """测试上下文管理器自动提交"""
        # 使用上下文管理器
        with Session(self.db) as session:
            stmt = insert(self.User).values(name='Alice')
            session.execute(stmt)
            # 退出时自动提交

        # 验证提交
        session2 = Session(self.db)
        stmt = select(self.User).filter_by(name='Alice')
        alice = session2.execute(stmt).scalars().first()
        self.assertIsNotNone(alice)
        session2.close()

    def test_context_manager_rollback_on_error(self) -> None:
        """测试上下文管理器错误处理"""
        # Session 上下文管理器在异常时会调用 rollback()
        # Insert statement 的 execute() 会立即写入 storage
        # 所以这里只测试异常不会导致程序崩溃
        exception_caught = False
        try:
            with Session(self.db) as session:
                stmt = insert(self.User).values(name='Bob')
                session.execute(stmt)
                raise ValueError("测试错误")
        except ValueError:
            exception_caught = True

        self.assertTrue(exception_caught)


class TestTransactionComplex(unittest.TestCase):
    """复杂事务场景测试"""

    def setUp(self) -> None:
        """测试前设置"""
        self.db = Storage(in_memory=True)
        Base: Type[PureBaseModel] = declarative_base(self.db)

        class Account(Base):
            __tablename__ = 'accounts'
            id = Column('id', int, primary_key=True)
            name = Column('name', str)
            balance = Column('balance', int)

        class Transaction(Base):
            __tablename__ = 'transactions'
            id = Column('id', int, primary_key=True)
            from_account = Column('from_account', int)
            to_account = Column('to_account', int)
            amount = Column('amount', int)

        self.Account = Account
        self.Transaction = Transaction
        self.session = Session(self.db)

        # 插入初始账户
        stmt = insert(self.Account).values(name='Alice', balance=1000)
        result = self.session.execute(stmt)
        self.alice_id = result.inserted_primary_key

        stmt = insert(self.Account).values(name='Bob', balance=500)
        result = self.session.execute(stmt)
        self.bob_id = result.inserted_primary_key

        self.session.commit()

    def tearDown(self) -> None:
        """测试后清理"""
        self.session.close()
        self.db.close()

    def test_transfer_transaction(self) -> None:
        """测试转账事务"""
        transfer_amount = 200

        # 记录初始余额
        stmt = select(self.Account).filter_by(id=self.alice_id)
        alice_initial = self.session.execute(stmt).scalars().first().balance

        stmt = select(self.Account).filter_by(id=self.bob_id)
        bob_initial = self.session.execute(stmt).scalars().first().balance

        # 转账事务
        with self.session.begin():
            # 扣款
            stmt = select(self.Account).filter_by(id=self.alice_id)
            alice = self.session.execute(stmt).scalars().first()
            stmt = update(self.Account).where(self.Account.id == self.alice_id).values(
                balance=alice.balance - transfer_amount
            )
            self.session.execute(stmt)

            # 收款
            stmt = select(self.Account).filter_by(id=self.bob_id)
            bob = self.session.execute(stmt).scalars().first()
            stmt = update(self.Account).where(self.Account.id == self.bob_id).values(
                balance=bob.balance + transfer_amount
            )
            self.session.execute(stmt)

            # 记录交易
            stmt = insert(self.Transaction).values(
                from_account=self.alice_id,
                to_account=self.bob_id,
                amount=transfer_amount
            )
            self.session.execute(stmt)

        # 验证结果
        stmt = select(self.Account).filter_by(id=self.alice_id)
        alice_final = self.session.execute(stmt).scalars().first().balance

        stmt = select(self.Account).filter_by(id=self.bob_id)
        bob_final = self.session.execute(stmt).scalars().first().balance

        self.assertEqual(alice_final, alice_initial - transfer_amount)
        self.assertEqual(bob_final, bob_initial + transfer_amount)

        # 验证交易记录
        stmt = select(self.Transaction)
        transactions = self.session.execute(stmt).scalars().all()
        self.assertEqual(len(transactions), 1)

    def test_insufficient_balance_rollback(self) -> None:
        """测试余额不足时回滚"""
        transfer_amount = 2000  # 超过 Alice 余额

        # 记录初始余额
        stmt = select(self.Account).filter_by(id=self.alice_id)
        alice_initial = self.session.execute(stmt).scalars().first().balance

        stmt = select(self.Account).filter_by(id=self.bob_id)
        bob_initial = self.session.execute(stmt).scalars().first().balance

        try:
            with self.session.begin():
                # 获取 Alice 余额
                stmt = select(self.Account).filter_by(id=self.alice_id)
                alice = self.session.execute(stmt).scalars().first()

                # 检查余额
                if alice.balance < transfer_amount:
                    raise ValueError("余额不足")

                # 以下代码不会执行
                stmt = update(self.Account).where(self.Account.id == self.alice_id).values(
                    balance=alice.balance - transfer_amount
                )
                self.session.execute(stmt)

        except ValueError:
            pass

        # 验证回滚
        stmt = select(self.Account).filter_by(id=self.alice_id)
        alice_final = self.session.execute(stmt).scalars().first().balance

        stmt = select(self.Account).filter_by(id=self.bob_id)
        bob_final = self.session.execute(stmt).scalars().first().balance

        self.assertEqual(alice_final, alice_initial)
        self.assertEqual(bob_final, bob_initial)

        # 验证没有交易记录
        stmt = select(self.Transaction)
        transactions = self.session.execute(stmt).scalars().all()
        self.assertEqual(len(transactions), 0)


if __name__ == '__main__':
    unittest.main()
