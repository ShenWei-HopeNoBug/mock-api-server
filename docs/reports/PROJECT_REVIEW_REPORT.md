# mock-api-server 项目评审报告

> 评审日期：2026-10-31
> 评审范围：全量代码（约 7.6k 行核心代码，不含 qt_ui 生成代码与 venv）
> 评审标准：业界生产项目通用标准（依赖管理 / 测试 / 安全 / 可靠性 / 可观测性 / 工程化）

---

## 总体评价

这不是一个传统的"服务端项目"，而是一个 **Windows 桌面工具**（PyQt5 GUI + Flask 本地服务 + mitmproxy 抓包 + SQLite + MCP 服务的组合体）。按个人/团队内部工具的标准看，完成度不低——有类型标注、有 schema 版本管理、有设计文档、代码注释密度高；但按"业界生产项目"标准衡量，差距集中在：**零测试、无 CI、依赖管理混乱、安全面偏宽、日志/错误处理不统一**。

| 维度 | 评级 | 说明 |
|---|---|---|
| 功能完整度 | 较好 | 功能链条完整，变体/限速/抓包细节有深度 |
| 代码质量 | 中等 | 类型和注释好，但有死代码、无 lint 强制 |
| 测试 | 差 | 无任何自动化测试 |
| 依赖管理 | 差 | 双依赖文件互相矛盾，其中之一是坏的 |
| 安全性 | 偏差 | 0.0.0.0 + 无鉴权 shutdown + 开放代理 |
| 可观测性 | 中等 | 有滚动日志，但 print/logger 混用严重 |
| 工程化 | 差 | 无 pyproject、无 CI、无 LICENSE、构建靠 hack |
| 文档 | 中等 | README 尚可但与内部规则文档自相矛盾 |

---

## 🔴 高优先级问题

### 1. 完全没有自动化测试和 CI

全项目没有任何测试目录、没有 pytest、没有 `.github/workflows`。唯一的 `test.py` 是个手动 scratch 文件（还被 .gitignore 排除），`insert_test_db_data.py` 是手动灌数据的脚本。核心匹配逻辑（`MockRequestHandler`、变体轮换 `_select_variant`、Range 解析 `_parse_range`）都是纯逻辑、高度可测，却裸奔。任何重构（比如这个项目刚做完 sqlite 重构）都没有安全网。

### 2. 依赖管理是混乱且坏的

- **两个依赖文件互相矛盾**：`requirements.txt`（pipreqs 生成的最小集）和 `package.txt`（pip freeze 全量环境）。README 让用户装 `package.txt` —— 那是开发者本机 venv 的全量快照（含 ipython、jupyter 相关一堆无关包）。
- **`requirements.txt` 是坏的**：代码用了 `PyQt5.QtWebEngineWidgets`（`lib/webview_lib.py`、两个 dialog），但 requirements.txt 里**没有 PyQtWebEngine**（pipreqs 识别不出这个映射）。照它装的干净环境，打开数据管理窗口就 `ImportError`。
- **`package.txt` 是 UTF-16 编码**：Windows 上 `pip freeze > package.txt` 在 PowerShell 里生成的 UTF-16LE 文件直接提交了。pip 虽然能读 BOM，但这文件在 diff/编辑器里都是乱的。
- **`gen_requirements.py` 依赖 pipreqs**：该工具已基本停维护，识别不了 pywin32、PyQtWebEngine、Pillow↔PIL 之外很多映射 —— 生成的 requirements.txt 本身就是错误产物。
- **没有 pyproject.toml**：无项目元数据、无 dev/prod 依赖分离（pyinstaller、pipreqs 混在里面）。

### 3. 安全面偏宽

| 问题 | 位置 | 风险 |
|---|---|---|
| 两个 Flask 服务绑 `0.0.0.0` | `module/mock_server.py:300`、`module/app_server.py:49` | 整个局域网可达 |
| `/system/shutdown` 无鉴权且是 GET | `module/mock_server.py:267`、`module/app_server.py:38` | 同网段任何人访问一下 URL 就能杀服务；GET 改状态还会被预取/爬虫误触 |
| mitmproxy 监听 `0.0.0.0` | `qt_win/app.py` 中 `host: "0.0.0.0"` | LAN 上的开放正向代理，可被陌生人蹭用 |
| CORS `*` + 无鉴权 | `module/mock_server.py:215` | 任意网页可读静态资源/触发 shutdown |
| `shutdown_local_server` 按端口 `proc.terminate()` | `lib/utils_lib.py:449-457` | 端口被无关进程占用时会误杀别人的进程 |
| 下载无任何校验 | `lib/download_lib.py:395` | URL 来自抓包数据：无 scheme 白名单、无大小上限、`response.content` 全量进内存，一个超大响应直接撑爆内存 |
| Werkzeug dev server 当常驻服务 | `app.run(threaded=True)` | Flask 自带服务器明确声明 not for production；本地工具可接受但至少应绑 127.0.0.1 或用 waitress |

对比：`module/mcp_server.py:671` 很谨慎地绑了 `127.0.0.1` —— 说明作者知道该这么做，但三个服务的策略不一致。

做得**好**的反面例子是静态文件服务：`basename` + `realpath` 双重 containment 校验防目录穿越（`lib/static_file_lib.py:153-174`），这里反而很规范。

### 4. 无控制台版本中 `print()` 是颗雷

打包的主版本是 `-w`（无黑窗）构建（`build.py:111`），PyInstaller windowed 模式下 `sys.stdout`/`sys.stderr` 为 `None`，全项目 **80+ 处裸 `print()`**（包括 `start_server` 线程入口第一行 `module/mock_server.py:202`）。视 PyInstaller 版本行为，这些 print 要么静默丢失，要么抛 `AttributeError` 直接杀掉线程——`module/mcp_server.py:654` 里已经专门为 `sys.stdout.isatty()` 崩溃做过兼容，证明这个坑实际踩到过，但其余 print 全没处理。

### 5. 文档自相矛盾

- README 写 "Python 3.13.15"，`.devin/rules/code-rules.md` 写 "python 3.8 + pyqt5"，两份权威文档对 Python 版本的描述差 5 个大版本（代码本身按 3.8 兼容写的，全部用 `Optional`/`Union` 旧式写法）。
- README 从未提及 GUI 依赖 `appServer/` 下的前端构建产物（另一个仓库 mock-api-server-web-v3 的输出），也从未提 `requirements.txt`。

---

## 🟡 中优先级问题

### 6. 错误处理哲学有问题

`error_catch` 装饰器全局泛滥，统一吞掉异常、只记一行无堆栈的日志、返回兜底值（`lib/decorate.py`）。后果：

- 排障时看不到 traceback，`APP_LOGGER.error(f'...：{e}')` 只有 exception message（`lib/decorate.py:56,70`）；
- 静默错误返回：`is_app_running` 检查失败返回 `True` → 应用直接拒绝启动且不告诉为什么（`lib/app_lib.py:55`）；`__get_params_json_string` 失败返回 `'{}'` → 畸形 JSON body 会被错误匹配到空参变体；
- `get`/`set` 配置失败返回 `None`/`False`，调用方分不清"值不存在"和"IO 失败"。

### 7. 日志不统一

`APP_LOGGER.` 出现 54 次，`print(` 出现 80 次。业务关键路径（mock 命中失败、延时命中、节流命中、下载进度）全走 print 不进日志文件，无控制台版本里直接蒸发。没有级别配置、没有 request 日志、没有结构化日志。

### 8. 明确的 bug

- **下载日志状态写错**：`lib/download_lib.py` 两个 except 分支（`L444-451`、`L455-462`）都写 `"success": True`，下载失败的记录被标成成功，`get_output_data_list` 靠 `success` 过滤时会受影响（靠 `os.path.exists` 兜底才没出大错）。
- **静态资源 basename 扁平化碰撞**：URL 替换（`lib/static_file_lib.py:52`）和下载落盘（`lib/download_lib.py:371`）都只取 URL 最后一段文件名。`cdn.a.com/img/logo.png` 和 `cdn.b.com/other/logo.png` 会互相覆盖/命中同一份文件 —— 不同源站同名资源必然串。
- **`_should_use_throttled` 死分支**：`lib/static_file_lib.py:118-120`，`if self._is_image(...): return True; return True` —— `_is_image` 调用是死代码，重构残留。
- **schema 迁移无事务**：`_migrate_api` 连续多条 ALTER（`lib/db/api_data.py:64-80`）不在事务里，中途失败留下半迁移状态，且 `user_version` 没推进 → 下次启动重跑已成功的 ALTER → `duplicate column` 启动崩溃循环。

### 9. 可靠性细节

- 固定 `time.sleep(1)` 等服务就绪（`module/app_server.py:102`），不可靠；
- `is_local_server_running` 用 HTTP GET `/ping` 探测端口，每次探测都在服务端刷访问日志，retry 最多 20 次 = 刷屏；
- `create_thread` 装饰器丢弃返回值和异常，线程句柄不保留，无法 join/监管；
- 子进程（mitmproxy/mcp/mock server）拉起后没有存活监控，崩了 UI 仍显示 RUNNING；
- `mock_api_map` 只在 `start_server` 构建一次 → **运行期间改 mock 数据不生效必须重启服务**，README 没说明这个行为；
- `create_api_map` 里 `get_mock_api_data_list` 拆成 3 次全表查询（MITMPROXY/MCP/USER 各一次，`lib/app_lib.py:218-231`）+ 每行一次 `get_variants_by_api_id` 的 N+1 查询，数据量大了启动会慢。

### 10. 配置/数据文件管理薄弱

- `ConfigFileManager` 读写 JSON 无锁、非原子写（`lib/utils_lib.py:258,282`），写一半进程被杀 → 配置文件损坏；
- `mock_server_config.json` 等 JSON 损坏后 `json.loads` 直接抛异常让服务启动崩溃，没有损坏回退/备份机制；
- `backup` 工作目录创建了，但 `lib/backup_lib.py` 是死代码 —— 备份目录永远空转，承诺的备份能力不存在。

### 11. 死代码与冗余

| 项 | 说明 |
|---|---|
| `lib/backup_lib.py` | 无人引用 |
| `lib/file_lib.py`、`lib/hash_lib.py` | 只被 backup_lib 引用，等于全死；且两个文件重复实现同一个 file hash 函数 |
| `_is_video`（`lib/static_file_lib.py:348`） | 无人调用 |
| `STATIC_MATCH_CACHE_LIMIT`（`config/enum/SERVER.py:23`） | 定义未使用 |
| `qt_ui/*/win_ui.py` | pyuic5 生成代码提交入库（文件头自己都写 WARNING），应构建期生成或改用运行时 loadUi |
| `resources/` | 空目录 |
| `app-icon.png`（513KB） | 与 `assets/app.ico` 重复 |
| `test.py` | 应进 gitignore 的 scratch 文件残留在磁盘 |
| `qt_ui` vs `qt_win` | 新旧两套 UI 体系并存，命名也不能自解释 |

### 12. 工程化缺失清单

- 无 `LICENSE`、无 `CHANGELOG`、无 `CONTRIBUTING`；
- 无 lint/format/typecheck 配置（没有 ruff/black/mypy/flake8 任何配置文件，风格靠自觉）；
- 无 git hook / commit 规范，commit message 随意（"协议修改"、"类型定义修改"、"注释添加"）；
- 版本号两处维护（`config/globals.py` + 构建时 `_build_config.py`），无 bump 工具；
- `.gitignore` 明显是从 JS 项目模板复制的（`node_modules`、`dist-ssr`、`lerna-debug.log`），`logs` 还写了两遍；
- import 顺序混乱（`module/mock_server.py:37` 在业务 import 之后才 `import json`）；`build.py:85-90,134-139` 用裸字符串字面量当注释。

### 13. 构建/发布流程脆弱

- `build.py` 用**正则改写 PyInstaller spec 文件**来跳过 COLLECT —— spec 是 PyInstaller 内部产物，格式变了就静默失效；
- PyInstaller 本身不在任何依赖文件里 pin，版本漂移会导致 spec 格式假设失效；
- `appServer/` 前端产物不进构建脚本（`--add-data` 只有 schema 和 assets），分发产物依赖手工拷贝，无任何校验；
- 无签名、无安装包、无 checksum，dist 发布纯靠裸 exe。

### 14. 平台耦合未声明

`ctypes.windll`（`main.py:46`）、`win32gui/win32process`（`lib/app_lib.py`）、`os.startfile`（`qt_win/app.py:183`）、`--add-data` 的 `;` 分隔符 —— 整个项目**只能跑在 Windows**，README 的环境要求里没写，也没有平台 guard 给出友好报错。

### 15. 功能/设计上的小问题

- `VALID_HTTP_METHODS = ('GET', 'POST')` —— 只能 mock 两种方法，PUT/DELETE/PATCH 接口没法 mock，对 mock 工具是明显的功能短板；响应也固定 `jsonify` + 200，无法模拟非 200 状态码、自定义 Header、非 JSON body；
- `_get_api_match_meta` 未命中时 fallback 到"最后插入的匹配项"（`lib/server_lib.py:346-356`）—— 隐式行为，可能返回用户意料之外的数据，且无文档；
- `is_url_match` / `get_static_match_regexp` 把配置项当正则编译：`include_files` 里的 `.png` 的 `.` 没转义会匹配任意字符；配置里的非法正则会触发 ReDoS 或被 error_catch 静默吞掉；
- `get_ip_address()` 用 `gethostbyname(gethostname())`，装了 VPN/Docker/虚拟网卡时拿到的 IP 可能是错的，替换出的静态资源 URL 就废了（`module/mock_server.py:65`）；
- `white_download_log`/`white_log` 命名拼写错误（white→write），在公开函数名里；
- `/ping` 和 `/system/shutdown` 路由在两个服务里重复定义，没收敛到共享模块；
- LIKE 查询直接拼 `%input%`，输入含 `%`/`_` 时语义变化（`lib/db/api_data.py:225`），小但真实；
- `MockDBCache` 切换工作目录后旧连接未见显式关闭路径（GUI `select_work_dir` 不 close 旧 DB）。

---

## 🟢 做得不错的地方

- SQL 全部参数化，**没有注入问题**；LIKE 走参数绑定；
- 静态文件目录穿越防护是教科书式的（basename + realpath containment）；
- SQLite 用法相当讲究：WAL、busy_timeout、autocommit + 显式事务上下文、schema 版本号 + 增量迁移、连接幂等 close；
- `ThreadSafeLRUCache`、per-device 锁、跨进程 Event 优雅关闭信号链 —— 并发意识在线；
- 类型标注覆盖率高，`app_types/` 统一收编 TypedDict；
- `docs/` 里有成体系的重构计划和任务文档，这在个人项目里少见；
- `.gitignore` 关键点都覆盖了（venv、logs、dist、server/ 运行时数据没入库）。

---

## 改进建议（按投入产出排序）

1. **修依赖**：删掉 `package.txt` 方案，用 `requirements.txt`（补齐 `PyQtWebEngine`）+ `requirements-dev.txt`（pyinstaller/pipreqs），或直接上 `pyproject.toml` + uv/pip-tools。
2. **补测试**：至少给 `server_lib`（匹配/变体/Range）、`db` 层、URL 替换逻辑上 pytest；配一个最简 CI（lint + test）。
3. **收安全面**：非必要服务统一 `127.0.0.1`；`shutdown` 改 POST + 本地校验 token；下载加 scheme 白名单和大小上限（`stream=True` + 限制）；文档里写清 LAN 暴露面。
4. **统一日志**：消灭裸 `print`，全部走 logger；`error_catch` 记 `exc_info=True` 带堆栈。
5. **修明确 bug**：下载日志 `success` 字段、basename 碰撞、schema 迁移事务、`_should_use_throttled` 死分支。
6. **清理**：删死代码（backup_lib/file_lib/hash_lib）、删空 `resources/`、统一 `qt_ui`/`qt_win`、修 `white_` 命名。
7. **补齐工程文件**：LICENSE、CHANGELOG、lint 配置、版本号单一来源。
8. **文档对齐**：README 写明 Windows-only、前端产物依赖、真实 Python 版本、mock 数据热更新需重启。

---

## 处理进度跟踪

> 逐项处理时在此处勾选记录。

- [x] 依赖管理整改（requirements.txt / package.txt / pyproject.toml）— `5b4dc12` + `fc26535`
- [ ] 自动化测试补齐（pytest + CI）
- [x] 安全面收敛（绑定地址 / shutdown 鉴权）— `docs/plans/v0_1_5/security/security-hardening-plan.md`；下载校验另行立项
- [x] 日志统一（消灭裸 print / error_catch 带堆栈）— `01d35d5` + 本次提交
- [ ] 明确 bug 修复（下载日志 / basename 碰撞 / schema 迁移事务 / 死分支）
- [x] 死代码清理（backup_lib 删除；file_lib / hash_lib 保留仅删测试代码）— `docs/plans/v0_1_5/cleanup/dead-code-cleanup-plan.md`；`resources/.mitmproxy-ca.7z` 保留
- [x] 工程文件补齐（LICENSE / CHANGELOG / lint 配置）— `3e73ff0`
- [x] 文档对齐（README / code-rules）— `fc26535`（随 uv 迁移一并修订）

---

## 复查记录：2026-11-04（第二次复查）

> 复查范围：全量代码 + 首次报告逐项核验（含 PySide6 迁移、Qt Bridge 统一等报告后变更）
> 结论：勾选项目均已验证落地；未勾选项（测试/CI、§8 明确 bug）基本未动；另发现 5 个报告遗漏或新引入的问题。

### ✅ 已解决（本次验证通过）

| 首次报告条目 | 验证结果 |
|---|---|
| §2 依赖管理混乱 | `requirements.txt`/`package.txt` 双文件已移除，迁移 `pyproject.toml` + `uv.lock` 单源；PyQtWebEngine 问题随 PySide6 迁移消解；版本号改读 pyproject（`config/globals.py`） |
| §3 安全面（部分） | `app_server` 已绑 `127.0.0.1`；`/system/shutdown` 改 POST + 回环校验并收敛为 `register_system_routes` 共享注册（`lib/server_lib.py:428`）；README 新增「网络暴露面」声明 |
| §4/§7 print 与日志 | 运行时代码裸 `print` 已清零（残留仅脚本类 `build.py`/`tools/` 与 `__main__` 调试块）；分域 logger + `exc_info=True` 带堆栈；`-w` 下 `sys.stderr=None` 防护（`logger_lib.py:13-22`）；werkzeug access 日志降噪 |
| §11 死代码 | `backup_lib` 删除、`STATIC_MATCH_CACHE_LIMIT`/`_is_video` 删除、`white_`→`write_` 改名、`test.py` 移除、`app-icon.png` 归 `tools/`、`resources/.mitmproxy-ca.7z` 已入库 |
| §12 工程文件 | LICENSE / CHANGELOG / ruff 配置 / `.gitignore` 重写均已落地 |
| §5 文档矛盾 | README 已写 Python 3.13+ / Windows 10+ / uv；code-rules 已更新 PySide6 约定 |
| 报告外新增工作 | PySide6 6.10.3 迁移完成；Qt Bridge 信封/分发层统一（`bridge_lib.py`）；进程管理改进——ready/stop Event、join+terminate 兜底、退出清理流程、mock/mcp 进程句柄保留、webview 闪屏修复 |

### ❌ 仍存留（首次报告未关闭项）

**🔴 §8 明确 bug——四个全部原样未修：**

| Bug | 位置 | 说明 |
|---|---|---|
| 下载失败日志记 `success: True` | `lib/download_lib.py:452,463` | 两个 except 分支仍写 True，`get_output_data_list`(:54-59) 按 success 过滤语义仍错，靠 `os.path.exists` 兜底未出大错 |
| basename 扁平化碰撞 | `static_file_lib.py:53,161`、`download_lib.py:374` | 不同源站同名文件互相覆盖/串命中；`output_static_files`(:94) 导出同名覆盖同理 |
| `_should_use_throttled` 死分支 | `static_file_lib.py:117-121` | `if self._is_image(...): return True; return True` 原样 |
| schema 迁移无事务 | `base.py:58-71`、`mock_db.py:26-31`、`api_data.py:66-82`、`static_data.py:33-42` | 裸 `self._conn.execute(ALTER)`，`user_version` 最后才推进；中途失败 → 下次启动重跑已成功 ALTER → `duplicate column` 崩溃循环 |

**🟡 可靠性/安全残留：**

- §1 零测试、零 CI 未变；pytest 虽进 dev 依赖但无测试文件；
- 下载仍无校验：无 scheme 白名单、无大小上限、`response.content` 全量进内存（`download_lib.py:398,418`）；
- 配置 JSON 无损坏回退（`mock_server.py:110-111`、`request_catch.py:87-88` 裸 `json.loads`）；`ConfigFileManager` 仍无锁、非原子写、`get→None`/`set→False` 静默兜底（`utils_lib.py:261-284`）；
- `mock_api_map` 仅启动时构建（`mock_server.py:206`），改 mock 数据需重启服务，README 仍未说明；
- N+1：`get_mock_api_data_list` 仍 3 次分类型全表查询（`app_lib.py:218-233`）+ `create_api_map` 每行一次 `get_variants_by_api_id`（`mock_server.py:184`）；
- 就绪等待仍 `time.sleep(1)` + `/ping` 轮询（`app_server.py:103`、`qt_win/app.py:706,735,781`；日志刷屏已降噪）；
- `create_thread` 仍丢句柄/异常（`decorate.py:97-102`）；子进程拉起后无存活监控，崩溃后 UI 仍显示 RUNNING；
- `select_work_dir` 仍不 close 旧 DB（`qt_win/app.py:337-350`）；`shutdown_local_server` 仍按端口 terminate（`utils_lib.py:450-457`，安全文档已声明接受）；
- CORS 仍 `origins:"*"`（`mock_server.py:219,253`），已收窄至仅静态路由；
- 正则未转义问题原样：`is_url_match`/`get_static_match_regexp`（`utils_lib.py:370-375`、`download_lib.py:115`）；LIKE 未转义 `%`/`_`（`api_data.py:224-230`、`variants.py:289-294`）；
- `get_ip_address` 仍 `gethostbyname(gethostname())`（`utils_lib.py:60-65`）；`_get_api_match_meta` 隐式 fallback 最后插入项（`server_lib.py:350-360`）；
- `is_app_running` 失败静默返回 True（`app_lib.py:57`）；Werkzeug dev server 仍作运行时（本地工具可接受）；
- §13 构建：`build.py` 正则改写 spec 跳过 COLLECT 仍在（`:46-83`）；`appServer/` 产物仍不进 `--add-data`；仍无签名/checksum；
- §15 功能短板：`VALID_HTTP_METHODS=('GET','POST')` 未扩展；响应仍固定 `jsonify`+200；
- README 仍未提 `appServer/` 前端产物依赖（`.gitignore` 排除 `/appServer/*`，干净克隆后 WebView 弹窗无内容）；`insert_test_db_data.py` 仍留根目录；
- `qt_ui/*/win_ui.py` 生成物仍入库——已被 code-rules 文档化为约定（改 `.ui` 后 `pyside6-uic` 重新生成），降级为可接受项。

### 🆕 新发现/新引入问题（首次报告之外）

| # | 问题 | 位置 | 说明 |
|---|---|---|---|
| 1 | mitmproxy 启动失败误报 RUNNING | `qt_win/app.py:594-597` | `ready_event` 10s 超时仅记 warning 即 `emit('RUNNING')`；子进程早夭（配置损坏/端口冲突）时 UI 显示运行中 |
| 2 | 端口占用探测不一致 | `qt_win/app.py:566,683,765` vs `app_server.py:91-92` | 三个启动入口只查 `0.0.0.0`；app_server 已双地址探测。127.0.0.1-only 占用漏检，叠加问题 1 直接误报 RUNNING |
| 3 | 自定规则与代码矛盾 | `.devin/rules/code-rules.md` vs `qt_win/app.py:698`、`asyncio_mitmproxy_server.py:91`、`mcp_server.py:707` | 规则写"`Process` 必须 `daemon=True`"，4 处 Process 仅 `app_server.py:81` 落实；要么规则要么代码需修正（抓包进程保活刷数据 vs 退出 atexit join 卡死的取舍需写清） |
| 4 | 多进程共写同一日志文件 | `lib/logger_lib.py:25-43` | GUI + 3 子进程各自持 `RotatingFileHandler(logs/app.log)`，Windows 上轮转时他进程持句柄 → rename 失败 → logging 内部报错/丢日志 |
| 5 | BridgeDispatcher 每消息裸起线程 | `lib/bridge_lib.py:118` | 无上限、非 daemon、无句柄，高频消息线程无界增长 |

### 复查后建议优先级

1. 修 `success:True` 日志 bug + schema 迁移包事务（会真实咬人）；
2. 修 mitmproxy 超时误报 RUNNING（补 `is_alive()` 判断即可）；
3. 补 pytest：`server_lib` 匹配/变体/Range、`static_file_lib`、db 层均为纯逻辑；
4. 下载加 scheme 白名单 + `stream=True` 大小上限；
5. 其余（basename 碰撞、配置原子写、N+1、正则/LIKE 转义、GET/POST-only 扩展、daemon 规则对齐）按独立立项推进。

---

## 处理进展：2026-11-05

| 项 | 状态 | 说明 |
|---|---|---|
| 下载失败日志记 `success: True` | ✅ 已修复 | flag 修正 + 日志块收敛 `append_log` + `.part` 原子写 + compress 拆独立 try（方案：`docs/plans/v0_1_5/bugfix/download-log-success-flag-plan.md`）；连带消除「残缺文件自锁」与压缩失败语义污染 |
| schema 迁移无事务 | ✅ 已修复 | 迁移整体包 `_transaction`（`user_version` 与 DDL 原子提交）+ 全部 `ADD COLUMN` 幂等化；实测顺带修通 v≤2 老库升级必崩路径（`_init_schema` 预建最新形态表所致）（方案：`docs/plans/v0_1_5/bugfix/schema-migration-transaction-plan.md`） |
| `_should_use_throttled` 死分支 | ✅ 已收敛 | 非 bug：`bdf9f4c` 为修复视频全量下载拿到空 body 有意改为全类型节流，残留 `if _is_image: True` 半截分支；方法简化为 `return self.static_load_speed > 0`，docstring 记录探测机制废弃史（无 plan 文档，改动不足立项） |
| mitmproxy 启动失败误报 RUNNING（新发现 #1） | ✅ 已修复 | `start_catch_server` 拆分入口+同步实现；等待改 ready/死亡双通道轮询（早夭秒回）；失败三态统一 terminate+清理+弹窗+READY；入口 try/except 防 START_WAIT 卡死；`run_mitmproxy` 补 BaseException 落盘；`_cleanup_in_thread` 补孤儿兜底（方案：`docs/plans/v0_1_5/bugfix/mitmproxy-start-failure-running-plan.md`）；实测发现 `127.0.0.1`-only 占用在 Windows 下不崩而是静默劫持端口，仍归问题 #2 独立立项 |
| BridgeDispatcher 每消息裸起线程（新发现 #5） | ✅ 已修复 | thread-per-message → 单常驻 daemon worker + `Queue(512)` FIFO；`dispatch` 非阻塞入队、满/关闭丢弃并计数限流 warn；`shutdown()` 非阻塞排空（poison pill 队满挤位）；`_send_response` `_closed` 守卫防 deleted QObject emit；两弹窗 `closeEvent` 接入（方案：`docs/plans/v0_1_5/qt-bridge/bridge-dispatcher-worker-queue-plan.md`，refactor §5.5 TODO 收口） |
| Process daemon 规则矛盾（新发现 #3） | ✅ 已修复 | mitmproxy/mock/mcp 三处 `Process` 补 `daemon=True`（mitmproxy 顺带补 `name=`），`CODE_RULES.md` 补禁孙进程约束说明（方案：`docs/plans/v0_1_5/bugfix/process-daemon-true-plan.md`）；daemon 语义实测：父进程正常退出 atexit terminate 生效 |
