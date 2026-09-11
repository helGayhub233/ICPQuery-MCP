# Changelog

## 0.4.0 - 2026-09-11

### Fixed

- Fixed intermittent `Error executing tool icp_query: 验证码识别失败` ("captcha recognition failed") by constraining the slider-gap candidate to the piece's own size: a strict pass now only accepts near-square runs whose width and height match the slider block (scaled to half), so a larger flat background region can no longer outscore the real gap.
- Kept the previous "largest near-square same-color block" behavior as a fallback that only applies when the strict pass finds nothing, so valid matches are not lost when the size constraint is too tight.

### Changed

- Updated the MCP Python SDK dependency to the latest 2.2.0 and raised the requirement to `mcp>=2.2.0,<3`, keeping `uv.lock`, the server dependency metadata and the README compatibility badge in sync.

### Added

- Added `_piece_side()` in `captcha.py` to measure the slider block's actual side length from the alpha-channel bounding box instead of assuming the canvas size.
- Added a bounded retry in `ICPQueryClient._check_img` (`_CAPTCHA_ATTEMPTS = 2`); the upstream returns a fresh image per attempt, so one automatic retry keeps the caller-visible failure rate low. The original logic moved to `_solve_captcha`.
- Added `tests/test_captcha.py` regression coverage: `_piece_side` uses the opaque bounding box, a larger same-color decoy no longer displaces the real gap, and the fallback path still returns the largest near-square block when no sized candidate exists.

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
- Marked `ICP_CONCURRENCY` and `ICP_RATE_LIMIT_MAX_CONCURRENT` as "fixed at 1 (not configurable)" in the env var table to reflect the hardcoded single-request-complete invariant.
- Merged the tool list and query parameters into a single table; renamed the "Release verification" section to "Development" with compile/check/build commands.
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

- Updated the MCP Python SDK dependency to the then-latest PyPI release `mcp[cli]>=1.28.1`, syncing the README badge and runtime requirements.
- Adjusted the HTTP client dependency to `httpx[socks]>=0.27.0` for local SOCKS proxy environments.
- Aligned with `SurveyHub-MCP` by adding `.gitignore`, the MIT `LICENSE`, and the pyproject license declaration.
- Added in-process singleton queue protection: even when a Qoder/IDE client fans out 5-10 tool calls concurrently, `icp_query` and `icp_blacklist` queue up and execute serially inside the server process, starting the next real query only after the previous one fully completes.
- Normalized `rate_limit.max_concurrent` to `1` as a safe default against upstream risk control and bans.
- Normalized `concurrency` to `1`; App, Mini Program and Quick App detail fetching now also access the upstream serially.
- Added comments and notes in `server.py`, `core/config.py`, `core/ratelimit.py`, `config.example.yml` and `README.md` stating that agents default to exactly one real query in flight.

### Added

- Initialized the `ICPQuery-MCP` Python project with the same `src-layout`, `pyproject.toml`, local CLI and FastMCP server structure used by `SoftwareCopyright-MCP`.
- Ported the core MCP capabilities of `icp-query-go`:
  - `icp_query`: query ICP filing information, supporting `web/app/mapp/kapp`.
  - `icp_blacklist`: query the violation blacklist, supporting `bweb/bapp/bmapp/bkapp`.
  - `config_show`: print the current runtime configuration.
  - `check_environment`: check dependencies, configuration and supported query types.
- Implemented the MIIT API flow:
  - Automatically obtain the `auth` token.
  - Automatically request and solve the slider captcha.
  - Submit the captcha result to obtain a signature.
  - Query the filing / blacklist endpoints.
  - Automatically enrich App, Mini Program and Quick App results with details.
- Added a Python slider-captcha offset module using Pillow for image decoding, downsampling, color quantization and gap localization.
- Added MCP tool-level rate limiting and concurrency control with configurable query rate and maximum concurrency.
- Added YAML configuration loading with `ICP_`-prefixed environment variable overrides.
- Added the local `icpquery` CLI:
  - `icpquery query`
  - `icpquery config-show`
  - `icpquery check-env`
  - `icpquery version`
- Added `config.example.yml` as an example configuration.
- Added a Chinese `README.md` covering installation, running, MCP client configuration, CLI usage and the disclaimer.
- Added `.gitignore` for virtual environments, caches, build artifacts and OS files.

### Verified

- Created a Python 3.11 virtual environment and installed the project dependencies.
- Verified the MCP server can create a `FastMCP` instance.
- Verified the CLI:
  - `icpquery check-env`
  - `icpquery config-show`
- Verified an ICP query for `baidu.com` returns `code=200` and `success=true`.

### Notes

- This project calls the MIIT ICP filing API in a non-official way; endpoint behavior, captcha policy or risk-control policy may change.
- `proxy.pool.url` and local IPv6 egress rotation are kept as configuration placeholders only; the current Python version favors the explicit `proxy` and the fixed tunnel `proxy.tunnel`.
