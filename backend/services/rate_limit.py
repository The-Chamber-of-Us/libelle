"""Lightweight in-memory rate limiting for public intake."""
from __future__ import annotations

import math
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Callable, Deque, Dict, Iterable, Optional, Tuple


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    scope: str = ""
    retry_after_seconds: int = 0


class InMemoryIntakeRateLimiter:
    """
    Sliding-window in-memory limiter.

    This is intentionally lightweight for v0.3. Counters reset on process
    restart and are not shared across multiple backend instances.
    """

    def __init__(
        self,
        *,
        enabled: bool,
        per_ip_limit: int,
        per_email_limit: int,
        global_limit: int,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.enabled = enabled
        self.per_ip_limit = per_ip_limit
        self.per_email_limit = per_email_limit
        self.global_limit = global_limit
        self._clock = clock
        self._events: Dict[str, Deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, *, ip_address: str, email: Optional[str]) -> RateLimitDecision:
        if not self.enabled:
            return RateLimitDecision(allowed=True)

        now = self._clock()
        rules = list(self._rules(ip_address=ip_address, email=email))

        with self._lock:
            for key, scope, limit, window_seconds in rules:
                decision = self._check_rule(
                    key=key,
                    scope=scope,
                    limit=limit,
                    window_seconds=window_seconds,
                    now=now,
                )
                if not decision.allowed:
                    return decision

            for key, _scope, limit, _window_seconds in rules:
                if limit > 0:
                    self._events[key].append(now)

        return RateLimitDecision(allowed=True)

    def reset(self) -> None:
        with self._lock:
            self._events.clear()

    def _rules(self, *, ip_address: str, email: Optional[str]) -> Iterable[Tuple[str, str, int, int]]:
        yield (f"ip:{ip_address or 'unknown'}", "ip", self.per_ip_limit, 60)
        if email:
            yield (f"email:{email.strip().lower()}", "email", self.per_email_limit, 60 * 60)
        yield ("global", "global", self.global_limit, 60)

    def _check_rule(
        self,
        *,
        key: str,
        scope: str,
        limit: int,
        window_seconds: int,
        now: float,
    ) -> RateLimitDecision:
        if limit <= 0:
            return RateLimitDecision(allowed=True)

        events = self._events[key]
        cutoff = now - window_seconds
        while events and events[0] <= cutoff:
            events.popleft()

        if len(events) < limit:
            return RateLimitDecision(allowed=True)

        retry_after = max(1, math.ceil(window_seconds - (now - events[0])))
        return RateLimitDecision(
            allowed=False,
            scope=scope,
            retry_after_seconds=retry_after,
        )
