# zondi.py V4 - Proper Login -> Dashboard Flow
from flask import Flask, request, jsonify, session, redirect
import os, datetime, json
from pathlib import Path

app = Flask(__name__)
app.secret_key = "zondi-ga-rankuwa-v4"
Path("evidence").mkdir(exist_ok=True)
EVIDENCE_FILE = "evidence/data.json"
evidence = json.load(open(EVIDENCE_FILE)) if os.path.exists(EVIDENCE_FILE) else []
def save_ev(): json.dump(evidence, open(EVIDENCE_FILE,"w"))

LOGIN_PAGE = """
<html><head><title>Zondi Login</title><meta name="viewport" content="width=device-width, initial-scale=1">
<style>body{background:#050a0f;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;font-family:Arial;color:white}
.box{background:#0f1a24;padding:30px;border-radius:16px;border:1px solid #00e5ff33;width:90%;max-width:350px;text-align:center}
input{width:100%;padding:14px;margin:8px 0;border-radius:10px;border:none;background:#1a2a3a;color:white}
.btn{width:100%;padding:14px;background:#00e5ff;color:black;font-weight:bold;border:none;border-radius:10px;margin-top:12px;cursor:pointer}
small{color:#888}</style></head>
<body>
<div class="box">
<h2 style="color:#00e5ff">ZONDI SERVICES</h2><p>Ga-Rankuwa Security</p>
<input id="u" placeholder="Username">
<input id="p" type="password" placeholder="Password">
<button class="btn" onclick="doLogin()">LOGIN</button>
<p id="msg" style="color:#f55;font-size:12px"></p>
<small>Guard: guard1 / 1234<br>Client: client1 / 1234</small>
</div>
<script>
async function doLogin(){
 let res=await fetch('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({u:document.getElementById('u').value,p:document.getElementById('p').value})});
 let d=await res.json();
 if(d.ok){window.location='/dashboard';} else document.getElementById('msg').innerText='Wrong login';
}
</script>
</body></html>
"""

DASHBOARD_PAGE = """
<html><head><title>Zondi Dashboard</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/face-api.js@0.22.2/dist/face-api.min.js"></script>
<style>
body{background:#050a0f;color:white;font-family:Arial;margin:0;padding:0}
.top{background:#0f1a24;padding:12px 16px;display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #0ff3}
.card{background:#0f1a24;border:1px solid #0ff2;margin:12px;padding:14px;border-radius:12px}
.btn{padding:12px;width:100%;border-radius:10px;font-weight:bold;border:none;margin-top:8px;cursor:pointer}
.btn-cyan{background:#00e5ff;color:black}.btn-red{background:#b00020;color:white}.btn-dark{background:#333;color:white}
.log{background:black;height:80px;overflow-y:auto;font-size:11px;padding:8px;border-radius:8px;color:#0f0}
#map{height:240px;border-radius:10px}
.locked{border:2px solid red} .unlocked{border:2px solid #0f0}
</style>
</head>
<body>
<div class="top"><span style="color:#00e5ff;font-weight:bold">ZONDI DASHBOARD</span><span id="roleBadge" style="font-size:12px"></span><button onclick="fetch('/api/logout').then(()=>location='/')" style="background:none;border:1px solid #555;color:#aaa;border-radius:6px;padding:4px 8px">Logout</button></div>

<div class="card" id="faceCard">
<h3>Step 1: Face Unlock (Guard only)</h3>
<video id="faceCam" autoplay muted style="width:100%;height:160px;background:black;border-radius:10px" class="locked"></video>
<button class="btn btn-dark" onclick="setupFace()">Register Face</button>
<button class="btn btn-cyan" onclick="unlockFace()">Unlock Radio</button>
<p id="faceStatus" style="font-size:12px;color:orange">LOCKED</p>
</div>

<div class="card">
<h3>T780-07 Controls</h3>
<div id="pttArea" style="opacity:0.3;pointer-events:none">
<button class="btn btn-cyan" onmousedown="log('PTT START')" onmouseup="log('PTT END')">HOLD TO TALK</button>
<button class="btn btn-red" onclick="doSOS()">SOS EMERGENCY RECORD</button>
<video id="vid" autoplay muted style="width:100%;height:160px;background:black;border-radius:10px;margin-top:8px;display:none"></video>
</div>
<div id="log" class="log">Welcome to dashboard</div>
</div>

<div class="card">
<h3>Live Tracking - Ga-Rankuwa</h3>
<div id="map"></div>
<p id="coords" style="font-size:11px">-25.6242, 28.0038</p>
<button class="btn btn-dark" onclick="simMove()">Simulate Movement</button>
</div>

<div class="card">
<h3>Business Reports</h3>
<button class="btn btn-cyan" onclick="genPDF()">Generate Night Report PDF</button>
<div id="evList" style="font-size:11px;margin-top:8px"></div>
</div>

<script>
let unlocked=false, faceDesc=null, userRole=null;
fetch('/api/me').then(r=>r.json()).then(d=>{userRole=d.role; document.getElementById('roleBadge').innerText=d.role.toUpperCase()+' - '+d.user; if(d.role==='client'){document.getElementById('faceCard').style.display='none'; document.getElementById('pttArea').innerHTML='<p style=color:#0ff>Client view: Live tracking only</p>'; document.getElementById('pttArea').style.opacity='1'; document.getElementById('pttArea').style.pointerEvents='auto';} loadEv();});

let map=L.map('map').setView([-25.6242,28.0038],14); L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(map); let marker=L.marker([-25.6242,28.0038]).addTo(map);
function log(m){let l=document.getElementById('log');l.innerHTML=new Date().toLocaleTimeString()+' - '+m+'<br>'+l.innerHTML}
async function setupFace(){log('Loading face models...'); await faceapi.nets.tinyFaceDetector.loadFromUri('https://cdn.jsdelivr.net/npm/face-api.js@0.22.2/weights'); await faceapi.nets.faceLandmark68Net.loadFromUri('https://cdn.jsdelivr.net/npm/face-api.js@0.22.2/weights'); await faceapi.nets.faceRecognitionNet.loadFromUri('https://cdn.jsdelivr.net/npm/face-api.js@0.22.2/weights'); let cam=document.getElementById('faceCam'); let s=await navigator.mediaDevices.getUserMedia({video:true}); cam.srcObject=s; cam.onloadeddata=async()=>{let det=await faceapi.detectSingleFace(cam, new faceapi.TinyFaceDetectorOptions()).withFaceLandmarks().withFaceDescriptor(); if(det){faceDesc=det.descriptor; log('Face registered')} else log('No face found')}} 
async function unlockFace(){if(!faceDesc){log('Register first');return} let cam=document.getElementById('faceCam'); let det=await faceapi.detectSingleFace(cam, new faceapi.TinyFaceDetectorOptions()).withFaceLandmarks().withFaceDescriptor(); if(det){let dist=faceapi.euclideanDistance(faceDesc,det.descriptor); if(dist<0.6){unlocked=true; document.getElementById('faceCam').className='unlocked'; document.getElementById('faceStatus').innerText='UNLOCKED - PTT enabled'; document.getElementById('pttArea').style.opacity='1'; document.getElementById('pttArea').style.pointerEvents='auto'; log('Unlocked')} else log('Face mismatch')} }
function simMove(){let lat=-25.6242+(Math.random()-0.5)*0.01, lng=28.0038+(Math.random()-0.5)*0.01; marker.setLatLng([lat,lng]); map.setView([lat,lng]); fetch('/api/location?lat='+lat+'&lng='+lng); log('Moved')}
async function doSOS(){log('SOS 8s rec'); let vid=document.getElementById('vid'); vid.style.display='block'; try{let s=await navigator.mediaDevices.getUserMedia({video:true,audio:true}); vid.srcObject=s; let chunks=[]; let r=new MediaRecorder(s); r.ondataavailable=e=>chunks.push(e.data); r.onstop=async()=>{let blob=new Blob(chunks,{type:'video/webm'}); let fd=new FormData(); fd.append('video',blob,'sos.webm'); fd.append('trigger','DASHBOARD_SOS'); let res=await fetch('/api/emergency/upload',{method:'POST',body:fd}); log('Saved'); loadEv();}; r.start(); setTimeout(()=>{r.stop(); s.getTracks().forEach(t=>t.stop());},8000);}catch(e){let fd=new FormData(); fd.append('trigger','DASHBOARD_SOS'); await fetch('/api/emergency/upload',{method:'POST',body:fd}); loadEv();}}
async function loadEv(){let res=await fetch('/api/evidence'); let list=await res.json(); document.getElementById('evList').innerHTML=list.map(e=>'<div style=background:black;padding:5px;margin:3px 0;border-radius:6px>'+e.id+' | '+e.trigger+'<br><small>'+e.timestamp+'</small></div>').join('')||'No evidence'}
function genPDF(){const {jsPDF}=window.jspdf; let doc=new jsPDF(); doc.text('ZONDI SERVICES - NIGHT REPORT',10,10); doc.text('Date: '+new Date().toLocaleString(),10,20); doc.text('Guard: T780-07 Ga-Rankuwa',10,30); fetch('/api/evidence').then(r=>r.json()).then(list=>{let y=40; list.forEach(e=>{doc.text(e.id+' - '+e.timestamp,10,y); y+=8}); doc.save('Zondi_Report.pdf'); log('PDF generated');});}
</script>
</body></html>
"""

@app.route("/")
def login_page():
    if session.get("user"): return redirect("/dashboard")
    return LOGIN_PAGE

@app.route("/dashboard")
def dashboard():
    if not session.get("user"): return redirect("/")
    return DASHBOARD_PAGE

@app.route("/api/me")
def me():
    if not session.get("user"): return jsonify({"role":"none"})
    return jsonify({"user":session.get("user"),"role":session.get("role")})

@app.route("/api/login", methods=["POST"])
def login():
    data=request.get_json()
    u=data.get("u"); p=data.get("p")
    if u=="guard1" and p=="1234":
        session["user"]=u; session["role"]="guard"; return jsonify({"ok":True})
    if u=="client1" and p=="1234":
        session["user"]=u; session["role"]="client"; return jsonify({"ok":True})
    return jsonify({"ok":False})

@app.route("/api/logout")
def logout():
    session.clear(); return jsonify({"ok":True})

@app.route("/api/location")
def loc(): return jsonify({"ok":True})

@app.route("/api/emergency/upload", methods=["POST"])
def upload():
    trigger=request.form.get("trigger","SOS")
    video=request.files.get("video")
    fname=f"{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.webm"
    if video: video.save(os.path.join("evidence",fname))
    entry={"id":f"EV-{len(evidence)+1:04d}","device_id":"T780-07","timestamp":datetime.datetime.now().isoformat(),"trigger":trigger,"video":fname}
    evidence.append(entry); save_ev(); return jsonify(entry)

@app.route("/api/evidence")
def ev():
    if not session.get("user"): return jsonify([])
    return jsonify(evidence)

@app.route("/api/t780/sos", methods=["POST"])
def t780_real():
    data=request.get_json() or {}
    entry={"id":f"EV-{len(evidence)+1:04d}","device_id":data.get("device_id","T780-REAL"),"timestamp":datetime.datetime.now().isoformat(),"trigger":"REAL_T780_RED_BUTTON"}
    evidence.append(entry); save_ev(); return jsonify(entry)

if __name__=="__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
