# zondi.py V7.4 - Removed shop name from registration
from flask import Flask, request, jsonify, session, redirect
import os, datetime, json
from pathlib import Path

app = Flask(__name__)
app.secret_key = "zondi-v7-4-no-shop-field"
Path("evidence").mkdir(exist_ok=True)
EVIDENCE_FILE = "evidence/data.json"
USERS_FILE = "evidence/users.json"

def load_evidence():
    if os.path.exists(EVIDENCE_FILE):
        try: return json.load(open(EVIDENCE_FILE))
        except: return []
    return []
def load_users():
    if os.path.exists(USERS_FILE):
        try: return json.load(open(USERS_FILE))
        except: pass
    return {"guard1":{"pass":"1234","role":"guard"},"client1":{"pass":"1234","role":"client"}}
def save_ev(data):
    with open(EVIDENCE_FILE,"w") as f: json.dump(data,f)
def save_users(data):
    with open(USERS_FILE,"w") as f: json.dump(data,f)

COMMON_STYLE = """
<style>
body{margin:0;font-family:Arial;background:#f6f8fb;color:#1a2a3a}
.nav{display:flex;justify-content:space-between;align-items:center;padding:14px 20px;background:white;box-shadow:0 2px 10px rgba(0,0,0,0.06);position:sticky;top:0;z-index:10}
.logo{font-weight:800;color:#0b5fff}
.nav a{color:#5a6a7a;text-decoration:none;margin-right:14px;font-size:14px}
.nav a.active{color:#0b5fff;font-weight:700}
.btn{padding:12px 20px;border-radius:12px;font-weight:700;border:none;cursor:pointer;text-decoration:none;display:inline-block}
.btn-primary{background:#0b5fff;color:white}
.btn-out{border:1.5px solid #dde5f0;color:#0b5fff;background:white}
.card{background:white;border-radius:20px;padding:20px;box-shadow:0 4px 20px rgba(0,0,0,0.05);border:1px solid #eef2f7;margin:12px}
</style>
"""

LANDING = COMMON_STYLE + """
<html><head><title>Zondi Home</title><meta name="viewport" content="width=device-width, initial-scale=1"></head><body>
<div class="nav"><div class="logo">ZONDI SERVICES</div><div><a href="/" class="active">Home</a><a href="/shop">Shop</a><a href="/login">Login</a></div></div>
<div style="text-align:center;padding:60px 20px;background:white">
<span style="background:#e8f0ff;color:#0b5fff;padding:6px 12px;border-radius:100px;font-size:11px;font-weight:700">GA-RANKUWA • SOSHANGUVE • MABOPANE</span>
<h1 style="font-size:38px;color:#10203a;margin:16px 0">Security that <span style="color:#0b5fff">feels like family</span><br>protects like SAPS.</h1>
<p style="color:#6a7a8a;max-width:560px;margin:auto">Clean, friendly, works offline. Buy protection in our Shop like airtime.</p>
<div style="margin-top:24px"><a class="btn btn-primary" href="/shop">Go to Shop</a> <a class="btn btn-out" href="/login" style="margin-left:8px">Login</a></div>
</div>
<div style="max-width:1000px;margin:auto;display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px;padding:20px">
<div class="card">Guard Down auto SOS<br><small style="color:#888">No movement 10min → WhatsApp</small></div>
<div class="card">Video Proof Vault<br><small style="color:#888">8s SOS video saved</small></div>
<div class="card">Works Offline<br><small style="color:#888">Queues when no data</small></div>
</div>
</body></html>
"""

SHOP_PAGE = COMMON_STYLE + """
<html><head><title>Zondi Shop</title><meta name="viewport" content="width=device-width, initial-scale=1"></head><body>
<div class="nav"><div class="logo">ZONDI SERVICES</div><div><a href="/">Home</a><a href="/shop" class="active">Shop</a><a href="/login">Login</a></div></div>
<div style="max-width:1000px;margin:auto;padding:24px">
<h1 style="text-align:center;color:#10203a">Zondi Shop</h1>
<p style="text-align:center;color:#6a7a8a">Buy security like groceries. Cash, EFT, PayShap welcome.</p>
<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px;margin-top:20px">
<div class="card"><h3>Starter Pack</h3><div style="font-size:32px;font-weight:800">R499<span style="font-size:14px;color:#888">/mo</span></div><p style="font-size:13px;color:#666">1 Shop, 1 Guard, 1 T780<br>✓ Live map<br>✓ Daily PDF<br>✓ WhatsApp SOS</p><a class="btn btn-out" href="/login" style="width:100%;text-align:center;box-sizing:border-box">Add to Cart</a></div>
<div class="card" style="border:2px solid #0b5fff"><span style="background:#0b5fff;color:white;padding:4px 8px;border-radius:20px;font-size:10px">BEST SELLER</span><h3>Growth Pack</h3><div style="font-size:32px;font-weight:800">R1,499<span style="font-size:14px;color:#888">/mo</span></div><p style="font-size:13px;color:#666">3 Shops + Patrol<br>✓ Guard Down SOS<br>✓ Offline mode<br>✓ Face unlock<br>✓ 3x T780</p><a class="btn btn-primary" href="/login" style="width:100%;text-align:center;box-sizing:border-box">Buy Growth Pack</a></div>
<div class="card"><h3>Enterprise</h3><div style="font-size:32px;font-weight:800">R3,999<span style="font-size:14px;color:#888">/mo</span></div><p style="font-size:13px;color:#666">Complex / Mall<br>✓ Unlimited zones<br>✓ 24/7 call center<br>✓ 10+ devices</p><a class="btn btn-out" href="/login" style="width:100%;text-align:center;box-sizing:border-box">Contact Sales</a></div>
</div>
</div>
</body></html>
"""

LOGIN_PAGE = COMMON_STYLE + """
<html><head><title>Login</title><meta name="viewport" content="width=device-width, initial-scale=1">
<style>body{display:flex;justify-content:center;align-items:center;min-height:100vh}.box{background:white;padding:28px;border-radius:20px;width:90%;max-width:360px;box-shadow:0 10px 30px rgba(0,0,0,0.08)} input,select{width:100%;padding:14px;margin:6px 0;border-radius:12px;border:1.5px solid #dde5f0;box-sizing:border-box}.tab{display:flex;background:#f0f5ff;border-radius:100px;padding:4px;margin:12px 0}.tab div{flex:1;padding:8px;text-align:center;border-radius:100px;cursor:pointer;font-size:14px}.active{background:white;font-weight:700;color:#0b5fff;box-shadow:0 2px 6px rgba(0,0,0,0.08)}</style>
</head><body>
<div class="nav" style="position:absolute;top:0;left:0;right:0"><div class="logo">ZONDI</div><div><a href="/">Home</a><a href="/shop">Shop</a></div></div>
<div class="box">
<h2 style="margin:0;color:#10203a;text-align:center">Welcome</h2><p style="text-align:center;color:#888;font-size:13px">Login to your shop</p>
<div class="tab"><div id="t1" class="active" onclick="showTab(1)">Login</div><div id="t2" onclick="showTab(2)">Register</div></div>
<div id="loginForm"><input id="u" placeholder="username lowercase"><input id="p" type="password" placeholder="password"><button class="btn btn-primary" style="width:100%;margin-top:8px" onclick="doLogin()">Login</button><p id="msg1" style="color:red;font-size:12px"></p></div>
<div id="regForm" style="display:none"><input id="ru" placeholder="username"><input id="rp" type="password" placeholder="password"><select id="rr"><option value="client">Client</option><option value="guard">Guard</option></select><button class="btn btn-primary" style="width:100%;margin-top:8px" onclick="doReg()">Create account</button><p id="msg2" style="font-size:12px"></p></div>
</div>
<script>
function showTab(n){
 document.getElementById("loginForm").style.display=n==1?"block":"none";
 document.getElementById("regForm").style.display=n==2?"block":"none";
 document.getElementById("t1").className=n==1?"active":"";
 document.getElementById("t2").className=n==2?"active":"";
}
async function doLogin(){
 let u=document.getElementById("u").value.trim().toLowerCase();
 let p=document.getElementById("p").value.trim();
 let res=await fetch("/api/login",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({u,p})});
 let d=await res.json();
 if(d.ok) location="/dashboard"; else document.getElementById("msg1").innerText="Wrong login";
}
async function doReg(){
 let u=document.getElementById("ru").value.trim().toLowerCase();
 let p=document.getElementById("rp").value.trim();
 let r=document.getElementById("rr").value;
 if(!u||!p){document.getElementById("msg2").innerText="Fill all"; return;}
 let res=await fetch("/api/register",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({u,p,role:r})});
 let d=await res.json();
 if(d.ok){document.getElementById("msg2").style.color="green"; document.getElementById("msg2").innerText="Created! Login now."; showTab(1);}
 else {document.getElementById("msg2").style.color="red"; document.getElementById("msg2").innerText=d.error;}
}
</script>
</body></html>
"""

DASH_PAGE = COMMON_STYLE + """
<html><head><title>Dashboard</title><meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>#map{height:260px;border-radius:16px}.log{background:#10203a;color:#7aff9a;height:80px;overflow-y:auto;font-size:11px;padding:8px;border-radius:10px}</style>
</head><body>
<div class="nav"><div class="logo">ZONDI DASHBOARD</div><div><a href="/">Home</a><a href="/shop">Shop</a><span id="rb" style="font-weight:700;color:#0b5fff;margin-left:10px"></span><button onclick="fetch('/api/logout').then(()=>location='/')" style="margin-left:8px;border:none;background:#f0f5ff;padding:6px 12px;border-radius:8px">Logout</button></div></div>
<div class="card"><b>Safety:</b> Last move <span id="lastMove">Just now</span><div style="background:#e8eef7;height:8px;border-radius:10px;margin-top:8px"><div id="bar" style="background:#0b5fff;height:8px;width:100%;border-radius:10px"></div></div></div>
<div class="card"><button class="btn btn-primary" style="width:100%" onclick="simMove()">Simulate Patrol Move</button><button class="btn" style="width:100%;margin-top:8px;background:#ff3b3b;color:white" onclick="doSOS('MANUAL')">SOS + WhatsApp</button><video id="vid" autoplay muted style="width:100%;height:160px;background:#10203a;border-radius:12px;margin-top:10px;display:none"></video><div id="log" class="log" style="margin-top:10px">Ready</div></div>
<div class="card"><div id="map"></div></div>
<div class="card"><h3>Evidence</h3><div id="evList" style="font-size:12px"></div></div>
<script>
let lastMove=Date.now(), curLat=-25.6242, curLng=28.0038;
fetch("/api/me").then(r=>r.json()).then(d=>{document.getElementById("rb").innerText=d.user; loadEv();});
let map=L.map("map").setView([-25.6242,28.0038],14); L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png").addTo(map); let mk=L.marker([-25.6242,28.0038]).addTo(map);
function log(m){let l=document.getElementById("log"); l.innerHTML=new Date().toLocaleTimeString()+" - "+m+"<br>"+l.innerHTML;}
function simMove(){curLat=-25.6242+(Math.random()-0.5)*0.01; curLng=28.0038+(Math.random()-0.5)*0.01; mk.setLatLng([curLat,curLng]); map.setView([curLat,curLng]); lastMove=Date.now(); document.getElementById("lastMove").innerText="Just now"; document.getElementById("bar").style.width="100%"; log("Moved");}
setInterval(()=>{let d=(Date.now()-lastMove)/1000; if(d>10) document.getElementById("lastMove").innerText=Math.floor(d)+"s ago"; let pct=Math.max(0,100-(d/120)*100); document.getElementById("bar").style.width=pct+"%";},1000);
async function doSOS(t){log(t+" SOS"); let v=document.getElementById("vid"); v.style.display="block"; try{let s=await navigator.mediaDevices.getUserMedia({video:true,audio:true}); v.srcObject=s; let ch=[]; let rec=new MediaRecorder(s); rec.ondataavailable=e=>ch.push(e.data); rec.onstop=async()=>{let b=new Blob(ch,{type:"video/webm"}); let fd=new FormData(); fd.append("video",b,"sos.webm"); fd.append("trigger",t); fd.append("lat",curLat); fd.append("lng",curLng); await fetch("/api/emergency/upload",{method:"POST",body:fd}); loadEv();}; rec.start(); setTimeout(()=>{rec.stop(); s.getTracks().forEach(x=>x.stop());},8000);}catch(e){let fd=new FormData(); fd.append("trigger",t); await fetch("/api/emergency/upload",{method:"POST",body:fd}); loadEv();}}
async function loadEv(){let r=await fetch("/api/evidence"); let ls=await r.json(); document.getElementById("evList").innerHTML=ls.map(e=>"<div style=background:#f6f8fb;padding:8px;margin:4px 0;border-radius:10px>"+e.id+" | "+e.trigger+"<br><small>"+e.timestamp+"</small></div>").join("")||"No evidence";}
</script>
</body></html>
"""

@app.route("/")
def home(): return LANDING
@app.route("/shop")
def shop(): return SHOP_PAGE
@app.route("/pricing")
def pricing(): return SHOP_PAGE
@app.route("/login")
def login_page():
    if session.get("user"): return redirect("/dashboard")
    return LOGIN_PAGE
@app.route("/dashboard")
def dashboard():
    if not session.get("user"): return redirect("/login")
    return DASH_PAGE
@app.route("/api/register", methods=["POST"])
def register():
    data=request.get_json()
    u=data.get("u","").strip().lower(); p=data.get("p","").strip(); role=data.get("role","client")
    if not u or not p: return jsonify({"ok":False,"error":"Fill all"})
    users=load_users()
    if u in users: return jsonify({"ok":False,"error":"Exists"})
    users[u]={"pass":p,"role":role}; save_users(users); return jsonify({"ok":True})
@app.route("/api/login", methods=["POST"])
def login():
    data=request.get_json()
    u=data.get("u","").strip().lower(); p=data.get("p","").strip()
    users=load_users()
    if u in users and users[u]["pass"]==p:
        session["user"]=u; session["role"]=users[u]["role"]; return jsonify({"ok":True})
    return jsonify({"ok":False})
@app.route("/api/me")
def me():
    if not session.get("user"): return jsonify({"role":"none"})
    return jsonify({"user":session.get("user"),"role":session.get("role")})
@app.route("/api/logout")
def logout(): session.clear(); return jsonify({"ok":True})
@app.route("/api/emergency/upload", methods=["POST"])
def upload():
    trigger=request.form.get("trigger","SOS"); lat=request.form.get("lat"); lng=request.form.get("lng")
    video=request.files.get("video")
    fname=datetime.datetime.now().strftime("%Y%m%d_%H%M%S")+".webm"
    if video: video.save(os.path.join("evidence",fname))
    ev=load_evidence()
    entry={"id":f"EV-{len(ev)+1:04d}","timestamp":datetime.datetime.now().isoformat(),"trigger":trigger,"lat":lat,"lng":lng,"video":fname}
    ev.append(entry); save_ev(ev); return jsonify(entry)
@app.route("/api/evidence")
def ev():
    if not session.get("user"): return jsonify([])
    return jsonify(load_evidence())

if __name__=="__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
