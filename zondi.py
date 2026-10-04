# zondi.py — ZONDI SECURE — VERCEL SAFE + RADIO POLLING (NO SUSPEND)
# Fixes: 500 error + tabs not clicking + radio laptop->phone signal
import os, jwt, datetime
from functools import wraps
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

app = Flask(__name__, static_folder='.', static_url_path='')
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'zondi-super-secret-2025-GV-Mkhwanazi')
CORS(app, supports_credentials=True, resources={r"/api/*": {"origins": "*"}})

# --- STORES (use Supabase later, but works now) ---
clients_live = {} # user_id -> {lat,lng,name,email,time}
sos_feed = [] # list of SOS
patrol_scans = [] # QR/NFC scans
incidents = [] # incident reports
radio_messages = [] # NEW: radio voice clips {channel,audio,from,time}

JWT_SECRET = app.config['SECRET_KEY']

# --- AUTH HELPERS ---
def decode_token(req):
    auth = req.headers.get('Authorization','')
    if not auth.startswith('Bearer '): return None
    try:
        tok = auth.split(' ')[1]
        return jwt.decode(tok, JWT_SECRET, algorithms=['HS256'])
    except Exception as e:
        print(f"token decode fail {e}")
        return None

def auth_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        user = decode_token(request)
        if not user:
            return jsonify({'error':'unauthorized'}), 401
        request.user = user
        return f(*args, **kwargs)
    return wrapper

# --- LOGIN ---
@app.route('/api/login', methods=['POST'])
def login():
    data = request.json or {}
    email = data.get('email','').lower().strip()
    # DEMO - replace with Supabase real check
    # Accept any email for now so patrol never blocks
    user = {
        'user_id': email.replace('@','_').replace('.','_'),
        'email': email,
        'name': data.get('name') or email.split('@')[0],
        'role': 'patroller' if 'patrol' in email or 'guard' in email else 'admin'
    }
    if 'patrol' in email or 'guard' in email or 'zondi' in email:
        user['role'] = 'patroller'
    # admin check
    if 'admin' in email:
        user['role'] = 'admin'
    payload = {**user, 'exp': datetime.datetime.utcnow() + datetime.timedelta(days=7)}
    token = jwt.encode(payload, JWT_SECRET, algorithm='HS256')
    return jsonify({'token': token, 'user': user})

# --- LIVE LOCATION ---
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
    return jsonify({'ok': True})

@app.route('/api/location/live')
@auth_required
def live():
    return jsonify(list(clients_live.values()))

# --- SOS ---
@app.route('/api/sos-feed')
@auth_required
def sos_feed_route():
    return jsonify(sos_feed[-50:])

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
        'msg': data.get('msg','SOS ALERT')
    }
    sos_feed.append(item)
    return jsonify({'ok': True, 'sos': item})

# --- PATROL QR/NFC SCAN ---
@app.route('/api/patrol-scan', methods=['POST'])
@auth_required
def patrol_scan():
    data = request.json or {}
    item = {
        'user_id': request.user['user_id'],
        'officer': data.get('officer') or request.user.get('email'),
        'code': data.get('code'),
        'lat': data.get('lat'),
        'lng': data.get('lng'),
        'acc': data.get('acc'),
        'time': data.get('time') or datetime.datetime.utcnow().isoformat()
    }
    patrol_scans.append(item)
    return jsonify({'ok': True})

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
    return jsonify({'ok': True})

# ================= RADIO POLLING - WORKS ON VERCEL (NO SOCKET) =================
# Laptop uploads audio, phones poll every 1.5s - you still get BEEP + voice + LIVE badge

@app.route('/api/radio/upload', methods=['POST', 'OPTIONS'])
@auth_required
def radio_upload():
    if request.method == 'OPTIONS':
        return jsonify({'ok': True})
    data = request.json or {}
    if not data.get('audio'):
        return jsonify({'error':'no audio'}), 400
    msg = {
        'id': len(radio_messages) + 1,
        'channel': str(data.get('channel','1')),
        'audio': data.get('audio'), # base64 data:audio/webm;base64,...
        'from': data.get('from') or request.user.get('name') or request.user.get('email'),
        'from_email': request.user.get('email'),
        'time': datetime.datetime.utcnow().isoformat(),
        'type': data.get('type','audio/webm')
    }
    radio_messages.append(msg)
    # keep only last 100 to save memory
    if len(radio_messages) > 100:
        radio_messages.pop(0)
    print(f"[RADIO] CH{msg['channel']} from {msg['from']} len={len(msg['audio'])}")
    return jsonify({'ok': True, 'id': msg['id']})

@app.route('/api/radio/feed')
@auth_required
def radio_feed():
    ch = str(request.args.get('channel','1'))
    # optional since param for polling
    since = request.args.get('since', '0')
    try: since_id = int(since)
    except: since_id = 0
    filtered = [m for m in radio_messages if m['channel']==ch and m['id'] > since_id]
    # return last 15 max
    return jsonify(filtered[-15:])

@app.route('/api/radio/history')
@auth_required
def radio_history():
    ch = str(request.args.get('channel','1'))
    filtered = [m for m in radio_messages if m['channel']==ch][-20:]
    # don't return full audio in history list to save bandwidth, just meta
    meta = [{'id':m['id'],'from':m['from'],'time':m['time'],'channel':m['channel']} for m in filtered]
    return jsonify(meta)

@app.route('/api/radio/clear', methods=['POST'])
@auth_required
def radio_clear():
    # admin can clear channel
    if request.user.get('role')!= 'admin':
        return jsonify({'error':'admin only'}), 403
    ch = str(request.json.get('channel','1'))
    global radio_messages
    radio_messages = [m for m in radio_messages if m['channel']!=ch]
    return jsonify({'ok':True})

# --- STATIC FILES ---
@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/patrol')
def patrol():
    return send_from_directory('.', 'patrol.html')

@app.route('/patrol.html')
def patrol2():
    return send_from_directory('.', 'patrol.html')

@app.route('/login')
def login_page():
    return send_from_directory('.', 'login.html')

@app.route('/login.html')
def login_page2():
    return send_from_directory('.', 'login.html')

@app.route('/assets/<path:path>')
def assets(path):
    return send_from_directory('assets', path)

@app.route('/<path:path>')
def catch_all(path):
    # serve file if exists
    if os.path.exists(path):
        return send_from_directory('.', path)
    # else return index for SPA
    if os.path.exists('index.html'):
        return send_from_directory('.', 'index.html')
    return jsonify({'error':'not found', 'path':path}), 404

# Vercel needs app variable
# For local: python zondi.py
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"ZONDI SECURE - Vercel Safe + Radio Polling running on {port}")
    app.run(host='0.0.0.0', port=port, debug=True)
