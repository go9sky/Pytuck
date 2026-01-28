# 更新日志 / Changelog

本文件记录项目的所有重要变更。格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，遵循 [语义化版本](https://semver.org/lang/zh-CN/) 规范。

This file documents all notable changes. Format based on [Keep a Changelog](https://keepachangelog.com/en-US/1.0.0/), following [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

> 历史版本请查看 / For historical versions, see: [docs/changelog/](./docs/changelog/)

---

## [0.6.0] - 2026-01-28

### 新增 / Added

- **无主键模型支持 / Primary Key-less Model Support**
  - 支持定义没有主键的模型，使用内部隐式 `_pytuck_rowid` 作为行标识
  - Storage/Table 层完整支持无主键表的数据存储、序列化和查询
  - 适用于日志表、事件表等不需要唯一标识的场景
  - 示例 / Example：
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

- **逻辑组合查询功能 / Logical Query Operators (OR/AND/NOT)**
  - 新增 `or_()`, `and_()`, `not_()` 逻辑操作符
  - 支持复杂的条件组合和嵌套查询
  - 示例 / Example：
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

- **外部文件加载功能 / External File Loading (load_table)**
  - 新增 `load_table()` 函数，将 CSV/Excel 文件加载为模型对象列表
  - 用户先定义模型（表名、列类型），然后加载外部文件
  - 类型强制转换：能转就转，不能转就报错
  - 支持 CSV（自定义编码、分隔符）和 Excel（指定工作表）
  - 示例 / Example：
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

### 修复 / Fixed

- **安全修复：SQL 注入漏洞 / Security Fix: SQL Injection**
  - 修复 SQLite 后端的 SQL 注入漏洞，使用参数化查询
  - Fixed SQL injection vulnerability in SQLite backend using parameterized queries

### 重构 / Refactored

- **异常类重命名 / Exception Rename**
  - 将 `ConnectionError` 重命名为 `DatabaseConnectionError`，避免与 Python 内置异常冲突
  - Renamed `ConnectionError` to `DatabaseConnectionError` to avoid conflict with Python built-in exception

- **移除 Excel 行号映射功能 / Removed Excel Row Number Mapping**
  - 移除 `row_number_mapping` 等选项，简化 Excel 后端实现
  - Removed `row_number_mapping` options to simplify Excel backend

- **其他优化 / Other Improvements**
  - 重构模型基类实现更可靠的脏数据跟踪
  - 优化存储模块的安全性和错误处理
  - 修复查询语句中的闭包绑定问题
  - Refactored model base class for more reliable dirty data tracking
  - Improved security and error handling in storage module
  - Fixed closure binding issue in query statements
