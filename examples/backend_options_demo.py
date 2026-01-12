"""
Pytuck - 后端配置选项演示

演示如何使用强类型的后端配置选项来配置不同的存储引擎。
这是 Pytuck 0.2.0 版本的新特性，使用 dataclass 替代了 **kwargs 参数。
"""

import os
import sys
import tempfile
from typing import Type

# 添加父目录到路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from examples.common import get_project_temp_dir

from pytuck import Storage, declarative_base, Session, Column, PureBaseModel
from pytuck import select, insert
from pytuck.common.options import (
    JsonBackendOptions,
    CsvBackendOptions,
    SqliteBackendOptions,
    ExcelBackendOptions,
    XmlBackendOptions,
    BinaryBackendOptions
)


def demo_json_options():
    """演示 JSON 引擎配置选项"""
    print("\n" + "="*50)
    print("JSON 引擎配置选项演示")
    print("="*50)

    # 创建临时文件
    temp_dir = get_project_temp_dir()
    json_file = temp_dir / 'demo_json_options.json'

    # 清理旧文件
    try:
        json_file.unlink()
    except FileNotFoundError:
        pass

    # 配置 JSON 选项：自定义缩进和字符编码
    json_opts = JsonBackendOptions(
        indent=4,           # 使用 4 个空格缩进
        ensure_ascii=False  # 允许非 ASCII 字符（支持中文等）
    )

    # 创建数据库
    db = Storage(file_path=json_file, engine='json', backend_options=json_opts)
    Base: Type[PureBaseModel] = declarative_base(db)

    class User(Base):
        __tablename__ = 'users'
        id = Column('id', int, primary_key=True)
        name = Column('name', str)
        description = Column('description', str)

    session = Session(db)

    # 插入包含中文的数据
    stmt = insert(User).values(name='张三', description='这是一个中文描述')
    session.execute(stmt)
    session.commit()

    # 检查使用的JSON实现
    backend = db.backend
    print(f"✓ JSON文件已创建: {json_file}")
    print(f"✓ 使用的JSON实现: {backend._impl_name}")
    print("配置选项:")
    print(f"  indent: {json_opts.indent}")
    print(f"  ensure_ascii: {json_opts.ensure_ascii}")
    print(f"  impl: {json_opts.impl} (默认使用标准库)")

    db.close()

    # 显示文件内容
    print("\n文件内容预览:")
    with open(json_file, 'r', encoding='utf-8') as f:
        content = f.read()
        lines = content.split('\n')[:10]  # 只显示前10行
        for line in lines:
            print(f"  {line}")

    # 清理
    os.remove(json_file)

    # 演示使用orjson（如果安装了）
    print("\n" + "-"*40)
    print("JSON 高性能实现演示")
    print("-"*40)

    try:
        import orjson
        print("✓ 检测到 orjson，演示高性能JSON序列化")

        orjson_file = os.path.join(temp_dir, 'demo_orjson.json')
        if os.path.exists(orjson_file):
            os.remove(orjson_file)

        # 使用 orjson
        json_orjson_opts = JsonBackendOptions(
            impl='orjson',       # 指定使用orjson
            indent=4,           # indent参数会被舍弃，但不影响功能
            ensure_ascii=False  # ensure_ascii参数会被舍弃
        )

        db_orjson = Storage(file_path=orjson_file, engine='json', backend_options=json_orjson_opts)
        Base_orjson: Type[PureBaseModel] = declarative_base(db_orjson)

        class FastUser(Base_orjson):
            __tablename__ = 'fast_users'
            id = Column('id', int, primary_key=True)
            name = Column('name', str)
            data = Column('data', str)

        session_orjson = Session(db_orjson)

        # 插入数据
        stmt = insert(FastUser).values(name='高速用户', data='大量数据' * 100)
        session_orjson.execute(stmt)
        session_orjson.commit()

        backend_orjson = db_orjson.backend
        print(f"✓ orjson文件已创建: {orjson_file}")
        print(f"✓ 使用的JSON实现: {backend_orjson._impl_name}")
        print("✓ orjson特点: 比标准json快2-3倍，indent/ensure_ascii参数被自动舍弃")

        session_orjson.close()
        db_orjson.close()
        os.remove(orjson_file)

    except ImportError:
        print("- orjson 未安装，跳过高性能JSON演示")
        print("  安装方法: pip install pytuck[orjson]")

    # 演示自定义JSON实现
    print("\n" + "-"*40)
    print("自定义JSON实现演示")
    print("-"*40)

    # 先导入后端以便覆盖方法
    from pytuck.backends.json_backend import JSONBackend

    def setup_custom_rapidjson(self, impl):
        """模拟rapidjson自定义实现"""
        # 实际场景中，这里会 import rapidjson
        # 为了演示，我们使用标准库json模拟
        import json

        def dumps_func(obj):
            return json.dumps(obj, indent=self.options.indent, separators=(',', ': '))

        self._dumps_func = dumps_func
        self._loads_func = json.loads
        self._impl_name = f'custom_{impl}'

    # 覆盖方法
    original_setup_custom = JSONBackend._setup_custom_json
    JSONBackend._setup_custom_json = setup_custom_rapidjson

    try:
        custom_file = os.path.join(temp_dir, 'demo_custom_json.json')
        if os.path.exists(custom_file):
            os.remove(custom_file)

        # 使用自定义JSON实现
        json_custom_opts = JsonBackendOptions(
            impl='rapidjson',    # 指定自定义实现名称
            indent=2
        )

        db_custom = Storage(file_path=custom_file, engine='json', backend_options=json_custom_opts)
        Base_custom: Type[PureBaseModel] = declarative_base(db_custom)

        class CustomUser(Base_custom):
            __tablename__ = 'custom_users'
            id = Column('id', int, primary_key=True)
            name = Column('name', str)

        session_custom = Session(db_custom)

        # 插入数据
        stmt = insert(CustomUser).values(name='自定义用户')
        session_custom.execute(stmt)
        session_custom.commit()

        backend_custom = db_custom.backend
        print(f"✓ 自定义JSON文件已创建: {custom_file}")
        print(f"✓ 使用的JSON实现: {backend_custom._impl_name}")
        print("✓ 自定义实现方法: JSONBackend._setup_custom_json = your_custom_function")

        # 查询数据验证
        users = session_custom.execute(select(CustomUser)).all()
        for user in users:  # 直接迭代模型实例
            print(f"  查询到用户: id={user.id}, name={user.name}")
        print(f'✓ 自定义实现查询成功，数据正确')

        session_custom.close()
        db_custom.close()
        os.remove(custom_file)

    except Exception as e:
        print(f"❌ 自定义实现演示失败: {e}")
    finally:
        # 恢复原始方法
        JSONBackend._setup_custom_json = original_setup_custom


def demo_csv_options():
    """演示 CSV 引擎配置选项"""
    print("\n" + "="*50)
    print("CSV 引擎配置选项演示")
    print("="*50)

    # 创建临时文件
    temp_dir = tempfile.gettempdir()
    csv_file = os.path.join(temp_dir, 'demo_csv_options.zip')

    # 清理旧文件
    if os.path.exists(csv_file):
        os.remove(csv_file)

    # 配置 CSV 选项：使用 GBK 编码和分号分隔符
    csv_opts = CsvBackendOptions(
        encoding='gbk',     # 使用 GBK 编码（适用于中文 Excel）
        delimiter=';'       # 使用分号作为分隔符
    )

    # 创建数据库
    db = Storage(file_path=csv_file, engine='csv', backend_options=csv_opts)
    Base: Type[PureBaseModel] = declarative_base(db)

    class Product(Base):
        __tablename__ = 'products'
        id = Column('id', int, primary_key=True)
        name = Column('name', str)
        price = Column('price', float)

    session = Session(db)

    # 插入数据
    products = [
        {'name': '苹果', 'price': 5.99},
        {'name': '香蕉', 'price': 3.99},
        {'name': '橙子', 'price': 4.99}
    ]

    for product_data in products:
        stmt = insert(Product).values(**product_data)
        session.execute(stmt)

    session.commit()
    db.close()

    print(f"✓ CSV 文件已创建: {csv_file}")
    print("配置选项:")
    print(f"  encoding: {csv_opts.encoding}")
    print(f"  delimiter: '{csv_opts.delimiter}'")

    # 清理
    os.remove(csv_file)


def demo_sqlite_options():
    """演示 SQLite 引擎配置选项"""
    print("\n" + "="*50)
    print("SQLite 引擎配置选项演示")
    print("="*50)

    # 创建临时文件
    temp_dir = tempfile.gettempdir()
    sqlite_file = os.path.join(temp_dir, 'demo_sqlite_options.sqlite')

    # 清理旧文件
    if os.path.exists(sqlite_file):
        os.remove(sqlite_file)

    # 配置 SQLite 选项
    sqlite_opts = SqliteBackendOptions(
        check_same_thread=False,    # 允许多线程访问
        timeout=30.0                # 设置超时时间为 30 秒
    )

    # 创建数据库
    db = Storage(file_path=sqlite_file, engine='sqlite', backend_options=sqlite_opts)
    Base: Type[PureBaseModel] = declarative_base(db)

    class Log(Base):
        __tablename__ = 'logs'
        id = Column('id', int, primary_key=True)
        message = Column('message', str)
        level = Column('level', str)

    session = Session(db)

    # 插入数据
    logs = [
        {'message': '应用程序启动', 'level': 'INFO'},
        {'message': '用户登录成功', 'level': 'INFO'},
        {'message': '数据库连接失败', 'level': 'ERROR'}
    ]

    for log_data in logs:
        stmt = insert(Log).values(**log_data)
        session.execute(stmt)

    session.commit()
    db.close()

    print(f"✓ SQLite 文件已创建: {sqlite_file}")
    print("配置选项:")
    print(f"  check_same_thread: {sqlite_opts.check_same_thread}")
    print(f"  timeout: {sqlite_opts.timeout}")

    # 清理
    os.remove(sqlite_file)


def demo_binary_default():
    """演示 Binary 引擎（默认选项）"""
    print("\n" + "="*50)
    print("Binary 引擎演示（默认选项）")
    print("="*50)

    # 创建临时文件
    temp_dir = tempfile.gettempdir()
    binary_file = os.path.join(temp_dir, 'demo_binary_default.db')

    # 清理旧文件
    if os.path.exists(binary_file):
        os.remove(binary_file)

    # Binary 引擎目前没有配置选项，使用默认
    binary_opts = BinaryBackendOptions()

    # 创建数据库
    db = Storage(file_path=binary_file, engine='binary', backend_options=binary_opts)
    Base: Type[PureBaseModel] = declarative_base(db)

    class Settings(Base):
        __tablename__ = 'settings'
        id = Column('id', int, primary_key=True)
        key = Column('key', str)
        value = Column('value', str)

    session = Session(db)

    # 插入数据
    settings = [
        {'key': 'theme', 'value': 'dark'},
        {'key': 'language', 'value': 'zh-CN'},
        {'key': 'auto_save', 'value': 'true'}
    ]

    for setting_data in settings:
        stmt = insert(Settings).values(**setting_data)
        session.execute(stmt)

    session.commit()
    db.close()

    print(f"✓ Binary 文件已创建: {binary_file}")
    print("配置选项: 无（使用默认设置）")

    # 显示文件大小
    file_size = os.path.getsize(binary_file)
    print(f"文件大小: {file_size} bytes")

    # 清理
    os.remove(binary_file)


def demo_without_options():
    """演示不显式指定选项（使用默认值）"""
    print("\n" + "="*50)
    print("使用默认选项演示")
    print("="*50)

    # 创建临时文件
    temp_dir = tempfile.gettempdir()
    default_file = os.path.join(temp_dir, 'demo_default.json')

    # 清理旧文件
    if os.path.exists(default_file):
        os.remove(default_file)

    # 不指定 backend_options，系统会自动使用默认选项
    db = Storage(file_path=default_file, engine='json')  # 不传 backend_options
    Base: Type[PureBaseModel] = declarative_base(db)

    class Item(Base):
        __tablename__ = 'items'
        id = Column('id', int, primary_key=True)
        name = Column('name', str)

    session = Session(db)

    # 插入数据
    stmt = insert(Item).values(name='测试项目')
    session.execute(stmt)
    session.commit()
    db.close()

    print(f"✓ 使用默认选项创建文件: {default_file}")
    print("默认 JSON 选项:")
    default_opts = JsonBackendOptions()  # 获取默认值
    print(f"  indent: {default_opts.indent}")
    print(f"  ensure_ascii: {default_opts.ensure_ascii}")

    # 清理
    os.remove(default_file)


def main():
    """主演示函数"""
    print("=" * 60)
    print("Pytuck - 后端配置选项演示")
    print("=" * 60)
    print("演示如何使用强类型配置选项代替 **kwargs 参数")

    # 演示各种配置选项
    demo_json_options()
    demo_csv_options()
    demo_sqlite_options()
    demo_binary_default()
    demo_without_options()

    print("\n" + "="*60)
    print("演示完成")
    print("="*60)
    print("\n主要特性:")
    print("✓ 强类型配置选项，IDE 自动补全支持")
    print("✓ 编译时类型检查，减少运行时错误")
    print("✓ 清晰的配置接口，易于理解和维护")
    print("✓ 向后兼容，不指定选项时自动使用默认值")
    print("✓ JSON引擎支持多种实现（orjson、ujson等）")

    print("\n旧 API (不再支持):")
    print("❌ Storage('file.json', engine='json', indent=4)  # 错误")
    print("\n新 API (推荐):")
    print("✅ opts = JsonBackendOptions(indent=4)")
    print("✅ Storage('file.json', engine='json', backend_options=opts)")
    print("\nJSON高性能实现:")
    print("✅ opts = JsonBackendOptions(impl='orjson')  # 2-3倍性能提升")
    print("✅ opts = JsonBackendOptions(impl='ujson')   # 1.5-2倍性能提升")
    print("✅ 自定义实现: JSONBackend._setup_custom_json = your_function")


if __name__ == '__main__':
    # main()
    demo_json_options()