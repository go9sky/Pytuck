"""
Pytuck XML存储引擎

使用结构化XML格式，适合企业集成和标准化数据交换
"""

import json
import base64
from pathlib import Path
from typing import Any, Dict, Union, TYPE_CHECKING, Tuple, Optional
from datetime import datetime
from .base import StorageBackend
from ..common.exceptions import SerializationError
from .versions import get_format_version

from ..common.options import XmlBackendOptions

if TYPE_CHECKING:
    from ..core.storage import Table
    from lxml import etree


class XMLBackend(StorageBackend):
    """XML format storage engine (requires lxml)"""

    ENGINE_NAME = 'xml'
    REQUIRED_DEPENDENCIES = ['lxml']
    FORMAT_VERSION = get_format_version('xml')

    def __init__(self, file_path: Union[str, Path], options: XmlBackendOptions):
        """
        初始化 XML 后端

        Args:
            file_path: XML 文件路径
            options: XML 后端配置选项
        """
        assert isinstance(options, XmlBackendOptions), "options must be an instance of XmlBackendOptions"
        super().__init__(file_path, options)
        # 类型安全：将 options 转为具体的 XmlBackendOptions 类型
        self.options: XmlBackendOptions = options

    def save(self, tables: Dict[str, 'Table']) -> None:
        """保存所有表数据到XML文件"""
        try:
            from lxml import etree
        except ImportError:
            raise SerializationError("lxml is required for XML backend. Install with: pip install pytuck[xml]")

        temp_path = self.file_path.parent / (self.file_path.name + '.tmp')
        try:
            # 创建根元素
            root = etree.Element(
                'database',
                format_version=str(self.FORMAT_VERSION),
                timestamp=datetime.now().isoformat()
            )

            # 为每个表创建 <table> 元素
            for table_name, table in tables.items():
                self._save_table_to_xml(root, table_name, table)

            # 写入文件（原子性）
            tree = etree.ElementTree(root)
            tree.write(
                str(temp_path),
                pretty_print=self.options.pretty_print,
                xml_declaration=True,
                encoding=self.options.encoding
            )

            if self.file_path.exists():
                self.file_path.unlink()
            temp_path.replace(self.file_path)

        except Exception as e:
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except FileNotFoundError:
                    pass
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
            tree = etree.parse(str(self.file_path))
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
        return self.file_path.exists()

    def delete(self) -> None:
        """删除文件"""
        if self.exists():
            self.file_path.unlink()

    def _save_table_to_xml(self, root: Any, table_name: str, table: 'Table') -> None:
        """保存单个表到XML"""
        from lxml import etree

        table_elem = etree.SubElement(root, 'table',
                                      name=table_name,
                                      primary_key=table.primary_key,
                                      next_id=str(table.next_id))

        # 表备注
        if table.comment:
            table_elem.set('comment', table.comment)

        # 列定义
        columns_elem = etree.SubElement(table_elem, 'columns')
        for col in table.columns.values():
            col_elem = etree.SubElement(
                columns_elem, 'column',
                name=col.name,
                type=col.col_type.__name__,
                nullable=str(col.nullable).lower(),
                primary_key=str(col.primary_key).lower(),
                index=str(col.index).lower()
            )
            if col.comment:
                col_elem.set('comment', col.comment)

        # 记录数据
        records_elem = etree.SubElement(table_elem, 'records')
        for record in table.data.values():
            record_elem = etree.SubElement(records_elem, 'record')
            for col_name, value in record.items():
                column = table.columns[col_name]
                field_elem = etree.SubElement(
                    record_elem, 'field', name=col_name, type=column.col_type.__name__
                )

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
        from ..core.storage import Table
        from ..core.orm import Column

        table_name = table_elem.get('name')
        primary_key = table_elem.get('primary_key')
        next_id = int(table_elem.get('next_id'))
        table_comment = table_elem.get('comment')

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
                index=(col_elem.get('index') == 'true'),
                comment=col_elem.get('comment')
            )
            columns.append(column)

        # 创建表
        table = Table(table_name, columns, primary_key, comment=table_comment)
        table.next_id = next_id

        # 加载记录
        records_elem = table_elem.find('records')
        if records_elem is not None:
            for record_elem in records_elem.findall('record'):
                record = {}
                for field_elem in record_elem.findall('field'):
                    col_name = field_elem.get('name')
                    col_type_name = field_elem.get('type')

                    value: Any
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
            file_stat = self.file_path.stat()
            file_size = file_stat.st_size
            modified_time = file_stat.st_mtime

            from lxml import etree
            tree = etree.parse(str(self.file_path))
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

    @classmethod
    def probe(cls, file_path: Union[str, Path]) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        轻量探测文件是否为 XML 引擎格式

        通过检查 XML 文件的根元素是否为 <database> 来识别。
        优先使用 lxml，回退到标准库的 xml.etree.ElementTree。

        实现策略：
        1. 读取前 8KB 内容进行快速字符串检查
        2. 如果通过初步检查，从文件直接解析完整 XML（不使用截断的内容）

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

            # 空文件不可能是有效的 XML
            if file_size == 0:
                return False, {'error': 'empty_file'}

            # 第一步：读取前 8KB 内容进行快速字符串检查
            with open(file_path, 'r', encoding='utf-8') as f:
                preview = f.read(8192)  # 8KB

            # 基本 XML 格式检查（快速排除非 XML 文件）
            if '<database' not in preview:
                return False, None

            # 第二步：确定可用的 XML 解析器
            xml_parser = None
            if cls.is_available():
                try:
                    from lxml import etree
                    xml_parser = 'lxml'
                except ImportError:
                    pass

            # 回退到标准库
            if xml_parser is None:
                try:
                    import xml.etree.ElementTree as ET
                    xml_parser = 'stdlib'
                except ImportError:
                    return False, {'error': 'no_xml_parser_available'}

            # 第三步：从文件直接解析完整 XML（不使用截断的 preview）
            try:
                if xml_parser == 'lxml':
                    from lxml import etree
                    tree = etree.parse(str(file_path))
                    root = tree.getroot()
                else:
                    import xml.etree.ElementTree as ET
                    tree = ET.parse(str(file_path))
                    root = tree.getroot()

                # 检查根元素
                if root.tag != 'database':
                    return False, None

                # 获取元数据信息
                format_version = root.get('format_version')
                timestamp = root.get('timestamp')
                table_count = len(root.findall('table'))

                # 成功识别为 XML 格式
                return True, {
                    'engine': 'xml',
                    'format_version': format_version,
                    'table_count': table_count,
                    'file_size': file_size,
                    'modified': file_stat.st_mtime,
                    'timestamp': timestamp,
                    'xml_parser': xml_parser,
                    'confidence': 'high' if cls.is_available() else 'medium'
                }

            except Exception as parse_error:
                # XML 解析失败
                return False, {'error': f'xml_parse_error: {str(parse_error)}'}

        except UnicodeDecodeError:
            return False, {'error': 'not_utf8_xml'}
        except Exception as e:
            return False, {'error': f'probe_exception: {str(e)}'}
