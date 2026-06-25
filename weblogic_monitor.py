import sys
import os
from javax.mail import Authenticator, PasswordAuthentication



# ---------------------------------------------------------------------------
# Config  - load .env then env vars
# ---------------------------------------------------------------------------
_script_dir = os.environ.get('WL_SCRIPT_DIR')
if _script_dir:
    _script_dir = _script_dir.strip()
    _env_path = os.path.join(_script_dir, '.env')
    if os.path.isfile(_env_path):
        for _line in open(_env_path):
            _line = _line.strip()
            if _line and not _line.startswith('#') and '=' in _line:
                _k, _v = _line.split('=', 1)
                os.environ[_k.strip()] = _v.strip()

ADMIN_URL = os.environ.get('WL_ADMIN_URL', 't3://localhost:7101')
ADMIN_USER = os.environ.get('WL_ADMIN_USER', 'weblogic')
ADMIN_PASS = os.environ.get('WL_ADMIN_PASS')
SMTP_USER = os.environ.get('WL_SMTP_USER')
SMTP_PASS = os.environ.get('WL_SMTP_PASS')
EMAIL_FROM = os.environ.get('WL_EMAIL_FROM', SMTP_USER)
EMAIL_TO = os.environ.get('WL_EMAIL_TO')
INTERVAL = int(os.environ.get('WL_CHECK_INTERVAL', '7200'))

def _check_config():
    missing = []
    if not ADMIN_PASS:
        missing.append('WL_ADMIN_PASS')
    if not SMTP_USER:
        missing.append('WL_SMTP_USER')
    if not SMTP_PASS:
        missing.append('WL_SMTP_PASS')
    if not EMAIL_TO:
        missing.append('WL_EMAIL_TO')
    if missing:
        print 'ERROR: Missing required env vars: ' + ', '.join(missing)
        print '       Check your .env file or set them as system env vars.'
        raise SystemExit(1)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def section(title):
    print ''
    dashes = '-' * max(50 - len(title), 4)
    print '--- ' + title + ' ' + dashes

def list_children(path):
    """Return list of child MBean names at the given WLST path."""
    try:
        cd(path)
        m = ls(returnMap='true')
        if m:
            result = []
            for k in m:
                result.append(str(k))
            return result
    except:
        pass
    return []

def safe_get(mbean, attr, default='N/A'):
    try:
        val = getattr(mbean, attr)()
        if val is None:
            return default
        return val
    except:
        return default

def fmt_mb(bytes_val):
    if isinstance(bytes_val, (int, long)) and bytes_val > 0:
        return str(round(bytes_val / (1024.0 * 1024.0), 1)) + ' MB'
    return 'N/A'

def fmt_pct(val):
    if isinstance(val, (int, long, float)) and val >= 0:
        return str(round(val, 1)) + '%'
    return 'N/A'

def color_for_health(val, warn=40, crit=20, invert=False):
    if not isinstance(val, (int, long, float)) or val < 0:
        return '#9ca3af'
    if invert:
        if val >= warn:
            return '#ef4444'
        if val >= crit:
            return '#f59e0b'
        return '#10b981'
    else:
        if val < crit:
            return '#ef4444'
        if val < warn:
            return '#f59e0b'
        return '#10b981'

# ---------------------------------------------------------------------------
# Collectors
# ---------------------------------------------------------------------------
def collect_jvm_metrics(server):
    data = {}
    data['heap_free'] = -1
    data['heap_total'] = -1
    data['heap_pct'] = -1
    data['cpu'] = -1
    data['gc_list'] = []
    try:
        jvms = list_children('/ServerRuntimes/' + server + '/JVMRuntime')
        if jvms:
            cd('/ServerRuntimes/' + server + '/JVMRuntime/' + jvms[0])
            data['heap_free'] = safe_get(cmo, 'getHeapFreeCurrent', -1)
            data['heap_total'] = safe_get(cmo, 'getHeapSizeCurrent', -1)
            if isinstance(data['heap_total'], (int, long)) and data['heap_total'] > 0:
                data['heap_pct'] = round(float(data['heap_free']) / float(data['heap_total']) * 100.0, 1)
    except:
        pass
    try:
        from java.lang.management import ManagementFactory
        os_mx = ManagementFactory.getOperatingSystemMXBean()
        if hasattr(os_mx, 'getProcessCpuLoad'):
            load = os_mx.getProcessCpuLoad()
            if isinstance(load, float) and load >= 0:
                data['cpu'] = round(load * 100.0, 1)
    except:
        pass
    try:
        from java.lang.management import ManagementFactory
        gc_beans = ManagementFactory.getGarbageCollectorMXBeans()
        for i in range(gc_beans.size()):
            gc = gc_beans.get(i)
            data['gc_list'].append({
                'name': str(gc.getName()),
                'count': gc.getCollectionCount(),
                'time': gc.getCollectionTime(),
            })
    except:
        pass
    return data

def collect_thread_pool(server):
    try:
        cd('/ServerRuntimes/' + server + '/ThreadPoolRuntime/ThreadPoolRuntime')
        return {
            'active': safe_get(cmo, 'getExecuteThreadTotalCount', -1),
            'idle': safe_get(cmo, 'getExecuteThreadIdleCount', -1),
            'hogging': safe_get(cmo, 'getHoggingThreadCount', -1),
            'standby': safe_get(cmo, 'getStandbyThreadCount', -1),
            'queue': safe_get(cmo, 'getQueueLength', -1),
            'pending': safe_get(cmo, 'getPendingUserRequestCount', -1),
            'stuck': safe_get(cmo, 'getStuckThreadCount', -1),
        }
    except:
        pass
    return {}

def collect_jdbc_metrics(server):
    results = []
    try:
        cd('/ServerRuntimes/' + server + '/JDBCServiceRuntime/' + server + '/JDBCDataSourceRuntimeMBeans')
        ds_list = ls(returnMap='true')
        if ds_list:
            for ds in ds_list:
                try:
                    cd('/ServerRuntimes/' + server + '/JDBCServiceRuntime/' + server + '/JDBCDataSourceRuntimeMBeans/' + ds)
                    results.append({
                        'name': ds,
                        'active': safe_get(cmo, 'getActiveConnectionsCurrentCount', -1),
                        'leaked': safe_get(cmo, 'getLeakedConnectionCount', -1),
                        'wait_high': safe_get(cmo, 'getWaitSecondsHighCount', -1),
                    })
                except:
                    pass
    except:
        pass
    return results

def collect_jms_metrics(server):
    results = []
    try:
        cd('/ServerRuntimes/' + server + '/JMSRuntime/' + server + '.jms/JMSServers')
        jms_list = ls(returnMap='true')
        if jms_list:
            for jn in jms_list:
                try:
                    cd('/ServerRuntimes/' + server + '/JMSRuntime/' + server + '.jms/JMSServers/' + jn)
                    results.append({
                        'name': jn,
                        'messages_cur': safe_get(cmo, 'getMessagesCurrentCount', -1),
                        'messages_pending': safe_get(cmo, 'getMessagesPendingCount', -1),
                        'destinations': collect_jms_destinations(server, jn),
                    })
                except:
                    pass
    except:
        pass
    return results

def collect_jms_destinations(server, jms_name):
    results = []
    try:
        cd('/ServerRuntimes/' + server + '/JMSRuntime/' + server + '.jms/JMSServers/' + jms_name + '/Destinations')
        dest_list = ls(returnMap='true')
        if dest_list:
            for d in dest_list:
                try:
                    cd('/ServerRuntimes/' + server + '/JMSRuntime/' + server + '.jms/JMSServers/' + jms_name + '/Destinations/' + d)
                    results.append({
                        'name': d,
                        'messages_cur': safe_get(cmo, 'getMessagesCurrentCount', -1),
                        'messages_pending': safe_get(cmo, 'getMessagesPendingCount', -1),
                        'consumers': safe_get(cmo, 'getConsumersCurrentCount', -1),
                    })
                except:
                    pass
    except:
        pass
    return results

def collect_saf_agents(server):
    results = []
    try:
        cd('/ServerRuntimes/' + server + '/SAFRuntime/' + server + '.saf/Agents')
        agent_list = ls(returnMap='true')
        if agent_list:
            for a in agent_list:
                try:
                    cd('/ServerRuntimes/' + server + '/SAFRuntime/' + server + '.saf/Agents/' + a)
                    results.append({
                        'name': a,
                        'state': safe_get(cmo, 'getState', 'unknown'),
                        'messages_cur': safe_get(cmo, 'getMessagesCurrentCount', -1),
                        'failed_total': safe_get(cmo, 'getFailedMessagesTotalCount', -1),
                    })
                except:
                    pass
    except:
        pass
    return results

_HEALTH_NAMES = {0: 'OK', 1: 'WARN', 2: 'CRITICAL', 3: 'FAILED', 4: 'OVERLOADED'}

def collect_all_servers():
    results = []
    sv_list = list_children('/ServerRuntimes')
    for sv in sv_list:
        server = {}
        server['name'] = sv
        server['state'] = 'unknown'
        server['health'] = 'unknown'
        try:
            cd('/ServerRuntimes/' + sv)
            server['state'] = str(cmo.getState())
            hs = cmo.getHealthState()
            server['health'] = _HEALTH_NAMES.get(hs.getState(), str(hs.getState()))
        except:
            pass
        server['jvm'] = collect_jvm_metrics(sv)
        server['threads'] = collect_thread_pool(sv)
        server['jdbc'] = collect_jdbc_metrics(sv)
        server['jms'] = collect_jms_metrics(sv)
        server['saf'] = collect_saf_agents(sv)
        results.append(server)
    return results

# ---------------------------------------------------------------------------
# HTML builder  - clean professional light theme, email-compatible inline CSS
# ---------------------------------------------------------------------------
def badge(text, color):
    return ('<span style="display:inline-block;padding:2px 10px;'
        'border-radius:4px;font-size:12px;font-weight:700;color:#fff;'
        'background:' + color + '">' + text + '</span>')

def progress_bar(pct, color):
    w = str(max(0, min(100, pct))) + '%'
    return ('<div style="background:#e5e7eb;border-radius:4px;height:8px;'
        'overflow:hidden;min-width:80px">'
        '<div style="width:' + w + ';height:8px;background:' + color
        + ';border-radius:4px"></div></div>')

def hcell(content, bg='#f8f9fa'):
    return '<th style="padding:8px 10px;font-size:11px;font-weight:700;' + (
        'color:#475569;text-transform:uppercase;text-align:left;background:' + bg + '">'
        + content + '</th>')

def dcell(content, color='#1e293b'):
    return '<td style="padding:8px 10px;font-size:13px;border-top:1px solid #e2e8f0;color:' + color + '">' + str(content) + '</td>'

def build_html_report(data):
    html = []
    html.append('<!DOCTYPE html>\n')
    html.append('<html><head><meta charset="UTF-8">')
    html.append('<title>WebLogic Health Report</title></head>\n')
    html.append('<body style="margin:0;padding:0;background:#f1f5f9;'
        'font-family:Arial,Helvetica,sans-serif;color:#1e293b">\n')

    # Outer container
    html.append('<table align="center" width="100%" cellpadding="0" cellspacing="0"'
        ' style="max-width:680px;margin:20px auto;background:#ffffff;'
        'border-radius:8px;overflow:hidden;border:1px solid #e2e8f0">\n')

    # Header
    from time import strftime as fmt_time
    ts = fmt_time('%Y-%m-%d %H:%M:%S')
    host = os.environ.get('COMPUTERNAME') or os.environ.get('HOSTNAME', 'localhost')
    sv_count = len(data)
    up_count = 0
    for s in data:
        if s.get('state') == 'RUNNING':
            up_count = up_count + 1
    html.append('<tr><td style="padding:24px 28px;background:#1e40af">\n')
    html.append('<table width="100%" cellpadding="0" cellspacing="0">\n')
    html.append('<tr>\n')
    html.append('<td style="font-size:22px;font-weight:700;color:#ffffff">'
        'WebLogic Domain Report</td>\n')
    html.append('<td style="text-align:right;font-size:12px;color:#93c5fd">\n')
    html.append('<div style="font-weight:600;color:#ffffff">' + host + '</div>\n')
    html.append('<div>' + ts + '</div>\n')
    html.append('</td>\n</tr>\n</table>\n')
    html.append('</td></tr>\n')

    # Summary bar
    html.append('<tr><td style="padding:16px 28px">\n')
    html.append('<table width="100%" cellpadding="0" cellspacing="0">\n')
    html.append('<tr>\n')
    html.append('<td style="width:25%;padding:14px 8px;text-align:center;'
        'background:#f8fafc;border-radius:6px;border:1px solid #e2e8f0">\n')
    html.append('<div style="font-size:26px;font-weight:700;color:#1e293b">' + str(sv_count) + '</div>\n')
    html.append('<div style="font-size:11px;color:#64748b">Servers</div>\n')
    html.append('</td>\n')
    if up_count == sv_count:
        running_color = '#16a34a'
    else:
        running_color = '#dc2626'
    html.append('<td style="width:25%;padding:14px 8px;text-align:center;'
        'background:#f8fafc;border-radius:6px;border:1px solid #e2e8f0">\n')
    html.append('<div style="font-size:26px;font-weight:700;color:' + running_color + '">' + str(up_count) + '</div>\n')
    html.append('<div style="font-size:11px;color:#64748b">Running</div>\n')
    html.append('</td>\n')
    total_ds = 0
    for s in data:
        total_ds = total_ds + len(s.get('jdbc', []))
    html.append('<td style="width:25%;padding:14px 8px;text-align:center;'
        'background:#f8fafc;border-radius:6px;border:1px solid #e2e8f0">\n')
    html.append('<div style="font-size:26px;font-weight:700;color:#1e293b">' + str(total_ds) + '</div>\n')
    html.append('<div style="font-size:11px;color:#64748b">Datasources</div>\n')
    html.append('</td>\n')
    total_jms = 0
    for s in data:
        total_jms = total_jms + len(s.get('jms', []))
    html.append('<td style="width:25%;padding:14px 8px;text-align:center;'
        'background:#f8fafc;border-radius:6px;border:1px solid #e2e8f0">\n')
    html.append('<div style="font-size:26px;font-weight:700;color:#1e293b">' + str(total_jms) + '</div>\n')
    html.append('<div style="font-size:11px;color:#64748b">JMS Servers</div>\n')
    html.append('</td>\n')
    html.append('</tr>\n</table>\n')
    html.append('</td></tr>\n')

    # Per-server sections
    for s in data:
        html.append('<tr><td style="padding:8px 28px 4px">\n')
        html.append('<div style="font-size:16px;font-weight:700;color:#1e293b">'
            + s['name'] + '</div>\n')
        state_color = '#16a34a'
        if s['state'] == 'SHUTDOWN' or s['state'] == 'FAILED':
            state_color = '#dc2626'
        elif s['state'] == 'ADMIN':
            state_color = '#f59e0b'
        if s['health'] == 'OK':
            health_color = '#10b981'
        else:
            health_color = '#dc2626'
        html.append('<div style="margin:4px 0 8px;font-size:12px;color:#64748b">'
            + badge(s['state'], state_color) + ' &nbsp; Health: '
            + badge(s['health'], health_color) + '</div>\n')
        html.append('</td></tr>\n')

        # JVM + CPU row
        j = s.get('jvm', {})
        html.append('<tr><td style="padding:0 28px">\n')
        html.append('<table width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #e2e8f0;border-radius:6px;overflow:hidden">\n')
        html.append('<tr>' + hcell('Metric', '#f1f5f9') + hcell('Value', '#f1f5f9') + '</tr>\n')
        hp = j.get('heap_pct', -1)
        if hp >= 0:
            hc = color_for_health(hp, 40, 20)
            html.append('<tr>' + dcell('Heap Free') + dcell(progress_bar(hp, hc) + ' ' + fmt_pct(hp)) + '</tr>\n')
            html.append('<tr>' + dcell('Heap Usage') + dcell(fmt_mb(j.get('heap_free')) + ' / ' + fmt_mb(j.get('heap_total'))) + '</tr>\n')
        else:
            html.append('<tr>' + dcell('Heap') + dcell('N/A', '#94a3b8') + '</tr>\n')
        cpu = j.get('cpu', -1)
        if cpu >= 0:
            cc = color_for_health(cpu, 50, 80, invert=True)
            html.append('<tr>' + dcell('CPU Load') + dcell(progress_bar(cpu, cc) + ' ' + fmt_pct(cpu)) + '</tr>\n')
        else:
            html.append('<tr>' + dcell('CPU Load') + dcell('N/A', '#94a3b8') + '</tr>\n')
        gc_list = j.get('gc_list', [])
        for gc in gc_list:
            html.append('<tr>' + dcell('GC: ' + gc['name']) + dcell(str(gc['count']) + ' collections, ' + str(gc['time']) + ' ms') + '</tr>\n')
        if not gc_list:
            html.append('<tr>' + dcell('GC Collections') + dcell('N/A', '#94a3b8') + '</tr>\n')

        # Thread pool
        tp = s.get('threads', {})
        if tp:
            html.append('<tr>' + dcell('Active Threads') + dcell(str(tp.get('active', 'N/A'))) + '</tr>\n')
            html.append('<tr>' + dcell('Idle Threads') + dcell(str(tp.get('idle', 'N/A'))) + '</tr>\n')
            html.append('<tr>' + dcell('Hogging Threads') + dcell(str(tp.get('hogging', 'N/A'))) + '</tr>\n')
            html.append('<tr>' + dcell('Stuck Threads') + dcell(str(tp.get('stuck', 'N/A'))) + '</tr>\n')
            html.append('<tr>' + dcell('Queue Length') + dcell(str(tp.get('queue', 'N/A'))) + '</tr>\n')
        html.append('</table>\n')
        html.append('</td></tr>\n')

        # JDBC section
        jdbc_list = s.get('jdbc', [])
        if jdbc_list:
            html.append('<tr><td style="padding:12px 28px 4px">\n')
            html.append('<div style="font-size:13px;font-weight:700;color:#1e293b">JDBC Data Sources</div>\n')
            html.append('</td></tr>\n')
            html.append('<tr><td style="padding:0 28px 4px">\n')
            html.append('<table width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #e2e8f0;border-radius:6px;overflow:hidden">\n')
            html.append('<tr>' + hcell('Name') + hcell('Active') + hcell('Leaked') + hcell('Wait (s)') + '</tr>\n')
            for ds in jdbc_list:
                lk = ds.get('leaked', -1)
                if isinstance(lk, (int, long)) and lk > 0:
                    lk_color = '#dc2626'
                else:
                    lk_color = '#1e293b'
                wa = ds.get('wait_high', -1)
                if isinstance(wa, (int, long)) and wa > 5:
                    wa_color = '#dc2626'
                else:
                    wa_color = '#1e293b'
                if lk >= 0:
                    lk_str = str(lk)
                else:
                    lk_str = 'N/A'
                if wa >= 0:
                    wa_str = str(wa)
                else:
                    wa_str = 'N/A'
                html.append('<tr>')
                html.append(dcell(ds['name']))
                html.append(dcell(str(ds.get('active', 'N/A'))))
                html.append(dcell(lk_str, lk_color))
                html.append(dcell(wa_str, wa_color))
                html.append('</tr>\n')
            html.append('</table>\n')
            html.append('</td></tr>\n')

        # JMS section
        jms_list = s.get('jms', [])
        if jms_list:
            html.append('<tr><td style="padding:12px 28px 4px">\n')
            html.append('<div style="font-size:13px;font-weight:700;color:#1e293b">JMS Servers</div>\n')
            html.append('</td></tr>\n')
            html.append('<tr><td style="padding:0 28px 4px">\n')
            html.append('<table width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #e2e8f0;border-radius:6px;overflow:hidden">\n')
            html.append('<tr>' + hcell('Name') + hcell('Current Msgs') + hcell('Pending Msgs') + '</tr>\n')
            for jms in jms_list:
                html.append('<tr>')
                html.append(dcell(jms['name']))
                html.append(dcell(str(jms.get('messages_cur', 'N/A'))))
                html.append(dcell(str(jms.get('messages_pending', 'N/A'))))
                html.append('</tr>\n')
                dests = jms.get('destinations', [])
                if dests:
                    html.append('<tr><td colspan="3" style="padding:0 8px 6px 28px">\n')
                    html.append('<table width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #e2e8f0;border-radius:4px;overflow:hidden;font-size:11px">\n')
                    html.append('<tr>' + hcell('Destination','#f1f5f9') + hcell('Cur','#f1f5f9') + hcell('Pending','#f1f5f9') + hcell('Con','#f1f5f9') + '</tr>\n')
                    for d in dests:
                        dn = d['name']
                        if len(dn) > 40:
                            dn = dn[:38] + '..'
                        html.append('<tr>')
                        html.append(dcell(dn))
                        html.append(dcell(str(d.get('messages_cur', 'N/A'))))
                        html.append(dcell(str(d.get('messages_pending', 'N/A'))))
                        html.append(dcell(str(d.get('consumers', 'N/A'))))
                        html.append('</tr>\n')
                    html.append('</table>\n')
                    html.append('</td></tr>\n')
            html.append('</table>\n')
            html.append('</td></tr>\n')

        # SAF agents
        saf_list = s.get('saf', [])
        if saf_list:
            html.append('<tr><td style="padding:12px 28px 4px">\n')
            html.append('<div style="font-size:13px;font-weight:700;color:#1e293b">SAF Agents</div>\n')
            html.append('</td></tr>\n')
            html.append('<tr><td style="padding:0 28px 4px">\n')
            html.append('<table width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #e2e8f0;border-radius:6px;overflow:hidden">\n')
            html.append('<tr>' + hcell('Name') + hcell('State') + hcell('Current Msgs') + hcell('Failed Total') + '</tr>\n')
            for saf in saf_list:
                html.append('<tr>')
                html.append(dcell(saf['name']))
                html.append(dcell(str(saf.get('state', 'N/A'))))
                html.append(dcell(str(saf.get('messages_cur', 'N/A'))))
                html.append(dcell(str(saf.get('failed_total', 'N/A'))))
                html.append('</tr>\n')
            html.append('</table>\n')
            html.append('</td></tr>\n')

    # Spacer
    html.append('<tr><td style="height:16px"></td></tr>\n')

    # Footer
    html.append('<tr><td style="padding:16px 28px;background:#f8fafc;'
        'border-top:1px solid #e2e8f0;text-align:center;font-size:11px;color:#94a3b8">')
    html.append('Generated by WLST &bull; WebLogic Health Monitor')
    html.append('</td></tr>\n')

    html.append('</table>\n')
    html.append('</body></html>\n')
    return ''.join(html)

# ---------------------------------------------------------------------------
# Email via javax.mail
# ---------------------------------------------------------------------------
class _EmailAuth(Authenticator):
    def getPasswordAuthentication(self):
        return PasswordAuthentication(SMTP_USER, SMTP_PASS)

def send_email(subject, body):
    if not SMTP_USER or not SMTP_PASS:
        print '  SMTP credentials not configured, skipping email.'
        return False
    try:
        from javax.mail import Session, Message, Transport, PasswordAuthentication
        from javax.mail.internet import InternetAddress, MimeMessage
        import java.util
        props = java.util.Properties()
        props.setProperty('mail.smtp.host', 'smtp.gmail.com')
        props.setProperty('mail.smtp.port', '587')
        props.setProperty('mail.smtp.auth', 'true')
        props.setProperty('mail.smtp.starttls.enable', 'true')
        props.setProperty('mail.smtp.connectiontimeout', '15000')
        props.setProperty('mail.smtp.timeout', '15000')
        sess = Session.getInstance(props, _EmailAuth())
        msg = MimeMessage(sess)
        msg.setFrom(InternetAddress(EMAIL_FROM))
        msg.setRecipient(Message.RecipientType.TO, InternetAddress(EMAIL_TO))
        msg.setSubject(subject)
        msg.setContent(body, 'text/html; charset=UTF-8')
        msg.saveChanges()
        Transport.send(msg)
        print '  Email sent to ' + EMAIL_TO
        return True
    except Exception, e:
        print '  EMAIL FAILED: ' + str(e)
        return False

# ---------------------------------------------------------------------------
# Report save
# ---------------------------------------------------------------------------
def save_report(html):
    from time import strftime as fmt_time
    fname = 'weblogic_report_' + fmt_time('%Y%m%d_%H%M') + '.html'
    fpath = os.path.join(os.environ.get('TEMP', os.environ.get('TMP', '.')), fname)
    f = open(fpath, 'w')
    f.write(html.encode('utf-8'))
    f.close()
    print '  Saved: ' + fpath
    return fpath

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def run_once():
    from time import strftime as fmt_time
    host = os.environ.get('COMPUTERNAME') or os.environ.get('HOSTNAME', 'localhost')
    print ''
    print '============================================================'
    print ' WebLogic Domain Health Check'
    print ' Target : ' + ADMIN_URL
    print ' Host   : ' + host
    print ' Time   : ' + fmt_time('%Y-%m-%d %H:%M:%S')
    print '============================================================'

    connect(ADMIN_USER, ADMIN_PASS, ADMIN_URL)
    domainRuntime()

    print '  Connected to domain'

    section('Metrics Collection')
    data = collect_all_servers()

    sv_up = 0
    for s in data:
        if s['state'] == 'RUNNING':
            sv_up = sv_up + 1
    print '  Servers: ' + str(len(data)) + ' (' + str(sv_up) + ' running)'
    ds_count = 0
    jms_count = 0
    for s in data:
        ds_count = ds_count + len(s.get('jdbc', []))
        jms_count = jms_count + len(s.get('jms', []))
    print '  Datasources: ' + str(ds_count)
    print '  JMS Servers: ' + str(jms_count)

    for s in data:
        print ''
        print '  ' + s['name'] + ' [' + s['state'] + '/' + s['health'] + ']'
        j = s.get('jvm', {})
        if j.get('heap_pct', -1) >= 0:
            print '    Heap: ' + fmt_pct(j['heap_pct']) + ' free (' + fmt_mb(j['heap_free']) + ' / ' + fmt_mb(j['heap_total']) + ')'
        if j.get('cpu', -1) >= 0:
            print '    CPU:  ' + fmt_pct(j['cpu'])
        tp = s.get('threads', {})
        if tp:
            print '    Threads: ' + str(tp.get('active', '?')) + ' total, ' + str(tp.get('idle', '?')) + ' idle, ' + str(tp.get('hogging', '?')) + ' hogging, ' + str(tp.get('stuck', '?')) + ' stuck, queue=' + str(tp.get('queue', '?'))
        for ds in s.get('jdbc', []):
            print '    DS ' + ds['name'] + ': active=' + str(ds.get('active', '?')) + ' leaked=' + str(ds.get('leaked', '?'))
        for jms in s.get('jms', []):
            print '    JMS ' + jms['name'] + ': cur=' + str(jms.get('messages_cur', '?')) + ' pending=' + str(jms.get('messages_pending', '?'))
            for d in jms.get('destinations', []):
                print '      DEST ' + d['name'] + ': cur=' + str(d.get('messages_cur', '?')) + ' pending=' + str(d.get('messages_pending', '?')) + ' consumers=' + str(d.get('consumers', '?'))
        for saf in s.get('saf', []):
            print '    SAF ' + saf['name'] + ': ' + str(saf.get('state', '?')) + ' cur=' + str(saf.get('messages_cur', '?')) + ' failed=' + str(saf.get('failed_total', '?'))

    disconnect()

    section('Report')
    html = build_html_report(data)
    rpath = save_report(html)

    section('Email')
    subject = 'WebLogic Health Report - ' + host + ' [' + str(sv_up) + '/' + str(len(data)) + ' running]'
    print '  SMTP smtp.gmail.com:587 ...'
    send_email(subject, html)

def run_daemon():
    print 'Daemon mode: checking every ' + str(INTERVAL) + ' seconds'
    print 'Press Ctrl+C to stop.'
    from time import sleep, strftime as fmt_time
    while True:
        try:
            run_once()
            sleep(INTERVAL)
            next_check = fmt_time('%Y-%m-%d %H:%M:%S')
            print ''
            print 'Next check at: ' + next_check
        except KeyboardInterrupt:
            print ''
            print 'Stopped by user.'
            break
        except Exception, e:
            print 'ERROR: ' + str(e)
            print 'Retrying in 60 seconds ...'
            sleep(60)

if __name__ in ('__main__', 'main'):
    _check_config()
    is_daemon = True
    for i, a in enumerate(sys.argv):
        if a == '--once':
            is_daemon = False
        if a == '--interval' and i + 1 < len(sys.argv):
            try:
                INTERVAL = int(sys.argv[i + 1])
            except:
                pass
    if is_daemon:
        run_daemon()
    else:
        run_once()
