# SQLite 重构 — 子任务地图

> 总体方案见 [../sqlite-refactor-plan.md](../sqlite-refactor-plan.md)，本目录将其拆解为原子级子任务，按实施顺序排列。

## 实施顺序

| # | 子任务 | 文档 | 涉及文件 |
|---|--------|------|----------|
| 1 | 数据库设计与连接管理策略 | [task-01-database-design.md](task-01-database-design.md) | `data/mock.db`（设计） |
| 2 | MockDB 数据访问层 | [task-02-db-lib.md](task-02-db-lib.md) | `lib/db_lib.py`（新建） |
| 3 | 工作目录配置调整（仅新增 DB 常量） | [task-03-work-file-config.md](task-03-work-file-config.md) | `config/work_file.py`、`lib/work_file_lib.py` |
| 4 | app_lib 改造 | [task-04-app-lib.md](task-04-app-lib.md) | `lib/app_lib.py` |
| 5 | request_catch 改造 | [task-06-request-catch.md](task-06-request-catch.md) | `module/request_catch.py` |
| 6 | mitmproxy_lib 与 server_lib 改造 | [task-05-mitmproxy-server-lib.md](task-05-mitmproxy-server-lib.md) | `lib/mitmproxy_lib.py`、`lib/server_lib.py` |
| 7 | mock_server 改造 | [task-07-mock-server.md](task-07-mock-server.md) | `module/mock_server.py` |
| 8 | app.py 改造 | [task-08-app-py.md](task-08-app-py.md) | `qt_win/app.py` |
| 9 | mitmproxy_data_edit_dialog 改造 | [task-09-edit-dialog.md](task-09-edit-dialog.md) | `qt_win/mitmproxy_data_edit_dialog.py` |
| 10 | 连带清理（含 JSON 文件项移除） | [task-10-cleanup.md](task-10-cleanup.md) | `config/enum/MITMPROXY.py`、`lib/utils_lib.py`、`requirements.txt`、`config/work_file.py`、`lib/work_file_lib.py` |

> **执行顺序调整说明**：原方案中 task-05（删除 `mitmproxy_lib` 旧函数）在 task-06（`request_catch` 改用 DB）之前执行，会导致 `request_catch` 仍调用已删除的 `save_response` / `save_static` / `load_response_cache` / `load_static_cache` 而报错。调整为 **先 task-06 再 task-05**，确保 `request_catch` 不再调用旧函数后再删除。同时 task-03 中的 `WORK_FILE_DICT` JSON 文件项移除延后到 task-10，避免中间状态全新安装时旧代码读不到 JSON 文件。

## 不变的部分

- `open_mitmproxy_preview_html` — 数据格式不变
- 前端 web 页面 — 无感
- `SimpleFolderBackup` 类本身 — 保留，本次不调用（`request_catch.py` 和 `mitmproxy_data_edit_dialog.py` 两处调用均移除，后续适配 SQLite 后再启用）

## 依赖关系

```
task-01 (设计)
   │
   ▼
task-02 (db_lib)
   │
   ▼
task-03 (work_file 配置 — 仅新增 DB 常量)
   │
   ├──► task-04 (app_lib) ──► task-06 (request_catch) ──► task-05 (删除旧函数)
   │                                                        │
   │                                                        ▼
   │                                                    task-07 (mock_server)
   │                                                        │
   └────────────────────────────────────────────────────► task-08 (app.py)
                                                                │
                                                                ▼
                                                           task-09 (edit_dialog)

task-10 (连带清理 — 含 JSON 文件项移除) 在所有任务完成后执行
```

> **说明**：
> - task-02 是核心基础，task-04 / task-06 均直接依赖 `MockDB` 类
> - task-03 仅新增 `DB_DATA_PATH` 常量，不移除 JSON 文件项（延后到 task-10），task-04 / task-06 均需此常量
> - **task-06 必须在 task-05 之前**：task-05 删除 `mitmproxy_lib` 旧函数（`save_response` / `save_static` / `load_response_cache` / `load_static_cache`），task-06 改造 `request_catch` 后不再调用这些函数，才可安全删除
> - task-07 依赖 task-04（`get_mock_api_data_list` / `_close_mock_db`），不依赖 task-05
> - task-08 依赖 task-04（`close_all_mock_db`）和 task-07（`start_server` 签名变更）
> - task-10 在所有任务完成后执行，移除 `WORK_FILE_DICT` 中 JSON 文件项、`pandas` 依赖、`MITMPROXY_DATA_FIELDS` 等
