<!-- mcp-name: io.github.helGayhub233/icpquery-mcp -->

<h1 align="center">ICPQuery-MCP</h1>

<p align="center">查询网站、App、小程序及快应用备案与违法违规黑名单的 MCP Server</p>

<p align="center">
  <img src="https://badgen.net/pypi/v/icpquery-mcp?label=PyPI&color=3775A9&cache=300" alt="PyPI v0.2.0"/>
  <img src="https://badgen.net/badge/Python/%3E%3D3.10/3776AB" alt="Python >=3.10"/>
  <img src="https://badgen.net/badge/MCP%20SDK/2.0.0/6F42C1" alt="MCP SDK 2.0.0"/>
  <img src="https://badgen.net/pypi/dm/icpquery-mcp?label=Downloads&color=2EA44F&cache=86400" alt="PyPI 下载量"/>
  <img src="https://badgen.net/github/license/helGayhub233/ICPQuery-MCP?label=License&color=blue" alt="许可证"/>
</p>

## 支持类型

| 类型 | 能力 |
| --- | --- |
| 网站备案 | 域名、主体名称、备案号等关键词查询 |
| App 备案 | App 名称、主体名称等关键词查询，并自动补充详情 |
| 小程序备案 | 小程序名称、主体名称等关键词查询，并自动补充详情 |
| 快应用备案 | 快应用名称、主体名称等关键词查询，并自动补充详情 |
| 违法违规黑名单 | 网站、App、小程序、快应用黑名单查询 |

## 快速开始

### 1. 安装 uv

`uvx`（uv 自带）是 Python 生态中 `npx` 的等价物——在临时隔离环境中下载并运行包，无需全局安装。

```bash
# Linux / macOS（官方安装脚本）
curl -LsSf https://astral.sh/uv/install.sh | sh

# macOS（Homebrew）
brew install uv
```

### 2. 配置 MCP 客户端

将以下配置加入支持 MCP 的客户端（Claude Desktop、Cursor 等），无需预先安装 ICPQuery-MCP：

```json
{
  "mcpServers": {
    "icp-query": {
      "command": "uvx",
      "args": ["icpquery-mcp"],
      "env": {
        "ICP_PROXY_TUNNEL": "http://127.0.0.1:7890"
      }
    }
  }
}
```

目标接口有创宇盾防护，高频访问或特定 IP 可能触发拦截。触发拦截时通过 `ICP_PROXY_TUNNEL` 走代理访问；不需要代理时移除 `env` 或将值留空。代理地址须带协议前缀（`http://`、`https://` 或 `socks5://`）。

> **版本锁定**（生产环境推荐）：将 `args` 替换为 `["--from", "icpquery-mcp==0.2.0", "icpquery-mcp"]`，避免随发布版本浮动。

频率限制已内置默认值（query 5 次/分钟、blacklist 3 次/分钟），无需额外配置。完整配置示例见 `mcp.json.example` 和 `config.example.yml`。

### 其他安装方式

**pip：**

```bash
python -m pip install -U icpquery-mcp
icpquery-mcp
```

此时将客户端配置中的 `command` 改为 `icpquery-mcp`，`args` 设为 `[]`。

**pipx：**

```bash
pipx install icpquery-mcp
icpquery-mcp
```

**从源码：**

```bash
git clone https://github.com/helGayhub233/ICPQuery-MCP.git
cd ICPQuery-MCP
uv sync
uv run icpquery-mcp
```

从源码运行时，推荐在客户端配置中固定项目目录：

```json
{
  "mcpServers": {
    "icp-query": {
      "command": "uv",
      "args": ["--directory", "/absolute/path/to/ICPQuery-MCP", "run", "icpquery-mcp"]
    }
  }
}
```

## 配置

### 环境变量

环境变量统一使用 `ICP_` 前缀。`config_show` 和 `check_environment` 会将已配置的代理地址显示为 `<configured>`，避免凭据泄漏到 MCP 对话上下文。

| 环境变量 | 说明 | 默认值 |
| --- | --- | --- |
| `ICP_TIMEOUT` | HTTP 请求超时秒数 | `30` |
| `ICP_CONCURRENCY` | 详情补全并发数（固定为串行，不可调） | `1` |
| `ICP_RATE_LIMIT_ENABLED` | 是否启用 MCP 工具频率限制 | `true` |
| `ICP_RATE_LIMIT_QUERY_PER_MIN` | `icp_query` 每分钟允许次数 | `5` |
| `ICP_RATE_LIMIT_BLACKLIST_PER_MIN` | `icp_blacklist` 每分钟允许次数 | `3` |
| `ICP_RATE_LIMIT_MAX_CONCURRENT` | 查询工具最大并发数（固定为串行，不可调） | `1` |
| `ICP_PROXY_TUNNEL` | 固定代理地址，例如 `socks5://127.0.0.1:1080` | — |
| `ICP_PROXY_POOL_URL` | 代理池 API 地址（当前保留） | — |
| `ICP_PROXY_POOL_SIZE` | 代理池大小（当前保留） | — |
| `ICP_PROXY_POOL_IPV6` | 本地 IPv6 出口轮换开关（当前保留） | — |

## 工具列表

| 工具 | 说明 | 参数 |
| --- | --- | --- |
| `icp_query` | 查询 ICP 备案信息 | `name`（关键词）、`type`（`web`/`app`/`mapp`/`kapp`，默认 `web`）、`page`（默认 `1`）、`page_size`（最大 `26`）、`proxy`（单次代理） |
| `icp_blacklist` | 查询违法违规黑名单 | `name`（关键词）、`type`（`bweb`/`bapp`/`bmapp`/`bkapp`，默认 `bweb`）、`proxy`（单次代理） |
| `config_show` | 查看当前运行配置 | — |
| `check_environment` | 检查运行环境、依赖和支持类型 | — |

`proxy` 参数优先级高于 `ICP_PROXY_TUNNEL` 环境变量。

## 本地 CLI

除 MCP 工具外，项目还提供独立的 CLI 入口 `icpquery`：

```bash
icpquery check-env              # 检查运行环境
icpquery config-show            # 查看当前配置
icpquery query baidu.com        # 查询网站备案
icpquery query 微信 -t app      # 查询 App 备案
icpquery query baidu.com -t bweb  # 查询网站黑名单
```

## 请求限制

项目在单个 MCP server 实例内做本地保护，避免客户端并发请求直接打到目标接口。

| 工具 | 控制方式 |
| --- | --- |
| `icp_query` | 同一 server 实例共享队列执行，默认每分钟 `5` 次 |
| `icp_blacklist` | 同一 server 实例共享队列执行，默认每分钟 `3` 次 |
| App/小程序/快应用详情补全 | 串行执行 |

Qoder 等 MCP 客户端可能默认并发触发 5-10 个 tool call；同一 server（同一 `ToolLimiter`）实例会强制串行化，前一个查询完整结束后，下一个查询才会访问目标接口。多 server/worker 部署如需跨实例保持同样约束，须提供外部协调机制。

## MCP 协议兼容性

服务使用官方 `MCPServer` API，同时兼容 `2026-07-28` 新协议和 `2025-11-25` 旧协议。SDK 会根据客户端自动选择 `server/discover` 或传统 `initialize` 流程，无需启动两套服务。

## 项目结构

```text
src/icpquery_mcp/
  server.py              # MCP 入口
  cli.py                 # 本地 CLI
  core/
    client.py            # 工信部接口调用、token、验证码和详情补全
    captcha.py           # 滑块验证码偏移识别
    config.py            # YAML 和环境变量配置
    ratelimit.py         # 频率控制和单例队列保护
  tools/
    local_tools.py       # MCP 工具与 CLI 复用封装
```

## 开发

```bash
# 编译检查
python -m compileall src

# 检查运行环境
icpquery check-env

# 单元测试
python -m unittest discover -s tests -v

# 构建
uv build
```

版本记录见 `CHANGELOG.md`。

## 注意事项

**本项目仅供学习和技术研究使用，严禁用于任何商业或非法用途。**

请只在合法授权范围内使用，并自行承担接口变化、验证码策略变化、目标风控或网络环境导致的失败风险。

## 许可证

MIT License，见 `LICENSE`。
