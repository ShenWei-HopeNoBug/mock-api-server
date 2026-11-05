# 依赖管理整改方案（两步走）

> 关联文档：[PROJECT_REVIEW_REPORT.md](../../../reports/PROJECT_REVIEW_REPORT.md)「改进建议-1」
> 状态：Step 1 已完成（`5b4dc12`）；Step 2 已实施待提交
> 范围：`requirements.txt` / `package.txt` / `requirements-dev.txt` / `.gitattributes` / `pyproject.toml` / `README.md` / `config/globals.py` / `gen_requirements.py`

## 1. 背景

评审报告指出依赖管理混乱（详见评审报告 §2）：

- `requirements.txt` 为 pipreqs 生成产物，缺 `PyQtWebEngine` 直接依赖（webview 对话框实际在用），干净环境按它安装会 `ImportError`；
- `package.txt` 为 UTF-16LE + BOM 的全量 `pip freeze` 快照（80+ 包，含 ipython/jupyter 等开发机污染包），README 却引导新人装它；
- `gen_requirements.py` 依赖 pipreqs，其产物天生不可靠；
- `.gitattributes` 为空文件，无文本/eol 声明，行尾编码全靠自觉；
- 版本号两处维护（`config/globals.py` + 构建期 `_build_config.py`）。

本机环境基线：Python 3.13.15（`.venv`），依赖版本以 `package.txt` 快照为对账基准。

## 2. 目标与拆分

依赖声明收敛为可信单源，删除错误流程。拆为两步，中间设人工验收门：

- **Step 1 — requirements.txt 单源化**（本方案实施范围）：纯文件增删，不引入新工具链。做完即为自洽终态，即使 Step 2 不做也成立。
- **Step 2 — uv 迁移**（冻结）：`pyproject.toml` + `uv.lock`，Step 1 验收通过且确认迁移后另行展开，骨架见 §5。

## 3. 改动总清单

| 文件 | 动作 | 说明 |
|---|---|---|
| `requirements.txt` | 删除重建 | `git rm` 后以 UTF-8 无 BOM + LF 重写，补 `PyQtWebEngine` |
| `requirements-dev.txt` | 新建 | UTF-8 + LF |
| `.gitattributes` | 写入内容 | 原为空文件 |
| `package.txt` | `git rm` | B 步骤对账完成后删除 |
| `gen_requirements.py` | `git rm` | pipreqs 产物不可靠，一并删 |
| `README.md` | 修订 | 安装命令、dev 依赖说明、删 package.txt 节 |

代码零改动；`.venv` 不动；应用照常运行。

## 4. Step 1 — requirements.txt 单源化

### 4.1 对账

全量 import 扫描 × `package.txt` 快照比对，确认直接依赖清单无遗漏（已知缺 `PyQtWebEngine`；`pywin32` 走 `win32gui`/`win32process`/`win32con` import，pipreqs 同样识别不出）。

### 4.2 requirements.txt 目标内容

版本号全部从 `package.txt` 快照抄取，只列直接依赖，不列 `PyQt5-Qt5` / `PyQt5_sip` / `PyQtWebEngine-Qt5` 等传递依赖：

```text
Flask==3.1.3
Flask_Cors==4.0.1
mcp==2.0.0
mitmproxy==12.2.3
Pillow==10.4.0
psutil==6.1.0
PyQt5==5.15.11
PyQtWebEngine==5.15.7
pywin32==312
Requests==2.32.3
starlette==1.6.0
uvicorn==0.52.4
```

### 4.3 requirements-dev.txt 目标内容

```text
pyinstaller==6.11.1
pyinstaller-hooks-contrib==2024.10
pipreqs==0.4.13
```

### 4.4 .gitattributes

原文件为空，写入：

```text
* text=auto eol=lf
```

不做全仓 renormalize：行尾随后续文件修改惰性归一，保持本次 diff 干净。后续如需一次性归一，`git add --renormalize .` 单独提交。

### 4.5 README 修订点

- 「安装依赖」改为 `pip install -r requirements.txt`；
- 补充说明打包/工具链依赖：`pip install -r requirements-dev.txt`；
- 删除「初始化 package.txt」整节。

### 4.6 Step 1 验收（人工执行）

```bash
# 干净环境安装 + 全链路 import 冒烟
python -m venv .venv-check && .venv-check\Scripts\activate
pip install -r requirements.txt
python -c "from qt_win.app import MainWindow"

# dev 依赖可用
pip install -r requirements-dev.txt && pyinstaller --version

# 仓库内无 UTF-16/UTF-32 文本文件
git ls-files | xargs file | grep -iE "utf-16|utf-32"   # 应无输出
```

## 5. Step 2 — uv 迁移（冻结，骨架留档）

> 前置条件：Step 1 验收通过 + 确认迁移。届时细节重新展开讨论。

- 手写 `pyproject.toml`（`[tool.uv] package = false`；`[dependency-groups] dev` 放 pyinstaller/pytest/ruff；**首版直接依赖全部 `==` 钉死当前版本**，保证解析结果与现状等价，后续升级走 `uv lock --upgrade-package`）；
- `uv lock` 生成并提交 `uv.lock`；删除旧 `.venv`，`uv sync` 重建；
- 删除 `requirements*.txt`（需要时 `uv export -o requirements.txt` 随时导出）；
- `config/globals.py` 的 `version` 改为 `tomllib` 读 `pyproject.toml`（打包态文件不存在时兜底 `'v0.0.0'`），解决版本号两处维护；
- 文档对齐：README 换 `uv sync` / `uv run python main.py` / `uv run python build.py`；`.devin/rules/code-rules.md` 的 "python 3.8" 改 3.13；
- 验收：干净目录 `uv sync` → import 冒烟 → `uv run python build.py` 打包链路不断 → 仓库内无非 UTF-8 文本文件。

**主要风险**：`>=` 宽松约束导致 uv 解析出与现状不同的版本树（mitmproxy/mcp 快迭代包行为差异）→ 以首版全 `==` 对冲。

## 6. 实施顺序

```
4.1 对账（确认无遗漏直接依赖）
  → 4.2 ~ 4.4 文件改动（requirements / dev / gitattributes）
  → git rm package.txt + gen_requirements.py
  → 4.5 README 修订
  → 4.6 人工验收
  → 提交（建议单 commit；renormalize 如做则独立 commit）
```

## 7. 影响面

| 项 | Step 1 | Step 2（冻结） |
|---|---|---|
| 风险 | 几乎为零 | 依赖版本漂移（`==` 对冲后近零） |
| 日常命令 | `pip install -r requirements*.txt`，无变化 | 换 `uv sync` / `uv run` / `uv add` |
| `.venv` | 不动 | 删除重建，PyCharm 重建索引 |
| 代码改动 | 无 | 仅 `globals.py` 一处 |
| Git | 6 个文件改动 | 删 requirements、增 pyproject.toml / uv.lock |
| 不可逆点 | package.txt / gen_requirements.py 删除（git 历史可查） | `uv sync` 会清掉 venv 中不在 lock 内的包 |

## 8. 实施记录

| 日期 | 步骤 | 结果 | 备注 |
|---|---|---|---|
| 2026-10-31 | §4.1 对账 | 除 PyQtWebEngine 外新发现 `werkzeug` 直接依赖（`app_types/static_file_types.py:8` Headers）；`PyQt5_sip` 判定为传递依赖剔除 | requirements.txt 最终 13 条直接依赖 |
| 2026-10-31 | §4.2 ~ §4.5 文件改动 | requirements.txt 重建（13 条）；requirements-dev.txt 新建；.gitattributes 写入 `* text=auto eol=lf`；package.txt / gen_requirements.py 删除；README 修订 | `git ls-files --eol` 确认三文件 index 均为 LF |
| 2026-10-31 | §4.6 验收 | 干净 venv `pip install -r requirements.txt` 成功；`from qt_win.app import MainWindow` 冒烟通过；dev 安装后 `PyInstaller --version` = 6.11.1；无 UTF-16/32 漏网文件 | 已提交 `5b4dc12` |
| 2026-10-31 | §5 uv 迁移实施 | uv 0.13.6 安装；`pyproject.toml` 创建（13 条直接依赖全 `==`，dev 组 = pyinstaller/hooks-contrib/pytest/ruff/uv，`package = false`）；`uv.lock` 生成（96 包）；`uv sync` 收敛 `.venv`（清除开发机污染包） | 发现 `pyqt5-qt5` 解析漂移问题，以 `constraint-dependencies` 修正，详见 §9 |
| 2026-10-31 | §5 版本单源化 + 文档对齐 | `globals.py` 改 `tomllib` 读 pyproject（兜底 `v0.0.0`）；README 换 `uv sync`/`uv run` 工作流；code-rules.md Python 版本更正为 3.13；`requirements*.txt` 删除 | 应用户要求版本同步提升至 `0.1.5` |
| 2026-10-31 | §5 验收 | 干净目录（工作树副本）`uv sync` 96 包安装成功；`MainWindow` 冒烟 + `globals.version = v0.1.5` 通过；`uv run python build.py` 打包成功，产出 `dist/mockServer.20261031044326-v0.1.5/`（两个 exe + site-packages） | 二进制关键面核对：Qt 5.15.2/PyQt 5.15.11、mitmproxy-rs/windows 0.12.11 与快照一致 |

## 9. 方案修正

| 日期 | 修正内容 | 原因 |
|---|---|---|
| 2026-10-31 | `pyproject.toml` 增加 `[tool.uv] constraint-dependencies`：`pyqt5-qt5==5.15.2`、`pyqt5-sip==12.17.0`、`pyqtwebengine-qt5==5.15.2`、`mitmproxy-rs==0.12.11`、`mitmproxy-windows==0.12.11` | 直接依赖全 `==` 只能保证直接依赖不漂移，传递依赖仍会解析到最新版：① `pyqt5-qt5`/`pyqtwebengine-qt5` 被解析到 5.15.19，但该版本无 win_amd64 wheel 导致 `uv sync` 直接失败；② `mitmproxy-rs`/`windows`、`pyqt5-sip` 等二进制面漂移存在行为差异风险，钉死到 package.txt 快照版本保证迁移环境与现状等价。纯 Python 工具类传递依赖不约束，跟随正常解析 |
| 2026-10-31 | dev 依赖组不含 `pipreqs` | `gen_requirements.py` 已删除，pipreqs 产物不可靠且不再有需要它的流程 |
| 2026-10-31 | dev 依赖组包含 `uv==0.13.6` | uv 装进项目 `.venv` 使用；若不在依赖组内，`uv sync` 会把 venv 里的 uv 本体一并清除 |
| 2026-10-31 | `pyproject.toml` 版本号定为 `0.1.5` 而非快照 `0.1.4` | 用户要求版本提升；`globals.version` 经 `tomllib` 读出为 `v0.1.5`，构建产物名同步带 `v0.1.5` |
