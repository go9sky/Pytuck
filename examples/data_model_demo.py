"""
Pytuck 数据模型特性演示

展示 Pytuck 数据模型作为独立数据容器的特性：
- Session 关闭后仍可访问
- Storage 关闭后仍可访问
- 可序列化（JSON）
- 可作为纯数据容器使用
- 对比 SQLAlchemy 的 DetachedInstanceError
"""

import sys
import os
import json
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from pytuck import Storage, declarative_base, Session, Column
from pytuck import PureBaseModel, select, insert
from typing import Type

print("=" * 60)
print("Pytuck 数据模型特性演示")
print("=" * 60)

# 1. 初始化
db = Storage(in_memory=True)
Base: Type[PureBaseModel] = declarative_base(db)

class User(Base):
    __tablename__ = 'users'
    id = Column('id', int, primary_key=True)
    name = Column('name', str)
    age = Column('age', int)
    email = Column('email', str, nullable=True)

session = Session(db)

# 插入测试数据
for name, age in [('Alice', 20), ('Bob', 25), ('Charlie', 30)]:
    stmt = insert(User).values(name=name, age=age, email=f'{name.lower()}@example.com')
    session.execute(stmt)
session.commit()

# ============================================================
# 2. Session 关闭后仍可访问
# ============================================================
print("\n2. Session 关闭后仍可访问")

stmt = select(User).where(User.name == 'Alice')
alice = session.execute(stmt).scalars().first()

print(f"   查询前: {alice.name}, {alice.age}岁, email={alice.email}")

# 关闭 Session
session.close()

print(f"   Session 关闭后: {alice.name}, {alice.age}岁, email={alice.email}")
print(f"   ✓ 仍可访问属性")
print(f"   ✓ to_dict() 仍可用: {alice.to_dict()}")

# ============================================================
# 3. Storage 关闭后仍可访问
# ============================================================
print("\n3. Storage 关闭后仍可访问")

# 重新打开
db2 = Storage(in_memory=True)
Base2: Type[PureBaseModel] = declarative_base(db2)

class User2(Base2):
    __tablename__ = 'users'
    id = Column('id', int, primary_key=True)
    name = Column('name', str)
    age = Column('age', int)

session2 = Session(db2)
stmt = insert(User2).values(name='David', age=35)
session2.execute(stmt)
session2.commit()

stmt = select(User2).where(User2.name == 'David')
david = session2.execute(stmt).scalars().first()

print(f"   查询前: {david.name}, {david.age}岁")

# 关闭 Session 和 Storage
session2.close()
db2.close()

print(f"   Session 和 Storage 关闭后: {david.name}, {david.age}岁")
print(f"   ✓ 仍可访问属性")
print(f"   ✓ 对象完全独立于连接")

# ============================================================
# 4. 可序列化（JSON）
# ============================================================
print("\n4. 可序列化（JSON）")

# 单个对象序列化
user_dict = alice.to_dict()
user_json = json.dumps(user_dict, indent=2)
print(f"   单个对象 JSON:")
print("   " + user_json.replace("\n", "\n   "))

# 列表序列化（查询多条）
db3 = Storage(in_memory=True)
Base3: Type[PureBaseModel] = declarative_base(db3)

class User3(Base3):
    __tablename__ = 'users'
    id = Column('id', int, primary_key=True)
    name = Column('name', str)
    age = Column('age', int)

session3 = Session(db3)
for name, age in [('Eve', 22), ('Frank', 28)]:
    stmt = insert(User3).values(name=name, age=age)
    session3.execute(stmt)
session3.commit()

stmt = select(User3)
users = session3.execute(stmt).scalars().all()
session3.close()

users_list = [u.to_dict() for u in users]
users_json = json.dumps(users_list, indent=2)
print(f"\n   列表 JSON:")
print("   " + users_json.replace("\n", "\n   "))

# ============================================================
# 5. 作为纯数据容器使用
# ============================================================
print("\n5. 作为纯数据容器使用")

def format_user(user: PureBaseModel) -> str:
    """格式化用户信息（普通函数，无需数据库连接）"""
    return f"{user.name} ({user.age}岁)"

def filter_adults(users: list) -> list:
    """筛选成年人（普通列表操作）"""
    return [u for u in users if u.age >= 25]

# 传递给普通函数
formatted = format_user(alice)
print(f"   格式化函数: {formatted}")

# 列表操作
adults = filter_adults([alice, david])
print(f"   筛选成年人: {[format_user(u) for u in adults]}")

# API 响应格式
api_response = {
    'status': 'success',
    'data': alice.to_dict(),
    'meta': {'total': 1}
}
print(f"   API 响应: {json.dumps(api_response, ensure_ascii=False)}")

# ============================================================
# 6. 对比 SQLAlchemy
# ============================================================
print("\n6. 对比 SQLAlchemy")

comparison_table = """
   ┌──────────────────────────┬──────────┬─────────────────┐
   │ 特性                     │ Pytuck   │ SQLAlchemy      │
   ├──────────────────────────┼──────────┼─────────────────┤
   │ Session 关闭后访问属性   │ ✅ 支持  │ ❌ Detached     │
   │ Storage 关闭后访问       │ ✅ 支持  │ ❌ Detached     │
   │ 延迟加载关联对象         │ ❌ 无    │ ✅ 支持         │
   │ 模型作为纯数据容器       │ ✅ 是    │ ❌ 绑定 session │
   │ 查询结果物化时机         │ 立即     │ 延迟（可选）    │
   │ 适合作为 API 响应        │ ✅ 是    │ 需要 detach     │
   └──────────────────────────┴──────────┴─────────────────┘
"""
print(comparison_table)

print("\n   SQLAlchemy 示例（会报错）:")
print("""
   # SQLAlchemy 代码
   session = Session(engine)
   user = session.query(User).filter_by(name='Alice').first()
   session.close()

   # ❌ DetachedInstanceError: Instance is not bound to a Session
   print(user.name)
""")

print("\n   Pytuck 示例（不会报错）:")
print("""
   # Pytuck 代码
   session = Session(db)
   stmt = select(User).where(User.name == 'Alice')
   user = session.execute(stmt).scalars().first()
   session.close()

   # ✅ 正常工作
   print(user.name)
""")

# ============================================================
# 7. 使用场景
# ============================================================
print("\n7. 使用场景")

scenarios = """
   ✅ 适合场景:
      • Web API 开发：查询后直接返回模型，无需担心连接
      • 数据传递：模型对象可以在函数间自由传递
      • 数据导出：查询后关闭连接，慢慢处理数据
      • 缓存结果：可以缓存模型对象而非字典
      • 单元测试：测试数据访问逻辑，无需保持连接

   ⚠️  不适合场景:
      • 需要延迟加载：Pytuck 立即加载所有数据
      • 大数据集流式处理：所有数据立即加载到内存
      • 复杂关联查询：需要手动实现 JOIN
"""
print(scenarios)

# ============================================================
# 总结
# ============================================================
print("\n" + "=" * 60)
print("总结")
print("=" * 60)
print("数据模型特性:")
print("  ✓ 独立性：查询结果立即物化到内存，完全独立")
print("  ✓ 无延迟加载：所有数据立即加载，无 lazy loading")
print("  ✓ 可序列化：支持 JSON、Pickle 等序列化")
print("  ✓ 纯数据容器：像 Pydantic 模型一样使用")
print("\n优势:")
print("  • 简单：无需担心 Session 状态")
print("  • 灵活：对象可以自由传递和缓存")
print("  • 适合 API：天然支持作为响应对象")
print("\n注意:")
print("  • 大数据集：会立即加载到内存")
print("  • 关联查询：需要手动 JOIN")

db3.close()
