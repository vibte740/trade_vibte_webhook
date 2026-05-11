"""Integration tests for FastAPI webhook endpoint."""
import pytest
from fastapi.testclient import TestClient

from app.api.webhook import app
from app.core.config import get_settings
from app.services.paper_engine import get_paper_engine


@pytest.fixture
def client():
    """Test client fixture."""
    # Reset paper engine
    import app.services.paper_engine as pe
    pe._paper_engine = None

    # Reset rate limiter and request tracker
    from app.utils.rate_limiter import _rate_limiter, _request_tracker
    _rate_limiter._requests.clear()
    _request_tracker.total_requests = 0
    _request_tracker.valid_requests = 0
    _request_tracker.invalid_requests = 0
    _request_tracker._recent_requests.clear()

    # Override settings for testing
    settings = get_settings()
    original_dry_run = settings.dry_run
    settings.dry_run = True

    with TestClient(app) as c:
        yield c

    settings.dry_run = original_dry_run


def test_health_endpoint(client):
    """Health check should return 200."""
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert "dry_run" in data


def test_metrics_endpoint(client):
    """Metrics should return statistics."""
    resp = client.get("/metrics")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_requests" in data


def test_test_endpoint_valid_payload(client):
    """Test endpoint should accept valid payload."""
    payload = {
        "ticker": "BINANCE:BTCUSDT",
        "action": "buy",
        "quantity": 0.1,
        "price": 63000.0,
    }
    resp = client.post("/webhook/test", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "order_id" in data
    assert data["dry_run"] is True


def test_webhook_endpoint_requires_signature(client):
    """Main webhook should reject requests without signature."""
    payload = {
        "ticker": "BINANCE:BTCUSDT",
        "action": "buy",
        "quantity": 0.1,
    }
    resp = client.post("/webhook", json=payload)
    assert resp.status_code == 401


def test_webhook_endpoint_invalid_signature(client):
    """Main webhook should reject requests with bad signature."""
    payload = {
        "ticker": "BINANCE:BTCUSDT",
        "action": "buy",
        "quantity": 0.1,
    }
    # Note: signature verification might be disabled depending on config
    headers = {
        "X-TradingView-Signature": "bad-signature"
    }
    resp = client.post("/webhook", json=payload, headers=headers)
    # If signatures enabled expect 401, else 200
    settings = get_settings()
    if settings.verify_signatures:
        assert resp.status_code == 401
    else:
        assert resp.status_code == 200


def test_invalid_payload_rejected(client):
    """Missing required fields should return 400."""
    payload = {
        "ticker": "",
        "action": "buy",
        "quantity": -1,
    }
    resp = client.post("/webhook/test", json=payload)
    assert resp.status_code == 422  # Validation error


def test_multiple_orders_accumulate_positions(client):
    """Multiple buys should accumulate position."""
    engine = get_paper_engine()
    engine.positions.clear()

    for _ in range(3):
        payload = {
            "ticker": "BINANCE:ETHUSDT",
            "action": "buy",
            "quantity": 0.5,
            "price": 3000.0,
        }
        resp = client.post("/webhook/test", json=payload)
        assert resp.status_code == 200

    assert engine.positions["BINANCE:ETHUSDT"].quantity >= 0.5


def test_buy_sell_cycle_creates_trade(client):
    """Full buy-sell cycle should create a trade record."""
    engine = get_paper_engine()
    engine.positions.clear()
    engine.trade_history.clear()

    buy_payload = {
        "ticker": "BINANCE:BTCUSDT",
        "action": "buy",
        "quantity": 0.2,
        "price": 60000.0,
    }
    sell_payload = {
        "ticker": "BINANCE:BTCUSDT",
        "action": "sell",
        "quantity": 0.2,
        "price": 61000.0,
    }

    client.post("/webhook/test", json=buy_payload)
    client.post("/webhook/test", json=sell_payload)

    trades = engine.trade_history
    assert len(trades) == 1
    assert trades[0].pnl > 0


def test_concurrent_requests_rate_limit(client):
    """Too many requests should be rate-limited."""
    # Hit the rate limit hard
    for i in range(130):
        resp = client.post("/webhook", json={
            "ticker": "BTCUSDT",
            "action": "buy",
            "quantity": 0.01,
        })
        if resp.status_code == 429:
            break

    assert resp.status_code == 429


def test_stats_endpoint_after_requests(client):
    """Metrics should reflect processed requests."""
    # Disable signature verification for this test to allow a successful request
    from app.core.config import get_settings
    settings = get_settings()
    original_verify = settings.verify_signatures
    settings.verify_signatures = False
    try:
        resp = client.post("/webhook", json={
            "ticker": "BINANCE:ETHUSDT",
            "action": "buy",
            "quantity": 0.1,
            "price": 3000.0,
        })
        assert resp.status_code == 200
    finally:
        settings.verify_signatures = original_verify

    resp = client.get("/metrics")
    data = resp.json()
    assert data["total_requests"] >= 1
    assert data["success_rate"] > 0
