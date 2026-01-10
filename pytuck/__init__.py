"""
Pytuck - 轻量级 Python 文档数据库

基于对象模型的数据库系统，无需编写SQL，支持：
- SQLAlchemy 2.0 风格 API
- Pythonic 查询表达式
- 多存储引擎（Binary, JSON, CSV, SQLite, Excel, XML）
- 索引优化
- 事务支持
- 类型安全

两种使用模式：

1. 纯模型模式（默认，推荐）- 通过 Session 操作数据：
    from typing import Type
    from pytuck import Storage, declarative_base, Session, Column
    from pytuck import PureBaseModel, select, insert, update, delete

    db = Storage(file_path='mydb.db')
    Base: Type[PureBaseModel] = declarative_base(db)

    class User(Base):
        __tablename__ = 'users'
        id = Column('id', int, primary_key=True)
        name = Column('name', str)
        age = Column('age', int)

    session = Session(db)

    # 插入
    stmt = insert(User).values(name='Alice', age=20)
    session.execute(stmt)
    session.commit()

    # 查询
    stmt = select(User).where(User.age >= 18)
    result = session.execute(stmt)
    users = result.scalars().all()

2. Active Record 模式 - 模型自带 CRUD 方法：
    from typing import Type
    from pytuck import Storage, declarative_base, Column
    from pytuck import CRUDBaseModel

    db = Storage(file_path='mydb.db')
    Base: Type[CRUDBaseModel] = declarative_base(db, crud=True)

    class User(Base):
        __tablename__ = 'users'
        id = Column('id', int, primary_key=True)
        name = Column('name', str)

    # 直接在模型上操作
    user = User.create(name='Alice')
    user.name = 'Bob'
    user.save()
    user.delete()
"""

from .orm import (
    Column,
    Relationship,
    declarative_base,
    PureBaseModel,
    CRUDBaseModel,
)
from .storage import Storage
from .session import Session
from .query import Query, BinaryExpression
from .statements import select, insert, update, delete
from .result import Result, ScalarResult, Row, CursorResult
from .exceptions import (
    PytuckException,
    TableNotFoundError,
    RecordNotFoundError,
    DuplicateKeyError,
    TransactionError,
    SerializationError
)
from .tools.migrate import migrate_engine, get_available_engines

__version__ = '0.1.0'
__all__ = [
    # ==================== 推荐 API ====================

    # SQLAlchemy 2.0 风格语句构建器
    'select',      # SELECT 查询
    'insert',      # INSERT 插入
    'update',      # UPDATE 更新
    'delete',      # DELETE 删除

    # 核心组件
    'Storage',            # 存储引擎
    'declarative_base',   # 声明式基类工厂
    'Session',            # 会话管理
    'Column',             # 列定义
    'Relationship',       # 关系定义

    # 类型定义（用于类型注解）
    'PureBaseModel',      # 纯模型基类类型
    'CRUDBaseModel',      # Active Record 基类类型

    # 查询结果
    'Result',        # 查询结果包装器
    'ScalarResult',  # 标量结果
    'Row',           # 行对象
    'CursorResult',  # CUD 操作结果

    # 高级用法
    'BinaryExpression',  # 查询表达式（用于构建复杂查询）
    'Query',             # 查询构建器（内部使用）

    # ==================== 异常 ====================

    'PytuckException',
    'TableNotFoundError',
    'RecordNotFoundError',
    'DuplicateKeyError',
    'TransactionError',
    'SerializationError',

    # ==================== 工具 ====================

    'migrate_engine',        # 数据迁移
    'get_available_engines', # 获取可用引擎
]
