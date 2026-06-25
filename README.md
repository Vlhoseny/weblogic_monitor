# WebLogic Health Monitor

WLST-based daemon that collects full WebLogic domain health (servers, deployments, datasources, clusters, Node Manager) and emails a dark-themed HTML dashboard every N hours.

---

## Quick Start

```cmd
git clone https://github.com/Vlhoseny/weblogic_monitor.git
cd weblogic-monitor
copy .env.example .env
```

Edit `.env` with your credentials:

| Variable | What to put |
|----------|-------------|
| `WL_ADMIN_URL` | `t3://localhost:7101` (or your Admin Server) |
| `WL_ADMIN_USER` | WebLogic admin username (`weblogic`) |
| `WL_ADMIN_PASS` | WebLogic admin password |
| `WL_SMTP_USER` | Gmail address for sending |
| `WL_SMTP_PASS` | Gmail App Password (16 chars) — [create one](https://support.google.com/accounts/answer/185833) |
| `WL_EMAIL_FROM` | Sender address (same as `WL_SMTP_USER`) |
| `WL_EMAIL_TO` | Recipient address |

Then:

```cmd
run.bat
```

The script runs forever, checking every 2 hours. Press **Ctrl+C** to stop.

For a single run: `run.bat --once`

## Daemon Mode

The script runs in a loop by default. Each cycle:

1. Connects to the Admin Server
2. Collects domain info, server states + JVM heap, deployments, datasources, clusters
3. Checks Node Manager reachability
4. Generates a dark HTML report
5. Emails it via SMTP (Gmail)
6. Sleeps for the configured interval (default 2 hours)

Control:

| Command | Behavior |
|---------|----------|
| `run.bat` | Daemon mode (loops every 2h) |
| `run.bat --once` | Single run, then exit |
| `run.bat --interval 3600` | Check every 3600s (1h) |
| Ctrl+C | Stop gracefully |

Environment variable `WL_CHECK_INTERVAL` sets the default interval (seconds). Default: 7200.

## How It Works

The script (`weblogic_monitor.py`) uses WebLogic Scripting Tool (WLST) to:

- **Domain** — name, version
- **Servers** — state (RUNNING/SHUTDOWN/FAILED), health (OK/FAILED/WARNING), heap free %
- **Deployments** — application list from domain config
- **Datasources** — name, max capacity
- **Clusters** — cluster membership
- **Node Manager** — reachability via SSL then plain

Results are compiled into a dark-themed HTML table and sent via `javax.mail` (Jython-compatible).

## If run.bat Can't Find WebLogic

Set `MW_HOME`:

```cmd
set MW_HOME=C:\Oracle\Middleware\Oracle_Home
run.bat
```

Or run manually:

```cmd
set USER_MEM_ARGS=-Xms256m -Xmx1024m
set WL_SCRIPT_DIR=C:\path\to\weblogic-monitor
"C:\Oracle\Middleware\Oracle_Home\oracle_common\common\bin\wlst.cmd" weblogic_monitor.py --once
```

## Project Files

| File | What it is |
|------|-----------|
| `weblogic_monitor.py` | The monitoring script |
| `run.bat` | One-click launcher (auto-finds WLST) |
| `.env` | Your credentials (**do not share**) |
| `.env.example` | Template for `.env` |

## Security

- `.env` is in `.gitignore` — credentials never committed
- Script reads secrets from `.env` or environment variables only
- Gmail App Password required (revocable, scoped to Mail)
- For production, consider WebLogic `UserConfigFile` instead
