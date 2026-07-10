from __future__ import annotations

from typing import Any

from icpquery_mcp.core.config import load_config
from icpquery_mcp.core.ratelimit import ToolLimiter
from icpquery_mcp.tools import local_tools


try:
    from mcp.server.fastmcp import FastMCP
except ImportError:  # pragma: no cover - depends on installed mcp sdk version
    FastMCP = None  # type: ignore[assignment]


def create_server(config_path: str | None = None) -> Any:
    if FastMCP is None:
        raise RuntimeError("缺少 MCP Python SDK，请在 venv 中执行：python -m pip install -e .")

    cfg = load_config(config_path)
    limiter = ToolLimiter(
        query_per_min=cfg.rate_limit.query_per_min,
        blacklist_per_min=cfg.rate_limit.blacklist_per_min,
        max_concurrent=cfg.rate_limit.max_concurrent,
        enabled=cfg.rate_limit.enabled,
    )
    mcp = FastMCP("ICPQuery MCP")

    @mcp.tool()
    def check_environment() -> dict[str, Any]:
        """检查 ICPQuery-MCP 的 Python 运行环境、依赖和支持的查询类型。"""
        return local_tools.check_environment(config_path)

    @mcp.tool()
    async def icp_query(name: str, type: str = "web", page: int = 1, page_size: int = 26, proxy: str = "") -> dict[str, Any]:
        """查询工信部 ICP 备案信息，支持 web/app/mapp/kapp。"""
        return await limiter.run(
            "query",
            lambda: local_tools.async_icp_query(name, type, page, page_size, proxy, config_path),
        )

    @mcp.tool()
    async def icp_blacklist(name: str, type: str = "bweb", proxy: str = "") -> dict[str, Any]:
        """查询工信部违法违规黑名单，支持 bweb/bapp/bmapp/bkapp。"""
        return await limiter.run(
            "blacklist",
            lambda: local_tools.async_icp_blacklist(name, type, proxy, config_path),
        )

    @mcp.tool()
    def config_show() -> dict[str, Any]:
        """查看当前 ICP 查询服务配置。"""
        return local_tools.show_config(config_path)

    @mcp.resource("config://example")
    def config_example() -> str:
        """ICPQuery-MCP 示例配置。"""
        return """timeout: 30
concurrency: 1

rate_limit:
  enabled: true
  query_per_min: 5
  blacklist_per_min: 3
  max_concurrent: 1

proxy:
  tunnel: ""
  pool:
    url: ""
    size: 100
    ipv6: false
"""

    return mcp


def main() -> None:
    create_server().run()


if __name__ == "__main__":
    main()
