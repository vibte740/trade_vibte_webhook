# Skill: Crypto Supertrend Scanner

Fetches OHLCV data from Binance public API, computes the Supertrend indicator (ATR-based),
and produces a structured morning briefing with trend direction, price vs. Supertrend level,
ATR values, and fresh BUY/SELL crossover signals.

## Triggers

Run this skill when the user requests:
- Daily crypto signals or Supertrend scan
- Morning crypto briefing / crypto trend report
- Which coins are bullish/bearish right now
- New buy/sell signals in crypto
- "Run the Supertrend" or any variant
- Add/remove coins from the Supertrend watchlist
- Change ATR period, multiplier, or timeframe (1h/4h/1d)

## Configuration

Edit `scripts/crypto_supertrend.py` to change defaults:

```python
DEFAULT_SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT",
    "ADAUSDT", "DOGEUSDT", "AVAXUSDT", "DOTUSDT", "LINKUSDT",
    "MATICUSDT", "LTCUSDT", "UNIUSDT", "ATOMUSDT", "NEARUSDT",
    "APTUSDT", "ARBUSDT", "OPUSDT", "INJUSDT", "SUIUSDT",
]
DEFAULT_INTERVAL = "1d"  # 1h, 4h, 1d
DEFAULT_ATR_PERIOD = 10
DEFAULT_MULTIPLIER = 3.0
```

Or override via CLI arguments (see Usage).

---

## Usage (Agent)

```bash
# Default scan: 20 coins, 1d candles, text output
python scripts/crypto_supertrend.py

# JSON output for downstream LLM processing or automation
python scripts/crypto_supertrend.py --output json

# Custom watchlist (space-separated)
python scripts/crypto_supertrend.py --symbols BTCUSDT ETHUSDT SOLUSDT

# Shorter timeframe, tighter settings
python scripts/crypto_supertrend.py --interval 4h --atr-period 7 --multiplier 2.5

# 1-hour scalping mode
python scripts/crypto_supertrend.py --interval 1h --atr-period 5 --multiplier 2.0

# Save to file for later processing
python scripts/crypto_supertrend.py --output json > reports/supertrend_$(date +%Y%m%d).json
```

---

## Output Formats

### Text (default)

```
============================================================
  🔔 CRYPTO SUPERTREND MORNING BRIEFING
  2026-05-11 06:00:00 UTC   ATR(10) × 3.0  |  Interval: 1d
============================================================

  Universe: 20 coins | 🟢 14 Bullish | 🔴 6 Bearish

  🟢 NEW BUY signals  : SOL, NEAR
  🔴 NEW SELL signals : DOGE

------------------------------------------------------------
  COIN     PRICE   SUPERTREND DIR       SIGNAL  VS ST%
------------------------------------------------------------
  BTC    72345.00  71500.00  🟢 BULLISH ⬆️ HOLD   +1.18%
  ETH    3488.40   3450.20   🟢 BULLISH ⬆️ HOLD   +1.10%
  SOL    145.67    146.29    🔴 BEARISH ⬇️ SELL  -0.42%
  ...
```

### JSON (`--output json`)

```json
{
  "generated_at": "2026-05-11T06:00:00+00:00",
  "settings": {
    "atr_period": 10,
    "multiplier": 3.0,
    "interval": "1d"
  },
  "summary": {
    "total": 20,
    "bullish": 14,
    "bearish": 6,
    "buy_signals": ["SOL", "NEAR"],
    "sell_signals": ["DOGE"]
  },
  "coins": [
    {
      "symbol": "SOL",
      "price": 145.67,
      "supertrend": 146.29,
      "direction": "BEARISH",
      "signal": "SELL",
      "price_vs_st_pct": -0.42,
      "atr": 5.82,
      "candle_date": "2026-05-10"
    }
  ],
  "errors": []
}
```

**Signal field:**
- `BUY` — price crossed **above** Supertrend today (fresh bullish reversal)
- `SELL` — price crossed **below** Supertrend today (fresh bearish reversal)
- `HOLD` — no crossover; trend continued

---

## Scheduling (Daily Morning Briefing)

### Cron (Linux/macOS)

```bash
# Edit crontab
crontab -e

# Run daily at 06:00 UTC, save JSON report with date stamp
0 6 * * * cd /path/to/project && .venv/bin/python scripts/crypto_supertrend.py \
  --output json > reports/supertrend_$(date +\%Y\%m\%d).json 2>&1
```

### systemd Timer (Linux)

Create two files:

`/usr/local/lib/systemd/system/crypto-supertrend.service`:
```ini
[Unit]
Description=Crypto Supertrend Daily Scan
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
WorkingDirectory=/path/to/project
ExecStart=/path/to/project/.venv/bin/python scripts/crypto_supertrend.py --output json
StandardOutput=append:/path/to/project/logs/supertrend_cron.log
StandardError=append:/path/to/project/logs/supertrend_error.log
```

`/usr/local/lib/systemd/system/crypto-supertrend.timer`:
```ini
[Unit]
Description=Daily Crypto Supertrend Scan at 06:00 UTC

[Timer]
OnCalendar=*-*-* 06:00:00
Persistent=true
TimeZone=UTC

[Install]
WantedBy=timers.target
```

Enable:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now crypto-supertrend.timer
```

---

## How Supertrend Works (Brief)

1. **True Range (TR)** = max(high−low, |high−prev_close|, |low−prev_close|)
2. **ATR** = Wilder's exponential moving average of TR over `atr_period` candles
3. **Bands**:
   - Upper band = `(high + low)/2 + multiplier × ATR`
   - Lower band = `(high + low)/2 − multiplier × ATR`
4. **Trend direction**:
   - If close > Supertrend → **bullish** (Supertrend = lower band)
   - If close < Supertrend → **bearish** (Supertrend = upper band)
5. **Signal**: Direction change between today and yesterday produces BUY/SELL

Recommended defaults: **ATR=10, multiplier=3.0** for daily candles.
For scalping (1h): try **ATR=5–7, multiplier=2.0–2.5**.

---

## Watchlist Management

### Temporarily (CLI)

```bash
# Only top 5
python scripts/crypto_supertrend.py --symbols BTCUSDT ETHUSDT SOLUSDT BNBUSDT AVAXUSDT

# Focus on DeFi tokens
python scripts/crypto_supertrend.py --symbols UNIUSDT AAVEUSDT COMPUSDT CRVUSDT
```

### Permanently (edit defaults)

Open `scripts/crypto_supertrend.py` and edit `DEFAULT_SYMBOLS` list.

---

## Integration with TradingWebhook

You can feed Supertrend signals directly into the webhook:

```bash
# Generate JSON, then POST each fresh signal to the test endpoint
python scripts/crypto_supertrend.py --output json | \
  jq -c '.coins[] | select(.signal != "HOLD")' | \
  while read -r coin; do
    symbol=$(echo "$coin" | jq -r '.symbol')
    action=$(echo "$coin" | jq -r '.signal | ascii_downcase')  # buy or sell
    price=$(echo "$coin" | jq -r '.price')
    curl -X POST http://localhost:8000/webhook/test \
      -H "Content-Type: application/json" \
      -d "{\"ticker\":\"$symbol\",\"action\":\"$action\",\"quantity\":0.1,\"price\":$price}"
  done
```

For full automation, add the above pipeline to your daily cron after the scan.

---

## Dependencies

Install once:
```bash
pip install requests pandas numpy
```

No API key required — uses Binance public `/api/v3/klines` endpoint.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `403 Forbidden` | IP blocked / geo-restricted | Use VPN or switch to another exchange API |
| Empty `coins` array | Invalid symbol or network issue | Verify symbols on binance.com; check connectivity |
| All signals = HOLD | Strong trend; no fresh crossovers | Reduce multiplier (2.5) or check shorter timeframe |
| Too many BUY/SELL | Multiplier too low | Increase multiplier to 3.5–4.0 for fewer signals |
| Timezone confusion | Cron uses server TZ | Add `TZ=UTC` to crontab or use `--timezone` flag if added |

---

## Advanced: Adding New Exchanges

The script currently uses Binance public API. To add Coinbase, Kraken, or Bybit:

1. Add exchange client in `fetch_ohlcv()` function
2. Normalize symbol format (e.g., `BTC-USDT` vs `BTCUSDT`)
3. Adjust rate-limit handling (Binance allows 1200 req/min without key)

Pull requests welcome.

---

## Files

| Path | Description |
|---|---|
| `scripts/crypto_supertrend.py` | Main script |
| `skill/CryptoSupertrend.md` | This skill definition |
| `docs/scheduling/DAILY_SCHEDULE.md` | Cron/systemd setup guide |
| `docs/supertrend/` | Historical briefings (auto-generated) |
