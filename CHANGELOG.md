# Changelog

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
