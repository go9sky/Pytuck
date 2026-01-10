"""
Pytuck JSON存储引擎

人类可读的JSON格式，便于调试和手工编辑
"""

import json
import os
from typing import Any, Dict, TYPE_CHECKING
from datetime import datetime
from .base import StorageBackend
from ..exceptions import SerializationError

if TYPE_CHECKING:
    from ..storage import Table
    from ..orm import Column


class JSONBackend(StorageBackend):
    """JSON format storage engine (human-readable)"""

    ENGINE_NAME = 'json'
    REQUIRED_DEPENDENCIES = []  # 标准库

    def save(self, tables: Dict[str, 'Table']) -> None:
        """保存所有表数据到JSON文件"""
        data = {
            'version': '0.1.0',
            'timestamp': datetime.now().isoformat(),
            'tables': {}
        }

        # 序列化所有表
        for table_name, table in tables.items():
            data['tables'][table_name] = self._serialize_table(table)

        # 写入文件（原子性）
        temp_path = self.file_path + '.tmp'

        try:
            with open(temp_path, 'w', encoding='utf-8') as f:
                indent = self.options.get('indent', 2)
                json.dump(data, f, indent=indent, ensure_ascii=False)

            # 原子性重命名
            if os.path.exists(self.file_path):
                os.remove(self.file_path)
            os.rename(temp_path, self.file_path)

        except Exception as e:
            if os.path.exists(temp_path):
                os.remove(temp_path)
            raise SerializationError(f"Failed to save JSON file: {e}")

    def load(self) -> Dict[str, 'Table']:
        """从JSON文件加载所有表数据"""
        if not self.exists():
            raise FileNotFoundError(f"JSON file not found: {self.file_path}")

        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            tables = {}
            for table_name, table_data in data['tables'].items():
                table = self._deserialize_table(table_name, table_data)
                tables[table_name] = table

            return tables

        except Exception as e:
            raise SerializationError(f"Failed to load JSON file: {e}")

    def exists(self) -> bool:
        """检查文件是否存在"""
        return os.path.exists(self.file_path)

    def delete(self) -> None:
        """删除文件"""
        if self.exists():
            os.remove(self.file_path)

    def _serialize_table(self, table: 'Table') -> Dict[str, Any]:
        """序列化表为JSON可序列化的字典"""
        return {
            'primary_key': table.primary_key,
            'next_id': table.next_id,
            'columns': [
                {
                    'name': col.name,
                    'type': col.col_type.__name__,
                    'nullable': col.nullable,
                    'primary_key': col.primary_key,
                    'index': col.index,
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
        from ..storage import Table
        from ..orm import Column

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
                index=col_data.get('index', False)
            )
            columns.append(column)

        # 创建表
        table = Table(table_name, columns, table_data['primary_key'])
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

        file_size = os.path.getsize(self.file_path)
        modified_time = os.path.getmtime(self.file_path)

        # 尝试读取版本信息
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
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
        }
