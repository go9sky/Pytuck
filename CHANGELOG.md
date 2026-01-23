# 更新日志 / Changelog

本文件记录项目的所有重要变更。格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，遵循 [语义化版本](https://semver.org/lang/zh-CN/) 规范。

This file documents all notable changes. Format based on [Keep a Changelog](https://keepachangelog.com/en-US/1.0.0/), following [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

> 历史版本请查看 / For historical versions, see: [docs/changelog/](./docs/changelog/)

---

## [0.4.0] - 2026-01-23

### 新增 / Added

- **扩展字段类型支持 / Extended Field Type Support**：新增 5 种字段类型，总计支持 10 种类型
  - 新增类型 / New types：`datetime`, `date`, `timedelta`, `list`, `dict`
  - 原有类型 / Existing types：`int`, `str`, `float`, `bool`, `bytes`
  - 所有 6 种存储引擎均支持新类型的序列化/反序列化
  - All 6 storage engines support serialization/deserialization of new types
  - 使用示例 / Usage example：
    ```python
    from datetime import datetime, date, timedelta

    class Event(Base):
        __tablename__ = 'events'
        id = Column('id', int, primary_key=True)
        created_at = Column('created_at', datetime)
        event_date = Column('event_date', date)
        duration = Column('duration', timedelta)
        tags = Column('tags', list)
        metadata = Column('metadata', dict)
    ```

- **Binary 引擎 v4 格式 / Binary Engine v4 Format**：全新的存储格式，优化大数据集性能
  - **WAL（预写日志）/ Write-Ahead Log**：写入操作先追加到 WAL，实现 O(1) 写入延迟
  - **双 Header 机制 / Dual Header**：HeaderA/HeaderB 交替使用，支持原子切换和崩溃恢复
  - **Generation 计数 / Generation Counter**：递增计数器用于崩溃后选择有效 Header
  - **CRC32 校验 / CRC32 Checksum**：Header 和 WAL 条目完整性验证
  - **索引区压缩 / Index Compression**：使用 zlib 压缩索引区域，节省约 81% 空间
  - **批量 I/O / Batch I/O**：缓冲写入/读取，减少 I/O 操作次数
  - **编解码器缓存 / Codec Cache**：预缓存类型编解码器，避免重复查找

- **Binary 引擎加密支持 / Binary Engine Encryption**：三级加密/混淆功能，纯 Python 实现，零外部依赖
  - **低级（low）**：XOR 混淆，防随手查看，读取性能税约 100%
  - **中级（medium）**：LCG 流密码，防普通用户，读取性能税约 400%
  - **高级（high）**：ChaCha20 纯 Python 实现，密码学安全，读取性能税约 2000%
  - 加密范围：Data Region 和 Index Region（Schema Region 保持明文便于格式探测）
  - 新增 `EncryptionError` 异常类
  - 使用示例 / Usage example：
    ```python
    from pytuck import Storage
    from pytuck.common.options import BinaryBackendOptions

    # 创建加密数据库 / Create encrypted database
    opts = BinaryBackendOptions(encryption='high', password='mypassword')
    db = Storage('data.db', engine='binary', backend_options=opts)
    ```

### 改进 / Improved

- **TypeRegistry 统一类型编解码 / Unified Type Codec via TypeRegistry**
  - 新增 `get_type_name()` / `get_type_by_name()` 类型名称映射
  - 新增 `serialize_for_text()` / `deserialize_from_text()` 文本序列化接口
  - 所有文本后端（JSON/CSV/Excel/XML/SQLite）统一使用 TypeRegistry
  - 移除各后端重复的 `type_map` 定义，代码更简洁
  - All text backends now use TypeRegistry for consistent serialization

- **JSON 后端格式优化 / JSON Backend Format Optimization**
  - 移除冗余的 `_type`/`_value` 自描述格式
  - 直接存储序列化值，根据 schema 反序列化
  - JSON 文件更简洁，与其他后端格式一致
  - Removed redundant `_type`/`_value` wrapper, stores serialized values directly

- **主键查询优化 / Primary Key Query Optimization**（影响所有存储引擎）
  - 检测 `WHERE pk = value` 形式的查询，使用 O(1) 直接访问替代 O(n) 全表扫描
  - Update 和 Delete 语句均支持此优化
  - **性能提升 / Performance**：单条更新/删除从毫秒级降至微秒级（~1000x 提升）

- **Binary 引擎性能提升 / Binary Engine Performance**
  - 保存 10 万条记录：4.18s → 0.57s（7.3x 提速）
  - 加载 10 万条记录：2.91s → 0.85s（3.4x 提速）
  - 文件大小：151MB → 120MB（21% 压缩）

### 变更 / Changed

- **引擎格式版本升级 / Engine Format Version Upgrade**
  - Binary: v3 → v4（WAL + 双 Header + 索引压缩）

### 技术细节 / Technical Details

- 实现了完整的 WAL 写入流程：`_append_wal_entry()`, `_read_wal_entries()`, `_replay_wal()`
- Storage 层集成 WAL：写操作自动记录到 WAL，checkpoint 时批量持久化
- 新增 `TypeRegistry.get_codec_by_code()` 方法用于反向查找编解码器
- `Update._execute()` 和 `Delete._execute()` 添加主键检测逻辑
