# zondi.py — FINAL VERCEL FIX — whole app
import os, jwt, datetime, traceback
from functools import wraps
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'zondi-super-secret-2025-GV-Mkhwanazi')
# FIX 1: simple CORS - no conflict
CORS(app)

clients_live = {}
sos_feed = []
patrol_scans = []
incidents = []
radio_messages = []

JWT_SECRET = app.config['SECRET_KEY']

def decode_token(req):
    auth = req.headers.get('Authorization','')
    if not auth.startswith('Bearer '): return None
    try:
        tok = auth.split(' ')[1]
        return jwt.decode(tok, JWT_SECRET, algorithms=['HS256'])
    except:
        return None

def auth_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        user = decode_token(request)
        if not user:
            return jsonify({'error':'unauthorized'}), 401
        request.user_data = user
        return f(*args, **kwargs)
    return wrapper

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json or {}
    email = data.get('email','').lower().strip() or 'patrol@zondi.local'
    user = {
        'user_id': email.replace('@','_').replace('.','_'),
        'email': email,
        'name': data.get('name') or email.split('@')[0],
        'role': 'admin' if 'admin' in email else 'patroller'
    }
    payload = {**user, 'exp': datetime.datetime.utcnow() + datetime.timedelta(days=7)}
    token = jwt.encode(payload, JWT_SECRET, algorithm='HS256')
    return jsonify({'token': token, 'user': user})

@app.route('/api/patroller-ping', methods=['POST'])
@auth_required
def patroller_ping():
    data = request.json or {}
    uid = request.user_data['user_id']
    clients_live[uid] = {
        'user_id': uid,
        'name': request.user_data.get('name'),
        'email': request.user_data.get('email'),
        'lat': data.get('lat'), 'lng': data.get('lng'),
        'time': datetime.datetime.utcnow().isoformat()
    }
    return jsonify({'ok': True})

@app.route('/api/location/live')
@auth_required
def live(): return jsonify(list(clients_live.values()))

@app.route('/api/sos-feed')
@auth_required
def sos_feed_route(): return jsonify(sos_feed[-50:])

@app.route('/api/sos', methods=['POST'])
@auth_required
def create_sos():
    data = request.json or {}
    sos_feed.append({
        'user_id': request.user_data['user_id'],
        'name': request.user_data.get('name'),
        'lat': data.get('lat'), 'lng': data.get('lng'),
        'time': datetime.datetime.utcnow().isoformat(),
        'msg': data.get('msg','SOS')
    })
    return jsonify({'ok': True})

@app.route('/api/patrol-scan', methods=['POST'])
@auth_required
def patrol_scan():
    patrol_scans.append(request.json)
    return jsonify({'ok': True})

@app.route('/api/incident', methods=['POST'])
@auth_required
def incident():
    incidents.append(request.json)
    return jsonify({'ok': True})

# --- RADIO POLLING (Vercel safe) ---
@app.route('/api/radio/upload', methods=['POST'])
@auth_required
def radio_upload():
    data = request.json or {}
    audio = data.get('audio','')
    # FIX 3: block huge files > 500KB
    if len(audio) > 600000:
        return jsonify({'error':'audio too long, max 5 sec'}), 413
    if not audio: return jsonify({'error':'no audio'}), 400
    msg = {
        'id': len(radio_messages)+1,
        'channel': str(data.get('channel','1')),
        'audio': audio,
        'from': request.user_data.get('name'),
        'from_email': request.user_data.get('email'),
        'time': datetime.datetime.utcnow().isoformat()
    }
    radio_messages.append(msg)
    if len(radio_messages) > 30: radio_messages.pop(0)
    return jsonify({'ok': True, 'id': msg['id']})

@app.route('/api/radio/feed')
@auth_required
def radio_feed():
    ch = str(request.args.get('channel','1'))
    since = int(request.args.get('since','0') or 0)
    filtered = [m for m in radio_messages if m['channel']==ch and m['id']>since]
    return jsonify(filtered[-10:])

# --- STATIC (FIX 2: safe file serving) ---
# --- STATIC - LINKED - FIX FOR HTMLS NOT LINKED ---
import pathlib
BASE_DIR = pathlib.Path(__file__).parent.resolve()

def safe_send(filename):
    file_path = BASE_DIR / filename
    if file_path.exists():
        return send_from_directory(str(BASE_DIR), filename)
    return jsonify({'error': f'{filename} missing at {file_path}'}), 404

@app.route('/')
def index(): return safe_send('index.html')

@app.route('/patrol')
@app.route('/patrol.html')
def patrol(): return safe_send('patrol.html')

@app.route('/login')
@app.route('/login.html')
def login_page(): return safe_send('login.html')

@app.route('/assets/<path:path>')
def assets(path):
    return send_from_directory(str(BASE_DIR / 'assets'), path)

@app.route('/<path:path>')
def catch_all(path):
    if path.startswith('api/'):
        return jsonify({'error':'api not found'}), 404
    full = BASE_DIR / path
    if full.exists() and full.is_file():
        return send_from_directory(str(BASE_DIR), path)
    if (BASE_DIR / 'index.html').exists():
        return send_from_directory(str(BASE_DIR), 'index.html')
    return jsonify({'status':'ZONDI API running'}), 200

# Vercel requires app variable
