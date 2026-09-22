# zondi.py V5 FIXED - No more SyntaxError
from flask import Flask, request, jsonify, session, redirect
import os, datetime, json
from pathlib import Path

app = Flask(__name__)
app.secret_key = "zondi-v5-fixed-2026"
Path("evidence").mkdir(exist_ok=True)
EVIDENCE_FILE = "evidence/data.json"
USERS_FILE = "evidence/users.json"

if os.path.exists(EVIDENCE_FILE):
    evidence = json.load(open(EVIDENCE_FILE))
else:
    evidence = []

if os.path.exists(USERS_FILE):
    users = json.load(open(USERS_FILE))
else:
    users = {"guard1":{"pass":"1234","role":"guard"},"client1":{"pass":"1234","role":"client"}}

def save_ev():
    with open(EVIDENCE_FILE,"w") as f:
        json.dump(evidence, f)

def save_users():
    with open(USERS_FILE,"w") as f:
        json.dump(users, f)

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
<input id="ru" placeholder="Choose Username">
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
 let res=await fetch("/api/login",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({u:document.getElementById("u").value,p:document.getElementById("p").value})});
 let d=await res.json(); if(d.ok) window.location="/dashboard"; else document.getElementById("msg1").innerText="Wrong login";
}
async function doReg(){
 let u=document.getElementById("ru").value, p=document.getElementById("rp").value, r=document.getElementById("rr").value, c=document.getElementById("rc").value;
 if(!u||!p){document.getElementById("msg2").innerText="Fill username & password"; return;}
 let res=await fetch("/api/register",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({u,p,role:r,company:c})});
 let d=await res.json();
 if(d.ok){document.getElementById("msg2").style.color="#0f0"; document.getElementById("msg2").innerText="Account created! Now login."; showTab(1);}
 else {document.getElementById("msg2").style.color="#f55"; document.getElementById("msg2").innerText=d.error;}
}
</script>
</body></html>
'''

DASHBOARD_PAGE = '''
<html><head><title>Dashboard</title><meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js"></script>
<style>body{background:#050a0f;color:white;font-family:Arial;margin:0}.top{background:#0f1a24;padding:12px 16px;display:flex;justify-content:space-between;border-bottom:1px solid #0ff3}
.card{background:#0f1a24;border:1px solid #0ff2;margin:12px;padding:14px;border-radius:12px}.btn{padding:12px;width:100%;border-radius:10px;font-weight:bold;border:none;margin-top:8px;cursor:pointer}
.btn-cyan{background:#00e5ff;color:black}.btn-red{background:#b00020;color:white}.btn-dark{background:#333;color:white}
.log{background:black;height:80px;overflow-y:auto;font-size:11px;padding:8px;border-radius:8px;color:#0f0}#map{height:240px;border-radius:10px}</style>
</head><body>
<div class="top"><span style="color:#00e5ff;font-weight:bold">ZONDI DASHBOARD</span><span><span id="roleBadge" style="font-size:12px;margin-right:8px"></span><button onclick="fetch('/api/logout').then(()=>location='/')" style="background:none;border:1px solid #555;color:#aaa;border-radius:6px;padding:4px 8px">Logout</button></span></div>
<div class="card"><h3>T780-07 Controls</h3><div id="pttArea"><button class="btn btn-cyan" onclick="log('PTT pressed')">HOLD TO TALK</button><button class="btn btn-red" onclick="doSOS()">SOS EMERGENCY</button><video id="vid" autoplay muted style="width:100%;height:160px;background:black;border-radius:10px;margin-top:8px;display:none"></video></div><div id="log" class="log">Welcome</div></div>
<div class="card"><h3>Live Map</h3><div id="map"></div><button class="btn btn-dark" onclick="simMove()">Simulate Movement</button></div>
<div class="card"><h3>Evidence & Reports</h3><button class="btn btn-cyan" onclick="genPDF()">Generate PDF Report</button><div id="evList" style="font-size:11px;margin-top:8px"></div></div>
<script>
fetch("/api/me").then(r=>r.json()).then(d=>{document.getElementById("roleBadge").innerText=d.user+" ("+d.role+")"; loadEv();});
let map=L.map("map").setView([-25.6242,28.0038],14); L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png").addTo(map); let marker=L.marker([-25.6242,28.0038]).addTo(map);
function log(m){let l=document.getElementById("log");l.innerHTML=new Date().toLocaleTimeString()+" - "+m+"<br>"+l.innerHTML}
function simMove(){let lat=-25.6242+(Math.random()-0.5)*0.01, lng=28.0038+(Math.random()-0.5)*0.01; marker.setLatLng([lat,lng]); map.setView([lat,lng]); log("Moved")}
async function doSOS(){log("SOS"); let vid=document.getElementById("vid"); vid.style.display="block"; try{let s=await navigator.mediaDevices.getUserMedia({video:true,audio:true}); vid.srcObject=s; let chunks=[]; let r=new MediaRecorder(s); r.ondataavailable=e=>chunks.push(e.data); r.onstop=async()=>{let blob=new Blob(chunks,{type:"video/webm"}); let fd=new FormData(); fd.append("video",blob,"sos.webm"); fd.append("trigger","SOS"); await fetch("/api/emergency/upload",{method:"POST",body:fd}); loadEv();}; r.start(); setTimeout(()=>{r.stop(); s.getTracks().forEach(t=>t.stop());},8000);}catch(e){let fd=new FormData(); fd.append("trigger","SOS"); await fetch("/api/emergency/upload",{method:"POST",body:fd}); loadEv();}}
async function loadEv(){let res=await fetch("/api/evidence"); let list=await res.json(); document.getElementById("evList").innerHTML=list.map(e=>"<div style=background:black;padding:5px;margin:3px 0;border-radius:6px>"+e.id+" | "+e.trigger+"<br><small>"+e.timestamp+"</small></div>").join("")||"No evidence"}
function genPDF(){const {jsPDF}=window.jspdf; let doc=new jsPDF(); doc.text("ZONDI - NIGHT REPORT",10,10); doc.text("Date: "+new Date().toLocaleString(),10,20); fetch("/api/evidence").then(r=>r.json()).then(list=>{let y=30; list.forEach(e=>{doc.text(e.id+" - "+e.timestamp,10,y); y+=8}); doc.save("Report.pdf");});}
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
    u = data.get("u","").strip()
    p = data.get("p","").strip()
    role = data.get("role","client")
    if not u or not p:
        return jsonify({"ok":False,"error":"Fill all fields"})
    if u in users:
        return jsonify({"ok":False,"error":"Username already exists"})
    users[u] = {"pass":p,"role":role,"company":data.get("company","")}
    save_users()
    return jsonify({"ok":True})

@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json()
    u = data.get("u")
    p = data.get("p")
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
    entry = {"id":f"EV-{len(evidence)+1:04d}","device_id":session.get("user","T780"),"timestamp":datetime.datetime.now().isoformat(),"trigger":trigger,"video":fname}
    evidence.append(entry)
    save_ev()
    return jsonify(entry)

@app.route("/api/evidence")
def ev():
    if not session.get("user"):
        return jsonify([])
    return jsonify(evidence)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
