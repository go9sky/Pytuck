"""
Pytuck 类型检查测试

本模块包含两部分：
1. test_mypy_pytuck: 运行时测试，确保整个 pytuck 库通过 mypy 类型检查
2. TYPE_CHECKING 块中的类型示例：仅供 mypy 静态分析验证泛型类型系统

运行测试: pytest tests/test_typing.py -v
运行 mypy: mypy --config-file mypy.ini pytuck
"""

import subprocess
import sys
from typing import List, Optional, TYPE_CHECKING, cast


def test_mypy_pytuck() -> None:
    """确保整个 pytuck 库通过 mypy 类型检查"""
    result = subprocess.run(
        [sys.executable, '-m', 'mypy', 'pytuck', '--config-file', 'mypy.ini'],
        capture_output=True,
        text=True
    )
    assert result.returncode == 0, f"mypy errors:\n{result.stdout}\n{result.stderr}"


# ============================================================================
# 以下代码仅在 TYPE_CHECKING 时执行，用于 mypy 静态类型验证
# 这些代码演示了 Pytuck 的泛型类型系统，确保类型推断正确
# ============================================================================

if TYPE_CHECKING:
    from pytuck import Storage, declarative_base, Session, Column
    from pytuck import select, insert, update, delete
    from pytuck.query.result import Result, CursorResult
    from pytuck.query.statements import Select, Insert, Update, Delete

    # 示例模型定义
    db = Storage(':memory:')
    Base = declarative_base(db)

    class User(Base):  # type: ignore[valid-type,misc]
        __tablename__ = 'users'
        id = Column(int, primary_key=True)
        name = Column(str)
        age = Column(int)

    # Statement 工厂函数应返回泛型类型
    select_stmt: Select[User] = select(User)
    insert_stmt: Insert[User] = insert(User)
    update_stmt: Update[User] = update(User)
    delete_stmt: Delete[User] = delete(User)

    # 方法链应保持类型
    filtered_stmt: Select[User] = select_stmt.where(User.age >= 18)
    ordered_stmt: Select[User] = filtered_stmt.order_by('name')
    limited_stmt: Select[User] = ordered_stmt.limit(10)

    # Session.execute 应返回正确类型的结果
    session = Session(db)
    select_result: Result[User] = session.execute(select(User))
    insert_result: CursorResult[User] = session.execute(
        insert(User).values(name='Alice', age=25)
    )

    # 直接使用 Result 的方法进行类型断言（不再依赖 ScalarResult）
    users: List[User] = select_result.all()
    user: Optional[User] = select_result.first()
    one_user: User = select_result.one()
    maybe_user: Optional[User] = select_result.one_or_none()

    # 属性访问类型验证
    if user is not None:
        name_str: str = cast(str, user.name)
        age_int: int = cast(int, user.age)
        id_int: int = cast(int, user.id)
