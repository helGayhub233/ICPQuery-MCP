from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class RateLimitConfig(BaseModel):
    enabled: bool = True
    query_per_min: int = 5
    blacklist_per_min: int = 3
    max_concurrent: int = 1


class ProxyPoolConfig(BaseModel):
    url: str = ""
    size: int = 100
    ipv6: bool = False


class ProxyConfig(BaseModel):
    tunnel: str = ""
    pool: ProxyPoolConfig = Field(default_factory=ProxyPoolConfig)


class Config(BaseModel):
    timeout: int = 30
    concurrency: int = 5
    rate_limit: RateLimitConfig = Field(default_factory=RateLimitConfig)
    proxy: ProxyConfig = Field(default_factory=ProxyConfig)

    def normalized(self) -> "Config":
        data = self.model_dump()
        data["timeout"] = max(int(data.get("timeout") or 30), 1)
        data["concurrency"] = 1
        rl = data["rate_limit"]
        rl["query_per_min"] = max(int(rl.get("query_per_min") or 5), 1)
        rl["blacklist_per_min"] = max(int(rl.get("blacklist_per_min") or 3), 1)
        rl["max_concurrent"] = 1
        pool = data["proxy"]["pool"]
        pool["size"] = max(int(pool.get("size") or 100), 1)
        return Config(**data)


ENV_KEYS = {
    "ICP_TIMEOUT": ("timeout",),
    "ICP_CONCURRENCY": ("concurrency",),
    "ICP_RATE_LIMIT_ENABLED": ("rate_limit", "enabled"),
    "ICP_RATE_LIMIT_QUERY_PER_MIN": ("rate_limit", "query_per_min"),
    "ICP_RATE_LIMIT_BLACKLIST_PER_MIN": ("rate_limit", "blacklist_per_min"),
    "ICP_RATE_LIMIT_MAX_CONCURRENT": ("rate_limit", "max_concurrent"),
    "ICP_PROXY_TUNNEL": ("proxy", "tunnel"),
    "ICP_PROXY_POOL_URL": ("proxy", "pool", "url"),
    "ICP_PROXY_POOL_SIZE": ("proxy", "pool", "size"),
    "ICP_PROXY_POOL_IPV6": ("proxy", "pool", "ipv6"),
}


def load_config(path: str | None = None) -> Config:
    data: dict[str, Any] = {}
    if path:
        config_path = Path(path).expanduser()
        if config_path.exists():
            loaded = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
            if isinstance(loaded, dict):
                data = loaded

    data = _deep_merge(data, _env_overrides())
    return Config(**data).normalized()


def _env_overrides() -> dict[str, Any]:
    data: dict[str, Any] = {}
    for env_key, path in ENV_KEYS.items():
        raw = os.getenv(env_key)
        if raw is None:
            continue
        value = _coerce_env(raw)
        cursor = data
        for part in path[:-1]:
            cursor = cursor.setdefault(part, {})
        cursor[path[-1]] = value
    return data


def _coerce_env(value: str) -> str | int | bool:
    lower = value.lower()
    if lower in {"true", "yes", "1", "on"}:
        return True
    if lower in {"false", "no", "0", "off"}:
        return False
    try:
        return int(value)
    except ValueError:
        return value


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result
