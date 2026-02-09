# Pytuck 开发待办清单

本文件记录 Pytuck 项目的详细开发计划，供开发者参考。

> 版本发布记录请查看：[CHANGELOG.md](./CHANGELOG.md) | [历史版本](./docs/changelog/)

---

## 已完成

- [x] 核心 ORM 和内存存储
- [x] 插件化多引擎持久化（Binary、JSON、CSV、SQLite、Excel、XML）
- [x] SQLAlchemy 2.0 风格 API（select、insert、update、delete）
- [x] 基础事务支持
- [x] Identity Map（对象唯一性管理）
- [x] 自动脏跟踪（Dirty Tracking）
- [x] merge() 操作
- [x] 统一数据库连接器架构（pytuck/connectors/）
- [x] 数据迁移工具（migrate_engine、import_from_database）
- [x] 统一引擎版本管理（pytuck/backends/versions.py）
- [x] 表和列备注支持（comment 参数）
- [x] 泛型类型提示系统
- [x] 强类型配置选项系统（dataclass 替代 **kwargs）
- [x] Schema 同步与迁移功能（SyncOptions、SyncResult、三层 API）
- [x] Excel 行号映射功能（row_number_mapping）
- [x] SQLite 原生 SQL 模式优化
- [x] 异常系统重构（统一异常层次结构）
- [x] 后端自动注册机制（__init_subclass__）
- [x] 查询结果 API 简化（移除 scalars() 中间层）
- [x] 迁移工具延迟加载后端支持
- [x] 无主键模型支持（使用内部隐式 `_pytuck_rowid`）
- [x] 逻辑组合查询 OR/AND/NOT（`or_()`, `and_()`, `not_()`）
- [x] 外部文件加载功能 load_table（CSV/Excel → 模型对象列表）
- [x] ORM 事件钩子（Model 级 + Storage 级事件回调）
- [x] 关系预取 API（prefetch，批量加载关联数据解决 N+1 问题）
- [x] 查询索引优化（SortedIndex 范围查询加速 + order_by 索引排序 + Column 索引类型指定）
- [x] 批量操作优化（`bulk_insert` / `bulk_update`，批量主键分配 + 批量索引更新 + 批量事件）

---

## 近期计划

（暂无）

---

## 中期计划

- [ ] **to_dict() 增强**
  - 支持 `include` / `exclude` 字段筛选
  - 支持控制关联数据的序列化深度（`depth=1` 只展开一层 relationship）
  - 对接 JSON 序列化的常见需求

- [ ] **Column 级数据校验器（validator）**
  - 比 `strict` 模式更灵活：自定义校验函数、值范围约束
  - 预期 API：`Column(str, validator=lambda x: len(x) <= 100)`

- [ ] **模型继承支持**
  - 允许模型类继承以复用列定义（当前每个模型必须独立定义所有列）
  - 应用场景：基类定义 `created_at` / `updated_at` 等公共字段，子类继承复用

- [ ] **非二进制后端增量保存**
  - 当前 JSON/CSV/Excel/XML 每次保存完整重写文件
  - 目标：减少大文件场景的 I/O 开销

- [ ] **Binary 加密懒加载兼容**
  - 当前加密启用后懒加载被完全禁用（数据区整体加密，无法按偏移读取）
  - 改进为分块加密方案，使加密和懒加载可共存

- [ ] **临时文件安全改进**
  - 使用 `tempfile` 模块替代手动构造临时文件路径
  - 确保临时文件自动清理

---

## 计划增加的引擎

- [ ] **DuckDB** - 嵌入式分析型数据库
  - 列式存储，分析性能强
  - 嵌入式设计，安装方便
  - 适合需要复杂查询和分析能力的场景

- [ ] **LMDB** - 高性能嵌入式键值数据库
  - 读取极快，ACID 事务保证
  - 内存映射（mmap），零拷贝读取
  - 与 Pytuck 的键值存储模型天然匹配

---

## 远期 / 可选

- [ ] **复合主键支持**（视用户需求，当前显式禁止多主键）
- [ ] **查询结果缓存**（可选的缓存机制，减少重复查询开销）
- [ ] **Pytuck-CLI** - 命令行工具（数据库管理、导入导出、Schema 迁移）
- [ ] **FastAPI 集成示例/插件**
- [ ] **Pandas DataFrame 互操作**

---

## 技术债务

- [x] 完善单元测试覆盖率（特别是 WAL、lazy load、索引、关联关系场景）
- [x] 基准测试自动化（CI 集成，检测性能回归）
- [ ] API 参考文档生成
- [ ] 最佳实践指南（持久化策略选择、引擎对比建议）

---

## 生态系统

- [x] **Pytuck-view** - Web 数据浏览器（[GitHub](https://github.com/pytuck/pytuck-view) | [Gitee](https://gitee.com/pytuck/pytuck-view) | `pip install pytuck-view`）

---

## 不做的事（设计决策）

以下功能经过评估，不纳入 Pytuck 核心开发计划：

| 功能 | 理由 |
|------|------|
| **JOIN（多表关联查询）** | 已有 Relationship 实现关联查询（延迟加载+缓存），文档数据库不需要 SQL JOIN |
| **聚合函数（COUNT/SUM/AVG 等）** | Pytuck 定位是数据读写，不做计算引擎。用户可用 Python 原生 `len()` / `sum()` / `min()` / `max()` 处理查询结果 |
| **TinyDB / PyDbLite3 / diskcache 引擎** | 与 Pytuck 功能高度重叠或偏离核心定位 |
| **Django ORM 兼容层** | 维护成本高，需求不明确 |
| **SQLite 连接池** | Pytuck 定位嵌入式单进程，连接池意义不大 |
| **跨进程文件锁 / 并发访问** | 定位单进程嵌入式数据库，受限环境（如 Ren'Py）无法使用平台特定 API |

---

**注意**：此文档为开发者内部使用，功能优先级可能根据实际情况调整。
