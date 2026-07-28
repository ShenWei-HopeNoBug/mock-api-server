# Qt Bridge 通信协议文档

## 概述

`QtRequestManager` 基于 `QtBridge` 实现了 Promise 化的请求/响应模式。JS 端向 Qt 客户端发送 `type = "request"` 消息，Qt 返回 `type = "response"` 消息，通过 `action_id` 进行请求-响应配对。

---

## 请求方向（JS → Qt）

`QtRequestManager.request` 通过 `bridge.sendObjMsg` 发送一条 JSON 消息，结构如下：

```json
{
  "type": "request",
  "name": "<请求名称>",
  "action_id": "<UUID>",
  "params": {},
  "data": {}
}
```

### 字段说明

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `type` | `string` | 是 | — | 固定 `"request"`，标识这是一次请求 |
| `name` | `string` | 是 | — | 请求名称（协议标识），由调用方传入 |
| `action_id` | `string` | 是 | — | 每次请求自动生成的 UUID，用于关联响应 |
| `params` | `object` | 否 | `{}` | 请求参数对象，对应 `RequestConfig.params` |
| `data` | `object` | 否 | `{}` | 请求业务数据对象，对应 `RequestConfig.data` |

### 发送链路

```
QtRequestManager.request
  → bridge.sendObjMsg(data)
    → JSON.stringify(data)
      → bridge.send(message)
        → Qt 底层 send_js2qt_msg(message)
```

---

## 响应方向（Qt → JS）

Qt 通过 `qt2js_signal` 下发 JSON 字符串，`QtRequestManager` 解析后匹配 `action_id` 对应的 pending 请求。响应消息结构如下：

```json
{
  "type": "response",
  "name": "<请求名称>",
  "action_id": "<对应请求的 UUID>",
  "status_code": 0,
  "status_msg": "",
  "data": {}
}
```

### 字段说明

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `type` | `string` | 是 | 必须为 `"response"`，否则消息被忽略 |
| `name` | `string` | 是 | 请求名称 |
| `action_id` | `string` | 是 | 与请求时的 `action_id` 一一对应，用于匹配 pending 请求 |
| `status_code` | `number` | 是 | 状态码，`0` 表示成功；非 `0` 表示失败，会以 `RESPONSE_ERROR` 拒绝 Promise |
| `status_msg` | `string` | 否 | 状态消息，失败时作为 reject 的 error message |
| `data` | `object` | 是 | 响应业务数据对象 |

### 接收链路

```
Qt qt2js_signal
  → QtBridge._receive(message)
    → publish(RECEIVE, message)
      → QtRequestManager.handleRawReceive(messageStr)
        → parseMessage(messageStr)
          → JSON.parse
            → 匹配 action_id → settle pending
```

---

## 关键流程

1. **发起请求**：生成 `action_id`（UUID）→ 存入 `pendingMap` → 设置超时定时器 → 发送消息
2. **超时**：默认 `15000ms`，可通过 `RequestConfig.timeout` 覆盖；超时后以 `TIMEOUT` 错误拒绝
3. **响应匹配**：收到消息 → `JSON.parse` → 校验 `type === "response"` → 用 `action_id` 查 `pendingMap` → 匹配则 settle
4. **成功条件**：`status_code === 0` → resolve 整个 `ResponsePayload`
5. **失败条件**：`status_code !== 0` → reject `RESPONSE_ERROR`
6. **解析失败兜底**：`JSON.parse` 失败时，用正则 `"action_id":"<value>"` 模糊匹配原始字符串定位 pending 请求，以 `PARSE_ERROR` 拒绝

---

## 错误码汇总

| 错误码 | 触发场景 |
|---|---|
| `TIMEOUT` | 请求超时 |
| `BRIDGE_NOT_READY` | bridge 未注册时发起请求 |
| `DESTROYED` | manager 已销毁 |
| `BRIDGE_DESTROYED` | bridge 销毁导致 pending 清理 |
| `RESPONSE_ERROR` | `status_code !== 0` |
| `SEND_FAILED` | `sendObjMsg` 返回失败或抛异常 |
| `PARSE_ERROR` | 响应 JSON 解析失败 |
| `RESPONSE_HANDLE_ERROR` | 响应处理过程中抛异常 |

---

## 类型定义

相关 TypeScript 类型定义位于 `type.d.ts`：

- `RequestConfig` — 请求配置
- `ResponsePayload` — Qt 下发的响应载荷
- `PendingRequest` — pending 请求内部记录
- `QtRequestErrorCode` — 错误码联合类型
- `QtRequestError` — 请求错误接口
- `ParseMessageResult` — 消息解析结果
- `ConstructorOptions` — 构造器选项
