"""Structured output models exposed by ICPQuery MCP tools."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from icpquery_mcp.core.config import Config


class ICPQueryResponse(BaseModel):
    """MIIT query response with stable status fields and extensible provider data."""

    model_config = ConfigDict(extra="allow")

    code: int | str | None = Field(default=None, description="MIIT or client response code.")
    success: bool | None = Field(default=None, description="Whether the query completed successfully.")
    message: str | None = Field(default=None, description="Human-readable status or error message.")
    data: Any | None = Field(default=None, description="Registration or blacklist records returned by MIIT.")
    params: Any | None = Field(default=None, description="Query parameters echoed by the upstream service.")
    total: int | None = Field(default=None, ge=0, description="Total matching records, when reported.")
    page: int | None = Field(default=None, ge=1, description="Current one-based result page, when reported.")
    page_size: int | None = Field(default=None, ge=1, description="Requested or returned page size, when reported.")


class EnvironmentReport(BaseModel):
    """Local runtime capabilities and redacted effective configuration."""

    ok: Literal[True] = Field(description="Whether the local environment inspection completed.")
    python: str = Field(description="Supported Python version requirement.")
    dependencies: list[str] = Field(description="Required runtime dependency names.")
    supported_query_types: list[str] = Field(description="Supported normal registration query categories.")
    supported_blacklist_types: list[str] = Field(description="Supported illegal-entity blacklist categories.")
    config: Config = Field(description="Effective configuration with proxy secrets redacted.")
