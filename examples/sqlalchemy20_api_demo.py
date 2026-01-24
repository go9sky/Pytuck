"""
Pytuck SQLAlchemy 2.0 风格 API 演示

展示新的 execute() 风格 API：
- 使用 select(), insert(), update(), delete() 构建语句
- 使用 session.execute(stmt) 执行
- IO 操作明确可见
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from pytuck import (
    Storage, declarative_base, Session, Column,
    select, insert, update, delete
)

print("=" * 60)
print("Pytuck SQLAlchemy 2.0 风格 API 演示")
print("=" * 60)

# 1. 初始化
db = Storage(in_memory=True)
Base = declarative_base(db)

class User(Base):
    __tablename__ = 'users'
    id = Column('id', int, primary_key=True)
    name = Column('name', str, nullable=False)
    age = Column('age', int)

session = Session(db)

# ============================================================
# 2. 插入数据（execute + insert）
# ============================================================
print("\n2. 插入数据（execute + insert）")

# 单条插入
stmt = insert(User).values(name='Alice', age=20)
result = session.execute(stmt)
u1 = User(name='Eve', age=22)
print('user1构造：', u1.to_dict())
session.add(u1)
print('user1添加到session：', u1.to_dict())
session.flush()
print("   ✓ user1 flush后：", u1.to_dict())
session.commit()
print("   ✓ user1插入后：", u1.to_dict())
print(f"   ✓ 插入成功，主键: {result.inserted_primary_key}")

u2 = User(name='Frank', age='28')
session.add(u2)
session.flush()
session.close()
print("   ✓ user2 session关闭后：", u2.to_dict())

# 批量插入
for name, age in [('Bob', 25), ('Charlie', 19), ('David', 30)]:
    stmt = insert(User).values(name=name, age=age)
    session.execute(stmt)
session.commit()
print(f"   ✓ 批量插入完成")

# ============================================================
# 3. 查询数据（execute + select）
# ============================================================
print("\n3. 查询数据（execute + select）")

# 查询所有（IO 明确：execute() 处）
stmt = select(User)
result = session.execute(stmt)
users = result.all()
print(f"   ✓ 所有用户: {[u.name for u in users]}")

# 条件查询（表达式语法）
stmt = select(User).where(User.age >= 20)
result = session.execute(stmt)
adults = result.all()
print(f"   ✓ where(User.age >= 20): {[u.name for u in adults]}")

# 简单等值查询（filter_by 语法）
stmt = select(User).filter_by(name='Alice')
result = session.execute(stmt)
alice = result.first()
print(f"   ✓ filter_by(name='Alice'): {alice.name}, {alice.age}岁")

# 多条件等值查询
stmt = select(User).filter_by(age=20)
result = session.execute(stmt)
age_20 = result.all()
print(f"   ✓ filter_by(age=20): {[u.name for u in age_20]}")

# 混合使用 filter_by 和 where
stmt = select(User).filter_by(name='Bob').where(User.age >= 20)
result = session.execute(stmt)
bob = result.first()
print(f"   ✓ 混合查询 filter_by + where: {bob.name if bob else 'Not found'}")

# 多条件（AND）
stmt = select(User).where(User.age >= 20, User.age < 30)
result = session.execute(stmt)
young_adults = result.all()
print(f"   ✓ where(多条件): 20 <= 年龄 < 30: {[u.name for u in young_adults]}")

# 排序和限制
stmt = select(User).order_by('age', desc=True).limit(2)
result = session.execute(stmt)
top2 = result.all()
print(f"   ✓ order_by + limit: 年龄最大的2人: {[f'{u.name}({u.age})' for u in top2]}")

# 获取后访问
stmt = select(User).where(User.id == 2)
result = session.execute(stmt)
user2 = result.first()
print(f"   ✓ 获取后访问: ID=2 的用户是 {user2.name}, {user2.age}岁")
session.close()
print(f'   ✓ session 关闭后，user2 仍然可访问: {user2.name}, {user2.age}岁')

# ============================================================
# 4. 更新数据（execute + update）
# ============================================================
print("\n4. 更新数据（execute + update）")

# 更新单条（通过update）
stmt = update(User).where(User.name == 'Alice').values(age=21)
result = session.execute(stmt)
session.commit()
print(f"   ✓ 更新 Alice 年龄，影响 {result.rowcount()} 行")

# 验证更新
stmt = select(User).where(User.name == 'Alice')
result = session.execute(stmt)
alice = result.first()
print(f"   ✓ 验证：{alice.name} 现在 {alice.age} 岁")

# 单条更新（通过模型实例）
stmt = select(User).where(User.name == 'Bob')
result = session.execute(stmt)
bob = result.first()
print(f'   ✓ 原始数据: {bob.name}, 年龄 {bob.age}')
bob.age = 99
session.flush()
session.commit()

# 验证更新
stmt = select(User).where(User.name == 'Bob')
result = session.execute(stmt)
bob_reloaded = result.first()
print(f"   ✓ 验证：{bob_reloaded.name} 现在 {bob_reloaded.age} 岁")

# 批量更新
stmt = update(User).where(User.age < 20).values(age=20)
result = session.execute(stmt)
session.commit()
print(f"   ✓ 批量更新，影响 {result.rowcount()} 行")

# ============================================================
# 5. 删除数据（execute + delete）
# ============================================================
print("\n5. 删除数据（execute + delete）")

# 条件删除
stmt = delete(User).where(User.name == 'David')
result = session.execute(stmt)
session.commit()
print(f"   ✓ 删除 David，影响 {result.rowcount()} 行")

# 验证删除
stmt = select(User)
result = session.execute(stmt)
remaining = result.all()
print(f"   ✓ 剩余用户: {[u.name for u in remaining]}")

# ============================================================
# 6. Result 对象的多种用法
# ============================================================
print("\n6. Result 对象的多种用法")

stmt = select(User).where(User.age >= 20)
result = session.execute(stmt)

# 方式 1：result.all() - 返回模型实例列表（直接返回模型实例）
users = result.all()
print(f"   方式 1 - result.all(): {[u.name for u in users]}")

# 重新查询（Result 只能消费一次）
result = session.execute(stmt)

# 方式 2：all() - 返回 Row 对象列表
rows = result.all()
print(f"   方式 2 - all(): {[row.name for row in rows]}")

# 重新查询
result = session.execute(stmt)

# 方式 3：result.all() - 返回字典列表（fetchall 已移除）
dicts = result.all()
print(f"   方式 3 - fetchall(): {[d['name'] for d in dicts]}")

# ============================================================
# 总结
# ============================================================
print("\n" + "=" * 60)
print("总结")
print("=" * 60)
print("SQLAlchemy 2.0 风格 API 特点:")
print("  ✓ IO 明确：所有数据库操作都通过 execute() 执行")
print("  ✓ 一致性：增删改查使用统一的 statement 模式")
print("  ✓ 灵活性：Result 提供多种数据提取方式")
print("  ✓ 类型安全：IDE 友好，更好的代码补全")
print("\n语法对比:")
print("  旧：session.query(User).filter(User.age >= 20).all()")
print("  新：session.execute(select(User).where(User.age >= 20)).all()")
print("\n推荐：新项目使用 execute() 风格，旧项目逐步迁移")

session.close()
