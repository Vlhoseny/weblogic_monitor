# WebLogic Health Monitor

A WLST (WebLogic Scripting Tool) script that connects to your local WebLogic Admin Server, collects runtime metrics from all managed servers, and emails a formatted HTML health dashboard.

## What It Does

| Metric | Source |
|--------|--------|
| Server state (RUNNING/SHUTDOWN/FAILED) | `ServerRuntimes` MBean |
| Health state (OK/WARN/CRITICAL) | `HealthState` MBean |
| Free JVM heap % | `JVMRuntime` MBean |
| Hostname & timestamp | Local system |

Results are sent as an HTML email via Gmail SMTP and saved locally to `%TEMP%\weblogic_report_*.html`.

## Prerequisites

- Oracle WebLogic Server 12c+ (QuickStart or Full install)
- A Gmail account with an [App Password](https://support.google.com/accounts/answer/185833) (requires 2-Step Verification enabled)
- Python is **not** required — the script runs inside WLST (Jython 2.7)

## Setup

### 1. Clone or download

```bash
git clone https://github.com/Vlhoseny/weblogic_monitor.git
cd weblogic_monitor
```

### 2. Configure credentials

Copy the example environment file and edit it with your credentials:

```cmd
copy .env.example .env
```

Fill in your `.env` file:

```ini
WL_ADMIN_PASS=weblogic1                    # WebLogic admin password
WL_SMTP_USER=your.email@gmail.com          # Gmail address
WL_SMTP_PASS=xxxx xxxx xxxx xxxx           # Gmail App Password (16 chars with spaces)
WL_EMAIL_FROM=your.email@gmail.com         # Sender address
WL_EMAIL_TO=recipient@example.com          # Comma-separated recipients
```

### 3. Get a Gmail App Password

1. Go to https://myaccount.google.com/security
2. Enable **2-Step Verification** (if not already on)
3. Go to **App Passwords** (search in Google Account settings)
4. Select **Mail** + **Windows Computer** and generate
5. Copy the 16-character password (spaces included) into `WL_SMTP_PASS`

## Usage

Open a **Command Prompt** (cmd.exe) — not PowerShell — and run:

```cmd
set USER_MEM_ARGS=-Xms256m -Xmx1024m
"C:\Oracle\Middleware\Oracle_Home\oracle_common\common\bin\wlst.cmd" weblogic_monitor.py
```

On first run, WLST will show:

```
WebLogic Health Monitor
 Target : t3://127.0.0.1:7101
 Host   : 0x
 Time   : 2026-06-25 00:43:47
============================================================
Server                   State        Health     FreeHeap%
------------------------------------------------------------
DefaultServer            RUNNING      OK         16.4%
------------------------------------------------------------
OK: Report saved to C:\Users\...\weblogic_report_*.html
OK: Email sent to YOUR-EMAIL@mail.com
```

## Scheduling (Optional)

To run daily via Windows Task Scheduler:

1. Open **Task Scheduler** → **Create Basic Task**
2. Trigger: **Daily** at your preferred time
3. Action: **Start a program**
   - Program: `C:\Windows\System32\cmd.exe`
   - Arguments: `/c "set USER_MEM_ARGS=-Xms256m -Xmx1024m && C:\Oracle\Middleware\Oracle_Home\oracle_common\common\bin\wlst.cmd C:\path\to\weblogic_monitor.py"`
   - Start in: `C:\path\to\weblogic-monitor`

## Project Structure

```
weblogic-monitor/
├── weblogic_monitor.py   # Main WLST script
├── .env                  # Credentials (gitignored — never commit)
├── .env.example          # Template for .env
├── .gitignore
└── README.md
```

## Security Notes

- **Never commit `.env`** — it contains passwords and is already in `.gitignore`
- The script reads all secrets from environment variables or a local `.env` file
- For production, use WebLogic `UserConfigFile`/`UserKeyFile` instead of plaintext passwords

## Environment Variables Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `WL_ADMIN_URL` | `t3://127.0.0.1:7101` | Admin Server URL |
| `WL_ADMIN_USER` | `weblogic` | Admin username |
| `WL_ADMIN_PASS` | *(empty)* | Admin password |
| `WL_SMTP_HOST` | `smtp.gmail.com` | SMTP server |
| `WL_SMTP_PORT` | `587` | SMTP port |
| `WL_SMTP_USER` | *(empty)* | Gmail address |
| `WL_SMTP_PASS` | *(empty)* | Gmail App Password |
| `WL_SMTP_USE_TLS` | `true` | Enable STARTTLS |
| `WL_EMAIL_FROM` | *(empty)* | Sender address |
| `WL_EMAIL_TO` | *(empty)* | Recipients (comma-separated) |
