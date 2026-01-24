## 基本要求

- 始终使用中文回答

### 运行环境

- **Windows**：默认使用 PowerShell 执行命令，PowerShell 中命令无法执行时再尝试 cmd
- **Linux/macOS**：使用默认 shell（bash/zsh）

---

# Pytuck 项目说明

## 项目简介

Pytuck 是一个纯 Python 实现的轻量级文档数据库，支持多种存储引擎，无需编写 SQL，通过对象和方法管理数据。

## 目录结构

```
pytuck/
├── pytuck/                   # 核心库（根目录只允许 __init__.py 和 py.typed）
│   ├── __init__.py          # 公开 API 导出
│   ├── py.typed             # 类型注解标记文件
│   ├── common/              # 公共模块（无内部依赖，可直接导入）
│   │   ├── __init__.py      # 公共模块导出
│   │   ├── options.py       # 配置选项 dataclass 定义
│   │   ├── utils.py         # 工具函数
│   │   └── exceptions.py    # 异常定义
│   ├── core/                # 核心模块
│   │   ├── __init__.py      # 核心模块导出
│   │   ├── orm.py           # ORM 核心：Column, PureBaseModel, CRUDBaseModel, declarative_base
│   │   ├── storage.py       # 存储引擎封装
│   │   ├── session.py       # 会话管理（事务、连接）
│   │   ├── index.py         # 索引管理
│   │   └── types.py         # 类型编解码
│   ├── query/               # 查询子系统
│   │   ├── __init__.py      # 查询模块导出
│   │   ├── builder.py       # 查询构建器（Query, BinaryExpression, Condition）
│   │   ├── statements.py    # SQL 风格语句构建（select, insert, update, delete）
│   │   └── result.py        # 查询结果封装（Result, ScalarResult, Row, CursorResult）
│   ├── backends/            # 存储引擎实现
│   │   ├── __init__.py      # 后端导出（导入所有后端触发自动注册）
│   │   ├── base.py          # StorageBackend 基类（含 __init_subclass__ 自动注册）
│   │   ├── registry.py      # BackendRegistry 注册器和工厂函数
│   │   ├── versions.py      # 统一引擎版本管理
│   │   ├── backend_binary.py  # 二进制引擎（默认）
│   │   ├── backend_csv.py   # CSV 引擎
│   │   ├── backend_excel.py # Excel 引擎
│   │   ├── backend_json.py  # JSON 引擎
│   │   ├── backend_sqlite.py # SQLite 引擎
│   │   └── backend_xml.py   # XML 引擎
│   ├── connectors/          # 数据库连接器（统一接口）
│   │   ├── __init__.py      # 连接器导出
│   │   ├── base.py          # DatabaseConnector 抽象基类
│   │   └── connector_sqlite.py # SQLite 连接器
│   └── tools/               # 工具模块（不从根包导出）
│       ├── __init__.py      # 工具导出
│       ├── migrate.py       # 数据迁移工具
│       └── adapters.py      # 数据库适配器（connectors 的薄包装）
├── docs/                     # 项目文档
│   ├── changelog/           # 历史版本日志归档
│   │   └── *.*.*.md
│   └── ...                  # 其他文档
├── examples/                 # 用户示例代码（仅存放演示脚本）
│   ├── _common.py           # 示例共用工具（下划线前缀表示内部使用）
│   ├── new_api_demo.py      # 纯模型模式示例（PureBaseModel + Session）
│   ├── active_record_demo.py # Active Record 模式示例（CRUDBaseModel）
│   ├── sqlalchemy20_api_demo.py # SQLAlchemy 2.0 风格 API
│   └── ...                  # 其他 *_demo.py 示例文件
├── tests/                    # 测试文件（pytest 框架）
│   ├── __init__.py
│   ├── conftest.py          # pytest 配置和共享 fixtures
│   ├── test_*.py            # 测试用例文件（必须以 test_ 开头）
│   └── benchmark/           # 性能基准测试（排除在 pytest 外）
│       ├── __init__.py
│       ├── benchmark.py     # 引擎性能基准测试
│       └── benchmark_encryption.py  # 加密性能测试
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
| `Column` | core/orm.py | 列定义描述符 |
| `PureBaseModel` | core/orm.py | 纯模型基类类型 |
| `CRUDBaseModel` | core/orm.py | Active Record 基类类型 |
| `declarative_base()` | core/orm.py | 创建模型基类的工厂函数 |
| `Relationship` | core/orm.py | 关联关系描述符 |
| `Storage` | core/storage.py | 存储引擎封装 |
| `Session` | core/session.py | 会话管理 |
| `Query` | query/builder.py | 查询构建器 |
| `BinaryExpression` | query/builder.py | 查询表达式 |
| `select/insert/update/delete` | query/statements.py | SQL 风格语句 |
| `Result` | query/result.py | 查询结果 |
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

### 路径操作规范（强制）

**所有文件路径操作必须使用 `pathlib.Path`**，避免混合使用 `os.path` 和字符串操作：

#### 统一原则
- **内部统一使用 Path**：所有内部路径处理使用 `pathlib.Path`
- **边界转换**：公共 API 接受路径参数时立即转换：`file_path = Path(file_path).expanduser()`
- **兼容性处理**：调用外部 API 时根据需要转换为字符串：`str(path)`
- **Python 3.7 兼容**：避免使用 Python 3.8+ 特有的 Path 方法参数

#### 标准模式

```python
# ✅ 正确的路径操作模式
from pathlib import Path

# 接受路径参数时立即转换
def __init__(self, file_path: str, options: BackendOptions):
    self.file_path: Path = Path(file_path).expanduser()

# 路径拼接和操作
temp_path = self.file_path.parent / (self.file_path.name + '.tmp')

# 文件操作
if self.file_path.exists():
    self.file_path.unlink()
temp_path.replace(self.file_path)

# 文件信息获取
file_stat = self.file_path.stat()
size = file_stat.st_size
mtime = file_stat.st_mtime

# Python 3.7 兼容的文件删除
try:
    file_path.unlink()
except FileNotFoundError:
    pass

# 调用外部API时转换为字符串
with zipfile.ZipFile(str(temp_path), 'w') as zf:
    # ...
```

#### 禁止的模式

```python
# ❌ 错误的混合使用
import os
temp_path = self.file_path + '.tmp'  # Path + str
if os.path.exists(self.file_path):   # 混合 os.path 和 Path
    os.remove(self.file_path)

# ❌ Python 3.8+ 特有参数
file_path.unlink(missing_ok=True)    # 不兼容 Python 3.7
```

#### 临时文件管理
- **示例和测试**：统一使用 `examples.common.get_project_temp_dir()` 返回 `Path` 对象
- **测试隔离**：测试中建议使用 `tempfile.TemporaryDirectory()` 确保隔离
- **原子操作**：使用 `Path.replace()` 进行原子性文件替换，避免 remove + rename 模式

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
    from .storage import Storage  # 同包内引用
    from ..core.storage import Storage  # 跨包引用示例

T = TypeVar('T', bound='PureBaseModel')

def get_record(table_name: str, pk: Any) -> Optional[Dict[str, Any]]:
    """获取记录"""
    pass

def create(cls: Type[T], **kwargs: Any) -> T:
    """创建实例"""
    pass
```

### 测试（强制）

**测试框架**：使用 pytest（作为开发依赖，不影响用户安装）

**一键运行所有测试**：
```bash
pytest tests/ -v
```

**强制要求**：
- **每次代码改动后必须运行全部测试并确保通过**
- 新增功能必须添加对应的测试用例
- 测试文件命名：`test_<模块名>.py`
- 测试类命名：`Test<功能名>`
- 测试方法命名：`test_<场景>`

**安装开发依赖**：
```bash
pip install -e ".[dev]"
```

**运行单个测试文件**：
```bash
pytest tests/test_orm.py -v
```

**运行性能基准测试**（不在 pytest 范围内）：
```bash
python tests/benchmark/benchmark.py -n 1000
python tests/benchmark/benchmark_encryption.py
```

### 模块职责规范（强制）

每个模块应保持单一职责，不应定义不属于其职责范围的内容：

| 模块 | 职责 | 可以定义 | 不可以定义 |
|------|------|----------|-----------|
| `common/exceptions.py` | 异常定义 | 所有自定义异常类 | 业务逻辑、工具函数 |
| `common/utils.py` | 工具函数 | 通用工具函数、辅助类 | 异常类、业务逻辑 |
| `common/options.py` | 配置选项 | dataclass 配置选项、默认值函数 | 异常类、业务逻辑 |
| `core/orm.py` | ORM 核心 | 模型基类、Column、Relationship | 异常类、存储逻辑 |
| `core/storage.py` | 存储封装 | Storage、Table 类 | 异常类、ORM 逻辑 |
| `query/builder.py` | 查询构建 | Query、Condition、BinaryExpression | 异常类、存储逻辑 |
| `backends/*.py` | 后端实现 | 具体后端类 | 异常类、ORM 逻辑 |
| `tools/*.py` | 工具函数 | 迁移等辅助功能 | 异常类、核心逻辑 |

**规则**：
- 异常类只能在 `common/exceptions.py` 中定义，其他模块通过 `from ..common.exceptions import XxxError` 导入使用
- 工具函数只能在 `common/utils.py` 中定义，其他模块通过 `from ..common.utils import xxx` 导入使用
- 每个模块只导入其职责范围内需要的依赖
- 避免循环依赖：使用 `TYPE_CHECKING` 进行类型注解导入

### 目录结构规范（强制）

#### 1. pytuck/ 根目录限制

**pytuck/ 根目录只允许存在一个 `.py` 文件**：
- `__init__.py`：公开 API 导出

**禁止在根目录下创建其他文件或模块**：
```
pytuck/
├── __init__.py     ✅ 允许
├── py.typed        ✅ 允许
├── any_module.py   ❌ 禁止
└── any_folder/     ❌ 禁止（除了规定的子目录）
```

#### 2. common/ 目录规范

**无内部依赖的模块必须放入 `pytuck/common/` 目录**：
- 该目录下的所有模块都应该是无内部依赖的
- 可以安全地直接导入，无需 `TYPE_CHECKING` 条件导入
- 适用于配置选项、常量、工具函数等

**示例**：
```python
# ✅ 正确：直接导入 common 模块
from pytuck.common.options import JsonBackendOptions

# ❌ 错误：common 模块不应该有内部依赖
# pytuck/common/options.py 中不应该导入 pytuck.core.* 等内部模块
```

#### 3. tests/ 目录规范（强制）

**tests/ 目录专门用于测试代码**，禁止放置示例、调试脚本或临时文件。

**目录结构**：
```
tests/
├── __init__.py
├── conftest.py          # pytest 共享 fixtures（必须存在）
├── test_*.py            # 测试用例文件（必须以 test_ 开头）
└── benchmark/           # 性能基准测试（独立子目录）
    ├── __init__.py
    ├── benchmark.py
    └── benchmark_encryption.py
```

**规则**：
| 规则 | 说明 |
|------|------|
| 测试文件命名 | 必须以 `test_` 开头，如 `test_orm.py` |
| 测试类命名 | 必须以 `Test` 开头，如 `TestColumn` |
| 测试方法命名 | 必须以 `test_` 开头，如 `test_insert` |
| 禁止创建 | ❌ 调试脚本、临时文件、示例代码 |
| benchmark 目录 | 性能测试脚本，排除在 pytest 运行范围外 |

**pytest 配置已在 `pyproject.toml` 中设置**：
- `testpaths = ["tests"]`
- `norecursedirs = ["benchmark"]`（排除 benchmark 目录）

#### 4. examples/ 目录规范（强制）

**examples/ 目录专门用于用户示例脚本**，展示 Pytuck 的使用方法。

**目录结构**：
```
examples/
├── _common.py           # 共用工具（下划线前缀表示内部使用）
├── *_demo.py            # 示例脚本（必须以 _demo.py 结尾）
└── README.md            # 示例说明文档（可选）
```

**规则**：
| 规则 | 说明 |
|------|------|
| 示例文件命名 | 必须以 `_demo.py` 结尾，如 `new_api_demo.py` |
| 内部工具命名 | 以下划线开头，如 `_common.py` |
| 禁止创建 | ❌ 测试文件、调试脚本、临时文件、未完成的代码 |
| 每个示例 | 必须是完整可运行的独立脚本 |

**禁止放入 examples/ 的文件类型**：
- `test_*.py`（测试文件应放入 tests/）
- `debug_*.py`（调试脚本应删除或放入 .gitignore）
- `temp*.py`、`tmp*.py`（临时文件应删除）
- 依赖外部未发布服务的脚本

### **kwargs 使用规范（强制）

#### 允许使用场景

**仅在以下情况下允许使用 `**kwargs`**：
1. **ORM 动态字段操作**：字段名在运行时确定
   ```python
   # ✅ 正确：字段名动态
   def filter_by(self, **kwargs: Any) -> 'Query':
       # 字段名在运行时确定，无法用 dataclass
       pass

   def values(self, **kwargs: Any) -> 'Insert':
       # 动态设置字段值
       pass
   ```

2. **Python 标准协议**：
   ```python
   # ✅ 正确：Python 内置协议
   def __init_subclass__(cls, **kwargs: Any) -> None:
       pass
   ```
   
3. **装饰器参数**：
   ```python
   # ✅ 正确：装饰器参数
   def my_decorator(func: Callable[..., Any], **kwargs: Any) -> Callable[..., Any]:
       pass
   ```

#### 禁止使用场景

**其他场景必须使用强类型 dataclass 替代 `**kwargs`**，避免滥用

#### dataclass 设计规范

**创建配置选项 dataclass 时必须遵循**：
1. **完整类型注解**：所有字段必须有类型注解
2. **合理默认值**：提供符合常用场景的默认值
3. **清晰文档**：添加 docstring 说明用途
4. **分组组织**：使用 Union 类型组织相关选项

```python
from dataclasses import dataclass

@dataclass
class JsonBackendOptions:
    """JSON 后端配置选项"""
    indent: int = 2                    # 缩进空格数
    ensure_ascii: bool = False         # 是否强制 ASCII 编码

# 使用 Union 类型组织
BackendOptions = Union[
    JsonBackendOptions,
    CsvBackendOptions,
    SqliteBackendOptions,
    # ...
]
```

### 存储引擎元数据规范（强制）

存储引擎的元数据（schema）必须采用**统一存储**方式，**禁止为每个表单独创建元数据结构**。

**原则**：
- 所有表的 schema 信息必须集中存储在一个位置
- 不要为每个表创建单独的 schema 文件、工作表或数据库表

**各引擎的正确做法**：

| 引擎 | 元数据存储位置 | 禁止的做法 |
|------|----------------|-----------|
| CSV (ZIP) | `_metadata.json` 中的 `tables` 字段 | ❌ 为每个表创建 `{table}_schema.json` |
| Excel | `_pytuck_tables` 工作表 | ❌ 为每个表创建 `{table}_schema` 工作表 |
| SQLite | `_pytuck_tables` 表 | ❌ 为每个表创建 `_pytuck_{table}_schema` 表 |
| JSON | `_metadata` 中的 `tables` 字段 | ❌ 为每个表创建单独的 schema 键 |
| XML | `<_pytuck_tables>` 元素 | ❌ 为每个表创建 `<{table}_schema>` 元素 |
| Binary | 文件头中的统一 schema 区域 | ❌ 为每个表创建单独的 schema 块 |

**新增引擎时必须遵循**：
1. 设计一个统一的元数据存储结构
2. 所有表的 schema 信息存储在同一位置
3. 使用类似 `_pytuck_tables` 的命名约定
4. 结构应包含：`table_name`, `primary_key`, `next_id`, `columns` (JSON)

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

### CHANGELOG 归档规范（强制）

当发布新版本时，**必须将旧版本内容归档到 `docs/changelog/` 目录**：

**归档流程**：
1. 创建归档文件 `docs/changelog/{版本号}.md`（如 `docs/changelog/0.4.0.md`）
2. 将旧版本的中英文内容合并到归档文件中
3. 更新 `CHANGELOG.md` 和 `CHANGELOG.EN.md`，只保留当前版本内容

**归档文件格式**：
```markdown
# Changelog - v{版本号}

> 发布日期 / Release Date: YYYY-MM-DD

---

## 中文

### 新增
...

---

## English

### Added
...
```

**规则**：
- 每个版本单独一个归档文件
- 归档文件包含完整的中英文内容
- 主 CHANGELOG 文件只保留当前最新版本
- 主文件顶部保留历史版本链接：`> 历史版本请查看 / For historical versions, see: [docs/changelog/](./docs/changelog/)`

## 常用命令

```bash
# 安装开发依赖
pip install -e ".[dev]"

# 一键运行所有测试（每次改动后必须运行）
pytest tests/ -v

# 运行单个测试文件
pytest tests/test_orm.py -v

# 运行性能基准测试
python tests/benchmark/benchmark.py -n 1000
python tests/benchmark/benchmark_encryption.py

# 运行示例
python examples/new_api_demo.py
python examples/active_record_demo.py
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
