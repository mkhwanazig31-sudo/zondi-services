from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import json, os, secrets
from datetime import datetime
app=Flask(__name__); CORS(app)
USERS_FILE='users.json'; SOS_FILE='sos_reports.json'; DNW_FILE='dnw_assets.json'
DEV_PASS='DNW2024!Boss'; DEV_TOKENS=set()
def load_json(f):
    if not os.path.exists(f): return []
    try: return json.load(open(f,'r',encoding='utf-8'))
    except: return []
def save_json(f,d): json.dump(d,open(f,'w',encoding='utf-8'),indent=2)
def is_dev():
    t=request.headers.get('Authorization','').replace('Bearer ','').strip()
    return t in DEV_TOKENS

@app.route('/')
def h(): return send_from_directory('.','login.html')
@app.route('/login')
def l(): return send_from_directory('.','login.html')
@app.route('/developers')
@app.route('/developers.html')
def d(): return send_from_directory('.','developers.html')
@app.route('/clients')
@app.route('/clients.html')
def c(): return send_from_directory('.','clients.html')
@app.route('/patrol')
@app.route('/patrol.html')
def p(): return send_from_directory('.','patrol.html')
@app.route('/register')
@app.route('/register.html')
def r(): return send_from_directory('.','register.html')

@app.route('/api/register',methods=['POST'])
def reg():
    d=request.json or {}; e=d.get('email','').lower().strip()
    users=load_json(USERS_FILE)
    if any(u.get('email','').lower()==e for u in users): return jsonify({"error":"Email exists"}),400
    role=d.get('role','client')
    users.append({"email":e,"password":d.get('password',''),"role":role,"name":d.get('name',e),"phone":d.get('phone',''),"status":"pending" if role=='patroller' else "approved","approved":False if role=='patroller' else True,"created_at":datetime.now().isoformat()})
    save_json(USERS_FILE,users); return jsonify({"ok":True})

@app.route('/api/login',methods=['POST'])
def log():
    d=request.json or {}; e=d.get('email','').lower().strip(); pw=d.get('password','')
    users=load_json(USERS_FILE)
    u=next((x for x in users if x.get('email','').lower()==e and x.get('password','')==pw),None)
    if not u: return jsonify({"error":"Wrong email or password"}),401
    if u.get('role')=='patroller' and not u.get('approved'): return jsonify({"error":"Waiting for Developer approval"}),403
    return jsonify({k:u.get(k) for k in ['email','role','name','phone','status','approved']})

@app.route('/api/developer-login',methods=['POST'])
@app.route('/api/admin/login',methods=['POST'])
def dev_login():
    d=request.json or {}
    if d.get('password')!=DEV_PASS: return jsonify({"error":"Wrong developer password"}),401
    t=secrets.token_hex(16); DEV_TOKENS.add(t)
    return jsonify({"ok":True,"token":t,"dev_token":t})

@app.route('/api/dev-logout',methods=['POST'])
def dev_out():
    t=request.headers.get('Authorization','').replace('Bearer ','').strip()
    DEV_TOKENS.discard(t); return jsonify({"ok":True})

@app.route('/api/admin/pending')
def pending():
    if not is_dev(): return jsonify({"error":"Unauthorized"}),401
    users=load_json(USERS_FILE)
    pats=[u for u in users if u.get('role')=='patroller']
    return jsonify({"pending":[u for u in pats if u.get('status')!='approved'],"all_patrollers":pats})

@app.route('/api/admin/approve',methods=['POST'])
def approve():
    if not is_dev(): return jsonify({"error":"Unauthorized"}),401
    d=request.json or {}; e=d.get('email','').lower(); act=d.get('action','approve')
    users=load_json(USERS_FILE)
    if act=='approve':
        for u in users:
            if u.get('email','').lower()==e: u['status']='approved'; u['approved']=True
    elif act=='reject': users=[u for u in users if u.get('email','').lower()!=e]
    elif act=='revoke':
        for u in users:
            if u.get('email','').lower()==e: u['status']='pending'; u['approved']=False
    save_json(USERS_FILE,users); return jsonify({"ok":True})

@app.route('/api/sos',methods=['POST'])
def sos(): d=request.json or {}; d['time']=datetime.now().isoformat(); data=load_json(SOS_FILE); data.append(d); save_json(SOS_FILE,data[-1000:]); return jsonify({"ok":True})
@app.route('/api/sos/live')
def sos_live(): return jsonify(load_json(SOS_FILE)[-500:])

# DNW PB708 BOSS FEATURE
@app.route('/api/dnw/register',methods=['POST'])
def dnw_r(): d=request.json or {}; d['time']=datetime.now().isoformat(); data=load_json(DNW_FILE); data=[x for x in data if x.get('stickerId')!=d.get('stickerId')]; data.append(d); save_json(DNW_FILE,data); return jsonify({"ok":True})
@app.route('/api/dnw/live')
def dnw_l(): return jsonify(load_json(DNW_FILE)[-500:])
@app.route('/api/dnw/scan',methods=['POST'])
def dnw_s():
    d=request.json or {}; d['time']=datetime.now().isoformat()
    sos=load_json(SOS_FILE); sos.append({"phoneId":d.get('stickerId'),"name":f"{d.get('name')} [PB708]","lat":d.get('lat'),"lng":d.get('lng'),"address":f"DNW {d.get('type','')} Asset","time":d['time']}); save_json(SOS_FILE,sos[-1000:])
    assets=load_json(DNW_FILE); assets=[x for x in assets if x.get('stickerId')!=d.get('stickerId')]; assets.append(d); save_json(DNW_FILE,assets); return jsonify({"ok":True})

@app.route('/<path:path>')
def catch_all(path):
    if os.path.exists(path): return send_from_directory('.',path)
    return jsonify({"error":"Not found"}),404

if __name__=='__main__':
    for f in [USERS_FILE,SOS_FILE,DNW_FILE]:
        if not os.path.exists(f): save_json(f,[])
    app.run(host='0.0.0.0',port=5000,debug=True)
