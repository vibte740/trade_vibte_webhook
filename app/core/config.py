"""Core configuration loaded from environment variables."""
from functools import lru_cache
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable binding."""

    # ── Server ──────────────────────────────────────────────────────────────────
    host: str = Field(default="0.0.0.0", alias="HOST")
    port: int = Field(default=8000, alias="PORT")
    workers: int = Field(default=1, alias="WORKERS")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # ── Webhook ─────────────────────────────────────────────────────────────────
    webhook_secret: str = Field(..., alias="WEBHOOK_SECRET")
    webhook_signature_header: str = Field(
        default="X-TradingView-Signature", alias="WEBHOOK_SIGNATURE_HEADER"
    )
    verify_signatures: bool = Field(default=True, alias="VERIFY_SIGNATURES")

    # ── Operation Mode ──────────────────────────────────────────────────────────
    dry_run: bool = Field(default=True, alias="DRY_RUN")

    # ── Paper Trading ───────────────────────────────────────────────────────────
    paper_capital: float = Field(default=10000.0, alias="PAPER_CAPITAL")
    paper_journal_path: str = Field(default="data/paper_trades.jsonl", alias="PAPER_JOURNAL_PATH")
    max_position_size_pct: float = Field(default=5.0, alias="MAX_POSITION_SIZE_PCT")
    max_daily_loss_pct: float = Field(default=2.0, alias="MAX_DAILY_LOSS_PCT")

    # ── Broker ──────────────────────────────────────────────────────────────────
    broker: str = Field(default="simulate", alias="BROKER")
    binance_api_key: Optional[str] = Field(default=None, alias="BINANCE_API_KEY")
    binance_api_secret: Optional[str] = Field(default=None, alias="BINANCE_API_SECRET")
    bybit_api_key: Optional[str] = Field(default=None, alias="BYBIT_API_KEY")
    bybit_api_secret: Optional[str] = Field(default=None, alias="BYBIT_API_SECRET")
    oanda_access_token: Optional[str] = Field(default=None, alias="OANDA_ACCESS_TOKEN")
    oanda_account_id: Optional[str] = Field(default=None, alias="OANDA_ACCOUNT_ID")

    # ── MCP ─────────────────────────────────────────────────────────────────────
    mcp_enabled: bool = Field(default=True, alias="MCP_ENABLED")
    mcp_server_path: Optional[str] = Field(default=None, alias="MCP_SERVER_PATH")
    mcp_server_args: str = Field(default="", alias="MCP_SERVER_ARGS")

    # ── Metrics ─────────────────────────────────────────────────────────────────
    enable_metrics: bool = Field(default=True, alias="ENABLE_METRICS")
    metrics_port: int = Field(default=9090, alias="METRICS_PORT")

    # ── Alerting ────────────────────────────────────────────────────────────────
    alert_email: Optional[str] = Field(default=None, alias="ALERT_EMAIL")
    slack_webhook_url: Optional[str] = Field(default=None, alias="SLACK_WEBHOOK_URL")

    # ── Logging ─────────────────────────────────────────────────────────────────
    log_format: str = Field(default="console", alias="LOG_FORMAT")
    log_file: Optional[str] = Field(default=None, alias="LOG_FILE")
    log_max_bytes: int = Field(default=10_485_760, alias="LOG_MAX_BYTES")
    log_backup_count: int = Field(default=5, alias="LOG_BACKUP_COUNT")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("broker")
    @classmethod
    def validate_broker(cls, v: str) -> str:
        allowed = {"simulate", "binance", "bybit", "oanda"}
        if v.lower() not in allowed:
            raise ValueError(f"Unsupported broker: {v} (allowed: {', '.join(allowed)})")
        return v.lower()

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        v_upper = v.upper()
        if v_upper not in allowed:
            raise ValueError(f"Invalid log level: {v}. Allowed: {', '.join(allowed)}")
        return v_upper

    @property
    def is_paper_trading(self) -> bool:
        """Return True if we are in paper-trading/dry-run mode."""
        return self.dry_run or self.broker == "simulate"

    @property
    def is_live_trading(self) -> bool:
        """Return True if we are configured for live trading."""
        return not self.dry_run and self.broker != "simulate"


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings (loads from env once)."""
    return Settings()
