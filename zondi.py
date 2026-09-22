# zondi.py V3 - Face Lock + Client Portal + Real T780 SOS + PDF Report
from flask import Flask, request, jsonify, session
import os, datetime, json
from pathlib import Path

app = Flask(__name__)
app.secret_key = "zondi-ga-rankuwa-2026-secret"
Path("evidence").mkdir(exist_ok=True)
EVIDENCE_FILE = "evidence/data.json"
evidence = json.load(open(EVIDENCE_FILE)) if os.path.exists(EVIDENCE_FILE) else []
def save_ev(): json.dump(evidence, open(EVIDENCE_FILE,"w"))

HTML = """
<html><head><title>Zondi V3 Pro</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/face-api.js@0.22.2/dist/face-api.min.js"></script>
<style>
body{background:#050a0f;color:white;font-family:Arial;padding:12px;margin:0}
.card{background:#0f1a24;border:1px solid #0ff3;padding:14px;border-radius:12px;margin-bottom:12px}
.btn{padding:12px;width:100%;border-radius:10px;font-weight:bold;border:none;margin-top:8px;cursor:pointer}
.btn-cyan{background:#00e5ff;color:black}.btn-red{background:#b00020;color:white}.btn-dark{background:#333;color:white}
.log{background:black;height:90px;overflow-y:auto;font-size:11px;padding:8px;border-radius:8px;color:#0f0}
#map{height:220px;border-radius:10px} input{width:100%;padding:10px;border-radius:8px;border:none;margin:5px 0}
.locked{border:2px solid red} .unlocked{border:2px solid #0f0}
</style>
</head>
<body>
<h2 style="color:#00e5ff">ZONDI V3 PRO</h2>

<div class="card" id="loginCard">
<h3>Client / Guard Login</h3>
<input id="user" placeholder="Username (try client1 / guard1)">
<input id="pass" type="password" placeholder="Password (1234)">
<button class="btn btn-cyan" onclick="login()">LOGIN</button>
<p style="font-size:10px;color:#aaa">Guard1 can do PTT + SOS. Client1 can only view map + reports.</p>
</div>

<div class="card">
<h3>Face Unlock - Anti-Theft</h3>
<p style="font-size:11px">Guard must verify face before radio works</p>
<video id="faceCam" autoplay muted style="width:100%;height:160px;background:black;border-radius:10px" class="locked"></video>
<button class="btn btn-dark" onclick="setupFace()">1. Register My Face</button>
<button class="btn btn-cyan" onclick="unlockFace()">2. Unlock Radio With Face</button>
<p id="faceStatus" style="font-size:12px;color:orange">Status: LOCKED - PTT disabled</p>
</div>

<div class="card">
<h3>T780-07 - Ga-Rankuwa</h3>
<div id="pttArea" style="opacity:0.3;pointer-events:none">
<button class="btn btn-cyan" onmousedown="ptt(1)" onmouseup="ptt(0)">HOLD TO TALK - PTT (Face Locked)</button>
<button class="btn btn-red" onclick="doSOS()">SOS EMERGENCY</button>
<video id="vid" autoplay muted style="width:100%;height:160px;background:black;border-radius:10px;margin-top:8px;display:none"></video>
</div>
<div id="log" class="log">Waiting login...</div>
</div>

<div class="card">
<h3>Live Map - Client View</h3>
<div id="map"></div>
<p id="coords" style="font-size:11px">-25.6242, 28.0038</p>
<button class="btn btn-dark" onclick="simMove()">Simulate T780 Movement</button>
</div>

<div class="card">
<h3>Business - Shift Report</h3>
<button class="btn btn-cyan" onclick="genPDF()">Generate Night Shift PDF (06:00 Report)</button>
<div id="evList" style="font-size:11px;margin-top:8px"></div>
</div>

<script>
let unlocked=false, faceDescriptor=null, role=null;
let map=L.map('map').setView([-25.6242,28.0038],14);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(map);
let marker=L.marker([-25.6242,28.0038]).addTo(map).bindPopup('T780-07');

function log(m){let l=document.getElementById('log');l.innerHTML=new Date().toLocaleTimeString()+' - '+m+'<br>'+l.innerHTML}

async function login(){
 let u=document.getElementById('user').value, p=document.getElementById('pass').value;
 let res=await fetch('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({u,p})});
 let d=await res.json();
 if(d.ok){role=d.role; log('Logged as '+role); document.getElementById('loginCard').style.display='none'; loadEv();
  if(role==='client'){document.getElementById('pttArea').innerHTML='<p style=color:#0ff>Client view only - tracking guard live</p>'} 
 } else alert('Wrong login. Use guard1/1234 or client1/1234');
}

async function setupFace(){
 log('Loading face models...'); await faceapi.nets.tinyFaceDetector.loadFromUri('https://cdn.jsdelivr.net/npm/face-api.js@0.22.2/weights');
 await faceapi.nets.faceLandmark68Net.loadFromUri('https://cdn.jsdelivr.net/npm/face-api.js@0.22.2/weights');
 await faceapi.nets.faceRecognitionNet.loadFromUri('https://cdn.jsdelivr.net/npm/face-api.js@0.22.2/weights');
 let cam=document.getElementById('faceCam'); let s=await navigator.mediaDevices.getUserMedia({video:true}); cam.srcObject=s;
 cam.onloadeddata=async()=>{
  let det=await faceapi.detectSingleFace(cam, new faceapi.TinyFaceDetectorOptions()).withFaceLandmarks().withFaceDescriptor();
  if(det){faceDescriptor=det.descriptor; log('Face registered! Now unlock.');} else log('No face found, look at camera');
 };
}
async function unlockFace(){
 if(!faceDescriptor){log('Register face first'); return;}
 let cam=document.getElementById('faceCam');
 let det=await faceapi.detectSingleFace(cam, new faceapi.TinyFaceDetectorOptions()).withFaceLandmarks().withFaceDescriptor();
 if(det){
  let dist=faceapi.euclideanDistance(faceDescriptor, det.descriptor);
  if(dist<0.6){unlocked=true; document.getElementById('faceCam').className='unlocked'; document.getElementById('faceStatus').innerText='UNLOCKED - PTT enabled'; document.getElementById('faceStatus').style.color='#0f0'; document.getElementById('pttArea').style.opacity='1'; document.getElementById('pttArea').style.pointerEvents='auto'; log('FACE MATCH - Radio unlocked');}
  else log('Face not match dist='+dist.toFixed(2));
 } else log('No face detected');
}

function ptt(s){log(s?'PTT START - Guard talking':'PTT END'); if(s) fetch('/api/ptt/start'); else fetch('/api/ptt/end');}
function simMove(){let lat=-25.6242+(Math.random()-0.5)*0.01, lng=28.0038+(Math.random()-0.5)*0.01; marker.setLatLng([lat,lng]); map.setView([lat,lng]); document.getElementById('coords').innerText=lat.toFixed(4)+','+lng.toFixed(4); fetch('/api/location?lat='+lat+'&lng='+lng); log('T780 moved')}

async function doSOS(){
 log('SOS TRIGGERED - Recording 8s'); let vid=document.getElementById('vid'); vid.style.display='block';
 try{
  let s=await navigator.mediaDevices.getUserMedia({video:true,audio:true}); vid.srcObject=s; let chunks=[]; let r=new MediaRecorder(s);
  r.ondataavailable=e=>chunks.push(e.data); r.onstop=async()=>{
   let blob=new Blob(chunks,{type:'video/webm'}); let fd=new FormData(); fd.append('video',blob,'sos.webm'); fd.append('device_id','T780-07'); fd.append('trigger','FACE_VERIFIED_SOS');
   let res=await fetch('/api/emergency/upload',{method:'POST',body:fd}); let d=await res.json(); log('Evidence saved '+d.id); loadEv();
  }; r.start(); setTimeout(()=>{r.stop(); s.getTracks().forEach(t=>t.stop());},8000);
 }catch(e){let fd=new FormData(); fd.append('device_id','T780-07'); let res=await fetch('/api/emergency/upload',{method:'POST',body:fd}); loadEv();}
}
async function loadEv(){let res=await fetch('/api/evidence'); let list=await res.json(); document.getElementById('evList').innerHTML=list.map(e=>'<div style=background:black;padding:5px;margin:3px 0;border-radius:6px>'+e.id+' | '+e.device_id+' | '+e.trigger+'<br><small>'+e.timestamp+'</small></div>').join('')||'No evidence';}
function genPDF(){
 const {jsPDF}=window.jspdf; let doc=new jsPDF(); doc.text('ZONDI SERVICES - NIGHT SHIFT REPORT',10,10);
 doc.text('Zone: Ga-Rankuwa 4B - Date: '+new Date().toLocaleDateString(),10,20);
 doc.text('Guard: T780-07 - Incidents: '+document.getElementById('evList').innerText.length+' events',10,30);
 doc.text('Evidence:',10,40); fetch('/api/evidence').then(r=>r.json()).then(list=>{
  let y=50; list.forEach(e=>{doc.text(e.id+' - '+e.timestamp+' - '+e.trigger,10,y); y+=10}); doc.save('Zondi_Night_Report.pdf'); log('PDF report generated for client');
 });
}
</script>
</body></html>
"""

@app.route("/")
def home(): return HTML

@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json()
    if data.get("u")=="guard1" and data.get("p")=="1234":
        return jsonify({"ok":True,"role":"guard"})
    if data.get("u")=="client1" and data.get("p")=="1234":
        return jsonify({"ok":True,"role":"client"})
    return jsonify({"ok":False})

@app.route("/api/location")
def loc(): return jsonify({"ok":True})

@app.route("/api/ptt/<state>")
def ptt(state):
    evidence.append({"id":f"PTT-{len(evidence)}","device_id":"T780-07","timestamp":datetime.datetime.now().isoformat(),"trigger":f"PTT_{state.upper()}"})
    save_ev(); return jsonify({"ok":True})

# REAL T780 WEBHOOK - This is what real eTera radio will call when red button pressed
@app.route("/api/t780/sos", methods=["POST"])
def t780_real_sos():
    data = request.get_json() or {}
    entry={"id":f"EV-{len(evidence)+1:04d}","device_id":data.get("device_id","T780-07-REAL"),"timestamp":datetime.datetime.now().isoformat(),"trigger":"REAL_T780_RED_BUTTON","lat":data.get("lat"),"lng":data.get("lng"),"battery":data.get("battery")}
    evidence.append(entry); save_ev()
    print(f"REAL SOS FROM RADIO: {entry}")
    return jsonify({"status":"received","id":entry["id"]})

@app.route("/api/emergency/upload", methods=["POST"])
def upload():
    device_id=request.form.get("device_id","T780-07")
    trigger=request.form.get("trigger","MANUAL_SOS")
    video=request.files.get("video")
    fname=f"{device_id}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.webm"
    if video: video.save(os.path.join("evidence",fname))
    entry={"id":f"EV-{len(evidence)+1:04d}","device_id":device_id,"timestamp":datetime.datetime.now().isoformat(),"trigger":trigger,"video":fname}
    evidence.append(entry); save_ev(); return jsonify(entry)

@app.route("/api/evidence")
def ev(): return jsonify(evidence)

if __name__=="__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
