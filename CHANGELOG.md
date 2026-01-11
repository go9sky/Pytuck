# 更新日志

本文件记录项目的所有重要变更。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
遵循 [语义化版本](https://semver.org/lang/zh-CN/) 规范。

> [English Version](./CHANGELOG.EN.md)

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
