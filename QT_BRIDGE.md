# Qt Bridge 通信协议文档

本文档描述 Qt 客户端（PySide6）与内嵌 Webview 页面之间的桥接协议。两端代码仓库：

- Qt 端：`mock-api-server`（本仓库）
- Web 端：`mock-api-server-web-v3`，桥接模块位于 `src/utils/bridge/`

## 架构分层

| 层级 | 职责 | Qt 端实现 | Web 端实现 |
|---|---|---|---|
| L1 传输层 | 双向字符串通道 | `QWebChannel` + `TInteractObj` | `qwebchannel.js` + `QtBridge` |
| L2 消息层 | JSON 消息格式与 `type` 分发 | `receive()` → `type` 分流 | 消息体构造（`sendObjMsg`） |
| L3 会话层 | 请求配对、超时、拦截器、事件去重 | `_REQUEST_HANDLERS` / `_EVENT_HANDLERS` 分发 | `QtRequestManager` / `QtEventSender` |
| L4 业务层 | 协议名 → 业务处理 | 各弹窗 handler | 各视图 API hooks |

---

## 通道与初始化

### 通道注册（Qt 端）

每个 webview 弹窗创建独立的 `QWebChannel`，并通过 `registerObject` 注册一个命名通信对象：

| 通道对象名 | Qt 弹窗 | 加载页面 | 支持消息类型 |
|---|---|---|---|
| `dataManager` | `MitmproxyDataEditDialog`（抓包数据管理） | `apps/dataManager/index.html #/outputManager` | `request` |
| `downloadProxy` | `DownloadProxyConfigDialog`（下载代理配置） | `apps/configEdit/index.html #/downloadProxy` | `request` + `event` |

通信对象为 `TInteractObj`（`lib/TInteractObject.py`），暴露给 JS 的成员：

| 成员 | 类型 | 方向 | 说明 |
|---|---|---|---|
| `send_js2qt_msg(str)` | Slot | JS → Qt | JS 调用发送消息，内部 emit `js2qt_signal` |
| `qt2js_signal` | Signal | Qt → JS | Qt 下发消息，JS 侧 `connect(callback)` 订阅 |
| `send_qt2js_msg(str)` | Slot | Qt 内部 | emit `qt2js_signal`（Qt 侧调用入口） |
| `send_qt2js_dict_msg(dict)` | Slot | Qt 内部 | `JsonFormat.dumps` 后走 `send_qt2js_msg` |
| `js2qt_signal` | Signal | Qt 内部 | 弹窗内 `receive()` 的订阅源 |
| `build_qt_response(...)` | static | Qt 内部 | 构造 response 消息体 |

### JS 端初始化链路

```
index.html: <script src="qrc:/qtwebchannel/qwebchannel.js">
  → App.vue onBeforeMount: QtBridge.getQtBridgeData()          # 10s 超时
    → new QWebChannel(qt.webChannelTransport, cb)
      → channel.objects                                       # { dataManager, downloadProxy, ... }
        → store.setRegister(!error) / setChannelObj(objects)
  → 各视图 hook watch(store.register) → init():
    → 取 channelObj.<通道名> → isBridgeUsable() 校验
    → new QtBridge({ bridge })                                # connect qt2js_signal
    → new QtRequestManager(bridge, { timeout: 10000 })
    → setupDefaultInterceptors(manager, onError)
    → isReady = true → onReady()
```

桥接对象可用性判定（`isBridgeUsable`）：`send_js2qt_msg` 为函数 **且** `qt2js_signal.connect` 为函数。

---

## 消息格式

所有消息均为 JSON 字符串，通过 `type` 字段区分种类。

### JS → Qt：request（请求，需要回包）

```json
{
  "type": "request",
  "name": "/mock_data/list",
  "action_id": "<UUID>",
  "params": {},
  "data": {}
}
```

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `type` | `string` | 是 | 固定 `"request"` |
| `name` | `string` | 是 | 协议名，约定 `/namespace/action`（如 `/mock_data/create`） |
| `action_id` | `string` | 是 | 每次请求生成的 UUID，用于配对 response |
| `params` | `object` | 否 | 请求参数，**Qt 端 handler 实际只消费此字段** |
| `data` | `object` | 否 | 保留字段，Qt 端目前不读取 |

### JS → Qt：event（单向事件，无回包）

```json
{
  "type": "event",
  "name": "download_proxy.close_requested",
  "action_id": "<UUID>",
  "params": {},
  "data": {}
}
```

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `type` | `string` | 是 | 固定 `"event"` |
| `name` | `string` | 是 | 事件名，约定 `domain.action_name`（如 `download_proxy.close_requested`） |
| `action_id` | `string` | 是 | 事件标识，Qt 端用作去重 key（见「单向事件流程」） |
| `params` | `object` | 否 | 仅当为 plain object 时才包含 |
| `data` | `any` | 否 | 仅当非 `undefined` 时才包含 |

### Qt → JS：response（请求回包）

```json
{
  "type": "response",
  "name": "/mock_data/list",
  "action_id": "<对应请求的 UUID>",
  "status_code": 0,
  "status_msg": "",
  "data": {}
}
```

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `type` | `string` | 是 | 固定 `"response"`，其他值被 `QtRequestManager` 忽略 |
| `name` | `string` | 是 | 对应请求的协议名 |
| `action_id` | `string` | 是 | 与请求一一对应，用于匹配 pending 请求 |
| `status_code` | `number` | 是 | 业务状态码，`0` 成功；非 `0` 失败 → `RESPONSE_ERROR`（见「错误体系」） |
| `status_msg` | `string` | 否 | 失败原因，作为 reject 的 error message |
| `data` | `any` | 是 | 业务数据载荷，见「状态语义」 |

#### 状态语义（v0_1_5 起）

- **信封 `status_code` 是成败的唯一权威**：`0` 成功，非 `0` 失败（`BIZ_CODE`）；`data` 不再承载 `success` / `status_code` / `status_msg`。
- Qt 端经 `lib/bridge_lib._unpack_result` 统一解包：handler 返回 DB `OperationResult` 时，状态三元组上提为信封字段、剥离出载荷；失败时 `data` 固定为 `null`，成功时 `data` 只含业务字段（剥空则为 `null`）。
- **载荷键名契约**：`data` 对象禁止使用 `success` / `status_code` / `status_msg` 三个键名（会被误识别为状态层）；`affected_count`、`id` 等业务字段不受此限。
- **MCP 边界例外**：`module/mcp_server.py` 工具返回值在 MCP 适配层由 `status_code` 派生 `success` 布尔（LLM 可读性），该字段只存在于 MCP 响应，不回写 DB、不进 Qt 信封。

### `action_id` 语义

| 场景 | 作用 |
|---|---|
| request ↔ response | 配对标识，JS 端 `pendingMap` 以此为 key |
| event | Qt 端去重标识 `(name, action_id)`；JS 端 `sendEvent` 允许调用方传入固定 `actionId` 实现重试去重，不传则生成新 UUID |

---

## 请求-响应流程

### JS 端发送链路

```
manager.fetch(name, params, { timeout, noMessage })
  → manager.request({ name, params, ... })
    → generateUUID → pendingMap.set(actionId, pending)
    → timeoutMs > 0 时启动超时定时器
    → bridge.sendObjMsg({ type:'request', name, action_id, params, data })
      → JSON.stringify → bridge.send → bridge.send_js2qt_msg(message)
```

超时规则：`QtRequestManager` 构造参数 `timeout` 为默认值，**`0` 表示无超时**；单次请求 `config.timeout` 可覆盖，非法值（非有限数 / 负数）回退默认值。各视图 hook 统一传 `10000`。

### Qt 端分发链路

```
send_js2qt_msg → js2qt_signal → dialog.receive(message)      # @create_thread，工作线程
  → json.loads → 按 type 分流
    'request' → _request(incoming)
      → _REQUEST_HANDLERS.get(name)
      → handler(self, params)                                # 只读 params
        → 返回 result → _unpack_result(result)               # OperationResult 状态上提
          → send_response(data, code, msg)
        → 抛异常 → resolve_biz_error(e) → send_response(None, code, msg)
send_response → build_qt_response → send_qt2js_dict_msg      # @create_thread → qt2js_signal
```

**未知协议名的处理目前两端不一致**（新增协议时需注意）：

| 弹窗 | 未知 request name 行为 |
|---|---|
| `MitmproxyDataEditDialog` | 静默丢弃，无回包 → JS 端只能等超时 |
| `DownloadProxyConfigDialog` | 回包 `BIZ_PARAM_INVALID`（-20002），`status_msg` 为 `不支持的请求路径: {name}` |

### JS 端接收链路

```
qt2js_signal → QtBridge._receive → publish(RECEIVE)
  → QtRequestManager.handleRawReceive(messageStr)
    → parseMessage: JSON.parse
        失败 → 正则 "action_id"\s*:\s*"<id>" 匹配原始字符串定位 pending → PARSE_ERROR
    → type !== 'response' → 忽略
    → pendingMap.get(action_id) → 不存在/已结算 → 忽略
    → status_code !== 0 → reject QtRequestError(RESPONSE_ERROR, status_msg)
    → 否则 resolve QtResponse{ config, data: 完整 ResponsePayload }
      → 依次经过 interceptors.response 拦截器链
```

### 拦截器

`manager.interceptors.response` 为 axios 风格的 `InterceptorManager`（`use` / `eject` / `forEach`）。**所有结算路径**（成功、超时、发送失败、销毁等）都会经过响应拦截器链。

`setupDefaultInterceptors` 注册的默认行为：

- `onFulfilled`：解包 `QtResponse` → 返回 `data.data`，即调用方拿到的是业务数据而非完整载荷
- `onRejected`：`config.noMessage` 为真时跳过全局 toast，否则 `messageFn(error.message)`，然后继续 reject

> 注意：若未注册拦截器，`request()` resolve 的值是 `QtResponse` 包装对象 `{ config, data }`，不是业务数据。

### `fetch` 简写签名

```ts
manager.fetch<T, P>(name, params?, { timeout?, noMessage? }) // = request({ name, params, ...config })
```

---

## 单向事件流程

event 用于 JS → Qt 的单向通知，**无回包**，不经过 `QtRequestManager`。

### JS 端

`createQtEventSender(getBridge, onError)` 返回 `sendEvent(name, options)`：

```ts
sendEvent('download_proxy.close_requested', {
  actionId?,        // 可选，传入固定 id 可实现 Qt 端重试去重
  params?,          // 仅 plain object 才会包含在消息体中
  data?,            // 非 undefined 才包含
  errorMessage?,    // 发送失败时的 toast 文案
  noMessage?,       // 为 true 时关闭失败 toast
}) // → { success, actionId }
```

### Qt 端

```
receive → type === 'event' → _event(incoming)
  → 校验 name / action_id 为非空字符串
  → _EVENT_HANDLERS.get(name)，未注册则忽略
  → 去重：key = (name, action_id)，命中则忽略
  → handler(self, event)
    → 抛异常 → 移除去重 key（允许同 action_id 重试）→ 异常继续上抛
```

去重实现：每弹窗一个 `OrderedDict` LRU，容量 256；因 `receive` 在工作线程执行，检查与写入在 `_event_lock` 保护下完成。

---

## 业务协议清单

### `dataManager` 通道（抓包数据管理）

请求参数 / 返回数据的类型定义见 Web 端 `types/qt/dataManager.d.ts`、Qt 端 `app_types/app_gui_types.py` 与 `app_types/db_types.py`。

| name | params 要点 | 返回 data（成功时；失败固定 `null`） | 说明 |
|---|---|---|---|
| `/mock_data/list` | `type`、`page_num`、`page_size`、url/params/response/method/request_content_type/enabled/时间段/operator 筛选 | `{ list, total, page_num, page_size }` | 分页查询 Mock 接口 |
| `/mock_data/detail` | `id` | `ApiDataDetail \| null` | 接口详情 |
| `/mock_data/create` | 接口字段 | `{ id }` | 新增 |
| `/mock_data/update` | 接口字段 | `null` | 更新 |
| `/mock_data/delete` | `id` | `null` | 删除 |
| `/mock_data/batch_delete` | 同 list 筛选字段 | `{ affected_count }` | 按条件批量删除 |
| `/mock_data/copy` | `id` | `{ id }`（新记录） | 复制 |
| `/variant/create` | 变体字段 | `{ id }` | 新增响应变体 |
| `/variant/update` | 变体字段 | `null` | 更新变体 |
| `/variant/delete` | `id` | `null` | 删除变体 |
| `/variant/reorder` | `api_data_id`、`variant_ids` | `null` | 变体排序 |
| `/variant/copy` | `id`、`api_data_id` | `{ id }`（新变体） | 复制变体 |
| `/variant/set_exclusive_enabled` | `id` | `null` | 设为唯一启用变体 |

> 注意：`data` 为纯业务载荷，成败只看信封 `status_code`（见「状态语义」）；DB 层 `OperationResult` 的 `status_code`/`status_msg` 已由 `_unpack_result` 上提，不再透传到载荷内。

### `downloadProxy` 通道（下载代理配置）

类型定义见 Web 端 `types/qt/downloadProxy.d.ts`、Qt 端 `app_types/download_types.py`。

| 种类 | name | params / data | 返回 | 说明 |
|---|---|---|---|---|
| request | `/download_proxy/list` | — | `{ list: ProxyConfig[] }` | 获取代理配置列表 |
| request | `/download_proxy/update` | `{ download_proxy_list: ProxyConfig[] }` | `null` | 全量覆盖保存 |
| event | `download_proxy.close_requested` | — | 无回包 | 请求关闭弹窗（emit `close_signal` → 主线程 `close()`） |

---

## 错误体系

### JS 端错误码（`QtRequestErrorCode`）

reject 值为 `QtRequestError` 实例（`Error` 子类），含 `code` / `message` / `reqName` / `config` 字段。

| 错误码 | 触发场景 |
|---|---|
| `TIMEOUT` | 请求超时（仅 `timeout > 0` 时可能触发） |
| `BRIDGE_NOT_READY` | bridge 未注册时发起请求 |
| `DESTROYED` | manager 已销毁后发起请求 |
| `BRIDGE_DESTROYED` | bridge 销毁导致所有 pending 请求被拒 |
| `RESPONSE_ERROR` | 回包 `status_code !== 0` |
| `SEND_FAILED` | `sendObjMsg` 返回失败或抛异常 |
| `PARSE_ERROR` | 回包 JSON 解析失败（按 `action_id` 正则定位 pending） |
| `RESPONSE_HANDLE_ERROR` | 响应处理过程中抛异常 |

### 业务状态码（`status_code`）

定义于 `config/enum/BIZ_CODE.py`，**以源文件为准**。编码规则：5 位负数，前两位为大类，`0` 表示成功。

| 码段 | 大类 |
|---|---|
| `0` | 成功 |
| `-10xxx` | 通用/系统错误 |
| `-20xxx` | 参数校验错误 |
| `-30xxx` | 数据操作错误 |
| `-40xxx` | 文件/IO 错误 |

### 异常 → status_code 映射（Qt 端）

handler 抛出的异常经 `lib/biz_error_lib.resolve_biz_error` 按顺序 `isinstance` 匹配（`DEFAULT_EXC_STATUS_MAP`），未匹配兜底 `BIZ_UNKNOWN_ERROR`：

| 异常类型 | status_code | status_msg |
|---|---|---|
| `KeyError` | `-20001` | `缺少必填参数: {e}` |
| `ValueError` | `-20002` | `str(e)` |
| `FileNotFoundError` | `-40001` | `str(e)` |
| `PermissionError` | `-40002` | `str(e)` |
| 其他 `Exception` | `-10001` | `str(e)` |

弹窗可传入自定义映射表扩展：`_MY_MAP + DEFAULT_EXC_STATUS_MAP`。

---

## 生命周期与线程模型

### JS 端销毁顺序

```
requestManager.destroy()        # 清理 pendingMap，pending 以 DESTROYED 拒绝
  → bridge.destroy()
      → publish(BEFORE_DESTROY) # 订阅者（manager）以 BRIDGE_DESTROYED 清理 pending
      → dispose()               # disconnect qt2js_signal + 清空订阅
      → destroyed = true
```

- `bridge.dispose()`：仅解绑与清订阅，可复用（`init` 可重新注册）
- `bridge.destroy()`：终态，先广播 `BEFORE_DESTROY` 再清理，保证 manager 能收到遗言事件
- 组件卸载时 hook 自动按上述顺序销毁，防止 pending Promise 永久挂起

### Qt 端线程模型

- `receive()` 与 `send_qt2js_dict_msg()` 均带 `@create_thread`：**每条消息在独立工作线程处理/回发**，不阻塞 GUI
- `receive` 另有 `@error_catch` 兜底，异常仅记日志
- 工作线程中的 UI 操作须通过 Signal 回主线程（如 `close_signal` → `dialog.close()`）
- 事件去重表等共享状态在 `_event_lock` 保护下访问

---

## 协议演进约定

新增协议时遵循以下约定，保持两端一致：

1. **命名**：request 用 `/namespace/action`（如 `/mock_data/create`）；event 用 `domain.action_name`（如 `download_proxy.close_requested`）
2. **参数**：request 参数放 `params`；`data` 为保留字段暂不使用
3. **回包**：handler 返回值经 `_unpack_result` 解包——`OperationResult` 的状态三元组上提为信封 `status_code`/`status_msg`，其余字段作为 `data`；失败走异常 → `resolve_biz_error`，不要在 `data` 内自行携带状态字段
4. **未知名**：新弹窗应对未知 request name 回包 `BIZ_PARAM_INVALID`（对齐 `DownloadProxyConfigDialog` 行为），避免前端只能靠超时兜底
5. **事件**：新增 event 需在弹窗实现 `_event` 分支与 `_EVENT_HANDLERS`（当前仅 `DownloadProxyConfigDialog` 实现；`MitmproxyDataEditDialog` 会静默忽略 event）
6. **类型同步**：Qt 端更新 `app_types/`，Web 端更新 `types/qt/*.d.ts` 与 `src/utils/bridge/type.d.ts`

---

## 附录：文件索引

### Qt 端（mock-api-server）

| 文件 | 说明 |
|---|---|
| `lib/TInteractObject.py` | 通信对象 `TInteractObj`：信号/槽 + `build_qt_response` |
| `app_types/qt_bridge_types.py` | 协议消息 TypedDict：`QtBridgeRequest` / `QtBridgeEvent` / `QtResponsePayload` |
| `lib/biz_error_lib.py` | 异常 → `status_code`/`status_msg` 映射 |
| `lib/bridge_lib.py` | `_unpack_result`：`OperationResult` 状态三元组上提信封 |
| `config/enum/BIZ_CODE.py` | 业务状态码常量 |
| `app_types/mcp_types.py` | MCP 工具返回类型（`success` 由 `status_code` 派生） |
| `qt_win/mitmproxy_data_edit_dialog.py` | `dataManager` 通道弹窗 |
| `qt_win/download_proxy_config_dialog.py` | `downloadProxy` 通道弹窗 |

### Web 端（mock-api-server-web-v3）

| 文件 | 说明 |
|---|---|
| `src/utils/bridge/QtBridge.ts` | 传输层封装 + `getQtBridgeData` |
| `src/utils/bridge/QtRequestManager.ts` | 请求/响应会话层 + `QtRequestError` |
| `src/utils/bridge/QtEventSender.ts` | `createQtEventSender` 单向事件 |
| `src/utils/bridge/InterceptorManager.ts` | axios 风格拦截器管理器 |
| `src/utils/bridge/defaultInterceptors.ts` | 默认解包 + 全局 toast 拦截器 |
| `src/utils/bridge/tools.ts` | `isBridgeUsable` |
| `src/utils/bridge/type.d.ts` | 桥接模块全部 TS 类型 |
| `types/qtSdk.d.ts` | QWebChannel 运行时 SDK 类型 |
| `types/qt/dataManager.d.ts`、`types/qt/downloadProxy.d.ts` | 各通道业务协议类型 |
| `apps/*/hooks/use*Bridge.ts`、`useDataManagerRequest.ts` | 各页面 bridge/manager 生命周期 hook |
| `apps/*/store/useQtBridge.ts` | `register` + `channelObj` 全局状态 |
