import tempfile
from pathlib import Path

def get_project_temp_dir() -> Path:
    """获取项目的临时目录路径"""
    temp_dir = Path(tempfile.gettempdir()) / 'Pytuck_Temp'
    temp_dir.mkdir(parents=True, exist_ok=True)
    return temp_dir