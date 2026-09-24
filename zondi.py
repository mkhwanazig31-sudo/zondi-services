import os
from flask import Flask, request, jsonify, session, send_from_directory
from flask_cors import CORS
from pymongo import MongoClient
from datetime import datetime

app = Flask(__name__, static_folder='.')
app.secret_key = 'zondi-2024-secure-key-final'
CORS(app, supports_credentials=True)

# ===== PASSWORD YOU WANTED =====
DEV_PASS = 'zondi@123'

# Mongo (keep your old URI)
MONGO_URI = os.environ.get('MONGO_URI', 'mongodb+srv://zondi:zondi123@cluster0.mongodb.net/zondi?retryWrites=true&w=majority')
client = MongoClient(MONGO_URI)
db = client.get_database('zondi')

@app.route('/')
def home():
    return send_from_directory('.', 'login.html')

@app.route('/<path:filename>')
def serve_file(filename):
    # Allow these files to be served
    allowed = ['login.html','clients.html','patrol.html','developers.html','manifest.json','sw.js']
    if filename in allowed or filename.startswith('api/'):
        return send_from_directory('.', filename)
    # For dev portal check
    if filename == 'developers.html':
        if not session.get('dev_auth'):
            return send_from_directory('.', 'login.html')
        return send_from_directory('.', 'developers.html')
    return send_from_directory('.', filename)

# ===== DEV LOGIN API - THIS FIXES YOUR ERROR =====
@app.route('/api/dev/login', methods=['POST'])
def dev_login():
    data = request.get_json() or {}
    pwd = data.get('password','').strip()
    if pwd == DEV_PASS:
        session['dev_auth'] = True
        session.permanent = True
        return jsonify({"ok":True, "redirect":"/developers.html"})
    else:
        return jsonify({"ok":False, "error":"Developer access denied"}), 401

@app.route('/api/dev/check')
def dev_check():
    return jsonify({"ok": bool(session.get('dev_auth'))})

@app.route('/api/dev/logout', methods=['POST'])
def dev_logout():
    session.pop('dev_auth', None)
    return jsonify({"ok":True})

# ===== YOUR OTHER APIS KEEP SAME =====
@app.route('/api/sos', methods=['POST'])
def sos():
    data = request.get_json()
    data['time'] = datetime.utcnow().isoformat()
    db.sos.insert_one(data)
    return jsonify({"ok":True})

@app.route('/api/sos/live')
def sos_live():
    items = list(db.sos.find({}, {'_id':0}).sort('_id',-1).limit(50))
    return jsonify(items)

@app.route('/api/dnw/register', methods=['POST'])
def dnw_reg():
    data = request.get_json()
    data['time'] = datetime.utcnow().isoformat()
    db.dnw.update_one({"stickerId":data.get('stickerId')}, {"$set":data}, upsert=True)
    return jsonify({"ok":True})

@app.route('/api/dnw/scan', methods=['POST'])
def dnw_scan():
    data = request.get_json()
    data['time'] = datetime.utcnow().isoformat()
    db.dnw_live.insert_one(data)
    return jsonify({"ok":True})

@app.route('/api/dnw/live')
def dnw_live():
    items = list(db.dnw_live.find({}, {'_id':0}).sort('_id',-1).limit(50))
    return jsonify(items)

@app.route('/api/auth/login', methods=['POST'])
def auth_login():
    data = request.get_json()
    user = db.users.find_one({"email":data.get('email')})
    if not user: 
        # auto create client if not exists
        new = {"email":data.get('email'), "role":"client", "approved":True}
        db.users.insert_one(new)
        return jsonify({"ok":True, "user":new})
    return jsonify({"ok":True, "user":{"email":user['email'],"role":user.get('role','client'),"approved":user.get('approved',True)}})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
