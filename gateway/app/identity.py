import hashlib
import hmac
import secrets
import time
from collections import defaultdict, deque

COOKIE_NAME = "sid"


def sign(session_id: str, secret: str) -> str:
    """Return 'id.signature'.

    The signature stops a visitor editing the cookie to read somebody else's
    documents.
    """
    digest = hmac.new(
        secret.encode(), session_id.encode(), hashlib.sha256
    ).hexdigest()[:32]

    return f"{session_id}.{digest}"


def verify(cookie: str, secret: str) -> str | None:
    """Return the session id if the signature matches, otherwise None."""
    session_id, _, digest = cookie.partition(".")

    if not session_id or not digest:
        return None

    expected = sign(session_id, secret).split(".")[1]

    # compare_digest avoids leaking the answer through response timing.
    if not hmac.compare_digest(digest, expected):
        return None

    return session_id


def new_session_id() -> str:
    return secrets.token_urlsafe(16)


class RateLimiter:
    """Allow `limit` requests per `window` seconds, per caller.

    Held in memory, so the count resets on restart and is not shared between
    instances. Enough for a single-instance deployment; a shared store such as
    Redis would be the next step.
    """

    def __init__(self, limit: int, window: int):
        self.limit = limit
        self.window = window
        self._hits: dict[str, deque] = defaultdict(deque)

    def allow(self, caller: str) -> bool:
        now = time.time()
        hits = self._hits[caller]

        # Drop anything that has aged out of the window.
        while hits and now - hits[0] > self.window:
            hits.popleft()

        if len(hits) >= self.limit:
            return False

        hits.append(now)
        return True

    def retry_after(self, caller: str) -> int:
        hits = self._hits[caller]

        if not hits:
            return 0

        return max(1, int(self.window - (time.time() - hits[0])))
