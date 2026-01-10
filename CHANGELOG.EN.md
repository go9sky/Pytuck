# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-01-10

### Added

- **Unified Database Connector Architecture**
  - New `pytuck/connectors/` module providing unified database operation interface
  - `DatabaseConnector` abstract base class defining common database operation standards
  - `SQLiteConnector` implementation, shared by `SQLiteBackend` and migration tools
  - `get_connector()` factory function for obtaining connector instances
  - Connector files use `_connector.py` suffix to avoid conflicts with third-party library names

- **Data Migration Tools**
  - `migrate_engine()` - Data migration between Pytuck formats
  - `import_from_database()` - Import from external relational databases to Pytuck format
  - `get_available_engines()` - Get available storage engines

### Changed

- **Refactored SQLiteBackend**
  - Now uses `SQLiteConnector` for underlying database operations
  - Reduced code duplication, improved maintainability

- **Export Policy Adjustment**
  - tools module is no longer exported from `pytuck` root package
  - Users need to import migration tools from `pytuck.tools` manually
  ```python
  # New import method
  from pytuck.tools import migrate_engine, import_from_database

  # No longer supported
  # from pytuck import migrate_engine
  ```

### Architecture Improvements

- Foundation laid for future extensions (e.g., DuckDB), adding new engines only requires:
  1. Create `pytuck/connectors/<db>_connector.py`
  2. Register in `CONNECTORS` registry
  3. Create corresponding backend

## [0.1.0] - 2026-01-10

### Added

- **Core ORM System**
  - `Column` descriptor for defining model fields with type validation
  - `PureBaseModel` - Pure data model base class (SQLAlchemy 2.0 style)
  - `CRUDBaseModel` - Active Record style base class with built-in CRUD methods
  - `declarative_base()` factory function for creating model base classes

- **SQLAlchemy 2.0 Style API**
  - `select()`, `insert()`, `update()`, `delete()` statement builders
  - `Session` class for managing database operations
  - `Result`, `ScalarResult`, `CursorResult` for query result handling

- **Pythonic Query Syntax**
  - Binary expressions: `Model.field >= value`, `Model.field != value`
  - `IN` queries: `Model.field.in_([1, 2, 3])`
  - Chained conditions: `.where(cond1, cond2)`
  - Simple equality: `.filter_by(name='value')`

- **Multi-Engine Storage**
  - `binary` - Default engine, compact binary format, zero dependencies
  - `json` - Human-readable JSON format
  - `csv` - ZIP-based CSV archive, Excel compatible
  - `sqlite` - SQLite database with ACID support
  - `excel` - Excel workbook format (requires openpyxl)
  - `xml` - Structured XML format (requires lxml)

- **Index Support**
  - Hash-based indexes for accelerated lookups
  - Automatic index usage in equality queries

- **Transaction Support**
  - Basic transaction with commit/rollback
  - Context manager support

### Notes

- This is the initial release
- Python 3.7+ supported
- Zero required dependencies for core functionality
