# 桌宠 Live2D 模型外置配置方案

> 状态：已实施
> 关联：[desktop-pet-live2d-plan](desktop-pet-live2d-plan.md)（模型语义耦合分析见该会话记录）
> 范围：`app_env.py` / `qt_win/live2d_pet.py` / `qt_win/app.py` / `tools/live2d_spike.py` / `tests/` 改动

## 1. 背景与目标

当前模型路径写死在 `app_env.LIVE2D_MODEL_JSON`，且 `live2d_pet.py` 内硬编码 `Idle`/`TapBody`/`Body` 三个模型语义字符串与 200×300 窗口尺寸——这些是对模型内容的约定，换模型要改多处代码。

目标：**换模型 = 编辑 `system/pet_model.json` + 放置模型文件，代码零改**。`system/` 是既有约定目录（`config/work_file.py` 的 `history.json` 同址，`.gitignore` 已排除，打包后位于 exe 同目录）——打包产物用户也可自行换模型。

## 2. 配置定义

`system/pet_model.json`（应用工作目录下，与 `system/history.json` 同基）：

```json
{
  "model_json": "assets/live2d/hiyori/Hiyori.model3.json",
  "window_w": 200,
  "window_h": 300,
  "idle_group": "Idle",
  "tap_group": "TapBody",
  "hit_area": "Body"
}
```

| 字段 | 默认 | 语义 |
|---|---|---|
| `model_json` | bundled Hiyori | 模型入口 json。`assets/` 前缀 → `_resource_path`（打包内嵌）；绝对路径 → 原样；其他相对路径 → `os.path.abspath`（与 `system/` 同 CWD 基，打包后=exe 目录） |
| `window_w/h` | 200 / 300 | 立绘窗口逻辑尺寸，宽高比按模型比例配 |
| `idle_group` | `Idle` | 待机随机动作组；**空值 = 无待机循环**（模型无此组时配空防 no-op 轮询） |
| `tap_group` | `TapBody` | 点按动作组；空值 = 点按播任意动作 |
| `hit_area` | `Body` | 点按命中区；空值 = 不判定命中、直接播 tap_group |

模型兼容性约束（配置无法绕过，文档写明）：`.moc3` 须 ≤ Cubism SDK 5-r.5（live2d-py 1.0.0 内置 Core）；视线跟随需模型绑了 Drag 参数，无绑定时注视失效但功能不崩。

## 3. 加载与降级（`app_env.py`）

```python
PET_MODEL_CONFIG_PATH = os.path.join(SYSTEM_DIR-ish, 'pet_model.json')  # './system/pet_model.json'

def load_pet_model_config() -> dict:
  # 读 json → 逐字段校验类型并回默认值（部分字段坏不拖垮整体）
  # 文件缺失/解析失败 → 全字段默认值
  # model_json 按 §2 规则解析为绝对路径
```

**回退链**：配置的 `model_json` 文件不存在 → 回退 bundled Hiyori 默认 → 也不存在 → `FileNotFoundError` 上抛 → 走 `_create_pet` 既有降级球路径。

**可发现性**：首次进入桌宠模式时若 `system/pet_model.json` 不存在 → 写入默认值模板（注释字段含义写在 key 命名里即可，JSON 无注释）。用户能看到、能改。

## 4. `live2d_pet.py` 改造

构造签名改为接收配置（字段独立参数，不引 dict 类型耦合）：

```python
def __init__(self, model_json, on_restore, on_quit, on_build_menu=None,
             window_w=200, window_h=300, idle_group='Idle',
             tap_group='TapBody', hit_area='Body'):
```

- `WINDOW_W/H` 类常量 → 构造参数，`setFixedSize(window_w, window_h)` 用实例值
- `initializeGL`/`paintGL` 的 `'Idle'` → `self._idle_group`；**空值跳过待机随机动作**
- `_on_pet_tap`：`hit_area` 非空才 `IsAreaHit`，`tap_group` 非空才 `StartRandomMotion(tap_group)` 否则 `StartRandomMotion()`
- `OCC_*`/`ALPHA_THRESHOLD`/膨胀半径不动（按渲染像素自适应，与模型无关）

## 5. `app.py` 接线

- `_create_pet`：`cfg = app_env.load_pet_model_config()` → 展开传参；首次进入时先 `_ensure_pet_model_config()` 写模板
- **换模型生效时机**：`_pet` 懒建复用，配置变化不重载。加一条轻量检测：`enter_pet_mode` 比对上次创建时的配置快照（`self._pet_cfg_key = json.dumps(sorted(cfg))`），变了 → `deleteLater() + None` 重建——换模型免重启，GL 重载仅在配置真变时发生

## 6. `tools/live2d_spike.py`

`MODEL_JSON` 改用 `app_env.load_pet_model_config()['model_json']`，与主链路同一来源。

## 7. 测试（tests/，pytest 既有基建）

新增 `tests/test_pet_model_config.py`（或并入 app_env 测试）：`monkeypatch.chdir(tmp_path)` + 写 `system/pet_model.json`，覆盖：

- 文件缺失 → 全默认；JSON 坏 → 全默认
- 部分字段非法类型 → 该字段回默认，其他保留
- `assets/` 前缀 → `_resource_path` 基；绝对路径原样；相对路径 → CWD 基
- 配置 model 不存在 → 回退 bundled 路径

## 8. 改动清单

| 文件 | 改动 |
|---|---|
| `app_env.py` | +`PET_MODEL_CONFIG_PATH`/`PET_MODEL_DEFAULT`/`load_pet_model_config`/`_ensure_pet_model_config`；`LIVE2D_MODEL_JSON` 保留作 bundled 默认路径 |
| `qt_win/live2d_pet.py` | 构造收 6 参数；类常量→实例值；idle/tap/hit 空值降级分支 |
| `qt_win/app.py` | `_create_pet` 读配置传参；`enter_pet_mode` 配置快照比对重建 + 首进写模板 |
| `tools/live2d_spike.py` | `MODEL_JSON` 走同一 loader |
| `tests/test_pet_model_config.py` | loader 纯逻辑 4 项用例 |

## 9. 验收

- 无 `system/pet_model.json`：进桌宠 → 自动生成模板 + Hiyori 正常显示（回归现状）
- 改 `model_json` 指向另一模型目录（≤5-r.5 moc3）→ 回桌宠模式直接生效
- 配置 `idle_group: ''` → 模型静止但可点按/拖拽；`hit_area: ''` → 点按直接播动作
- 配置坏 JSON/缺文件 → 回退 Hiyori 或球，无闪退
- 打包产物：exe 同目录 `system/pet_model.json` + `live2d_models/` 相对路径模型生效
- `uv run ruff check .` 归零 + `uv run pytest` 全绿

## 10. 实施记录

| 日期 | 步骤 | 结果 | 备注 |
|---|---|---|---|
| 2026-11-14 | 全量实施 | `app_env.py` 新增 `load_pet_model_config`/`ensure_pet_model_config`（逐字段校验+三分支路径解析+模板自写）；`live2d_pet.py` 构造 6 参数化（窗口尺寸转实例值，idle/tap/hit 空值降级）；`app.py` `_create_pet` 配置注入 + `enter_pet_mode` 快照比对重建；spike 改走同一 loader；`tests/test_app_env.py` 6 用例 | ruff 归零；pytest 6/6 全绿 |

## 11. 方案修正

| 日期 | 原方案 | 实际做法 | 原因 |
|---|---|---|---|
