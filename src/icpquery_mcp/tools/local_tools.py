from __future__ import annotations

import asyncio
from typing import Any

from icpquery_mcp.core.client import BLACKLIST_TYPES, SERVICE_TYPES, ICPQueryClient
from icpquery_mcp.core.config import Config, load_config


def show_config(config_path: str | None = None) -> dict[str, Any]:
    return load_config(config_path).model_dump()


async def async_icp_query(
    name: str,
    type: str = "web",
    page: int = 1,
    page_size: int = 26,
    proxy: str = "",
    config_path: str | None = None,
) -> dict[str, Any]:
    if not name.strip():
        raise ValueError("name 不能为空")
    cfg = load_config(config_path)
    client = ICPQueryClient(cfg)
    return await client.query(name.strip(), type, page or 1, page_size or 26, proxy)


async def async_icp_blacklist(
    name: str,
    type: str = "bweb",
    proxy: str = "",
    config_path: str | None = None,
) -> dict[str, Any]:
    if not name.strip():
        raise ValueError("name 不能为空")
    cfg = load_config(config_path)
    client = ICPQueryClient(cfg)
    return await client.blacklist(name.strip(), type, proxy)


def icp_query(
    name: str,
    type: str = "web",
    page: int = 1,
    page_size: int = 26,
    proxy: str = "",
    config_path: str | None = None,
) -> dict[str, Any]:
    return asyncio.run(async_icp_query(name, type, page, page_size, proxy, config_path))


def icp_blacklist(name: str, type: str = "bweb", proxy: str = "", config_path: str | None = None) -> dict[str, Any]:
    return asyncio.run(async_icp_blacklist(name, type, proxy, config_path))


def check_environment(config_path: str | None = None) -> dict[str, Any]:
    cfg = load_config(config_path)
    return {
        "ok": True,
        "python": ">=3.10",
        "dependencies": ["mcp", "httpx", "pydantic", "pillow", "pyyaml"],
        "supported_query_types": sorted(SERVICE_TYPES),
        "supported_blacklist_types": sorted(BLACKLIST_TYPES),
        "config": cfg.model_dump(),
    }


def create_client(config: Config | None = None) -> ICPQueryClient:
    return ICPQueryClient(config or load_config(None))
