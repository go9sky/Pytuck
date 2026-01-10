# Pytuck 示例代码

本目录包含 Pytuck 的各种使用示例。

## 示例列表

### 1. new_api_demo.py - 新 API 完整演示 ⭐️ 推荐

展示新的 SQLAlchemy 风格 API 的所有功能：

- 使用 `declarative_base(db)` 创建声明式基类
- 通过 `Session` 管理所有 CRUD 操作
- 纯粹的模型定义（无业务方法）
- 事务管理和回滚
- 链式查询
- 上下文管理器

**运行方式：**
```bash
python3 examples/new_api_demo.py
```

**适合对象：**
- 新用户学习 Pytuck
- 从其他 ORM（如 SQLAlchemy）迁移过来的用户
- 希望使用最佳实践的开发者

### 2. transaction_demo.py - 事务功能演示

展示事务的使用方法：

- 成功的转账交易
- 失败的交易自动回滚
- 批量操作的事务保护
- 数据一致性保证

**运行方式：**
```bash
python3 examples/transaction_demo.py
```

**适合对象：**
- 需要使用事务功能的开发者
- 关注数据一致性的场景

### 3. all_engines_test.py - 多引擎测试

测试所有存储引擎的功能：

- binary: 二进制引擎（默认，最快）
- json: JSON 引擎（人类可读）
- csv: CSV 引擎（ZIP 压缩）
- sqlite: SQLite 引擎
- excel: Excel 引擎（需要 openpyxl）
- xml: XML 引擎（需要 lxml）

**运行方式：**
```bash
python3 examples/all_engines_test.py
```

**适合对象：**
- 测试不同存储引擎的性能
- 选择合适的存储格式

## API 选择指南

### 使用新 API（推荐）

如果你是：
- ✅ 新项目
- ✅ 学习过 SQLAlchemy 或其他主流 ORM
- ✅ 希望代码架构清晰、易维护
- ✅ 需要使用保留字段名（如 save、delete、filter 等）

**示例：**
```python
from pytuck import Storage, declarative_base, Session, Column

db = Storage('mydb.db')
Base = declarative_base(db)

class User(Base):
    __tablename__ = 'users'
    id = Column('id', int, primary_key=True)
    name = Column('name', str)

session = Session(db)
user = User(name='Alice')
session.add(user)
session.commit()
```

### 使用旧 API（兼容）

如果你是：
- 🔄 现有项目迁移中
- 🔄 希望快速上手（类似 Django ORM）
- 🔄 暂时不想改变现有代码

**注意：** 旧 API 已标记为兼容保留，建议逐步迁移到新 API。

## 快速开始

1. 安装依赖：
```bash
# 基础功能无需额外依赖

# 如果要使用 Excel 引擎
pip install openpyxl

# 如果要使用 XML 引擎
pip install lxml
```

2. 运行新 API 示例：
```bash
python3 examples/new_api_demo.py
```

3. 查看输出，理解新 API 的工作方式

4. 参考 `MIGRATION_GUIDE.md` 了解新旧 API 对比和迁移方法

## 更多资源

- **迁移指南**: `/MIGRATION_GUIDE.md` - 详细的新旧 API 对比和迁移步骤
- **实现计划**: `/.claude/plans/inherited-giggling-rainbow.md` - 新架构的设计文档
- **测试代码**: `/tests/` - 单元测试和集成测试

## 常见问题

### Q: 应该使用哪个 API？

**A:** 推荐使用新 API（`new_api_demo.py`），它提供更清晰的架构和更好的可维护性。

### Q: 旧代码还能继续使用吗？

**A:** 可以。旧 API 完全兼容，但建议新功能使用新 API，并逐步迁移现有代码。

### Q: 如何选择存储引擎？

**A:**
- **binary**: 默认选择，性能最好，适合大多数场景
- **json**: 需要人类可读、调试方便时使用
- **sqlite**: 需要 SQL 查询或与其他工具集成时使用
- **csv**: 需要与 Excel 等工具交互时使用
- **excel**: 直接生成 Excel 报表时使用

### Q: Session 需要手动关闭吗？

**A:** 建议使用上下文管理器：
```python
with Session(db) as session:
    session.add(user)
    # 自动 commit 和 close
```

## 贡献示例

欢迎贡献新的示例！请确保：

1. 代码清晰易懂，有充分注释
2. 使用新 API（除非专门演示旧 API）
3. 包含预期输出说明
4. 更新本 README.md
