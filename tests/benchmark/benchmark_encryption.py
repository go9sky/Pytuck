"""
Pytuck 加密性能测试脚本

测试所有支持加密的引擎的加密性能：

Binary 引擎:
- 无加密
- 低级加密 (low) - XOR
- 中级加密 (medium) - LCG
- 高级加密 (high) - ChaCha20

CSV 引擎:
- 无密码
- ZIP 密码保护 (password) - ZipCrypto

测试内容：
1. 写入 N 条记录的时间
2. 读取所有记录的时间
3. 文件大小

用法:
    python tests/benchmark/benchmark_encryption.py                          # 默认测试
    python tests/benchmark/benchmark_encryption.py -n 1000 5000             # 自定义记录数
    python tests/benchmark/benchmark_encryption.py -e binary                # 只测试 Binary
    python tests/benchmark/benchmark_encryption.py -e csv                   # 只测试 CSV
    python tests/benchmark/benchmark_encryption.py --output-json result.json  # JSON 输出
"""

import sys
import json
import tempfile
import time
import argparse
import platform
from pathlib import Path
from datetime import datetime
from typing import Type, Optional, List, Dict, Any

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from pytuck import Storage, declarative_base, Session, Column, insert, select
from pytuck import PureBaseModel
from pytuck.common.options import BinaryBackendOptions, CsvBackendOptions

# 从 benchmark.py 导入工具函数，避免重复定义
from benchmark import format_time, format_size, get_file_size


def parse_args() -> argparse.Namespace:
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='Pytuck 加密性能基准测试')
    parser.add_argument(
        '-n', '--counts', type=int, nargs='+',
        default=[1000, 5000, 10000],
        help='测试记录数量列表（默认: 1000 5000 10000）'
    )
    parser.add_argument(
        '-e', '--engines', nargs='+',
        choices=['binary', 'csv'], default=['binary', 'csv'],
        help='测试引擎（默认: binary csv）'
    )
    parser.add_argument(
        '--output-json', type=str, default=None,
        metavar='FILE',
        help='将结果输出为 JSON 文件'
    )
    return parser.parse_args()


def benchmark_one(
    engine: str,
    level: Optional[str],
    record_count: int,
    tmpdir: str
) -> Dict[str, Any]:
    """
    对单个引擎+加密配置运行写入/读取性能测试

    Args:
        engine: 'binary' 或 'csv'
        level: binary 加密等级 'low'/'medium'/'high'/None；
               csv 时 'password' 或 None
        record_count: 测试记录数
        tmpdir: 临时目录

    Returns:
        性能数据字典
    """
    level_name = level if level else "none"

    # 根据引擎确定文件扩展名和选项
    if engine == 'binary':
        ext = '.db'
        if level:
            write_opts: Any = BinaryBackendOptions(encryption=level, password='benchmark123')
            read_opts: Any = BinaryBackendOptions(encryption=level, password='benchmark123')
        else:
            write_opts = BinaryBackendOptions()
            read_opts = BinaryBackendOptions()
    elif engine == 'csv':
        ext = '.zip'
        if level == 'password':
            write_opts = CsvBackendOptions(password='benchmark123')
            read_opts = CsvBackendOptions(password='benchmark123')
        else:
            write_opts = CsvBackendOptions()
            read_opts = CsvBackendOptions()
    else:
        raise ValueError(f"不支持的引擎: {engine}")

    db_path = Path(tmpdir) / f"test_{engine}_{level_name}{ext}"

    # === 写入测试 ===
    start_time = time.perf_counter()

    db = Storage(file_path=str(db_path), engine=engine, backend_options=write_opts)
    Base: Type[PureBaseModel] = declarative_base(db)

    class User(Base):
        __tablename__ = 'users'
        id = Column(int, primary_key=True)
        name = Column(str)
        age = Column(int)
        email = Column(str)
        bio = Column(str)

    session = Session(db)

    for i in range(record_count):
        session.execute(insert(User).values(
            name=f'User_{i}',
            age=20 + (i % 50),
            email=f'user_{i}@example.com',
            bio=f'This is a bio for user {i}. ' * 3
        ))

    session.commit()
    db.close()

    write_time = time.perf_counter() - start_time

    # 获取文件大小
    file_size = get_file_size(db_path)

    # === 读取测试 ===
    start_time = time.perf_counter()

    db = Storage(file_path=str(db_path), engine=engine, backend_options=read_opts)
    Base2: Type[PureBaseModel] = declarative_base(db)

    class User2(Base2):
        __tablename__ = 'users'
        id = Column(int, primary_key=True)
        name = Column(str)
        age = Column(int)
        email = Column(str)
        bio = Column(str)

    session = Session(db)
    result = session.execute(select(User2))
    users = result.all()

    read_time = time.perf_counter() - start_time

    db.close()

    return {
        'engine': engine,
        'level': level_name,
        'record_count': record_count,
        'write_time': write_time,
        'read_time': read_time,
        'file_size': file_size,
        'records_read': len(users)
    }


def print_comparison_table(
    results: List[Dict[str, Any]],
    record_count: int
) -> None:
    """
    打印性能对比表格

    按引擎分组，同引擎内以 none 为基准计算性能税。

    Args:
        results: 当前 record_count 的所有测试结果
        record_count: 记录数（用于标题）
    """
    print(f"\n  {'='*70}")
    print(f"  性能对比表 ({record_count} 条记录)")
    print(f"  {'='*70}")
    print(f"  {'引擎':<10} {'等级':<12} {'写入时间':<15} {'读取时间':<15} {'文件大小':<12} {'性能税'}")
    print(f"  {'-'*70}")

    # 按引擎分组
    engines_seen: List[str] = []
    for r in results:
        if r['engine'] not in engines_seen:
            engines_seen.append(r['engine'])

    for eng in engines_seen:
        eng_results = [r for r in results if r['engine'] == eng]
        # 找到基准（none）
        base_result = next((r for r in eng_results if r['level'] == 'none'), None)
        base_write = base_result['write_time'] if base_result else 0
        base_read = base_result['read_time'] if base_result else 0

        for r in eng_results:
            engine_display = r['engine'].upper() if r['engine'] == 'csv' else r['engine'].capitalize()

            if r['level'] == 'none':
                overhead_str = "(基准)"
            else:
                write_overhead = ((r['write_time'] / base_write) - 1) * 100 if base_write > 0 else 0
                read_overhead = ((r['read_time'] / base_read) - 1) * 100 if base_read > 0 else 0
                overhead_str = f"+{write_overhead:.1f}%/+{read_overhead:.1f}%"

            print(
                f"  {engine_display:<10} {r['level']:<12} "
                f"{format_time(r['write_time']):<15} "
                f"{format_time(r['read_time']):<15} "
                f"{format_size(r['file_size']):<12} "
                f"{overhead_str}"
            )


def main() -> None:
    """运行加密性能测试"""
    args = parse_args()
    all_results: List[Dict[str, Any]] = []

    print("=" * 70)
    print("Pytuck 加密性能基准测试")
    print("=" * 70)
    print(f"\n系统: {platform.system()} {platform.release()}")
    print(f"Python: {platform.python_version()}")
    print(f"日期: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"测试引擎: {', '.join(args.engines)}")
    print(f"测试记录数: {args.counts}")

    with tempfile.TemporaryDirectory() as tmpdir:
        for count in args.counts:
            print(f"\n{'='*70}")
            print(f"测试记录数: {count}")
            print("=" * 70)

            count_results: List[Dict[str, Any]] = []

            # Binary 引擎：测试 none/low/medium/high
            if 'binary' in args.engines:
                for level in [None, 'low', 'medium', 'high']:
                    level_name = level if level else "none"
                    print(f"\n  测试 Binary 加密等级: {level_name}...")

                    result = benchmark_one('binary', level, count, tmpdir)
                    count_results.append(result)
                    all_results.append(result)

                    print(f"    写入时间: {format_time(result['write_time'])}")
                    print(f"    读取时间: {format_time(result['read_time'])}")
                    print(f"    文件大小: {format_size(result['file_size'])}")

            # CSV 引擎：测试 无密码/有密码
            if 'csv' in args.engines:
                for level in [None, 'password']:
                    level_name = level if level else "none"
                    print(f"\n  测试 CSV 加密等级: {level_name}...")

                    result = benchmark_one('csv', level, count, tmpdir)
                    count_results.append(result)
                    all_results.append(result)

                    print(f"    写入时间: {format_time(result['write_time'])}")
                    print(f"    读取时间: {format_time(result['read_time'])}")
                    print(f"    文件大小: {format_size(result['file_size'])}")

            # 打印该 count 的对比表格
            print_comparison_table(count_results, count)

    print("\n" + "=" * 70)
    print("测试完成!")
    print("=" * 70)

    # JSON 输出
    if args.output_json:
        output_path = Path(args.output_json)
        output_data = {
            'timestamp': datetime.now().isoformat(),
            'system': platform.system(),
            'python_version': platform.python_version(),
            'engines': args.engines,
            'results': all_results
        }
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(output_data, indent=2, ensure_ascii=False),
            encoding='utf-8'
        )
        print(f"\n结果已保存到: {output_path}")


if __name__ == '__main__':
    main()
