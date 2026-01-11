# Pytuck 开发待办清单

本文件记录 Pytuck 项目的详细开发计划，供开发者参考。

## 已完成

### ✨ SQLAlchemy 2.0 风格对象状态管理（0.3.0）

**实现日期**：2026-01-11
**重要性**：🔥 高 - 核心 ORM 功能完善

**技术实现**：

1. **Identity Map（对象唯一性管理）**
   - 同一 Session 中相同主键的对象保证是同一个 Python 实例
   - 实现了 `Session._identity_map: Dict[Tuple[Type[PureBaseModel], Any], PureBaseModel]`
   - 查询时先检查 identity map，避免重复对象
   - 解决了 `session.get(User, 1)` 和 `session.execute(select(User).where(User.id == 1)).scalars().first()` 返回不同对象的问题

2. **自动脏跟踪（Dirty Tracking）**
   - 属性赋值（如 `user.name = "new"`）自动检测并在 `session.commit()` 时更新数据库
   - 通过在模型基类中重写 `__setattr__` 方法实现透明拦截
   - 检测 Column 属性修改，自动调用 `session._mark_dirty(instance)`
   - 只在值真正改变时标记为 dirty，避免无意义的数据库写操作

3. **查询实例自动注册**
   - `session.execute(select(...))` 返回的实例自动关联到 Session
   - 增强了 `ScalarResult._create_instance()` 方法，支持 identity map 查找和注册
   - 实例自动获得 `_pytuck_session` 和 `_pytuck_state` 属性
   - 修复了 `Session.flush()` 中的实例注册逻辑，统一使用 `_register_instance()` 方法

4. **merge() 操作**
   - 合并外部/detached 对象到 Session 中
   - 智能处理：如果对象已存在则更新属性，否则从数据库加载或创建新对象
   - 适用于 API 数据合并、序列化对象处理等场景
   - 返回 Session 管理的实例（可能不是传入的同一个对象）

5. **增强的上下文管理器**
   - 完善的事务支持：`with session.begin():`
   - 异常时自动回滚，成功时自动提交
   - 支持嵌套的 Session 和 begin() 上下文

**解决的问题**：
- ❌ **之前**：`bob.age = 99; session.commit()` 不生效
- ✅ **现在**：属性赋值自动检测并更新数据库
- ❌ **之前**：`session.get()` 和 `execute(select())` 返回不同对象实例
- ✅ **现在**：Identity Map 保证对象唯一性
- ❌ **之前**：查询返回的实例未关联到 Session，无法脏跟踪
- ✅ **现在**：自动注册，完整支持脏跟踪

**向后兼容性**：
- 100% 向后兼容，现有代码无需修改
- 现有的 `update()` 语句和 CRUD 模式的 `save()` 方法继续正常工作
- 新功能是增量增强，不破坏原有 API

### 其他已完成功能

- [x] 统一数据库连接器架构（`pytuck/connectors/` 模块）
- [x] 数据迁移工具（`migrate_engine()`, `import_from_database()`）
- [x] 从外部关系型数据库导入功能
- [x] 统一引擎版本管理（`pytuck/backends/versions.py`）
- [x] 表和列备注支持（`comment` 参数）
- [x] 泛型类型提示系统，完整的 IDE 开发体验支持
- [x] 强类型配置选项系统（dataclass 替代 **kwargs）

## 计划中的功能

### Web UI 界面支持

**目标**：为独立的 Web UI 库（如 Pytuck-LiteUI）提供 API 支持

**核心技术特性**：
- 数据库结构反射和元数据查询接口
- 表数据的分页查询和导出功能
- 实时数据变更通知接口
- RESTful API 风格的数据操作端点

**预期用户界面功能**：
- 可视化数据库表结构浏览
- 图形化数据增删改查操作
- SQL 风格查询构建器界面
- 数据导入/导出向导
- 存储引擎管理界面

**预期 API 设计**：
```python
# 数据库反射 API
storage.get_table_info()  # 获取所有表信息
storage.get_column_info(table_name)  # 获取表列信息

# 分页查询 API
storage.paginate(table_name, page=1, per_page=20, filters=...)

# Web 友好的查询构建
storage.build_query(table=User, conditions=[...], sort=...)
```

**架构设计理念**：
- 关注点分离：Pytuck 专注于核心 ORM，UI 作为独立库开发
- API 优先：为 Web UI 提供专门的 API 接口
- 可扩展性：通过标准化的 API，支持多种不同的 UI 实现

### ORM 事件钩子系统

**目标**：基于 SQLAlchemy 事件模式的完整事件系统

**核心架构**：
- **事件注册机制**：`event.listen()` 和 `@event.listens_for()` 装饰器
- **多种注册方式**：装饰器、函数式、用户自定义装饰器

**实施计划**：

**第一阶段：实例级别事件**（最重要）
- `before_insert` / `after_insert` - 插入前后触发
- `before_update` / `after_update` - 更新前后触发
- `before_delete` / `after_delete` - 删除前后触发

**第二阶段：会话级别事件**
- `before_flush` / `after_flush` - Session flush 前后触发
- `before_commit` / `after_commit` - Session commit 前后触发

**第三阶段：存储级别事件**（Pytuck 特有）
- `before_save` / `after_save` - 文件保存到磁盘前后触发
- `before_load` / `after_load` - 文件从磁盘加载前后触发

**预期用法**：
```python
from pytuck.core import event

# 方式1：装饰器注册
@event.listens_for(User, 'before_insert')
def log_user_creation(instance, session):
    print(f"Creating user: {instance.name}")
    instance.created_at = datetime.now()

# 方式2：函数式注册
def audit_changes(instance, session):
    logger.info(f"User {instance.id} modified")

event.listen(User, 'after_update', audit_changes)

# 方式3：用户自定义装饰器（基于 event.listen）
def before_insert(model_class):
    def decorator(func):
        event.listen(model_class, 'before_insert', func)
        return func
    return decorator
```

**应用场景**：
- 数据审计：记录变更历史
- 自动时间戳：创建时间、更新时间的自动设置
- 数据验证：插入/更新前的复杂业务规则验证
- 缓存失效：数据变更时自动清理相关缓存
- 事件通知：数据变更时发送通知或触发其他系统
- 数据同步：同步到搜索引擎、分析系统等

**技术实现要点**：
```python
# pytuck/core/events.py
class EventRegistry:
    def __init__(self):
        self._listeners = defaultdict(list)

    def listen(self, target, event_type, func):
        key = (target, event_type)
        self._listeners[key].append(func)

    def trigger(self, target, event_type, *args, **kwargs):
        key = (target, event_type)
        for func in self._listeners[key]:
            func(*args, **kwargs)
```

### JOIN 支持（多表关联查询）

**目标**：实现类似 SQL 的多表关联查询功能

**技术挑战**：
- Pytuck 是文档数据库，没有传统关系数据库的外键约束
- 需要在内存中进行表关联操作
- 性能优化：大数据量时的关联效率

**设计思路**：
```python
# 预期 API
query = session.query(User).join(Order, User.id == Order.user_id)
users_with_orders = query.all()

# 或者使用 relationship
class User(Base):
    orders = relationship("Order", back_populates="user")

class Order(Base):
    user = relationship("User", back_populates="orders")
```

### OR 条件支持

**目标**：支持复杂的逻辑查询条件

**当前状态**：只支持 AND 条件
**预期效果**：
```python
# 当前只能这样（隐式 AND）
users = session.query(User).filter(
    User.age >= 18,
    User.status == 'active'
).all()

# 预期支持 OR 条件
from pytuck.query import or_

users = session.query(User).filter(
    or_(User.age >= 65, User.vip == True)
).all()
```

### 聚合函数支持

**目标**：支持 COUNT, SUM, AVG, MIN, MAX 等聚合操作

**预期 API**：
```python
from pytuck.query import func

# 统计查询
user_count = session.query(func.count(User.id)).scalar()

# 聚合查询
avg_age = session.query(func.avg(User.age)).scalar()

# 分组聚合
results = session.query(
    User.department,
    func.count(User.id)
).group_by(User.department).all()
```

### 关系延迟加载

**目标**：优化关联数据的加载性能

**技术要点**：
- 延迟加载：只在访问时才加载关联数据
- 预加载：批量加载避免 N+1 问题
- 缓存机制：避免重复查询

### Schema 迁移工具

**目标**：提供数据库结构版本管理和迁移功能

**功能需求**：
- 自动检测 schema 变更
- 生成迁移脚本
- 版本控制和回滚支持

### 并发访问支持

**目标**：支持多进程/多线程安全访问

**技术挑战**：
- 文件锁机制
- 事务隔离
- 死锁检测和处理

## 计划增加的引擎

### 高优先级

- [ ] **DuckDB** - 分析型数据库引擎
  - 优秀的列式存储和分析性能
  - 支持复杂的 SQL 查询
  - 适合大数据分析场景

### 中优先级

- [ ] **TinyDB** - 纯 Python 文档数据库
  - 零依赖，轻量级
  - JSON 文档存储
  - 适合小型应用

- [ ] **diskcache** - 基于磁盘的缓存引擎
  - 持久化缓存支持
  - 适合缓存场景

### 低优先级

- [ ] **PyDbLite3** - 纯 Python 内存数据库
  - 纯内存操作，高性能
  - 适合临时数据处理

## 计划中的优化

### 性能优化

- [ ] **非二进制后端增量保存**
  - 当前：每次保存完整重写文件
  - 目标：只保存变更部分，提升大数据量性能

- [ ] **大数据集的流式读写支持**
  - 当前：全量加载到内存
  - 目标：支持流式处理，减少内存占用

- [ ] **SQLite 后端连接池**
  - 优化连接管理
  - 提升并发性能

### 安全性优化

- [ ] **使用 `tempfile` 模块改进临时文件处理安全性**
  - 避免临时文件安全风险
  - 自动清理机制

### 功能增强

- [ ] **关联关系和延迟加载增强**
  - 更智能的关联数据加载策略
  - 批量加载优化
  - 循环引用检测

## 技术债务

### 代码质量

- [ ] 统一异常处理机制
- [ ] 完善单元测试覆盖率
- [ ] 性能基准测试自动化

### 文档完善

- [ ] API 参考文档生成
- [ ] 最佳实践指南
- [ ] 性能调优指南

## 生态系统

### 工具链

- [ ] **Pytuck-CLI** - 命令行工具
  - 数据库管理命令
  - 数据导入导出
  - Schema 迁移

- [ ] **Pytuck-Admin** - Web 管理界面（即 Pytuck-LiteUI）
  - 可视化数据库管理
  - 查询构建器
  - 实时监控

### 集成支持

- [ ] **FastAPI 集成插件**
- [ ] **Django ORM 兼容层**
- [ ] **Pandas 数据分析集成**

## 版本规划

### v0.3.0（下一版本）
- Web UI 支持 API
- ORM 事件钩子系统（第一阶段）
- OR 条件支持

### v0.4.0
- JOIN 支持
- 聚合函数
- DuckDB 引擎

### v0.5.0
- Schema 迁移工具
- 并发访问支持
- 性能优化

---

**注意**：此文档为开发者内部使用，功能优先级和时间规划可能根据实际情况调整。