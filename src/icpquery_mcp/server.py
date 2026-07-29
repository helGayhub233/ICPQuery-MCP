from __future__ import annotations

from typing import Annotated, Any, Literal

from icpquery_mcp.core.config import Config, load_config
from icpquery_mcp.core.ratelimit import ToolLimiter
from icpquery_mcp.models import EnvironmentReport, ICPQueryResponse
from icpquery_mcp.tools import local_tools
from mcp.server import MCPServer
from mcp.types import ToolAnnotations
from pydantic import Field

LOCAL_READ_TOOL = ToolAnnotations(
    read_only_hint=True,
    destructive_hint=False,
    idempotent_hint=True,
    open_world_hint=False,
)
REMOTE_READ_TOOL = ToolAnnotations(
    read_only_hint=True,
    destructive_hint=False,
    idempotent_hint=True,
    open_world_hint=True,
)

SERVER_INSTRUCTIONS = (
    "Use icp_query for normal MIIT website, app, mini-program, and quick-app "
    "registration records; use icp_blacklist only for illegal-entity records. "
    "Queries are serialized and rate-limited to reduce target-service throttling. "
    "Use check_environment for diagnostics and config_show for redacted effective settings."
)

TargetName = Annotated[
    str,
    Field(
        min_length=1,
        description=(
            "Organization, domain, application, mini-program, or quick-app name "
            "to search, as selected by type."
        ),
    ),
]
RegistrationType = Annotated[
    Literal["web", "app", "mapp", "kapp"],
    Field(
        description=(
            "Registration category: web for websites, app for mobile apps, "
            "mapp for mini-programs, or kapp for quick apps."
        )
    ),
]
BlacklistType = Annotated[
    Literal["bweb", "bapp", "bmapp", "bkapp"],
    Field(
        description=(
            "Blacklist category: bweb for websites, bapp for mobile apps, "
            "bmapp for mini-programs, or bkapp for quick apps."
        )
    ),
]
Page = Annotated[int, Field(ge=1, description="One-based results page.")]
PageSize = Annotated[
    int,
    Field(ge=1, le=26, description="Number of records requested per page, from 1 through 26."),
]
Proxy = Annotated[
    str,
    Field(
        description=(
            "Optional HTTP, HTTPS, or SOCKS proxy URL. Leave empty to use the "
            "server's configured proxy."
        )
    ),
]


def create_server(config_path: str | None = None) -> Any:
    cfg = load_config(config_path)
    limiter = ToolLimiter(
        query_per_min=cfg.rate_limit.query_per_min,
        blacklist_per_min=cfg.rate_limit.blacklist_per_min,
        max_concurrent=cfg.rate_limit.max_concurrent,
        enabled=cfg.rate_limit.enabled,
    )
    from icpquery_mcp import __version__

    mcp = MCPServer(
        "icpquery-mcp",
        title="ICPQuery MCP",
        description="MIIT ICP registration and illegal-entity blacklist queries.",
        instructions=SERVER_INSTRUCTIONS,
        version=__version__,
    )

    @mcp.tool(
        title="Check ICPQuery Environment",
        description=(
            "Inspect the local ICPQuery-MCP Python environment, dependencies, and "
            "supported registration and blacklist categories. Use this only for "
            "diagnostics; it does not query MIIT or modify local configuration."
        ),
        annotations=LOCAL_READ_TOOL,
    )
    def check_environment() -> EnvironmentReport:
        return EnvironmentReport.model_validate(local_tools.check_environment(config_path))

    @mcp.tool(
        title="Query MIIT ICP Registrations",
        description=(
            "Search MIIT ICP registration records for a website, app, mini-program, "
            "or quick app. Use icp_blacklist instead for illegal or non-compliant "
            "entity records. This read-only remote request is limited to 5 calls per "
            "minute by default and may use the configured proxy."
        ),
        annotations=REMOTE_READ_TOOL,
    )
    async def icp_query(
        name: TargetName,
        type: RegistrationType = "web",
        page: Page = 1,
        page_size: PageSize = 26,
        proxy: Proxy = "",
    ) -> ICPQueryResponse:
        result = await limiter.run(
            "query",
            lambda: local_tools.async_icp_query(name, type, page, page_size, proxy, config_path),
        )
        return ICPQueryResponse.model_validate(result)

    @mcp.tool(
        title="Query MIIT Illegal-Entity Blacklist",
        description=(
            "Search the MIIT illegal-entity blacklist for websites, apps, "
            "mini-programs, or quick apps. Use icp_query for normal registration and "
            "ownership records. This read-only remote request is limited to 3 calls "
            "per minute by default and may use the configured proxy."
        ),
        annotations=REMOTE_READ_TOOL,
    )
    async def icp_blacklist(
        name: TargetName,
        type: BlacklistType = "bweb",
        proxy: Proxy = "",
    ) -> ICPQueryResponse:
        result = await limiter.run(
            "blacklist",
            lambda: local_tools.async_icp_blacklist(name, type, proxy, config_path),
        )
        return ICPQueryResponse.model_validate(result)

    @mcp.tool(
        title="Show ICPQuery Configuration",
        description=(
            "Return the effective local ICPQuery-MCP timeout, proxy, concurrency, and "
            "rate-limit settings. Use check_environment for dependency diagnostics. "
            "This read-only operation does not reveal credentials or modify configuration."
        ),
        annotations=LOCAL_READ_TOOL,
    )
    def config_show() -> Config:
        return Config.model_validate(local_tools.show_config(config_path))

    @mcp.resource(
        "icpquery://config/example",
        name="config-example",
        title="ICPQuery Configuration Example",
        description="Example YAML configuration for ICPQuery-MCP rate limits and proxy settings.",
        mime_type="text/yaml",
    )
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
    create_server().run(transport="stdio")


if __name__ == "__main__":
    main()
