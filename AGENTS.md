# AGENTS.md

## 项目

mock-api-server：本地 mock 服务桌面工具。PySide6（Qt6 WebEngine）+ Flask + mitmproxy + SQLite + MCP，**仅支持 Windows 10+**。

## 命令

```bash
uv sync                    # 安装/同步依赖（含 dev 组）
uv run python main.py      # 运行应用
uv run ruff check .        # lint（要求归零）
uv run ruff check --fix .  # 自动修复
uv run python build.py     # PyInstaller 打包（产出带/不带黑窗两个 exe）
```

## 规则（改动代码前必读）

- `docs/rules/code/CODE_RULES.md` —— 代码规范（注释/类型/Qt 约定/命名风格）
- `docs/rules/git/COMMIT_MESSAGE.md` —— git 提交规范（Conventional Commits）

`docs/rules/` 内约定：按主题分子目录（`code/`、`git/`），文档统一全大写+下划线命名。

## 文档地图

- `docs/README.md` —— 项目文档总地图（plans / rules / reference / reports 四类）
- `docs/plans/README.md` —— 方案与实施文档存档索引（含 plan 文档归置与「实施记录/方案修正」栏目约定）
- `docs/reference/QT_BRIDGE.md` —— Qt Bridge 桥接协议分层说明
- `docs/reports/PROJECT_REVIEW_REPORT.md` —— 项目评审与复查记录（问题台账）
- `CHANGELOG.md` —— 版本变更记录

## 红线

- `qt_ui/*/win_ui.py` 是 `pyside6-uic` 生成物，不手改；改界面先改 `.ui` 再重新生成
- `multiprocessing.Process` 必须 `daemon=True`（非 daemon 子进程会卡死退出流程；现状与规则存在差异，以规则为准并推动对齐）
- 应用固定 `windowsvista` 样式（Qt6 windows11 样式跟随深色模式会冲突）
- 密钥、证书产物、`server/`、`system/`、`logs/` 等运行时数据不入库
- 工作目录 `server/` 内的 JSON 配置与 `mock.db` 为用户数据，不重置、不覆盖
