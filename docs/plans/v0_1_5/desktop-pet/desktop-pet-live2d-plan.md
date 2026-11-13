# Live2D 接入方案（桌宠 V2）

> 关联文档：[desktop-pet-basic-plan](desktop-pet-basic-plan.md)（V1 最小闭环）；[GUI_STACK_DESKTOP_PET_DISCUSSION.md](../../../discussions/GUI_STACK_DESKTOP_PET_DISCUSSION.md)（Live2D 路线评估 §3.2、待验证清单 §6）
> 状态：已实施（2026-11-14，渲染/点穿/打包运行待人工验收）
> 范围：`tools/live2d_spike.py` / `qt_win/pet_shell.py` / `qt_win/live2d_pet.py` 新增；`qt_win/desktop_pet.py` / `qt_win/app.py` / `main.py` / `app_env.py` / `pyproject.toml` / `build.py` / `assets/live2d/` 改动

## 1. 背景与范围

V1 占位圆球已完成最小闭环。本方案将渲染层替换为 Live2D：保留全部既有交互（拖拽、右键菜单「打开主面板/退出」），新增模型点击反应与视线跟随，窗口尺寸调整为立绘比例。

**范围外**：服务状态联动表情、皮肤切换、口型同步、物理参数调试（后续迭代）。

## 2. 前置事实（已核实）

| 事实 | 结论 |
|---|---|
| `live2d-py` 1.0.0 | `cp311-abi3` 稳定 ABI wheel，Python 3.13 直接可用，无需源码编译 |
| wheel 内容 | `_live2d.pyd` 静态链接 Cubism Core；`live2d/FrameworkShaders/` GLSL 源码运行时加载 → PyInstaller 必须 `--collect-data live2d` |
| 资源路径 | `_resource_path()` 已兼容打包模式；`--add-data "assets;assets/"` 使 `assets/live2d/` 免改动入包 |
| 环境 | `main.py` 已有 `QTWEBENGINE_CHROMIUM_FLAGS=--in-process-gpu` + `AA_ShareOpenGLContexts` |

## 3. 阶段一：Spike 隔离验证

新增 `tools/live2d_spike.py`（~150 行，独立可跑不入主链路），复刻 main.py 环境变量与 GL 设置，建 `QOpenGLWidget` 顶层窗加载模型验证四件事：

| 验证项 | 通过标准 |
|---|---|
| 渲染 + 透明 | 模型正常显示，背景真透明（`WA_TranslucentBackground` + `setAutoFillBackground(False)` + `QSurfaceFormat.setAlphaBufferSize(8)`，live2d-py issue #30 的坑位） |
| 逐像素点穿 | 盖住桌面图标点立绘轮廓外透明区，下层响应（人工） |
| `--in-process-gpu` 共存 | 同环境变量下渲染无闪帧/黑屏 |
| PyInstaller 打包 | `pyinstaller --collect-all live2d` 打包后可运行 |

全过进阶段二；卡死则回帧动画兜底，占位球继续服役。

## 4. 阶段二：集成实施

### 4.1 公共交互层（mixin）

新增 `qt_win/pet_shell.py`：

```python
class PetShellMixin:
    """桌宠窗口壳：无边框透明置顶 + 拖拽 + 右键菜单 + 屏幕角定位。
    子类提供回调与可覆写钩子；mixin 须在 Qt 基类之前继承。"""

    def _init_pet_shell(self, on_restore, on_quit):
        # 存回调 + setWindowFlags(Frameless|StaysOnTop|Tool) + WA_TranslucentBackground

    def move_to_corner(self, margin=20): ...

    # 拖拽：press 记偏移 → move 跟随 → release 清零
    # 点击判定：release 时位移 < 5px 视为"点按"而非拖拽 → 调 _on_pet_tap(pos)
    def mousePressEvent / mouseMoveEvent / mouseReleaseEvent

    def contextMenuEvent(self, event):  # QMenu[打开主面板, 退出] 与 V1 一致

    # 可覆写钩子（默认 no-op）
    def _on_pet_tap(self, pos): ...        # 点按（未拖拽）：Live2D 做 HitTest 动作反应
    def _on_pointer_move(self, pos): ...   # 非拖拽移动：Live2D 做视线跟随
```

两个渲染层各自单继承 mixin + 一个 Qt 基类（mixin 在前保证事件方法生效，纯 Python mixin 无多 Qt 父类坑）：

```python
class DesktopPetWindow(PetShellMixin, QWidget):        # 现有类改造，行为不变
class Live2DPetWindow(PetShellMixin, QOpenGLWidget):   # 新文件 qt_win/live2d_pet.py
```

### 4.2 `qt_win/live2d_pet.py`

| 项 | 方案 |
|---|---|
| 尺寸 | 立绘比例 ~200×300（Hiyori 类立绘），类常量可配 |
| 渲染循环 | QTimer 30fps → `update()`；桌宠不需要 60fps |
| GL 生命周期 | `initializeGL`: `live2d.glInit()` + `LAppModel` + `LoadModelJson`；`paintGL`: `clearBuffer`+`Update`+`Draw`；`resizeGL`: `model.Resize(w*dpr, h*dpr)` |
| 透明 | `setAutoFillBackground(False)` + alpha buffer format（spike 验证过的配置直接迁移） |
| DPI | `devicePixelRatio` 乘进 viewport 与 `HitTest` 坐标（已知坑） |
| 点击反应 | `_on_pet_tap` → `model.HitTest('Head'/'Body', x*dpr, y*dpr)` → `StartMotion(tap 组)`；命中区按 model3.json 定义，无命中播默认反应 |
| 视线跟随 | `_on_pointer_move` → `model.Drag(x, y)`（归一化坐标） |
| 初始化 | `live2d.init()` 于 main.py 建 QApplication 后调一次；`live2d.dispose()` 挂 `app.aboutToQuit` |

### 4.3 降级逻辑（enter_pet_mode）

```python
def _create_pet(self):
    try:
        from qt_win.live2d_pet import Live2DPetWindow  # 延迟导入
        return Live2DPetWindow(model_json=app_env.LIVE2D_MODEL_JSON, ...)
    except Exception as e:
        APP_LOGGER.warning(f'Live2D 初始化失败，降级占位球：{e}')
        return DesktopPetWindow(...)
```

缺模型/GL 异常/导入失败一律降级球，永不出现"点 X 后什么都没了"。

### 4.4 模型素材

- 官方示例模型（Hiyori），实施时从 Live2D 官方示例仓库拉取入 `assets/live2d/hiyori/`（含 model3.json + 贴图 + motions，~10MB 量级）；
- `app_env` 加 `LIVE2D_MODEL_JSON = _resource_path('assets/live2d/hiyori/Hiyori.model3.json')`。

### 4.5 依赖与打包

- `pyproject.toml`：`live2d-py==1.0.0`、`pyopengl`（pin 版本）
- `build.py`：PyInstaller args 加 `"--collect-all", "live2d"`（收 `_live2d.pyd` + GLSL）

## 5. 合规项

- **Cubism SDK**：wheel 已含 Core 二进制，应用分发仍受 Live2D Release License 约束（个人/小规模免费档可用，商用须签协议）；
- **示例模型**：官方示例模型开发占位 OK，**发布前**确认其分发条款或换自研/明确免费模型 → 记入发布 checklist。

## 6. 影响面与边界

| 项 | 说明 |
|---|---|
| 既有交互 | mixin 迁移后球版行为逐字节等价（菜单/拖拽/角定位） |
| 性能 | 30fps GL 渲染常驻开销 ~1-3% CPU + 模型显存，轻量 |
| 退出清理 | `aboutToQuit` 里 dispose，不碰 `_cleanup_in_thread` 顺序 |
| 降级路径 | 无 live2d-py/模型 → 球，功能等价回 V1 |

## 7. 验收清单

- [ ] Spike 四项全过并记录结论（回填讨论文档 §6 待验证清单）
- [ ] 点 X 出立绘小人（~200×300），拖拽/菜单/角定位与球版一致
- [ ] 点按（非拖拽）头/身体出动作反应；鼠标移动视线跟随
- [ ] 缺模型 → 自动降级球 + warning 日志
- [ ] 文件菜单/桌宠菜单双退出 + `_force_quit` 一次性消费无回归
- [ ] 打包版实测；`uv run ruff check .` 归零

## 8. 明确不做

状态联动表情、皮肤/多模型切换、口型同步、物理调试器、点按与拖拽的组合手势（如拖起小人摇晃）、Live2D 模型的二次封装抽象（暂只承载一个模型）。

## 9. 改动清单

| 文件 | 改动 |
|---|---|
| `tools/live2d_spike.py` | 新增，阶段一验证脚本 |
| `qt_win/pet_shell.py` | 新增，PetShellMixin 公共交互层 |
| `qt_win/desktop_pet.py` | 改造为 `PetShellMixin, QWidget`，行为不变 |
| `qt_win/live2d_pet.py` | 新增，Live2D 渲染窗口 |
| `qt_win/app.py` | `enter_pet_mode` → `_create_pet` 降级选择 |
| `main.py` | `live2d.init()` + `aboutToQuit` dispose |
| `app_env.py` | `LIVE2D_MODEL_JSON` 路径 |
| `assets/live2d/hiyori/` | 新增模型素材 |
| `pyproject.toml` | +live2d-py/pyopengl |
| `build.py` | +`--collect-all live2d` |

## 10. 实施记录

| 日期 | 步骤 | 结果 | 备注 |
|---|---|---|---|
| 2026-11-14 | 阶段一 spike + 阶段二集成全部实施 | 依赖 `live2d-py==1.0.0`/`pyopengl==3.1.9`（uv add，lock 已同步）；Hiyori 官方示例模型入 `assets/live2d/hiyori/`（4.8MB）；`ruff` 归零；**打包冒烟通过**：`--collect-all live2d` 构建产物含 `_live2d.pyd`+GLSL+模型，exe 正常运行（PID 存活、~227MB） | live2d-py 1.0.0 API 与文档期调研的 v3 子包命名不同：`live2d.Model`（非 `LAppModel`）、`IsAreaHit`/`StartRandomMotion`/`Drag`，CsmSDK 5-r.5 |

## 11. 方案修正

| 日期 | 修正内容 | 原因 |
|---|---|---|
| 2026-11-14 | live2d 生命周期不在 main.py 显式 init/dispose，改为 `live2d_pet.ensure_live2d_init()` 延迟初始化 + `aboutToQuit` 挂 dispose（main.py 零改动）；`enter_pet_mode` 增加 show 后 `init_failed` 检查降级（initializeGL 在 show 时才执行，构造期检查覆盖不到 GL 阶段失败） | 延迟初始化使 live2d 仅在首次进桌宠时启动，启动路径零风险且失败可降级；GL 阶段失败（上下文创建/模型解析）必须 show 后兜底 |
