# Scheduling Daily Supertrend Analysis

## Overview

The Supertrend analysis script (`scripts/generate_daily_supertrend.py`) generates a daily report of profitable crypto trading signals based on the Supertrend indicator. The report is saved to `docs/supertrend/` with a timestamped filename.

---

## Prerequisites

Install optional dependencies for live market data:

```bash
pip install ccxt  # or: pip install -r requirements-analysis.txt
```

The script falls back to synthetic demo data if `ccxt` is unavailable.

---

## Manual Execution

Run the script manually:

```bash
cd /Users/zuzzuu/vibte/trade_vibte_webhook
.venv/bin/python scripts/generate_daily_supertrend.py
```

Output:
```
✓ Report saved to: docs/supertrend/daily_supertrend_2026-05-11_15-40-22.txt
✓ Updated symlink: daily_supertrend_latest.txt
✅ Daily Supertrend analysis complete. 8 opportunities found.
```

---

## Automated Scheduling (Cron)

Add a cron job to run daily at a specific time (e.g., 00:30 UTC after daily candle close):

```bash
# Edit crontab
crontab -e

# Add this line (adjust paths and timezone as needed):
30 0 * * * cd /Users/zuzzuu/vibte/trade_vibte_webhook && .venv/bin/python scripts/generate_daily_supertrend.py >> /Users/zuzzuu/vibte/trade_vibte_webhook/logs/cron_supertrend.log 2>&1
```

**Notes:**
- Ensure virtualenv path is correct (`.venv/bin/python`)
- Logs are appended to `logs/cron_supertrend.log` (create the `logs/` directory if needed)
- Cron uses system timezone; adjust hour field if you want a different local time

---

## Automated Scheduling (systemd Timer)

For Linux/macOS with systemd, create a timer unit:

**Service file** — `/usr/local/lib/systemd/system/supertrend-analysis.service`:
```ini
[Unit]
Description=Daily Supertrend Crypto Analysis
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
WorkingDirectory=/Users/zuzzuu/vibte/trade_vibte_webhook
ExecStart=/Users/zuzzuu/vibte/trade_vibte_webhook/.venv/bin/python scripts/generate_daily_supertrend.py
StandardOutput=append:/Users/zuzzuu/vibte/trade_vibte_webhook/logs/supertrend.log
StandardError=append:/Users/zuzzuu/vibte/trade_vibte_webhook/logs/supertrend_error.log
```

**Timer file** — `/usr/local/lib/systemd/system/supertrend-analysis.timer`:
```ini
[Unit]
Description=Run Supertrend analysis daily at 00:30

[Timer]
OnCalendar=*-*-* 00:30:00
Persistent=true

[Install]
WantedBy=timers.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now supertrend-analysis.timer
sudo systemctl status supertrend-analysis.timer
```

---

## Output File Naming Convention

Reports are saved as:

```
docs/supertrend/daily_supertrend_YYYY-MM-DD_HH-MM-SS.txt
```

Example:
- `daily_supertrend_2026-05-11_15-40-22.txt`

A symlink `daily_supertrend_latest.txt` always points to the most recent report.

---

## Report Content

Each report includes:
- Timestamp of generation
- Supertrend settings (ATR length, multiplier)
- Top 10 profitable signals from the last 24h with:
  - Symbol and direction (LONG/SHORT)
  - Signal flip time
  - Profit percentage after signal
  - Trend duration (hours)
  - Supertrend value
  - Current price
  - Volume confirmation
  - Confidence level (high/medium/low)

See `skill/Supertrend.md` for full methodology.

---

## Email / Notification Integration (Optional)

To email the report after generation, add to the end of `generate_daily_supertrend.py` or wrap the script:

```python
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def email_report(report_path: Path):
    # Configure your SMTP settings
    smtp_server = "smtp.gmail.com"
    smtp_port = 587
    sender = "alerts@yourdomain.com"
    receiver = "you@domain.com"
    password = "YOUR_APP_PASSWORD"

    msg = MIMEMultipart()
    msg['Subject'] = f"Daily Supertrend Analysis — {datetime.now().strftime('%Y-%m-%d')}"
    msg['From'] = sender
    msg['To'] = receiver

    with open(report_path) as f:
        body = f.read()
    msg.attach(MIMEText(body, 'plain'))

    with smtplib.SMTP(smtp_server, smtp_port) as server:
        server.starttls()
        server.login(sender, password)
        server.send_message(msg)
    print(f"✓ Report emailed to {receiver}")
```

Then call `email_report(filepath)` in `main()` after saving.

---

## Schedule Alternatives

| Tool | Best for | Notes |
|---|---|---|
| **cron** | Unix-like servers, simplicity | Widely available, no extra deps |
| **systemd timer** | Modern Linux with systemd | Better logging, dependency control |
| **`schedule` Python lib** | In-process, portable | Requires long-running daemon |
| **Airflow / Prefect** | Complex DAGs, monitoring | Overkill for single daily task |

---

## Troubleshooting

**Report not generated:**
- Check `logs/cron_supertrend.log` or systemd journal: `journalctl -u supertrend-analysis.service`
- Verify virtualenv path and script permissions (`chmod +x`)
- Ensure network connectivity if using live data (`ccxt`)

**Old report remains in `latest` symlink:**
- Script may have failed before symlink creation; check file write permissions on `docs/supertrend/`

**Data quality issues:**
- If using synthetic data, switch to live data by setting `use_live = True` in `generate_daily_supertrend.py` and installing `ccxt`
