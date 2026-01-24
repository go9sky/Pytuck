# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

> [中文版](./CHANGELOG.md)

> For historical versions, see: [docs/changelog/](./docs/changelog/)

---

## [0.5.0] - 2026-01-24

### Improved

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
