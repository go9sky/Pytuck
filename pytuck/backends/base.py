"""
Pytuck 存储后端抽象基类

定义所有持久化引擎必须实现的接口
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any, List, Optional, Union, TYPE_CHECKING

from ..common.options import BackendOptions

if TYPE_CHECKING:
    from ..core.storage import Table


class StorageBackend(ABC):
    """
    存储后端抽象基类

    所有持久化引擎必须实现此接口，提供统一的 save/load API
    """

    # 引擎标识符（用于注册和选择）
    ENGINE_NAME: str = None  # type: ignore

    # 所需的外部依赖列表（用于检查可用性）
    REQUIRED_DEPENDENCIES: List[str] = []

    def __init__(self, file_path: Union[str, Path], options: BackendOptions):
        """
        初始化后端

        Args:
            file_path: 数据文件路径，接受字符串或 Path 对象（不同引擎解释不同）
                - binary: 单个 .db 文件
                - json: 单个 .json 文件
                - csv: ZIP 文件路径
                - sqlite: 单个 .sqlite 文件
                - excel: 单个 .xlsx 文件
                - xml: 单个 .xml 文件
            options: 强类型的后端配置选项对象
        """
        # 输入兼容性处理：统一转为 Path 对象
        self.file_path: Path = Path(file_path).expanduser()
        self.options = options

    @abstractmethod
    def save(self, tables: Dict[str, 'Table']) -> None:
        """
        保存所有表数据到持久化存储

        Args:
            tables: 表字典 {table_name: Table对象}

        Table 对象结构：
            - table.name: str - 表名
            - table.columns: Dict[str, Column] - 列定义
            - table.primary_key: str - 主键字段名
            - table.data: Dict[pk, record_dict] - 数据 {主键: 记录字典}
            - table.indexes: Dict[str, HashIndex] - 索引
            - table.next_id: int - 下一个自增ID

        实现要点：
            1. 序列化表结构（列定义、主键、next_id）
            2. 序列化所有记录数据
            3. 可选：持久化索引数据（也可以在加载时重建）
            4. 确保原子性写入（先写临时文件，再重命名）
        """
        pass

    @abstractmethod
    def load(self) -> Dict[str, 'Table']:
        """
        从持久化存储加载所有表数据

        Returns:
            表字典 {table_name: Table对象}

        实现要点：
            1. 反序列化表结构
            2. 反序列化所有记录
            3. 重建 Table 对象
            4. 重建索引（如果未持久化）
            5. 恢复 next_id 状态

        Raises:
            SerializationError: 反序列化失败
            FileNotFoundError: 数据文件不存在
        """
        pass

    @abstractmethod
    def exists(self) -> bool:
        """
        检查数据文件是否存在

        Returns:
            是否存在

        用于判断是加载现有数据还是创建新数据库
        """
        pass

    @abstractmethod
    def delete(self) -> None:
        """
        删除数据文件（用于清理）

        实现要点：
            - 删除所有相关文件（数据、索引、元数据等）
            - 如果是目录（如CSV），删除整个目录
        """
        pass

    @classmethod
    def is_available(cls) -> bool:
        """
        检查引擎是否可用（依赖是否满足）

        Returns:
            是否可用

        实现逻辑：
            尝试导入所有 REQUIRED_DEPENDENCIES，全部成功则可用
        """
        for dep in cls.REQUIRED_DEPENDENCIES:
            try:
                __import__(dep)
            except ImportError:
                return False
        return True

    def get_metadata(self) -> Dict[str, Any]:
        """
        获取后端元数据（可选实现）

        Returns:
            元数据字典（版本、大小、修改时间等）

        示例返回：
            {
                'version': '0.1.0',
                'size': 12345,  # 字节
                'modified': '2026-01-05T10:00:00',
                'table_count': 5,
                'record_count': 1000,
            }
        """
        return {}

    def supports_server_side_pagination(self) -> bool:
        """
        检查后端是否支持服务端分页

        Returns:
            True 如果支持服务端分页，False 使用内存分页
        """
        return False

    def query_with_pagination(self,
                             table_name: str,
                             conditions: List[Dict[str, Any]],
                             limit: Optional[int] = None,
                             offset: int = 0,
                             order_by: Optional[str] = None,
                             order_desc: bool = False) -> Dict[str, Any]:
        """
        带分页的查询（可选实现，用于数据库后端优化）

        Args:
            table_name: 表名
            conditions: 查询条件列表（简化格式）
            limit: 限制返回记录数
            offset: 跳过的记录数
            order_by: 排序字段名
            order_desc: 是否降序排列

        Returns:
            {
                'records': List[Dict[str, Any]],  # 查询结果
                'total_count': int,               # 总记录数（可选）
                'has_more': bool,                 # 是否还有更多数据（可选）
            }

        Note:
            - 默认实现抛出 NotImplementedError
            - 只有支持的后端才需要实现此方法
            - SQLite、DuckDB 等数据库后端可以实现真正的服务端分页
            - JSON、CSV 等文件后端通常不实现此方法
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support server-side pagination. "
            f"Use storage.query() with memory-based pagination instead."
        )

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(file_path='{self.file_path}')"
