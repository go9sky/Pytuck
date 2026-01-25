"""
SQLite 原生 SQL 模式专项测试

测试 SQLite 后端在原生 SQL 模式（use_native_sql=True）下的行为：
- 全部 10 种类型的 CRUD 操作
- NULL 值查询（IS NULL / IS NOT NULL）
- 类型序列化/反序列化往返一致性
- 原生模式与兼容模式行为一致性
- Schema-only 加载验证
- 多列排序
"""

from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Type

import pytest

from pytuck import (
    Storage, Session, Column,
    PureBaseModel, declarative_base,
    select, insert, update, delete
)
from pytuck.common.options import SqliteBackendOptions


class TestNativeSqlModeDefault:
    """验证原生 SQL 模式默认配置"""

    def test_native_mode_enabled_by_default(self, tmp_path: Path) -> None:
        """验证 SQLite 后端默认启用原生 SQL 模式"""
        db_file = tmp_path / 'test_default.sqlite'
        db = Storage(file_path=str(db_file), engine='sqlite')

        # 验证默认选项
        assert SqliteBackendOptions().use_native_sql is True

        # 验证 Storage 检测到原生模式
        assert db.is_native_sql_mode is True

        db.close()

    def test_memory_mode_when_disabled(self, tmp_path: Path) -> None:
        """验证可以禁用原生 SQL 模式"""
        db_file = tmp_path / 'test_memory.sqlite'
        options = SqliteBackendOptions(use_native_sql=False)
        db = Storage(file_path=str(db_file), engine='sqlite', backend_options=options)

        # 验证非原生模式
        assert db.is_native_sql_mode is False

        db.close()


class TestNativeSqlAllTypes:
    """测试全部 10 种类型在原生 SQL 模式下的 CRUD"""

    def test_all_10_types_insert_and_query(self, tmp_path: Path) -> None:
        """测试全部 10 种类型的插入和查询"""
        db_file = tmp_path / 'test_all_types.sqlite'
        db = Storage(file_path=str(db_file), engine='sqlite')
        Base: Type[PureBaseModel] = declarative_base(db)

        class AllTypesModel(Base):
            __tablename__ = 'all_types'
            id = Column(int, primary_key=True)
            # 基础类型
            int_field = Column(int)
            str_field = Column(str)
            float_field = Column(float)
            bool_field = Column(bool)
            bytes_field = Column(bytes)
            # 扩展类型
            datetime_field = Column(datetime)
            date_field = Column(date)
            timedelta_field = Column(timedelta)
            list_field = Column(list)
            dict_field = Column(dict)

        session = Session(db)

        # 准备测试数据
        test_datetime = datetime(2025, 1, 25, 10, 30, 0)
        test_date = date(2025, 1, 25)
        test_timedelta = timedelta(hours=1, minutes=30, seconds=45)
        test_list = ['a', 'b', 'c', 1, 2, 3]
        test_dict = {'name': 'test', 'value': 123, 'nested': {'key': 'val'}}
        test_bytes = b'\x00\x01\x02\xff'

        # 插入记录
        stmt = insert(AllTypesModel).values(
            int_field=42,
            str_field='hello',
            float_field=3.14159,
            bool_field=True,
            bytes_field=test_bytes,
            datetime_field=test_datetime,
            date_field=test_date,
            timedelta_field=test_timedelta,
            list_field=test_list,
            dict_field=test_dict
        )
        session.execute(stmt)
        session.commit()

        # 查询记录
        result = session.execute(select(AllTypesModel)).first()
        assert result is not None

        # 验证所有类型
        assert result.int_field == 42
        assert result.str_field == 'hello'
        assert abs(result.float_field - 3.14159) < 0.0001
        assert result.bool_field is True
        assert result.bytes_field == test_bytes
        assert result.datetime_field == test_datetime
        assert result.date_field == test_date
        assert result.timedelta_field == test_timedelta
        assert result.list_field == test_list
        assert result.dict_field == test_dict

        session.close()
        db.close()

    def test_all_10_types_update(self, tmp_path: Path) -> None:
        """测试全部 10 种类型的更新"""
        db_file = tmp_path / 'test_update_types.sqlite'
        db = Storage(file_path=str(db_file), engine='sqlite')
        Base: Type[PureBaseModel] = declarative_base(db)

        class TypesModel(Base):
            __tablename__ = 'types'
            id = Column(int, primary_key=True)
            datetime_field = Column(datetime)
            list_field = Column(list)

        session = Session(db)

        # 插入初始数据
        original_dt = datetime(2025, 1, 1, 0, 0, 0)
        session.execute(insert(TypesModel).values(
            datetime_field=original_dt,
            list_field=[1, 2, 3]
        ))
        session.commit()

        # 更新数据
        new_dt = datetime(2025, 12, 31, 23, 59, 59)
        session.execute(
            update(TypesModel)
            .where(TypesModel.id == 1)
            .values(datetime_field=new_dt, list_field=['x', 'y', 'z'])
        )
        session.commit()

        # 验证更新
        result = session.execute(select(TypesModel)).first()
        assert result is not None
        assert result.datetime_field == new_dt
        assert result.list_field == ['x', 'y', 'z']

        session.close()
        db.close()

    def test_all_10_types_delete(self, tmp_path: Path) -> None:
        """测试删除操作"""
        db_file = tmp_path / 'test_delete_types.sqlite'
        db = Storage(file_path=str(db_file), engine='sqlite')
        Base: Type[PureBaseModel] = declarative_base(db)

        class SimpleModel(Base):
            __tablename__ = 'simple'
            id = Column(int, primary_key=True)
            name = Column(str)

        session = Session(db)

        # 插入多条记录
        for i in range(5):
            session.execute(insert(SimpleModel).values(name=f'item_{i}'))
        session.commit()

        # 验证插入
        assert len(session.execute(select(SimpleModel)).all()) == 5

        # 删除一条
        session.execute(delete(SimpleModel).where(SimpleModel.id == 3))
        session.commit()

        # 验证删除
        assert len(session.execute(select(SimpleModel)).all()) == 4

        session.close()
        db.close()


class TestNativeSqlNullHandling:
    """测试 NULL 值处理"""

    def test_null_query_is_null(self, tmp_path: Path) -> None:
        """测试 filter_by(field=None) 使用 IS NULL"""
        db_file = tmp_path / 'test_null.sqlite'
        db = Storage(file_path=str(db_file), engine='sqlite')
        Base: Type[PureBaseModel] = declarative_base(db)

        class NullModel(Base):
            __tablename__ = 'null_test'
            id = Column(int, primary_key=True)
            name = Column(str, nullable=True)
            value = Column(int, nullable=True)

        session = Session(db)

        # 插入包含 NULL 的数据
        session.execute(insert(NullModel).values(name='Alice', value=100))
        session.execute(insert(NullModel).values(name=None, value=None))
        session.execute(insert(NullModel).values(name='', value=0))
        session.commit()

        # 查询 NULL 值
        null_records = session.execute(
            select(NullModel).filter_by(name=None)
        ).all()
        assert len(null_records) == 1
        assert null_records[0].value is None

        # 查询空字符串（不是 NULL）
        empty_records = session.execute(
            select(NullModel).where(NullModel.name == '')
        ).all()
        assert len(empty_records) == 1
        assert empty_records[0].value == 0

        session.close()
        db.close()

    def test_null_for_all_nullable_types(self, tmp_path: Path) -> None:
        """测试所有可空类型的 NULL 值"""
        db_file = tmp_path / 'test_null_types.sqlite'
        db = Storage(file_path=str(db_file), engine='sqlite')
        Base: Type[PureBaseModel] = declarative_base(db)

        class NullableTypes(Base):
            __tablename__ = 'nullable_types'
            id = Column(int, primary_key=True)
            dt = Column(datetime, nullable=True)
            d = Column(date, nullable=True)
            td = Column(timedelta, nullable=True)
            lst = Column(list, nullable=True)
            dct = Column(dict, nullable=True)

        session = Session(db)

        # 插入全 NULL 记录
        session.execute(insert(NullableTypes).values(
            dt=None, d=None, td=None, lst=None, dct=None
        ))
        session.commit()

        # 验证读取
        result = session.execute(select(NullableTypes)).first()
        assert result is not None
        assert result.dt is None
        assert result.d is None
        assert result.td is None
        assert result.lst is None
        assert result.dct is None

        session.close()
        db.close()


class TestNativeSqlPersistence:
    """测试类型序列化/反序列化往返一致性"""

    def test_persistence_roundtrip(self, tmp_path: Path) -> None:
        """测试关闭并重新打开后数据一致性"""
        db_file = tmp_path / 'test_persist.sqlite'

        # 第一次打开，写入数据
        db1 = Storage(file_path=str(db_file), engine='sqlite')
        Base1: Type[PureBaseModel] = declarative_base(db1)

        class PersistModel(Base1):
            __tablename__ = 'persist'
            id = Column(int, primary_key=True)
            dt = Column(datetime)
            d = Column(date)
            td = Column(timedelta)
            lst = Column(list)
            dct = Column(dict)

        session1 = Session(db1)

        test_dt = datetime(2025, 6, 15, 12, 30, 45)
        test_date = date(2025, 6, 15)
        test_td = timedelta(days=1, hours=2, minutes=3, seconds=4.5)
        test_list = [1, 'two', 3.0, None, {'nested': True}]
        test_dict = {'a': 1, 'b': [1, 2, 3], 'c': {'nested': 'value'}}

        session1.execute(insert(PersistModel).values(
            dt=test_dt, d=test_date, td=test_td, lst=test_list, dct=test_dict
        ))
        session1.commit()
        session1.close()
        db1.close()

        # 第二次打开，读取数据
        db2 = Storage(file_path=str(db_file), engine='sqlite')
        Base2: Type[PureBaseModel] = declarative_base(db2)

        class PersistModel2(Base2):
            __tablename__ = 'persist'
            id = Column(int, primary_key=True)
            dt = Column(datetime)
            d = Column(date)
            td = Column(timedelta)
            lst = Column(list)
            dct = Column(dict)

        session2 = Session(db2)
        result = session2.execute(select(PersistModel2)).first()

        assert result is not None
        assert result.dt == test_dt
        assert result.d == test_date
        # timedelta 比较需要考虑浮点精度
        assert abs(result.td.total_seconds() - test_td.total_seconds()) < 0.01
        assert result.lst == test_list
        assert result.dct == test_dict

        session2.close()
        db2.close()


class TestNativeSqlModeConsistency:
    """验证原生模式与兼容模式行为一致"""

    def test_native_vs_memory_mode_results(self, tmp_path: Path) -> None:
        """原生模式和兼容模式应产生相同结果"""
        # 原生模式
        native_file = tmp_path / 'native.sqlite'
        native_db = Storage(
            file_path=str(native_file),
            engine='sqlite',
            backend_options=SqliteBackendOptions(use_native_sql=True)
        )
        NativeBase: Type[PureBaseModel] = declarative_base(native_db)

        class NativeModel(NativeBase):
            __tablename__ = 'test'
            id = Column(int, primary_key=True)
            name = Column(str)
            value = Column(int)

        native_session = Session(native_db)
        native_session.execute(insert(NativeModel).values(name='a', value=1))
        native_session.execute(insert(NativeModel).values(name='b', value=2))
        native_session.execute(insert(NativeModel).values(name='c', value=3))
        native_session.commit()

        native_result = native_session.execute(
            select(NativeModel).where(NativeModel.value >= 2)
        ).all()

        native_session.close()
        native_db.close()

        # 兼容模式
        memory_file = tmp_path / 'memory.sqlite'
        memory_db = Storage(
            file_path=str(memory_file),
            engine='sqlite',
            backend_options=SqliteBackendOptions(use_native_sql=False)
        )
        MemoryBase: Type[PureBaseModel] = declarative_base(memory_db)

        class MemoryModel(MemoryBase):
            __tablename__ = 'test'
            id = Column(int, primary_key=True)
            name = Column(str)
            value = Column(int)

        memory_session = Session(memory_db)
        memory_session.execute(insert(MemoryModel).values(name='a', value=1))
        memory_session.execute(insert(MemoryModel).values(name='b', value=2))
        memory_session.execute(insert(MemoryModel).values(name='c', value=3))
        memory_session.commit()

        memory_result = memory_session.execute(
            select(MemoryModel).where(MemoryModel.value >= 2)
        ).all()

        memory_session.close()
        memory_db.close()

        # 比较结果
        assert len(native_result) == len(memory_result) == 2
        assert {r.name for r in native_result} == {r.name for r in memory_result}


class TestNativeSqlSchemaOnlyLoad:
    """验证原生模式只加载 schema 不加载数据"""

    def test_schema_only_load(self, tmp_path: Path) -> None:
        """原生模式重新打开时 table.data 应为空"""
        db_file = tmp_path / 'schema_only.sqlite'

        # 第一次打开，写入数据
        db1 = Storage(file_path=str(db_file), engine='sqlite')
        Base1: Type[PureBaseModel] = declarative_base(db1)

        class DataModel(Base1):
            __tablename__ = 'data'
            id = Column(int, primary_key=True)
            value = Column(str)

        session1 = Session(db1)
        for i in range(100):
            session1.execute(insert(DataModel).values(value=f'item_{i}'))
        session1.commit()
        session1.close()
        db1.close()

        # 第二次打开
        db2 = Storage(file_path=str(db_file), engine='sqlite')

        # 验证 schema 已加载
        assert 'data' in db2.tables

        # 验证 table.data 为空（schema-only 加载）
        table = db2.tables['data']
        assert len(table.data) == 0

        # 但查询仍能正确返回数据
        Base2: Type[PureBaseModel] = declarative_base(db2)

        class DataModel2(Base2):
            __tablename__ = 'data'
            id = Column(int, primary_key=True)
            value = Column(str)

        session2 = Session(db2)
        results = session2.execute(select(DataModel2)).all()
        assert len(results) == 100

        session2.close()
        db2.close()


class TestNativeSqlMultiColumnOrderBy:
    """测试多列排序"""

    def test_multi_column_order_by(self, tmp_path: Path) -> None:
        """测试多列排序优先级"""
        db_file = tmp_path / 'order_by.sqlite'
        db = Storage(file_path=str(db_file), engine='sqlite')
        Base: Type[PureBaseModel] = declarative_base(db)

        class OrderModel(Base):
            __tablename__ = 'orders'
            id = Column(int, primary_key=True)
            category = Column(str)
            priority = Column(int)
            name = Column(str)

        session = Session(db)

        # 插入测试数据
        data = [
            ('A', 1, 'alice'),
            ('A', 2, 'bob'),
            ('B', 1, 'carol'),
            ('A', 1, 'dave'),
            ('B', 2, 'eve'),
        ]
        for cat, pri, name in data:
            session.execute(insert(OrderModel).values(
                category=cat, priority=pri, name=name
            ))
        session.commit()

        # 多列排序：先按 category 升序，再按 priority 降序
        results = session.execute(
            select(OrderModel)
            .order_by('category')
            .order_by('priority', desc=True)
        ).all()

        # 验证排序顺序
        # A 类别应该在前，且 priority=2 在 priority=1 之前
        assert results[0].category == 'A'
        assert results[0].priority == 2
        assert results[0].name == 'bob'

        # A 类别 priority=1 的两条记录
        a_pri1 = [r for r in results if r.category == 'A' and r.priority == 1]
        assert len(a_pri1) == 2

        # B 类别应该在后
        b_records = [r for r in results if r.category == 'B']
        assert len(b_records) == 2
        assert b_records[0].priority == 2  # priority=2 在前

        session.close()
        db.close()
