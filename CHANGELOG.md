# 更新日志

本文件记录项目的所有重要变更。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
遵循 [语义化版本](https://semver.org/lang/zh-CN/) 规范。

> [English Version](./CHANGELOG.EN.md)

## [0.2.0] - 2026-01-10

### 新增

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

### 变更

- **重构 SQLiteBackend**
  - 改为使用 `SQLiteConnector` 进行底层数据库操作
  - 减少代码重复，提高可维护性

- **调整导出规范**
  - tools 模块不再从 `pytuck` 根包导出
  - 用户需从 `pytuck.tools` 手动导入迁移工具
  ```python
  # 新的导入方式
  from pytuck.tools import migrate_engine, import_from_database

  # 不再支持
  # from pytuck import migrate_engine
  ```

### 架构改进

- 为未来扩展（如 DuckDB）奠定基础，添加新引擎只需：
  1. 创建 `pytuck/connectors/<db>_connector.py`
  2. 在 `CONNECTORS` 注册表中注册
  3. 创建对应的 backend

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
