# schema 迁移事务化与幂等化方案

> 关联文档：[PROJECT_REVIEW_REPORT.md](../../../reports/PROJECT_REVIEW_REPORT.md)「§8 明确的 bug」schema 迁移无事务条目、「复查记录：2026-11-04」❌仍存留-🔴
> 状态：已实施（2026-11-05）
> 范围：`lib/db/mock_db.py`、`lib/db/base.py`、`lib/db/api_data.py`、`lib/db/static_data.py`、`lib/db/variants.py`

## 1. 背景

`BaseSQLiteDB` 连接为 autocommit（`base.py:36` `isolation_level=None`），`MockDB._migrate_schema`（`mock_db.py:26-31`）调度三个 Mixin 的裸 `self._conn.execute(ALTER)`，每条独立提交；`user_version` 由 `super()._migrate_schema()` 在全部 DDL 成功后才推进——**"已迁移"与"已记录"之间存在非原子窗口**。中途失败（磁盘满/库损坏/锁竞争）→ 下次启动重跑已成功过的 `ADD COLUMN` → `duplicate column` → 崩溃循环且无法自愈。

**实施前核查新增发现**：启动顺序为 `_init_schema()`（`base.py:42`，执行 v5.sql 全量 `CREATE TABLE IF NOT EXISTS`）→ `_check_schema_version()` 迁移。v5.sql 中 `api_response_variants` 已含 `operator`+`type` 列，因此 **v1/v2 老库（无变体表）升级路径现在就会崩**：`_init_schema` 预建最新形态表 → `_migrate_variant` 的 `ADD COLUMN operator`/`type` 撞 `duplicate column`。仅包事务只能保证回滚干净，重启仍在同点崩——**幂等 ALTER 由可选项升级为必做项**。

已验证关键事实：

- `PRAGMA user_version = N` 可放入事务且随 COMMIT/ROLLBACK 生效/回滚（实测 :memory: 库：回滚后版本号与建表同步撤销）；
- 三个 Mixin 迁移方法内部均为裸 `self._conn.execute`，共享同一连接对象，无嵌套 `_transaction()`，可直接被外层事务包裹；
- `CREATE TABLE/INDEX IF NOT EXISTS`、`DROP INDEX IF EXISTS` 本身幂等，无需处理。

## 2. 决策

| 项 | 决定 |
|---|---|
| 原子性 | `MockDB._migrate_schema` 整体包 `with self._transaction():`，`super()._migrate_schema()`（user_version）同处事务内 |
| 幂等性 | `BaseSQLiteDB` 新增 `_column_exists` 工具；全部 `ADD COLUMN` 改为列不存在才执行 |
| init/migrate 顺序 | 不调换：`_init_schema` 先跑对"表整体缺失"库有修复作用；幂等写法使顺序不再敏感 |
| 新库/降级路径 | 不动（`db_version == 0` 走 `executescript` 建表不进迁移；降级仅 warning） |
| 实施方式 | 当前分支单 commit，不自动提交 |

## 3. 改动清单

### 3.1 `lib/db/base.py` — 新增列存在性工具

```python
def _column_exists(self, table: str, column: str) -> bool:
  """检查表是否存在指定列（供幂等迁移判断）"""
  rows = self._conn.execute(f'PRAGMA table_info({table})').fetchall()
  return any(row[1] == column for row in rows)
```

`table`/`column` 均为代码内字面量，无注入面。

### 3.2 `lib/db/mock_db.py` — 迁移包事务

```python
def _migrate_schema(self, from_version: int, to_version: int) -> None:
  """执行 schema 版本迁移，调度各 Mixin 的表级迁移逻辑（整体一个事务）"""
  with self._transaction():
    self._migrate_api(from_version, to_version)
    self._migrate_static(from_version, to_version)
    self._migrate_variant(from_version, to_version)
    super()._migrate_schema(from_version, to_version)
```

`_transaction` 自带 `self._lock` 与 ROLLBACK 日志，复用现成基建；Mixin 签名零改动。

### 3.3 三个 Mixin — `ADD COLUMN` 幂等化（共 8 处）

模式统一为：

```python
if not self._column_exists('api_data', 'timeout'):
  self._conn.execute('ALTER TABLE api_data ADD COLUMN timeout INTEGER NOT NULL DEFAULT 0')
```

| 文件 | 列（迁移版本段） |
|---|---|
| `api_data.py` | `timeout`、`request_content_type`（v1→v2）；`response_variant_ids`、`enabled`（v2→v3）；`operator`（v3→v4） |
| `static_data.py` | `operator`（v3→v4） |
| `variants.py` | `operator`（v3→v4）；`type`（v4→v5） |

效果：`_init_schema` 预建最新形态表时 ALTER 自动跳过（v≤2 老库修通）；迁移可安全重入（事务外半改、未来新增步骤均不怕重复）。

## 4. 影响面

| 调用方 | 结论 |
|---|---|
| `MockDB.__init__` → `_check_schema_version` → `_migrate_schema` | 唯一触发点，调用方零改动 |
| mixin 其他 `_transaction` 用法 | 不涉及 |
| WAL/busy_timeout/锁语义 | 不变 |

## 5. 行为等价与验收

- 正常路径：迁移结果与现状一致（相同列、相同 `user_version`）；
- 失败路径：ROLLBACK 后库与迁移前逐字节等价、`user_version` 不推进、可重试。

验证矩阵：

| 场景 | 构造 | 预期 |
|---|---|---|
| v1 无变体表老库 | 按 v1.sql 建库 + `user_version=1` | 升到 v5 不崩，列齐全（本次新修通路径） |
| v3/v4 常规升级 | 对应版本建库 | ALTER 按需执行 |
| 迁移中途失败 | 预建冲突对象/模拟 ALTER 抛错 | ROLLBACK、版本号未推进、重启重试成功 |
| 新库 | `user_version=0` | 走原路径不受影响 |

```bash
uv run ruff check .   # 保持归零
```

## 6. 明确不做

- `_init_schema`/`_check_schema_version` 顺序调换（幂等写法已覆盖）；
- 历史库数据修复工具（崩溃库由 WAL/checkpoint 机制自然恢复）；
- 迁移框架化（版本步进表、down 迁移），当前 8 处 ALTER 直判足够。

## 7. 实施记录

| 日期 | 步骤 | 结果 | 备注 |
|---|---|---|---|
| 2026-11-05 | 按 §3 全部实施 | `ruff` 归零 + 4 场景实测通过：v1 无变体表升级修通、v3 常规升级、幂等重跑、注入失败整体回滚且可重试 | 三个 Mixin 补充 `_column_exists` 宿主属性声明；验证用临时脚本未入库 |

## 8. 方案修正

| 日期 | 修正内容 | 原因 |
|---|---|---|
| 2026-11-05 | 新增 §1「`_init_schema` 预建最新表 → v≤2 老库必崩」发现；幂等 ALTER 由可选项升级为必做项（§2/§3.3） | 实施前核查 `schema/v5.sql` 与启动顺序发现初版方案（仅事务）不足以修通该路径 |
