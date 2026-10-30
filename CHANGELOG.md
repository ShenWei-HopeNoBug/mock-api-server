# Changelog

本项目遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 规范。

> v0.1.5 之前的记录由 git 提交历史与 `dist/` 产物目录回填，仅记要点。

## [Unreleased]

### Added

- 工程文件补齐：MIT `LICENSE`、`CHANGELOG.md`、`.editorconfig`、`.python-version`
- `pyproject.toml` 补充 `readme`/`license`/`authors` 元数据与 ruff lint 配置（`E4,E7,E9,F,I` 保守规则集）

### Changed

- `.gitignore` 重写：移除 JS 模板残留，补齐 `.venv`、`*.pyc`、`.ruff_cache`、`.pytest_cache`、`mockServer.*.spec` 等 Python 产物忽略项
- `README.md` 补充开发工作流命令一览

## [0.1.5] - 2026-10-31

### Added

- `PROJECT_REVIEW_REPORT.md` 项目评审报告留档
- `docs/README.md` 文档地图与归置规范；`docs/v0_1_5/` 方案文档体系

### Changed

- 依赖管理迁移至 `uv` + `pyproject.toml` + `uv.lock`，移除 `requirements*.txt`、`package.txt`、`gen_requirements.py`
- 版本号单源化：`config/globals.py` 改由 `tomllib` 读取 `pyproject.toml`
- `.gitattributes` 统一文本 LF 行尾

## [0.1.4] - 2026-10-08

### Changed

- 代理/下载配置界面优化，异常 catch 处理抽象，协议处理完善

## [0.1.3] - 2026-09-06

### Added

- 静态资源限速体系：令牌桶、漏桶、Sliding Window、Progressive Delay、Random Jitter 策略
- 响应变体唯一启用支持

### Changed

- SQLite 存储重构：mock 数据由 JSON 文件迁入 `mock.db`（schema 版本化管理）
- Python 升级至 3.13.15，依赖包版本同步调整

### Fixed

- 视频全量下载失败问题修复

## [0.0.5] - 2026-07-08

### Changed

- 编辑 mock 数据的 webview 页面替换为 web-v3 版本

## [0.0.3] - 2025-05-04

### Added

- 早期版本：PyQt5 GUI + Flask 本地 mock 服务，mock 数据管理与代理抓包基础能力
