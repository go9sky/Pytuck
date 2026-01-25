"""
Pytuck 类型验证测试

测试类型验证和转换功能：
- 基本类型验证（int, str, float, bool, bytes）
- 扩展类型验证（datetime, date, timedelta, list, dict）
- 自动类型转换（宽松模式）
- 严格模式（strict=True）
- None 值处理
- ValidationError 抛出
"""

import os
import sys
import unittest
from datetime import datetime, date, timedelta, timezone
from typing import Type

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pytuck import Storage, declarative_base, Session, Column, PureBaseModel, select, insert
from pytuck.common.exceptions import ValidationError


class TestTypeConversionLooseMode(unittest.TestCase):
    """类型自动转换测试（宽松模式，默认）"""

    def setUp(self) -> None:
        """测试前设置"""
        self.db = Storage(in_memory=True)
        Base: Type[PureBaseModel] = declarative_base(self.db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str, nullable=False)
            age = Column(int)
            score = Column(float)
            active = Column(bool)
            avatar = Column(bytes, nullable=True)

        self.User = User
        self.session = Session(self.db)

    def tearDown(self) -> None:
        """测试后清理"""
        self.session.close()
        self.db.close()

    def test_int_conversion_from_string(self) -> None:
        """测试 int 自动转换：'25' → 25"""
        user = self.User(name='Alice', age='25', score=3.5, active=True)
        self.assertEqual(user.age, 25)
        self.assertIsInstance(user.age, int)

    def test_int_conversion_from_float(self) -> None:
        """测试 int 自动转换：25.9 → 25"""
        user = self.User(name='Bob', age=25.9, score=3.5, active=True)
        self.assertEqual(user.age, 25)
        self.assertIsInstance(user.age, int)

    def test_float_conversion_from_string(self) -> None:
        """测试 float 自动转换：'3.14' → 3.14"""
        user = self.User(name='Charlie', age=30, score='3.14', active=True)
        self.assertEqual(user.score, 3.14)
        self.assertIsInstance(user.score, float)

    def test_float_conversion_from_int(self) -> None:
        """测试 float 自动转换：90 → 90.0"""
        user = self.User(name='David', age=30, score=90, active=True)
        self.assertEqual(user.score, 90.0)
        self.assertIsInstance(user.score, float)

    def test_str_conversion_from_int(self) -> None:
        """测试 str 自动转换：123 → '123'"""
        user = self.User(name=123, age=30, score=3.5, active=True)
        self.assertEqual(user.name, '123')
        self.assertIsInstance(user.name, str)

    def test_bool_conversion_from_int(self) -> None:
        """测试 bool 自动转换：1 → True, 0 → False"""
        user1 = self.User(name='Eve', age=20, score=3.5, active=1)
        self.assertTrue(user1.active)

        user2 = self.User(name='Frank', age=25, score=3.5, active=0)
        self.assertFalse(user2.active)

    def test_bool_conversion_from_string(self) -> None:
        """测试 bool 自动转换：'true', '1', 'yes' → True"""
        for val in ['true', 'True', '1', 'yes', 'Yes']:
            user = self.User(name='Test', age=20, score=3.5, active=val)
            self.assertTrue(user.active, f"Failed for value: {val}")

        for val in ['false', 'False', '0', 'no', 'No', '']:
            user = self.User(name='Test', age=20, score=3.5, active=val)
            self.assertFalse(user.active, f"Failed for value: {val}")

    def test_bytes_conversion_from_string(self) -> None:
        """测试 bytes 自动转换：'hello' → b'hello'"""
        user = self.User(name='George', age=30, score=3.5, active=True, avatar='hello')
        self.assertEqual(user.avatar, b'hello')
        self.assertIsInstance(user.avatar, bytes)

    def test_bytes_conversion_from_bytearray(self) -> None:
        """测试 bytes 自动转换：bytearray → bytes"""
        user = self.User(name='Helen', age=30, score=3.5, active=True, avatar=bytearray(b'data'))
        self.assertEqual(user.avatar, b'data')
        self.assertIsInstance(user.avatar, bytes)


class TestTypeValidationStrictMode(unittest.TestCase):
    """严格模式测试（strict=True，不进行类型转换）"""

    def setUp(self) -> None:
        """测试前设置"""
        self.db = Storage(in_memory=True)
        Base: Type[PureBaseModel] = declarative_base(self.db)

        class StrictUser(Base):
            __tablename__ = 'strict_users'
            id = Column(int, primary_key=True)
            name = Column(str, nullable=False, strict=True)
            age = Column(int, strict=True)
            score = Column(float, strict=True)
            active = Column(bool, strict=True)

        self.StrictUser = StrictUser

    def tearDown(self) -> None:
        """测试后清理"""
        self.db.close()

    def test_strict_int_rejects_string(self) -> None:
        """测试严格模式：int 列拒绝字符串"""
        with self.assertRaises(ValidationError) as cm:
            self.StrictUser(name='Alice', age='25', score=3.5, active=True)
        self.assertIn('strict mode', str(cm.exception))

    def test_strict_float_rejects_string(self) -> None:
        """测试严格模式：float 列拒绝字符串"""
        with self.assertRaises(ValidationError) as cm:
            self.StrictUser(name='Bob', age=25, score='3.14', active=True)
        self.assertIn('strict mode', str(cm.exception))

    def test_strict_str_rejects_int(self) -> None:
        """测试严格模式：str 列拒绝整数"""
        with self.assertRaises(ValidationError) as cm:
            self.StrictUser(name=123, age=25, score=3.5, active=True)
        self.assertIn('strict mode', str(cm.exception))

    def test_strict_bool_rejects_int(self) -> None:
        """测试严格模式：bool 列拒绝整数"""
        with self.assertRaises(ValidationError) as cm:
            self.StrictUser(name='Charlie', age=25, score=3.5, active=1)
        self.assertIn('strict mode', str(cm.exception))

    def test_strict_accepts_correct_types(self) -> None:
        """测试严格模式：接受正确类型"""
        user = self.StrictUser(name='David', age=30, score=3.14, active=True)
        self.assertEqual(user.name, 'David')
        self.assertEqual(user.age, 30)
        self.assertEqual(user.score, 3.14)
        self.assertTrue(user.active)


class TestNullHandling(unittest.TestCase):
    """NULL 值处理测试"""

    def setUp(self) -> None:
        """测试前设置"""
        self.db = Storage(in_memory=True)
        Base: Type[PureBaseModel] = declarative_base(self.db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str, nullable=False)  # NOT NULL
            email = Column(str, nullable=True)  # NULL OK
            age = Column(int, nullable=True)

        self.User = User

    def tearDown(self) -> None:
        """测试后清理"""
        self.db.close()

    def test_nullable_column_accepts_none(self) -> None:
        """测试 nullable=True 允许 None"""
        user = self.User(name='Alice', email=None, age=None)
        self.assertIsNone(user.email)
        self.assertIsNone(user.age)

    def test_non_nullable_column_rejects_none(self) -> None:
        """测试 nullable=False 拒绝 None"""
        with self.assertRaises(ValidationError) as cm:
            self.User(name=None, email='test@example.com', age=25)
        self.assertIn('cannot be null', str(cm.exception))

    def test_primary_key_accepts_none(self) -> None:
        """测试主键列允许 None（自动生成）"""
        user = self.User(name='Bob', email='bob@example.com', age=30)
        self.assertIsNone(user.id)


class TestValidationErrors(unittest.TestCase):
    """ValidationError 抛出测试"""

    def setUp(self) -> None:
        """测试前设置"""
        self.db = Storage(in_memory=True)
        Base: Type[PureBaseModel] = declarative_base(self.db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)
            age = Column(int)
            score = Column(float)
            active = Column(bool)

        self.User = User

    def tearDown(self) -> None:
        """测试后清理"""
        self.db.close()

    def test_invalid_int_conversion(self) -> None:
        """测试无效 int 转换"""
        with self.assertRaises(ValidationError) as cm:
            self.User(name='Alice', age='not_a_number', score=3.5, active=True)
        self.assertIn('Cannot convert', str(cm.exception))

    def test_invalid_float_conversion(self) -> None:
        """测试无效 float 转换"""
        with self.assertRaises(ValidationError) as cm:
            self.User(name='Bob', age=25, score='not_a_float', active=True)
        self.assertIn('Cannot convert', str(cm.exception))

    def test_invalid_bool_conversion(self) -> None:
        """测试无效 bool 转换"""
        with self.assertRaises(ValidationError) as cm:
            self.User(name='Charlie', age=30, score=3.5, active='maybe')
        self.assertIn('Cannot convert', str(cm.exception))

    def test_invalid_bytes_conversion(self) -> None:
        """测试无效 bytes 转换"""
        column = Column(bytes, name='data')
        with self.assertRaises(ValidationError) as cm:
            column.validate(123)
        self.assertIn('Cannot convert', str(cm.exception))


class TestValidationInInsertUpdate(unittest.TestCase):
    """插入和更新时的类型验证测试"""

    def setUp(self) -> None:
        """测试前设置"""
        self.db = Storage(in_memory=True)
        Base: Type[PureBaseModel] = declarative_base(self.db)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)
            age = Column(int)

        self.User = User
        self.session = Session(self.db)

    def tearDown(self) -> None:
        """测试后清理"""
        self.session.close()
        self.db.close()

    def test_insert_with_type_conversion(self) -> None:
        """测试插入时自动类型转换"""
        stmt = insert(self.User).values(name='Alice', age='25')
        result = self.session.execute(stmt)
        self.session.commit()

        # 验证插入成功
        stmt = select(self.User).where(self.User.id == result.inserted_primary_key)
        user = self.session.execute(stmt).first()
        self.assertEqual(user.age, 25)
        self.assertIsInstance(user.age, int)

    def test_model_construction_with_conversion(self) -> None:
        """测试模型构造时类型转换"""
        user = self.User(name=123, age='30')
        self.assertEqual(user.name, '123')
        self.assertEqual(user.age, 30)


class TestBoolConversionEdgeCases(unittest.TestCase):
    """布尔值转换边界测试"""

    def setUp(self) -> None:
        """测试前设置"""
        self.column = Column(bool, name='active')

    def test_bool_true_values(self) -> None:
        """测试 True 值转换"""
        true_values = [True, 1, '1', 'true', 'True', 'yes', 'Yes']
        for val in true_values:
            result = self.column.validate(val)
            self.assertTrue(result, f"Failed for value: {val}")

    def test_bool_false_values(self) -> None:
        """测试 False 值转换"""
        false_values = [False, 0, '0', 'false', 'False', 'no', 'No', '']
        for val in false_values:
            result = self.column.validate(val)
            self.assertFalse(result, f"Failed for value: {val}")

    def test_bool_invalid_string(self) -> None:
        """测试无效布尔字符串"""
        with self.assertRaises(ValidationError):
            self.column.validate('maybe')

    def test_bool_rejects_int_type_for_int_column(self) -> None:
        """测试 int 列拒绝 bool 类型（bool 是 int 子类）"""
        int_column = Column(int, name='count')
        with self.assertRaises(ValidationError):
            int_column.validate(True)


class TestIntBoolSeparation(unittest.TestCase):
    """测试 int 和 bool 的类型分离"""

    def setUp(self) -> None:
        """测试前设置"""
        self.db = Storage(in_memory=True)
        Base: Type[PureBaseModel] = declarative_base(self.db)

        class Data(Base):
            __tablename__ = 'data'
            id = Column(int, primary_key=True)
            count = Column(int)
            flag = Column(bool)

        self.Data = Data

    def tearDown(self) -> None:
        """测试后清理"""
        self.db.close()

    def test_int_column_accepts_int(self) -> None:
        """测试 int 列接受 int"""
        data = self.Data(count=42, flag=True)
        self.assertEqual(data.count, 42)
        self.assertIsInstance(data.count, int)
        self.assertNotIsInstance(data.count, bool)

    def test_int_column_rejects_bool(self) -> None:
        """测试 int 列拒绝 bool（虽然 bool 是 int 子类）"""
        with self.assertRaises(ValidationError):
            self.Data(count=True, flag=True)

    def test_bool_column_accepts_bool(self) -> None:
        """测试 bool 列接受 bool"""
        data = self.Data(count=42, flag=True)
        self.assertTrue(data.flag)
        self.assertIsInstance(data.flag, bool)


class TestDatetimeTypes(unittest.TestCase):
    """datetime, date, timedelta 类型测试"""

    def setUp(self) -> None:
        """测试前设置"""
        self.db = Storage(in_memory=True)
        Base: Type[PureBaseModel] = declarative_base(self.db)

        class Event(Base):
            __tablename__ = 'events'
            id = Column(int, primary_key=True)
            created_at = Column(datetime, nullable=True)
            event_date = Column(date, nullable=True)
            duration = Column(timedelta, nullable=True)

        self.Event = Event
        self.session = Session(self.db)

    def tearDown(self) -> None:
        """测试后清理"""
        self.session.close()
        self.db.close()

    def test_datetime_accepts_datetime(self) -> None:
        """测试 datetime 列接受 datetime 对象"""
        now = datetime.now()
        event = self.Event(created_at=now)
        self.assertEqual(event.created_at, now)
        self.assertIsInstance(event.created_at, datetime)

    def test_datetime_with_timezone(self) -> None:
        """测试 datetime 支持时区"""
        tz_aware = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        event = self.Event(created_at=tz_aware)
        self.assertEqual(event.created_at, tz_aware)
        self.assertIsNotNone(event.created_at.tzinfo)

    def test_datetime_from_iso_string(self) -> None:
        """测试 datetime 从 ISO 字符串转换"""
        event = self.Event(created_at='2024-01-15T10:30:00')
        self.assertIsInstance(event.created_at, datetime)
        self.assertEqual(event.created_at.year, 2024)
        self.assertEqual(event.created_at.month, 1)
        self.assertEqual(event.created_at.day, 15)
        self.assertEqual(event.created_at.hour, 10)
        self.assertEqual(event.created_at.minute, 30)

    def test_datetime_from_iso_string_with_timezone(self) -> None:
        """测试 datetime 从带时区的 ISO 字符串转换"""
        event = self.Event(created_at='2024-01-15T10:30:00+08:00')
        self.assertIsInstance(event.created_at, datetime)
        self.assertIsNotNone(event.created_at.tzinfo)

    def test_date_accepts_date(self) -> None:
        """测试 date 列接受 date 对象"""
        today = date.today()
        event = self.Event(event_date=today)
        self.assertEqual(event.event_date, today)
        self.assertIsInstance(event.event_date, date)

    def test_date_from_iso_string(self) -> None:
        """测试 date 从 ISO 字符串转换"""
        event = self.Event(event_date='2024-01-15')
        self.assertIsInstance(event.event_date, date)
        self.assertEqual(event.event_date.year, 2024)
        self.assertEqual(event.event_date.month, 1)
        self.assertEqual(event.event_date.day, 15)

    def test_timedelta_accepts_timedelta(self) -> None:
        """测试 timedelta 列接受 timedelta 对象"""
        duration = timedelta(hours=2, minutes=30)
        event = self.Event(duration=duration)
        self.assertEqual(event.duration, duration)
        self.assertIsInstance(event.duration, timedelta)

    def test_timedelta_from_int_seconds(self) -> None:
        """测试 timedelta 从整数（秒）转换"""
        event = self.Event(duration=3600)  # 1 hour
        self.assertIsInstance(event.duration, timedelta)
        self.assertEqual(event.duration.total_seconds(), 3600)

    def test_timedelta_from_float_seconds(self) -> None:
        """测试 timedelta 从浮点数（秒）转换"""
        event = self.Event(duration=3661.5)  # 1 hour, 1 minute, 1.5 seconds
        self.assertIsInstance(event.duration, timedelta)
        self.assertEqual(event.duration.total_seconds(), 3661.5)

    def test_null_datetime_types(self) -> None:
        """测试 datetime 类型 NULL 值"""
        event = self.Event(created_at=None, event_date=None, duration=None)
        self.assertIsNone(event.created_at)
        self.assertIsNone(event.event_date)
        self.assertIsNone(event.duration)


class TestListDictTypes(unittest.TestCase):
    """list 和 dict 类型测试"""

    def setUp(self) -> None:
        """测试前设置"""
        self.db = Storage(in_memory=True)
        Base: Type[PureBaseModel] = declarative_base(self.db)

        class Document(Base):
            __tablename__ = 'documents'
            id = Column(int, primary_key=True)
            tags = Column(list, nullable=True)
            metadata = Column(dict, nullable=True)

        self.Document = Document
        self.session = Session(self.db)

    def tearDown(self) -> None:
        """测试后清理"""
        self.session.close()
        self.db.close()

    def test_list_accepts_list(self) -> None:
        """测试 list 列接受 list 对象"""
        tags = ['python', 'database', 'orm']
        doc = self.Document(tags=tags)
        self.assertEqual(doc.tags, tags)
        self.assertIsInstance(doc.tags, list)

    def test_list_with_nested_data(self) -> None:
        """测试 list 支持嵌套数据"""
        nested = [[1, 2], [3, 4], {'key': 'value'}]
        doc = self.Document(tags=nested)
        self.assertEqual(doc.tags, nested)

    def test_list_from_tuple(self) -> None:
        """测试 list 从 tuple 转换"""
        doc = self.Document(tags=('a', 'b', 'c'))
        self.assertIsInstance(doc.tags, list)
        self.assertEqual(doc.tags, ['a', 'b', 'c'])

    def test_list_from_json_string(self) -> None:
        """测试 list 从 JSON 字符串转换"""
        doc = self.Document(tags='["x", "y", "z"]')
        self.assertIsInstance(doc.tags, list)
        self.assertEqual(doc.tags, ['x', 'y', 'z'])

    def test_dict_accepts_dict(self) -> None:
        """测试 dict 列接受 dict 对象"""
        meta = {'author': 'Alice', 'version': 1.0}
        doc = self.Document(metadata=meta)
        self.assertEqual(doc.metadata, meta)
        self.assertIsInstance(doc.metadata, dict)

    def test_dict_with_nested_data(self) -> None:
        """测试 dict 支持嵌套数据"""
        nested = {'level1': {'level2': {'level3': 'value'}}}
        doc = self.Document(metadata=nested)
        self.assertEqual(doc.metadata, nested)

    def test_dict_from_json_string(self) -> None:
        """测试 dict 从 JSON 字符串转换"""
        doc = self.Document(metadata='{"key": "value"}')
        self.assertIsInstance(doc.metadata, dict)
        self.assertEqual(doc.metadata, {'key': 'value'})

    def test_null_list_dict_types(self) -> None:
        """测试 list/dict 类型 NULL 值"""
        doc = self.Document(tags=None, metadata=None)
        self.assertIsNone(doc.tags)
        self.assertIsNone(doc.metadata)


class TestDatetimeTypePersistence(unittest.TestCase):
    """datetime 类型持久化测试"""

    def setUp(self) -> None:
        """测试前设置"""
        self.db = Storage(in_memory=True)
        Base: Type[PureBaseModel] = declarative_base(self.db)

        class Task(Base):
            __tablename__ = 'tasks'
            id = Column(int, primary_key=True)
            title = Column(str)
            created_at = Column(datetime, nullable=True)
            due_date = Column(date, nullable=True)
            duration = Column(timedelta, nullable=True)
            tags = Column(list, nullable=True)
            options = Column(dict, nullable=True)

        self.Task = Task
        self.session = Session(self.db)

    def tearDown(self) -> None:
        """测试后清理"""
        self.session.close()
        self.db.close()

    def test_insert_and_query_new_types(self) -> None:
        """测试新类型的插入和查询"""
        now = datetime.now()
        today = date.today()
        duration = timedelta(hours=2)
        tags = ['important', 'urgent']
        options = {'priority': 1, 'notify': True}

        stmt = insert(self.Task).values(
            title='Test Task',
            created_at=now,
            due_date=today,
            duration=duration,
            tags=tags,
            options=options
        )
        result = self.session.execute(stmt)
        self.session.commit()

        # 查询验证
        stmt = select(self.Task).where(self.Task.id == result.inserted_primary_key)
        task = self.session.execute(stmt).first()

        self.assertIsNotNone(task)
        self.assertEqual(task.title, 'Test Task')
        self.assertEqual(task.created_at, now)
        self.assertEqual(task.due_date, today)
        self.assertEqual(task.duration, duration)
        self.assertEqual(task.tags, tags)
        self.assertEqual(task.options, options)


if __name__ == '__main__':
    unittest.main()
