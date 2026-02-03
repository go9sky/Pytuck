# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

> [中文版](./CHANGELOG.md)

> For historical versions, see: [docs/changelog/](./docs/changelog/)

---

## [0.6.3] - 2026-02-03

### Added

- **CSV Backend ZIP Password Protection**
  - Added `CsvBackendOptions.password` option to create encrypted ZIP files
  - Uses ZipCrypto encryption (pure Python, no external dependencies)
  - Generated encrypted ZIP is compatible with WinRAR, 7-Zip and other tools
  - Example:
    ```python
    from pytuck.common.options import CsvBackendOptions

    # Create encrypted CSV storage
    opts = CsvBackendOptions(password="my_password")
    db = Storage(file_path="data.zip", engine="csv", backend_options=opts)
    ```
  - **Security Note**: ZipCrypto is a weak encryption, suitable for casual protection only. For high security, use Binary backend encryption (ChaCha20)

- **Query Condition Column Name Mapping**
  - Support using model field names in query conditions with automatic conversion to database column names
  - When using `Column(type, name='db_column')`, query conditions are automatically mapped

### Fixed

- **Database Column Name Mapping Issue**
  - Fixed column name mapping and matching in query conditions

- **Primary Key-less Model get() Method**
  - Fixed `session.get()` handling for primary key-less models
  - Improved data mapping logic

### Tests

- Added CSV backend ZIP encryption tests (12 test cases)
- Added configuration error, multi-thread safety, and advanced query tests
- Added engine metadata specification and error recovery tests
