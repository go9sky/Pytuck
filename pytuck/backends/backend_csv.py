"""
Pytuck CSV存储引擎

使用ZIP压缩包存储多个CSV文件，保持单文件设计，适合数据分析和Excel兼容
"""

import csv
import json
import io
import threading
import zipfile
from pathlib import Path
from typing import Any, Dict, Union, TYPE_CHECKING, Tuple, Optional
from datetime import datetime
from .base import StorageBackend
from ..common.exceptions import SerializationError, EncryptionError
from .versions import get_format_version
from ..core.types import TypeRegistry

from ..common.options import CsvBackendOptions

if TYPE_CHECKING:
    from ..core.storage import Table
    from ..core.orm import Column

# 模块级锁，用于同步 csv.field_size_limit() 的全局修改（进程内线程安全）
_CSV_FIELD_SIZE_LOCK = threading.Lock()


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
            metadata_bytes = json.dumps(metadata, indent=self.options.indent).encode('utf-8')

            if self.options.password:
                # 使用加密 ZIP 写入器
                from ..common.encrypted_zip import EncryptedZipFile
                with EncryptedZipFile(str(temp_path), self.options.password) as zf:
                    zf.writestr('_metadata.json', metadata_bytes)
                    for table_name, table in tables.items():
                        csv_bytes = self._generate_csv_bytes(table_name, table)
                        zf.writestr(f'{table_name}.csv', csv_bytes)
            else:
                # 原有行为：标准 zipfile（无加密）
                with zipfile.ZipFile(str(temp_path), 'w', zipfile.ZIP_DEFLATED) as zf:
                    zf.writestr('_metadata.json', metadata_bytes)
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
                # 检测是否加密
                encrypted = any((info.flag_bits & 0x1) != 0 for info in zf.infolist())

                if encrypted:
                    if not self.options.password:
                        raise EncryptionError(
                            "CSV archive is encrypted. Please provide password in CsvBackendOptions."
                        )
                    pwd = self.options.password.encode('utf-8')
                else:
                    pwd = None

                # 读取元数据
                metadata: Dict[str, Any] = {}
                if '_metadata.json' in zf.namelist():
                    with zf.open('_metadata.json', pwd=pwd) as f:
                        metadata = json.load(f)

                # 从 metadata 中获取所有表的 schema
                tables_schema: Dict[str, Dict[str, Any]] = metadata.get('tables', {})

                # 找到所有CSV文件
                tables = {}
                csv_files = [name for name in zf.namelist() if name.endswith('.csv') and not name.startswith('_')]

                for csv_file in csv_files:
                    table_name = csv_file[:-4]  # 移除 .csv
                    schema = tables_schema.get(table_name, {})
                    table = self._load_table_from_zip(zf, table_name, schema, pwd=pwd)
                    tables[table_name] = table

            return tables

        except EncryptionError:
            raise
        except RuntimeError as e:
            # zipfile 在密码错误时抛出 RuntimeError
            if "Bad password" in str(e) or "password" in str(e).lower():
                raise EncryptionError("Incorrect password for CSV archive.")
            raise SerializationError(f"Failed to load CSV archive: {e}")
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
        csv_bytes = self._generate_csv_bytes(table_name, table)
        zf.writestr(f'{table_name}.csv', csv_bytes)

    def _generate_csv_bytes(self, table_name: str, table: 'Table') -> bytes:
        """生成表的 CSV 字节数据"""
        csv_buffer = io.StringIO()

        if len(table.data) > 0:
            fieldnames = list(table.columns.keys())
            writer = csv.DictWriter(csv_buffer, fieldnames=fieldnames, delimiter=self.options.delimiter)
            writer.writeheader()

            for record in table.data.values():
                # 序列化特殊类型
                row = self._serialize_record(record, table.columns)
                writer.writerow(row)

        return csv_buffer.getvalue().encode(self.options.encoding)

    def _load_table_from_zip(
        self,
        zf: zipfile.ZipFile,
        table_name: str,
        schema: Dict[str, Any],
        pwd: Optional[bytes] = None
    ) -> 'Table':
        """从ZIP加载单个表"""
        from ..core.storage import Table
        from ..core.orm import Column

        csv_file = f'{table_name}.csv'

        # 重建列定义
        columns = []

        for col_data in schema.get('columns', []):
            col_type = TypeRegistry.get_type_by_name(col_data['type'])
            column = Column(
                col_type,
                name=col_data['name'],
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
        self._read_csv_into_table(zf, csv_file, table, pwd)

        # 重建索引（删除构造函数创建的空索引）
        for col_name, column in table.columns.items():
            if column.index:
                if col_name in table.indexes:
                    del table.indexes[col_name]
                table.build_index(col_name)

        return table

    def _read_csv_into_table(
        self,
        zf: zipfile.ZipFile,
        csv_file: str,
        table: 'Table',
        pwd: Optional[bytes]
    ) -> None:
        """
        从 ZIP 中读取 CSV 文件并填充到表中

        若配置了 field_size_limit，则临时修改 csv.field_size_limit() 全局设置，
        并通过锁保证进程内线程安全，读取完成后恢复原值。
        """
        limit = self.options.field_size_limit
        if limit is not None:
            with _CSV_FIELD_SIZE_LOCK:
                prev_limit = csv.field_size_limit(limit)
                try:
                    self._do_read_csv(zf, csv_file, table, pwd)
                finally:
                    csv.field_size_limit(prev_limit)
        else:
            self._do_read_csv(zf, csv_file, table, pwd)

    def _do_read_csv(
        self,
        zf: zipfile.ZipFile,
        csv_file: str,
        table: 'Table',
        pwd: Optional[bytes]
    ) -> None:
        """实际执行 CSV 读取并填充表数据"""
        with zf.open(csv_file, pwd=pwd) as f:
            encoding = self.options.encoding
            text_stream = io.TextIOWrapper(f, encoding=encoding)
            reader = csv.DictReader(text_stream, delimiter=self.options.delimiter)

            # 检查主键列是否存在于 CSV header 中（仅当有主键时）
            if table.primary_key and reader.fieldnames and table.primary_key not in reader.fieldnames:
                raise SerializationError(
                    f"CSV 文件 '{csv_file}' 缺少主键列 '{table.primary_key}'，"
                    f"可用列: {reader.fieldnames}"
                )

            for idx, row_data in enumerate(reader):
                record = self._deserialize_record(row_data, table.columns)
                # 确定主键或使用内部索引
                if table.primary_key:
                    pk = record[table.primary_key]
                else:
                    # 无主键表：使用行索引作为内部 pk
                    pk = idx + 1
                    # 更新 next_id 以确保后续插入的正确性
                    if pk >= table.next_id:
                        table.next_id = pk + 1
                table.data[pk] = record

    @staticmethod
    def _serialize_record(record: Dict[str, Any], columns: Dict[str, 'Column']) -> Dict[str, str]:
        """序列化记录（处理特殊类型）"""
        result = {}
        for key, value in record.items():
            if key not in columns:
                result[key] = str(value) if value is not None else ''
                continue

            column = columns[key]
            if value is None:
                result[key] = ''
            elif column.col_type == bool:
                # bool 转字符串（CSV 特殊处理）
                result[key] = 'true' if value else 'false'
            else:
                # 使用 TypeRegistry 统一序列化
                serialized = TypeRegistry.serialize_for_text(value, column.col_type)
                result[key] = str(serialized) if serialized is not None else ''
        return result

    @staticmethod
    def _deserialize_record(record_data: Dict[str, str], columns: Dict[str, 'Column']) -> Dict[str, Any]:
        """反序列化记录"""
        result: Dict[str, Any] = {}
        for key, value in record_data.items():
            if key not in columns:
                continue

            column = columns[key]

            # 处理空值
            if value == '' or value is None:
                result[key] = None
            else:
                # 使用 TypeRegistry 统一反序列化
                result[key] = TypeRegistry.deserialize_from_text(value, column.col_type)

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
                # 检测是否加密
                encrypted = any((info.flag_bits & 0x1) != 0 for info in zf.infolist())

                if encrypted:
                    if self.options.password:
                        # 使用密码读取 metadata
                        pwd = self.options.password.encode('utf-8')
                        try:
                            with zf.open('_metadata.json', pwd=pwd) as f:
                                metadata = json.load(f)
                        except RuntimeError:
                            # 密码错误
                            return {
                                'engine': 'csv',
                                'encrypted': True,
                                'file_size': file_size,
                                'modified': modified_time,
                                'error': 'incorrect_password'
                            }
                    else:
                        # 加密但未提供密码
                        return {
                            'engine': 'csv',
                            'encrypted': True,
                            'requires_password': True,
                            'file_size': file_size,
                            'modified': modified_time
                        }
                else:
                    if '_metadata.json' in zf.namelist():
                        with zf.open('_metadata.json') as f:
                            metadata = json.load(f)
                    else:
                        metadata = {}

            metadata['engine'] = 'csv'
            metadata['file_size'] = file_size
            metadata['modified'] = modified_time
            if encrypted:
                metadata['encrypted'] = True

            return metadata

        except Exception:
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

                    # 检测是否加密
                    encrypted = any((info.flag_bits & 0x1) != 0 for info in zf.infolist())

                    if encrypted:
                        # 加密的 ZIP 无法直接读取 metadata，但可以识别格式
                        csv_files = [name for name in namelist if name.endswith('.csv') and not name.startswith('_')]
                        return True, {
                            'engine': 'csv',
                            'encrypted': True,
                            'requires_password': True,
                            'csv_file_count': len(csv_files),
                            'file_size': file_size,
                            'modified': file_stat.st_mtime,
                            'confidence': 'medium'
                        }

                    # 尝试读取 metadata（未加密情况）
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
