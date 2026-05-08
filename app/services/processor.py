"""Main webhook processing pipeline."""
from datetime import datetime
from typing import Any, Dict, Optional

import structlog

from app.core.config import get_settings
from app.models.schemas import TradingViewPayload
from app.mcp.client import create_mcp_client, MCPClient
from app.services.paper_engine import get_paper_engine, PaperTradingEngine
from app.utils.rate_limiter import log_webhook_event

logger = structlog.get_logger(__name__)


class WebhookProcessor:
    """
    Single Responsibility: process TradingView signal → execution result.

    Pipeline stages:
    1.  Payload validation (Pydantic)
    2.  Dry-run decision (config flag)
    3.  MCP forward (if enabled)
    4.  Paper-trading execution (simulate order)
    5.  Result enrichment & logging
    """

    def __init__(self):
        self.settings = get_settings()
        self.paper_engine: PaperTradingEngine = get_paper_engine()
        self.mcp_client: Optional[MCPClient] = None

        if self.settings.mcp_enabled:
            self.mcp_client = create_mcp_client(self.settings)
            logger.info("mcp_client_initialized")

    async def initialize(self) -> None:
        """Connect to MCP if enabled (called on startup)."""
        if self.mcp_client:
            await self.mcp_client.connect()

    async def process(
        self,
        payload: TradingViewPayload,
        request_id: str,
    ) -> Dict[str, Any]:
        """
        Execute full webhook processing pipeline.

        Returns a dict with keys:
          - status: "executed" | "validated" | "error"
          - dry_run: bool
          - order_id: str | None
          - message: str
          - timestamp: ISO string
        """
        start_time = datetime.utcnow()

        try:
            # ── Stage 1: Payload already validated by Pydantic ───────────────────
            logger.info(
                "processing_signal",
                request_id=request_id,
                ticker=payload.ticker,
                action=payload.action,
                quantity=payload.quantity,
                dry_run=self.settings.dry_run,
            )

            # ── Stage 2: Execute or simulate ──────────────────────────────────
            if self.settings.dry_run:
                # Dry-run mode: validate + simulate locally
                order_price = payload.price or self._estimate_price(payload.ticker)
                result = await self.paper_engine.process_order(
                    ticker=payload.ticker,
                    action=payload.action,
                    requested_qty=payload.quantity,
                    price=order_price,
                    strategy_name=payload.strategy.name if payload.strategy else None,
                    strategy_params=payload.strategy.params if payload.strategy else None,
                )
                result["dry_run"] = True
            else:
                # Live mode: send to MCP (which talks to real broker)
                if not self.mcp_client:
                    raise RuntimeError("MCP client not available in live mode")
                result = await self.mcp_client.execute_signal(payload.dict())
                result["dry_run"] = False

            # ── Stage 3: Enrich result ────────────────────────────────────────
            processing_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

            enriched = {
                **result,
                "request_id": request_id,
                "timestamp": datetime.utcnow().isoformat(),
                "ticker": payload.ticker,
                "action": payload.action.value,
                "quantity": payload.quantity,
                "processing_ms": round(processing_ms, 2),
                "broker": self.settings.broker,
                "mode": "paper" if self.settings.is_paper_trading else "live",
            }

            # ── Stage 4: Logging ──────────────────────────────────────────────
            log_webhook_event(
                logger,
                "signal_result",
                payload.dict(),
                request_id=request_id,
                **enriched,
            )

            return enriched

        except Exception as e:
            logger.error(
                "signal_processing_failed",
                request_id=request_id,
                error=str(e),
                exc_info=True,
            )
            raise

    def _estimate_price(self, ticker: str) -> float:
        """Return a placeholder price for dry-run when none provided."""
        # In production, you'd fetch from a price feed or MCP
        # For now, return a hard-coded BTC-ish price
        if "BTC" in ticker:
            return 62_000.0
        if "ETH" in ticker:
            return 3_400.0
        return 100.0
