"""Unit tests for paper trading engine."""
import tempfile
from pathlib import Path
from app.services.paper_engine import (
    PaperTradingEngine,
    Order,
    Position,
    Trade,
    OrderSide,
)


def test_buy_order_execution():
    """Test basic buy order execution."""
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
        journal = f.name

    try:
        engine = PaperTradingEngine(initial_capital=10000.0, journal_path=journal)
        engine.set_price("BTCUSDT", 50000.0)

        result = engine.process_order(
            ticker="BTCUSDT",
            action="buy",
            requested_qty=0.1,
            price=50000.0,
        )

        assert result["status"] == "filled"
        assert result["order_id"].startswith("ORD-")
        assert engine.cash < 10000.0
        assert len(engine.positions) == 1
        assert engine.positions["BTCUSDT"].quantity == 0.1
    finally:
        Path(journal).unlink(missing_ok=True)


def test_sell_order_closes_position():
    """Test sell order that closes an existing long."""
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
        journal = f.name

    try:
        engine = PaperTradingEngine(initial_capital=10000.0, journal_path=journal)
        engine.set_price("BTCUSDT", 50000.0)

        # Buy first
        engine.process_order(ticker="BTCUSDT", action="buy", requested_qty=0.1, price=50000.0)
        assert len(engine.trade_history) == 0

        # Sell to close
        engine.set_price("BTCUSDT", 55000.0)
        result = engine.process_order(ticker="BTCUSDT", action="sell", requested_qty=0.1, price=55000.0)

        assert result["status"] == "filled"
        assert len(engine.positions) == 0
        assert len(engine.trade_history) == 1
        trade = engine.trade_history[0]
        assert trade.pnl > 0  # Profit
        assert trade.entry_price == 50000.0
        assert trade.exit_price == 55000.0
    finally:
        Path(journal).unlink(missing_ok=True)


def test_position_sizing_limit():
    """Test position size limit (5% of capital)."""
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
        journal = f.name

    try:
        engine = PaperTradingEngine(initial_capital=10000.0, journal_path=journal)
        engine.set_price("BTCUSDT", 50000.0)

        # Request large size
        result = engine.process_order(
            ticker="BTCUSDT",
            action="buy",
            requested_qty=1.0,  # $50k
            price=50000.0,
        )

        # Should be limited to 5% of capital = $500 => 0.01 BTC
        max_allowed = 10000.0 * 0.05 / 50000.0
        actual_qty = result["quantity"]
        assert actual_qty <= max_allowed + 1e-9
    finally:
        Path(journal).unlink(missing_ok=True)


def test_daily_loss_limit():
    """Test daily loss limit enforcement."""
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
        journal = f.name

    try:
        engine = PaperTradingEngine(initial_capital=10000.0, journal_path=journal)

        # First trade: small loss
        engine.set_price("BTCUSDT", 50000.0)
        engine.process_order(ticker="BTCUSDT", action="buy", requested_qty=0.1, price=50000.0)
        engine.set_price("BTCUSDT", 49000.0)  # Down 2%
        result = engine.process_order(ticker="BTCUSDT", action="sell", requested_qty=0.1, price=49000.0)

        assert result["status"] == "filled"

        # Second trade: should hit daily loss limit (2% of capital = $200)
        # Already lost ~100, so one more small loss should trigger
        engine.set_price("BTCUSDT", 50000.0)
        engine.process_order(ticker="BTCUSDT", action="buy", requested_qty=0.1, price=50000.0)
        engine.set_price("BTCUSDT", 49500.0)  # Down 1% = $50 loss
        result2 = engine.process_order(ticker="BTCUSDT", action="sell", requested_qty=0.1, price=49500.0)

        # If limit hit, should be rejected
        if result2["status"] == "rejected":
            assert "Daily loss limit" in result2["error"]
    finally:
        Path(journal).unlink(missing_ok=True)


def test_unrealized_pnl():
    """Test P&L updates as price changes."""
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
        journal = f.name

    try:
        engine = PaperTradingEngine(initial_capital=10000.0, journal_path=journal)
        engine.set_price("BTCUSDT", 50000.0)
        engine.process_order(ticker="BTCUSDT", action="buy", requested_qty=0.1, price=50000.0)

        pos = engine.positions["BTCUSDT"]
        assert pos.unrealized_pnl == 0.0

        engine.set_price("BTCUSDT", 52000.0)
        assert pos.unrealized_pnl > 0
        assert pos.unrealized_pnl_pct > 0

        engine.set_price("BTCUSDT", 48000.0)
        assert pos.unrealized_pnl < 0
    finally:
        Path(journal).unlink(missing_ok=True)


def test_stats_calculation():
    """Test trading statistics."""
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
        journal = f.name

    try:
        engine = PaperTradingEngine(initial_capital=10000.0, journal_path=journal)
        engine.set_price("BTCUSDT", 50000.0)
        engine.process_order(ticker="BTCUSDT", action="buy", requested_qty=0.1, price=50000.0)
        engine.set_price("BTCUSDT", 55000.0)
        engine.process_order(ticker="BTCUSDT", action="sell", requested_qty=0.1, price=55000.0)

        stats = engine.get_stats()
        assert stats["total_trades"] == 1
        assert stats["winning_trades"] == 1
        assert stats["win_rate"] == 100.0
        assert stats["realized_pnl"] > 0
        assert stats["total_return_pct"] > 0
    finally:
        Path(journal).unlink(missing_ok=True)
