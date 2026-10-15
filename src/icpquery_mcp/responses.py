"""Provider status, pagination, and bounded MCP response construction."""

from __future__ import annotations

import copy
import json
from typing import Any

from mcp.types import CallToolResult, TextContent

from icpquery_mcp.models import ICPQueryResponse, ToolFailure

MAX_OUTPUT_BYTES = 64 * 1024
MAX_STRING_CHARS = 4096


def failure_payload(error_type: str, message: str, *, code: int | str | None = None,
                    details: dict[str, Any] | None = None) -> dict[str, Any]:
    return ToolFailure.model_validate({
        "success": False, "code": code, "message": message,
        "error": {"type": error_type, "message": message, "details": details},
    }).model_dump(mode="json", exclude_none=True)


def record_container(payload: dict[str, Any]) -> tuple[list[Any], dict[str, Any], str] | None:
    params = payload.get("params")
    if isinstance(params, dict) and isinstance(params.get("list"), list):
        return params["list"], params, "list"
    if isinstance(payload.get("data"), list):
        return payload["data"], payload, "data"
    return None


def _integer(value: Any, *, minimum: int = 0) -> bool:
    return type(value) is int and value >= minimum


def normalize_response(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        return failure_payload("invalid_response", "MIIT returned a non-object response. Check provider status before retrying.")
    code = data.get("code")
    numeric_code = int(code) if isinstance(code, str) and code.isascii() and code.isdigit() else code
    if data.get("success") is False or (type(numeric_code) is int and numeric_code != 200):
        original_error = data.get("error")
        if isinstance(original_error, dict) and isinstance(original_error.get("type"), str):
            return failure_payload(original_error["type"], str(data.get("message") or original_error.get("message") or "MIIT query failed."),
                                   code=code if type(code) in (str, int) else None, details=original_error.get("details"))
        message = str(data.get("message") or "MIIT rejected the query. Check the query and provider status before retrying.")
        if numeric_code == 500:
            # Keep the existing client code while retaining the upstream code.
            return failure_payload("provider_error", "工信部服务器异常", code=122, details={"provider_code": 500})
        return failure_payload("provider_error", message, code=code if type(code) in (str, int) else None)
    if data.get("success") is not True or (code is not None and numeric_code != 200):
        return failure_payload("invalid_response", "MIIT did not return a valid business status. Inspect provider status before retrying.")

    payload = dict(data)
    container = record_container(payload)
    returned = len(container[0]) if container else 0
    params = payload.get("params")
    sources = [payload, params] if isinstance(params, dict) else [payload]
    totals = [source[key] for source in sources for key in ("total", "totalCount", "total_count")
              if _integer(source.get(key))]
    total = max(totals) if totals else None
    page = next((value for value in (payload.get("page"), params.get("pageNum") if isinstance(params, dict) else None)
                 if _integer(value, minimum=1)), None)
    page_size = next((value for value in (payload.get("page_size"), params.get("pageSize") if isinstance(params, dict) else None)
                      if _integer(value, minimum=1)), None)
    for key, value in (("page", page), ("page_size", page_size), ("total", total)):
        if value is None:
            payload.pop(key, None)
        else:
            payload[key] = value

    signals = [source[key] for source in sources for key in ("has_next", "hasNext", "hasNextPage")
               if type(source.get(key)) is bool]
    contradictory = len(set(totals)) > 1
    if total is not None and page is not None and page_size is not None:
        end = (page - 1) * page_size + returned
        if end <= total:
            signals.append(end < total)
        else:
            contradictory = True
    elif total is not None and total == returned:
        signals.append(False)
    contradictory = contradictory or (True in signals and False in signals)
    if contradictory:
        warning = {"type": "pagination_conflict", "message": "MIIT pagination signals conflict; completeness is not guaranteed."}
        warnings = list(payload.get("warnings") or [])
        if not any(item.get("type") == warning["type"] for item in warnings):
            warnings.append(warning)
        payload["warnings"] = warnings
    has_more = True if True in signals else False if signals and not contradictory else None
    payload.update(
        returned_count=returned,
        truncated=has_more is True,
        completeness="partial" if has_more is True else "complete" if has_more is False else "unknown",
        next_action="call_next_page" if has_more is True else "stop" if has_more is False else "unknown",
    )
    return payload


def render_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)


def bounded_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Bound both UTF-8 JSON copies and retain a prefix of the current page."""
    result = copy.deepcopy(payload)
    container = record_container(result)
    received = len(container[0]) if container else 0
    truncated_fields = 0

    def clip(value: Any, key: str = "") -> Any:
        nonlocal truncated_fields
        if isinstance(value, str) and len(value) > MAX_STRING_CHARS and key not in {"dataId", "id", "mainLicence", "serviceLicence", "cursor", "next_cursor"}:
            truncated_fields += 1
            return value[:MAX_STRING_CHARS] + "…[truncated]"
        if isinstance(value, list):
            return [clip(item) for item in value]
        if isinstance(value, dict):
            return {name: clip(item, name) for name, item in value.items()}
        return value

    result = clip(result)
    container = record_container(result)
    oversized = len(render_json(result).encode("utf-8")) > MAX_OUTPUT_BYTES
    if not oversized and not truncated_fields:
        return result
    if result.get("success") is not True:
        if oversized:
            return failure_payload("output_too_large", "Error diagnostics exceeded the output budget. Narrow the request before retrying.")
        return result

    output = {"max_bytes": MAX_OUTPUT_BYTES, "max_string_chars": MAX_STRING_CHARS,
              "received_count": received, "omitted_records": 0, "truncated_fields": truncated_fields}
    result["output"] = output
    result.setdefault("warnings", []).append({
        "type": "output_truncated",
        "message": "Local output was clipped. Narrow the query, disable details, or reduce page_size before advancing pages.",
    })
    result.update(truncated=True, completeness="partial", next_action="refine_query")
    if container:
        records, parent, key = container
        low, high = 0, len(records)
        while low < high:
            middle = (low + high + 1) // 2
            parent[key] = records[:middle]
            output["omitted_records"] = received - middle
            result["returned_count"] = middle
            if len(render_json(result).encode("utf-8")) <= MAX_OUTPUT_BYTES:
                low = middle
            else:
                high = middle - 1
        parent[key] = records[:low]
        output["omitted_records"] = received - low
        result["returned_count"] = low
    if len(render_json(result).encode("utf-8")) > MAX_OUTPUT_BYTES:
        return failure_payload("output_too_large", "Response metadata exceeded the output budget. Narrow the query or disable details before retrying.")
    return result


def tool_result(payload: dict[str, Any], *, query: bool = False) -> CallToolResult:
    if query:
        payload = ICPQueryResponse.model_validate(normalize_response(payload)).model_dump(mode="json", exclude_none=True)
    payload = bounded_payload(payload)
    return CallToolResult(
        content=[TextContent(type="text", text=render_json(payload))],
        structured_content=payload,
        is_error=payload.get("success") is False,
    )
