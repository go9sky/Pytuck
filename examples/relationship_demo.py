"""
Pytuck Relationship 关联关系示例

展示 Relationship 的各种使用方式：
- 一对多关联（One-to-Many）
- 多对一关联（Many-to-One）
- 双向关联（Bidirectional）
- 字符串引用（使用表名）
- 一对一关联（One-to-One）
- 多对多关联（Many-to-Many，通过中间表）
- 自引用关联（Self-Reference，树形结构）
"""

import os
import sys
from typing import Type

# 添加父目录到路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from pytuck import Storage, declarative_base, Column
from pytuck import CRUDBaseModel
from pytuck.core.orm import Relationship

print("=" * 70)
print("Pytuck Relationship 关联关系示例")
print("=" * 70)

# ============================================================================
# 1. 基础示例：一对多 / 多对一关联（使用表名字符串引用）
# ============================================================================

print("\n" + "=" * 70)
print("1. 基础示例：一对多 / 多对一关联")
print("=" * 70)

db1 = Storage(in_memory=True)
Base1: Type[CRUDBaseModel] = declarative_base(db1, crud=True)


# 使用字符串（表名）定义关联 - 无需考虑类定义顺序
class Order(Base1):
    """订单模型"""
    __tablename__ = 'orders'

    id = Column('id', int, primary_key=True)
    user_id = Column('user_id', int)
    amount = Column('amount', float)

    # 多对一：订单 -> 用户（使用表名引用，此时 User 类尚未定义）
    user = Relationship('users', foreign_key='user_id')


class User(Base1):
    """用户模型"""
    __tablename__ = 'users'

    id = Column('id', int, primary_key=True)
    name = Column('name', str)

    # 一对多：用户 -> 订单（使用表名引用）
    orders = Relationship('orders', foreign_key='user_id', back_populates='user')


# 创建测试数据
alice = User.create(name='Alice')
bob = User.create(name='Bob')

order1 = Order.create(user_id=alice.id, amount=100.0)
order2 = Order.create(user_id=alice.id, amount=200.0)
order3 = Order.create(user_id=bob.id, amount=150.0)

print("\n   创建的数据：")
print(f"   - 用户: Alice (id={alice.id}), Bob (id={bob.id})")
print(f"   - 订单: #{order1.id} (Alice, 100.0), #{order2.id} (Alice, 200.0), #{order3.id} (Bob, 150.0)")

# 一对多访问：用户 -> 订单列表
alice_obj = User.get(alice.id)
print(f"\n   一对多访问 (User -> Orders):")
print(f"   - Alice 的订单数量: {len(alice_obj.orders)}")
for order in alice_obj.orders:
    print(f"     - 订单 #{order.id}: {order.amount}")

# 多对一访问：订单 -> 用户
order_obj = Order.get(order1.id)
print(f"\n   多对一访问 (Order -> User):")
print(f"   - 订单 #{order_obj.id} 属于: {order_obj.user.name}")

db1.close()

# ============================================================================
# 2. 一对一关联
# ============================================================================

print("\n" + "=" * 70)
print("2. 一对一关联")
print("=" * 70)

db2 = Storage(in_memory=True)
Base2: Type[CRUDBaseModel] = declarative_base(db2, crud=True)


class UserProfile(Base2):
    """用户资料模型"""
    __tablename__ = 'user_profiles'

    id = Column('id', int, primary_key=True)
    user_id = Column('user_id', int)
    bio = Column('bio', str)
    avatar_url = Column('avatar_url', str, nullable=True)

    # 多对一：资料 -> 用户
    user = Relationship('users', foreign_key='user_id')


class User2(Base2):
    """用户模型"""
    __tablename__ = 'users'

    id = Column('id', int, primary_key=True)
    name = Column('name', str)
    email = Column('email', str)

    # 一对一：用户 -> 资料（实际是一对多，取第一个即可）
    profile = Relationship('user_profiles', foreign_key='user_id')


# 创建测试数据
user = User2.create(name='Charlie', email='charlie@example.com')
profile = UserProfile.create(
    user_id=user.id,
    bio='Hello, I am Charlie!',
    avatar_url='https://example.com/avatar.png'
)

print("\n   创建的数据：")
print(f"   - 用户: {user.name} (id={user.id})")
print(f"   - 资料: bio='{profile.bio}'")

# 用户 -> 资料
user_obj = User2.get(user.id)
user_profile = user_obj.profile[0] if user_obj.profile else None
print(f"\n   一对一访问 (User -> Profile):")
print(f"   - {user_obj.name} 的简介: {user_profile.bio if user_profile else 'N/A'}")

# 资料 -> 用户
profile_obj = UserProfile.get(profile.id)
print(f"\n   一对一反向访问 (Profile -> User):")
print(f"   - 资料所属用户: {profile_obj.user.name}")

db2.close()

# ============================================================================
# 3. 多对多关联（通过中间表）
# ============================================================================

print("\n" + "=" * 70)
print("3. 多对多关联（通过中间表）")
print("=" * 70)

db3 = Storage(in_memory=True)
Base3: Type[CRUDBaseModel] = declarative_base(db3, crud=True)


class Enrollment(Base3):
    """选课记录（中间表）"""
    __tablename__ = 'enrollments'

    id = Column('id', int, primary_key=True)
    student_id = Column('student_id', int)
    course_id = Column('course_id', int)
    grade = Column('grade', str, nullable=True)

    # 关联到两端
    student = Relationship('students', foreign_key='student_id')
    course = Relationship('courses', foreign_key='course_id')


class Student(Base3):
    """学生模型"""
    __tablename__ = 'students'

    id = Column('id', int, primary_key=True)
    name = Column('name', str)

    # 学生 -> 选课记录
    enrollments = Relationship('enrollments', foreign_key='student_id')


class Course(Base3):
    """课程模型"""
    __tablename__ = 'courses'

    id = Column('id', int, primary_key=True)
    title = Column('title', str)
    credits = Column('credits', int)

    # 课程 -> 选课记录
    enrollments = Relationship('enrollments', foreign_key='course_id')


# 创建测试数据
student1 = Student.create(name='David')
student2 = Student.create(name='Eva')

course1 = Course.create(title='Mathematics', credits=4)
course2 = Course.create(title='Physics', credits=3)
course3 = Course.create(title='Chemistry', credits=3)

# 选课
Enrollment.create(student_id=student1.id, course_id=course1.id, grade='A')
Enrollment.create(student_id=student1.id, course_id=course2.id, grade='B+')
Enrollment.create(student_id=student2.id, course_id=course1.id, grade='A-')
Enrollment.create(student_id=student2.id, course_id=course3.id, grade='A')

print("\n   创建的数据：")
print(f"   - 学生: David, Eva")
print(f"   - 课程: Mathematics, Physics, Chemistry")
print(f"   - 选课: David(Math, Physics), Eva(Math, Chemistry)")

# 学生 -> 课程
david = Student.get(student1.id)
print(f"\n   多对多访问 (Student -> Courses):")
print(f"   - {david.name} 选修的课程:")
for enrollment in david.enrollments:
    print(f"     - {enrollment.course.title} (成绩: {enrollment.grade})")

# 课程 -> 学生
math = Course.get(course1.id)
print(f"\n   多对多反向访问 (Course -> Students):")
print(f"   - 选修 {math.title} 的学生:")
for enrollment in math.enrollments:
    print(f"     - {enrollment.student.name} (成绩: {enrollment.grade})")

db3.close()

# ============================================================================
# 4. 自引用关联（树形结构）
# ============================================================================

print("\n" + "=" * 70)
print("4. 自引用关联（树形结构）")
print("=" * 70)

db4 = Storage(in_memory=True)
Base4: Type[CRUDBaseModel] = declarative_base(db4, crud=True)


class Category(Base4):
    """分类模型（树形结构）"""
    __tablename__ = 'categories'

    id = Column('id', int, primary_key=True)
    name = Column('name', str)
    parent_id = Column('parent_id', int, nullable=True)

    # 自引用关系 - 需要用 uselist 明确指定方向
    parent = Relationship('categories', foreign_key='parent_id', uselist=False)
    children = Relationship('categories', foreign_key='parent_id', uselist=True)


# 创建分类树
#   Electronics
#   ├── Phones
#   │   ├── iPhone
#   │   └── Android
#   └── Laptops
#       ├── MacBook
#       └── ThinkPad

electronics = Category.create(name='Electronics', parent_id=None)
phones = Category.create(name='Phones', parent_id=electronics.id)
laptops = Category.create(name='Laptops', parent_id=electronics.id)

iphone = Category.create(name='iPhone', parent_id=phones.id)
android = Category.create(name='Android', parent_id=phones.id)

macbook = Category.create(name='MacBook', parent_id=laptops.id)
thinkpad = Category.create(name='ThinkPad', parent_id=laptops.id)

print("\n   创建的分类树：")
print("   Electronics")
print("   ├── Phones")
print("   │   ├── iPhone")
print("   │   └── Android")
print("   └── Laptops")
print("       ├── MacBook")
print("       └── ThinkPad")

# 获取子节点
electronics_obj = Category.get(electronics.id)
print(f"\n   获取子节点 (parent -> children):")
print(f"   - {electronics_obj.name} 的子分类:")
for child in electronics_obj.children:
    print(f"     - {child.name}")
    for grandchild in child.children:
        print(f"       - {grandchild.name}")

# 获取父节点
iphone_obj = Category.get(iphone.id)
print(f"\n   获取父节点 (child -> parent):")
print(f"   - {iphone_obj.name} 的父分类: {iphone_obj.parent.name}")
print(f"   - {iphone_obj.parent.name} 的父分类: {iphone_obj.parent.parent.name}")

# 根节点无父节点
print(f"\n   根节点检查:")
print(f"   - {electronics_obj.name} 的父分类: {electronics_obj.parent}")

db4.close()

# ============================================================================
# 5. 混合使用：类引用 + 字符串引用
# ============================================================================

print("\n" + "=" * 70)
print("5. 混合使用：类引用 + 字符串引用")
print("=" * 70)

db5 = Storage(in_memory=True)
Base5: Type[CRUDBaseModel] = declarative_base(db5, crud=True)


# 先定义的类可以被后面的类直接引用
class Tag(Base5):
    """标签模型"""
    __tablename__ = 'tags'

    id = Column('id', int, primary_key=True)
    name = Column('name', str)
    post_id = Column('post_id', int)

    # 使用字符串引用（此时 Post 尚未定义）
    post = Relationship('posts', foreign_key='post_id')


class Post(Base5):
    """文章模型"""
    __tablename__ = 'posts'

    id = Column('id', int, primary_key=True)
    title = Column('title', str)

    # 使用类引用（Tag 已定义）
    tags = Relationship(Tag, foreign_key='post_id')


# 创建测试数据
post = Post.create(title='Introduction to Pytuck')
Tag.create(name='Python', post_id=post.id)
Tag.create(name='Database', post_id=post.id)
Tag.create(name='ORM', post_id=post.id)

print("\n   创建的数据：")
print(f"   - 文章: {post.title}")
print(f"   - 标签: Python, Database, ORM")

# 文章 -> 标签
post_obj = Post.get(post.id)
print(f"\n   文章 -> 标签:")
print(f"   - {post_obj.title} 的标签:")
for tag in post_obj.tags:
    print(f"     - {tag.name}")

# 标签 -> 文章
tag_obj = Tag.filter_by(name='Python').first()
print(f"\n   标签 -> 文章:")
print(f"   - {tag_obj.name} 标签所属文章: {tag_obj.post.title}")

db5.close()

# ============================================================================
# 总结
# ============================================================================

print("\n" + "=" * 70)
print("总结")
print("=" * 70)

print("""
Relationship 使用要点：

1. 字符串引用（推荐）
   - 使用表名而非类名：Relationship('users', foreign_key='user_id')
   - 无需考虑类定义顺序，支持前向引用

2. 类引用
   - 直接使用类对象：Relationship(Order, foreign_key='user_id')
   - 需要目标类已定义

3. uselist 参数
   - uselist=True  : 返回列表（一对多）
   - uselist=False : 返回单个对象（多对一）
   - None（默认）  : 自动判断（根据外键位置）
   - 自引用场景必须显式指定

4. back_populates 参数
   - 用于双向关联的反向属性名
   - 便于代码可读性，非必需

5. 关系类型
   - 一对多：父表使用 uselist=True 或自动判断
   - 多对一：子表使用 uselist=False 或自动判断
   - 一对一：一对多 + 业务约束
   - 多对多：通过中间表实现
   - 自引用：使用 uselist 明确指定方向
""")

print("=" * 70)
print("示例完成！")
print("=" * 70)
