# main.py - ZONDI SERVICES - NO GLITCH VERSION
from flask import Flask, request, jsonify
import os, datetime
from pathlib import Path

app = Flask(__name__)
Path("evidence").mkdir(exist_ok=True)

evidence = []

HTML = """
<html>
<head><title>Zondi Services</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
body{background:#050a0f;color:white;font-family:Arial;padding:15px}
.card{background:#0f1a24;border:1px solid #0ff3;padding:15px;border-radius:12px;margin-bottom:12px}
.btn{background:#00e5ff;color:black;padding:12px;width:100%;border-radius:10px;font-weight:bold;border:none;margin-top:8px}
.btn-red{background:#b00020;color:white}
.tag{font-size:11px;background:#003300;color:#00ff88;padding:3px 8px;border-radius:5px}
.log{background:black;height:100px;overflow-y:auto;font-size:11px;padding:8px;border-radius:8px;color:#aaa}
</style>
</head>
<body>
<h2 style="color:#00e5ff">ZONDI SERVICES - T780 FEATURE LIVE</h2>
<p style="font-size:12px;color:#888">main.py running on Render - No glitch</p>

<div class="card">
<h3>eTera T780 - Unit 07 - Ga-Rankuwa</h3>
<p><span class="tag">ONLINE - 4G LTE</span> <span class="tag">Battery 78% - 11h left</span></p>
<p style="font-size:11px;margin-top:8px">
IP68 Waterproof | 5200mAh | NFC | 4G LTE | Dual SIM | M6 Connector
</p>
<button class="btn" id="pttBtn">HOLD TO TALK - PTT</button>
<button class="btn btn-red" onclick="doSOS()">SOS EMERGENCY - RECORD & UPLOAD</button>
<video id="vid" autoplay muted style="width:100%;height:180px;background:black;border-radius:10px;margin-top:10px;display:none"></video>
<div id="log" class="log">System ready. T780 connected...</div>
</div>

<div class="card">
<h3>Live Location</h3>
<p style="font-size:12px;color:#0ff" id="loc">Ga-Rankuwa - Zone 4B - -25.6242, 28.0038</p>
<button class="btn" style="background:#333;color:white" onclick="doGPS()">Update GPS</button>
</div>

<div class="card">
<h3>Evidence Locker (Dev View)</h3>
<div id="evList" style="font-size:12px">No evidence yet</div>
<button class="btn" style="background:#333;color:white" onclick="loadEv()">Refresh Evidence</button>
</div>

<script>
function log(m){let l=document.getElementById('log');l.innerHTML=new Date().toLocaleTimeString()+' - '+m+'<br>'+l.innerHTML}
document.getElementById('pttBtn').onmousedown=()=>log('PTT START - Broadcasting to radios');
document.getElementById('pttBtn').onmouseup=()=>log('PTT END');

function doGPS(){
 fetch('/api/location?lat=-25.6245&lng=28.004')
 .then(r=>r.json()).then(d=>{
   document.getElementById('loc').innerText=d.zone+' - '+d.lat+','+d.lng;
   log('GPS updated: '+d.lat+','+d.lng);
 });
}

async function doSOS(){
 log('SOS TRIGGERED - Recording 10s...');
 let vid=document.getElementById('vid'); vid.style.display='block';
 try{
   let stream=await navigator.mediaDevices.getUserMedia({video:true,audio:true});
   vid.srcObject=stream;
   let chunks=[]; let rec=new MediaRecorder(stream);
   rec.ondataavailable=e=>chunks.push(e.data);
   rec.onstop=async()=>{
     let blob=new Blob(chunks,{type:'video/webm'});
     let fd=new FormData(); fd.append('video',blob,'sos.webm');
     fd.append('device_id','T780-07');
     let res=await fetch('/api/emergency/upload',{method:'POST',body:fd});
     let data=await res.json();
     log('EVIDENCE UPLOADED: '+data.id+' to dev');
     loadEv();
   };
   rec.start();
   setTimeout(()=>{rec.stop(); stream.getTracks().forEach(t=>t.stop());}, 10000);
 }catch(e){
   log('No camera, logging SOS anyway: '+e.message);
   let fd=new FormData(); fd.append('device_id','T780-07');
   let res=await fetch('/api/emergency/upload',{method:'POST',body:fd});
   let data=await res.json(); log('Logged: '+data.id);
 }
}

async function loadEv(){
 let res=await fetch('/api/evidence'); let list=await res.json();
 document.getElementById('evList').innerHTML=list.map(e=>'<div style=background:black;padding:6px;margin:4px 0;border-radius:6px>'+e.id+' - '+e.device_id+' - '+e.timestamp+'</div>').join('') || 'Empty';
}
log('Ready - T780 feature loaded');
</script>
</body>
</html>
"""

@app.route("/")
def home():
    return HTML

@app.route("/api/location")
def loc():
    lat = request.args.get("lat", "-25.6242")
    lng = request.args.get("lng", "28.0038")
    return jsonify({"lat": lat, "lng": lng, "zone": "Ga-Rankuwa - Zone 4B"})

@app.route("/api/emergency/upload", methods=["POST"])
def up():
    device_id = request.form.get("device_id", "T780-07")
    video = request.files.get("video")
    fname = f"{device_id}_{datetime.datetime.now().strftime('%H%M%S')}.webm"
    if video:
        video.save(os.path.join("evidence", fname))
    entry = {"id": f"EV-{len(evidence)+1:04d}", "device_id": device_id, "timestamp": datetime.datetime.now().isoformat(), "video": fname}
    evidence.append(entry)
    return jsonify(entry)

@app.route("/api/evidence")
def ev():
    return jsonify(evidence)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
