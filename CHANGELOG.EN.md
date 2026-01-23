# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

> [中文版](./CHANGELOG.md)

> For historical versions, see: [docs/changelog/](./docs/changelog/)

---

## [0.4.0] - 2026-01-23

### Added

- **Extended Field Type Support**: Added 5 new field types, now supporting 10 types total
  - New types: `datetime`, `date`, `timedelta`, `list`, `dict`
  - Existing types: `int`, `str`, `float`, `bool`, `bytes`
  - All 6 storage engines support serialization/deserialization of new types
  - Usage example:
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

- **Binary Engine v4 Format**: New storage format optimized for large dataset performance
  - **WAL (Write-Ahead Log)**: Write operations append to WAL first, achieving O(1) write latency
  - **Dual Header Mechanism**: HeaderA/HeaderB alternating use, supporting atomic switching and crash recovery
  - **Generation Counter**: Incrementing counter for selecting valid Header after crash
  - **CRC32 Checksums**: Header and WAL entry integrity verification
  - **Index Region Compression**: Using zlib compression for index region, saving ~81% space
  - **Batch I/O**: Buffered writes/reads, reducing I/O operation counts
  - **Codec Caching**: Pre-cached type encoders/decoders, avoiding repeated lookups

- **Binary Engine Encryption Support**: Three-tier encryption/obfuscation, pure Python implementation, zero external dependencies
  - **Low Level (low)**: XOR obfuscation, prevents casual viewing, ~100% read performance tax
  - **Medium Level (medium)**: LCG stream cipher, prevents regular users, ~400% read performance tax
  - **High Level (high)**: ChaCha20 pure Python implementation, cryptographically secure, ~2000% read performance tax
  - Encryption scope: Data Region and Index Region (Schema Region remains plaintext for format probing)
  - Added `EncryptionError` exception class
  - Usage example:
    ```python
    from pytuck import Storage
    from pytuck.common.options import BinaryBackendOptions

    # Create encrypted database
    opts = BinaryBackendOptions(encryption='high', password='mypassword')
    db = Storage('data.db', engine='binary', backend_options=opts)
    ```

### Improved

- **Unified Type Codec via TypeRegistry**
  - Added `get_type_name()` / `get_type_by_name()` type name mappings
  - Added `serialize_for_text()` / `deserialize_from_text()` text serialization interfaces
  - All text backends (JSON/CSV/Excel/XML/SQLite) now use TypeRegistry for consistent serialization
  - Removed duplicate `type_map` definitions from each backend, cleaner code

- **JSON Backend Format Optimization**
  - Removed redundant `_type`/`_value` self-describing format
  - Stores serialized values directly, deserializes based on schema
  - JSON files are more concise, consistent with other backends

- **Primary Key Query Optimization** (affects ALL storage engines)
  - Detects `WHERE pk = value` style queries, using O(1) direct access instead of O(n) full table scan
  - Both Update and Delete statements support this optimization
  - **Performance Boost**: Single update/delete reduced from milliseconds to microseconds (~1000x improvement)

- **Binary Engine Performance Improvements**
  - Save 100k records: 4.18s → 0.57s (7.3x faster)
  - Load 100k records: 2.91s → 0.85s (3.4x faster)
  - File size: 151MB → 120MB (21% reduction)

### Changed

- **Engine Format Version Upgrade**
  - Binary: v3 → v4 (WAL + Dual Header + Index Compression)

### Technical Details

- Implemented complete WAL write workflow: `_append_wal_entry()`, `_read_wal_entries()`, `_replay_wal()`
- Storage layer WAL integration: write operations automatically logged to WAL, batch persistence during checkpoint
- Added `TypeRegistry.get_codec_by_code()` method for reverse codec lookup
- `Update._execute()` and `Delete._execute()` added primary key detection logic
