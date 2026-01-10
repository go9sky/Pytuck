# Pytuck - Lightweight Python Document Database

[![PyPI version](https://badge.fury.io/py/pytuck.svg)](https://badge.fury.io/py/pytuck)
[![Python Versions](https://img.shields.io/pypi/pyversions/pytuck.svg)](https://pypi.org/project/pytuck/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Gitee](https://img.shields.io/badge/Gitee-go9sky%2Fpytuck-red)](https://gitee.com/go9sky/pytuck)

[中文文档](README.md)

A lightweight, pure Python document database with multi-engine support. No SQL required - manage your data through Python objects and methods.

## Repository Mirrors

- **GitHub**: https://github.com/go9sky/pytuck
- **Gitee (China Mirror)**: https://gitee.com/go9sky/pytuck

## Key Features

- **No SQL Required** - Work entirely with Python objects and methods
- **Multi-Engine Support** - Binary, JSON, CSV, SQLite, Excel, XML storage formats
- **Pluggable Architecture** - Zero dependencies by default, optional engines on demand
- **SQLAlchemy 2.0 Style API** - Modern query builders (`select()`, `insert()`, `update()`, `delete()`)
- **Pythonic Query Syntax** - Use native Python operators (`User.age >= 18`)
- **Index Optimization** - Hash indexes for accelerated queries
- **Type Safety** - Automatic type validation and conversion
- **Persistence** - Automatic or manual data persistence to disk

## Quick Start

### Installation

```bash
# Basic installation (binary engine only, zero dependencies)
pip install pytuck

# Install specific engines
pip install pytuck[excel]   # Excel engine (requires openpyxl)
pip install pytuck[xml]     # XML engine (requires lxml)

# Install all engines
pip install pytuck[all]

# Development environment
pip install pytuck[dev]
```

### Basic Usage

Pytuck offers two usage modes:

#### Mode 1: Pure Model (Default, Recommended)

Operate data through Session, following SQLAlchemy 2.0 style:

```python
from typing import Type
from pytuck import Storage, declarative_base, Session, Column
from pytuck import PureBaseModel, select, insert, update, delete

# Create database (default: binary engine)
db = Storage(file_path='mydb.db')
Base: Type[PureBaseModel] = declarative_base(db)

# Define model
class Student(Base):
    __tablename__ = 'students'

    id = Column('id', int, primary_key=True)
    name = Column('name', str, nullable=False, index=True)
    age = Column('age', int)
    email = Column('email', str, nullable=True)

# Create Session
session = Session(db)

# Insert records
stmt = insert(Student).values(name='Alice', age=20, email='alice@example.com')
result = session.execute(stmt)
session.commit()
print(f"Created student, ID: {result.inserted_primary_key}")

# Query records
stmt = select(Student).where(Student.id == 1)
result = session.execute(stmt)
alice = result.scalars().first()
print(f"Found: {alice.name}, {alice.age} years old")

# Conditional query (Pythonic syntax)
stmt = select(Student).where(Student.age >= 18).order_by('name')
result = session.execute(stmt)
adults = result.scalars().all()
for student in adults:
    print(f"  - {student.name}")

# Update records
stmt = update(Student).where(Student.id == 1).values(age=21)
session.execute(stmt)
session.commit()

# Delete records
stmt = delete(Student).where(Student.id == 1)
session.execute(stmt)
session.commit()

# Close
session.close()
db.close()
```

#### Mode 2: Active Record

Models with built-in CRUD methods for simpler operations:

```python
from typing import Type
from pytuck import Storage, declarative_base, Column
from pytuck import CRUDBaseModel

# Create database
db = Storage(file_path='mydb.db')
Base: Type[CRUDBaseModel] = declarative_base(db, crud=True)  # Note: crud=True

# Define model
class Student(Base):
    __tablename__ = 'students'

    id = Column('id', int, primary_key=True)
    name = Column('name', str, nullable=False)
    age = Column('age', int)

# Create record (auto-save)
alice = Student.create(name='Alice', age=20)
print(f"Created: {alice.name}, ID: {alice.id}")

# Or save manually
bob = Student(name='Bob', age=22)
bob.save()

# Query records
student = Student.get(1)  # Query by primary key
students = Student.filter(Student.age >= 18).all()  # Conditional query
students = Student.filter_by(name='Alice').all()  # Equality query
all_students = Student.all()  # Get all

# Update records
alice.age = 21
alice.save()

# Delete records
alice.delete()

# Close
db.close()
```

**How to Choose?**
- **Pure Model Mode**: Suited for larger projects, team development, clear data access layer separation
- **Active Record Mode**: Suited for smaller projects, rapid prototyping, simple CRUD operations

## Storage Engines

Pytuck supports multiple storage engines, each suited for different scenarios:

### Binary Engine (Default)

**Features**: Zero dependencies, compact, high performance

```python
db = Storage(file_path='data.db', engine='binary')
```

**Use Cases**:
- Production deployment
- Embedded applications
- Minimum footprint required

### JSON Engine

**Features**: Human-readable, debug-friendly, standard format

```python
db = Storage(file_path='data.json', engine='json', indent=2)
```

**Use Cases**:
- Development and debugging
- Configuration storage
- Data exchange

### CSV Engine

**Features**: Excel compatible, tabular format, data analysis friendly

```python
db = Storage(file_path='data_dir', engine='csv', encoding='utf-8')
```

**Use Cases**:
- Data analysis
- Excel import/export
- Tabular data

### SQLite Engine

**Features**: Mature, stable, ACID compliance, SQL support

```python
db = Storage(file_path='data.sqlite', engine='sqlite')
```

**Use Cases**:
- Need SQL queries
- Need transaction guarantees
- Large datasets

### Excel Engine (Optional)

**Requires**: `openpyxl>=3.0.0`

```python
db = Storage(file_path='data.xlsx', engine='excel')
```

**Use Cases**:
- Business reports
- Visualization needs
- Office automation

### XML Engine (Optional)

**Requires**: `lxml>=4.9.0`

```python
db = Storage(file_path='data.xml', engine='xml')
```

**Use Cases**:
- Enterprise integration
- Standardized exchange
- Configuration files

## Advanced Features

### Transaction Support

Pytuck supports memory-level transactions with automatic rollback on exceptions:

```python
# Session transaction (recommended)
with session.begin():
    session.add(User(name='Alice'))
    session.add(User(name='Bob'))
    # Auto-commit on success, auto-rollback on exception

# Storage-level transaction
with db.transaction():
    db.insert('users', {'name': 'Alice'})
    db.insert('users', {'name': 'Bob'})
    # Auto-rollback to pre-transaction state on exception
```

### Session Context Manager

Session supports context manager for automatic commit/rollback:

```python
with Session(db) as session:
    stmt = insert(User).values(name='Alice')
    session.execute(stmt)
    # Auto-commit on exit, auto-rollback on exception
```

### Auto-commit Mode

```python
session = Session(db, autocommit=True)
# Each operation auto-commits
session.add(User(name='Alice'))  # Auto-committed
```

### Object State Tracking

Session provides complete object state tracking:

```python
# Add single object
session.add(user)

# Batch add
session.add_all([user1, user2, user3])

# Flush to database (without committing transaction)
session.flush()

# Commit transaction
session.commit()

# Rollback transaction
session.rollback()
```

### Auto Flush

Enable `auto_flush` for automatic disk persistence on each write:

```python
db = Storage(file_path='data.db', auto_flush=True)

# Insert automatically writes to disk
stmt = insert(Student).values(name='Bob', age=21)
session.execute(stmt)
session.commit()
```

### Index Queries

Add indexes to fields to accelerate queries:

```python
class Student(Base):
    __tablename__ = 'students'
    name = Column('name', str, index=True)  # Create index

# Index query (automatically optimized)
stmt = select(Student).filter_by(name='Bob')
result = session.execute(stmt)
bob = result.scalars().first()
```

### Query Operators

Supported Pythonic query operators:

```python
# Equal
stmt = select(Student).where(Student.age == 20)

# Not equal
stmt = select(Student).where(Student.age != 20)

# Greater than / Greater than or equal
stmt = select(Student).where(Student.age > 18)
stmt = select(Student).where(Student.age >= 18)

# Less than / Less than or equal
stmt = select(Student).where(Student.age < 30)
stmt = select(Student).where(Student.age <= 30)

# IN query
stmt = select(Student).where(Student.age.in_([18, 19, 20]))

# Multiple conditions (AND)
stmt = select(Student).where(Student.age >= 18, Student.age < 30)

# Simple equality query (filter_by)
stmt = select(Student).filter_by(name='Alice', age=20)
```

### Sorting and Pagination

```python
# Sorting
stmt = select(Student).order_by('age')
stmt = select(Student).order_by('age', desc=True)

# Pagination
stmt = select(Student).limit(10)
stmt = select(Student).offset(10).limit(10)

# Count
stmt = select(Student).where(Student.age >= 18)
result = session.execute(stmt)
adults = result.scalars().all()
count = len(adults)
```

## Performance Benchmark

- Test environment: macOS, Python 3.13.11
- Test data: 100 000 records

| Engine | Insert | Full Scan | Indexed | Filtered | Update | Save | Load | File Size |
|--------|--------|-----------|---------|----------|--------|------|------|-----------|
| Binary | 490.16ms | 198.83ms | 520.1μs | 137.22ms | 2.05s | 360.15ms | 690.97ms | 11.04MB |
| JSON | 623.97ms | 200.42ms | 486.6μs | 84.47ms | 2.14s | 377.35ms | 534.53ms | 18.14MB |
| CSV | 618.45ms | 209.03ms | 458.6μs | 156.90ms | 2.23s | 186.68ms | 553.73ms | 732.0KB |
| SQLite | 707.76ms | 232.20ms | 576.1μs | 91.83ms | 2.21s | 145.68ms | 596.65ms | 6.97MB |
| Excel | 636.64ms | 213.70ms | 443.3μs | 84.96ms | 2.16s | 2.40s | 3.83s | 2.84MB |
| XML | 857.93ms | 229.73ms | 487.0μs | 84.69ms | 1.97s | 975.08ms | 1.27s | 34.54MB |

**Notes**:
- Indexed: 100 indexed field equality lookups
- Update: 100 record updates
- Save/Load: Persist to disk / Load from disk

**Conclusions**:
- **Binary** fastest for insert and full scan, suitable for read-heavy workloads
- **SQLite** fastest save (145ms), well-balanced overall performance
- **CSV** smallest file size (732KB, ZIP compressed), excellent save speed, suitable for data exchange
- **JSON** fast filtered queries, balances performance and readability, suitable for development/debugging
- **Excel** slower I/O (3.83s load), suitable for scenarios requiring visual editing
- **XML** largest file size (34.54MB), suitable for enterprise integration and standardized exchange

### Engine Feature Comparison

| Engine | Query Perf | I/O Perf | Storage Eff | Human Readable | Dependencies |
|--------|-----------|----------|-------------|----------------|--------------|
| Binary | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ❌ | None |
| JSON | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ✅ | None |
| CSV | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ✅ | None |
| SQLite | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ❌ | None |
| Excel | ⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐ | ✅ | openpyxl |
| XML | ⭐⭐⭐⭐ | ⭐⭐ | ⭐ | ✅ | lxml |

**Legend**:
- **Query Perf**: In-memory query speed (full scan, indexed lookup, filtered query)
- **I/O Perf**: Disk read/write speed (save and load)
- **Storage Eff**: File size efficiency (smaller is better)
- **Human Readable**: Whether file content can be directly read/edited
- **Dependencies**: Whether additional third-party libraries are required

## Installation Methods

### Install from PyPI

```bash
# Basic installation
pip install pytuck

# With specific extras
pip install pytuck[all]      # All optional engines
pip install pytuck[excel]    # Excel support only
pip install pytuck[xml]      # XML support only
pip install pytuck[dev]      # Development tools
```

### Install from Source

```bash
# Clone repository
git clone https://github.com/go9sky/pytuck.git
cd pytuck

# Editable install
pip install -e .

# With all extras
pip install -e .[all]

# Development mode
pip install -e .[dev]
```

### Build and Publish

```bash
# Install build tools
pip install build twine

# Build wheel and source distribution
python -m build

# Upload to PyPI
python -m twine upload dist/*

# Upload to Test PyPI
python -m twine upload --repository testpypi dist/*
```

## Architecture

```
┌─────────────────────────────────────┐
│       Application Layer             │
│   BaseModel, Column, Query API      │
└─────────────────────────────────────┘
               ↓
┌─────────────────────────────────────┐
│          ORM Layer (orm.py)         │
│   Model definitions, validation,    │
│   relationship mapping              │
└─────────────────────────────────────┘
               ↓
┌─────────────────────────────────────┐
│     Storage Layer (storage.py)      │
│   Table management, CRUD ops,       │
│   query execution                   │
└─────────────────────────────────────┘
               ↓
┌─────────────────────────────────────┐
│    Backend Layer (backends/)        │
│  BinaryBackend | JSONBackend | ...  │
└─────────────────────────────────────┘
               ↓
┌─────────────────────────────────────┐
│        Utility Layer (utils/)       │
│   Index, TypeCodec, Transaction     │
└─────────────────────────────────────┘
```

## Roadmap

### Completed
- Core ORM and in-memory storage
- Pluggable multi-engine persistence
- SQLAlchemy 2.0 style API
- Basic transaction support

## Current Limitations

Pytuck is a lightweight embedded database designed for simplicity. Here are the current limitations:

| Limitation | Description |
|------------|-------------|
| **No JOIN support** | Single table queries only, no multi-table joins |
| **No OR conditions** | Query conditions only support AND logic |
| **No aggregate functions** | No COUNT, SUM, AVG, MIN, MAX support |
| **No relationship loading** | No lazy loading or eager loading of related objects |
| **No migration tools** | Schema changes require manual handling |
| **Single writer** | No concurrent write support, suitable for single-process use |
| **Full rewrite on save** | Non-binary/SQLite backends rewrite entire file on each save |
| **No nested transactions** | Only single-level transactions supported |

## Roadmap / TODO

### Planned Features
- JOIN support (multi-table queries)
- OR condition support
- Aggregate functions (COUNT, SUM, AVG, MIN, MAX)
- Relationship lazy loading
- Schema migration tools
- Concurrent access support

### Planned Optimizations
- Incremental save for non-binary backends (currently full rewrite on each save)
- Use `tempfile` module for safer temporary file handling
- Streaming read/write for large datasets
- Connection pooling for SQLite backend
- Relationship and lazy loading enhancements

## Examples

See the `examples/` directory for more examples:

- `sqlalchemy20_api_demo.py` - Complete SQLAlchemy 2.0 style API example (recommended)
- `all_engines_test.py` - All storage engine functionality tests
- `transaction_demo.py` - Transaction management example

## Contributing

Issues and Pull Requests are welcome!

## License

MIT License - see [LICENSE](LICENSE) for details.

## Acknowledgments

Inspired by SQLAlchemy, Django ORM, and TinyDB.
