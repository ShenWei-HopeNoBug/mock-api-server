# 桌宠模型外置化变更（beta 收敛）

> 状态：已实施
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
| `./pets/` | app 级全局模型目录（与 `./system` 同级） | 首进桌宠时 `ensure_pet_model_config` 自动创建；打包后=exe 同目录 `pets/`；dev=仓库根 `pets/` |
| 仓库根 `pets/` | `pets/hiyori/` 测试模型 | 入库、即 dev 的全局 pets——模板默认路径 `pets/hiyori/Hiyori.model3.json` 在 dev 下直接命中，零拷贝 |
| `./system/pet_model.json` | 配置文件 | 位置不变（随 history.json），避免迁移 |

## 4. 逐项改动

### 4.1 `git mv assets/live2d pets`

仓库根测试资产（dev-only），保留 git 历史；`assets/` 仅剩 `app.ico`；`pets/` 命名绕开 `live2d` 包名冲突且模型无关。

### 4.2 `config/work_file.py`

新增 `PETS_DIR = r'./pets'` 常量于 `SYSTEM_DIR` 旁（同属 app 级目录段，不入 `WORK_DIR_DICT`——pets 是全局目录非 work_dir 用户数据）；自动创建由 `app_env.ensure_pet_model_config` 承担（见 4.4）。

### 4.3 `build.py`

- `--add-data "assets;assets/"` → `--add-data "assets/app.ico;assets/"`（-4.8MB）
- `--collect-all live2d` **保留**（live2d-py 为渲染运行时，删了用户放模型也渲不了）

### 4.4 `lib/pet_lib.py`（桌宠领域逻辑，原拟 `app_env.py` 已归位）

- 删 `LIVE2D_MODEL_JSON` 常量与三层内嵌兜底，`model_json` 默认 `''`：
  - 配置缺失 → `''` 静默（正常态）；JSON 损坏 → `''`+warning；路径不存在 → `''`+warning（warning 含解析后完整路径，提示用户该放哪）
- `_resolve_pet_model_path(raw)`：删 `assets/` 前缀分支；绝对路径→原样；相对路径→`os.path.abspath(raw)`（app 根/CWD 为基，与 `system/`、`pets/` 的 `./` 锚定一致）
- `load_pet_model_config()` 保持无参
- `ensure_pet_model_config()`：`os.makedirs(PETS_DIR)` 连带建全局 pets 目录（挪到"配置已存在即 return"之前——配置在手目录被删也要补建）
- `PET_MODEL_CONFIG_PATH` 常量归 `config/work_file.py`（与 `HISTORY_CONFIG_PATH` 同模式）；`app_env.py` 剥离全部桌宠代码回归纯构建环境面
- `_PET_MODEL_DEFAULT['model_json']` → `'pets/hiyori/Hiyori.model3.json'`（app 根相对）

### 4.5 `app.py`

- `_create_pet()`：`model_json` 为空直接返回 `DesktopPetWindow`（未配置=正常态，跳过 Live2D 尝试，不打 warning）；其余走原"尝试→异常→球"链路
- 两级降级、config-diff 免重启重建机制不动

### 4.6 `tests/lib/test_pet_lib.py`（原 `tests/test_app_env.py`，随代码归位迁移）

- 三处兜底断言 `LIVE2D_MODEL_JSON` → `''`
- `assets/` 前缀解析用例 → app 根（`abspath`）基相对路径解析用例
- `ensure_` 用例补 pets 目录连带创建断言

### 4.7 `tools/live2d_spike.py`

主链路同源生效，仅补注释说明模型路径走 `./pets/`（app 根相对）。

## 5. 使用流程

**打包用户**：首次进桌宠自动生成 `system/pet_model.json` 模板并建空 `pets/`（exe 同目录）→ 放模型（如 `pets/hiyori/`）→ 改 `model_json` 指向 `pets/<目录>/<model3.json>` → 再进桌宠生效（config-diff 重建免重启）。

**dev**：仓库根 `pets/hiyori/` 即全局 pets——模板默认路径直接命中，开箱出 Live2D，零拷贝零配置。

## 6. 影响面

| 项 | 评估 |
|---|---|
| 文件 | 8：work_file.py / build.py / lib/pet_lib.py / app.py / tests/lib/test_pet_lib.py / `assets/live2d→pets` / 本文档+README / spike 注释 |
| 用户感知 | 未配置/配错→图标球（原=hiyori）；beta 默认关闭、配置即开启 |
| 升级副作用 | 无启动弹窗扰动——`pets/` 不入 `WORK_DIR_DICT`，完整性检查不受影响；`pets/` 与模板同机懒建于首进桌宠（中间态曾挂 work_dir 的用户会残留 `server/pets/` 空目录，无害） |
| 配置落点 | `pet_model.json` 在 `./system/`、模型在 `./pets/`——同属 app 级目录（打包后均=exe 同目录），与 work_dir 解耦 |
| 迁移兼容 | 旧模板 `assets/...` → 按 app 根相对解析 → 不存在 → warning+球（warning 带完整解析路径，自解释） |
| 打包产物 | -4.8MB；`assets/` 仅 `app.ico`；live2d-py 运行库保留 |
| 风险 | 低：新逻辑=一个函数签名+一个 join，无环境分叉；降级链两级未动；测试覆盖 |
| 不可变项 | `win_ui.py` 生成物、`pet_model.json` 落点、两级降级机制 |

## 7. 验收

- `ruff` 归零、pytest 全量过
- dev 实跑三态：无配置出球+生成模板+pets 目录 → 模板默认路径直接命中仓库 `pets/hiyori` 出 Live2D → 改错路径出 warning+球
- 打包冒烟：`build.py` 后 dist 无 `assets/live2d`；exe 无模型出球、exe 同目录 `pets/`+配置出 Live2D

## 8. 实施记录

| 日期 | 步骤 | 结果 | 备注 |
|---|---|---|---|
| 2026-11-14 | 目录迁移 + work_dir 注册 | `git mv assets/live2d pets`（14 文件保留历史）；`work_file.py` 加 `PETS_DIR='/pets'` 并入 `WORK_DIR_DICT`，既有 `create_work_files`/`check_work_files` 自动接管 | 老用户升级首跑会弹一次既有"创建工作目录文件"确认，确认后空目录就位 |
| 2026-11-14 | `build.py` 收窄打包 | `--add-data` 改 `assets/app.ico;assets/`；`--collect-all live2d` 保留（渲染运行时） | assets/ 仅剩 app.ico，-4.8MB |
| 2026-11-14 | `app_env.py` 兜底删除 | 删 `LIVE2D_MODEL_JSON`+三层内嵌兜底→`model_json=''`；`_resolve_pet_model_path` 删 `assets/` 前缀、改 `work_dir` 基；`load_pet_model_config(work_dir)` 加参；模板路径 `pets/hiyori/...` | warning 文案统一"降级图标球"并带完整解析路径，提示用户应放位置 |
| 2026-11-14 | `app.py` + 测试 | `_create_pet` 空 model_json 直接 `DesktopPetWindow`（不打 warning）；两处调用传 `self.work_dir`；`test_app_env.py` 重写 7 例 | 端到端冒烟过：自动建目录→未配置空串→放模型命中 三态全对 |
| 2026-11-14 | 验证 | ruff 归零、pytest 全量过 | 手码 `assets/live2d`、`LIVE2D_MODEL_JSON` 引用清零 |
| 2026-11-14 | pets 改 app 级全局目录 | `WORK_DIR_DICT` 摘除，`PETS_DIR='./pets'` 挪 `SYSTEM_DIR` 旁；解析基回 `os.path.abspath`（app 根）；`load_pet_model_config` 回无参；`ensure_` 连带 `makedirs(PETS_DIR)` 且挪到"配置已存在即 return"之前 | 用户拍板：先只支持全局 pets 与 system 同级；顺带收益——dev 下模板默认路径直接命中仓库 `pets/hiyori`，零拷贝 |
| 2026-11-14 | 桌宠代码归位 `lib/pet_lib.py` | 5 符号（`PET_MODEL_CONFIG_PATH`→`work_file.py` 常量，`_PET_MODEL_DEFAULT`/`_resolve_`/`load_`/`ensure_`→`lib/pet_lib.py`）整体迁出 `app_env.py`；测试迁 `tests/lib/test_pet_lib.py`；app/spike 调用点改 import | `app_env` 回归纯构建环境面（APP_ICON/VERSION/LOG 开关）；内嵌兜底删除后 pet 代码不再用 `_resource_path`，滞留打包桥接文件已无理由 |

## 9. 方案修正

| 日期 | 原方案 | 实际做法 | 原因 |
|---|---|---|---|
| 2026-11-14 | 沿用 `assets/` 前缀分支做内嵌资源解析 | 删除该分支，相对路径统一以 work_dir 为基 | `pets/` 挂 WORK_DIR_DICT 后模型归入用户数据语义；work_dir 已由启动机制解析，无需 frozen/CWD 分叉 |
| 2026-11-14 | 模型目录命名 `live2d/` 放仓库根 | 改 `pets/` | `live2d` 与 live2d-py 包同名存在命名空间目录遮蔽隐患；`pets/` 彻底绕开且语义模型无关 |
| 2026-11-14 | `pets/` 挂 `WORK_DIR_DICT` 作 work_dir 子目录（`<work_dir>/pets`，相对路径以 work_dir 为基） | 改 app 级 `./pets` 与 `./system` 同级，解析基回 app 根 `abspath`，自动创建并入 `ensure_pet_model_config` | 用户定调"先只支持全局 pets"——模型属 app 级资源非 work_dir 用户数据；同时消掉 work_dir 传参与升级弹窗副作用 |
| 2026-11-14 | 桌宠配置代码驻 `app_env.py`（历史沿用：内嵌模型曾需 `_resource_path` 解析） | 迁 `lib/pet_lib.py`（领域逻辑）+ `config/work_file.py`（`PET_MODEL_CONFIG_PATH` 常量），贴合"常量在 config、逻辑在 lib"分层 | 内嵌兜底删除后 `_resource_path` 耦合消失，`app_env` 应只剩构建环境桥接；pet 代码曾占该文件 2/3 体量，归位后模块职责单一 |
