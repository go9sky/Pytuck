"""
索引测试

覆盖 pytuck/core/index.py 的 HashIndex、SortedIndex 功能：
- 基本 CRUD（insert/remove/lookup/clear/len）
- None 值不索引
- 幂等性与边界条件
- SortedIndex 范围查询（inclusive/exclusive/equal bounds）
- SortedIndex 排序输出（asc/desc）
"""

import pytest

from pytuck.core.index import HashIndex, SortedIndex, BaseIndex


# ---------- HashIndex ----------


class TestHashIndex:
    """哈希索引测试"""

    def test_insert_and_lookup(self) -> None:
        """基本插入和查找"""
        idx = HashIndex("age")
        idx.insert(20, 1)
        idx.insert(25, 2)
        assert idx.lookup(20) == {1}
        assert idx.lookup(25) == {2}

    def test_insert_none_ignored(self) -> None:
        """None 值不索引"""
        idx = HashIndex("age")
        idx.insert(None, 1)
        assert idx.lookup(None) == set()
        assert len(idx) == 0

    def test_insert_duplicate_pk(self) -> None:
        """同值同 pk 多次插入，幂等"""
        idx = HashIndex("age")
        idx.insert(20, 1)
        idx.insert(20, 1)
        idx.insert(20, 1)
        assert idx.lookup(20) == {1}
        assert len(idx) == 1

    def test_multiple_pks_same_value(self) -> None:
        """同一个值对应多个 pk"""
        idx = HashIndex("age")
        idx.insert(20, 1)
        idx.insert(20, 2)
        idx.insert(20, 3)
        assert idx.lookup(20) == {1, 2, 3}
        assert len(idx) == 3

    def test_remove_existing(self) -> None:
        """删除已有条目"""
        idx = HashIndex("age")
        idx.insert(20, 1)
        idx.insert(20, 2)
        idx.remove(20, 1)
        assert idx.lookup(20) == {2}
        assert len(idx) == 1

    def test_remove_last_pk_cleans_key(self) -> None:
        """删除最后一个 pk 后，value 键被清理"""
        idx = HashIndex("age")
        idx.insert(20, 1)
        idx.remove(20, 1)
        assert idx.lookup(20) == set()
        assert 20 not in idx.map
        assert len(idx) == 0

    def test_remove_nonexistent(self) -> None:
        """删除不存在的条目不报错"""
        idx = HashIndex("age")
        # 空索引 remove
        idx.remove(20, 1)
        # 值存在但 pk 不存在
        idx.insert(20, 1)
        idx.remove(20, 99)
        assert idx.lookup(20) == {1}
        # 值不存在
        idx.remove(999, 1)

    def test_lookup_empty(self) -> None:
        """空索引查找返回空集合"""
        idx = HashIndex("age")
        assert idx.lookup(20) == set()
        assert idx.lookup(None) == set()

    def test_clear(self) -> None:
        """清空索引"""
        idx = HashIndex("age")
        idx.insert(20, 1)
        idx.insert(25, 2)
        idx.clear()
        assert len(idx) == 0
        assert idx.lookup(20) == set()
        assert idx.lookup(25) == set()

    def test_len(self) -> None:
        """len 计算正确（统计所有 pk 总数）"""
        idx = HashIndex("age")
        assert len(idx) == 0
        idx.insert(20, 1)
        assert len(idx) == 1
        idx.insert(20, 2)
        assert len(idx) == 2
        idx.insert(25, 3)
        assert len(idx) == 3

    def test_repr(self) -> None:
        """__repr__ 包含关键信息"""
        idx = HashIndex("age")
        idx.insert(20, 1)
        idx.insert(25, 2)
        r = repr(idx)
        assert "HashIndex" in r
        assert "age" in r
        assert "entries=2" in r
        assert "values=2" in r

    def test_lookup_returns_copy(self) -> None:
        """lookup 返回的是副本，修改不影响索引"""
        idx = HashIndex("age")
        idx.insert(20, 1)
        result = idx.lookup(20)
        result.add(999)
        assert idx.lookup(20) == {1}

    def test_string_values(self) -> None:
        """字符串值也能正常索引"""
        idx = HashIndex("name")
        idx.insert("Alice", 1)
        idx.insert("Bob", 2)
        idx.insert("Alice", 3)
        assert idx.lookup("Alice") == {1, 3}
        assert idx.lookup("Bob") == {2}

    def test_supports_range_query_false(self) -> None:
        """HashIndex 不支持范围查询"""
        idx = HashIndex("age")
        assert idx.supports_range_query() is False


# ---------- SortedIndex ----------


class TestSortedIndex:
    """有序索引测试"""

    def test_insert_and_lookup(self) -> None:
        """基本插入和查找"""
        idx = SortedIndex("score")
        idx.insert(80, 1)
        idx.insert(90, 2)
        assert idx.lookup(80) == {1}
        assert idx.lookup(90) == {2}

    def test_insert_none_ignored(self) -> None:
        """None 值不索引"""
        idx = SortedIndex("score")
        idx.insert(None, 1)
        assert idx.lookup(None) == set()
        assert len(idx) == 0
        assert len(idx.sorted_values) == 0

    def test_insert_maintains_order(self) -> None:
        """插入后保持排序"""
        idx = SortedIndex("score")
        idx.insert(50, 3)
        idx.insert(10, 1)
        idx.insert(30, 2)
        idx.insert(90, 5)
        idx.insert(70, 4)
        assert idx.sorted_values == [10, 30, 50, 70, 90]

    def test_insert_duplicate_value(self) -> None:
        """重复值只存一个 key，但 pk 集合扩展"""
        idx = SortedIndex("score")
        idx.insert(80, 1)
        idx.insert(80, 2)
        assert idx.lookup(80) == {1, 2}
        # sorted_values 中只有一个 80
        assert idx.sorted_values.count(80) == 1
        assert len(idx) == 2

    def test_remove_cleans_sorted_list(self) -> None:
        """删除最后 pk 后从 sorted_values 移除"""
        idx = SortedIndex("score")
        idx.insert(80, 1)
        idx.insert(90, 2)
        idx.remove(80, 1)
        assert 80 not in idx.sorted_values
        assert 80 not in idx.value_to_pks
        assert idx.sorted_values == [90]

    def test_remove_partial(self) -> None:
        """删除一个 pk 后，值仍然保留"""
        idx = SortedIndex("score")
        idx.insert(80, 1)
        idx.insert(80, 2)
        idx.remove(80, 1)
        assert idx.lookup(80) == {2}
        assert 80 in idx.sorted_values

    def test_remove_nonexistent(self) -> None:
        """删除不存在的不报错"""
        idx = SortedIndex("score")
        idx.remove(80, 1)  # 空索引
        idx.insert(80, 1)
        idx.remove(80, 99)  # pk 不存在
        idx.remove(999, 1)  # 值不存在
        assert idx.lookup(80) == {1}

    def test_supports_range_query(self) -> None:
        """SortedIndex 支持范围查询"""
        idx = SortedIndex("score")
        assert idx.supports_range_query() is True

    def test_range_query_inclusive(self) -> None:
        """包含边界的范围查询"""
        idx = SortedIndex("score")
        idx.insert(10, "a")
        idx.insert(20, "b")
        idx.insert(30, "c")
        idx.insert(40, "d")
        idx.insert(50, "e")
        result = idx.range_query(20, 40, include_min=True, include_max=True)
        assert result == {"b", "c", "d"}

    def test_range_query_exclusive(self) -> None:
        """排除边界的范围查询"""
        idx = SortedIndex("score")
        idx.insert(10, "a")
        idx.insert(20, "b")
        idx.insert(30, "c")
        idx.insert(40, "d")
        idx.insert(50, "e")
        result = idx.range_query(20, 40, include_min=False, include_max=False)
        assert result == {"c"}

    def test_range_query_mixed(self) -> None:
        """一端包含一端排除"""
        idx = SortedIndex("score")
        idx.insert(10, "a")
        idx.insert(20, "b")
        idx.insert(30, "c")
        idx.insert(40, "d")
        # include_min=True, include_max=False
        result = idx.range_query(20, 40, include_min=True, include_max=False)
        assert result == {"b", "c"}
        # include_min=False, include_max=True
        result = idx.range_query(20, 40, include_min=False, include_max=True)
        assert result == {"c", "d"}

    def test_range_query_equal_bounds(self) -> None:
        """min==max 的各种组合"""
        idx = SortedIndex("score")
        idx.insert(10, "a")
        idx.insert(20, "b")
        idx.insert(30, "c")
        # 包含两端：应返回 value==20 的 pk
        assert idx.range_query(20, 20, True, True) == {"b"}
        # 排除一端：应返回空
        assert idx.range_query(20, 20, False, True) == set()
        assert idx.range_query(20, 20, True, False) == set()
        assert idx.range_query(20, 20, False, False) == set()

    def test_range_query_empty_result(self) -> None:
        """范围内无匹配值"""
        idx = SortedIndex("score")
        idx.insert(10, "a")
        idx.insert(50, "b")
        result = idx.range_query(20, 40, True, True)
        assert result == set()

    def test_range_query_empty_index(self) -> None:
        """空索引范围查询返回空集合"""
        idx = SortedIndex("score")
        result = idx.range_query(0, 100, True, True)
        assert result == set()

    def test_range_query_all(self) -> None:
        """范围覆盖全部值"""
        idx = SortedIndex("score")
        idx.insert(10, "a")
        idx.insert(20, "b")
        idx.insert(30, "c")
        result = idx.range_query(0, 100, True, True)
        assert result == {"a", "b", "c"}

    def test_range_query_multiple_pks_per_value(self) -> None:
        """范围查询中一个值有多个 pk"""
        idx = SortedIndex("score")
        idx.insert(20, "a")
        idx.insert(20, "b")
        idx.insert(30, "c")
        result = idx.range_query(20, 30, True, True)
        assert result == {"a", "b", "c"}

    def test_get_sorted_pks_asc(self) -> None:
        """升序获取 pk 列表"""
        idx = SortedIndex("score")
        idx.insert(30, "c")
        idx.insert(10, "a")
        idx.insert(20, "b")
        pks = idx.get_sorted_pks(reverse=False)
        # 按值升序：10->a, 20->b, 30->c
        assert pks == ["a", "b", "c"]

    def test_get_sorted_pks_desc(self) -> None:
        """降序获取 pk 列表"""
        idx = SortedIndex("score")
        idx.insert(30, "c")
        idx.insert(10, "a")
        idx.insert(20, "b")
        pks = idx.get_sorted_pks(reverse=True)
        # 按值降序：30->c, 20->b, 10->a
        assert pks == ["c", "b", "a"]

    def test_get_sorted_pks_empty(self) -> None:
        """空索引返回空列表"""
        idx = SortedIndex("score")
        assert idx.get_sorted_pks() == []

    def test_clear(self) -> None:
        """清空索引"""
        idx = SortedIndex("score")
        idx.insert(10, "a")
        idx.insert(20, "b")
        idx.clear()
        assert len(idx) == 0
        assert idx.sorted_values == []
        assert idx.value_to_pks == {}

    def test_len(self) -> None:
        """len 计算正确"""
        idx = SortedIndex("score")
        assert len(idx) == 0
        idx.insert(10, "a")
        assert len(idx) == 1
        idx.insert(10, "b")  # 同值不同 pk
        assert len(idx) == 2
        idx.insert(20, "c")
        assert len(idx) == 3

    def test_repr(self) -> None:
        """__repr__ 包含关键信息"""
        idx = SortedIndex("score")
        idx.insert(10, "a")
        idx.insert(20, "b")
        r = repr(idx)
        assert "SortedIndex" in r
        assert "score" in r
        assert "entries=2" in r
        assert "values=2" in r

    def test_lookup_returns_copy(self) -> None:
        """lookup 返回的是副本"""
        idx = SortedIndex("score")
        idx.insert(10, "a")
        result = idx.lookup(10)
        result.add("z")
        assert idx.lookup(10) == {"a"}


# ---------- BaseIndex ----------


class TestBaseIndex:
    """基类索引测试"""

    def test_range_query_not_supported(self) -> None:
        """BaseIndex 默认 range_query 抛 NotImplementedError"""
        # HashIndex 继承了 BaseIndex 的默认 supports_range_query (False)
        # 但 BaseIndex.range_query 应该抛 NotImplementedError
        idx = HashIndex("age")
        with pytest.raises(NotImplementedError):
            idx.range_query(0, 100)

    def test_supports_range_query_default_false(self) -> None:
        """BaseIndex 默认不支持范围查询"""
        idx = HashIndex("age")
        assert idx.supports_range_query() is False
