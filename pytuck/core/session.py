"""
Session - 会话管理器

提供类似 SQLAlchemy 的 Session 模式，统一管理数据库操作。
"""

from typing import Any, Dict, List, Optional, Type, Tuple, TYPE_CHECKING, Union, Generator, overload
from contextlib import contextmanager

from ..common.types import T
from ..common.exceptions import QueryError, TransactionError
from ..common.options import SyncOptions, SyncResult
from ..query.builder import Query, BinaryExpression, LogicalExpression
from ..query.result import Result, CursorResult
from ..query.statements import Statement, Insert, Select, Update, Delete
from .storage import Storage
from .orm import PureBaseModel, Column, PSEUDO_PK_NAME


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

    def __init__(self, storage: Storage, autocommit: bool = False):
        """
        初始化 Session

        Args:
            storage: Storage 实例
            autocommit: 是否自动提交（默认 False）
        """
        self.storage = storage
        self.autocommit = autocommit

        # 对象状态追踪
        self._new_objects: List[PureBaseModel] = []      # 待插入对象
        self._dirty_objects: List[PureBaseModel] = []    # 待更新对象
        self._deleted_objects: List[PureBaseModel] = []  # 待删除对象

        # 标识映射：缓存已加载的对象 {(model_class, pk): instance}
        self._identity_map: Dict[Tuple[Type[PureBaseModel], Any], PureBaseModel] = {}

        # 事务状态
        self._in_transaction = False

    def add(self, instance: PureBaseModel) -> None:
        """
        添加对象到会话（标记为待插入）

        Args:
            instance: 模型实例
        """
        if instance not in self._new_objects:
            self._new_objects.append(instance)

        if self.autocommit:
            self.commit()

    def add_all(self, instances: List[PureBaseModel]) -> None:
        """
        批量添加对象到会话

        Args:
            instances: 模型实例列表
        """
        for instance in instances:
            self.add(instance)

    def delete(self, instance: PureBaseModel) -> None:
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
            assert table_name is not None, f"Model {instance.__class__.__name__} must have __tablename__ defined"

            # 构建要插入的数据（使用 Column.name 作为存储键）
            data = {}
            for attr_name, column in instance.__columns__.items():
                value = getattr(instance, attr_name, None)
                if value is not None:
                    # 使用 Column.name 作为存储键
                    db_col_name = column.name if column.name else attr_name
                    data[db_col_name] = value

            # 插入到数据库
            pk = self.storage.insert(table_name, data)

            # 设置主键（或隐式 rowid）
            pk_name = instance.__primary_key__
            if pk_name:
                setattr(instance, pk_name, pk)
            else:
                # 无主键时，使用隐式 rowid
                setattr(instance, '_pytuck_rowid', pk)

            # 从数据库重新读取并更新实例（刷新所有字段，类似 SQLAlchemy）
            db_record = self.storage.select(table_name, pk)
            for db_col_name, value in db_record.items():
                if db_col_name != PSEUDO_PK_NAME:
                    # 将 Column.name 转换回属性名
                    attr_name = instance._column_to_attr_name(db_col_name) or db_col_name
                    object.__setattr__(instance, attr_name, value)

            # 注册到标识映射（使用统一的方法，设置 session 引用）
            self._register_instance(instance)

        # 2. 处理待更新对象
        for instance in self._dirty_objects:
            table_name = instance.__tablename__
            assert table_name is not None, f"Model {instance.__class__.__name__} must have __tablename__ defined"

            pk_name = instance.__primary_key__
            if pk_name:
                pk = getattr(instance, pk_name)
            else:
                pk = getattr(instance, '_pytuck_rowid', None)

            # 构建要更新的数据（使用 Column.name 作为存储键）
            data = {}
            for attr_name, column in instance.__columns__.items():
                value = getattr(instance, attr_name, None)
                if value is not None:
                    # 使用 Column.name 作为存储键
                    db_col_name = column.name if column.name else attr_name
                    data[db_col_name] = value

            # 更新数据库
            self.storage.update(table_name, pk, data)

            # 从数据库重新读取并更新实例
            db_record = self.storage.select(table_name, pk)
            for db_col_name, value in db_record.items():
                if db_col_name != PSEUDO_PK_NAME:
                    # 将 Column.name 转换回属性名
                    attr_name = instance._column_to_attr_name(db_col_name) or db_col_name
                    object.__setattr__(instance, attr_name, value)

        # 3. 处理待删除对象
        for instance in self._deleted_objects:
            table_name = instance.__tablename__
            assert table_name is not None, f"Model {instance.__class__.__name__} must have __tablename__ defined"

            pk_name = instance.__primary_key__
            if pk_name:
                pk = getattr(instance, pk_name)
            else:
                pk = getattr(instance, '_pytuck_rowid', None)

            # 从数据库删除
            self.storage.delete(table_name, pk)

            # 从标识映射移除
            if pk_name:
                key = (instance.__class__, pk)
            else:
                key = (instance.__class__, (PSEUDO_PK_NAME, pk))
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

    def get(self, model_class: Type[T], pk: Any) -> Optional[T]:
        """
        通过主键获取对象

        Args:
            model_class: 模型类
            pk: 主键值

        Returns:
            模型实例，如果不存在返回 None

        Raises:
            QueryError: 如果模型没有定义主键（reason='no_primary_key'）

        Note:
            无主键模型无法使用此方法，请使用 select() 语句进行查询。
        """
        # 无主键模型不支持 get() 方法，抛出明确错误
        if model_class.__primary_key__ is None:
            raise QueryError(
                f"Model '{model_class.__name__}' has no primary key. "
                f"Use select() statement to query records instead.",
                details={'model': model_class.__name__, 'reason': 'no_primary_key'}
            )

        # 先从标识映射查找
        instance = self._get_from_identity_map(model_class, pk)
        if instance is not None:
            return instance

        # 从数据库查询
        table_name = model_class.__tablename__
        assert table_name is not None, f"Model {model_class.__name__} must have __tablename__ defined"

        try:
            # 原生 SQL 模式：直接从数据库查询
            if self.storage._native_sql_mode and self.storage._connector:
                pk_attr_name = model_class.__primary_key__
                # 获取主键的 Column.name
                pk_col_name = pk_attr_name
                if pk_attr_name in model_class.__columns__:
                    pk_column = model_class.__columns__[pk_attr_name]
                    pk_col_name = pk_column.name if pk_column.name else pk_attr_name

                # 使用 query_rows 获取单条记录
                rows = self.storage._connector.query_rows(
                    table_name,
                    where_clause=f'`{pk_col_name}` = ?',
                    params=(pk,),
                    limit=1
                )
                if not rows:
                    return None
                record = rows[0]
            else:
                # 内存模式：从 Table.data 获取
                record = self.storage.get_table(table_name).get(pk)

            # 将 Column.name 转换为属性名
            attr_data = {}
            for db_col_name, value in record.items():
                if db_col_name == PSEUDO_PK_NAME:
                    continue
                attr_name = model_class._column_to_attr_name(db_col_name) or db_col_name
                attr_data[attr_name] = value

            # 创建模型实例
            instance = model_class(**attr_data)

            # 注册到标识映射
            self._register_instance(instance)

            return instance
        except Exception:
            return None

    def refresh(self, instance: T) -> None:
        """
        从数据库刷新实例的所有属性

        类似 SQLAlchemy 的 session.refresh()，重新从数据库加载实例的所有字段值。

        Args:
            instance: 模型实例

        Raises:
            QueryError: 如果实例没有有效的主键或 rowid

        Example:
            user = session.get(User, 1)
            # ... 其他操作可能修改了数据库中的记录 ...
            session.refresh(user)  # 重新加载最新数据
        """
        model_class = instance.__class__
        pk_name = model_class.__primary_key__

        # 获取主键或 rowid
        if pk_name:
            pk_value = getattr(instance, pk_name, None)
        else:
            pk_value = getattr(instance, '_pytuck_rowid', None)

        if pk_value is None:
            raise QueryError(
                "Cannot refresh instance without primary key or rowid",
                details={'model': model_class.__name__}
            )

        table_name = instance.__tablename__
        assert table_name is not None, f"Model {model_class.__name__} must have __tablename__ defined"

        # 从数据库读取记录
        db_record = self.storage.select(table_name, pk_value)

        # 更新实例属性（使用 object.__setattr__ 避免触发脏跟踪）
        for db_col_name, value in db_record.items():
            if db_col_name != PSEUDO_PK_NAME:
                # 将 Column.name 转换回属性名
                attr_name = model_class._column_to_attr_name(db_col_name) or db_col_name
                object.__setattr__(instance, attr_name, value)

    # ==================== 语句执行（带类型重载） ====================

    @overload
    def execute(self, statement: Select[T]) -> Result[T]: ...

    @overload
    def execute(self, statement: Insert[T]) -> CursorResult[T]: ...

    @overload
    def execute(self, statement: Update[T]) -> CursorResult[T]: ...

    @overload
    def execute(self, statement: Delete[T]) -> CursorResult[T]: ...

    def execute(self, statement: Statement) -> Union[Result, CursorResult]:
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
            users = result.all()

            # 插入
            stmt = insert(User).values(name='Alice', age=20)
            result = session.execute(stmt)
            session.commit()
        """
        from ..query.statements import Select, Insert, Update, Delete
        from ..query.result import Result, CursorResult

        # 原生 SQL 模式：使用编译器执行
        if self.storage.is_native_sql_mode:
            return self._execute_native_sql(statement)

        # 内存模式：现有执行路径
        if isinstance(statement, Select):
            records = statement._execute(self.storage)
            # 传递 session 引用给 Result，用于自动注册实例
            return Result(records, statement.model_class, 'select', session=self)

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
            raise QueryError(
                f"Unsupported statement type: {type(statement).__name__}",
                details={'statement_type': type(statement).__name__}
            )

    def _execute_native_sql(self, statement: Statement) -> Union[Result, CursorResult]:
        """
        原生 SQL 模式下执行语句

        使用 SQL 编译器将语句编译为 SQL 并直接在数据库上执行。

        Args:
            statement: Statement 对象

        Returns:
            Result 或 CursorResult
        """
        from ..query.statements import Select, Insert, Update, Delete
        from ..query.compiler import QueryCompiler
        from ..query.result import Result, CursorResult
        import json
        from datetime import datetime, date, timedelta
        from .types import TypeRegistry

        compiler = QueryCompiler()

        assert self.storage._connector is not None, "Connector must not be None in native SQL mode"
        connector = self.storage._connector

        if isinstance(statement, Select):
            # 编译并执行 SELECT
            if compiler.can_compile(statement):
                compiled = compiler.compile(statement)

                # 从编译后的 SQL 中提取 WHERE 部分
                # 使用 connector 的 query_rows 方法
                table = self.storage.get_table(statement.model_class.__tablename__)

                # 构建 order by 字符串
                order_by_str = None
                if statement._order_by_fields:
                    order_parts = []
                    for field, desc in statement._order_by_fields:
                        if desc:
                            order_parts.append(f'`{field}` DESC')
                        else:
                            order_parts.append(f'`{field}` ASC')
                    order_by_str = ', '.join(order_parts)

                # 构建 where 子句（使用编译器处理，支持 LogicalExpression）
                where_sql, params_list = compiler._compile_where(statement)
                where_clause = where_sql if where_sql else None
                params = params_list

                # 执行查询
                rows = connector.query_rows(
                    statement.model_class.__tablename__,
                    where_clause=where_clause,
                    params=tuple(params),
                    order_by=order_by_str,
                    limit=statement._limit_value,
                    offset=statement._offset_value if statement._offset_value > 0 else None
                )

                # 反序列化记录
                records = [self._deserialize_record(row, table.columns) for row in rows]
                return Result(records, statement.model_class, 'select', session=self)

            else:
                # 回退到内存执行
                records = statement._execute(self.storage)
                return Result(records, statement.model_class, 'select', session=self)

        elif isinstance(statement, Insert):
            # 编译并执行 INSERT
            table = self.storage.get_table(statement.model_class.__tablename__)

            # 验证和序列化值（使用 Column.name 作为存储键）
            validated_data = {}
            for attr_name, value in statement._values.items():
                # 将属性名转换为 Column.name
                if attr_name in statement.model_class.__columns__:
                    model_column = statement.model_class.__columns__[attr_name]
                    db_col_name = model_column.name if model_column.name else attr_name
                    if db_col_name in table.columns:
                        column = table.columns[db_col_name]
                        validated_data[db_col_name] = column.validate(value)

            # 获取主键的 Column.name
            pk_attr_name = statement.model_class.__primary_key__
            pk_col_name = pk_attr_name
            if pk_attr_name and pk_attr_name in statement.model_class.__columns__:
                pk_column = statement.model_class.__columns__[pk_attr_name]
                pk_col_name = pk_column.name if pk_column.name else pk_attr_name

            pk = connector.insert_row(
                statement.model_class.__tablename__,
                validated_data,
                pk_col_name
            )

            # 更新 next_id
            if pk is not None and isinstance(pk, int) and pk >= table.next_id:
                table.next_id = pk + 1
                self.storage._dirty = True

            return CursorResult(1, statement.model_class, 'insert', inserted_pk=pk)

        elif isinstance(statement, Update):
            # 编译并执行 UPDATE
            table = self.storage.get_table(statement.model_class.__tablename__)
            pk_attr_name = statement.model_class.__primary_key__

            # 获取主键的 Column.name
            pk_col_name = pk_attr_name
            if pk_attr_name and pk_attr_name in statement.model_class.__columns__:
                pk_column = statement.model_class.__columns__[pk_attr_name]
                pk_col_name = pk_column.name if pk_column.name else pk_attr_name

            # 验证值（使用 Column.name 作为存储键）
            validated_data = {}
            for attr_name, value in statement._values.items():
                # 将属性名转换为 Column.name
                if attr_name in statement.model_class.__columns__:
                    model_column = statement.model_class.__columns__[attr_name]
                    db_col_name = model_column.name if model_column.name else attr_name
                    if db_col_name in table.columns:
                        column = table.columns[db_col_name]
                        validated_data[db_col_name] = column.validate(value)

            # 优化：主键直接更新（仅对简单 BinaryExpression 生效）
            pk_value = None
            if len(statement._where_clauses) == 1:
                expr = statement._where_clauses[0]
                if isinstance(expr, BinaryExpression):
                    # 比较属性名（_attr_name）而非 Column.name
                    if expr.column._attr_name == pk_attr_name and expr.operator in ('=', '=='):
                        pk_value = expr.value

            if pk_value is not None:
                # 主键直接更新
                count = connector.update_row(
                    statement.model_class.__tablename__,
                    pk_col_name,
                    pk_value,
                    validated_data
                )
                return CursorResult(count, statement.model_class, 'update')
            else:
                # 条件更新
                count = statement._execute(self.storage)
                return CursorResult(count, statement.model_class, 'update')

        elif isinstance(statement, Delete):
            # 编译并执行 DELETE
            table = self.storage.get_table(statement.model_class.__tablename__)
            pk_attr_name = statement.model_class.__primary_key__

            # 获取主键的 Column.name
            pk_col_name = pk_attr_name
            if pk_attr_name and pk_attr_name in statement.model_class.__columns__:
                pk_column = statement.model_class.__columns__[pk_attr_name]
                pk_col_name = pk_column.name if pk_column.name else pk_attr_name

            # 优化：主键直接删除（仅对简单 BinaryExpression 生效）
            pk_value = None
            if len(statement._where_clauses) == 1:
                expr = statement._where_clauses[0]
                if isinstance(expr, BinaryExpression):
                    # 比较属性名（_attr_name）而非 Column.name
                    if expr.column._attr_name == pk_attr_name and expr.operator in ('=', '=='):
                        pk_value = expr.value

            if pk_value is not None:
                # 主键直接删除
                count = connector.delete_row(
                    statement.model_class.__tablename__,
                    pk_col_name,
                    pk_value
                )
                return CursorResult(count, statement.model_class, 'delete')
            else:
                # 条件删除
                count = statement._execute(self.storage)
                return CursorResult(count, statement.model_class, 'delete')

        else:
            raise QueryError(
                f"Unsupported statement type: {type(statement).__name__}",
                details={'statement_type': type(statement).__name__}
            )

    @staticmethod
    def _deserialize_record(record: dict, columns: dict) -> dict:
        """
        反序列化数据库记录

        将数据库存储格式转换为 Python 对象。

        Args:
            record: 原始记录字典
            columns: 列定义字典

        Returns:
            反序列化后的记录字典
        """
        from datetime import datetime, date, timedelta
        from .types import TypeRegistry
        import json

        result: dict = {}
        for col_name, value in record.items():
            if col_name in columns and value is not None:
                column = columns[col_name]
                col_type = column.col_type

                if col_type == bool and isinstance(value, int):
                    value = bool(value)
                elif col_type in (datetime, date, timedelta):
                    value = TypeRegistry.deserialize_from_text(value, col_type)
                elif col_type in (list, dict) and isinstance(value, str):
                    value = json.loads(value)

            result[col_name] = value

        return result

    def _register_instance(self, instance: PureBaseModel) -> None:
        """
        注册实例到 identity map

        Args:
            instance: 模型实例
        """
        pk_name = instance.__primary_key__
        if pk_name:
            pk = getattr(instance, pk_name, None)
            if pk is not None:
                key = (instance.__class__, pk)
                self._identity_map[key] = instance
        else:
            # 无主键：使用隐式 rowid
            rowid = getattr(instance, '_pytuck_rowid', None)
            if rowid is not None:
                key = (instance.__class__, (PSEUDO_PK_NAME, rowid))
                self._identity_map[key] = instance

        # 设置实例的 session 引用，用于脏跟踪
        instance._pytuck_session = self
        instance._pytuck_state = 'persistent'

    def _get_from_identity_map(self, model_class: Type[T], pk: Any) -> Optional[T]:
        """
        从 identity map 获取实例

        Args:
            model_class: 模型类
            pk: 主键值

        Returns:
            模型实例，如果不存在返回 None
        """
        key = (model_class, pk)
        return self._identity_map.get(key)  # type: ignore

    def _mark_dirty(self, instance: PureBaseModel) -> None:
        """
        标记实例为 dirty（需要更新）

        Args:
            instance: 模型实例
        """
        if instance not in self._dirty_objects and instance not in self._new_objects:
            self._dirty_objects.append(instance)

    def merge(self, instance: T) -> T:
        """
        合并一个 detached 实例到会话中

        这个方法会检查实例是否已存在于 identity map 中：
        - 如果存在，更新现有实例的属性并返回现有实例
        - 如果不存在，从数据库加载或创建新实例，然后更新属性

        对于无主键模型，只能通过内部 rowid 来查找 identity map。
        如果没有 rowid，则作为新对象处理。

        Args:
            instance: 要合并的模型实例

        Returns:
            会话管理的实例（可能不是传入的同一个对象）

        Example:
            # 从外部来源获得的数据
            external_user = User(id=1, name="Updated Name", age=25)

            # 合并到会话
            managed_user = session.merge(external_user)
            session.commit()  # 提交更新
        """
        model_class = instance.__class__
        pk_name = model_class.__primary_key__

        # 获取主键值或 rowid
        if pk_name:
            pk_value = getattr(instance, pk_name, None)
        else:
            # 无主键模型：尝试获取 rowid
            pk_value = getattr(instance, '_pytuck_rowid', None)

        if pk_value is None:
            # 没有主键/rowid，作为新对象处理
            self.add(instance)
            return instance

        # 尝试从 identity map 获取现有实例
        if pk_name:
            existing = self._get_from_identity_map(model_class, pk_value)
        else:
            # 无主键模型使用特殊的 key 格式
            key = (model_class, (PSEUDO_PK_NAME, pk_value))
            existing = self._identity_map.get(key)  # type: ignore

        if existing is not None:
            # 已存在，更新其属性
            for col_name, column in model_class.__columns__.items():
                if hasattr(instance, col_name):
                    value = getattr(instance, col_name)
                    if getattr(existing, col_name) != value:
                        setattr(existing, col_name, value)
            return existing

        # 不存在于 identity map
        if pk_name:
            # 有主键：尝试从数据库加载
            existing = self.get(model_class, pk_value)

            if existing is not None:
                # 从数据库加载成功，更新属性
                for col_name, column in model_class.__columns__.items():
                    if hasattr(instance, col_name):
                        value = getattr(instance, col_name)
                        if getattr(existing, col_name) != value:
                            setattr(existing, col_name, value)
                return existing

        # 数据库中也不存在（或无主键模型），作为新对象处理
        self.add(instance)
        return instance

    def query(self, model_class: Type[T]) -> Query[T]:
        """
        创建查询构建器（SQLAlchemy 1.4 风格，不推荐，但也不警告）

        ⚠️ 不推荐使用：请改用 session.execute(select(...)) 风格

        推荐写法：
            from pytuck import select
            stmt = select(User).where(User.age >= 18)
            result = session.execute(stmt)
            users = result.all()

        旧写法（将依旧持续支持）：
            users = session.query(User).filter(User.age >= 18).all()

        Args:
            model_class: 模型类

        Returns:
            Query 对象
        """
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
            raise TransactionError("Nested transactions are not supported in Session")

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

    def __exit__(self, exc_type: Optional[Type[BaseException]], exc_val: Optional[BaseException], exc_tb: Any) -> None:
        """上下文管理器出口"""
        if exc_type is None:
            self.commit()
        else:
            self.rollback()

    # ==================== Schema 操作（面向模型） ====================

    @staticmethod
    def _resolve_table_name(model_or_table: Union[Type[PureBaseModel], str]) -> str:
        """
        解析表名

        Args:
            model_or_table: 模型类或表名字符串

        Returns:
            表名字符串
        """
        if isinstance(model_or_table, str):
            return model_or_table
        else:
            table_name = model_or_table.__tablename__
            assert table_name is not None, f"Model {model_or_table.__name__} must have __tablename__ defined"
            return table_name

    def sync_schema(
        self,
        model_class: Type[PureBaseModel],
        options: Optional[SyncOptions] = None
    ) -> SyncResult:
        """
        同步模型到数据库表结构

        从模型类中提取列定义，与数据库中的表结构对比并同步。

        Args:
            model_class: 模型类
            options: 同步选项

        Returns:
            SyncResult: 同步结果

        Example:
            from pytuck import SyncOptions

            result = session.sync_schema(User)
            if result.has_changes:
                print(f"Added columns: {result.columns_added}")

            # 自定义选项
            opts = SyncOptions(sync_column_comments=False)
            result = session.sync_schema(User, options=opts)
        """
        table_name = self._resolve_table_name(model_class)
        columns = list(model_class.__columns__.values())
        comment = getattr(model_class, '__table_comment__', None)
        return self.storage.sync_table_schema(table_name, columns, comment, options)

    def add_column(
        self,
        model_or_table: Union[Type[PureBaseModel], str],
        column: Column,
        default_value: Any = None
    ) -> None:
        """
        添加列

        Args:
            model_or_table: 模型类或表名字符串
            column: 列定义
            default_value: 为现有记录填充的默认值

        Example:
            from pytuck import Column

            # 通过模型类
            session.add_column(User, Column(int, nullable=True, name='age'))

            # 通过表名
            session.add_column('users', Column(int, nullable=True, name='age'))

            # 带默认值
            session.add_column(User, Column(str, name='status'), default_value='active')
        """
        table_name = self._resolve_table_name(model_or_table)
        self.storage.add_column(table_name, column, default_value)

    def drop_column(
        self,
        model_or_table: Union[Type[PureBaseModel], str],
        column_name: str
    ) -> None:
        """
        删除列

        Args:
            model_or_table: 模型类或表名字符串
            column_name: 字段名（Column.name），而非 Python 属性名

        Example:
            # 通过模型类
            session.drop_column(User, 'old_field')

            # 通过表名
            session.drop_column('users', 'old_field')

            # 属性名与字段名不一致时，使用字段名
            # 定义：student_no = Column(str, name="Student No.")
            session.drop_column(Student, "Student No.")  # 正确
            # session.drop_column(Student, "student_no")  # 错误！
        """
        table_name = self._resolve_table_name(model_or_table)
        self.storage.drop_column(table_name, column_name)

    def update_table_comment(
        self,
        model_or_table: Union[Type[PureBaseModel], str],
        comment: Optional[str]
    ) -> None:
        """
        更新表备注

        Args:
            model_or_table: 模型类或表名字符串
            comment: 新的表备注

        Example:
            session.update_table_comment(User, '用户信息表')
            session.update_table_comment('users', '用户信息表')
        """
        table_name = self._resolve_table_name(model_or_table)
        self.storage.update_table_comment(table_name, comment)

    def update_column(
        self,
        model_or_table: Union[Type[PureBaseModel], str],
        column_name: str,
        comment: Optional[str] = None,
        index: Optional[bool] = None
    ) -> None:
        """
        更新列属性

        Args:
            model_or_table: 模型类或表名字符串
            column_name: 字段名（Column.name），而非 Python 属性名
            comment: 新的列备注（None 表示不修改）
            index: 是否索引（None 表示不修改）

        Example:
            # 更新备注
            session.update_column(User, 'name', comment='用户名')

            # 添加索引
            session.update_column(User, 'email', index=True)

            # 同时更新
            session.update_column('users', 'phone', comment='电话号码', index=True)

            # 属性名与字段名不一致时，使用字段名
            # 定义：student_no = Column(str, name="Student No.")
            session.update_column(Student, "Student No.", comment="学号")
        """
        table_name = self._resolve_table_name(model_or_table)
        self.storage.update_column(table_name, column_name, comment, index)

    def drop_table(self, model_or_table: Union[Type[PureBaseModel], str]) -> None:
        """
        删除表

        Args:
            model_or_table: 模型类或表名字符串

        Example:
            session.drop_table(TempData)
            session.drop_table('temp_data')
        """
        table_name = self._resolve_table_name(model_or_table)
        self.storage.drop_table(table_name)

    def rename_table(
        self,
        old_model_or_table: Union[Type[PureBaseModel], str],
        new_name: str
    ) -> None:
        """
        重命名表

        Args:
            old_model_or_table: 旧模型类或表名
            new_name: 新表名

        Example:
            session.rename_table(User, 'user_accounts')
            session.rename_table('users', 'user_accounts')
        """
        old_name = self._resolve_table_name(old_model_or_table)
        self.storage.rename_table(old_name, new_name)
