# 更新日志

本文件记录项目的所有重要变更。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
遵循 [语义化版本](https://semver.org/lang/zh-CN/) 规范。

> [English Version](./CHANGELOG.EN.md)

## [0.3.0] - 2026-01-13

### 新增

- **Pytuck-View Web UI 支持**：为轻量级 Web 界面提供完整的数据查询支持
  - 新增 `Storage.query_table_data()` 方法，专为 Web UI 设计的分页查询接口
  - 扩展 `Storage.query()` 方法，添加 limit/offset/order_by/order_desc 参数支持
  - 通用后端分页接口：`StorageBackend.supports_server_side_pagination()` 和 `query_with_pagination()`
  - SQLite 后端服务端分页优化：使用数据库级 LIMIT/OFFSET 实现真正的分页，避免大表全量加载
  - 支持动态表数据查询，无需预定义模型类，返回标准化字典格式

- **JSON 多库支持**：新增对 orjson、ujson 等高性能 JSON 库的支持
  - 通过 `JsonBackendOptions(impl='orjson')` 指定 JSON 实现
  - 支持自定义 JSON 库扩展机制
  - 智能参数处理：不兼容参数自动舍弃，不影响功能
  - 性能提升：orjson 比标准库快 2-3 倍，ujson 快 1.5-2 倍
  - 用户指定库优先，不自动回退，确保用户明确知道使用的实现

- **完整的 SQLAlchemy 2.0 风格对象状态管理**
  - **Identity Map（对象唯一性）**：同一 Session 中相同主键的对象保证是同一个 Python 实例
  - **自动脏跟踪（Dirty Tracking）**：属性赋值（如 `user.name = "new"`）自动检测并在 `session.commit()` 时更新数据库
  - **查询实例自动注册**：通过 `session.execute(select(...))` 返回的实例自动关联到 Session，支持脏跟踪
  - **merge() 操作**：合并外部/detached 对象到 Session 中，智能处理更新现有对象或创建新对象
  - **增强的上下文管理器**：完整的事务支持，异常时自动回滚

- **核心 API 增强**
  - `Session._register_instance()` - 统一的实例注册机制
  - `Session._get_from_identity_map()` - 从 Identity Map 获取实例
  - `Session._mark_dirty()` - 标记实例为需要更新状态
  - `Session.merge()` - 合并 detached 对象到会话中
  - 增强的 `Result`/`ScalarResult` 类，支持 Session 引用传递和自动实例注册

### 变更

- **查询结果对象化**：`Result.all()`, `first()`, `one()` 现在默认返回模型实例
  - `session.execute(select(Model)).all()` 现在直接返回 `List[Model]`
  - 符合面向对象设计理念，提供更直观的API
  - 减少用户需要记住 `.scalars()` 调用的认知负担
  - 新增 `Result.one_or_none()` 方法，与 SQLAlchemy API 保持一致
  - 新增 `Result.rows()` 方法，为需要 Row 对象功能的用户提供迁移路径
  - 支持索引访问：`rows()[0][0]`，字典访问：`rows()[0]['field']`
  - 现有 `.scalars().all()` 调用继续工作但不再必需
  - 大多数代码无需修改（属性访问 `row.name` → `user.name` 仍然工作）
  - 为未来多表查询（`select(Student, Teacher)`）和 JOIN 支持预留了架构扩展空间

### 修复

- **查询结果类型误用问题**：修复了 `examples/backend_options_demo.py` 中错误使用 `row[0]` 访问模型实例的问题
  - 问题：用户期望 `session.execute(select(Model)).all()` 返回的 `row[0]` 是模型实例
  - 实际：`row[0]` 是第一个字段值（如 `id` 的值 1），不是模型实例
  - 修复：通过查询结果对象化，现在 `.all()` 直接返回模型实例列表，用户可以直接迭代使用
- **属性赋值更新问题**：修复了通过属性赋值（如 `bob.age = 99`）修改模型实例后，`session.flush()/commit()` 无法将更改写入数据库的问题
- **Identity Map 不一致问题**：修复了 `session.get()` 和 `session.execute(select(...))` 返回不同对象实例的问题
- **实例注册缺失**：修复了查询返回的实例未正确关联到 Session 的问题

### 改进

- **路径操作现代化**：所有内部路径操作统一使用 pathlib.Path
  - 提高代码一致性和可维护性
  - 支持更丰富的路径操作方法
  - 改进跨平台兼容性
  - 存储后端构造函数支持 Union[str, Path] 输入类型

- **模型基类增强**：在 `PureBaseModel` 和 `CRUDBaseModel` 中添加 `__setattr__` 脏跟踪机制
- **Session 实例管理**：完善了 `flush()` 方法中的实例注册逻辑，确保所有实例都有正确的 Session 引用

### 技术细节

- 实现了完整的 SQLAlchemy 2.0 风格对象生命周期管理（persistent/detached 状态）
- 通过 `__setattr__` 拦截 Column 属性修改，实现透明的脏跟踪
- 增强了 `ScalarResult._create_instance()` 方法，支持 Identity Map 一致性检查
- 修复了 `Session.flush()` 中新对象的注册逻辑，统一使用 `_register_instance()` 方法

## [0.2.0] - 2026-01-11

### 新增

- **泛型类型提示系统**
  - 完整的泛型支持，大幅提升 IDE 开发体验
  - `select(User)` 返回 `Select[User]`，不再是泛泛的 `Select` 类型
  - `session.execute(stmt)` 返回精确的 `Result[User]` 或 `CursorResult[User]` 类型
  - `result.scalars().all()` 返回 `List[User]`，不再是 `List[PureBaseModel]`
  - 所有语句构建器（Select、Insert、Update、Delete）支持泛型类型推断
  - 所有结果类（Result、ScalarResult、CursorResult）支持泛型类型
  - Session.execute 方法通过 @overload 提供精确类型重载
  - Query 构建器支持泛型（向后兼容但已弃用）
  - 新增 `pytuck/common/types.py` - 统一的 TypeVar 定义模块
  - 新增 `mypy.ini` - MyPy 静态类型检查配置
  - 新增 `tests/test_typing.py` - 类型检查验证测试
  - 新增 `examples/typing_demo.py` - 完整的类型提示演示
  - 100% 向后兼容，现有代码无需修改即可获得类型提示增强

- **强类型配置选项系统**
  - 新增 `pytuck/common/options.py` 模块，定义所有后端和连接器配置选项
  - 使用 dataclass 替代 **kwargs 参数，提升类型安全性和 IDE 支持
  - `JsonBackendOptions`、`CsvBackendOptions`、`SqliteBackendOptions` 等强类型配置类
  - `get_default_backend_options()` 和 `get_default_connector_options()` 辅助函数

- **统一数据库连接器架构**
  - 新增 `pytuck/connectors/` 模块，提供统一的数据库操作接口
  - `DatabaseConnector` 抽象基类，定义通用数据库操作规范
  - `SQLiteConnector` 实现，被 `SQLiteBackend` 和迁移工具共同使用
  - `get_connector()` 工厂函数，获取连接器实例
  - 文件命名采用 `_connector.py` 后缀，避免与第三方库名称冲突

- **数据迁移工具**
  - `migrate_engine()` - Pytuck 格式之间的数据迁移
  - `import_from_database()` - 从外部关系型数据库导入到 Pytuck 格式
  - `get_available_engines()` - 获取可用存储引擎

- **统一引擎版本管理**
  - 新增 `pytuck/backends/versions.py`，集中管理所有引擎格式版本
  - 使用整数格式（1, 2, 3...）统一版本号
  - 引擎版本独立于库版本，便于格式演进和向后兼容检测

- **表和列备注支持**
  - `Column` 类新增 `comment` 参数，支持字段备注
  - `Table` 类新增 `comment` 参数，支持表备注
  - 模型类支持 `__table_comment__` 类属性
  - 所有存储引擎均支持备注的序列化和反序列化

- **新示例文件**
  - `backend_options_demo.py` - 演示强类型后端配置选项
  - `migration_tools_demo.py` - 演示数据迁移和导入工具

### 变更

- **API 破坏性变更**：移除 **kwargs 参数支持
  ```python
  # ❌ 旧方式（不再支持）
  Storage('file.json', engine='json', indent=4)

  # ✅ 新方式（强类型）
  opts = JsonBackendOptions(indent=4)
  Storage('file.json', engine='json', backend_options=opts)
  ```

- **架构规范化**
  - 创建 `pytuck/common/` 目录，存放无内部依赖的模块
  - `pytuck/` 根目录只允许 `__init__.py` 一个 `.py` 文件
  - 强制使用强类型选项替代 **kwargs（除 ORM 动态字段外）

- **重构 SQLiteBackend**
  - 改为使用 `SQLiteConnector` 进行底层数据库操作
  - 修复连接参数处理，支持 None 值的可选参数
  - 减少代码重复，提高可维护性

- **重构存储引擎元数据结构**（破坏性变更）
  - **Binary 引擎**：分离 Schema 区和数据区，所有表的 schema 统一存储
  - **CSV 引擎**：不再为每个表创建单独的 `{table}_schema.json`，所有表 schema 统一存储在 `_metadata.json`
  - **Excel 引擎**：不再为每个表创建单独的 `{table}_schema` 工作表，所有表 schema 统一存储在 `_pytuck_tables` 工作表
  - 遵循"不为每个表创建单独 schema"的设计原则，提升性能和可维护性
  - 此变更使前三个引擎（Binary/CSV/Excel）数据格式不向后兼容

- **调整导出规范**
  - tools 模块不再从 `pytuck` 根包导出
  - 用户需从 `pytuck.tools` 手动导入迁移工具
  ```python
  # 新的导入方式
  from pytuck.tools import migrate_engine, import_from_database

  # 不再支持
  # from pytuck import migrate_engine
  ```

- **引擎格式版本升级**
  - Binary: v1 → v2（统一元数据结构 + 添加 comment 支持）
  - CSV: v1 → v2（统一元数据结构 + 添加 comment 支持）
  - Excel: v1 → v2（统一元数据结构 + 添加 comment 支持）
  - JSON: v1 → v2（添加 comment 支持）
  - SQLite: v1 → v2（添加 comment 支持）
  - XML: v1 → v2（添加 comment 支持）

### 文档更新

- 更新 `README.md`，所有存储引擎示例使用新的强类型选项 API
- 更新 `CLAUDE.md` 开发规范：
  - 新增目录结构规范（根目录限制、common 目录规范）
  - 新增 **kwargs 使用规范（禁止和允许场景）
  - 新增 dataclass 设计规范

### 架构改进

- 为未来扩展（如 DuckDB）奠定基础，添加新引擎只需：
  1. 创建 `pytuck/connectors/<db>_connector.py`
  2. 在 `CONNECTORS` 注册表中注册
  3. 创建对应的 backend
  4. 在 `pytuck/common/options.py` 中定义配置选项

### 测试

- 所有现有测试通过
- 验证所有存储引擎在新选项系统下正常工作
- 验证数据迁移工具的强类型选项功能

## [0.1.0] - 2026-01-10

### 新增

- **核心 ORM 系统**
  - `Column` 描述符，支持类型验证的字段定义
  - `PureBaseModel` - 纯数据模型基类（SQLAlchemy 2.0 风格）
  - `CRUDBaseModel` - Active Record 风格基类，内置 CRUD 方法
  - `declarative_base()` 工厂函数，用于创建模型基类

- **SQLAlchemy 2.0 风格 API**
  - `select()`、`insert()`、`update()`、`delete()` 语句构建器
  - `Session` 类，用于管理数据库操作
  - `Result`、`ScalarResult`、`CursorResult` 查询结果处理

- **Pythonic 查询语法**
  - 二元表达式：`Model.field >= value`、`Model.field != value`
  - `IN` 查询：`Model.field.in_([1, 2, 3])`
  - 链式条件：`.where(cond1, cond2)`
  - 简单相等：`.filter_by(name='value')`

- **多引擎存储**
  - `binary` - 默认引擎，紧凑二进制格式，零依赖
  - `json` - 人类可读的 JSON 格式
  - `csv` - 基于 ZIP 的 CSV 归档，Excel 兼容
  - `sqlite` - SQLite 数据库，支持 ACID
  - `excel` - Excel 工作簿格式（需要 openpyxl）
  - `xml` - 结构化 XML 格式（需要 lxml）

- **索引支持**
  - 基于哈希的索引，加速查找
  - 相等查询自动使用索引

- **事务支持**
  - 基本事务，支持提交/回滚
  - 上下文管理器支持

### 说明

- 这是首个发布版本
- 支持 Python 3.7+
- 核心功能零外部依赖
