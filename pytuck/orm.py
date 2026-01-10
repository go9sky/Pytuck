"""
Pytuck ORM层

提供对象关系映射功能，支持两种模式：
- PureBaseModel: 纯模型定义，通过 Session 操作数据
- CRUDBaseModel: Active Record 模式，模型自带 CRUD 方法
"""
import sys
from typing import (
    Any, Dict, List, Optional, Type, Union, TYPE_CHECKING,
    overload, Literal, Tuple
)

from .exceptions import ValidationError
from .types import TypeCode, TypeRegistry

if TYPE_CHECKING:
    from .storage import Storage
    from .query import Query, BinaryExpression


class Column:
    """列定义"""
    __slots__ = ['name', 'col_type', 'nullable', 'primary_key',
                 'index', 'default', 'foreign_key', '_type_code',
                 '_attr_name', '_owner_class']

    def __init__(self,
                 name: str,
                 col_type: Type,
                 nullable: bool = True,
                 primary_key: bool = False,
                 index: bool = False,
                 default: Any = None,
                 foreign_key: Optional[tuple] = None):
        """
        初始化列定义

        Args:
            name: 列名
            col_type: Python类型（int, str, float, bool, bytes）
            nullable: 是否可空
            primary_key: 是否为主键
            index: 是否建立索引
            default: 默认值
            foreign_key: 外键关系 (table_name, column_name)
        """
        self.name = name
        self.col_type = col_type
        self.nullable = nullable
        self.primary_key = primary_key
        self.index = index
        self.default = default
        self.foreign_key = foreign_key

        # 获取类型编码
        try:
            self._type_code, _ = TypeRegistry.get_codec(col_type)
        except Exception as e:
            raise ValidationError(f"Unsupported column type {col_type}: {e}")

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'name': self.name,
            'type': self.col_type.__name__,
            'type_code': int(self._type_code),
            'nullable': self.nullable,
            'primary_key': self.primary_key,
            'index': self.index,
            'default': self.default,
            'foreign_key': self.foreign_key,
        }

    def validate(self, value: Any) -> Any:
        """
        验证并处理值

        Args:
            value: 要验证的值

        Returns:
            处理后的值

        Raises:
            ValidationError: 验证失败
        """
        # 处理None值
        if value is None:
            if not self.nullable and not self.primary_key:
                raise ValidationError(f"Column '{self.name}' cannot be null")
            return None

        # 类型检查（bool要放在int前面，因为bool是int的子类）
        if self.col_type == bool:
            if not isinstance(value, bool):
                raise ValidationError(
                    f"Column '{self.name}' expects type {self.col_type.__name__}, got {type(value).__name__}"
                )
        elif not isinstance(value, self.col_type):
            # 尝试类型转换
            try:
                value = self.col_type(value)
            except (ValueError, TypeError):
                raise ValidationError(
                    f"Column '{self.name}' expects type {self.col_type.__name__}, got {type(value).__name__}"
                )

        return value

    def __repr__(self) -> str:
        return f"Column(name='{self.name}', type={self.col_type.__name__}, pk={self.primary_key})"

    # ==================== 描述符协议 ====================

    def __set_name__(self, owner: Type['PureBaseModel'], name: str) -> None:
        """
        在类定义时被调用，存储属性名和拥有者类

        这允许 Column 知道它属于哪个模型类
        """
        self._attr_name = name
        self._owner_class = owner

    def __get__(self, instance: Optional['PureBaseModel'], owner: Type['PureBaseModel']) -> Union['Column', Any]:
        """
        描述符协议：
        - 类访问（instance=None）：返回 Column 对象（用于查询）
        - 实例访问：返回实例属性的值
        """
        if instance is None:
            # 类级别访问：Student.age -> Column 对象
            return self

        # 实例级别访问：student.age -> 实际值
        return instance.__dict__.get(self._attr_name, None)

    def __set__(self, instance: 'PureBaseModel', value: Any) -> None:
        """设置实例属性值"""
        validated_value = self.validate(value)
        instance.__dict__[self._attr_name] = validated_value

    # ==================== 查询表达式支持（魔术方法） ====================

    def __eq__(self, other: Any) -> 'BinaryExpression':
        """等于：Student.age == 20"""
        from .query import BinaryExpression
        return BinaryExpression(self, '=', other)

    def __ne__(self, other: Any) -> 'BinaryExpression':
        """不等于：Student.age != 20"""
        from .query import BinaryExpression
        return BinaryExpression(self, '!=', other)

    def __lt__(self, other: Any) -> 'BinaryExpression':
        """小于：Student.age < 20"""
        from .query import BinaryExpression
        return BinaryExpression(self, '<', other)

    def __le__(self, other: Any) -> 'BinaryExpression':
        """小于等于：Student.age <= 20"""
        from .query import BinaryExpression
        return BinaryExpression(self, '<=', other)

    def __gt__(self, other: Any) -> 'BinaryExpression':
        """大于：Student.age > 20"""
        from .query import BinaryExpression
        return BinaryExpression(self, '>', other)

    def __ge__(self, other: Any) -> 'BinaryExpression':
        """大于等于：Student.age >= 20"""
        from .query import BinaryExpression
        return BinaryExpression(self, '>=', other)

    def in_(self, values: list) -> 'BinaryExpression':
        """IN 操作：Student.age.in_([18, 19, 20])"""
        from .query import BinaryExpression
        return BinaryExpression(self, 'IN', values)


# ==================== 模型基类定义 ====================

class PureBaseModel:
    """
    纯模型基类 - 仅定义数据结构

    这是一个真实的基类，declarative_base() 返回的类会继承它。
    可用于 isinstance() 检查和类型注解。

    通过 Session 进行所有数据库操作：

        from pytuck import Storage, declarative_base, Session, Column
        from pytuck import PureBaseModel
        from typing import Type

        db = Storage(file_path='mydb.db')
        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column('id', int, primary_key=True)
            name = Column('name', str)

        user = User(name='Alice')
        isinstance(user, PureBaseModel)  # True

        session = Session(db)
        session.add(user)
        session.commit()
    """

    # 类属性
    __abstract__: bool = True
    __storage__: 'Storage' = None
    __tablename__: Optional[str] = None
    __columns__: Dict[str, Column] = {}
    __primary_key__: str = 'id'
    __relationships__: Dict[str, 'Relationship'] = {}

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        data = {}
        for col_name in self.__columns__:
            data[col_name] = getattr(self, col_name, None)
        return data

    def __repr__(self) -> str:
        """字符串表示"""
        pk_value = getattr(self, self.__primary_key__, None)
        return f"<{self.__class__.__name__}(pk={pk_value})>"


class CRUDBaseModel(PureBaseModel):
    """
    Active Record 基类 - 模型自带 CRUD 方法

    这是一个真实的基类，declarative_base(crud=True) 返回的类会继承它。
    可用于 isinstance() 检查和类型注解。

    可以直接在模型实例/类上进行数据库操作：

        from pytuck import Storage, declarative_base, Column
        from pytuck import CRUDBaseModel
        from typing import Type

        db = Storage(file_path='mydb.db')
        Base: Type[CRUDBaseModel] = declarative_base(db, crud=True)

        class User(Base):
            __tablename__ = 'users'
            id = Column('id', int, primary_key=True)
            name = Column('name', str)

        user = User.create(name='Alice')
        isinstance(user, CRUDBaseModel)  # True
        isinstance(user, PureBaseModel)  # True（继承关系）

        user.name = 'Bob'
        user.save()
        user.delete()
    """

    # 实例状态
    _loaded_from_db: bool = False
    _pk_value: Any = None

    # ==================== 实例方法 ====================

    def save(self) -> None:
        """
        保存记录（自动判断 insert 或 update）

        Example:
            user = User(name='Alice')
            user.save()  # INSERT
            user.name = 'Bob'
            user.save()  # UPDATE
        """
        raise NotImplementedError("This method should be overridden by declarative_base")

    def delete(self) -> None:
        """
        删除当前记录

        Example:
            user = User.get(1)
            user.delete()
        """
        raise NotImplementedError("This method should be overridden by declarative_base")

    def refresh(self) -> None:
        """
        从数据库刷新当前实例

        Example:
            user = User.get(1)
            # 数据库中被其他进程修改
            user.refresh()  # 获取最新数据
        """
        raise NotImplementedError("This method should be overridden by declarative_base")

    # ==================== 类方法 ====================

    @classmethod
    def create(cls, **kwargs: Any) -> 'CRUDBaseModel':
        """
        创建并保存新记录

        Example:
            user = User.create(name='Alice', age=20)
        """
        raise NotImplementedError("This method should be overridden by declarative_base")

    @classmethod
    def get(cls, pk: Any) -> Optional['CRUDBaseModel']:
        """
        根据主键获取记录

        Example:
            user = User.get(1)
        """
        raise NotImplementedError("This method should be overridden by declarative_base")

    @classmethod
    def filter(cls, *expressions: 'BinaryExpression') -> 'Query':
        """
        条件查询（表达式语法）

        Example:
            users = User.filter(User.age >= 18).all()
        """
        raise NotImplementedError("This method should be overridden by declarative_base")

    @classmethod
    def filter_by(cls, **kwargs: Any) -> 'Query':
        """
        简单等值查询

        Example:
            users = User.filter_by(name='Alice').all()
        """
        raise NotImplementedError("This method should be overridden by declarative_base")

    @classmethod
    def all(cls) -> List['CRUDBaseModel']:
        """
        获取所有记录

        Example:
            users = User.all()
        """
        raise NotImplementedError("This method should be overridden by declarative_base")


class Relationship:
    """关联关系描述符（延迟加载）"""

    def __init__(self,
                 target_model: Union[str, Type[PureBaseModel]],
                 foreign_key: str,
                 lazy: bool = True,
                 back_populates: Optional[str] = None):
        """
        初始化关联关系

        Args:
            target_model: 目标模型类或类名（字符串）
            foreign_key: 外键字段名
            lazy: 是否延迟加载
            back_populates: 反向关联的属性名
        """
        self.target_model = target_model
        self.foreign_key = foreign_key
        self.lazy = lazy
        self.back_populates = back_populates
        self.is_one_to_many = False
        self.name = None
        self.owner = None

    def __set_name__(self, owner: Type[PureBaseModel], name: str) -> None:
        """在类定义时调用"""
        self.name = name
        self.owner = owner

        # 判断是一对多还是多对一
        # 如果外键在目标模型中，则是一对多
        # 如果外键在当前模型中，则是多对一
        columns = getattr(owner, '__columns__', {})
        if self.foreign_key in columns:
            self.is_one_to_many = False
        else:
            self.is_one_to_many = True

    def __get__(self, instance: Optional[PureBaseModel], owner: Type[PureBaseModel]) -> Union['Relationship', Optional[PureBaseModel], List[PureBaseModel]]:
        """获取关联对象"""
        if instance is None:
            return self

        # 检查缓存
        cache_key = f'_cached_{self.name}'
        if hasattr(instance, cache_key):
            return getattr(instance, cache_key)

        # 延迟加载
        target_model = self._resolve_target_model()

        primary_key = getattr(owner, '__primary_key__', 'id')

        if self.is_one_to_many:
            # 反向关联：查询外键指向当前实例的所有记录
            pk_value = getattr(instance, primary_key)
            # 使用 filter_by（如果目标模型支持）
            if hasattr(target_model, 'filter_by'):
                results: Union[Optional[PureBaseModel], List[PureBaseModel]] = target_model.filter_by(**{
                    self.foreign_key: pk_value
                }).all()
            else:
                results = []
        else:
            # 正向关联：根据外键值查询目标对象
            fk_value = getattr(instance, self.foreign_key)
            if fk_value is None:
                results = None
            elif hasattr(target_model, 'get'):
                results = target_model.get(fk_value)
            else:
                results = None

        # 缓存结果
        setattr(instance, cache_key, results)
        return results

    def _resolve_target_model(self) -> Type[PureBaseModel]:
        """解析目标模型"""
        if isinstance(self.target_model, str):
            # 字符串形式的模型名，从owner的模块中查找
            owner_module = sys.modules[self.owner.__module__]
            if hasattr(owner_module, self.target_model):
                return getattr(owner_module, self.target_model)
            else:
                raise ValidationError(f"Cannot find model '{self.target_model}'")
        else:
            return self.target_model

    def __repr__(self) -> str:
        return f"Relationship(target={self.target_model}, fk={self.foreign_key})"


# ==================== 工厂函数 ====================

@overload
def declarative_base(
    storage: 'Storage',
    *,
    crud: Literal[False] = ...
) -> Type[PureBaseModel]: ...


@overload
def declarative_base(
    storage: 'Storage',
    *,
    crud: Literal[True]
) -> Type[CRUDBaseModel]: ...


def declarative_base(
    storage: 'Storage',
    *,
    crud: bool = False
) -> Union[Type[PureBaseModel], Type[CRUDBaseModel]]:
    """
    创建声明式基类工厂函数

    这是 SQLAlchemy 风格 API，用于创建绑定特定 Storage 的声明式基类。
    所有模型应继承自此函数返回的 Base 类。

    Args:
        storage: Storage 实例，用于绑定数据库连接
        crud: 是否包含 CRUD 方法（默认 False）
            - False: 返回 PureBaseModel 类型（纯模型定义，通过 Session 操作）
            - True: 返回 CRUDBaseModel 类型（Active Record 模式，模型自带 CRUD）

    Returns:
        基类类型

    Examples:
        # 纯模型（默认，推荐）
        from typing import Type
        from pytuck import PureBaseModel

        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column('id', int, primary_key=True)
            name = Column('name', str)

        # 通过 Session 操作
        session = Session(db)
        user = User(name='Alice')
        session.add(user)
        session.commit()

        # Active Record 模式
        from pytuck import CRUDBaseModel

        Base: Type[CRUDBaseModel] = declarative_base(db, crud=True)

        class Post(Base):
            __tablename__ = 'posts'
            id = Column('id', int, primary_key=True)
            title = Column('title', str)

        # 直接在模型上操作
        post = Post.create(title='Hello')
        post.title = 'Updated'
        post.save()
        post.delete()
    """

    if crud:
        return _create_crud_base(storage)
    else:
        return _create_pure_base(storage)


def _create_pure_base(storage: 'Storage') -> Type[PureBaseModel]:
    """创建纯模型基类"""

    class DeclarativePureBase(PureBaseModel):
        """声明式纯模型基类"""

        # 类属性
        __abstract__ = True
        __storage__ = storage
        __tablename__: Optional[str] = None
        __columns__: Dict[str, Column] = {}
        __primary_key__: str = 'id'
        __relationships__: Dict[str, Relationship] = {}

        def __init_subclass__(cls, **kwargs: Any):
            """子类初始化时自动收集字段并创建表"""
            super().__init_subclass__(**kwargs)

            # 跳过抽象类
            if cls.__dict__.get('__abstract__', False):
                return

            # 子类必须定义 __tablename__
            if not hasattr(cls, '__tablename__') or cls.__tablename__ is None:
                raise ValidationError(
                    f"Model {cls.__name__} must define __tablename__"
                )

            # 收集列定义
            cls.__columns__ = {}
            cls.__relationships__ = {}

            for attr_name, attr_value in list(cls.__dict__.items()):
                if isinstance(attr_value, Column):
                    cls.__columns__[attr_name] = attr_value
                    if attr_value.primary_key:
                        cls.__primary_key__ = attr_name
                elif isinstance(attr_value, Relationship):
                    cls.__relationships__[attr_name] = attr_value
                    attr_value.__set_name__(cls, attr_name)

            # 自动创建表
            if cls.__columns__:
                try:
                    columns_list = list(cls.__columns__.values())
                    storage.create_table(cls.__tablename__, columns_list)
                except Exception:
                    # 表可能已存在，忽略
                    pass

        def __init__(self, **kwargs: Any):
            """初始化模型实例"""
            for col_name, column in self.__columns__.items():
                if col_name in kwargs:
                    value = column.validate(kwargs[col_name])
                    setattr(self, col_name, value)
                elif column.default is not None:
                    setattr(self, col_name, column.default)
                elif column.nullable or column.primary_key:
                    setattr(self, col_name, None)
                else:
                    raise ValidationError(f"Missing required column '{col_name}'")

        def to_dict(self) -> Dict[str, Any]:
            """转换为字典"""
            data = {}
            for col_name in self.__columns__:
                data[col_name] = getattr(self, col_name, None)
            return data

        def __repr__(self) -> str:
            """字符串表示"""
            pk_value = getattr(self, self.__primary_key__, None)
            return f"<{self.__class__.__name__}(pk={pk_value})>"

    return DeclarativePureBase  # type: ignore


def _create_crud_base(storage: 'Storage') -> Type[CRUDBaseModel]:
    """创建带 CRUD 方法的模型基类"""

    class DeclarativeCRUDBase(CRUDBaseModel):
        """声明式 CRUD 模型基类"""

        # 类属性
        __abstract__ = True
        __storage__ = storage
        __tablename__: Optional[str] = None
        __columns__: Dict[str, Column] = {}
        __primary_key__: str = 'id'
        __relationships__: Dict[str, Relationship] = {}

        def __init_subclass__(cls, **kwargs: Any):
            """子类初始化时自动收集字段并创建表"""
            super().__init_subclass__(**kwargs)

            # 跳过抽象类
            if cls.__dict__.get('__abstract__', False):
                return

            # 子类必须定义 __tablename__
            if not hasattr(cls, '__tablename__') or cls.__tablename__ is None:
                raise ValidationError(
                    f"Model {cls.__name__} must define __tablename__"
                )

            # 收集列定义
            cls.__columns__ = {}
            cls.__relationships__ = {}

            for attr_name, attr_value in list(cls.__dict__.items()):
                if isinstance(attr_value, Column):
                    cls.__columns__[attr_name] = attr_value
                    if attr_value.primary_key:
                        cls.__primary_key__ = attr_name
                elif isinstance(attr_value, Relationship):
                    cls.__relationships__[attr_name] = attr_value
                    attr_value.__set_name__(cls, attr_name)

            # 自动创建表
            if cls.__columns__:
                try:
                    columns_list = list(cls.__columns__.values())
                    storage.create_table(cls.__tablename__, columns_list)
                except Exception:
                    # 表可能已存在，忽略
                    pass

        def __init__(self, **kwargs: Any):
            """初始化模型实例"""
            self._loaded_from_db = False
            self._pk_value = None

            for col_name, column in self.__columns__.items():
                if col_name in kwargs:
                    value = column.validate(kwargs[col_name])
                    setattr(self, col_name, value)
                elif column.default is not None:
                    setattr(self, col_name, column.default)
                elif column.nullable or column.primary_key:
                    setattr(self, col_name, None)
                else:
                    raise ValidationError(f"Missing required column '{col_name}'")

        def to_dict(self) -> Dict[str, Any]:
            """转换为字典"""
            data = {}
            for col_name in self.__columns__:
                data[col_name] = getattr(self, col_name, None)
            return data

        def __repr__(self) -> str:
            """字符串表示"""
            pk_value = getattr(self, self.__primary_key__, None)
            return f"<{self.__class__.__name__}(pk={pk_value})>"

        # ==================== 实例方法 ====================

        def save(self) -> None:
            """保存记录（insert or update）"""
            # 准备数据
            data = {}
            for col_name in self.__columns__:
                value = getattr(self, col_name, None)
                data[col_name] = value

            # 判断是insert还是update
            pk_value = getattr(self, self.__primary_key__)

            if pk_value is None or not self._loaded_from_db:
                # Insert
                pk_value = storage.insert(self.__tablename__, data)
                setattr(self, self.__primary_key__, pk_value)
                self._pk_value = pk_value
                self._loaded_from_db = True
            else:
                # Update
                storage.update(self.__tablename__, pk_value, data)

        def delete(self) -> None:
            """删除当前记录"""
            pk_value = getattr(self, self.__primary_key__)
            if pk_value is None:
                raise ValidationError("Cannot delete record without primary key")

            storage.delete(self.__tablename__, pk_value)
            self._loaded_from_db = False

        def refresh(self) -> None:
            """从数据库刷新数据"""
            pk_value = getattr(self, self.__primary_key__)
            if pk_value is None:
                raise ValidationError("Cannot refresh record without primary key")

            data = storage.select(self.__tablename__, pk_value)

            for col_name, value in data.items():
                setattr(self, col_name, value)

        # ==================== 类方法 ====================

        @classmethod
        def create(cls, **kwargs: Any) -> 'DeclarativeCRUDBase':
            """创建并保存新记录"""
            instance = cls(**kwargs)
            instance.save()
            return instance

        @classmethod
        def get(cls, pk: Any) -> Optional['DeclarativeCRUDBase']:
            """根据主键获取记录"""
            try:
                data = storage.select(cls.__tablename__, pk)
                instance = cls(**data)
                instance._loaded_from_db = True
                instance._pk_value = pk
                return instance
            except Exception:
                return None

        @classmethod
        def filter(cls, *expressions: 'BinaryExpression') -> 'Query':
            """
            条件查询（表达式语法）

            Args:
                *expressions: BinaryExpression 对象

            Returns:
                Query 对象

            Example:
                users = User.filter(User.age >= 18).all()
            """
            from .query import Query
            query = Query(cls)
            if expressions:
                query = query.filter(*expressions)
            return query

        @classmethod
        def filter_by(cls, **kwargs: Any) -> 'Query':
            """
            简单等值查询

            Args:
                **kwargs: 字段名=值 的等值条件

            Returns:
                Query 对象

            Example:
                users = User.filter_by(name='Alice').all()
            """
            from .query import Query
            query = Query(cls)
            if kwargs:
                query = query.filter_by(**kwargs)
            return query

        @classmethod
        def all(cls) -> List['DeclarativeCRUDBase']:
            """获取所有记录"""
            from .query import Query
            return Query(cls).all()

    return DeclarativeCRUDBase  # type: ignore
