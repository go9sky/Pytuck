# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

> [中文版](./CHANGELOG.md)

> For historical versions, see: [docs/changelog/](./docs/changelog/)

---

## [0.7.0] - 2026-02-07

### Added

- **ORM Event Hooks**
  - Model-level events: `before_insert`/`after_insert`, `before_update`/`after_update`, `before_delete`/`after_delete`
  - Storage-level events: `before_flush`/`after_flush`
  - Supports both decorator and functional registration
  - Example:
    ```python
    from pytuck import event

    @event.listens_for(User, 'before_insert')
    def set_timestamp(instance):
        instance.created_at = datetime.now()

    # Functional registration
    event.listen(User, 'after_update', audit_changes)

    # Storage-level events
    event.listen(db, 'before_flush', lambda storage: print("flushing..."))

    # Remove listener
    event.remove(User, 'before_insert', set_timestamp)
    ```

- **Relationship Prefetch API**
  - Added `prefetch()` function for batch loading related data, solving the N+1 query problem
  - Supports both standalone function call and query option styles
  - Supports one-to-many and many-to-one relationships
  - Example:
    ```python
    from pytuck import prefetch, select

    # Style 1: Standalone function
    users = session.execute(select(User)).all()
    prefetch(users, 'orders')              # Single query loads all users' orders
    prefetch(users, 'orders', 'profile')   # Multiple relationship names

    # Style 2: Query option
    stmt = select(User).options(prefetch('orders'))
    users = session.execute(stmt).all()    # orders are batch-loaded
    ```

- **Select.options() Method**
  - Added query option chaining support, currently used for prefetch

- **Query Index Optimization**
  - `Column` now supports specifying index type: `index='hash'` (hash index) or `index='sorted'` (sorted index)
  - Range queries (`>`, `>=`, `<`, `<=`) automatically use SortedIndex for acceleration, avoiding full table scans
  - `order_by` sorting automatically leverages SortedIndex ordering, with inline pagination (early stopping)
  - `SortedIndex.range_query()` supports open-ended queries (`None` boundaries)
  - Backward compatible: `index=True` still creates HashIndex
  - Example:
    ```python
    class User(Base):
        __tablename__ = 'users'
        id = Column(int, primary_key=True)
        name = Column(str, index=True)        # Hash index (equality query acceleration)
        age = Column(int, index='sorted')      # Sorted index (range query + sorting acceleration)

    # Range queries automatically use sorted index
    stmt = select(User).where(User.age >= 18, User.age < 30)

    # Sorting automatically uses sorted index (no full-data sorting needed)
    stmt = select(User).order_by('age').limit(10)
    ```

### Performance Benchmark (Query Index Optimization)

> Test environment: 100,000 records, age field range 1-100, comparing No Index / HashIndex / SortedIndex

**Storage.query (Low-level Engine)**

| Scenario | No Index | SortedIndex | Speedup |
|----------|----------|-------------|---------|
| Range query `age BETWEEN 30 AND 50` (~21% data) | 10.00s | 3.16s | **3.2x** |
| High selectivity `age > 95` (~5% data) | 7.95s | 541ms | **14.7x** |
| Full `order_by('age')` | 7.21s | 8.01s | 0.9x |

**select() API (High-level)**

| Scenario | No Index | SortedIndex | Speedup |
|----------|----------|-------------|---------|
| Range query `age BETWEEN X AND Y` | 33.60s | 28.28s | **1.2x** |
| High selectivity `age > 95` | 10.19s | 2.96s | **3.4x** |
| Combo `range + order_by + limit` | 6.51s | 4.48s | **1.5x** |

**Key Findings**:
- Range queries are SortedIndex's primary strength — bisect locates boundaries to reduce scan volume
- Higher selectivity (fewer matching records) yields greater speedup — up to **14.7x** at the engine level
- Upper-layer API speedup is lower than engine-level due to fixed model instantiation overhead
- Pure sorting shows no improvement since Python's C-level timsort is already highly optimized
- Combined queries (range + sort + pagination) benefit from reduced candidate set before sorting

> Run benchmark: `python tests/benchmark/benchmark_index.py -n 100000`

### Tests

- Added ORM event hooks tests (35 test cases)
- Added relationship prefetch tests (23 test cases)
- Added query index optimization tests (42 test cases)
- Added index optimization benchmark script (`tests/benchmark/benchmark_index.py`)
