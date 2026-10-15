"""MCP contract handling shared by all public tools."""

from __future__ import annotations

import logging
from typing import Any

import httpx
from mcp.server import CacheHint, MCPServer
from mcp.server.mcpserver.exceptions import ToolError, UnexpectedToolError
from mcp.shared.exceptions import MCPError
from mcp.types import CallToolResult, InputRequiredResult, Tool
from pydantic import ValidationError

from icpquery_mcp.core.errors import QueryError
from icpquery_mcp.models import ToolFailure
from icpquery_mcp.responses import failure_payload, tool_result

logger = logging.getLogger(__name__)
DEFAULT_CACHE_HINTS = {
    method: CacheHint(ttl_ms=3_600_000 if method == "resources/read" else 300_000, scope="public")
    for method in ("tools/list", "resources/list", "resources/templates/list", "prompts/list", "server/discover", "resources/read")
}


class ICPQueryMCPServer(MCPServer):
    """Advertise and enforce structured success and failure contracts."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        # The catalog, discovery instructions, and example resource are static.
        # Dynamic config and MIIT results are tools/call and receive no TTL.
        kwargs["cache_hints"] = {**DEFAULT_CACHE_HINTS, **(kwargs.get("cache_hints") or {})}
        super().__init__(*args, **kwargs)

    async def list_tools(self) -> list[Tool]:
        tools = await super().list_tools()
        result = []
        for tool in tools:
            output_schema = dict(tool.output_schema or {})
            if tool.name in {"check_environment", "config_show"}:
                # Preserve existing success shapes while declaring a common
                # failure branch. SDK 2.3 wraps annotated Union outputs in a
                # 'result' field, so compose the wire schema explicitly.
                failure = ToolFailure.model_json_schema(mode="serialization")
                definitions = {**output_schema.pop("$defs", {}), **failure.pop("$defs", {}), "ToolFailure": failure}
                output_schema = {"type": "object", "anyOf": [output_schema, {"$ref": "#/$defs/ToolFailure"}], "$defs": definitions}
            result.append(tool.model_copy(update={
                "input_schema": {**tool.input_schema, "additionalProperties": False},
                "output_schema": output_schema,
            }))
        return result

    async def call_tool(
        self, name: str, arguments: dict[str, Any], context: Any = None
    ) -> CallToolResult | InputRequiredResult:
        registered = next((tool for tool in await super().list_tools() if tool.name == name), None)
        if registered is None:
            return tool_result(failure_payload("tool_not_found", "Unknown tool. Select an available name from tools/list."))
        extra = sorted(arguments.keys() - registered.input_schema.get("properties", {}).keys())
        if extra:
            return self._validation_result([
                {"loc": [field], "type": "extra_forbidden", "message": "Extra inputs are not permitted"}
                for field in extra
            ])
        try:
            return await super().call_tool(name, arguments, context)
        except MCPError:
            raise
        except ToolError as error:
            cause = error.__cause__
            if isinstance(cause, ValidationError) and not isinstance(error, UnexpectedToolError):
                errors = cause.errors(include_input=False, include_context=False, include_url=False)
                return self._validation_result([
                    {"loc": list(item["loc"]), "type": item["type"], "message": item["msg"]}
                    for item in errors
                ])
            if isinstance(cause, QueryError):
                return tool_result(failure_payload(cause.error_type, str(cause)))
            if isinstance(cause, httpx.TimeoutException):
                return tool_result(failure_payload("timeout", "MIIT request timed out. Check provider and proxy status before retrying."))
            if isinstance(cause, httpx.HTTPStatusError):
                return tool_result(failure_payload("http_error", "MIIT returned an HTTP error. Check provider and proxy status before retrying.", code=cause.response.status_code))
            if isinstance(cause, httpx.RequestError):
                return tool_result(failure_payload("network_error", "Unable to contact MIIT. Check network and proxy configuration before retrying."))
            if isinstance(error, UnexpectedToolError):
                logger.exception("Tool %r raised an unexpected exception", name)
                return tool_result(failure_payload("internal_error", "Tool execution failed unexpectedly. Inspect server logs before retrying."))
            return tool_result(failure_payload("tool_error", str(error)))

    @staticmethod
    def _validation_result(errors: list[dict[str, Any]]) -> CallToolResult:
        return tool_result(failure_payload(
            "validation_error", "Invalid tool arguments. Correct the listed fields using tools/list before retrying.",
            details={"validation_errors": errors},
        ))
