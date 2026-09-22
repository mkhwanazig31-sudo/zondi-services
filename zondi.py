from flask import Flask, request, jsonify, send_from_directory, render_template_string
import os, json, datetime

app = Flask(__name__)

# --- FIXED FOR RENDER - NO CRASH ---
DB_FILE = "zondi_db.json"
UPLOAD_DIR = "uploads"

# If /data disk exists (you add it later), use it for permanent storage
if os.path.exists("/data"):
    DB_FILE = "/data/zondi_db.json"
    UPLOAD_DIR = "/data/uploads"

os.makedirs(UPLOAD_DIR, exist_ok=True)

if not os.path.exists(DB_FILE):
    with open(DB_FILE,"w") as f: 
        json.dump({"locations":[],"sos_events":[],"users":[],"purchases":[],"videos":[],"app_version":"2.0"}, f)

def load_db():
    try:
        with open(DB_FILE) as f: 
            return json.load(f)
    except: 
        return {"locations":[],"sos_events":[],"users":[],"purchases":[],"videos":[],"app_version":"2.0"}

def save_db(db):
    db["app_version"] = "2.0"
    db["last_update"] = datetime.datetime.now().isoformat()
    with open(DB_FILE,"w") as f: 
        json.dump(db,f,indent=2)

NAV = """<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><link rel="manifest" href="/manifest.json"><style>body{margin:0;font-family:system-ui;background:#fff}</style>
<div style="padding:12px 16px;display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #eee;background:#fff;position:sticky;top:0;z-index:20"><div style="font-size:10px;color:#888">GA-RANKUWA • SOSHANGUVE • MABOPANE</div><div style="display:flex;gap:10px;font-size:12px"><a href="/" style="text-decoration:none;color:#111">Home</a><a href="/shop" style="text-decoration:none;color:#111">Shop</a><a href="/login" style="text-decoration:none;color:#fff;background:#111;padding:6px 14px;border-radius:20px">Login</a><span style="font-size:9px;color:#16a34a;background:#f0fdf4;padding:3px 6px;border-radius:6px">v2.0</span></div></div>"""

HOME_HTML = NAV + """<div style="max-width:420px;margin:0 auto;min-height:100vh;display:flex;flex-direction:column;justify-content:center;align-items:center;padding:24px;text-align:center"><h1 style="font-size:28px;font-weight:800">Security that feels like family<br><span style="color:#2563eb">protects like SAPS.</span></h1><p style="color:#666;font-size:13px">📍 pins + 🎥 5min T780 + WhatsApp • Silent Update Ready</p><a href="/login" style="background:#111;color:#fff;padding:14px 28px;border-radius:12px;text-decoration:none;font-weight:700;width:280px;text-align:center">Enter App</a></div>"""

SHOP_HTML = NAV + """<div style="max-width:420px;margin:0 auto;padding:16px"><h2>Shop</h2><div id="shopList"></div></div><script>let packs=[{id:'starter',name:'Starter',price:499},{id:'growth',name:'Growth',price:1499},{id:'enterprise',name:'Enterprise',price:3999}];document.getElementById('shopList').innerHTML=packs.map(p=>`<div style="border:1px solid #eee;border-radius:16px;padding:16px;display:flex;justify-content:space-between;margin-bottom:12px"><div><b>${p.name}</b><br>R${p.price}</div><button onclick="buy('${p.id}')" style="background:#111;color:#fff;padding:10px 18px;border-radius:10px;border:0">Buy</button></div>`).join('');function buy(id){let email=prompt('Email:');fetch('/api/purchase',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({pack:id,email:email})}).then(()=>location.href='/login')}</script>"""

AUTH_HTML = """<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><style>body{margin:0;font-family:system-ui;background:#fff}.app{max-width:420px;margin:0 auto;min-height:100vh;background:#fff;padding:0 16px 80px;box-sizing:border-box}.seg{display:flex;background:#f1f5f9;border-radius:12px;padding:4px;gap:4px}.seg button{flex:1;padding:10px;border:0;border-radius:8px;font-weight:700}.seg.active{background:#111;color:#fff}input{width:100%;padding:12px;margin:6px 0;border:1px solid #ddd;border-radius:12px;box-sizing:border-box}</style><div style="padding:12px 16px;display:flex;justify-content:space-between;border-bottom:1px solid #eee;background:#fff;position:sticky;top:0;z-index:20"><div style="font-size:10px;color:#888">GA-RANKUWA v2.0</div><div style="display:flex;gap:10px;font-size:12px"><a href="/" style="text-decoration:none;color:#111">Home</a><a href="/shop" style="text-decoration:none;color:#111">Shop</a></div></div><div class="app"><h2 style="text-align:center">Authorise - Add 📍 Pin</h2><div style="margin:12px 0"><div style="font-size:11px;color:#888;margin-bottom:6px">CHOOSE PORTAL</div><div class="seg" id="roleSeg"><button id="btn-client" class="active" onclick="setRole('client')">Client Portal</button><button id="btn-patroller" onclick="setRole('patroller')">Patrollers Portal</button></div></div><div style="display:flex;gap:16px;justify-content:center;margin:12px 0;font-size:13px"><button id="tab-login" onclick="showTab('login')" style="font-weight:700;border:0;background:0;border-bottom:2px solid #111">Login</button><button id="tab-register" onclick="showTab('register')" style="border:0;background:0;color:#888">Signup + Pin</button></div><div id="login-form"><input id="l_email" placeholder="Email"><input id="l_pass" type="password" placeholder="Password"><button onclick="doLogin()" style="background:#111;color:#fff;padding:14px;width:100%;border:0;border-radius:12px;margin-top:10px;font-weight:700">Login</button><p id="autoMsg" style="font-size:11px;color:#2563eb;text-align:center"></p></div><div id="register-form" style="display:none"><input id="r_name" placeholder="Full Name - e.g. Gontse"><input id="r_email" placeholder="Email"><input id="r_phone" placeholder="Phone"><input id="r_address" placeholder="📍 Shop Address - e.g. 95 Unit 20 Ga-Rankuwa"><input id="r_shop" placeholder="Shop Name - e.g. Gontse Tuck Shop"><input id="r_pass" type="password" placeholder="Password"><button onclick="doRegister()" style="background:#2563eb;color:#fff;padding:14px;width:100%;border:0;border-radius:12px;margin-top:10px;font-weight:700">Create Pin + Signup</button></div><div id="msg" style="text-align:center;font-size:12px;margin-top:12px;color:#16a34a"></div></div><script>
let currentRole='client';
function setRole(r){currentRole=r;document.getElementById('btn-client').className=r=='client'?'active':'';document.getElementById('btn-patroller').className=r=='patroller'?'active':'';}
function showTab(t){document.getElementById('login-form').style.display=t=='login'?'block':'none';document.getElementById('register-form').style.display=t=='register'?'block':'none';}
window.onload=()=>{
 let a=JSON.parse(localStorage.getItem('zondi_auth')||'null');
 if(a && a.email){
   document.getElementById('autoMsg').innerText='Welcome back '+a.email+' • loading...';
   fetch('/api/me?email='+a.email).then(r=>r.json()).then(d=>{
     if(d.ok){location.href=d.redirect}
   });
 }
 fetch('/api/version').then(r=>r.json()).then(v=>{
   localStorage.setItem('zondi_version', v.version);
 });
};
function saveAuth(email,role,name,address){localStorage.setItem('zondi_auth',JSON.stringify({email:email,role:role,name:name,address:address}));localStorage.setItem('zondi_address',address||'');localStorage.setItem('zondi_shopname',document.getElementById('r_shop')?.value||'Shop');}
function doLogin(){let email=document.getElementById('l_email').value.trim();let stored=JSON.parse(localStorage.getItem('zondi_auth')||'{}');saveAuth(email,currentRole,stored.name||email,stored.address||'');fetch('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:email,pass:document.getElementById('l_pass').value,role:currentRole})}).then(r=>r.json()).then(d=>{if(d.ok)location.href=d.redirect;else document.getElementById('msg').innerText=d.error;});}
function doRegister(){let email=document.getElementById('r_email').value.trim();let addr=document.getElementById('r_address').value.trim();if(!addr){document.getElementById('msg').innerText='Add address e.g. 95 Unit 20';return;}saveAuth(email,currentRole,document.getElementById('r_name').value,addr);fetch('/api/register',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:email,name:document.getElementById('r_name').value,phone:document.getElementById('r_phone').value,address:addr,shop:document.getElementById('r_shop').value,pass:document.getElementById('r_pass').value,role:currentRole})}).then(r=>r.json()).then(d=>{if(d.ok)location.href=d.redirect;else document.getElementById('msg').innerText=d.error;});}
</script>"""

@app.route("/")
def home(): return render_template_string(HOME_HTML)
@app.route("/shop")
def shop(): return render_template_string(SHOP_HTML)
@app.route("/login")
def login(): return render_template_string(AUTH_HTML)

@app.route("/api/version")
def version():
    return jsonify({"version":"2.0
