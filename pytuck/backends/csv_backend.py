"""
Pytuck CSV存储引擎

使用ZIP压缩包存储多个CSV文件，保持单文件设计，适合数据分析和Excel兼容
"""

import csv
import json
import base64
import io
import zipfile
from pathlib import Path
from typing import Any, Dict, Union, TYPE_CHECKING, Tuple, Optional
from datetime import datetime
from .base import StorageBackend
from ..common.exceptions import SerializationError
from .versions import get_format_version

from ..common.options import CsvBackendOptions

if TYPE_CHECKING:
    from ..core.storage import Table
    from ..core.orm import Column


class CSVBackend(StorageBackend):
    """CSV format storage engine (ZIP-based, Excel compatible)"""

    ENGINE_NAME = 'csv'
    REQUIRED_DEPENDENCIES = []  # 标准库
    FORMAT_VERSION = get_format_version('csv')

    def __init__(self, file_path: Union[str, Path], options: CsvBackendOptions):
        """
        初始化 CSV 后端

        Args:
            file_path: CSV ZIP 文件路径
            options: CSV 后端配置选项
        """
        assert isinstance(options, CsvBackendOptions), "options must be an instance of CsvBackendOptions"
        super().__init__(file_path, options)
        # 类型安全：将 options 转为具体的 CsvBackendOptions 类型
        self.options: CsvBackendOptions = options

    def save(self, tables: Dict[str, 'Table']) -> None:
        """保存所有表数据到ZIP压缩包"""
        # 使用临时文件保证原子性
        temp_path = self.file_path.parent / (self.file_path.name + '.tmp')

        try:
            with zipfile.ZipFile(str(temp_path), 'w', zipfile.ZIP_DEFLATED) as zf:
                # 收集所有表的 schema
                tables_schema: Dict[str, Dict[str, Any]] = {}
                for table_name, table in tables.items():
                    tables_schema[table_name] = {
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
                                'comment': col.comment
                            }
                            for col in table.columns.values()
                        ]
                    }

                # 保存全局元数据（包含所有表的 schema）
                metadata = {
                    'format_version': self.FORMAT_VERSION,
                    'timestamp': datetime.now().isoformat(),
                    'table_count': len(tables),
                    'tables': tables_schema
                }
                zf.writestr('_metadata.json', json.dumps(metadata, indent=self.options.indent))

                # 为每个表保存 CSV 数据
                for table_name, table in tables.items():
                    self._save_table_to_zip(zf, table_name, table)

            # 原子性重命名
            if self.file_path.exists():
                self.file_path.unlink()
            temp_path.replace(self.file_path)

        except Exception as e:
            # 清理临时文件
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except FileNotFoundError:
                    pass
            raise SerializationError(f"Failed to save CSV archive: {e}")

    def load(self) -> Dict[str, 'Table']:
        """从ZIP压缩包加载所有表数据"""
        if not self.exists():
            raise FileNotFoundError(f"CSV archive not found: {self.file_path}")

        try:
            with zipfile.ZipFile(str(self.file_path), 'r') as zf:
                # 读取元数据
                metadata: Dict[str, Any] = {}
                if '_metadata.json' in zf.namelist():
                    with zf.open('_metadata.json') as f:
                        metadata = json.load(f)

                # 从 metadata 中获取所有表的 schema
                tables_schema: Dict[str, Dict[str, Any]] = metadata.get('tables', {})

                # 找到所有CSV文件
                tables = {}
                csv_files = [name for name in zf.namelist() if name.endswith('.csv') and not name.startswith('_')]

                for csv_file in csv_files:
                    table_name = csv_file[:-4]  # 移除 .csv
                    schema = tables_schema.get(table_name, {})
                    table = self._load_table_from_zip(zf, table_name, schema)
                    tables[table_name] = table

            return tables

        except Exception as e:
            raise SerializationError(f"Failed to load CSV archive: {e}")

    def exists(self) -> bool:
        """检查文件是否存在"""
        return self.file_path.exists()

    def delete(self) -> None:
        """删除文件"""
        if self.exists():
            self.file_path.unlink()

    def _save_table_to_zip(self, zf: zipfile.ZipFile, table_name: str, table: 'Table') -> None:
        """保存单个表的 CSV 数据到ZIP"""
        # 保存 CSV 数据到内存
        csv_buffer = io.StringIO()

        if len(table.data) > 0:
            fieldnames = list(table.columns.keys())
            writer = csv.DictWriter(csv_buffer, fieldnames=fieldnames, delimiter=self.options.delimiter)
            writer.writeheader()

            for record in table.data.values():
                # 序列化特殊类型
                row = self._serialize_record(record, table.columns)
                writer.writerow(row)

        # 写入ZIP
        zf.writestr(f'{table_name}.csv', csv_buffer.getvalue())

    def _load_table_from_zip(
        self, zf: zipfile.ZipFile, table_name: str, schema: Dict[str, Any]
    ) -> 'Table':
        """从ZIP加载单个表"""
        from ..core.storage import Table
        from ..core.orm import Column

        csv_file = f'{table_name}.csv'

        # 重建列定义
        columns = []
        type_map = {
            'int': int,
            'str': str,
            'float': float,
            'bool': bool,
            'bytes': bytes,
        }

        for col_data in schema.get('columns', []):
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
            schema.get('primary_key', 'id'),
            comment=schema.get('comment')
        )
        table.next_id = schema.get('next_id', 1)

        # 加载 CSV 数据
        with zf.open(csv_file) as f:
            encoding = self.options.encoding
            text_stream = io.TextIOWrapper(f, encoding=encoding)
            reader = csv.DictReader(text_stream, delimiter=self.options.delimiter)

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
        result: Dict[str, Any] = {}
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
            file_stat = self.file_path.stat()
            file_size = file_stat.st_size
            modified_time = file_stat.st_mtime

            with zipfile.ZipFile(str(self.file_path), 'r') as zf:
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

    @classmethod
    def probe(cls, file_path: Union[str, Path]) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        轻量探测文件是否为 CSV 引擎格式

        通过检查 ZIP 文件是否包含 _metadata.json 文件来识别。
        只检查 ZIP 结构和关键文件存在性，非常快速。

        Returns:
            Tuple[bool, Optional[Dict]]: (是否匹配, 元数据信息或None)
        """
        try:
            file_path = Path(file_path).expanduser()
            if not file_path.exists():
                return False, {'error': 'file_not_found'}

            # 获取文件信息
            file_stat = file_path.stat()
            file_size = file_stat.st_size

            # 空文件不可能是有效的 ZIP
            if file_size == 0:
                return False, {'error': 'empty_file'}

            # 检查是否为有效的 ZIP 文件
            if not zipfile.is_zipfile(file_path):
                return False, None

            # 检查 ZIP 内容
            try:
                with zipfile.ZipFile(str(file_path), 'r') as zf:
                    namelist = zf.namelist()

                    # 检查是否包含 _metadata.json 文件
                    if '_metadata.json' not in namelist:
                        return False, None

                    # 尝试读取 metadata
                    try:
                        with zf.open('_metadata.json') as f:
                            metadata = json.load(f)

                        # 检查是否为 Pytuck CSV 格式
                        if not isinstance(metadata, dict):
                            return False, None

                        # 检查必要的字段
                        if 'tables' not in metadata:
                            return False, None

                        # 获取元数据信息
                        format_version = metadata.get('format_version')
                        table_count = len(metadata.get('tables', {}))
                        timestamp = metadata.get('timestamp')

                        # 检查是否有 CSV 文件
                        csv_files = [name for name in namelist if name.endswith('.csv') and not name.startswith('_')]

                        # 成功识别为 CSV 格式
                        return True, {
                            'engine': 'csv',
                            'format_version': format_version,
                            'table_count': table_count,
                            'csv_file_count': len(csv_files),
                            'file_size': file_size,
                            'modified': file_stat.st_mtime,
                            'timestamp': timestamp,
                            'confidence': 'high'
                        }

                    except (json.JSONDecodeError, KeyError):
                        return False, {'error': 'invalid_metadata_format'}

            except zipfile.BadZipFile:
                return False, {'error': 'corrupted_zip'}

        except Exception as e:
            return False, {'error': f'probe_exception: {str(e)}'}
