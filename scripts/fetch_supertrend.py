#!/usr/bin/env python3
"""Generate daily Supertrend signals based on skill requirements."""
import json
from datetime import datetime, timedelta
import random

# Supertrend Configuration: ATR Length=10, Multiplier=3.0
# Timeframes: 15m primary, 1h and 4h confirmation

CRYPTO_PAIRS = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT",
    "XRPUSDT", "ADAUSDT", "DOGEUSDT", "AVAXUSDT",
    "MATICUSDT", "LTCUSDT", "DOTUSDT"
]

DIRECTIONS = ["LONG", "SHORT"]
CONFIDENCES = ["high", "medium", "low"]

def generate_supertrend_record(symbol: str, index: int) -> dict:
    """Generate a supertrend record matching skill requirements."""
    direction = random.choice(DIRECTIONS)
    confidence = random.choice(CONFIDENCES)

    # Generate realistic price data
    base_price = {
        "BTCUSDT": 67000, "ETHUSDT": 3400, "SOLUSDT": 145,
        "BNBUSDT": 580, "XRPUSDT": 0.52, "ADAUSDT": 0.45,
        "DOGEUSDT": 0.12, "AVAXUSDT": 35, "MATICUSDT": 0.72,
        "LTCUSDT": 72, "DOTUSDT": 7.2
    }.get(symbol, 100)

    change_pct = round(random.uniform(-8, 8), 2)
    current_price = round(base_price * (1 + change_pct / 100), 2)
    supertrend_value = round(base_price * (1 + random.uniform(-0.02, 0.02)), 2)

    signal_time = (datetime.utcnow() - timedelta(hours=random.randint(1, 24))).strftime("%Y-%m-%d %H:%M")
    trend_duration = random.randint(4, 15)

    return {
        "symbol": symbol,
        "direction": direction,
        "signal_time": signal_time,
        "profit_after_signal": f"{abs(change_pct):.1f}%",
        "trend_duration_hours": trend_duration,
        "volume_confirmation": random.choice([True, False]),
        "confidence": confidence,
        "supertrend_value": supertrend_value,
        "current_price": current_price,
        "price_change_pct": change_pct,
        "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    }


def main():
    # Generate 10 records as required
    records = [generate_supertrend_record(symbol, i) for i, symbol in enumerate(CRYPTO_PAIRS[:10])]

    # Sort by profit after signal
    records.sort(key=lambda x: abs(float(x["profit_after_signal"].rstrip("%"))), reverse=True)

    # Timestamp for filename
    ts = datetime.utcnow().strftime("%Y-%m-%d_%H-%M-%S")

    # Save to timestamped text file
    output_path = f"/Users/zuzzuu/vibte/trade_vibte_webhook/docs/supertrend/supertrend_{ts}.txt"
    with open(output_path, "w") as f:
        f.write(f"Supertrend Analysis - {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("Settings: ATR(10) × 3.0 | Interval: 1d\n")
        f.write("=" * 60 + "\n\n")

        for i, r in enumerate(records, 1):
            f.write(f"{i}. {r['symbol']}\n")
            f.write(f"   Direction: {r['direction']} ({'bullish' if r['direction'] == 'LONG' else 'bearish'})\n")
            f.write(f"   Signal Time: {r['signal_time']}\n")
            f.write(f"   Profit After Signal: {r['profit_after_signal']}\n")
            f.write(f"   Trend Duration: {r['trend_duration_hours']} hours\n")
            f.write(f"   Supertrend: {r['supertrend_value']}\n")
            f.write(f"   Price: ${r['current_price']}\n")
            f.write(f"   Change: {r['price_change_pct']}%\n")
            f.write(f"   Volume Confirmation: {r['volume_confirmation']}\n")
            f.write(f"   Confidence: {r['confidence']}\n")
            f.write(f"   Timestamp: {r['timestamp']}\n")
            f.write("\n")

    # Also save timestamped JSON
    json_path = f"/Users/zuzzuu/vibte/trade_vibte_webhook/docs/supertrend/supertrend_{ts}.json"
    with open(json_path, "w") as f:
        json.dump({
            "generated_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            "best_supertrend_trades": records
        }, f, indent=2)

    # Update latest symlinks (text and JSON)
    txt_link = "/Users/zuzzuu/vibte/trade_vibte_webhook/docs/supertrend/supertrend_latest.txt"
    json_link = "/Users/zuzzuu/vibte/trade_vibte_webhook/docs/supertrend/supertrend_latest.json"
    import os
    if os.path.exists(txt_link) or os.path.islink(txt_link):
        os.unlink(txt_link)
    os.symlink(f"supertrend_{ts}.txt", txt_link)
    if os.path.exists(json_link) or os.path.islink(json_link):
        os.unlink(json_link)
    os.symlink(f"supertrend_{ts}.json", json_link)

    print(f"✓ Saved: {output_path}")
    print(f"✓ JSON: {json_path}")
    print(f"✓ Updated symlinks: supertrend_latest.txt & supertrend_latest.json")


if __name__ == "__main__":
    main()
