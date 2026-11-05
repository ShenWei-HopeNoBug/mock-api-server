# 下载执行簇类化封装方案

> 关联文档：无直接台账条目（主动重构，非评审问题项）
> 状态：已实施（2026-11-05）
> 范围：`lib/download_lib.py` 重构 + `app_types/download_types.py` 一行注释

## 1. 背景

`download_server_static`（:318-466）主循环约 150 行，一次下载运行贯穿的状态（work_dir、下载配置、`DownloadDetailManager` 动态超时计数、`download_log` 数组、`log_name`、循环内 asset/path/proxies）靠参数透传 + 内层闭包（`write_log`/`append_log` 隐式捕获循环变量）维持，可读性与可测性差。

本文件实际包含三个功能簇，仅下载执行簇存在贯穿单次运行的状态，具备类化价值：

| 簇 | 函数 | 外部调用方 |
|---|---|---|
| 下载执行 | `download_server_static` → `get_download_ready_assets` → `get_download_assets_list` → `get_download_config`；`DownloadDetailManager`、`get_download_proxies`、`write_download_log` | `qt_win/app.py:656` |
| 导出 | `get_output_data_list`、`output_static_files` | `qt_win/output_static_dialog.py` |
| 共享工具 | `get_static_match_regexp` | `lib/static_file_lib.py:46` |

## 2. 决策

| 项 | 决定 |
|---|---|
| 封装形态 | 可实例化类 `StaticAssetDownloader`，一次下载运行一个实例 |
| 封装边界 | 只包下载执行簇；导出簇、共享正则、通用写日志器、`DownloadDetailManager` 保持模块级 |
| 兼容性 | 保留 `download_server_static(...)` 薄入口，签名与 `@error_catch` 不变，调用方零改动 |
| session 注入 | `__init__` 收 `session` 参数默认 `None` → 回退 `requests` 模块（API 兼容），**默认不启用 `requests.Session()`**，避免 cookie jar 引入行为差；仅为测试留注入点 |
| 配置读取 | `get_download_config` 现状双读合并为 `run()` 内一次 |
| 实施方式 | 当前分支单 commit，不自动提交 |

## 3. 改动清单

### 3.1 类结构

```python
class StaticAssetDownloader:
  def __init__(self, work_dir: str = '.', static_url_path: str = STATIC_DIR,
               compress: bool = True, callback: Optional[Callable[[Dict[str, Any]], None]] = None,
               stop_event: Optional[threading.Event] = None,
               session: Optional[Any] = None):
    self.work_dir = work_dir
    self.assets_dir = f'{work_dir}{static_url_path}'
    self.compress = compress
    self.callback = callback
    self.stop_event = stop_event
    self.session = session or requests          # 注入点：默认 requests 模块，行为与现状一致
    # run() 内初始化：config / detail_manager / download_log / log_name
```

`run()` 开头集中装载运行级状态：

```python
def run(self) -> None:
  self.config = self._load_config()
  self.base_timeout = self.config.get('download_timeout', DEFAULT_DOWNLOAD_CONNECT_TIMEOUT)
  self.auto_adjust_timeout = self.config.get('auto_adjust_timeout', DEFAULT_AUTO_ADJUST_DOWNLOAD_TIMEOUT)
  self.download_proxy_list = self.config.get('download_proxy_list', [])
  self.detail_manager = DownloadDetailManager(timeout=self.base_timeout)
  self.download_log = []
  self.log_name = create_timestamp()
  assets = self._get_ready_assets()
  ...
  for i, asset in enumerate(assets):
    self._download_one(asset, i, len(assets))
    self._write_log()
```

### 3.2 函数映射

| 现模块函数 | 去向 |
|---|---|
| `download_server_static` | 薄入口：`StaticAssetDownloader(...).run()`，`@error_catch` 保留在入口 |
| `get_download_ready_assets` | `self._get_ready_assets()`（`@error_catch` 随方法） |
| `get_download_assets_list` | `self._get_assets_list()`，改用 `self.config` 消二次读 |
| `get_download_config` | `self._load_config()` |
| `get_download_proxies` | `self._get_proxies(url)` |
| 主循环体 | `self._download_one(asset, i, total)`：item 级变量（`file_name`/`assets_path`/`part_path`/`connect_timeout`/`proxies`/`log_base`）保持局部 |
| 内层 `write_log` | `self._write_log()`（调模块级 `write_download_log`） |
| 内层 `append_log` | `self._append_log(log_base, success, message)`：`_download_one` 组装一次四静态字段 `log_base`，追加 `{**log_base, "success": ..., "message": ...}` |

### 3.3 模块级保留

`get_output_data_list`、`output_static_files`、`get_static_match_regexp`、`write_download_log`、`DownloadDetailManager`。

### 3.4 连带一处注释

`app_types/download_types.py:12`「消费端 `get_download_proxies`」→ 改为 `StaticAssetDownloader._get_proxies`（纯注释）。

## 4. 影响面（已核实）

| 调用方 | 依赖 | 结论 |
|---|---|---|
| `qt_win/app.py:656` | `download_server_static` | 签名不变，零改动 |
| `qt_win/output_static_dialog.py` | `get_output_data_list`/`output_static_files` | 不动 |
| `lib/static_file_lib.py` | `get_static_match_regexp` | 不动 |
| 删除的 4 个模块函数 | 无外部引用（已 grep 确认） | 安全吸收 |
| 依赖/导入/打包/线程模型 | — | 无新依赖、无循环导入变化、线程安全等价 |

## 5. 行为等价清单（实施时逐行对照项）

- `stop_event` 检查两处（ready 列表循环内 + 主循环开头），命中即 return 且**不写日志、不打「完毕」**；
- `write_log` 时机：非 200 分支内一次 + 每轮末尾一次；
- `DownloadDetailManager` 计数时机：非 200 不更新、ConnectionError 记失败、成功记成功；
- `.part` 原子写 + 双 except 清理、`compress` 独立 try + warning、`callback` 时序、`time.sleep(0.8)` 仅成功路径——原样搬运；
- `self.session` 默认 `requests` 模块 → 无 cookie jar，与现状逐字节等价。

## 6. 提交拆分

单 commit：`refactor(download): 下载执行簇封装为 StaticAssetDownloader`，含代码 + 本方案文档 + `docs/plans/README.md` 新域登记。不自动提交。

## 7. 验收

```bash
uv run ruff check .                    # 归零
.venv/Scripts/python -m py_compile lib/download_lib.py
```

| 项 | 方式 |
|---|---|
| 公开接口兼容 | `qt_win/app.py` 不改仍可用 |
| 行为等价 | 逐行 diff 对照 §5 清单 |
| 冒烟（可选） | GUI 触发一次静态资源下载，观察进度回调与 `download/*.json` 日志结构 |

## 8. 明确不做

- 导出簇类化、共享函数挪位置；
- `requests.Session()` 默认启用（cookie 共享属行为变更）；
- basename 碰撞、scheme 白名单、`stream=True` 大小上限等存量问题；
- 为重构新建测试文件（pytest 立项另行推进）。

## 9. 实施记录

| 日期 | 步骤 | 结果 | 备注 |
|---|---|---|---|
| 2026-11-05 | 按 §3 全部实施 | `ruff check` 归零 + `py_compile` 通过 | `_download_one` 内按原分支语义分布 `_write_log` 调用点；`session` 注入留点默认 `requests` 模块 |

## 10. 方案修正

| 日期 | 修正内容 | 原因 |
|---|---|---|
| — | — | — |
