# Changelog

## 0.3.0 - 2026-08-17

### Added

- Added a `glama.json` manifest at the repository root for Glama registry profile completion (maintainers, displayName, categories, tags, websiteUrl).
- Added regression coverage for configuration defaults, normalization and secret redaction, cross-tool request serialization and telemetry, lock recovery after failures, MCP tool metadata, structured output schemas, and the configuration resource.
- Added structured logging in `ToolLimiter.run` covering `queue.wait` and `tool.complete` events with `queue_wait_ms` / `exec_ms` fields, making serialized execution observable without duplicate contention logs.
- Added an explicit `meta` payload (`SINGLE_REQUEST_META`) on every tool, exposing `icpquery/concurrency_mode: single_request_complete`, `icpquery/concurrency_reason`, and `icpquery/max_parallel_recommended: 1` to agents via `tools/list` `_meta`.
- Added `website_url` as server initialization metadata and declared `dependencies` for the MCP SDK's install/dev workflows.
- Added explicit `structured_output=True` on all four tools (previously implied by Pydantic return types).

### Changed

- Strengthened `SERVER_INSTRUCTIONS` to state explicitly that remote tools share a single-request-complete lock within one server instance and that agents SHOULD issue them strictly sequentially, never in parallel.
- Strengthened the `icp_query` and `icp_blacklist` tool descriptions to disclose the concurrency-sensitive upstream, the shared serialization lock, the default rate limits, and the "MUST NOT fan out parallel calls" guidance; `check_environment` and `config_show` descriptions now note they are exempt from the serialization queue.
- Reworked `ToolLimiter.run` around a typed shared-lock invariant and contention timing; `SlidingWindowLimiter.acquire` now records rate-limit waits without exposing an unused return value.
- Changed `Config.concurrency` default from `5` to `1` to match `Config.normalized()` behavior and remove the misleading impression that parallel detail fetching is allowed.
- Documented per-instance lock semantics and the need for external coordination when multi-worker deployments require the same cross-instance invariant in `ratelimit.py`.
- Reorganized README: numbered installation steps (1. install uv → 2. configure client), added uv prerequisite, version-pinning guidance, and pipx alternative; consolidated all config into a dedicated section with a default-value column.
- Simplified the quick-start MCP config example: removed `ICP_RATE_LIMIT_QUERY_PER_MIN` and `ICP_RATE_LIMIT_BLACKLIST_PER_MIN` (defaults are built-in), exposed `ICP_PROXY_TUNNEL` directly with interception guidance.
- Marked `ICP_CONCURRENCY` and `ICP_RATE_LIMIT_MAX_CONCURRENT` as "固定 1（不可调）" in the env var table to reflect the hardcoded single-request-complete invariant.
- Merged the tool list and query parameters into a single table; renamed "发布验证" to "开发" with compile/check/build commands.
- Added `mcp-name` ownership marker to README for MCP Registry verification.

## 0.2.0 - 2026-07-29

### Added

- Added MCP Tool Annotations, meaningful titles, complete parameter descriptions, server instructions, and a namespaced configuration resource.
- Added PyPI project metadata and an `uvx` MCP client configuration example.
- Added explicit Pydantic output models for environment diagnostics, configuration, MIIT status and errors, pagination, and provider data.

### Changed

- Updated the README compatibility badge to MCP SDK 2.0.0.
- Redacted configured proxy URLs from diagnostic tool output.
- Aligned the public `page_size` schema with the upstream maximum of 26.
- Reduced the MCP runtime dependency to the SDK package without the unused CLI extra.
- Standardized builds on Hatchling and explicitly included release examples in the source distribution.
- Migrated from FastMCP v1 to the official MCP Python SDK 2.0.0 `MCPServer` API.
- Added dual-era protocol support for MCP `2026-07-28` and legacy `2025-11-25` clients.
- Declared server identity metadata through the public `MCPServer` constructor and migrated protocol model fields to snake_case.

## 0.1.0 - 2026-07-10

### Changed

- 将 MCP Python SDK 依赖更新为当前 PyPI 最新版本 `mcp[cli]>=1.28.1`，并同步更新 README 徽章与运行要求。
- 将 HTTP 客户端依赖调整为 `httpx[socks]>=0.27.0`，兼容本地 SOCKS 代理环境。
- 对齐 `SurveyHub-MCP` 补全 `.gitignore`、MIT `LICENSE` 和 pyproject 许可证声明。
- 增加 MCP 内部单例队列保护：即使 Qoder/IDE 默认并发触发 5/10 个工具调用，`icp_query` 和 `icp_blacklist` 也会在服务进程内排队串行执行，前一个完整结束后才进入下一个真实查询。
- `rate_limit.max_concurrent` 强制归一为 `1`，作为防止目标接口风控/banned 的安全默认值。
- `concurrency` 强制归一为 `1`，App、小程序、快应用详情补全也改为串行访问目标接口。
- 在 `server.py`、`core/config.py`、`core/ratelimit.py`、`config.example.yml` 和 `README.md` 增加注释/说明，明确智能体默认仅并发 1 个真实查询。

### Added

- 初始化 `ICPQuery-MCP` Python3 项目，采用 `SoftwareCopyright-MCP` 同款 `src-layout`、`pyproject.toml`、本地 CLI 和 FastMCP 服务结构。
- 复刻 `icp-query-go` 核心 MCP 能力：
  - `icp_query`：查询 ICP 备案信息，支持 `web/app/mapp/kapp`。
  - `icp_blacklist`：查询违法违规黑名单，支持 `bweb/bapp/bmapp/bkapp`。
  - `config_show`：输出当前运行配置。
  - `check_environment`：检查依赖、配置和支持的查询类型。
- 实现工信部接口调用流程：
  - 自动获取 `auth` token。
  - 自动请求并识别滑块验证码。
  - 提交验证码结果获取签名。
  - 查询备案/黑名单接口。
  - 对 App、小程序、快应用结果自动补充详情信息。
- 增加 Python 版滑块验证码偏移识别模块，使用 Pillow 进行图片解码、降采样、颜色量化和缺口定位。
- 增加 MCP 工具级限流与并发控制，支持查询频率和最大并发配置。
- 增加 YAML 配置读取与 `ICP_` 前缀环境变量覆盖。
- 增加 `icpquery` 本地 CLI：
  - `icpquery query`
  - `icpquery config-show`
  - `icpquery check-env`
  - `icpquery version`
- 增加 `config.example.yml` 示例配置。
- 增加中文 `README.md`，包含安装、运行、MCP 客户端配置、CLI 使用和免责声明。
- 增加 `.gitignore`，忽略虚拟环境、缓存、构建产物和系统文件。
### Verified

- 已创建 Python 3.11 虚拟环境并安装项目依赖。
- 已验证 MCP Server 可创建 `FastMCP` 实例。
- 已验证 CLI：
  - `icpquery check-env`
  - `icpquery config-show`
- 已验证 `baidu.com` ICP 查询返回 `code=200`、`success=true`。

### Notes

- 本项目通过非官方方式调用工信部 ICP 备案查询接口，接口行为、验证码策略或风控策略可能变化。
- `proxy.pool.url` 和本地 IPv6 出口轮换暂保留配置结构，当前 Python 版本优先支持显式代理 `proxy` 和固定代理隧道 `proxy.tunnel`。
