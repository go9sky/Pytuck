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

### Tests

- Added ORM event hooks tests (35 test cases)
- Added relationship prefetch tests (23 test cases)
