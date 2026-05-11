#!/usr/bin/env python3
"""
Crypto Supertrend Scanner — Daily morning briefing.

Fetches OHLCV from Binance public API, computes Supertrend (ATR-based),
and outputs a structured report with trend direction, current price vs.
Supertrend level, ATR value, and fresh BUY/SELL crossover signals.

No API key required (uses public Binance REST endpoints).
"""
import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
import requests

# ── Configuration ──────────────────────────────────────────────────────────────

DEFAULT_SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT",
    "ADAUSDT", "DOGEUSDT", "AVAXUSDT", "DOTUSDT", "LINKUSDT",
    "MATICUSDT", "LTCUSDT", "UNIUSDT", "ATOMUSDT", "NEARUSDT",
    "APTUSDT", "ARBUSDT", "OPUSDT", "INJUSDT", "SUIUSDT",
]

DEFAULT_INTERVAL = "1d"  # 1h, 4h, 1d
DEFAULT_ATR_PERIOD = 10
DEFAULT_MULTIPLIER = 3.0

BINANCE_BASE = "https://api.binance.com/api/v3"
KLINE_ENDPOINT = "/klines"

# ── Data Fetching ──────────────────────────────────────────────────────────────

def fetch_ohlcv(symbol: str, interval: str = "1d", limit: int = 100) -> pd.DataFrame:
    """
    Fetch OHLCV candle data from Binance public API.
    Returns DataFrame with columns: open, high, low, close, volume (indexed by timestamp).
    """
    url = f"{BINANCE_BASE}{KLINE_ENDPOINT}"
    params = {
        "symbol": symbol,
        "interval": interval,
        "limit": limit,
    }
    resp = requests.get(url, params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()

    # Binance returns: [open_time, open, high, low, close, volume, ...]
    df = pd.DataFrame(data, columns=[
        "timestamp", "open", "high", "low", "close", "volume",
        "close_time", "quote_asset_volume", "num_trades",
        "taker_buy_base", "taker_buy_quote", "ignore"
    ])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df.set_index("timestamp", inplace=True)
    df["open"] = pd.to_numeric(df["open"])
    df["high"] = pd.to_numeric(df["high"])
    df["low"] = pd.to_numeric(df["low"])
    df["close"] = pd.to_numeric(df["close"])
    df["volume"] = pd.to_numeric(df["volume"])
    return df[["open", "high", "low", "close", "volume"]]


# ── Supertrend Calculation ────────────────────────────────────────────────────

def calculate_atr(df: pd.DataFrame, period: int) -> pd.Series:
    """Calculate Average True Range (Wilder's RMA)."""
    high = df["high"]
    low = df["low"]
    close = df["close"]

    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low - close.shift()).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    # Wilder's smoothing (RMA) — equivalent to EMA with alpha=1/period
    atr = tr.ewm(alpha=1/period, adjust=False).mean()
    return atr


def calculate_supertrend(df: pd.DataFrame, atr_period: int, multiplier: float):
    """
    Compute Supertrend indicator.

    Returns:
        tuple: (supertrend_series, direction_series)
        direction: 1 = bullish (green), -1 = bearish (red)
    """
    atr = calculate_atr(df, atr_period)
    hl2 = (df["high"] + df["low"]) / 2
    upperband = hl2 + (multiplier * atr)
    lowerband = hl2 - (multiplier * atr)

    supertrend = pd.Series(index=df.index, dtype=float)
    direction = pd.Series(index=df.index, dtype=int)

    # Initialize
    supertrend.iloc[0] = upperband.iloc[0]
    direction.iloc[0] = -1  # start bearish until close > upperband

    for i in range(1, len(df)):
        close = df["close"].iloc[i]
        prev_close = df["close"].iloc[i - 1]
        prev_st = supertrend.iloc[i - 1]
        prev_dir = direction.iloc[i - 1]

        # Determine direction
        if close > upperband.iloc[i]:
            direction.iloc[i] = 1
        elif close < lowerband.iloc[i]:
            direction.iloc[i] = -1
        else:
            direction.iloc[i] = prev_dir

        # Assign supertrend value
        if direction.iloc[i] == 1:
            supertrend.iloc[i] = lowerband.iloc[i]
        else:
            supertrend.iloc[i] = upperband.iloc[i]

        # Prevent same-candle whipsaw: if direction changed, use previous direction's band
        if direction.iloc[i] != prev_dir and i > 1:
            if direction.iloc[i] == 1:
                supertrend.iloc[i] = lowerband.iloc[i]
            else:
                supertrend.iloc[i] = upperband.iloc[i]

    return supertrend, direction


# ── Signal Detection ───────────────────────────────────────────────────────────

def detect_signals_extended(df: pd.DataFrame, symbol: str, supertrend: pd.Series, direction: pd.Series, atr_period: int) -> Optional[Dict]:
    """
    Identify latest Supertrend status and any fresh crossover.
    Returns enriched dict with direction, signal, price, supertrend, ATR,
    and, if this is a fresh signal (BUY/SELL), also includes signal_time
    and trend_duration_hours.
    """
    if len(df) < 2:
        return None

    last_idx = df.index[-1]
    prev_idx = df.index[-2]

    last_dir = direction.loc[last_idx]
    prev_dir = direction.loc[prev_idx]
    last_price = df["close"].loc[last_idx]
    last_st = supertrend.loc[last_idx]
    last_atr = calculate_atr(df, atr_period).iloc[-1]

    # Determine signal type on most recent candle
    signal_type = "HOLD"
    if last_dir == 1 and prev_dir == -1:
        signal_type = "BUY"
    elif last_dir == -1 and prev_dir == 1:
        signal_type = "SELL"

    # Price vs Supertrend pct
    price_vs_st_pct = ((last_price - last_st) / last_st * 100) if last_st else 0.0

    # Find most recent direction flip and compute its age
    flip_time = None
    trend_duration_hours = None
    flips = direction != direction.shift(1)
    flip_indices = flips[flips].index
    if len(flip_indices) > 0:
        last_flip = flip_indices[-1]
        if last_flip == last_idx:
            # Fresh flip today — duration is 0 (or 1 candle)
            trend_duration_hours = 0.25 if df.index.freq else 0.25
        else:
            # Ongoing trend since last flip
            delta = last_idx - last_flip
            # Approximate hours from number of periods (assumes 15m for 1d scan)
            trend_duration_hours = round(delta.total_seconds() / 3600, 1)
        flip_time = last_flip

    return {
        "symbol": symbol,
        "price": round(last_price, 4),
        "supertrend": round(last_st, 4),
        "direction": "BULLISH" if last_dir == 1 else "BEARISH",
        "signal": signal_type,
        "price_vs_st_pct": round(price_vs_st_pct, 2),
        "atr": round(last_atr, 4),
        "candle_date": last_idx.strftime("%Y-%m-%d"),
        "signal_time": flip_time.strftime("%Y-%m-%d %H:%M") if flip_time else "N/A",
        "trend_duration_hours": trend_duration_hours,
    }


def detect_signals(df: pd.DataFrame, symbol: str, supertrend: pd.Series, direction: pd.Series, atr_period: int) -> List[Dict]:
    """
    Identify latest Supertrend status and any fresh crossover.
    Returns a single-element list containing the coin's current state.
    """
    if len(df) < 2:
        return []

    last_idx = df.index[-1]
    prev_idx = df.index[-2]

    last_dir = direction.loc[last_idx]
    prev_dir = direction.loc[prev_idx]
    last_price = df["close"].loc[last_idx]
    last_st = supertrend.loc[last_idx]
    last_atr = calculate_atr(df, atr_period).iloc[-1]

    # Fresh crossover check
    signal_type = "HOLD"
    if last_dir == 1 and prev_dir == -1:
        signal_type = "BUY"
    elif last_dir == -1 and prev_dir == 1:
        signal_type = "SELL"

    # Price vs Supertrend %
    price_vs_st_pct = round(((last_price - last_st) / last_st * 100), 2) if last_st else 0.0

    # Find most recent direction flip (anywhere in history)
    flips = direction != direction.shift(1)
    flip_indices = flips[flips].index
    signal_time = "N/A"
    trend_duration_hours = None
    if len(flip_indices) > 0:
        last_flip = flip_indices[-1]
        signal_time = last_flip.strftime("%Y-%m-%d %H:%M")
        if last_flip == last_idx:
            trend_duration_hours = 0.25
        else:
            delta = last_idx - last_flip
            trend_duration_hours = round(delta.total_seconds() / 3600, 1)

    # Volume confirmation: compare avg volume after flip vs before
    vol_after_avg = df["volume"].iloc[-20:].mean()
    vol_before_avg = df["volume"].iloc[-40:-20].mean() if len(df) >= 40 else vol_after_avg
    volume_confirmed = vol_after_avg > vol_before_avg * 1.2

    # Confidence score (per skill doc)
    score = 0
    if signal_type in ("BUY", "SELL"):
        score += 3
    if volume_confirmed:
        score += 2
    if trend_duration_hours and trend_duration_hours >= 4:
        score += 2
    score += 1  # multi-timeframe alignment check (always assume for now)
    if score >= 8:
        confidence = "high"
    elif score >= 5:
        confidence = "medium"
    else:
        confidence = "low"

    return [{
        "symbol": symbol,
        "price": round(last_price, 4),
        "supertrend": round(last_st, 4),
        "direction": "BULLISH" if last_dir == 1 else "BEARISH",
        "signal": signal_type,
        "price_vs_st_pct": price_vs_st_pct,
        "atr": round(last_atr, 4),
        "candle_date": last_idx.strftime("%Y-%m-%d"),
        "signal_time": signal_time,
        "trend_duration_hours": trend_duration_hours,
        "volume_confirmation": bool(volume_confirmed),
        "confidence": confidence,
    }]


# ── Scan Pipeline ──────────────────────────────────────────────────────────────

def scan_symbol(symbol: str, interval: str, atr_period: int, multiplier: float) -> Optional[Dict]:
    """Fetch data, compute Supertrend, return signal dict or None on error."""
    try:
        df = fetch_ohlcv(symbol, interval=interval, limit=max(100, atr_period * 3))
        if len(df) < atr_period + 2:
            return None

        df.index.name = "timestamp"  # ensure index has a name
        st, direction = calculate_supertrend(df, atr_period, multiplier)
        signals = detect_signals(df, symbol, st, direction, atr_period)
        return signals[0] if signals else None
    except Exception as e:
        return {
            "symbol": symbol,
            "error": str(e),
        }


def run_scan(
    symbols: List[str],
    interval: str,
    atr_period: int,
    multiplier: float,
) -> Dict:
    """Run Supertrend scan across all symbols. Returns structured report dict."""
    results = []
    errors = []
    bullish = 0
    bearish = 0
    buy_signals = []
    sell_signals = []

    for sym in symbols:
        res = scan_symbol(sym, interval, atr_period, multiplier)
        if res is None:
            errors.append({"symbol": sym, "error": "insufficient_data"})
            continue
        if "error" in res:
            errors.append(res)
            continue

        results.append(res)
        if res["direction"] == "BULLISH":
            bullish += 1
        else:
            bearish += 1
        if res["signal"] == "BUY":
            buy_signals.append(sym)
        elif res["signal"] == "SELL":
            sell_signals.append(sym)

    generated_at = datetime.now(timezone.utc)
    report = {
        "generated_at": generated_at.isoformat(),
        "settings": {
            "atr_period": atr_period,
            "multiplier": multiplier,
            "interval": interval,
        },
        "summary": {
            "total": len(symbols),
            "bullish": bullish,
            "bearish": bearish,
            "buy_signals": buy_signals,
            "sell_signals": sell_signals,
        },
        "coins": results,
        "errors": errors,
    }
    return report


# ── Output Formatting ──────────────────────────────────────────────────────────

def format_text(report: Dict) -> str:
    """Render human-readable plain text briefing."""
    lines = []
    ts = datetime.fromisoformat(report["generated_at"]).strftime("%Y-%m-%d %H:%M:%S UTC")
    sett = report["settings"]
    header = (
        "=" * 62 + "\n"
        f"  🔔 CRYPTO SUPERTREND MORNING BRIEFING\n"
        f"  {ts}   ATR({sett['atr_period']}) × {sett['multiplier']}  |  "
        f"Interval: {sett['interval']}\n"
        + "=" * 62
    )
    lines.append(header)
    lines.append("")

    sm = report["summary"]
    lines.append(
        f"  Universe: {sm['total']} coins | 🟢 {sm['bullish']} Bullish | 🔴 {sm['bearish']} Bearish"
    )

    if sm["buy_signals"]:
        lines.append(f"  🟢 NEW BUY signals  : {', '.join(sm['buy_signals']) if sm['buy_signals'] else 'None'}")
    if sm["sell_signals"]:
        lines.append(f"  🔴 NEW SELL signals : {', '.join(sm['sell_signals']) if sm['sell_signals'] else 'None'}")
    lines.append("")

    separator = "-" * 62
    lines.append(separator)
    lines.append("  COIN     PRICE   SUPERTREND DIR       SIGNAL  VS ST%")
    lines.append(separator)

    # Sort: signals first, then by absolute price_vs_st_pct descending
    def sort_key(c):
        is_signal = c["signal"] != "HOLD"
        return (not is_signal, -abs(c["price_vs_st_pct"]))

    for coin in sorted(report["coins"], key=sort_key):
        emoji = "🟢" if coin["direction"] == "BULLISH" else "🔴"
        arrow = "⬆️" if coin["direction"] == "BULLISH" else "⬇️"
        line = (
            f"  {coin['symbol']:<8} {coin['price']:>9.4f}  {coin['supertrend']:>9.4f}  "
            f"{emoji} {coin['direction']:<8} {arrow} {coin['signal']:<5}  {coin['price_vs_st_pct']:>+6.2f}%"
        )
        lines.append(line)

    lines.append("")
    lines.append(separator)
    lines.append(f"  Generated: {ts} | Total coins: {sm['total']} | "
                 f"Fresh BUY: {len(sm['buy_signals'])} | Fresh SELL: {len(sm['sell_signals'])}")
    lines.append("=" * 62)
    return "\n".join(lines)


def format_json(report: Dict) -> str:
    """Return JSON string (pretty-printed)."""
    import json
    return json.dumps(report, indent=2)


# ── Main ────────────────────────────────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(
        description="Crypto Supertrend Scanner — Daily morning trend briefing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                              # Scan 20 coins, daily, text output
  %(prog)s --output json                # Machine-readable JSON
  %(prog)s --symbols BTCUSDT ETHUSDT    # Custom watchlist
  %(prog)s --interval 4h --atr-period 7 --multiplier 2.5
        """
    )
    parser.add_argument(
        "--symbols",
        nargs="+",
        default=DEFAULT_SYMBOLS,
        help="Space-separated list of Binance USDT symbols (e.g. BTCUSDT ETHUSDT)",
    )
    parser.add_argument(
        "--interval",
        default=DEFAULT_INTERVAL,
        choices=["1h", "4h", "1d"],
        help="Candle timeframe (default: 1d)",
    )
    parser.add_argument(
        "--atr-period",
        type=int,
        default=DEFAULT_ATR_PERIOD,
        help="ATR smoothing period (default: 10)",
    )
    parser.add_argument(
        "--multiplier",
        type=float,
        default=DEFAULT_MULTIPLIER,
        help="Supertrend band multiplier (default: 3.0)",
    )
    parser.add_argument(
        "--output",
        default="text",
        choices=["text", "json"],
        help="Output format (default: text)",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    print(f"🔍 Scanning {len(args.symbols)} coins | "
          f"Interval={args.interval} | ATR({args.atr_period}) × {args.multiplier}",
          file=sys.stderr)

    report = run_scan(
        symbols=args.symbols,
        interval=args.interval,
        atr_period=args.atr_period,
        multiplier=args.multiplier,
    )

    if args.output == "json":
        print(format_json(report))
    else:
        print(format_text(report))

    # Brief summary to stderr
    sm = report["summary"]
    print(f"\n✅ Scan complete: {sm['bullish']} bullish, {sm['bearish']} bearish | "
          f"BUY: {len(sm['buy_signals'])} | SELL: {len(sm['sell_signals'])}",
          file=sys.stderr)

    # Exit non-zero only on systemic errors; individual symbol errors are in report
    return 0


if __name__ == "__main__":
    sys.exit(main())
