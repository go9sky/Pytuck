# 更新日志

本文件记录项目的所有重要变更。格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，遵循 [语义化版本](https://semver.org/lang/zh-CN/) 规范。

> [English Version](./CHANGELOG.EN.md)

> 历史版本请查看：[docs/changelog/](./docs/changelog/)

---

## [0.6.2] - 2026-02-01

### 新增

- **Storage.count_rows() 方法**
  - 新增获取表记录数的公共接口
  - 支持 Native SQL 模式和内存模式
  - 表不存在时抛出 `TableNotFoundError`
  - 示例：
    ```python
    count = storage.count_rows('users')
    print(f"users 表有 {count} 条记录")
    ```

- **主键类型自动转换**
  - 在 `Table` 类中添加 `_normalize_pk` 方法
  - `insert`、`update`、`delete`、`get` 方法自动转换主键类型
  - 解决传入字符串主键 `'1'` 与整数主键 `1` 不匹配的问题

### 修复

- **主键重复检测失败**
  - 修复内存模式下主键类型不匹配导致重复检测失败的问题
  - 表定义 `int` 主键，传入 `'1'`（字符串）现在能正确检测到与 `1`（整数）重复

- **主键重复异常统一**
  - Native SQL 模式下插入重复主键现在抛出 `DuplicateKeyError` 而非 `sqlite3.IntegrityError`

- **insert 返回值修正**
  - 用户指定主键时返回用户提供的值，而非 SQLite 的 `lastrowid`
  - 修复 insert 后立即 delete 失败的问题

- **delete 无主键表处理**
  - 统一无主键表的删除操作使用 `rowid`

- **外部文件加载列名映射**
  - 修复 `load_table` 使用 `Column(type, name='xxx')` 时列名映射问题

- **mypy 类型检查错误**
  - 修复 `orm.py` 中 datetime/date 类型转换的类型检查错误

### 文档

- 更新列操作方法的文档说明
- 更新 README 中的 GitHub 和 Gitee 链接

### 测试

- 添加 `test_insert_issues.py`：主键重复、返回值、insert+delete 联动测试
- 添加 `test_count_rows.py`：count_rows 方法测试
- 添加 `TestPkTypeMismatch`：主键类型不匹配场景测试
- 添加 Column.name 映射在 Schema 操作中的测试

---

## [0.6.1] - 2026-01-29

### 修复

- **Column.name 映射问题**
  - 修复使用 `Column(type, name='xxx')` 定义列时，查询结果属性为 None 的问题
  - 修复 `session.query().all()` 和 `session.execute(select(...))` 的列名映射
  - 相关文件：`pytuck/query/result.py`, `pytuck/query/builder.py`

---

## [0.6.0] - 2026-01-28

### 新增

- **无主键模型支持**
  - 支持定义没有主键的模型，使用内部隐式 `_pytuck_rowid` 作为行标识
  - Storage/Table 层完整支持无主键表的数据存储、序列化和查询
  - 适用于日志表、事件表等不需要唯一标识的场景
  - 示例：
    ```python
    class LogEntry(Base):
        __tablename__ = 'logs'
        # 无 primary_key=True 的列
        timestamp = Column(datetime)
        message = Column(str)
        level = Column(str)

    # 正常使用 insert/select/update/delete
    session.execute(insert(LogEntry).values(
        timestamp=datetime.now(),
        message='User logged in',
        level='INFO'
    ))
    ```

- **逻辑组合查询功能（OR/AND/NOT）**
  - 新增 `or_()`, `and_()`, `not_()` 逻辑操作符
  - 支持复杂的条件组合和嵌套查询
  - 示例：
    ```python
    from pytuck import or_, and_, not_

    # OR 查询
    stmt = select(User).where(or_(User.age >= 65, User.vip == True))

    # AND 查询（显式）
    stmt = select(User).where(and_(User.age >= 18, User.status == 'active'))

    # NOT 查询
    stmt = select(User).where(not_(User.deleted == True))

    # 组合查询
    stmt = select(User).where(
        or_(
            and_(User.age >= 18, User.age < 30),
            User.vip == True
        )
    )
    ```

- **外部文件加载功能（load_table）**
  - 新增 `load_table()` 函数，将 CSV/Excel 文件加载为模型对象列表
  - 用户先定义模型（表名、列类型），然后加载外部文件
  - 类型强制转换：能转就转，不能转就报错
  - 支持 CSV（自定义编码、分隔符）和 Excel（指定工作表）
  - 示例：
    ```python
    from pytuck.tools import load_table

    class User(Base):
        __tablename__ = 'users'
        id = Column(int, primary_key=True)
        name = Column(str)
        age = Column(int)

    # 加载 CSV 文件
    users = load_table(User, 'users.csv')

    # 加载 Excel 文件
    users = load_table(User, 'data.xlsx', sheet_name='Sheet1')

    # 自定义分隔符
    users = load_table(User, 'data.csv', delimiter=';')

    # 遍历数据
    for user in users:
        print(user.id, user.name, user.age)
    ```

### 修复

- **安全修复：SQL 注入漏洞**
  - 修复 SQLite 后端的 SQL 注入漏洞，使用参数化查询

### 重构

- **异常类重命名**
  - 将 `ConnectionError` 重命名为 `DatabaseConnectionError`，避免与 Python 内置异常冲突

- **移除 Excel 行号映射功能**
  - 移除 `row_number_mapping` 等选项，简化 Excel 后端实现

- **其他优化**
  - 重构模型基类实现更可靠的脏数据跟踪
  - 优化存储模块的安全性和错误处理
  - 修复查询语句中的闭包绑定问题
