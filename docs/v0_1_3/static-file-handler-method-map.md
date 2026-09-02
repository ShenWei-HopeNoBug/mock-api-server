# StaticFileHandler 方法职责图（按当前实现）

## 0. 术语约定

- `探测响应（200 empty）`：指限速模式下视频无 `Range` 请求时，返回空 body 的 `200` 响应，用于引导浏览器立即改发 `Range` 请求。
- `416 回退`：指在限速视频场景中，当流程退化为 `200` 全量传输候选时，主动返回 `416`，强制浏览器重新走分段请求。
- `direct 路径`：指通过 `_serve_direct(...)` 处理的非节流返回路径。
- `throttled 路径`：指通过 `_serve_throttled(...)` + `create_reader(...)` 处理的节流返回路径。

## 1. 模块入口与总调用链

> `lib/static_file_lib.py` 里包含 2 个入口：
> - `create_assets_replace_func(...)`：生成静态资源 URL 替换函数
> - `StaticFileHandler.match(...)`：处理静态文件请求

```text
create_assets_replace_func(include_files, static_host, static_url_path, static_load_speed)
  ├─ include_files 为空 -> None
  ├─ get_static_match_regexp(include_files)
  └─ 返回 replace_assets(response_text)
      └─ 将匹配到的静态资源 URL 重写为 {static_host}{assets_route}/{file_name}

match(path, request_headers)
  ├─ _resolve_file(route_path)
  │   ├─ is_file_request(...)
  │   ├─ basename + realpath + containment 校验
  │   └─ _resolve_file_fail(...)（404/403）
  ├─ _should_use_throttled(file_path, range_header)
  ├─ _serve_throttled(...)    # 需要节流
  │   ├─ _check_cache_hit(...) -> 304?
  │   ├─ _build_throttled_meta_or_response(...)
  │   │   ├─ _check_if_range(...)
  │   │   ├─ _parse_range(...)
  │   │   ├─ _build_partial_meta(...) / _build_full_meta(...)
  │   │   ├─ _build_416_response(...) -> 416?
  │   │   └─ _apply_common_headers(...)
  │   └─ _throttle.create_reader(...) + Response(...)
  └─ _serve_direct(...)       # 直接返回
      ├─ _check_cache_hit(...) -> 304?
      ├─ （限速视频探测）Response(200 empty)
      ├─ send_from_directory(..., conditional=has_range_header)
      └─ _apply_cache_headers(...) -> _apply_common_headers(...)
```

---

## 2. 编排层（入口/分流）

### `match(path, request_headers)`
- 统一入口，只做编排：路径解析、分流决策、路由到 direct / throttled。
- 解析失败时返回 `_resolve_file` 中已经准备好的 `(msg, status_code)`。

### `_should_use_throttled(file_path, range_header)`
- 节流分流规则（当前代码）：
  - `static_load_speed <= 0`：始终 direct。
  - 图片：开启限速后始终 throttled（即使无 `Range`）。
  - 视频：仅 `Range` 请求 throttled；无 `Range` 走 direct 探测。
  - 其他类型：仅 `Range` 请求 throttled。

---

## 3. 路径解析与安全校验

### `_resolve_file(route_path)`
- 负责文件请求识别、文件名提取、越界校验、存在性校验。
- 安全点：`basename` 去目录层级 + `realpath` containment 防目录穿越/符号链接越界。

### `_resolve_file_fail(msg, status_code)`
- 统一构造解析失败返回结构：`valid=False` + `result=(msg, status_code)`。

---

## 4. Direct 路径（非节流发送）

### `_serve_direct(file_path, file_name, request_headers)`
- 先 `os.stat`，后续复用同一 `stat`（避免 TOCTOU）。
- 缓存命中时直接 `304`（`_build_304_response`）。
- **限速 + 视频 + 无 Range**：返回探测响应（`200 empty`，`Content-Length: 0`），引导浏览器发 `Range`。
- 其余走 `send_from_directory`：
  - `conditional=True` 仅在有 `Range` 时启用；
  - `200/206/304` 时补齐自定义缓存头，保持响应头一致性。

---

## 5. Throttled 路径（节流发送）

### `_serve_throttled(file_path, file_name, range_header, request_headers)`
- 先做 304 条件缓存判断，命中则短路返回。
- 第一次 `open` 仅用于获取 `file_total` 与构建协议元信息；失败返回 `404`。
- 调用 `_build_throttled_meta_or_response(...)`：返回 `ResponseMeta` 或直接终态 `Response`（如 416）。
- 第二次通过注入策略 `self._throttle.create_reader(...)` 创建 reader；失败同样返回 `404`。

### `_build_throttled_meta_or_response(...)`
- 统一处理 `If-Range` / `Range` 语义。
- `Range` 非法时返回 `416`。
- 合法时生成 `206`（分段）或 `200`（整段）元信息。
- 限速视频若退化为 `200`，执行 `416 回退`，避免全量无分段传输。

### `_build_partial_meta(start, end, file_total)`
- 构建 `206` 元信息，含 `Content-Range`、`Accept-Ranges`、`Vary: Range`。

### `_build_full_meta(file_total)`
- 构建 `200` 元信息，范围为完整文件。

---

## 6. 协议与缓存判定

### `_check_cache_hit(file_path, request_headers, stat)`
- 条件请求命中判定：`If-None-Match`（优先）/`If-Modified-Since`。
- `If-None-Match` 支持 `*` 与弱 ETag 比较。

### `_check_if_range(stat, request_headers)`
- `If-Range` 校验：
  - ETag：强比较；
  - 日期：与格式化后的 `mtime` 精确比较。

### `_parse_range(range_header, file_total)`
- 仅支持单区间：`start-end`、`start-`、`-suffix`。
- 空文件、越界或格式非法返回 `None`。

### `_compute_etag(file_size, mtime)` / `_format_http_date(timestamp)`
- 前者生成强 ETag（`"size-mtime_ms"`）。
- 后者统一输出 HTTP 日期（IMF-fixdate）。

---

## 7. 响应构建与头部策略

### `_apply_common_headers(headers, file_path, stat, status_code)`
- 统一写入：`ETag`、`Last-Modified`、`Cache-Control`。
- `206/416` 使用 partial 强缓存；其他状态按资源类型缓存策略。

### `_apply_cache_headers(response, file_path, stat)`
- 对 `send_from_directory` 响应补头的薄封装。

### `_build_304_response(file_path, stat)`
- 返回无 body 的 `304`，并附带缓存相关头。

### `_build_416_response(content_type, file_total, stat)`
- 返回 `416`，包含 `Content-Range: bytes */{total}` 与 `Content-Length: 0`。

---

## 8. 资源类型与辅助方法

### `_is_image(file_path)` / `_is_video(file_path)`
- 基于 MIME 前缀判断图片/视频。

### `_build_cache_control(file_path)` / `_build_partial_cache_control()`
- 普通策略：图片强缓存、其他协商缓存。
- 分段策略：`206/416` 统一强缓存。

### `_format_size(size_bytes)`
- 仅用于日志打印，格式化 B/KB/MB。

---

## 9. 依赖说明（当前实现）

- 节流读取执行器不在本类内硬编码，实际由注入的 `throttle_strategy` 提供：`self._throttle.create_reader(...)`。
- 因此开启限速场景下，`StaticFileHandler` 依赖外部正确注入可用的节流策略对象。
