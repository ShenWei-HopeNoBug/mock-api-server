# 打包产物 OpenGL/numpy 告警消除方案

> 范围：`build.py` / `lib/logger_lib.py`
> 关联：[desktop-pet-live2d-plan](desktop-pet-live2d-plan.md)（live2d-py 依赖链来源）

## 1. 背景

带黑窗的打包 exe（`mockServer.win.*.exe`）控制台打印：

```
Unable to import OpenGL.arrays.numpymodule.NumpyHandler: No numpy module present:
...（numpy C 扩展 _multiarray_umath DLL load failed 排查长文）
```

告警无功能影响（桌宠 Live2D 正常渲染），但属噪音且误导用户以为打包损坏。

## 2. 根因分析

依赖链：

```
live2d-py==1.0.0 install_requires numpy + pyopengl（uv.lock）
  → numpy 被 PyInstaller 收进 site-packages（模块源码在）
  → 但 C 扩展配套 DLL（numpy.libs 内 OpenBLAS 等）收集不全
  → 冻结运行时 _multiarray_umath DLL load failed
  → qt_win/live2d_pet.py `from OpenGL.GL import` 时 PyOpenGL
    尝试注册 NumpyHandler → numpy 半残状态报出长文
  → PyOpenGL 捕获后降级 ctypes array handler（功能不受影响）
```

关键点：numpy 在运行时**完全不被使用**——`live2d_pet.py` 只用
`glBindFramebuffer`/`glReadPixels` 与 GL 常量，live2d-py 内核是编译扩展。
告警出现时一切功能正常，即已实测证明无人需要 numpy。

另注：app 域 logger 均 `propagate=False`，该 WARNING 由 root logger 的
`lastResort` handler 打到 stderr，故仅黑窗版可见。

## 3. 方案

| # | 改动 | 位置 | 说明 |
|---|---|---|---|
| 1 | `"--exclude-module", "numpy"` | `build.py` pyinstaller args（`--collect-all live2d` 后） | numpy 不进包：C 扩展报错长文消失；顺带省 ~60MB 体积 |
| 2 | `logging.getLogger('OpenGL').setLevel(logging.ERROR)` | `lib/logger_lib.py` 模块级（`_DOMAIN_LOGGERS` 后） | PyOpenGL 对 NumpyHandler 缺失仍会打一行 WARNING，静音残余行；归位日志基建而非 live2d_pet（E402 不级联） |

### 备选（否决）

- `--collect-all numpy` 修好 numpy：告警也消失，但为运行时死依赖多背 ~60MB
- 不动：仅黑窗版噪音，但易误报为打包故障

### 风险

`--exclude-module numpy` 唯一风险是隐藏的运行时 numpy 使用——当前 numpy C
扩展已坏而功能全好，等于已实测验证无人依赖。

## 4. 影响面

| 文件 | 改动 |
|---|---|
| `build.py` | +`--exclude-module numpy` |
| `lib/logger_lib.py` | +OpenGL logger 静音（模块级一行） |

行为零变化；仅黑窗版控制台输出变干净。

## 5. 验证

- ruff 归零、pytest 全量过（已执行）
- 打包冒烟：`build.py` 后黑窗 exe 启动不再出现 numpy 排查长文与 NumpyHandler 告警；
  桌宠 Live2D（exe 同目录 `pets/` + `system/pet_model.json`）渲染不受影响

## 6. 实施记录

| 日期 | 步骤 | 结果 | 备注 |
|---|---|---|---|
| 2026-11-14 | 全量实施 | `build.py` exclude numpy；`logger_lib` OpenGL logger 静音 | 静音初置于 live2d_pet.py 触发 E402 级联（后续所有 import 需 noqa），改归位 logger_lib 模块级——其加载早于 live2d_pet 懒导入，时序安全 |

## 7. 方案修正

| 日期 | 原方案 | 实际做法 | 原因 |
|---|---|---|---|
| 2026-11-14 | OpenGL logger 静音写在 `live2d_pet.py` OpenGL import 之前 | 改置 `lib/logger_lib.py` 模块级 | E402：`from OpenGL.GL import` 前的裸语句使后续全部 import 需 noqa；logger_lib 为日志基建归属且先执行 |
