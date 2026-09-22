# zondi.py - FIXED: Shop tab + Register works + SOS in nav
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

# NAV BAR - now has Shop, SOS, Login
NAV = """
<div style="padding:12px 24px;display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #eee;font-family:system-ui">
<div style="font-size:11px;color:#888">GA-RANKUWA • SOSHANGUVE • MABOPANE</div>
<div style="display:flex;gap:16px;font-size:13px">
<a href="/" style="text-decoration:none;color:#333">Home</a>
<a href="/shop" style="text-decoration:none;color:#333;font-weight:700">Shop</a>
<a href="/sos" style="text-decoration:none;color:#fff;background:#e11d48;padding:4px 10px;border-radius:12px">SOS</a>
<a href="/login" style="text-decoration:none;color:#333">Login</a>
</div>
</div>
"""

HOME_HTML = NAV + """
<div style="font-family:system-ui;padding:80px 24px;text-align:center">
<p style="font-size:10px;color:#888;letter-spacing:2px">GA-RANKUWA • SOSHANGUVE • MABOPANE</p>
<h1 style="font-size:28px;font-weight:800;line-height:1.2">Security that feels like family<br><span style="color:#2563eb">protects like SAPS.</span></h1>
<p style="color:#666;font-size:14px">No more black screens. Clean, friendly, works offline. Buy protection in our Shop, live online.</p>
<br>
<a href="/shop" style="background:#2563eb;color:#fff;padding:10px 20px;border-radius:8px;text-decoration:none;font-weight:700">Go to Shop</a>
<a href="/login" style="margin-left:12px;color:#333;text-decoration:none">Login</a>
<br><br>
<div style="display:flex;justify-content:center;gap:40px;font-size:12px;color:#888;margin-top:40px">
<div>✓ Works Offline</div><div>✓ Video Proof Vault</div><div>✓ One tap SOS</div>
</div>
<br><br>
<a href="/sos" style="color:#e11d48;font-size:13px;text-decoration:none">→ New: Add SOS panic button to home screen (no login)</a>
</div>
"""

SHOP_HTML = NAV + """
<div style="font-family:system-ui;padding:24px;max-width:800px;margin:auto">
<h2>Zondi Shop</h2><p style="color:#666;font-size:13px">Buy protection - works offline</p>
<div style="display:flex;gap:16px;flex-wrap:wrap;margin-top:20px">
<div style="border:1px solid #eee;border-radius:12px;padding:20px;width:220px;text-align:center"><h4>Starter Pack</h4><div style="font-size:24px;font-weight:800">R499</div><p style="font-size:12px;color:#666">For 1 shop</p><button style="background:#2563eb;color:#fff;padding:8px 16px;border-radius:6px;border:0;width:100%;margin-top:10px">Add to Cart</button></div>
<div style="border:2px solid #2563eb;border-radius:12px;padding:20px;width:220px;text-align:center"><h4>Growth Pack</h4><div style="background:#2563eb;color:#fff;font-size:10px;display:inline-block;padding:2px 6px;border-radius:4px">POPULAR</div><div style="font-size:24px;font-weight:800">R1,499</div><p style="font-size:12px;color:#666">For 3 shops + SOS</p><button style="background:#2563eb;color:#fff;padding:8px 16px;border-radius:6px;border:0;width:100%;margin-top:10px">Buy Growth Pack</button></div>
<div style="border:1px solid #eee;border-radius:12px;padding:20px;width:220px;text-align:center"><h4>Enterprise</h4><div style="font-size:24px;font-weight:800">R3,999</div><p style="font-size:12px;color:#666">Unlimited + T780 radio</p><button style="background:#000;color:#fff;padding:8px 16px;border-radius:6px;border:0;width:100%;margin-top:10px">Buy Enterprise</button></div>
</div>
<br><p style="font-size:12px">Also: <a href="/sos" style="color:#e11d48">/sos panic</a> | <a href="/clients">/clients tracking</a></p>
</div>
"""

# LOGIN + REGISTER IN ONE PAGE - TABS NOW WORK
AUTH_HTML = NAV + """
<div style="font-family:system-ui;display:flex;justify-content:center;padding:60px 20px">
<div style="width:340px;text-align:center">
<h2>Welcome</h2><p style="color:#666;font-size:13px">Login to your shop</p>
<div style="display:flex;gap:20px;justify-content:center;font-size:13px;margin:16px 0">
<button id="tab-login" onclick="showTab('login')" style="font-weight:700;border:0;background:0;border-bottom:2px solid #2563eb;padding-bottom:4px">Login</button>
<button id="tab-register" onclick="showTab('register')" style="border:0;background:0;color:#666;padding-bottom:4px">Register</button>
</div>

<div id="login-form">
<input id="l_user" placeholder="Username / Email" style="width:100%;padding:10px;margin:6px 0;border:1px solid #ddd;border-radius:6px">
<input id="l_pass" type="password" placeholder="Password" style="width:100%;padding:10px;margin:6px 0;border:1px solid #ddd;border-radius:6px">
<button onclick="doLogin()" style="background:#2563eb;color:#fff;padding:10px;width:100%;border:0;border-radius:6px;margin-top:10px">Login</button>
</div>

<div id="register-form" style="display:none">
<input id="r_name" placeholder="Full Name" style="width:100%;padding:10px;margin:6px 0;border:1px solid #ddd;border-radius:6px">
<input id="r_email" placeholder="Email" style="width:100%;padding:10px;margin:6px 0;border:1px solid #ddd;border-radius:6px">
<input id="r_phone" placeholder="Phone - e.g. 071..." style="width:100%;padding:10px;margin:6px 0;border:1px solid #ddd;border-radius:6px">
<input id="r_pass" type="password" placeholder="Create Password" style="width:100%;padding:10px;margin:6px 0;border:1px solid #ddd;border-radius:6px">
<button onclick="doRegister()" style="background:#000;color:#fff;padding:10px;width:100%;border:0;border-radius:6px;margin-top:10px">Create Account</button>
<p style="font-size:11px;color:#666;margin-top:8px">By registering, you agree to always-on tracking for shop safety</p>
</div>

<div id="msg" style="font-size:12px;margin-top:10px;color:green"></div>
</div>
</div>
<script>
function showTab(t){
 document.getElementById('login-form').style.display = t=='login' ? 'block' : 'none';
 document.getElementById('register-form').style.display = t=='register' ? 'block' : 'none';
 document.getElementById('tab-login').style.borderBottom = t=='login' ? '2px solid #2563eb' : 'none';
 document.getElementById('tab-register').style.borderBottom = t=='register' ? '2px solid #2563eb' : 'none';
}
function doLogin(){
 fetch('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({user:document.getElementById('l_user').value, pass:document.getElementById('l_pass').value})})
 .then(r=>r.json()).then(d=>{document.getElementById('msg').innerText=d.ok ? 'Logged in! -> /clients' : d.error; if(d.ok) setTimeout(()=>location.href='/clients',800)});
}
function doRegister(){
 fetch('/api/register',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:document.getElementById('r_name').value,email:document.getElementById('r_email').value,phone:document.getElementById('r_phone').value,pass:document.getElementById('r_pass').value})})
 .then(r=>r.json()).then(d=>{document.getElementById('msg').innerText=d.ok ? 'Account created! Login now' : d.error; if(d.ok) showTab('login')});
}
// auto open register if URL is /register
if(location.pathname=='/register') showTab('register');
</script>
"""

@app.route("/")
def home(): return render_template_string(HOME_HTML)
@app.route("/shop")
def shop(): return render_template_string(SHOP_HTML)
@app.route("/login")
def login(): return render_template_string(AUTH_HTML)
@app.route("/register")
def register(): return render_template_string(AUTH_HTML)

@app.route("/api/register", methods=["POST"])
def api_register():
    data = request.get_json() or {}
    db = load_db()
    if not data.get("email") or not data.get("pass"):
        return jsonify({"ok":False,"error":"Email and password needed"})
    db["users"].append({**data, "created": datetime.datetime.now().isoformat()})
    save_db(db)
    return jsonify({"ok":True})

@app.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json() or {}
    db = load_db()
    user = next((u for u in db["users"] if u.get("email")==data.get("user") or u.get("phone")==data.get("user")), None)
    if user: return jsonify({"ok":True})
    return jsonify({"ok":False,"error":"Not found - please Register first"})

@app.route("/api/sos", methods=["POST"])
def api_sos():
    data = request.get_json(force=True) or {}
    db = load_db()
    evt = {**data, "time": datetime.datetime.now().isoformat()}
    db["locations"].append(evt)
    db["locations"]=db["locations"][-1000:]
    db["sos_events"].append(evt)
    save_db(db)
    return jsonify({"ok":True})

@app.route("/sos")
def sos_page(): return send_from_directory(".", "sos.html")
@app.route("/clients")
@app.route("/client")
def clients_page(): return send_from_directory(".", "clients.html")
@app.route("/manifest.json")
def mf(): return send_from_directory(".", "manifest.json")
@app.route("/sw.js")
def sw(): return send_from_directory(".", "sw.js")
@app.route("/api/tracking/<phoneId>")
def trail(phoneId):
    db = load_db()
    return jsonify([l for l in db["locations"] if l.get("phoneId")==phoneId][-20:])

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
