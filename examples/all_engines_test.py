"""
Pytuck - 所有存储引擎综合测试

测试所有6种存储引擎的功能：
- binary: 二进制引擎（默认）
- json: JSON引擎
- csv: CSV引擎（ZIP压缩）
- sqlite: SQLite引擎
- excel: Excel引擎（需要 openpyxl）
- xml: XML引擎（需要 lxml）
"""

import os
import sys
from datetime import datetime

# 添加父目录到路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from examples.common import get_project_temp_dir

from pytuck import Storage, declarative_base, Session, Column
from pytuck import select, insert, update, delete
from pytuck.backends import BackendRegistry, print_available_engines


def test_engine(engine_name: str, file_ext: str) -> bool:
    """
    测试单个存储引擎

    Args:
        engine_name: 引擎名称
        file_ext: 文件扩展名

    Returns:
        测试是否成功
    """
    print(f"\n{'='*60}")
    print(f"测试引擎: {engine_name.upper()}")
    print(f"{'='*60}")

    # 检查引擎是否可用
    backend_class = BackendRegistry.get(engine_name)
    if not backend_class or not backend_class.is_available():
        print(f"❌ 引擎 '{engine_name}' 不可用，跳过测试")
        if backend_class and backend_class.REQUIRED_DEPENDENCIES:
            deps = ', '.join(backend_class.REQUIRED_DEPENDENCIES)
            print(f"   需要安装: pip install pytuck[{engine_name}]")
            print(f"   依赖: {deps}")
        return False

    # 创建临时文件
    temp_dir = get_project_temp_dir()
    db_file = os.path.join(temp_dir, f'test_{engine_name}.{file_ext}')

    try:
        # 清理旧文件
        if os.path.exists(db_file):
            os.remove(db_file)

        print(f"\n1️⃣  创建数据库: {db_file}")
        db = Storage(file_path=db_file, engine=engine_name)
        Base = declarative_base(db)

        # 定义模型
        class Student(Base):
            __tablename__ = 'students'

            id = Column('id', int, primary_key=True)
            name = Column('name', str, nullable=False, index=True)
            age = Column('age', int)
            email = Column('email', str, nullable=True)
            active = Column('active', bool)
            avatar = Column('avatar', bytes, nullable=True)

        session = Session(db)
        print("✓ 数据库创建成功")

        # 插入测试数据
        print("\n2️⃣  插入测试数据")
        test_data = [
            {'name': 'Alice', 'age': 20, 'email': 'alice@example.com', 'active': True, 'avatar': b'avatar_alice'},
            {'name': 'Bob', 'age': 22, 'email': 'bob@example.com', 'active': False, 'avatar': b'avatar_bob'},
            {'name': 'Charlie', 'age': 19, 'email': None, 'active': True, 'avatar': None},
            {'name': 'David', 'age': 21, 'email': 'david@example.com', 'active': True, 'avatar': b'avatar_david'},
            {'name': 'Eve', 'age': 23, 'email': 'eve@example.com', 'active': False, 'avatar': b'avatar_eve'},
        ]

        for data in test_data:
            stmt = insert(Student).values(**data)
            result = session.execute(stmt)
            print(f"   ✓ 创建: {data['name']} (ID: {result.inserted_primary_key})")

        session.commit()

        # 查询测试
        print("\n3️⃣  查询测试")

        # 按ID查询
        stmt = select(Student).where(Student.id == 1)
        result = session.execute(stmt)
        alice = result.scalars().first()
        print(f"   ✓ get(1): {alice.name}, {alice.age}岁, active={alice.active}")
        assert alice.name == 'Alice'
        assert alice.age == 20
        assert alice.active == True
        assert alice.avatar == b'avatar_alice'

        # 索引查询
        stmt = select(Student).filter_by(name='Bob')
        result = session.execute(stmt)
        bob = result.scalars().first()
        print(f"   ✓ filter_by(name='Bob'): {bob.name}, email={bob.email}, active={bob.active}")
        assert bob.email == 'bob@example.com'
        assert bob.active == False

        # 多条件查询（等值）
        stmt = select(Student).filter_by(active=True)
        result = session.execute(stmt)
        active_students = result.scalars().all()
        print(f"   ✓ filter_by(active=True): 找到 {len(active_students)} 条记录")
        assert len(active_students) == 3  # Alice, Charlie, David

        # 排序查询
        stmt = select(Student).order_by('age')
        result = session.execute(stmt)
        sorted_students = result.scalars().all()
        print(f"   ✓ order_by('age'): {sorted_students[0].name}(最年轻) -> {sorted_students[-1].name}(最年长)")
        assert sorted_students[0].name == 'Charlie'
        assert sorted_students[-1].name == 'Eve'

        # 统计
        stmt = select(Student).filter_by(active=True)
        result = session.execute(stmt)
        count = len(result.scalars().all())
        print(f"   ✓ count(active=True): {count} 条记录")
        assert count == 3

        # 更新测试
        print("\n4️⃣  更新测试")
        stmt = update(Student).where(Student.id == 1).values(age=21, email='alice.new@example.com')
        result = session.execute(stmt)
        session.commit()
        print(f"   ✓ 更新 Alice: age=21, email=alice.new@example.com")

        # 验证更新
        stmt = select(Student).where(Student.id == 1)
        result = session.execute(stmt)
        alice_reloaded = result.scalars().first()
        assert alice_reloaded.age == 21
        assert alice_reloaded.email == 'alice.new@example.com'
        print(f"   ✓ 验证更新成功")

        # 删除测试
        print("\n5️⃣  删除测试")
        stmt = delete(Student).where(Student.name == 'Charlie')
        result = session.execute(stmt)
        session.commit()
        print(f"   ✓ 删除 Charlie")

        # 验证删除
        stmt = select(Student)
        result = session.execute(stmt)
        remaining = len(result.scalars().all())
        print(f"   ✓ 剩余记录: {remaining} 条")
        assert remaining == 4

        # 持久化测试
        print("\n6️⃣  持久化测试")
        print(f"   保存数据到磁盘...")
        session.close()
        db.close()
        print(f"   ✓ 数据已保存")

        # 检查文件大小
        if os.path.exists(db_file):
            file_size = os.path.getsize(db_file)
            print(f"   文件大小: {file_size / 1024:.2f} KB")

        # 重新加载测试
        print("\n7️⃣  重新加载测试")
        db2 = Storage(file_path=db_file, engine=engine_name)
        Base2 = declarative_base(db2)

        class Student2(Base2):
            __tablename__ = 'students'

            id = Column('id', int, primary_key=True)
            name = Column('name', str, nullable=False, index=True)
            age = Column('age', int)
            email = Column('email', str, nullable=True)
            active = Column('active', bool)
            avatar = Column('avatar', bytes, nullable=True)

        session2 = Session(db2)

        # 验证数据
        stmt = select(Student2)
        result = session2.execute(stmt)
        all_students = result.scalars().all()
        print(f"   ✓ 加载到 {len(all_students)} 条记录")
        assert len(all_students) == 4

        # 验证具体数据
        stmt = select(Student2).where(Student2.id == 1)
        result = session2.execute(stmt)
        alice2 = result.scalars().first()
        print(f"   ✓ 验证 Alice: age={alice2.age}, email={alice2.email}, active={alice2.active}")
        assert alice2.age == 21
        assert alice2.email == 'alice.new@example.com'
        assert alice2.active == True
        assert alice2.avatar == b'avatar_alice'

        # 验证 bytes 和 None
        stmt = select(Student2).where(Student2.id == 2)
        result = session2.execute(stmt)
        bob2 = result.scalars().first()
        print(f"   ✓ 验证 Bob: avatar={bob2.avatar[:12]}..., active={bob2.active}")
        assert bob2.avatar == b'avatar_bob'
        assert bob2.active == False

        # 验证 NULL 值（Charlie已被删除，检查其他有NULL的记录）
        stmt = select(Student2).filter_by(email=None)
        result = session2.execute(stmt)
        students_with_null_email = result.scalars().all()
        print(f"   ✓ NULL 值处理: 找到 {len(students_with_null_email)} 条无邮箱记录")

        stmt = select(Student2).filter_by(avatar=None)
        result = session2.execute(stmt)
        students_with_null_avatar = result.scalars().all()
        print(f"   ✓ NULL bytes 处理: 找到 {len(students_with_null_avatar)} 条无头像记录")

        # 索引查询验证
        stmt = select(Student2).filter_by(name='David')
        result = session2.execute(stmt)
        david = result.scalars().first()
        print(f"   ✓ 索引查询: {david.name}, age={david.age}")
        assert david.name == 'David'
        assert david.age == 21

        session2.close()
        db2.close()

        # 清理
        print("\n8️⃣  清理测试文件")
        if os.path.exists(db_file):
            os.remove(db_file)
            print(f"   ✓ 已删除: {db_file}")

        print(f"\n✅ 引擎 '{engine_name}' 测试通过！")
        return True

    except Exception as e:
        print(f"\n❌ 引擎 '{engine_name}' 测试失败: {e}")
        import traceback
        traceback.print_exc()

        # 清理
        if os.path.exists(db_file):
            try:
                os.remove(db_file)
            except:
                pass

        return False


def main():
    """主测试函数"""
    print("=" * 60)
    print("Pytuck - 所有存储引擎综合测试")
    print("=" * 60)
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 打印可用引擎
    print("\n可用引擎列表:")
    print("-" * 60)
    print_available_engines()

    # 测试所有引擎
    engines_to_test = [
        ('binary', 'db'),
        ('json', 'json'),
        ('csv', 'zip'),
        ('sqlite', 'sqlite'),
        ('excel', 'xlsx'),
        ('xml', 'xml'),
    ]

    results = {}
    for engine_name, file_ext in engines_to_test:
        success = test_engine(engine_name, file_ext)
        results[engine_name] = success

    # 总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)

    for engine_name, success in results.items():
        status = "✅ 通过" if success else "❌ 失败/跳过"
        print(f"  {engine_name:10} : {status}")

    passed = sum(1 for s in results.values() if s)
    total = len(results)
    print(f"\n通过率: {passed}/{total} ({passed*100//total}%)")

    if passed == total:
        print("\n🎉 所有测试通过！")
    else:
        print(f"\n⚠️  有 {total - passed} 个引擎测试失败或跳过")


if __name__ == '__main__':
    main()
