# 更新日志 / Changelog

本文件记录项目的所有重要变更。格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，遵循 [语义化版本](https://semver.org/lang/zh-CN/) 规范。

This file documents all notable changes. Format based on [Keep a Changelog](https://keepachangelog.com/en-US/1.0.0/), following [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

> 历史版本请查看 / For historical versions, see: [docs/changelog/](./docs/changelog/)

---

## [0.5.0] - 2026-01-25

### 新增 / Added

- **Schema 同步与迁移功能 / Schema Sync & Migration**
  - 支持在程序第二次启动加载已有数据库时自动同步表结构
  - 新增 `SyncOptions` 配置类，控制同步行为：
    - `sync_table_comment`：是否同步表备注（默认 True）
    - `sync_column_comments`：是否同步列备注（默认 True）
    - `add_new_columns`：是否添加新列（默认 True）
    - `drop_missing_columns`：是否删除缺失的列（默认 False，危险操作）
  - 新增 `SyncResult` 结果类，记录同步变更详情
  - `declarative_base()` 新增 `sync_schema` 和 `sync_options` 参数，支持模型定义时自动同步
  - 三层 API 设计，支持不同使用场景：
    - **Table 层**：`table.add_column()`, `table.drop_column()`, `table.update_comment()` 等
    - **Storage 层**：`storage.sync_table_schema()`, `storage.add_column()`, `storage.drop_table()`, `storage.rename_table()` 等
    - **Session 层**：`session.sync_schema()`, `session.add_column()`, `session.drop_column()` 等
  - 支持 SQLite 原生 SQL 模式下的 DDL 操作（ALTER TABLE）
  - 支持纯表名 API（无需模型类），便于 Pytuck-view 等外部工具调用
  - 新增 26 个测试用例
  - 示例 / Example：
    ```python
    from pytuck import Storage, declarative_base, SyncOptions, Column

    # 自动同步模式
    db = Storage(file_path='existing.db')
    Base = declarative_base(db, sync_schema=True)

    class User(Base):
        __tablename__ = 'users'
        id = Column(int, primary_key=True)
        name = Column(str)
        age = Column(int, nullable=True)  # 新增列，自动同步

    # 手动同步模式
    from pytuck import Session
    session = Session(db)
    result = session.sync_schema(User)
    if result.has_changes:
        print(f"Added columns: {result.columns_added}")

    # Storage 层 API（面向 Pytuck-view）
    db.add_column('users', Column(str, nullable=True, name='email'))
    db.sync_table_schema('users', columns, comment='用户表')
    ```

- **Excel 后端行号映射功能 / Excel Row Number Mapping**
  - 新增 `row_number_mapping` 选项，支持将 Excel 物理行号用作主键或映射到指定字段
  - `row_number_mapping='as_pk'`：将行号直接作为主键值
  - `row_number_mapping='field'`：将行号映射到指定字段（默认 `row_num`）
  - `row_number_field_name`：自定义行号字段名称
  - `row_number_override`：在 Pytuck 创建的文件中强制应用行号映射
  - `persist_row_number`：保存时持久化行号字段
  - 支持读取外部 Excel 文件（无 Pytuck 元数据）
  - 新增 Excel 行号映射专项测试（11 个测试用例）
  - 示例 / Example：
    ```python
    from pytuck import Storage
    from pytuck.common.options import ExcelBackendOptions

    # 将行号作为主键
    opts = ExcelBackendOptions(row_number_mapping='as_pk')
    db = Storage(file_path='external.xlsx', engine='excel', backend_options=opts)

    # 将行号映射到 row_num 字段
    opts = ExcelBackendOptions(
        row_number_mapping='field',
        row_number_field_name='row_num',
        persist_row_number=True
    )
    db = Storage(file_path='external.xlsx', engine='excel', backend_options=opts)
    ```

### 改进 / Improved

- **SQLite 原生 SQL 模式优化 / SQLite Native SQL Mode**
  - SQLite 后端默认启用原生 SQL 模式（`use_native_sql=True`），直接执行 SQL 而非全量加载/保存
  - 完善 `TYPE_TO_SQL` 映射，支持全部 10 种 Pytuck 类型：
    - 基础类型：`int`, `str`, `float`, `bool`, `bytes`
    - 扩展类型：`datetime`, `date`, `timedelta`, `list`, `dict`
  - 完善 `SQL_TO_TYPE` 反向映射，支持外部 SQLite 数据库类型推断（`DATETIME`, `DATE`, `TIMESTAMP`）
  - 新增原生 SQL 模式专项测试（11 个测试用例）
  - 修复 NULL 值查询问题（使用 `IS NULL` 而非 `= NULL`）
  - 支持多列排序（`order_by('col1').order_by('col2', desc=True)`）

- **迁移工具延迟加载后端支持 / Migration Tool Lazy Loading Backend Support**
  - 修复 `migrate_engine()` 在源后端使用延迟加载模式（如 SQLite 原生模式）时数据为空的问题
  - `StorageBackend` 基类新增 `supports_lazy_loading()` 方法，用于判断后端是否只加载 schema
  - `StorageBackend` 基类新增 `populate_tables_with_data()` 方法，用于在延迟加载模式下填充数据
  - `StorageBackend` 基类新增 `save_full()` 方法，确保迁移时保存所有数据
  - 新增延迟加载后端迁移专项测试（5 个测试用例）

- **后端注册器优化 / Backend Registry Optimization**：使用 `__init_subclass__` 实现自动注册
  - `StorageBackend` 基类新增 `__init_subclass__` 方法，子类定义时自动注册到 `BackendRegistry`
  - 移除了 `BackendRegistry._discover_backends()` 硬编码发现逻辑
  - 用户自定义后端只需继承 `StorageBackend` 并定义 `ENGINE_NAME` 即可自动注册
  - 依赖检查仍在 `get_backend()` 中尽早进行，确保用户数据安全
  - User-defined backends automatically register when subclassing `StorageBackend`
  - 示例 / Example：
    ```python
    from pytuck.backends import StorageBackend

    class MyCustomBackend(StorageBackend):
        ENGINE_NAME = 'custom'
        REQUIRED_DEPENDENCIES = ['my_lib']

        def save(self, tables): ...
        def load(self): ...
        def exists(self): ...
        def delete(self): ...

    # 类定义时自动注册，无需手动调用
    # Automatically registered on class definition
    ```

- **Relationship 关联关系优化 / Relationship Enhancement**
  - 支持使用表名字符串定义双向关联，无需在类定义后手动赋值反向关联
  - 新增 Storage 级别模型注册表（`_model_registry`），按表名映射模型类
  - 新增 `uselist` 参数，支持自引用场景显式指定返回类型：
    - `uselist=True`：强制返回列表（一对多）
    - `uselist=False`：强制返回单个对象（多对一）
    - `uselist=None`（默认）：根据外键位置自动判断
  - 支持 IDE 类型提示：通过直接声明返回类型获得精确的代码补全
  - 新增全面的 Relationship 测试（一对一、多对一、多对多、自引用、字符串引用）
  - 新增 `examples/relationship_demo.py` 综合示例
  - 示例 / Example：
    ```python
    from typing import List, Optional

    class Order(Base):
        __tablename__ = 'orders'
        id = Column(int, primary_key=True)
        user_id = Column(int)
        # 使用表名定义关联（无需考虑类定义顺序）
        user: Optional[User] = Relationship('users', foreign_key='user_id')  # type: ignore

    class User(Base):
        __tablename__ = 'users'
        id = Column(int, primary_key=True)
        # 双向关联，直接声明返回类型获得 IDE 提示
        orders: List[Order] = Relationship('orders', foreign_key='user_id')  # type: ignore

    # 自引用（树形结构）
    class Category(Base):
        __tablename__ = 'categories'
        id = Column(int, primary_key=True)
        parent_id = Column(int, nullable=True)
        parent: Optional['Category'] = Relationship(  # type: ignore
            'categories', foreign_key='parent_id', uselist=False
        )
        children: List['Category'] = Relationship(  # type: ignore
            'categories', foreign_key='parent_id', uselist=True
        )
    ```

### 重构 / Refactored

- **后端模块结构优化 / Backend Module Structure**
  - `pytuck/backends/__init__.py` 简化为仅导入/导出职责
  - `pytuck/backends/registry.py` 移除 `_initialized` 和 `_discover_backends()`
  - 内置后端在 `__init__.py` 中显式导入，触发自动注册

- **异常系统重构 / Exception System Refactoring**
  - 重构 `PytuckException` 基类，添加通用字段：`message`、`table_name`、`column_name`、`pk`、`details`
  - 添加 `to_dict()` 方法，便于日志记录和序列化
  - 新增异常类型：
    - `TypeConversionError`：类型转换失败（继承自 `ValidationError`）
    - `ConfigurationError`：配置错误（引擎配置、后端选项等）
    - `SchemaError`：Schema 定义错误（如缺少主键，继承自 `ConfigurationError`）
    - `QueryError`：查询构建或执行错误
    - `ConnectionError`：数据库连接未建立或已断开
    - `UnsupportedOperationError`：不支持的操作
  - 统一替换所有内置异常为自定义异常类型：
    - `ValueError` → `TypeConversionError`/`ValidationError`/`ConfigurationError`/`QueryError`
    - `TypeError` → `ConfigurationError`/`QueryError`
    - `RuntimeError` → `ConnectionError`/`TransactionError`
    - `NotImplementedError`（运行时）→ `UnsupportedOperationError`
  - 所有新异常类型已在 `pytuck/__init__.py` 中导出，可直接导入使用
  - 异常层次结构：
    ```
    PytuckException (基类)
    ├── TableNotFoundError        # 表不存在
    ├── RecordNotFoundError       # 记录不存在
    ├── DuplicateKeyError         # 主键重复
    ├── ColumnNotFoundError       # 列不存在
    ├── ValidationError           # 数据验证错误
    │   └── TypeConversionError   # 类型转换失败
    ├── ConfigurationError        # 配置错误
    │   └── SchemaError           # Schema 定义错误
    ├── QueryError                # 查询错误
    ├── TransactionError          # 事务错误
    ├── ConnectionError           # 连接错误
    ├── SerializationError        # 序列化错误
    ├── EncryptionError           # 加密错误
    ├── MigrationError            # 迁移错误
    ├── PytuckIndexError          # 索引错误
    └── UnsupportedOperationError # 不支持的操作
    ```

### 破坏性变更 / Breaking Changes

- **Column 定义 API 简化 / Column Definition API Simplification**
  - `Column` 构造函数签名变更：`col_type` 现在是第一个位置参数，`name` 变为可选关键字参数
  - `name` 参数默认使用变量名（通过 Python 描述符协议 `__set_name__` 自动获取）
  - 所有其他参数现在必须使用关键字形式传递
  - 迁移指南 / Migration Guide：
    ```python
    # 旧用法 / Old usage
    id = Column('id', int, primary_key=True)
    name = Column('name', str)
    email = Column('user_email', str)

    # 新用法 / New usage
    id = Column(int, primary_key=True)       # name 自动取 'id'
    name = Column(str)                        # name 自动取 'name'
    email = Column(str, name='user_email')   # 显式指定列名（当与变量名不同时）
    ```
  - 新签名 / New Signature：
    ```python
    Column(
        col_type: Type,              # 必填，第一个位置参数
        *,                           # 强制后续为关键字参数
        name: Optional[str] = None,  # 可选，默认取变量名
        nullable: bool = True,
        primary_key: bool = False,
        index: bool = False,
        default: Any = None,
        foreign_key: Optional[tuple] = None,
        comment: Optional[str] = None,
        strict: bool = False
    )
    ```

- **查询结果 API 简化 / Query Result API Simplification**
  - 移除 `Result.scalars()` 方法，直接使用 `Result.all()`/`first()`/`one()`/`one_or_none()`
  - 移除 `Result.rows()` 方法
  - 移除 `Result.fetchall()` 方法
  - 移除 `Row` 类
  - `ScalarResult` 改为内部类 `_ScalarResult`，不再公开导出
  - 迁移指南 / Migration Guide：
    ```python
    # 旧用法 / Old usage
    users = result.scalars().all()
    user = result.scalars().first()

    # 新用法 / New usage
    users = result.all()
    user = result.first()
    ```
  - 新 API 说明 / New API:
    - `Result.all()` → 返回模型实例列表 `List[T]`
    - `Result.first()` → 返回第一个模型实例 `Optional[T]`
    - `Result.one()` → 返回唯一模型实例 `T`（必须恰好一条）
    - `Result.one_or_none()` → 返回唯一模型实例或 None `Optional[T]`（最多一条）
    - `Result.rowcount()` → 返回结果数量 `int`
