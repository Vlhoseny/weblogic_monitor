# WebLogic Health Monitor

WLST-based daemon that collects full WebLogic domain health (servers, JVM heap/CPU/GC, thread pools, datasources, JMS queues/topics, SAF agents, deployments, clusters, Node Manager) and emails a professional light-theme HTML dashboard each cycle.

---

## Quick Start

```bash
git clone https://github.com/Vlhoseny/weblogic_monitor.git
cd weblogic-monitor
cp .env.example .env
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

**Windows:** `run.bat`  
**Linux/macOS:** `./run.sh`

The script runs forever, checking every 2 hours. Press **Ctrl+C** to stop.

For a single run: `run.bat --once` or `./run.sh --once`

## Daemon Mode

The script runs in a loop by default. Each cycle:

1. Connects to the Admin Server
2. Collects per-server metrics:
   - **JVM** — heap free/total/percentage, CPU load, GC counts/times
   - **Thread Pool** — total/idle/hogging/stuck threads, queue length
   - **JDBC Datasources** — active connections, leaked connections, wait seconds high
   - **JMS Servers** — current messages, pending messages
   - **JMS Destinations** (queues & topics per server) — current/pending messages, consumer count
   - **SAF Agents** — state, current messages, failed messages total
3. Checks Node Manager reachability
4. Generates a light-theme HTML report with color-coded status badges and progress bars
5. Emails it via SMTP (Gmail)
6. Sleeps for the configured interval

Control:

| Command | Behavior |
|---------|----------|
| `run.bat` / `./run.sh` | Daemon mode (loops every 2h) |
| `--once` | Single run, then exit |
| `--interval 3600` | Check every 3600s (1h) |
| Ctrl+C | Stop gracefully |

Environment variable `WL_CHECK_INTERVAL` sets the default interval (seconds). Default: 7200.

## How It Works

The script (`weblogic_monitor.py`) uses WebLogic Scripting Tool (WLST) and the domain runtime MBean tree to pull live metrics.

### Metrics Collected

| Category | Details |
|----------|---------|
| **Server** | State (RUNNING/SHUTDOWN/FAILED), health (OK/WARN/CRITICAL/FAILED) |
| **JVM** | Heap free %, heap free/total MB, process CPU load, GC collections & time |
| **Thread Pool** | Total/idle/hogging/stuck threads, queue length |
| **JDBC** | Per datasource: active connections, leaked connections, wait seconds high |
| **JMS** | Per JMSServer: current/pending messages |
| **JMS Destinations** | Per queue/topic: current/pending messages, consumer count |
| **SAF Agents** | State, current messages, failed messages total |
| **Deployments** | Application states (via `AppRuntimeStateRuntime`) |
| **Datasources** | Name (from config) |
| **Clusters** | Cluster membership |
| **Node Manager** | Reachability check |

Results are compiled into a light-theme HTML table with inline CSS and sent via `javax.mail`.

## If the Launcher Can't Find WebLogic

Set `MW_HOME`:

**Windows:**
```cmd
set MW_HOME=C:\Oracle\Middleware\Oracle_Home
run.bat
```

**Linux/macOS:**
```bash
export MW_HOME=/opt/oracle/middleware
./run.sh
```

Or run manually:

**Windows:**
```cmd
set USER_MEM_ARGS=-Xms256m -Xmx1024m
set WL_SCRIPT_DIR=C:\path\to\weblogic-monitor
"C:\Oracle\Middleware\Oracle_Home\oracle_common\common\bin\wlst.cmd" weblogic_monitor.py --once
```

**Linux/macOS:**
```bash
export USER_MEM_ARGS="-Xms256m -Xmx1024m"
export WL_SCRIPT_DIR=/path/to/weblogic-monitor
$MW_HOME/oracle_common/common/bin/wlst.sh weblogic_monitor.py --once
```

## Project Files

| File | What it is |
|------|-----------|
| `weblogic_monitor.py` | The monitoring script (Jython/WLST) |
| `run.bat` | One-click launcher for Windows |
| `run.sh` | One-click launcher for Linux/macOS |
| `.env` | Your credentials (**do not share**) |
| `.env.example` | Template for `.env` |

## Security

- `.env` is in `.gitignore` — credentials never committed
- Script reads secrets from `.env` or environment variables only
- Gmail App Password required (revocable, scoped to Mail)
- For production, consider WebLogic `UserConfigFile` instead
