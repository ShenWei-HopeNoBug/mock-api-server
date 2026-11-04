# Qt Bridge 协议信封与分发层统一重构方案

> 关联文档：[QT_BRIDGE.md](../../../QT_BRIDGE.md)（协议现行约定）、`mock-api-server-web-v3`（前端仓库）
> 状态：待实施
> 范围：`lib/bridge_lib.py`（新建）/ `lib/biz_error_lib.py` / `lib/db/*` / `lib/TInteractObject.py` / `app_types/{qt_bridge_types,db_types,mcp_types}.py` / `module/mcp_server.py` / `qt_win/{mitmproxy_data_edit_dialog,download_proxy_config_dialog}.py` / `insert_test_db_data.py` / `QT_BRIDGE.md`；前端 `mock-api-server-web-v3` 两文件

## 1. 背景

Qt 端（PySide6 + QWebChannel）与内嵌 webview 的桥接协议已随业务增长出现四类实质问题，对照 spring-boot-template 的 HTTP 统一返回/拦截设计差距明显：

1. **双层状态语义 + 前端假性成功 bug**：信封 `status_code` 与 `data` 载荷内 `OperationResult.status_code` 并存两级状态；经核实前端 13 个 mutation 调用点 `.then()` 均不检查 `res.success`（唯一例外 `reorderVariants` 检查但失败静默），DB 层返回 `success:false` 时信封仍为 0 → **前端对失败操作弹成功提示**（现存 bug）；
2. **分发逻辑复制粘贴 + 行为漂移**：两个 webview 弹窗各自实现 `receive`/`_request`/（可选）`_event`/`send_qt2js_dict_msg`（~60-70 行/弹窗），未知协议名处理不一致（MitmproxyData 静默 vs DownloadProxy 回包）、event 支持不一致、params 无统一校验、无请求日志；
3. **`success` 字段全局冗余**：DB 层 ~90 处手写 `{"success": ..., "status_code": ...}` 字面量，`success ⟺ status_code==0` 恒成立为零信息字段，且手写存在不一致隐患；`success` 的唯一真实消费方是 MCP 客户端（LLM 契约 `{"success": bool}`），Python 代码零读取；
4. **业务错误码表达力不足**：异常→状态码靠内建异常类型 isinstance 映射（`KeyError→-20001` 等），handler 无法表达 `-30xxx` 数据类业务错误。

## 2. 决策（已与用户确认）

| 项 | 决定 |
|---|---|
| `success` 字段 | DB 层全量删除，`status_code` 为唯一事实源；MCP 边界 `_mcp_result` 包装派生 `success` 保住 LLM 契约 |
| 成功载荷 | 信封承载状态，`data` 剥掉三元组后只剩业务字段（`{id?}`/`{affected_count}`/`null`） |
| `affected_count` | **保留**——载荷中唯一真实业务字段（批量删除 toast 依赖），不属冗余 |
| 分发器形态 | `lib/bridge_lib.py` 组合式 `BridgeDispatcher`（注入 `send`，不 import Qt，可单测），非 mixin |
| handler 签名 | 保持 `(ctx, params)` / `(ctx, event)`，handler 与注册字典零改动 |
| 未知 request name | 两弹窗统一回包 `BIZ_PARAM_INVALID`（对齐 DownloadProxy 现状） |
| params 校验 | 收紧：非 dict（None 视为 `{}`）→ `PARAM_INVALID` |
| `BizError` 空 msg | 兜底 `'操作失败'` |
| event 未注册 handler | 记 warn 日志 |
| 缺 action_id 的 request | **丢弃不执行**（现状 MitmproxyData 仍会执行 DB 变更，属有意收紧） |
| 实施拆分 | **两阶段顺序实施、分别验收**：Phase 1 信封状态收敛（含前端同步），Phase 2 分发层抽离 |

## 3. 总体设计

```
DB 层返回 {status_code, status_msg, ...业务字段}          ← status_code 唯一事实源
        │
        ├─→ BridgeDispatcher（bridge 边界）
        │     信封 = status_code；data = 剥离三元组后的纯业务载荷
        │     统一：路由 / 强校验 / 未知名回包 / 异常映射(BizError) / 事件去重 / 请求日志
        │
        └─→ _mcp_result（MCP 边界）
              {success: (status_code == 0), status_code, status_msg, ...} → LLM 契约
```

**载荷键名契约**：此后业务 `data` 不得使用 `success` / `status_code` / `status_msg` 三键名（会被 `_unpack_result` 误识别为状态层），写入 QT_BRIDGE.md。

## 4. Phase 1：信封单层状态收敛

> **顺序敏感**：§4.1-4.3（unpack + 弹窗接入 + web 同步）必须先于 §4.4-4.6（DB/MCP 内部清理）落地——`_unpack_result` 对旧三元组载荷本身兼容，先上它则 wire 立即收敛为新形态，后续清理对外不可见；反向则 `res?.success` 变 undefined 导致 reorder 静默回归。§4.1-4.3 为协议行为变更（前后端同批发布），§4.4-4.6 为内部清理（可拆 commit）。

### 4.1 `lib/bridge_lib.py` 新建（本阶段仅含解包函数）

```python
_STATUS_KEYS = {'success', 'status_code', 'status_msg'}

class UnpackedResult(NamedTuple):
    status_code: int
    status_msg: str
    data: Any

def _unpack_result(result: Any) -> UnpackedResult:
    """OperationResult 识别（dict 且 status_code 为 int）：三元组上提信封，业务字段为 data。
    判定只看 status_code（事实源），success 是否在场不影响；
    成功 → 剥离后业务字段（剥空 → None）；失败 → code/msg 上提、data=None。"""
```

### 4.2 两弹窗 `_request` 接入（各 +4 行临时重复，Phase 2 删除）

`MitmproxyDataEditDialog._request` / `DownloadProxyConfigDialog._request` handler 调用点后改为：

```python
result = handler(self, params)
unpacked = _unpack_result(result)
send_response(unpacked.data, status_code=unpacked.status_code, status_msg=unpacked.status_msg)
```

其余分发代码本阶段一律不动（未知名行为差异、event 差异、无校验等保持现状）。

### 4.3 web 端 `mock-api-server-web-v3`（与 §4.2 同批构建入 `appServer/static`）

- `types/qt/dataManager.d.ts`：`OperationResult` → `{id?: string}`；`BatchOperationResult` → `{affected_count?: number}`（删 `success`/`status_code`/`status_msg`）；
- `apps/dataManager/views/outputManager/components/VariantEditorDialog/index.vue`：删 `res?.success` 守卫（`.then` 仅信封 0 进入，顺带消灭失败静默）。

已核实前端消费面：仅批量删除读 `res?.affected_count`，其余 mutation 均不读 `res`。

### 4.4 `lib/db/` — `success` 全量删除 + `_ok`/`_fail` 构造器

`lib/db/utils.py` 新增：

```python
def _ok(msg: str = '成功', **extra: Any) -> Dict[str, Any]:
    return {"status_code": BIZ_SUCCESS, "status_msg": msg, **extra}

def _fail(code: int, msg: str, **extra: Any) -> Dict[str, Any]:
    return {"status_code": code, "status_msg": msg, **extra}
```

机械 1:1 映射（含 `_ensure_open(default=...)` 兜底 dict——「DB 关闭失败路径」最易漏）：

| 原字面量 | 替换 |
|---|---|
| `{"success": True, "id": api_id, "status_code": BIZ_SUCCESS, "status_msg": "成功"}` | `_ok(id=api_id)` |
| `{"success": False, "id": None, "status_code": c, "status_msg": m}` | `_fail(c, m, id=None)` |
| `{"success": False, ..., "affected_count": 0}` | `_fail(c, m, affected_count=0)` |

范围：`api_data.py` ~47 处、`variants.py` ~36 处、`static_data.py` ~4 处、`mock_db.py`/`__init__.py` 视残留。失败字面量的 `id: None` 保留（`_fail(..., id=None)`）做到字面级映射、零语义漂移。

`app_types/db_types.py` OperationResult 家族重写（继承替代平铺、删 `success`）：

```python
class OperationResult(TypedDict):
    status_code: int        # 成败唯一权威（0=成功）
    status_msg: str
class OperationResultWithId(OperationResult):
    id: str
class OperationResultWithOptionalId(OperationResult, total=False):
    id: Optional[str]
class BatchOperationResult(OperationResult):
    affected_count: int
DbOperationResult = Union[OperationResult, OperationResultWithId,
                          OperationResultWithOptionalId, BatchOperationResult]
```

**检核**：`lib/db/` 下搜 `success` 必须 0 残留。

### 4.5 `module/mcp_server.py` — 边界派生 `success`

`app_types/mcp_types.py` 新建：`McpOperationResult` / `McpOperationResultWithOptionalId` / `McpBatchOperationResult`（= DB 对应类型 + `success: bool`）。

```python
def _mcp_result(result: DbOperationResult) -> Dict[str, Any]:
    """含 int status_code → {success: code==0, **result}；非结果形态原样返回（防御兜底）"""
    if not isinstance(result.get('status_code'), int):
        return dict(result)
    return {'success': result['status_code'] == BIZ_SUCCESS, **result}
```

~15 处 `return db.xxx()` → `return _mcp_result(db.xxx())`；返回注解换 `Mcp*Result`；docstring `{"success": bool}` 契约不变（mcp==2.0.0 若按注解产 outputSchema，新注解与实际返回反而更一致）。

### 4.6 杂项

- `insert_test_db_data.py`：`success = batch_insert_api(...)` + `if success`（dict 恒真瑕疵）→ `result['status_code'] == BIZ_SUCCESS`；
- `QT_BRIDGE.md`：新增「状态语义」节（status_code 唯一权威、载荷纯净约定、三键名禁用契约、MCP 派生说明），response 示例同步。

## 5. Phase 2：分发层抽离统一

### 5.1 `lib/bridge_lib.py` 增补 `BridgeDispatcher`

`BridgeDispatcher(Generic[CtxT])`（纯 Python 无 Qt 依赖）：

```python
def __init__(
    self,
    send: BridgeSendFn,                          # interact_obj.send_qt2js_dict_msg
    request_handlers: Mapping[str, RequestHandler],    # (ctx, params) -> result
    event_handlers: Optional[Mapping[str, EventHandler]] = None,  # (ctx, event) -> None
    handler_context: Optional[CtxT] = None,      # 弹窗 self
    extra_exc_map: Sequence[ExcStatusRule] = (), # 拼在默认异常映射表之前
    dedup_size: int = 256,
    tag: str = '',                               # 日志前缀 'dataManager'/'downloadProxy'
) -> None
```

`dispatch(message)` 统一行为（相对 Phase 1 的新增项）：

| 分支 | 行为 |
|---|---|
| `json.loads` 失败 | 正则提取 `action_id` → 有则回包 `PARAM_INVALID`，无则 warn+drop |
| 消息体非 dict / 未知 type | warn + drop |
| request：`action_id` 缺/非 str | warn + drop（**不执行 handler**，有意收紧） |
| request：`name` 缺/非 str | 回包 `PARAM_INVALID` |
| request：`params` 非 dict（None→`{}`） | 回包 `PARAM_INVALID` |
| request：name 未注册 | 回包 `PARAM_INVALID`（两弹窗统一） |
| handler 返回 | `_unpack_result` → 回包 |
| handler 异常 | `resolve_biz_error(e, extra_exc_map + DEFAULT)` → 回包 |
| event：字段缺失/未注册 | warn + drop（未注册记 warn） |
| event：`(name, action_id)` LRU 去重 | `OrderedDict`+`Lock`，容量 `dedup_size`；handler 失败摘除 key 允许重试 |
| 全请求 | 统一日志 `[bridge:tag] name action_id code cost`（成功 info / 失败 warning） |
| 发送 | handler 已在 worker 线程直接 `send` emit（去原一层 `@create_thread`） |

### 5.2 `lib/biz_error_lib.py` — `BizError`

```python
class BizError(Exception):
    """业务异常：显式携带 status_code/status_msg（对齐 Spring BizException）"""
    status_code: int
    status_msg: str
    def __init__(self, status_code: int, status_msg: str = '') -> None:
        super().__init__(status_msg)
        self.status_code = status_code
        self.status_msg = status_msg
```

`resolve_biz_error` 首行：`if isinstance(e, BizError): return e.status_code, e.status_msg or '操作失败'`。映射优先级：`BizError` > `extra_exc_map` > `DEFAULT_EXC_STATUS_MAP` > `BIZ_UNKNOWN_ERROR`。

### 5.3 类型补强

- `qt_bridge_types.py`：`QtResponsePayload.type` → `Literal['response']`；新增 `CtxT = TypeVar('CtxT')`、`RequestHandler = Callable[[Any, Any], Any]`、`EventHandler = Callable[[Any, QtBridgeEvent], None]`、`BridgeSendFn = Callable[[QtResponsePayload], None]`；
- `TInteractObject.py`：`send_qt2js_dict_msg(data: dict)` → `(data: QtResponsePayload)`（`@Slot(str)` 与 dict 参数怪癖记 TODO 不修）。

### 5.4 两弹窗迁移

**`DownloadProxyConfigDialog`**（删 ~70 行）：`receive`/`_request`/`_event`/`send_qt2js_dict_msg`/`_seen_event_ids`/`_event_lock`；imports 删 `json`/`OrderedDict`/`Lock`/`QtBridgeIncomingMessage`/`QtBridgeRequest`/`BIZ_*`/`resolve_biz_error`/`create_thread`/`error_catch`（`QtBridgeEvent` 保留——`_handle_close_requested` 注解仍用）。

**`MitmproxyDataEditDialog`**（删 ~45 行）：`receive`/`_request`/`send_qt2js_dict_msg`；imports 删 `json`/`QtBridgeIncomingMessage`/`QtBridgeRequest`/`BIZ_SUCCESS`/`resolve_biz_error`/`create_thread`（`error_catch` 保留——`init` 在用）。

两弹窗 `init()` 中 `interact_obj.js2qt_signal.connect(receive)` 统一替换为：

```python
self._bridge: BridgeDispatcher[<Dialog>] = BridgeDispatcher(
    send=interact_obj.send_qt2js_dict_msg,
    request_handlers=self._REQUEST_HANDLERS,
    event_handlers=self._EVENT_HANDLERS,      # MitmproxyData 省略（无 event）
    handler_context=self,
    tag='downloadProxy',                      # / 'dataManager'
)
interact_obj.js2qt_signal.connect(self._bridge.dispatch)
```

handler 定义与 `_REQUEST_HANDLERS`/`_EVENT_HANDLERS` 字典**零改动**（加 `ClassVar[Dict[str, RequestHandler]]` 标注）。

### 5.5 `QT_BRIDGE.md`

L3 会话层改述为 `BridgeDispatcher`；新增统一行为表与 `BizError` 用法；文件索引补 `lib/bridge_lib.py`、`app_types/mcp_types.py`；TODO 注记（`@Slot` 怪癖、无界线程模型待议）。

## 6. 提交拆分

| Commit | 内容 |
|---|---|
| Phase1-A（协议行为变更，前后端同批） | §4.1 + §4.2 + §4.3（web 仓另仓提交，同批构建入 `appServer/static`） |
| Phase1-B（内部清理，对外不可见） | §4.4 + §4.5 + §4.6 |
| Phase2 | §5 全部 + `QT_BRIDGE.md` 分发层章节 |

不自动提交，由人确认后提交。Phase 1 完成后系统即处于可发布自洽态，Phase 2 可从容推进但不宜久拖（§4.2 留 ~8 行临时重复）。

## 7. 验收

Phase 1：

| # | 用例 | 预期 |
|---|---|---|
| 1 | 删除不存在 id | toast「记录不存在: xxx」**而非成功**（bug 修复确认） |
| 2 | 增/改/删/复制/变体排序正常路径 | toast 成功、刷新正常 |
| 3 | 批量删除 | 「共删除 N 条」计数正确 |
| 4 | `lib/db/` grep `success` | 0 残留 |
| 5 | MCP 工具调用 | `{success: bool,...}` 与 status_code 一致、无 schema 报错 |
| 6 | DevTools 观察回包 | 失败 `data=null`、成功载荷无三元组 |

Phase 2：

| # | 用例 | 预期 |
|---|---|---|
| 1 | 两弹窗正常路径 | 无回归 |
| 2 | DevTools 发未知名 request | 两弹窗均立即 `PARAM_INVALID` |
| 3 | 非法 JSON / params 非 dict | `PARAM_INVALID` 回包 |
| 4 | dataManager 发 event | warn 日志（未注册） |
| 5 | 日志 | `[bridge:tag] name action_id code cost` |
| 6 | `ruff check` | 无新增 |

## 8. 风险与缓解

| # | 风险 | 缓解 |
|---|---|---|
| R1 | `lib/db/` `success` 机械替换漏 `_ensure_open` 兜底 | 完工后 `lib/db/` grep `success` 归 0 |
| R2 | 新 Qt + 旧 web → `res?.success` 恒 undefined，reorder 静默回归 | §4.2+§4.3 同批构建入 `appServer/static`；反向组合仅退回现状 bug 不更差 |
| R3 | FastMCP 按返回注解产 outputSchema / 校验 | 新 `Mcp*Result` 注解与实返一致；验收用例 5 实调验证 |
| R4 | `_unpack_result` 误识别未来含 `status_code` 的业务载荷 | 三键名禁用契约入 QT_BRIDGE.md；现状全部返回类型无此键 |
| R5 | action_id 缺失丢弃 vs 现状会执行 DB 变更 | 有意收紧（无回包能力不产副作用），入文档变更说明 |
| R6 | `js2qt_signal.connect(self._bridge.dispatch)` 对象被 GC 断流 | `self._bridge` 强持有；冒烟首用例（列表加载）即暴露 |
| R7 | `@Slot(str)` + dict 参数存量怪癖 | 仅收紧 Python 注解不动 Slot 声明，记 TODO |

## 9. 明确不做

- worker 线程队列 / 有界线程池（现 `create_thread` 每消息一线程模型保留，另立议题）；
- `BizError` 在存量 handler 的批量采纳（能力落地即可，按需在后续协议开发中使用）；
- request `data` 保留字段语义化、i18n 取词、`notify` Qt→JS 主动 push；
- `@Slot(str)` 声明修复、`qt_win/` 其余原生弹窗（无 bridge）；
- 前端 `affected_count` 删除（§2 已决策保留）、其他 web 仓改动；
- `mcp_server` 非 OperationResult 返回工具的包装。

## 10. 实施记录

| 日期 | 步骤 | 结果 | 备注 |
|---|---|---|---|
| （待填） | | | |

## 11. 方案修正

| 日期 | 修正内容 | 原因 |
|---|---|---|
| （待填） | | |
