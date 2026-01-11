"""
Pytuck JSON存储引擎

人类可读的JSON格式，便于调试和手工编辑
"""

import json
import inspect
from pathlib import Path
from typing import Any, Dict, Callable, Union, TYPE_CHECKING
from datetime import datetime
from .base import StorageBackend
from ..common.exceptions import SerializationError
from .versions import get_format_version

from ..common.options import JsonBackendOptions

if TYPE_CHECKING:
    from ..core.storage import Table
    from ..core.orm import Column


class JSONBackend(StorageBackend):
    """JSON format storage engine (human-readable)"""

    ENGINE_NAME = 'json'
    REQUIRED_DEPENDENCIES = []  # 标准库
    FORMAT_VERSION = get_format_version('json')

    def __init__(self, file_path: Union[str, Path], options: JsonBackendOptions):
        """
        初始化 JSON 后端

        Args:
            file_path: JSON 文件路径
            options: JSON 后端配置选项
        """
        assert isinstance(options, JsonBackendOptions), "options must be an instance of JsonBackendOptions"
        super().__init__(file_path, options)
        # 类型安全：将 options 转为具体的 JsonBackendOptions 类型
        self.options: JsonBackendOptions = options
        self._setup_json_impl()

    def _setup_json_impl(self) -> None:
        """根据用户指定的impl选择JSON实现"""
        impl = self.options.impl

        if impl == 'orjson':
            self._setup_orjson()
        elif impl == 'ujson':
            self._setup_ujson()
        elif impl == 'json' or impl is None:
            self._setup_stdlib_json()
        else:
            # 调用用户自定义的JSON库处理方法
            self._setup_custom_json(impl)

        # 检验内部私有方法是否已被正确赋值
        if not hasattr(self, '_dumps_func') or not hasattr(self, '_loads_func') or not hasattr(self, '_impl_name'):
            raise ValueError(f"JSON implementation '{impl}' setup failed: _dumps_func, _loads_func, and _impl_name must be assigned")

    def _setup_orjson(self) -> None:
        """设置orjson实现，参数不兼容时直接舍弃"""
        try:
            import orjson
        except ImportError:
            raise ImportError(f"orjson not installed. Install with: pip install pytuck[orjson]")

        def dumps_func(obj: Any) -> str:
            # orjson不支持indent和ensure_ascii，直接舍弃这些参数
            result = orjson.dumps(obj)
            return result.decode('utf-8') if isinstance(result, bytes) else result

        self._dumps_func = dumps_func
        self._loads_func = orjson.loads
        self._impl_name = 'orjson'

    def _setup_ujson(self) -> None:
        """设置ujson实现，智能适配参数"""
        try:
            import ujson  # type: ignore
        except ImportError:
            raise ImportError(f"ujson not installed. Install with: pip install pytuck[ujson]")

        def dumps_func(obj: Any) -> str:
            # 检查ujson的dumps方法支持哪些参数，不支持的直接舍弃
            kwargs = {}

            try:
                sig = inspect.signature(ujson.dumps)
                if 'indent' in sig.parameters and self.options.indent:
                    kwargs['indent'] = self.options.indent
                if 'ensure_ascii' in sig.parameters:
                    kwargs['ensure_ascii'] = self.options.ensure_ascii

                return ujson.dumps(obj, **kwargs)
            except Exception:
                # 如果参数检查失败，就使用最简单的方式
                return ujson.dumps(obj)

        self._dumps_func = dumps_func
        self._loads_func = ujson.loads
        self._impl_name = 'ujson'

    def _setup_stdlib_json(self) -> None:
        """设置标准库json实现"""
        import json

        def dumps_func(obj: Any) -> str:
            return json.dumps(obj,
                            indent=self.options.indent,
                            ensure_ascii=self.options.ensure_ascii)

        self._dumps_func = dumps_func
        self._loads_func = json.loads
        self._impl_name = 'json'

    def _setup_custom_json(self, impl: str) -> None:
        """自定义JSON库处理方法，需要用户覆盖此方法

        用户应该通过以下方式来自定义JSON实现：
        JSONBackend._setup_custom_json = lambda self, impl: your_custom_logic

        自定义方法必须设置以下三个属性：
        - self._dumps_func: 序列化函数
        - self._loads_func: 反序列化函数
        - self._impl_name: 实现名称
        """
        raise NotImplementedError(
            f"Unsupported JSON library '{impl}'. "
            f"To use a custom JSON library, you must override _setup_custom_json method:\n"
            f"JSONBackend._setup_custom_json = lambda self, impl: your_custom_logic()\n"
            f"Your custom logic must set self._dumps_func, self._loads_func, and self._impl_name"
        )

    def save(self, tables: Dict[str, 'Table']) -> None:
        """保存所有表数据到JSON文件"""
        data = {
            'format_version': self.FORMAT_VERSION,
            'timestamp': datetime.now().isoformat(),
            'tables': {}
        }

        # 序列化所有表
        for table_name, table in tables.items():
            data['tables'][table_name] = self._serialize_table(table)  # type: ignore

        # 写入文件（原子性）
        temp_path = self.file_path.parent / (self.file_path.name + '.tmp')

        try:
            with open(temp_path, 'w', encoding='utf-8') as f:
                # 使用动态选择的JSON实现
                json_str = self._dumps_func(data)
                f.write(json_str)

            # 原子性重命名
            temp_path.replace(self.file_path)

        except Exception as e:
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except FileNotFoundError:
                    pass
            raise SerializationError(f"Failed to save JSON file: {e}")

    def load(self) -> Dict[str, 'Table']:
        """从JSON文件加载所有表数据"""
        if not self.exists():
            raise FileNotFoundError(f"JSON file not found: {self.file_path}")

        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                # 使用动态选择的JSON实现
                data = self._loads_func(f.read())

            tables = {}
            for table_name, table_data in data['tables'].items():
                table = self._deserialize_table(table_name, table_data)
                tables[table_name] = table

            return tables

        except Exception as e:
            raise SerializationError(f"Failed to load JSON file: {e}")

    def exists(self) -> bool:
        """检查文件是否存在"""
        return self.file_path.exists()

    def delete(self) -> None:
        """删除文件"""
        if self.file_path.exists():
            self.file_path.unlink()

    def _serialize_table(self, table: 'Table') -> Dict[str, Any]:
        """序列化表为JSON可序列化的字典"""
        return {
            'primary_key': table.primary_key,
            'next_id': table.next_id,
            'comment': table.comment,
            'columns': [
                {
                    'name': col.name,
                    'type': col.col_type.__name__,
                    'nullable': col.nullable,
                    'primary_key': col.primary_key,
                    'index': col.index,
                    'comment': col.comment,
                }
                for col in table.columns.values()
            ],
            'records': [
                self._serialize_record(record)
                for record in table.data.values()
            ]
        }

    def _deserialize_table(self, table_name: str, table_data: Dict[str, Any]) -> 'Table':
        """反序列化表"""
        from ..core.storage import Table
        from ..core.orm import Column

        # 重建列定义
        columns = []
        for col_data in table_data['columns']:
            # 类型名转类型
            type_map = {
                'int': int,
                'str': str,
                'float': float,
                'bool': bool,
                'bytes': bytes,
            }
            col_type = type_map.get(col_data['type'], str)

            column = Column(
                col_data['name'],
                col_type,
                nullable=col_data['nullable'],
                primary_key=col_data['primary_key'],
                index=col_data.get('index', False),
                comment=col_data.get('comment')
            )
            columns.append(column)

        # 创建表
        table = Table(
            table_name,
            columns,
            table_data['primary_key'],
            comment=table_data.get('comment')
        )
        table.next_id = table_data['next_id']

        # 加载记录
        for record_data in table_data['records']:
            record = self._deserialize_record(record_data, table.columns)
            pk = record[table.primary_key]
            table.data[pk] = record

        # 重建索引（清除构造函数创建的空索引）
        for col_name, column in table.columns.items():
            if column.index:
                # 删除空索引，重新构建
                if col_name in table.indexes:
                    del table.indexes[col_name]
                table.build_index(col_name)

        return table

    def _serialize_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """序列化记录（处理特殊类型）"""
        result = {}
        for key, value in record.items():
            if isinstance(value, bytes):
                # bytes 转 base64
                import base64
                result[key] = {
                    '_type': 'bytes',
                    '_value': base64.b64encode(value).decode('ascii')
                }
            else:
                result[key] = value
        return result

    def _deserialize_record(self, record_data: Dict[str, Any], columns: Dict[str, 'Column']) -> Dict[str, Any]:
        """反序列化记录"""
        result = {}
        for key, value in record_data.items():
            if isinstance(value, dict) and '_type' in value:
                # 特殊类型
                if value['_type'] == 'bytes':
                    import base64
                    result[key] = base64.b64decode(value['_value'])
                else:
                    result[key] = value['_value']
            else:
                result[key] = value
        return result

    def get_metadata(self) -> Dict[str, Any]:
        """获取元数据"""
        if not self.exists():
            return {}

        file_stat = self.file_path.stat()
        file_size = file_stat.st_size
        modified_time = file_stat.st_mtime

        # 尝试读取版本信息
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                # 使用动态选择的JSON实现
                data = self._loads_func(f.read())
                version = data.get('version', 'unknown')
                timestamp = data.get('timestamp', 'unknown')
                table_count = len(data.get('tables', {}))
        except:
            version = 'unknown'
            timestamp = 'unknown'
            table_count = 0

        return {
            'engine': 'json',
            'version': version,
            'file_size': file_size,
            'modified': modified_time,
            'timestamp': timestamp,
            'table_count': table_count,
            'json_impl': getattr(self, '_impl_name', 'unknown'),  # 添加JSON实现信息
        }
