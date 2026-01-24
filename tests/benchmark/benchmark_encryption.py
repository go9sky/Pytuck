"""
Pytuck 加密性能测试脚本

测试四种加密情况下的性能：
- 无加密
- 低级加密 (low)
- 中级加密 (medium)
- 高级加密 (high)

测试内容：
1. 写入 N 条记录的时间
2. 读取所有记录的时间
3. 文件大小
"""

import sys
import tempfile
import time
from pathlib import Path
from typing import Type, Optional, List

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from pytuck import Storage, declarative_base, Session, Column, insert, select
from pytuck import PureBaseModel
from pytuck.common.options import BinaryBackendOptions


def format_time(seconds: float) -> str:
    """格式化时间显示"""
    if seconds < 1:
        return f"{seconds*1000:.2f}ms"
    return f"{seconds:.3f}s"


def format_size(size_bytes: int) -> str:
    """格式化文件大小显示"""
    if size_bytes < 1024:
        return f"{size_bytes}B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes/1024:.2f}KB"
    else:
        return f"{size_bytes/(1024*1024):.2f}MB"


def benchmark_encryption(
    encryption_level: Optional[str],
    record_count: int,
    tmpdir: str
) -> dict:
    """
    测试指定加密等级的性能

    Args:
        encryption_level: 加密等级 ('low', 'medium', 'high', None)
        record_count: 测试记录数
        tmpdir: 临时目录

    Returns:
        性能数据字典
    """
    level_name = encryption_level if encryption_level else "none"
    db_path = Path(tmpdir) / f"test_{level_name}.db"

    # 准备选项
    if encryption_level:
        opts = BinaryBackendOptions(encryption=encryption_level, password='benchmark123')
    else:
        opts = BinaryBackendOptions()

    # 测试写入性能
    start_time = time.perf_counter()

    db = Storage(file_path=str(db_path), engine='binary', backend_options=opts)
    Base: Type[PureBaseModel] = declarative_base(db)

    class User(Base):
        __tablename__ = 'users'
        id = Column('id', int, primary_key=True)
        name = Column('name', str)
        age = Column('age', int)
        email = Column('email', str)
        bio = Column('bio', str)

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
    file_size = db_path.stat().st_size

    # 测试读取性能
    if encryption_level:
        opts = BinaryBackendOptions(password='benchmark123')
    else:
        opts = BinaryBackendOptions()

    start_time = time.perf_counter()

    db = Storage(file_path=str(db_path), engine='binary', backend_options=opts)
    Base2: Type[PureBaseModel] = declarative_base(db)

    class User2(Base2):
        __tablename__ = 'users'
        id = Column('id', int, primary_key=True)
        name = Column('name', str)
        age = Column('age', int)
        email = Column('email', str)
        bio = Column('bio', str)

    session = Session(db)
    result = session.execute(select(User2))
    users = result.all()

    read_time = time.perf_counter() - start_time

    db.close()

    return {
        'level': level_name,
        'record_count': record_count,
        'write_time': write_time,
        'read_time': read_time,
        'file_size': file_size,
        'records_read': len(users)
    }


def main() -> None:
    """运行性能测试"""
    print("=" * 70)
    print("Pytuck 加密性能基准测试")
    print("=" * 70)

    # 测试配置
    record_counts = [1000, 5000, 10000]
    encryption_levels: List[Optional[str]] = [None, 'low', 'medium', 'high']

    with tempfile.TemporaryDirectory() as tmpdir:
        for count in record_counts:
            print(f"\n{'='*70}")
            print(f"测试记录数: {count}")
            print("=" * 70)

            results = []
            for level in encryption_levels:
                level_name = level if level else "none"
                print(f"\n  测试加密等级: {level_name}...")

                result = benchmark_encryption(level, count, tmpdir)
                results.append(result)

                print(f"    写入时间: {format_time(result['write_time'])}")
                print(f"    读取时间: {format_time(result['read_time'])}")
                print(f"    文件大小: {format_size(result['file_size'])}")

            # 打印对比表格
            print(f"\n  {'='*60}")
            print(f"  性能对比表 ({count} 条记录)")
            print(f"  {'='*60}")
            print(f"  {'等级':<10} {'写入时间':<15} {'读取时间':<15} {'文件大小':<12} {'性能税'}")
            print(f"  {'-'*60}")

            base_write = results[0]['write_time']
            base_read = results[0]['read_time']

            for r in results:
                write_overhead = ((r['write_time'] / base_write) - 1) * 100 if base_write > 0 else 0
                read_overhead = ((r['read_time'] / base_read) - 1) * 100 if base_read > 0 else 0

                if r['level'] == 'none':
                    overhead_str = "(基准)"
                else:
                    overhead_str = f"+{write_overhead:.1f}%/+{read_overhead:.1f}%"

                print(f"  {r['level']:<10} {format_time(r['write_time']):<15} {format_time(r['read_time']):<15} {format_size(r['file_size']):<12} {overhead_str}")

    print("\n" + "=" * 70)
    print("测试完成!")
    print("=" * 70)


if __name__ == '__main__':
    main()
