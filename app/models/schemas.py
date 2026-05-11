"""TradingView webhook payload models."""
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class TradeAction(str, Enum):
    """Supported trading actions."""
    BUY = "buy"
    SELL = "sell"
    STOP_BUY = "stop_buy"
    STOP_SELL = "stop_sell"
    ALERT = "alert"


class TickerData(BaseModel):
    """Strategy parameters that accompany an alert."""
    name: Optional[str] = Field(None, description="Strategy name")
    parameters: dict = Field(default_factory=dict, description="Strategy key-value parameters")


class TradingViewPayload(BaseModel):
    """Canonical TradingView webhook payload schema."""
    ticker: str = Field(..., description="Trading symbol (e.g. BINANCE:BTCUSDT)", min_length=1)
    action: TradeAction = Field(..., description="Trade action to perform")
    quantity: float = Field(..., description="Order quantity in base asset", gt=0)
    price: Optional[float] = Field(None, description="Current market price (optional)")
    strategy: Optional[TickerData] = Field(None, description="Strategy metadata")
    timestamp: Optional[datetime] = Field(None, description="Signal timestamp (UTC)")
    exchange: Optional[str] = Field(None, description="Exchange identifier")
    interval: Optional[str] = Field(None, description="Chart interval (e.g. '5m', '1h')")
    message: Optional[str] = Field(None, description="Custom alert message")

    @field_validator("ticker")
    @classmethod
    def normalize_ticker(cls, v: str) -> str:
        """Normalize ticker format."""
        return v.upper().strip()

    @field_validator("message")
    @classmethod
    def truncate_message(cls, v: Optional[str]) -> Optional[str]:
        """Truncate long messages."""
        if v and len(v) > 500:
            return v[:500] + "..."
        return v


class WebhookMetadata(BaseModel):
    """Metadata added during webhook processing."""
    received_at: datetime
    ip_address: str
    user_agent: Optional[str]
    signature_valid: bool
    processing_duration_ms: float


class ProcessedWebhook(BaseModel):
    """Complete payload after validation."""
    data: TradingViewPayload
    metadata: WebhookMetadata


# Convenience alias
AlertPayload = TradingViewPayload
