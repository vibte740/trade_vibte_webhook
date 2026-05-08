"""Pytest configuration and fixtures."""
import os
import sys
from pathlib import Path

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Configure environment for tests."""
    os.environ["DRY_RUN"] = "true"
    os.environ["LOG_LEVEL"] = "DEBUG"
    os.environ["WEBHOOK_SECRET"] = "test-secret-not-production"
    os.environ["PAPER_JOURNAL_PATH"] = "/tmp/test_trades.jsonl"
    yield
    # Cleanup
    Path("/tmp/test_trades.jsonl").unlink(missing_ok=True)


@pytest.fixture
def sample_payload():
    """Sample TradingView payload."""
    return {
        "ticker": "BINANCE:BTCUSDT",
        "action": "buy",
        "quantity": 0.05,
        "price": 63000.0,
        "strategy": {
            "name": "RSI_Divergence",
            "parameters": {"rsi": 28}
        }
    }
