from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
import unittest
from collections import Counter
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated
from unittest.mock import AsyncMock, patch

import httpx
from jsonschema import Draft202012Validator
from mcp import ClientSession, StdioServerParameters
from mcp.client import Client
from mcp.client._memory import InMemoryTransport
from mcp.client.stdio import stdio_client
from mcp.server import CacheHint
from mcp.server.mcpserver.exceptions import ToolError
from mcp.shared.exceptions import MCPError
from mcp.types import CallToolResult, ClientCapabilities, Implementation, InitializedNotification, InitializeRequest, InitializeRequestParams, InitializeResult

from icpquery_mcp import mcp_server
from icpquery_mcp.core.config import Config
from icpquery_mcp.core.errors import QueryError
from icpquery_mcp.models import ICPQueryResponse, ToolFailure
from icpquery_mcp.server import create_server
from icpquery_mcp.tools import local_tools


VERSIONS = ("2025-03-26", "2025-11-25", "2026-07-28")


async def negotiate(client, version):
    if version == "2026-07-28":
        return await client.discover()
    result = await client.send_request(InitializeRequest(params=InitializeRequestParams(
        protocol_version=version, capabilities=ClientCapabilities(),
        client_info=Implementation(name="icpquery-contract-tests", version="1"),
    )), InitializeResult)
    client.adopt(result)
    await client.send_notification(InitializedNotification())
    return result


@asynccontextmanager
async def connected(server, version):
    async with InMemoryTransport(server) as streams:
        async with ClientSession(*streams) as client:
            discovery = await negotiate(client, version)
            yield client, discovery


class MCPContractTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.environment = patch.dict(os.environ, {}, clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)
        config = Config()
        config.rate_limit.enabled = False
        self.config = patch("icpquery_mcp.server.load_config", return_value=config)
        self.config.start()
        self.addCleanup(self.config.stop)

    async def asyncSetUp(self):
        asyncio.get_running_loop().slow_callback_duration = 1.0

    def assert_failure(self, result, schema, error_type):
        self.assertTrue(result.is_error)
        self.assertIsNotNone(result.structured_content)
        payload = result.structured_content
        self.assertEqual(json.loads(result.content[0].text), payload)
        Draft202012Validator(schema).validate(payload)
        self.assertFalse(payload["success"])
        self.assertEqual(payload["error"]["type"], error_type)
        self.assertEqual(payload["completeness"], "unknown")
        self.assertEqual(payload["next_action"], "stop")

    async def test_error_contracts_and_schema_validity_in_each_protocol_era(self):
        for version in VERSIONS:
            with self.subTest(version=version), patch.object(httpx, "AsyncClient") as external_http:
                async with connected(create_server(), version) as (client, discovery):
                    modern = version == "2026-07-28"
                    self.assertIsNone(discovery.capabilities.logging)
                    self.assertEqual(discovery.capabilities.resources.subscribe, modern)
                    self.assertEqual(discovery.capabilities.tools.list_changed, modern)
                    if modern:
                        self.assertEqual(discovery.supported_versions, [version])
                        with self.assertRaises(MCPError) as caught:
                            await client.send_discover("2099-01-01")
                        self.assertEqual(caught.exception.code, -32022)
                    else:
                        self.assertEqual(discovery.protocol_version, version)
                    tools = {tool.name: tool for tool in (await client.list_tools()).tools}
                    for tool in tools.values():
                        Draft202012Validator.check_schema(tool.input_schema)
                        Draft202012Validator.check_schema(tool.output_schema)
                        self.assertIs(tool.input_schema["additionalProperties"], False)
                        arguments = {"bogus": "caller-secret"}
                        if tool.name.startswith("icp_"):
                            arguments["name"] = "example.test"
                        result = await client.call_tool(tool.name, arguments)
                        self.assert_failure(result, tool.output_schema, "validation_error")
                        self.assertNotIn("caller-secret", result.content[0].text)
                    for arguments in ({}, {"name": "example.test", "page_size": 99999},
                                      {"name": "   "}, {"name": "example.test", "page_size": "caller-secret"}):
                        result = await client.call_tool("icp_query", arguments)
                        self.assert_failure(result, tools["icp_query"].output_schema, "validation_error")
                        self.assertNotIn("caller-secret", result.content[0].text)
                    unknown = await client.call_tool("unknown_tool", {})
                    ToolFailure.model_validate(unknown.structured_content)
                    self.assertEqual(unknown.structured_content["error"]["type"], "tool_not_found")
                    for tool, method in (("icp_query", "async_icp_query"), ("icp_blacklist", "async_icp_blacklist")):
                        with patch.object(local_tools, method, new=AsyncMock(return_value={"success": False, "code": 403, "message": "rejected"})):
                            result = await client.call_tool(tool, {"name": "example.test"})
                        self.assert_failure(result, tools[tool].output_schema, "provider_error")
                external_http.assert_not_called()

    async def test_network_and_upstream_failures_are_typed_and_credential_safe(self):
        request = httpx.Request("POST", "https://audit:server-secret@example.test/?token=server-secret")
        errors = (
            (httpx.ReadTimeout("server-secret", request=request), "timeout"),
            (httpx.ConnectError("server-secret", request=request), "network_error"),
            (httpx.HTTPStatusError("server-secret", request=request, response=httpx.Response(503, request=request)), "http_error"),
            (QueryError("captcha_error", "Retry the captcha sequentially."), "captcha_error"),
        )
        async with connected(create_server(), "2026-07-28") as (client, _):
            schema = {tool.name: tool.output_schema for tool in (await client.list_tools()).tools}["icp_query"]
            for error, error_type in errors:
                with self.subTest(error_type=error_type), patch.object(local_tools, "async_icp_query", new=AsyncMock(side_effect=error)):
                    result = await client.call_tool("icp_query", {"name": "example.test"})
                    self.assert_failure(result, schema, error_type)
                    self.assertNotIn("server-secret", result.content[0].text)

    async def test_local_success_shapes_and_proxy_redaction_are_preserved(self):
        with patch.dict(os.environ, {"ICP_PROXY_TUNNEL": "http://audit:server-secret@127.0.0.1:9999", "ICP_PROXY_POOL_URL": "https://example.test/?token=server-secret"}):
            async with connected(create_server(), "2026-07-28") as (client, _):
                tools = {tool.name: tool for tool in (await client.list_tools()).tools}
                for name in ("config_show", "check_environment"):
                    result = await client.call_tool(name, {})
                    self.assertFalse(result.is_error)
                    self.assertEqual(json.loads(result.content[0].text), result.structured_content)
                    Draft202012Validator(tools[name].output_schema).validate(result.structured_content)
                    self.assertNotIn("server-secret", result.content[0].text)
                    config = result.structured_content.get("config", result.structured_content)
                    self.assertEqual(config["proxy"]["tunnel"], "<configured>")
                    self.assertEqual(config["proxy"]["pool"]["url"], "<configured>")
                    self.assertNotIn("result", result.structured_content)

    async def test_cache_hints_are_honored_but_dynamic_tools_are_always_called(self):
        counts = Counter()
        server = create_server()

        async def observe(context, call_next):
            counts[context.method] += 1
            return await call_next(context)

        server.middleware.append(observe)
        async with Client(server, mode="auto") as client:
            for _ in range(2):
                tools = await client.list_tools()
                self.assertEqual((tools.ttl_ms, tools.cache_scope), (300_000, "public"))
                await client.list_resources()
                await client.list_resource_templates()
                await client.list_prompts()
                reference = await client.read_resource("icpquery://config/example")
                self.assertEqual((reference.ttl_ms, reference.cache_scope), (3_600_000, "public"))
                await client.call_tool("config_show", {})
            for method in mcp_server.DEFAULT_CACHE_HINTS:
                self.assertEqual(counts[method], 1, method)
            self.assertEqual(counts["tools/call"], 2)
            await client.list_tools(cache_mode="refresh")
            self.assertEqual(counts["tools/list"], 2)
            async with client.listen(tools_list_changed=True) as subscription:
                self.assertTrue(subscription.honored.tools_list_changed)

    async def test_cache_hint_overrides_preserve_unmentioned_defaults(self):
        server = mcp_server.ICPQueryMCPServer("override", cache_hints={"tools/list": CacheHint(ttl_ms=17, scope="private")})
        async with connected(server, "2026-07-28") as (client, _):
            listing = await client.list_tools()
            self.assertEqual((listing.ttl_ms, listing.cache_scope), (17, "private"))
            self.assertEqual((await client.list_resources()).ttl_ms, 300_000)

    async def test_protocol_errors_and_cancellation_are_preserved(self):
        server = mcp_server.ICPQueryMCPServer("exceptions")

        @server.tool()
        async def protocol() -> Annotated[CallToolResult, ICPQueryResponse]:
            raise MCPError(code=-32602, message="sentinel")

        @server.tool()
        async def cancelled() -> Annotated[CallToolResult, ICPQueryResponse]:
            raise asyncio.CancelledError()

        @server.tool()
        async def deliberate() -> Annotated[CallToolResult, ICPQueryResponse]:
            raise ToolError("Correct the operation before retrying.")

        @server.tool()
        async def crashed() -> Annotated[CallToolResult, ICPQueryResponse]:
            raise RuntimeError("server-secret")

        with self.assertRaises(asyncio.CancelledError):
            await server.call_tool("cancelled", {})
        async with connected(server, "2026-07-28") as (client, _):
            schema = (await client.list_tools()).tools[0].output_schema
            with self.assertRaises(MCPError) as caught:
                await client.call_tool("protocol", {})
            self.assertEqual(caught.exception.code, -32602)
            self.assert_failure(await client.call_tool("deliberate", {}), schema, "tool_error")
            with self.assertLogs(mcp_server.logger, level="ERROR"):
                result = await client.call_tool("crashed", {})
            self.assert_failure(result, schema, "internal_error")
            self.assertNotIn("server-secret", result.content[0].text)

    async def test_stdio_launch_and_error_contract_in_three_independent_processes(self):
        project = Path(__file__).resolve().parents[1]
        environment = {key: value for key, value in os.environ.items() if key in {"PATH", "HOME", "LANG", "LC_ALL", "TMPDIR", "SYSTEMROOT"}}
        for version in VERSIONS:
            with self.subTest(version=version), tempfile.TemporaryFile(mode="w+") as stderr:
                params = StdioServerParameters(command=sys.executable, args=["-B", "-m", "icpquery_mcp.server"], cwd=str(project), env=environment)
                async with stdio_client(params, errlog=stderr) as streams:
                    async with ClientSession(*streams) as client:
                        await negotiate(client, version)
                        tools = {tool.name: tool for tool in (await client.list_tools()).tools}
                        self.assertEqual(len(tools), 4)
                        result = await client.call_tool("icp_query", {"name": "example.test", "page_size": 99999})
                        self.assert_failure(result, tools["icp_query"].output_schema, "validation_error")
                        self.assertFalse((await client.call_tool("config_show", {})).is_error)
