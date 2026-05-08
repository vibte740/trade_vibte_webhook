# TradingView Webhook Listener — Configuration Guide

This guide explains how to configure TradingView alerts to send signals to your webhook listener.

## 1. Webhook URL

Set the webhook URL in TradingView to:
```
https://your-server.com/webhook
```
Replace `your-server.com` with your actual server IP/hostname.

**For local development, use ngrok or similar:**
```bash
ngrok http 8000
```
Then set webhook URL to the ngrok HTTPS endpoint.

## 2. Alert Message Format

TradingView supports JSON payloads in the alert "Message" field. Use this format:

```json
{
  "ticker": "BINANCE:BTCUSDT",
  "action": "buy",
  "quantity": 0.05,
  "price": 63000.50,
  "strategy": {
    "name": "MyStrategy",
    "parameters": {
      "rsi_period": 14,
      "ema_period": 50
    }
  },
  "interval": "1h"
}
```

### Field Reference

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `ticker` | string | ✅ | Trading symbol in exchange:symbol format |
| `action` | string | ✅ | `buy`, `sell`, `stop_buy`, `stop_sell` |
| `quantity` | float | ✅ | Order size in base asset |
| `price` | float | ❌ | Current/trigger price (optional) |
| `strategy.name` | string | ❌ | Strategy identifier |
| `strategy.parameters` | object | ❌ | Strategy key-value parameters |
| `interval` | string | ❌ | Chart timeframe (e.g. `5m`, `1h`, `1d`) |
| `exchange` | string | ❌ | Override exchange (if not in ticker) |

## 3. Signature Verification

The webhook expects a signature header: `X-TradingView-Signature`. TradingView's webhook system does not natively support custom signature headers, so you have two options:

### Option A: Disable Signature Verification (Development)
In `.env`:
```
VERIFY_SIGNATURES=false
```
This is **not recommended for production**.

### Option B: Use Custom Webhook Middleware (Production)
You'll need to insert a proxy/middleware layer that adds the signature. Example with Express.js:

```javascript
const crypto = require('crypto');

app.use('/webhook', (req, res, next) => {
  const secret = process.env.WEBHOOK_SECRET;
  const body = JSON.stringify(req.body);
  const timestamp = Date.now().toString();
  const signature = crypto
    .createHmac('sha256', secret)
    .update(timestamp + '.' + body)
    .digest('hex');

  req.headers['X-TradingView-Signature'] = `timestamp=${timestamp},v_signature=${signature}`;
  next();
});
```

## 4. Pine Script Example

Below is a Pine Script v5 strategy that sends alerts to your webhook:

```pinescript
//@version=5
strategy("RSI Divergence Strategy", overlay=true, margin_long=100, margin_short=100)

// RSI
rsiLength = input.int(14, "RSI Length")
rsi = ta.rsi(close, rsiLength)

// Divergence detection (simplified)
bullishDiv = ta.lowest(rsi, 5) < 30 and rsi[1] < rsi and close > close[1]
bearishDiv = ta.highest(rsi, 5) > 70 and rsi[1] > rsi and close < close[1]

// Entry conditions
longCondition = bullishDiv
shortCondition = bearishDiv

// Strategy logic
if (longCondition)
    strategy.entry("Long", strategy.long)
    alert("{\"ticker\":\"BINANCE:BTCUSDT\",\"action\":\"buy\",\"quantity\":0.05,\"price\":\"{{close}}\",\"strategy\":{\"name\":\"RSI_Divergence\",\"parameters\":{\"rsi\":{{rsi}}}}}", alert.freq_once_per_bar_close)

if (shortCondition)
    strategy.entry("Short", strategy.short)
    alert("{\"ticker\":\"BINANCE:BTCUSDT\",\"action\":\"sell\",\"quantity\":0.05,\"price\":\"{{close}}\",\"strategy\":{\"name\":\"RSI_Divergence\",\"parameters\":{\"rsi\":{{rsi}}}}}", alert.freq_once_per_bar_close)

// Plotting
plotshape(bullishDiv, "Bullish Divergence", shape.triangleup, location.belowbar, color=color.green, size=size.small)
plotshape(bearishDiv, "Bearish Divergence", shape.triangledown, location.abovebar, color=color.red, size=size.small)
```

## 5. Testing Your Setup

Use the test endpoint (no signature required):

```bash
curl -X POST http://localhost:8000/webhook/test \
  -H "Content-Type: application/json" \
  -d '{
    "ticker": "BINANCE:BTCUSDT",
    "action": "buy",
    "quantity": 0.01,
    "price": 63000
  }'
```

Expected response:
```json
{
  "success": true,
  "dry_run": true,
  "status": "filled",
  "order_id": "ORD-20260509-123456-BTCUSDT",
  "message": "Signal processed"
}
```

## 6. Logs & Monitoring

- **Logs:** Written to `logs/` or stdout (console in dev)
- **Metrics:** GET `/metrics` returns request stats
- **Health:** GET `/health` returns service status

## 7. Common Issues

| Symptom | Likely Fix |
|---------|------------|
| HTTP 401 | Signature missing/invalid, disable `VERIFY_SIGNATURES` for testing |
| HTTP 422 | Invalid JSON or missing required fields |
| HTTP 429 | Rate limit exceeded (max 120 req/min) |
| No orders | Check paper engine journal at `data/paper_trades.jsonl` |
| Signal rejected | Check logs for validation errors |

## 8. Next Steps

1. Configure your `.env` with desired trading parameters
2. Deploy webhook listener (Docker/K8s)
3. Create Pine Script strategy
4. Validate with test endpoint
5. Go live with production webhook URL
