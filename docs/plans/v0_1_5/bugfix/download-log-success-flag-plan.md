# 下载失败日志 success 字段修复方案

> 关联文档：[PROJECT_REVIEW_REPORT.md](../../../reports/PROJECT_REVIEW_REPORT.md)「§8 明确的 bug」首项、「复查记录：2026-11-04」❌仍存留-🔴
> 状态：已实施（2026-11-05）
> 范围：`lib/download_lib.py`（单文件）

## 1. 背景

`download_server_static` 下载循环内四个 `download_log.append` 块系复制粘贴产物，`except ConnectionError`（:447-454）与 `except Exception`（:458-465）两个分支把失败记录错写 `"success": True`。

`success` 字段唯一直接消费方是同文件 `get_output_data_list`（:53-59）：`success and os.path.exists(static_path)` 双条件过滤后汇入导出列表（`qt_win/output_static_dialog.py:220`）。目前靠 `os.path.exists` 兜底未出大错，但与同一循环的两处连带缺陷叠加会构成真实危害：

- **残缺文件 + 成功标记**：`fl.write` 写盘中途失败（磁盘满/权限）或 `compress_image` 异常 → 截断文件留盘 + 日志记 `success:True` → 被当作"下载成功"导出；
- **坏状态自锁**：残缺文件残留后，下次下载 `os.path.exists(assets_path)` 直接跳过（:380，同理 `get_download_ready_assets` :185）→ 永不重试；
- **compress 语义污染**：压缩失败与下载失败混在同一 try 内，flag 修对后压缩失败会把"文件完整可用"记成 `success:False`，既不导出也不重试。

## 2. 决策（方案拟定，实施前与用户确认）

| 项 | 决定 |
|---|---|
| 修复方式 | flag 修正 + 日志块收敛为 `append_log` 内层函数 + `.part` 原子写 + compress 拆独立 try，四件套一次做 |
| 历史日志 | 不迁移（导出侧 `os.path.exists` 兜底，存量虚报影响可忽略） |
| `.part` 残留 | 可不清理（不阻塞重试）；except 分支顺手 remove 列为可选项 |
| 实施方式 | 当前分支，单 commit，不自动提交 |

## 3. 改动清单

### 3.1 日志 append 收敛为内层函数 + flag 修正

`download_server_static` 内 `write_log` 旁新增内层函数，四个 append 块替换为单行调用（字段构造与现状完全一致）：

```python
# 追加下载日志条目（各分支共用，仅 success/message 为差异点）
def append_log(success: bool, message: str = '') -> None:
  download_log.append({
    "url": asset,
    "save_path": assets_path,
    "file_name": file_name,
    "proxies": proxies,
    "success": success,
    "message": message,
  })
```

| 位置 | 改动 |
|---|---|
| 非 200 分支（:402-409） | `append_log(False, f"下载失败! STATUS_CODE:{response.status_code}")`（语义不变） |
| 成功分支（:431-438） | `append_log(True)` |
| `except ConnectionError`（:447-454） | `append_log(False, f"下载连接异常! ConnectionError:{e}")` ← 核心修复 |
| `except Exception`（:458-465） | `append_log(False, f"下载报错! ERROR:{e}")` ← 核心修复 |

### 3.2 落盘原子化（:417-420）

直写正式路径 → 先写临时文件再原子改名：

```python
# 将文件写入指定位置（先写 .part 再原子改名，中断不留残缺文件）
part_path = f'{assets_path}.part'
with open(part_path, 'wb') as fl:
  fl.write(assets_data)
os.replace(part_path, assets_path)
```

`.part` 文件不匹配 `os.path.exists(assets_path)` 的存在性检查（:185、:380），中断残留可被下次下载自然重试覆盖；`_resolve_file`/`send_from_directory` 消费端永远只见完整文件。

### 3.3 compress 拆独立 try（:422-428）

`compress_image` 移出主 try，压缩失败仅记 warning 保留原图，不污染 `success` 语义（文件完整可用 ≠ 下载失败）：

```python
# 压缩下载图片（压缩失败不影响文件可用性，仅记 warning）
if compress:
  try:
    compress_image(input_path=assets_path, output_path=assets_path, quality=80)
  except Exception as e:
    DOWNLOAD_LOGGER.warning(f'压缩图片失败，保留原图：{file_name} {e}')
```

`compress_image` 自带 `error_catch` 吞异常返回 False，外层 try 作双保险。

### 3.4（可选）except 分支清理 `.part` 残留

两个 except 分支内各加一行，保持 static 目录整洁：

```python
if os.path.exists(part_path):
  os.remove(part_path)
```

`part_path` 变量需在循环体前段（`assets_path` 赋值后）提前定义，供 try/except 共同引用。

## 4. 提交拆分

单 commit：§3 全部（含可选项按实施时确认结果取舍）+ 本方案文档与 `docs/plans/README.md` 登记 + `docs/reports/PROJECT_REVIEW_REPORT.md` 复查记录对应项勾选。不自动提交，由人确认后提交。

## 5. 验收

```bash
uv run ruff check .   # 保持归零
```

| 场景 | 构造 | 预期 |
|---|---|---|
| 非 200 | 返回 404 的静态资源 URL | 日志 `success:False`，无文件，下次重试 |
| 连接失败 | 不可达域名/错误代理 | `success:False`，无文件 |
| 写盘中断 | 模拟 `open`/写盘异常 | `success:False`，仅 `.part` 残留、无正式文件 |
| 压缩失败 | 模拟 `compress_image` 抛异常 | 文件完整、`success:True` + warning 日志 |
| 正常路径 | 常规下载 | `success:True`、文件完整、无 `.part` 残留 |
| 导出 | 混合成败日志跑导出弹窗 | 失败项不进导出列表 |

## 6. 明确不做

- basename 扁平化碰撞、`output_static_files` 导出同名覆盖（§8 姊妹问题，另行立项）；
- `_should_use_throttled` 死分支、schema 迁移事务（§8 其余条目）；
- 下载 scheme 白名单、`stream=True` 大小上限（归安全方案「下载校验」立项）；
- 历史 `download/*.json` 错误日志迁移；
- `get_download_ready_assets` 的 basename 提取方式（`asset.split('/')[-1]`，同属 basename 碰撞项）。

## 7. 实施记录

| 日期 | 步骤 | 结果 | 备注 |
|---|---|---|---|
| 2026-11-05 | 按 §3 全部实施（含 §3.4 可选项 `.part` 残留清理） | `ruff check` 归零 | 单文件改动；`part_path` 提前至 `assets_path` 赋值后定义供 try/except 共用 |

## 8. 方案修正

| 日期 | 修正内容 | 原因 |
|---|---|---|
| — | — | — |
