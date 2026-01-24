# 更新日志 / Changelog

本文件记录项目的所有重要变更。格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，遵循 [语义化版本](https://semver.org/lang/zh-CN/) 规范。

This file documents all notable changes. Format based on [Keep a Changelog](https://keepachangelog.com/en-US/1.0.0/), following [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

> 历史版本请查看 / For historical versions, see: [docs/changelog/](./docs/changelog/)

---

## [0.5.0] - 2026-01-24

### 改进 / Improved

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
