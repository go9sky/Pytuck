# Pytuck 项目说明

## 项目简介

Pytuck 是一个纯 Python 实现的轻量级文档数据库，支持多种存储引擎，无需编写 SQL，通过对象和方法管理数据。

## 目录结构

```
pytuck/
├── pytuck/                   # 核心库
│   ├── __init__.py          # 公开 API 导出
│   ├── orm.py               # ORM 核心：Column, PureBaseModel, CRUDBaseModel, declarative_base
│   ├── storage.py           # 存储引擎封装
│   ├── session.py           # 会话管理（事务、连接）
│   ├── query.py             # 查询构建器（Query, BinaryExpression, Condition）
│   ├── statements.py        # SQL 风格语句构建（select, insert, update, delete）
│   ├── result.py            # 查询结果封装（Result, ScalarResult, Row, CursorResult）
│   ├── exceptions.py        # 异常定义
│   ├── index.py             # 索引管理
│   ├── types.py             # 类型编解码
│   ├── utils.py             # 工具函数
│   ├── backends/            # 存储引擎实现
│   │   ├── base.py          # 基类
│   │   ├── binary.py        # 二进制引擎（默认）
│   │   ├── json_backend.py  # JSON 引擎
│   │   ├── csv_backend.py   # CSV 引擎
│   │   ├── sqlite_backend.py # SQLite 引擎
│   │   ├── excel_backend.py # Excel 引擎
│   │   └── xml_backend.py   # XML 引擎
│   ├── connectors/          # 数据库连接器（统一接口）
│   │   ├── __init__.py      # 连接器导出
│   │   ├── base.py          # DatabaseConnector 抽象基类
│   │   └── sqlite_connector.py # SQLite 连接器
│   └── tools/               # 工具模块（不从根包导出）
│       ├── __init__.py      # 工具导出
│       ├── migrate.py       # 数据迁移工具
│       └── adapters.py      # 数据库适配器（connectors 的薄包装）
├── examples/                 # 示例代码
│   ├── new_api_demo.py      # 纯模型模式示例（PureBaseModel + Session）
│   ├── active_record_demo.py # Active Record 模式示例（CRUDBaseModel）
│   ├── sqlalchemy20_api_demo.py # SQLAlchemy 2.0 风格 API
│   ├── transaction_demo.py  # 事务管理示例
│   └── all_engines_test.py  # 多引擎测试
├── tests/                    # 测试文件
│   ├── __init__.py
│   └── test_orm.py          # ORM 综合测试
└── README.md                 # 项目文档
```

## 核心概念

### 两种模型基类

1. **PureBaseModel**（纯模型）
   - 只定义数据结构，不包含 CRUD 方法
   - 通过 Session + Statement API 操作数据
   - 适合大型项目、团队开发

2. **CRUDBaseModel**（Active Record）
   - 继承 PureBaseModel，添加 CRUD 方法
   - 包含 create, save, delete, refresh, get, filter, filter_by, all
   - 适合小型项目、快速原型

### declarative_base 工厂函数

```python
from typing import Type
from pytuck import Storage, declarative_base, PureBaseModel, CRUDBaseModel

db = Storage(file_path='mydb.db')

# 纯模型模式（默认）
Base: Type[PureBaseModel] = declarative_base(db)

# Active Record 模式
Base: Type[CRUDBaseModel] = declarative_base(db, crud=True)
```

### 关键类和函数

| 名称 | 位置 | 用途 |
|------|------|------|
| `Column` | orm.py | 列定义描述符 |
| `PureBaseModel` | orm.py | 纯模型基类类型 |
| `CRUDBaseModel` | orm.py | Active Record 基类类型 |
| `declarative_base()` | orm.py | 创建模型基类的工厂函数 |
| `Relationship` | orm.py | 关联关系描述符 |
| `Storage` | storage.py | 存储引擎封装 |
| `Session` | session.py | 会话管理 |
| `Query` | query.py | 查询构建器 |
| `BinaryExpression` | query.py | 查询表达式 |
| `select/insert/update/delete` | statements.py | SQL 风格语句 |
| `Result` | result.py | 查询结果 |
| `DatabaseConnector` | connectors/base.py | 数据库连接器抽象基类 |
| `SQLiteConnector` | connectors/sqlite_connector.py | SQLite 连接器 |
| `migrate_engine` | tools/migrate.py | Pytuck 格式间数据迁移 |
| `import_from_database` | tools/migrate.py | 从外部数据库导入 |

## 数据持久化

Pytuck 的数据持久化机制需要特别注意：

### 纯模型模式（Session）

```python
# 默认模式：auto_flush=False
db = Storage(file_path='data.db')

session.execute(insert(User).values(name='Alice'))
session.commit()  # 只提交到 Storage 内存，不写入磁盘！

# 必须手动写入磁盘
db.flush()  # 方式1：显式刷新
# 或
db.close()  # 方式2：关闭时自动刷新
```

### Active Record 模式（CRUDBaseModel）

```python
# 默认模式：auto_flush=False
db = Storage(file_path='data.db')
Base = declarative_base(db, crud=True)

# create/save/delete 只修改内存，不写入磁盘！
user = User.create(name='Alice')
user.save()

# 必须手动写入磁盘
db.flush()  # 方式1：显式刷新
# 或
db.close()  # 方式2：关闭时自动刷新
```

### 自动持久化

```python
# 自动模式：每次操作后自动写入磁盘
db = Storage(file_path='data.db', auto_flush=True)

# 纯模型模式
session.commit()  # 自动写入磁盘

# Active Record 模式
User.create(name='Alice')  # 自动写入磁盘
user.save()  # 自动写入磁盘
```

### 方法说明

| 方法 | 模式 | 说明 |
|------|------|------|
| `session.flush()` | 纯模型 | 将 Session 待处理对象刷新到 Storage 内存 |
| `session.commit()` | 纯模型 | 调用 flush()；若 `auto_flush=True` 则同时写入磁盘 |
| `Model.create/save/delete()` | Active Record | 修改 Storage 内存；若 `auto_flush=True` 则同时写入磁盘 |
| `storage.flush()` | 通用 | 强制将内存数据写入磁盘（当 `_dirty=True` 时） |
| `storage.close()` | 通用 | 关闭数据库，自动调用 `flush()` |

### 注意事项

- **默认不自动写入磁盘**：`commit()` 和 `save()` 只是提交到内存，需要 `flush()` 或 `close()` 才写入磁盘
- **生产环境建议**：使用 `auto_flush=True` 确保数据安全
- **批量操作优化**：大量操作时使用默认模式，最后统一 `flush()`

## 开发约定

### 代码风格
- 使用 Python 3.7+ 类型注解
- 遵循 PEP 8 规范
- 中文注释，英文代码

### 类型提示规范（强制）
- **所有函数和方法必须有完整的类型提示**
  - 入参类型：所有参数都需要类型注解
  - 返回类型：必须声明返回类型（除了 `def __init__(self)` 等特例方法外，任何自定义方法包括 `-> None` 的返回类型，都应该声明）
- 使用 `typing` 模块中的类型：`Any`, `Optional`, `List`, `Dict`, `Tuple`, `Union`, `Type`, `TypeVar` 等
- 泛型类型使用 `TypeVar` 定义
- 对于复杂类型，优先使用 `TYPE_CHECKING` 导入避免循环引用
- 示例：

```python
from typing import Any, Dict, List, Optional, Type, TypeVar, TYPE_CHECKING

if TYPE_CHECKING:
    from .storage import Storage

T = TypeVar('T', bound='PureBaseModel')

def get_record(table_name: str, pk: Any) -> Optional[Dict[str, Any]]:
    """获取记录"""
    pass

def create(cls: Type[T], **kwargs: Any) -> T:
    """创建实例"""
    pass
```

### 测试
- 测试文件位于 `tests/` 目录
- 运行测试：`python -m unittest tests.test_orm` 或 `python tests/test_orm.py`

### 模块职责规范（强制）

每个模块应保持单一职责，不应定义不属于其职责范围的内容：

| 模块 | 职责 | 可以定义 | 不可以定义 |
|------|------|----------|-----------|
| `exceptions.py` | 异常定义 | 所有自定义异常类 | 业务逻辑、工具函数 |
| `orm.py` | ORM 核心 | 模型基类、Column、Relationship | 异常类、存储逻辑 |
| `storage.py` | 存储封装 | Storage、Table 类 | 异常类、ORM 逻辑 |
| `query.py` | 查询构建 | Query、Condition、BinaryExpression | 异常类、存储逻辑 |
| `backends/*.py` | 后端实现 | 具体后端类 | 异常类、ORM 逻辑 |
| `tools/*.py` | 工具函数 | 迁移等辅助功能 | 异常类、核心逻辑 |

**规则**：
- 异常类只能在 `exceptions.py` 中定义，其他模块通过 `from .exceptions import XxxError` 导入使用
- 每个模块只导入其职责范围内需要的依赖
- 避免循环依赖：使用 `TYPE_CHECKING` 进行类型注解导入

### 示例代码
- 新示例应使用新 API（declarative_base + Session 或 crud=True）
- 示例文件命名：`<功能>_demo.py`

### 文档更新规范（强制）

当更新 README.md 或 CHANGELOG.md 时，**必须同步更新对应的英文文档**：

| 中文文档 | 英文文档 |
|----------|----------|
| `README.md` | `README.EN.md` |
| `CHANGELOG.md` | `CHANGELOG.EN.md` |

**规则**：
- 任何添加到中文文档的内容，必须同时添加到英文文档
- 保持两个文档的结构和章节对应一致
- 代码示例可以保持一致（代码本身是英文）

### CHANGELOG 日期规范（强制）

在创建或更新 CHANGELOG 条目时，**必须先获取当前日期**再写入：

```bash
# Windows PowerShell
powershell -Command "Get-Date -Format 'yyyy-MM-dd'"

# Linux/macOS
date +%Y-%m-%d
```

**规则**：
- 版本条目格式：`## [版本号] - YYYY-MM-DD`
- 日期必须是实际创建/发布日期，不能使用占位符或猜测日期
- 创建新版本条目前，必须先执行日期获取命令确认当前日期

## 常用命令

```bash
# 运行测试
python tests/test_orm.py

# 运行示例
python examples/new_api_demo.py
python examples/active_record_demo.py

# 运行多引擎测试
python examples/all_engines_test.py
```

## API 快速参考

### 纯模型模式

```python
from typing import Type
from pytuck import Storage, declarative_base, Session, Column
from pytuck import PureBaseModel, select, insert, update, delete

db = Storage(file_path='mydb.db')
Base: Type[PureBaseModel] = declarative_base(db)

class User(Base):
    __tablename__ = 'users'
    id = Column('id', int, primary_key=True)
    name = Column('name', str)

session = Session(db)

# 插入
stmt = insert(User).values(name='Alice')
session.execute(stmt)
session.commit()

# 查询
stmt = select(User).where(User.name == 'Alice')
result = session.execute(stmt)
users = result.scalars().all()
```

### Active Record 模式

```python
from typing import Type
from pytuck import Storage, declarative_base, Column, CRUDBaseModel

db = Storage(file_path='mydb.db')
Base: Type[CRUDBaseModel] = declarative_base(db, crud=True)

class User(Base):
    __tablename__ = 'users'
    id = Column('id', int, primary_key=True)
    name = Column('name', str)

# 创建
user = User.create(name='Alice')

# 查询
user = User.get(1)
users = User.filter(User.name == 'Alice').all()

# 更新
user.name = 'Bob'
user.save()

# 删除
user.delete()
```
