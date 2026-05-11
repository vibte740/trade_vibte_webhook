# TradingView Webhook Listener

Production-grade webhook listener for TradingView alerts with MCP integration and paper trading engine.

## Architecture Overview

```
┌─────────────┐     ┌─────────────────────────────────────────────────────────────────┐
│ TradingView │────▶│  Webhook Endpoint (/webhook)                                    │
│   Alerts    │     │  ┌────────────────────────────────────────────────────────┐ │
│             │     │  │ 1. Signature verification (HMAC-SHA256)                │ │
│             │     │  │ 2. Rate limiting (per-IP token bucket)                 │ │
│             │     │  │ 3. Payload validation (Pydantic models)                 │ │
│             │     │  └────────────────────────────────────────────────────────┘ │
└─────────────┘     └───────────────┬─────────────────────────────────────────────┘
                                    │
          ┌─────────────────────────┼──────────────────────────┐
          │                         │                          │
          ▼                         ▼                          ▼
    ┌─────────┐            ┌──────────────┐           ┌──────────────┐
    │  Dry-Run│            │ Paper Trading│           │    MCP       │
    │  Mode   │            │   Engine     │           │ Integration  │
    │         │            │ ┌──────────┐ │           │ ┌──────────┐ │
    │ Validate│            │ │Position  │ │           │ │Execute   │ │
    │ Only    │            │ │Tracking  │ │           │ │Signal    │ │
    │         │            │ │P&L       │ │           │ │via MCP   │ │
    └─────────┘            │ │Journal   │ │           │ └──────────┘ │
                           │ └──────────┘ │           └──────────────┘
                           └──────────────┘
```

## Features

- ✅ **Secure webhook endpoint** — HMAC-SHA256 signature verification
- ✅ **Schema validation** — Pydantic models for TradingView payloads
- ✅ **Rate limiting** — Per-IP token bucket (120 req/min)
- ✅ **Dry-run mode** — Validate signals without executing orders
- ✅ **Paper trading engine** — Full order simulation, position tracking, P&L
- ✅ **MCP integration** — Bridge to local TradingView MCP for live execution
- ✅ **Risk management** — Position limits, daily loss stops
- ✅ **Trade journal** — Append-only JSONL audit trail
- ✅ **Structured logging** — JSON/console log formats with structlog
- ✅ **Health & metrics** — `/health` and `/metrics` endpoints
- ✅ **CLI tool** — `trade-vibte-webhook` command with subcommands

## Quick Start

### Prerequisites

- Python 3.10+
- `pip` or `poetry`
- TradingView account (for alerts)

### Installation

```bash
# Clone repo
git clone <your-repo>
cd trade_vibte_webhook

# Install dependencies
pip install -r requirements.txt

# Copy & edit environment
cp .env.example .env
# Edit .env with your webhook secret
```

### Running the Server

```bash
# Development (auto-reload)
python -m uvicorn app.api.webhook:app --reload

# With CLI
python -m app.main serve --reload

# Production
python -m app.main serve --host 0.0.0.0 --port 8000 --workers 4
```

### Environment Variables

Key settings (see `.env.example` for full list):

| Variable | Description | Default |
|----------|-------------|---------|
| `HOST` | Bind address | `0.0.0.0` |
| `PORT` | Bind port | `8000` |
| `WEBHOOK_SECRET` | HMAC secret (REQUIRED) | — |
| `DRY_RUN` | If true, only validate, don't trade | `true` |
| `BROKER` | `simulate`, `binance`, `bybit`, `oanda` | `simulate` |
| `PAPER_CAPITAL` | Starting capital for paper trading | `10000.0` |

## TradingView Alert Setup

1. Create a new alert in TradingView
2. Set **Message** to a JSON payload:

```json
{
  "ticker": "BINANCE:BTCUSDT",
  "action": "buy",
  "quantity": 0.05,
  "price": 62340.50,
  "strategy": {
    "name": "RSI_Divergence",
    "parameters": {"rsi": 28, "ema": 50}
  }
}
```

3. Set **Webhook URL** to: `https://your-server.com/webhook`
4. Enable **Alert Message** → **JSON**
5. Note: Signature verification must be disabled on TradingView (not supported), so set `VERIFY_SIGNATURES=false` for Testing

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/webhook` | Main webhook (requires signature) |
| `POST` | `/webhook/test` | Test endpoint (no signature) |
| `GET` | `/health` | Health check |
| `GET` | `/metrics` | Request statistics |

### Test Payload Example

```bash
curl -X POST http://localhost:8000/webhook/test \
  -H "Content-Type: application/json" \
  -d '{
    "ticker": "BINANCE:BTCUSDT",
    "action": "buy",
    "quantity": 0.1,
    "price": 63000
  }'
```

## MCP Integration

The Local Trading MCP exposes tools like `execute_signal`, `get_positions`, and `get_balance`. To enable:

1. Set `MCP_ENABLED=true` in `.env`
2. Provide `MCP_SERVER_PATH` (or default HTTP transport will be used)
3. The webhook forwards validated signals to MCP for execution

MCP client supports:
- `StdioTransport` — launch local MCP as subprocess
- `HttpTransport` — connect to already-running HTTP MCP server

## Paper Trading Engine

When `DRY_RUN=true` (default), orders are simulated locally:

- **Order matching:** Market orders fill at next tick price
- **Position tracking:** Long/short positions with unrealized P&L
- **Risk limits:** Max 5% of capital per position; 2% daily loss stop
- **Journal:** All orders/trades appended to `data/paper_trades.jsonl`
- **Commission:** 0.1% taker fee (adjustable)

### Reading the Journal

```python
import pandas as pd

trades = pd.read_json("data/paper_trades.jsonl", lines=True)
print(trades.tail())
```

## Production Deployment

### Docker

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "-m", "app.main", "serve", "--host", "0.0.0.0", "--port", "8000"]
```

### Kubernetes

See `k8s/` for example manifests (to be added).

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest -v

# Lint
ruff check .
black .

# Type checking
mypy app/
```

## Daily Supertrend Analysis

A scheduled script scans the top 20 crypto pairs and generates a Supertrend signal report.
Each run creates a **timestamped file** (`supertrend_YYYY-MM-DD_HH-MM-SS.txt`) and a
`supertrend_latest.txt` symlink points to the most recent report.

### Usage

```bash
# Generate a new timestamped report (live Binance data)
make supertrend-current
# or
.venv/bin/python scripts/update_supertrend_current.py

# Older synthetic/CCXT-based version (keeps historical archives)
.venv/bin/python scripts/generate_daily_supertrend.py
```

Reports are saved to `docs/supertrend/supertrend_YYYY-MM-DD_HH-MM-SS.txt`.
The current report is always available at `docs/supertrend/supertrend_latest.txt`.

### Scheduling

See [docs/scheduling/DAILY_SCHEDULE.md](docs/scheduling/DAILY_SCHEDULE.md) for cron and systemd timer setup.

### Configuration

- **ATR Length:** 10
- **Multiplier:** 3.0
- **Primary timeframe:** 15m
- **Confirmation:** 1h, 4h

The script uses synthetic demo data by default. For live data install `ccxt`:

```bash
pip install -r requirements-analysis.txt
```

Then set `use_live = True` in `scripts/generate_daily_supertrend.py`.

### Methodology

Read `skill/Supertrend.md` for the complete strategy, confidence scoring algorithm, and filtering rules.

---

## Project Structure

```
trade_vibte_webhook/
├── app/
│   ├── api/           # FastAPI routes (webhook.py)
│   ├── core/          # Config, logging, security
│   ├── models/        # Pydantic schemas
│   ├── services/      # Paper engine & processor
│   ├── mcp/           # MCP client adapter
│   ├── utils/         # Rate limiting, helpers
│   └── main.py        # CLI entrypoint
├── data/              # Paper trading journal (JSONL)
├── logs/              # Rotating application logs
├── tests/             # Unit & integration tests
├── .env.example       # Environment template
├── pyproject.toml     # Project metadata
└── requirements.txt   # Dependencies
```

## Error Handling & Observability

- **HTTP status codes:** 200 OK, 400 Bad Request, 401 Unauthorized, 429 Too Many Requests, 500 Internal Server Error
- **Logging:** JSON format in production, colored console in development
- **Metrics:** Request counts, success rate, processing latency
- **Alerting:** Optional Slack webhook for critical failures

## Security Notes

- **Never commit `.env`** — keep webhook secret secure
- **Use HTTPS** in production (behind reverse proxy)
- **Restrict CORS** origins to known hosts
- **Rotate webhook secrets** periodically
- **Enable signature verification** when using a custom TradingView integration

## License

MIT

## Support

Issues: https://github.com/vibte/trade_vibte_webhook/issues
