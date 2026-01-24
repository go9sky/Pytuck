"""
Pytuck SQLAlchemy 2.0 风格 API 完整示例

展示推荐的使用方式：
- declarative_base() 工厂函数创建基类
- Session 管理所有 CRUD 操作
- execute() 风格明确 IO 边界
- Pythonic 查询表达式
"""

import os
import sys
from typing import Type

# 添加父目录到路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from pytuck import Storage, declarative_base, Session, Column, Relationship
from pytuck import PureBaseModel, select, insert, update, delete

print("=" * 60)
print("Pytuck SQLAlchemy 2.0 风格 API 完整示例")
print("=" * 60)

# ============================================================================
# 1. 初始化数据库和创建声明式基类
# ============================================================================

print("\n1. 初始化数据库")
db = Storage(in_memory=True)
Base: Type[PureBaseModel] = declarative_base(db)  # 类型注解
print("   ✓ Storage 创建成功")
print("   ✓ 声明式基类创建成功")

# ============================================================================
# 2. 定义模型（纯数据模型，无业务方法）
# ============================================================================

print("\n2. 定义模型")


class Class(Base):
    """班级模型"""
    __tablename__ = 'classes'

    id = Column('id', int, primary_key=True)
    name = Column('name', str, nullable=False)


class Student(Base):
    """学生模型"""
    __tablename__ = 'students'

    id = Column('id', int, primary_key=True)
    name = Column('name', str, nullable=False, index=True)
    age = Column('age', int)
    class_id = Column('class_id', int, foreign_key=('classes', 'id'))


print("   ✓ Class 模型定义完成")
print("   ✓ Student 模型定义完成")

# ============================================================================
# 3. 创建 Session
# ============================================================================

print("\n3. 创建 Session")
session = Session(db)
print("   ✓ Session 创建成功")

# ============================================================================
# 4. 插入数据（execute + insert）
# ============================================================================

print("\n4. 插入数据（execute + insert）")

# 插入班级
stmt = insert(Class).values(name='Class A')
result = session.execute(stmt)
class_a_id = result.inserted_primary_key
session.commit()

stmt = insert(Class).values(name='Class B')
result = session.execute(stmt)
class_b_id = result.inserted_primary_key
session.commit()

print(f"   ✓ 插入班级: Class A (ID: {class_a_id})")
print(f"   ✓ 插入班级: Class B (ID: {class_b_id})")

# 批量插入学生
students_data = [
    {'name': 'Alice', 'age': 20, 'class_id': class_a_id},
    {'name': 'Bob', 'age': 21, 'class_id': class_a_id},
    {'name': 'Charlie', 'age': 19, 'class_id': class_b_id},
    {'name': 'David', 'age': 22, 'class_id': class_b_id},
]

for data in students_data:
    stmt = insert(Student).values(**data)
    session.execute(stmt)
session.commit()

print(f"   ✓ 批量插入 {len(students_data)} 个学生")

# ============================================================================
# 5. 查询数据（execute + select）
# ============================================================================

print("\n5. 查询数据（execute + select）")

# 查询所有学生（IO 明确：execute() 处）
stmt = select(Student)
result = session.execute(stmt)
all_students = result.all()
print(f"   ✓ 所有学生: {[s.name for s in all_students]}")

# 条件查询（Pythonic 表达式语法）
stmt = select(Student).where(Student.age >= 20)
result = session.execute(stmt)
adults = result.all()
print(f"   ✓ where(Student.age >= 20): {[s.name for s in adults]}")

# 简单等值查询（filter_by 语法）
stmt = select(Student).filter_by(name='Alice')
result = session.execute(stmt)
alice = result.first()
print(f"   ✓ filter_by(name='Alice'): {alice.name}, {alice.age}岁")

# 多条件查询（AND）
stmt = select(Student).where(
    Student.class_id == class_a_id,
    Student.age < 22
)
result = session.execute(stmt)
young_in_class_a = result.all()
print(f"   ✓ Class A 中年龄 < 22 的学生: {[s.name for s in young_in_class_a]}")

# 混合使用 filter_by 和 where
stmt = select(Student).filter_by(class_id=class_a_id).where(Student.age >= 20)
result = session.execute(stmt)
class_a_adults = result.all()
print(f"   ✓ 混合查询: Class A 成年学生: {[s.name for s in class_a_adults]}")

# 排序和限制
stmt = select(Student).order_by('age', desc=True).limit(2)
result = session.execute(stmt)
top2 = result.all()
print(f"   ✓ order_by + limit: 年龄最大的2人: {[f'{s.name}({s.age})' for s in top2]}")

# 统计
stmt = select(Student)
result = session.execute(stmt)
total = len(result.all())
print(f"   ✓ 总学生数: {total}")

# 不等于查询
stmt = select(Student).where(Student.name != 'Alice')
result = session.execute(stmt)
not_alice = result.all()
print(f"   ✓ 名字不是 Alice 的学生: {[s.name for s in not_alice]}")

# IN 查询
stmt = select(Student).where(Student.age.in_([19, 20, 21]))
result = session.execute(stmt)
teenagers = result.all()
print(f"   ✓ 年龄在 [19, 20, 21] 中的学生: {[s.name for s in teenagers]}")

# ============================================================================
# 6. 更新数据（execute + update）
# ============================================================================

print("\n6. 更新数据（execute + update）")

# 查询 Alice 当前年龄
stmt = select(Student).filter_by(name='Alice')
result = session.execute(stmt)
alice = result.first()
print(f"   原始数据: {alice.name}, 年龄 {alice.age}")

# 更新 Alice 的年龄
stmt = update(Student).where(Student.name == 'Alice').values(age=21)
result = session.execute(stmt)
session.commit()
print(f"   ✓ 更新 Alice 年龄，影响 {result.rowcount()} 行")

# 验证更新
stmt = select(Student).filter_by(name='Alice')
result = session.execute(stmt)
alice_updated = result.first()
print(f"   ✓ 更新后数据: {alice_updated.name}, 年龄 {alice_updated.age}")

# 批量更新
stmt = update(Student).where(Student.age < 20).values(age=20)
result = session.execute(stmt)
session.commit()
print(f"   ✓ 批量更新，影响 {result.rowcount()} 行")

# ============================================================================
# 7. 删除数据（execute + delete）
# ============================================================================

print("\n7. 删除数据（execute + delete）")

# 查询当前总数
stmt = select(Student)
result = session.execute(stmt)
before_count = len(result.all())
print(f"   删除前总数: {before_count}")

# 条件删除
stmt = delete(Student).where(Student.name == 'David')
result = session.execute(stmt)
session.commit()
print(f"   ✓ 删除 David，影响 {result.rowcount()} 行")

# 验证删除
stmt = select(Student)
result = session.execute(stmt)
after_count = len(result.all())
print(f"   删除后总数: {after_count}")

# ============================================================================
# 8. 事务管理
# ============================================================================

print("\n8. 事务管理")

print("   场景 1: 成功的事务")
with session.begin():
    stmt = insert(Student).values(name='Emma', age=20, class_id=class_a_id)
    session.execute(stmt)
    stmt = insert(Student).values(name='Frank', age=21, class_id=class_b_id)
    session.execute(stmt)

stmt = select(Student)
result = session.execute(stmt)
count_after_commit = len(result.all())
print(f"   ✓ 事务提交成功，当前总数: {count_after_commit}")

print("\n   场景 2: 失败的事务（自动回滚）")
stmt = select(Student)
result = session.execute(stmt)
initial_count = len(result.all())

try:
    with session.begin():
        stmt = insert(Student).values(name='Grace', age=23, class_id=class_a_id)
        session.execute(stmt)
        # 模拟错误
        raise ValueError("模拟业务逻辑错误")
except ValueError as e:
    print(f"   ✗ 捕获到异常: {e}")

stmt = select(Student)
result = session.execute(stmt)
final_count = len(result.all())
print(f"   ✓ 事务自动回滚，学生数未变: {initial_count} -> {final_count}")

# ============================================================================
# 9. Result 对象的用法
# ============================================================================

print("\n9. Result 对象的用法")

stmt = select(Student).where(Student.age >= 20)

# 方式 1：all() - 返回模型实例列表
result = session.execute(stmt)
users = result.all()
print(f"   方式 1 - all(): {[u.name for u in users]}")

# 方式 2：first() - 单条查询
result = session.execute(stmt)
first = result.first()
print(f"   方式 2 - first(): {first.name if first else None}")

# 方式 3：one() - 必须恰好一条
stmt_single = select(Student).filter_by(name='Alice')
result = session.execute(stmt_single)
user = result.one()
print(f"   方式 3 - one(): {user.name}")

# 方式 4：one_or_none() - 最多一条
result = session.execute(stmt_single)
user = result.one_or_none()
print(f"   方式 4 - one_or_none(): {user.name if user else None}")

# ============================================================================
# 总结
# ============================================================================

print("\n" + "=" * 60)
print("总结")
print("=" * 60)
print("SQLAlchemy 2.0 风格 API 特点:")
print("  ✓ 使用 declarative_base(db) 创建基类")
print("  ✓ 模型纯粹，只定义数据结构")
print("  ✓ 通过 Session 进行所有 CRUD 操作")
print("  ✓ execute() 明确标识所有 IO 操作")
print("  ✓ Pythonic 查询语法（原生 Python 运算符）")
print("  ✓ 支持事务管理（自动回滚）")
print("  ✓ 支持链式查询")
print("  ✓ 职责分离，架构清晰")
print("\n查询语法示例:")
print("  # 表达式查询（复杂条件）")
print("  stmt = select(Student).where(Student.age >= 20)")
print("  ")
print("  # 简单等值查询（filter_by）")
print("  stmt = select(Student).filter_by(name='Alice')")
print("  ")
print("  # 混合使用")
print("  stmt = select(Student).filter_by(active=True).where(Student.age >= 20)")
print("\n推荐：所有新项目使用 SQLAlchemy 2.0 风格 API！")

# 关闭 session
session.close()
print("\n✓ Session 已关闭")
