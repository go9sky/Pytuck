"""
Pytuck 事务功能演示

展示如何使用事务保证数据一致性
- 使用 declarative_base 和 Session
- 使用 SQLAlchemy 2.0 风格 API
- 演示事务的成功提交和自动回滚
"""

import os
import sys

# 添加父目录到路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from pytuck import Storage, declarative_base, Session, Column
from pytuck import select, insert, update

print("=" * 60)
print("Pytuck 事务功能演示")
print("=" * 60)

# 创建内存数据库
db = Storage(in_memory=True)
Base = declarative_base(db)

# 定义模型
class User(Base):
    """用户模型"""
    __tablename__ = 'users'

    id = Column(int, primary_key=True)
    name = Column(str, nullable=False)
    balance = Column(int)  # 账户余额


class Order(Base):
    """订单模型"""
    __tablename__ = 'orders'

    id = Column(int, primary_key=True)
    user_id = Column(int, index=True)
    amount = Column(int)


# 创建 Session
session = Session(db)

# 插入初始数据
stmt = insert(User).values(name='Alice', balance=1000)
result = session.execute(stmt)
alice_id = result.inserted_primary_key

stmt = insert(User).values(name='Bob', balance=500)
result = session.execute(stmt)
bob_id = result.inserted_primary_key

session.commit()

# 查询初始余额
stmt = select(User).filter_by(id=alice_id)
alice = session.execute(stmt).first()

stmt = select(User).filter_by(id=bob_id)
bob = session.execute(stmt).first()

stmt = select(Order)
orders = session.execute(stmt).all()

print("初始状态:")
print(f"  Alice 余额: {alice.balance}")
print(f"  Bob 余额: {bob.balance}")
print(f"  订单数: {len(orders)}")

print("\n" + "="*60)
print("场景 1: 成功的转账交易")
print("="*60)

# Alice 给 Bob 转账 200 元
with session.begin():
    # 扣除 Alice 的余额
    stmt = update(User).where(User.id == alice_id).values(balance=alice.balance - 200)
    session.execute(stmt)

    # 增加 Bob 的余额
    stmt = update(User).where(User.id == bob_id).values(balance=bob.balance + 200)
    session.execute(stmt)

    # 创建订单记录
    stmt = insert(Order).values(user_id=alice_id, amount=200)
    session.execute(stmt)

# 查询更新后的余额
stmt = select(User).filter_by(id=alice_id)
alice = session.execute(stmt).first()

stmt = select(User).filter_by(id=bob_id)
bob = session.execute(stmt).first()

stmt = select(Order)
orders = session.execute(stmt).all()

print("✓ 转账成功！")
print(f"  Alice 余额: {alice.balance}")
print(f"  Bob 余额: {bob.balance}")
print(f"  订单数: {len(orders)}")

print("\n" + "="*60)
print("场景 2: 失败的转账交易（余额不足）")
print("="*60)

try:
    with session.begin():
        # 获取当前余额
        stmt = select(User).filter_by(id=alice_id)
        alice = session.execute(stmt).first()

        # Alice 尝试转账 2000 元（超过余额）
        new_balance = alice.balance - 2000

        if new_balance < 0:
            raise ValueError("余额不足")

        stmt = update(User).where(User.id == alice_id).values(balance=new_balance)
        session.execute(stmt)

        stmt = select(User).filter_by(id=bob_id)
        bob = session.execute(stmt).first()

        stmt = update(User).where(User.id == bob_id).values(balance=bob.balance + 2000)
        session.execute(stmt)

        stmt = insert(Order).values(user_id=alice_id, amount=2000)
        session.execute(stmt)

except ValueError as e:
    print(f"✗ 转账失败: {e}")

# 验证回滚
stmt = select(User).filter_by(id=alice_id)
alice = session.execute(stmt).first()

stmt = select(User).filter_by(id=bob_id)
bob = session.execute(stmt).first()

stmt = select(Order)
orders = session.execute(stmt).all()

print("✓ 事务自动回滚，数据保持一致:")
print(f"  Alice 余额: {alice.balance}")
print(f"  Bob 余额: {bob.balance}")
print(f"  订单数: {len(orders)}")

print("\n" + "="*60)
print("场景 3: 批量操作")
print("="*60)

# 记录当前订单数
stmt = select(Order)
before_orders = session.execute(stmt).all()
before_count = len(before_orders)

try:
    with session.begin():
        # 批量插入多个订单
        for i in range(5):
            stmt = insert(Order).values(user_id=alice_id, amount=100)
            session.execute(stmt)

        # 模拟错误
        if True:  # 模拟某种业务逻辑错误
            raise Exception("批量操作中发生错误")

except Exception as e:
    print(f"✗ 批量操作失败: {e}")

# 验证回滚
stmt = select(Order)
after_orders = session.execute(stmt).all()
after_count = len(after_orders)

print("✓ 事务回滚，订单未创建:")
print(f"  订单数: {after_count}")

print("\n" + "="*60)
print("场景 4: 使用上下文管理器自动提交")
print("="*60)

print(f"  当前订单数: {after_count}")

# Session 的上下文管理器会自动提交
with Session(db) as s:
    stmt = insert(Order).values(user_id=bob_id, amount=50)
    s.execute(stmt)
    # 退出时自动 commit

# 验证自动提交
stmt = select(Order)
final_orders = session.execute(stmt).all()
final_count = len(final_orders)

print(f"✓ 自动提交成功，订单数: {final_count}")

print("\n" + "="*60)
print("总结")
print("="*60)
print("事务功能确保了数据一致性：")
print("  - 使用 with session.begin() 管理事务")
print("  - 成功时所有操作生效")
print("  - 失败时所有操作自动回滚")
print("  - 不会出现部分更新的情况")
print("  - 使用 with Session(db) 可以自动提交")

# 关闭 session
session.close()
print("\n✓ Session 已关闭")
