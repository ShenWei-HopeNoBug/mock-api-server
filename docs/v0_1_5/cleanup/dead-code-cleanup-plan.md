# 死代码清理方案

> 关联文档：[PROJECT_REVIEW_REPORT.md](../../../PROJECT_REVIEW_REPORT.md)「§11 死代码与冗余」「改进建议-6」
> 状态：待实施
> 范围：`lib/{backup_lib,file_lib,hash_lib}.py` / `config/work_file.py` / `lib/download_lib.py` / `config/enum/SERVER.py` / `lib/static_file_lib.py` / `app-icon.png` / `tools/ico_transform.py`

## 1. 背景

评审 §11 死代码清单落地前需修正两处事实：

- `resources/` **非空目录**：内含 `resources/.mitmproxy-ca.7z`（mitmproxy CA 证书包，git 已跟踪，代码零引用）。经用户确认为保留资产，由安全方案在 README 中说明用途，本方案不处理；
- `qt_ui` vs `qt_win` 非"两套 UI 体系"：实为分层架构（`qt_ui/` = `.ui` 源 + `pyside6-uic` 生成物 + 样式 + 复合组件，`qt_win/` = dialog 逻辑层），`.devin/rules/code-rules.md` 已记录分层约定，本方案不做改名合并。

## 2. 决策（已与用户确认）

| 项 | 决定 |
|---|---|
| `qt_ui`/`qt_win` | 不改名、不合并 |
| `resources/.mitmproxy-ca.7z` | 保留 |
| `app-icon.png` | 移入 `tools/`（作为 `ico_transform.py` 输入源，保留 ico 再生成能力） |
| 实施方式 | 当前分支，单 commit，不自动提交 |

## 3. 改动清单

### 3.1 死代码三件套

- 删 `lib/backup_lib.py`、`lib/file_lib.py`、`lib/hash_lib.py`（引用关系已验证：仅 backup_lib 引用 file_lib，hash_lib 零引用；动手前全仓 grep 兜底一次）；
- `config/work_file.py`：`WORK_DIR_DICT` 摘除 `BACKUP_DIR` 项 + 删 `BACKUP_DIR` 常量（否则 `create_work_files` 每次仍建 `server/backup/` 空目录）；存量用户工作目录不动。

### 3.2 `white_` 命名修正

`lib/download_lib.py`：`white_download_log` → `write_download_log`（:193 定义、:347 唯一调用点）、嵌套 `white_log` → `write_log`。无外部引用，零风险。

### 3.3 散件

- 删 `STATIC_MATCH_CACHE_LIMIT`（`config/enum/SERVER.py:23`，定义未使用）；
- 删 `_is_video`（`lib/static_file_lib.py:349`，无人调用；`_is_image` 在用，勿误删）；
- `app-icon.png` `git mv` → `tools/`，同步 `tools/ico_transform.py` 的 `from_path`；
- 磁盘 `test.py` 顺手删除（已 gitignore，不进 commit）。

## 4. 提交拆分

单 commit：§3 全部 + 本方案文档与 `docs/README.md` 登记 + `PROJECT_REVIEW_REPORT.md` 勾选「死代码清理」。不自动提交，由人确认后提交。

## 5. 验收

```bash
uv run ruff check .                           # 保持归零
python -c "from qt_win.app import MainWindow"  # 冒烟
# 新建工作目录：server/backup/ 不再生成
```

## 6. 明确不做

- `main_win/win_ui.ui` 与生成物漂移修复（缺 MCP 控件、重生成即崩）：另行立项；
- `_should_use_throttled` 死分支、basename 碰撞、schema 迁移事务、下载 `success` 字段：归「明确 bug」清单；
- `.gitignore` JS 模板残留条目（归工程化项）；
- `resources/` 目录本体（含保留的 `.mitmproxy-ca.7z`）。

## 7. 实施记录

| 日期 | 步骤 | 结果 | 备注 |
|---|---|---|---|
| （待填） | | | |

## 8. 方案修正

| 日期 | 修正内容 | 原因 |
|---|---|---|
| （待填） | | |
