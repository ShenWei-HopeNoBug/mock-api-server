# Mock API Server

## 简介

以本地 mock 数据为数据源，启动本地 HTTP 服务按路由规则匹配请求并返回模拟响应，服务于前端开发与接口联调。所有 mock 接口统一挂载在 `/api` 路由前缀下，前端只需将请求目标指向本地服务即可命中对应的 mock 数据。

### 功能简述

**1. 三种 mock 数据导入方式**

- **代理抓包自动录入**：内置 mitmproxy 代理，流量经过时自动捕获 JSON 响应并写入数据库，支持配置 URL 过滤规则
- **MCP 服务由 Agent 导入**：启动本地 MCP 服务，Agent 可通过 MCP 工具集直接创建/修改/删除 mock 接口及响应变体
- **GUI 可视化管理**：内嵌 WebView 数据管理界面，支持 mock 接口与响应变体的分页查询、增删改、批量删除、复制、拖拽排序等完整操作

**2. 工作目录隔离的 SQLite 存储**

每个工作目录拥有独立的 SQLite 数据库，可按场景/项目切换不同工作目录，各目录的 mock 数据互不干扰。

**3. 响应变体与轮播模拟**

单条 mock 接口支持配置多个响应变体。请求时通过 Header `Mock-Server-Device-Id` 传入 UUID 触发变体模式：同一 Device ID 的请求按变体顺序依次切换返回不同响应，适合模拟轮询/状态流转场景；不传则始终返回默认响应。变体支持独立超时配置，空闲超时后自动重置为首个变体。

**4. 静态资源本地化**

- **URL 自动替换**：mock 服务启动后自动将响应体中匹配配置扩展名的远程静态资源 URL 替换为本地地址，由内置静态文件服务提供，无需依赖远程服务器即可完整渲染页面
- **批量下载与压缩**：一键扫描所有 mock 数据中引用的静态资源 URL，批量下载到本地，支持图片自动压缩、下载代理配置与动态超时调整

**5. 响应延时模拟**

支持全局响应延时与单条接口独立延时两级配置，另支持静态资源按文件大小限速加载，用于测试 loading 态、超时处理及弱网场景。

**6. MCP 工具集**

本地 MCP 服务向 Agent 暴露 mock 接口与响应变体的完整 CRUD 工具，另含变体跨接口复制能力。

> 注：mock 数据在 mock 服务启动时加载为匹配映射，运行期间增删改 mock 数据需重启服务后生效。

## 环境要求

- 操作系统：64 位 Windows 10 及以上（含 Windows 11）；不支持 Windows 7 / 8 / 8.1（Qt6/PySide6 最低要求 Windows 10）
- Python 3.13+
- [uv](https://docs.astral.sh/uv/)（依赖与环境管理，`pip install uv` 或 winget 安装）
- 前端构建产物（可选）：数据管理界面（WebView 弹窗）依赖 `appServer/` 静态产物，由前端仓库 `mock-api-server-web-v3` 构建后拷贝至本目录；未提供时应用正常启动，仅数据管理弹窗无内容

## 快速开始

### 安装依赖

```bash
uv sync
```

`uv sync` 会按 `uv.lock` 自动创建 `.venv` 并安装全部运行依赖与开发依赖（打包工具链 PyInstaller 包含在 dev 依赖组中）。

### 运行

```bash
uv run python main.py
```

## 目录结构

| 目录 | 说明 |
|---|---|
| `main.py` | 应用入口（QApplication、全局异常、单实例检查） |
| `module/` | 本地服务：mock 服务、APP 前端服务、mitmproxy 抓包、MCP 服务 |
| `lib/` | 业务逻辑层：DB 访问、静态文件处理、下载、Qt Bridge、日志、工具函数 |
| `qt_win/` | PySide6 窗口与弹窗逻辑层 |
| `qt_ui/` | 界面层：`.ui` 源文件 + `pyside6-uic` 生成物（不手改）+ 样式 |
| `config/` | 常量、枚举、路由、菜单与工作文件定义 |
| `schema/` | SQLite 建表脚本（按版本 `vN.sql`） |
| `appServer/` | 前端构建产物目录（由 web-v3 仓库生成，不入库） |
| `docs/` | 项目文档总目录（plans / rules / reference / reports，地图见 `docs/README.md`） |
| `resources/` | mitmproxy CA 证书压缩包等静态资源 |
| `tools/` | 杂项工具脚本（ico 转换等） |
| `server/` | 默认工作目录（`config/` JSON 配置、`data/mock.db`、`static/`、`download/`、`output/`），运行时生成不入库 |
| `system/` `logs/` | 运行时数据：历史配置与滚动日志，不入库 |

## 工具命令

### 打包

运行项目目录中的 `build.py` 脚本进行打包，基于 PyInstaller 构建，一次产出两个 exe（带控制台黑窗和不带黑窗版本），共用同一份 `site-packages` 依赖目录：

```bash
uv run python build.py
```

产物输出在 `dist/` 目录下，包含可执行 exe、`site-packages` 依赖目录以及内置的 `schema/` 和 `assets/` 资源。

## 开发工作流

```bash
uv sync                    # 安装/同步依赖（含 dev 组）
uv run python main.py      # 运行应用
uv run python build.py     # PyInstaller 打包
uv run ruff check .        # lint 检查
uv run ruff check --fix .  # 自动修复可修项
uv add <pkg>               # 新增运行依赖
uv add --dev <pkg>         # 新增开发依赖
```

## 网络暴露面

各本地服务的默认端口、绑定地址与局域网（LAN）可达范围如下：

| 服务 | 默认端口 | 绑定地址 | 局域网内他人能做什么 |
|---|---|---|---|
| mitmproxy 抓包 | 8080（界面可配） | `0.0.0.0` | 将本机用作开放正向代理（抓包开启期间） |
| mock 服务 | 5000（界面可配） | `0.0.0.0` | 查询 mock 数据、拉取本地静态资源 |
| APP 前端服务 | 5050（被占自动递增） | `127.0.0.1` | 不可达（仅本机） |
| MCP 服务 | 8765（界面可配） | `127.0.0.1` | 不可达（仅本机） |

- `/system/shutdown` 仅接受来自 `127.0.0.1` 的 `POST` 请求，局域网设备无法远程关闭服务；
- mitmproxy 与 mock 服务按设计需对局域网可达（被测设备直连）；在不可信的网络环境（如公共 WiFi）中请勿开启抓包与 mock 服务；
- `resources/.mitmproxy-ca.7z` 为 mitmproxy CA 证书压缩包，供移动设备安装信任以抓取 HTTPS 流量。

## 文档

- [docs/README.md](docs/README.md) —— 项目文档总地图（方案存档 / 规范 / 参考 / 报告四类）
- [docs/reference/QT_BRIDGE.md](docs/reference/QT_BRIDGE.md) —— Qt Bridge 桥接协议分层说明
- [docs/reports/PROJECT_REVIEW_REPORT.md](docs/reports/PROJECT_REVIEW_REPORT.md) —— 项目评审与复查记录（问题台账）
- [AGENTS.md](AGENTS.md) —— agent 与协作者入口索引（规则、命令、红线）

## License

MIT，见 [LICENSE](LICENSE)。