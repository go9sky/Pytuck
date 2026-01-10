"""
Pytuck 类型验证测试

测试类型验证和转换功能：
- 基本类型验证（int, str, float, bool, bytes）
- 自动类型转换（宽松模式）
- 严格模式（strict=True）
- None 值处理
- ValidationError 抛出
"""

import os
import sys
import unittest
from typing import Type

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pytuck import Storage, declarative_base, Session, Column, PureBaseModel, select, insert
from pytuck.core.exceptions import ValidationError


class TestTypeConversionLooseMode(unittest.TestCase):
    """类型自动转换测试（宽松模式，默认）"""

    def setUp(self) -> None:
        """测试前设置"""
        self.db = Storage(in_memory=True)
        Base: Type[PureBaseModel] = declarative_base(self.db)

        class User(Base):
            __tablename__ = 'users'
            id = Column('id', int, primary_key=True)
            name = Column('name', str, nullable=False)
            age = Column('age', int)
            score = Column('score', float)
            active = Column('active', bool)
            avatar = Column('avatar', bytes, nullable=True)

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
            id = Column('id', int, primary_key=True)
            name = Column('name', str, nullable=False, strict=True)
            age = Column('age', int, strict=True)
            score = Column('score', float, strict=True)
            active = Column('active', bool, strict=True)

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
            id = Column('id', int, primary_key=True)
            name = Column('name', str, nullable=False)  # NOT NULL
            email = Column('email', str, nullable=True)  # NULL OK
            age = Column('age', int, nullable=True)

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
            id = Column('id', int, primary_key=True)
            name = Column('name', str)
            age = Column('age', int)
            score = Column('score', float)
            active = Column('active', bool)

        self.User = User

    def tearDown(self) -> None:
        """测试后清理"""
        self.db.close()

    def test_invalid_int_conversion(self) -> None:
        """测试无效 int 转换"""
        with self.assertRaises(ValidationError) as cm:
            self.User(name='Alice', age='not_a_number', score=3.5, active=True)
        self.assertIn('cannot convert', str(cm.exception))

    def test_invalid_float_conversion(self) -> None:
        """测试无效 float 转换"""
        with self.assertRaises(ValidationError) as cm:
            self.User(name='Bob', age=25, score='not_a_float', active=True)
        self.assertIn('cannot convert', str(cm.exception))

    def test_invalid_bool_conversion(self) -> None:
        """测试无效 bool 转换"""
        with self.assertRaises(ValidationError) as cm:
            self.User(name='Charlie', age=30, score=3.5, active='maybe')
        self.assertIn('Cannot convert', str(cm.exception))

    def test_invalid_bytes_conversion(self) -> None:
        """测试无效 bytes 转换"""
        column = Column('data', bytes)
        with self.assertRaises(ValidationError) as cm:
            column.validate(123)
        self.assertIn('cannot convert', str(cm.exception))


class TestValidationInInsertUpdate(unittest.TestCase):
    """插入和更新时的类型验证测试"""

    def setUp(self) -> None:
        """测试前设置"""
        self.db = Storage(in_memory=True)
        Base: Type[PureBaseModel] = declarative_base(self.db)

        class User(Base):
            __tablename__ = 'users'
            id = Column('id', int, primary_key=True)
            name = Column('name', str)
            age = Column('age', int)

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
        user = self.session.execute(stmt).scalars().first()
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
        self.column = Column('active', bool)

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
        int_column = Column('count', int)
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
            id = Column('id', int, primary_key=True)
            count = Column('count', int)
            flag = Column('flag', bool)

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


if __name__ == '__main__':
    unittest.main()
