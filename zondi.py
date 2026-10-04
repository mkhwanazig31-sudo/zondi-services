# zondi.py — ZONDI SECURE BACKEND — FIXED #1 NFC + #2 RADIO LAPTOP->PHONE
import os, time, jwt, datetime
from functools import wraps
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from flask_socketio import SocketIO, join_room, leave_room, emit

app = Flask(__name__, static_folder='.', static_url_path='')
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'zondi-super-secret-2025')
CORS(app, supports_credentials=True)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet', logger=False, engineio_logger=False)

# --- IN-MEMORY STORE (replace with Supabase/Postgres later) ---
clients_live = {} # user_id -> {user_id, name, email, lat, lng, time, channel}
sos_feed = []
patrol_scans = []
incidents = []
radio_history = [] # {channel, from, time, type}

JWT_SECRET = app.config['SECRET_KEY']

def make_token(user):
    payload = {
        'user_id': user['user_id'],
        'email': user['email'],
        'name': user.get('name',''),
        'role': user.get('role','patroller'),
        'exp': datetime.datetime.utcnow() + datetime.timedelta(days=7)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm='HS256')

def decode_token(req):
    auth = req.headers.get('Authorization','')
    if not auth.startswith('Bearer '): return None
    try:
        tok = auth.split(' ')[1]
        return jwt.decode(tok, JWT_SECRET, algorithms=['HS256'])
    except: return None

def auth_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        user = decode_token(request)
        if not user: return jsonify({'error':'unauthorized'}), 401
        request.user = user
        return f(*args, **kwargs)
    return wrapper

# --- USERS (demo) - your real login uses Supabase ---
DEMO_USERS = {
    'patroller@zondi.co.za': {'user_id':'p1','email':'patroller@zondi.co.za','name':'Patroller 1','role':'patroller','password':'zondi123'},
    'admin@zondi.co.za': {'user_id':'admin1','email':'admin@zondi.co.za','name':'Admin','role':'admin','password':'zondi123'}
}

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json or {}
    email = data.get('email','').lower()
    pwd = data.get('password','')
    u = DEMO_USERS.get(email)
    if not u or u['password']!=pwd:
        return jsonify({'error':'invalid credentials'}), 401
    tok = make_token(u)
    return jsonify({'token':tok, 'user':{'user_id':u['user_id'],'email':u['email'],'name':u['name'],'role':u['role']}})

# --- PATROLLER PING - LIVE LOCATION ---
@app.route('/api/patroller-ping', methods=['POST'])
@auth_required
def patroller_ping():
    data = request.json or {}
    uid = request.user['user_id']
    clients_live[uid] = {
        'user_id': uid,
        'name': request.user.get('name'),
        'email': request.user.get('email'),
        'lat': data.get('lat'),
        'lng': data.get('lng'),
        'acc': data.get('acc', 0),
        'time': datetime.datetime.utcnow().isoformat(),
        'channel': data.get('channel','1')
    }
    # broadcast to map
    socketio.emit('client:update', clients_live[uid])
    return jsonify({'ok':True})

@app.route('/api/location/live')
@auth_required
def live():
    return jsonify(list(clients_live.values()))

@app.route('/api/sos-feed')
@auth_required
def sos():
    return jsonify(sos_feed[-100:])

@app.route('/api/sos', methods=['POST'])
@auth_required
def create_sos():
    data = request.json or {}
    item = {
        'user_id': request.user['user_id'],
        'name': request.user.get('name'),
        'email': request.user.get('email'),
        'lat': data.get('lat'),
        'lng': data.get('lng'),
        'time': datetime.datetime.utcnow().isoformat(),
        'status': 'active',
        'msg': data.get('msg','SOS')
    }
    sos_feed.append(item)
    socketio.emit('sos:new', item)
    return jsonify({'ok':True, 'sos':item})

# --- PATROL SCAN ---
@app.route('/api/patrol-scan', methods=['POST'])
@auth_required
def patrol_scan():
    data = request.json or {}
    item = {
        'user_id': request.user['user_id'],
        'officer': data.get('officer'),
        'code': data.get('code'),
        'lat': data.get('lat'),
        'lng': data.get('lng'),
        'time': data.get('time') or datetime.datetime.utcnow().isoformat(),
        'acc': data.get('acc')
    }
    patrol_scans.append(item)
    socketio.emit('patrol:scan', item)
    return jsonify({'ok':True})

@app.route('/api/incident', methods=['POST'])
@auth_required
def incident():
    data = request.json or {}
    item = {
        'user_id': request.user['user_id'],
        'text': data.get('text'),
        'lat': data.get('lat'),
        'lng': data.get('lng'),
        'time': datetime.datetime.utcnow().isoformat()
    }
    incidents.append(item)
    return jsonify({'ok':True})

# ================= RADIO - FIX #2 LAPTOP -> PHONE =================
# Laptop and phone join same room "channel_1" etc, then any audio/text relays to whole room

@socketio.on('connect')
def on_connect(auth=None):
    # auth can be {token}
    token = None
    if auth and 'token' in auth: token = auth['token']
    else: token = request.args.get('token')
    if not token:
        # allow but mark offline
        return True
    try:
        user = jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
        request.user_id = user['user_id']
        print(f"[RADIO] connect {user['email']}")
    except Exception as e:
        print(f"[RADIO] connect bad token {e}")
    emit('connected', {'ok':True})
    return True

@socketio.on('join_channel')
def on_join_channel(data):
    try:
        channel = str(data.get('channel','1'))
        token = data.get('auth',{}).get('token') or (data.get('token'))
        user = None
        if token:
            try: user = jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
            except: pass
        room = f'channel_{channel}'
        join_room(room)
        print(f"[RADIO] {user['email'] if user else 'anon'} joined {room}")
        emit('channel:joined', {'channel':channel, 'room':room}, room=room)
        # announce presence
        socketio.emit('radio:presence', {'channel':channel, 'user': user, 'action':'joined'}, room=room)
    except Exception as e:
        print(f"join_channel err {e}")

@socketio.on('radio:ptt')
def on_ptt(data):
    # PTT start/stop event
    try:
        ch = str(data.get('channel','1'))
        room = f'channel_{ch}'
        # relay to everyone EXCEPT sender? we relay to ALL including sender for sync
        payload = {
            'channel': ch,
            'user_id': getattr(request, 'user_id', 'unknown'),
            'user': data.get('user'),
            'action': data.get('action','start'), # start / stop
            'time': datetime.datetime.utcnow().isoformat()
        }
        socketio.emit('radio:ptt', payload, room=room, include_self=False)
        print(f"[RADIO PTT] {payload}")
    except Exception as e:
        print(f"ptt err {e}")

@socketio.on('radio:audio')
def on_audio(data):
    # THIS IS THE FIX for laptop -> phone
    # data: {channel, audio (base64), user, type}
    try:
        ch = str(data.get('channel','1'))
        room = f'channel_{ch}'
        payload = {
            'channel': ch,
            'audio': data.get('audio'),
            'from': data.get('user') or getattr(request, 'user_id', 'unknown'),
            'time': datetime.datetime.utcnow().isoformat(),
            'type': data.get('type','audio/webm')
        }
        # BROADCAST TO ROOM - this makes laptop audio reach phones in same channel
        socketio.emit('radio:audio', payload, room=room, include_self=False)
        # also legacy event for old frontend
        socketio.emit('radio:rx', payload, room=room, include_self=False)
        print(f"[RADIO AUDIO] relayed to {room} len={len(payload.get('audio',''))}")
    except Exception as e:
        print(f"radio:audio err {e}")

@socketio.on('radio:text')
def on_text(data):
    try:
        ch = str(data.get('channel','1'))
        room = f'channel_{ch}'
        payload = {
            'channel': ch,
            'text': data.get('text'),
            'from': data.get('user'),
            'time': datetime.datetime.utcnow().isoformat()
        }
        socketio.emit('radio:text', payload, room=room, include_self=False)
        radio_history.append(payload)
    except Exception as e:
        print(f"radio:text err {e}")

@socketio.on('yanton_key')
def on_yanton_key(data):
    # YANTON side button maps to PTT
    try:
        ch = str(data.get('channel','1'))
        room = f'channel_{ch}'
        socketio.emit('yanton_key', data, room=room, include_self=False)
    except: pass

# --- STATIC ---
@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/patrol')
def patrol():
    return send_from_directory('.', 'patrol.html')

@app.route('/assets/<path:path>')
def assets(path):
    return send_from_directory('assets', path)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"ZONDI SECURE running on {port} — RADIO FIX #2 ENABLED")
    socketio.run(app, host='0.0.0.0', port=port)
