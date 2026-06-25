import sys
import os
import socket

_script_dir = (os.environ.get('WL_SCRIPT_DIR') or '').strip() or os.getcwd()
_env_path = os.path.join(_script_dir, '.env')
if os.path.isfile(_env_path):
    for _line in open(_env_path):
        _line = _line.strip()
        if _line and not _line.startswith('#') and '=' in _line:
            _k, _v = _line.split('=', 1)
            os.environ[_k.strip()] = _v.strip()

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

CHECK_INTERVAL = int(os.environ.get('WL_CHECK_INTERVAL', '7200'))

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

HEALTH_MAP = {
    0: ('OK',       '#2ecc71'),
    1: ('WARN',     '#f1c40f'),
    2: ('CRITICAL', '#e74c3c'),
    3: ('FAILED',   '#c0392b'),
    4: ('OVERLOAD', '#e67e22'),
}

STATE_COLORS = {
    'running': '#2ecc71', 'shutdown': '#7f8c8d',
    'failed': '#e74c3c', 'admin': '#e67e22',
}

def badge(text, bg):
    return ('<span style="display:inline-block;padding:3px 10px;'
        'border-radius:10px;font-size:12px;font-weight:700;'
        'color:#fff;background:' + bg + '">' + text + '</span>')

def get_health_label(state_code):
    return HEALTH_MAP.get(state_code, ('UNKNOWN', '#95a5a6'))

def sf(fmt='%Y-%m-%d %H:%M:%S'):
    from time import strftime as _f
    return _f(fmt)

def section(title):
    print ''
    print '--- ' + title + ' ' + ('-' * max(50 - len(title), 4))

# ---------------------------------------------------------------------------
# Collectors
# ---------------------------------------------------------------------------

def soft(fn, fallback=None):
    try:
        return fn()
    except Exception:
        return fallback

def collect_domain_info():
    name = 'Unknown'
    version = 'N/A'
    try:
        cd('/')
        name = str(cmo.getName())
    except Exception:
        pass
    try:
        from java.lang import System
        v = System.getProperty('weblogic.version')
        if v:
            version = str(v)
    except Exception:
        pass
    return {'name': name, 'version': version}

def collect_servers():
    results = []
    try:
        cd('/ServerRuntimes')
        names = ls(returnMap='true')
    except Exception:
        return results
    for name in names:
        s = {'name': name, 'state': 'UNKNOWN', 'health_label': 'UNKNOWN',
             'health_color': '#95a5a6', 'heap_free_pct': -1.0}
        try:
            cd('/ServerRuntimes/' + name)
            s['state'] = cmo.getState()
        except Exception:
            pass
        try:
            hs = cmo.getHealthState()
            if hs:
                s['health_label'], s['health_color'] = get_health_label(hs.getState())
        except Exception:
            pass
        try:
            cd('/ServerRuntimes/' + name + '/JVMRuntime/' + name)
            free  = cmo.getHeapFreeCurrent()
            total = cmo.getHeapSizeCurrent()
            if total > 0:
                s['heap_free_pct'] = round((float(free) / total) * 100, 1)
        except Exception:
            pass
        results.append(s)
    return results

def collect_deployments():
    results = []
    try:
        domainConfig()
        cd('/AppDeployments')
        apps = ls(returnMap='true')
    except Exception:
        return results
    for name in apps:
        results.append({'name': name, 'state': 'configured'})
    if len(apps) == 0:
        domainRuntime()
        try:
            cd('/AppRuntimeStateRuntime/AppRuntimeStateRuntime')
            states = ls(returnMap='true')
            for appName in states:
                pass
        except Exception:
            pass
    return results

def collect_datasources():
    results = []
    try:
        domainConfig()
        cd('/JDBCSystemResources')
        names = ls(returnMap='true')
    except Exception:
        return results
    for name in names:
        r = {'name': name, 'state': 'configured', 'max': -1}
        try:
            cd('/JDBCSystemResources/' + name + '/JDBCResource/' + name
               + '/JDBCConnectionPoolParams/' + name)
            r['max'] = int(cmo.getMaxCapacity())
        except Exception:
            pass
        results.append(r)
    return results

def collect_clusters():
    results = []
    try:
        domainConfig()
        cd('/Clusters')
        names = ls(returnMap='true')
    except Exception:
        return results
    for name in names:
        results.append({'name': name})
    return results

def check_nm():
    try:
        nmConnect(username=ADMIN_USER, password=ADMIN_PASS,
                  host='localhost', port='5556',
                  domainName='', domainDir='', nmType='ssl')
        nmDisconnect()
        return 'Running'
    except Exception:
        pass
    try:
        nmConnect(username=ADMIN_USER, password=ADMIN_PASS,
                  host='localhost', port='5556',
                  domainName='', domainDir='', nmType='plain')
        nmDisconnect()
        return 'Running'
    except Exception:
        pass
    return 'Not reachable'

def collect_domain_health():
    d = {}

    connect(ADMIN_USER, ADMIN_PASS, ADMIN_URL)

    section('Domain Info')
    d['domain'] = collect_domain_info()
    print '  Name: %s   Version: %s' % (d['domain']['name'], d['domain']['version'])

    domainRuntime()
    section('Servers')
    d['servers'] = collect_servers()
    up = len([1 for s in d['servers'] if s['state'] == 'RUNNING'])
    print '  %d/%d running' % (up, len(d['servers']))
    for s in d['servers']:
        if s['heap_free_pct'] >= 0:
            hp = ' (%.1f%% heap)' % s['heap_free_pct']
        else:
            hp = ''
        print '    %-24s %-10s %s%s' % (s['name'], s['state'], s['health_label'], hp)

    section('Deployments')
    d['deployments'] = collect_deployments()
    print '  %d found' % len(d['deployments'])
    for a in d['deployments']:
        print '    %-30s %s' % (a['name'], a['state'])

    section('Datasources')
    d['datasources'] = collect_datasources()
    print '  %d found' % len(d['datasources'])
    for ds in d['datasources']:
        if ds['max'] > 0:
            cap = ', max: %d' % ds['max']
        else:
            cap = ''
        print '    %-30s %s%s' % (ds['name'], ds['state'], cap)

    section('Clusters')
    d['clusters'] = collect_clusters()
    print '  %d found' % len(d['clusters'])
    for c in d['clusters']:
        print '    %s' % c['name']

    disconnect()

    section('Node Manager')
    d['nm'] = check_nm()
    print '  %s' % d['nm']

    return d

# ---------------------------------------------------------------------------
# HTML report
# ---------------------------------------------------------------------------

def build_html_report(data, hostname):
    now = sf()
    rows = []

    def td(cells):
        parts = []
        for c in cells:
            parts.append('<td style="padding:10px 14px;font-size:13px;'
                        'border-top:1px solid #2d3139;color:#e4e7eb">'
                        + c + '</td>')
        return '<tr>' + ''.join(parts) + '</tr>\n'

    def th(cells):
        parts = []
        for c in cells:
            parts.append('<th style="padding:10px 14px;font-size:11px;font-weight:700;'
                        'color:#9ca3af;text-transform:uppercase;text-align:left;'
                        'background:#2d3139">' + c + '</th>')
        return '<tr>' + ''.join(parts) + '</tr>\n'

    html = []
    html.append('<!DOCTYPE html>\n<html><head><meta charset="UTF-8"><title>WebLogic Health Report</title></head>\n')
    html.append('<body style="margin:0;padding:0;background:#1a1d23;font-family:Arial,Helvetica,sans-serif;color:#e4e7eb">\n')
    html.append('<table align="center" width="100%" cellpadding="0" cellspacing="0" style="max-width:700px;background:#1a1d23">\n')

    html.append('<tr><td style="padding:30px 20px 10px">\n'
        '<table width="100%" cellpadding="0" cellspacing="0" style="border-bottom:1px solid #2d3139;padding-bottom:12px">\n'
        '<tr>\n'
        '<td style="font-size:20px;font-weight:700;color:#8b5cf6">WebLogic Domain Report</td>\n'
        '<td style="text-align:right;font-size:12px;color:#9ca3af">\n'
        '<div style="color:#e4e7eb;font-weight:600">' + hostname + '</div>\n'
        '<div>' + now + '</div>\n'
        '</td>\n</tr>\n</table>\n</td></tr>\n')

    d = data['domain']
    sv = data['servers']
    up = len([1 for s in sv if s['state'] == 'RUNNING'])
    nm_ok = data.get('nm') == 'Running'

    html.append('<tr><td style="padding:16px 20px 4px">\n'
        '<table width="100%" cellpadding="0" cellspacing="0">\n<tr>\n'
        '<td style="width:25%;padding:8px;text-align:center;background:#22262e;border-radius:6px">\n'
        '<div style="font-size:22px;font-weight:700;color:#e4e7eb">' + str(len(sv)) + '</div>\n'
        '<div style="font-size:11px;color:#9ca3af">Servers</div>\n</td>\n'
        '<td style="width:25%;padding:8px;text-align:center;background:#22262e;border-radius:6px">\n'
        '<div style="font-size:22px;font-weight:700;color:#2ecc71">' + str(up) + '</div>\n'
        '<div style="font-size:11px;color:#9ca3af">Running</div>\n</td>\n'
        '<td style="width:25%;padding:8px;text-align:center;background:#22262e;border-radius:6px">\n'
        '<div style="font-size:22px;font-weight:700;color:#e4e7eb">' + str(len(data['deployments'])) + '</div>\n'
        '<div style="font-size:11px;color:#9ca3af">Deployments</div>\n</td>\n'
        '<td style="width:25%;padding:8px;text-align:center;background:#22262e;border-radius:6px">\n'
        '<div style="font-size:22px;font-weight:700;color:#f1c40f">' + str(len(data['datasources'])) + '</div>\n'
        '<div style="font-size:11px;color:#9ca3af">Datasources</div>\n</td>\n'
        '</tr>\n</table>\n</td></tr>\n')

    if nm_ok:
        nm_badge = badge('Running', '#2ecc71')
    else:
        nm_badge = badge('Down', '#e74c3c')
    html.append('<tr><td style="padding:4px 20px 14px;font-size:12px;color:#9ca3af">\n'
        'Domain: ' + d['name'] + ' &nbsp;|&nbsp; Version: ' + d['version']
        + ' &nbsp;|&nbsp; Node Manager: ' + nm_badge + '</td></tr>\n')

    if data.get('clusters'):
        cnames = []
        for c in data['clusters']:
            cnames.append(c['name'])
        html.append('<tr><td style="padding:0 20px 10px;font-size:12px;color:#9ca3af">'
            'Clusters: ' + ', '.join(cnames) + '</td></tr>\n')

    html.append('<tr><td style="padding:4px 20px">\n'
        '<table width="100%" cellpadding="0" cellspacing="0" style="background:#22262e;border-radius:6px;overflow:hidden">\n')
    html.append(th(['Server', 'State', 'Health', 'Free Heap']))
    for s in sv:
        sn = s['state'].lower()
        sb = badge(s['state'], STATE_COLORS.get(sn, '#95a5a6'))
        hb = badge(s['health_label'], s['health_color'])
        hp = s['heap_free_pct']
        if hp < 0:
            hc = '<span style="color:#6b7280;font-style:italic">N/A</span>'
        elif hp < 20:
            hc = badge(str(round(hp, 1)) + '%', '#e74c3c')
        elif hp < 40:
            hc = badge(str(round(hp, 1)) + '%', '#f1c40f')
        else:
            hc = badge(str(round(hp, 1)) + '%', '#2ecc71')
        html.append(td([s['name'], sb, hb, hc]))
    html.append('</table>\n</td></tr>\n')

    if data['deployments']:
        html.append('<tr><td style="padding:16px 20px 4px;font-size:14px;font-weight:600">'
            'Deployments</td></tr>\n')
        html.append('<tr><td style="padding:4px 20px">\n'
            '<table width="100%" cellpadding="0" cellspacing="0" style="background:#22262e;border-radius:6px;overflow:hidden">\n')
        html.append(th(['Application', 'State']))
        for a in data['deployments']:
            as_ = a['state'].lower()
            if as_ in ('active', 'prepared'):
                ab = badge(a['state'], '#2ecc71')
            elif as_ == 'failed':
                ab = badge(a['state'], '#e74c3c')
            else:
                ab = badge(a['state'], '#f1c40f')
            html.append(td([a['name'], ab]))
        html.append('</table>\n</td></tr>\n')

    if data['datasources']:
        html.append('<tr><td style="padding:16px 20px 4px;font-size:14px;font-weight:600">'
            'Datasources</td></tr>\n')
        html.append('<tr><td style="padding:4px 20px">\n'
            '<table width="100%" cellpadding="0" cellspacing="0" style="background:#22262e;border-radius:6px;overflow:hidden">\n')
        html.append(th(['Name', 'Max Connections']))
        for ds in data['datasources']:
            if ds['max'] > 0:
                c = str(ds['max'])
            else:
                c = 'N/A'
            html.append(td([ds['name'], c]))
        html.append('</table>\n</td></tr>\n')

    html.append('<tr><td style="padding:20px;text-align:center;font-size:11px;color:#6b7280">'
        'Generated by WLST &ndash; WebLogic Health Monitor</td></tr>\n')
    html.append('</table>\n</body></html>\n')
    return ''.join(html)

# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------

def send_email(html_body, subject=None):
    if not SMTP_USER or not SMTP_PASS:
        print '  SMTP not configured - skipping.'
        return False

    from time import strftime as _f
    if subject is None:
        subject = 'WebLogic Health Report - ' + _f('%Y-%m-%d %H:%M')

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

    mp = MimeMultipart('alternative')
    hp_ = MimeBodyPart()
    hp_.setContent(html_body, 'text/html; charset=utf-8')
    mp.addBodyPart(hp_)
    msg.setContent(mp)

    print '  SMTP %s:%s ...' % (SMTP_HOST, SMTP_PORT)
    try:
        t = session.getTransport('smtp')
        t.connect(SMTP_HOST, SMTP_USER, SMTP_PASS)
        t.sendMessage(msg, msg.getAllRecipients())
        t.close()
        print '  Email sent to ' + ', '.join(EMAIL_TO)
        return True
    except Exception, e:
        print '  ERROR: ' + str(e)
        return False

# ---------------------------------------------------------------------------
# Run cycle
# ---------------------------------------------------------------------------

def run_once():
    now = sf()
    hostname = socket.gethostname()
    print ''
    print '=' * 60
    print ' WebLogic Domain Health Check'
    print ' Target : %s' % ADMIN_URL
    print ' Host   : %s' % hostname
    print ' Time   : %s' % now
    print '=' * 60

    data = collect_domain_health()

    if not data.get('servers'):
        print 'ERROR: No servers found.'
        return

    section('Summary')
    for s in data['servers']:
        if s['heap_free_pct'] >= 0:
            hp = '%.1f%%' % s['heap_free_pct']
        else:
            hp = 'N/A'
        print '  %-24s %-10s %-10s %s' % (s['name'], s['state'], s['health_label'], hp)

    html = build_html_report(data, hostname)

    rdir = os.environ.get('TEMP', '/tmp')
    rpath = os.path.join(rdir, 'weblogic_report_%s.html' % sf('%Y%m%d_%H%M'))
    try:
        f = open(rpath, 'w')
        f.write(html.encode('utf-8'))
        f.close()
        section('Report')
        print '  Saved: %s' % rpath
    except Exception, e:
        pass

    section('Email')
    send_email(html)

# ---------------------------------------------------------------------------
# Entry
# ---------------------------------------------------------------------------

if len(sys.argv) > 1 and sys.argv[1] == '--once':
    run_once()
else:
    from time import strftime as _tf, sleep as slp
    interval = CHECK_INTERVAL
    for i, a in enumerate(sys.argv):
        if a == '--interval' and i + 1 < len(sys.argv):
            try:
                interval = int(sys.argv[i + 1])
            except ValueError:
                pass

    print 'WebLogic Health Monitor - Daemon Mode'
    print 'Interval: every %d seconds (%d hours, %d minutes)' % (
        interval, interval / 3600, (interval % 3600) / 60)
    print 'Press Ctrl+C to stop.'
    print ''

    try:
        while True:
            run_once()
            nx = _tf('%Y-%m-%d %H:%M:%S')
            print ''
            print 'Next check at %s (waiting %d minutes)...' % (nx, interval / 60)
            print 'Press Ctrl+C to stop.'
            slp(interval)
    except KeyboardInterrupt:
        print ''
        print 'Stopped by user.'
