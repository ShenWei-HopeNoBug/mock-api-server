# pytest 测试基线方案

> 关联文档：[PROJECT_REVIEW_REPORT.md](../../../reports/PROJECT_REVIEW_REPORT.md)「🔴 高优先级问题 #1」；`AGENTS.md`；`pyproject.toml`
> 状态：已实施
> 范围：新增 `tests/`（镜像源码结构）、`pyproject.toml`（pytest ini）、`AGENTS.md`（测试命令）

## 1. 背景

评审问题 #1：全项目无任何自动化测试，唯一 `test.py` 是 gitignore 排除的 scratch 文件、`insert_test_db_data.py` 是手动灌数据脚本；核心匹配逻辑（`MockRequestHandler`、变体轮换 `_select_variant`、Range 解析 `_parse_range`）裸奔，sqlite 重构类变更没有安全网。

现状利好：`pytest>=8` 已在 dev 依赖组（venv 已装 9.2.0）；`lib/` 多数核心类构造注入式、纯函数占比高，天然可测。

## 2. 决策

| 项 | 决定 |
|---|---|
| 目标 | 建测试基建 + 首批高价值用例（~90 例），确立"变更配测试"模式；不设覆盖率硬指标 |
| 目录结构 | **镜像源码结构**（非 plans 式功能域）：`tests/lib/test_<文件>.py` ↔ `lib/<文件>.py`，`lib/db/` 对应 `tests/lib/db/`；双向定位零成本 |
| `__init__.py` | 不加（pytest 不需收集；文件名保持唯一避免 prepend 模式撞名） |
| CI | 明确不做（本地仓库无远端诉求） |
| 提交 | 两 commit：① 基建+T1 纯逻辑（utils/server_lib/static_file）② T2/T3（db/bridge/logger） |

## 3. 改动清单

### 3.1 目录与用例清单

```
tests/
  conftest.py                     # tmp_work_dir / mock_db / flask_app / make_handler
  lib/
    test_utils_lib.py             # ↔ lib/utils_lib.py        ~20 例
    test_server_lib.py            # ↔ lib/server_lib.py       ~20 例
    test_static_file_lib.py       # ↔ lib/static_file_lib.py  ~20 例
    test_bridge_lib.py            # ↔ lib/bridge_lib.py       ~6 例
    test_logger_lib.py            # ↔ lib/logger_lib.py       ~5 例
    db/
      test_api_data.py            # ↔ lib/db/api_data.py      ~10 例
      test_variants.py            # ↔ lib/db/variants.py      ~5 例
      test_cache.py               # ↔ lib/db/cache.py+迁移    ~5 例
  module/                         # 预留（MockServer/MCP 路由级测试）
```

**`test_utils_lib.py`**：`create_md5`（str/bytes/一致性）、`is_url_match`（str/list）、`remove_url_query`/`remove_url_domain`/`get_url_domain`（含无 scheme）、`get_request_content_type`（json/form/multipart/none/其他×方法）、`is_file_request`、`remove_byte_empty_content`、`JsonFormat` dumps/format/sort、`limit_num_range` 边界。

**`test_server_lib.py`**：
- `_select_variant`：首命中 `variants[0]`→顺序推进→末位驻留；`last_variant_timeout` 超时重置回 `variants[0]`（`monkeypatch` 打 `time.time`）；空 `device_state` 自动初始化；
- `_get_api_match_meta`：`request_key` 未中→None、`response_key` 精确中、未中→fallback 最后插入项、inner 空→None；
- `ClientStateManager`：get_or_create 新/旧、LRU `move_to_end`、limit 淘汰、md5 归一化 key、get/set/delete；
- `parse_flask_request`：GET args→params + route 去 query；POST json/form/multipart（file→`file-{md5}`）/未知 content-type→空 params；
- `handle` 未命中→404 `{'error': 'No valid mock data'}`；
- `register_system_routes`：`/ping` 200、`/system/shutdown` GET 405、POST 回环 200+回调、非回环 403。

**`test_static_file_lib.py`**：
- `_parse_range` 全分支：无头/空文件→None、`bytes=0-99`、`bytes=0-` 到尾、`bytes=-500` suffix、suffix>size→从头、`start≥total`→None、截断后 `start>end`→None、`bytes=-`→None、畸形→None、end 超界截断；
- `_resolve_file`：正常命中、`../` 被 basename 剥掉、绝对路径同理、符号链接逃逸→containment 失败（Windows 无权限建 symlink 时 `pytest.skip`）；
- `_compute_etag` 稳定格式、`_check_if_range` etag/日期匹配、`_is_image`、`_build_cache_control` 图片 vs 其他、`_format_size`、`_format_http_date`。

**`test_bridge_lib.py`**（此前临时验证脚本转正）：FIFO 顺序、shutdown 排空后 worker 退出、关闭后 dispatch 丢弃+限流 warn、队满 512 丢新+warn、队满时 shutdown 挤位非阻塞、`_closed` 后 `_send_response` 不调 send。

**`test_db_*.py`**：MockDB tmp work_dir 初始化建表；api insert→`get_api_detail`；`get_api_list_page` 分页+总数；LIKE 模糊查询；update/delete；变体 insert/`get_variant_by_id`/按 api 列举；`MockDBCache` 同 work_dir 同实例、异 work_dir 异实例、`close`/`close_all`、同库重开迁移幂等（`user_version` 不变）。

**`test_logger_lib.py`**：child+stdlib `queue.Queue`→全域 logger 挂 `QueueHandler` 且记录入队（无需 spawn）；`queue=None`→`ValueError`；未知 role→`ValueError`；重复 configure 幂等；`shutdown_logging` 幂等；模块全局态用 `monkeypatch` 复位。

### 3.2 `conftest.py` fixture

| fixture | 行为 |
|---|---|
| `tmp_work_dir` | `tmp_path` 建 `data/`、`config/` 目录 |
| `mock_db` | `MockDBCache.get(tmp_work_dir)` yield → teardown `MockDBCache.close_all()` |
| `flask_app` | 独立 `Flask('test')` 实例（挂被测路由用） |
| `make_handler` | 工厂：`mock_api_map` dict + lambda key funcs + `ThreadSafeLRUCache` 构 `MockRequestHandler` |

### 3.3 `pyproject.toml`

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
addopts = "-q"
```

### 3.4 `AGENTS.md`

命令区补 `.venv/Scripts/pytest.exe`（uv 不在 PATH 时的实跑命令）。

## 4. 影响面

| 项 | 说明 |
|---|---|
| 业务代码 | **零改动**——实施中发现的 bug 单独记录再议 |
| 依赖 | 无新增（pytest 已在 dev 组） |
| lint | `tests/` 不进 ruff exclude，同规则归零 |
| 运行方式 | `.venv/Scripts/pytest.exe` / `uv run pytest`；`pytest tests/lib/db` 按目录粒度跑 |
| 维护规则 | 新 lib 文件→`tests/lib/test_<名>.py`；lib 新子包→对应子目录；单源文件单测文件，超 ~300 行按类拆 |

### 项目特有坑（实施注意）

- `MockDBCache._cache` 类级全局 dict，测试间串库 → fixture teardown 必 `close_all()`；
- `jsonify`/`parse_flask_request` 需 Flask request context → `flask_app` + `test_request_context()`；
- `_select_variant` 依赖 `time.time()` → `monkeypatch` 控时间测 timeout 回退，不搞 sleep；
- `configure_logging` `_LOG_CONFIGURED` 全局一次性 → 用例内 `monkeypatch` 复位模块全局；
- Windows 建 symlink 可能无权限 → 符号链接逃逸用例 `pytest.skip` 兜底；
- `QueueHandler` 兼容 stdlib `queue.Queue`（`put_nowait`），child 模式无需真 spawn。

## 5. 行为等价与验收

| 场景 | 预期 |
|---|---|
| `.venv/Scripts/pytest.exe` | 全绿（~90 例） |
| `.venv/Scripts/ruff.exe check .` | 归零（tests/ 同规则） |
| 单文件跑 | `pytest tests/lib/test_server_lib.py` 独立通过 |
| 误报防护 | 用例不依赖执行顺序（每个 fixture 独立） |

## 6. 明确不做

- CI / GitHub Actions 等流水线；
- Qt / WebEngine 测试（不引入 pytest-qt）；
- spawn 真子进程测试（重；mp logging 行为已手工验证）；
- mitmproxy / MCP 实服务测试；
- 覆盖率硬指标与强制门禁；
- 任何业务代码改动；
- `test.py` scratch 文件清理（gitignore 已排除）。

## 7. 实施记录

| 日期 | 步骤 | 结果 | 备注 |
|---|---|---|---|
| 2026-11-05 | commit① 基建+T1 | `tests/` 基建（conftest 4 fixture）+ pytest ini + AGENTS 命令；utils/server_lib/static_file 三组纯逻辑用例落地 | `c252ce3`；实测 71 过 1 skip（symlink 权限兜底生效） |
| 2026-11-05 | logger 置位污染修复 | `configure_logging` 校验前置、通过才置 `_LOG_CONFIGURED` | `90ae620`；由新 logger 用例抓出的存量 bug（校验失败置位残留→后续正确配置被静默跳过且不抛错），见 §8 |
| 2026-11-05 | commit② T2/T3 | db 三件套（api/variants/cache 迁移幂等）+ bridge（FIFO/排空/队满/关闭守卫/事件去重）+ logger（角色挂载/队列传输/幂等/置位污染回归） | 全量 113 过 1 skip，`ruff check` 归零 |

## 8. 方案修正

| 日期 | 修正内容 | 原因 |
|---|---|---|
| 2026-11-05 | 新增一例不在原清单的业务修复：`configure_logging` 置位顺序 | 测试抓出的真实 bug：`_LOG_CONFIGURED` 在校验前置位，非法调用残留置位使后续配置静默跳过；校验前置修复，单独 `fix(log)` commit |
| 2026-11-05 | logger 用例断言改精确类型匹配（`type(h) is htype`） | pytest caplog 插件的 `LogCaptureHandler` 及 `RotatingFileHandler` 均为 `StreamHandler` 子类，`isinstance` 计数互扰 |
