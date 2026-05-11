#!/usr/bin/env python3
"""
Update docs/supertrend/daily_supertrend.txt with live Supertrend scan results.

This is the "current" daily report (non-timestamped). For historical archives
with timestamps, use scripts/generate_daily_supertrend.py.
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add scripts dir to path for direct import
SCRIPTS_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPTS_DIR))

from crypto_supertrend import run_scan, DEFAULT_SYMBOLS, DEFAULT_ATR_PERIOD, DEFAULT_MULTIPLIER, DEFAULT_INTERVAL


def format_text_report(report: dict, analysis_time: str) -> str:
    """Format report into text matching the original daily_supertrend.txt style."""
    lines = []
    lines.append(f"Daily Supertrend Analysis - {analysis_time}")
    lines.append("Supertrend Settings: ATR Length=10, Multiplier=3.0")
    lines.append("Timeframes: 15m (primary), 1h, 4h (confirmation)")
    lines.append("=" * 60)
    lines.append("")

    # Sort by absolute deviation descending (most extreme moves first)
    coins = sorted(report["coins"], key=lambda c: abs(c["price_vs_st_pct"]), reverse=True)

    for i, c in enumerate(coins, 1):
        dir_lower = "bullish" if c["direction"] == "BULLISH" else "bearish"
        trend_dur = f"{c['trend_duration_hours']} hours" if c.get("trend_duration_hours") is not None else "--"
        vol_conf = c.get("volume_confirmation", False)
        confidence = c.get("confidence", "medium")
        profit_pct = abs(c["price_vs_st_pct"])

        lines.append(f"{i}. {c['symbol']}")
        lines.append(f"   Direction: {c['direction']} ({dir_lower})")
        lines.append(f"   Signal Time: {c.get('signal_time', 'N/A')}")
        lines.append(f"   Profit After Signal: {profit_pct:.1f}%")
        lines.append(f"   Trend Duration: {trend_dur}")
        lines.append(f"   Supertrend Value: {c['supertrend']}")
        lines.append(f"   Current Price: {c['price']}")
        lines.append(f"   Price Change: {c['price_vs_st_pct']:.2f}%")
        lines.append(f"   Volume Confirmation: {vol_conf}")
        lines.append(f"   Confidence: {confidence}")
        lines.append(f"   Timestamp: {analysis_time}")
        lines.append("")

    lines.append("=" * 60)
    lines.append(f"Total coins scanned: {report['summary']['total']} | "
                 f"Bullish: {report['summary']['bullish']} | Bearish: {report['summary']['bearish']}")
    return "\n".join(lines)


def main():
    analysis_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    print(f"🔄 Updating current daily Supertrend report...", file=sys.stderr)
    report = run_scan(
        symbols=DEFAULT_SYMBOLS,
        interval=DEFAULT_INTERVAL,
        atr_period=DEFAULT_ATR_PERIOD,
        multiplier=DEFAULT_MULTIPLIER,
    )

    content = format_text_report(report, analysis_time)
    out_path = Path("docs/supertrend/daily_supertrend.txt")
    out_path.write_text(content)
    print(f"✓ {out_path} updated ({len(report['coins'])} coins)", file=sys.stderr)

    # Also update JSON
    json_path = Path("docs/supertrend/daily_supertrend.json")
    import json
    with json_path.open("w") as f:
        json.dump(report, f, indent=2)
    print(f"✓ {json_path} updated", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
