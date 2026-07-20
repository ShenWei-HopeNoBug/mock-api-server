# SQLite 重构 — 子任务地图

> 总体方案见 [../sqlite-refactor-plan.md](../sqlite-refactor-plan.md)，本目录将其拆解为原子级子任务，按实施顺序排列。

## 实施顺序

| # | 子任务 | 文档 | 涉及文件 |
|---|--------|------|----------|
| 1 | 数据库设计与连接管理策略 | [task-01-database-design.md](task-01-database-design.md) | `data/mock.db`（设计） |
| 2 | MockDB 数据访问层 | [task-02-db-lib.md](task-02-db-lib.md) | `lib/db_lib.py`（新建） |
| 3 | 工作目录配置调整 | [task-03-work-file-config.md](task-03-work-file-config.md) | `config/work_file.py`、`lib/work_file_lib.py` |
| 4 | app_lib 改造 | [task-04-app-lib.md](task-04-app-lib.md) | `lib/app_lib.py` |
| 5 | mitmproxy_lib 与 server_lib 改造 | [task-05-mitmproxy-server-lib.md](task-05-mitmproxy-server-lib.md) | `lib/mitmproxy_lib.py`、`lib/server_lib.py` |
| 6 | request_catch 改造 | [task-06-request-catch.md](task-06-request-catch.md) | `module/request_catch.py` |
| 7 | mock_server 改造 | [task-07-mock-server.md](task-07-mock-server.md) | `module/mock_server.py` |
| 8 | app.py 改造 | [task-08-app-py.md](task-08-app-py.md) | `qt_win/app.py` |
| 9 | mitmproxy_data_edit_dialog 改造 | [task-09-edit-dialog.md](task-09-edit-dialog.md) | `qt_win/mitmproxy_data_edit_dialog.py` |
| 10 | 连带清理 | [task-10-cleanup.md](task-10-cleanup.md) | `config/enum/MITMPROXY.py`、`lib/utils_lib.py`、`requirements.txt` |

## 不变的部分

- `open_mitmproxy_preview_html` — 数据格式不变
- 前端 web 页面 — 无感
- `SimpleFolderBackup` 类本身 — 保留，本次不调用（`request_catch.py` 和 `mitmproxy_data_edit_dialog.py` 两处调用均移除，后续适配 SQLite 后再启用）

## 依赖关系

```
task-01 (设计) ──► task-02 (db_lib)
                        │
                        ├──► task-03 (work_file 配置)
                        │
                        ├──► task-04 (app_lib) ──► task-05 (mitmproxy/server lib)
                        │                              │
                        │                              ├──► task-06 (request_catch) ◄── task-02
                        │                              └──► task-07 (mock_server)   ◄── task-02
                        │
                        └──► task-08 (app.py)     ◄── task-04 (需要 close_all_mock_db)
                                   │
                                   └──► task-09 (edit_dialog)

task-10 (连带清理) 依赖 task-04 / task-05 完成后执行
```

> **说明**：
> - task-02 是核心基础，task-04 / task-06 / task-07 均直接依赖 `MockDB` 类
> - task-03 与 task-02 无强依赖（配置常量调整不依赖 db_lib 实现），可并行
> - task-08 依赖 task-04（需要 `close_all_mock_db` 函数）
> - task-06 / task-07 同时依赖 task-02（`MockDB` 类）和 task-05（`mitmproxy_lib` 保留的内存缓冲函数）
