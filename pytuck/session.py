"""
Session - 会话管理器

提供类似 SQLAlchemy 的 Session 模式，统一管理数据库操作。
"""

from typing import Any, Dict, List, Optional, Type, Tuple, TYPE_CHECKING, Union, Generator
from contextlib import contextmanager


if TYPE_CHECKING:
    from .result import Result, CursorResult
    from .statements import Statement, Insert, Select, Update, Delete
    from .storage import Storage
    from .orm import PureBaseModel

from .query import Query


class Session:
    """
    会话管理器

    统一管理所有数据库操作（CRUD），提供对象状态追踪和事务管理。

    使用方式:
        session = Session(storage)

        # 插入
        user = User(name='Alice', age=20)
        session.add(user)
        session.commit()

        # 查询
        user = session.get(User, 1)
        users = session.query(User).filter(age__gte=18).all()

        # 更新
        user.age = 21
        session.commit()

        # 删除
        session.delete(user)
        session.commit()

        # 事务
        with session.begin():
            session.add(User(name='Bob'))
            session.add(User(name='Charlie'))
    """

    def __init__(self, storage: 'Storage', autocommit: bool = False):
        """
        初始化 Session

        Args:
            storage: Storage 实例
            autocommit: 是否自动提交（默认 False）
        """
        self.storage = storage
        self.autocommit = autocommit

        # 对象状态追踪
        self._new_objects: List['PureBaseModel'] = []      # 待插入对象
        self._dirty_objects: List['PureBaseModel'] = []    # 待更新对象
        self._deleted_objects: List['PureBaseModel'] = []  # 待删除对象

        # 标识映射：缓存已加载的对象 {(model_class, pk): instance}
        self._identity_map: Dict[Tuple[Type['PureBaseModel'], Any], 'PureBaseModel'] = {}

        # 事务状态
        self._in_transaction = False

    def add(self, instance: 'PureBaseModel') -> None:
        """
        添加对象到会话（标记为待插入）

        Args:
            instance: 模型实例
        """
        if instance not in self._new_objects:
            self._new_objects.append(instance)

        if self.autocommit:
            self.commit()

    def add_all(self, instances: List['PureBaseModel']) -> None:
        """
        批量添加对象到会话

        Args:
            instances: 模型实例列表
        """
        for instance in instances:
            self.add(instance)

    def delete(self, instance: 'PureBaseModel') -> None:
        """
        标记对象为待删除

        Args:
            instance: 模型实例
        """
        # 从新增列表中移除（如果还未持久化）
        if instance in self._new_objects:
            self._new_objects.remove(instance)
        else:
            # 已持久化的对象标记为待删除
            if instance not in self._deleted_objects:
                self._deleted_objects.append(instance)

        if self.autocommit:
            self.commit()

    def flush(self) -> None:
        """
        将待处理的修改刷新到数据库（不提交事务）
        """
        # 1. 处理待插入对象
        for instance in self._new_objects:
            table_name = instance.__tablename__

            # 构建要插入的数据
            data = {}
            for col_name, column in instance.__columns__.items():
                value = getattr(instance, col_name, None)
                if value is not None:
                    data[col_name] = value

            # 插入到数据库
            pk = self.storage.insert(table_name, data)

            # 设置主键
            pk_name = instance.__primary_key__
            setattr(instance, pk_name, pk)

            # 加入标识映射
            self._identity_map[(instance.__class__, pk)] = instance

        # 2. 处理待更新对象
        for instance in self._dirty_objects:
            table_name = instance.__tablename__
            pk_name = instance.__primary_key__
            pk = getattr(instance, pk_name)

            # 构建要更新的数据
            data = {}
            for col_name in instance.__columns__.keys():
                value = getattr(instance, col_name, None)
                if value is not None:
                    data[col_name] = value

            # 更新数据库
            self.storage.update(table_name, pk, data)

        # 3. 处理待删除对象
        for instance in self._deleted_objects:
            table_name = instance.__tablename__
            pk_name = instance.__primary_key__
            pk = getattr(instance, pk_name)

            # 从数据库删除
            self.storage.delete(table_name, pk)

            # 从标识映射移除
            key = (instance.__class__, pk)
            if key in self._identity_map:
                del self._identity_map[key]

        # 清空待处理列表
        self._new_objects.clear()
        self._dirty_objects.clear()
        self._deleted_objects.clear()

    def commit(self) -> None:
        """
        提交事务（刷新修改并持久化）
        """
        self.flush()

        # 如果启用了 auto_flush，触发持久化
        if self.storage.auto_flush:
            self.storage.flush()

    def rollback(self) -> None:
        """
        回滚事务（清空所有待处理修改）
        """
        self._new_objects.clear()
        self._dirty_objects.clear()
        self._deleted_objects.clear()
        self._identity_map.clear()

    def get(self, model_class: Type['PureBaseModel'], pk: Any) -> Optional['PureBaseModel']:
        """
        通过主键获取对象

        Args:
            model_class: 模型类
            pk: 主键值

        Returns:
            模型实例，如果不存在返回 None
        """
        # 先从标识映射查找
        key = (model_class, pk)
        if key in self._identity_map:
            return self._identity_map[key]

        # 从数据库查询
        table_name = model_class.__tablename__
        try:
            record = self.storage.get_table(table_name).get(pk)

            # 创建模型实例
            instance = model_class(**record)

            # 加入标识映射
            self._identity_map[key] = instance

            return instance
        except Exception:
            return None

    def execute(self, statement: 'Statement') -> Union['Result', 'CursorResult']:
        """
        执行 statement（SQLAlchemy 2.0 风格）

        Args:
            statement: Statement 对象 (Select, Insert, Update, Delete)

        Returns:
            Result 对象

        用法：
            # 查询
            stmt = select(User).where(User.age >= 18)
            result = session.execute(stmt)
            users = result.scalars().all()

            # 插入
            stmt = insert(User).values(name='Alice', age=20)
            result = session.execute(stmt)
            session.commit()
        """
        from .statements import Select, Insert, Update, Delete
        from .result import Result, CursorResult

        # 执行 statement
        if isinstance(statement, Select):
            records = statement._execute(self.storage)
            return Result(records, statement.model_class, 'select')

        elif isinstance(statement, Insert):
            pk = statement._execute(self.storage)
            # 标记为新对象（用于事务管理）
            # 注意：这里不创建实例，只记录操作
            return CursorResult(1, statement.model_class, 'insert', inserted_pk=pk)

        elif isinstance(statement, Update):
            count = statement._execute(self.storage)
            return CursorResult(count, statement.model_class, 'update')

        elif isinstance(statement, Delete):
            count = statement._execute(self.storage)
            return CursorResult(count, statement.model_class, 'delete')

        else:
            raise TypeError(f"Unsupported statement type: {type(statement)}")

    def query(self, model_class: Type['PureBaseModel']) -> Query:
        """
        创建查询构建器（SQLAlchemy 1.4 风格，不推荐）

        ⚠️ 不推荐使用：请改用 session.execute(select(...)) 风格

        推荐写法：
            from pytuck import select
            stmt = select(User).where(User.age >= 18)
            result = session.execute(stmt)
            users = result.scalars().all()

        旧写法（仍然支持）：
            users = session.query(User).filter(User.age >= 18).all()

        Args:
            model_class: 模型类

        Returns:
            Query 对象
        """
        import warnings
        warnings.warn(
            "session.query() is deprecated. Use session.execute(select(...)) instead.",
            DeprecationWarning,
            stacklevel=2
        )
        return Query(model_class, self.storage)

    @contextmanager
    def begin(self) -> Generator['Session', None, None]:
        """
        事务上下文管理器

        用法:
            with session.begin():
                session.add(User(name='Alice'))
                session.add(User(name='Bob'))
        """
        if self._in_transaction:
            raise RuntimeError("Nested transactions are not supported in Session")

        self._in_transaction = True

        try:
            # 使用 Storage 的事务支持
            with self.storage.transaction():
                yield self
                # 提交 Session 级别的修改
                self.flush()
        except Exception:
            # 回滚 Session 状态
            self.rollback()
            raise
        finally:
            self._in_transaction = False

    def close(self) -> None:
        """
        关闭会话，清理所有状态
        """
        self.rollback()

    def __enter__(self) -> 'Session':
        """上下文管理器入口"""
        return self

    def __exit__(self, exc_type: Optional[Type[BaseException]], exc_val: Optional[BaseException], exc_tb: Any) -> bool:
        """上下文管理器出口"""
        if exc_type is None:
            self.commit()
        else:
            self.rollback()
        return False
