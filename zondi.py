from flask import Flask, request, jsonify, send_from_directory
import json, os
from datetime import datetime

app = Flask(__name__, static_folder='.')

SOS_FILE = 'sos_feed.json'
USERS_FILE = 'users.json'
PATROLLER_FILE = 'patrollers_live.json'

def load_json(f):
    if not os.path.exists(f): return []
    try:
        with open(f) as fh: return json.load(fh)
    except: return []

def save_json(f, data):
    with open(f,'w') as fh: json.dump(fh, data, indent=2)

# FIX NOT FOUND - serve files correctly
@app.route('/')
def home():
    if os.path.exists('index.html'):
        return send_from_directory('.', 'index.html')
    return "Zondi Services - API Running. Go to /clients or /patrollers", 200

@app.route('/login')
def login_page(): return send_from_directory('.', 'login.html')

@app.route('/clients')
@app.route('/client')
@app.route('/clients.html')
def clients_page(): return send_from_directory('.', 'clients.html')

@app.route('/patrollers')
@app.route('/patrol')
@app.route('/patrollers.html')
@app.route('/patrol.html')
def patrollers_page(): return send_from_directory('.', 'patrol.html')

@app.route('/shop')
def shop_page():
    if os.path.exists('shop.html'): return send_from_directory('.', 'shop.html')
    return home()

@app.route('/sos')
def sos_page():
    if os.path.exists('sos.html'): return send_from_directory('.', 'sos.html')
    return home()

@app.route('/sw.js')
def sw(): return send_from_directory('.', 'sw.js')

@app.route('/manifest.json')
def manifest():
    if os.path.exists('manifest.json'): return send_from_directory('.', 'manifest.json')
    return jsonify({"name":"Zondi"})

# API
@app.route('/api/sos', methods=['POST'])
def api_sos():
    data = request.json
    data['time'] = datetime.now().isoformat()
    feed = load_json(SOS_FILE)
    feed.append(data)
    if len(feed) > 800: feed = feed[-800:]
    save_json(SOS_FILE, feed)
    return jsonify({"ok":True})

@app.route('/api/sos-feed')
def api_feed(): return jsonify(load_json(SOS_FILE))

@app.route('/api/tracking/<phone_id>')
def api_tracking(phone_id):
    feed = load_json(SOS_FILE)
    t = [x for x in feed if x.get('phoneId')==phone_id]
    return jsonify(t)

@app.route('/api/patroller-ping', methods=['POST'])
def patroller_ping():
    d=request.json
    d['time']=datetime.now().isoformat()
    data=load_json(PATROLLER_FILE)
    data=[x for x in data if x.get('email')!=d.get('email')]
    data.append(d)
    save_json(PATROLLER_FILE, data)
    return jsonify({"ok":True})

@app.route('/api/patrollers-live')
def patrollers_live(): return jsonify(load_json(PATROLLER_FILE))

@app.route('/api/login', methods=['POST'])
def api_login():
    d=request.json
    users=load_json(USERS_FILE)
    u=next((x for x in users if x['email']==d['email'] and x['password']==d['password']), None)
    if u: return jsonify(u)
    return jsonify({"error":"not found"}), 401

@app.route('/api/signup', methods=['POST'])
def api_signup():
    d=request.json
    users=load_json(USERS_FILE)
    users.append(d)
    save_json(USERS_FILE, users)
    return jsonify({"ok":True})

# CATCH ALL - prevents Not Found screenshot
@app.route('/<path:path>')
def catch_all(path):
    if os.path.exists(path):
        return send_from_directory('.', path)
    # if someone types /something wrong, send to login
    return send_from_directory('.', 'login.html') if os.path.exists('login.html') else home()

if __name__=='__main__':
    app.run(host='0.0.0.0', port=10000)
