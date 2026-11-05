# 安全面收敛方案

> 关联文档：[PROJECT_REVIEW_REPORT.md](../../../reports/PROJECT_REVIEW_REPORT.md)「§3 安全面偏宽」「改进建议-3」
> 状态：待实施
> 范围：`module/app_server.py` / `module/mock_server.py` / `lib/server_lib.py` / `qt_win/app.py` / `README.md` / `CHANGELOG.md`

## 1. 背景

项目含 4 个本地服务，绑定策略不一致：

| 服务 | 绑定 | 连接方 | LAN 暴露是否功能需要 |
|---|---|---|---|
| mitmproxy | `0.0.0.0`（`qt_win/app.py:577`） | 移动设备设其为 HTTP 代理 | 是（显式代理即本功能） |
| mock_server | `0.0.0.0`（`mock_server.py:305`） | 被测设备直连 `/api`、`/static`；响应内静态资源 URL 重写至 LAN IP | 是 |
| app_server | `0.0.0.0`（`app_server.py:54`） | 仅本机 QWebEngineView（URL 全写死 `127.0.0.1`） | 否 |
| mcp_server | `127.0.0.1` | 本机 Agent | 已收敛 |

关键事实：`module/request_catch.py` 的 mitmproxy 插件只记录流量写库、不做请求转发——mock server 是被测设备直连的独立服务，不能简单绑回环。

残留攻击面：

- `/system/shutdown` 无鉴权且为 GET（`mock_server.py:270`、`app_server.py:41`）：LAN 内任意设备一条 URL 即可杀服务；GET 改状态还存在预取/爬虫误触风险；
- `shutdown_local_server` 按端口 `proc.terminate()`（`lib/utils_lib.py:450-457`）：端口被无关进程占用时存在误杀可能。

## 2. 决策（已与用户确认）

| 项 | 决定 |
|---|---|
| 绑定收敛范围 | 最小集：仅 app_server → `127.0.0.1`；mock_server / mitmproxy 维持 `0.0.0.0`（功能需要） |
| shutdown 加固 | 保留端点：改 `POST` + `request.remote_addr == '127.0.0.1'` 校验；不用 token、不删端点换进程句柄 |
| `resources/.mitmproxy-ca.7z` | 保留入库（mitmproxy CA 证书包，供移动设备安装信任以抓取 HTTPS），README 中说明用途 |
| 实施方式 | 当前分支，单 commit，不自动提交 |
| 下载校验 | 本次不做（另行立项） |

## 3. 改动清单

### 3.1 `lib/server_lib.py`：新增 `register_system_routes`

共享注册函数：`/ping`（GET 返回 pong）+ `/system/shutdown`（POST，先校验 `request.remote_addr == '127.0.0.1'`，否则 403；通过后延时触发 `on_shutdown` 回调）。两服务的重复路由收敛到单点、加固只写一遍，同时消掉报告 §15「/ping 与 /system/shutdown 路由重复」项。

### 3.2 `module/app_server.py`：绑定收敛（3 处连带）

| 位置 | 改动 |
|---|---|
| `:54` | `app.run(host='0.0.0.0')` → `host='127.0.0.1'` |
| `:97` | 端口占用探测同时查 `0.0.0.0` 与 `127.0.0.1` 两个 laddr（任一被占都会阻塞 bind） |
| `:65` | `shutdown_local_server` 补 `ip='127.0.0.1'`（`find_connection_process` 按 `laddr.ip` 匹配） |
| `:37-50` | 本地 `/ping` + `/system/shutdown` 路由换 `register_system_routes` |

### 3.3 `module/mock_server.py`

`:266-279` 本地 `/ping` + `/system/shutdown` 路由换 `register_system_routes`；`app.run` 维持 `0.0.0.0`。

### 3.4 `qt_win/app.py`

`:732`、`:857` 两处 `requests.get` → `requests.post`（GUI 触发 shutdown 的调用方）。

### 3.5 文档

- `README.md` 新增「网络暴露面」节：四服务表格（端口 / 绑定 / 暴露范围 / LAN 内他人能做什么）+「不可信局域网勿开抓包与 mock 服务」提示 + `resources/.mitmproxy-ca.7z` 用途说明；
- `CHANGELOG.md` Unreleased 补记；
- `docs/reports/PROJECT_REVIEW_REPORT.md` 勾选「安全面收敛」（随本方案 commit 落地）。

## 4. 提交拆分

单 commit：§3 全部 + 本方案文档与 `docs/plans/README.md` 登记。不自动提交，由人确认后提交。

## 5. 验收

```bash
uv run ruff check .                 # 保持归零
# dev 冒烟：GUI 启动 → 打开数据管理窗口，WebEngine 正常加载 127.0.0.1:5050 前端
# mock server 启动后：
#   curl http://127.0.0.1:5000/ping                     → pong
#   curl http://127.0.0.1:5000/system/shutdown          → 405
#   curl -X POST http://127.0.0.1:5000/system/shutdown  → 正常关闭
#   curl -X POST http://<LAN-IP>:5000/system/shutdown   → 403
# GUI「停止」按钮正常关闭两个服务
```

## 6. 明确不做

- 下载校验（URL scheme 白名单、`stream=True` + 大小上限）：另行立项；
- bind_host 配置项 / adb reverse 回环模式文档、token 鉴权、删除端点换进程句柄关服务；
- CORS 收紧（`/system`、`/api` 本不在 CORS resources 内，加固靠 remote_addr 而非 CORS）、Werkzeug 换 waitress；
- `get_ip_address()` 改 UDP 出网卡探测（遇到 static_host 取错 IP 再加）；
- `qt_ui`/`qt_win` 改名、`main_win/win_ui.ui` 漂移修复（另行立项）。

## 7. 已知残留风险

`shutdown_local_server` 仍按端口 `terminate`：端点收紧为仅回环后触发者只剩本机 GUI，误杀面已收敛；若端口恰被无关进程占用且本机发起 shutdown 仍可能误杀，进程句柄方案留作后续。

## 8. 实施记录

| 日期 | 步骤 | 结果 | 备注 |
|---|---|---|---|
| 2026-11-01 | §3 全部落地 | `lib/server_lib.py` 新增 `register_system_routes`；`app_server` 绑定 `127.0.0.1` + 双地址端口探测 + `shutdown_local_server(ip='127.0.0.1')`；两服务系统路由收敛单点；`qt_win/app.py` 两处改 POST；`README` 新增「网络暴露面」；`CHANGELOG` Unreleased 补记；评审报告勾选 | `ruff check` 归零；test_client 实测 `GET /ping`→200、`GET shutdown`→405、回环 `POST`→200、LAN `POST`→403；四模块 import 冒烟通过 |

## 9. 方案修正

| 日期 | 修正内容 | 原因 |
|---|---|---|
| （待填） | | |
