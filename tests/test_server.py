from __future__ import annotations

import unittest
from unittest.mock import patch

from icpquery_mcp.server import SINGLE_REQUEST_META, create_server


class ServerMetadataTests(unittest.IsolatedAsyncioTestCase):
    async def test_all_public_tools_have_structured_schemas_and_metadata(self) -> None:
        tools = {tool.name: tool for tool in await create_server().list_tools()}

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
                "mcp>=2.2.0,<3",
                "pillow>=10.0.0",
                "pydantic>=2.0.0",
                "pyyaml>=6.0.0",
            ],
        )


if __name__ == "__main__":
    unittest.main()
