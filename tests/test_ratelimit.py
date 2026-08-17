from __future__ import annotations

import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from icpquery_mcp.core.ratelimit import ToolLimiter


class ToolLimiterTests(unittest.IsolatedAsyncioTestCase):
    async def test_serializes_query_and_blacklist_calls_through_one_lock(self) -> None:
        limiter = ToolLimiter(5, 3, max_concurrent=99, enabled=False)
        active = 0
        maximum_active = 0

        async def operation(value: str) -> str:
            nonlocal active, maximum_active
            active += 1
            maximum_active = max(maximum_active, active)
            await asyncio.sleep(0.01)
            active -= 1
            return value

        results = await asyncio.gather(
            limiter.run("query", lambda: operation("query")),
            limiter.run("blacklist", lambda: operation("blacklist")),
            limiter.run("query", lambda: operation("query-2")),
        )

        self.assertEqual(results, ["query", "blacklist", "query-2"])
        self.assertEqual(maximum_active, 1)

    async def test_releases_lock_after_operation_failure(self) -> None:
        limiter = ToolLimiter(5, 3, max_concurrent=1, enabled=False)

        async def fail() -> None:
            raise RuntimeError("upstream failed")

        with self.assertRaisesRegex(RuntimeError, "upstream failed"):
            await limiter.run("query", fail)

        self.assertEqual(await limiter.run("query", lambda: asyncio.sleep(0, result="ok")), "ok")

    async def test_emits_structured_queue_and_completion_logs(self) -> None:
        limiter = ToolLimiter(5, 3, max_concurrent=1, enabled=False)
        first_started = asyncio.Event()
        release_first = asyncio.Event()
        clock = 0.0

        async def first_operation() -> str:
            first_started.set()
            await release_first.wait()
            return "query"

        async def second_operation() -> str:
            return "blacklist"

        with (
            patch(
                "icpquery_mcp.core.ratelimit.time",
                SimpleNamespace(monotonic=lambda: clock),
            ),
            self.assertLogs("icpquery_mcp.ratelimit", level="INFO") as logs,
        ):
            first = asyncio.create_task(limiter.run("query", first_operation))
            await first_started.wait()
            second = asyncio.create_task(limiter.run("blacklist", second_operation))
            await asyncio.sleep(0)
            clock = 1.0
            release_first.set()
            self.assertEqual(await asyncio.gather(first, second), ["query", "blacklist"])

        output = "\n".join(logs.output)
        self.assertRegex(
            output,
            r"queue\.wait kind=blacklist queue_wait_ms=\d+ mode=single_request_complete",
        )
        self.assertRegex(
            output,
            r"tool\.complete kind=query exec_ms=\d+ queue_ms=\d+ mode=single_request_complete",
        )
        self.assertRegex(
            output,
            r"tool\.complete kind=blacklist exec_ms=\d+ queue_ms=\d+ mode=single_request_complete",
        )


if __name__ == "__main__":
    unittest.main()
