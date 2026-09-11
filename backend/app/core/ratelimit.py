"""
In-process rate limiting for the authentication endpoints.

Without this, `/auth/login` is an offline-speed password oracle: an attacker can
try thousands of passwords a second against a known officer e-mail. bcrypt slows
each attempt, but nothing bounds the number of attempts.

Deliberately in-process and dependency-free. That is the correct trade for a
single-node deployment; behind more than one worker each process keeps its own
counters, so the effective limit multiplies by the worker count. For a
multi-node deployment move this to Redis or enforce it at the reverse proxy —
`docs/DEPLOYMENT.md` says so.
"""

import threading
import time
from collections import defaultdict, deque
from typing import Deque, Dict, Tuple


class SlidingWindowLimiter:
    """Allows `limit` events per `window_seconds`, keyed by caller."""

    def __init__(self, limit: int, window_seconds: int):
        self.limit = limit
        self.window = window_seconds
        self._hits: Dict[str, Deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str) -> Tuple[bool, int]:
        """
        Returns (allowed, retry_after_seconds).

        Records the event when it is allowed, so callers do not have to remember
        to do it separately.
        """
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            while hits and now - hits[0] > self.window:
                hits.popleft()

            if len(hits) >= self.limit:
                return False, max(1, int(self.window - (now - hits[0])) + 1)

            hits.append(now)

            # Opportunistic cleanup: without it, one key per attacker IP would
            # accumulate for the life of the process.
            if len(self._hits) > 4096:
                for stale in [k for k, v in self._hits.items() if not v or now - v[-1] > self.window]:
                    del self._hits[stale]

            return True, 0

    def reset(self, key: str) -> None:
        """Clears a key's history - called after a successful sign-in."""
        with self._lock:
            self._hits.pop(key, None)


#: Failed attempts against ONE account. Tight: this is what actually stops a
#: targeted brute force, and it costs a legitimate officer nothing — they know
#: their own password, and a success clears the budget.
login_email_limiter = SlidingWindowLimiter(limit=8, window_seconds=300)

#: Failed attempts from one address, across all accounts. Deliberately much
#: looser than the per-account limit: a Legal Metrology office puts every
#: inspector behind one public IP, so a tight per-IP budget means one colleague
#: fat-fingering a password locks out the whole office. The per-account limit is
#: the real defence; this one only blunts a spray across many accounts.
login_ip_limiter = SlidingWindowLimiter(limit=50, window_seconds=300)

#: Account creation, to stop a public deployment being filled with junk accounts.
#: Also raised for shared-NAT offices onboarding a team in one sitting.
register_limiter = SlidingWindowLimiter(limit=20, window_seconds=3600)


def client_key(request, suffix: str = "") -> str:
    """
    Identifies the caller.

    Prefers the left-most X-Forwarded-For entry so a proxied deployment limits the
    real client rather than the proxy. That header is caller-controlled and can be
    spoofed, which is why login is *also* limited per e-mail address: an attacker
    rotating the header still cannot brute-force one officer's account.
    """
    forwarded = request.headers.get("x-forwarded-for", "")
    ip = forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else "unknown")
    return f"{ip}:{suffix}" if suffix else ip
