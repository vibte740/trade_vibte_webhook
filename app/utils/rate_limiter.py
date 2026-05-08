"""Rate limiting and request tracking utilities."""
import time
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple

from structlog.stdlib import BoundLogger


class SimpleRateLimiter:
    """Token bucket rate limiter per IP address."""

    def __init__(self, max_requests: int = 60, window_seconds: int = 60):
        """
        Initialize rate limiter.

        Args:
            max_requests: Max requests allowed per window
            window_seconds: Time window in seconds
        """
        self.max_requests = max_requests
        self.window = window_seconds
        self._requests: Dict[str, list] = defaultdict(list)

    def is_allowed(self, key: str) -> Tuple[bool, Optional[int]]:
        """
        Check if request from key is allowed.

        Returns:
            (allowed: bool, remaining: Optional[int])
        """
        now = time.time()
        window_start = now - self.window

        # Clean old entries
        self._requests[key] = [t for t in self._requests[key] if t > window_start]

        # Check rate limit
        if len(self._requests[key]) >= self.max_requests:
            return False, 0

        self._requests[key].append(now)
        return True, self.max_requests - len(self._requests[key])


class RequestTracker:
    """Track webhook requests for monitoring and audit."""

    def __init__(self):
        self.total_requests = 0
        self.valid_requests = 0
        self.invalid_requests = 0
        self.dry_run_mode = True
        self._recent_requests = []
        self._recent_limit = 1000

    def record_request(self, ip: str, valid: bool, processing_ms: float) -> None:
        """Record a processed webhook request."""
        self.total_requests += 1
        if valid:
            self.valid_requests += 1
        else:
            self.invalid_requests += 1

        self._recent_requests.append({
            "timestamp": datetime.utcnow().isoformat(),
            "ip": ip,
            "valid": valid,
            "processing_ms": round(processing_ms, 2),
        })
        if len(self._recent_requests) > self._recent_limit:
            self._recent_requests.pop(0)

    def get_stats(self) -> Dict[str, object]:
        """Return current statistics."""
        return {
            "total_requests": self.total_requests,
            "valid_requests": self.valid_requests,
            "invalid_requests": self.invalid_requests,
            "success_rate": (
                (self.valid_requests / self.total_requests * 100)
                if self.total_requests > 0 else 0.0
            ),
            "dry_run_mode": self.dry_run_mode,
            "recent_requests": self._recent_requests[-50:],
        }


# Global instances
_rate_limiter = SimpleRateLimiter(max_requests=120, window_seconds=60)
_request_tracker = RequestTracker()


def check_rate_limit(ip: str, logger: Optional[BoundLogger] = None) -> bool:
    """Check if IP is within rate limit."""
    allowed, remaining = _rate_limiter.is_allowed(ip)
    if logger and not allowed:
        logger.warning("rate_limit_exceeded", ip=ip)
    return allowed


def get_request_stats() -> Dict[str, object]:
    """Get current request statistics."""
    return _request_tracker.get_stats()
