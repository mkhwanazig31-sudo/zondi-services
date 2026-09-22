from flask import Flask, request, jsonify, send_from_directory, render_template_string
import os, json, datetime

app = Flask(__name__)

@app.after_request
def after(r):
    r.headers.add('Access-Control-Allow-Origin', '*')
    r.headers.add('Access-Control-Allow-Headers', 'Content-Type')
    r.headers.add('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')
    return r

DB_FILE = "zondi_db.json"
UPLOAD_DIR = "uploads"
if os.path.exists("/data"):
    DB_FILE = "/data/zondi_db.json"
    UPLOAD_DIR = "/data/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

if not os.path.exists(DB_FILE):
    with open(DB_FILE,"w") as f: 
        json.dump({"locations":[],"sos_events":[],"users":[],"purchases":[],"videos":[]}, f)

def load_db():
    try:
        with open(DB_FILE) as f: return json.load(f)
    except: return {"locations":[],"sos_events":[],"users":[],"purchases":[],"videos":[]}

def save_db(db):
    with open(DB_FILE,"w") as f: json.dump(db,f,indent=2)

NAV = """<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><style>body{margin:0;font-family:system-ui;background:#fff}</style>
<div style="padding:12px 16px;display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #eee;background:#fff;position:sticky;top:0;z-index:20"><div style="font-size:10px;color:#888">GA-RANKUWA • SOSHANGUVE • MABOPANE</div><div style="display:flex;gap:10px;font-size:12px"><a href="/" style="text-decoration:none;color:#111">Home</a><a href="/shop" style="text-decoration:none;color:#111">Shop</a><a href="/login" style="text-decoration:none;color:#fff;background:#111;padding:6px 14px;border-radius:20px">Login</a></div></div>"""

HOME_HTML = NAV + """<div style="max-width:420px;margin:0 auto;min-height:100vh;display:flex;flex-direction:column;justify-content:center;align-items:center;padding:24px;text-align:center"><h1 style="font-size:28px;font-weight:800">Security that feels like family<br><span style="color:#2563eb">protects like SAPS.</span></h1><p style="color:#666;font-size:13px">Every client gets 📍 pin with address - tap pin to track</p><a href="/login" style="background:#111;color:#fff;padding:14px 28px;border-radius:12px;text-decoration:none;font-weight:700;width:280px;text-align:center">Enter App</a><a href="/sos" style="margin-top:12px;color:#e11d48;font-size:13px;text-decoration:none">SOS works without login</a></div>"""

SHOP_HTML = NAV + """<div style="max-width:420px;margin:0 auto;padding:16px"><h2>Shop</h2><div id="shopList"></div></div><script>let packs=[{id:'starter',name:'Starter Pack',price:499,desc:'1 shop - Clients Portal',role:'client'},{id:'growth',name:'Growth Pack',price:1499,desc:'3 shops - Clients + Patrollers',role:'both',popular:true},{id:'enterprise',name:'Enterprise',price:3999,desc:'Unlimited + T780',role:'both'}];document.getElementById('shopList').innerHTML=packs.map(p=>`<div style="border:${p.popular?'2px solid #2563eb':'1px solid #eee'};border-radius:16px;padding:16px;display:flex;justify-content:space-between;align-items:center;margin-bottom:12px"><div><b>${p.name}</b><br><span style="font-size:12px;color:#666">${p.desc}</span><br><span style="font-size:20px;font-weight:800">R${p.price}</span></div><button onclick="buy('${p.id}','${p.role}')" style="background:#111;color:#fff;padding:10px 18px;border-radius:10px;border:0">Buy</button></div>`).join('');function buy(id,role){let email=prompt('Enter email to unlock:'); if(!email) return; fetch('/api/purchase',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({pack:id,role:role,email:email})}).then(()=>{alert('Purchased! Now login'); location.href='/login';});}</script>"""

AUTH_HTML = """<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><style>body{margin:0;font-family:system-ui;background:#fff}.app{max-width:420px;margin:0 auto;min-height:100vh;background:#fff;padding:0 16px 80px;box-sizing:border-box}.seg{display:flex;background:#f1f5f9;border-radius:12px;padding:4px;gap:4px}.seg button{flex:1;padding:10px;border:0;border-radius:8px;font-weight:700}.seg .active{background:#111;color:#fff}input{width:100%;padding:12px;margin:6px 0;border:1px solid #ddd;border-radius:12px;box-sizing:border-box}</style><div style="padding:12px 16px;display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #eee;background:#fff;position:sticky;top:0;z-index:20"><div style="font-size:10px;color:#888">GA-RANKUWA • SOSHANGUVE • MABOPANE</div><div style="display:flex;gap:10px;font-size:12px"><a href="/" style="text-decoration:none;color:#111">Home</a><a href="/shop" style="text-decoration:none;color:#111">Shop</a></div></div><div class="app"><h2 style="text-align:center">Authorise - Add Your 📍 Pin</h2><div style="display:flex;gap:16px;justify-content:center;margin:12px 0;font-size:13px"><button id="tab-login" onclick="showTab('login')" style="font-weight:700;border:0;background:0;border-bottom:2px solid #111">Login</button><button id="tab-register" onclick="showTab('register')" style="border:0;background:0;color:#888">Signup + Pin</button></div><div style="margin:12px 0"><div style="font-size:11px;color:#888;margin-bottom:6px">CHOOSE PORTAL</div><div class="seg" id="roleSeg"><button id="btn-client" class="active" onclick="setRole('client')">Client Portal</button><button id="btn-patroller" onclick="setRole('patroller')">Patrollers Portal</button></div></div><div id="login-form"><input id="l_email" placeholder="Email"><input id="l_pass" type="password" placeholder="Password"><button onclick="doLogin()" style="background:#111;color:#fff;padding:14px;width:100%;border:0;border-radius:12px;margin-top:10px;font-weight:700">Login & Enter Portal</button></div><div id="register-form" style="display:none"><input id="r_name" placeholder="Full Name - e.g. Gontse"><input id="r_email" placeholder="Email"><input id="r_phone" placeholder="Phone"><input id="r_address" placeholder="📍 Shop Address - e.g. 95 Unit 20 Ga-Rankuwa"><input id="r_shop" placeholder="Shop Name - e.g. Gontse Tuck Shop"><input id="r_pass" type="password" placeholder="Password"><button onclick="doRegister()" style="background:#2563eb;color:#fff;padding:14px;width:100%;border:0;border-radius:12px;margin-top:10px;font-weight:700">Create Pin + Signup</button><div style="font-size:10px;color:#666;margin-top:6px">Your pin will be: 📍Gontse - 95 Unit 20 - visible to patrollers to tap</div></div><div id="msg" style="text-align:center;font-size:12px;margin-top:12px;color:#16a34a"></div></div><script>let currentRole='client';function setRole(r){currentRole=r;document.getElementById('btn-client').className=r=='client'?'active':'';document.getElementById('btn-patroller').className=r=='patroller'?'active':'';}function showTab(t){document.getElementById('login-form').style.display=t=='login'?'block':'none';document.getElementById('register-form').style.display=t=='register'?'block':'none';}function saveAuth(e,r,n,a){localStorage.setItem('zondi_auth',JSON.stringify({email:e,role:r,name:n,address:a}));localStorage.setItem('zondi_address',a||'');localStorage.setItem('zondi_shopname',document.getElementById('r_shop')?.value||'Shop');}function doLogin(){let e=document.getElementById('l_email').value.trim();let s=JSON.parse(localStorage.getItem('zondi_auth')||'{}');saveAuth(e,currentRole,s.name||e,s.address||'');fetch('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:e,pass:document.getElementById('l_pass').value,role:currentRole})}).then(r=>r.json()).then(d=>{if(d.ok)location.href=d.redirect;else document.getElementById('msg').innerText=d.error;});}function doRegister(){let e=document.getElementById('r_email').value.trim();let a=document.getElementById('r_address').value.trim();if(!a){document.getElementById('msg').innerText='Add your address';return;}saveAuth(e,currentRole,document.getElementById('r_name').value,a);fetch('/api/register',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:e,name:document.getElementById('r_name').value,phone:document.getElementById('r_phone').value,address:a,shop:document.getElementById('r_shop').value,pass:document.getElementById('r_pass').value,role:currentRole})}).then(r=>r.json()).then(d=>{if(d.ok)location.href=d.redirect;else document.getElementById('msg').innerText=d.error;});}</script>"""

@app.route("/")
def home(): return render_template_string(HOME_HTML)
@app.route("/shop")
def shop(): return render_template_string(SHOP_HTML)
@app.route("/login")
def login(): return render_template_string(AUTH_HTML)
@app.route("/api/register", methods=["POST"])
def api_register():
    data=request.get_json() or {}
    db=load_db()
    if any(u.get("email")==data.get("email") for u in db["users"]):
        return jsonify({"ok":False,"error":"Email exists - Login"})
    db["users"].append({**data,"created":datetime.datetime.now().isoformat()})
    save_db(db)
    return jsonify({"ok":True,"redirect":"/patrollers" if data.get("role")=="patroller" else "/clients"})
@app.route("/api/login", methods=["POST"])
def api_login():
    data=request.get_json() or {}
    db=load_db()
    user=next((u for u in db["users"] if u.get("email")==data.get("email")), None)
    if not user: return jsonify({"ok":False,"error":"Not found - Signup"})
    return jsonify({"ok":True,"redirect":"/patrollers" if user.get("role")=="patroller" else "/clients"})
@app.route("/api/purchase", methods=["POST"])
def purchase():
    data=request.get_json() or {}
    db=load_db(); db["purchases"].append({**data,"time":datetime.datetime.now().isoformat()}); save_db(db)
    return jsonify({"ok":True})
@app.route("/api/sos", methods=["POST","OPTIONS"])
def api_sos():
    if request.method=="OPTIONS": return jsonify({"ok":True})
    data=request.get_json(force=True) or {}
    db=load_db()
    user=next((u for u in db["users"] if u.get("email")==data.get("email")), None)
    if user:
        if not data.get("address"): data["address"]=user.get("address","")
        if not data.get("shopName"): data["shopName"]=user.get("shop","")
    if data.get("latitude"): data["lat"]=data.get("latitude")
    if data.get("longitude"): data["lng"]=data.get("longitude")
    try: data["lat"]=float(data.get("lat",0))
    except: data["lat"]=0
    try: data["lng"]=float(data.get("lng",0))
    except: data["lng"]=0
    evt={**data,"time":datetime.datetime.now().isoformat()}
    db["locations"].append(evt); db["locations"]=db["locations"][-2000:]
    db["sos_events"].append(evt); db["sos_events"]=db["sos_events"][-500:]
    save_db(db)
    return jsonify({"ok":True})
@app.route("/api/sos-feed")
def sos_feed(): return jsonify(load_db()["sos_events"][-200:])
@app.route("/api/users")
def users(): return jsonify(load_db()["users"][-100:])
@app.route("/health")
def health(): db=load_db(); return jsonify({"ok":True,"users":len(db["users"]),"sos":len(db["sos_events"])})
@app.route("/clients")
def clients_portal(): return send_from_directory(".", "clients.html")
@app.route("/patrollers")
def patrollers_route(): return send_from_directory(".", "patrol.html")
@app.route("/api/tracking/<phoneId>")
def trail(phoneId):
    db=load_db()
    return jsonify([l for l in db["locations"] if l.get("phoneId")==phoneId][-30:])
@app.route("/manifest.json")
def mf(): return send_from_directory(".", "manifest.json") if os.path.exists("manifest.json") else jsonify({})
@app.route("/sw.js")
def sw(): return send_from_directory(".", "sw.js") if os.path.exists("sw.js") else ("",204)
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
