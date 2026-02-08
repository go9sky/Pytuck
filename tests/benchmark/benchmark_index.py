#!/usr/bin/env python3
"""
Pytuck 索引优化性能基准测试

对比 无索引 / HashIndex / SortedIndex 三种模式下
范围查询、排序、组合查询的性能差异。

用法:
    python tests/benchmark/benchmark_index.py                 # 默认测试（100000条记录）
    python tests/benchmark/benchmark_index.py -n 50000        # 自定义记录数
    python tests/benchmark/benchmark_index.py -r 200          # 自定义范围查询次数
"""

import sys
import time
import random
import argparse
from typing import Any, Dict, List, Tuple, Type
from pathlib import Path

# 添加项目根目录到路径以便导入
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from pytuck import Storage, declarative_base, Session, Column, PureBaseModel
from pytuck import select, insert
from pytuck.query.builder import Condition


# ============== 配置 ==============

DEFAULT_RECORD_COUNT = 100000
DEFAULT_RANGE_RUNS = 100
DEFAULT_ORDER_RUNS = 50


# ============== 工具 ==============

class Timer:
    """简单的计时器上下文管理器"""

    def __init__(self) -> None:
        self.elapsed: float = 0.0
        self.start: float = 0.0

    def __enter__(self) -> 'Timer':
        self.start = time.perf_counter()
        return self

    def __exit__(self, *args: Any) -> None:
        self.elapsed = time.perf_counter() - self.start


def format_time(seconds: float) -> str:
    """格式化时间，使用合适的单位"""
    if seconds < 0.001:
        return f"{seconds * 1000000:.1f}us"
    elif seconds < 1:
        return f"{seconds * 1000:.2f}ms"
    else:
        return f"{seconds:.2f}s"


# ============== 数据库构建 ==============

def build_db(
    index_type: Any,
    record_count: int,
    ages: List[int]
) -> Tuple[Storage, Session, type]:
    """
    创建并填充内存数据库

    Args:
        index_type: age 列的索引类型（False / True / 'sorted'）
        record_count: 记录数
        ages: 预生成的 age 值列表

    Returns:
        (Storage, Session, UserModel)
    """
    db = Storage()
    Base: Type[PureBaseModel] = declarative_base(db)

    class User(Base):
        __tablename__ = 'users'
        id = Column(int, primary_key=True)
        name = Column(str, index=True)
        age = Column(int, index=index_type)

    session = Session(db)
    for i in range(record_count):
        stmt = insert(User).values(id=i + 1, name=f'User_{i}', age=ages[i])
        session.execute(stmt)
    session.commit()
    return db, session, User


# ============== 测试函数 ==============

def bench_storage_range(
    label: str,
    conditions: List[Condition],
    db_none: Storage,
    db_hash: Storage,
    db_sorted: Storage,
    runs: int
) -> Tuple[float, float, float, int]:
    """Storage.query 范围查询测试，返回 (none_time, hash_time, sorted_time, count)"""
    # 无索引
    with Timer() as t_none:
        for _ in range(runs):
            records = db_none.query('users', conditions)
    cnt = len(records)

    # HashIndex
    with Timer() as t_hash:
        for _ in range(runs):
            db_hash.query('users', conditions)

    # SortedIndex
    with Timer() as t_sorted:
        for _ in range(runs):
            db_sorted.query('users', conditions)

    return t_none.elapsed, t_hash.elapsed, t_sorted.elapsed, cnt


def bench_select_range(
    session_none: Session,
    session_hash: Session,
    session_sorted: Session,
    model_none: type,
    model_hash: type,
    model_sorted: type,
    range_pairs: List[Tuple[int, int]],
) -> Tuple[float, float, float]:
    """select() API 范围查询测试"""
    # 无索引
    with Timer() as t_none:
        for lo, hi in range_pairs:
            stmt = select(model_none).where(model_none.age >= lo, model_none.age <= hi)
            session_none.execute(stmt).all()

    # HashIndex
    with Timer() as t_hash:
        for lo, hi in range_pairs:
            stmt = select(model_hash).where(model_hash.age >= lo, model_hash.age <= hi)
            session_hash.execute(stmt).all()

    # SortedIndex
    with Timer() as t_sorted:
        for lo, hi in range_pairs:
            stmt = select(model_sorted).where(model_sorted.age >= lo, model_sorted.age <= hi)
            session_sorted.execute(stmt).all()

    return t_none.elapsed, t_hash.elapsed, t_sorted.elapsed


# ============== 主测试流程 ==============

def run_benchmark(record_count: int, range_runs: int, order_runs: int) -> Dict[str, Tuple[float, ...]]:
    """
    运行全部基准测试

    Args:
        record_count: 测试记录数
        range_runs: 范围查询执行次数
        order_runs: 排序查询执行次数

    Returns:
        各测试结果字典
    """
    results: Dict[str, Tuple[float, ...]] = {}

    print("=" * 70)
    print(f"  Pytuck 索引优化性能基准测试  (N={record_count:,})")
    print("=" * 70)
    print()

    # 准备数据
    random.seed(42)
    ages = [random.randint(1, 100) for _ in range(record_count)]

    print("准备测试数据...")
    with Timer() as t1:
        db_none, s_none, M_none = build_db(False, record_count, ages)
    with Timer() as t2:
        db_hash, s_hash, M_hash = build_db(True, record_count, ages)
    with Timer() as t3:
        db_sorted, s_sorted, M_sorted = build_db('sorted', record_count, ages)

    print(f"  无索引:      {format_time(t1.elapsed):>10}")
    print(f"  HashIndex:   {format_time(t2.elapsed):>10}")
    print(f"  SortedIndex: {format_time(t3.elapsed):>10}")
    print()

    # ==================== Part A: Storage.query 底层测试 ====================

    print("=" * 70)
    print("  Part A: Storage.query 底层引擎对比")
    print("=" * 70)
    print()

    # A1: 范围查询 (age >= 30 AND age <= 50)
    print("-" * 70)
    print(f"A1: 范围查询  (age >= 30 AND age <= 50)  x{range_runs}")
    print("-" * 70)
    conds = [Condition('age', '>=', 30), Condition('age', '<=', 50)]
    a1_none, a1_hash, a1_sorted, cnt = bench_storage_range(
        "A1", conds, db_none, db_hash, db_sorted, range_runs
    )
    print(f"  无索引:      {format_time(a1_none):>10}  ({cnt} 条)")
    print(f"  HashIndex:   {format_time(a1_hash):>10}  (vs无索引 {a1_none/a1_hash:.1f}x)")
    print(f"  SortedIndex: {format_time(a1_sorted):>10}  (vs无索引 {a1_none/a1_sorted:.1f}x)")
    results['A1_range'] = (a1_none, a1_hash, a1_sorted)
    print()

    # A2: 高选择性范围 (age > 95, ~5%数据)
    print("-" * 70)
    print(f"A2: 高选择性范围  (age > 95)  x{range_runs}")
    print("-" * 70)
    conds = [Condition('age', '>', 95)]
    a2_none, a2_hash, a2_sorted, cnt = bench_storage_range(
        "A2", conds, db_none, db_hash, db_sorted, range_runs
    )
    print(f"  无索引:      {format_time(a2_none):>10}  ({cnt} 条)")
    print(f"  SortedIndex: {format_time(a2_sorted):>10}  (vs无索引 {a2_none/a2_sorted:.1f}x)")
    results['A2_selective'] = (a2_none, a2_hash, a2_sorted)
    print()

    # A3: order_by 全量排序
    print("-" * 70)
    print(f"A3: 全量 order_by('age')  x{order_runs}")
    print("-" * 70)
    with Timer() as t_none:
        for _ in range(order_runs):
            db_none.query('users', [], order_by='age', order_desc=False)
    with Timer() as t_sorted:
        for _ in range(order_runs):
            db_sorted.query('users', [], order_by='age', order_desc=False)
    print(f"  无索引 (Python sort):  {format_time(t_none.elapsed):>10}")
    print(f"  SortedIndex (遍历):    {format_time(t_sorted.elapsed):>10}  "
          f"(vs无索引 {t_none.elapsed/t_sorted.elapsed:.1f}x)")
    results['A3_orderby'] = (t_none.elapsed, t_none.elapsed, t_sorted.elapsed)
    print()

    # ==================== Part B: select() API 上层测试 ====================

    print("=" * 70)
    print("  Part B: select() API 上层对比")
    print("=" * 70)
    print()

    # B1: 范围查询 (随机范围)
    print("-" * 70)
    print(f"B1: 范围查询  (age >= X AND age <= Y)  x{range_runs}")
    print("-" * 70)
    random.seed(123)
    range_pairs = [(random.randint(1, 50), random.randint(51, 100)) for _ in range(range_runs)]
    b1_none, b1_hash, b1_sorted = bench_select_range(
        s_none, s_hash, s_sorted, M_none, M_hash, M_sorted, range_pairs
    )
    print(f"  无索引:      {format_time(b1_none):>10}")
    print(f"  HashIndex:   {format_time(b1_hash):>10}  (vs无索引 {b1_none/b1_hash:.1f}x)")
    print(f"  SortedIndex: {format_time(b1_sorted):>10}  (vs无索引 {b1_none/b1_sorted:.1f}x)")
    results['B1_range'] = (b1_none, b1_hash, b1_sorted)
    print()

    # B2: 高选择性范围 (age > 95)
    print("-" * 70)
    print(f"B2: 高选择性范围  (age > 95)  x{range_runs}")
    print("-" * 70)
    with Timer() as t_none:
        for _ in range(range_runs):
            select(M_none).where(M_none.age > 95)
            s_none.execute(select(M_none).where(M_none.age > 95)).all()
    with Timer() as t_sorted:
        for _ in range(range_runs):
            s_sorted.execute(select(M_sorted).where(M_sorted.age > 95)).all()
    print(f"  无索引:      {format_time(t_none.elapsed):>10}")
    print(f"  SortedIndex: {format_time(t_sorted.elapsed):>10}  "
          f"(vs无索引 {t_none.elapsed/t_sorted.elapsed:.1f}x)")
    results['B2_selective'] = (t_none.elapsed, t_none.elapsed, t_sorted.elapsed)
    print()

    # B3: 排序 + limit
    print("-" * 70)
    print(f"B3: 排序查询  order_by('age').limit(10)  x{order_runs}")
    print("-" * 70)
    with Timer() as t_none:
        for _ in range(order_runs):
            s_none.execute(select(M_none).order_by('age').limit(10)).all()
    with Timer() as t_sorted:
        for _ in range(order_runs):
            s_sorted.execute(select(M_sorted).order_by('age').limit(10)).all()
    print(f"  无索引:      {format_time(t_none.elapsed):>10}  (全量排序)")
    print(f"  SortedIndex: {format_time(t_sorted.elapsed):>10}  (索引遍历)")
    print(f"  加速比: {t_none.elapsed/t_sorted.elapsed:.1f}x")
    results['B3_orderby'] = (t_none.elapsed, t_none.elapsed, t_sorted.elapsed)
    print()

    # B4: 范围 + 排序 + 分页
    print("-" * 70)
    print(f"B4: 组合查询  where(age>=20,age<=60).order_by('age').limit(20)  x{order_runs}")
    print("-" * 70)
    with Timer() as t_none:
        for _ in range(order_runs):
            stmt = select(M_none).where(M_none.age >= 20, M_none.age <= 60).order_by('age').limit(20)
            s_none.execute(stmt).all()
    with Timer() as t_hash:
        for _ in range(order_runs):
            stmt = select(M_hash).where(M_hash.age >= 20, M_hash.age <= 60).order_by('age').limit(20)
            s_hash.execute(stmt).all()
    with Timer() as t_sorted:
        for _ in range(order_runs):
            stmt = select(M_sorted).where(M_sorted.age >= 20, M_sorted.age <= 60).order_by('age').limit(20)
            s_sorted.execute(stmt).all()
    print(f"  无索引:      {format_time(t_none.elapsed):>10}")
    print(f"  HashIndex:   {format_time(t_hash.elapsed):>10}")
    print(f"  SortedIndex: {format_time(t_sorted.elapsed):>10}  "
          f"(vs无索引 {t_none.elapsed/t_sorted.elapsed:.1f}x)")
    results['B4_combo'] = (t_none.elapsed, t_hash.elapsed, t_sorted.elapsed)
    print()

    # ==================== 汇总 ====================

    print("=" * 70)
    print("  性能对比汇总")
    print("=" * 70)
    print()

    hdr = f"  {'测试场景':<40} {'无索引':>10} {'Hash':>10} {'Sorted':>10} {'加速比':>8}"
    print(hdr)
    print(f"  {'-'*40} {'-'*10} {'-'*10} {'-'*10} {'-'*8}")

    def fmt_row(name: str, t_none: float, t_hash: float, t_sorted: float) -> None:
        sp = t_none / t_sorted if t_sorted > 0 else 0
        h = format_time(t_hash) if t_hash != t_none else '---'
        print(f"  {name:<40} {format_time(t_none):>10} {h:>10} "
              f"{format_time(t_sorted):>10} {sp:>7.1f}x")

    print("  [Storage.query 底层]")
    fmt_row("    范围 age BETWEEN 30 AND 50", *results['A1_range'])
    fmt_row("    高选择性 age > 95", *results['A2_selective'])
    fmt_row("    全量 order_by", *results['A3_orderby'])
    print()
    print("  [select() API 上层]")
    fmt_row("    范围 age BETWEEN X AND Y", *results['B1_range'])
    fmt_row("    高选择性 age > 95", *results['B2_selective'])
    fmt_row("    排序 order_by + limit(10)", *results['B3_orderby'])
    fmt_row("    组合 range+order_by+limit", *results['B4_combo'])
    print()

    print("说明:")
    print("  - 加速比 = 无索引耗时 / SortedIndex 耗时")
    print("  - HashIndex 不支持范围查询加速，范围场景性能与无索引相同")
    print("  - SortedIndex 优势场景：")
    print("    1) 范围查询：bisect 定位边界，减少遍历量")
    print("    2) 高选择性条件：匹配记录越少，加速越显著")
    print("    3) 组合查询：范围缩小候选集后排序开销大幅降低")
    print()

    # 清理
    s_none.close()
    s_hash.close()
    s_sorted.close()
    db_none.close()
    db_hash.close()
    db_sorted.close()

    return results


# ============== 入口 ==============

def main() -> None:
    parser = argparse.ArgumentParser(description='Pytuck 索引优化性能基准测试')
    parser.add_argument('-n', '--count', type=int, default=DEFAULT_RECORD_COUNT,
                        help=f'测试记录数（默认 {DEFAULT_RECORD_COUNT}）')
    parser.add_argument('-r', '--range-runs', type=int, default=DEFAULT_RANGE_RUNS,
                        help=f'范围查询执行次数（默认 {DEFAULT_RANGE_RUNS}）')
    parser.add_argument('-o', '--order-runs', type=int, default=DEFAULT_ORDER_RUNS,
                        help=f'排序查询执行次数（默认 {DEFAULT_ORDER_RUNS}）')

    args = parser.parse_args()
    run_benchmark(args.count, args.range_runs, args.order_runs)


if __name__ == '__main__':
    main()
