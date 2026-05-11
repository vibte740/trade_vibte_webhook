# Supertrend Analysis Reports

This directory contains automatically generated Supertrend analysis reports for cryptocurrency pairs.

## File Naming

Reports use **asset-based filenames** that include the top bullish symbols:

```
supertrend_ASSET1_ASSET2_..._YYYY-MM-DD_HH-MM-SS.txt
```

Example: `supertrend_SOL_BTC_ETH_2026-05-11_23-09-03.txt`

If no bullish assets are found, the file is named `supertrend_NEUTRAL_YYYY-MM-DD_HH-MM-SS.txt`.

**Symlinks:**
- `supertrend_latest.txt` → most recent `.txt` report
- `supertrend_latest.json` → most recent `.json` data
- `supertrend_assets_YYYY-MM-DD.txt` → plain list of bullish symbols for that day

## Generation

```bash
make supertrend-assets
# or
.venv/bin/python scripts/update_supertrend_current.py
```

## Report Content

Each full report includes:
- Generation timestamp
- Settings: ATR period, multiplier, timeframe
- Full coin table sorted by absolute deviation from Supertrend
- Direction (BULLISH/BEARISH), latest signal (BUY/SELL/HOLD), signal time
- Price vs Supertrend %, ATR, trend duration, volume confirmation, confidence

The companion JSON (`supertrend_*.json`) contains the same data in machine-readable form.

The daily asset list (`supertrend_assets_YYYY-MM-DD.txt`) contains just the bullish symbol names, one per line, for quick consumption by other tools.

## Methodology

See `skill/Supertrend.md` or `skill/CryptoSupertrend.md` for the complete strategy logic and confidence scoring algorithm.
