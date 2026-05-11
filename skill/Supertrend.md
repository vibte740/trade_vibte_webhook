# Skill: Find Profitable Supertrend Signals (Last 24h Crypto)

## Objective
Detect crypto pairs where the Supertrend indicator generated profitable trends during the last 24 hours.

---

# Strategy Overview

The AI agent scans crypto pairs and evaluates:

- Supertrend direction
- Trend duration
- Price movement after signal
- Volume confirmation
- Profitability over last 24h

Goal:
- Find coins with strong sustained trends
- Avoid fake breakouts and sideways markets

---

# Indicator Setup

## Supertrend Configuration

Recommended Default Settings:

| Setting | Value |
|---|---|
| ATR Length | 10 |
| Multiplier | 3.0 |

---

# Timeframes

## Primary Timeframe
- 15m

## Confirmation Timeframes
- 1h
- 4h

---

# Signal Logic

## Bullish Signal

Conditions:
- Supertrend flips from red → green
- Candle closes above Supertrend line
- Volume increases
- Price maintains trend for multiple candles

Result:
- Long candidate

---

## Bearish Signal

Conditions:
- Supertrend flips from green → red
- Candle closes below Supertrend line
- Selling volume increases

Result:
- Short candidate

---

# Profitability Detection Logic

## Evaluate Last 24 Hours

For each crypto pair:

1. Detect latest Supertrend flip
2. Measure move after signal
3. Calculate:
   - Maximum favorable move
   - Drawdown
   - Trend duration

---

## Example Profitability Rules

### Strong Bullish Trend
Requirements:
- Trend duration > 4 hours
- Gain after signal > 3%
- No major reversal
- Volume confirmation exists

### Strong Bearish Trend
Requirements:
- Downtrend duration > 4 hours
- Drop after signal > 3%
- Selling pressure confirmed

---

# AI Agent Filtering

## Ignore Assets If
- Sideways movement
- Low volume
- Multiple fake flips
- ATR too small
- Trend already exhausted

---

# Confidence Scoring

| Condition | Score |
|---|---|
| Supertrend alignment | +3 |
| High volume | +2 |
| Strong momentum | +2 |
| Multi-timeframe confirmation | +3 |

---

# Confidence Levels

| Total Score | Confidence |
|---|---|
| 8–10 | High |
| 5–7 | Medium |
| Below 5 | Low |

---

# Best Market Conditions

Supertrend works best in:
- Trending markets
- High momentum breakouts
- Strong directional moves

Performs poorly in:
- Choppy markets
- Range-bound markets
- Low volatility periods

---

# Recommended Crypto Pairs

Prefer:
- BTCUSDT
- ETHUSDT
- SOLUSDT
- BNBUSDT
- High-volume perpetual pairs

Avoid:
- Illiquid altcoins
- Newly listed tokens

---

# Example AI Workflow

1. Scan top 100 crypto pairs
2. Detect Supertrend flips
3. Measure profitability over last 24h
4. Rank by:
   - Profit %
   - Trend strength
   - Volume
5. Return top opportunities

---

# Example Output

```json
{
  "timestamp": "2026-05-11 15:00",
  "best_supertrend_trades": [
    {
      "symbol": "SOLUSDT",
      "direction": "LONG",
      "signal_time": "2026-05-10 18:00",
      "profit_after_signal": "8.4%",
      "trend_duration_hours": 9,
      "volume_confirmation": true,
      "confidence": "high"
    },
    {
      "symbol": "BTCUSDT",
      "direction": "SHORT",
      "profit_after_signal": "4.1%",
      "trend_duration_hours": 6,
      "confidence": "medium"
    }
  ],
  "market_condition": "trending"
}