# 桌宠模型外置化变更（beta 收敛）

> 状态：待实施
> 范围：`config/work_file.py` / `build.py` / `app_env.py` / `qt_win/app.py` / `tests/test_app_env.py` / `tools/live2d_spike.py` / `assets/live2d→pets`（迁移）
> 前案：[desktop-pet-model-config-plan](desktop-pet-model-config-plan.md)（本文修正其"内嵌兜底"设计，前案正文不动）

## 1. 背景与现状

Live2D 属 beta 能力，不应默认开放。现状链路：

| 层 | 位置 | 现状 |
|---|---|---|
| 打包 | `build.py` | `--add-data "assets;assets/"` 全量进包，含 `assets/live2d/hiyori/` 官方示例模型 ~4.8MB；`--collect-all live2d` 收 live2d-py 渲染库本体 |
| 配置 | `app_env.load_pet_model_config()` | 三层兜底全指内嵌 hiyori：配置缺失→静默内嵌；JSON 损坏→warning 回内嵌；配置路径不存在→warning 回内嵌 |
| 模板 | `app_env.ensure_pet_model_config()` | 首进桌宠写 `./system/pet_model.json`，`model_json` 为 `assets/` 内嵌路径 |
| 目录 | `config/work_file.py` | `WORK_DIR_DICT` 注册 work_dir 子目录（config/data/static/download/output），`create_work_files`/`check_work_files` 启动时完整性检查+自动创建 |
| 降级 | `app.py` | 两级已在跑：`Live2DPetWindow` 构造异常→图标球；show 后 `init_failed`→图标球 |
| 测试 | `tests/test_app_env.py` | 5 例断言内嵌兜底语义 |

## 2. 目标语义

```
pet_model.json 存在 且 model_json 解析出存在的文件 → Live2DPetWindow
其余一切情况（未配置/损坏/路径不存在/GL失败）      → DesktopPetWindow 图标球
```

- 无内嵌兜底、无静默 hiyori；未配置=正常态（不打 warning，beta 隐藏）；配错=warning 留痕
- 用户启用路径：模型放 `<work_dir>/pets/`，编辑 `system/pet_model.json`

## 3. 目录布局

| 位置 | 内容 | 说明 |
|---|---|---|
| `<work_dir>/pets/` | 自动创建的空目录 | 用户放模型的位置；dev=`server/pets/`，打包默认=`<exe>/server/pets/`（自定义 work_dir 随用户数据走） |
| 仓库根 `pets/` | `pets/hiyori/` 测试模型 | 入库、仅 dev 用；`server/` 是 gitignore 运行时数据不可放 |
| `./system/pet_model.json` | 配置文件 | 位置不变（随 history.json），避免迁移 |

## 4. 逐项改动

### 4.1 `git mv assets/live2d pets`

仓库根测试资产（dev-only），保留 git 历史；`assets/` 仅剩 `app.ico`；`pets/` 命名绕开 `live2d` 包名冲突且模型无关。

### 4.2 `config/work_file.py`

新增 `PETS_DIR = r'/pets'` 常量 + `WORK_DIR_DICT` 注册 `"PETS_DIR"`——既有 `create_work_files`/`check_work_files` 机制接管自动创建与完整性检查。

### 4.3 `build.py`

- `--add-data "assets;assets/"` → `--add-data "assets/app.ico;assets/"`（-4.8MB）
- `--collect-all live2d` **保留**（live2d-py 为渲染运行时，删了用户放模型也渲不了）

### 4.4 `app_env.py`

- 删 `LIVE2D_MODEL_JSON` 常量与三层内嵌兜底，`model_json` 默认 `''`：
  - 配置缺失 → `''` 静默（正常态）；JSON 损坏 → `''`+warning；路径不存在 → `''`+warning（warning 含解析后完整路径，提示用户该放哪）
- `_resolve_pet_model_path(raw, work_dir)`：删 `assets/` 前缀分支；绝对路径→原样；相对路径→`os.path.join(work_dir, raw)`
- `load_pet_model_config(work_dir=DEFAULT_WORK_DIR)` 加参
- `_PET_MODEL_DEFAULT['model_json']` → `'pets/hiyori/Hiyori.model3.json'`（work_dir 相对）

### 4.5 `app.py`

- `_create_pet()`：`load_pet_model_config(work_dir=self.work_dir)`；`model_json` 为空直接返回 `DesktopPetWindow`（未配置=正常态，跳过 Live2D 尝试，不打 warning）；其余走原"尝试→异常→球"链路
- `enter_pet_mode()` 的 cfg_key 调用同步传 `self.work_dir`；两级降级、config-diff 免重启重建机制不动

### 4.6 `tests/test_app_env.py`

- 三处兜底断言 `LIVE2D_MODEL_JSON` → `''`
- `assets/` 前缀解析用例 → work_dir 基相对路径解析用例
- 无 frozen 用例需求（解析基统一为 work_dir，无环境分叉）

### 4.7 `tools/live2d_spike.py`

主链路同源生效，仅补注释说明模型路径走 `<work_dir>/pets/`。

## 5. 使用流程

**打包用户**：启动后 `server/pets/` 已自动创建（空）→ 放模型（如 `server/pets/hiyori/`）→ 首次进桌宠生成 `system/pet_model.json` 模板 → 改 `model_json` 指向 `pets/<目录>/<model3.json>` → 再进桌宠生效（config-diff 重建免重启）。

**dev**：`server/pets/` 同建但空；一次性 `cp -r pets server/`（复刻打包布局），或 `model_json` 写绝对路径。

## 6. 影响面

| 项 | 评估 |
|---|---|
| 文件 | 8：work_file.py / build.py / app_env.py / app.py / test_app_env.py / `assets/live2d→pets` / 本文档+README / spike 注释 |
| 用户感知 | 未配置/配错→图标球（原=hiyori）；beta 默认关闭、配置即开启 |
| 升级副作用 | `pets/` 入完整性检查→老用户首跑弹一次既有"是否创建工作目录文件？"确认，确认后自动创建（与任何新增 WORK_DIR_DICT 目录行为一致） |
| 配置落点 | `pet_model.json` 仍在 `./system/`（不动，零迁移）；模型在 `work_dir/pets/`——用户换 work_dir 时模型随数据走，语义正确 |
| 迁移兼容 | 旧模板 `assets/...` → 按 work_dir 相对解析 → 不存在 → warning+球（warning 带完整解析路径，自解释） |
| 打包产物 | -4.8MB；`assets/` 仅 `app.ico`；live2d-py 运行库保留 |
| 风险 | 低：新逻辑=一个函数签名+一个 join，无环境分叉；降级链两级未动；测试覆盖 |
| 不可变项 | `win_ui.py` 生成物、`pet_model.json` 落点、两级降级机制 |

## 7. 验收

- `ruff` 归零、pytest 全量过
- dev 实跑三态：无配置出球+生成模板 → `cp -r pets server/` → 模板默认路径命中出 Live2D → 改错路径出 warning+球
- 打包冒烟：`build.py` 后 dist 无 `assets/live2d`；exe 无模型出球、`server/pets/`+配置出 Live2D
- 自定义 work_dir 场景：模型随 work_dir 解析正确

## 8. 实施记录

| 日期 | 步骤 | 结果 | 备注 |
|---|---|---|---|

## 9. 方案修正

| 日期 | 原方案 | 实际做法 | 原因 |
|---|---|---|---|
| 2026-11-14 | 沿用 `assets/` 前缀分支做内嵌资源解析 | 删除该分支，相对路径统一以 work_dir 为基 | `pets/` 挂 WORK_DIR_DICT 后模型归入用户数据语义；work_dir 已由启动机制解析，无需 frozen/CWD 分叉 |
| 2026-11-14 | 模型目录命名 `live2d/` 放仓库根 | 改 `pets/` | `live2d` 与 live2d-py 包同名存在命名空间目录遮蔽隐患；`pets/` 彻底绕开且语义模型无关 |
