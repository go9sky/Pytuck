# Pytuck - 轻量级 Python 文档数据库

[![Gitee](https://img.shields.io/badge/Gitee-Pytuck%2FPytuck-red)](https://gitee.com/Pytuck/Pytuck)
[![GitHub](https://img.shields.io/badge/GitHub-Pytuck%2FPytuck-blue)](https://github.com/Pytuck/Pytuck)

[![PyPI version](https://badge.fury.io/py/pytuck.svg)](https://badge.fury.io/py/pytuck)
[![Python Versions](https://img.shields.io/pypi/pyversions/pytuck.svg)](https://pypi.org/project/pytuck/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

中文 | [English](README.EN.md)

纯Python实现的轻量级文档数据库，支持多种存储引擎，无SQL，通过对象和方法管理数据。

> **设计初衷**：为 Ren'Py 等阉割版 Python 环境提供零依赖的关系型数据库方案，让任何受限环境都能享受 SQLAlchemy 风格的 Pythonic 数据操作体验。

## 仓库镜像

- **GitHub**: https://github.com/Pytuck/Pytuck
- **Gitee**: https://gitee.com/Pytuck/Pytuck

## 核心特性

- **无SQL设计** - 完全通过Python对象和方法操作数据，无需编写SQL
- **多引擎支持** - 支持二进制、JSON、CSV、SQLite、Excel、XML等多种存储格式
- **插件化架构** - 默认零依赖，可选引擎按需安装
- **SQLAlchemy 2.0 风格 API** - 现代化的查询构建器（`select()`, `insert()`, `update()`, `delete()`）
- **泛型类型提示** - 完整的泛型支持，IDE智能提示精确到具体模型类型（`List[User]` 而非 `List[PureBaseModel]`）
- **Pythonic 查询语法** - 使用原生 Python 运算符构建查询（`User.age >= 18`）
- **索引优化** - 哈希索引和有序索引加速查询，范围查询和排序自动利用索引
- **类型安全** - 自动类型验证和转换（宽松/严格模式），支持 10 种字段类型
- **关联关系** - 支持一对多和多对一关联，延迟加载+自动缓存
- **独立数据模型** - Session 关闭后仍可访问，像 Pydantic 一样使用
- **持久化** - 数据自动或手动持久化到磁盘

## 快速开始

### 安装

```bash
# 基础安装（仅二进制引擎，无外部依赖）
pip install pytuck

# 安装特定引擎
pip install pytuck[json]    # JSON引擎
pip install pytuck[excel]   # Excel引擎（需要 openpyxl）
pip install pytuck[xml]     # XML引擎（需要 lxml）

# 安装所有引擎
pip install pytuck[all]

# 开发环境
pip install pytuck[dev]
```

### 基础使用

Pytuck 提供两种使用模式：

#### 模式 1：纯模型模式（默认，推荐）

通过 Session 操作数据，符合 SQLAlchemy 2.0 风格：

```python
from typing import Type
from pytuck import Storage, declarative_base, Session, Column
from pytuck import PureBaseModel, select, insert, update, delete

# 创建数据库（默认二进制引擎）
db = Storage(file_path='mydb.db')
Base: Type[PureBaseModel] = declarative_base(db)

# 定义模型
class Student(Base):
    __tablename__ = 'students'

    id = Column(int, primary_key=True)
    name = Column(str, nullable=False, index=True)
    age = Column(int)
    email = Column(str, nullable=True)

# 创建 Session
session = Session(db)

# 插入记录
stmt = insert(Student).values(name='Alice', age=20, email='alice@example.com')
result = session.execute(stmt)
session.commit()
print(f"Created student, ID: {result.inserted_primary_key}")

# 查询记录
stmt = select(Student).where(Student.id == 1)
result = session.execute(stmt)
alice = result.first()
print(f"Found: {alice.name}, {alice.age} years old")

# 条件查询（Pythonic 语法）
stmt = select(Student).where(Student.age >= 18).order_by('name')
result = session.execute(stmt)
adults = result.all()
for student in adults:
    print(f"  - {student.name}")

# Identity Map 示例（0.3.0 新增，对象唯一性保证）
student1 = session.get(Student, 1)  # 从数据库加载
stmt = select(Student).where(Student.id == 1)
student2 = session.execute(stmt).scalars().first()  # 通过查询获得
print(f"是同一个对象？{student1 is student2}")  # True，同一个实例

# merge() 操作示例（0.3.0 新增，合并外部数据）
external_student = Student(id=1, name="Alice Updated", age=22)  # 来自外部的数据
merged = session.merge(external_student)  # 智能合并到 Session
session.commit()  # 更新生效

# 更新记录
# 方式1：使用 update 语句（批量更新）
stmt = update(Student).where(Student.id == 1).values(age=21)
session.execute(stmt)
session.commit()

# 方式2：属性赋值更新（0.3.0 新增，更直观）
stmt = select(Student).where(Student.id == 1)
result = session.execute(stmt)
alice = result.first()
alice.age = 21  # 属性赋值自动检测并更新数据库
session.commit()  # 自动将修改写入数据库

# 删除记录
stmt = delete(Student).where(Student.id == 1)
session.execute(stmt)
session.commit()

# 关闭
session.close()
db.close()
```

#### 模式 2：Active Record 模式

模型自带 CRUD 方法，更简洁的操作方式：

```python
from typing import Type
from pytuck import Storage, declarative_base, Column
from pytuck import CRUDBaseModel

# 创建数据库
db = Storage(file_path='mydb.db')
Base: Type[CRUDBaseModel] = declarative_base(db, crud=True)  # 注意 crud=True

# 定义模型
class Student(Base):
    __tablename__ = 'students'

    id = Column(int, primary_key=True)
    name = Column(str, nullable=False)
    age = Column(int)

# 创建记录（自动保存）
alice = Student.create(name='Alice', age=20)
print(f"Created: {alice.name}, ID: {alice.id}")

# 或者手动保存
bob = Student(name='Bob', age=22)
bob.save()

# 查询记录
student = Student.get(1)  # 按主键查询
students = Student.filter(Student.age >= 18).all()  # 条件查询
students = Student.filter_by(name='Alice').all()  # 等值查询
all_students = Student.all()  # 获取全部

# 更新记录
alice.age = 21  # Active Record 模式本来就支持属性赋值更新
alice.save()    # 显式保存到数据库

# 删除记录
alice.delete()

# 关闭
db.close()
```

**如何选择？**
- **纯模型模式**：适合大型项目、团队开发、需要清晰的数据访问层分离
- **Active Record 模式**：适合小型项目、快速原型、简单的 CRUD 操作

## 存储引擎

Pytuck 支持多种存储引擎，每种引擎适用于不同场景：

### 二进制引擎（默认）

**特点**: 无外部依赖、紧凑、高性能、支持加密

```python
from pytuck.common.options import BinaryBackendOptions

# 基础使用
db = Storage(file_path='data.db', engine='binary')

# 启用加密（三级可选：low/medium/high）
opts = BinaryBackendOptions(encryption='high', password='mypassword')
db = Storage(file_path='secure.db', engine='binary', backend_options=opts)

# 打开加密数据库（自动检测加密等级）
opts = BinaryBackendOptions(password='mypassword')
db = Storage(file_path='secure.db', engine='binary', backend_options=opts)
```

**加密等级说明**:

| 等级 | 算法 | 安全性 | 适用场景 |
|------|------|--------|----------|
| `low` | XOR 混淆 | 防随手查看 | 防止文件被意外打开 |
| `medium` | LCG 流密码 | 防普通用户 | 一般保护需求 |
| `high` | ChaCha20 | 密码学安全 | 敏感数据保护 |

**加密性能测试结果**（1000 条记录，每条约 100 字节）：

| 等级 | 写入时间 | 读取时间 | 文件大小 | 读取性能税 |
|------|----------|----------|----------|------------|
| 无加密 | 41ms | 17ms | 183KB | (基准) |
| low | 33ms | 33ms | 183KB | +100% |
| medium | 82ms | 86ms | 183KB | +418% |
| high | 342ms | 335ms | 183KB | +1928% |

> **注意**: 加密功能使用纯 Python 实现以保持零依赖。如需更高性能，建议选择 `low` 或 `medium` 等级。
> 运行 `examples/benchmark_encryption.py` 可在您的环境中进行性能测试。

**适用场景**:
- 生产环境部署
- 嵌入式应用
- 敏感数据保护

### JSON 引擎

**特点**: 人类可读、便于调试、标准格式

```python
from pytuck.common.options import JsonBackendOptions

# 配置 JSON 选项
json_opts = JsonBackendOptions(indent=2, ensure_ascii=False)
db = Storage(file_path='data.json', engine='json', backend_options=json_opts)
```

**适用场景**:
- 开发调试
- 配置存储
- 数据交换

### CSV 引擎

**特点**: Excel兼容、表格格式、数据分析友好、支持密码保护

```python
from pytuck.common.options import CsvBackendOptions

# 配置 CSV 选项
csv_opts = CsvBackendOptions(encoding='utf-8', delimiter=',')
db = Storage(file_path='data.zip', engine='csv', backend_options=csv_opts)

# 启用 ZIP 密码保护（ZipCrypto 加密，兼容 WinRAR/7-Zip）
csv_opts = CsvBackendOptions(password="my_password")
db = Storage(file_path='secure.zip', engine='csv', backend_options=csv_opts)
```

**适用场景**:
- 数据分析
- Excel导入导出
- 表格数据
- 需要最小体积
- 需要与其他工具共享加密文件

### SQLite 引擎

**特点**: 成熟稳定、ACID特性、支持SQL

```python
from pytuck.common.options import SqliteBackendOptions

# 配置 SQLite 选项（可选）
sqlite_opts = SqliteBackendOptions()  # 使用默认配置
db = Storage(file_path='data.sqlite', engine='sqlite', backend_options=sqlite_opts)
```

**适用场景**:
- 需要SQL查询
- 需要事务保证
- 大量数据

### Excel 引擎（可选）

**依赖**: `openpyxl>=3.0.0`

```python
from pytuck.common.options import ExcelBackendOptions

# 配置 Excel 选项（可选）
excel_opts = ExcelBackendOptions(read_only=False)  # 使用默认配置
db = Storage(file_path='data.xlsx', engine='excel', backend_options=excel_opts)
```

**适用场景**:
- 业务报表
- 可视化需求
- 办公自动化

### XML 引擎（可选）

**依赖**: `lxml>=4.9.0`

```python
from pytuck.common.options import XmlBackendOptions

# 配置 XML 选项
xml_opts = XmlBackendOptions(encoding='utf-8', pretty_print=True)
db = Storage(file_path='data.xml', engine='xml', backend_options=xml_opts)
```

**适用场景**:
- 企业集成
- 标准化交换
- 配置文件

## 高级特性

### 泛型类型提示

Pytuck 提供完整的泛型类型支持，让 IDE 能够精确推断查询结果的具体类型，显著提升开发体验：

#### IDE 类型推断效果

```python
from typing import List, Optional
from pytuck import Storage, declarative_base, Session, Column
from pytuck import select, insert, update, delete

db = Storage('mydb.db')
Base = declarative_base(db)

class User(Base):
    __tablename__ = 'users'
    id = Column(int, primary_key=True)
    name = Column(str)
    age = Column(int)

session = Session(db)

# 语句构建器类型推断
stmt = select(User)  # IDE 推断：Select[User] ✅
chained = stmt.where(User.age >= 18)  # IDE 推断：Select[User] ✅

# 会话执行类型推断
result = session.execute(stmt)  # IDE 推断：Result[User] ✅

# 结果处理精确类型
users = result.all()  # 返回 模型实例列表 List[T]
user = result.first()  # 返回 第一个模型实例 Optional[T]

说明：
- Result.all() → 返回模型实例列表 List[T]
- Result.first() → 返回第一个模型实例 Optional[T]
- Result.one() → 返回唯一模型实例 T（必须恰好一条）
- Result.one_or_none() → 返回唯一模型实例或 None Optional[T]（最多一条）
- Result.rowcount() → 返回结果数量 int

# IDE 知道具体属性类型
for user in users:
    user_name: str = user.name  # ✅ IDE 知道这是 str 类型
    user_age: int = user.age    # ✅ IDE 知道这是 int 类型
    # user.invalid_field        # ❌ IDE 警告属性不存在
```

#### 类型安全特性

- **精确的类型推断**：`select(User)` 返回 `Select[User]`，不再是泛泛的 `Select`
- **智能代码补全**：IDE 准确提示模型属性和方法
- **编译时错误检测**：MyPy 可以在编译时发现类型错误
- **方法链类型保持**：所有链式调用都保持具体的泛型类型
- **100% 向后兼容**：现有代码无需修改，自动获得类型提示增强

#### 对比效果

**之前：**
```python
users = result.all()  # IDE: List[PureBaseModel] 😞
user.name                       # IDE: 不知道有什么属性 😞
```

**现在：**
```python
users = result.all()  # IDE: List[User] ✅
user.name                       # IDE: 知道是 str 类型 ✅
user.age                        # IDE: 知道是 int 类型 ✅
```

### 数据持久化

Pytuck 提供灵活的数据持久化机制。

#### 纯模型模式（Session）

```python
db = Storage(file_path='data.db')  # auto_flush=False（默认）

# 数据修改只在内存中
session.execute(insert(User).values(name='Alice'))
session.commit()  # 提交到 Storage 内存

# 手动写入磁盘
db.flush()  # 方式1：显式刷新
# 或
db.close()  # 方式2：关闭时自动刷新
```

启用自动持久化：

```python
db = Storage(file_path='data.db', auto_flush=True)

# 每次 commit 后自动写入磁盘
session.execute(insert(User).values(name='Alice'))
session.commit()  # 自动写入磁盘，无需手动 flush
```

#### Active Record 模式（CRUDBaseModel）

CRUDBaseModel 没有 Session，直接操作 Storage：

```python
db = Storage(file_path='data.db')  # auto_flush=False（默认）
Base = declarative_base(db, crud=True)

class User(Base):
    __tablename__ = 'users'
    id = Column(int, primary_key=True)
    name = Column(str)

# create/save/delete 只修改内存
user = User.create(name='Alice')
user.name = 'Bob'
user.save()

# 手动写入磁盘
db.flush()  # 方式1：显式刷新
# 或
db.close()  # 方式2：关闭时自动刷新
```

启用自动持久化：

```python
db = Storage(file_path='data.db', auto_flush=True)
Base = declarative_base(db, crud=True)

# 每次 create/save/delete 后自动写入磁盘
user = User.create(name='Alice')  # 自动写入磁盘
user.name = 'Bob'
user.save()  # 自动写入磁盘
```

#### 持久化方法总结

| 方法 | 模式 | 说明 |
|------|------|------|
| `session.commit()` | 纯模型 | 提交事务到 Storage 内存；若 `auto_flush=True` 则同时写入磁盘 |
| `Model.create/save/delete()` | Active Record | 修改 Storage 内存；若 `auto_flush=True` 则同时写入磁盘 |
| `storage.flush()` | 通用 | 强制将内存数据写入磁盘 |
| `storage.close()` | 通用 | 关闭数据库，自动调用 `flush()` |

**建议**：
- 生产环境使用 `auto_flush=True` 确保数据安全
- 批量操作时使用默认模式，最后调用 `flush()` 提高性能

### 事务支持

Pytuck 支持内存级事务，异常时自动回滚：

```python
# Session 事务（推荐）
with session.begin():
    session.add(User(name='Alice'))
    session.add(User(name='Bob'))
    # 成功则自动提交，异常则自动回滚

# Storage 级事务
with db.transaction():
    db.insert('users', {'name': 'Alice'})
    db.insert('users', {'name': 'Bob'})
    # 异常时自动回滚到事务开始前的状态
```

### Session 上下文管理器

Session 支持上下文管理器，自动处理提交和回滚：

```python
with Session(db) as session:
    stmt = insert(User).values(name='Alice')
    session.execute(stmt)
    # 退出时自动 commit，异常时自动 rollback
```

### 自动提交模式

```python
session = Session(db, autocommit=True)
# 每次操作后自动提交
session.add(User(name='Alice'))  # 自动提交
```

### 对象状态追踪

Session 提供完整的对象状态追踪：

```python
# 添加单个对象
session.add(user)

# 批量添加
session.add_all([user1, user2, user3])

# 刷新到数据库（不提交事务）
session.flush()

# 提交事务
session.commit()

# 回滚事务
session.rollback()
```

### 自动刷新

启用 `auto_flush` 后，每次写操作自动持久化到磁盘：

```python
db = Storage(file_path='data.db', auto_flush=True)

# 插入自动写入磁盘
stmt = insert(Student).values(name='Bob', age=21)
session.execute(stmt)
session.commit()
```

### 索引查询

为字段添加索引以加速查询：

```python
class Student(Base):
    __tablename__ = 'students'
    name = Column(str, index=True)           # 哈希索引（等值查询加速）
    age = Column(int, index='sorted')         # 有序索引（范围查询+排序加速）

# 等值查询（使用哈希索引）
stmt = select(Student).filter_by(name='Bob')
result = session.execute(stmt)
bob = result.first()

# 范围查询（自动使用有序索引）
stmt = select(Student).where(Student.age >= 18, Student.age < 30)
result = session.execute(stmt)
adults = result.all()

# 排序查询（自动使用有序索引，无需全量排序）
stmt = select(Student).order_by('age').limit(10)
result = session.execute(stmt)
youngest = result.all()
```

### 查询操作符

支持 Pythonic 查询操作符：

```python
# 等于
stmt = select(Student).where(Student.age == 20)

# 不等于
stmt = select(Student).where(Student.age != 20)

# 大于/大于等于
stmt = select(Student).where(Student.age > 18)
stmt = select(Student).where(Student.age >= 18)

# 小于/小于等于
stmt = select(Student).where(Student.age < 30)
stmt = select(Student).where(Student.age <= 30)

# IN 查询
stmt = select(Student).where(Student.age.in_([18, 19, 20]))

# 多条件（AND）
stmt = select(Student).where(Student.age >= 18, Student.age < 30)

# 简单等值查询（filter_by）
stmt = select(Student).filter_by(name='Alice', age=20)
```

### 排序和分页

```python
# 排序
stmt = select(Student).order_by('age')
stmt = select(Student).order_by('age', desc=True)

# 分页
stmt = select(Student).limit(10)
stmt = select(Student).offset(10).limit(10)

# 计数
stmt = select(Student).where(Student.age >= 18)
result = session.execute(stmt)
adults = result.all()
count = len(adults)
```

## 数据模型特性

Pytuck 的数据模型具有独特的特性，使其既像 ORM 又像纯数据容器。

### 独立的数据对象

Pytuck 的模型实例是完全独立的 Python 对象，查询后立即物化到内存：

- ✅ **Session 关闭后仍可访问**：无 DetachedInstanceError
- ✅ **Storage 关闭后仍可操作**：已加载的对象完全独立
- ✅ **无延迟加载**：所有直接属性立即加载
- ✅ **可序列化**：支持 JSON、Pickle 等序列化
- ✅ **可作为数据容器**：像 Pydantic 模型一样使用

```python
from pytuck import Storage, declarative_base, Session, Column, select

db = Storage(file_path='data.db')
Base = declarative_base(db)

class User(Base):
    __tablename__ = 'users'
    id = Column(int, primary_key=True)
    name = Column(str)

session = Session(db)
stmt = select(User).where(User.id == 1)
user = session.execute(stmt).scalars().first()

# 关闭 session 和 storage
session.close()
db.close()

# 仍然可以访问！
print(user.name)  # ✅ 正常工作
print(user.to_dict())  # ✅ 正常工作
```

**对比 SQLAlchemy**：

| 特性 | Pytuck | SQLAlchemy |
|------|--------|------------|
| Session 关闭后访问属性 | ✅ 支持 | ❌ DetachedInstanceError |
| 关联对象延迟加载 | ✅ 支持（带缓存） | ✅ 支持 |
| 模型作为纯数据容器 | ✅ 是 | ❌ 否（绑定 session） |

### 关联关系（Relationship）

Pytuck 支持一对多、多对一、自引用等关联关系：

```python
from pytuck.core.orm import Relationship
from typing import List, Optional

class User(Base):
    __tablename__ = 'users'
    id = Column(int, primary_key=True)
    name = Column(str)
    # 一对多：使用表名引用（推荐）
    orders: List['Order'] = Relationship('orders', foreign_key='user_id')  # type: ignore

class Order(Base):
    __tablename__ = 'orders'
    id = Column(int, primary_key=True)
    user_id = Column(int)
    amount = Column(float)
    # 多对一
    user: Optional[User] = Relationship('users', foreign_key='user_id')  # type: ignore

# 自引用（树形结构）- 使用 uselist 指定方向
class Category(Base):
    __tablename__ = 'categories'
    id = Column(int, primary_key=True)
    parent_id = Column(int, nullable=True)
    parent: Optional['Category'] = Relationship('categories', foreign_key='parent_id', uselist=False)  # type: ignore
    children: List['Category'] = Relationship('categories', foreign_key='parent_id', uselist=True)  # type: ignore
```

**特性**：
- ✅ **表名引用**：使用表名字符串，支持前向引用
- ✅ **延迟加载**：首次访问时查询，自动缓存
- ✅ **uselist 参数**：自引用场景显式指定返回类型
- ✅ **类型提示**：直接声明返回类型获得 IDE 补全

> 完整示例见 `examples/relationship_demo.py`

### 类型验证与转换

Pytuck 提供零依赖的自动类型验证和转换：

```python
class User(Base):
    __tablename__ = 'users'
    id = Column(int, primary_key=True)
    age = Column(int)  # 声明为 int

# 宽松模式（默认）：自动转换
user = User(age='25')  # ✅ 自动转换 '25' → 25

# 严格模式：不转换，类型错误抛出异常
class StrictUser(Base):
    __tablename__ = 'strict_users'
    id = Column(int, primary_key=True)
    age = Column(int, strict=True)  # 严格模式

user = StrictUser(age='25')  # ❌ ValidationError
```

**类型转换规则（宽松模式）**：

| Python 类型 | 转换规则 | 示例 |
|------------|---------|------|
| int | int(value) | '123' → 123 |
| float | float(value) | '3.14' → 3.14 |
| str | str(value) | 123 → '123' |
| bool | 特殊规则* | '1', 'true', 1 → True |
| bytes | encode() 如果是 str | 'hello' → b'hello' |
| datetime | ISO 8601 解析 | '2024-01-15T10:30:00' → datetime |
| date | ISO 8601 解析 | '2024-01-15' → date |
| timedelta | 总秒数 | 3600.0 → timedelta(hours=1) |
| list | JSON 解析 | '[1,2,3]' → [1, 2, 3] |
| dict | JSON 解析 | '{"a":1}' → {'a': 1} |
| None | nullable=True 允许 | None → None |

*bool 转换规则：
- True: `True`, `1`, `'1'`, `'true'`, `'True'`, `'yes'`, `'Yes'`
- False: `False`, `0`, `'0'`, `'false'`, `'False'`, `'no'`, `'No'`, `''`

**使用场景**：

```python
# Web API 开发：查询后直接返回，无需担心连接
@app.get("/users/{id}")
def get_user(id: int):
    session = Session(db)
    stmt = select(User).where(User.id == id)
    user = session.execute(stmt).scalars().first()
    session.close()

    # 返回模型，无需担心 session 已关闭
    return user.to_dict()

# 数据传递：模型对象可以在函数间自由传递
def process_users(users: List[User]) -> List[dict]:
    return [u.to_dict() for u in users]

# JSON 序列化
import json
user_json = json.dumps(user.to_dict())
```

## 性能基准测试

以下是 v4 版本的基准测试结果。

### 测试环境

- **系统**: Windows 11, Python 3.12.10
- **测试数据量**: 100,000 条记录
- **模式**: 扩展测试（包含索引对比、范围查询、批量读取、懒加载查询）

### 性能对比表

| 引擎 | 插入 | 索引查询 | 非索引查询 | 索引加速 | 范围查询 | 保存 | 加载 | 懒加载 | 文件大小 |
|------|------|----------|------------|----------|----------|------|------|--------|----------|
| Binary | 794.57ms | 1.39ms | 7.13s | 5124x | 333.29ms | 869.68ms | 1.01s | 319.88ms | 11.73MB |
| JSON | 844.76ms | 1.42ms | 8.95s | 6279x | 337.01ms | 845.77ms | 319.37ms | - | 18.90MB |
| CSV | 838.89ms | 1.47ms | 7.24s | 4939x | 346.85ms | 453.50ms | 472.90ms | - | 731.9KB |
| SQLite | 879.05ms | 1.40ms | 7.21s | 5145x | 333.84ms | 325.80ms | 393.39ms | - | 6.97MB |
| Excel | 897.48ms | 1.41ms | 7.25s | 5150x | 340.40ms | 5.75s | 7.63s | - | 2.84MB |
| XML | 1.23s | 1.41ms | 7.41s | 5248x | 333.87ms | 2.49s | 2.03s | - | 34.54MB |

**说明**:
- **索引查询**: 100 次索引字段等值查询（毫秒级）
- **非索引查询**: 100 次非索引字段全表扫描（秒级）
- **索引加速**: 索引查询 vs 非索引查询的加速比
- **范围查询**: 范围条件查询（如 `age >= 20 AND age < 62`）
- **懒加载**: 仅 Binary 引擎支持，只加载索引不加载数据

### 引擎特性对比

| 引擎 | 查询性能 | I/O性能 | 存储效率 | 人类可读 | 外部依赖 | 推荐场景 |
|------|---------|---------|---------|---------|---------|----------|
| Binary | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ❌ | 无 | **生产环境首选** |
| JSON | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ✅ | 无 | 开发调试、配置存储 |
| CSV | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ✅ | 无 | 数据交换、最小体积 |
| SQLite | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ❌ | 无 | 需要 SQL、ACID 保证 |
| Excel | ⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐ | ✅ | openpyxl | 可视化编辑、报表 |
| XML | ⭐⭐⭐⭐ | ⭐⭐ | ⭐ | ✅ | lxml | 企业集成、标准化 |

**结论**:
- **Binary** 插入最快（794ms），支持懒加载和加密，**生产环境首选**
- **JSON** 加载最快（319ms），便于调试，适合开发和配置存储
- **CSV** 文件最小（732KB，ZIP压缩），I/O性能优秀，适合数据交换
- **SQLite** I/O性能最佳（保存325ms），综合性能均衡，适合需要 ACID 的场景
- **Excel** I/O 较慢（加载7.63s），适合需要可视化编辑的场景
- **XML** 文件最大（34.54MB），适合企业集成和标准化交换

## 数据迁移

在不同引擎之间迁移数据：

```python
from pytuck.tools.migrate import migrate_engine
from pytuck.common.options import JsonBackendOptions

# 配置目标引擎选项
json_opts = JsonBackendOptions(indent=2, ensure_ascii=False)

# 从二进制迁移到JSON
migrate_engine(
    source_path='data.db',
    source_engine='binary',
    target_path='data.json',
    target_engine='json',
    target_options=json_opts  # 使用强类型选项
)
```

## 架构设计

```
┌─────────────────────────────────────┐
│         应用层 (Application)         │
│    BaseModel, Column, Query API      │
└─────────────────────────────────────┘
               ↓
┌─────────────────────────────────────┐
│          ORM层 (orm.py)             │
│   模型定义、验证、关系映射           │
└─────────────────────────────────────┘
               ↓
┌─────────────────────────────────────┐
│      存储引擎层 (storage.py)         │
│   Table管理、CRUD操作、查询执行      │
└─────────────────────────────────────┘
               ↓
┌─────────────────────────────────────┐
│     后端插件层 (backends/)           │
│  BinaryBackend | JSONBackend | ...  │
└─────────────────────────────────────┘
               ↓
┌─────────────────────────────────────┐
│         公共层 (common/)             │
│   Options, Utils, Exceptions        │
└─────────────────────────────────────┘
```

## 项目状态

- ✅ Phase 1: 核心ORM和内存存储
- ✅ Phase 2: 插件化多引擎持久化
- ✅ Phase 3: SQLAlchemy 2.0 风格 API
- ✅ Phase 4: 基础事务支持

## 当前限制

Pytuck 是一个轻量级嵌入式数据库，设计目标是简单易用。以下是当前版本的限制：

### 功能限制

| 限制 | 说明 |
|------|------|
| **无 JOIN 支持** | 仅支持单表查询，不支持多表关联查询 |
| **无聚合函数** | 不支持 COUNT, SUM, AVG, MIN, MAX 等 |
| **全量保存** | 非二进制/SQLite 后端每次保存完整重写文件 |
| **无嵌套事务** | 仅支持单层事务，不支持嵌套 |

### 并发限制

| 限制 | 说明 |
|------|------|
| **仅支持单进程** | 不支持多进程并发访问，仅建议单进程读写 |
| **auto_flush=True 不支持多线程写入** | 多线程并发写入时会导致文件锁冲突，应使用 `auto_flush=False` 并在最后统一 `flush()` |
| **多线程读取安全** | 支持多线程并发读取同一 Storage |

### 事务语义

Pytuck 的事务模型与传统 ACID 数据库略有不同：

| 行为 | 说明 |
|------|------|
| **execute() 立即生效** | `session.execute()` 操作立即写入 Storage 内存，同一 Session 可立即查询到 |
| **rollback() 仅清除 pending** | `session.rollback()` 只清除通过 `session.add()` 添加的 pending 对象，不会撤销已 execute 的操作 |
| **commit() 持久化** | `session.commit()` 将数据提交；若 `auto_flush=True` 则同时写入磁盘 |

```python
# 事务行为示例
session = Session(db)

# execute() 立即写入内存
session.execute(insert(User).values(id=1, name='Alice'))
# 此时可以立即查询到
user = session.execute(select(User).where(User.id == 1)).first()  # ✅ 能查到

# rollback() 只影响 pending 对象
user2 = User(id=2, name='Bob')
session.add(user2)  # 放入 pending
session.rollback()  # 清除 pending，但 id=1 的记录仍存在
```

### 引擎特定限制

| 引擎 | 限制 |
|------|------|
| **SQLite** | 不支持中文列名（Column.name 参数不支持中文字符） |
| **Excel** | I/O 性能较慢，不适合频繁读写；需要 openpyxl 依赖 |
| **XML** | 文件体积较大，I/O 性能一般；需要 lxml 依赖 |

## 路线图 / TODO

### 已完成

- [x] **扩展字段类型支持** ✨NEW✨
  - [x] 新增 `datetime`, `date`, `timedelta`, `list`, `dict` 五种类型
  - [x] 统一 TypeRegistry 编解码，所有后端使用一致的序列化接口
  - [x] JSON 后端格式优化，移除冗余的 `_type`/`_value` 包装
- [x] **Binary 引擎 v4 格式** ✨NEW✨
  - [x] WAL（预写日志）支持 O(1) 写入延迟
  - [x] 双 Header 机制实现原子切换和崩溃恢复
  - [x] 索引区 zlib 压缩（节省约 81% 空间）
  - [x] 批量 I/O 和编解码器缓存优化
  - [x] 三级加密支持（low/medium/high），纯 Python 实现
- [x] **主键查询优化**（影响所有存储引擎）✨NEW✨
  - [x] `WHERE pk = value` 查询使用 O(1) 直接访问
  - [x] 单条更新/删除性能提升约 1000 倍
- [x] 完整的 SQLAlchemy 2.0 风格对象状态管理
  - [x] Identity Map（对象唯一性管理）
  - [x] 自动脏跟踪（属性赋值自动检测并更新数据库）
  - [x] merge() 操作（合并 detached 对象）
  - [x] 查询实例自动注册到 Session
- [x] 统一数据库连接器架构（`pytuck/connectors/` 模块）
- [x] 数据迁移工具（`migrate_engine()`, `import_from_database()`）
- [x] 从外部关系型数据库导入功能
- [x] 统一引擎版本管理（`pytuck/backends/versions.py`）
- [x] 表和列备注支持（`comment` 参数）
- [x] 完整的泛型类型提示系统
- [x] 强类型配置选项系统（dataclass 替代 **kwargs）
- [x] **Schema 同步与迁移功能** ✨NEW✨
  - [x] 支持程序重启时自动同步表结构（新增列、备注等）
  - [x] `SyncOptions` 配置类控制同步行为
  - [x] `SyncResult` 记录同步变更详情
  - [x] 三层 API 设计：Table → Storage → Session
  - [x] 支持 SQLite 原生 SQL 模式 DDL 操作
  - [x] 纯表名 API 支持（无需模型类）
- [x] **Excel 后端行号映射功能** ✨NEW✨
  - [x] `row_number_mapping='as_pk'`：行号作为主键
  - [x] `row_number_mapping='field'`：行号映射到指定字段
  - [x] 支持读取外部 Excel 文件
- [x] **SQLite 原生 SQL 模式优化** ✨NEW✨
  - [x] 默认启用原生 SQL 模式（直接执行 SQL）
  - [x] 完善类型映射（10 种 Pytuck 类型）
  - [x] 多列排序支持
- [x] **异常系统重构** ✨NEW✨
  - [x] 统一的异常层次结构
  - [x] 新增 TypeConversionError、ConfigurationError、SchemaError 等
- [x] **后端自动注册机制** ✨NEW✨
  - [x] 使用 `__init_subclass__` 实现自动注册
  - [x] 自定义后端只需继承 `StorageBackend` 即可
- [x] **查询结果 API 简化** ✨NEW✨
  - [x] 移除 `Result.scalars()` 中间层
  - [x] 直接使用 `result.all()`, `result.first()` 等
- [x] **迁移工具延迟加载后端支持** ✨NEW✨
  - [x] 修复延迟加载模式下数据迁移问题
- [x] **无主键模型支持** ✨NEW✨
  - [x] 支持定义没有主键的模型，使用内部隐式 `_pytuck_rowid`
  - [x] 适用于日志表、事件表等场景
- [x] **逻辑组合查询 OR/AND/NOT** ✨NEW✨
  - [x] 新增 `or_()`, `and_()`, `not_()` 逻辑操作符
  - [x] 支持复杂的条件组合和嵌套查询
- [x] **外部文件加载功能 load_table** ✨NEW✨
  - [x] 新增 `load_table()` 函数，将 CSV/Excel 文件加载为模型对象列表
  - [x] 类型强制转换：能转就转，不能转就报错

### 计划中的功能

> 📋 详细开发计划请参阅 [TODO.md](./TODO.md)

- [x] **Web UI 数据浏览器** - 已发布为独立项目 [pytuck-view](https://github.com/pytuck/pytuck-view)（`pip install pytuck-view`）
- [x] **ORM 事件钩子** - Model 级 + Storage 级事件回调
- [x] **关系预取（prefetch）** - 批量加载关联数据，解决 N+1 问题
- [x] **查询索引优化** - 自动利用索引加速范围查询和排序
- [ ] **批量操作优化** - bulk_insert / bulk_update API

### 计划增加的引擎

- [ ] DuckDB - 嵌入式分析型数据库
- [ ] LMDB - 高性能嵌入式键值数据库

### 计划中的优化

- [ ] 非二进制后端增量保存（当前每次保存完整重写）
- [ ] Binary 加密懒加载兼容（分块加密方案）

## 安装方式

### 从 PyPI 安装

```bash
# 基础安装
pip install pytuck

# 安装特定功能
pip install pytuck[all]      # 所有可选引擎
pip install pytuck[excel]    # 仅 Excel 支持
pip install pytuck[xml]      # 仅 XML 支持
pip install pytuck[dev]      # 开发工具
```

### 从源码安装

```bash
# 克隆仓库
git clone https://github.com/Pytuck/Pytuck.git
cd pytuck

# 可编辑安装
pip install -e .

# 安装所有可选依赖
pip install -e .[all]

# 开发模式
pip install -e .[dev]
```

### 打包与发布

```bash
# 安装构建工具
pip install build twine

# 构建 wheel 和源码分发包
python -m build

# 上传到 PyPI
python -m twine upload dist/*

# 上传到 Test PyPI
python -m twine upload --repository testpypi dist/*
```

## 示例代码

查看 `examples/` 目录获取更多示例：

- `sqlalchemy20_api_demo.py` - SQLAlchemy 2.0 风格 API 完整示例（推荐）
- `all_engines_test.py` - 所有存储引擎功能测试
- `transaction_demo.py` - 事务管理示例
- `type_validation_demo.py` - 类型验证和转换示例
- `data_model_demo.py` - 数据模型独立性特性示例
- `backend_options_demo.py` - 后端配置选项演示（新）
- `migration_tools_demo.py` - 数据迁移工具演示（新）

## 贡献

欢迎提交 Issue 和 Pull Request！

## 许可证

MIT License

## 致谢

灵感来自于 SQLAlchemy 和 TinyDB。
