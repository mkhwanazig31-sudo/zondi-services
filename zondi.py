import os
from flask import Flask, request, jsonify, session, send_from_directory
from flask_cors import CORS
from datetime import datetime

app = Flask(__name__, static_folder='.')
app.secret_key = 'zondi-final-2026-secure'
CORS(app, supports_credentials=True)

DEV_PASS = 'zondi@123'

# Mongo safe - won't crash
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

# memory fallback if no DB
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

@app.route('/')
def home(): return send_from_directory('.', 'login.html')

@app.route('/<path:filename>')
def serve(filename):
    return send_from_directory('.', filename)

# AUTH
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
    user={"email":data.get('email','client@zondi.com'), "role":data.get('role','client'), "approved":True}
    save('users', user)
    return jsonify({"ok":True,"user":user})

# LIVE LOCATION - CLIENT MOVES IT SHOWS
@app.route('/api/location/update', methods=['POST'])
def loc_update():
    data=request.get_json() or {}
    save('locs', data) # {email, lat, lng, role}
    return jsonify({"ok":True})

@app.route('/api/location/live')
def loc_live():
    return jsonify(get('locs'))

# SOS
@app.route('/api/sos', methods=['POST'])
def sos():
    save('sos', request.get_json() or {})
    return jsonify({"ok":True})

@app.route('/api/sos/live')
def sos_live(): return jsonify(get('sos'))

# DNW PB708
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

# RADIO FEATURE - Walkie talkie
@app.route('/api/radio/send', methods=['POST'])
def radio_send():
    data=request.get_json() or {}
    # {from, to, audioBase64, lat, lng}
    save('radio', data)
    return jsonify({"ok":True})

@app.route('/api/radio/live')
def radio_live(): return jsonify(get('radio'))

# DEV - Approve patrollers
@app.route('/api/users/list')
def users_list(): return jsonify(get('users'))

@app.route('/api/users/approve', methods=['POST'])
def approve():
    if not session.get('dev_auth'): return jsonify({"ok":False}),403
    return jsonify({"ok":True})

if __name__=='__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT',10000)))
