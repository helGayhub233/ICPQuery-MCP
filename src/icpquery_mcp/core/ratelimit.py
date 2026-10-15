from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Literal, TypeVar

logger = logging.getLogger("icpquery_mcp.ratelimit")
LimiterKind = Literal["query", "blacklist"]
ResultT = TypeVar("ResultT")


@dataclass
class SlidingWindowLimiter:
    per_minute: int
    calls: deque[float] = field(default_factory=deque)

    async def acquire(self) -> None:
        """Wait until the sliding window has capacity, then record this call."""
        now = time.monotonic()
        while self.calls and now - self.calls[0] >= 60:
            self.calls.popleft()
        waited = 0.0
        if len(self.calls) >= self.per_minute:
            delay = 60 - (now - self.calls[0])
            waited = max(delay, 0)
            if waited:
                logger.info(
                    "rate_limit.wait kind_window=%s per_minute=%d sleep=%.2fs",
                    "query_or_blacklist",
                    self.per_minute,
                    waited,
                )
            await asyncio.sleep(waited)
        self.calls.append(time.monotonic())


class ToolLimiter:
    """Server-side serialization guard for the MCP tool surface.

    All remote calls made through one server instance share a lock that remains
    held until the upstream operation completes. Multi-worker HTTP deployments
    need an external coordination mechanism to provide the same guarantee.
    """

    def __init__(self, query_per_min: int, blacklist_per_min: int, max_concurrent: int, enabled: bool = True) -> None:
        self.enabled = enabled
        self.query = SlidingWindowLimiter(query_per_min)
        self.blacklist = SlidingWindowLimiter(blacklist_per_min)
        self.configured_max_concurrent = max_concurrent
        # Serialize all upstream tools regardless of MCP client concurrency.
        # This lock covers every remote tool owned by this limiter instance.
        self._remote_call_lock = asyncio.Lock()

    async def run(self, kind: LimiterKind, func: Callable[[], Awaitable[ResultT]]) -> ResultT:
        """Run one remote operation under the shared serialization lock."""
        acquired_at = time.monotonic()
        async with self._remote_call_lock:
            queue_wait = time.monotonic() - acquired_at
            if queue_wait > 0.05:
                logger.warning(
                    "queue.wait kind=%s queue_wait_ms=%d "
                    "mode=single_request_complete",
                    kind,
                    int(queue_wait * 1000),
                )
            if self.enabled:
                limiter = self.query if kind == "query" else self.blacklist
                await limiter.acquire()
            started_at = time.monotonic()
            try:
                return await func()
            finally:
                duration = time.monotonic() - started_at
                logger.info(
                    "tool.complete kind=%s exec_ms=%d queue_ms=%d "
                    "mode=single_request_complete",
                    kind,
                    int(duration * 1000),
                    int(queue_wait * 1000),
                )
