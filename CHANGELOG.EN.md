# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

> [中文版](./CHANGELOG.md)

> For historical versions, see: [docs/changelog/](./docs/changelog/)

---

## [0.5.0] - 2026-01-25

### Added

- **Schema Sync & Migration**
  - Support automatic schema synchronization when loading existing database on program restart
  - Added `SyncOptions` configuration class to control sync behavior:
    - `sync_table_comment`: Whether to sync table comments (default: True)
    - `sync_column_comments`: Whether to sync column comments (default: True)
    - `add_new_columns`: Whether to add new columns (default: True)
    - `drop_missing_columns`: Whether to drop missing columns (default: False, dangerous)
  - Added `SyncResult` result class to record sync change details
  - `declarative_base()` now supports `sync_schema` and `sync_options` parameters for automatic sync at model definition
  - Three-layer API design for different use cases:
    - **Table layer**: `table.add_column()`, `table.drop_column()`, `table.update_comment()`, etc.
    - **Storage layer**: `storage.sync_table_schema()`, `storage.add_column()`, `storage.drop_table()`, `storage.rename_table()`, etc.
    - **Session layer**: `session.sync_schema()`, `session.add_column()`, `session.drop_column()`, etc.
  - Support for SQLite native SQL mode DDL operations (ALTER TABLE)
  - Support for pure table-name API (no model class required), convenient for Pytuck-view and other external tools
  - Added 26 test cases
  - Example:
    ```python
    from pytuck import Storage, declarative_base, SyncOptions, Column

    # Automatic sync mode
    db = Storage(file_path='existing.db')
    Base = declarative_base(db, sync_schema=True)

    class User(Base):
        __tablename__ = 'users'
        id = Column('id', int, primary_key=True)
        name = Column('name', str)
        age = Column('age', int, nullable=True)  # New column, auto synced

    # Manual sync mode
    from pytuck import Session
    session = Session(db)
    result = session.sync_schema(User)
    if result.has_changes:
        print(f"Added columns: {result.columns_added}")

    # Storage layer API (for Pytuck-view)
    db.add_column('users', Column('email', str, nullable=True))
    db.sync_table_schema('users', columns, comment='User table')
    ```

- **Excel Row Number Mapping**
  - Added `row_number_mapping` option to use Excel physical row numbers as primary key or map to a field
  - `row_number_mapping='as_pk'`: Use row number directly as primary key value
  - `row_number_mapping='field'`: Map row number to a specified field (default: `row_num`)
  - `row_number_field_name`: Customize the row number field name
  - `row_number_override`: Force row number mapping even for Pytuck-created files
  - `persist_row_number`: Persist row number field when saving
  - Support for loading external Excel files (without Pytuck metadata)
  - Added dedicated Excel row number mapping tests (11 test cases)
  - Example:
    ```python
    from pytuck import Storage
    from pytuck.common.options import ExcelBackendOptions

    # Use row number as primary key
    opts = ExcelBackendOptions(row_number_mapping='as_pk')
    db = Storage(file_path='external.xlsx', engine='excel', backend_options=opts)

    # Map row number to row_num field
    opts = ExcelBackendOptions(
        row_number_mapping='field',
        row_number_field_name='row_num',
        persist_row_number=True
    )
    db = Storage(file_path='external.xlsx', engine='excel', backend_options=opts)
    ```

### Improved

- **SQLite Native SQL Mode Optimization**
  - SQLite backend now defaults to native SQL mode (`use_native_sql=True`), executing SQL directly instead of full load/save
  - Completed `TYPE_TO_SQL` mapping for all 10 Pytuck types:
    - Basic types: `int`, `str`, `float`, `bool`, `bytes`
    - Extended types: `datetime`, `date`, `timedelta`, `list`, `dict`
  - Completed `SQL_TO_TYPE` reverse mapping for external SQLite database type inference (`DATETIME`, `DATE`, `TIMESTAMP`)
  - Added dedicated native SQL mode tests (11 test cases)
  - Fixed NULL value query issue (using `IS NULL` instead of `= NULL`)
  - Multi-column ORDER BY support (`order_by('col1').order_by('col2', desc=True)`)

- **Migration Tool Lazy Loading Backend Support**
  - Fixed `migrate_engine()` returning empty data when source backend uses lazy loading mode (e.g., SQLite native mode)
  - Added `supports_lazy_loading()` method to `StorageBackend` base class to check if backend only loads schema
  - Added `populate_tables_with_data()` method to `StorageBackend` base class for on-demand data loading
  - Added `save_full()` method to `StorageBackend` base class to ensure all data is saved during migration
  - Added dedicated lazy loading backend migration tests (5 test cases)

- **Backend Registry Optimization**: Automatic registration using `__init_subclass__`
  - Added `__init_subclass__` method to `StorageBackend` base class for automatic registration to `BackendRegistry` when subclassed
  - Removed hardcoded `BackendRegistry._discover_backends()` discovery logic
  - User-defined backends only need to inherit `StorageBackend` and define `ENGINE_NAME` for automatic registration
  - Dependency checks still performed early in `get_backend()` to ensure user data safety
  - Example:
    ```python
    from pytuck.backends import StorageBackend

    class MyCustomBackend(StorageBackend):
        ENGINE_NAME = 'custom'
        REQUIRED_DEPENDENCIES = ['my_lib']

        def save(self, tables): ...
        def load(self): ...
        def exists(self): ...
        def delete(self): ...

    # Automatically registered on class definition
    ```

### Refactored

- **Backend Module Structure Optimization**
  - Simplified `pytuck/backends/__init__.py` to import/export responsibilities only
  - Removed `_initialized` and `_discover_backends()` from `pytuck/backends/registry.py`
  - Built-in backends explicitly imported in `__init__.py` to trigger automatic registration

- **Exception System Refactoring**
  - Refactored `PytuckException` base class with common fields: `message`, `table_name`, `column_name`, `pk`, `details`
  - Added `to_dict()` method for logging and serialization
  - New exception types:
    - `TypeConversionError`: Type conversion failure (extends `ValidationError`)
    - `ConfigurationError`: Configuration errors (engine config, backend options, etc.)
    - `SchemaError`: Schema definition errors (e.g., missing primary key, extends `ConfigurationError`)
    - `QueryError`: Query building or execution errors
    - `ConnectionError`: Database connection not established or disconnected
    - `UnsupportedOperationError`: Unsupported operations
  - Unified replacement of all built-in exceptions with custom exception types:
    - `ValueError` → `TypeConversionError`/`ValidationError`/`ConfigurationError`/`QueryError`
    - `TypeError` → `ConfigurationError`/`QueryError`
    - `RuntimeError` → `ConnectionError`/`TransactionError`
    - `NotImplementedError` (runtime) → `UnsupportedOperationError`
  - All new exception types exported in `pytuck/__init__.py` for direct import
  - Exception hierarchy:
    ```
    PytuckException (base)
    ├── TableNotFoundError        # Table not found
    ├── RecordNotFoundError       # Record not found
    ├── DuplicateKeyError         # Duplicate primary key
    ├── ColumnNotFoundError       # Column not found
    ├── ValidationError           # Data validation error
    │   └── TypeConversionError   # Type conversion failure
    ├── ConfigurationError        # Configuration error
    │   └── SchemaError           # Schema definition error
    ├── QueryError                # Query error
    ├── TransactionError          # Transaction error
    ├── ConnectionError           # Connection error
    ├── SerializationError        # Serialization error
    ├── EncryptionError           # Encryption error
    ├── MigrationError            # Migration error
    ├── PytuckIndexError          # Index error
    └── UnsupportedOperationError # Unsupported operation
    ```

### Breaking Changes

- **Query Result API Simplification**
  - Removed `Result.scalars()` method, use `Result.all()`/`first()`/`one()`/`one_or_none()` directly
  - Removed `Result.rows()` method
  - Removed `Result.fetchall()` method
  - Removed `Row` class
  - `ScalarResult` changed to internal class `_ScalarResult`, no longer publicly exported
  - Migration Guide:
    ```python
    # Old usage
    users = result.scalars().all()
    user = result.scalars().first()

    # New usage
    users = result.all()
    user = result.first()
    ```
  - New API:
    - `Result.all()` → Returns list of model instances `List[T]`
    - `Result.first()` → Returns first model instance `Optional[T]`
    - `Result.one()` → Returns exactly one model instance `T` (raises if not exactly one)
    - `Result.one_or_none()` → Returns one model instance or None `Optional[T]` (at most one)
    - `Result.rowcount()` → Returns result count `int`
