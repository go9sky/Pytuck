"""
Pytuck Active Record 模式示例

展示 CRUDBaseModel 的使用方式：
- declarative_base(db, crud=True) 创建带 CRUD 方法的基类
- 模型自带 create, save, delete, refresh, get, filter, filter_by, all 方法
- 无需 Session，直接在模型上操作
"""

import os
import sys
from typing import Type

# 添加父目录到路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from pytuck import Storage, declarative_base, Column
from pytuck import CRUDBaseModel

print("=" * 60)
print("Pytuck Active Record 模式示例")
print("=" * 60)

# ============================================================================
# 1. 初始化数据库和创建 CRUD 基类
# ============================================================================

print("\n1. 初始化数据库")
db = Storage(in_memory=True)
Base: Type[CRUDBaseModel] = declarative_base(db, crud=True)  # 注意 crud=True
print("   ✓ Storage 创建成功")
print("   ✓ CRUD 基类创建成功")

# ============================================================================
# 2. 定义模型（自带 CRUD 方法）
# ============================================================================

print("\n2. 定义模型")


class User(Base):
    """用户模型"""
    __tablename__ = 'users'

    id = Column('id', int, primary_key=True)
    name = Column('name', str, nullable=False)
    email = Column('email', str)
    age = Column('age', int)


print("   ✓ User 模型定义完成")
print(f"   ✓ 模型方法: create, save, delete, refresh, get, filter, filter_by, all")

# ============================================================================
# 3. 创建记录
# ============================================================================

print("\n3. 创建记录")

# 方式 1: 使用 create（自动保存）
alice = User.create(name='Alice', email='alice@example.com', age=25)
print(f"   ✓ create: {alice.name} (ID: {alice.id})")

# 方式 2: 实例化后手动保存
bob = User(name='Bob', email='bob@example.com', age=30)
bob.save()
print(f"   ✓ save: {bob.name} (ID: {bob.id})")

# 批量创建
for i in range(3):
    User.create(name=f'User{i}', email=f'user{i}@example.com', age=20 + i)
print("   ✓ 批量创建 3 个用户")

# ============================================================================
# 4. 查询记录
# ============================================================================

print("\n4. 查询记录")

# 按主键查询
user = User.get(1)
print(f"   get(1): {user.name if user else 'Not found'}")

# 获取所有记录
all_users = User.all()
print(f"   all(): {len(all_users)} 个用户")

# 条件查询（表达式语法）
adults = User.filter(User.age >= 25).all()
print(f"   filter(age >= 25): {[u.name for u in adults]}")

# 等值查询
alice_list = User.filter_by(name='Alice').all()
print(f"   filter_by(name='Alice'): {[u.name for u in alice_list]}")

# 链式查询
young_adults = User.filter(User.age >= 20).filter(User.age < 28).all()
print(f"   filter(age >= 20).filter(age < 28): {[u.name for u in young_adults]}")

# 排序
ordered = User.filter(User.age >= 0).order_by('age', desc=True).all()
print(f"   order_by(age, desc=True): {[f'{u.name}({u.age})' for u in ordered[:3]]}")

# 限制数量
limited = User.filter(User.age >= 0).limit(2).all()
print(f"   limit(2): {[u.name for u in limited]}")

# first()
first_user = User.filter(User.age >= 0).first()
print(f"   first(): {first_user.name if first_user else 'Not found'}")

# count()
count = User.filter(User.age >= 25).count()
print(f"   filter(age >= 25).count(): {count}")

# ============================================================================
# 5. 更新记录
# ============================================================================

print("\n5. 更新记录")

# 获取记录
alice = User.get(1)
print(f"   更新前: {alice.name}, age={alice.age}")

# 修改属性
alice.age = 26
alice.email = 'alice.updated@example.com'
alice.save()
print(f"   更新后: {alice.name}, age={alice.age}")

# 验证更新（通过重新获取）
alice_refreshed = User.get(1)
print(f"   验证: {alice_refreshed.name}, age={alice_refreshed.age}")

# ============================================================================
# 6. 刷新记录
# ============================================================================

print("\n6. 刷新记录 (refresh)")

user = User.get(2)
print(f"   获取 Bob: age={user.age}")

# 模拟外部修改（通过另一个实例）
another_bob = User.get(2)
another_bob.age = 35
another_bob.save()
print(f"   外部修改 Bob: age={another_bob.age}")

# 刷新原实例
user.refresh()
print(f"   刷新后: age={user.age}")

# ============================================================================
# 7. 删除记录
# ============================================================================

print("\n7. 删除记录")

# 查询当前数量
before_count = len(User.all())
print(f"   删除前: {before_count} 个用户")

# 删除单条记录
user_to_delete = User.filter_by(name='User0').first()
if user_to_delete:
    user_to_delete.delete()
    print(f"   ✓ 删除 User0")

# 验证删除
after_count = len(User.all())
print(f"   删除后: {after_count} 个用户")

# ============================================================================
# 8. to_dict 方法
# ============================================================================

print("\n8. to_dict 方法")

user = User.get(1)
user_dict = user.to_dict()
print(f"   to_dict(): {user_dict}")

# ============================================================================
# 总结
# ============================================================================

print("\n" + "=" * 60)
print("总结")
print("=" * 60)
print("Active Record 模式特点:")
print("  ✓ 使用 declarative_base(db, crud=True) 创建基类")
print("  ✓ 模型自带 CRUD 方法，无需 Session")
print("  ✓ create() 创建并保存记录")
print("  ✓ save() 保存或更新记录")
print("  ✓ delete() 删除记录")
print("  ✓ refresh() 从数据库刷新数据")
print("  ✓ get(pk) 按主键查询")
print("  ✓ filter(expr) 条件查询")
print("  ✓ filter_by(**kwargs) 等值查询")
print("  ✓ all() 获取全部记录")
print("\n适用场景:")
print("  - 小型项目和脚本")
print("  - 快速原型开发")
print("  - 简单的 CRUD 操作")
print("  - 对代码简洁性要求高的场景")
print("\n类型注解示例:")
print("  from typing import Type")
print("  from pytuck import CRUDBaseModel")
print("  ")
print("  Base: Type[CRUDBaseModel] = declarative_base(db, crud=True)")

# 关闭数据库
db.close()
print("\n✓ 数据库已关闭")
