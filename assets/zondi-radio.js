import os, time, uuid
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, send_from_directory
from functools import wraps
import jwt

app = Flask(__name__, static_folder='assets', static_url_path='/assets')

SECRET = os.getenv('JWT_SECRET','zondi-secret-dev')
DEV_PASS = os.getenv('DEV_PORTAL_PASSWORD','')

# In-memory — works on Render, Vercel resets but ok for now
USERS = {}
LOCATIONS = {}
RADIOS = {}
RADIO_FEED = []
SOS_FEED = []
PENDING_RESETS = []

def make_token(user):
    payload = {
        "email": user['email'],
        "role": user.get('role','client'),
        "name": user.get('name',''),
        "exp": datetime.utcnow()+timedelta(days=7)
    }
    return jwt.encode(payload, SECRET, algorithm="HS256")

def decode_token(t):
    try:
        return jwt.decode(t, SECRET, algorithms=["HS256"])
    except:
        return None

def get_auth():
    h = request.headers.get('Authorization','')
    if h.startswith('Bearer '):
        return decode_token(h[7:])
    c = request.cookies.get('zondi_token')
    if c:
        return decode_token(c)
    return None

def require_auth(f):
    @wraps(f)
    def w(*a,**k):
        u = get_auth()
        if not u:
            return jsonify({"ok":False,"error":"Unauthorized"}), 401
        request.user = u
        return f(*a,**k)
    return w

# ---- PAGES ----
@app.route('/')
def idx():
    return send_from_directory('.', 'index.html')

@app.route('/<path:p>')
def pages(p):
    if p.startswith('assets/'):
        return send_from_directory('.', p)
    name = p.replace('.html','').split('/')[0]
    for cand in [p, f"{name}.html", 'index.html']:
        try:
            return send_from_directory('.', cand)
        except:
            continue
    return send_from_directory('.', 'index.html')

# ---- AUTH ----
@app.route('/api/register', methods=['POST'])
def reg():
    d = request.get_json() or {}
    email = d.get('email','').lower().strip()
    if not email or not d.get('password'):
        return jsonify({"ok":False,"error":"Missing"}), 400
    if email in USERS:
        return jsonify({"ok":False,"error":"Exists"}), 400
    role = d.get('role','client')
    status = 'pending' if role == 'patroller' else 'approved'
    USERS[email] = {
        "email": email,
        "name": d.get('name',email),
        "password": d.get('password'),
        "role": role,
        "status": status,
        "phone": d.get('phone','')
    }
    return jsonify({"ok":True})

@app.route('/api/login', methods=['POST'])
def login():
    d = request.get_json() or {}
    email = d.get('email','').lower().strip()
    u = USERS.get(email)
    if not u or u['password']!= d.get('password'):
        return jsonify({"ok":False,"error":"Invalid credentials"}), 401
    if u['role'] == 'patroller' and u['status']!= 'approved':
        return jsonify({"ok":False,"error":"Patroller pending approval"}), 403
    return jsonify({
        "ok": True,
        "token": make_token(u),
        "user": {"email": u['email'], "name": u['name'], "role": u['role']}
    })

@app.route('/api/me')
@require_auth
def me():
    u = USERS.get(request.user['email'].lower())
    if not u:
        return jsonify({"ok":False}), 404
    return jsonify({"ok":True,"user":u})

@app.route('/api/logout', methods=['POST'])
def logout():
    return jsonify({"ok":True})

@app.route('/api/dev-login', methods=['POST'])
def dev_login():
    d = request.get_json() or {}
    if not DEV_PASS:
        return jsonify({"ok":False,"error":"Dev not configured"}), 503
    if d.get('password')!= DEV_PASS:
        return jsonify({"ok":False,"error":"Wrong password"}), 401
    tok = jwt.encode({
        "email":"dev@zondi.local","role":"dev","name":"Developer",
        "exp": datetime.utcnow()+timedelta(days=1)
    }, SECRET, algorithm="HS256")
    return jsonify({"ok":True,"token":tok,"redirect":"/dev"})

@app.route('/api/dev-logout', methods=['POST'])
def dev_logout():
    return jsonify({"ok":True})

# ---- LOCATION WITH STALE FILTER FIX ----
@app.route('/api/location/update', methods=['POST'])
@require_auth
def loc_up():
    d = request.get_json() or {}
    email = request.user['email'].lower()
    LOCATIONS[email] = {
        "lat": d.get('lat'), "lng": d.get('lng'),
        "time": time.time(),
        "email": email,
        "name": request.user.get('name', email),
        "accuracy": d.get('accuracy')
    }
    return jsonify({"ok":True})

@app.route('/api/location/live')
@require_auth
def loc_live():
    now = time.time()
    live = []
    for k,v in list(LOCATIONS.items()):
        if now - v['time'] < 90: # show only if active in last 90s
            live.append(v)
        elif now - v['time'] > 300: # purge after 5min
            LOCATIONS.pop(k,None)
    return jsonify({"ok":True,"locations":live})

@app.route('/api/sos', methods=['POST'])
@require_auth
def sos():
    d = request.get_json() or {}
    SOS_FEED.append({
        "email": request.user['email'],
        "name": request.user.get('name'),
        "lat": d.get('lat'), "lng": d.get('lng'),
        "time": time.time()
    })
    return jsonify({"ok":True})

@app.route('/api/sos-feed')
@require_auth
def sos_feed():
    return jsonify(SOS_FEED[-30:])

# ---- RADIO NET REAL PRESENCE + WAVES ----
@app.route('/api/radio/presence', methods=['POST'])
@require_auth
def radio_presence():
    d = request.get_json() or {}
    email = request.user['email'].lower()
    now = time.time()
    RADIOS[email] = {
        "email": email,
        "name": request.user.get('name',email),
        "last_seen": now,
        "tx": bool(d.get('tx'))
    }
    # purge offline >20s
    for k,v in list(RADIOS.items()):
        if now - v['last_seen'] > 20:
            RADIOS.pop(k,None)
    others = [v for k,v in RADIOS.items() if k!= email]
    return jsonify({"ok":True,"radios":others,"connected":len(RADIOS)})

@app.route('/api/radio/push', methods=['POST'])
@require_auth
def radio_push():
    f = request.files.get('audio')
    if not f:
        return jsonify({"ok":False,"error":"No audio"}), 400
    fid = str(uuid.uuid4())+".webm"
    f.save(f"/tmp/{fid}")
    RADIO_FEED.append({
        "name": request.user.get('name'),
        "email": request.user['email'],
        "time": time.time(),
        "url": f"/api/radio/audio/{fid}"
    })
    if len(RADIO_FEED) > 30:
        RADIO_FEED.pop(0)
    sent_to = len([v for k,v in RADIOS.items() if k!= request.user['email'].lower()])
    return jsonify({"ok":True,"sent_to":sent_to})

@app.route('/api/radio/audio/<fid>')
def radio_audio(fid):
    return send_from_directory("/tmp", fid)

@app.route('/api/radio/feed')
@require_auth
def radio_feed():
    return jsonify({"ok":True,"items":RADIO_FEED[-20:]})

@app.route('/api/patrol-scan', methods=['POST'])
@require_auth
def scan():
    return jsonify({"ok":True})

@app.route('/api/incident', methods=['POST'])
@require_auth
def inc():
    return jsonify({"ok":True})

@app.route('/api/forgot-password', methods=['POST'])
def forgot():
    d = request.get_json() or {}
    PENDING_RESETS.append({
        "email": d.get('email','').lower(),
        "requested_at": datetime.utcnow().isoformat(),
        "status": "pending"
    })
    return jsonify({"ok":True,"message":"If that email exists, a reset request was created."})

@app.route('/api/admin/pending')
@require_auth
def admin_pending():
    if request.user.get('role')!= 'dev':
        return jsonify({"ok":False}), 403
    all_p = [v for v in USERS.values() if v['role']=='patroller']
    return jsonify({
        "ok": True,
        "pending": [v for v in all_p if v['status']=='pending'],
        "all_patrollers": all_p
    })

@app.route('/api/admin/approve', methods=['POST'])
@require_auth
def admin_approve():
    if request.user.get('role')!= 'dev':
        return jsonify({"ok":False}), 403
    d = request.get_json() or {}
    email = d.get('email','').lower()
    act = d.get('action')
    u = USERS.get(email)
    if not u:
        return jsonify({"ok":False,"error":"Not found"}), 404
    if act == 'approve': u['status']='approved'
    elif act == 'reject': USERS.pop(email,None)
    elif act == 'revoke': u['status']='pending'
    return jsonify({"ok":True})

@app.route('/api/admin/password-reset-requests')
@require_auth
def pw_list():
    if request.user.get('role')!= 'dev':
        return jsonify({"ok":False}), 403
    return jsonify({"ok":True,"requests":PENDING_RESETS[-20:]})

@app.route('/api/admin/password-reset', methods=['POST'])
@require_auth
def pw_reset():
    if request.user.get('role')!= 'dev':
        return jsonify({"ok":False}), 403
    d = request.get_json() or {}
    email = d.get('email','').lower()
    u = USERS.get(email)
    if u:
        u['password'] = d.get('password')
        return jsonify({"ok":True})
    return jsonify({"ok":False,"error":"Not found"}), 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT',5000)))
