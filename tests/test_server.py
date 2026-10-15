from __future__ import annotations

import unittest
from unittest.mock import patch

from icpquery_mcp.core.client import _normalize_response
from icpquery_mcp.server import SINGLE_REQUEST_META, create_server


class ServerMetadataTests(unittest.IsolatedAsyncioTestCase):
    async def test_all_public_tools_have_structured_schemas_and_metadata(self) -> None:
        server = create_server()
        tools = {tool.name: tool for tool in await server.list_tools()}

        self.assertEqual(
            set(tools),
            {"check_environment", "icp_query", "icp_blacklist", "config_show"},
        )
        for tool in tools.values():
            self.assertIsNotNone(tool.output_schema)
            self.assertEqual(tool.meta, SINGLE_REQUEST_META)

        self.assertIn("server instance", SINGLE_REQUEST_META["icpquery/concurrency_reason"])
        self.assertNotIn("process-wide", SINGLE_REQUEST_META["icpquery/concurrency_reason"])
        self.assertTrue(tools["icp_query"].annotations.read_only_hint)
        self.assertTrue(tools["icp_query"].annotations.open_world_hint)
        self.assertFalse(tools["config_show"].annotations.open_world_hint)
        self.assertIn("bounded to one page", server.instructions)
        schema = tools["icp_query"].input_schema
        self.assertIn("include_details", schema["properties"])
        self.assertFalse(schema["properties"]["include_details"].get("default", True))

    async def test_configuration_resource_is_registered(self) -> None:
        resources = await create_server().list_resources()

        self.assertEqual([str(resource.uri) for resource in resources], ["icpquery://config/example"])
        self.assertEqual(resources[0].mime_type, "text/yaml")

    async def test_server_factory_declares_identity_and_install_dependencies(self) -> None:
        with patch("icpquery_mcp.server.logging.basicConfig") as basic_config:
            server = create_server()

        for call in basic_config.call_args_list:
            self.assertNotEqual(
                call.kwargs.get("format"),
                "%(asctime)s %(levelname)s %(name)s: %(message)s",
            )
        self.assertEqual(server.website_url, "https://github.com/helGayhub233/ICPQuery-MCP")
        self.assertEqual(
            server.dependencies,
            [
                "httpx[socks]>=0.27.0",
                "mcp[cli]>=2.3.0,<3",
                "pillow>=10.0.0",
                "pydantic>=2.0.0",
                "pyyaml>=6.0.0",
            ],
        )

    def test_response_contract_reports_next_page_from_total(self) -> None:
        result = _normalize_response(
            {
                "code": 200,
                "success": True,
                "params": {
                    "list": [{"dataId": "1"}, {"dataId": "2"}],
                    "pageNum": 1,
                    "pageSize": 2,
                    "total": 5,
                },
            }
        )
        self.assertEqual(result["returned_count"], 2)
        self.assertTrue(result["truncated"])
        self.assertEqual(result["completeness"], "partial")
        self.assertEqual(result["next_action"], "call_next_page")

class TransportSecurityTests(unittest.IsolatedAsyncioTestCase):
    async def test_miit_client_keeps_tls_certificate_verification_enabled(self) -> None:
        from icpquery_mcp.core.client import ICPQueryClient
        from icpquery_mcp.core.config import Config

        response = unittest.mock.Mock()
        response.raise_for_status.return_value = None
        async_client = unittest.mock.AsyncMock()
        async_client.__aenter__.return_value = async_client
        async_client.post.return_value = response
        with patch("icpquery_mcp.core.client.httpx.AsyncClient", return_value=async_client) as factory:
            await ICPQueryClient(Config())._post("https://example.test", b"{}", {}, "")

        self.assertNotEqual(factory.call_args.kwargs.get("verify"), False)

    def test_protocol_nonce_uses_secure_random_source(self) -> None:
        from icpquery_mcp.core.client import _random_hex

        with patch("icpquery_mcp.core.client.secrets.token_hex", return_value="ab" * 32) as token_hex:
            self.assertEqual(_random_hex(32), "ab" * 32)
        token_hex.assert_called_once_with(32)

    def test_protocol_md5_is_explicitly_non_security_use(self) -> None:
        import asyncio
        from icpquery_mcp.core.client import ICPQueryClient
        from icpquery_mcp.core.config import Config

        client = ICPQueryClient(Config())
        response = unittest.mock.Mock()
        response.json.return_value = {"params": {"bussiness": "token", "expire": 1000}}
        with patch.object(client, "_post", new=unittest.mock.AsyncMock(return_value=response)), patch(
            "icpquery_mcp.core.client.hashlib.md5", wraps=__import__("hashlib").md5
        ) as md5:
            asyncio.run(client._get_token(""))
        self.assertFalse(md5.call_args.kwargs.get("usedforsecurity", True))

class OutputSchemaPortabilityTests(unittest.IsolatedAsyncioTestCase):
    async def test_provider_payload_fields_declare_json_container_types(self) -> None:
        tools = {tool.name: tool for tool in await create_server().list_tools()}
        for name in ("icp_query", "icp_blacklist"):
            for field in ("data", "params"):
                field_schema = tools[name].output_schema["properties"][field]
                definition_name = field_schema["$ref"].rsplit("/", 1)[-1]
                variants = tools[name].output_schema["$defs"][definition_name]["anyOf"]
                self.assertTrue(all(bool(variant) for variant in variants), f"{name}.{field}")

if __name__ == "__main__":
    unittest.main()
