# Scheduling Daily Supertrend Analysis

## Overview

The Supertrend analysis script (`scripts/update_supertrend_current.py`) generates a report of current crypto Supertrend signals. Each run creates a timestamped file (`supertrend_YYYY-MM-DD_HH-MM-SS.txt`) and updates the `supertrend_latest.txt` symlink.

---

## Prerequisites

No external dependencies beyond core project requirements. Uses Binance public REST API (no API key needed).

---

## Manual Execution

```bash
cd /Users/zuzzuu/vibte/trade_vibte_webhook
.venv/bin/python scripts/update_supertrend_current.py
```

Output example:
```
🔍 Generating Supertrend report…
✓ Saved: docs/supertrend/supertrend_2026-05-11_13-58-15.txt
✓ Linked: supertrend_latest.txt → supertrend_2026-05-11_13-58-15.txt
✓ JSON: docs/supertrend/supertrend_2026-05-11_13-58-15.json
```

---

## Automated Scheduling (Cron)

Run daily at 06:00 UTC:

```bash
crontab -e

# Add line:
0 6 * * * cd /Users/zuzzuu/vibte/trade_vibte_webhook && .venv/bin/python scripts/update_supertrend_current.py >> /Users/zuzzuu/vibte/trade_vibte_webhook/logs/supertrend_cron.log 2>&1
```

---

## Automated Scheduling (systemd Timer)

**Service** — `/usr/local/lib/systemd/system/supertrend-analysis.service`:
```ini
[Unit]
Description=Daily Supertrend Crypto Analysis
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
WorkingDirectory=/Users/zuzzuu/vibte/trade_vibte_webhook
ExecStart=/Users/zuzzuu/vibte/trade_vibte_webhook/.venv/bin/python scripts/update_supertrend_current.py
StandardOutput=append:/Users/zuzzuu/vibte/trade_vibte_webhook/logs/supertrend.log
StandardError=append:/Users/zuzzuu/vibte/trade_vibte_webhook/logs/supertrend_error.log
```

**Timer** — `/usr/local/lib/systemd/system/supertrend-analysis.timer`:
```ini
[Unit]
Description=Run Supertrend analysis daily at 06:00 UTC

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
sudo systemctl enable --now supertrend-analysis.timer
```

---

## Output Files

| File | Description |
|---|---|
| `docs/supertrend/supertrend_YYYY-MM-DD_HH-MM-SS.txt` | Timestamped text report (immutable) |
| `docs/supertrend/supertrend_YYYY-MM-DD_HH-MM-SS.json` | companion JSON |
| `docs/supertrend/supertrend_latest.txt` | Symlink → most recent `.txt` |
| `docs/supertrend/supertrend_latest.json` | Symlink → most recent `.json` |

---

## Troubleshooting

| Issue | Fix |
|---|---|
| No output file | Check `logs/supertrend_cron.log` or `journalctl -u supertrend-analysis.service` |
| Stale `latest` symlink | Script failed mid-run; check file write permissions on `docs/supertrend/` |
| Empty `coins` list | Network issue; verify Binance API accessibility |

