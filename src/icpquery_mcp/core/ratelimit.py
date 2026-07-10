from __future__ import annotations

import asyncio
import time
from collections import deque
from dataclasses import dataclass, field


@dataclass
class SlidingWindowLimiter:
    per_minute: int
    calls: deque[float] = field(default_factory=deque)

    async def acquire(self) -> None:
        now = time.monotonic()
        while self.calls and now - self.calls[0] >= 60:
            self.calls.popleft()
        if len(self.calls) >= self.per_minute:
            delay = 60 - (now - self.calls[0])
            await asyncio.sleep(max(delay, 0))
        self.calls.append(time.monotonic())


class ToolLimiter:
    def __init__(self, query_per_min: int, blacklist_per_min: int, max_concurrent: int, enabled: bool = True) -> None:
        self.enabled = enabled
        self.query = SlidingWindowLimiter(query_per_min)
        self.blacklist = SlidingWindowLimiter(blacklist_per_min)
        self.configured_max_concurrent = max_concurrent
        # 内部保险丝：无论 MCP 客户端并发多少 tool call，真实查询只串行执行。
        self.singleton_lock = asyncio.Lock()

    async def run(self, kind: str, func):
        async with self.singleton_lock:
            if self.enabled:
                limiter = self.query if kind == "query" else self.blacklist
                await limiter.acquire()
            return await func()
