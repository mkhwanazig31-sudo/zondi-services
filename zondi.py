import os, pathlib, json
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
DATABASE_URL = os.getenv('DATABASE_URL')

# --- DB HELPERS ---
USE_PG = False
try:
    import psycopg2
    import psycopg2.extras
    if DATABASE_URL:
        USE_PG = True
except:
    USE_PG = False

def get_conn():
    if not USE_PG:
        return None
    try:
        return psycopg2.connect(DATABASE_URL, sslmode='require')
    except Exception as e:
        print("PG connect failed:", e)
        return None

def init_db():
    conn = get_conn()
    if not conn:
        return
    try:
        cur = conn.cursor()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS zondi_users (
            email TEXT PRIMARY KEY,
            name TEXT,
            role TEXT,
            password TEXT,
            status TEXT,
            phone TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS zondi_locations (
            email TEXT PRIMARY KEY,
            name TEXT,
            lat DOUBLE PRECISION,
            lng DOUBLE PRECISION,
            updated_at TIMESTAMP DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS zondi_sos (
            id SERIAL PRIMARY KEY,
            email TEXT,
            name TEXT,
            lat DOUBLE PRECISION,
            lng DOUBLE PRECISION,
            time TIMESTAMP DEFAULT NOW()
        );
        """)
        conn.commit()
        cur.close()
    except Exception as e:
        print("init_db error", e)
    finally:
        conn.close()

def db_get_user(email):
    email = email.lower().strip()
    conn = get_conn()
    if not conn:
        return None
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM zondi_users WHERE email=%s", (email,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        return row
    except Exception as e:
        print("db_get_user error", e)
        return None

def db_save_user(u):
    conn = get_conn()
    if not conn:
        return False
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO zondi_users (email,name,role,password,status,phone)
            VALUES (%s,%s,%s,%s,%s,%s)
            ON CONFLICT (email) DO UPDATE SET name=EXCLUDED.name, role=EXCLUDED.role, password=EXCLUDED.password, status=EXCLUDED.status, phone=EXCLUDED.phone
        """, (u['email'].lower(), u.get('name',''), u.get('role','client'), u.get('password',''), u.get('status','active'), u.get('phone','')))
        conn.commit()
        cur.close()
        conn.close()
        return True
    except Exception as e:
        print("db_save_user error", e)
        return False

if USE_PG:
    init_db()

# --- FILE FALLBACK ---
DB_FILE = BASE_DIR / "zondi_db.json"
USERS = {'client@test.com': {'email':'client@test.com','name':'Test Client','role':'client','password':generate_password_hash('12345678'), 'status':'active'}}
PATROLLERS = []
LOCATIONS = {}
SOS_EVENTS = []
RESET_REQUESTS = []

def load_file_db():
    if DB_FILE.exists():
        try:
            data = json.loads(DB_FILE.read_text())
            global USERS, PATROLLERS
            USERS = data.get("USERS", USERS)
            PATROLLERS = data.get("PATROLLERS", PATROLLERS)
        except: pass

def save_file_db():
    try:
        DB_FILE.write_text(json.dumps({"USERS":USERS,"PATROLLERS":PATROLLERS}))
        pathlib.Path("/tmp/zondi_db.json").write_text(json.dumps({"USERS":USERS,"PATROLLERS":PATROLLERS}))
    except: pass

if not USE_PG:
    load_file_db()

# --- AUTH ---
def make_token(user_dict):
    payload = {'email': user_dict['email'], 'name': user_dict.get('name',''), 'role': user_dict.get('role','client'), 'exp': datetime.utcnow() + timedelta(days=7)}
    return jwt.encode(payload, SECRET, algorithm='HS256')

def get_user_from_token():
    auth = request.headers.get('Authorization','')
    token = auth.replace('Bearer ','').strip() or request.cookies.get('zondi_token')
    if not token: return None
    try: return jwt.decode(token, SECRET, algorithms=['HS256'])
    except: return None

def auth_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        user = get_user_from_token()
        if not user: return jsonify({'ok':False,'error':'Session expired, login again'}), 401
        request.user_data = user
        return f(*args, **kwargs)
    return wrapper

def dev_auth_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        user = get_user_from_token()
        if not user or user.get('role')!= 'dev': return jsonify({'ok':False,'error':'Developer session expired'}), 401
        request.user_data = user
        return f(*args, **kwargs)
    return wrapper

@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.get_json(force=True, silent=True) or {}
    email = str(data.get('email','')).lower().strip()
    pw = str(data.get('password',''))
    u = None
    if USE_PG:
        u = db_get_user(email)
    else:
        u = USERS.get(email)
        if not u:
            for p in PATROLLERS:
                if p['email'].lower()==email:
                    u=p; break
    if not u or not check_password_hash(u.get('password',''), pw):
        return jsonify({'ok':False,'error':'Invalid email or password'}), 401
    if u.get('status')=='pending':
        return jsonify({'ok':False,'error':'Patroller pending approval. Contact admin.'}), 403
    token = make_token(u)
    return jsonify({'ok':True,'token':token,'user':{'email':u['email'],'name':u.get('name',''),'role':u.get('role','client')}})

@app.route('/api/register', methods=['POST'])
def api_register():
    data = request.get_json(force=True, silent=True) or {}
    email = str(data.get('email','')).lower().strip()
    name = str(data.get('name','') or data.get('fullName','')).strip() or email
    pw = str(data.get('password',''))
    role = str(data.get('role','client')).lower()
    phone = str(data.get('phone','')).strip()
    if not email or len(pw)<6:
        return jsonify({'ok':False,'error':'Email and 6+ char password required'}), 400
    exists = db_get_user(email) if USE_PG else (USERS.get(email) or any(p['email'].lower()==email for p in PATROLLERS))
    if exists:
        return jsonify({'ok':False,'error':'Email already registered'}), 400
    hashed = generate_password_hash(pw)
    status = 'pending' if role=='patroller' else 'active'
    user_obj = {'email':email,'name':name,'role':role,'password':hashed,'status':status,'phone':phone}
    if USE_PG:
        db_save_user(user_obj)
    else:
        if role=='patroller':
            PATROLLERS.append(user_obj)
        else:
            USERS[email]=user_obj
        save_file_db()
    if role=='patroller':
        return jsonify({'ok':True,'message':'Patroller registered, pending approval'})
    else:
        token = make_token(user_obj)
        return jsonify({'ok':True,'token':token,'user':{'email':email,'name':name,'role':'client'}})

@app.route('/api/dev-login', methods=['POST'])
def api_dev_login():
    if not DEV_PASS: return jsonify({'ok':False,'error':'Set DEV_PORTAL_PASSWORD in Vercel'}), 503
    data = request.get_json(force=True, silent=True) or {}
    if str(data.get('password',''))!= DEV_PASS: return jsonify({'ok':False,'error':'Wrong developer password'}), 401
    token = make_token({'email':'dev@zondi.local','name':'Developer','role':'dev'})
    return jsonify({'ok':True,'token':token,'redirect':'/dev'})

@app.route('/api/me')
@auth_required
def api_me(): return jsonify({'ok':True,'user':request.user_data})
@app.route('/api/logout', methods=['POST'])
def api_logout(): return jsonify({'ok':True})

@app.route('/api/location/update', methods=['POST'])
@auth_required
def loc_update():
    data = request.get_json(force=True, silent=True) or {}
    LOCATIONS[request.user_data['email'].lower()] = {'email':request.user_data['email'],'name':request.user_data.get('name',''),'lat':data.get('lat'),'lng':data.get('lng'),'updated_at':datetime.utcnow().isoformat()}
    return jsonify({'ok':True})

@app.route('/api/location/live')
@auth_required
def loc_live():
    if request.user_data.get('role') not in ['patroller','dev']: return jsonify({'ok':False,'error':'Patrol only'}), 403
    return jsonify({'ok':True,'locations': list(LOCATIONS.values())})

@app.route('/api/sos', methods=['POST'])
@auth_required
def api_sos(): return jsonify({'ok':True})
@app.route('/api/sos-feed')
@auth_required
def sos_feed(): return jsonify([])
@app.route('/api/patrol-scan', methods=['POST'])
@auth_required
def patrol_scan(): return jsonify({'ok':True})
@app.route('/api/incident', methods=['POST'])
@auth_required
def incident(): return jsonify({'ok':True})
@app.route('/api/patroller-ping', methods=['POST'])
@auth_required
def patroller_ping(): return loc_update()

@app.route('/api/admin/pending')
@dev_auth_required
def admin_pending():
    if USE_PG:
        conn=get_conn(); cur=conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor); cur.execute("SELECT * FROM zondi_users WHERE role='patroller' AND status='pending'"); pending=cur.fetchall(); cur.execute("SELECT * FROM zondi_users WHERE role='patroller'"); all_p=cur.fetchall(); conn.close(); return jsonify({'ok':True,'pending':pending,'all_patrollers':all_p})
    return jsonify({'ok':True,'pending':[p for p in PATROLLERS if p.get('status')=='pending'],'all_patrollers':PATROLLERS})

@app.route('/api/admin/approve', methods=['POST'])
@dev_auth_required
def admin_approve():
    data = request.get_json(force=True, silent=True) or {}; email=str(data.get('email','')).lower(); action=str(data.get('action','')).lower()
    if USE_PG:
        conn=get_conn(); cur=conn.cursor()
        if action=='approve': cur.execute("UPDATE zondi_users SET status='approved', role='patroller' WHERE email=%s",(email,))
        elif action=='reject': cur.execute("DELETE FROM zondi_users WHERE email=%s",(email,))
        elif action=='revoke': cur.execute("UPDATE zondi_users SET status='pending' WHERE email=%s",(email,))
        conn.commit(); conn.close()
    else:
        for p in PATROLLERS:
            if p['email'].lower()==email:
                if action=='approve': p['status']='approved'; p['role']='patroller'
                elif action=='reject': PATROLLERS.remove(p); break
                elif action=='revoke': p['status']='pending'
        save_file_db()
    return jsonify({'ok':True})

# --- FIX FOR API NOT FOUND BANNER ---
@app.route('/api/dev-stats')
@dev_auth_required
def dev_stats():
    if USE_PG:
        try:
            conn=get_conn(); cur=conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute("SELECT COUNT(*) as c FROM zondi_users WHERE role='client'"); clients=cur.fetchone()['c']
            cur.execute("SELECT COUNT(*) as c FROM zondi_users WHERE role='patroller' AND status='approved'"); patrollers=cur.fetchone()['c']
            cur.execute("SELECT COUNT(*) as c FROM zondi_users WHERE role='patroller' AND status='pending'"); pending=cur.fetchone()['c']
            conn.close()
            return jsonify({'ok':True,'clients':clients,'patrollers':patrollers,'pending':pending,'incidents':0,'sos':0})
        except: pass
    return jsonify({'ok':True,'clients':len(USERS),'patrollers':len([p for p in PATROLLERS if p.get('status')=='approved']),'pending':len([p for p in PATROLLERS if p.get('status')=='pending']),'incidents':0,'sos':0})

@app.route('/api/reset-requests')
@dev_auth_required
def reset_requests_route():
    return jsonify({'ok':True,'requests':RESET_REQUESTS})

@app.route('/api/clients/me')
@auth_required
def clients_me():
    email=request.user_data['email'].lower()
    u=db_get_user(email) if USE_PG else USERS.get(email)
    return jsonify({'ok':True,'user':u or request.user_data})

@app.route('/api/clients/requests')
@auth_required
def client_requests_route():
    return jsonify({'ok':True,'requests':[]})

@app.route('/api/forgot-password', methods=['POST'])
def forgot_api(): return jsonify({'ok':True,'message':'Request sent to admin'})

# --- ZONDI RADIO NET - REAL ---
RADIO_DIR = BASE_DIR / "radio"
RADIO_DIR.mkdir(exist_ok=True)
RADIO_LOG = []
RADIO_PRESENCE = {}

def cleanup_presence():
    now = datetime.utcnow()
    dead = [e for e, v in list(RADIO_PRESENCE.items()) if (now - v['last']).total_seconds() > 35]
    for e in dead:
        del RADIO_PRESENCE[e]

@app.route('/api/radio/presence', methods=['POST'])
@auth_required
def radio_presence():
    data = request.get_json(silent=True) or {}
    email = request.user_data['email'].lower()
    RADIO_PRESENCE[email] = {
        'email': email,
        'name': request.user_data.get('name','Patroller'),
        'role': request.user_data.get('role','patroller'),
        'last': datetime.utcnow(),
        'lat': data.get('lat'),
        'lng': data.get('lng'),
        'tx': data.get('tx', False)
    }
    cleanup_presence()
    active = []
    for v in RADIO_PRESENCE.values():
        if v['email']!= email:
            active.append({
                'email': v['email'],
                'name': v['name'],
                'role': v['role'],
                'active': True,
                'tx': v['tx'],
                'ago': int((datetime.utcnow() - v['last']).total_seconds())
            })
    return jsonify({'ok':True,'connected':len(RADIO_PRESENCE), 'radios':active})

@app.route('/api/radio/feed')
@auth_required
def radio_feed():
    cleanup_presence()
    return jsonify({'ok':True,'items':RADIO_LOG[-20:], 'presence': list(RADIO_PRESENCE.values())})

@app.route('/api/radio/push', methods=['POST'])
@auth_required
def radio_push():
    f = request.files.get('audio')
    if not f: return jsonify({'ok':False,'error':'No audio'}),400
    fname = f"radio_{int(datetime.utcnow().timestamp())}_{request.user_data['email'].split('@')[0]}.webm"
    path = RADIO_DIR / fname
    f.save(str(path))
    item = {'name':request.user_data.get('name','Patroller'),'email':request.user_data['email'].lower(),'time':datetime.utcnow().isoformat(),'file':fname,'url':f'/radio/{fname}'}
    RADIO_LOG.append(item)
    if len(RADIO_LOG)>50: RADIO_LOG.pop(0)
    return jsonify({'ok':True,'item':item, 'sent_to': len(RADIO_PRESENCE)-1})

@app.route('/radio/<path:filename>')
def serve_radio(filename):
    return send_from_directory(str(RADIO_DIR), filename)

def safe_send(f):
    fp = BASE_DIR / f
    if fp.exists() and fp.is_file(): return send_from_directory(str(BASE_DIR), f)
    return jsonify({'error': f'{f} not found.'}), 404

@app.route('/')
def root(): return safe_send('index.html')
@app.route('/login')
def login_route(): return safe_send('login.html')
@app.route('/clients')
def clients_route(): return safe_send('clients.html')
@app.route('/patrol')
def patrol_route(): return safe_send('patrol.html')
@app.route('/dev')
def dev_route(): return safe_send('dev.html') if (BASE_DIR/'dev.html').exists() else safe_send('dev_portal.html')
@app.route('/register')
def register_route(): return safe_send('register.html')
@app.route('/forgot-password')
def forgot_route(): return safe_send('forgot-password.html')
@app.route('/assets/<path:path>')
def assets_route(path):
    for folder_name in ['assets','asset']:
        folder = BASE_DIR / folder_name
        fp = folder / path
        if fp.exists() and fp.is_file(): return send_from_directory(str(folder), path)
    return jsonify({'error': f'Asset {path} not found'}), 404
@app.route('/<path:filename>')
def catch_all(filename):
    if filename.startswith('api/'): return jsonify({'ok':False,'error':'API not found: '+filename}), 404
    p = BASE_DIR / filename
    if p.exists() and p.is_file(): return send_from_directory(str(BASE_DIR), filename)
    return send_from_directory(str(BASE_DIR), 'index.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT',5000)))
