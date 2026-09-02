# StaticFileHandler 方法职责图

## 1. 总体调用链

```text
match(path, request_headers)
  ├─ _resolve_file(route_path)
  │   └─ 解析路径 + 安全校验（文件存在/目录越界）
  ├─ _should_use_throttled(file_path, range_header)
  │   └─ 按资源类型与限速开关做分流决策
  ├─ _serve_throttled(...)   # 需要节流时
  │   ├─ _check_cache_hit(...)                -> 304?
  │   ├─ _build_throttled_meta_or_response(...)
  │   │   ├─ _check_if_range(...)
  │   │   ├─ _parse_range(...)
  │   │   ├─ _build_partial_meta(...) / _build_full_meta(...)
  │   │   ├─ _build_416_response(...)         -> 416?
  │   │   └─ _apply_common_headers(...)
  │   └─ ThrottledFileReader + Response(...)
  └─ _serve_direct(...)      # 不需要节流时
      ├─ _check_cache_hit(...)                -> 304?
      ├─（限速视频探测）Response(200 empty)
      ├─ send_from_directory(...)
      └─ _apply_cache_headers(...) -> _apply_common_headers(...)
```

---

## 2. 编排层（入口/路由）

### `match(path, request_headers)`
- 入口编排方法，不处理协议细节。
- 职责：文件解析、分流决策、路由到 direct 或 throttled。

### `_should_use_throttled(file_path, range_header)`
- 统一节流策略判断，减少 `match` 中 if/else 嵌套。
- 当前规则：
  - 未开启限速：全部 direct。
  - 图片：限速开启后无论是否 `Range` 都节流。
  - 视频：仅 `Range` 请求节流，无 `Range` 走探测响应。
  - 其他：仅 `Range` 请求节流。

---

## 3. Direct 路径（非节流发送）

### `_serve_direct(file_path, file_name, request_headers)`
- 负责“直接发送文件”路径。
- 关键职责：
  - 先做缓存命中判断（304 优先）。
  - 限速 + 视频 + 无 Range 时返回 `200 empty` 探测响应。
  - 其余通过 `send_from_directory` 发送。
  - 在框架返回后补充统一缓存相关响应头。

---

## 4. Throttled 路径（节流发送）

### `_serve_throttled(file_path, file_name, range_header, request_headers)`
- 负责节流传输主流程。
- 职责聚焦：文件大小读取、调用元信息构建、构建 `ThrottledFileReader` 输出。

### `_build_throttled_meta_or_response(...)`
- 负责协议细节集中处理：
  - `If-Range` 校验。
  - `Range` 解析。
  - 合法时生成 `200/206` 元信息。
  - 非法时直接返回 `416`。
  - 视频限速下避免 200 全量传输（必要时回退 416）。

### `_build_partial_meta(start, end, file_total)`
- 生成 `206` 响应元信息。
- 包含 `Content-Range`、`Accept-Ranges`、`Vary: Range`。

### `_build_full_meta(file_total)`
- 生成 `200` 响应元信息（完整区间）。

---

## 5. 协议与缓存工具层

### `_check_cache_hit(file_path, request_headers, stat)`
- 条件请求命中判定（`If-None-Match` / `If-Modified-Since`）。
- 命中后上层直接返回 304，跳过文件发送与节流。

### `_check_if_range(stat, request_headers)`
- `If-Range` 校验：ETag 强比较 + 日期比较。

### `_parse_range(range_header, file_total)`
- 解析单区间 `Range`（`start-end`、`start-`、`-suffix`）。

### `_compute_etag(file_size, mtime)`
- 生成 ETag（`size + mtime(ms)`）。

### `_format_http_date(timestamp)`
- 统一 HTTP 日期格式化。

---

## 6. 响应头与终态响应构建

### `_apply_common_headers(headers, file_path, stat, status_code)`
- 统一写入：`ETag`、`Last-Modified`、`Cache-Control`。
- `206/416` 使用 partial 强缓存；其他状态按文件类型策略。

### `_apply_cache_headers(response, file_path, stat)`
- `send_from_directory` 返回后补头的薄封装（内部复用 `_apply_common_headers`）。

### `_build_304_response(file_path, stat)`
- 构建 304 响应（无 body）。

### `_build_416_response(content_type, file_total, stat)`
- 构建 416 响应（含 `Content-Range: bytes */total`）。

---

## 7. 资源类型判断与缓存策略

### `_is_image(file_path)` / `_is_video(file_path)`
- MIME 前缀判断资源类型。

### `_build_cache_control(file_path)`
- 普通缓存策略：图片强缓存，其它协商缓存。

### `_build_partial_cache_control()`
- `206/416` 专用强缓存策略。

---

## 8. 流式读取执行器

### `ThrottledFileReader`
- 文件读取执行器（按 chunk 读取 + 每块 sleep）。
- 与 `Response(reader, ...)` 配合实现弱网节流效果。
