"""Unit tests for Pydantic payload models."""
import pytest
from datetime import datetime, timezone
from app.models.schemas import TradingViewPayload, TradeAction, TickerData


class TestTradingViewPayload:
    """Test TradingView payload validation and normalization."""

    def test_valid_buy_payload(self):
        payload = TradingViewPayload(
            ticker="BINANCE:BTCUSDT",
            action=TradeAction.BUY,
            quantity=0.05,
            price=62340.50,
        )
        assert payload.ticker == "BINANCE:BTCUSDT"
        assert payload.action == TradeAction.BUY
        assert payload.quantity == 0.05
        assert payload.price == 62340.50

    def test_ticker_normalization(self):
        """Ticker should be upper-cased."""
        payload = TradingViewPayload(
            ticker="binance:btcusdt",
            action=TradeAction.BUY,
            quantity=0.1,
        )
        assert payload.ticker == "BINANCE:BTCUSDT"

    def test_missing_required_fields(self):
        """Should raise validation error for missing required fields."""
        with pytest.raises(Exception):
            TradingViewPayload(ticker="", action="", quantity=0)  # type: ignore

    def test_invalid_quantity(self):
        """Quantity must be positive."""
        with pytest.raises(Exception):
            TradingViewPayload(
                ticker="BTCUSDT",
                action=TradeAction.BUY,
                quantity=-0.1,
            )

    def test_with_strategy(self):
        """Payload with strategy metadata."""
        payload = TradingViewPayload(
            ticker="BINANCE:ETHUSDT",
            action=TradeAction.SELL,
            quantity=1.5,
            strategy=TickerData(
                name="RSI_Divergence",
                parameters={"rsi": 28, "ema": 50}
            ),
        )
        assert payload.strategy.name == "RSI_Divergence"
        assert payload.strategy.parameters["rsi"] == 28

    def test_with_all_fields(self):
        """Full payload with optional fields."""
        payload = TradingViewPayload(
            ticker="BINANCE:BTCUSDT",
            action=TradeAction.STOP_BUY,
            quantity=0.1,
            price=64000,
            strategy=TickerData(name="MA_Cross", parameters={"fast": 10, "slow": 50}),
            timestamp=datetime.now(timezone.utc),
            exchange="BINANCE",
            interval="1h",
            message="Strong bullish divergence detected",
        )
        assert payload.exchange == "BINANCE"
        assert payload.interval == "1h"
        assert len(payload.message) <= 500
