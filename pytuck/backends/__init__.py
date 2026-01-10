"""
Pytuck 后端注册器和工厂

提供引擎注册、发现和实例化功能
"""

from typing import Any, Dict, List, Type, Optional
from .base import StorageBackend


class BackendRegistry:
    """
    后端注册器（单例模式）

    负责管理所有可用的存储引擎
    """

    _backends: Dict[str, Type[StorageBackend]] = {}
    _initialized = False

    @classmethod
    def register(cls, backend_class: Type[StorageBackend]):
        """
        注册后端

        Args:
            backend_class: 后端类（必须是 StorageBackend 的子类）

        示例:
            BackendRegistry.register(BinaryBackend)
        """
        if not issubclass(backend_class, StorageBackend):
            raise TypeError(f"{backend_class} must be a subclass of StorageBackend")

        if backend_class.ENGINE_NAME is None:
            raise ValueError(f"{backend_class} must define ENGINE_NAME")

        cls._backends[backend_class.ENGINE_NAME] = backend_class

    @classmethod
    def get(cls, engine_name: str) -> Optional[Type[StorageBackend]]:
        """
        获取后端类

        Args:
            engine_name: 引擎名称

        Returns:
            后端类，如果不存在则返回 None
        """
        if not cls._initialized:
            cls._discover_backends()

        return cls._backends.get(engine_name)

    @classmethod
    def available_engines(cls) -> Dict[str, bool]:
        """
        获取所有引擎及其可用性

        Returns:
            字典 {engine_name: is_available}

        示例:
            {
                'binary': True,
                'json': True,
                'csv': True,
                'sqlite': True,
                'excel': False,  # 未安装 openpyxl
                'xml': False,    # 未安装 lxml
            }
        """
        if not cls._initialized:
            cls._discover_backends()

        return {
            name: backend.is_available()
            for name, backend in cls._backends.items()
        }

    @classmethod
    def list_engines(cls) -> List[str]:
        """
        列出所有已注册的引擎名称

        Returns:
            引擎名称列表
        """
        if not cls._initialized:
            cls._discover_backends()

        return list(cls._backends.keys())

    @classmethod
    def _discover_backends(cls):
        """
        自动发现并注册所有后端（延迟导入）

        采用延迟导入策略：
        - 导入失败不影响其他引擎
        - 只在首次使用时执行
        """
        if cls._initialized:
            return

        cls._initialized = True

        # 二进制引擎（总是可用，无依赖）
        try:
            from .binary import BinaryBackend
            cls.register(BinaryBackend)
        except ImportError:
            pass

        # JSON 引擎（标准库，总是可用）
        try:
            from .json_backend import JSONBackend
            cls.register(JSONBackend)
        except ImportError:
            pass

        # CSV 引擎（标准库，总是可用）
        try:
            from .csv_backend import CSVBackend
            cls.register(CSVBackend)
        except ImportError:
            pass

        # SQLite 引擎（内置，总是可用）
        try:
            from .sqlite_backend import SQLiteBackend
            cls.register(SQLiteBackend)
        except ImportError:
            pass

        # Excel 引擎（需要 openpyxl）
        try:
            from .excel_backend import ExcelBackend
            cls.register(ExcelBackend)
        except ImportError:
            pass

        # XML 引擎（需要 lxml）
        try:
            from .xml_backend import XMLBackend
            cls.register(XMLBackend)
        except ImportError:
            pass


def get_backend(engine: str, file_path: str, **kwargs: Any) -> StorageBackend:
    """
    获取后端实例（工厂函数）

    Args:
        engine: 引擎名称（'binary', 'json', 'csv', 'sqlite', 'excel', 'xml'）
        file_path: 文件路径
        **kwargs: 引擎特定参数

    Returns:
        后端实例

    Raises:
        ValueError: 引擎不存在或不可用

    示例:
        backend = get_backend('binary', 'data.db')
        backend = get_backend('json', 'data.json', indent=2)
        backend = get_backend('csv', 'data_dir', encoding='utf-8')
    """
    backend_class = BackendRegistry.get(engine)

    if backend_class is None:
        available = BackendRegistry.list_engines()
        raise ValueError(
            f"Backend '{engine}' not found. "
            f"Available backends: {available}"
        )

    if not backend_class.is_available():
        deps = ', '.join(backend_class.REQUIRED_DEPENDENCIES) if backend_class.REQUIRED_DEPENDENCIES else 'none'
        raise ValueError(
            f"Backend '{engine}' is not available. "
            f"Required dependencies: {deps}. "
            f"Install with: pip install pytuck[{engine}]"
        )

    return backend_class(file_path, **kwargs)


def print_available_engines():
    """
    打印所有可用引擎的信息（调试工具）

    输出格式：
        Available Storage Engines:
        ✓ binary  - Binary format (no dependencies)
        ✓ json    - JSON format (no dependencies)
        ✗ excel   - Excel format (requires: openpyxl)
    """
    engines = BackendRegistry.available_engines()

    print("Available Storage Engines:")
    print("-" * 50)

    for engine_name in sorted(engines.keys()):
        available = engines[engine_name]
        backend_class = BackendRegistry.get(engine_name)

        status = "✓" if available else "✗"
        deps = backend_class.REQUIRED_DEPENDENCIES

        if deps:
            deps_str = f" (requires: {', '.join(deps)})"
        else:
            deps_str = " (no dependencies)"

        print(f"{status} {engine_name:10} - {backend_class.__doc__ or 'Storage backend'}{deps_str}")


# 导出公共接口
__all__ = [
    'StorageBackend',
    'BackendRegistry',
    'get_backend',
    'print_available_engines',
]
