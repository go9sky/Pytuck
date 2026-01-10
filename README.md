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
- **Pythonic 查询语法** - 使用原生 Python 运算符构建查询（`User.age >= 18`）
- **索引优化** - 哈希索引加速查询
- **类型安全** - 自动类型验证和转换
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
db = Storage(file_path='data.json', engine='json', indent=2)
```

**适用场景**:
- 开发调试
- 配置存储
- 数据交换

### CSV 引擎

**特点**: Excel兼容、表格格式、数据分析友好

```python
db = Storage(file_path='data_dir', engine='csv', encoding='utf-8')
```

**适用场景**:
- 数据分析
- Excel导入导出
- 表格数据

### SQLite 引擎

**特点**: 成熟稳定、ACID特性、支持SQL

```python
db = Storage(file_path='data.sqlite', engine='sqlite')
```

**适用场景**:
- 需要SQL查询
- 需要事务保证
- 大量数据

### Excel 引擎（可选）

**依赖**: `openpyxl>=3.0.0`

```python
db = Storage(file_path='data.xlsx', engine='excel')
```

**适用场景**:
- 业务报表
- 可视化需求
- 办公自动化

### XML 引擎（可选）

**依赖**: `lxml>=4.9.0`

```python
db = Storage(file_path='data.xml', engine='xml')
```

**适用场景**:
- 企业集成
- 标准化交换
- 配置文件

## 高级特性

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

# 从二进制迁移到JSON
migrate_engine(
    source_path='data.db',
    source_engine='binary',
    target_path='data.json',
    target_engine='json'
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
│         辅助层 (utils/)              │
│   Index, TypeCodec, Transaction      │
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

- [ ] JOIN 支持（多表关联查询）
- [ ] OR 条件支持
- [ ] 聚合函数（COUNT, SUM, AVG, MIN, MAX）
- [ ] 关系延迟加载
- [ ] Schema 迁移工具
- [ ] 并发访问支持

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

## 贡献

欢迎提交 Issue 和 Pull Request！

## 许可证

MIT License

## 致谢

灵感来自于 SQLAlchemy, Django ORM 和 TinyDB。
