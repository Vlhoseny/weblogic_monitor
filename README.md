# WebLogic Health Monitor

Get a daily email with your WebLogic server health — state, JVM heap, and status.

---

## How to Run (3 minutes)

### 1. Download

```cmd
git clone https://github.com/Vlhoseny/weblogic_monitor.git
cd weblogic_monitor
```

### 2. Set up your credentials

```cmd
copy .env.example .env
notepad .env
```

Fill in these 5 values:

| Variable | What to put |
|----------|-------------|
| `WL_ADMIN_PASS` | Your WebLogic `weblogic` user password |
| `WL_SMTP_USER` | Your Gmail address (e.g. `you@gmail.com`) |
| `WL_SMTP_PASS` | A Gmail **App Password** (16 chars) — [get one here](https://support.google.com/accounts/answer/185833) |
| `WL_EMAIL_FROM` | Same as `WL_SMTP_USER` |
| `WL_EMAIL_TO` | Who gets the email (e.g. `you@gmail.com`) |

> **What's an App Password?** Google requires it instead of your regular password.
> Go to https://myaccount.google.com/apppasswords, create one for "Mail" on "Windows Computer", copy the 16-character code.

### 3. Run

**Double-click** `run.bat` — it finds WebLogic automatically and runs the script.

That's it. You'll see server status in the console and get an email.

---

## What If run.bat Can't Find WebLogic?

Set your `MW_HOME` environment variable:

```cmd
set MW_HOME=C:\Oracle\Middleware\Oracle_Home
run.bat
```

Or run manually:

```cmd
set USER_MEM_ARGS=-Xms256m -Xmx1024m
"C:\Oracle\Middleware\Oracle_Home\oracle_common\common\bin\wlst.cmd" weblogic_monitor.py
```

---

```
WebLogic Health Monitor
 Target : t3://127.0.0.1:7101
 Host   : 0xVSTVDEV
 Time   : 2026-06-25 00:43:47
============================================================
Server                   State        Health     FreeHeap%
------------------------------------------------------------
DefaultServer            RUNNING      OK         16.4%
------------------------------------------------------------
OK: Report saved to C:\Users\...\weblogic_report_*.html
OK: Email sent to you@example.com
```

## Schedule Daily Emails (Task Scheduler)

1. Open **Task Scheduler** → **Create Basic Task**
2. Trigger: **Daily** at 8:00 AM
3. Action: **Start a program**
   - Program: `C:\Windows\System32\cmd.exe`
   - Arguments: `/c "C:\path\to\weblogic-monitor\run.bat"`

---

## Project Files

| File | What it is |
|------|-----------|
| `weblogic_monitor.py` | The monitoring script |
| `run.bat` | One-click launcher (auto-finds WebLogic) |
| `.env` | Your credentials (**do not share**) |
| `.env.example` | Template for `.env` |

---

## Security

- `.env` is in `.gitignore` — your passwords **stay on your machine**
- The script reads secrets from `.env` or environment variables, not from the code
- For production, use WebLogic's `UserConfigFile` instead of plaintext passwords
