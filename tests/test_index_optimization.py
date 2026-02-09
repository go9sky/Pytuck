"""
查询索引优化测试

测试 SortedIndex 用于范围查询和 order_by 排序优化。
"""

import copy
import tempfile
from typing import Type

import pytest

from pytuck import (
    Storage, Session, Column, declarative_base,
    PureBaseModel, CRUDBaseModel,
    select, insert, update, delete,
    ValidationError,
)
from pytuck.core.index import BaseIndex, HashIndex, SortedIndex
from pytuck.query.builder import Condition


# ===== Fixtures =====

@pytest.fixture
def storage():
    """创建内存存储"""
    return Storage()


@pytest.fixture
def sorted_index_storage(storage):
    """创建带 SortedIndex 列的存储和模型"""
    Base: Type[PureBaseModel] = declarative_base(storage)

    class User(Base):
        __tablename__ = 'users'
        id = Column(int, primary_key=True)
        name = Column(str)
        age = Column(int, nullable=True, index='sorted')
        score = Column(float, nullable=True, index='hash')

    session = Session(storage)

    # 插入测试数据
    test_data = [
        {'name': 'Alice', 'age': 25, 'score': 90.0},
        {'name': 'Bob', 'age': 30, 'score': 85.0},
        {'name': 'Charlie', 'age': 20, 'score': 95.0},
        {'name': 'Diana', 'age': 35, 'score': 80.0},
        {'name': 'Eve', 'age': 28, 'score': 88.0},
        {'name': 'Frank', 'age': 22, 'score': 92.0},
        {'name': 'Grace', 'age': None, 'score': 70.0},  # age 为 None
        {'name': 'Henry', 'age': 40, 'score': 75.0},
    ]

    for data in test_data:
        stmt = insert(User).values(**data)
        session.execute(stmt)
    session.commit()

    return storage, User, session


# ===== A. Column 索引类型测试 =====

class TestColumnIndexType:
    """测试 Column.index 参数的索引类型选择"""

    def test_column_index_true_creates_hash(self, storage):
        """Column(index=True) 创建 HashIndex"""
        Base: Type[PureBaseModel] = declarative_base(storage)

        class Item(Base):
            __tablename__ = 'items_hash_true'
            id = Column(int, primary_key=True)
            code = Column(str, index=True)

        table = storage.get_table('items_hash_true')
        assert 'code' in table.indexes
        assert isinstance(table.indexes['code'], HashIndex)

    def test_column_index_hash_creates_hash(self, storage):
        """Column(index='hash') 创建 HashIndex"""
        Base: Type[PureBaseModel] = declarative_base(storage)

        class Item(Base):
            __tablename__ = 'items_hash_str'
            id = Column(int, primary_key=True)
            code = Column(str, index='hash')

        table = storage.get_table('items_hash_str')
        assert 'code' in table.indexes
        assert isinstance(table.indexes['code'], HashIndex)

    def test_column_index_sorted_creates_sorted(self, storage):
        """Column(index='sorted') 创建 SortedIndex"""
        Base: Type[PureBaseModel] = declarative_base(storage)

        class Item(Base):
            __tablename__ = 'items_sorted'
            id = Column(int, primary_key=True)
            value = Column(int, index='sorted')

        table = storage.get_table('items_sorted')
        assert 'value' in table.indexes
        assert isinstance(table.indexes['value'], SortedIndex)

    def test_column_index_invalid_raises(self):
        """Column(index='invalid') 抛出 ValidationError"""
        with pytest.raises(ValidationError, match="Unsupported index type"):
            Column(int, index='invalid')

    def test_column_index_false_no_index(self, storage):
        """Column(index=False) 不创建索引"""
        Base: Type[PureBaseModel] = declarative_base(storage)

        class Item(Base):
            __tablename__ = 'items_no_index'
            id = Column(int, primary_key=True)
            value = Column(int, index=False)

        table = storage.get_table('items_no_index')
        assert 'value' not in table.indexes


# ===== B. SortedIndex 范围查询测试（直接测试 index） =====

class TestSortedIndexRangeQuery:
    """测试 SortedIndex.range_query 的开区间支持"""

    @pytest.fixture
    def idx(self):
        """创建带数据的 SortedIndex"""
        index = SortedIndex('value')
        # 值: 1, 3, 5, 7, 9, 10, 15, 20
        for pk, val in enumerate([1, 3, 5, 7, 9, 10, 15, 20], start=1):
            index.insert(val, pk)
        return index

    def test_range_query_gt(self, idx):
        """大于查询：value > 5"""
        result = idx.range_query(min_val=5, include_min=False)
        # 应返回 7,9,10,15,20 对应的 pk
        expected_values = {7, 9, 10, 15, 20}
        expected_pks = set()
        for pk, val in enumerate([1, 3, 5, 7, 9, 10, 15, 20], start=1):
            if val in expected_values:
                expected_pks.add(pk)
        assert result == expected_pks

    def test_range_query_gte(self, idx):
        """大于等于查询：value >= 5"""
        result = idx.range_query(min_val=5, include_min=True)
        expected_values = {5, 7, 9, 10, 15, 20}
        expected_pks = set()
        for pk, val in enumerate([1, 3, 5, 7, 9, 10, 15, 20], start=1):
            if val in expected_values:
                expected_pks.add(pk)
        assert result == expected_pks

    def test_range_query_lt(self, idx):
        """小于查询：value < 10"""
        result = idx.range_query(max_val=10, include_max=False)
        expected_values = {1, 3, 5, 7, 9}
        expected_pks = set()
        for pk, val in enumerate([1, 3, 5, 7, 9, 10, 15, 20], start=1):
            if val in expected_values:
                expected_pks.add(pk)
        assert result == expected_pks

    def test_range_query_lte(self, idx):
        """小于等于查询：value <= 10"""
        result = idx.range_query(max_val=10, include_max=True)
        expected_values = {1, 3, 5, 7, 9, 10}
        expected_pks = set()
        for pk, val in enumerate([1, 3, 5, 7, 9, 10, 15, 20], start=1):
            if val in expected_values:
                expected_pks.add(pk)
        assert result == expected_pks

    def test_range_query_between(self, idx):
        """区间查询：5 <= value <= 10"""
        result = idx.range_query(min_val=5, max_val=10, include_min=True, include_max=True)
        expected_values = {5, 7, 9, 10}
        expected_pks = set()
        for pk, val in enumerate([1, 3, 5, 7, 9, 10, 15, 20], start=1):
            if val in expected_values:
                expected_pks.add(pk)
        assert result == expected_pks

    def test_range_query_open_ended_no_lower(self, idx):
        """无下界查询：value <= 5"""
        result = idx.range_query(min_val=None, max_val=5, include_max=True)
        expected_values = {1, 3, 5}
        expected_pks = set()
        for pk, val in enumerate([1, 3, 5, 7, 9, 10, 15, 20], start=1):
            if val in expected_values:
                expected_pks.add(pk)
        assert result == expected_pks

    def test_range_query_open_ended_no_upper(self, idx):
        """无上界查询：value >= 15"""
        result = idx.range_query(min_val=15, max_val=None, include_min=True)
        expected_values = {15, 20}
        expected_pks = set()
        for pk, val in enumerate([1, 3, 5, 7, 9, 10, 15, 20], start=1):
            if val in expected_values:
                expected_pks.add(pk)
        assert result == expected_pks

    def test_range_query_all(self, idx):
        """全范围查询：min=None, max=None"""
        result = idx.range_query(min_val=None, max_val=None)
        assert len(result) == 8  # 所有 pk

    def test_range_query_empty_result(self, idx):
        """无匹配结果"""
        result = idx.range_query(min_val=100, max_val=200)
        assert result == set()


# ===== C. Storage.query 范围查询加速 =====

class TestQueryRangeWithSortedIndex:
    """测试 Storage.query 利用 SortedIndex 加速范围查询"""

    def test_query_gt_with_sorted_index(self, sorted_index_storage):
        """age > 28 使用索引"""
        storage, User, session = sorted_index_storage
        condition = Condition('age', '>', 28)
        results = storage.query('users', [condition])
        ages = [r['age'] for r in results]
        assert all(a > 28 for a in ages)
        assert set(ages) == {30, 35, 40}

    def test_query_gte_with_sorted_index(self, sorted_index_storage):
        """age >= 28 使用索引"""
        storage, User, session = sorted_index_storage
        condition = Condition('age', '>=', 28)
        results = storage.query('users', [condition])
        ages = [r['age'] for r in results]
        assert all(a >= 28 for a in ages)
        assert set(ages) == {28, 30, 35, 40}

    def test_query_lt_with_sorted_index(self, sorted_index_storage):
        """age < 25 使用索引"""
        storage, User, session = sorted_index_storage
        condition = Condition('age', '<', 25)
        results = storage.query('users', [condition])
        ages = [r['age'] for r in results]
        assert all(a < 25 for a in ages)
        assert set(ages) == {20, 22}

    def test_query_lte_with_sorted_index(self, sorted_index_storage):
        """age <= 25 使用索引"""
        storage, User, session = sorted_index_storage
        condition = Condition('age', '<=', 25)
        results = storage.query('users', [condition])
        ages = [r['age'] for r in results]
        assert all(a <= 25 for a in ages)
        assert set(ages) == {20, 22, 25}

    def test_query_range_with_sorted_index(self, sorted_index_storage):
        """age > 20 AND age < 35 组合范围查询"""
        storage, User, session = sorted_index_storage
        conditions = [
            Condition('age', '>', 20),
            Condition('age', '<', 35),
        ]
        results = storage.query('users', conditions)
        ages = [r['age'] for r in results]
        assert all(20 < a < 35 for a in ages)
        assert set(ages) == {22, 25, 28, 30}

    def test_query_range_without_index_fallback(self, sorted_index_storage):
        """无索引列的范围查询走全表扫描，结果正确"""
        storage, User, session = sorted_index_storage
        # name 列没有索引
        condition = Condition('name', '>', 'C')
        results = storage.query('users', [condition])
        names = [r['name'] for r in results]
        assert all(n > 'C' for n in names)

    def test_query_range_with_hash_index_no_optimization(self, sorted_index_storage):
        """HashIndex 列的范围查询不走索引优化（走全表扫描）"""
        storage, User, session = sorted_index_storage
        # score 是 HashIndex，不支持范围查询
        table = storage.get_table('users')
        assert isinstance(table.indexes['score'], HashIndex)
        assert not table.indexes['score'].supports_range_query()

        condition = Condition('score', '>', 85.0)
        results = storage.query('users', [condition])
        scores = [r['score'] for r in results]
        assert all(s > 85.0 for s in scores)
        assert set(scores) == {88.0, 90.0, 92.0, 95.0}


# ===== D. order_by 索引排序 =====

class TestOrderByWithSortedIndex:
    """测试 order_by 利用 SortedIndex 排序"""

    def test_order_by_asc(self, sorted_index_storage):
        """升序排列"""
        storage, User, session = sorted_index_storage
        results = storage.query('users', [], order_by='age')
        ages = [r['age'] for r in results]
        # 有值部分应升序，None 排在最后
        non_none_ages = [a for a in ages if a is not None]
        assert non_none_ages == sorted(non_none_ages)
        # None 排在最后
        none_idx = [i for i, a in enumerate(ages) if a is None]
        if none_idx:
            assert none_idx[0] == len(ages) - 1

    def test_order_by_desc(self, sorted_index_storage):
        """降序排列"""
        storage, User, session = sorted_index_storage
        results = storage.query('users', [], order_by='age', order_desc=True)
        ages = [r['age'] for r in results]
        # 降序时 None 排在最前
        none_idx = [i for i, a in enumerate(ages) if a is None]
        if none_idx:
            assert none_idx[0] == 0
        # 有值部分应降序
        non_none_ages = [a for a in ages if a is not None]
        assert non_none_ages == sorted(non_none_ages, reverse=True)

    def test_order_by_with_limit_offset(self, sorted_index_storage):
        """分页 + 索引排序"""
        storage, User, session = sorted_index_storage
        # 升序取第3-5个（offset=2, limit=3）
        results = storage.query('users', [], order_by='age', offset=2, limit=3)
        ages = [r['age'] for r in results]
        # 升序排列：20, 22, 25, 28, 30, 35, 40, None
        # offset=2 跳过 20,22，取 25,28,30
        assert ages == [25, 28, 30]

    def test_order_by_without_sorted_index(self, sorted_index_storage):
        """无 SortedIndex 的列走 Python sort"""
        storage, User, session = sorted_index_storage
        # score 是 HashIndex，不支持 SortedIndex 排序优化
        results = storage.query('users', [], order_by='score')
        scores = [r['score'] for r in results]
        non_none_scores = [s for s in scores if s is not None]
        assert non_none_scores == sorted(non_none_scores)

    def test_order_by_with_none_values(self, sorted_index_storage):
        """None 值的排序规则"""
        storage, User, session = sorted_index_storage
        # 升序：None 在最后
        results_asc = storage.query('users', [], order_by='age')
        ages_asc = [r['age'] for r in results_asc]
        assert ages_asc[-1] is None

        # 降序：None 在最前
        results_desc = storage.query('users', [], order_by='age', order_desc=True)
        ages_desc = [r['age'] for r in results_desc]
        assert ages_desc[0] is None


# ===== E. 集成测试（通过 Session/Select API） =====

class TestIntegrationSelectAPI:
    """测试通过 Session/Select API 的索引优化"""

    def test_select_range_query_sorted_index(self, sorted_index_storage):
        """select(User).where(User.age > 18) 使用索引"""
        storage, User, session = sorted_index_storage
        stmt = select(User).where(User.age > 25)
        result = session.execute(stmt)
        users = result.all()
        ages = [u.age for u in users]
        assert all(a > 25 for a in ages)
        assert set(ages) == {28, 30, 35, 40}

    def test_select_order_by_sorted_index(self, sorted_index_storage):
        """select(User).order_by('age') 使用索引排序"""
        storage, User, session = sorted_index_storage
        stmt = select(User).order_by('age')
        result = session.execute(stmt)
        users = result.all()
        ages = [u.age for u in users]
        non_none = [a for a in ages if a is not None]
        assert non_none == sorted(non_none)
        # None 在最后
        assert ages[-1] is None

    def test_select_range_and_order_combined(self, sorted_index_storage):
        """范围查询 + 排序组合"""
        storage, User, session = sorted_index_storage
        stmt = select(User).where(User.age >= 25).order_by('age')
        result = session.execute(stmt)
        users = result.all()
        ages = [u.age for u in users]
        assert ages == [25, 28, 30, 35, 40]

    def test_select_range_with_limit(self, sorted_index_storage):
        """范围查询 + 分页"""
        storage, User, session = sorted_index_storage
        stmt = select(User).where(User.age > 20).order_by('age').limit(3)
        result = session.execute(stmt)
        users = result.all()
        ages = [u.age for u in users]
        assert ages == [22, 25, 28]

    def test_query_api_range_sorted_index(self, storage):
        """CRUDBaseModel.filter 使用索引"""
        Base: Type[CRUDBaseModel] = declarative_base(storage, crud=True)

        class Product(Base):
            __tablename__ = 'products'
            id = Column(int, primary_key=True)
            price = Column(float, index='sorted')

        Product.create(price=10.0)
        Product.create(price=20.0)
        Product.create(price=30.0)
        Product.create(price=40.0)
        Product.create(price=50.0)

        results = Product.filter(Product.price >= 30.0).all()
        prices = [p.price for p in results]
        assert set(prices) == {30.0, 40.0, 50.0}


# ===== F. 边界条件 =====

class TestEdgeCases:
    """边界条件测试"""

    def test_sorted_index_with_duplicate_values(self, storage):
        """SortedIndex 处理重复值"""
        Base: Type[PureBaseModel] = declarative_base(storage)

        class Item(Base):
            __tablename__ = 'dup_items'
            id = Column(int, primary_key=True)
            category = Column(int, index='sorted')

        session = Session(storage)
        for cat in [1, 2, 2, 3, 3, 3, 4]:
            session.execute(insert(Item).values(category=cat))
        session.commit()

        # 范围查询
        results = storage.query('dup_items', [Condition('category', '>=', 2), Condition('category', '<=', 3)])
        assert len(results) == 5  # 2,2,3,3,3

        # order_by
        results = storage.query('dup_items', [], order_by='category')
        cats = [r['category'] for r in results]
        assert cats == sorted(cats)

    def test_sorted_index_update_record(self, sorted_index_storage):
        """更新记录后索引正确维护"""
        storage, User, session = sorted_index_storage
        table = storage.get_table('users')
        idx = table.indexes['age']

        # 更新 Alice (age=25) 改为 age=99
        # 通过 Session API
        stmt = select(User).where(User.name == 'Alice')
        result = session.execute(stmt)
        alice = result.first()
        assert alice is not None
        assert alice.age == 25

        # 通过 update 语句
        upd = update(User).where(User.name == 'Alice').values(age=99)
        session.execute(upd)
        session.commit()

        # 验证索引更新
        # 25 不应该再有 Alice 的 pk
        results_25 = storage.query('users', [Condition('age', '=', 25)])
        assert all(r['name'] != 'Alice' for r in results_25)

        # 99 应该有 Alice
        results_99 = storage.query('users', [Condition('age', '=', 99)])
        assert any(r['name'] == 'Alice' for r in results_99)

    def test_sorted_index_delete_record(self, sorted_index_storage):
        """删除记录后索引正确维护"""
        storage, User, session = sorted_index_storage

        # 删除 Bob (age=30)
        stmt = delete(User).where(User.name == 'Bob')
        session.execute(stmt)
        session.commit()

        # 索引中不应再有 age=30 的 Bob
        results = storage.query('users', [Condition('age', '=', 30)])
        assert len(results) == 0

        # order_by 也不应包含 Bob
        all_results = storage.query('users', [], order_by='age')
        names = [r['name'] for r in all_results]
        assert 'Bob' not in names

    def test_transaction_rollback_restores_sorted_index(self, storage):
        """事务回滚恢复 SortedIndex"""
        Base: Type[PureBaseModel] = declarative_base(storage)

        class Item(Base):
            __tablename__ = 'tx_items'
            id = Column(int, primary_key=True)
            value = Column(int, index='sorted')

        session = Session(storage)
        session.execute(insert(Item).values(value=10))
        session.execute(insert(Item).values(value=20))
        session.commit()

        # 验证初始状态
        results = storage.query('tx_items', [])
        assert len(results) == 2

        # 使用事务上下文管理器，在异常时自动回滚
        try:
            with session.begin():
                session.execute(insert(Item).values(value=40))
                raise ValueError("simulate error")  # 触发回滚
        except ValueError:
            pass

        # 40 不应该存在（事务已回滚）
        results = storage.query('tx_items', [Condition('value', '=', 40)])
        assert len(results) == 0

        # 索引也应该回滚
        table = storage.get_table('tx_items')
        idx = table.indexes['value']
        assert idx.lookup(40) == set()

    def test_update_column_index_type_change(self, storage):
        """索引类型切换（hash → sorted）"""
        Base: Type[PureBaseModel] = declarative_base(storage)

        class Item(Base):
            __tablename__ = 'type_change_items'
            id = Column(int, primary_key=True)
            value = Column(int, index=True)  # hash

        session = Session(storage)
        for v in [10, 20, 30]:
            session.execute(insert(Item).values(value=v))
        session.commit()

        table = storage.get_table('type_change_items')
        assert isinstance(table.indexes['value'], HashIndex)

        # 切换为 sorted
        table.update_column_index('value', 'sorted')
        assert isinstance(table.indexes['value'], SortedIndex)

        # 验证索引数据完整
        results = storage.query('type_change_items', [Condition('value', '>=', 20)])
        values = [r['value'] for r in results]
        assert set(values) == {20, 30}

    def test_sorted_index_deepcopy(self):
        """SortedIndex 支持 deepcopy"""
        idx = SortedIndex('col')
        idx.insert(1, 'pk1')
        idx.insert(2, 'pk2')
        idx.insert(3, 'pk3')

        idx_copy = copy.deepcopy(idx)
        assert isinstance(idx_copy, SortedIndex)
        assert idx_copy.lookup(2) == {'pk2'}
        assert idx_copy.sorted_values == [1, 2, 3]

        # 修改副本不影响原索引
        idx_copy.insert(4, 'pk4')
        assert idx.lookup(4) == set()

    def test_sorted_index_empty_table(self, storage):
        """空表的 SortedIndex 操作"""
        Base: Type[PureBaseModel] = declarative_base(storage)

        class Empty(Base):
            __tablename__ = 'empty_table'
            id = Column(int, primary_key=True)
            value = Column(int, index='sorted')

        results = storage.query('empty_table', [Condition('value', '>', 0)])
        assert results == []

        results = storage.query('empty_table', [], order_by='value')
        assert results == []

    def test_order_by_desc_limit_with_none(self, sorted_index_storage):
        """降序 + 分页 + None 值"""
        storage, User, session = sorted_index_storage
        # 降序: None, 40, 35, 30, 28, 25, 22, 20
        # limit=3 → None, 40, 35
        results = storage.query('users', [], order_by='age', order_desc=True, limit=3)
        ages = [r['age'] for r in results]
        assert ages[0] is None
        assert ages[1] == 40
        assert ages[2] == 35

    def test_order_by_asc_offset_skips_values(self, sorted_index_storage):
        """升序 + offset 跳过有值记录"""
        storage, User, session = sorted_index_storage
        # 升序: 20, 22, 25, 28, 30, 35, 40, None
        # offset=5, limit=2 → 35, 40
        results = storage.query('users', [], order_by='age', offset=5, limit=2)
        ages = [r['age'] for r in results]
        assert ages == [35, 40]

    def test_range_and_order_combined(self, sorted_index_storage):
        """范围查询 + 排序组合"""
        storage, User, session = sorted_index_storage
        conditions = [Condition('age', '>=', 25), Condition('age', '<=', 35)]
        results = storage.query('users', conditions, order_by='age')
        ages = [r['age'] for r in results]
        assert ages == [25, 28, 30, 35]

    def test_range_query_eq_combined_with_range(self, sorted_index_storage):
        """等值查询 + 范围查询组合"""
        storage, User, session = sorted_index_storage
        # age > 20 AND score = 90.0（score 是 HashIndex）
        conditions = [
            Condition('age', '>', 20),
            Condition('score', '=', 90.0),
        ]
        results = storage.query('users', conditions)
        assert len(results) == 1
        assert results[0]['name'] == 'Alice'
        assert results[0]['age'] == 25
