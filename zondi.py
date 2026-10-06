import os, pathlib, json
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
import jwt

app = Flask(__name__)
CORS(app, supports_credentials=True)
BASE_DIR = pathlib.Path(__file__).resolve().parent
SECRET = os.getenv('JWT_SECRET', 'zondi-secret-2026-change-me')
DEV_PASS = os.getenv('DEV_PORTAL_PASSWORD', os.getenv('DEV_PASSWORD', 'Zondi2026!'))
DATABASE_URL = os.getenv('DATABASE_URL')

USE_PG = False
try:
    import psycopg2
    import psycopg2.extras
    if DATABASE_URL: USE_PG = True
except: USE_PG = False

def get_conn():
    if not USE_PG or not DATABASE_URL: return None
    try: return psycopg2.connect(DATABASE_URL, sslmode='require')
    except: return None

def init_db():
    conn = get_conn()
    if not conn: return
    try:
        cur = conn.cursor()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS zondi_users (email TEXT PRIMARY KEY, name TEXT, role TEXT, password TEXT, status TEXT, phone TEXT, created_at TIMESTAMP DEFAULT NOW());
        CREATE TABLE IF NOT EXISTS zondi_locations (email TEXT PRIMARY KEY, name TEXT, lat DOUBLE PRECISION, lng DOUBLE PRECISION, updated_at TIMESTAMP DEFAULT NOW());
        CREATE TABLE IF NOT EXISTS zondi_sos (id SERIAL PRIMARY KEY, email TEXT, name TEXT, lat DOUBLE PRECISION, lng DOUBLE PRECISION, time TIMESTAMP DEFAULT NOW());
        """)
        conn.commit(); cur.close()
    except Exception as e: print("init_db", e)
    finally:
        try: conn.close()
        except: pass

TMP_DIR = pathlib.Path("/tmp")
DB_FILE = TMP_DIR / "zondi_db.json"
USERS = {'client@test.com': {'email':'client@test.com','name':'Test Client','role':'client','password':generate_password_hash('12345678'),'status':'active'}}
PATROLLERS = []; LOCATIONS = {}; SOS_EVENTS = []; RESET_REQUESTS = []

def load_file_db():
    if DB_FILE.exists():
        try:
            d=json.loads(DB_FILE.read_text()); USERS.update(d.get("USERS",{}))
        except: pass
def save_file_db():
    try: DB_FILE.write_text(json.dumps({"USERS":USERS}))
    except: pass
try:
    if not USE_PG: load_file_db()
    else: init_db()
except: pass

def db_get_user(email):
    email=email.lower().strip(); conn=get_conn()
    if not conn: return None
    try:
        cur=conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM zondi_users WHERE email=%s",(email,))
        r=cur.fetchone(); cur.close(); conn.close(); return r
    except: return None

def make_token(u): return jwt.encode({'email':u['email'],'name':u.get('name',''),'role':u.get('role','client'),'exp':datetime.utcnow()+timedelta(days=7)}, SECRET, algorithm='HS256')
def get_user_from_token():
    t=request.headers.get('Authorization','').replace('Bearer ','').strip() or request.cookies.get('zondi_token')
    if not t: return None
    try: return jwt.decode(t, SECRET, algorithms=['HS256'])
    except: return None
def auth_required(f):
    @wraps(f)
    def w(*a,**k):
        u=get_user_from_token()
        if not u: return jsonify({'ok':False,'error':'login'}),401
        request.user_data=u; return f(*a,**k)
    return w
def dev_auth_required(f):
    @wraps(f)
    def w(*a,**k):
        u=get_user_from_token()
        if not u or u.get('role')!='dev': return jsonify({'ok':False,'error':'dev'}),401
        request.user_data=u; return f(*a,**k)
    return w

@app.route('/api/health')
def health(): return jsonify({'ok':True,'branch':'main','pg':USE_PG,'time':datetime.utcnow().isoformat()})
@app.route('/api/login', methods=['POST'])
def api_login():
    d=request.get_json(force=True,silent=True) or {}; email=str(d.get('email','')).lower().strip(); pw=str(d.get('password',''))
    u=db_get_user(email) if USE_PG else USERS.get(email)
    if not u or not check_password_hash(u.get('password',''), pw): return jsonify({'ok':False,'error':'Invalid email or password'}),401
    if u.get('status')=='pending': return jsonify({'ok':False,'error':'Patroller pending approval'}),403
    return jsonify({'ok':True,'token':make_token(u),'user':{'email':u['email'],'name':u.get('name',''),'role':u.get('role','client')}})
@app.route('/api/register', methods=['POST'])
def api_register():
    d=request.get_json(force=True,silent=True) or {}; email=str(d.get('email','')).lower().strip(); name=str(d.get('name','')).strip() or email; pw=str(d.get('password','')); role=str(d.get('role','client')).lower()
    if not email or len(pw)<6: return jsonify({'ok':False,'error':'Email + 6 chars needed'}),400
    if (db_get_user(email) if USE_PG else USERS.get(email)): return jsonify({'ok':False,'error':'Email exists'}),400
    hashed=generate_password_hash(pw); obj={'email':email,'name':name,'role':role,'password':hashed,'status':'active' if role=='client' else 'pending'}
    if USE_PG:
        conn=get_conn()
        if conn:
            cur=conn.cursor(); cur.execute("INSERT INTO zondi_users (email,name,role,password,status) VALUES (%s,%s,%s,%s,%s) ON CONFLICT (email) DO UPDATE SET name=EXCLUDED.name,password=EXCLUDED.password",(email,name,role,hashed,obj['status'])); conn.commit(); conn.close()
    else: USERS[email]=obj; save_file_db()
    if role!='client': return jsonify({'ok':True,'message':'pending'})
    return jsonify({'ok':True,'token':make_token(obj)})
@app.route('/api/dev-login', methods=['POST'])
def api_dev_login():
    if not DEV_PASS: return jsonify({'ok':False,'error':'Set DEV_PORTAL_PASSWORD'}),503
    d=request.get_json(silent=True) or {}
    if str(d.get('password',''))!=DEV_PASS: return jsonify({'ok':False,'error':'Wrong password'}),401
    return jsonify({'ok':True,'token':make_token({'email':'dev@zondi.local','name':'Developer','role':'dev'})})
@app.route('/api/me')
@auth_required
def api_me(): return jsonify({'ok':True,'user':request.user_data})
@app.route('/api/location/update', methods=['POST'])
@auth_required
def loc_update():
    d=request.get_json(silent=True) or {}; email=request.user_data['email'].lower()
    LOCATIONS[email]={'email':email,'name':request.user_data.get('name',''),'lat':d.get('lat'),'lng':d.get('lng'),'updated_at':datetime.utcnow().isoformat()}
    return jsonify({'ok':True})
@app.route('/api/location/live')
@auth_required
def loc_live(): return jsonify({'ok':True,'locations':list(LOCATIONS.values())})
@app.route('/api/sos', methods=['POST'])
@auth_required
def api_sos():
    d=request.get_json(silent=True) or {}; SOS_EVENTS.append({'email':request.user_data['email'],'lat':d.get('lat'),'lng':d.get('lng'),'time':datetime.utcnow().isoformat()}); return jsonify({'ok':True})
@app.route('/api/admin/pending')
@dev_auth_required
def admin_pending(): return jsonify({'ok':True,'pending':[],'all_patrollers':[]})
@app.route('/api/dev-stats')
@dev_auth_required
def dev_stats(): return jsonify({'ok':True,'clients':len(USERS),'patrollers':0,'pending':0})

def safe_send(f):
    fp=BASE_DIR/f
    if fp.exists() and fp.is_file(): return send_from_directory(str(BASE_DIR), f)
    return send_from_directory(str(BASE_DIR), 'index.html')

@app.route('/')
def root(): return safe_send('index.html')
@app.route('/login')
def login_route(): return safe_send('login.html')
@app.route('/clients')
def clients_route(): return safe_send('clients.html')
@app.route('/patrol')
def patrol_route(): return safe_send('patrol.html')
@app.route('/register')
def reg_route(): return safe_send('register.html')
@app.route('/dev')
def dev_route(): return safe_send('dev.portal.html')
@app.route('/forgot-password')
def forgot_route(): return safe_send('forgot-password.html')
@app.route('/assets/<path:path>')
def assets_route(path):
    folder=BASE_DIR/'assets'
    if (folder/path).exists(): return send_from_directory(str(folder), path)
    return jsonify({'error':'not found'}),404

@app.route('/<path:filename>')
def catch_all(filename):
    if filename in ("api/index.py","api/index","api"):
        return safe_send('index.html')
    if filename.startswith('api/'): return jsonify({'ok':False,'error':'API not found: '+filename}),404
    p=BASE_DIR/filename
    if p.exists() and p.is_file(): return send_from_directory(str(BASE_DIR), filename)
    return send_from_directory(str(BASE_DIR), 'index.html')
