"""
Zondi API v3 - PTT Radio like Eter T2770 + Dev Portal Approval
Install: pip install flask flask-cors flask-socketio eventlet
Run: python zondi_v3.py
"""

from flask import Flask, request, jsonify, send_from_directory, session, redirect
from flask_cors import CORS
from flask_socketio import SocketIO, emit, join_room, leave_room
import json, os, threading
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
import uuid

app = Flask(__name__, static_folder='.')
app.config['SECRET_KEY'] = os.environ.get(
    'SECRET_KEY',
    'zondi-secret-change-me'
)
app.permanent_session_lifetime = timedelta(hours=8)
CORS(app, resources={r"/api/*": {"origins": "*"}})
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet', logger=False)

DEV_TOKEN_MAX_AGE = 8 * 60 * 60
dev_token_serializer = URLSafeTimedSerializer(
    app.config['SECRET_KEY'],
    salt='zondi-dev-portal-v4'
)

FILES = {
    'sos': 'sos_feed.json',
    'users': 'users.json',
    'patrollers': 'patrollers_live.json',
    'voice': 'radio_talk.json'
}
file_lock = threading.Lock()
# Track who is talking on which channel (T2770 logic: only 1 talker per channel)
active_talkers = {}  # channel -> {email, started_at}
channel_lock = threading.Lock()

def load_json(f):
    if not os.path.exists(f): return []
    try:
        with file_lock:
            with open(f, 'r', encoding='utf-8') as fh:
                d=json.load(fh)
                return d if isinstance(d,list) else []
    except: return []

def save_json(f,data):
    with file_lock:
        tmp=f+'.tmp'
        with open(tmp,'w',encoding='utf-8') as fh:
            json.dump(data,fh,indent=2)
        os.replace(tmp,f)

def init_files():
    for f in FILES.values():
        if not os.path.exists(f): save_json(f, [])

def sanitize_user(u):
    return {k:v for k,v in u.items() if k!='password'}

# ===== PAGES =====
@app.route('/')
def home(): return send_from_directory('.', 'login.html') if os.path.exists('login.html') else jsonify({"name":"Zondi API v3 - T2770 Radio","status":"running"})

for route in ['/login','/login.html','/register','/register.html','/clients','/clients.html','/patrollers','/patrol','/patrollers.html','/patrol.html','/admin','/admin.html','/dev','/dev.html','/radio','/radio.html']:
    @app.route(route, endpoint=route)
    def page_handler(route=route):
        # strip leading /
        fname = route.strip('/').split('.')[0] + '.html'
        # Developer Portal page shell can be loaded directly.
        # Its data/actions are protected by the developer token/session APIs.

        # map /dev and /admin to dev_portal.html if exists
        if fname in ['admin.html','dev.html']:
            if os.path.exists('dev_portal.html'): return send_from_directory('.', 'dev_portal.html')
            if os.path.exists('admin.html'): return send_from_directory('.', 'admin.html')
        if os.path.exists(fname): return send_from_directory('.', fname)
        # fallback
        base = fname.split('/')[0]
        if os.path.exists(base): return send_from_directory('.', base)
        return send_from_directory('.', 'login.html') if os.path.exists('login.html') else (f"Missing {fname}",404)

# ===== AUTH - WITH APPROVAL STATUS =====
@app.route('/api/signup', methods=['POST'])
@app.route('/api/register', methods=['POST'])
def api_reg():
    d=request.get_json(silent=True) or {}
    email=d.get('email','').lower().strip()
    pwd=d.get('password','')
    role=d.get('role','client').lower()

    if not email or not pwd: return jsonify({"error":"Email and password required"}),400
    if len(pwd)<6: return jsonify({"error":"Password min 6 chars"}),400

    users=load_json(FILES['users'])
    if any(x.get('email','').lower()==email for x in users):
        return jsonify({"error":"Email already registered"}),400

    new_user={
        "id": str(uuid.uuid4()),
        "email": email,
        "password": generate_password_hash(pwd),
        "role": role,
        "name": d.get('name',''),
        "phone": d.get('phone',''),
        "status": "approved" if role=='client' else "pending", # clients auto-approved, patrollers need YOU
        "created_at": datetime.now().isoformat()
    }
    users.append(new_user)
    save_json(FILES['users'], users)
    return jsonify({"ok":True,"user":sanitize_user(new_user),"message":"Patroller account pending approval by admin" if role=='patroller' else "Registered"}),201

@app.route('/api/login', methods=['POST'])
def api_login():
    d=request.get_json(silent=True) or {}
    email=d.get('email','').lower().strip()
    pwd=d.get('password','')
    users=load_json(FILES['users'])
    u=next((x for x in users if x.get('email','').lower()==email),None)
    if not u or not check_password_hash(u.get('password',''), pwd):
        # legacy plain support
        if u and u.get('password','')==pwd:
            u['password']=generate_password_hash(pwd)
            save_json(FILES['users'], users)
        else:
            return jsonify({"error":"Wrong email or password"}),401
    
    # CHECK APPROVAL
    if u.get('role')=='patroller' and u.get('status')!='approved':
        return jsonify({"error":f"Account {u.get('status')}. Wait for admin approval","status":u.get('status')}),403

    return jsonify(sanitize_user(u))

# ===== DEVELOPER PORTAL AUTH =====
def create_dev_token():
    return dev_token_serializer.dumps({
        "scope": "developer",
        "v": 4,
    })


def token_from_request():
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        return header[7:].strip()
    return ""


def token_authenticated():
    token = token_from_request()
    if not token:
        return False

    try:
        payload = dev_token_serializer.loads(
            token,
            max_age=DEV_TOKEN_MAX_AGE,
        )
        return payload.get("scope") == "developer"
    except (BadSignature, SignatureExpired, TypeError, ValueError):
        return False


@app.route('/api/dev-login', methods=['POST'])
def dev_login():
    d = request.get_json(silent=True) or {}
    password = str(d.get('password', ''))

    expected_password = os.environ.get('DEV_PORTAL_PASSWORD', '')
    if not expected_password:
        return jsonify({
            "error": "Developer portal password is not configured on the server"
        }), 503

    if password != expected_password:
        session.clear()
        return jsonify({"error": "Incorrect developer password"}), 401

    session.clear()
    session.permanent = True
    session['dev_authenticated'] = True
    session['dev_login_at'] = datetime.now().isoformat()
    session.modified = True

    return jsonify({
        "ok": True,
        "authenticated": True,
        "token": create_dev_token(),
        "expires_in": DEV_TOKEN_MAX_AGE,
        "redirect": "/dev"
    })


@app.route('/api/dev-status', methods=['GET'])
def dev_status():
    authenticated = (
        session.get('dev_authenticated') is True
        or token_authenticated()
    )

    return jsonify({
        "authenticated": authenticated,
        "login_at": session.get('dev_login_at'),
    })


@app.route('/api/dev-logout', methods=['POST'])
def dev_logout():
    session.clear()
    return jsonify({"ok": True})


def require_dev_auth():
    if session.get('dev_authenticated') is True:
        return None

    if token_authenticated():
        return None

    return jsonify({
        "error": "developer authentication required"
    }), 401


# ===== DEV PORTAL - APPROVE PATROLLERS =====
@app.route('/api/admin/pending')
def admin_pending():
    auth_error = require_dev_auth()
    if auth_error:
        return auth_error
    users=load_json(FILES['users'])
    pending=[sanitize_user(x) for x in users if x.get('role')=='patroller' and x.get('status')=='pending']
    all_patrollers=[sanitize_user(x) for x in users if x.get('role')=='patroller']
    return jsonify({"pending":pending,"all_patrollers":all_patrollers})

@app.route('/api/admin/approve', methods=['POST'])
def admin_approve():
    auth_error = require_dev_auth()
    if auth_error:
        return auth_error

    d=request.get_json(silent=True) or {}
    email=d.get('email','').lower().strip()
    action=d.get('action','approve') # approve / reject / revoke
    users=load_json(FILES['users'])
    found=False
    for u in users:
        if u.get('email','').lower()==email and u.get('role')=='patroller':
            if action=='approve': u['status']='approved'
            elif action=='reject': u['status']='rejected'
            elif action=='revoke': u['status']='pending'
            found=True
    if not found: return jsonify({"error":"patroller not found"}),404
    save_json(FILES['users'], users)
    return jsonify({"ok":True,"action":action,"email":email})

# ===== SOS & TRACKING (same as before, thread-safe) =====
@app.route('/api/sos', methods=['POST'])
def api_sos():
    data=request.get_json(silent=True) or {}
    if not data.get('phoneId'): return jsonify({"error":"phoneId required"}),400
    data['id']=str(uuid.uuid4()); data['time']=datetime.now().isoformat()
    feed=load_json(FILES['sos']); feed.append(data)
    if len(feed)>1000: feed=feed[-1000:]
    save_json(FILES['sos'], feed)
    # BROADCAST SOS LIVE TO ALL PATROLLERS
    socketio.emit('new_sos', data, room='patrollers_room')
    return jsonify({"ok":True,"id":data['id']})

@app.route('/api/sos-feed')
def api_feed():
    return jsonify(load_json(FILES['sos'])[-300:])

@app.route('/api/tracking/<phone_id>')
def api_tracking(phone_id):
    feed=load_json(FILES['sos'])
    return jsonify([x for x in feed if x.get('phoneId')==phone_id and x.get('lat')][-100:])

@app.route('/api/patroller-ping', methods=['POST'])
def pp():
    d=request.get_json(silent=True) or {}
    if not d.get('email'): return jsonify({"error":"email required"}),400
    d['time']=datetime.now().isoformat(); d['email']=d['email'].lower().strip()
    # check if approved patroller
    users=load_json(FILES['users'])
    u=next((x for x in users if x.get('email','').lower()==d['email'] and x.get('role')=='patroller' and x.get('status')=='approved'),None)
    if not u: return jsonify({"error":"Not an approved patroller"}),403

    data=load_json(FILES['patrollers'])
    data=[x for x in data if x.get('email')!=d.get('email')]
    data.append(d)
    save_json(FILES['patrollers'], data)
    socketio.emit('patroller_update', d, room='patrollers_room')
    return jsonify({"ok":True})

@app.route('/api/patrollers-live')
def pl():
    data=load_json(FILES['patrollers'])
    cutoff=datetime.now()-timedelta(minutes=5)
    fresh=[]
    for p in data:
        try:
            if datetime.fromisoformat(p.get('time',''))>cutoff: fresh.append(p)
        except: pass
    return jsonify(fresh)

# ===== T2770 STYLE PTT RADIO - SOCKET.IO =====
@socketio.on('join_channel')
def handle_join(data):
    channel=str(data.get('channel','1'))
    email=data.get('email','anonymous')
    join_room(f"channel_{channel}")
    join_room('patrollers_room')
    emit('channel_joined', {"channel":channel,"email":email}, room=request.sid)
    # notify others
    emit('user_joined_channel', {"channel":channel,"email":email}, room=f"channel_{channel}", include_self=False)
    print(f"{email} joined channel {channel}")

@socketio.on('leave_channel')
def handle_leave(data):
    channel=str(data.get('channel','1'))
    leave_room(f"channel_{channel}")
    emit('user_left_channel', {"channel":channel,"email":data.get('email')}, room=f"channel_{channel}")

@socketio.on('ptt_start')
def handle_ptt_start(data):
    channel=str(data.get('channel','1'))
    email=data.get('email','')
    with channel_lock:
        current=active_talkers.get(channel)
        if current and (datetime.now() - current['started_at']).seconds < 30:
            # Channel busy - T2770 behavior
            emit('channel_busy', {"channel":channel,"busy_by":current['email']}, room=request.sid)
            return
        # Claim channel
        active_talkers[channel]={"email":email,"started_at":datetime.now()}
    
    emit('ptt_started', {"channel":channel,"email":email}, room=f"channel_{channel}", include_self=False)
    emit('ptt_granted', {"channel":channel}, room=request.sid)

@socketio.on('ptt_audio')
def handle_ptt_audio(data):
    # data: {channel, audio (base64), email}
    channel=str(data.get('channel','1'))
    # only allow if this user owns the channel
    with channel_lock:
        owner=active_talkers.get(channel)
        if not owner or owner['email']!=data.get('email'):
            emit('ptt_denied', {"reason":"not owner"}, room=request.sid)
            return
    # Broadcast audio chunk to everyone in channel except sender
    emit('audio_chunk', data, room=f"channel_{channel}", include_self=False)

@socketio.on('ptt_end')
def handle_ptt_end(data):
    channel=str(data.get('channel','1'))
    email=data.get('email','')
    with channel_lock:
        owner=active_talkers.get(channel)
        if owner and owner['email']==email:
            del active_talkers[channel]
    emit('ptt_ended', {"channel":channel,"email":email}, room=f"channel_{channel}", include_self=False)
    emit('ptt_released', {"channel":channel}, room=request.sid)

# Keep old HTTP radio for text messages
@app.route('/api/radio/talk', methods=['POST','GET'])
def radio_http():
    if request.method=='POST':
        d=request.get_json(silent=True) or {}
        d['id']=str(uuid.uuid4()); d['time']=datetime.now().isoformat()
        feed=load_json(FILES['voice']); feed.append(d)
        if len(feed)>50: feed=feed[-50:]
        save_json(FILES['voice'], feed)
        socketio.emit('text_message', d, room=f"channel_{d.get('channel','1')}")
        return jsonify({"ok":True})
    else:
        channel=request.args.get('channel')
        feed=load_json(FILES['voice'])[-20:]
        if channel: feed=[x for x in feed if str(x.get('channel'))==str(channel)]
        return jsonify(feed)

if __name__=='__main__':
    init_files()
    print("Zondi v3 - T2770 Radio Running")
    print("Developer Portal: protected by DEV_PORTAL_PASSWORD")
    print("Dev portal: /dev.html or /admin.html")
    print("Radio: /radio.html")
    socketio.run(app, host='0.0.0.0', port=int(os.environ.get('PORT',10000)), debug=False)
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no">
  <meta name="theme-color" content="#07100b">
  <meta name="color-scheme" content="dark">
  <title>Zondi — Developer Portal</title>
  <style>
    :root{
      --bg:#050806;--surface:#0b110d;--surface2:#101812;--surface3:#151e17;
      --border:rgba(255,255,255,.07);--border2:rgba(255,255,255,.11);
      --text:#f5f8f6;--muted:#8b9690;--green:#22c55e;--green2:#4ade80;
      --red:#ef4444;--amber:#f59e0b;--radius:18px
    }
    *{box-sizing:border-box;margin:0;padding:0;font-family:Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif;-webkit-tap-highlight-color:transparent}
    body{min-height:100vh;background:radial-gradient(circle at 10% -5%,rgba(34,197,94,.11),transparent 28%),var(--bg);color:var(--text)}
    button{font:inherit;cursor:pointer}
    .topbar{position:sticky;top:0;z-index:20;display:flex;align-items:center;justify-content:space-between;padding:13px 16px;background:rgba(7,12,8,.95);backdrop-filter:blur(18px);border-bottom:1px solid var(--border)}
    .brand{display:flex;align-items:center;gap:11px}.logo{width:40px;height:40px;border-radius:13px;display:flex;align-items:center;justify-content:center;background:linear-gradient(145deg,var(--green2),#16a34a);color:#03200b;font-size:18px;box-shadow:0 8px 20px rgba(34,197,94,.16)}
    .brand-title{font-size:14px;font-weight:900;letter-spacing:.08em}.brand-sub{margin-top:3px;color:var(--muted);font-size:10px}
    .logout{border:1px solid rgba(239,68,68,.14);background:rgba(239,68,68,.06);color:#ffaaaa;border-radius:10px;padding:9px 11px;font-size:10px;font-weight:800}
    .page{width:min(900px,100%);margin:0 auto;padding:18px 14px 40px}
    .hero{padding:18px;border:1px solid rgba(34,197,94,.12);border-radius:22px;background:radial-gradient(circle at 100% 0%,rgba(34,197,94,.10),transparent 38%),linear-gradient(145deg,#101a12,#09100b);box-shadow:0 20px 45px rgba(0,0,0,.18);margin-bottom:14px}
    .hero-title{font-size:21px;font-weight:900;letter-spacing:-.03em}.hero-copy{margin-top:6px;color:var(--muted);font-size:11px;line-height:1.5}
    .stats{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-top:14px}.stat{padding:11px;border-radius:14px;border:1px solid var(--border);background:rgba(255,255,255,.025)}.stat-value{font-size:18px;font-weight:900}.stat-label{margin-top:3px;color:var(--muted);font-size:8px;font-weight:700;text-transform:uppercase;letter-spacing:.06em}
    .section{margin-top:14px;padding:15px;border-radius:20px;border:1px solid var(--border);background:rgba(255,255,255,.025)}
    .section-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:11px}.section-title{font-size:13px;font-weight:900}.section-sub{margin-top:3px;color:var(--muted);font-size:9px}
    .refresh{border:1px solid var(--border);background:rgba(255,255,255,.035);color:#dce5df;border-radius:10px;width:34px;height:34px}
    .user-card{display:flex;gap:11px;align-items:flex-start;padding:12px;border-radius:15px;border:1px solid var(--border);background:rgba(255,255,255,.025);margin-bottom:8px}.avatar{width:40px;height:40px;flex:0 0 40px;border-radius:12px;display:flex;align-items:center;justify-content:center;background:rgba(34,197,94,.10);font-size:15px;font-weight:900;color:#bbf7d0}.info{min-width:0;flex:1}.name{font-size:12px;font-weight:900;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.email{margin-top:3px;color:#aeb8b2;font-size:9px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.meta{margin-top:5px;color:var(--muted);font-size:8px}.actions{display:flex;flex-wrap:wrap;gap:7px;margin-top:9px}.btn{border:0;border-radius:9px;padding:8px 10px;font-size:9px;font-weight:900}.approve{background:linear-gradient(135deg,var(--green2),#16a34a);color:#03200b}.reject{background:rgba(239,68,68,.07);border:1px solid rgba(239,68,68,.16);color:#ffadad}.revoke{background:rgba(245,158,11,.07);border:1px solid rgba(245,158,11,.16);color:#fcd34d}.badge{display:inline-flex;padding:4px 7px;border-radius:999px;font-size:7px;font-weight:900;text-transform:uppercase;letter-spacing:.06em}.pending{background:rgba(245,158,11,.10);color:#fcd34d}.approved{background:rgba(34,197,94,.10);color:#bbf7d0}.rejected{background:rgba(239,68,68,.10);color:#fecaca}
    .empty{padding:28px 16px;border-radius:15px;border:1px dashed var(--border2);background:rgba(255,255,255,.015);text-align:center;color:var(--muted)}.empty-icon{font-size:28px;margin-bottom:8px}.empty-title{color:#dfe7e1;font-size:11px;font-weight:900}.empty-copy{margin-top:4px;font-size:9px;line-height:1.5}
    .notice{padding:11px 12px;border-radius:13px;background:rgba(34,197,94,.06);border:1px solid rgba(34,197,94,.10);color:#b8ebc8;font-size:9px;line-height:1.5;margin-top:10px}
    .toast{position:fixed;left:50%;bottom:18px;z-index:1000;width:min(calc(100% - 28px),460px);padding:12px 14px;border-radius:13px;background:rgba(13,20,15,.97);border:1px solid var(--border2);box-shadow:0 18px 45px rgba(0,0,0,.35);font-size:10px;font-weight:700;transform:translate(-50%,15px);opacity:0;pointer-events:none;transition:.2s}.toast.show{opacity:1;transform:translate(-50%,0)}.toast.error{border-color:rgba(239,68,68,.25);color:#ffb0b0}
    @media(max-width:560px){.stats{grid-template-columns:1fr 1fr 1fr}.user-card{align-items:flex-start}.actions .btn{flex:1}.topbar{padding-left:12px;padding-right:12px}}
  </style>
</head>
<body>
  <header class="topbar">
    <div class="brand">
      <div class="logo">🛡️</div>
      <div><div class="brand-title">ZONDI</div><div class="brand-sub">Developer Portal</div></div>
    </div>
    <button class="logout" onclick="logout()">Sign out</button>
  </header>

  <main class="page">
    <section class="hero">
      <div class="hero-title">Patroller management</div>
      <div class="hero-copy">Approve trusted patrollers, review their status, and manage access to the Zondi response network.</div>
      <div class="stats">
        <div class="stat"><div class="stat-value" id="pendingCount">—</div><div class="stat-label">Pending</div></div>
        <div class="stat"><div class="stat-value" id="approvedCount">—</div><div class="stat-label">Approved</div></div>
        <div class="stat"><div class="stat-value" id="totalCount">—</div><div class="stat-label">Total</div></div>
      </div>
      <div class="notice">Approved patrollers stay approved until you explicitly reject or revoke them. Their existing email and password remain their login credentials.</div>
    </section>

    <section class="section">
      <div class="section-head">
        <div><div class="section-title">Pending approvals</div><div class="section-sub">New patrollers waiting for access</div></div>
        <button class="refresh" onclick="loadPortal()" aria-label="Refresh">↻</button>
      </div>
      <div id="pendingList"></div>
    </section>

    <section class="section">
      <div class="section-head">
        <div><div class="section-title">All patrollers</div><div class="section-sub">Current account status</div></div>
      </div>
      <div id="allList"></div>
    </section>
  </main>

  <div id="toast" class="toast"></div>

  <script>
    const pendingList = document.getElementById('pendingList');
    const allList = document.getElementById('allList');

    function devHeaders(extra = {}) {
      const token = sessionStorage.getItem('zondi_dev_token');
      const headers = Object.assign({}, extra);
      if (token) headers['Authorization'] = `Bearer ${token}`;
      return headers;
    }

    function clearDevTokenAndLogin() {
      sessionStorage.removeItem('zondi_dev_token');
      window.location.href = '/login?dev=1';
    }

    function escapeHtml(value) {
      return String(value ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#039;');
    }

    function initial(name, email) {
      const v = String(name || email || 'P').trim();
      return (v[0] || 'P').toUpperCase();
    }

    function formatDate(value) {
      if (!value) return 'Recently joined';
      const d = new Date(value);
      if (Number.isNaN(d.getTime())) return 'Recently joined';
      return d.toLocaleDateString([], { day:'numeric', month:'short', year:'numeric' });
    }

    function badge(status) {
      const cls = status === 'approved' ? 'approved' : status === 'rejected' ? 'rejected' : 'pending';
      return `<span class="badge ${cls}">${escapeHtml(status || 'pending')}</span>`;
    }

    function userCard(user, pendingOnly=false) {
      const name = escapeHtml(user.name || user.email || 'Patroller');
      const email = escapeHtml(user.email || '');
      const phone = escapeHtml(user.phone || 'No phone provided');
      const status = user.status || 'pending';

      let actions = '';
      if (pendingOnly || status === 'pending' || status === 'rejected') {
        actions += `<button class="btn approve" onclick="act('${encodeURIComponent(user.email)}','approve',this)">Approve</button>`;
      }
      if (pendingOnly || status === 'pending') {
        actions += `<button class="btn reject" onclick="act('${encodeURIComponent(user.email)}','reject',this)">Reject</button>`;
      }
      if (status === 'approved') {
        actions += `<button class="btn revoke" onclick="act('${encodeURIComponent(user.email)}','revoke',this)">Revoke access</button>`;
      }

      return `
        <article class="user-card">
          <div class="avatar">${escapeHtml(initial(user.name, user.email))}</div>
          <div class="info">
            <div class="name">${name}</div>
            <div class="email">${email}</div>
            <div class="meta">📞 ${phone} · Joined ${formatDate(user.created_at)}</div>
            <div style="margin-top:7px">${badge(status)}</div>
            <div class="actions">${actions}</div>
          </div>
        </article>`;
    }

    function renderUsers(pending, all) {
      document.getElementById('pendingCount').textContent = pending.length;
      document.getElementById('approvedCount').textContent = all.filter(u => u.status === 'approved').length;
      document.getElementById('totalCount').textContent = all.length;

      if (!pending.length) {
        pendingList.innerHTML = `<div class="empty"><div class="empty-icon">✨</div><div class="empty-title">All caught up</div><div class="empty-copy">There are no patrollers waiting for approval.</div></div>`;
      } else {
        pendingList.innerHTML = pending.map(u => userCard(u, true)).join('');
      }

      if (!all.length) {
        allList.innerHTML = `<div class="empty"><div class="empty-icon">👮</div><div class="empty-title">No patrollers yet</div><div class="empty-copy">Approved and pending patroller accounts will appear here.</div></div>`;
      } else {
        allList.innerHTML = all.map(u => userCard(u)).join('');
      }
    }

    async function loadPortal() {
      pendingList.innerHTML = `<div class="empty"><div class="empty-icon">⏳</div><div class="empty-title">Loading</div><div class="empty-copy">Checking patroller accounts…</div></div>`;
      allList.innerHTML = '';

      try {
        const res = await fetch('/api/admin/pending', { headers: devHeaders() });
        const data = await res.json().catch(() => ({}));
        if (res.status === 401 || res.status === 403) {
          clearDevTokenAndLogin();
          return;
        }
        if (!res.ok) throw new Error(data.error || 'Unable to load the portal.');
        renderUsers(data.pending || [], data.all_patrollers || []);
      } catch (err) {
        pendingList.innerHTML = `<div class="empty"><div class="empty-icon">⚠️</div><div class="empty-title">Portal unavailable</div><div class="empty-copy">${escapeHtml(err.message)}</div></div>`;
      }
    }

    async function act(encodedEmail, action, button) {
      const email = decodeURIComponent(encodedEmail);
      const original = button.textContent;
      button.disabled = true;
      button.textContent = '…';

      try {
        const res = await fetch('/api/admin/approve', {
          method:'POST',
          headers:devHeaders({'Content-Type':'application/json'}),
          body:JSON.stringify({ email, action })
        });

        const data = await res.json().catch(() => ({}));
        if (res.status === 401 || res.status === 403) {
          clearDevTokenAndLogin();
          return;
        }
        if (!res.ok || !data.ok) throw new Error(data.error || 'Action failed.');

        if (action === 'approve') showToast(`${email} is now approved.`);
        if (action === 'reject') showToast(`${email} was rejected.`);
        if (action === 'revoke') showToast(`${email} access was revoked.`);
        await loadPortal();
      } catch (err) {
        button.disabled = false;
        button.textContent = original;
        showToast(err.message, true);
      }
    }

    async function logout() {
      try {
        await fetch('/api/dev-logout', {
          method:'POST',
          headers:devHeaders()
        });
      } catch {}
      sessionStorage.removeItem('zondi_dev_token');
      window.location.href = '/login';
    }

    function showToast(message, error=false) {
      const el = document.getElementById('toast');
      el.textContent = message;
      el.classList.toggle('error', error);
      el.classList.add('show');
      clearTimeout(showToast.timer);
      showToast.timer = setTimeout(() => el.classList.remove('show'), 2800);
    }

    loadPortal();
    setInterval(loadPortal, 30000);
  </script>
</body>
</html>

<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta
    name="viewport"
    content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no"
  >

  <meta name="theme-color" content="#07100b">
  <meta name="color-scheme" content="dark">

  <title>Zondi — Login</title>

  <style>
    :root {
      --bg: #050806;
      --bg-soft: #09110c;
      --card: rgba(13, 20, 15, 0.88);
      --card-border: rgba(255, 255, 255, 0.08);

      --green: #22c55e;
      --green-light: #4ade80;
      --green-dark: #16a34a;

      --text: #f8fafc;
      --muted: #8b949e;
      --muted-2: #667078;

      --danger: #ff6b6b;
      --danger-bg: rgba(127, 29, 29, 0.18);

      --warning: #fbbf24;
      --warning-bg: rgba(120, 53, 15, 0.18);

      --input: rgba(255, 255, 255, 0.045);
      --input-focus: rgba(34, 197, 94, 0.08);

      --radius-xl: 28px;
      --radius-lg: 18px;
      --radius-md: 14px;
    }

    * {
      box-sizing: border-box;
      margin: 0;
      padding: 0;
      -webkit-tap-highlight-color: transparent;
    }

    html {
      min-height: 100%;
      background: var(--bg);
    }

    body {
      min-height: 100vh;
      min-height: 100dvh;
      font-family:
        Inter,
        ui-sans-serif,
        system-ui,
        -apple-system,
        BlinkMacSystemFont,
        "Segoe UI",
        sans-serif;
      color: var(--text);
      background:
        radial-gradient(
          circle at 50% -10%,
          rgba(34, 197, 94, 0.14),
          transparent 38%
        ),
        radial-gradient(
          circle at 100% 100%,
          rgba(22, 163, 74, 0.08),
          transparent 32%
        ),
        var(--bg);

      display: flex;
      align-items: center;
      justify-content: center;

      padding: 22px;
      overflow-x: hidden;
    }

    /* Decorative glow */
    body::before {
      content: "";
      position: fixed;
      width: 280px;
      height: 280px;
      border-radius: 50%;
      top: -150px;
      right: -100px;
      background: rgba(34, 197, 94, 0.08);
      filter: blur(50px);
      pointer-events: none;
    }

    body::after {
      content: "";
      position: fixed;
      width: 240px;
      height: 240px;
      border-radius: 50%;
      bottom: -150px;
      left: -90px;
      background: rgba(34, 197, 94, 0.05);
      filter: blur(55px);
      pointer-events: none;
    }

    .page {
      width: 100%;
      max-width: 430px;
      position: relative;
      z-index: 2;
    }

    .shell {
      width: 100%;
      padding: 30px;
      border-radius: var(--radius-xl);
      border: 1px solid var(--card-border);
      background:
        linear-gradient(
          180deg,
          rgba(255, 255, 255, 0.025),
          rgba(255, 255, 255, 0)
        ),
        var(--card);

      backdrop-filter: blur(24px);
      -webkit-backdrop-filter: blur(24px);

      box-shadow:
        0 30px 70px rgba(0, 0, 0, 0.42),
        inset 0 1px 0 rgba(255, 255, 255, 0.025);
    }

    /* Top decorative bar */
    .top-line {
      width: 62px;
      height: 4px;
      margin: 0 auto 28px;
      border-radius: 999px;
      background: linear-gradient(
        90deg,
        var(--green-dark),
        var(--green-light)
      );
      box-shadow: 0 0 22px rgba(34, 197, 94, 0.35);
    }

    .brand {
      text-align: center;
      margin-bottom: 28px;
    }

    .logo-wrap {
      width: 78px;
      height: 78px;
      margin: 0 auto 17px;
      border-radius: 23px;

      display: flex;
      align-items: center;
      justify-content: center;

      background:
        linear-gradient(
          145deg,
          rgba(74, 222, 128, 0.24),
          rgba(22, 163, 74, 0.11)
        );

      border: 1px solid rgba(74, 222, 128, 0.18);

      box-shadow:
        0 18px 38px rgba(34, 197, 94, 0.11),
        inset 0 1px 0 rgba(255, 255, 255, 0.07);
    }

    .logo {
      width: 46px;
      height: 46px;
      border-radius: 15px;

      display: flex;
      align-items: center;
      justify-content: center;

      font-size: 25px;

      background: linear-gradient(
        145deg,
        var(--green-light),
        var(--green-dark)
      );

      box-shadow:
        0 9px 22px rgba(34, 197, 94, 0.28),
        inset 0 1px 0 rgba(255, 255, 255, 0.25);
    }

    .brand h1 {
      font-size: 27px;
      line-height: 1;
      letter-spacing: 0.12em;
      font-weight: 900;
      margin-bottom: 10px;
    }

    .brand p {
      color: var(--muted);
      font-size: 13px;
      line-height: 1.5;
    }

    .brand p strong {
      color: #b6f3c9;
      font-weight: 700;
    }

    /* Status messages */
    .status {
      display: none;
      margin-bottom: 15px;
      padding: 13px 14px;
      border-radius: var(--radius-md);
      font-size: 13px;
      line-height: 1.45;
    }

    .status.show {
      display: block;
      animation: slideDown 0.25s ease;
    }

    .status.error {
      color: #ffb4b4;
      background: var(--danger-bg);
      border: 1px solid rgba(255, 107, 107, 0.2);
    }

    .status.pending {
      color: #fde68a;
      background: var(--warning-bg);
      border: 1px solid rgba(251, 191, 36, 0.18);
    }

    /* Form */
    .form {
      display: grid;
      gap: 14px;
    }

    .field {
      display: grid;
      gap: 8px;
    }

    .field-label {
      font-size: 12px;
      color: #aab3ba;
      font-weight: 700;
      padding-left: 3px;
    }

    .input-wrap {
      min-height: 55px;
      display: flex;
      align-items: center;

      padding: 0 15px;

      border-radius: var(--radius-md);
      border: 1px solid rgba(255, 255, 255, 0.075);
      background: var(--input);

      transition:
        border-color 0.2s ease,
        background 0.2s ease,
        box-shadow 0.2s ease,
        transform 0.2s ease;
    }

    .input-wrap:focus-within {
      border-color: rgba(34, 197, 94, 0.6);
      background: var(--input-focus);
      box-shadow:
        0 0 0 4px rgba(34, 197, 94, 0.08),
        0 10px 25px rgba(0, 0, 0, 0.12);
    }

    .input-icon {
      width: 20px;
      margin-right: 11px;
      opacity: 0.62;
      font-size: 16px;
      flex-shrink: 0;
    }

    .input-wrap input {
      width: 100%;
      min-width: 0;

      border: 0;
      outline: 0;
      background: transparent;
      color: var(--text);

      font: inherit;
      font-size: 14px;
      padding: 16px 0;
    }

    .input-wrap input::placeholder {
      color: #59636b;
    }

    .password-toggle {
      border: 0;
      background: transparent;
      color: #7f898f;
      cursor: pointer;
      font-size: 15px;
      padding: 7px;
      border-radius: 9px;
      transition: 0.2s ease;
      flex-shrink: 0;
    }

    .password-toggle:hover {
      color: var(--green-light);
      background: rgba(255, 255, 255, 0.05);
    }

    .login-btn {
      width: 100%;
      min-height: 56px;

      margin-top: 4px;

      border: 0;
      border-radius: var(--radius-md);

      background: linear-gradient(
        135deg,
        var(--green-light),
        var(--green-dark)
      );

      color: #031107;

      font-size: 15px;
      font-weight: 900;
      letter-spacing: 0.01em;

      cursor: pointer;

      box-shadow:
        0 14px 30px rgba(34, 197, 94, 0.18),
        inset 0 1px 0 rgba(255, 255, 255, 0.28);

      transition:
        transform 0.18s ease,
        box-shadow 0.18s ease,
        filter 0.18s ease;
    }

    .login-btn:hover {
      transform: translateY(-1px);
      filter: brightness(1.04);
      box-shadow:
        0 18px 34px rgba(34, 197, 94, 0.22),
        inset 0 1px 0 rgba(255, 255, 255, 0.28);
    }

    .login-btn:active {
      transform: translateY(1px) scale(0.995);
    }

    .login-btn:disabled {
      cursor: not-allowed;
      opacity: 0.72;
      transform: none;
    }

    .btn-content {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 10px;
    }

    .spinner {
      width: 16px;
      height: 16px;
      border: 2px solid rgba(3, 17, 7, 0.25);
      border-top-color: #031107;
      border-radius: 50%;
      animation: spin 0.7s linear infinite;
      display: none;
    }

    .login-btn.loading .spinner {
      display: block;
    }

    .login-btn.loading .btn-text {
      opacity: 0.85;
    }

    /* Developer Portal */
    .dev-access { margin-top: 15px; text-align: center; }
    .dev-access button { border: 1px solid rgba(255,255,255,.06); background: rgba(255,255,255,.025); color: #69736d; font-size: 11px; font-weight: 800; cursor: pointer; padding: 9px 13px; border-radius: 11px; transition: .2s ease; }
    .dev-access button:hover { color: var(--green-light); background: rgba(34,197,94,.06); border-color: rgba(34,197,94,.12); transform: translateY(-1px); }
    .dev-modal { position: fixed; inset: 0; z-index: 9999; display: none; align-items: center; justify-content: center; padding: 20px; }
    .dev-modal.show { display: flex; }
    .dev-overlay { position: absolute; inset: 0; background: rgba(0,0,0,.72); backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px); }
    .dev-card { width: 100%; max-width: 360px; position: relative; z-index: 2; padding: 26px; border-radius: 24px; border: 1px solid rgba(255,255,255,.09); background: linear-gradient(145deg, rgba(20,29,22,.98), rgba(8,13,9,.98)); box-shadow: 0 30px 80px rgba(0,0,0,.55); animation: devIn .2s ease; }
    .dev-close { position: absolute; top: 14px; right: 14px; width: 32px; height: 32px; border-radius: 9px; border: 1px solid rgba(255,255,255,.07); background: rgba(255,255,255,.035); color: #9ba59f; cursor: pointer; }
    .dev-icon { width: 52px; height: 52px; display: flex; align-items: center; justify-content: center; border-radius: 15px; margin-bottom: 15px; background: rgba(34,197,94,.1); font-size: 21px; }
    .dev-card h2 { font-size: 20px; font-weight: 900; margin-bottom: 6px; }
    .dev-card p { color: #7f8a83; font-size: 11px; line-height: 1.5; margin-bottom: 18px; }
    .dev-error { display: none; padding: 10px 12px; margin-bottom: 10px; border-radius: 11px; background: rgba(127,29,29,.18); border: 1px solid rgba(239,68,68,.18); color: #ffaaaa; font-size: 11px; }
    .dev-error.show { display: block; }
    .dev-input { min-height: 52px; display: flex; align-items: center; gap: 10px; padding: 0 14px; border-radius: 13px; border: 1px solid rgba(255,255,255,.07); background: rgba(255,255,255,.04); margin-bottom: 10px; }
    .dev-input span { opacity: .65; }
    .dev-input input { width: 100%; border: 0; outline: 0; background: transparent; color: white; font-size: 13px; }
    .dev-input input::placeholder { color: #5e6861; }
    .dev-login-button { width: 100%; min-height: 52px; border: 0; border-radius: 13px; background: linear-gradient(135deg, #4ade80, #16a34a); color: #03200b; font-size: 12px; font-weight: 900; cursor: pointer; box-shadow: 0 12px 25px rgba(34,197,94,.15); transition: transform .18s ease, filter .18s ease; }
    .dev-login-button:hover { transform: translateY(-1px); filter: brightness(1.04); }
    .dev-login-button:disabled { opacity: .7; cursor: wait; transform: none; }
    @keyframes devIn { from { opacity: 0; transform: translateY(10px) scale(.98); } to { opacity: 1; transform: translateY(0) scale(1); } }

    /* Footer */
    .footer {
      margin-top: 20px;
      text-align: center;
      color: var(--muted);
      font-size: 13px;
    }

    .footer a {
      color: var(--green-light);
      font-weight: 800;
      text-decoration: none;
      transition: color 0.2s ease;
    }

    .footer a:hover {
      color: #86efac;
    }

    .security-note {
      display: flex;
      justify-content: center;
      align-items: center;
      gap: 7px;

      margin-top: 22px;
      padding-top: 18px;

      border-top: 1px solid rgba(255, 255, 255, 0.055);

      color: #5f696f;
      font-size: 11px;
    }

    .security-dot {
      width: 6px;
      height: 6px;
      border-radius: 50%;
      background: var(--green);
      box-shadow: 0 0 10px rgba(34, 197, 94, 0.6);
    }

    @keyframes slideDown {
      from {
        opacity: 0;
        transform: translateY(-5px);
      }

      to {
        opacity: 1;
        transform: translateY(0);
      }
    }

    @keyframes spin {
      to {
        transform: rotate(360deg);
      }
    }

    @media (max-width: 480px) {
      body {
        padding: 14px;
      }

      .shell {
        padding: 24px 19px 20px;
        border-radius: 24px;
      }

      .logo-wrap {
        width: 72px;
        height: 72px;
      }

      .brand h1 {
        font-size: 25px;
      }
    }

    @media (min-width: 700px) {
      .shell {
        padding: 36px;
      }
    }

    @media (prefers-reduced-motion: reduce) {
      *,
      *::before,
      *::after {
        animation-duration: 0.001ms !important;
        animation-iteration-count: 1 !important;
        transition-duration: 0.001ms !important;
      }
    }
  </style>
</head>

<body>
  <main class="page">
    <section class="shell" aria-label="Zondi login">

      <div class="top-line"></div>

      <div class="brand">
        <div class="logo-wrap">
          <div class="logo" aria-hidden="true">🛡️</div>
        </div>

        <h1>ZONDI</h1>

        <p>
          Community safety for
          <strong>Ga-Rankuwa</strong>
        </p>
      </div>

      <div id="err" class="status error" role="alert"></div>
      <div id="pending" class="status pending" role="alert"></div>

      <form class="form" id="loginForm">

        <div class="field">
          <label class="field-label" for="email">Email address</label>

          <div class="input-wrap">
            <span class="input-icon" aria-hidden="true">✉</span>

            <input
              id="email"
              name="email"
              type="email"
              autocomplete="email"
              placeholder="you@example.com"
              required
            >
          </div>
        </div>

        <div class="field">
          <label class="field-label" for="password">Password</label>

          <div class="input-wrap">
            <span class="input-icon" aria-hidden="true">🔒</span>

            <input
              id="password"
              name="password"
              type="password"
              autocomplete="current-password"
              placeholder="Enter your password"
              required
            >

            <button
              class="password-toggle"
              type="button"
              id="togglePassword"
              aria-label="Show password"
              title="Show password"
            >
              👁
            </button>
          </div>
        </div>

        <button
          class="login-btn"
          id="loginBtn"
          type="submit"
        >
          <span class="btn-content">
            <span class="spinner"></span>
            <span class="btn-text">Sign in <span aria-hidden="true">→</span></span>
          </span>
        </button>

      </form>

      <div class="footer">
        Don't have an account?
        <a href="/register">Create one</a>
      </div>

      <div class="dev-access">
        <button type="button" id="openDevBtn">
          ⚙️ Developer Portal
        </button>
      </div>

      <div class="security-note">
        <span class="security-dot"></span>
        Secure Zondi community access
      </div>

    </section>
  </main>

  <div id="devModal" class="dev-modal" aria-hidden="true">
    <div id="devOverlay" class="dev-overlay"></div>
    <div class="dev-card" role="dialog" aria-modal="true" aria-labelledby="devTitle">
      <button class="dev-close" type="button" id="closeDevBtn" aria-label="Close developer portal">✕</button>
      <div class="dev-icon">⚙️</div>
      <h2 id="devTitle">Developer Portal</h2>
      <p>Authorized Zondi administration access.</p>
      <div id="devError" class="dev-error" role="alert"></div>
      <div class="dev-input">
        <span aria-hidden="true">🔐</span>
        <input id="devPassword" type="password" placeholder="Developer password" autocomplete="current-password">
      </div>
      <button id="devLoginButton" class="dev-login-button" type="button">Enter Developer Portal →</button>
    </div>
  </div>

  <script>
    const form = document.getElementById("loginForm");
    const emailInput = document.getElementById("email");
    const passwordInput = document.getElementById("password");
    const togglePassword = document.getElementById("togglePassword");

    const loginBtn = document.getElementById("loginBtn");
    const errorBox = document.getElementById("err");
    const pendingBox = document.getElementById("pending");

    function hideMessages() {
      errorBox.classList.remove("show");
      pendingBox.classList.remove("show");
      errorBox.textContent = "";
      pendingBox.textContent = "";
    }

    function showError(message) {
      pendingBox.classList.remove("show");
      errorBox.textContent = message || "Something went wrong.";
      errorBox.classList.add("show");
    }

    function showPending(message) {
      errorBox.classList.remove("show");
      pendingBox.textContent =
        message || "Your patroller account is waiting for approval.";
      pendingBox.classList.add("show");
    }

    function setLoading(loading) {
      loginBtn.disabled = loading;
      loginBtn.classList.toggle("loading", loading);

      if (loading) {
        loginBtn.querySelector(".btn-text").textContent = "Signing in…";
      } else {
        loginBtn.querySelector(".btn-text").innerHTML =
          'Sign in <span aria-hidden="true">→</span>';
      }
    }

    togglePassword.addEventListener("click", () => {
      const visible = passwordInput.type === "text";

      passwordInput.type = visible ? "password" : "text";

      togglePassword.textContent = visible ? "👁" : "🙈";
      togglePassword.setAttribute(
        "aria-label",
        visible ? "Show password" : "Hide password"
      );
      togglePassword.setAttribute(
        "title",
        visible ? "Show password" : "Hide password"
      );
    });

    form.addEventListener("submit", async (event) => {
      event.preventDefault();

      hideMessages();

      const email = emailInput.value.trim().toLowerCase();
      const password = passwordInput.value;

      if (!email || !password) {
        showError("Please enter your email and password.");
        return;
      }

      setLoading(true);

      try {
        const response = await fetch("/api/login", {
          method: "POST",
          headers: {
            "Content-Type": "application/json"
          },
          body: JSON.stringify({
            email,
            password
          })
        });

        let data = {};

        try {
          data = await response.json();
        } catch {
          data = {};
        }

        if (!response.ok) {
          if (response.status === 403) {
            showPending(
              data.error ||
              `Account ${data.status || "pending"}. Wait for admin approval.`
            );
          } else {
            showError(
              data.error ||
              "Unable to sign in. Please check your details and try again."
            );
          }

          return;
        }

        /*
          Your Flask backend returns the sanitized user object directly:
          {
            id,
            email,
            role,
            name,
            phone,
            status,
            created_at
          }

          Store it so the other frontend pages can identify the
          currently logged-in user.
        */
        localStorage.setItem("zondi_user", JSON.stringify(data));
        localStorage.setItem("zondi_email", data.email || email);

        /*
          Route according to the role already returned by Flask.
        */
        switch (data.role) {
          case "patroller":
            window.location.href = "/patrol";
            break;

          case "admin":
            window.location.href = "/admin";
            break;

          case "client":
          default:
            window.location.href = "/clients";
            break;
        }

      } catch (error) {
        console.error("Login error:", error);

        showError(
          "Unable to connect to Zondi. Please check your connection and try again."
        );
      } finally {
        setLoading(false);
      }
    });

    const devModal = document.getElementById("devModal");
    const openDevBtn = document.getElementById("openDevBtn");
    const closeDevBtn = document.getElementById("closeDevBtn");
    const devOverlay = document.getElementById("devOverlay");
    const devPassword = document.getElementById("devPassword");
    const devError = document.getElementById("devError");
    const devLoginButton = document.getElementById("devLoginButton");

    function openDevPortal() {
      devError.classList.remove("show");
      devError.textContent = "";
      devPassword.value = "";
      devModal.classList.add("show");
      devModal.setAttribute("aria-hidden", "false");
      setTimeout(() => devPassword.focus(), 100);
    }

    function closeDevPortal() {
      devModal.classList.remove("show");
      devModal.setAttribute("aria-hidden", "true");
      devError.classList.remove("show");
      devError.textContent = "";
    }

    async function developerLogin() {
      const password = devPassword.value;
      devError.classList.remove("show");
      devError.textContent = "";
      if (!password) {
        devError.textContent = "Enter the developer password.";
        devError.classList.add("show");
        devPassword.focus();
        return;
      }
      devLoginButton.disabled = true;
      devLoginButton.textContent = "Checking access…";
      try {
        const response = await fetch("/api/dev-login", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ password })
        });
        let data = {};
        try { data = await response.json(); } catch { data = {}; }
        if (!response.ok) throw new Error(data.error || "Developer access denied.");

        if (!data.token) {
          throw new Error("Developer token was not returned by the server.");
        }

        sessionStorage.setItem("zondi_dev_token", data.token);

        const verify = await fetch("/api/dev-status", {
          method: "GET",
          headers: {
            "Authorization": `Bearer ${data.token}`
          }
        });

        const status = await verify.json().catch(() => ({}));

        if (!verify.ok || !status.authenticated) {
          sessionStorage.removeItem("zondi_dev_token");
          throw new Error(
            status.error || "Developer access could not be verified."
          );
        }

        window.location.href = data.redirect || "/dev";
      } catch (error) {
        console.error("Developer login error:", error);
        devError.textContent = error.message || "Unable to access the developer portal.";
        devError.classList.add("show");
      } finally {
        devLoginButton.disabled = false;
        devLoginButton.textContent = "Enter Developer Portal →";
      }
    }

    openDevBtn.addEventListener("click", openDevPortal);
    closeDevBtn.addEventListener("click", closeDevPortal);
    devOverlay.addEventListener("click", closeDevPortal);
    devLoginButton.addEventListener("click", developerLogin);
    devPassword.addEventListener("keydown", event => {
      if (event.key === "Enter") developerLogin();
      if (event.key === "Escape") closeDevPortal();
    });
    document.addEventListener("keydown", event => {
      if (event.key === "Escape" && devModal.classList.contains("show")) closeDevPortal();
    });

    // Small UX improvement: focus email when page opens.
    window.addEventListener("load", () => {
      emailInput.focus();
    });
  </script>
</body>
</html>
