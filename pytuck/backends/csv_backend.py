"""
Pytuck CSV存储引擎

使用ZIP压缩包存储多个CSV文件，保持单文件设计，适合数据分析和Excel兼容
"""

import csv
import json
import os
import base64
import io
import zipfile
from typing import Any, Dict, TYPE_CHECKING
from datetime import datetime
from .base import StorageBackend
from ..exceptions import SerializationError

if TYPE_CHECKING:
    from ..storage import Table
    from ..orm import Column


class CSVBackend(StorageBackend):
    """CSV format storage engine (ZIP-based, Excel compatible)"""

    ENGINE_NAME = 'csv'
    REQUIRED_DEPENDENCIES = []  # 标准库

    def save(self, tables: Dict[str, 'Table']) -> None:
        """保存所有表数据到ZIP压缩包"""
        # 使用临时文件保证原子性
        temp_path = self.file_path + '.tmp'

        try:
            with zipfile.ZipFile(temp_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                # 保存全局元数据
                metadata = {
                    'version': '0.1.0',
                    'timestamp': datetime.now().isoformat(),
                    'table_count': len(tables)
                }
                zf.writestr('_metadata.json', json.dumps(metadata, indent=2))

                # 为每个表保存 CSV + schema
                for table_name, table in tables.items():
                    self._save_table_to_zip(zf, table_name, table)

            # 原子性重命名
            if os.path.exists(self.file_path):
                os.remove(self.file_path)
            os.rename(temp_path, self.file_path)

        except Exception as e:
            # 清理临时文件
            if os.path.exists(temp_path):
                os.remove(temp_path)
            raise SerializationError(f"Failed to save CSV archive: {e}")

    def load(self) -> Dict[str, 'Table']:
        """从ZIP压缩包加载所有表数据"""
        if not self.exists():
            raise FileNotFoundError(f"CSV archive not found: {self.file_path}")

        try:
            with zipfile.ZipFile(self.file_path, 'r') as zf:
                # 读取元数据
                if '_metadata.json' in zf.namelist():
                    with zf.open('_metadata.json') as f:
                        metadata = json.load(f)

                # 找到所有CSV文件
                tables = {}
                csv_files = [name for name in zf.namelist() if name.endswith('.csv') and not name.startswith('_')]

                for csv_file in csv_files:
                    table_name = csv_file[:-4]  # 移除 .csv
                    table = self._load_table_from_zip(zf, table_name)
                    tables[table_name] = table

            return tables

        except Exception as e:
            raise SerializationError(f"Failed to load CSV archive: {e}")

    def exists(self) -> bool:
        """检查文件是否存在"""
        return os.path.exists(self.file_path)

    def delete(self) -> None:
        """删除文件"""
        if self.exists():
            os.remove(self.file_path)

    def _save_table_to_zip(self, zf: zipfile.ZipFile, table_name: str, table: 'Table') -> None:
        """保存单个表到ZIP"""
        # 保存 schema
        schema = {
            'primary_key': table.primary_key,
            'next_id': table.next_id,
            'columns': [
                {
                    'name': col.name,
                    'type': col.col_type.__name__,
                    'nullable': col.nullable,
                    'primary_key': col.primary_key,
                    'index': col.index
                }
                for col in table.columns.values()
            ]
        }
        zf.writestr(f'{table_name}_schema.json', json.dumps(schema, indent=2))

        # 保存 CSV 数据到内存
        csv_buffer = io.StringIO()
        encoding = self.options.get('encoding', 'utf-8')

        if len(table.data) > 0:
            fieldnames = list(table.columns.keys())
            writer = csv.DictWriter(csv_buffer, fieldnames=fieldnames)
            writer.writeheader()

            for record in table.data.values():
                # 序列化特殊类型
                row = self._serialize_record(record, table.columns)
                writer.writerow(row)

        # 写入ZIP
        zf.writestr(f'{table_name}.csv', csv_buffer.getvalue())

    def _load_table_from_zip(self, zf: zipfile.ZipFile, table_name: str) -> 'Table':
        """从ZIP加载单个表"""
        from ..storage import Table
        from ..orm import Column

        schema_file = f'{table_name}_schema.json'
        csv_file = f'{table_name}.csv'

        # 加载 schema
        with zf.open(schema_file) as f:
            schema = json.load(f)

        # 重建列定义
        columns = []
        for col_data in schema['columns']:
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
        table = Table(table_name, columns, schema['primary_key'])
        table.next_id = schema['next_id']

        # 加载 CSV 数据
        with zf.open(csv_file) as f:
            text_stream = io.TextIOWrapper(f, encoding=self.options.get('encoding', 'utf-8'))
            reader = csv.DictReader(text_stream)

            for row_data in reader:
                record = self._deserialize_record(row_data, table.columns)
                pk = record[table.primary_key]
                table.data[pk] = record

        # 重建索引（删除构造函数创建的空索引）
        for col_name, column in table.columns.items():
            if column.index:
                if col_name in table.indexes:
                    del table.indexes[col_name]
                table.build_index(col_name)

        return table

    def _serialize_record(self, record: Dict[str, Any], columns: Dict[str, 'Column']) -> Dict[str, str]:
        """序列化记录（处理特殊类型）"""
        result = {}
        for key, value in record.items():
            if value is None:
                result[key] = ''
            elif isinstance(value, bytes):
                # bytes 转 base64
                result[key] = base64.b64encode(value).decode('ascii')
            elif isinstance(value, bool):
                # bool 转字符串
                result[key] = 'true' if value else 'false'
            else:
                result[key] = str(value) if value is not None else ''
        return result

    def _deserialize_record(self, record_data: Dict[str, str], columns: Dict[str, 'Column']) -> Dict[str, Any]:
        """反序列化记录"""
        result = {}
        for key, value in record_data.items():
            if key not in columns:
                continue

            column = columns[key]

            # 处理空值
            if value == '' or value is None:
                result[key] = None
            # 根据类型转换
            elif column.col_type == int:
                result[key] = int(value)
            elif column.col_type == float:
                result[key] = float(value)
            elif column.col_type == bool:
                result[key] = (value.lower() == 'true')
            elif column.col_type == bytes:
                # base64 解码
                result[key] = base64.b64decode(value)
            else:  # str
                result[key] = value

        return result

    def get_metadata(self) -> Dict[str, Any]:
        """获取元数据"""
        if not self.exists():
            return {}

        try:
            file_size = os.path.getsize(self.file_path)
            modified_time = os.path.getmtime(self.file_path)

            with zipfile.ZipFile(self.file_path, 'r') as zf:
                if '_metadata.json' in zf.namelist():
                    with zf.open('_metadata.json') as f:
                        metadata = json.load(f)
                else:
                    metadata = {}

            metadata['engine'] = 'csv'
            metadata['file_size'] = file_size
            metadata['modified'] = modified_time

            return metadata

        except:
            return {}
