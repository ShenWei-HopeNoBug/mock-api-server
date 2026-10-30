# 日志统一方案

> 关联文档：[PROJECT_REVIEW_REPORT.md](../../../PROJECT_REVIEW_REPORT.md)「§4 print 炸弹」「§6 error_catch」「§7 日志不统一」「§9 日志噪音」「改进建议-4」
> 状态：已完成（`01d35d5` + print 迁移 commit）
> 范围：`lib/logger_lib.py` / `lib/decorate.py` / 运行时文件 print 迁移 / werkzeug 降噪

## 1. 背景

基建已有但混用严重：`logger_lib.py` 提供 `setup_logger`（stream + `RotatingFileHandler` 10MB×5 → `logs/app.log`），`APP_LOGGER` 在 18 个文件使用；同时 57 处业务 `print` 散在 15 个文件，mock 命中、延时、限速、抓包、下载进度等关键路径全走 print 不进日志文件。

三个实质问题（比"不规范"更严重）：

1. **-w 打包版 `print()` 会崩**：PyInstaller windowed 模式 `sys.stdout=None`，`print()` 抛 `AttributeError` 可杀掉所在线程（`mock_server.start_server` 入口第一行即是 print）；`mcp_server.py:654` 已有 `isatty()` 兼容代码证明踩过坑；
2. **同模式下 `StreamHandler` 也会崩**：`sys.stderr=None` 时 stream handler emit 同样抛异常，需在挂 handler 时防御；
3. **werkzeug access 日志刷屏**：`/ping` 健康检查每探测一次刷一条访问日志（retry 最多 20 次）。

## 2. 决策（已与用户确认）

| 项 | 决定 |
|---|---|
| logger 组织 | 分域 logger：APP / MOCK / STATIC / CATCH / MCP / APPSRV / DB / DOWNLOAD，共享同一组 handler（同一 `logs/app.log` + console） |
| `error_catch` | 只加 `exc_info=True` 堆栈，不改吞异常兜底语义（语义收紧留"明确 bug 修复"议题） |

## 3. 改动清单

### 3.1 `lib/logger_lib.py` 加固 + 分域 logger

- `get_stream_logger_handler()` 返回 `Optional`：`sys.stderr is None`（-w 打包态）时不创建、不挂载，仅保留文件 handler；
- 按域预置 logger：

| Logger | 覆盖文件 |
|---|---|
| `APP_LOGGER` | `main.py`、`app_env.py`、`qt_win/*`、`lib/app_lib`、`lib/work_file_lib`、`lib/utils_lib`、`lib/decorate` |
| `MOCK_LOGGER` | `module/mock_server`、`lib/server_lib` |
| `STATIC_LOGGER` | `lib/static_file_lib` |
| `CATCH_LOGGER` | `module/asyncio_mitmproxy_server`、`module/request_catch` |
| `MCP_LOGGER` | `module/mcp_server` |
| `APPSRV_LOGGER` | `module/app_server` |
| `DB_LOGGER` | `lib/db/*` |
| `DOWNLOAD_LOGGER` | `lib/download_lib` |

### 3.2 `error_catch` 带堆栈

`lib/decorate.py` sync/async 两个 wrapper：`APP_LOGGER.error(f'...：{e}', exc_info=True)`，删除手动拼接的时间戳（formatter 已带 `asctime`）。`error_return` 兜底、`log` 开关、全部调用方不变。

### 3.3 print → logger 迁移（约 45 处）

| 处理 | 文件 |
|---|---|
| 转换 | `module/`×5、`lib/`（app_lib/download_lib/server_lib/static_file_lib/utils_lib/work_file_lib）、`qt_win/app.py`、`main.py` |
| 同步迁移 | `lib/db/*` 现有 `APP_LOGGER` → `DB_LOGGER`（机械替换） |
| 不碰 | `build.py`、`tools/`、`insert_test_db_data.py`（CLI 合理输出）；`lib/backup_lib`、`lib/hash_lib`、`lib/file_lib`（死代码，留清理议题删除） |

级别约定：业务事件（命中/延时/限速/保存/启动）→ `info`；诊断细节 → `debug`；明显调试残留（如 `print('server_config', server_config)`）→ `debug` 或删除。

### 3.4 werkzeug 降噪

`mock_server` / `app_server` 启动处 `logging.getLogger('werkzeug').setLevel(logging.ERROR)`。

## 4. 提交拆分

| Commit | 内容 |
|---|---|
| 1 | §3.1 logger_lib 加固与分域 logger + §3.2 error_catch 堆栈 + §3.4 werkzeug 降噪 + 本方案文档与登记 |
| 2 | §3.3 print→logger 全量迁移 + db 域迁移 + 冒烟验证 + `CHANGELOG` Unreleased 补记 |

## 5. 验收

```bash
uv run ruff check .                          # 保持归零
# 模拟 -w 打包态：stdout/stderr 置 None 后 logger 不崩、文件仍写入
python -c "import sys; sys.stdout=None; sys.stderr=None
from lib.logger_lib import APP_LOGGER; APP_LOGGER.info('test')"
# dev 冒烟：应用启动后 logs/app.log 有分域日志记录
# 打包后人工运行 win 版 exe，确认无崩溃且 app.log 正常滚动
```

## 6. 明确不做

- dictConfig / yaml 日志配置化（过度设计）；
- structlog、多日志文件切分、`logging.basicConfig` 重构 import 时机；
- `error_catch` 吞异常语义收紧（属"明确 bug 修复"议题，逐点评估）；
- 死代码文件内 print（随文件删除）；
- `__name__` 层级 logger 重构（分域命名已满足可读性）。

## 7. 实施记录

| 日期 | 步骤 | 结果 | 备注 |
|---|---|---|---|
| 2026-10-31 | §3.1 logger_lib 加固 + 分域 | `get_stream_logger_handler` 改 `Optional`（`sys.stderr is None` 不挂载）；8 个分域 logger 预置；`LOG_FORMAT`/`LOG_DATE_FORMAT` 提为模块常量 | 模拟 `sys.stdout/stderr=None` 验证：logger 不崩且 `logs/app.log` 正常写入 |
| 2026-10-31 | §3.2 error_catch 堆栈 | sync/async 两处改 `APP_LOGGER.error(msg, exc_info=True)`，删手动时间戳与 `datetime` import | 语义不变 |
| 2026-10-31 | §3.4 werkzeug 降噪 | `mock_server`/`app_server` 启动处 `setLevel(ERROR)` | `ruff check` 归零保持，`MainWindow` 冒烟通过 |
| 2026-10-31 | §3.3 print→logger 迁移 | 45 处运行时 print 全部转换（info×37 / warning×6 / debug×2）；`lib/db/*` 及 `module/*` 文件内 `APP_LOGGER` 同步迁移至 DB/MOCK/APPSRV/CATCH/MCP 域；`work_file_lib.py` 的 `__main__` 块 print 按 CLI 约定保留 | 级别微调：`server_config`/`mitmproxy_config`/`mcp_config` 等启动配置类归 info，probe 检测与抓包过滤归 debug |
| 2026-10-31 | §5 验收 | 范围内 print 残留 0；8 域 logger 在 `stdout/stderr=None` 下全部正常写入 `logs/app.log`；`MainWindow` 冒烟通过 | CHANGELOG [Unreleased] 已补记 |

## 8. 方案修正

| 日期 | 修正内容 | 原因 |
|---|---|---|
| （待填） | | |
