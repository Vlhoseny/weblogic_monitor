# =============================================================================
# WebLogic Health Monitor - WLST/Jython 2.7 Script
# =============================================================================
# Collects server state, health, and JVM metrics from a local WebLogic domain
# and emails an HTML dashboard report.
#
# Quick start:
#   1. Copy .env.example to .env and fill in your credentials
#   2. Double-click run.bat  (or run: wlst.cmd weblogic_monitor.py)
# =============================================================================

import sys
import os
import socket

# Load .env file if present (for local credentials)
_script_dir = (os.environ.get('WL_SCRIPT_DIR') or '').strip() or os.getcwd()
if not _script_dir:
    try:
        _script_dir = os.path.dirname(os.path.abspath(__file__))
    except NameError:
        try:
            _script_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        except Exception:
            _script_dir = os.getcwd()
_env_path = os.path.join(_script_dir, '.env')
if os.path.isfile(_env_path):
    for _line in open(_env_path):
        _line = _line.strip()
        if _line and not _line.startswith('#') and '=' in _line:
            _k, _v = _line.split('=', 1)
            os.environ[_k.strip()] = _v.strip()

# ---------------------------------------------------------------------------
# CONFIGURATION - set via environment variables or edit defaults below
# ---------------------------------------------------------------------------

ADMIN_URL      = os.environ.get('WL_ADMIN_URL',     't3://127.0.0.1:7101')
ADMIN_USER     = os.environ.get('WL_ADMIN_USER',    'weblogic')
ADMIN_PASS     = os.environ.get('WL_ADMIN_PASS',    '')

SMTP_HOST      = os.environ.get('WL_SMTP_HOST',     'smtp.gmail.com')
SMTP_PORT      = int(os.environ.get('WL_SMTP_PORT', '587'))
SMTP_USER      = os.environ.get('WL_SMTP_USER',     '')
SMTP_PASS      = os.environ.get('WL_SMTP_PASS',     '')
SMTP_USE_TLS   = os.environ.get('WL_SMTP_USE_TLS',  'true').lower() == 'true'

EMAIL_FROM     = os.environ.get('WL_EMAIL_FROM',    '')
EMAIL_TO       = os.environ.get('WL_EMAIL_TO',      '').split(',')

# ---------------------------------------------------------------------------
# Validate required config
# ---------------------------------------------------------------------------
_missing = []
if not ADMIN_PASS:
    _missing.append('WL_ADMIN_PASS')
if not SMTP_USER:
    _missing.append('WL_SMTP_USER')
if not SMTP_PASS:
    _missing.append('WL_SMTP_PASS')
if not EMAIL_FROM:
    _missing.append('WL_EMAIL_FROM')
if not EMAIL_TO or EMAIL_TO == ['']:
    _missing.append('WL_EMAIL_TO')
if _missing:
    print '=' * 60
    print ' MISSING CONFIGURATION'
    print '=' * 60
    for v in _missing:
        print '   - %s' % v
    print
    print ' Create/edit the .env file in this directory:'
    print '   copy .env.example .env'
    print '   notepad .env'
    print
    sys.exit(1)

# ---------------------------------------------------------------------------
# HealthState constants (weblogic.health.HealthState)
# ---------------------------------------------------------------------------
HEALTH_MAP = {
    0: ('OK',       '#2ecc71'),
    1: ('WARN',     '#f1c40f'),
    2: ('CRITICAL', '#e74c3c'),
    3: ('FAILED',   '#c0392b'),
    4: ('OVERLOAD', '#e67e22'),
}


def get_health_label(state_code):
    """Return (label, color) for a health state integer."""
    return HEALTH_MAP.get(state_code, ('UNKNOWN', '#95a5a6'))


def collect_metrics():
    """Connect to the Admin Server and collect metrics from every server."""
    results = []
    try:
        connect(ADMIN_USER, ADMIN_PASS, ADMIN_URL)
    except Exception, e:
        print 'ERROR: Failed to connect to %s - %s' % (ADMIN_URL, str(e))
        sys.exit(1)

    domainRuntime()

    # Get server names by navigating the runtime tree
    serverNames = []
    try:
        cd('/ServerRuntimes')
        serverNames = ls(returnMap='true')
    except Exception, e:
        print 'ERROR: Cannot list server runtimes - %s' % str(e)
        disconnect()
        sys.exit(1)

    if not serverNames:
        print 'WARN: No server runtimes found.'
        disconnect()
        return results

    for name in serverNames:
        state = 'UNKNOWN'
        health_code = -1
        heap_free_pct = -1.0

        # Server state and health
        try:
            cd('/ServerRuntimes/' + name)
            state = cmo.getState()
        except Exception:
            pass

        try:
            hs = cmo.getHealthState()
            if hs:
                health_code = hs.getState()
        except Exception:
            pass

        health_label, health_color = get_health_label(health_code)

        # JVM heap (JVMRuntime is under the server runtime in domainRuntime tree)
        try:
            cd('/ServerRuntimes/' + name + '/JVMRuntime/' + name)
            free  = cmo.getHeapFreeCurrent()
            total = cmo.getHeapSizeCurrent()
            if total > 0:
                heap_free_pct = round((float(free) / total) * 100, 1)
        except Exception:
            pass

        results.append({
            'name':          name,
            'state':         state,
            'health_label':  health_label,
            'health_color':  health_color,
            'heap_free_pct': heap_free_pct,
        })

    disconnect()
    return results


def build_html(metrics, hostname):
    """Generate a dark-theme HTML dashboard."""
    from time import strftime as fmt_time
    now = fmt_time('%Y-%m-%d %H:%M:%S')

    rows = ''
    for m in metrics:
        state_name = m['state'].lower()
        state_badge = ('<span class="badge state-'
            + state_name + '">' + m['state'] + '</span>')

        health_badge = ('<span class="badge" style="background:'
            + m['health_color'] + '">' + m['health_label'] + '</span>')

        if m['heap_free_pct'] < 0:
            heap_cell = '<span class="muted">N/A</span>'
        elif m['heap_free_pct'] < 20:
            heap_cell = ('<span class="badge state-critical">'
                + str(round(m['heap_free_pct'], 1)) + '</span>')
        elif m['heap_free_pct'] < 40:
            heap_cell = ('<span class="badge" style="background:#f1c40f">'
                + str(round(m['heap_free_pct'], 1)) + '</span>')
        else:
            heap_cell = ('<span class="badge" style="background:#2ecc71">'
                + str(round(m['heap_free_pct'], 1)) + '</span>')

        rows += ('<tr>'
            '<td>' + m['name'] + '</td>'
            '<td>' + state_badge + '</td>'
            '<td>' + health_badge + '</td>'
            '<td>' + heap_cell + '</td>'
            '</tr>')

    html = ('''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>WebLogic Health Monitor</title>
<style>
  * { margin:0; padding:0; box-sizing:border-box; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
    background: #1a1d23;
    color: #e4e7eb;
    padding: 40px 20px;
  }
  .container { max-width: 960px; margin: 0 auto; }
  .header {
    display: flex; justify-content: space-between; align-items: center;
    margin-bottom: 32px; padding-bottom: 16px;
    border-bottom: 1px solid #2d3139;
  }
  .header h1 {
    font-size: 22px; font-weight: 600;
    background: linear-gradient(135deg, #6366f1, #8b5cf6);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
  }
  .header .meta { font-size: 13px; color: #9ca3af; text-align: right; }
  .header .meta span { display: block; }
  .header .meta .host { color: #e4e7eb; font-weight: 500; }
  table {
    width: 100%; border-collapse: collapse;
    background: #22262e; border-radius: 12px; overflow: hidden;
  }
  th {
    background: #2d3139; color: #9ca3af; font-size: 11px;
    text-transform: uppercase; letter-spacing: 0.5px;
    padding: 14px 18px; text-align: left; font-weight: 600;
  }
  td {
    padding: 14px 18px; font-size: 14px; border-top: 1px solid #2d3139;
  }
  tr:hover td { background: #2a2e37; }
  .badge {
    display: inline-block; padding: 3px 12px; border-radius: 12px;
    font-size: 12px; font-weight: 600; color: #fff;
  }
  .badge.state-running    { background: #2ecc71; }
  .badge.state-shutdown   { background: #7f8c8d; }
  .badge.state-failed     { background: #e74c3c; }
  .badge.state-critical   { background: #e74c3c; }
  .badge.state-admin      { background: #e67e22; }
  .badge.state-unknown    { background: #95a5a6; }
  .muted { color: #6b7280; font-style: italic; }
  .footer {
    text-align: center; margin-top: 24px; font-size: 12px; color: #6b7280;
  }
</style>
</head>
<body>
<div class="container">
  <div class="header">
      <h1>WebLogic Health Monitor</h1>
    <div class="meta">
      <span class="host">''' + hostname + '''</span>
      <span>''' + now + '''</span>
    </div>
  </div>
  <table>
    <thead>
      <tr>
        <th>Server</th>
        <th>State</th>
        <th>Health</th>
        <th>Free Heap</th>
      </tr>
    </thead>
    <tbody>
      ''' + rows + '''
    </tbody>
  </table>
  <div class="footer">
    Generated by WLST - WebLogic Health Monitor
  </div>
</div>
</body>
</html>''')

    return html


def send_email(html_body, subject=None):
    """Send the HTML report via SMTP using javax.mail (Jython-safe)."""
    from time import strftime as fmt_time

    if not SMTP_USER or not SMTP_PASS:
        print 'WARN: SMTP not configured - skipping email. Set WL_SMTP_USER and WL_SMTP_PASS in .env'
        return False

    if subject is None:
        subject = 'WebLogic Health Report - ' + fmt_time('%Y-%m-%d %H:%M')

    from javax.mail import Session, Message
    from javax.mail.internet import MimeMessage, InternetAddress, MimeMultipart, MimeBodyPart
    from java.util import Properties

    props = Properties()
    props.put('mail.smtp.host', SMTP_HOST)
    props.put('mail.smtp.port', str(SMTP_PORT))
    props.put('mail.smtp.auth', 'true')
    props.put('mail.smtp.connectiontimeout', '15000')
    props.put('mail.smtp.timeout', '15000')
    props.put('mail.smtp.writetimeout', '15000')
    if SMTP_USE_TLS:
        props.put('mail.smtp.starttls.enable', 'true')

    session = Session.getInstance(props)
    msg = MimeMessage(session)
    msg.setFrom(InternetAddress(EMAIL_FROM))
    for to in EMAIL_TO:
        msg.addRecipient(Message.RecipientType.TO, InternetAddress(to))
    msg.setSubject(subject)

    multipart = MimeMultipart('alternative')
    htmlPart = MimeBodyPart()
    htmlPart.setContent(html_body, 'text/html; charset=utf-8')
    multipart.addBodyPart(htmlPart)
    msg.setContent(multipart)

    print '  Connecting to SMTP %s:%s ...' % (SMTP_HOST, SMTP_PORT)
    try:
        transport = session.getTransport('smtp')
        transport.connect(SMTP_HOST, SMTP_USER, SMTP_PASS)
        transport.sendMessage(msg, msg.getAllRecipients())
        transport.close()
        print 'OK: Email sent to ' + ', '.join(EMAIL_TO)
        return True
    except Exception, e:
        print 'ERROR: Failed to send email - ' + str(e)
        return False


# ---------------------------------------------------------------------------
# Daemon loop
# ---------------------------------------------------------------------------
INTERVAL_SECONDS = 7200  # 2 hours

def run_once():
    from time import strftime as fmt_time
    now = fmt_time('%Y-%m-%d %H:%M:%S')
    hostname = socket.gethostname()
    print ''
    print '=' * 60
    print ' WebLogic Health Monitor'
    print ' Target : %s' % ADMIN_URL
    print ' Host   : %s' % hostname
    print ' Time   : %s' % now
    print '=' * 60

    metrics = collect_metrics()

    if not metrics:
        print 'ERROR: No server metrics collected.'
        return

    print ''
    print '%-24s %-12s %-10s %s' % ('Server', 'State', 'Health', 'FreeHeap%')
    print '-' * 60
    for m in metrics:
        if m['heap_free_pct'] >= 0:
            heap_str = '%.1f%%' % m['heap_free_pct']
        else:
            heap_str = 'N/A'
        print '%-24s %-12s %-10s %s' % (
            m['name'], m['state'], m['health_label'], heap_str)
    print '-' * 60

    html = build_html(metrics, hostname)

    report_dir = os.environ.get('TEMP', '/tmp')
    report_path = os.path.join(report_dir, 'weblogic_report_%s.html' % fmt_time('%Y%m%d_%H%M'))
    try:
        f = open(report_path, 'w')
        f.write(html.encode('utf-8'))
        f.close()
        print 'OK: Report saved to %s' % report_path
    except Exception, e:
        print 'WARN: Could not write report file - %s' % str(e)

    send_email(html)

    print '[%s] Done.' % now


if len(sys.argv) > 1 and sys.argv[1] == '--once':
    run_once()
else:
    from time import strftime as fmt_time, sleep as _sleep

    print 'WebLogic Health Monitor - Daemon Mode'
    print 'Interval: every %d seconds (%d hours)' % (INTERVAL_SECONDS, INTERVAL_SECONDS / 3600)
    print 'Press Ctrl+C to stop.'
    print ''

    try:
        while True:
            run_once()
            next_run = fmt_time('%Y-%m-%d %H:%M:%S')
            print ''
            print 'Next check at %s (waiting %d minutes)...' % (next_run, INTERVAL_SECONDS / 60)
            print 'Press Ctrl+C to stop.'
            _sleep(INTERVAL_SECONDS)
    except KeyboardInterrupt:
        print ''
        print 'Stopped by user.'
