# Pytuck - 轻量级 Python 文档数据库

[![Gitee](https://img.shields.io/badge/Gitee-go9sky%2Fpytuck-red)](https://gitee.com/go9sky/pytuck)
[![GitHub](https://img.shields.io/badge/GitHub-go9sky%2Fpytuck-blue)](https://github.com/go9sky/pytuck)

[![PyPI version](https://badge.fury.io/py/pytuck.svg)](https://badge.fury.io/py/pytuck)
[![Python Versions](https://img.shields.io/pypi/pyversions/pytuck.svg)](https://pypi.org/project/pytuck/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

[English Documentation](README.EN.md)

纯Python实现的轻量级文档数据库，支持多种存储引擎，无SQL，通过对象和方法管理数据。

## 仓库镜像

- **GitHub**: https://github.com/go9sky/pytuck
- **Gitee**: https://gitee.com/go9sky/pytuck

## 核心特性

- **无SQL设计** - 完全通过Python对象和方法操作数据，无需编写SQL
- **多引擎支持** - 支持二进制、JSON、CSV、SQLite、Excel、XML等多种存储格式
- **插件化架构** - 默认零依赖，可选引擎按需安装
- **SQLAlchemy 2.0 风格 API** - 现代化的查询构建器（`select()`, `insert()`, `update()`, `delete()`）
- **泛型类型提示** - 完整的泛型支持，IDE智能提示精确到具体模型类型（`List[User]` 而非 `List[PureBaseModel]`）
- **Pythonic 查询语法** - 使用原生 Python 运算符构建查询（`User.age >= 18`）
- **索引优化** - 哈希索引加速查询
- **类型安全** - 自动类型验证和转换（宽松/严格模式）
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

    id = Column('id', int, primary_key=True)
    name = Column('name', str, nullable=False, index=True)
    age = Column('age', int)
    email = Column('email', str, nullable=True)

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
alice = result.scalars().first()
print(f"Found: {alice.name}, {alice.age} years old")

# 条件查询（Pythonic 语法）
stmt = select(Student).where(Student.age >= 18).order_by('name')
result = session.execute(stmt)
adults = result.scalars().all()
for student in adults:
    print(f"  - {student.name}")

# 更新记录
stmt = update(Student).where(Student.id == 1).values(age=21)
session.execute(stmt)
session.commit()

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

    id = Column('id', int, primary_key=True)
    name = Column('name', str, nullable=False)
    age = Column('age', int)

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
alice.age = 21
alice.save()

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

**特点**: 无外部依赖、紧凑、高性能

```python
db = Storage(file_path='data.db', engine='binary')
```

**适用场景**:
- 生产环境部署
- 嵌入式应用
- 需要最小体积

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

**特点**: Excel兼容、表格格式、数据分析友好

```python
from pytuck.common.options import CsvBackendOptions

# 配置 CSV 选项
csv_opts = CsvBackendOptions(encoding='utf-8', delimiter=',')
db = Storage(file_path='data_dir', engine='csv', backend_options=csv_opts)
```

**适用场景**:
- 数据分析
- Excel导入导出
- 表格数据

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
excel_opts = ExcelBackendOptions(sheet_name='Sheet1')  # 使用默认配置
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
    id = Column('id', int, primary_key=True)
    name = Column('name', str)
    age = Column('age', int)

session = Session(db)

# 语句构建器类型推断
stmt = select(User)  # IDE 推断：Select[User] ✅
chained = stmt.where(User.age >= 18)  # IDE 推断：Select[User] ✅

# 会话执行类型推断
result = session.execute(stmt)  # IDE 推断：Result[User] ✅

# 结果处理精确类型
users = result.scalars().all()  # IDE 推断：List[User] ✅ （不再是 List[PureBaseModel]）
user = result.scalars().first()  # IDE 推断：Optional[User] ✅

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
users = result.scalars().all()  # IDE: List[PureBaseModel] 😞
user.name                       # IDE: 不知道有什么属性 😞
```

**现在：**
```python
users = result.scalars().all()  # IDE: List[User] ✅
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
    id = Column('id', int, primary_key=True)
    name = Column('name', str)

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
    name = Column('name', str, index=True)  # 创建索引

# 索引查询（自动优化）
stmt = select(Student).filter_by(name='Bob')
result = session.execute(stmt)
bob = result.scalars().first()
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
adults = result.scalars().all()
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
    id = Column('id', int, primary_key=True)
    name = Column('name', str)

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

Pytuck 支持一对多和多对一关联关系，具有延迟加载和缓存机制：

```python
from pytuck.core.orm import Relationship

# 定义关联关系
class User(Base):
    __tablename__ = 'users'
    id = Column('id', int, primary_key=True)
    name = Column('name', str)
    # 一对多：一个用户有多个订单
    orders = Relationship('Order', foreign_key='user_id')

class Order(Base):
    __tablename__ = 'orders'
    id = Column('id', int, primary_key=True)
    user_id = Column('user_id', int)
    amount = Column('amount', float)
    # 多对一：一个订单属于一个用户
    user = Relationship(User, foreign_key='user_id')

# 使用关联
user = User.get(1)
orders = user.orders  # 延迟加载，首次访问时查询
for order in orders:
    print(f"Order: {order.amount}")

# 反向访问
order = Order.get(1)
user = order.user  # 多对一查询
print(f"User: {user.name}")
```

**Relationship 特性**：

- ✅ **延迟加载**：首次访问时才查询数据库
- ✅ **自动缓存**：加载后缓存结果，避免重复查询
- ✅ **双向关联**：支持 back_populates 参数
- ✅ **Storage 关闭后**：已加载的关联仍可访问（使用缓存）
- ⚠️ **需要预加载**：Storage 关闭前访问一次以触发加载

```python
# 预加载策略
user = User.get(1)
orders = user.orders  # 在 storage 关闭前访问，触发加载并缓存

db.close()

# 关闭后仍可访问（使用缓存）
for order in orders:
    print(order.amount)  # ✅ 正常工作
```

### 类型验证与转换

Pytuck 提供零依赖的自动类型验证和转换：

```python
class User(Base):
    __tablename__ = 'users'
    id = Column('id', int, primary_key=True)
    age = Column('age', int)  # 声明为 int

# 宽松模式（默认）：自动转换
user = User(age='25')  # ✅ 自动转换 '25' → 25

# 严格模式：不转换，类型错误抛出异常
class StrictUser(Base):
    __tablename__ = 'strict_users'
    id = Column('id', int, primary_key=True)
    age = Column('age', int, strict=True)  # 严格模式

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

以下是不同环境下的基准测试结果。

### 测试 1: Windows 11, Python 3.12.10

测试数据量: 1 0000 条记录

| 引擎 | 插入 | 全表查询 | 索引查询 | 条件查询 | 更新 | 保存 | 加载 | 文件大小 |
|------|------|----------|----------|----------|------|------|------|----------|
| Binary | 85.38ms | 42.26ms | 1.10ms | 21.12ms | 709.34ms | 94.75ms | 110.68ms | 1.09MB |
| JSON | 84.33ms | 58.12ms | 1.15ms | 21.77ms | 702.70ms | 110.68ms | 50.76ms | 1.86MB |
| CSV | 83.61ms | 52.88ms | 1.12ms | 20.94ms | 697.88ms | 47.22ms | 54.73ms | 73.8KB |
| SQLite | 95.75ms | 36.41ms | 1.15ms | 27.43ms | 699.34ms | 43.35ms | 41.86ms | 700.0KB |
| Excel | 101.41ms | 47.06ms | 1.23ms | 21.25ms | 679.85ms | 551.74ms | 738.39ms | 294.2KB |
| XML | 84.30ms | 95.31ms | 1.10ms | 20.99ms | 686.28ms | 245.91ms | 194.11ms | 3.43MB |

### 测试 2: macOS, Python 3.13.11

测试数据量: 10 0000 条记录

| 引擎 | 插入 | 全表查询 | 索引查询 | 条件查询 | 更新 | 保存 | 加载 | 文件大小 |
|------|------|----------|----------|----------|------|------|------|----------|
| Binary | 490.16ms | 198.83ms | 520.1μs | 137.22ms | 2.05s | 360.15ms | 690.97ms | 11.04MB |
| JSON | 623.97ms | 200.42ms | 486.6μs | 84.47ms | 2.14s | 377.35ms | 534.53ms | 18.14MB |
| CSV | 618.45ms | 209.03ms | 458.6μs | 156.90ms | 2.23s | 186.68ms | 553.73ms | 732.0KB |
| SQLite | 707.76ms | 232.20ms | 576.1μs | 91.83ms | 2.21s | 145.68ms | 596.65ms | 6.97MB |
| Excel | 636.64ms | 213.70ms | 443.3μs | 84.96ms | 2.16s | 2.40s | 3.83s | 2.84MB |
| XML | 857.93ms | 229.73ms | 487.0μs | 84.69ms | 1.97s | 975.08ms | 1.27s | 34.54MB |

**说明**:
- 索引查询: 100次索引字段等值查询
- 更新: 100次记录更新
- 保存/加载: 持久化到磁盘/从磁盘加载

**结论**:
- **Binary** 插入和全表查询最快，适合读多写少场景
- **SQLite** 保存速度最快（145ms），综合性能均衡
- **CSV** 文件最小（732KB，ZIP压缩），保存速度优秀，适合数据交换
- **JSON** 条件查询快，平衡性能和可读性，适合开发调试
- **Excel** I/O 较慢（加载3.83s），适合需要可视化编辑的场景
- **XML** 文件最大（34.54MB），适合企业集成和标准化交换

### 引擎特性对比

| 引擎 | 查询性能 | I/O性能 | 存储效率 | 人类可读 | 外部依赖 |
|------|---------|---------|---------|---------|---------|
| Binary | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ❌ | 无 |
| JSON | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ✅ | 无 |
| CSV | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ✅ | 无 |
| SQLite | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ❌ | 无 |
| Excel | ⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐ | ✅ | openpyxl |
| XML | ⭐⭐⭐⭐ | ⭐⭐ | ⭐ | ✅ | lxml |

**说明**:
- **查询性能**: 内存中查询速度（全表扫描、索引查询、条件过滤）
- **I/O性能**: 磁盘读写速度（保存和加载）
- **存储效率**: 文件大小（越小越好）
- **人类可读**: 文件内容是否可直接阅读/编辑
- **外部依赖**: 是否需要额外安装第三方库

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

| 限制 | 说明 |
|------|------|
| **无 JOIN 支持** | 仅支持单表查询，不支持多表关联查询 |
| **无 OR 条件** | 查询条件仅支持 AND 逻辑，不支持 OR |
| **无聚合函数** | 不支持 COUNT, SUM, AVG, MIN, MAX 等 |
| **无关系加载** | 不支持延迟加载和预加载关联对象 |
| **无迁移工具** | Schema 变更需要手动处理 |
| **单写入者** | 不支持并发写入，适合单进程使用 |
| **全量保存** | 非二进制/SQLite 后端每次保存完整重写文件 |
| **无嵌套事务** | 仅支持单层事务，不支持嵌套 |

## 路线图 / TODO

### 已完成

- [x] 统一数据库连接器架构（`pytuck/connectors/` 模块）
- [x] 数据迁移工具（`migrate_engine()`, `import_from_database()`）
- [x] 从外部关系型数据库导入功能
- [x] 统一引擎版本管理（`pytuck/backends/versions.py`）
- [x] 表和列备注支持（`comment` 参数）

### 计划中的功能

> 📋 详细开发计划请参阅 [TODO.md](./TODO.md)

- [ ] **Web UI 界面支持** - 为独立 Web UI 库提供 API 支持
- [ ] **ORM 事件钩子系统** - 基于 SQLAlchemy 事件模式的完整事件系统
- [ ] **JOIN 支持** - 多表关联查询
- [ ] **OR 条件支持** - 复杂逻辑查询条件
- [ ] **聚合函数** - COUNT, SUM, AVG, MIN, MAX 等
- [ ] **关系延迟加载** - 优化关联数据加载性能
- [ ] **Schema 迁移工具** - 数据库结构版本管理
- [ ] **并发访问支持** - 多进程/线程安全访问

### 计划增加的引擎

- [ ] DuckDB - 分析型数据库引擎
- [ ] TinyDB - 纯 Python 文档数据库
- [ ] PyDbLite3 - 纯 Python 内存数据库
- [ ] diskcache - 基于磁盘的缓存引擎

### 计划中的优化

- [ ] 非二进制后端增量保存（当前每次保存完整重写）
- [ ] 使用 `tempfile` 模块改进临时文件处理安全性
- [ ] 大数据集的流式读写支持
- [ ] SQLite 后端连接池
- [ ] 关联关系和延迟加载增强

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
git clone https://github.com/go9sky/pytuck.git
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

灵感来自于 SQLAlchemy, Django ORM 和 TinyDB。
