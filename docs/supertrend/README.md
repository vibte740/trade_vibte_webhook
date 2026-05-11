# Supertrend Daily Analysis Reports

This directory contains automatically generated daily Supertrend analysis reports for cryptocurrency pairs.

## File Naming

Reports are saved with timestamps:
```
daily_supertrend_YYYY-MM-DD_HH-MM-SS.txt
```

Example: `daily_supertrend_2026-05-11_12-31-17.txt`

**Symlink:** `daily_supertrend_latest.txt` always points to the most recent report.

## Generation

Reports are generated automatically by the scheduled job defined in [DAILY_SCHEDULE.md](../../docs/scheduling/DAILY_SCHEDULE.md).

### Manual generation:
```bash
make supertrend
# or
.venv/bin/python scripts/generate_daily_supertrend.py
```

## Report Format

Each report includes:
- Generation timestamp
- Supertrend parameters (ATR length = 10, multiplier = 3.0)
- Top 10 profitable signals from the last 24 hours
- Trend direction, duration, profit %, volume confirmation, confidence level

## Archive

Old reports are retained indefinitely in this directory for historical analysis.

## Methodology

See `skill/Supertrend.md` for the complete strategy logic and confidence scoring.
