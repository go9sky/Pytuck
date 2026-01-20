#!/usr/bin/env python3
"""
Pytuck 性能基准测试

对所有存储引擎进行全面的性能测试。
运行此脚本生成 README 所需的基准测试结果。

用法:
    python tests/benchmark.py                    # 默认测试（10000条记录）
    python tests/benchmark.py -n 5000            # 自定义记录数
    python tests/benchmark.py --keep             # 保留测试生成的文件
    python tests/benchmark.py -n 10000 --keep    # 组合使用
"""

import os
import sys
import time
import argparse
import shutil
import platform
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime

# 添加父目录到路径以便导入
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from examples.common import mktemp_dir_project

from pytuck import Storage, declarative_base, Session, Column, PureBaseModel
from pytuck import select, insert, update, delete
from pytuck.common.options import BinaryBackendOptions


# ============== 配置 ==============

# 默认测试记录数
DEFAULT_RECORD_COUNT = 10000

# 引擎列表（名称, 显示名称, 依赖包列表）
ENGINES = [
    ('binary', 'Binary', []),
    ('json', 'JSON', []),
    ('csv', 'CSV', []),
    ('sqlite', 'SQLite', []),
    ('excel', 'Excel', ['openpyxl']),
    ('xml', 'XML', ['lxml']),
]


# ============== 工具函数 ==============

def check_dependency(packages: List[str]) -> bool:
    """检查所需依赖包是否已安装"""
    for pkg in packages:
        try:
            __import__(pkg)
        except ImportError:
            return False
    return True


def format_time(seconds: float) -> str:
    """格式化时间，使用合适的单位"""
    if seconds < 0.001:
        return f"{seconds * 1000000:.1f}μs"
    elif seconds < 1:
        return f"{seconds * 1000:.2f}ms"
    else:
        return f"{seconds:.2f}s"


def format_size(bytes_size: int) -> str:
    """格式化文件大小，使用合适的单位"""
    if bytes_size < 1024:
        return f"{bytes_size}B"
    elif bytes_size < 1024 * 1024:
        return f"{bytes_size / 1024:.1f}KB"
    else:
        return f"{bytes_size / (1024 * 1024):.2f}MB"


def get_file_size(path: str) -> int:
    """获取文件或目录大小"""
    if os.path.isfile(path):
        return os.path.getsize(path)
    elif os.path.isdir(path):
        total = 0
        for dirpath, dirnames, filenames in os.walk(path):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                total += os.path.getsize(fp)
        return total
    return 0


class Timer:
    """简单的计时器上下文管理器"""

    def __init__(self):
        self.elapsed = 0.0

    def __enter__(self):
        self.start = time.perf_counter()
        return self

    def __exit__(self, *args):
        self.elapsed = time.perf_counter() - self.start


# ============== 基准测试类 ==============

class EngineBenchmark:
    """单个引擎的基准测试"""

    def __init__(self, engine_name: str, temp_dir: str):
        self.engine_name = engine_name
        self.temp_dir = temp_dir
        self.results: Dict[str, Any] = {}

        # 根据引擎类型确定文件扩展名
        extensions = {
            'binary': '.db',
            'json': '.json',
            'csv': '.zip',
            'sqlite': '.sqlite',
            'excel': '.xlsx',
            'xml': '.xml',
        }
        ext = extensions.get(engine_name, '.db')
        self.file_path = os.path.join(temp_dir, f'benchmark_{engine_name}{ext}')

    def setup_database(self, record_count: int) -> Tuple['Storage', 'Session', type]:
        """创建数据库和模型"""
        # 清理已存在的文件
        if os.path.exists(self.file_path):
            if os.path.isdir(self.file_path):
                shutil.rmtree(self.file_path)
            else:
                os.remove(self.file_path)

        # 创建存储
        db = Storage(file_path=self.file_path, engine=self.engine_name)
        Base = declarative_base(db)

        # 定义测试模型
        class BenchmarkUser(Base):
            __tablename__ = 'benchmark_users'

            id = Column('id', int, primary_key=True)
            name = Column('name', str, nullable=False, index=True)
            email = Column('email', str, nullable=True)
            age = Column('age', int, nullable=True)
            score = Column('score', float, nullable=True)
            active = Column('active', bool, nullable=True)

        session = Session(db)
        return db, session, BenchmarkUser

    def benchmark_insert(self, session: 'Session', model_class: type, count: int) -> float:
        """测试插入性能"""
        with Timer() as t:
            for i in range(count):
                stmt = insert(model_class).values(
                    name=f'User_{i}',
                    email=f'user{i}@example.com',
                    age=20 + (i % 50),
                    score=float(i % 100) / 10.0,
                    active=(i % 2 == 0)
                )
                session.execute(stmt)
            session.commit()
        return t.elapsed

    def benchmark_query_all(self, session: 'Session', model_class: type) -> float:
        """测试全表扫描性能"""
        with Timer() as t:
            stmt = select(model_class)
            result = session.execute(stmt)
            records = result.scalars().all()
        return t.elapsed

    def benchmark_query_indexed(self, session: 'Session', model_class: type, count: int) -> float:
        """测试索引查询性能（100次查询）"""
        with Timer() as t:
            for i in range(min(100, count)):
                stmt = select(model_class).filter_by(name=f'User_{i}')
                result = session.execute(stmt)
                record = result.scalars().first()
        return t.elapsed

    def benchmark_query_filtered(self, session: 'Session', model_class: type) -> float:
        """测试条件过滤查询性能"""
        with Timer() as t:
            stmt = select(model_class).where(model_class.age >= 30, model_class.age < 50)
            result = session.execute(stmt)
            records = result.scalars().all()
        return t.elapsed

    def benchmark_update(self, session: 'Session', model_class: type, count: int) -> float:
        """测试更新性能（100次更新）"""
        update_count = min(100, count)
        with Timer() as t:
            for i in range(update_count):
                stmt = update(model_class).where(model_class.id == i + 1).values(
                    age=25 + (i % 30),
                    score=float(i % 50) / 5.0
                )
                session.execute(stmt)
            session.commit()
        return t.elapsed

    def benchmark_delete(self, session: 'Session', model_class: type, count: int) -> float:
        """测试删除性能（50次删除）"""
        delete_count = min(50, count)
        with Timer() as t:
            for i in range(delete_count):
                stmt = delete(model_class).where(model_class.id == count - i)
                session.execute(stmt)
            session.commit()
        return t.elapsed

    def benchmark_save(self, db: 'Storage') -> float:
        """测试保存到磁盘性能"""
        with Timer() as t:
            db.flush()
        return t.elapsed

    def benchmark_load(self) -> float:
        """测试从磁盘加载性能"""
        with Timer() as t:
            db = Storage(file_path=self.file_path, engine=self.engine_name)
        db.close()
        return t.elapsed

    def benchmark_lazy_load(self) -> Optional[float]:
        """测试懒加载性能（仅 Binary 引擎）"""
        if self.engine_name != 'binary':
            return None

        options = BinaryBackendOptions(lazy_load=True)
        with Timer() as t:
            db = Storage(file_path=self.file_path, engine='binary', backend_options=options)
        db.close()
        return t.elapsed

    def run(self, record_count: int) -> Dict[str, Any]:
        """运行此引擎的所有基准测试"""
        results = {
            'engine': self.engine_name,
            'record_count': record_count,
        }

        try:
            # 初始化
            db, session, Model = self.setup_database(record_count)

            # 插入测试
            results['insert'] = self.benchmark_insert(session, Model, record_count)

            # 查询测试
            results['query_all'] = self.benchmark_query_all(session, Model)
            results['query_indexed'] = self.benchmark_query_indexed(session, Model, record_count)
            results['query_filtered'] = self.benchmark_query_filtered(session, Model)

            # 更新测试
            results['update'] = self.benchmark_update(session, Model, record_count)

            # 保存测试
            results['save'] = self.benchmark_save(db)

            # 获取文件大小（删除前）
            results['file_size'] = get_file_size(self.file_path)

            # 删除测试
            results['delete'] = self.benchmark_delete(session, Model, record_count)

            # 关闭并重新加载测试
            session.close()
            db.close()
            results['load'] = self.benchmark_load()

            # 懒加载测试（仅 Binary 引擎）
            lazy_load_time = self.benchmark_lazy_load()
            if lazy_load_time is not None:
                results['lazy_load'] = lazy_load_time

            results['success'] = True

        except Exception as e:
            results['success'] = False
            results['error'] = str(e)

        return results


# ============== 主测试运行器 ==============

def run_benchmarks(record_count: int, keep_files: bool = False, engines: List[str] = None) -> List[Dict[str, Any]]:
    """
    运行所有引擎的基准测试

    Args:
        record_count: 测试数量
        keep_files: 是否保留测试文件
        engines: 指定引擎名，不指定则运行全部

    Returns:

    """
    all_results = []

    # 创建临时目录
    if keep_files:
        temp_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'benchmark_output')
        os.makedirs(temp_dir, exist_ok=True)
        print(f"测试文件将保存到: {temp_dir}")
    else:
        temp_dir = mktemp_dir_project(prefix='pytuck_benchmark_')

    try:
        print("=" * 60)
        print("Pytuck 性能基准测试")
        print("=" * 60)
        print(f"\n系统: {platform.system()} {platform.release()}")
        print(f"Python: {platform.python_version()}")
        print(f"日期: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"测试数据量: {record_count} 条记录")
        print()

        for engine_name, display_name, deps in ENGINES:
            if engines and engine_name not in engines:
                continue

            # 检查依赖
            if deps and not check_dependency(deps):
                print(f"[跳过] {display_name}: 缺少依赖 {deps}")
                continue

            print(f"\n{'─' * 50}")
            print(f"测试 {display_name} 引擎")
            print(f"{'─' * 50}")

            benchmark = EngineBenchmark(engine_name, temp_dir)
            result = benchmark.run(record_count)
            all_results.append(result)

            if result['success']:
                print(f"  插入 ({record_count}条):  {format_time(result['insert'])}")
                print(f"  全表查询:          {format_time(result['query_all'])}")
                print(f"  索引查询 (100次):  {format_time(result['query_indexed'])}")
                print(f"  条件查询:          {format_time(result['query_filtered'])}")
                print(f"  更新 (100次):      {format_time(result['update'])}")
                print(f"  删除 (50次):       {format_time(result['delete'])}")
                print(f"  保存到磁盘:        {format_time(result['save'])}")
                print(f"  从磁盘加载:        {format_time(result['load'])}")
                if 'lazy_load' in result:
                    print(f"  懒加载:            {format_time(result['lazy_load'])}")
                print(f"  文件大小:          {format_size(result['file_size'])}")
            else:
                print(f"  错误: {result.get('error', '未知错误')}")

    finally:
        # 清理临时文件（如果不保留）
        if not keep_files:
            shutil.rmtree(temp_dir, ignore_errors=True)

    return all_results


def generate_markdown_table(results: List[Dict[str, Any]], record_count: int) -> str:
    """生成中文 Markdown 表格"""
    filtered = [r for r in results if r.get('record_count') == record_count and r.get('success')]

    if not filtered:
        return "暂无基准测试结果。"

    lines = []
    lines.append(f"测试数据量: {record_count} 条记录\n")
    lines.append("| 引擎 | 插入 | 全表查询 | 索引查询 | 条件查询 | 更新 | 保存 | 加载 | 文件大小 |")
    lines.append("|------|------|----------|----------|----------|------|------|------|----------|")

    for r in filtered:
        engine = r['engine'].capitalize()
        if r['engine'] == 'sqlite':
            engine = 'SQLite'

        lines.append(
            f"| {engine} | "
            f"{format_time(r['insert'])} | "
            f"{format_time(r['query_all'])} | "
            f"{format_time(r['query_indexed'])} | "
            f"{format_time(r['query_filtered'])} | "
            f"{format_time(r['update'])} | "
            f"{format_time(r['save'])} | "
            f"{format_time(r['load'])} | "
            f"{format_size(r['file_size'])} |"
        )

    return '\n'.join(lines)


def generate_english_table(results: List[Dict[str, Any]], record_count: int) -> str:
    """生成英文 Markdown 表格"""
    filtered = [r for r in results if r.get('record_count') == record_count and r.get('success')]

    if not filtered:
        return "No benchmark results available."

    lines = []
    lines.append(f"Test data: {record_count} records\n")
    lines.append("| Engine | Insert | Full Scan | Indexed | Filtered | Update | Save | Load | File Size |")
    lines.append("|--------|--------|-----------|---------|----------|--------|------|------|-----------|")

    for r in filtered:
        engine = r['engine'].capitalize()
        if r['engine'] == 'sqlite':
            engine = 'SQLite'

        lines.append(
            f"| {engine} | "
            f"{format_time(r['insert'])} | "
            f"{format_time(r['query_all'])} | "
            f"{format_time(r['query_indexed'])} | "
            f"{format_time(r['query_filtered'])} | "
            f"{format_time(r['update'])} | "
            f"{format_time(r['save'])} | "
            f"{format_time(r['load'])} | "
            f"{format_size(r['file_size'])} |"
        )

    return '\n'.join(lines)


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description='Pytuck 性能基准测试',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
示例:
  python benchmark.py                         # 使用默认设置（{DEFAULT_RECORD_COUNT}条记录，所有引擎）
  python benchmark.py -n 5000                 # 测试5000条记录
  python benchmark.py --keep                  # 保留测试生成的文件
  python benchmark.py -n 20000 --keep         # 测试20000条记录并保留文件
  python benchmark.py -e binary json          # 只测试 binary 和 json 引擎
  python benchmark.py -n 1000 -e sqlite csv   # 测试1000条记录，只测 sqlite 和 csv 引擎
        """
    )
    parser.add_argument(
        '-n', '--count',
        type=int,
        default=DEFAULT_RECORD_COUNT,
        help=f'测试记录数量（默认: {DEFAULT_RECORD_COUNT}）'
    )
    parser.add_argument(
        '--keep',
        action='store_true',
        help='保留测试生成的文件（保存到 tests/benchmark_output/）'
    )
    engines = [e[0] for e in ENGINES]
    parser.add_argument(
        '-e', '--engines',
        default=engines,  # 默认选择所有引擎
        nargs='+',
        choices=engines,
        metavar='ENGINE',
        help='指定要测试的引擎（可选多个，例如: -e binary json；默认: 所有引擎）',
    )
    return parser.parse_args()


def main():
    """主入口"""
    args = parse_args()

    print(f"\n启动 Pytuck 性能基准测试...")
    print(f"测试数据量: {args.count} 条记录")
    print(f'测试引擎: {", ".join(args.engines)}')
    if args.keep:
        print("测试文件将被保留")
    print()

    results = run_benchmarks(args.count, args.keep, args.engines)

    print("\n" + "=" * 60)
    print("汇总 - 可用于 README 的 Markdown 表格")
    print("=" * 60)

    print("\n### 中文版本 (README.md):\n")
    print(generate_markdown_table(results, args.count))

    print("\n### 英文版本 (README.EN.md):\n")
    print(generate_english_table(results, args.count))

    print("\n" + "=" * 60)
    print("基准测试完成!")
    print("=" * 60)

    return results


if __name__ == '__main__':
    main()
