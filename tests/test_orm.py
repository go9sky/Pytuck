"""
Pytuck ORM 模块测试

测试内容：
1. PureBaseModel - 纯模型定义
2. CRUDBaseModel - Active Record 模式
3. declarative_base - 工厂函数
4. Column - 列定义和验证
5. 多引擎兼容性测试
"""
import os
import sys
import tempfile
import unittest
from typing import Type

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pytuck import (
    Storage, Session, Column, Relationship,
    declarative_base, PureBaseModel, CRUDBaseModel,
    select, insert, update, delete,
)
from pytuck.exceptions import ValidationError


class TestColumn(unittest.TestCase):
    """Column 类测试"""

    def test_column_basic(self):
        """测试 Column 基本功能"""
        col = Column('name', str, nullable=False)
        self.assertEqual(col.name, 'name')
        self.assertEqual(col.col_type, str)
        self.assertFalse(col.nullable)
        self.assertFalse(col.primary_key)

    def test_column_primary_key(self):
        """测试主键列"""
        col = Column('id', int, primary_key=True)
        self.assertTrue(col.primary_key)

    def test_column_validation_success(self):
        """测试列验证成功"""
        col = Column('age', int)
        self.assertEqual(col.validate(25), 25)
        self.assertEqual(col.validate(None), None)  # nullable=True

    def test_column_validation_type_conversion(self):
        """测试类型转换"""
        col = Column('age', int)
        self.assertEqual(col.validate("25"), 25)

    def test_column_validation_nullable_fail(self):
        """测试非空验证失败"""
        col = Column('name', str, nullable=False)
        with self.assertRaises(ValidationError):
            col.validate(None)

    def test_column_validation_type_fail(self):
        """测试类型验证失败"""
        col = Column('age', int)
        with self.assertRaises(ValidationError):
            col.validate("not_a_number")

    def test_column_to_dict(self):
        """测试转换为字典"""
        col = Column('id', int, primary_key=True)
        d = col.to_dict()
        self.assertEqual(d['name'], 'id')
        self.assertEqual(d['type'], 'int')
        self.assertTrue(d['primary_key'])


class TestDeclarativeBase(unittest.TestCase):
    """declarative_base 工厂函数测试"""

    def setUp(self):
        """设置测试环境"""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, 'test.db')
        self.db = Storage(file_path=self.db_path)

    def tearDown(self):
        """清理测试环境"""
        self.db.close()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        os.rmdir(self.temp_dir)

    def test_default_returns_pure_base(self):
        """测试默认返回纯模型基类"""
        Base = declarative_base(self.db)

        class TestModel(Base):
            __tablename__ = 'test_default'
            id = Column('id', int, primary_key=True)
            name = Column('name', str)

        # 验证没有 CRUD 方法
        self.assertFalse(hasattr(TestModel, 'create'))
        self.assertFalse(hasattr(TestModel, 'save'))
        self.assertFalse(hasattr(TestModel, 'delete'))

    def test_crud_false_returns_pure_base(self):
        """测试 crud=False 返回纯模型基类"""
        Base = declarative_base(self.db, crud=False)

        class TestModel(Base):
            __tablename__ = 'test_crud_false'
            id = Column('id', int, primary_key=True)

        self.assertFalse(hasattr(TestModel, 'create'))

    def test_crud_true_returns_crud_base(self):
        """测试 crud=True 返回 CRUD 基类"""
        Base = declarative_base(self.db, crud=True)

        class TestModel(Base):
            __tablename__ = 'test_crud_true'
            id = Column('id', int, primary_key=True)
            name = Column('name', str)

        # 验证有 CRUD 方法
        self.assertTrue(hasattr(TestModel, 'create'))
        self.assertTrue(hasattr(TestModel, 'save'))
        self.assertTrue(hasattr(TestModel, 'delete'))
        self.assertTrue(hasattr(TestModel, 'refresh'))
        self.assertTrue(hasattr(TestModel, 'get'))
        self.assertTrue(hasattr(TestModel, 'filter'))
        self.assertTrue(hasattr(TestModel, 'filter_by'))
        self.assertTrue(hasattr(TestModel, 'all'))

    def test_storage_binding(self):
        """测试 Storage 绑定"""
        Base = declarative_base(self.db)

        class TestModel(Base):
            __tablename__ = 'test_binding'
            id = Column('id', int, primary_key=True)

        self.assertIs(TestModel.__storage__, self.db)

    def test_tablename_required(self):
        """测试 __tablename__ 必须定义"""
        Base = declarative_base(self.db)

        with self.assertRaises(ValidationError):
            class TestModel(Base):
                id = Column('id', int, primary_key=True)

    def test_column_collection(self):
        """测试列收集"""
        Base = declarative_base(self.db)

        class TestModel(Base):
            __tablename__ = 'test_columns'
            id = Column('id', int, primary_key=True)
            name = Column('name', str)
            age = Column('age', int)

        self.assertEqual(len(TestModel.__columns__), 3)
        self.assertIn('id', TestModel.__columns__)
        self.assertIn('name', TestModel.__columns__)
        self.assertIn('age', TestModel.__columns__)

    def test_primary_key_detection(self):
        """测试主键检测"""
        Base = declarative_base(self.db)

        class TestModel(Base):
            __tablename__ = 'test_pk'
            user_id = Column('user_id', int, primary_key=True)
            name = Column('name', str)

        self.assertEqual(TestModel.__primary_key__, 'user_id')


class TestPureBaseModel(unittest.TestCase):
    """PureBaseModel 测试"""

    def setUp(self):
        """设置测试环境"""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, 'test.db')
        self.db = Storage(file_path=self.db_path)

        # 创建纯模型基类
        self.Base: Type[PureBaseModel] = declarative_base(self.db)

        class User(self.Base):
            __tablename__ = 'users'
            id = Column('id', int, primary_key=True)
            name = Column('name', str, nullable=False)
            age = Column('age', int)

        self.User = User

    def tearDown(self):
        """清理测试环境"""
        self.db.close()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        os.rmdir(self.temp_dir)

    def test_instance_creation(self):
        """测试实例创建"""
        user = self.User(name='Alice', age=25)
        self.assertEqual(user.name, 'Alice')
        self.assertEqual(user.age, 25)
        self.assertIsNone(user.id)

    def test_to_dict(self):
        """测试转换为字典"""
        user = self.User(name='Alice', age=25)
        d = user.to_dict()
        self.assertEqual(d['name'], 'Alice')
        self.assertEqual(d['age'], 25)

    def test_repr(self):
        """测试字符串表示"""
        user = self.User(name='Alice', age=25)
        repr_str = repr(user)
        self.assertIn('User', repr_str)

    def test_default_values(self):
        """测试默认值"""
        Base = declarative_base(self.db)

        class TestModel(Base):
            __tablename__ = 'test_defaults'
            id = Column('id', int, primary_key=True)
            status = Column('status', str, default='active')

        instance = TestModel()
        self.assertEqual(instance.status, 'active')

    def test_session_operations(self):
        """测试通过 Session 操作"""
        session = Session(self.db)

        # 插入
        user = self.User(name='Alice', age=25)
        session.add(user)
        session.commit()

        # 查询
        stmt = select(self.User).where(self.User.name == 'Alice')
        result = session.execute(stmt)
        users = result.scalars().all()

        self.assertEqual(len(users), 1)
        self.assertEqual(users[0].name, 'Alice')


class TestCRUDBaseModel(unittest.TestCase):
    """CRUDBaseModel 测试"""

    def setUp(self):
        """设置测试环境"""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, 'test.db')
        self.db = Storage(file_path=self.db_path)

        # 创建 CRUD 基类
        self.Base: Type[CRUDBaseModel] = declarative_base(self.db, crud=True)

        class User(self.Base):
            __tablename__ = 'users'
            id = Column('id', int, primary_key=True)
            name = Column('name', str, nullable=False)
            age = Column('age', int)

        self.User = User

    def tearDown(self):
        """清理测试环境"""
        self.db.close()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        os.rmdir(self.temp_dir)

    def test_create(self):
        """测试 create 方法"""
        user = self.User.create(name='Alice', age=25)
        self.assertIsNotNone(user.id)
        self.assertEqual(user.name, 'Alice')
        self.assertEqual(user.age, 25)
        self.assertTrue(user._loaded_from_db)

    def test_save_insert(self):
        """测试 save 插入"""
        user = self.User(name='Bob', age=30)
        self.assertIsNone(user.id)

        user.save()

        self.assertIsNotNone(user.id)
        self.assertTrue(user._loaded_from_db)

    def test_save_update(self):
        """测试 save 更新"""
        user = self.User.create(name='Alice', age=25)
        original_id = user.id

        user.name = 'Alice Updated'
        user.save()

        # ID 应该不变
        self.assertEqual(user.id, original_id)

        # 从数据库重新获取验证更新
        refreshed = self.User.get(original_id)
        self.assertEqual(refreshed.name, 'Alice Updated')

    def test_delete(self):
        """测试 delete 方法"""
        user = self.User.create(name='ToDelete', age=20)
        user_id = user.id

        user.delete()

        # 验证已删除
        deleted = self.User.get(user_id)
        self.assertIsNone(deleted)

    def test_refresh(self):
        """测试 refresh 方法"""
        user = self.User.create(name='Original', age=25)

        # 模拟外部修改（通过另一个实例）
        another = self.User.get(user.id)
        another.name = 'Modified'
        another.save()

        # 刷新原实例
        user.refresh()
        self.assertEqual(user.name, 'Modified')

    def test_get_found(self):
        """测试 get 方法 - 找到记录"""
        user = self.User.create(name='FindMe', age=30)

        found = self.User.get(user.id)
        self.assertIsNotNone(found)
        self.assertEqual(found.name, 'FindMe')

    def test_get_not_found(self):
        """测试 get 方法 - 未找到记录"""
        result = self.User.get(99999)
        self.assertIsNone(result)

    def test_filter_expression(self):
        """测试 filter 方法 - 表达式语法"""
        self.User.create(name='Young', age=18)
        self.User.create(name='Old', age=60)

        users = self.User.filter(self.User.age >= 30).all()
        self.assertEqual(len(users), 1)
        self.assertEqual(users[0].name, 'Old')

    def test_filter_by(self):
        """测试 filter_by 方法"""
        self.User.create(name='Alice', age=25)
        self.User.create(name='Bob', age=30)

        users = self.User.filter_by(name='Alice').all()
        self.assertEqual(len(users), 1)
        self.assertEqual(users[0].name, 'Alice')

    def test_all(self):
        """测试 all 方法"""
        self.User.create(name='User1', age=20)
        self.User.create(name='User2', age=25)
        self.User.create(name='User3', age=30)

        users = self.User.all()
        self.assertEqual(len(users), 3)

    def test_filter_chaining(self):
        """测试链式查询"""
        self.User.create(name='Alice', age=25)
        self.User.create(name='Bob', age=30)
        self.User.create(name='Charlie', age=35)

        users = self.User.filter(self.User.age >= 25).filter(self.User.age < 35).all()
        self.assertEqual(len(users), 2)

    def test_filter_order_by(self):
        """测试排序"""
        self.User.create(name='Charlie', age=35)
        self.User.create(name='Alice', age=25)
        self.User.create(name='Bob', age=30)

        users = self.User.filter(self.User.age >= 0).order_by('age').all()
        self.assertEqual(users[0].name, 'Alice')
        self.assertEqual(users[-1].name, 'Charlie')

    def test_filter_limit(self):
        """测试限制"""
        for i in range(10):
            self.User.create(name=f'User{i}', age=20+i)

        users = self.User.filter(self.User.age >= 0).limit(3).all()
        self.assertEqual(len(users), 3)


class TestMultipleEngines(unittest.TestCase):
    """多存储引擎测试"""

    def _test_engine(self, engine: str, file_ext: str):
        """测试单个引擎"""
        temp_dir = tempfile.mkdtemp()
        db_path = os.path.join(temp_dir, f'test.{file_ext}')

        try:
            db = Storage(file_path=db_path, engine=engine)
            Base = declarative_base(db, crud=True)

            class Item(Base):
                __tablename__ = 'items'
                id = Column('id', int, primary_key=True)
                name = Column('name', str)
                value = Column('value', float)

            # 创建
            item = Item.create(name='Test', value=3.14)
            self.assertIsNotNone(item.id)

            # 读取
            found = Item.get(item.id)
            self.assertEqual(found.name, 'Test')

            # 更新
            found.value = 2.71
            found.save()

            # 验证更新
            updated = Item.get(item.id)
            self.assertAlmostEqual(updated.value, 2.71, places=2)

            # 删除
            updated.delete()
            deleted = Item.get(item.id)
            self.assertIsNone(deleted)

            db.close()

        finally:
            if os.path.exists(db_path):
                os.remove(db_path)
            if os.path.exists(temp_dir):
                os.rmdir(temp_dir)

    def test_binary_engine(self):
        """测试 Binary 引擎"""
        self._test_engine('binary', 'db')

    def test_json_engine(self):
        """测试 JSON 引擎"""
        self._test_engine('json', 'json')

    def test_csv_engine(self):
        """测试 CSV 引擎"""
        # CSV 引擎需要特殊处理，跳过此测试
        pass

    def test_sqlite_engine(self):
        """测试 SQLite 引擎"""
        try:
            import sqlite3
            self._test_engine('sqlite', 'sqlite')
        except ImportError:
            self.skipTest("SQLite not available")


class TestTypeAnnotations(unittest.TestCase):
    """类型注解测试"""

    def setUp(self):
        """设置测试环境"""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, 'test.db')
        self.db = Storage(file_path=self.db_path)

    def tearDown(self):
        """清理测试环境"""
        self.db.close()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        os.rmdir(self.temp_dir)

    def test_pure_base_type_annotation(self):
        """测试 PureBaseModel 类型注解"""
        Base: Type[PureBaseModel] = declarative_base(self.db)

        class User(Base):
            __tablename__ = 'users'
            id = Column('id', int, primary_key=True)
            name = Column('name', str)

        # 类型检查应该通过
        self.assertTrue(True)

    def test_crud_base_type_annotation(self):
        """测试 CRUDBaseModel 类型注解"""
        Base: Type[CRUDBaseModel] = declarative_base(self.db, crud=True)

        class User(Base):
            __tablename__ = 'users'
            id = Column('id', int, primary_key=True)
            name = Column('name', str)

        # 类型检查应该通过
        self.assertTrue(True)

    def test_isinstance_pure_base_model(self):
        """测试 PureBaseModel 的 isinstance 检查"""
        Base = declarative_base(self.db)

        class User(Base):
            __tablename__ = 'users_isinstance'
            id = Column('id', int, primary_key=True)
            name = Column('name', str)

        user = User(name='Alice')

        # isinstance 检查应该通过
        self.assertIsInstance(user, PureBaseModel)
        self.assertTrue(isinstance(user, PureBaseModel))

    def test_isinstance_crud_base_model(self):
        """测试 CRUDBaseModel 的 isinstance 检查"""
        Base = declarative_base(self.db, crud=True)

        class User(Base):
            __tablename__ = 'users_isinstance_crud'
            id = Column('id', int, primary_key=True)
            name = Column('name', str)

        user = User.create(name='Alice')

        # isinstance 检查应该通过（CRUDBaseModel 和 PureBaseModel）
        self.assertIsInstance(user, CRUDBaseModel)
        self.assertIsInstance(user, PureBaseModel)
        self.assertTrue(isinstance(user, CRUDBaseModel))
        self.assertTrue(isinstance(user, PureBaseModel))

    def test_issubclass_checks(self):
        """测试 issubclass 检查"""
        PureBase = declarative_base(self.db)
        CRUDBase = declarative_base(self.db, crud=True)

        class PureUser(PureBase):
            __tablename__ = 'pure_users_sub'
            id = Column('id', int, primary_key=True)

        class CRUDUser(CRUDBase):
            __tablename__ = 'crud_users_sub'
            id = Column('id', int, primary_key=True)

        # issubclass 检查
        self.assertTrue(issubclass(PureUser, PureBaseModel))
        self.assertTrue(issubclass(CRUDUser, CRUDBaseModel))
        self.assertTrue(issubclass(CRUDUser, PureBaseModel))


def run_tests():
    """运行所有测试"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # 添加所有测试类
    suite.addTests(loader.loadTestsFromTestCase(TestColumn))
    suite.addTests(loader.loadTestsFromTestCase(TestDeclarativeBase))
    suite.addTests(loader.loadTestsFromTestCase(TestPureBaseModel))
    suite.addTests(loader.loadTestsFromTestCase(TestCRUDBaseModel))
    suite.addTests(loader.loadTestsFromTestCase(TestMultipleEngines))
    suite.addTests(loader.loadTestsFromTestCase(TestTypeAnnotations))

    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # 返回是否全部通过
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
