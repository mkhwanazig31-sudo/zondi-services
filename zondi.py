from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import json, os, threading
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import safe_join
import uuid

app = Flask(__name__, static_folder='.')
CORS(app)  # Enable for mobile/web app clients

# Config
SOS_FILE = 'sos_feed.json'
USERS_FILE = 'users.json'
PATROLLER_FILE = 'patrollers_live.json'
VOICE_FILE = 'radio_talk.json'
ALLOWED_STATIC_EXTS = {'.html', '.js', '.css', '.json', '.png', '.jpg', '.jpeg', '.svg', '.ico', '.map'}

# Thread-safe file access
file_lock = threading.Lock()

def load_json(f):
    if not os.path.exists(f): 
        return []
    try:
        with file_lock:
            with open(f, 'r', encoding='utf-8') as fh:
                d = json.load(fh)
                return d if isinstance(d, list) else []
    except Exception as e:
        print(f"Load error {f}: {e}")
        return []

def save_json(f, data):
    try:
        with file_lock:
            # atomic write
            tmp = f + '.tmp'
            with open(tmp, 'w', encoding='utf-8') as fh:
                json.dump(data, fh, indent=2)
            os.replace(tmp, f)
    except Exception as e:
        print(f"Save error {f}: {e}")

def init_files():
    for f in [SOS_FILE, USERS_FILE, PATROLLER_FILE, VOICE_FILE]:
        if not os.path.exists(f): 
            save_json(f, [])

# === Helpers ===
def sanitize_user(u):
    """Never return password"""
    return {k: v for k, v in u.items() if k != 'password'}

# === Routes - Pages ===
@app.route('/')
def home(): 
    return send_from_directory('.', 'login.html') if os.path.exists('login.html') else jsonify({"name": "Zondi API", "status": "running", "version": "2.0"})

@app.route('/login')
@app.route('/login.html')
def login_page(): return send_from_directory('.', 'login.html')

@app.route('/register')
@app.route('/register.html')
def reg_page(): return send_from_directory('.', 'register.html')

@app.route('/clients')
@app.route('/clients.html')
def clients_page(): return send_from_directory('.', 'clients.html')

@app.route('/patrollers')
@app.route('/patrol')
@app.route('/patrollers.html')
@app.route('/patrol.html')
def patrol_page(): return send_from_directory('.', 'patrol.html')

# === API - SOS ===
@app.route('/api/sos', methods=['POST'])
def api_sos():
    data = request.get_json(silent=True) or {}
    
    # validation
    if not data.get('phoneId') or not data.get('lat'):
        return jsonify({"error": "phoneId and lat required"}), 400

    data['id'] = str(uuid.uuid4())
    data['time'] = datetime.now().isoformat()
    
    feed = load_json(SOS_FILE)
    feed.append(data)
    if len(feed) > 1000: 
        feed = feed[-1000:]
    save_json(SOS_FILE, feed)
    return jsonify({"ok": True, "id": data['id']})

@app.route('/api/sos-feed')
def api_feed(): 
    limit = request.args.get('limit', 300, type=int)
    limit = min(max(limit, 1), 500)
    return jsonify(load_json(SOS_FILE)[-limit:])

@app.route('/api/tracking/<phone_id>')
def api_tracking(phone_id):
    if not phone_id or len(phone_id) > 100:
        return jsonify({"error": "invalid phoneId"}), 400
    feed = load_json(SOS_FILE)
    filtered = [x for x in feed if x.get('phoneId') == phone_id and x.get('lat')][-100:]
    return jsonify(filtered)

# === API - Patrollers Live ===
@app.route('/api/patroller-ping', methods=['POST'])
def pp():
    d = request.get_json(silent=True) or {}
    if not d.get('email'):
        return jsonify({"error": "email required"}), 400
    
    d['time'] = datetime.now().isoformat()
    d['email'] = d['email'].lower().strip()
    
    data = load_json(PATROLLER_FILE)
    data = [x for x in data if x.get('email') != d.get('email')]
    data.append(d)
    save_json(PATROLLER_FILE, data)
    return jsonify({"ok": True})

@app.route('/api/patrollers-live')
def pl():
    data = load_json(PATROLLER_FILE)
    cutoff = datetime.now() - timedelta(minutes=5)
    fresh = []
    for p in data:
        try:
            t = datetime.fromisoformat(p.get('time', ''))
            if t > cutoff:
                fresh.append(p)
        except:
            # keep if no time but don't break
            continue
    return jsonify(fresh)

# === API - Auth UPGRADED ===
@app.route('/api/login', methods=['POST'])
def api_login():
    d = request.get_json(silent=True) or {}
    email = d.get('email', '').lower().strip()
    pwd = d.get('password', '')
    
    if not email or not pwd:
        return jsonify({"error": "Email and password required"}), 400

    users = load_json(USERS_FILE)
    u = next((x for x in users if x.get('email', '').lower() == email), None)
    
    if not u:
        return jsonify({"error": "Wrong email or password"}), 401

    # support both old plain text and new hashed
    stored_pwd = u.get('password', '')
    is_valid = False
    if stored_pwd.startswith('pbkdf2:') or stored_pwd.startswith('scrypt:'):
        is_valid = check_password_hash(stored_pwd, pwd)
    else:
        is_valid = (stored_pwd == pwd)  # legacy support, will upgrade on login
        if is_valid:
            # auto-upgrade to hashed
            u['password'] = generate_password_hash(pwd)
            # save updated user list
            save_json(USERS_FILE, users)

    if not is_valid:
        return jsonify({"error": "Wrong email or password"}), 401

    return jsonify(sanitize_user(u))

@app.route('/api/signup', methods=['POST'])
@app.route('/api/register', methods=['POST'])
def api_reg():
    d = request.get_json(silent=True) or {}
    email = d.get('email', '').lower().strip()
    password = d.get('password', '')
    role = d.get('role', 'client').lower()  # client / patroller / admin

    if not email or not password:
        return jsonify({"error": "Email and password required"}), 400
    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters"}), 400

    users = load_json(USERS_FILE)
    if any(x.get('email', '').lower() == email for x in users):
        return jsonify({"error": "Email already registered. Go to Login"}), 400

    # hash password
    hashed = generate_password_hash(password)
    new_user = {
        "id": str(uuid.uuid4()),
        "email": email,
        "password": hashed,
        "role": role,
        "name": d.get('name', ''),
        "phone": d.get('phone', ''),
        "created_at": datetime.now().isoformat()
    }
    # keep extra fields if provided but don't override secured ones
    for k, v in d.items():
        if k not in new_user:
            new_user[k] = v
    new_user['password'] = hashed
    new_user['email'] = email

    users.append(new_user)
    save_json(USERS_FILE, users)
    return jsonify({"ok": True, "user": sanitize_user(new_user)}), 201

# === RADIO T720 VOICE ===
@app.route('/api/radio/talk', methods=['POST'])
def radio_talk_post():
    d = request.get_json(silent=True) or {}
    if not d.get('channel') or not d.get('sender'):
        return jsonify({"error": "channel and sender required"}), 400

    d['id'] = str(uuid.uuid4())
    d['time'] = datetime.now().isoformat()
    feed = load_json(VOICE_FILE)
    feed.append(d)
    if len(feed) > 50: 
        feed = feed[-50:]
    save_json(VOICE_FILE, feed)
    return jsonify({"ok": True, "id": d['id']})

@app.route('/api/radio/talk', methods=['GET'])
def radio_talk_get():
    channel = request.args.get('channel')
    limit = request.args.get('limit', 20, type=int)
    limit = min(max(limit, 1), 50)
    feed = load_json(VOICE_FILE)[-limit:]
    if channel:
        feed = [x for x in feed if str(x.get('channel')) == str(channel)]
    return jsonify(feed)

# === Secure Static File Serving ===
@app.route('/<path:path>')
def catch_all(path):
    # API 404
    if path.startswith('api/'): 
        return jsonify({"error": "not found"}), 404
    
    # Security: prevent directory traversal
    if '..' in path or path.startswith('/'):
        return jsonify({"error": "invalid path"}), 400

    # Only allow specific file types
    _, ext = os.path.splitext(path)
    if ext.lower() not in ALLOWED_STATIC_EXTS and ext != '':
        # if it's a frontend route, serve login.html
        return send_from_directory('.', 'login.html')

    full_path = safe_join('.', path)
    if full_path and os.path.exists(full_path) and os.path.isfile(full_path):
        return send_from_directory('.', path)
    
    # SPA fallback
    return send_from_directory('.', 'login.html') if os.path.exists('login.html') else jsonify({"error": "not found"}), 404

if __name__ == '__main__':
    init_files()
    port = int(os.environ.get('PORT', 10000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    app.run(host='0.0.0.0', port=port, debug=debug)
