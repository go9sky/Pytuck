# Pytuck - Lightweight Python Document Database

[![Gitee](https://img.shields.io/badge/Gitee-Pytuck%2FPytuck-red)](https://gitee.com/Pytuck/Pytuck)
[![GitHub](https://img.shields.io/badge/GitHub-Pytuck%2FPytuck-blue)](https://github.com/Pytuck/Pytuck)

[![PyPI version](https://badge.fury.io/py/pytuck.svg)](https://badge.fury.io/py/pytuck)
[![Python Versions](https://img.shields.io/pypi/pyversions/pytuck.svg)](https://pypi.org/project/pytuck/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

[中文](README.md) | English

A lightweight, pure Python document database with multi-engine support. No SQL required - manage your data through Python objects and methods.

> **Design Philosophy**: Provide a zero-dependency relational database solution for restricted Python environments like Ren'Py, enabling SQLAlchemy-style Pythonic data operations in any limited environment.

## Repository Mirrors

- **GitHub**: https://github.com/Pytuck/Pytuck
- **Gitee**: https://gitee.com/Pytuck/Pytuck

## Key Features

- **No SQL Required** - Work entirely with Python objects and methods
- **Multi-Engine Support** - Binary, JSON, CSV, SQLite, Excel, XML storage formats
- **Pluggable Architecture** - Zero dependencies by default, optional engines on demand
- **SQLAlchemy 2.0 Style API** - Modern query builders (`select()`, `insert()`, `update()`, `delete()`)
- **Generic Type Hints** - Complete generic support with precise IDE type inference (`List[User]` instead of `List[PureBaseModel]`)
- **Pythonic Query Syntax** - Use native Python operators (`User.age >= 18`)
- **Index Optimization** - Hash indexes for accelerated queries
- **Type Safety** - Automatic type validation and conversion (loose/strict modes), supports 10 field types
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

    id = Column(int, primary_key=True)
    name = Column(str, nullable=False, index=True)
    age = Column(int)
    email = Column(str, nullable=True)

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
alice = result.first()
print(f"Found: {alice.name}, {alice.age} years old")

# Conditional query (Pythonic syntax)
stmt = select(Student).where(Student.age >= 18).order_by('name')
result = session.execute(stmt)
adults = result.all()
for student in adults:
    print(f"  - {student.name}")

# Identity Map example (0.3.0 NEW, object uniqueness guarantee)
student1 = session.get(Student, 1)  # Load from database
stmt = select(Student).where(Student.id == 1)
student2 = session.execute(stmt).scalars().first()  # Get through query
print(f"Same object? {student1 is student2}")  # True, same instance

# merge() operation example (0.3.0 NEW, merge external data)
external_student = Student(id=1, name="Alice Updated", age=22)  # External data
merged = session.merge(external_student)  # Intelligently merge into Session
session.commit()  # Update takes effect

# Update records
# Method 1: Use update statement (bulk update)
stmt = update(Student).where(Student.id == 1).values(age=21)
session.execute(stmt)
session.commit()

# Method 2: Attribute assignment update (0.3.0 NEW, more intuitive)
stmt = select(Student).where(Student.id == 1)
result = session.execute(stmt)
alice = result.first()
alice.age = 21  # Attribute assignment auto-detected and updates database
session.commit()  # Automatically writes changes to database

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

    id = Column(int, primary_key=True)
    name = Column(str, nullable=False)
    age = Column(int)

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
alice.age = 21  # Active Record mode already supports attribute assignment updates
alice.save()    # Explicitly save to database

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

**Features**: Zero dependencies, compact, high performance, encryption support

```python
from pytuck.common.options import BinaryBackendOptions

# Basic usage
db = Storage(file_path='data.db', engine='binary')

# Enable encryption (three levels: low/medium/high)
opts = BinaryBackendOptions(encryption='high', password='mypassword')
db = Storage(file_path='secure.db', engine='binary', backend_options=opts)

# Open encrypted database (auto-detects encryption level)
opts = BinaryBackendOptions(password='mypassword')
db = Storage(file_path='secure.db', engine='binary', backend_options=opts)
```

**Encryption Levels**:

| Level | Algorithm | Security | Use Case |
|-------|-----------|----------|----------|
| `low` | XOR obfuscation | Prevents casual viewing | Prevent accidental file opening |
| `medium` | LCG stream cipher | Prevents regular users | General protection needs |
| `high` | ChaCha20 | Cryptographically secure | Sensitive data protection |

**Encryption Performance Benchmark** (1000 records, ~100 bytes each):

| Level | Write Time | Read Time | File Size | Read Overhead |
|-------|------------|-----------|-----------|---------------|
| None | 41ms | 17ms | 183KB | (baseline) |
| low | 33ms | 33ms | 183KB | +100% |
| medium | 82ms | 86ms | 183KB | +418% |
| high | 342ms | 335ms | 183KB | +1928% |

> **Note**: Encryption uses pure Python implementation to maintain zero dependencies. For better performance, consider using `low` or `medium` levels.
> Run `examples/benchmark_encryption.py` to test performance in your environment.

**Use Cases**:
- Production deployment
- Embedded applications
- Sensitive data protection
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
excel_opts = ExcelBackendOptions(read_only=False)  # Use default config
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
    id = Column(int, primary_key=True)
    name = Column(str)
    age = Column(int)

session = Session(db)

# Statement builder type inference
stmt = select(User)  # IDE infers: Select[User] ✅
chained = stmt.where(User.age >= 18)  # IDE infers: Select[User] ✅

# Session execution type inference
result = session.execute(stmt)  # IDE infers: Result[User] ✅

# Result processing precise types
users = result.all()  # Returns a list of model instances List[T]
user = result.first()  # Returns the first model instance Optional[T]

Notes:
- Result.all() → Returns a list of model instances List[T]
- Result.first() → Returns the first model instance Optional[T]
- Result.one() → Returns the unique model instance T (must be exactly one)
- Result.one_or_none() → Returns the unique model instance or None Optional[T] (at most one)
- Result.rowcount() → Returns the number of results int

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
users = result.all()  # IDE: List[PureBaseModel] 😞
user.name                       # IDE: doesn't know what attributes exist 😞
```

**Now:**
```python
users = result.all()  # IDE: List[User] ✅
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
    id = Column(int, primary_key=True)
    name = Column(str)

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
    name = Column(str, index=True)  # Create index

# Index query (automatically optimized)
stmt = select(Student).filter_by(name='Bob')
result = session.execute(stmt)
bob = result.first()
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
adults = result.all()
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
    id = Column(int, primary_key=True)
    name = Column(str)

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

Pytuck supports one-to-many, many-to-one, and self-referential relationships:

```python
from pytuck.core.orm import Relationship
from typing import List, Optional

class User(Base):
    __tablename__ = 'users'
    id = Column(int, primary_key=True)
    name = Column(str)
    # One-to-many: use table name reference (recommended)
    orders: List['Order'] = Relationship('orders', foreign_key='user_id')  # type: ignore

class Order(Base):
    __tablename__ = 'orders'
    id = Column(int, primary_key=True)
    user_id = Column(int)
    amount = Column(float)
    # Many-to-one
    user: Optional[User] = Relationship('users', foreign_key='user_id')  # type: ignore

# Self-reference (tree structure) - use uselist to specify direction
class Category(Base):
    __tablename__ = 'categories'
    id = Column(int, primary_key=True)
    parent_id = Column(int, nullable=True)
    parent: Optional['Category'] = Relationship('categories', foreign_key='parent_id', uselist=False)  # type: ignore
    children: List['Category'] = Relationship('categories', foreign_key='parent_id', uselist=True)  # type: ignore
```

**Features**:
- ✅ **Table Name Reference**: Use table name string for forward references
- ✅ **Lazy Loading**: Queries on first access, auto-cached
- ✅ **uselist Parameter**: Explicitly specify return type for self-reference
- ✅ **Type Hints**: Declare return type for IDE completion

> See `examples/relationship_demo.py` for complete examples

### Type Validation and Conversion

Pytuck provides zero-dependency automatic type validation and conversion:

```python
class User(Base):
    __tablename__ = 'users'
    id = Column(int, primary_key=True)
    age = Column(int)  # Declared as int

# Loose mode (default): auto conversion
user = User(age='25')  # ✅ Automatically converts '25' → 25

# Strict mode: no conversion, raises error on type mismatch
class StrictUser(Base):
    __tablename__ = 'strict_users'
    id = Column(int, primary_key=True)
    age = Column(int, strict=True)  # Strict mode

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
| datetime | ISO 8601 parse | '2024-01-15T10:30:00' → datetime |
| date | ISO 8601 parse | '2024-01-15' → date |
| timedelta | Total seconds | 3600.0 → timedelta(hours=1) |
| list | JSON parse | '[1,2,3]' → [1, 2, 3] |
| dict | JSON parse | '{"a":1}' → {'a': 1} |
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

Here are v4 version benchmark results.

### Test Environment

- **System**: Windows 11, Python 3.12.10
- **Test Data**: 100,000 records
- **Mode**: Extended test (including index comparison, range queries, batch reads, lazy loading)

### Performance Comparison

| Engine | Insert | Indexed | Non-Indexed | Speedup | Range | Save | Load | Lazy | Size |
|--------|--------|---------|-------------|---------|-------|------|------|------|------|
| Binary | 794.57ms | 1.39ms | 7.13s | 5124x | 333.29ms | 869.68ms | 1.01s | 319.88ms | 11.73MB |
| JSON | 844.76ms | 1.42ms | 8.95s | 6279x | 337.01ms | 845.77ms | 319.37ms | - | 18.90MB |
| CSV | 838.89ms | 1.47ms | 7.24s | 4939x | 346.85ms | 453.50ms | 472.90ms | - | 731.9KB |
| SQLite | 879.05ms | 1.40ms | 7.21s | 5145x | 333.84ms | 325.80ms | 393.39ms | - | 6.97MB |
| Excel | 897.48ms | 1.41ms | 7.25s | 5150x | 340.40ms | 5.75s | 7.63s | - | 2.84MB |
| XML | 1.23s | 1.41ms | 7.41s | 5248x | 333.87ms | 2.49s | 2.03s | - | 34.54MB |

**Notes**:
- **Indexed**: 100 indexed field equality lookups (millisecond level)
- **Non-Indexed**: 100 non-indexed field full table scans (second level)
- **Speedup**: Index query vs non-indexed query speedup ratio
- **Range**: Range condition queries (e.g., `age >= 20 AND age < 62`)
- **Lazy**: Only Binary engine supports lazy loading (loads index only, not data)

### Engine Feature Comparison

| Engine | Query Perf | I/O Perf | Storage Eff | Human Readable | Dependencies | Recommended Use |
|--------|-----------|----------|-------------|----------------|--------------|-----------------|
| Binary | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ❌ | None | **Production First Choice** |
| JSON | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ✅ | None | Development, Config Storage |
| CSV | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ✅ | None | Data Exchange, Minimum Size |
| SQLite | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ❌ | None | SQL Needed, ACID Guarantee |
| Excel | ⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐ | ✅ | openpyxl | Visual Editing, Reports |
| XML | ⭐⭐⭐⭐ | ⭐⭐ | ⭐ | ✅ | lxml | Enterprise Integration |

**Conclusions**:
- **Binary** fastest insert (794ms), supports lazy loading and encryption, **production first choice**
- **JSON** fastest load (319ms), easy debugging, suitable for development and config storage
- **CSV** smallest file (732KB, ZIP compressed), excellent I/O, suitable for data exchange
- **SQLite** best I/O (save 325ms), well-balanced, suitable for ACID requirements
- **Excel** slower I/O (7.63s load), suitable for visual editing scenarios
- **XML** largest file (34.54MB), suitable for enterprise integration

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
git clone https://github.com/Pytuck/Pytuck.git
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
| **No aggregate functions** | No COUNT, SUM, AVG, MIN, MAX support |
| **No relationship loading** | No lazy loading or eager loading of related objects |
| **Single writer** | No concurrent write support, suitable for single-process use |
| **Full rewrite on save** | Non-binary/SQLite backends rewrite entire file on each save |
| **No nested transactions** | Only single-level transactions supported |

## Roadmap / TODO

### Completed

- [x] **Extended Field Type Support** ✨NEW✨
  - [x] Added `datetime`, `date`, `timedelta`, `list`, `dict` five new types
  - [x] Unified TypeRegistry codec, all backends use consistent serialization interface
  - [x] JSON backend format optimization, removed redundant `_type`/`_value` wrapper
- [x] **Binary Engine v4 Format** ✨NEW✨
  - [x] WAL (Write-Ahead Log) for O(1) write latency
  - [x] Dual Header mechanism for atomic switching and crash recovery
  - [x] Index region zlib compression (saves ~81% space)
  - [x] Batch I/O and codec caching optimizations
  - [x] Three-tier encryption support (low/medium/high), pure Python implementation
- [x] **Primary Key Query Optimization** (affects ALL storage engines) ✨NEW✨
  - [x] `WHERE pk = value` queries use O(1) direct access
  - [x] Single update/delete performance improved ~1000x
- [x] Complete SQLAlchemy 2.0 Style Object State Management
  - [x] Identity Map (Object Uniqueness Management)
  - [x] Automatic Dirty Tracking (Attribute assignment auto-detected and updates database)
  - [x] merge() Operation (Merge detached objects)
  - [x] Query Instance Auto-Registration to Session
- [x] Unified database connector architecture (`pytuck/connectors/` module)
- [x] Data migration tools (`migrate_engine()`, `import_from_database()`)
- [x] Import from external relational databases feature
- [x] Unified engine version management (`pytuck/backends/versions.py`)
- [x] Table and column comment support (`comment` parameter)
- [x] Complete generic type hints system
- [x] Strongly-typed configuration options system (dataclass replaces **kwargs)
- [x] **Schema Sync & Migration** ✨NEW✨
  - [x] Support automatic schema synchronization when loading existing database
  - [x] `SyncOptions` configuration class to control sync behavior
  - [x] `SyncResult` to record sync change details
  - [x] Three-layer API design: Table → Storage → Session
  - [x] Support SQLite native SQL mode DDL operations
  - [x] Pure table-name API (no model class required)
- [x] **Excel Row Number Mapping** ✨NEW✨
  - [x] `row_number_mapping='as_pk'`: Use row number as primary key
  - [x] `row_number_mapping='field'`: Map row number to a field
  - [x] Support loading external Excel files
- [x] **SQLite Native SQL Mode Optimization** ✨NEW✨
  - [x] Native SQL mode enabled by default
  - [x] Complete type mapping (10 Pytuck types)
  - [x] Multi-column ORDER BY support
- [x] **Exception System Refactoring** ✨NEW✨
  - [x] Unified exception hierarchy
  - [x] Added TypeConversionError, ConfigurationError, SchemaError, etc.
- [x] **Backend Auto-Registration** ✨NEW✨
  - [x] Automatic registration via `__init_subclass__`
  - [x] Custom backends only need to inherit `StorageBackend`
- [x] **Query Result API Simplification** ✨NEW✨
  - [x] Removed `Result.scalars()` intermediate layer
  - [x] Use `result.all()`, `result.first()` directly
- [x] **Migration Tool Lazy Loading Support** ✨NEW✨
  - [x] Fixed data migration issues with lazy loading backends
- [x] **Primary Key-less Model Support** ✨NEW✨
  - [x] Support defining models without a primary key, using internal implicit `_pytuck_rowid`
  - [x] Suitable for log tables, event tables, etc.
- [x] **Logical Query Operators OR/AND/NOT** ✨NEW✨
  - [x] Added `or_()`, `and_()`, `not_()` logical operators
  - [x] Support for complex condition combinations and nested queries
- [x] **External File Loading (load_table)** ✨NEW✨
  - [x] Added `load_table()` function to load CSV/Excel files as model object lists
  - [x] Type coercion: convert if possible, raise error if not

### Planned Features

> 📋 For detailed development plans, please refer to [TODO.md](./TODO.md)

- [ ] **Web UI Interface Support** - Provide API support for independent Web UI library
- [ ] **ORM Event Hooks System** - Complete event system based on SQLAlchemy event pattern
- [ ] **JOIN Support** - Multi-table relational queries
- [ ] **Aggregate Functions** - COUNT, SUM, AVG, MIN, MAX, etc.
- [ ] **Relationship Lazy Loading** - Optimize associated data loading performance
- [ ] **Concurrent Access Support** - Multi-process/thread-safe access

### Planned Engines

- [ ] DuckDB - Analytical database engine
- [ ] TinyDB - Pure Python document database
- [ ] PyDbLite3 - Pure Python in-memory database
- [ ] diskcache - Disk-based cache engine

### Planned Optimizations

- [ ] Incremental save for non-binary backends (currently full rewrite on each save)
- [ ] Binary engine Compaction (space reclaim) mechanism
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

Inspired by SQLAlchemy, and TinyDB.
