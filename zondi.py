# zondi.py - NO GOOGLE CONSOLE - Free auth sync - White theme
from flask import Flask, request, jsonify, send_from_directory, render_template_string
import os, json, datetime

app = Flask(__name__)

DB_FILE = "zondi_db.json"
if not os.path.exists(DB_FILE):
    with open(DB_FILE,"w") as f: json.dump({"locations":[],"sos_events":[],"users":[]}, f)

def load_db():
    try:
        with open(DB_FILE) as f: return json.load(f)
    except: return {"locations":[],"sos_events":[],"users":[]}
def save_db(db):
    with open(DB_FILE,"w") as f: json.dump(db,f,indent=2)

NAV = """
<div style="padding:12px 20px;display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #eee;background:#fff;position:sticky;top:0;z-index:20;font-family:system-ui">
<div style="font-size:10px;color:#888;letter-spacing:1px">GA-RANKUWA • SOSHANGUVE • MABOPANE</div>
<div style="display:flex;gap:12px;font-size:13px;align-items:center">
<a href="/" style="text-decoration:none;color:#333">Home</a>
<a href="/shop" style="text-decoration:none;color:#333">Shop</a>
<a href="/login" style="text-decoration:none;color:#fff;background:#111;padding:6px 14px;border-radius:20px">Login</a>
</div>
</div>
"""

HOME_HTML = NAV + """
<div style="font-family:system-ui;padding:80px 24px;text-align:center;background:#fff;min-height:80vh">
<p style="font-size:10px;color:#888;letter-spacing:2px">GA-RANKUWA • SOSHANGUVE • MABOPANE</p>
<h1 style="font-size:28px;font-weight:800;color:#111">Security that feels like family<br><span style="color:#2563eb">protects like SAPS.</span></h1>
<p style="color:#666;font-size:14px">First authorise, then we send you to your portal. No Google subscription needed.</p>
<br>
<a href="/login" style="background:#2563eb;color:#fff;padding:12px 24px;border-radius:8px;text-decoration:none;font-weight:700">Login / Signup to Enter Portal</a>
<br><br>
<div style="font-size:12px;color:#888">✓ Free sync ✓ Clients Portal ✓ Patrollers Portal ✓ SOS no login</div>
</div>
"""

SHOP_HTML = NAV + """
<div style="font-family:system-ui;padding:24px;max-width:900px;margin:auto;background:#fff;min-height:80vh"><h2>Shop</h2></div>
"""

AUTH_HTML = NAV + """
<div style="font-family:system-ui;display:flex;justify-content:center;padding:30px 20px;background:#fff;min-height:90vh">
<div style="width:380px;text-align:center">
<h2 style="color:#111">Authorise to Enter</h2><p style="color:#666;font-size:13px">Home → Login/Signup → Your Portal (auto)</p>

<div style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:10px;padding:8px;font-size:11px;color:#166534;margin:12px 0">✓ Free sync - No Google Console. Your email+password syncs on any phone via our DB.</div>

<div style="display:flex;gap:16px;justify-content:center;margin:14px 0;font-size:13px">
<button id="tab-login" onclick="showTab('login')" style="font-weight:700;border:0;background:0;border-bottom:2px solid #2563eb">Login</button>
<button id="tab-register" onclick="showTab('register')" style="border:0;background:0;color:#666">Signup</button>
</div>

<div id="login-form">
<select id="l_role" style="width:100%;padding:10px;margin:6px 0;border:1px solid #ddd;border-radius:8px"><option value="client">Client Portal - Shop Owner</option><option value="patroller">Patrollers Portal - Guard</option></select>
<input id="l_email" placeholder="Email - e.g. you@gmail.com" style="width:100%;padding:10px;margin:6px 0;border:1px solid #ddd;border-radius:8px">
<input id="l_pass" type="password" placeholder="Password" style="width:100%;padding:10px;margin:6px 0;border:1px solid #ddd;border-radius:8px">
<button onclick="doLogin()" style="background:#2563eb;color:#fff;padding:11px;width:100%;border:0;border-radius:8px;margin-top:10px;font-weight:700">Login & Go to My Portal</button>
</div>

<div id="register-form" style="display:none">
<select id="r_role" style="width:100%;padding:10px;margin:6px 0;border:1px solid #ddd;border-radius:8px"><option value="client">Signup as Client - Shop Owner</option><option value="patroller">Signup as Patroller - Guard</option></select>
<input id="r_name" placeholder="Full Name" style="width:100%;padding:10px;margin:6px 0;border:1px solid #ddd;border-radius:8px">
<input id="r_email" placeholder="Email - will sync on any device" style="width:100%;padding:10px;margin:6px 0;border:1px solid #ddd;border-radius:8px">
<input id="r_phone" placeholder="Phone" style="width:100%;padding:10px;margin:6px 0;border:1px solid #ddd;border-radius:8px">
<input id="r_pass" type="password" placeholder="Create Password" style="width:100%;padding:10px;margin:6px 0;border:1px solid #ddd;border-radius:8px">
<button onclick="doRegister()" style="background:#111;color:#fff;padding:11px;width:100%;border:0;border-radius:8px;margin-top:10px;font-weight:700">Signup & Authorise</button>
</div>

<div id="msg" style="font-size:12px;margin-top:12px;color:#16a34a"></div>

<div style="margin-top:14px;padding:10px;background:#f8fafc;border-radius:8px;font-size:11px;color:#666;text-align:left">
<b>New Flow (no Google):</b><br>1. Home → Login<br>2. Choose role: Client or Patroller<br>3. Signup with email/pass → we save in DB<br>4. Auto redirect to <b>your portal only</b><br>5. On another phone, just Login with same email/pass → same portal opens = sync!
</div>
</div>
</div>
<script>
function showTab(t){
 document.getElementById('login-form').style.display=t=='login'?'block':'none';
 document.getElementById('register-form').style.display=t=='register'?'block':'none';
}
function saveAuth(email, role, name){
 localStorage.setItem('zondi_auth', JSON.stringify({email:email, role:role, name:name, time:Date.now()}));
}
function doLogin(){
 let email=document.getElementById('l_email').value.trim(); let pass=document.getElementById('l_pass').value; let role=document.getElementById('l_role').value;
 if(!email||!pass){document.getElementById('msg').innerText='Enter email & password'; return;}
 saveAuth(email, role, email);
 fetch('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:email,pass:pass,role:role})})
 .then(r=>r.json()).then(d=>{
   if(d.ok){ document.getElementById('msg').innerText='Authorised! Going to '+role+' portal...'; setTimeout(()=>location.href=d.redirect,800);}
   else document.getElementById('msg').innerText=d.error;
 });
}
function doRegister(){
 let email=document.getElementById('r_email').value.trim(); let role=document.getElementById('r_role').value; let name=document.getElementById('r_name').value; let pass=document.getElementById('r_pass').value;
 if(!email||!pass){document.getElementById('msg').innerText='Enter email & password'; return;}
 saveAuth(email, role, name);
 fetch('/api/register',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:email,name:name,phone:document.getElementById('r_phone').value,pass:pass,role:role})})
 .then(r=>r.json()).then(d=>{ 
   if(d.ok){document.getElementById('msg').innerText='Account created as '+role+'! Redirecting...'; setTimeout(()=>location.href=d.redirect,1000);}
   else document.getElementById('msg').innerText=d.error;
 });
}
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
        return jsonify({"ok":False,"error":"Email already exists - Login instead"})
    if not data.get("email") or not data.get("pass"):
        return jsonify({"ok":False,"error":"Email & password needed"})
    data["created"]=datetime.datetime.now().isoformat()
    db["users"].append(data)
    save_db(db)
    redirect = "/patrollers" if data.get("role")=="patroller" else "/clients"
    return jsonify({"ok":True,"redirect":redirect})

@app.route("/api/login", methods=["POST"])
def api_login():
    data=request.get_json() or {}
    db=load_db()
    user = next((u for u in db["users"] if u.get("email")==data.get("email") and u.get("pass")==data.get("pass")), None)
    # also allow if user exists but pass different role - we update role
    if not user and any(u.get("email")==data.get("email") for u in db["users"]):
        return jsonify({"ok":False,"error":"Wrong password"})
    if not user:
        # for demo, allow first login to auto-create? no, require signup
        return jsonify({"ok":False,"error":"Not found - please Signup first"})
    role = user.get("role") or data.get("role","client")
    redirect = "/patrollers" if role=="patroller" else "/clients"
    return jsonify({"ok":True,"redirect":redirect, "role":role})

@app.route("/api/sos", methods=["POST"])
def api_sos():
    data=request.get_json(force=True) or {}
    db=load_db()
    evt={**data,"time":datetime.datetime.now().isoformat()}
    db["locations"].append(evt)
    db["locations"]=db["locations"][-1000:]
    db["sos_events"].append(evt)
    save_db(db)
    return jsonify({"ok":True})

@app.route("/api/sos-feed")
def sos_feed(): return jsonify(load_db()["sos_events"][-100:])

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
