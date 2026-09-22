from flask import Flask, request, jsonify, send_from_directory, render_template_string
import os, json, datetime

app = Flask(__name__)
DB_FILE = "zondi_db.json"
if not os.path.exists(DB_FILE):
    with open(DB_FILE,"w") as f: json.dump({"locations":[],"sos_events":[],"users":[],"purchases":[],"videos":[]}, f)

def load_db():
    try:
        with open(DB_FILE) as f: return json.load(f)
    except: return {"locations":[],"sos_events":[],"users":[],"purchases":[],"videos":[]}
def save_db(db):
    with open(DB_FILE,"w") as f: json.dump(db,f,indent=2)

NAV = """
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<link rel="manifest" href="/manifest.json">
<meta name="theme-color" content="#ffffff">
<div style="padding:12px 16px;display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #eee;background:#fff;position:sticky;top:0;z-index:20;font-family:system-ui;backdrop-filter:blur(10px)">
<div style="font-size:10px;color:#888;letter-spacing:1px">GA-RANKUWA • SOSHANGUVE • MABOPANE</div>
<div style="display:flex;gap:10px;font-size:12px;align-items:center">
<a href="/" style="text-decoration:none;color:#111;font-weight:600">Home</a>
<a href="/shop" style="text-decoration:none;color:#111">Shop</a>
<a href="/login" style="text-decoration:none;color:#fff;background:#111;padding:6px 14px;border-radius:20px">Login</a>
</div>
</div>
"""

HOME_HTML = NAV + """
<style>body{margin:0;font-family:system-ui;background:#fff;color:#111;height:100vh;display:flex;flex-direction:column}</style>
<div style="flex:1;display:flex;flex-direction:column;justify-content:center;align-items:center;padding:24px;text-align:center">
<p style="font-size:10px;color:#888;letter-spacing:2px">GA-RANKUWA • SOSHANGUVE • MABOPANE</p>
<h1 style="font-size:28px;font-weight:800;line-height:1.1;margin:12px 0">Security that feels like family<br><span style="color:#2563eb">protects like SAPS.</span></h1>
<p style="color:#666;font-size:14px;max-width:320px">Finished app look. No floating. Shop unlocks your portal. Video vault saves SOS proof.</p>
<br>
<a href="/login" style="background:#111;color:#fff;padding:14px 28px;border-radius:12px;text-decoration:none;font-weight:700;display:block;width:280px;text-align:center">Enter App - Login / Signup</a>
<a href="/sos" style="margin-top:12px;color:#e11d48;font-size:13px;text-decoration:none">SOS panic - works without login</a>
<div style="display:flex;gap:20px;font-size:11px;color:#888;margin-top:32px"><span>✓ Works Offline</span><span>✓ Video Vault</span><span>✓ One tap SOS</span></div>
</div>
<script>if('serviceWorker' in navigator){navigator.serviceWorker.register('/sw.js')}</script>
"""

SHOP_HTML = NAV + """
<style>body{margin:0;font-family:system-ui;background:#fff}.app{max-width:420px;margin:0 auto;min-height:100vh;background:#fff}</style>
<div class="app" style="padding:16px">
<h2 style="margin:0">Shop - Unlock Portal</h2><p style="color:#666;font-size:13px">Buy pack → account unlocks portal automatically</p>
<div id="shopList" style="display:flex;flex-direction:column;gap:12px;margin-top:16px"></div>
<div style="margin-top:20px;padding:12px;background:#f8fafc;border-radius:12px;font-size:11px;color:#666">After purchase, you will be sent to Login to authorise. Your purchase is linked to email.</div>
</div>
<script>
let packs=[{id:'starter',name:'Starter Pack',price:499,desc:'1 shop - Clients Portal only',role:'client'},{id:'growth',name:'Growth Pack',price:1499,desc:'3 shops - Clients + Patrollers',role:'both',popular:true},{id:'enterprise',name:'Enterprise',price:3999,desc:'Unlimited + T780 radio',role:'both'}];
document.getElementById('shopList').innerHTML=packs.map(p=>`<div style="border:${p.popular?'2px solid #2563eb':'1px solid #eee'};border-radius:16px;padding:16px;display:flex;justify-content:space-between;align-items:center;background:#fff"><div><b>${p.name}</b>${p.popular?'<span style="background:#2563eb;color:#fff;font-size:9px;padding:2px 6px;border-radius:4px;margin-left:6px">POPULAR</span>':''}<br><span style="font-size:12px;color:#666">${p.desc}</span><br><span style="font-size:20px;font-weight:800">R${p.price}</span></div><button onclick="buy('${p.id}','${p.role}')" style="background:#111;color:#fff;padding:10px 18px;border-radius:10px;border:0;font-weight:700">Buy</button></div>`).join('');
function buy(id,role){let email=prompt('Enter email to unlock portal after purchase:'); if(!email) return; fetch('/api/purchase',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({pack:id,role:role,email:email})}).then(r=>r.json()).then(d=>{alert('Purchased! Now login with '+email+' to enter '+role+' portal'); location.href='/login';});}
</script>
"""

AUTH_HTML = NAV + """
<style>body{margin:0;font-family:system-ui;background:#fff}.app{max-width:400px;margin:0 auto;min-height:100vh;background:#fff;padding:16px;box-sizing:border-box}</style>
<div class="app">
<h2 style="text-align:center;margin:8px 0">Authorise</h2><p style="text-align:center;color:#666;font-size:13px">Home → Login → Your Portal</p>
<div style="display:flex;gap:16px;justify-content:center;margin:16px 0;font-size:13px"><button id="tab-login" onclick="showTab('login')" style="font-weight:700;border:0;background:0;border-bottom:2px solid #111">Login</button><button id="tab-register" onclick="showTab('register')" style="border:0;background:0;color:#666">Signup</button></div>
<div id="login-form"><select id="l_role" style="width:100%;padding:12px;margin:6px 0;border:1px solid #ddd;border-radius:12px"><option value="client">Client Portal</option><option value="patroller">Patrollers Portal</option></select><input id="l_email" placeholder="Email" style="width:100%;padding:12px;margin:6px 0;border:1px solid #ddd;border-radius:12px"><input id="l_pass" type="password" placeholder="Password" style="width:100%;padding:12px;margin:6px 0;border:1px solid #ddd;border-radius:12px"><button onclick="doLogin()" style="background:#111;color:#fff;padding:14px;width:100%;border:0;border-radius:12px;margin-top:10px;font-weight:700">Login & Enter Portal</button></div>
<div id="register-form" style="display:none"><select id="r_role" style="width:100%;padding:12px;margin:6px 0;border:1px solid #ddd;border-radius:12px"><option value="client">Signup as Client</option><option value="patroller">Signup as Patroller</option></select><input id="r_name" placeholder="Full Name" style="width:100%;padding:12px;margin:6px 0;border:1px solid #ddd;border-radius:12px"><input id="r_email" placeholder="Email" style="width:100%;padding:12px;margin:6px 0;border:1px solid #ddd;border-radius:12px"><input id="r_phone" placeholder="Phone" style="width:100%;padding:12px;margin:6px 0;border:1px solid #ddd;border-radius:12px"><input id="r_pass" type="password" placeholder="Password" style="width:100%;padding:12px;margin:6px 0;border:1px solid #ddd;border-radius:12px"><button onclick="doRegister()" style="background:#2563eb;color:#fff;padding:14px;width:100%;border:0;border-radius:12px;margin-top:10px;font-weight:700">Signup</button></div>
<div id="msg" style="font-size:12px;margin-top:12px;color:#16a34a;text-align:center"></div>
<div id="purchaseInfo" style="margin-top:12px;padding:10px;background:#fff7ed;border-radius:12px;font-size:11px;color:#9a3412"></div>
</div>
<script>
function showTab(t){document.getElementById('login-form').style.display=t=='login'?'block':'none';document.getElementById('register-form').style.display=t=='register'?'block':'none';}
function saveAuth(email,role,name){localStorage.setItem('zondi_auth',JSON.stringify({email:email,role:role,name:name}));}
function checkPurchase(email){fetch('/api/check-purchase/'+email).then(r=>r.json()).then(d=>{document.getElementById('purchaseInfo').innerHTML=d.has?`✅ Purchase found: ${d.pack} - Role: ${d.role} - You can enter ${d.role} portal`:`⚠️ No purchase yet - Go to Shop first or you get demo access`;});}
function doLogin(){let email=document.getElementById('l_email').value.trim();let role=document.getElementById('l_role').value;if(!email)return;checkPurchase(email);saveAuth(email,role,email);fetch('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:email,pass:document.getElementById('l_pass').value,role:role})}).then(r=>r.json()).then(d=>{if(d.ok)location.href=d.redirect; else document.getElementById('msg').innerText=d.error;});}
function doRegister(){let email=document.getElementById('r_email').value.trim();let role=document.getElementById('r_role').value;saveAuth(email,role,document.getElementById('r_name').value);fetch('/api/register',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:email,name:document.getElementById('r_name').value,phone:document.getElementById('r_phone').value,pass:document.getElementById('r_pass').value,role:role})}).then(r=>r.json()).then(d=>{if(d.ok)location.href=d.redirect; else document.getElementById('msg').innerText=d.error;});}
</script>
"""

@app.route("/")
def home(): return render_template_string(HOME_HTML)
@app.route("/shop")
def shop(): return render_template_string(SHOP_HTML)
@app.route("/login")
def login(): return render_template_string(AUTH_HTML)
@app.route("/register")
def reg(): return render_template_string(AUTH_HTML)

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
    if user.get("pass") and user.get("pass")!=data.get("pass"): return jsonify({"ok":False,"error":"Wrong password"})
    role=user.get("role")
    return jsonify({"ok":True,"redirect":"/patrollers" if role=="patroller" else "/clients"})

@app.route("/api/purchase", methods=["POST"])
def purchase():
    data=request.get_json() or {}
    db=load_db()
    db["purchases"].append({**data,"time":datetime.datetime.now().isoformat()})
    save_db(db)
    return jsonify({"ok":True})

@app.route("/api/check-purchase/<email>")
def check_purchase(email):
    db=load_db()
    p=next((x for x in reversed(db["purchases"]) if x.get("email")==email), None)
    if p: return jsonify({"has":True,**p})
    return jsonify({"has":False})

@app.route("/api/sos", methods=["POST"])
def api_sos():
    data=request.get_json(force=True) or {}
    db=load_db()
    evt={**data,"time":datetime.datetime.now().isoformat()}
    db["locations"].append(evt); db["locations"]=db["locations"][-1000:]
    db["sos_events"].append(evt)
    # video vault entry
    if data.get("type","").startswith("CLIENT_SOS"):
        db["videos"].append({"phoneId":data.get("phoneId"),"time":evt["time"],"lat":data.get("lat"),"lng":data.get("lng"),"type":"SOS_VIDEO_VAULT"})
    save_db(db)
    return jsonify({"ok":True})

@app.route("/api/sos-feed")
def sos_feed(): return jsonify(load_db()["sos_events"][-100:])
@app.route("/api/videos")
def videos(): return jsonify(load_db().get("videos",[])[-20:])

@app.route("/sos")
def sos_page(): return send_from_directory(".", "sos.html")
@app.route("/clients")
def clients_portal(): return send_from_directory(".", "clients.html")
@app.route("/client")
def client_alias(): return send_from_directory(".", "clients.html")
@app.route("/patrollers")
def patrollers_route(): return send_from_directory(".", "patrol.html")
@app.route("/patrol.html")
def patrol_file(): return send_from_directory(".", "patrol.html")
@app.route("/patrol")
def patrol_alias(): return send_from_directory(".", "patrol.html")
@app.route("/manifest.json")
def mf(): return send_from_directory(".", "manifest.json")
@app.route("/sw.js")
def sw(): return send_from_directory(".", "sw.js")
@app.route("/api/tracking/<phoneId>")
def trail(phoneId):
    db=load_db()
    return jsonify([l for l in db["locations"] if l.get("phoneId")==phoneId][-20:])

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
