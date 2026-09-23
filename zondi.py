from flask import Flask, request, jsonify, send_from_directory
import json, os
from datetime import datetime, timedelta

app = Flask(__name__, static_folder='.')

SOS_FILE = 'sos_feed.json'
USERS_FILE = 'users.json'
PATROLLER_FILE = 'patrollers_live.json'
VOICE_FILE = 'radio_talk.json'

def load_json(f):
    if not os.path.exists(f): return []
    try:
        with open(f) as fh:
            d=json.load(fh)
            return d if isinstance(d,list) else []
    except: return []

def save_json(f,data):
    with open(f,'w') as fh: json.dump(data,fh,indent=2)

@app.route('/')
def home(): return send_from_directory('.', 'login.html') if os.path.exists('login.html') else ("Zondi API",200)

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

@app.route('/api/sos', methods=['POST'])
def api_sos():
    data=request.json or {}
    data['time']=datetime.now().isoformat()
    feed=load_json(SOS_FILE)
    feed.append(data)
    if len(feed)>1000: feed=feed[-1000:]
    save_json(SOS_FILE,feed)
    return jsonify({"ok":True})

@app.route('/api/sos-feed')
def api_feed(): return jsonify(load_json(SOS_FILE)[-300:])

@app.route('/api/tracking/<phone_id>')
def api_tracking(phone_id):
    feed=load_json(SOS_FILE)
    return jsonify([x for x in feed if x.get('phoneId')==phone_id and x.get('lat')][-100:])

@app.route('/api/patroller-ping', methods=['POST'])
def pp():
    d=request.json or {}
    d['time']=datetime.now().isoformat()
    data=load_json(PATROLLER_FILE)
    data=[x for x in data if x.get('email')!=d.get('email')]
    data.append(d)
    save_json(PATROLLER_FILE,data)
    return jsonify({"ok":True})

@app.route('/api/patrollers-live')
def pl():
    data=load_json(PATROLLER_FILE)
    cutoff=datetime.now()-timedelta(minutes=5)
    fresh=[]
    for p in data:
        try:
            if datetime.fromisoformat(p.get('time',''))>cutoff: fresh.append(p)
        except: fresh.append(p)
    return jsonify(fresh)

@app.route('/api/login', methods=['POST'])
def api_login():
    d=request.json or {}
    users=load_json(USERS_FILE)
    email=d.get('email','').lower().strip()
    pwd=d.get('password','')
    u=next((x for x in users if x.get('email','').lower()==email and x.get('password')==pwd), None)
    if u: return jsonify(u)
    return jsonify({"error":"Wrong email or password"}),401

@app.route('/api/signup', methods=['POST'])
@app.route('/api/register', methods=['POST'])
def api_reg():
    d=request.json or {}
    users=load_json(USERS_FILE)
    email=d.get('email','').lower().strip()
    if not email or not d.get('password'):
        return jsonify({"error":"Email and password required"}),400
    if any(x.get('email','').lower()==email for x in users):
        return jsonify({"error":"Email already registered. Go to Login"}),400
    users.append(d)
    save_json(USERS_FILE,users)
    return jsonify({"ok":True,"user":d})

# === RADIO T720 VOICE - ADDED HERE ONLY ===
@app.route('/api/radio/talk', methods=['POST'])
def radio_talk_post():
    d=request.json or {}
    d['time']=datetime.now().isoformat()
    feed=load_json(VOICE_FILE)
    feed.append(d)
    if len(feed)>50: feed=feed[-50:]
    save_json(VOICE_FILE,feed)
    return jsonify({"ok":True})

@app.route('/api/radio/talk', methods=['GET'])
def radio_talk_get():
    channel=request.args.get('channel')
    feed=load_json(VOICE_FILE)[-20:]
    if channel:
        feed=[x for x in feed if str(x.get('channel'))==str(channel)]
    return jsonify(feed)

@app.route('/<path:path>')
def catch_all(path):
    if os.path.exists(path) and os.path.isfile(path):
        return send_from_directory('.', path)
    if path.startswith('api/'): return jsonify({"error":"not found"}),404
    return send_from_directory('.', 'login.html')

if __name__=='__main__':
    for f in [SOS_FILE,USERS_FILE,PATROLLER_FILE,VOICE_FILE]:
        if not os.path.exists(f): save_json(f,[])
    app.run(host='0.0.0.0',port=10000)
