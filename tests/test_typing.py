"""
Type checking tests for Pytuck generic type system

This file is designed for mypy validation, not runtime execution.
It demonstrates the improved type hints and validates type inference.

Run with: mypy --config-file mypy.ini tests/test_typing.py
"""

from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from pytuck import Storage, declarative_base, Session, Column
    from pytuck import select, insert, update, delete
    from pytuck.query.result import Result, ScalarResult, CursorResult
    from pytuck.query.statements import Select, Insert, Update, Delete

def test_statement_generics() -> None:
    """Test that statement factory functions return properly typed objects"""
    from pytuck import Storage, declarative_base, Column
    from pytuck import select, insert, update, delete

    db = Storage(':memory:')
    Base = declarative_base(db)

    class User(Base):
        __tablename__ = 'users'
        id = Column('id', int, primary_key=True)
        name = Column('name', str)
        age = Column('age', int)

    # Statement factory functions should return generic types
    select_stmt = select(User)          # Should be Select[User]
    insert_stmt = insert(User)          # Should be Insert[User]
    update_stmt = update(User)          # Should be Update[User]
    delete_stmt = delete(User)          # Should be Delete[User]

    # Method chaining should preserve types
    filtered_stmt = select_stmt.where(User.age >= 18)  # Should be Select[User]
    ordered_stmt = filtered_stmt.order_by('name')      # Should be Select[User]
    limited_stmt = ordered_stmt.limit(10)              # Should be Select[User]

    # Insert with values should preserve type
    insert_with_values = insert_stmt.values(name='Alice', age=25)  # Should be Insert[User]

    # Update with conditions and values
    update_with_conditions = update_stmt.where(User.id == 1).values(age=26)  # Should be Update[User]

    # Delete with conditions
    delete_with_conditions = delete_stmt.where(User.age < 18)  # Should be Delete[User]


def test_session_execute_overloads() -> None:
    """Test that Session.execute returns properly typed results"""
    from pytuck import Storage, declarative_base, Session, Column
    from pytuck import select, insert, update, delete

    db = Storage(':memory:')
    Base = declarative_base(db)

    class User(Base):
        __tablename__ = 'users'
        id = Column('id', int, primary_key=True)
        name = Column('name', str)
        age = Column('age', int)

    session = Session(db)

    # Select should return Result[User]
    select_result = session.execute(select(User))  # Should be Result[User]

    # Insert should return CursorResult[User]
    insert_result = session.execute(
        insert(User).values(name='Alice', age=25)
    )  # Should be CursorResult[User]

    # Update should return CursorResult[User]
    update_result = session.execute(
        update(User).where(User.id == 1).values(age=26)
    )  # Should be CursorResult[User]

    # Delete should return CursorResult[User]
    delete_result = session.execute(
        delete(User).where(User.age < 18)
    )  # Should be CursorResult[User]


def test_result_scalars_typing() -> None:
    """Test that result methods return properly typed objects"""
    from pytuck import Storage, declarative_base, Session, Column
    from pytuck import select

    db = Storage(':memory:')
    Base = declarative_base(db)

    class User(Base):
        __tablename__ = 'users'
        id = Column('id', int, primary_key=True)
        name = Column('name', str)
        age = Column('age', int)

    session = Session(db)
    result = session.execute(select(User))  # Result[User]

    # ScalarResult should be generic
    scalar_result = result.scalars()        # Should be ScalarResult[User]

    # ScalarResult methods should return User types
    users = scalar_result.all()             # Should be List[User] ✅
    user = scalar_result.first()            # Should be Optional[User] ✅
    one_user = scalar_result.one()          # Should be User ✅
    maybe_user = scalar_result.one_or_none()  # Should be Optional[User] ✅


def test_type_safety_examples() -> None:
    """Test examples that should pass/fail type checking"""
    from pytuck import Storage, declarative_base, Session, Column
    from pytuck import select

    db = Storage(':memory:')
    Base = declarative_base(db)

    class User(Base):
        __tablename__ = 'users'
        id = Column('id', int, primary_key=True)
        name = Column('name', str)
        age = Column('age', int)

    session = Session(db)
    result = session.execute(select(User))

    # These should pass type checking
    users: List[User] = result.scalars().all()
    user: Optional[User] = result.scalars().first()

    # Access User attributes (should be recognized by IDE)
    if user is not None:
        name_str: str = user.name     # ✅ Should know this is str
        age_int: int = user.age       # ✅ Should know this is int
        id_int: int = user.id         # ✅ Should know this is int

    # These should fail type checking (commented out to avoid mypy errors)
    # user_direct: User = result.scalars().first()  # ❌ Could be None
    # wrong_type: str = result.scalars().all()      # ❌ Wrong type


def test_session_get_typing() -> None:
    """Test that Session.get returns properly typed objects"""
    from pytuck import Storage, declarative_base, Session, Column

    db = Storage(':memory:')
    Base = declarative_base(db)

    class User(Base):
        __tablename__ = 'users'
        id = Column('id', int, primary_key=True)
        name = Column('name', str)

    session = Session(db)

    # get should return Optional[User]
    user = session.get(User, 1)  # Should be Optional[User]

    if user is not None:
        # IDE should know user is User instance
        user_name: str = user.name  # ✅ Should know this is str


def test_query_builder_typing() -> None:
    """Test that Query builder returns properly typed objects"""
    from pytuck import Storage, declarative_base, Session, Column

    db = Storage(':memory:')
    Base = declarative_base(db)

    class User(Base):
        __tablename__ = 'users'
        id = Column('id', int, primary_key=True)
        name = Column('name', str)
        age = Column('age', int)

    session = Session(db)

    # query should return Query[User] (though deprecated)
    query = session.query(User)  # Should be Query[User]

    # Query methods should preserve type
    filtered_query = query.filter(User.age >= 18)  # Should be Query[User]
    filtered_by_query = query.filter_by(name='Alice')  # Should be Query[User]
    ordered_query = query.order_by('name')  # Should be Query[User]
    limited_query = query.limit(10)  # Should be Query[User]
    offset_query = query.offset(5)  # Should be Query[User]

    # Query execution methods should return User types
    users = query.all()    # Should be List[User] ✅
    user = query.first()   # Should be Optional[User] ✅
    count = query.count()  # Should be int


def test_chained_operations() -> None:
    """Test complex chained operations maintain proper types"""
    from pytuck import Storage, declarative_base, Session, Column
    from pytuck import select, insert

    db = Storage(':memory:')
    Base = declarative_base(db)

    class User(Base):
        __tablename__ = 'users'
        id = Column('id', int, primary_key=True)
        name = Column('name', str)
        age = Column('age', int)

    session = Session(db)

    # Complex chained query should maintain User type throughout
    users = (session
             .execute(
                 select(User)
                 .where(User.age >= 18)
                 .order_by('name')
                 .limit(10)
             )
             .scalars()
             .all())  # Should be List[User] ✅

    # Verify we can access User attributes
    for user in users:
        user_name: str = user.name  # ✅ Should know this is str
        user_age: int = user.age    # ✅ Should know this is int


if __name__ == '__main__':
    # This file is for mypy validation, not runtime execution
    print("This file is for mypy type checking validation.")
    print("Run: mypy --config-file mypy.ini tests/test_typing.py")