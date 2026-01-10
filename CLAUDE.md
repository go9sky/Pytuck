# Pytuck 项目说明

## 项目简介

Pytuck 是一个纯 Python 实现的轻量级文档数据库，支持多种存储引擎，无需编写 SQL，通过对象和方法管理数据。

## 目录结构

```
littleDB/
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
│   └── backends/            # 存储引擎实现
│       ├── base.py          # 基类
│       ├── binary.py        # 二进制引擎（默认）
│       ├── json_backend.py  # JSON 引擎
│       ├── csv_backend.py   # CSV 引擎
│       ├── sqlite_backend.py # SQLite 引擎
│       ├── excel_backend.py # Excel 引擎
│       └── xml_backend.py   # XML 引擎
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

## 开发约定

### 代码风格
- 使用 Python 3.7+ 类型注解
- 遵循 PEP 8 规范
- 中文注释，英文代码

### 类型提示规范（强制）
- **所有函数和方法必须有完整的类型提示**
  - 入参类型：所有参数都需要类型注解
  - 返回类型：必须声明返回类型（不包括 `-> None`）
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
- 运行测试：`python -m pytest tests/` 或 `python tests/test_orm.py`

### 示例代码
- 新示例应使用新 API（declarative_base + Session 或 crud=True）
- 示例文件命名：`<功能>_demo.py`

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
