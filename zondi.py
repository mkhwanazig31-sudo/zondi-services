import os, pathlib, secrets
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
import jwt

app = Flask(__name__)
CORS(app, supports_credentials=True)

BASE_DIR = pathlib.Path(__file__).parent.resolve()
SECRET = os.getenv('JWT_SECRET', 'zondi-secret-2026-change-me')
DEV_PASS = os.getenv('DEV_PORTAL_PASSWORD', os.getenv('DEV_PASSWORD', ''))

# --- IN-MEMORY DB (works on Vercel, no Postgres needed) ---
USERS = {
    'client@test.com': {'email':'client@test.com','name':'Test Client','role':'client','password':generate_password_hash('12345678'), 'status':'active'},
}
PATROLLERS = [
    # example pending to test admin
]
LOCATIONS = {} # email -> {lat,lng,...}
SOS_EVENTS = []
RESET_REQUESTS = []

# --- AUTH ---
def make_token(user_dict):
    payload = {
        'email': user_dict['email'],
        'name': user_dict.get('name',''),
        'role': user_dict.get('role','client'),
        'exp': datetime.utcnow() + timedelta(days=7)
    }
    return jwt.encode(payload, SECRET, algorithm='HS256')

def get_user_from_token():
    auth = request.headers.get('Authorization','')
    token = auth.replace('Bearer ','').strip()
    if not token:
        token = request.cookies.get('zondi_token')
    if not token:
        return None
    try:
        return jwt.decode(token, SECRET, algorithms=['HS256'])
    except:
        return None

def auth_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        user = get_user_from_token()
        if not user:
            return jsonify({'ok':False,'error':'Session expired, login again'}), 401
        request.user_data = user
        return f(*args, **kwargs)
    return wrapper

def dev_auth_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        user = get_user_from_token()
        if not user or user.get('role')!= 'dev':
            return jsonify({'ok':False,'error':'Developer session expired'}), 401
        request.user_data = user
        return f(*args, **kwargs)
    return wrapper

# --- API ROUTES YOUR HTMLS CALL ---

@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.get_json(force=True, silent=True) or {}
    email = str(data.get('email','')).lower().strip()
    pw = str(data.get('password',''))

    # find user
    u = USERS.get(email)
    if not u:
        for p in PATROLLERS:
            if p['email'].lower() == email:
                u = p
                break

    if not u or not check_password_hash(u.get('password',''), pw):
        return jsonify({'ok':False,'error':'Invalid email or password'}), 401

    if u.get('status') == 'pending':
        return jsonify({'ok':False,'error':'Patroller pending approval. Contact admin.'}), 403

    token = make_token(u)
    return jsonify({'ok':True,'token':token,'user':{'email':u['email'],'name':u.get('name',''),'role':u.get('role','client')}})

@app.route('/api/register', methods=['POST'])
def api_register():
    data = request.get_json(force=True, silent=True) or {}
    email = str(data.get('email','')).lower().strip()
    name = str(data.get('name','')).strip()
    pw = str(data.get('password',''))
    role = str(data.get('role','client')).lower()
    phone = str(data.get('phone','')).strip()

    if not email or not pw or len(pw) < 6:
        return jsonify({'ok':False,'error':'Email and 6+ char password required'}), 400
    if email in USERS or any(p['email']==email for p in PATROLLERS):
        return jsonify({'ok':False,'error':'Email already registered'}), 400

    hashed = generate_password_hash(pw)
    if role == 'patroller':
        PATROLLERS.append({'email':email,'name':name or email,'role':'patroller','status':'pending','password':hashed,'phone':phone})
        return jsonify({'ok':True,'message':'Patroller registered, pending approval'})
    else:
        USERS[email] = {'email':email,'name':name or email,'role':'client','status':'active','password':hashed,'phone':phone}
        token = make_token(USERS[email])
        return jsonify({'ok':True,'token':token,'user':{'email':email,'name':name,'role':'client'}})

@app.route('/api/dev-login', methods=['POST'])
def api_dev_login():
    if not DEV_PASS:
        return jsonify({'ok':False,'error':'Developer access is not configured on the server. Set DEV_PORTAL_PASSWORD in Render → Environment.'}), 503
    data = request.get_json(force=True, silent=True) or {}
    if str(data.get('password',''))!= DEV_PASS:
        return jsonify({'ok':False,'error':'Wrong developer password'}), 401
    token = make_token({'email':'dev@zondi.local','name':'Developer','role':'dev'})
    return jsonify({'ok':True,'token':token,'redirect':'/dev'})

@app.route('/api/me')
@auth_required
def api_me():
    return jsonify({'ok':True,'user':request.user_data})

@app.route('/api/logout', methods=['POST'])
def api_logout():
    return jsonify({'ok':True})

@app.route('/api/dev-logout', methods=['POST'])
def api_dev_logout():
    return jsonify({'ok':True})

@app.route('/api/location/update', methods=['POST'])
@auth_required
def loc_update():
    data = request.get_json(force=True, silent=True) or {}
    email = request.user_data['email']
    LOCATIONS[email] = {
        'email': email,
        'name': request.user_data.get('name',''),
        'lat': data.get('lat'),
        'lng': data.get('lng'),
        'accuracy': data.get('accuracy'),
        'heading': data.get('heading'),
        'speed': data.get('speed'),
        'updated_at': datetime.utcnow().isoformat()
    }
    return jsonify({'ok':True})

@app.route('/api/location/live')
@auth_required
def loc_live():
    # only patroller + dev can see all
    if request.user_data.get('role') not in ['patroller','dev']:
        return jsonify({'ok':False,'error':'Patrol only'}), 403
    return jsonify({'ok':True,'locations': list(LOCATIONS.values()), 'sos': SOS_EVENTS[-10:]})

@app.route('/api/sos', methods=['POST'])
@auth_required
def api_sos():
    data = request.get_json(force=True, silent=True) or {}
    SOS_EVENTS.append({
        'email': request.user_data['email'],
        'name': request.user_data.get('name',''),
        'lat': data.get('lat'),
        'lng': data.get('lng'),
        'time': datetime.utcnow().isoformat()
    })
    return jsonify({'ok':True})

# --- ADMIN ---
@app.route('/api/admin/pending')
@dev_auth_required
def admin_pending():
    return jsonify({'ok':True,'pending':[p for p in PATROLLERS if p.get('status')=='pending'],'all_patrollers': PATROLLERS})

@app.route('/api/admin/approve', methods=['POST'])
@dev_auth_required
def admin_approve():
    data = request.get_json(force=True, silent=True) or {}
    email = str(data.get('email','')).lower()
    action = str(data.get('action','')).lower()
    for p in PATROLLERS:
        if p['email'].lower() == email:
            if action == 'approve':
                p['status']='approved'
                p['role']='patroller'
            elif action == 'reject':
                PATROLLERS.remove(p)
                break
            elif action == 'revoke':
                p['status']='pending'
    return jsonify({'ok':True})

@app.route('/api/admin/password-reset-requests')
@dev_auth_required
def admin_reset_list():
    return jsonify({'ok':True,'requests': RESET_REQUESTS})

@app.route('/api/admin/password-reset', methods=['POST'])
@dev_auth_required
def admin_reset_do():
    data = request.get_json(force=True, silent=True) or {}
    email = str(data.get('email','')).lower()
    new_pw = str(data.get('password',''))
    if len(new_pw) < 8:
        return jsonify({'ok':False,'error':'Password must be 8+ chars'}), 400
    h = generate_password_hash(new_pw)
    if email in USERS:
        USERS[email]['password']=h
    for p in PATROLLERS:
        if p['email'].lower()==email:
            p['password']=h
    return jsonify({'ok':True})

@app.route('/api/forgot-password', methods=['POST'])
def forgot_api():
    data = request.get_json(force=True, silent=True) or {}
    email = str(data.get('email','')).lower().strip()
    # hide existence
    RESET_REQUESTS.append({'email':email,'status':'pending','requested_at':datetime.utcnow().isoformat()})
    return jsonify({'ok':True,'message':'If account exists, request sent to admin'})

# --- STATIC SERVING - LINKED TO YOUR FILENAMES ---
def safe_send(filename):
    fp = BASE_DIR / filename
    if fp.exists() and fp.is_file():
        return send_from_directory(str(BASE_DIR), filename)
    return jsonify({'error': f'{filename} not found. Check GitHub root.'}), 404

@app.route('/')
def root():
    return safe_send('index.html')

@app.route('/dashboard')
def dashboard_route():
    # your dashboard.html is actually the new dashboard, but index.html is also dashboard
    if (BASE_DIR / 'dashboard.html').exists() and (BASE_DIR / 'index.html').exists():
        # index.html is the dashboard design you sent me, so serve it
        return safe_send('index.html')
    if (BASE_DIR / 'dashboard.html').exists():
        return safe_send('dashboard.html')
    return safe_send('index.html')

@app.route('/login')
def login_route(): return safe_send('login.html')

@app.route('/clients')
def clients_route(): return safe_send('clients.html')

@app.route('/patrol')
def patrol_route(): return safe_send('patrol.html')

@app.route('/dev')
def dev_route():
    if (BASE_DIR / 'dev.html').exists(): return safe_send('dev.html')
    if (BASE_DIR / 'dev_portal.html').exists(): return safe_send('dev_portal.html')
    return safe_send('index.html')

@app.route('/register')
def register_route(): return safe_send('register.html')

@app.route('/forgot-password')
def forgot_route(): return safe_send('forgot-password.html')

@app.route('/assets/<path:path>')
def assets_route(path):
    asset_dir = BASE_DIR / 'assets'
    if not asset_dir.exists():
        # fallback if folder named asset (singular) by mistake
        asset_dir = BASE_DIR / 'asset'
    return send_from_directory(str(asset_dir), path)

# catch-all for any other.html file directly
@app.route('/<path:filename>')
def catch_all(filename):
    if filename.startswith('api/'):
        return jsonify({'ok':False,'error':'API not found'}), 404
    p = BASE_DIR / filename
    if p.exists() and p.is_file():
        return send_from_directory(str(BASE_DIR), filename)
    # SPA fallback
    if (BASE_DIR / 'index.html').exists():
        return send_from_directory(str(BASE_DIR), 'index.html')
    return jsonify({'ok':True,'msg':'ZONDI API running'}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT',5000)))
