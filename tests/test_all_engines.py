"""
Pytuck - 所有存储引擎综合测试

测试所有6种存储引擎的功能：
- binary: 二进制引擎（默认）
- json: JSON引擎
- csv: CSV引擎（ZIP压缩）
- sqlite: SQLite引擎
- excel: Excel引擎（需要 openpyxl）
- xml: XML引擎（需要 lxml）
"""

import sys
import tempfile
from datetime import datetime, date, timedelta, timezone
from pathlib import Path
from typing import Type

import pytest

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from pytuck import Storage, declarative_base, Session, Column, PureBaseModel
from pytuck import select, insert, update, delete
from pytuck.backends import BackendRegistry


# 所有引擎配置：(引擎名称, 文件扩展名)
ALL_ENGINES = [
    ('binary', 'db'),
    ('json', 'json'),
    ('csv', 'zip'),
    ('sqlite', 'sqlite'),
    ('excel', 'xlsx'),
    ('xml', 'xml'),
]


def is_engine_available(engine_name: str) -> bool:
    """检查引擎是否可用"""
    backend_class = BackendRegistry.get(engine_name)
    return backend_class is not None and backend_class.is_available()


def get_skip_reason(engine_name: str) -> str:
    """获取跳过引擎的原因"""
    backend_class = BackendRegistry.get(engine_name)
    if backend_class and backend_class.REQUIRED_DEPENDENCIES:
        deps = ', '.join(backend_class.REQUIRED_DEPENDENCIES)
        return f"需要安装依赖: {deps}"
    return f"引擎 '{engine_name}' 不可用"


@pytest.fixture
def temp_db_path(tmp_path: Path):
    """提供临时数据库文件路径的工厂 fixture"""
    def _make_path(engine_name: str, file_ext: str) -> Path:
        return tmp_path / f'test_{engine_name}.{file_ext}'
    return _make_path


class TestAllEngines:
    """所有存储引擎的综合测试"""

    @pytest.mark.parametrize("engine_name,file_ext", ALL_ENGINES)
    def test_engine_crud_operations(self, engine_name: str, file_ext: str, tmp_path: Path) -> None:
        """
        测试引擎的 CRUD 操作

        Args:
            engine_name: 引擎名称
            file_ext: 文件扩展名
            tmp_path: pytest 提供的临时目录
        """
        # 检查引擎是否可用
        if not is_engine_available(engine_name):
            pytest.skip(get_skip_reason(engine_name))

        db_file = tmp_path / f'test_{engine_name}.{file_ext}'

        # 1. 创建数据库
        db = Storage(file_path=str(db_file), engine=engine_name)
        Base: Type[PureBaseModel] = declarative_base(db)

        class Student(Base):
            __tablename__ = 'students'
            id = Column(int, primary_key=True)
            name = Column(str, nullable=False, index=True)
            age = Column(int)
            email = Column(str, nullable=True)
            active = Column(bool)
            avatar = Column(bytes, nullable=True)

        session = Session(db)

        # 2. 插入测试数据
        test_data = [
            {'name': 'Alice', 'age': 20, 'email': 'alice@example.com', 'active': True, 'avatar': b'avatar_alice'},
            {'name': 'Bob', 'age': 22, 'email': 'bob@example.com', 'active': False, 'avatar': b'avatar_bob'},
            {'name': 'Charlie', 'age': 19, 'email': None, 'active': True, 'avatar': None},
            {'name': 'David', 'age': 21, 'email': 'david@example.com', 'active': True, 'avatar': b'avatar_david'},
            {'name': 'Eve', 'age': 23, 'email': 'eve@example.com', 'active': False, 'avatar': b'avatar_eve'},
        ]

        for data in test_data:
            stmt = insert(Student).values(**data)
            session.execute(stmt)
        session.commit()

        # 3. 查询测试
        # 按 ID 查询
        stmt = select(Student).where(Student.id == 1)
        alice = session.execute(stmt).first()
        assert alice is not None
        assert alice.name == 'Alice'
        assert alice.age == 20
        assert alice.active is True
        assert alice.avatar == b'avatar_alice'

        # 索引查询
        stmt = select(Student).filter_by(name='Bob')
        bob = session.execute(stmt).first()
        assert bob is not None
        assert bob.email == 'bob@example.com'
        assert bob.active is False

        # 条件查询
        stmt = select(Student).filter_by(active=True)
        active_students = session.execute(stmt).all()
        assert len(active_students) == 3  # Alice, Charlie, David

        # 排序查询
        stmt = select(Student).order_by('age')
        sorted_students = session.execute(stmt).all()
        assert sorted_students[0].name == 'Charlie'  # 最年轻
        assert sorted_students[-1].name == 'Eve'  # 最年长

        # 4. 更新测试
        stmt = update(Student).where(Student.id == 1).values(age=21, email='alice.new@example.com')
        session.execute(stmt)
        session.commit()

        # 验证更新
        stmt = select(Student).where(Student.id == 1)
        alice_updated = session.execute(stmt).first()
        assert alice_updated.age == 21
        assert alice_updated.email == 'alice.new@example.com'

        # 5. 删除测试
        stmt = delete(Student).where(Student.name == 'Charlie')
        session.execute(stmt)
        session.commit()

        # 验证删除
        stmt = select(Student)
        remaining = session.execute(stmt).all()
        assert len(remaining) == 4

        # 6. 持久化测试
        session.close()
        db.close()

        # 验证文件已创建
        assert db_file.exists()

        # 7. 重新加载测试
        db2 = Storage(file_path=str(db_file), engine=engine_name)
        Base2: Type[PureBaseModel] = declarative_base(db2)

        class Student2(Base2):
            __tablename__ = 'students'
            id = Column(int, primary_key=True)
            name = Column(str, nullable=False, index=True)
            age = Column(int)
            email = Column(str, nullable=True)
            active = Column(bool)
            avatar = Column(bytes, nullable=True)

        session2 = Session(db2)

        # 验证数据
        stmt = select(Student2)
        all_students = session2.execute(stmt).all()
        assert len(all_students) == 4

        # 验证具体数据
        stmt = select(Student2).where(Student2.id == 1)
        alice2 = session2.execute(stmt).first()
        assert alice2.age == 21
        assert alice2.email == 'alice.new@example.com'
        assert alice2.active is True
        assert alice2.avatar == b'avatar_alice'

        # 验证 bytes 类型
        stmt = select(Student2).where(Student2.id == 2)
        bob2 = session2.execute(stmt).first()
        assert bob2.avatar == b'avatar_bob'
        assert bob2.active is False

        # 索引查询验证
        stmt = select(Student2).filter_by(name='David')
        david = session2.execute(stmt).first()
        assert david.name == 'David'
        assert david.age == 21

        session2.close()
        db2.close()

    @pytest.mark.parametrize("engine_name,file_ext", ALL_ENGINES)
    def test_engine_null_handling(self, engine_name: str, file_ext: str, tmp_path: Path) -> None:
        """
        测试引擎的 NULL 值处理

        Args:
            engine_name: 引擎名称
            file_ext: 文件扩展名
            tmp_path: pytest 提供的临时目录
        """
        if not is_engine_available(engine_name):
            pytest.skip(get_skip_reason(engine_name))

        db_file = tmp_path / f'test_null_{engine_name}.{file_ext}'

        db = Storage(file_path=str(db_file), engine=engine_name)
        Base: Type[PureBaseModel] = declarative_base(db)

        class NullTest(Base):
            __tablename__ = 'null_test'
            id = Column(int, primary_key=True)
            str_field = Column(str, nullable=True)
            int_field = Column(int, nullable=True)
            bytes_field = Column(bytes, nullable=True)

        session = Session(db)

        # 插入包含 NULL 的数据
        session.execute(insert(NullTest).values(str_field='test', int_field=1, bytes_field=b'data'))
        session.execute(insert(NullTest).values(str_field=None, int_field=None, bytes_field=None))
        session.execute(insert(NullTest).values(str_field='', int_field=0, bytes_field=b''))
        session.commit()

        # 查询 NULL 值
        stmt = select(NullTest).filter_by(str_field=None)
        null_records = session.execute(stmt).all()
        assert len(null_records) == 1
        assert null_records[0].int_field is None
        assert null_records[0].bytes_field is None

        # 查询空字符串（不是 NULL）
        stmt = select(NullTest).where(NullTest.str_field == '')
        empty_records = session.execute(stmt).all()
        assert len(empty_records) == 1
        assert empty_records[0].int_field == 0
        assert empty_records[0].bytes_field == b''

        session.close()
        db.close()

    @pytest.mark.parametrize("engine_name,file_ext", ALL_ENGINES)
    def test_engine_index_query(self, engine_name: str, file_ext: str, tmp_path: Path) -> None:
        """
        测试引擎的索引查询性能

        Args:
            engine_name: 引擎名称
            file_ext: 文件扩展名
            tmp_path: pytest 提供的临时目录
        """
        if not is_engine_available(engine_name):
            pytest.skip(get_skip_reason(engine_name))

        db_file = tmp_path / f'test_index_{engine_name}.{file_ext}'

        db = Storage(file_path=str(db_file), engine=engine_name)
        Base: Type[PureBaseModel] = declarative_base(db)

        class IndexTest(Base):
            __tablename__ = 'index_test'
            id = Column(int, primary_key=True)
            indexed_name = Column(str, index=True)
            non_indexed_value = Column(str)

        session = Session(db)

        # 插入测试数据
        for i in range(100):
            session.execute(insert(IndexTest).values(
                indexed_name=f'name_{i}',
                non_indexed_value=f'value_{i}'
            ))
        session.commit()

        # 索引查询
        stmt = select(IndexTest).filter_by(indexed_name='name_50')
        result = session.execute(stmt).first()
        assert result is not None
        assert result.indexed_name == 'name_50'
        assert result.non_indexed_value == 'value_50'

        # 非索引查询
        stmt = select(IndexTest).where(IndexTest.non_indexed_value == 'value_75')
        result = session.execute(stmt).first()
        assert result is not None
        assert result.indexed_name == 'name_75'

        session.close()
        db.close()

    @pytest.mark.parametrize("engine_name,file_ext", ALL_ENGINES)
    def test_engine_new_types_persistence(self, engine_name: str, file_ext: str, tmp_path: Path) -> None:
        """
        测试引擎的新类型（datetime, date, timedelta, list, dict）持久化

        Args:
            engine_name: 引擎名称
            file_ext: 文件扩展名
            tmp_path: pytest 提供的临时目录
        """
        if not is_engine_available(engine_name):
            pytest.skip(get_skip_reason(engine_name))

        db_file = tmp_path / f'test_newtypes_{engine_name}.{file_ext}'

        # 1. 创建数据库
        db = Storage(file_path=str(db_file), engine=engine_name)
        Base: Type[PureBaseModel] = declarative_base(db)

        class Task(Base):
            __tablename__ = 'tasks'
            id = Column(int, primary_key=True)
            title = Column(str)
            created_at = Column(datetime, nullable=True)
            due_date = Column(date, nullable=True)
            duration = Column(timedelta, nullable=True)
            tags = Column(list, nullable=True)
            options = Column(dict, nullable=True)

        session = Session(db)

        # 2. 准备测试数据
        now = datetime(2024, 1, 15, 10, 30, 45, 123456)
        today = date(2024, 1, 20)
        duration = timedelta(hours=2, minutes=30, seconds=15)
        tags = ['important', 'urgent', 'review']
        options = {'priority': 1, 'notify': True, 'assignees': ['Alice', 'Bob']}

        # 插入数据
        stmt = insert(Task).values(
            title='Test Task',
            created_at=now,
            due_date=today,
            duration=duration,
            tags=tags,
            options=options
        )
        session.execute(stmt)

        # 插入带 NULL 值的数据
        stmt = insert(Task).values(
            title='Empty Task',
            created_at=None,
            due_date=None,
            duration=None,
            tags=None,
            options=None
        )
        session.execute(stmt)
        session.commit()

        # 3. 持久化
        session.close()
        db.close()

        # 验证文件已创建
        assert db_file.exists()

        # 4. 重新加载测试
        db2 = Storage(file_path=str(db_file), engine=engine_name)
        Base2: Type[PureBaseModel] = declarative_base(db2)

        class Task2(Base2):
            __tablename__ = 'tasks'
            id = Column(int, primary_key=True)
            title = Column(str)
            created_at = Column(datetime, nullable=True)
            due_date = Column(date, nullable=True)
            duration = Column(timedelta, nullable=True)
            tags = Column(list, nullable=True)
            options = Column(dict, nullable=True)

        session2 = Session(db2)

        # 5. 验证加载的数据
        stmt = select(Task2).where(Task2.id == 1)
        task1 = session2.execute(stmt).first()

        assert task1 is not None
        assert task1.title == 'Test Task'

        # 验证 datetime
        assert task1.created_at is not None
        assert isinstance(task1.created_at, datetime)
        assert task1.created_at.year == 2024
        assert task1.created_at.month == 1
        assert task1.created_at.day == 15
        assert task1.created_at.hour == 10
        assert task1.created_at.minute == 30

        # 验证 date
        assert task1.due_date is not None
        assert isinstance(task1.due_date, date)
        assert task1.due_date == today

        # 验证 timedelta
        assert task1.duration is not None
        assert isinstance(task1.duration, timedelta)
        assert task1.duration.total_seconds() == duration.total_seconds()

        # 验证 list
        assert task1.tags is not None
        assert isinstance(task1.tags, list)
        assert task1.tags == tags

        # 验证 dict
        assert task1.options is not None
        assert isinstance(task1.options, dict)
        assert task1.options == options

        # 6. 验证 NULL 值
        stmt = select(Task2).where(Task2.id == 2)
        task2 = session2.execute(stmt).first()

        assert task2 is not None
        assert task2.title == 'Empty Task'
        assert task2.created_at is None
        assert task2.due_date is None
        assert task2.duration is None
        assert task2.tags is None
        assert task2.options is None

        session2.close()
        db2.close()


# 允许直接运行测试
if __name__ == '__main__':
    pytest.main([__file__, '-v'])
