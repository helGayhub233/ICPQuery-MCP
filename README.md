<h1 align="center">ICPQuery-MCP</h1>

<p align="center">基于 <code>FastMCP</code> 编写的 ICP 备案查询 MCP Server，支持网站、App、小程序、快应用备案信息和违法违规黑名单查询</p>

<p align="center">
  <img src="https://img.shields.io/pypi/v/icpquery-mcp?label=PyPI&color=3775A9" alt="PyPI 版本"/>
  <img src="https://img.shields.io/badge/Python-%3E%3D3.10-3776AB" alt="Python >=3.10"/>
  <img src="https://img.shields.io/badge/MCP%20SDK-%3E%3D1.28.1-6F42C1" alt="MCP SDK >=1.28.1"/>
  <img src="https://img.shields.io/pypi/dm/icpquery-mcp?label=Downloads&color=2EA44F&cacheSeconds=86400" alt="PyPI 下载量"/>
  <img src="https://img.shields.io/github/license/helGayhub233/ICPQuery-MCP?label=License&color=blue" alt="许可证"/>
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

### 从源码运行

要求 Python `>=3.10`，MCP Python SDK `>=1.28.1`。

```bash
cd ICPQuery-MCP
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
icpquery-mcp
```

### MCP 配置

推荐在 MCP 客户端中固定项目目录运行：

```json
{
  "mcpServers": {
    "icp-query": {
      "command": "uv",
      "args": [
        "--directory",
        "/absolute/path/to/ICPQuery-MCP",
        "run",
        "icpquery-mcp"
      ],
      "env": {
        "ICP_RATE_LIMIT_QUERY_PER_MIN": "5",
        "ICP_RATE_LIMIT_BLACKLIST_PER_MIN": "3",
        "ICP_PROXY_TUNNEL": ""
      }
    }
  }
}
```

如果已经在虚拟环境中安装，也可以直接使用入口命令：

```json
{
  "mcpServers": {
    "icp-query": {
      "command": "icpquery-mcp",
      "args": []
    }
  }
}
```

## 本地 CLI

```bash
icpquery check-env
icpquery config-show
icpquery query baidu.com
icpquery query 微信 -t app
icpquery query baidu.com -t bweb
```

## 环境变量

环境变量使用 `ICP_` 前缀命名规范。

| 环境变量 | 说明 |
| --- | --- |
| `ICP_TIMEOUT` | HTTP 请求超时秒数，默认 `30` |
| `ICP_CONCURRENCY` | 详情补全并发数，内部会归一为 `1` |
| `ICP_RATE_LIMIT_ENABLED` | 是否启用 MCP 工具频率限制，默认 `true` |
| `ICP_RATE_LIMIT_QUERY_PER_MIN` | `icp_query` 每分钟允许次数，默认 `5` |
| `ICP_RATE_LIMIT_BLACKLIST_PER_MIN` | `icp_blacklist` 每分钟允许次数，默认 `3` |
| `ICP_RATE_LIMIT_MAX_CONCURRENT` | 查询工具最大并发数，内部会归一为 `1` |
| `ICP_PROXY_TUNNEL` | 固定代理地址，例如 `socks5://127.0.0.1:1080` |
| `ICP_PROXY_POOL_URL` | 代理池 API 地址，当前保留配置 |
| `ICP_PROXY_POOL_SIZE` | 代理池大小，当前保留配置 |
| `ICP_PROXY_POOL_IPV6` | 本地 IPv6 出口轮换开关，当前保留配置 |

默认配置见 `config.example.yml`。

## 工具列表

| 工具名称 | 说明 |
| --- | --- |
| `icp_query` | 查询 ICP 备案信息，支持 `web/app/mapp/kapp` |
| `icp_blacklist` | 查询违法违规黑名单，支持 `bweb/bapp/bmapp/bkapp` |
| `config_show` | 查看当前运行配置 |
| `check_environment` | 检查运行环境、依赖和支持类型 |

## 查询参数

### `icp_query`

| 参数 | 说明 |
| --- | --- |
| `name` | 查询关键词，支持公司名、域名、备案号、App 名等 |
| `type` | 查询类型：`web`、`app`、`mapp`、`kapp`，默认 `web` |
| `page` | 页码，默认 `1` |
| `page_size` | 每页数量，最大 `26` |
| `proxy` | 单次请求代理，优先级高于 `ICP_PROXY_TUNNEL` |

### `icp_blacklist`

| 参数 | 说明 |
| --- | --- |
| `name` | 查询关键词，支持域名、App 名等 |
| `type` | 黑名单类型：`bweb`、`bapp`、`bmapp`、`bkapp`，默认 `bweb` |
| `proxy` | 单次请求代理，优先级高于 `ICP_PROXY_TUNNEL` |

## 请求限制

项目会在 MCP 服务进程内做本地保护，避免客户端并发请求直接打到目标接口。

| 工具 | 控制方式 |
| --- | --- |
| `icp_query` | 单例队列执行，默认每分钟 `5` 次 |
| `icp_blacklist` | 单例队列执行，默认每分钟 `3` 次 |
| App/小程序/快应用详情补全 | 串行执行 |

Qoder 等 MCP 客户端可能默认并发触发 5/10 个 tool call；本项目内部会强制串行化，同一进程内前一个查询完整结束后，下一个查询才会访问目标接口。

## 项目结构

```text
src/
  icpquery_mcp/
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

## 手动验证

```bash
python -m compileall src
icpquery check-env
icpquery config-show
```

## 注意事项

**本项目仅供学习和技术研究使用，严禁用于任何商业或非法用途。**

请只在合法授权范围内使用，并自行承担接口变化、验证码策略变化、目标风控或网络环境导致的失败风险。

## 许可证

MIT License，见 `LICENSE`。
