"""Structured output models exposed by ICPQuery MCP tools."""

from __future__ import annotations

from typing import Literal, Union

from pydantic import BaseModel, ConfigDict, Field
from typing_extensions import TypeAliasType

from icpquery_mcp.core.config import Config


JSONValue = TypeAliasType(
    "JSONValue",
    Union[dict[str, "JSONValue"], list["JSONValue"], str, int, float, bool, None],
)


class ErrorDetail(BaseModel):
    type: str = Field(description="Stable machine-readable error category.")
    message: str = Field(description="Failure and recovery guidance.")
    details: dict[str, JSONValue] | None = None


class WarningDetail(BaseModel):
    type: str
    message: str
    details: dict[str, JSONValue] | None = None


class OutputClipping(BaseModel):
    max_bytes: int = Field(ge=2048)
    max_string_chars: int = Field(ge=1)
    received_count: int = Field(ge=0)
    omitted_records: int = Field(ge=0)
    truncated_fields: int = Field(ge=0)


class ToolFailure(BaseModel):
    """Shared failure branch for query, environment, and config tools."""

    model_config = ConfigDict(extra="forbid")

    success: Literal[False] = False
    code: int | str | None = None
    message: str
    error: ErrorDetail
    returned_count: Literal[0] = 0
    truncated: Literal[False] = False
    completeness: Literal["unknown"] = "unknown"
    next_action: Literal["stop"] = "stop"


class ICPQueryResponse(BaseModel):
    """MIIT query response with stable status fields and extensible provider data."""

    model_config = ConfigDict(extra="allow")

    code: int | str | None = Field(default=None, description="MIIT or client response code.")
    success: bool = Field(description="Whether the query completed successfully.")
    message: str | None = Field(default=None, description="Human-readable status or error message.")
    error: ErrorDetail | None = None
    warnings: list[WarningDetail] | None = None
    output: OutputClipping | None = Field(default=None, description="Local output clipping, separate from upstream pagination.")
    data: JSONValue = Field(default=None, description="Registration or blacklist records returned by MIIT.")
    params: JSONValue = Field(default=None, description="Query parameters echoed by the upstream service.")
    total: int | None = Field(default=None, ge=0, description="Total matching records, when reported.")
    page: int | None = Field(default=None, ge=1, description="Current one-based result page, when reported.")
    page_size: int | None = Field(default=None, ge=1, description="Requested or returned page size, when reported.")
    detail_requests: int = Field(default=0, ge=0, description="Number of per-record detail requests made by the server.")
    details_truncated: bool = Field(default=False, description="Whether detail enrichment was capped for this response.")
    returned_count: int = Field(default=0, ge=0, description="Number of records returned in this bounded response page.")
    truncated: bool = Field(default=False, description="Whether another page is known to exist.")
    completeness: Literal["complete", "partial", "unknown"] = Field(default="unknown", description="Whether the current page completes the result set.")
    next_action: Literal["stop", "call_next_page", "refine_query", "unknown"] = Field(default="unknown", description="Continuation guidance. refine_query means local clipping: narrow the query or page size before advancing pages.")


class EnvironmentReport(BaseModel):
    """Local runtime capabilities and redacted effective configuration."""

    ok: Literal[True] = Field(description="Whether the local environment inspection completed.")
    python: str = Field(description="Supported Python version requirement.")
    dependencies: list[str] = Field(description="Required runtime dependency names.")
    supported_query_types: list[str] = Field(description="Supported normal registration query categories.")
    supported_blacklist_types: list[str] = Field(description="Supported illegal-entity blacklist categories.")
    config: Config = Field(description="Effective configuration with proxy secrets redacted.")
