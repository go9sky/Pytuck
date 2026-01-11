# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-01-11

### Added

- **Generic Type Hints System**
  - Complete generic support, dramatically enhancing IDE development experience
  - `select(User)` returns `Select[User]`, not generic `Select` type
  - `session.execute(stmt)` returns precise `Result[User]` or `CursorResult[User]` types
  - `result.scalars().all()` returns `List[User]`, not `List[PureBaseModel]`
  - All statement builders (Select, Insert, Update, Delete) support generic type inference
  - All result classes (Result, ScalarResult, CursorResult) support generic types
  - Session.execute method provides precise type overloads through @overload
  - Query builder supports generics (backward compatible but deprecated)
  - New `pytuck/common/types.py` - Unified TypeVar definition module
  - New `mypy.ini` - MyPy static type checking configuration
  - New `tests/test_typing.py` - Type checking validation tests
  - New `examples/typing_demo.py` - Complete type hints demonstration
  - 100% backward compatible, existing code gains type hint enhancement without modification

- **Strongly-Typed Configuration Options System**
  - New `pytuck/common/options.py` module defining all backend and connector configuration options
  - Use dataclass to replace **kwargs parameters, enhancing type safety and IDE support
  - Strongly-typed configuration classes: `JsonBackendOptions`, `CsvBackendOptions`, `SqliteBackendOptions`, etc.
  - Helper functions: `get_default_backend_options()` and `get_default_connector_options()`

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

- **Unified Engine Version Management**
  - New `pytuck/backends/versions.py` for centralized engine format version management
  - Uses integer format (1, 2, 3...) for unified version numbers
  - Engine versions are independent of library version for easier format evolution and backward compatibility detection

- **Table and Column Comment Support**
  - `Column` class now accepts `comment` parameter for field annotations
  - `Table` class now accepts `comment` parameter for table annotations
  - Model classes support `__table_comment__` class attribute
  - All storage engines support comment serialization and deserialization

- **New Example Files**
  - `backend_options_demo.py` - Demonstrates strongly-typed backend configuration options
  - `migration_tools_demo.py` - Demonstrates data migration and import tools

### Changed

- **Breaking API Changes**: Removed **kwargs parameter support
  ```python
  # ❌ Old way (no longer supported)
  Storage('file.json', engine='json', indent=4)

  # ✅ New way (strongly-typed)
  opts = JsonBackendOptions(indent=4)
  Storage('file.json', engine='json', backend_options=opts)
  ```

- **Architecture Standardization**
  - Created `pytuck/common/` directory for modules with no internal dependencies
  - `pytuck/` root directory only allows the `.py` file `__init__.py`
  - Enforced strongly-typed options to replace **kwargs (except ORM dynamic fields)

- **Refactored SQLiteBackend**
  - Now uses `SQLiteConnector` for underlying database operations
  - Fixed connection parameter handling, supporting None values for optional parameters
  - Reduced code duplication, improved maintainability

- **Refactored Storage Engine Metadata Structure** (Breaking Change)
  - **Binary Engine**: Separated Schema section and Data section, unified schema storage for all tables
  - **CSV Engine**: No longer create separate `{table}_schema.json` for each table, all table schemas unified in `_metadata.json`
  - **Excel Engine**: No longer create separate `{table}_schema` worksheets for each table, all table schemas unified in `_pytuck_tables` worksheet
  - Follows "no per-table schema" design principle for improved performance and maintainability
  - This change makes the first three engines (Binary/CSV/Excel) data format backward incompatible

- **Export Policy Adjustment**
  - tools module is no longer exported from `pytuck` root package
  - Users need to import migration tools from `pytuck.tools` manually
  ```python
  # New import method
  from pytuck.tools import migrate_engine, import_from_database

  # No longer supported
  # from pytuck import migrate_engine
  ```

- **Engine Format Version Upgrades**
  - Binary: v1 → v2 (unified metadata structure + added comment support)
  - CSV: v1 → v2 (unified metadata structure + added comment support)
  - Excel: v1 → v2 (unified metadata structure + added comment support)
  - JSON: v1 → v2 (added comment support)
  - SQLite: v1 → v2 (added comment support)
  - XML: v1 → v2 (added comment support)

### Documentation Updates

- Updated `README.EN.md`, all storage engine examples use new strongly-typed options API
- Updated `CLAUDE.md` development standards:
  - Added directory structure standards (root directory restrictions, common directory standards)
  - Added **kwargs usage standards (prohibited and allowed scenarios)
  - Added dataclass design standards

### Architecture Improvements

- Foundation laid for future extensions (e.g., DuckDB), adding new engines only requires:
  1. Create `pytuck/connectors/<db>_connector.py`
  2. Register in `CONNECTORS` registry
  3. Create corresponding backend
  4. Define configuration options in `pytuck/common/options.py`

### Testing

- All existing tests pass
- Verified all storage engines work properly under new options system
- Verified data migration tools' strongly-typed options functionality

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
