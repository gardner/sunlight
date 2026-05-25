from __future__ import annotations

import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class RateLimitSnapshot:
    started_at: float
    starts_last_60s: int
    rpm_limit: int


class RequestRateLimiter:
    def __init__(
        self,
        rpm: int,
        *,
        clock: Callable[[], float] = time.time,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.rpm = max(rpm, 1)
        self.min_interval = 60 / self.rpm
        self.last_call_at = 0.0
        self.lock = threading.Lock()
        self.clock = clock
        self.sleep = sleep
        self.request_starts: deque[float] = deque()

    def wait(self) -> RateLimitSnapshot:
        with self.lock:
            now = self.clock()
            elapsed = now - self.last_call_at
            if self.last_call_at and elapsed < self.min_interval:
                self.sleep(self.min_interval - elapsed)
                now = self.clock()
            self.last_call_at = now
            cutoff = now - 60
            while self.request_starts and self.request_starts[0] <= cutoff:
                self.request_starts.popleft()
            self.request_starts.append(now)
            return RateLimitSnapshot(
                started_at=now,
                starts_last_60s=len(self.request_starts),
                rpm_limit=self.rpm,
            )
