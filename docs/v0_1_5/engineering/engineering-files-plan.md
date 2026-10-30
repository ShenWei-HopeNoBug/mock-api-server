# 工程文件补齐方案

> 关联文档：[PROJECT_REVIEW_REPORT.md](../../../PROJECT_REVIEW_REPORT.md)「§12 工程化缺失清单」「改进建议-7」
> 状态：待实施
> 范围：`.gitignore` / `LICENSE` / `CHANGELOG.md` / `pyproject.toml` / `.editorconfig` / `.python-version` / `README.md` / 存量 lint 基线

## 1. 背景

评审报告指出工程化缺失：无 `LICENSE`、无 `CHANGELOG`、无 lint 配置、`.gitignore` 为 JS 模板残留（含 `node_modules`/`lerna-debug`/`dist-ssr`，`logs` 重复两遍，且未忽略 `.venv`、`*.pyc`、`.ruff_cache` 等 Python 产物）。版本号单一来源已在 dependency 方案 Step 2 中顺带解决（`globals.py` 读 `pyproject.toml`）。

本机实测基线（ruff 0.17.3）：

- 默认规则全量 642 报错，其中 500+ 为 UP 系 pyupgrade 现代化建议（`UP045`×178、`UP006`×129、`UP009`×88 等），属"代码现代化"而非缺陷；
- 保守规则集 `E4,E7,E9,F,I` 基线 **56 报错，52 可自动修**：`I001` import 排序×48、`F841` 未用变量×3、`F541` 无效 f-string×2、`E713`×1、`E721`×1、`F401`×1；
- 存量最长行 198 字符，30 个文件超 88 列；
- **ruff formatter 硬编码 4 空格缩进，不认 `indent-width`**，与项目 2 空格风格冲突，本项目不做 `ruff format`。

## 2. 决策（已与用户确认）

| 项 | 决定 |
|---|---|
| LICENSE | MIT，署名 shenwei / ShenWei-HopeNoBug |
| ruff 规则范围 | 保守档 `E4,E7,E9,F,I`，只抓真 bug 类问题；UP 现代化另开议题 |
| CI | 本次不做，留给补测试议题统一上 |
| CONTRIBUTING | 不做，以 README「开发工作流」小节替代 |

## 3. 改动清单

| # | 文件 | 动作 | 说明 |
|---|---|---|---|
| 1 | `.gitignore` | 重写 | Python 骨架 + 项目段；删 JS 残留、`logs` 去重；新增 `.venv*`、`*.py[co]`、`*.egg-info`、`.ruff_cache`、`.pytest_cache`、`.mypy_cache`、`mockServer.*.spec`、`.devin/mcp_config.local.json`、`Thumbs.db`；保留 `/system /static /server /web /output.* /api_dict.json /main.spec /test.py /appServer/* /_build_config.py /dist /logs` |
| 2 | `LICENSE` | 新建 | MIT，shenwei，2026 |
| 3 | `CHANGELOG.md` | 新建 | Keep a Changelog 中文格式；按 git log + `dist/` 历史目录名回填 v0.0.5~v0.1.5；`[Unreleased]` 段起步 |
| 4 | `pyproject.toml` | 增改 | 补 `readme`/`license`/`authors` 元数据；新增 `[tool.ruff]` 与 `[tool.ruff.lint]` 配置 |
| 5 | `.editorconfig` | 新建 | `root=true`；utf-8 / lf / 2 空格 / 去尾空格 / 末行换行；`*.md` 例外保留尾空格 |
| 6 | `.python-version` | 新建 | 内容 `3.13`，uv/PyCharm 自动识别 |
| 7 | `README.md` | 增改 | 「开发工作流」小节：`uv sync` / `uv run python main.py` / `uv run python build.py` / `uv run ruff check .` |
| 8 | 存量 lint 基线 | 清理 | `ruff check --fix` 自动修 52 处；手工复核 `F841`×3、`E721`×1 |
| 9 | 登记勾选 | 增改 | 本文档落地 + `docs/README.md` 登记 `engineering/` 域 + 评审报告勾选 |

### 3.4 pyproject.toml 目标配置

```toml
readme = "README.md"
license = {text = "MIT"}
authors = [{name = "shenwei"}]

[tool.ruff]
target-version = "py313"
line-length = 120
indent-width = 2
extend-exclude = [".venv","dist","build","server","static","web","resources","appServer","data","output","system"]

[tool.ruff.lint]
select = ["E4","E7","E9","F","I"]
```

`.devin/mcp_config.local.json` 从 `.git/info/exclude` 挪入 `.gitignore`（规则可见化）。

## 4. 提交拆分

| Commit | 内容 |
|---|---|
| 1 | 清单 1~7 全部工程文件 + 本方案文档 + 文档地图登记（lint 基线 56 报错暂存，不挡路） |
| 2 | 清单 8：`ruff check --fix` + 手工修正，`ruff check` 归零（独立 commit 保持工程文件 diff 干净） |

## 5. 验收

```bash
uv run ruff check .          # 0 errors
uv sync                       # 不受影响
git status                    # .venv / __pycache__ / 运行产物均已忽略
uv run python build.py        # 打包链路不断（import 排序属机械改动）
```

## 6. 明确不做

- GitHub Actions CI（留补测试议题）；
- `ruff format`（formatter 4 空格硬编码，与项目风格冲突）；
- `CONTRIBUTING.md`、`SECURITY.md`（单人内部工具价值低）;
- UP 系 pyupgrade 全仓现代化修复（~500 处，如需做另开议题单独提交）。

## 7. 实施记录

| 日期 | 步骤 | 结果 | 备注 |
|---|---|---|---|
| （待填） | | | |

## 8. 方案修正

| 日期 | 修正内容 | 原因 |
|---|---|---|
| （待填） | | |
