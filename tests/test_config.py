from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from icpquery_mcp.core.config import Config, load_config
from icpquery_mcp.tools.local_tools import show_config


class ConfigTests(unittest.TestCase):
    def test_model_default_concurrency_is_one(self) -> None:
        self.assertEqual(Config().concurrency, 1)

    def test_normalizes_concurrency_and_positive_limits(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "config.yml"
            config_path.write_text(
                """timeout: 0
concurrency: 20
rate_limit:
  query_per_min: 0
  blacklist_per_min: -1
  max_concurrent: 10
proxy:
  pool:
    size: 0
""",
                encoding="utf-8",
            )

            with patch.dict(os.environ, {}, clear=True):
                config = load_config(str(config_path))

        self.assertEqual(config.timeout, 30)
        self.assertEqual(config.concurrency, 1)
        self.assertEqual(config.rate_limit.query_per_min, 5)
        self.assertEqual(config.rate_limit.blacklist_per_min, 1)
        self.assertEqual(config.rate_limit.max_concurrent, 1)
        self.assertEqual(config.proxy.pool.size, 100)

    def test_environment_overrides_are_coerced_and_secrets_are_redacted(self) -> None:
        environment = {
            "ICP_TIMEOUT": "45",
            "ICP_RATE_LIMIT_ENABLED": "false",
            "ICP_PROXY_TUNNEL": "socks5://user:password@127.0.0.1:1080",
            "ICP_PROXY_POOL_URL": "https://token@example.test/pool",
        }

        with patch.dict(os.environ, environment, clear=True):
            config = load_config()
            public = show_config()

        self.assertEqual(config.timeout, 45)
        self.assertFalse(config.rate_limit.enabled)
        self.assertEqual(public["proxy"]["tunnel"], "<configured>")
        self.assertEqual(public["proxy"]["pool"]["url"], "<configured>")
        self.assertNotIn("password", repr(public))
        self.assertNotIn("token", repr(public))


if __name__ == "__main__":
    unittest.main()
