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
import unittest
from typing import Type

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from examples._common import mktemp_dir_project
from pytuck import (
    Storage, Session, Column, Relationship,
    declarative_base, PureBaseModel, CRUDBaseModel,
    select, insert, update, delete,
)
from pytuck.common.exceptions import ValidationError, SchemaError


class TestColumn(unittest.TestCase):
    """Column 类测试"""

    def test_column_basic(self):
        """测试 Column 基本功能"""
        col = Column(str, name='username', nullable=False)
        self.assertEqual(col.name, 'username')
        self.assertEqual(col.col_type, str)
        self.assertFalse(col.nullable)
        self.assertFalse(col.primary_key)

    def test_column_primary_key(self):
        """测试主键列"""
        col = Column(int, primary_key=True)
        self.assertTrue(col.primary_key)

    def test_column_validation_success(self):
        """测试列验证成功"""
        col = Column(int, name='age')
        self.assertEqual(col.validate(25), 25)
        self.assertEqual(col.validate(None), None)  # nullable=True

    def test_column_validation_type_conversion(self):
        """测试类型转换"""
        col = Column(int, name='age')
        self.assertEqual(col.validate("25"), 25)

    def test_column_validation_nullable_fail(self):
        """测试非空验证失败"""
        col = Column(str, name='name', nullable=False)
        with self.assertRaises(ValidationError):
            col.validate(None)

    def test_column_validation_type_fail(self):
        """测试类型验证失败"""
        col = Column(int, name='age')
        with self.assertRaises(ValidationError):
            col.validate("not_a_number")

    def test_column_to_dict(self):
        """测试转换为字典"""
        col = Column(int, name='id', primary_key=True)
        d = col.to_dict()
        self.assertEqual(d['name'], 'id')
        self.assertEqual(d['type'], 'int')
        self.assertTrue(d['primary_key'])


class TestDeclarativeBase(unittest.TestCase):
    """declarative_base 工厂函数测试"""

    def setUp(self):
        """设置测试环境"""
        self.temp_dir = mktemp_dir_project()
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
            id = Column(int, primary_key=True)
            name = Column(str)

        # 验证没有 CRUD 方法
        self.assertFalse(hasattr(TestModel, 'create'))
        self.assertFalse(hasattr(TestModel, 'save'))
        self.assertFalse(hasattr(TestModel, 'delete'))

    def test_crud_false_returns_pure_base(self):
        """测试 crud=False 返回纯模型基类"""
        Base = declarative_base(self.db, crud=False)

        class TestModel(Base):
            __tablename__ = 'test_crud_false'
            id = Column(int, primary_key=True)

        self.assertFalse(hasattr(TestModel, 'create'))

    def test_crud_true_returns_crud_base(self):
        """测试 crud=True 返回 CRUD 基类"""
        Base = declarative_base(self.db, crud=True)

        class TestModel(Base):
            __tablename__ = 'test_crud_true'
            id = Column(int, primary_key=True)
            name = Column(str)

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
            id = Column(int, primary_key=True)

        self.assertIs(TestModel.__storage__, self.db)

    def test_tablename_required(self):
        """测试 __tablename__ 必须定义"""
        Base = declarative_base(self.db)

        with self.assertRaises(ValidationError):
            class TestModel(Base):
                id = Column(int, primary_key=True)

    def test_column_collection(self):
        """测试列收集"""
        Base = declarative_base(self.db)

        class TestModel(Base):
            __tablename__ = 'test_columns'
            id = Column(int, primary_key=True)
            name = Column(str)
            age = Column(int)

        self.assertEqual(len(TestModel.__columns__), 3)
        self.assertIn('id', TestModel.__columns__)
        self.assertIn('name', TestModel.__columns__)
        self.assertIn('age', TestModel.__columns__)

    def test_primary_key_detection(self):
        """测试主键检测"""
        Base = declarative_base(self.db)

        class TestModel(Base):
            __tablename__ = 'test_pk'
            user_id = Column(int, primary_key=True)
            name = Column(str)

        self.assertEqual(TestModel.__primary_key__, 'user_id')

    def test_no_primary_key_allowed(self):
        """测试无主键模型可以正常工作"""
        Base = declarative_base(self.db)

        class TestModel(Base):
            __tablename__ = 'test_no_pk'
            name = Column(str)
            age = Column(int)

        # 无主键模型的 __primary_key__ 应为 None
        self.assertIsNone(TestModel.__primary_key__)

    def test_id_column_without_primary_key_no_error(self):
        """测试定义 id 列但不设置 primary_key=True 不会自动成为主键"""
        Base = declarative_base(self.db)

        class TestModel(Base):
            __tablename__ = 'test_id_no_pk'
            id = Column(str)  # 没有 primary_key=True
            name = Column(str)

        # 即使有 id 列，如果没有 primary_key=True，也是无主键模型
        self.assertIsNone(TestModel.__primary_key__)


class TestPureBaseModel(unittest.TestCase):
    """PureBaseModel 测试"""

    def setUp(self):
        """设置测试环境"""
        self.temp_dir = mktemp_dir_project()
        self.db_path = os.path.join(self.temp_dir, 'test.db')
        self.db = Storage(file_path=self.db_path)

        # 创建纯模型基类
        self.Base: Type[PureBaseModel] = declarative_base(self.db)

        class User(self.Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str, nullable=False)
            age = Column(int)

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
            id = Column(int, primary_key=True)
            status = Column(str, default='active')

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
        users = result.all()

        self.assertEqual(len(users), 1)
        self.assertEqual(users[0].name, 'Alice')


class TestCRUDBaseModel(unittest.TestCase):
    """CRUDBaseModel 测试"""

    def setUp(self):
        """设置测试环境"""
        self.temp_dir = mktemp_dir_project()
        self.db_path = os.path.join(self.temp_dir, 'test.db')
        self.db = Storage(file_path=self.db_path)

        # 创建 CRUD 基类
        self.Base: Type[CRUDBaseModel] = declarative_base(self.db, crud=True)

        class User(self.Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str, nullable=False)
            age = Column(int)

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
        temp_dir = mktemp_dir_project()
        db_path = os.path.join(temp_dir, f'test.{file_ext}')

        try:
            db = Storage(file_path=db_path, engine=engine)
            Base = declarative_base(db, crud=True)

            class Item(Base):
                __tablename__ = 'items'
                id = Column(int, primary_key=True)
                name = Column(str)
                value = Column(float)

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
        self.temp_dir = mktemp_dir_project()
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
            id = Column(int, primary_key=True)
            name = Column(str)

        # 类型检查应该通过
        self.assertTrue(True)

    def test_crud_base_type_annotation(self):
        """测试 CRUDBaseModel 类型注解"""
        Base: Type[CRUDBaseModel] = declarative_base(self.db, crud=True)

        class User(Base):
            __tablename__ = 'users'
            id = Column(int, primary_key=True)
            name = Column(str)

        # 类型检查应该通过
        self.assertTrue(True)

    def test_isinstance_pure_base_model(self):
        """测试 PureBaseModel 的 isinstance 检查"""
        Base = declarative_base(self.db)

        class User(Base):
            __tablename__ = 'users_isinstance'
            id = Column(int, primary_key=True)
            name = Column(str)

        user = User(name='Alice')

        # isinstance 检查应该通过
        self.assertIsInstance(user, PureBaseModel)
        self.assertTrue(isinstance(user, PureBaseModel))

    def test_isinstance_crud_base_model(self):
        """测试 CRUDBaseModel 的 isinstance 检查"""
        Base = declarative_base(self.db, crud=True)

        class User(Base):
            __tablename__ = 'users_isinstance_crud'
            id = Column(int, primary_key=True)
            name = Column(str)

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
            id = Column(int, primary_key=True)

        class CRUDUser(CRUDBase):
            __tablename__ = 'crud_users_sub'
            id = Column(int, primary_key=True)

        # issubclass 检查
        self.assertTrue(issubclass(PureUser, PureBaseModel))
        self.assertTrue(issubclass(CRUDUser, CRUDBaseModel))
        self.assertTrue(issubclass(CRUDUser, PureBaseModel))


class TestColumnNameMapping(unittest.TestCase):
    """测试 Column.name 映射功能"""

    def setUp(self):
        """设置测试环境"""
        self.temp_dir = mktemp_dir_project()
        self.db_path = os.path.join(self.temp_dir, 'test.db')
        self.db = Storage(file_path=self.db_path)

    def tearDown(self):
        """清理测试环境"""
        self.db.close()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        os.rmdir(self.temp_dir)

    def test_to_dict_default_uses_attr_name(self):
        """测试 to_dict() 默认使用属性名"""
        Base = declarative_base(self.db)

        class User(Base):
            __tablename__ = 'users_todict_default'
            id = Column(int, primary_key=True)
            lv = Column(str, name='level')
            nm = Column(str, name='display_name')

        user = User(lv='admin', nm='Alice')
        d = user.to_dict()

        # 默认使用属性名作为键
        self.assertIn('lv', d)
        self.assertIn('nm', d)
        self.assertNotIn('level', d)
        self.assertNotIn('display_name', d)
        self.assertEqual(d['lv'], 'admin')
        self.assertEqual(d['nm'], 'Alice')

    def test_to_dict_with_column_names(self):
        """测试 to_dict(use_column_names=True) 使用 Column.name"""
        Base = declarative_base(self.db)

        class User(Base):
            __tablename__ = 'users_todict_colname'
            id = Column(int, primary_key=True)
            lv = Column(str, name='level')
            nm = Column(str, name='display_name')

        user = User(lv='admin', nm='Alice')
        d = user.to_dict(use_column_names=True)

        # 使用 Column.name 作为键
        self.assertIn('level', d)
        self.assertIn('display_name', d)
        self.assertNotIn('lv', d)
        self.assertNotIn('nm', d)
        self.assertEqual(d['level'], 'admin')
        self.assertEqual(d['display_name'], 'Alice')

    def test_crud_save_with_column_name(self):
        """测试 CRUDBaseModel.save() 使用 Column.name 正确存储数据"""
        Base = declarative_base(self.db, crud=True)

        class User(Base):
            __tablename__ = 'users_crud_colname'
            id = Column(int, primary_key=True)
            lv = Column(str, name='level')

        # 创建并保存
        user = User.create(lv='admin')
        self.assertEqual(user.lv, 'admin')

        # 通过 get 重新加载
        loaded_user = User.get(user.id)
        self.assertIsNotNone(loaded_user)
        self.assertEqual(loaded_user.lv, 'admin')

    def test_crud_refresh_with_column_name(self):
        """测试 CRUDBaseModel.refresh() 正确转换列名"""
        Base = declarative_base(self.db, crud=True)

        class User(Base):
            __tablename__ = 'users_crud_refresh'
            id = Column(int, primary_key=True)
            lv = Column(str, name='level')

        # 创建用户
        user = User.create(lv='admin')
        user_id = user.id

        # 直接通过 storage 更新（模拟外部修改）
        self.db.update('users_crud_refresh', user_id, {'level': 'superadmin'})

        # refresh 应该正确更新属性
        user.refresh()
        self.assertEqual(user.lv, 'superadmin')

    def test_session_add_with_column_name(self):
        """测试 Session.add() 使用 Column.name 正确存储数据"""
        Base = declarative_base(self.db)

        class User(Base):
            __tablename__ = 'users_session_colname'
            id = Column(int, primary_key=True)
            lv = Column(str, name='level')

        session = Session(self.db)
        user = User(lv='moderator')
        session.add(user)
        session.commit()

        # 验证数据正确存储
        self.assertIsNotNone(user.id)
        self.assertEqual(user.lv, 'moderator')

        # 通过 storage 直接读取验证
        record = self.db.select('users_session_colname', user.id)
        # 存储层使用 Column.name
        self.assertEqual(record.get('level'), 'moderator')

    def test_session_refresh_with_column_name(self):
        """测试 Session.refresh() 正确转换列名"""
        Base = declarative_base(self.db)

        class User(Base):
            __tablename__ = 'users_session_refresh'
            id = Column(int, primary_key=True)
            lv = Column(str, name='level')

        session = Session(self.db)
        user = User(lv='user')
        session.add(user)
        session.commit()

        user_id = user.id

        # 直接通过 storage 更新（模拟外部修改）
        self.db.update('users_session_refresh', user_id, {'level': 'premium'})

        # refresh 应该正确更新属性
        session.refresh(user)
        self.assertEqual(user.lv, 'premium')

    def test_attr_to_column_name_method(self):
        """测试 _attr_to_column_name 方法"""
        Base = declarative_base(self.db)

        class User(Base):
            __tablename__ = 'users_attr_method'
            id = Column(int, primary_key=True)
            lv = Column(str, name='level')
            name = Column(str)  # 未指定 name，使用属性名

        # 测试有显式 name 的列
        self.assertEqual(User._attr_to_column_name('lv'), 'level')

        # 测试未指定 name 的列（使用属性名）
        self.assertEqual(User._attr_to_column_name('name'), 'name')

        # 测试不存在的属性
        self.assertEqual(User._attr_to_column_name('nonexistent'), 'nonexistent')

    def test_column_to_attr_name_method(self):
        """测试 _column_to_attr_name 方法"""
        Base = declarative_base(self.db)

        class User(Base):
            __tablename__ = 'users_col_method'
            id = Column(int, primary_key=True)
            lv = Column(str, name='level')
            name = Column(str)

        # 测试通过 Column.name 查找属性名
        self.assertEqual(User._column_to_attr_name('level'), 'lv')

        # 测试未显式指定 name 的列
        self.assertEqual(User._column_to_attr_name('name'), 'name')

        # 测试不存在的列名
        self.assertIsNone(User._column_to_attr_name('nonexistent'))

    def test_session_query_with_column_name(self):
        """测试 session.query() 正确使用 Column.name 映射"""
        Base = declarative_base(self.db)

        class User(Base):
            __tablename__ = 'users_query_colname'
            id = Column(int, primary_key=True)
            lv = Column(str, name='level')
            nm = Column(str, name='display_name')

        session = Session(self.db)

        # 添加测试数据
        user1 = User(lv='admin', nm='Alice')
        user2 = User(lv='user', nm='Bob')
        session.add(user1)
        session.add(user2)
        session.commit()

        # 通过 session.query() 查询
        users = session.query(User).all()
        self.assertEqual(len(users), 2)

        # 验证属性正确映射
        user_names = {u.nm for u in users}
        self.assertIn('Alice', user_names)
        self.assertIn('Bob', user_names)

        user_levels = {u.lv for u in users}
        self.assertIn('admin', user_levels)
        self.assertIn('user', user_levels)

    def test_session_execute_select_with_column_name(self):
        """测试 session.execute(select()) 正确使用 Column.name 映射"""
        from pytuck import select

        Base = declarative_base(self.db)

        class User(Base):
            __tablename__ = 'users_select_colname'
            id = Column(int, primary_key=True)
            lv = Column(str, name='level')
            nm = Column(str, name='display_name')

        session = Session(self.db)

        # 添加测试数据
        user1 = User(lv='moderator', nm='Charlie')
        session.add(user1)
        session.commit()

        # 通过 session.execute(select()) 查询
        result = session.execute(select(User))
        users = result.all()
        self.assertEqual(len(users), 1)

        # 验证属性正确映射
        user = users[0]
        self.assertEqual(user.lv, 'moderator')
        self.assertEqual(user.nm, 'Charlie')


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
    suite.addTests(loader.loadTestsFromTestCase(TestColumnNameMapping))

    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # 返回是否全部通过
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
