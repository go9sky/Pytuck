"""
Pytuck 类型验证演示

展示类型验证和转换功能：
- 宽松模式（默认）：自动类型转换
- 严格模式：类型不匹配报错
- None 值处理
- 类型转换规则
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from pytuck import Storage, declarative_base, Session, Column
from pytuck import PureBaseModel
from pytuck.core.exceptions import ValidationError
from typing import Type

print("=" * 60)
print("Pytuck 类型验证演示")
print("=" * 60)

# 1. 初始化
db = Storage(in_memory=True)
Base: Type[PureBaseModel] = declarative_base(db)

# ============================================================
# 2. 宽松模式（默认）- 自动类型转换
# ============================================================
print("\n2. 宽松模式（默认）- 自动类型转换")

class User(Base):
    __tablename__ = 'users'
    id = Column('id', int, primary_key=True)
    name = Column('name', str, nullable=False)
    age = Column('age', int)
    score = Column('score', float)
    active = Column('active', bool)
    avatar = Column('avatar', bytes, nullable=True)

# 字符串 → int
user1 = User(name='Alice', age='25', score=3.5, active=True)
print(f"   ✓ age='25' → {user1.age} (type: {type(user1.age).__name__})")

# float → int
user2 = User(name='Bob', age=25.9, score=3.5, active=True)
print(f"   ✓ age=25.9 → {user2.age} (type: {type(user2.age).__name__})")

# 字符串 → float
user3 = User(name='Charlie', age=30, score='3.14', active=True)
print(f"   ✓ score='3.14' → {user3.score} (type: {type(user3.score).__name__})")

# int → str
user4 = User(name=123, age=30, score=3.5, active=True)
print(f"   ✓ name=123 → '{user4.name}' (type: {type(user4.name).__name__})")

# 布尔转换
user5 = User(name='David', age=30, score=3.5, active=1)
print(f"   ✓ active=1 → {user5.active} (type: {type(user5.active).__name__})")

user6 = User(name='Eve', age=30, score=3.5, active='true')
print(f"   ✓ active='true' → {user6.active} (type: {type(user6.active).__name__})")

# 字符串 → bytes
user7 = User(name='Frank', age=30, score=3.5, active=True, avatar='hello')
print(f"   ✓ avatar='hello' → {user7.avatar} (type: {type(user7.avatar).__name__})")

# ============================================================
# 3. 严格模式 - 类型不匹配报错
# ============================================================
print("\n3. 严格模式 - 类型不匹配报错")

class StrictUser(Base):
    __tablename__ = 'strict_users'
    id = Column('id', int, primary_key=True)
    name = Column('name', str, nullable=False, strict=True)
    age = Column('age', int, strict=True)
    score = Column('score', float, strict=True)
    active = Column('active', bool, strict=True)

# 正确类型：成功
user = StrictUser(name='George', age=30, score=3.14, active=True)
print(f"   ✓ 正确类型：name='{user.name}', age={user.age}")

# 错误类型：失败
try:
    StrictUser(name='Helen', age='25', score=3.5, active=True)
except ValidationError as e:
    print(f"   ✓ age='25' (str) → ValidationError: {e}")

try:
    StrictUser(name=123, age=30, score=3.5, active=True)
except ValidationError as e:
    print(f"   ✓ name=123 (int) → ValidationError: {e}")

try:
    StrictUser(name='Ivan', age=30, score='3.14', active=True)
except ValidationError as e:
    print(f"   ✓ score='3.14' (str) → ValidationError: {e}")

try:
    StrictUser(name='Jack', age=30, score=3.5, active=1)
except ValidationError as e:
    print(f"   ✓ active=1 (int) → ValidationError: {e}")

# ============================================================
# 4. None 值处理
# ============================================================
print("\n4. None 值处理")

class Product(Base):
    __tablename__ = 'products'
    id = Column('id', int, primary_key=True)
    name = Column('name', str, nullable=False)  # NOT NULL
    description = Column('description', str, nullable=True)  # NULL OK
    price = Column('price', float, nullable=False)  # NOT NULL

# nullable=True：允许 None
product = Product(name='Product A', description=None, price=99.9)
print(f"   ✓ description=None (nullable=True): {product.description}")

# nullable=False：拒绝 None
try:
    Product(name=None, description='Test', price=99.9)
except ValidationError as e:
    print(f"   ✓ name=None (nullable=False) → ValidationError: {e}")

# ============================================================
# 5. 布尔转换规则
# ============================================================
print("\n5. 布尔转换规则")

true_values = [True, 1, '1', 'true', 'True', 'yes', 'Yes']
false_values = [False, 0, '0', 'false', 'False', 'no', 'No', '']

print("   True 值:")
for val in true_values:
    user = User(name='Test', age=20, score=3.5, active=val)
    print(f"      {repr(val):15} → {user.active}")

print("   False 值:")
for val in false_values:
    user = User(name='Test', age=20, score=3.5, active=val)
    print(f"      {repr(val):15} → {user.active}")

# 无效布尔字符串
try:
    User(name='Test', age=20, score=3.5, active='maybe')
except ValidationError as e:
    print(f"   ✓ active='maybe' → ValidationError: {e}")

# ============================================================
# 6. int vs bool 类型分离
# ============================================================
print("\n6. int vs bool 类型分离")

class Data(Base):
    __tablename__ = 'data'
    id = Column('id', int, primary_key=True)
    count = Column('count', int)
    flag = Column('flag', bool)

# int 列接受 int
data1 = Data(count=42, flag=True)
print(f"   ✓ count=42 → {data1.count} (type: {type(data1.count).__name__})")
print(f"   ✓ isinstance(count, int): {isinstance(data1.count, int)}")
print(f"   ✓ isinstance(count, bool): {isinstance(data1.count, bool)}")

# int 列拒绝 bool（虽然 bool 是 int 子类）
try:
    Data(count=True, flag=True)
except ValidationError as e:
    print(f"   ✓ count=True (bool) → ValidationError: {e}")

# bool 列接受 bool
data2 = Data(count=42, flag=False)
print(f"   ✓ flag=False → {data2.flag} (type: {type(data2.flag).__name__})")

# ============================================================
# 7. 类型转换规则总结
# ============================================================
print("\n7. 类型转换规则总结（宽松模式）")
print("   ┌────────────┬────────────────────┬─────────────────┐")
print("   │ Python类型 │ 转换规则           │ 示例            │")
print("   ├────────────┼────────────────────┼─────────────────┤")
print("   │ int        │ int(value)         │ '123' → 123     │")
print("   │ float      │ float(value)       │ '3.14' → 3.14   │")
print("   │ str        │ str(value)         │ 123 → '123'     │")
print("   │ bool       │ 特殊规则*          │ '1' → True      │")
print("   │ bytes      │ encode() 如果是str │ 'hi' → b'hi'    │")
print("   │ None       │ nullable=True允许  │ None → None     │")
print("   └────────────┴────────────────────┴─────────────────┘")
print("   * bool 规则:")
print("      True: True, 1, '1', 'true', 'True', 'yes', 'Yes'")
print("      False: False, 0, '0', 'false', 'False', 'no', 'No', ''")

# ============================================================
# 总结
# ============================================================
print("\n" + "=" * 60)
print("总结")
print("=" * 60)
print("类型验证特性:")
print("  ✓ 宽松模式（默认）：自动类型转换，对用户友好")
print("  ✓ 严格模式：Column(strict=True)，类型不匹配报错")
print("  ✓ None 值：nullable=True 允许 None")
print("  ✓ 零依赖：使用标准库实现")
print("  ✓ 类型安全：int 列拒绝 bool（虽然 bool 是 int 子类）")
print("\n推荐:")
print("  • 默认使用宽松模式：提高开发效率")
print("  • 关键字段使用严格模式：确保类型安全")
print("  • 生产环境：结合业务需求选择合适模式")

db.close()
