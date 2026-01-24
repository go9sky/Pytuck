"""
Pytuck - 数据迁移工具演示

演示如何使用 Pytuck 的数据迁移工具，包括：
1. 在不同存储引擎间迁移数据 (migrate_engine)
2. 从外部数据库导入数据 (import_from_database)

使用新的强类型配置选项系统。
"""

import os
import sys
import sqlite3
from typing import Type

# 添加父目录到路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from examples._common import get_project_temp_dir

from pytuck import Storage, declarative_base, Session, Column, PureBaseModel
from pytuck import select, insert
from pytuck.tools.migrate import migrate_engine, import_from_database
from pytuck.common.options import (
    JsonBackendOptions,
    CsvBackendOptions,
    SqliteConnectorOptions
)


def create_sample_database():
    """创建示例 Pytuck 数据库"""
    temp_dir = get_project_temp_dir()
    source_file = os.path.join(temp_dir, 'source_data.db')

    # 清理旧文件
    if os.path.exists(source_file):
        os.remove(source_file)

    # 创建源数据库（使用 binary 引擎）
    db = Storage(file_path=source_file, engine='binary')
    Base: Type[PureBaseModel] = declarative_base(db)

    class Employee(Base):
        __tablename__ = 'employees'
        id = Column('id', int, primary_key=True)
        name = Column('name', str, nullable=False)
        department = Column('department', str)
        salary = Column('salary', float)
        active = Column('active', bool)

    class Department(Base):
        __tablename__ = 'departments'
        id = Column('id', int, primary_key=True)
        name = Column('name', str, nullable=False)
        budget = Column('budget', float)

    session = Session(db)

    # 插入部门数据
    departments = [
        {'name': '技术部', 'budget': 1000000.0},
        {'name': '销售部', 'budget': 800000.0},
        {'name': '人事部', 'budget': 500000.0}
    ]

    for dept_data in departments:
        stmt = insert(Department).values(**dept_data)
        session.execute(stmt)

    # 插入员工数据
    employees = [
        {'name': '张三', 'department': '技术部', 'salary': 8000.0, 'active': True},
        {'name': '李四', 'department': '技术部', 'salary': 9500.0, 'active': True},
        {'name': '王五', 'department': '销售部', 'salary': 7500.0, 'active': True},
        {'name': '赵六', 'department': '销售部', 'salary': 8500.0, 'active': False},
        {'name': '钱七', 'department': '人事部', 'salary': 6500.0, 'active': True}
    ]

    for emp_data in employees:
        stmt = insert(Employee).values(**emp_data)
        session.execute(stmt)

    session.commit()
    db.close()

    print(f"✓ 创建示例数据库: {source_file}")
    return source_file


def demo_engine_migration():
    """演示引擎间数据迁移"""
    print("\n" + "="*50)
    print("引擎间数据迁移演示")
    print("="*50)

    temp_dir = get_project_temp_dir()

    # 创建源数据库
    source_file = create_sample_database()

    # 目标文件
    json_target = os.path.join(temp_dir, 'migrated_data.json')
    csv_target = os.path.join(temp_dir, 'migrated_data.zip')

    # 清理旧文件
    for file in [json_target, csv_target]:
        if os.path.exists(file):
            os.remove(file)

    print(f"\n1️⃣  从 Binary 迁移到 JSON")

    # 配置 JSON 选项：美化输出，支持中文
    json_opts = JsonBackendOptions(
        indent=2,
        ensure_ascii=False
    )

    # 执行迁移
    result = migrate_engine(
        source_path=source_file,
        source_engine='binary',
        target_path=json_target,
        target_engine='json',
        overwrite=True,
        target_options=json_opts  # 使用自定义 JSON 选项
    )

    print(f"✓ 迁移完成:")
    print(f"  源文件: {result['source_path']}")
    print(f"  目标文件: {result['target_path']}")
    print(f"  表数量: {result['tables']}")
    print(f"  记录数量: {result['records']}")

    print(f"\n2️⃣  从 JSON 迁移到 CSV")

    # 配置 CSV 选项：使用 UTF-8 编码和逗号分隔符
    csv_opts = CsvBackendOptions(
        encoding='utf-8',
        delimiter=','
    )

    # 执行迁移
    result = migrate_engine(
        source_path=json_target,
        source_engine='json',
        target_path=csv_target,
        target_engine='csv',
        overwrite=True,
        source_options=json_opts,  # 源文件选项
        target_options=csv_opts    # 目标文件选项
    )

    print(f"✓ 迁移完成:")
    print(f"  源引擎: {result['source_engine']}")
    print(f"  目标引擎: {result['target_engine']}")
    print(f"  表数量: {result['tables']}")
    print(f"  记录数量: {result['records']}")

    # 清理
    for file in [source_file, json_target, csv_target]:
        if os.path.exists(file):
            os.remove(file)


def create_external_sqlite_database():
    """创建外部 SQLite 数据库（非 Pytuck 格式）"""
    temp_dir = get_project_temp_dir()
    external_db = os.path.join(temp_dir, 'external_company.db')

    # 清理旧文件
    if os.path.exists(external_db):
        os.remove(external_db)

    # 创建普通的 SQLite 数据库
    conn = sqlite3.connect(external_db)
    cursor = conn.cursor()

    # 创建表结构
    cursor.execute('''
        CREATE TABLE users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            email TEXT,
            age INTEGER,
            is_active INTEGER DEFAULT 1,
            created_at TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE projects (
            project_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            budget REAL,
            status TEXT DEFAULT 'active'
        )
    ''')

    cursor.execute('''
        CREATE TABLE user_projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            project_id INTEGER,
            role TEXT,
            FOREIGN KEY (user_id) REFERENCES users(user_id),
            FOREIGN KEY (project_id) REFERENCES projects(project_id)
        )
    ''')

    # 插入示例数据
    users_data = [
        ('alice_wang', 'alice@company.com', 28, 1, '2024-01-15'),
        ('bob_li', 'bob@company.com', 32, 1, '2024-01-16'),
        ('charlie_zhang', 'charlie@company.com', 25, 0, '2024-01-17'),
        ('diana_chen', 'diana@company.com', 30, 1, '2024-01-18')
    ]

    cursor.executemany('''
        INSERT INTO users (username, email, age, is_active, created_at)
        VALUES (?, ?, ?, ?, ?)
    ''', users_data)

    projects_data = [
        ('网站重构项目', '重构公司官网的前端和后端', 150000.0, 'active'),
        ('移动应用开发', '开发公司移动端 App', 200000.0, 'active'),
        ('数据分析平台', '构建企业内部数据分析平台', 300000.0, 'planning')
    ]

    cursor.executemany('''
        INSERT INTO projects (name, description, budget, status)
        VALUES (?, ?, ?, ?)
    ''', projects_data)

    user_projects_data = [
        (1, 1, 'lead'),
        (2, 1, 'developer'),
        (1, 2, 'consultant'),
        (4, 2, 'lead'),
        (2, 3, 'analyst')
    ]

    cursor.executemany('''
        INSERT INTO user_projects (user_id, project_id, role)
        VALUES (?, ?, ?)
    ''', user_projects_data)

    conn.commit()
    conn.close()

    print(f"✓ 创建外部 SQLite 数据库: {external_db}")
    return external_db


def demo_database_import():
    """演示从外部数据库导入数据"""
    print("\n" + "="*50)
    print("从外部数据库导入数据演示")
    print("="*50)

    temp_dir = get_project_temp_dir()

    # 创建外部 SQLite 数据库
    external_db = create_external_sqlite_database()

    # 目标文件
    pytuck_target = os.path.join(temp_dir, 'imported_company_data.json')

    # 清理旧文件
    if os.path.exists(pytuck_target):
        os.remove(pytuck_target)

    print(f"\n1️⃣  从外部 SQLite 导入到 Pytuck JSON")

    # 配置连接器选项
    source_opts = SqliteConnectorOptions(
        check_same_thread=False,  # 允许多线程
        timeout=10.0              # 10秒超时
    )

    # 配置目标选项
    target_opts = JsonBackendOptions(
        indent=2,
        ensure_ascii=False
    )

    # 执行导入
    result = import_from_database(
        source_path=external_db,
        target_path=pytuck_target,
        target_engine='json',
        source_options=source_opts,
        target_options=target_opts,
        primary_key_map={
            'users': 'user_id',
            'projects': 'project_id'
        },
        overwrite=True
    )

    print(f"✓ 导入完成:")
    print(f"  源数据库: {result['source_path']}")
    print(f"  目标文件: {result['target_path']}")
    print(f"  导入表数: {result['tables']}")
    print(f"  导入记录数: {result['records']}")

    # 显示表详情
    print(f"\n表详情:")
    for table_name, details in result['table_details'].items():
        print(f"  {table_name}:")
        print(f"    记录数: {details['records']}")
        print(f"    列: {', '.join(details['columns'])}")
        print(f"    主键: {details['primary_key']}")
        if details.get('auto_rowid'):
            print(f"    自动生成行ID: 是")

    print(f"\n2️⃣  验证导入的数据")

    # 验证导入的数据
    db = Storage(file_path=pytuck_target, engine='json')
    Base: Type[PureBaseModel] = declarative_base(db)

    class ImportedUser(Base):
        __tablename__ = 'users'
        user_id = Column('user_id', int, primary_key=True)
        username = Column('username', str)
        email = Column('email', str)
        age = Column('age', int)
        is_active = Column('is_active', bool)
        created_at = Column('created_at', str)

    class ImportedProject(Base):
        __tablename__ = 'projects'
        project_id = Column('project_id', int, primary_key=True)
        name = Column('name', str)
        description = Column('description', str)
        budget = Column('budget', float)
        status = Column('status', str)

    session = Session(db)

    # 查询用户
    stmt = select(ImportedUser).where(ImportedUser.is_active == True)
    result = session.execute(stmt)
    active_users = result.all()
    print(f"  活跃用户: {len(active_users)} 个")

    # 查询项目
    stmt = select(ImportedProject).where(ImportedProject.budget > 150000)
    result = session.execute(stmt)
    expensive_projects = result.all()
    print(f"  高预算项目 (>15万): {len(expensive_projects)} 个")

    for project in expensive_projects:
        print(f"    - {project.name}: {project.budget:,.0f} 元")

    db.close()

    # 清理
    for file in [external_db, pytuck_target]:
        if os.path.exists(file):
            os.remove(file)


def main():
    """主演示函数"""
    print("=" * 60)
    print("Pytuck - 数据迁移工具演示")
    print("=" * 60)
    print("演示新的强类型配置选项系统")

    try:
        # 演示迁移功能
        demo_engine_migration()

        # 演示导入功能
        demo_database_import()

        print("\n" + "="*60)
        print("演示完成")
        print("="*60)
        print("\n主要特性:")
        print("✓ migrate_engine: 在 Pytuck 存储引擎间迁移数据")
        print("✓ import_from_database: 从外部数据库导入数据")
        print("✓ 强类型配置选项，IDE 自动补全支持")
        print("✓ 灵活的主键映射和表过滤选项")

        print("\n新 API 对比:")
        print("旧方式 (字典选项):")
        print("❌ migrate_engine(..., target_options={'indent': 2})")
        print("\n新方式 (强类型选项):")
        print("✅ opts = JsonBackendOptions(indent=2)")
        print("✅ migrate_engine(..., target_options=opts)")

    except Exception as e:
        print(f"\n❌ 演示过程中出错: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()