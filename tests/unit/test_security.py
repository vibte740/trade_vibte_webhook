"""Unit tests for webhook security and rate limiting."""
import hashlib
import hmac
import time
from app.core.security import verify_signature, verify_tradingview_signature
from app.utils.rate_limiter import SimpleRateLimiter, _request_tracker


def test_hmac_signature_verification():
    """Test valid HMAC signature verification."""
    secret = "my-secret-key"
    payload = b'{"ticker":"BTCUSDT","action":"buy"}'
    timestamp = "1704689584"
    message = f"{timestamp}.{payload.decode()}"

    signature = hmac.new(
        secret.encode(),
        message.encode(),
        hashlib.sha256,
    ).hexdigest()

    # Simulate TradingView header format
    header_value = f"timestamp={timestamp},v_signature={signature}"

    assert verify_signature(payload, header_value, secret, "X-TradingView-Signature")


def test_invalid_signature():
    """Test rejection of invalid signature."""
    payload = b'{"test":"data"}'
    bad_sig = "timestamp=123,v_signature=bad_sig"
    assert not verify_signature(payload, bad_sig, "secret", "X-Header")


def test_tradingview_signer_wrapper():
    """Test TradingView signature wrapper."""
    import structlog

    logger = structlog.get_logger("test")
    payload = b'{"ticker":"BTCUSDT"}'
    # Invalid signature
    assert not verify_tradingview_signature(payload, "bad", "secret", logger)


class TestRateLimiter:
    """Test rate limiting functionality."""

    def test_allow_within_limit(self):
        limiter = SimpleRateLimiter(max_requests=10, window_seconds=1)
        allowed, remaining = limiter.is_allowed("192.168.1.1")
        assert allowed is True
        assert remaining == 9

    def test_block_exceeding_limit(self):
        limiter = SimpleRateLimiter(max_requests=3, window_seconds=1)
        # Exhaust limit
        for _ in range(3):
            limiter.is_allowed("127.0.0.1")
        allowed, remaining = limiter.is_allowed("127.0.0.1")
        assert allowed is False
        assert remaining == 0

    def test_rate_limit_per_key(self):
        """Limiter should track counts per key independently."""
        limiter = SimpleRateLimiter(max_requests=2, window_seconds=1)
        limiter.is_allowed("ip1")
        limiter.is_allowed("ip2")
        limiter.is_allowed("ip1")  # exhaust ip1 limit (2nd call)
        allowed1, _ = limiter.is_allowed("ip1")  # should be denied (3rd call)
        allowed2, _ = limiter.is_allowed("ip2")  # still has quota (2nd call)
        assert allowed1 is False
        assert allowed2 is True

    def test_rate_limit_expiry(self):
        """Requests should expire after window."""
        limiter = SimpleRateLimiter(max_requests=1, window_seconds=1)
        limiter.is_allowed("test")
        allowed, _ = limiter.is_allowed("test")
        assert allowed is False

        time.sleep(1.1)
        allowed, _ = limiter.is_allowed("test")
        assert allowed is True


def test_global_request_tracker():
    """Test global request statistics tracking."""
    tracker = _request_tracker
    tracker.total_requests = 0
    tracker.valid_requests = 0
    tracker.invalid_requests = 0

    tracker.record_request("127.0.0.1", valid=True, processing_ms=50.0)
    tracker.record_request("192.168.1.1", valid=False, processing_ms=100.0)

    stats = tracker.get_stats()
    assert stats["total_requests"] == 2
    assert stats["valid_requests"] == 1
    assert stats["invalid_requests"] == 1
    assert stats["success_rate"] == 50.0
