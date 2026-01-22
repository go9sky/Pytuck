"""
Pytest 配置和共享 fixtures

此文件提供 pytest 测试所需的共享配置和 fixtures。
"""
import sys
import tempfile
from pathlib import Path
from typing import Generator

import pytest

# 确保可以导入 pytuck
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """
    提供临时目录 fixture

    使用 TemporaryDirectory 确保测试隔离，
    测试结束后自动清理。

    Yields:
        临时目录的 Path 对象
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def temp_file(temp_dir: Path) -> Generator[Path, None, None]:
    """
    提供临时文件路径 fixture

    Args:
        temp_dir: 临时目录 fixture

    Yields:
        临时文件的 Path 对象（文件本身不会被创建）
    """
    yield temp_dir / "test_db.db"
