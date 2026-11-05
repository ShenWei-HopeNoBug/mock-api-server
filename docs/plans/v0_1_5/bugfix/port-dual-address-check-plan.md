# 端口占用探测双地址方案

> 关联文档：[PROJECT_REVIEW_REPORT.md](../../../reports/PROJECT_REVIEW_REPORT.md)「处理进展」🆕 新发现问题 #2
> 状态：待实施
> 范围：`lib/utils_lib.py`、`qt_win/app.py`、`module/app_server.py`、`tests/lib/test_utils_lib.py`、`docs/rules/code/CODE_RULES.md`

## 1. 背景

`check_local_connection(ip, port)` 用 `psutil.net_connections()` 按 `laddr.ip == ip 且 LISTEN` **精确匹配**——探 `'0.0.0.0'` 只见绑 `0.0.0.0` 的监听者，绑 `127.0.0.1` 的占坑进程完全不可见。

四个服务的绑定方式与探测现状：

| 服务 | 实际绑定 | 启动前探测 | 缺口 |
|---|---|---|---|
| mitmproxy | `0.0.0.0:8080`（`asyncio_mitmproxy_server.py:33`） | 仅 `0.0.0.0`（`app.py:588`） | 大 |
| mock | `0.0.0.0`（`mock_server.py:297` `app.run`） | 仅 `0.0.0.0`（`app.py:724`） | 大 |
| MCP | `127.0.0.1:8765`（`mcp_server.py:679` uvicorn） | 仅 `0.0.0.0`（`app.py:807`） | 中 |
| app_server | `127.0.0.1:5050` | 已双探（`app_server.py:96-97`） | 无——教训学过但未推广 |

**Windows 绑定语义**：`127.0.0.1:port` 独占存在时，再绑 `0.0.0.0:port` **不报 EADDRINUSE、bind 成功**——但回环包按最长前缀仍优先路由给 `127.0.0.1` 绑定者，wildcard 只能拿到非回环网卡流量。

**故障矩阵（127.0.0.1 占坑探测漏报后）**：

| 场景 | 当前后果 |
|---|---|
| 占 `127.0.0.1:8080` 起 mitmproxy | bind 成功 → ready 置位 → **显示 RUNNING，浏览器代理 127.0.0.1:8080 流量全进占坑者——静默劫持**（最恶劣） |
| 占 `127.0.0.1:5050` 起 mock | `/ping` 打到占坑者 → 20 次重试后「启动失败」（占坑者恰好回 200 → 静默 RUNNING） |
| 占 `127.0.0.1:8765` 起 MCP | uvicorn 绑 `127.0.0.1` 直接失败 → 白 spawn + 21s 重试 → 「启动失败」误导性提示（非「端口占用」） |

**必要性**：本地工具真实流量几乎全走回环，占坑者也几乎都是回环绑定（dev server/本地工具默认 `127.0.0.1`），单探 `0.0.0.0` 恰好漏掉最高发且后果最恶劣的一类。

## 2. 决策

| 项 | 决定 |
|---|---|
| 探测语义 | 新增 `is_local_port_occupied(port)`：单次 psutil 扫描，匹配 `laddr.ip ∈ {'0.0.0.0','127.0.0.1','::','::1'}`——通配 + 回环、IPv4/IPv6 全覆盖 |
| 探测集边界 | **不枚举本机全部网卡 IP**：`192.168.x.x` 占坑只会劫该网卡流量（回环不受影响），全量探测会把「别的网卡恰好同端口」的无辜服务误报成占用——宁可漏报不误报 |
| `::` 纳入理由 | Windows 下 `::` 监听默认双栈（IPV6_V6ONLY off）可劫 IPv4 回环；v6only=true 时属保守误报（宁可拦不错放） |
| 既有函数 | `check_local_connection`/`find_connection_process` 原样保留：精确匹配语义对「按已知 bind 地址找自己的监听进程」（shutdown 路径）依然正确 |
| 端口递增 | 不做：app_server 递增是 5050 为内部端口的特有策略；mitmproxy/mock/MCP 端口是用户配置值，递增会写偏配置语义 |
| 实施方式 | 当前分支单 commit，不自动提交 |

## 3. 改动清单

### 3.1 `lib/utils_lib.py`（`check_local_connection` 附近新增）

```python
# 本地服务启动前的端口占用探测集：通配 + 回环（IPv4/IPv6）
_LOCAL_LISTEN_ADDRS = ('0.0.0.0', '127.0.0.1', '::', '::1')

# 检测指定端口是否被本机通配/回环地址监听（服务启动前调用）
def is_local_port_occupied(port: int = 5000) -> bool:
  # 绑 0.0.0.0 会被 127.0.0.1 独占静默劫持回环流量；
  # 绑 127.0.0.1 会被 0.0.0.0 独占直接阻塞，两类都必须探
  for conn in psutil.net_connections():
    if conn.status != 'LISTEN' or not conn.laddr:
      continue
    if conn.laddr.port == port and conn.laddr.ip in _LOCAL_LISTEN_ADDRS:
      return True
  return False
```

### 3.2 `qt_win/app.py` 三处替换

`app.py:588`（mitmproxy）、`app.py:724`（mock）、`app.py:807`（MCP）：

```python
if is_local_port_occupied(self.catch_server_port):   # 其余两处同理
```

弹窗文案「端口已被占用」原样适用。import 行补 `is_local_port_occupied`。

### 3.3 `module/app_server.py`（:96-97）顺手统一

```python
while is_local_port_occupied(app_server_port):
```

语义不变，顺带白拿 IPv6 覆盖 + 少一次扫描；原双探注释语义并入 helper docstring。

### 3.4 `tests/lib/test_utils_lib.py` 追加用例

- monkeypatch `psutil.net_connections` 喂假行矩阵：`0.0.0.0`/`127.0.0.1`/`::`/`::1` 占坑 → True；`192.168.x.x` 占坑 → False（既定残余）；异端口 → False；非 LISTEN/空 laddr → 忽略；
- 真实 socket 自测：`socket.bind('127.0.0.1', 0)` 持口 → `is_local_port_occupied(real_port)` → True（无环境依赖）。

### 3.5 `docs/rules/code/CODE_RULES.md`

补规则：服务启动前端口探测必须用 `is_local_port_occupied`（双地址族），不得单探 `0.0.0.0`；`check_local_connection` 仅限「按已知 bind 地址找监听进程」用途。

## 4. 影响面

| 项 | 说明 |
|---|---|
| mitmproxy 启动 | `127.0.0.1:8080` 占坑从「静默 RUNNING + 流量劫持」变为启动前弹窗拒绝 |
| mock 启动 | 从「spawn → 21s 重试 → 误导性启动失败（或静默 RUNNING）」变为启动前弹窗拒绝 |
| MCP 启动 | 从「bind 崩溃 → 误导性启动失败」变为启动前弹窗拒绝 |
| app_server | 行为不变（已双探），边际扩展 IPv6 |
| 回归风险 | 低：`::` v6only 占坑属保守误报；单次扫描成本不增 |
| 行为性质 | 变严但全部是把隐性失败转显性拒绝，无正常路径回归 |

## 5. 行为等价与验收

| 场景 | 构造 | 预期 |
|---|---|---|
| 无占坑正常启动 | 四服务各启停 | 行为不变 |
| 回环占坑 | 外部进程 `socket.bind('127.0.0.1', 8080)` 后起 mitmproxy | 弹窗「端口已被占用」，不 spawn |
| 通配占坑 | 外部进程绑 `0.0.0.0:port` | 照旧弹窗（原有行为保持） |
| pytest | `pytest tests/lib/test_utils_lib.py` | 新用例全过 |

```bash
uv run pytest          # 全绿
uv run ruff check .    # 归零
```

## 6. 明确不做

- `check_local_connection`/`find_connection_process`/`shutdown_local_server`/`is_local_server_running` 任何改动；
- 端口冲突自动递增（仅 app_server 特有，不动）；
- 本机网卡 IP 全量枚举探测（误报代价大于漏报收益，见 §2）；
- mitmproxy/mock 绑定地址收敛 `127.0.0.1`（LAN 代理是既有功能面，独立议题）。

## 7. 实施记录

| 日期 | 步骤 | 结果 | 备注 |
|---|---|---|---|
| - | - | - | - |

## 8. 方案修正

| 日期 | 修正内容 | 原因 |
|---|---|---|
| - | - | - |
