#!/usr/bin/env python3
"""Quick smoke test: imports, config load, model validation."""
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from app.core.config import get_settings, Settings
    from app.models.schemas import TradingViewPayload, TradeAction

    # Test config loading
    settings = get_settings()
    print("✓ Config loaded")

    # Test model validation
    payload = TradingViewPayload(
        ticker="BINANCE:BTCUSDT",
        action=TradeAction.BUY,
        quantity=0.1,
        price=63000.0
    )
    print(f"✓ Payload validated: {payload.ticker}")

    # Test paper engine creation (without full execution)
    from app.services.paper_engine import PaperTradingEngine
    engine = PaperTradingEngine(initial_capital=10000.0, journal_path="/tmp/test_journal.jsonl")
    engine.set_price("BTCUSDT", 63000.0)
    print(f"✓ Paper engine initialized with cash: ${engine.cash:,.2f}")

    print("\n✅ All smoke checks passed. Application ready to run.")
    print("\nTo start server:")
    print("  python3 -m uvicorn app.api.webhook:app --reload")
    print("\nOr use CLI:")
    print("  python3 -m app.main serve --reload")

except Exception as e:
    print(f"❌ Smoke test failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
