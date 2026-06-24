# WebLogic Health Monitor

WLST/Jython script that collects WebLogic server metrics (state, health, JVM heap) and emails a dark-theme HTML dashboard via SMTP.

## Usage

```cmd
set USER_MEM_ARGS=-Xms256m -Xmx1024m
<MW_HOME>\oracle_common\common\bin\wlst.cmd weblogic_monitor.py
```

Edit the `CONFIGURATION` section at the top of the script to set your admin credentials and SMTP settings.
