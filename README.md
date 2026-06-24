# WebLogic Health Monitor

WLST/Jython script that collects WebLogic server metrics (state, health, JVM heap) and emails a dark-theme HTML dashboard via SMTP.

## Setup

Copy `.env.example` to `.env` and fill in your credentials:

```cmd
copy .env.example .env
```

Edit `.env` with your WebLogic admin password and Gmail SMTP app password.

## Usage

```cmd
set USER_MEM_ARGS=-Xms256m -Xmx1024m
<MW_HOME>\oracle_common\common\bin\wlst.cmd weblogic_monitor.py
```
