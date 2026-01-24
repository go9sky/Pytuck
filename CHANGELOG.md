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
