"""
Pytuck XML存储引擎

使用结构化XML格式，适合企业集成和标准化数据交换
"""

import json
import os
import base64
from typing import Any, Dict, TYPE_CHECKING
from datetime import datetime
from .base import StorageBackend
from ..exceptions import SerializationError

if TYPE_CHECKING:
    from ..storage import Table
    from lxml import etree


class XMLBackend(StorageBackend):
    """XML format storage engine (requires lxml)"""

    ENGINE_NAME = 'xml'
    REQUIRED_DEPENDENCIES = ['lxml']

    def save(self, tables: Dict[str, 'Table']) -> None:
        """保存所有表数据到XML文件"""
        try:
            from lxml import etree
        except ImportError:
            raise SerializationError("lxml is required for XML backend. Install with: pip install pytuck[xml]")

        try:
            # 创建根元素
            root = etree.Element('database',
                               version='0.1.0',
                               timestamp=datetime.now().isoformat())

            # 为每个表创建 <table> 元素
            for table_name, table in tables.items():
                self._save_table_to_xml(root, table_name, table)

            # 写入文件（原子性）
            temp_path = self.file_path + '.tmp'
            tree = etree.ElementTree(root)
            tree.write(temp_path,
                      pretty_print=True,
                      xml_declaration=True,
                      encoding='UTF-8')

            if os.path.exists(self.file_path):
                os.remove(self.file_path)
            os.rename(temp_path, self.file_path)

        except Exception as e:
            if os.path.exists(temp_path):
                os.remove(temp_path)
            raise SerializationError(f"Failed to save XML file: {e}")

    def load(self) -> Dict[str, 'Table']:
        """从XML文件加载所有表数据"""
        if not self.exists():
            raise FileNotFoundError(f"XML file not found: {self.file_path}")

        try:
            from lxml import etree
        except ImportError:
            raise SerializationError("lxml is required for XML backend. Install with: pip install pytuck[xml]")

        try:
            tree = etree.parse(self.file_path)
            root = tree.getroot()

            tables = {}
            for table_elem in root.findall('table'):
                table_name = table_elem.get('name')
                table = self._load_table_from_xml(table_elem)
                tables[table_name] = table

            return tables

        except Exception as e:
            raise SerializationError(f"Failed to load XML file: {e}")

    def exists(self) -> bool:
        """检查文件是否存在"""
        return os.path.exists(self.file_path)

    def delete(self) -> None:
        """删除文件"""
        if self.exists():
            os.remove(self.file_path)

    def _save_table_to_xml(self, root: Any, table_name: str, table: 'Table') -> None:
        """保存单个表到XML"""
        from lxml import etree

        table_elem = etree.SubElement(root, 'table',
                                      name=table_name,
                                      primary_key=table.primary_key,
                                      next_id=str(table.next_id))

        # 列定义
        columns_elem = etree.SubElement(table_elem, 'columns')
        for col in table.columns.values():
            etree.SubElement(columns_elem, 'column',
                           name=col.name,
                           type=col.col_type.__name__,
                           nullable=str(col.nullable).lower(),
                           primary_key=str(col.primary_key).lower(),
                           index=str(col.index).lower())

        # 记录数据
        records_elem = etree.SubElement(table_elem, 'records')
        for record in table.data.values():
            record_elem = etree.SubElement(records_elem, 'record')
            for col_name, value in record.items():
                column = table.columns[col_name]
                field_elem = etree.SubElement(record_elem, 'field',
                                             name=col_name,
                                             type=column.col_type.__name__)

                # 处理值
                if value is None:
                    field_elem.set('null', 'true')
                    field_elem.text = ''
                elif isinstance(value, bytes):
                    field_elem.set('encoding', 'base64')
                    field_elem.text = base64.b64encode(value).decode('ascii')
                elif isinstance(value, bool):
                    field_elem.text = str(value).lower()
                else:
                    field_elem.text = str(value)

    def _load_table_from_xml(self, table_elem: Any) -> 'Table':
        """从XML加载单个表"""
        from ..storage import Table
        from ..orm import Column

        table_name = table_elem.get('name')
        primary_key = table_elem.get('primary_key')
        next_id = int(table_elem.get('next_id'))

        # 重建列
        columns = []
        columns_elem = table_elem.find('columns')
        for col_elem in columns_elem.findall('column'):
            type_map = {
                'int': int,
                'str': str,
                'float': float,
                'bool': bool,
                'bytes': bytes
            }
            col_type = type_map.get(col_elem.get('type'), str)

            column = Column(
                col_elem.get('name'),
                col_type,
                nullable=(col_elem.get('nullable') == 'true'),
                primary_key=(col_elem.get('primary_key') == 'true'),
                index=(col_elem.get('index') == 'true')
            )
            columns.append(column)

        # 创建表
        table = Table(table_name, columns, primary_key)
        table.next_id = next_id

        # 加载记录
        records_elem = table_elem.find('records')
        if records_elem is not None:
            for record_elem in records_elem.findall('record'):
                record = {}
                for field_elem in record_elem.findall('field'):
                    col_name = field_elem.get('name')
                    col_type_name = field_elem.get('type')

                    # 处理 NULL
                    if field_elem.get('null') == 'true':
                        value = None
                    else:
                        text = field_elem.text or ''

                        # 根据类型转换
                        if col_type_name == 'int':
                            value = int(text) if text else 0
                        elif col_type_name == 'float':
                            value = float(text) if text else 0.0
                        elif col_type_name == 'bool':
                            value = (text.lower() == 'true')
                        elif col_type_name == 'bytes':
                            if field_elem.get('encoding') == 'base64':
                                value = base64.b64decode(text)
                            else:
                                value = text.encode('utf-8')
                        else:  # str
                            value = text

                    record[col_name] = value

                pk = record[primary_key]
                table.data[pk] = record

        # 重建索引
        for col_name, column in table.columns.items():
            if column.index:
                if col_name in table.indexes:
                    del table.indexes[col_name]
                table.build_index(col_name)

        return table

    def get_metadata(self) -> Dict[str, Any]:
        """获取元数据"""
        if not self.exists():
            return {}

        try:
            file_size = os.path.getsize(self.file_path)
            modified_time = os.path.getmtime(self.file_path)

            from lxml import etree
            tree = etree.parse(self.file_path)
            root = tree.getroot()

            metadata = {
                'engine': 'xml',
                'file_size': file_size,
                'modified': modified_time,
                'version': root.get('version', 'unknown'),
                'timestamp': root.get('timestamp', 'unknown'),
                'table_count': len(root.findall('table'))
            }

            return metadata

        except:
            return {}
