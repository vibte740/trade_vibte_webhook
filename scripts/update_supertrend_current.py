#!/usr/bin/env python3
"""
Generate a new Supertrend report with a filename that includes top bullish assets.

Each run creates a file like: supertrend_ASSET1_ASSET2_..._YYYY-MM-DD_HH-MM-SS.txt
and updates the 'supertrend_latest.txt' symlink.

Also creates a simple asset list file: supertrend_assets_YYYY-MM-DD.txt
containing just the bullish coin names (like supertrend_assetes.txt).
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add scripts dir to path
SCRIPTS_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPTS_DIR))

from crypto_supertrend import run_scan, DEFAULT_SYMBOLS, DEFAULT_ATR_PERIOD, DEFAULT_MULTIPLIER, DEFAULT_INTERVAL


def format_text_report(report: dict, analysis_time: str) -> str:
    """Format report into human-readable text."""
    lines = []
    lines.append(f"Supertrend Analysis - {analysis_time}")
    lines.append(f"Settings: ATR({DEFAULT_ATR_PERIOD}) × {DEFAULT_MULTIPLIER} | Interval: {DEFAULT_INTERVAL}")
    lines.append("=" * 62)
    lines.append("")

    # Sort by absolute deviation descending
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
        lines.append(f"   Supertrend: {c['supertrend']}")
        lines.append(f"   Price: {c['price']}")
        lines.append(f"   vs ST: {c['price_vs_st_pct']:+.2f}%")
        lines.append(f"   Volume Confirmed: {vol_conf}")
        lines.append(f"   Confidence: {confidence}")
        lines.append(f"   Timestamp: {analysis_time}")
        lines.append("")

    lines.append("=" * 62)
    lines.append(f"Scanned: {report['summary']['total']} | "
                 f"🟢 {report['summary']['bullish']} Bullish | 🔴 {report['summary']['bearish']} Bearish | "
                 f"BUY: {len(report['summary']['buy_signals'])} SELL: {len(report['summary']['sell_signals'])}")
    return "\n".join(lines)


def extract_bullish_symbols(report: dict, max_symbols: int = 5) -> list:
    """Return top bullish symbols by absolute price_vs_st_pct (positive only)."""
    bullish = [c for c in report["coins"] if c["direction"] == "BULLISH"]
    # Sort by price_vs_st_pct descending (most above Supertrend first)
    bullish.sort(key=lambda c: c["price_vs_st_pct"], reverse=True)
    return [c["symbol"] for c in bullish[:max_symbols]]


def main():
    now = datetime.now(timezone.utc)
    timestamp_str = now.strftime("%Y-%m-%d %H:%M:%S")
    filename_ts = now.strftime("%Y-%m-%d_%H-%M-%S")

    print(f"🔍 Generating Supertrend report…", file=sys.stderr)
    report = run_scan(
        symbols=DEFAULT_SYMBOLS,
        interval=DEFAULT_INTERVAL,
        atr_period=DEFAULT_ATR_PERIOD,
        multiplier=DEFAULT_MULTIPLIER,
    )

    # Prepare directories
    reports_dir = Path("docs/supertrend")
    reports_dir.mkdir(parents=True, exist_ok=True)

    # ── Asset-based filename (top bullish assets in name) ───────────────────────
    top_bullish = extract_bullish_symbols(report, max_symbols=5)
    if not top_bullish:
        asset_part = "NEUTRAL"
    else:
        asset_part = "_".join(top_bullish)

    # Full report with timestamp in content + asset-based filename
    content = format_text_report(report, timestamp_str)
    txt_filename = f"supertrend_{asset_part}_{filename_ts}.txt"
    txt_path = reports_dir / txt_filename
    txt_path.write_text(content)
    print(f"✓ Saved: {txt_path}", file=sys.stderr)

    # JSON sibling
    json_filename = f"supertrend_{asset_part}_{filename_ts}.json"
    json_path = reports_dir / json_filename
    import json
    with json_path.open("w") as f:
        json.dump(report, f, indent=2)
    print(f"✓ JSON: {json_path}", file=sys.stderr)

    # ── Update symlinks (point to the asset-named file) ─────────────────────────
    txt_link = reports_dir / "supertrend_latest.txt"
    json_link = reports_dir / "supertrend_latest.json"
    if txt_link.exists() or txt_link.is_symlink():
        txt_link.unlink()
    txt_link.symlink_to(txt_filename)
    if json_link.exists() or json_link.is_symlink():
        json_link.unlink()
    json_link.symlink_to(json_filename)
    print(f"✓ Symlinks updated → {txt_filename}", file=sys.stderr)

    # ── Also generate simple asset list file (for quick reference) ──────────────
    bullish_only = [c["symbol"] for c in report["coins"] if c["direction"] == "BULLISH"]
    bullish_only.sort(key=lambda s: s)
    asset_list_path = reports_dir / f"supertrend_assets_{now.strftime('%Y-%m-%d')}.txt"
    if bullish_only:
        asset_list_content = f"Bullish assets as of {timestamp_str} (UTC)\n\n" + "\n".join(bullish_only)
    else:
        asset_list_content = f"No bullish assets as of {timestamp_str} (UTC)"
    asset_list_path.write_text(asset_list_content)
    print(f"✓ Asset list: {asset_list_path}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
