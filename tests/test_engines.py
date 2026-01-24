"""
Pytuck 多存储引擎测试

测试所有6种存储引擎的功能：
- binary: 二进制引擎（默认）
- json: JSON引擎
- csv: CSV引擎（ZIP压缩）
- sqlite: SQLite引擎
- excel: Excel引擎（需要 openpyxl）
- xml: XML引擎（需要 lxml）
"""

import os
import sys
import unittest
from typing import Type, Dict, Any

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from examples._common import get_project_temp_dir
from pytuck import Storage, declarative_base, Session, Column, PureBaseModel, select, insert, update, delete
from pytuck.backends import BackendRegistry


def is_engine_available(engine_name: str) -> bool:
    """检查引擎是否可用"""
    backend_class = BackendRegistry.get(engine_name)
    if not backend_class:
        return False
    return backend_class.is_available()


class BaseEngineTest(unittest.TestCase):
    """引擎测试基类"""

    engine_name: str = 'binary'
    file_extension: str = 'db'

    def setUp(self) -> None:
        """测试前设置"""
        # 创建临时文件
        self.temp_dir = get_project_temp_dir()
        self.db_file = os.path.join(self.temp_dir, f'test_{self.engine_name}.{self.file_extension}')

        # 清理旧文件
        if os.path.exists(self.db_file):
            os.remove(self.db_file)

        # 创建数据库
        self.db = Storage(file_path=self.db_file, engine=self.engine_name)
        Base: Type[PureBaseModel] = declarative_base(self.db)

        class Student(Base):
            __tablename__ = 'students'
            id = Column('id', int, primary_key=True)
            name = Column('name', str, nullable=False, index=True)
            age = Column('age', int)
            email = Column('email', str, nullable=True)
            active = Column('active', bool)
            avatar = Column('avatar', bytes, nullable=True)

        self.Student = Student
        self.session = Session(self.db)

    def tearDown(self) -> None:
        """测试后清理"""
        self.session.close()
        self.db.close()

        # 清理测试文件
        if os.path.exists(self.db_file):
            try:
                os.remove(self.db_file)
            except:
                pass

    def test_insert_and_query(self) -> None:
        """测试插入和查询"""
        # 插入数据
        test_data = [
            {'name': 'Alice', 'age': 20, 'email': 'alice@example.com', 'active': True, 'avatar': b'avatar_alice'},
            {'name': 'Bob', 'age': 22, 'email': 'bob@example.com', 'active': False, 'avatar': b'avatar_bob'},
            {'name': 'Charlie', 'age': 19, 'email': None, 'active': True, 'avatar': None},
        ]

        for data in test_data:
            stmt = insert(self.Student).values(**data)
            self.session.execute(stmt)
        self.session.commit()

        # 查询所有
        stmt = select(self.Student)
        result = self.session.execute(stmt)
        students = result.all()
        self.assertEqual(len(students), 3)

        # 条件查询
        stmt = select(self.Student).where(self.Student.age >= 20)
        result = self.session.execute(stmt)
        adults = result.all()
        self.assertEqual(len(adults), 2)

    def test_update(self) -> None:
        """测试更新"""
        # 插入数据
        stmt = insert(self.Student).values(name='Alice', age=20, email='alice@example.com', active=True, avatar=b'avatar')
        self.session.execute(stmt)
        self.session.commit()

        # 更新
        stmt = update(self.Student).where(self.Student.name == 'Alice').values(age=21, email='alice.new@example.com')
        self.session.execute(stmt)
        self.session.commit()

        # 验证更新
        stmt = select(self.Student).filter_by(name='Alice')
        result = self.session.execute(stmt)
        alice = result.first()
        self.assertEqual(alice.age, 21)
        self.assertEqual(alice.email, 'alice.new@example.com')

    def test_delete(self) -> None:
        """测试删除"""
        # 插入数据
        for name in ['Alice', 'Bob', 'Charlie']:
            stmt = insert(self.Student).values(name=name, age=20, active=True, avatar=b'avatar')
            self.session.execute(stmt)
        self.session.commit()

        # 删除
        stmt = delete(self.Student).where(self.Student.name == 'Bob')
        self.session.execute(stmt)
        self.session.commit()

        # 验证删除
        stmt = select(self.Student)
        result = self.session.execute(stmt)
        students = result.all()
        self.assertEqual(len(students), 2)
        self.assertEqual({s.name for s in students}, {'Alice', 'Charlie'})

    def test_persistence(self) -> None:
        """测试数据持久化"""
        # 插入数据
        stmt = insert(self.Student).values(name='Alice', age=20, email='alice@example.com', active=True, avatar=b'avatar_alice')
        self.session.execute(stmt)
        self.session.commit()

        # 关闭数据库
        self.session.close()
        self.db.close()

        # 重新打开
        db2 = Storage(file_path=self.db_file, engine=self.engine_name)
        Base2: Type[PureBaseModel] = declarative_base(db2)

        class Student2(Base2):
            __tablename__ = 'students'
            id = Column('id', int, primary_key=True)
            name = Column('name', str, nullable=False, index=True)
            age = Column('age', int)
            email = Column('email', str, nullable=True)
            active = Column('active', bool)
            avatar = Column('avatar', bytes, nullable=True)

        session2 = Session(db2)

        # 验证数据
        stmt = select(Student2)
        result = session2.execute(stmt)
        students = result.all()
        self.assertEqual(len(students), 1)
        self.assertEqual(students[0].name, 'Alice')
        self.assertEqual(students[0].age, 20)
        self.assertEqual(students[0].active, True)
        self.assertEqual(students[0].avatar, b'avatar_alice')

        session2.close()
        db2.close()

    def test_null_values(self) -> None:
        """测试 NULL 值处理"""
        # 插入包含 NULL 的数据
        stmt = insert(self.Student).values(name='Alice', age=20, email=None, active=True, avatar=None)
        self.session.execute(stmt)
        self.session.commit()

        # 查询验证
        stmt = select(self.Student).filter_by(name='Alice')
        result = self.session.execute(stmt)
        alice = result.first()
        self.assertIsNone(alice.email)
        self.assertIsNone(alice.avatar)

    def test_boolean_values(self) -> None:
        """测试布尔值处理"""
        # 插入布尔值
        stmt = insert(self.Student).values(name='Alice', age=20, active=True, avatar=b'avatar')
        self.session.execute(stmt)

        stmt = insert(self.Student).values(name='Bob', age=25, active=False, avatar=b'avatar')
        self.session.execute(stmt)
        self.session.commit()

        # 查询验证
        stmt = select(self.Student).filter_by(active=True)
        result = self.session.execute(stmt)
        active_students = result.all()
        self.assertEqual(len(active_students), 1)
        self.assertEqual(active_students[0].name, 'Alice')

    def test_bytes_values(self) -> None:
        """测试二进制数据处理"""
        # 插入二进制数据
        avatar_data = b'binary_avatar_data_1234567890'
        stmt = insert(self.Student).values(name='Alice', age=20, active=True, avatar=avatar_data)
        self.session.execute(stmt)
        self.session.commit()

        # 查询验证
        stmt = select(self.Student).filter_by(name='Alice')
        result = self.session.execute(stmt)
        alice = result.first()
        self.assertEqual(alice.avatar, avatar_data)


# 为每个引擎创建测试类
@unittest.skipUnless(is_engine_available('binary'), "Binary engine not available")
class TestBinaryEngine(BaseEngineTest):
    """二进制引擎测试"""
    engine_name = 'binary'
    file_extension = 'db'


@unittest.skipUnless(is_engine_available('json'), "JSON engine not available")
class TestJSONEngine(BaseEngineTest):
    """JSON引擎测试"""
    engine_name = 'json'
    file_extension = 'json'


@unittest.skipUnless(is_engine_available('csv'), "CSV engine not available")
class TestCSVEngine(BaseEngineTest):
    """CSV引擎测试"""
    engine_name = 'csv'
    file_extension = 'zip'


@unittest.skipUnless(is_engine_available('sqlite'), "SQLite engine not available")
class TestSQLiteEngine(BaseEngineTest):
    """SQLite引擎测试"""
    engine_name = 'sqlite'
    file_extension = 'sqlite'


@unittest.skipUnless(is_engine_available('excel'), "Excel engine not available (install pytuck[excel])")
class TestExcelEngine(BaseEngineTest):
    """Excel引擎测试"""
    engine_name = 'excel'
    file_extension = 'xlsx'


@unittest.skipUnless(is_engine_available('xml'), "XML engine not available (install pytuck[xml])")
class TestXMLEngine(BaseEngineTest):
    """XML引擎测试"""
    engine_name = 'xml'
    file_extension = 'xml'


class TestEngineAvailability(unittest.TestCase):
    """引擎可用性测试"""

    def test_binary_engine_always_available(self) -> None:
        """测试二进制引擎总是可用"""
        self.assertTrue(is_engine_available('binary'))

    def test_json_engine_always_available(self) -> None:
        """测试 JSON 引擎总是可用（标准库）"""
        self.assertTrue(is_engine_available('json'))

    def test_csv_engine_always_available(self) -> None:
        """测试 CSV 引擎总是可用（标准库）"""
        self.assertTrue(is_engine_available('csv'))

    def test_sqlite_engine_always_available(self) -> None:
        """测试 SQLite 引擎总是可用（标准库）"""
        self.assertTrue(is_engine_available('sqlite'))

    def test_optional_engines(self) -> None:
        """测试可选引擎"""
        # Excel 和 XML 引擎可能不可用
        excel_available = is_engine_available('excel')
        xml_available = is_engine_available('xml')

        # 只是检查，不断言
        print(f"\nExcel engine available: {excel_available}")
        print(f"XML engine available: {xml_available}")


if __name__ == '__main__':
    # 打印可用引擎信息
    print("\n" + "="*60)
    print("Pytuck 多存储引擎测试")
    print("="*60)
    print("\n可用引擎:")
    for engine in ['binary', 'json', 'csv', 'sqlite', 'excel', 'xml']:
        available = is_engine_available(engine)
        status = "✓ 可用" if available else "✗ 不可用"
        print(f"  {engine:10} : {status}")
    print("="*60 + "\n")

    unittest.main()
