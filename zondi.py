# zondi.py - V2 - Persistent Evidence + Real Map
from flask import Flask, request, jsonify
import os, datetime, json
from pathlib import Path

app = Flask(__name__)
Path("evidence").mkdir(exist_ok=True)
EVIDENCE_FILE = "evidence/data.json"

# Load old evidence if exists
if os.path.exists(EVIDENCE_FILE):
    with open(EVIDENCE_FILE, "r") as f:
        evidence = json.load(f)
else:
    evidence = []

def save_evidence():
    with open(EVIDENCE_FILE, "w") as f:
        json.dump(evidence, f)

HTML = """
<html><head><title>Zondi V2</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
body{background:#050a0f;color:white;font-family:Arial;padding:15px;margin:0}
.card{background:#0f1a24;border:1px solid #0ff3;padding:15px;border-radius:12px;margin-bottom:12px}
.btn{background:#00e5ff;color:black;padding:12px;width:100%;border-radius:10px;font-weight:bold;border:none;margin-top:8px;cursor:pointer}
.btn-red{background:#b00020;color:white}
.log{background:black;height:100px;overflow-y:auto;font-size:11px;padding:8px;border-radius:8px;color:#aaa}
#map{height:250px;border-radius:10px;margin-top:10px}
</style>
</head>
<body>
<h2 style="color:#00e5ff">ZONDI V2 - Evidence Now Saves Forever</h2>

<div class="card">
<h3>eTera T780 - Unit 07</h3>
<p style="font-size:11px">Battery 78% | 4G LTE | Ga-Rankuwa Zone 4B</p>
<button class="btn" onmousedown="log('PTT START')" onmouseup="log('PTT END')">HOLD TO TALK - PTT</button>
<button class="btn btn-red" onclick="doSOS()">SOS EMERGENCY RECORD</button>
<video id="vid" autoplay muted style="width:100%;height:180px;background:black;border-radius:10px;margin-top:10px;display:none"></video>
<div id="log" class="log">System ready... V2 loaded</div>
</div>

<div class="card">
<h3>Live Location Map</h3>
<div id="map"></div>
<p style="font-size:11px;color:#0ff;margin-top:6px" id="coords">-25.6242, 28.0038 - Ga-Rankuwa</p>
<button class="btn" style="background:#333;color:white" onclick="moveMap()">Simulate T780 Moving</button>
</div>

<div class="card">
<h3>Evidence Locker - Now Persistent</h3>
<div id="evList">Loading...</div>
</div>

<script>
let map = L.map('map').setView([-25.6242, 28.0038], 15);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(map);
let marker = L.marker([-25.6242, 28.0038]).addTo(map).bindPopup('T780-07 - Ga-Rankuwa');

function log(m){let l=document.getElementById('log');l.innerHTML=new Date().toLocaleTimeString()+' - '+m+'<br>'+l.innerHTML}

function moveMap(){
 let lat = -25.6242 + (Math.random()-0.5)*0.01;
 let lng = 28.0038 + (Math.random()-0.5)*0.01;
 marker.setLatLng([lat,lng]); map.setView([lat,lng]);
 document.getElementById('coords').innerText = lat.toFixed(4)+', '+lng.toFixed(4);
 fetch('/api/location?lat='+lat+'&lng='+lng);
 log('T780 moved to '+lat.toFixed(4));
}

async function doSOS(){
 log('SOS - Recording...');
 let vid=document.getElementById('vid'); vid.style.display='block';
 try{
  let s=await navigator.mediaDevices.getUserMedia({video:true,audio:true});
  vid.srcObject=s; let chunks=[]; let r=new MediaRecorder(s);
  r.ondataavailable=e=>chunks.push(e.data);
  r.onstop=async()=>{
   let blob=new Blob(chunks,{type:'video/webm'});
   let fd=new FormData(); fd.append('video',blob,'sos.webm'); fd.append('device_id','T780-07');
   let res=await fetch('/api/emergency/upload',{method:'POST',body:fd});
   let d=await res.json(); log('SAVED FOREVER: '+d.id); loadEv();
  };
  r.start(); setTimeout(()=>{r.stop(); s.getTracks().forEach(t=>t.stop());}, 8000);
 }catch(e){
  let fd=new FormData(); fd.append('device_id','T780-07');
  let res=await fetch('/api/emergency/upload',{method:'POST',body:fd});
  let d=await res.json(); log('Saved without video: '+d.id); loadEv();
 }
}
async function loadEv(){
 let res=await fetch('/api/evidence'); let list=await res.json();
 document.getElementById('evList').innerHTML = list.map(e=>'<div style=background:black;padding:6px;margin:4px 0;border-radius:6px>'+e.id+' - '+e.device_id+'<br><small>'+e.timestamp+'</small></div>').join('') || 'Empty - no evidence yet';
}
loadEv();
</script>
</body></html>
"""

@app.route("/")
def home(): return HTML

@app.route("/api/location")
def loc():
    return jsonify({"lat": request.args.get("lat"), "lng": request.args.get("lng"), "zone": "Ga-Rankuwa"})

@app.route("/api/emergency/upload", methods=["POST"])
def upload():
    device_id = request.form.get("device_id", "T780-07")
    video = request.files.get("video")
    fname = f"{device_id}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.webm"
    if video:
        video.save(os.path.join("evidence", fname))
    entry = {"id": f"EV-{len(evidence)+1:04d}", "device_id": device_id, "timestamp": datetime.datetime.now().isoformat(), "video": fname}
    evidence.append(entry)
    save_evidence() # <-- THIS IS NEW! Now it saves to file forever
    return jsonify(entry)

@app.route("/api/evidence")
def ev():
    return jsonify(evidence)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
