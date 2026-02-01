# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

> [中文版](./CHANGELOG.md)

> For historical versions, see: [docs/changelog/](./docs/changelog/)

---

## [0.6.2] - 2026-02-01

### Added

- **Storage.count_rows() Method**
  - Added public interface to get table record count
  - Supports both Native SQL mode and memory mode
  - Raises `TableNotFoundError` when table doesn't exist
  - Example:
    ```python
    count = storage.count_rows('users')
    print(f"users table has {count} records")
    ```

- **Primary Key Type Auto-Conversion**
  - Added `_normalize_pk` method in `Table` class
  - `insert`, `update`, `delete`, `get` methods now auto-convert primary key types
  - Resolves mismatch between string primary key `'1'` and integer primary key `1`

### Fixed

- **Primary Key Duplicate Detection Failure**
  - Fixed duplicate detection failure in memory mode when primary key types don't match
  - Table defined with `int` primary key, passing `'1'` (string) now correctly detects duplicate with `1` (integer)

- **Unified Primary Key Duplicate Exception**
  - Native SQL mode now raises `DuplicateKeyError` instead of `sqlite3.IntegrityError` for duplicate primary keys

- **insert Return Value Fix**
  - Returns user-provided value when user specifies primary key, instead of SQLite's `lastrowid`
  - Fixed delete failure immediately after insert

- **delete for Primary Key-less Tables**
  - Unified delete operation for primary key-less tables to use `rowid`

- **External File Loading Column Name Mapping**
  - Fixed column name mapping issue when using `Column(type, name='xxx')` with `load_table`

- **mypy Type Check Error**
  - Fixed type check error for datetime/date type conversion in `orm.py`

### Documentation

- Updated documentation for column operation methods
- Updated GitHub and Gitee links in README

### Tests

- Added `test_insert_issues.py`: Primary key duplicate, return value, insert+delete integration tests
- Added `test_count_rows.py`: count_rows method tests
- Added `TestPkTypeMismatch`: Primary key type mismatch scenario tests
- Added Column.name mapping tests for Schema operations

---

## [0.6.1] - 2026-01-29

### Fixed

- **Column.name Mapping Issue**
  - Fixed query results returning None for all attributes when using `Column(type, name='xxx')` syntax
  - Fixed column name mapping in `session.query().all()` and `session.execute(select(...))`
  - Related files: `pytuck/query/result.py`, `pytuck/query/builder.py`

---

## [0.6.0] - 2026-01-28

### Added

- **Primary Key-less Model Support**
  - Support defining models without a primary key, using internal implicit `_pytuck_rowid` as row identifier
  - Full support in Storage/Table layer for data storage, serialization, and querying of primary key-less tables
  - Suitable for log tables, event tables, and other scenarios that don't require unique identifiers
  - Example:
    ```python
    class LogEntry(Base):
        __tablename__ = 'logs'
        # No column with primary_key=True
        timestamp = Column(datetime)
        message = Column(str)
        level = Column(str)

    # Normal usage with insert/select/update/delete
    session.execute(insert(LogEntry).values(
        timestamp=datetime.now(),
        message='User logged in',
        level='INFO'
    ))
    ```

- **Logical Query Operators (OR/AND/NOT)**
  - Added `or_()`, `and_()`, `not_()` logical operators
  - Support for complex condition combinations and nested queries
  - Example:
    ```python
    from pytuck import or_, and_, not_

    # OR query
    stmt = select(User).where(or_(User.age >= 65, User.vip == True))

    # AND query (explicit)
    stmt = select(User).where(and_(User.age >= 18, User.status == 'active'))

    # NOT query
    stmt = select(User).where(not_(User.deleted == True))

    # Combined query
    stmt = select(User).where(
        or_(
            and_(User.age >= 18, User.age < 30),
            User.vip == True
        )
    )
    ```

- **External File Loading (load_table)**
  - Added `load_table()` function to load CSV/Excel files as model object lists
  - User defines model (table name, column types) first, then loads external file
  - Type coercion: convert if possible, raise error if not
  - Support for CSV (custom encoding, delimiter) and Excel (specify worksheet)
  - Example:
    ```python
    from pytuck.tools import load_table

    class User(Base):
        __tablename__ = 'users'
        id = Column(int, primary_key=True)
        name = Column(str)
        age = Column(int)

    # Load CSV file
    users = load_table(User, 'users.csv')

    # Load Excel file
    users = load_table(User, 'data.xlsx', sheet_name='Sheet1')

    # Custom delimiter
    users = load_table(User, 'data.csv', delimiter=';')

    # Iterate data
    for user in users:
        print(user.id, user.name, user.age)
    ```

### Fixed

- **Security Fix: SQL Injection**
  - Fixed SQL injection vulnerability in SQLite backend using parameterized queries

### Refactored

- **Exception Rename**
  - Renamed `ConnectionError` to `DatabaseConnectionError` to avoid conflict with Python built-in exception

- **Removed Excel Row Number Mapping**
  - Removed `row_number_mapping` options to simplify Excel backend implementation

- **Other Improvements**
  - Refactored model base class for more reliable dirty data tracking
  - Improved security and error handling in storage module
  - Fixed closure binding issue in query statements
