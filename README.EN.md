# Pytuck - Lightweight Python Document Database

[![Gitee](https://img.shields.io/badge/Gitee-go9sky%2Fpytuck-red)](https://gitee.com/go9sky/pytuck)
[![GitHub](https://img.shields.io/badge/GitHub-go9sky%2Fpytuck-blue)](https://github.com/go9sky/pytuck)

[![PyPI version](https://badge.fury.io/py/pytuck.svg)](https://badge.fury.io/py/pytuck)
[![Python Versions](https://img.shields.io/pypi/pyversions/pytuck.svg)](https://pypi.org/project/pytuck/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

[中文文档](README.md)

A lightweight, pure Python document database with multi-engine support. No SQL required - manage your data through Python objects and methods.

## Repository Mirrors

- **GitHub**: https://github.com/go9sky/pytuck
- **Gitee**: https://gitee.com/go9sky/pytuck

## Key Features

- **No SQL Required** - Work entirely with Python objects and methods
- **Multi-Engine Support** - Binary, JSON, CSV, SQLite, Excel, XML storage formats
- **Pluggable Architecture** - Zero dependencies by default, optional engines on demand
- **SQLAlchemy 2.0 Style API** - Modern query builders (`select()`, `insert()`, `update()`, `delete()`)
- **Generic Type Hints** - Complete generic support with precise IDE type inference (`List[User]` instead of `List[PureBaseModel]`)
- **Pythonic Query Syntax** - Use native Python operators (`User.age >= 18`)
- **Index Optimization** - Hash indexes for accelerated queries
- **Type Safety** - Automatic type validation and conversion (loose/strict modes)
- **Relationships** - Supports one-to-many and many-to-one with lazy loading + auto caching
- **Independent Data Models** - Accessible after session close, usable like Pydantic
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
from pytuck.common.options import JsonBackendOptions

# Configure JSON options
json_opts = JsonBackendOptions(indent=2, ensure_ascii=False)
db = Storage(file_path='data.json', engine='json', backend_options=json_opts)
```

**Use Cases**:
- Development and debugging
- Configuration storage
- Data exchange

### CSV Engine

**Features**: Excel compatible, tabular format, data analysis friendly

```python
from pytuck.common.options import CsvBackendOptions

# Configure CSV options
csv_opts = CsvBackendOptions(encoding='utf-8', delimiter=',')
db = Storage(file_path='data_dir', engine='csv', backend_options=csv_opts)
```

**Use Cases**:
- Data analysis
- Excel import/export
- Tabular data

### SQLite Engine

**Features**: Mature, stable, ACID compliance, SQL support

```python
from pytuck.common.options import SqliteBackendOptions

# Configure SQLite options (optional)
sqlite_opts = SqliteBackendOptions()  # Use default config
db = Storage(file_path='data.sqlite', engine='sqlite', backend_options=sqlite_opts)
```

**Use Cases**:
- Need SQL queries
- Need transaction guarantees
- Large datasets

### Excel Engine (Optional)

**Requires**: `openpyxl>=3.0.0`

```python
from pytuck.common.options import ExcelBackendOptions

# Configure Excel options (optional)
excel_opts = ExcelBackendOptions(sheet_name='Sheet1')  # Use default config
db = Storage(file_path='data.xlsx', engine='excel', backend_options=excel_opts)
```

**Use Cases**:
- Business reports
- Visualization needs
- Office automation

### XML Engine (Optional)

**Requires**: `lxml>=4.9.0`

```python
from pytuck.common.options import XmlBackendOptions

# Configure XML options
xml_opts = XmlBackendOptions(encoding='utf-8', pretty_print=True)
db = Storage(file_path='data.xml', engine='xml', backend_options=xml_opts)
```

**Use Cases**:
- Enterprise integration
- Standardized exchange
- Configuration files

## Advanced Features

### Generic Type Hints

Pytuck provides complete generic type support, enabling IDEs to precisely infer the specific types of query results and significantly enhancing the development experience:

#### IDE Type Inference Effects

```python
from typing import List, Optional
from pytuck import Storage, declarative_base, Session, Column
from pytuck import select, insert, update, delete

db = Storage('mydb.db')
Base = declarative_base(db)

class User(Base):
    __tablename__ = 'users'
    id = Column('id', int, primary_key=True)
    name = Column('name', str)
    age = Column('age', int)

session = Session(db)

# Statement builder type inference
stmt = select(User)  # IDE infers: Select[User] ✅
chained = stmt.where(User.age >= 18)  # IDE infers: Select[User] ✅

# Session execution type inference
result = session.execute(stmt)  # IDE infers: Result[User] ✅

# Result processing precise types
users = result.scalars().all()  # IDE infers: List[User] ✅ (no longer List[PureBaseModel])
user = result.scalars().first()  # IDE infers: Optional[User] ✅

# IDE knows specific attribute types
for user in users:
    user_name: str = user.name  # ✅ IDE knows this is str
    user_age: int = user.age    # ✅ IDE knows this is int
    # user.invalid_field        # ❌ IDE warns attribute doesn't exist
```

#### Type Safety Features

- **Precise Type Inference**: `select(User)` returns `Select[User]`, not generic `Select`
- **Smart Code Completion**: IDE accurately suggests model attributes and methods
- **Compile-time Error Detection**: MyPy can detect type errors at compile time
- **Method Chain Type Preservation**: All chained calls maintain specific generic types
- **100% Backward Compatibility**: Existing code works unchanged and automatically gains type hint enhancement

#### Comparison Effects

**Before:**
```python
users = result.scalars().all()  # IDE: List[PureBaseModel] 😞
user.name                       # IDE: doesn't know what attributes exist 😞
```

**Now:**
```python
users = result.scalars().all()  # IDE: List[User] ✅
user.name                       # IDE: knows this is str type ✅
user.age                        # IDE: knows this is int type ✅
```

### Data Persistence

Pytuck provides flexible data persistence mechanisms.

#### Pure Model Mode (Session)

```python
db = Storage(file_path='data.db')  # auto_flush=False (default)

# Data changes only in memory
session.execute(insert(User).values(name='Alice'))
session.commit()  # Commits to Storage memory

# Manually write to disk
db.flush()  # Method 1: Explicit flush
# or
db.close()  # Method 2: Auto-flush on close
```

Enable auto persistence:

```python
db = Storage(file_path='data.db', auto_flush=True)

# Each commit automatically writes to disk
session.execute(insert(User).values(name='Alice'))
session.commit()  # Automatically writes to disk, no manual flush needed
```

#### Active Record Mode (CRUDBaseModel)

CRUDBaseModel has no Session, operates directly on Storage:

```python
db = Storage(file_path='data.db')  # auto_flush=False (default)
Base = declarative_base(db, crud=True)

class User(Base):
    __tablename__ = 'users'
    id = Column('id', int, primary_key=True)
    name = Column('name', str)

# create/save/delete only modify memory
user = User.create(name='Alice')
user.name = 'Bob'
user.save()

# Manually write to disk
db.flush()  # Method 1: Explicit flush
# or
db.close()  # Method 2: Auto-flush on close
```

Enable auto persistence:

```python
db = Storage(file_path='data.db', auto_flush=True)
Base = declarative_base(db, crud=True)

# Each create/save/delete automatically writes to disk
user = User.create(name='Alice')  # Automatically writes to disk
user.name = 'Bob'
user.save()  # Automatically writes to disk
```

#### Persistence Method Summary

| Method | Mode | Description |
|--------|------|-------------|
| `session.commit()` | Pure Model | Commits transaction to Storage memory; if `auto_flush=True`, also writes to disk |
| `Model.create/save/delete()` | Active Record | Modifies Storage memory; if `auto_flush=True`, also writes to disk |
| `storage.flush()` | Both | Forces in-memory data to be written to disk |
| `storage.close()` | Both | Closes database, automatically calls `flush()` |

**Recommendations**:
- Use `auto_flush=True` in production for data safety
- Use default mode for batch operations, call `flush()` at the end for better performance

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

## Data Model Features

Pytuck's data models have unique characteristics that make them behave like both ORM and pure data containers.

### Independent Data Objects

Pytuck model instances are completely independent Python objects that are immediately materialized to memory after query:

- ✅ **Accessible After Session Close**: No DetachedInstanceError
- ✅ **Operable After Storage Close**: Loaded objects are completely independent
- ✅ **No Lazy Loading**: All direct attributes are loaded immediately
- ✅ **Serializable**: Supports JSON, Pickle, and other serialization formats
- ✅ **Usable as Data Containers**: Use like Pydantic models

```python
from pytuck import Storage, declarative_base, Session, Column, select

db = Storage(file_path='data.db')
Base = declarative_base(db)

class User(Base):
    __tablename__ = 'users'
    id = Column('id', int, primary_key=True)
    name = Column('name', str)

session = Session(db)
stmt = select(User).where(User.id == 1)
user = session.execute(stmt).scalars().first()

# Close session and storage
session.close()
db.close()

# Still accessible!
print(user.name)  # ✅ Works
print(user.to_dict())  # ✅ Works
```

**Comparison with SQLAlchemy**:

| Feature | Pytuck | SQLAlchemy |
|---------|--------|------------|
| Access after Session close | ✅ Supported | ❌ DetachedInstanceError |
| Lazy loading relationships | ✅ Supported (with cache) | ✅ Supported |
| Model as pure data container | ✅ Yes | ❌ No (bound to session) |

### Relationships

Pytuck supports one-to-many and many-to-one relationships with lazy loading and caching:

```python
from pytuck.core.orm import Relationship

# Define relationships
class User(Base):
    __tablename__ = 'users'
    id = Column('id', int, primary_key=True)
    name = Column('name', str)
    # One-to-many: one user has many orders
    orders = Relationship('Order', foreign_key='user_id')

class Order(Base):
    __tablename__ = 'orders'
    id = Column('id', int, primary_key=True)
    user_id = Column('user_id', int)
    amount = Column('amount', float)
    # Many-to-one: one order belongs to one user
    user = Relationship(User, foreign_key='user_id')

# Use relationships
user = User.get(1)
orders = user.orders  # Lazy loaded on first access
for order in orders:
    print(f"Order: {order.amount}")

# Reverse access
order = Order.get(1)
user = order.user  # Many-to-one query
print(f"User: {user.name}")
```

**Relationship Features**:

- ✅ **Lazy Loading**: Queries database only on first access
- ✅ **Auto Caching**: Caches results to avoid repeated queries
- ✅ **Bidirectional**: Supports back_populates parameter
- ✅ **After Storage Close**: Already loaded relationships remain accessible (uses cache)
- ⚠️ **Requires Eager Loading**: Access once before storage close to trigger loading

```python
# Eager loading strategy
user = User.get(1)
orders = user.orders  # Access before storage close to load and cache

db.close()

# Still accessible after close (uses cache)
for order in orders:
    print(order.amount)  # ✅ Works
```

### Type Validation and Conversion

Pytuck provides zero-dependency automatic type validation and conversion:

```python
class User(Base):
    __tablename__ = 'users'
    id = Column('id', int, primary_key=True)
    age = Column('age', int)  # Declared as int

# Loose mode (default): auto conversion
user = User(age='25')  # ✅ Automatically converts '25' → 25

# Strict mode: no conversion, raises error on type mismatch
class StrictUser(Base):
    __tablename__ = 'strict_users'
    id = Column('id', int, primary_key=True)
    age = Column('age', int, strict=True)  # Strict mode

user = StrictUser(age='25')  # ❌ ValidationError
```

**Type Conversion Rules (Loose Mode)**:

| Python Type | Conversion Rule | Example |
|------------|----------------|---------|
| int | int(value) | '123' → 123 |
| float | float(value) | '3.14' → 3.14 |
| str | str(value) | 123 → '123' |
| bool | Special rules* | '1', 'true', 1 → True |
| bytes | encode() if str | 'hello' → b'hello' |
| None | Allowed if nullable=True | None → None |

*bool conversion rules:
- True: `True`, `1`, `'1'`, `'true'`, `'True'`, `'yes'`, `'Yes'`
- False: `False`, `0`, `'0'`, `'false'`, `'False'`, `'no'`, `'No'`, `''`

**Use Cases**:

```python
# Web API development: return directly after query, no connection concerns
@app.get("/users/{id}")
def get_user(id: int):
    session = Session(db)
    stmt = select(User).where(User.id == id)
    user = session.execute(stmt).scalars().first()
    session.close()

    # Return model, no concern about closed session
    return user.to_dict()

# Data transfer: model objects can be passed freely between functions
def process_users(users: List[User]) -> List[dict]:
    return [u.to_dict() for u in users]

# JSON serialization
import json
user_json = json.dumps(user.to_dict())
```

## Performance Benchmark

Here are benchmark results from different environments.

### Test 1: Windows 11, Python 3.12.10

Test data: 10,000 records

| Engine | Insert | Full Scan | Indexed | Filtered | Update | Save | Load | File Size |
|--------|--------|-----------|---------|----------|--------|------|------|-----------|
| Binary | 85.38ms | 42.26ms | 1.10ms | 21.12ms | 709.34ms | 94.75ms | 110.68ms | 1.09MB |
| JSON | 84.33ms | 58.12ms | 1.15ms | 21.77ms | 702.70ms | 110.68ms | 50.76ms | 1.86MB |
| CSV | 83.61ms | 52.88ms | 1.12ms | 20.94ms | 697.88ms | 47.22ms | 54.73ms | 73.8KB |
| SQLite | 95.75ms | 36.41ms | 1.15ms | 27.43ms | 699.34ms | 43.35ms | 41.86ms | 700.0KB |
| Excel | 101.41ms | 47.06ms | 1.23ms | 21.25ms | 679.85ms | 551.74ms | 738.39ms | 294.2KB |
| XML | 84.30ms | 95.31ms | 1.10ms | 20.99ms | 686.28ms | 245.91ms | 194.11ms | 3.43MB |

### Test 2: macOS, Python 3.13.11

Test data: 100,000 records

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

## Data Migration

Migrate data between different engines:

```python
from pytuck.tools.migrate import migrate_engine
from pytuck.common.options import JsonBackendOptions

# Configure target engine options
json_opts = JsonBackendOptions(indent=2, ensure_ascii=False)

# Migrate from binary to JSON
migrate_engine(
    source_path='data.db',
    source_engine='binary',
    target_path='data.json',
    target_engine='json',
    target_options=json_opts  # Use strongly-typed options
)
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
│      Common Layer (common/)         │
│   Exceptions, Utils, Options        │
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

### Completed

- [x] Unified database connector architecture (`pytuck/connectors/` module)
- [x] Data migration tools (`migrate_engine()`, `import_from_database()`)
- [x] Import from external relational databases feature
- [x] Unified engine version management (`pytuck/backends/versions.py`)
- [x] Table and column comment support (`comment` parameter)

### Planned Features

> 📋 For detailed development plans, please refer to [TODO.md](./TODO.md)

- [ ] **Web UI Interface Support** - Provide API support for independent Web UI library
- [ ] **ORM Event Hooks System** - Complete event system based on SQLAlchemy event pattern
- [ ] **JOIN Support** - Multi-table relational queries
- [ ] **OR Condition Support** - Complex logical query conditions
- [ ] **Aggregate Functions** - COUNT, SUM, AVG, MIN, MAX, etc.
- [ ] **Relationship Lazy Loading** - Optimize associated data loading performance
- [ ] **Schema Migration Tools** - Database structure version management
- [ ] **Concurrent Access Support** - Multi-process/thread-safe access

### Planned Engines

- [ ] DuckDB - Analytical database engine
- [ ] TinyDB - Pure Python document database
- [ ] PyDbLite3 - Pure Python in-memory database
- [ ] diskcache - Disk-based cache engine

### Planned Optimizations

- [ ] Incremental save for non-binary backends (currently full rewrite on each save)
- [ ] Use `tempfile` module for safer temporary file handling
- [ ] Streaming read/write for large datasets
- [ ] Connection pooling for SQLite backend
- [ ] Relationship and lazy loading enhancements

## Examples

See the `examples/` directory for more examples:

- `sqlalchemy20_api_demo.py` - Complete SQLAlchemy 2.0 style API example (recommended)
- `all_engines_test.py` - All storage engine functionality tests
- `transaction_demo.py` - Transaction management example
- `type_validation_demo.py` - Type validation and conversion example
- `data_model_demo.py` - Data model independence features example
- `backend_options_demo.py` - Backend configuration options demo (new)
- `migration_tools_demo.py` - Data migration tools demo (new)

## Contributing

Issues and Pull Requests are welcome!

## License

MIT License - see [LICENSE](LICENSE) for details.

## Acknowledgments

Inspired by SQLAlchemy, Django ORM, and TinyDB.
