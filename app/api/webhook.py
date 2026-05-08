"""Webhook HTTP API endpoints."""
import time
import uuid
from contextlib import asynccontextmanager
from typing import Dict, Any

import structlog
from fastapi import FastAPI, Request, HTTPException, Depends, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.logging_config import get_logger, setup_logging, log_webhook_event
from app.core.security import verify_tradingview_signature
from app.models.schemas import TradingViewPayload, ProcessedWebhook, WebhookMetadata
from app.services.processor import WebhookProcessor
from app.utils.rate_limiter import check_rate_limit, _request_tracker

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup/shutdown lifecycle."""
    # Startup
    settings = get_settings()
    setup_logging(
        log_format=settings.log_format,
        log_level=settings.log_level,
        log_file=settings.log_file,
        log_max_bytes=settings.log_max_bytes,
        log_backup_count=settings.log_backup_count,
    )
    logger.info(
        "starting_webhook_server",
        host=settings.host,
        port=settings.port,
        dry_run=settings.dry_run,
        broker=settings.broker,
        mcp_enabled=settings.mcp_enabled,
    )

    # Initialize processor
    processor = WebhookProcessor()
    app.state.processor = processor
    _request_tracker.dry_run_mode = settings.dry_run

    yield

    # Shutdown
    logger.info("shutting_down", stats=_request_tracker.get_stats())


app = FastAPI(
    title="TradingView Webhook Listener",
    description="Receive and process TradingView alerts with MCP integration and paper trading.",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS - restrict to known origins in production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: Restrict to TradingView IPs/origins
    allow_credentials=True,
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)


async def verify_request(request: Request) -> bool:
    """Verify webhook signature and rate limit."""
    settings = get_settings()
    client_ip = request.client.host if request.client else "unknown"

    # Rate limiting
    if not check_rate_limit(client_ip, logger):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
        )

    # Signature verification (if enabled)
    if settings.verify_signatures:
        signature = request.headers.get(settings.webhook_signature_header)
        if not signature:
            logger.warning("missing_signature_header", ip=client_ip)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing webhook signature",
            )

        # Read body for verification (must be done before fast read)
        body = await request.body()
        settings_obj = get_settings()
        if not verify_tradingview_signature(body, signature, settings_obj.webhook_secret, logger):
            logger.warning("invalid_signature", ip=client_ip, sig_prefix=signature[:20])
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid webhook signature",
            )
        return True

    return True


async def get_processor(request: Request) -> WebhookProcessor:
    """Get the webhook processor from app state."""
    return request.app.state.processor


@app.get("/health")
async def health_check() -> Dict[str, Any]:
    """Health check endpoint for monitoring."""
    settings = get_settings()
    return {
        "status": "healthy",
        "service": "trade-vibte-webhook",
        "dry_run": settings.dry_run,
        "broker": settings.broker,
        "mcp_enabled": settings.mcp_enabled,
        "mode": "paper_trading" if settings.is_paper_trading else "live_trading",
    }


@app.get("/metrics")
async def metrics() -> Dict[str, Any]:
    """Request metrics endpoint."""
    return _request_tracker.get_stats()


@app.post("/webhook")
async def receive_webhook(
    request: Request,
    processor: WebhookProcessor = Depends(get_processor),
    _: bool = Depends(verify_request),
) -> JSONResponse:
    """
    Receive TradingView webhook and process the signal.

    Expected JSON payload:
    {
        "ticker": "BINANCE:BTCUSDT",
        "action": "buy",
        "quantity": 0.05,
        "price": 62340.50,
        "strategy": {"name": "RSI_Divergence", "parameters": {...}},
        "timestamp": "2026-05-09T00:53:04Z",
        "interval": "5m"
    }
    """
    start_time = time.time()
    client_ip = request.client.host if request.client else "unknown"
    request_id = str(uuid.uuid4())[:8]

    try:
        # Parse and validate JSON body
        body = await request.json()
        logger.debug("webhook_received", request_id=request_id, ip=client_ip, body=body)

        # Validate payload
        payload = TradingViewPayload(**body)

        # Process through pipeline (validation, dry-run, execution)
        result = await processor.process(payload, request_id)

        duration_ms = (time.time() - start_time) * 1000
        _request_tracker.record_request(client_ip, valid=True, processing_ms=duration_ms)

        log_webhook_event(
            logger,
            "webhook_processed",
            body,
            request_id=request_id,
            duration_ms=round(duration_ms, 2),
            dry_run=result["dry_run"],
            order_id=result.get("order_id"),
            status=result["status"],
        )

        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "success": True,
                "request_id": request_id,
                "dry_run": result["dry_run"],
                "status": result["status"],
                "order_id": result.get("order_id"),
                "message": result.get("message", "Signal processed"),
                "timestamp": result.get("timestamp"),
            },
        )

    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        _request_tracker.record_request(client_ip, valid=False, processing_ms=duration_ms)

        logger.error(
            "webhook_processing_failed",
            error=str(e),
            error_type=type(e).__name__,
            request_id=request_id,
            ip=client_ip,
            duration_ms=round(duration_ms, 2),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to process webhook: {str(e)}",
        )


@app.post("/webhook/test")
async def test_webhook(
    payload: TradingViewPayload,
    processor: WebhookProcessor = Depends(get_processor),
) -> JSONResponse:
    """
    Test endpoint (no signature required) for local development.
    Useful for simulating alerts without TradingView webhooks.
    """
    request_id = f"test-{uuid.uuid4()[:8]}"
    start_time = time.time()

    try:
        result = await processor.process(payload, request_id)

        duration_ms = (time.time() - start_time) * 1000

        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "success": True,
                "request_id": request_id,
                "dry_run": result["dry_run"],
                "status": result["status"],
                "order_id": result.get("order_id"),
                "message": result.get("message", "Test signal processed"),
                "duration_ms": round(duration_ms, 2),
            },
        )
    except Exception as e:
        logger.error("test_webhook_failed", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Test failed: {str(e)}",
        )


@app.get("/")
async def root() -> Dict[str, str]:
    """Root endpoint with API info."""
    return {
        "service": "TradingView Webhook Listener",
        "version": "0.1.0",
        "docs_url": "/docs",
        "health_url": "/health",
        "webhook_url": "/webhook",
        "test_url": "/webhook/test",
    }
