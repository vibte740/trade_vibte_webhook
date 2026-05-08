"""Paper trading engine with order simulation and position management."""
import json
import logging
from contextlib asynccontextmanager
from dataclasses import dataclass, asdict
from datetime import datetime
from decimal import Decimal, ROUND_DOWN
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import structlog
from pydantic import BaseModel

from app.core.config import get_settings
from app.models.schemas import TradingViewPayload, TradeAction

logger = structlog.get_logger(__name__)


# ── Domain models ──────────────────────────────────────────────────────────────

class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderStatus(str, Enum):
    PENDING = "pending"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


@dataclass
class Order:
    """Simulated exchange order."""
    id: str
    ticker: str
    side: OrderSide
    quantity: float
    price: float
    status: OrderStatus = OrderStatus.PENDING
    filled_qty: float = 0.0
    avg_price: float = 0.0
    commission: float = 0.0
    created_at: datetime = None
    filled_at: Optional[datetime] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()


@dataclass
class Position:
    """Open trading position."""
    ticker: str
    side: OrderSide
    quantity: float
    entry_price: float
    current_price: float
    unrealized_pnl: float = 0.0
    unrealized_pnl_pct: float = 0.0
    opened_at: datetime = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None

    def __post_init__(self):
        if self.opened_at is None:
            self.opened_at = datetime.utcnow()


@dataclass
class Trade:
    """Executed trade record."""
    id: str
    ticker: str
    side: OrderSide
    quantity: float
    entry_price: float
    exit_price: float
    pnl: float
    pnl_pct: float
    commission: float
    opened_at: datetime
    closed_at: datetime
    strategy: Optional[str] = None
    strategy_params: Optional[Dict[str, Any]] = None


# ── Simulation logic ──────────────────────────────────────────────────────────

class PaperTradingEngine:
    """
    Simulates trading with paper money.

    Features:
    - Order matching at current market price
    - Position tracking and P&L calculation
    - Risk management (position sizing, daily loss limits)
    - Trade journaling (append-only JSONL)
    - Statistics and analytics
    """

    PRICE_PRECISION = 2  # For BTC-like assets; adjust per ticker

    def __init__(self, initial_capital: float, journal_path: str):
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.journal_path = Path(journal_path)
        self.journal_path.parent.mkdir(parents=True, exist_ok=True)

        # In-memory state
        self.positions: Dict[str, Position] = {}
        self.order_history: List[Order] = []
        self.trade_history: List[Trade] = []
        self.daily_pnl: Dict[str, float] = {}  # date -> P&L
        self.max_position_pct = 0.05  # 5%
        self.daily_loss_limit_pct = 0.02  # 2%

        # Simple price feed (for demo, use fixed prices or a mock OHLCV)
        self._price_feed: Dict[str, float] = {}

        logger.info("paper_trading_engine_initialized", capital=initial_capital)

    def set_price(self, ticker: str, price: float) -> None:
        """Update current market price for a ticker."""
        self._price_feed[ticker] = price
        self._update_position_pnl(ticker, price)

    def _update_position_pnl(self, ticker: str, price: float) -> None:
        """Recalculate unrealized P&L for a position."""
        pos = self.positions.get(ticker)
        if not pos:
            return
        pos.current_price = price
        if pos.side == OrderSide.BUY:
            pos.unrealized_pnl = (price - pos.entry_price) * pos.quantity
            pos.unrealized_pnl_pct = (price - pos.entry_price) / pos.entry_price
        else:
            pos.unrealized_pnl = (pos.entry_price - price) * pos.quantity
            pos.unrealized_pnl_pct = (pos.entry_price - price) / pos.entry_price

    def _check_daily_loss_limit(self) -> Tuple[bool, float]:
        """Check if daily loss limit is breached."""
        today = datetime.utcnow().strftime("%Y-%m-%d")
        loss = self.daily_pnl.get(today, 0.0)
        limit = -self.initial_capital * self.daily_loss_limit_pct
        return loss < limit, limit

    def _calculate_position_size(self, ticker: str, price: float, quantity: float) -> float:
        """Calculate max allowed position size based on risk rules."""
        max_capital = self.initial_capital * self.max_position_pct
        # Invert to base-asset quantity
        max_qty = max_capital / price
        return min(quantity, max_qty)

    async def process_order(
        self,
        ticker: str,
        action: TradeAction,
        requested_qty: float,
        price: float,
        strategy_name: Optional[str] = None,
        strategy_params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Process a TradingView signal as a simulated order.

        Args:
            ticker: Trading symbol
            action: Buy/sell/etc.
            requested_qty: Desired order size
            price: Current market price (or None for last known)
            strategy_name: Strategy that generated the signal
            strategy_params: Strategy parameters

        Returns:
            Order result dict
        """
        try:
            # Map action to side
            action_map = {
                TradeAction.BUY: OrderSide.BUY,
                TradeAction.STOP_BUY: OrderSide.BUY,
                TradeAction.SELL: OrderSide.SELL,
                TradeAction.STOP_SELL: OrderSide.SELL,
            }
            side = action_map.get(action)
            if not side:
                return {
                    "status": OrderStatus.REJECTED,
                    "error": f"Unsupported action: {action}",
                }

            # Validate price
            if price is None:
                price = self._price_feed.get(ticker)
                if price is None:
                    return {"status": OrderStatus.REJECTED, "error": "No price available"}

            # Apply position sizing limits
            allowed_qty = self._calculate_position_size(ticker, price, requested_qty)
            if allowed_qty < requested_qty:
                logger.info(
                    "position_size_limited",
                    ticker=ticker,
                    requested=requested_qty,
                    allowed=allowed_qty,
                )

            quantity = allowed_qty

            # Check daily loss limit
            breached, limit = self._check_daily_loss_limit()
            if breached:
                logger.warning("daily_loss_limit_hit", limit=limit)
                return {
                    "status": OrderStatus.REJECTED,
                    "error": f"Daily loss limit exceeded (limit: {limit})",
                }

            # ── Create and fill order (simple market fill) ───────────────────────
            order_id = f"ORD-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}-{ticker[:6]}"
            order = Order(
                id=order_id,
                ticker=ticker,
                side=side,
                quantity=quantity,
                price=price,
                status=OrderStatus.FILLED,
                filled_qty=quantity,
                avg_price=price,
                commission=quantity * price * 0.001,  # 0.1% taker fee
            )
            order.filled_at = datetime.utcnow()
            self.order_history.append(order)

            # ── Update position ───────────────────────────────────────────────────
            existing = self.positions.get(ticker)

            if side == OrderSide.BUY:
                # Increase long or open new
                if existing and existing.side == OrderSide.BUY:
                    # Average up
                    new_qty = existing.quantity + quantity
                    new_avg = (
                        existing.entry_price * existing.quantity
                        + price * quantity
                    ) / new_qty
                    existing.quantity = new_qty
                    existing.entry_price = new_avg
                    existing.stop_loss = min(existing.stop_loss or price, price * 0.95)
                else:
                    # Open new long (or flip short)
                    self.positions[ticker] = Position(
                        ticker=ticker,
                        side=OrderSide.BUY,
                        quantity=quantity,
                        entry_price=price,
                        current_price=price,
                        stop_loss=price * 0.95,
                        take_profit=price * 1.10,
                    )
                self.cash -= (quantity * price) + order.commission
            else:  # SELL
                if existing and existing.side == OrderSide.BUY:
                    # Reduce or close long
                    if quantity >= existing.quantity:
                        # Close full position - create a Trade
                        trade = Trade(
                            id=f"TRD-{order_id}",
                            ticker=ticker,
                            side=OrderSide.BUY,
                            quantity=existing.quantity,
                            entry_price=existing.entry_price,
                            exit_price=price,
                            pnl=(price - existing.entry_price) * existing.quantity - order.commission,
                            pnl_pct=(price - existing.entry_price) / existing.entry_price,
                            commission=order.commission,
                            opened_at=existing.opened_at,
                            closed_at=order.filled_at,
                            strategy=strategy_name,
                            strategy_params=strategy_params,
                        )
                        self.trade_history.append(trade)
                        self._record_daily_pnl(trade.pnl)
                        del self.positions[ticker]
                    else:
                        # Partial close
                        existing.quantity -= quantity
                        # For partial close, we need to book some P&L
                        portion = quantity / (existing.quantity + quantity)
                        realized_pnl = (price - existing.entry_price) * quantity - order.commission
                        self._record_daily_pnl(realized_pnl)
                else:
                    # Open short
                    self.positions[ticker] = Position(
                        ticker=ticker,
                        side=OrderSide.SELL,
                        quantity=quantity,
                        entry_price=price,
                        current_price=price,
                        stop_loss=price * 1.05,
                        take_profit=price * 0.90,
                    )
                    self.cash += (quantity * price) - order.commission

            # ── Persist to journal ─────────────────────────────────────────────────
            self._write_journal_entry({
                "type": "order",
                "order_id": order_id,
                "ticker": ticker,
                "side": side.value,
                "quantity": quantity,
                "price": price,
                "commission": order.commission,
                "timestamp": order.filled_at.isoformat(),
                "action": action.value,
                "strategy": strategy_name,
            })

            logger.info(
                "order_processed",
                order_id=order_id,
                ticker=ticker,
                side=side.value,
                quantity=quantity,
                price=price,
                cash_remaining=self.cash,
                positions_count=len(self.positions),
            )

            return {
                "status": OrderStatus.FILLED,
                "order_id": order_id,
                "side": side.value,
                "quantity": quantity,
                "price": price,
                "commission": order.commission,
                "timestamp": order.filled_at.isoformat(),
                "dry_run": True,
                "cash_remaining": self.cash,
                "positions": list(self.positions.keys()),
            }

        except Exception as e:
            logger.error("order_processing_failed", error=str(e), exc_info=True)
            return {"status": OrderStatus.REJECTED, "error": str(e)}

    def _record_daily_pnl(self, pnl: float) -> None:
        """Accumulate daily P&L."""
        today = datetime.utcnow().strftime("%Y-%m-%d")
        self.daily_pnl[today] = self.daily_pnl.get(today, 0.0) + pnl

    def _write_journal_entry(self, entry: Dict[str, Any]) -> None:
        """Append a JSONL entry to the paper trading journal."""
        with self.journal_path.open("a") as f:
            f.write(json.dumps(entry, default=str) + "\n")

    async def update_prices(self, price_data: Dict[str, float]) -> None:
        """Update prices for all positions."""
        for ticker, price in price_data.items():
            self.set_price(ticker, price)

    def get_stats(self) -> Dict[str, Any]:
        """Return trading statistics."""
        unrealized = sum(p.unrealized_pnl for p in self.positions.values())
        realized = sum(t.pnl for t in self.trade_history)
        total_pnl = unrealized + realized
        win_trades = [t for t in self.trade_history if t.pnl > 0]
        loss_trades = [t for t in self.trade_history if t.pnl < 0]

        return {
            "initial_capital": self.initial_capital,
            "current_cash": self.cash,
            "unrealized_pnl": unrealized,
            "realized_pnl": realized,
            "total_pnl": total_pnl,
            "total_return_pct": (total_pnl / self.initial_capital) * 100,
            "open_positions": len(self.positions),
            "total_trades": len(self.trade_history),
            "winning_trades": len(win_trades),
            "losing_trades": len(loss_trades),
            "win_rate": (len(win_trades) / len(self.trade_history) * 100)
            if self.trade_history else 0.0,
            "positions": [
                {
                    "ticker": p.ticker,
                    "side": p.side.value,
                    "quantity": p.quantity,
                    "entry_price": p.entry_price,
                    "current_price": p.current_price,
                    "unrealized_pnl": p.unrealized_pnl,
                    "unrealized_pnl_pct": p.unrealized_pnl_pct,
                }
                for p in self.positions.values()
            ],
        }

    def get_equity_curve(self) -> pd.DataFrame:
        """Return equity curve as DataFrame."""
        if not self.trade_history:
            return pd.DataFrame()

        df = pd.DataFrame([asdict(t) for t in self.trade_history])
        df["cumulative_pnl"] = df["pnl"].cumsum()
        df["equity"] = self.initial_capital + df["cumulative_pnl"]
        df["closed_at"] = pd.to_datetime(df["closed_at"])
        return df.sort_values("closed_at")


# ── Singleton management ───────────────────────────────────────────────────────

_paper_engine: Optional[PaperTradingEngine] = None


def get_paper_engine() -> PaperTradingEngine:
    """Get or create the global paper trading engine."""
    global _paper_engine
    if _paper_engine is None:
        settings = get_settings()
        _paper_engine = PaperTradingEngine(
            initial_capital=settings.paper_capital,
            journal_path=settings.paper_journal_path,
        )
    return _paper_engine
