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

### Tests

- Added ORM event hooks tests (35 test cases)
- Added relationship prefetch tests (23 test cases)
- Added query index optimization tests (42 test cases)
