import os
from flask import Flask, request, jsonify, session, send_from_directory
from flask_cors import CORS
from datetime import datetime
from functools import wraps

app = Flask(__name__, static_folder='.')
app.secret_key = os.environ.get('SECRET_KEY', 'zondi-dev-only-change-in-prod')
CORS(app, supports_credentials=True)

DEV_PASS = os.environ.get('DEV_PASS', 'zondi@123')

# Mongo safe
try:
    from pymongo import MongoClient
    MONGO_URI = os.environ.get('MONGO_URI','')
    db = None
    if MONGO_URI:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=3000)
        db = client.get_database('zondi')
        print("Mongo OK")
    else:
        print("No MONGO_URI - using memory mode")
except Exception as e:
    print(f"Mongo failed: {e}")
    db = None

MEM = {"locs":[], "sos":[], "dnw":[], "radio":[], "users":[]}

def save(col, data):
    data['time'] = datetime.utcnow().isoformat()
    if db is not None:
        try:
            db[col].insert_one(data)
            return
        except: pass
    MEM[col].append(data)
    MEM[col] = MEM[col][-100:]

def get(col):
    if db is not None:
        try:
            return list(db[col].find({}, {'_id':0}).sort('_id',-1).limit(100))
        except: pass
    return MEM.get(col, [])[::-1]

def dev_required(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if not session.get('dev_auth'):
            return jsonify({"ok":False, "error":"Not authorized"}),403
        return f(*args, **kwargs)
    return wrap

@app.route('/')
def home(): return send_from_directory('.', 'login.html')

@app.route('/<path:filename>')
def serve(filename):
    return send_from_directory('.', filename)

@app.route('/api/dev/login', methods=['POST'])
def dev_login():
    pwd = (request.get_json() or {}).get('password','').strip()
    if pwd == DEV_PASS:
        session['dev_auth']=True
        return jsonify({"ok":True})
    return jsonify({"ok":False, "error":"Developer access denied"}),401

@app.route('/api/auth/login', methods=['POST'])
def login():
    data=request.get_json() or {}
    user={"email":data.get('email','client@zondi.com'), "role":data.get('role','client'), "approved": False if data.get('role')=='patroller' else True}
    save('users', user)
    return jsonify({"ok":True,"user":user})

@app.route('/api/location/update', methods=['POST'])
def loc_update():
    data=request.get_json() or {}
    if not data.get('email') or not data.get('lat'):
        return jsonify({"ok":False}),400
    save('locs', data)
    return jsonify({"ok":True})

@app.route('/api/location/live')
def loc_live(): return jsonify(get('locs'))

@app.route('/api/sos', methods=['POST'])
def sos():
    save('sos', request.get_json() or {})
    return jsonify({"ok":True})

@app.route('/api/sos/live')
def sos_live(): return jsonify(get('sos'))

@app.route('/api/dnw/register', methods=['POST'])
def dnw_reg():
    save('dnw', request.get_json() or {})
    return jsonify({"ok":True})

@app.route('/api/dnw/scan', methods=['POST'])
def dnw_scan():
    save('dnw', request.get_json() or {})
    return jsonify({"ok":True})

@app.route('/api/dnw/live')
def dnw_live(): return jsonify(get('dnw'))

@app.route('/api/radio/send', methods=['POST'])
def radio_send():
    save('radio', request.get_json() or {})
    return jsonify({"ok":True})

@app.route('/api/radio/live')
def radio_live(): return jsonify(get('radio'))

@app.route('/api/users/list')
@dev_required
def users_list(): return jsonify(get('users'))

@app.route('/api/users/approve', methods=['POST'])
@dev_required
def approve():
    data = request.get_json() or {}
    email = data.get('email')
    # update in mongo if available
    if db is not None and email:
        try:
            db['users'].update_many({"email":email}, {"$set":{"approved":True}})
        except: pass
    # update memory
    for u in MEM['users']:
        if u.get('email')==email: u['approved']=True
    return jsonify({"ok":True})

if __name__=='__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT',10000)))
