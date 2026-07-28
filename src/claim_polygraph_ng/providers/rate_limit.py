"""Small process-local async request-start gate for specialist APIs."""

import asyncio
import time


class AsyncRequestRateGate:
    """Serialize request starts to a declared requests-per-second ceiling."""

    def __init__(self, requests_per_second: float) -> None:
        self._minimum_interval = 1 / requests_per_second
        self._lock = asyncio.Lock()
        self._last_started: float | None = None

    async def wait(self) -> None:
        async with self._lock:
            now = time.monotonic()
            if self._last_started is not None:
                remaining = self._minimum_interval - (now - self._last_started)
                if remaining > 0:
                    await asyncio.sleep(remaining)
            self._last_started = time.monotonic()
