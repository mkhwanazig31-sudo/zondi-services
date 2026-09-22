# zondi.py V5.1 FIXED - Login works even with multiple workers
from flask import Flask, request, jsonify, session, redirect
import os, datetime, json
from pathlib import Path

app = Flask(__name__)
app.secret_key = "zondi-v5-1-fix"
Path("evidence").mkdir(exist_ok=True)
EVIDENCE_FILE = "evidence/data.json"
USERS_FILE = "evidence/users.json"

def load_evidence():
    if os.path.exists(EVIDENCE_FILE):
        try:
            return json.load(open(EVIDENCE_FILE))
        except:
            return []
    return []

def load_users():
    if os.path.exists(USERS_FILE):
        try:
            return json.load(open(USERS_FILE))
        except:
            pass
    return {"guard1":{"pass":"1234","role":"guard"},"client1":{"pass":"1234","role":"client"}}

def save_ev(data):
    with open(EVIDENCE_FILE,"w") as f:
        json.dump(data, f)

def save_users(data):
    with open(USERS_FILE,"w") as f:
        json.dump(data, f)

LOGIN_PAGE = '''
<html><head><title>Zondi Login</title><meta name="viewport" content="width=device-width, initial-scale=1">
<style>body{background:#050a0f;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;font-family:Arial;color:white}
.box{background:#0f1a24;padding:30px;border-radius:16px;border:1px solid #00e5ff33;width:90%;max-width:360px;text-align:center}
input,select{width:100%;padding:14px;margin:7px 0;border-radius:10px;border:none;background:#1a2a3a;color:white;box-sizing:border-box}
.btn{width:100%;padding:14px;background:#00e5ff;color:black;font-weight:bold;border:none;border-radius:10px;margin-top:12px;cursor:pointer}
.tab{display:flex;margin-bottom:15px}.tab div{flex:1;padding:10px;cursor:pointer;border-bottom:2px solid #333}.active{border-bottom:2px solid #00e5ff!important;color:#00e5ff}
</style></head>
<body>
<div class="box">
<h2 style="color:#00e5ff;margin:0">ZONDI SERVICES</h2><p style="margin:5px 0 15px;color:#aaa">Ga-Rankuwa Security</p>
<div class="tab"><div id="t1" class="active" onclick="showTab(1)">LOGIN</div><div id="t2" onclick="showTab(2)">REGISTER</div></div>
<div id="loginForm">
<input id="u" placeholder="Username">
<input id="p" type="password" placeholder="Password">
<button class="btn" onclick="doLogin()">LOGIN</button>
<p id="msg1" style="color:#f55;font-size:12px"></p>
<small style="color:#888">guard1 / 1234 | client1 / 1234</small>
</div>
<div id="regForm" style="display:none">
<input id="ru" placeholder="Choose Username (lowercase)">
<input id="rp" type="password" placeholder="Choose Password">
<select id="rr"><option value="client">I am a Client</option><option value="guard">I am a Guard</option></select>
<input id="rc" placeholder="Zone e.g. Zone 4B">
<button class="btn" onclick="doReg()">CREATE ACCOUNT</button>
<p id="msg2" style="font-size:12px"></p>
</div>
</div>
<script>
function showTab(n){
 document.getElementById("loginForm").style.display=n==1?"block":"none";
 document.getElementById("regForm").style.display=n==2?"block":"none";
 document.getElementById("t1").className=n==1?"active":"";
 document.getElementById("t2").className=n==2?"active":"";
}
async function doLogin(){
 let u=document.getElementById("u").value.trim();
 let p=document.getElementById("p").value.trim();
 let res=await fetch("/api/login",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({u,p})});
 let d=await res.json(); if(d.ok) window.location="/dashboard"; else document.getElementById("msg1").innerText="Wrong login - user not found. Try register again with lowercase.";
}
async function doReg(){
 let u=document.getElementById("ru").value.trim().toLowerCase();
 let p=document.getElementById("rp").value.trim();
 let r=document.getElementById("rr").value;
 let c=document.getElementById("rc").value;
 if(!u||!p){document.getElementById("msg2").innerText="Fill username & password"; return;}
 let res=await fetch("/api/register",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({u,p,role:r,company:c})});
 let d=await res.json();
 if(d.ok){document.getElementById("msg2").style.color="#0f0"; document.getElementById("msg2").innerText="Account created as "+u+"! Now login with same lowercase name."; showTab(1); document.getElementById("u").value=u;}
 else {document.getElementById("msg2").style.color="#f55"; document.getElementById("msg2").innerText=d.error;}
}
</script>
</body></html>
'''

DASHBOARD_PAGE = '''
<html><head><title>Dashboard</title><meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>body{background:#050a0f;color:white;font-family:Arial;margin:0}.top{background:#0f1a24;padding:12px 16px;display:flex;justify-content:space-between;border-bottom:1px solid #0ff3}
.card{background:#0f1a24;border:1px solid #0ff2;margin:12px;padding:14px;border-radius:12px}.btn{padding:12px;width:100%;border-radius:10px;font-weight:bold;border:none;margin-top:8px;cursor:pointer}
.btn-cyan{background:#00e5ff;color:black}.btn-red{background:#b00020;color:white}.btn-dark{background:#333;color:white}
.log{background:black;height:80px;overflow-y:auto;font-size:11px;padding:8px;border-radius:8px;color:#0f0}#map{height:240px;border-radius:10px}</style>
</head><body>
<div class="top"><span style="color:#00e5ff;font-weight:bold">ZONDI DASHBOARD</span><span><span id="roleBadge" style="font-size:12px;margin-right:8px"></span><button onclick="fetch('/api/logout').then(()=>location='/')" style="background:none;border:1px solid #555;color:#aaa;border-radius:6px;padding:4px 8px">Logout</button></span></div>
<div class="card"><h3>T780-07 Controls</h3><div id="pttArea"><button class="btn btn-cyan" onclick="log('PTT pressed')">HOLD TO TALK</button><button class="btn btn-red" onclick="doSOS()">SOS EMERGENCY</button><video id="vid" autoplay muted style="width:100%;height:160px;background:black;border-radius:10px;margin-top:8px;display:none"></video></div><div id="log" class="log">Welcome</div></div>
<div class="card"><h3>Live Map</h3><div id="map"></div></div>
<div class="card"><h3>Evidence</h3><div id="evList" style="font-size:11px;margin-top:8px"></div></div>
<script>
fetch("/api/me").then(r=>r.json()).then(d=>{document.getElementById("roleBadge").innerText=d.user+" ("+d.role+")"; loadEv();});
let map=L.map("map").setView([-25.6242,28.0038],14); L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png").addTo(map); let marker=L.marker([-25.6242,28.0038]).addTo(map);
function log(m){let l=document.getElementById("log");l.innerHTML=new Date().toLocaleTimeString()+" - "+m+"<br>"+l.innerHTML}
async function doSOS(){log("SOS"); let vid=document.getElementById("vid"); vid.style.display="block"; try{let s=await navigator.mediaDevices.getUserMedia({video:true,audio:true}); vid.srcObject=s; let chunks=[]; let r=new MediaRecorder(s); r.ondataavailable=e=>chunks.push(e.data); r.onstop=async()=>{let blob=new Blob(chunks,{type:"video/webm"}); let fd=new FormData(); fd.append("video",blob,"sos.webm"); fd.append("trigger","SOS"); await fetch("/api/emergency/upload",{method:"POST",body:fd}); loadEv();}; r.start(); setTimeout(()=>{r.stop(); s.getTracks().forEach(t=>t.stop());},8000);}catch(e){let fd=new FormData(); fd.append("trigger","SOS"); await fetch("/api/emergency/upload",{method:"POST",body:fd}); loadEv();}}
async function loadEv(){let res=await fetch("/api/evidence"); let list=await res.json(); document.getElementById("evList").innerHTML=list.map(e=>"<div style=background:black;padding:5px;margin:3px 0;border-radius:6px>"+e.id+" | "+e.trigger+"<br><small>"+e.timestamp+"</small></div>").join("")||"No evidence"}
</script></body></html>
'''

@app.route("/")
def home():
    if session.get("user"):
        return redirect("/dashboard")
    return LOGIN_PAGE

@app.route("/dashboard")
def dashboard():
    if not session.get("user"):
        return redirect("/")
    return DASHBOARD_PAGE

@app.route("/api/register", methods=["POST"])
def register():
    data = request.get_json()
    u = data.get("u","").strip().lower()
    p = data.get("p","").strip()
    role = data.get("role","client")
    if not u or not p:
        return jsonify({"ok":False,"error":"Fill all fields"})
    users = load_users()
    if u in users:
        return jsonify({"ok":False,"error":"Username exists"})
    users[u] = {"pass":p,"role":role,"company":data.get("company","")}
    save_users(users)
    return jsonify({"ok":True})

@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json()
    u = data.get("u","").strip().lower()
    p = data.get("p","").strip()
    users = load_users()
    if u in users and users[u]["pass"] == p:
        session["user"] = u
        session["role"] = users[u]["role"]
        return jsonify({"ok":True})
    return jsonify({"ok":False})

@app.route("/api/me")
def me():
    if not session.get("user"):
        return jsonify({"role":"none"})
    return jsonify({"user":session.get("user"),"role":session.get("role")})

@app.route("/api/logout")
def logout():
    session.clear()
    return jsonify({"ok":True})

@app.route("/api/emergency/upload", methods=["POST"])
def upload():
    trigger = request.form.get("trigger","SOS")
    video = request.files.get("video")
    fname = f"{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.webm"
    if video:
        video.save(os.path.join("evidence",fname))
    ev = load_evidence()
    entry = {"id":f"EV-{len(ev)+1:04d}","device_id":session.get("user","T780"),"timestamp":datetime.datetime.now().isoformat(),"trigger":trigger,"video":fname}
    ev.append(entry)
    save_ev(ev)
    return jsonify(entry)

@app.route("/api/evidence")
def ev():
    if not session.get("user"):
        return jsonify([])
    return jsonify(load_evidence())

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
