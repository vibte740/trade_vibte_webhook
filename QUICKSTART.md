# TradingView Webhook Listener — Quick Start Guide

## What This Is

A production-grade **FastAPI webhook server** that receives TradingView alerts and:
- Validates payloads (Pydantic models)
- Simulates paper trading by default (no real money)
- Optionally forwards signals to a local TradingView MCP for live execution
- Logs everything to file and stdout
- Exposes metrics for monitoring

**No external dependencies beyond Python packages.** Ready to drop into production behind nginx.

---

## Directory Layout (Core Files)

```
app/
├── api/webhook.py        ── POST /webhook (main endpoint)
├── core/config.py        ── Settings loaded from .env
├── models/schemas.py     ── TradingViewPayload model
├── services/paper_engine.py ── Simulated exchange
├── services/processor.py ── Pipeline orchestration
├── mcp/client.py         ── MCP adapter
└── main.py               ── CLI: trade-vibte-webhook serve
```

---

## 1. Install

```bash
# System Python (or use virtualenv)
python3 -m pip install -r requirements.txt

# Verify installation
python3 smoke_test.py   # Should say "✓ ..."
```

**Minimal deps:** `fastapi uvicorn pydantic python-dotenv structlog`

**Paper engine extras:** `pandas numpy`

All listed in `requirements.txt`.

---

## 2. Configure

```bash
cp .env.example .env
# Edit .env:
#   - Set WEBHOOK_SECRET (already generated for you)
#   - Set DRY_RUN=true for paper trading OR false for live
#   - Set BROKER=simulate (paper) or binance/bybit/oanda (live)
#   - Set MCP_ENABLED & MCP_SERVER_PATH if using MCP
```

Quick check:
```bash
cat .env | grep -E 'WEBHOOK_SECRET|DRY_RUN|BROKER'
```

---

## 3. Run

```bash
# Development (auto-reload)
uvicorn app.api.webhook:app --reload

# OR using CLI
python3 -m app.main serve --reload

# Production
python3 -m app.main serve --host 0.0.0.0 --port 8000 --workers 4
```

Server starts on `http://0.0.0.0:8000`

---

## 4. Test

### Via Test Endpoint (no signature needed)
```bash
curl -X POST http://localhost:8000/webhook/test \
  -H "Content-Type: application/json" \
  -d '{
    "ticker": "BINANCE:BTCUSDT",
    "action": "buy",
    "quantity": 0.05,
    "price": 63000.00
  }'
```

Expected response:
```json
{
  "success": true,
  "dry_run": true,
  "status": "filled",
  "order_id": "ORD-20260509-xxxxxx-BTCUSDT",
  "message": "Signal processed"
}
```

### Check Paper Journal
```bash
cat data/paper_trades.jsonl | tail -n 5 | jq .
```

### Metrics
```bash
curl http://localhost:8000/metrics | jq .
```

---

## 5. Connect TradingView

1. Open TradingView chart
2. Click **"Create Alert"**
3. Set **Condition** (e.g., `RSI(close, 14) crosses below 30`)
4. Set **Message**:
   ```json
   {
     "ticker": "BINANCE:BTCUSDT",
     "action": "buy",
     "quantity": 0.05,
     "price": "{{close}}"
   }
   ```
   Use `{{variable}}` placeholders for dynamic values.
5. Set **Webhook URL** to your public endpoint, e.g.:
   ```
   https://your-server.com/webhook
   ```
   *For local testing:* Use ngrok `https://<id>.ngrok.io/webhook`
6. Create alert. When trigger hits, TradingView POSTs to your server.

---

## 6. Verify Live (Production)

1. **Deploy server** (VPS, cloud, or local with public IP)
2. **Obtain HTTPS** (use Let's Encrypt or Cloudflare Tunnel)
3. **Set webhook URL** in TradingView to `https://your-domain.com/webhook`
4. **Set `VERIFY_SIGNATURES=false`** in `.env` (TradingView does not support custom headers)
5. **Dry-run first:** Confirm signals appear in `data/paper_trades.jsonl`
6. **Go live:** Set `DRY_RUN=false` and configure `BROKER=binance` + API keys (requires MCP integration for live execution)

**Tip:** The `/webhook/test` endpoint is your friend for debugging before wiring TradingView.

---

## Key Concepts

### Dry-Run vs Live

| Mode | Behaviour |
|------|-----------|
| `DRY_RUN=true` | All signals validated & simulated locally. No external calls. Immediate console logs. |
| `DRY_RUN=false` | Signals forwarded to MCP for execution by configured broker (binance, etc.). |

### MCP Integration (for Live Trading)

The local TradingView MCP exposes tools like `execute_signal`. The `MCPClient`:
- Starts MCP via `StdioTransport` if `MCP_SERVER_PATH` given
- Connects via HTTP if no path (defaults port 3000)
- Forwards validated signals to `tools/call` with name `tradingview_execute_signal`

### Paper Engine Features

- **Position sizing:** Max 5% of capital per position
- **Daily loss limit:** 2% max loss per day (rejects new orders)
- **Commission:** 0.1% taker fee
- **Journal:** All orders & trades appended to `data/paper_trades.jsonl`
- **Stats API:** `engine.get_stats()` returns P&L, win rate, open positions

### Security

- **HMAC verification:** `X-TradingView-Signature` header validated against `WEBHOOK_SECRET`
- **Rate limiting:** 120 requests/minute per IP (token bucket)
- **Input validation:** Strict Pydantic schema rejects malformed payloads
- **Secure secrets:** `.env` excluded via git; secrets never logged

---

## Troubleshooting

| Symptom | Check |
|---------|-------|
| `curl: (22) 401` | Signature missing; set `VERIFY_SIGNATURES=false` for testing |
| `422 Unprocessable Entity` | JSON payload missing required fields (ticker, action, quantity) |
| No response | Check server logs (`tail -f logs/app.log` or console) |
| 429 Too Many Requests | Rate limit exceeded; increase limit in `app/utils/rate_limiter.py` or throttle client |
| Journal not created | Ensure `data/` directory is writable |

Log output (dev):
```
2026-05-09 01:00:00 | INFO  | app.api.webhook | webhook_received | ticker=BINANCE:BTCUSDT action=buy ...
2026-05-09 01:00:00 | INFO  | services.processor | processing_signal | request_id=abc123 ...
2026-05-09 01:00:00 | INFO  | services.paper_engine | order_processed | order_id=ORD-... side=buy ...
```

---

## Development Workflow

```bash
# 1. Install pre-commit hooks (optional)
pre-commit install

# 2. Make code changes
vim app/services/paper_engine.py

# 3. Format & lint
make format
make lint

# 4. Test
make test     # unit + integration
make smoke    # quick sanity

# 5. Run
make run

# 6. Docker
make docker-build
make docker-run
```

---

## Production Deployment

### Docker (Single Container)

```bash
docker build -t trade-vibte-webhook .
docker run -d \
  --name webhook \
  -p 8000:8000 \
  --env-file .env \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/logs:/app/logs \
  trade-vibte-webhook:latest
```

### Kubernetes (Example)

Minimal Deployment + Service + Ingress to be added based on your cluster.

---

## Resources

- `README.md` — Full project documentation
- `ALERT_SETUP.md` — TradingView Pine Script & alert configuration examples
- `PLANNING.md` — Architecture deep-dive & future roadmap
- `smoke_test.py` — Quick import & basic functionality check

---

Ready. The server is production-ready for dry-run trading; live trading requires MCP and broker API configuration.
