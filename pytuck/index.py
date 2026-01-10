"""
Pytuck 索引实现

提供哈希索引支持
"""

from typing import Any, List, Set, Tuple
from collections import defaultdict

from .utils import compute_hash


class HashIndex:
    """哈希索引"""

    def __init__(self, column_name: str, bucket_count: int = 1024):
        """
        初始化哈希索引

        Args:
            column_name: 索引的列名
            bucket_count: 桶数量
        """
        self.column_name = column_name
        self.bucket_count = bucket_count
        self.buckets: List[List[Tuple[Any, Set[Any]]]] = [[] for _ in range(bucket_count)]
        self.size = 0
        self.load_factor = 0.75

    def insert(self, value: Any, pk: Any) -> None:
        """
        插入索引条目

        Args:
            value: 字段值
            pk: 主键值
        """
        bucket_idx = self._hash(value) % self.bucket_count
        bucket = self.buckets[bucket_idx]

        # 查找是否已存在该值
        for i, (v, pk_set) in enumerate(bucket):
            if v == value:
                pk_set.add(pk)
                return

        # 不存在则新建
        bucket.append((value, {pk}))
        self.size += 1

        # 检查是否需要扩容
        if self.size / self.bucket_count > self.load_factor:
            self._resize()

    def remove(self, value: Any, pk: Any) -> None:
        """
        删除索引条目

        Args:
            value: 字段值
            pk: 主键值
        """
        bucket_idx = self._hash(value) % self.bucket_count
        bucket = self.buckets[bucket_idx]

        for i, (v, pk_set) in enumerate(bucket):
            if v == value:
                pk_set.discard(pk)
                if not pk_set:
                    # 如果该值的主键集合为空，删除条目
                    bucket.pop(i)
                    self.size -= 1
                return

    def lookup(self, value: Any) -> Set[Any]:
        """
        查找索引

        Args:
            value: 字段值

        Returns:
            主键集合
        """
        bucket_idx = self._hash(value) % self.bucket_count
        bucket = self.buckets[bucket_idx]

        for v, pk_set in bucket:
            if v == value:
                return pk_set.copy()

        return set()

    def clear(self) -> None:
        """清空索引"""
        self.buckets = [[] for _ in range(self.bucket_count)]
        self.size = 0

    def _hash(self, value: Any) -> int:
        """计算哈希值"""
        return compute_hash(value)

    def _resize(self) -> None:
        """扩容（2倍大小）"""
        new_bucket_count = self.bucket_count * 2
        new_buckets: List[List[Tuple[Any, Set[Any]]]] = [[] for _ in range(new_bucket_count)]

        # 重新哈希所有条目
        for bucket in self.buckets:
            for value, pk_set in bucket:
                new_bucket_idx = self._hash(value) % new_bucket_count
                new_buckets[new_bucket_idx].append((value, pk_set))

        self.buckets = new_buckets
        self.bucket_count = new_bucket_count

    def __repr__(self) -> str:
        return f"HashIndex(column='{self.column_name}', size={self.size}, buckets={self.bucket_count})"
