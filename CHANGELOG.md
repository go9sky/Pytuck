# 更新日志

本文件记录项目的所有重要变更。格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，遵循 [语义化版本](https://semver.org/lang/zh-CN/) 规范。

> [English Version](./CHANGELOG.EN.md)

> 历史版本请查看：[docs/changelog/](./docs/changelog/)

---

## [0.7.0] - 2026-02-09

### 新增

- **ORM 事件钩子**
  - 支持 Model 级事件：`before_insert`/`after_insert`、`before_update`/`after_update`、`before_delete`/`after_delete`
  - 支持 Storage 级事件：`before_flush`/`after_flush`
  - 支持装饰器和函数式两种注册方式
  - 示例：
    ```python
    from pytuck import event

    @event.listens_for(User, 'before_insert')
    def set_timestamp(instance):
        instance.created_at = datetime.now()

    # 函数式注册
    event.listen(User, 'after_update', audit_changes)

    # Storage 级事件
    event.listen(db, 'before_flush', lambda storage: print("flushing..."))

    # 移除监听器
    event.remove(User, 'before_insert', set_timestamp)
    ```

- **关系预取 API（prefetch）**
  - 新增 `prefetch()` 函数，批量预取关联数据，解决 N+1 查询问题
  - 支持独立函数调用和查询选项两种方式
  - 支持一对多和多对一关系
  - 示例：
    ```python
    from pytuck import prefetch, select

    # 方式1：独立函数
    users = session.execute(select(User)).all()
    prefetch(users, 'orders')          # 单次查询加载所有用户的订单
    prefetch(users, 'orders', 'profile')  # 支持多个关系名

    # 方式2：查询选项
    stmt = select(User).options(prefetch('orders'))
    users = session.execute(stmt).all()  # orders 已批量加载
    ```

- **Select.options() 方法**
  - 新增查询选项链式调用支持，目前用于 prefetch 预取

- **查询索引优化**
  - `Column` 支持指定索引类型：`index='hash'`（哈希索引）或 `index='sorted'`（有序索引）
  - 范围查询（`>`, `>=`, `<`, `<=`）自动使用 SortedIndex 加速，避免全表扫描
  - `order_by` 排序自动利用 SortedIndex 的有序性，支持内联分页（提前停止）
  - `SortedIndex.range_query()` 支持开区间查询（`None` 边界）
  - 向后兼容：`index=True` 仍创建 HashIndex
  - 示例：
    ```python
    class User(Base):
        __tablename__ = 'users'
        id = Column(int, primary_key=True)
        name = Column(str, index=True)        # 哈希索引（等值查询加速）
        age = Column(int, index='sorted')      # 有序索引（范围查询+排序加速）

    # 范围查询自动使用有序索引
    stmt = select(User).where(User.age >= 18, User.age < 30)

    # 排序自动使用有序索引（无需全量排序）
    stmt = select(User).order_by('age').limit(10)
    ```

- **批量操作优化（bulk_insert / bulk_update）**
  - `Session.bulk_insert(instances)` — 批量插入模型实例列表，立即写入内存
  - `Session.bulk_update(instances)` — 批量更新模型实例列表，立即写入内存
  - `CRUDBaseModel.bulk_insert(instances)` / `CRUDBaseModel.bulk_update(instances)` — Active Record 模式
  - 批量主键分配（一次性预留 ID 范围）、批量索引更新、WAL 批量写入
  - 新增批量事件：`before_bulk_insert` / `after_bulk_insert` / `before_bulk_update` / `after_bulk_update`
  - **与 `session.add_all()` 的区别**：`add_all()` 在 `commit()` 时逐条执行并触发逐条事件；`bulk_insert()` 调用时立即批量执行，跳过逐条事件和 select 回读，性能更优
  - 示例：
    ```python
    # Session 层
    users = [User(name='Alice', age=20), User(name='Bob', age=22)]
    session.bulk_insert(users)   # 立即写入内存，自动分配主键
    session.commit()             # 持久化到磁盘

    # Active Record 层
    User.bulk_insert([User(name='Carol'), User(name='Dave')])

    # 批量更新
    for u in users:
        u.age += 1
    session.bulk_update(users)
    ```

### 性能基准（查询索引优化）

> 测试环境：100,000 条记录，age 字段范围 1-100，对比无索引 / HashIndex / SortedIndex

**Storage.query 底层引擎**

| 测试场景 | 无索引 | SortedIndex | 加速比 |
|----------|--------|-------------|--------|
| 范围查询 `age BETWEEN 30 AND 50`（~21% 数据） | 10.00s | 3.16s | **3.2x** |
| 高选择性范围 `age > 95`（~5% 数据） | 7.95s | 541ms | **14.7x** |
| 全量 `order_by('age')` | 7.21s | 8.01s | 0.9x |

**select() API 上层**

| 测试场景 | 无索引 | SortedIndex | 加速比 |
|----------|--------|-------------|--------|
| 范围查询 `age BETWEEN X AND Y` | 33.60s | 28.28s | **1.2x** |
| 高选择性范围 `age > 95` | 10.19s | 2.96s | **3.4x** |
| 组合查询 `range + order_by + limit` | 6.51s | 4.48s | **1.5x** |

**结论**：
- 范围查询是 SortedIndex 的主要优势场景，通过 bisect 定位边界减少遍历量
- 选择性越高（匹配记录越少），加速越显著——高选择性场景底层可达 **14.7x**
- 上层 API 加速比低于底层，因为模型实例化开销占固定比例
- 纯排序场景由于 Python C 层 timsort 已高度优化，SortedIndex 遍历无明显优势
- 组合查询（范围 + 排序 + 分页）场景下，范围缩小候选集后排序开销显著降低

> 运行基准测试：`python tests/benchmark/benchmark_index.py -n 100000`

### 测试

- 添加 ORM 事件钩子测试（35 个测试用例）
- 添加关系预取测试（23 个测试用例）
- 添加查询索引优化测试（42 个测试用例）
- 添加索引优化性能基准测试脚本（`tests/benchmark/benchmark_index.py`）
- 添加批量操作测试（34 个测试用例）
