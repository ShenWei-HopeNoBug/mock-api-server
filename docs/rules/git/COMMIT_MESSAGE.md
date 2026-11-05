# Git 提交信息规范

> 适用范围：本仓库全部 git commit。规范只约束新提交，不改写历史。
> 格式基准：Conventional Commits 标准式 `<type>(<scope>): <描述>`。

## 1. 格式

```
<type>(<scope>): <中文描述>
<空行>
<可选正文：说明"为什么"，不写"改了什么"（diff 自己会说话），约 72 字符折行>
<空行>
<可选 footer>
```

- `<type>`：必填，英文小写，从 §2 白名单取值；
- `(<scope>)`：可选，英文小写，从 §3 建议集取值，超出集合的新 scope 视为合理扩展；
- `<描述>`：必填，单行 ≤ 50 字符（中英文同计），中文动词开头（新增/修复/统一/收敛/迁移/删除/更新），句尾不加句号；
- 正文/footer 之间、subject/body 之间均以空行分隔。

## 2. type 白名单

| type | 用途 | 典型场景 |
|---|---|---|
| `feat` | 新功能、新能力 | 新增下载代理配置、新增变体复制工具 |
| `fix` | bug 修复 | 修正错误日志字段、修复闪屏、修复崩溃 |
| `docs` | 纯文档变更 | 方案文档、README、评审报告、注释文档化 |
| `refactor` | 不改变外部行为的重构 | 抽离公共层、Mixin 拆分、收敛重复实现 |
| `perf` | 性能优化 | 消除 N+1、缓存、提速 |
| `style` | 格式/命名调整（不改语义） | lint 修复、改名、排版 |
| `test` | 测试代码与测试基建 | pytest 用例、测试夹具 |
| `build` | 依赖与构建打包 | pyproject/uv.lock、build.py、PyInstaller spec |
| `chore` | 其他杂务 | .gitignore、工程配置、清理杂项 |
| `revert` | 回滚既有提交 | revert 某 commit |

判型原则：一次提交多种性质时按**主导改动**归类；功能改动顺带的文档更新不拆 `docs`。

## 3. scope 建议集

| scope | 覆盖范围 |
|---|---|
| `mock` | mock 匹配/响应/延时逻辑（`mock_server`、`server_lib`） |
| `static` | 静态资源匹配/缓存/限速（`static_file_lib`、`throttle_lib`） |
| `db` | SQLite 层（`lib/db/*`、schema、迁移） |
| `bridge` | Qt Bridge 协议与分发（`bridge_lib`、`TInteractObject`） |
| `webview` | WebEngine 弹窗与交互 |
| `catch` | mitmproxy 抓包链路（`request_catch`、`asyncio_mitmproxy_server`） |
| `mcp` | MCP 服务与工具集 |
| `download` | 静态资源下载链路 |
| `build` | 打包构建（`build.py`、spec） |
| `deps` | 依赖管理（pyproject、uv.lock、requirements） |
| `qt` | Qt 窗口/控件层通用改动 |
| `docs` | 文档体系自身 |

## 4. footer 约定

- `BREAKING CHANGE: <说明>`：声明破坏性变更（接口/配置/数据格式不兼容）；
- `Generated with [Devin](https://devin.ai)` + `Co-Authored-By: Devin <...>`：agent 提交保留该 trailer；
- 引用评审/方案条目可写 `Refs: docs/reports/PROJECT_REVIEW_REPORT.md §8`、`Refs: docs/plans/v0_1_5/bugfix/xxx-plan.md`。

## 5. 正误例（本仓库真实提交改写对照）

| 原提交 | 按规范改写 | type |
|---|---|---|
| 修复webview弹窗首屏黑闪、小画面闪动及剪贴板失效 | `fix(webview): 修复弹窗首屏黑闪、小画面闪动及剪贴板失效` | fix |
| 迁移Qt绑定至PySide6 6.10.3（Chromium 134） | `build(deps): 迁移 Qt 绑定至 PySide6 6.10.3` | build |
| Qt Bridge 分发层统一：抽离 BridgeDispatcher 并接入两弹窗 | `refactor(bridge): 抽离 BridgeDispatcher 并接入两弹窗` | refactor |
| 安全面收敛：app_server绑定127.0.0.1、shutdown改POST回环校验 | `fix(mock): 收敛 app_server 绑定地址并加固 shutdown 端点` | fix |
| 新增复查记录：评审报告补充 2026-11-04 二次复查结果 | `docs: 评审报告补充二次复查记录` | docs |
| 死代码清理：backup_lib删除与杂项清理 | `chore: 删除 backup_lib 死代码与杂项清理` | chore |
| 日志统一：运行时print全量迁移分域logger | `refactor: 运行时 print 全量迁移分域 logger` | refactor |
| white_→write_ 改名（3 处） | `style(download): 修正 white_ 拼写为 write_` | style |
| 修改版本号 | `chore: 更新版本号` | chore |

反例（均不合规）：

```
修复了几个问题              # 无 type
Fix: xxx                    # type 必须小写
fix：xxx                    # 冒号必须是半角
fix(mock)：修复匹配。       # 句尾不加句号
feat(mock,db): xxx          # scope 单一，不并列
```

## 6. 其他约定

- commit message 语言：subject/正文用中文，type/scope/footer 标记用英文；
- 一个 commit 只做一件事；方案文档落地按各自「提交拆分」节执行，不自动提交；
- **agent 不主动执行 `git commit`**：未得到明确提交指示时只完成工作区改动，由人确认后提交（与 `docs/plans/README.md`「落地执行不自动 git commit」一致）；
- 合并提交（merge commit）保持默认生成信息，不套用本规范；
- 规范文档自身变更按 `docs:` 提交。
