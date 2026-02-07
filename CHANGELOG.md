# 更新日志

本文件记录项目的所有重要变更。格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，遵循 [语义化版本](https://semver.org/lang/zh-CN/) 规范。

> [English Version](./CHANGELOG.EN.md)

> 历史版本请查看：[docs/changelog/](./docs/changelog/)

---

## [0.7.0] - 2026-02-07

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

### 测试

- 添加 ORM 事件钩子测试（35 个测试用例）
- 添加关系预取测试（23 个测试用例）
