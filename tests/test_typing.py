"""
Type checking tests for Pytuck generic type system

This file is designed for mypy validation, not runtime execution.
It demonstrates the improved type hints and validates type inference.

Run with: mypy --config-file mypy.ini tests/test_typing.py
"""

from typing import List, Optional, TYPE_CHECKING, cast

if TYPE_CHECKING:
    from pytuck import Storage, declarative_base, Session, Column
    from pytuck import select, insert, update, delete
    from pytuck.query.result import Result, ScalarResult, CursorResult
    from pytuck.query.statements import Select, Insert, Update, Delete


def test_statement_generics() -> None:
    """Test that statement factory functions return properly typed objects"""
    # 在类型检查时跳过实际导入，只进行类型验证
    if TYPE_CHECKING:
        from pytuck import Storage, declarative_base, Column
        from pytuck import select, insert, update, delete
        from pytuck.core.orm import PureBaseModel

        db = Storage(':memory:')
        Base = declarative_base(db)

        class User(Base):  # type: ignore[misc]
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


def test_session_execute_overloads() -> None:
    """Test that Session.execute returns properly typed results"""
    if TYPE_CHECKING:
        from pytuck import Storage, declarative_base, Session, Column
        from pytuck import select, insert, update, delete
        from pytuck.core.orm import PureBaseModel

        db = Storage(':memory:')
        Base = declarative_base(db)

        class User(Base):  # type: ignore[misc]
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


def test_result_scalars_typing() -> None:
    """Test that result methods return properly typed objects"""
    if TYPE_CHECKING:
        from pytuck import Storage, declarative_base, Session, Column
        from pytuck import select
        from pytuck.core.orm import PureBaseModel

        db = Storage(':memory:')
        Base = declarative_base(db)

        class User(Base):  # type: ignore[misc]
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
    if TYPE_CHECKING:
        from pytuck import Storage, declarative_base, Session, Column
        from pytuck import select
        from pytuck.core.orm import PureBaseModel

        db = Storage(':memory:')
        Base = declarative_base(db)

        class User(Base):  # type: ignore[misc]
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
            # Use cast to help mypy understand attribute types
            name_str: str = cast(str, user.name)
            age_int: int = cast(int, user.age)
            id_int: int = cast(int, user.id)


if __name__ == '__main__':
    # This file is for mypy validation, not runtime execution
    print("This file is for mypy type checking validation.")
    print("Run: mypy --config-file mypy.ini tests/test_typing.py")