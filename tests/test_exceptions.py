"""
异常处理测试

测试方法：
- 等价类划分：各异常类型的触发条件
- 场景设计：完整的异常抛出和捕获流程
- 错误推断：异常继承关系和属性

覆盖范围：
- 异常继承层次结构
- 各异常类的触发条件
- 异常消息和属性
- to_dict 序列化
"""

import pytest
from typing import Type

from pytuck import (
    Storage, Session, Column, declarative_base,
    PureBaseModel, select, insert, update, delete,
    # 所有异常类
    PytuckException,
    TableNotFoundError,
    RecordNotFoundError,
    DuplicateKeyError,
    ColumnNotFoundError,
    ValidationError,
    TypeConversionError,
    ConfigurationError,
    SchemaError,
    QueryError,
    TransactionError,
    DatabaseConnectionError,
    SerializationError,
    EncryptionError,
    MigrationError,
    PytuckIndexError,
    UnsupportedOperationError,
)


class TestExceptionHierarchy:
    """异常继承关系测试"""

    def test_all_exceptions_inherit_from_base(self):
        """所有异常都继承自 PytuckException"""
        exception_classes = [
            TableNotFoundError,
            RecordNotFoundError,
            DuplicateKeyError,
            ColumnNotFoundError,
            ValidationError,
            TypeConversionError,
            ConfigurationError,
            SchemaError,
            QueryError,
            TransactionError,
            DatabaseConnectionError,
            SerializationError,
            EncryptionError,
            MigrationError,
            PytuckIndexError,
            UnsupportedOperationError,
        ]
        for exc_class in exception_classes:
            assert issubclass(exc_class, PytuckException), \
                f"{exc_class.__name__} should inherit from PytuckException"

    def test_type_conversion_error_inherits_validation_error(self):
        """TypeConversionError 继承自 ValidationError"""
        assert issubclass(TypeConversionError, ValidationError)

    def test_schema_error_inherits_configuration_error(self):
        """SchemaError 继承自 ConfigurationError"""
        assert issubclass(SchemaError, ConfigurationError)

    def test_catch_base_catches_subclass(self):
        """捕获 PytuckException 可以捕获所有子异常"""
        # 测试表不存在异常
        try:
            raise TableNotFoundError("users")
        except PytuckException as e:
            assert "users" in str(e)
            assert e.table_name == "users"

        # 测试验证异常
        try:
            raise ValidationError("Invalid data", column_name="age")
        except PytuckException as e:
            assert e.column_name == "age"

    def test_catch_validation_catches_type_conversion(self):
        """捕获 ValidationError 可以捕获 TypeConversionError"""
        try:
            raise TypeConversionError(
                "Cannot convert 'abc' to int",
                value="abc",
                target_type="int"
            )
        except ValidationError as e:
            assert "abc" in str(e)
            assert e.value == "abc"
            assert e.target_type == "int"


class TestExceptionAttributes:
    """异常属性测试"""

    def test_pytuck_exception_basic_attributes(self):
        """基类异常的基本属性"""
        exc = PytuckException(
            "Test message",
            table_name="users",
            column_name="age",
            pk=123,
            details={"key": "value"}
        )
        assert exc.message == "Test message"
        assert exc.table_name == "users"
        assert exc.column_name == "age"
        assert exc.pk == 123
        assert exc.details == {"key": "value"}
        assert str(exc) == "Test message"

    def test_exception_to_dict(self):
        """异常 to_dict 方法"""
        exc = TableNotFoundError("users")
        d = exc.to_dict()

        assert d["error"] == "TableNotFoundError"
        assert d["message"] == "Table 'users' not found"
        assert d["table_name"] == "users"

    def test_type_conversion_error_to_dict(self):
        """TypeConversionError 的详细信息"""
        exc = TypeConversionError(
            "Cannot convert 'abc' to int",
            value="abc",
            target_type="int",
            column_name="age"
        )
        d = exc.to_dict()

        assert d["error"] == "TypeConversionError"
        assert "details" in d
        assert d["details"]["value"] == "'abc'"
        assert d["details"]["value_type"] == "str"
        assert d["details"]["target_type"] == "int"

    def test_exception_repr(self):
        """异常 repr 表示"""
        exc = DuplicateKeyError("users", 123)
        # 默认的 Exception repr 包含消息
        assert "Duplicate primary key '123'" in repr(exc)


class TestTableNotFoundError:
    """TableNotFoundError 触发测试"""

    def test_access_nonexistent_table(self, tmp_path):
        """访问不存在的表"""
        db_path = tmp_path / "test.db"
        db = Storage(file_path=str(db_path))

        with pytest.raises(TableNotFoundError) as exc_info:
            db.get_table("nonexistent")

        assert exc_info.value.table_name == "nonexistent"
        db.close()

    def test_session_execute_on_nonexistent_table(self, tmp_path):
        """Session 操作不存在的表"""
        db_path = tmp_path / "test.db"
        db = Storage(file_path=str(db_path))

        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        # declarative_base 会自动注册模型，查询空表应返回空列表
        session = Session(db)
        result = session.execute(select(User)).all()
        assert result == []

        session.close()
        db.close()


class TestRecordNotFoundError:
    """RecordNotFoundError 触发测试"""

    def test_get_nonexistent_record(self, tmp_path):
        """获取不存在的记录返回 None"""
        db_path = tmp_path / "test.db"
        db = Storage(file_path=str(db_path))

        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        # declarative_base 自动注册模型
        session = Session(db)

        # get 返回 None，不抛异常
        result = session.get(User, 999)
        assert result is None

        session.close()
        db.close()

    def test_record_not_found_error_attributes(self):
        """RecordNotFoundError 属性"""
        exc = RecordNotFoundError("users", 123)
        assert exc.table_name == "users"
        assert exc.pk == 123
        assert "123" in str(exc)
        assert "users" in str(exc)


class TestDuplicateKeyError:
    """DuplicateKeyError 触发测试"""

    def test_insert_duplicate_primary_key(self, tmp_path):
        """插入重复主键"""
        db_path = tmp_path / "test.db"
        db = Storage(file_path=str(db_path))

        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        # declarative_base 自动注册模型
        session = Session(db)

        # 插入第一条记录
        session.execute(insert(User).values(id=1, name='Alice'))
        session.commit()

        # 插入重复主键
        with pytest.raises(DuplicateKeyError) as exc_info:
            session.execute(insert(User).values(id=1, name='Bob'))
            session.commit()

        assert exc_info.value.pk == 1
        assert exc_info.value.table_name == 'users'

        session.close()
        db.close()

    def test_duplicate_key_error_attributes(self):
        """DuplicateKeyError 属性"""
        exc = DuplicateKeyError("users", 42)
        assert exc.table_name == "users"
        assert exc.pk == 42
        assert "42" in str(exc)
        assert "Duplicate" in str(exc)


class TestValidationError:
    """ValidationError 触发测试"""

    def test_validation_error_with_details(self):
        """带详细信息的验证错误"""
        exc = ValidationError(
            "Field 'email' is invalid",
            table_name="users",
            column_name="email",
            details={"pattern": r"^\S+@\S+\.\S+$"}
        )
        assert exc.table_name == "users"
        assert exc.column_name == "email"
        assert exc.details["pattern"] == r"^\S+@\S+\.\S+$"


class TestTypeConversionError:
    """TypeConversionError 触发测试"""

    def test_invalid_int_conversion(self, tmp_path):
        """无效的整数转换抛出 ValidationError"""
        db_path = tmp_path / "test.db"
        db = Storage(file_path=str(db_path))

        Base: Type[PureBaseModel] = declarative_base(db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            age = Column(int)

        # declarative_base 自动注册模型
        session = Session(db)

        # 尝试插入无法转换的值（Column.validate 抛出 ValidationError）
        with pytest.raises(ValidationError) as exc_info:
            session.execute(insert(User).values(id=1, age='not_a_number'))

        assert "Cannot convert" in str(exc_info.value)

        session.close()
        db.close()

    def test_type_conversion_error_manual(self):
        """手动创建 TypeConversionError"""
        exc = TypeConversionError(
            "Cannot convert value to int",
            value="abc",
            target_type="int",
            column_name="age"
        )
        assert exc.value == "abc"
        assert exc.target_type == "int"
        assert exc.column_name == "age"


class TestConfigurationError:
    """ConfigurationError 触发测试"""

    def test_invalid_engine_name(self, tmp_path):
        """无效的引擎名称"""
        db_path = tmp_path / "test.invalid_engine"

        with pytest.raises(ConfigurationError):
            Storage(file_path=str(db_path), engine='invalid_engine')


class TestSchemaError:
    """SchemaError 触发测试"""

    def test_schema_error_attributes(self):
        """SchemaError 属性"""
        exc = SchemaError(
            "Missing primary key",
            table_name="users",
            details={"hint": "Add primary_key=True to a Column"}
        )
        assert exc.table_name == "users"
        assert exc.details["hint"] == "Add primary_key=True to a Column"


class TestQueryError:
    """QueryError 触发测试"""

    def test_invalid_operator_in_condition(self):
        """条件中使用无效操作符"""
        from pytuck.query.builder import Condition

        with pytest.raises(QueryError) as exc_info:
            Condition("age", "INVALID", 20)

        assert "Unsupported operator" in str(exc_info.value)

    def test_query_without_storage(self):
        """Query 没有关联 Storage 抛出 QueryError"""
        # 创建一个未绑定 storage 的简单模型类
        from pytuck.core.orm import PureBaseModel as RawPureBaseModel, Column as RawColumn

        class UnboundUser(RawPureBaseModel):
            __tablename__ = 'users'
            id = RawColumn(int, primary_key=True)
            name = RawColumn(str)

        # 不设置 storage
        from pytuck.query.builder import Query
        query = Query(UnboundUser, storage=None)

        # 尝试执行
        with pytest.raises(QueryError) as exc_info:
            query.all()

        assert "No database configured" in str(exc_info.value)

    def test_or_with_less_than_two_expressions(self):
        """or_() 需要至少 2 个表达式"""
        from pytuck import or_
        from pytuck.query.builder import BinaryExpression

        with pytest.raises(QueryError) as exc_info:
            or_()  # 0 个参数

        assert "at least 2 expressions" in str(exc_info.value)

    def test_and_with_less_than_two_expressions(self):
        """and_() 需要至少 2 个表达式"""
        from pytuck import and_

        with pytest.raises(QueryError):
            and_()  # 0 个参数


class TestTransactionError:
    """TransactionError 测试"""

    def test_transaction_error_attributes(self):
        """TransactionError 属性"""
        exc = TransactionError(
            "Transaction already committed",
            details={"state": "committed"}
        )
        assert exc.message == "Transaction already committed"
        assert exc.details["state"] == "committed"


class TestDatabaseConnectionError:
    """DatabaseConnectionError 测试"""

    def test_connection_error_attributes(self):
        """DatabaseConnectionError 属性"""
        exc = DatabaseConnectionError(
            "Cannot connect to database",
            details={"host": "localhost", "port": 5432}
        )
        assert "Cannot connect" in exc.message
        assert exc.details["host"] == "localhost"


class TestSerializationError:
    """SerializationError 测试"""

    def test_serialization_error_attributes(self):
        """SerializationError 属性"""
        exc = SerializationError(
            "Failed to serialize data",
            table_name="users",
            details={"format": "json"}
        )
        assert exc.table_name == "users"
        assert exc.details["format"] == "json"


class TestEncryptionError:
    """EncryptionError 测试"""

    def test_encryption_error_attributes(self):
        """EncryptionError 属性"""
        exc = EncryptionError(
            "Decryption failed: invalid key",
            details={"algorithm": "AES-256"}
        )
        assert "Decryption failed" in exc.message
        assert exc.details["algorithm"] == "AES-256"


class TestMigrationError:
    """MigrationError 测试"""

    def test_migration_error_attributes(self):
        """MigrationError 属性"""
        exc = MigrationError(
            "Migration failed: incompatible schema",
            details={"from_version": "1.0", "to_version": "2.0"}
        )
        assert "Migration failed" in exc.message
        assert exc.details["from_version"] == "1.0"


class TestPytuckIndexError:
    """PytuckIndexError 测试"""

    def test_index_error_attributes(self):
        """PytuckIndexError 属性"""
        exc = PytuckIndexError(
            "Index creation failed",
            table_name="users",
            column_name="email",
            details={"type": "unique"}
        )
        assert exc.table_name == "users"
        assert exc.column_name == "email"
        assert exc.details["type"] == "unique"


class TestUnsupportedOperationError:
    """UnsupportedOperationError 测试"""

    def test_unsupported_operation_attributes(self):
        """UnsupportedOperationError 属性"""
        exc = UnsupportedOperationError(
            "This backend does not support full-text search",
            details={"backend": "csv"}
        )
        assert "full-text search" in exc.message
        assert exc.details["backend"] == "csv"
