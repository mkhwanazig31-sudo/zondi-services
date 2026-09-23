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
from werkzeug.utils import safe_join
import uuid

app = Flask(__name__, static_folder='.')
app.config['SECRET_KEY'] = os.environ.get(
    'SECRET_KEY',
    'zondi-secret-change-me'
)
app.permanent_session_lifetime = timedelta(hours=8)
CORS(app, resources={r"/api/*": {"origins": "*"}})
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet', logger=False)

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
        # Developer Portal requires a server-side session.
        # The password itself is never stored in this HTML/JS.
        if route in ['/dev','/dev.html','/admin','/admin.html']:
            if not session.get('dev_authenticated'):
                return redirect('/login?dev=1')

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
@app.route('/api/dev-login', methods=['POST'])
def dev_login():
    d = request.get_json(silent=True) or {}
    password = d.get('password', '')

    expected_password = os.environ.get('DEV_PORTAL_PASSWORD', '')
    if not expected_password:
        return jsonify({
            "error": "Developer portal password is not configured on the server"
        }), 503

    if password != expected_password:
        return jsonify({"error": "Incorrect developer password"}), 401

    session.permanent = True
    session['dev_authenticated'] = True

    return jsonify({
        "ok": True,
        "redirect": "/dev"
    })


@app.route('/api/dev-logout', methods=['POST'])
def dev_logout():
    session.pop('dev_authenticated', None)
    return jsonify({"ok": True})


def require_dev_auth():
    if not session.get('dev_authenticated'):
        return jsonify({
            "error": "developer authentication required"
        }), 401
    return None


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
