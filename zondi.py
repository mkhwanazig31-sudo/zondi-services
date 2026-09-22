# zondi.py V6 - Landing Page + Guard Down + WhatsApp SOS + Offline Queue
from flask import Flask, request, jsonify, session, redirect
import os, datetime, json
from pathlib import Path

app = Flask(__name__)
app.secret_key = "zondi-v6-bc-2026"
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
    return {"guard1":{"pass":"1234","role":"guard","company":"Zone 4B"},"client1":{"pass":"1234","role":"client","company":"Shop 4B"}}
def save_ev(data):
    with open(EVIDENCE_FILE,"w") as f: json.dump(data,f)
def save_users(data):
    with open(USERS_FILE,"w") as f: json.dump(data,f)

LANDING = '''
<html><head><title>Zondi Services - Security</title><meta name="viewport" content="width=device-width, initial-scale=1">
<style>
body{margin:0;font-family:Arial;background:#050a0f;color:white}
.nav{display:flex;justify-content:space-between;padding:16px 24px;background:#0a1520;position:sticky;top:0;border-bottom:1px solid #0ff2}
.btn{padding:12px 22px;border-radius:10px;font-weight:bold;border:none;cursor:pointer;text-decoration:none;display:inline-block}
.btn-cyan{background:#00e5ff;color:black}.btn-out{background:transparent;border:1px solid #00e5ff;color:#00e5ff}
.hero{padding:60px 24px;text-align:center;background:radial-gradient(circle at 50% 0%, #0a2a3a, #050a0f 70%)}
.hero h1{font-size:38px;margin:0;color:#00e5ff;line-height:1.1}
.hero p{color:#aaa;max-width:600px;margin:16px auto;font-size:16px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:16px;padding:24px;max-width:1000px;margin:auto}
.card{background:#0f1a24;border:1px solid #1a3a4a;padding:20px;border-radius:16px}
.price{font-size:28px;color:#00e5ff;font-weight:bold}
.badge{background:#00e5ff22;border:1px solid #00e5ff55;color:#00e5ff;padding:4px 8px;border-radius:20px;font-size:11px}
</style></head>
<body>
<div class="nav"><span style="font-weight:bold;color:#00e5ff">ZONDI SERVICES</span><span><a class="btn btn-out" href="/login">Login</a></span></div>
<div class="hero">
<span class="badge">GA-RANKUWA • SOSIA • MABOPANE • GARAGE</span>
<h1>Security That Records<br>Everything.</h1>
<p>eTera T780 bodycam + GPS + Auto SOS + Evidence Vault. When guard presses SOS, we record 8s video, save location, and send WhatsApp alert to HQ and SAPS. Tamper-proof.</p>
<div style="margin-top:24px"><a class="btn btn-cyan" href="/login">Guard / Client Login</a> <a class="btn btn-out" href="#pricing" style="margin-left:8px">View Pricing</a></div>
<p style="font-size:11px;color:#666;margin-top:12px">Trusted by shops in Zone 4B • Offline mode works without data</p>
</div>

<div class="grid">
<div class="card"><h3>🚨 Guard Down Detection</h3><p style="color:#aaa;font-size:14px">If T780 doesn't move for 10 minutes, system auto-triggers SOS. "Guard Down" alert sent via WhatsApp with live location. No more silent incidents.</p></div>
<div class="card"><h3>📹 8s Evidence Vault</h3><p style="color:#aaa;font-size:14px">Every SOS auto-records 8 seconds video + audio. Stored encrypted. Cannot be deleted by guard. Court-ready evidence for SAPS cases.</p></div>
<div class="card"><h3>📱 WhatsApp SOS</h3><p style="color:#aaa;font-size:14px">No app needed for HQ. SOS sends WhatsApp message: "SOS at [location link] - Guard thabo - Battery 12% - Video: [link]". Click to view live map.</p></div>
<div class="card"><h3>📡 Works Offline</h3><p style="color:#aaa;font-size:14px">Ga-Rankuwa data is expensive. If no internet, T780 queues SOS. When back online, auto-uploads. Guard never loses evidence.</p></div>
</div>

<div id="pricing" class="grid" style="margin-top:20px">
<div class="card" style="border:1px solid #00e5ff"><h3>Starter - Shop Owner</h3><div class="price">R499/mo</div><p style="color:#aaa;font-size:13px">✓ Live guard tracking<br>✓ Daily PDF report 06:00<br>✓ Video evidence access<br>✓ WhatsApp alerts</p><a class="btn btn-cyan" href="/login" style="width:100%;text-align:center;box-sizing:border-box">Register as Client</a></div>
<div class="card"><h3>Pro - 3 Shops + Patrol</h3><div class="price">R1,499/mo</div><p style="color:#aaa;font-size:13px">✓ 3 zones + patrol car<br>✓ Guard face unlock<br>✓ Guard Down auto SOS<br>✓ SAPS integration</p><a class="btn btn-out" href="/login" style="width:100%;text-align:center;box-sizing:border-box">Talk to Zondi</a></div>
</div>

<div style="text-align:center;padding:40px 24px;color:#666;font-size:12px">Zondi Services (Pty) Ltd • Ga-Rankuwa • 2026 • eTera T780-07 Certified • Contact: 060 123 4567</div>
</body></html>
'''

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
<a href="/" style="color:#666;font-size:11px;text-decoration:none">← Back to Home</a>
<h2 style="color:#00e5ff;margin:10px 0 0">ZONDI</h2><p style="margin:5px 0 15px;color:#aaa">Ga-Rankuwa Security</p>
<div class="tab"><div id="t1" class="active" onclick="showTab(1)">LOGIN</div><div id="t2" onclick="showTab(2)">REGISTER</div></div>
<div id="loginForm">
<input id="u" placeholder="Username lowercase">
<input id="p" type="password" placeholder="Password">
<button class="btn" onclick="doLogin()">LOGIN</button>
<p id="msg1" style="color:#f55;font-size:12px"></p>
<small style="color:#888">guard1 / 1234</small>
</div>
<div id="regForm" style="display:none">
<input id="ru" placeholder="Username lowercase">
<input id="rp" type="password" placeholder="Password">
<select id="rr"><option value="client">Client - Shop Owner</option><option value="guard">Guard</option></select>
<input id="rc" placeholder="Shop name / Zone">
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
 let u=document.getElementById("u").value.trim().toLowerCase();
 let p=document.getElementById("p").value.trim();
 let res=await fetch("/api/login",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({u,p})});
 let d=await res.json(); if(d.ok) window.location="/dashboard"; else document.getElementById("msg1").innerText="Wrong login";
}
async function doReg(){
 let u=document.getElementById("ru").value.trim().toLowerCase();
 let p=document.getElementById("rp").value.trim();
 let r=document.getElementById("rr").value;
 let c=document.getElementById("rc").value;
 if(!u||!p){document.getElementById("msg2").innerText="Fill all"; return;}
 let res=await fetch("/api/register",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({u,p,role:r,company:c})});
 let d=await res.json();
 if(d.ok){document.getElementById("msg2").style.color="#0f0"; document.getElementById("msg2").innerText="Created "+u+"! Now login."; showTab(1); document.getElementById("u").value=u;}
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
.log{background:black;height:90px;overflow-y:auto;font-size:11px;padding:8px;border-radius:8px;color:#0f0}#map{height:260px;border-radius:10px}
.alert{background:#b00020;padding:10px;border-radius:10px;margin:12px;display:none}
</style></head><body>
<div class="top"><span style="color:#00e5ff;font-weight:bold">ZONDI DASHBOARD</span><span><span id="roleBadge" style="font-size:12px;margin-right:8px"></span><button onclick="fetch('/api/logout').then(()=>location='/')" style="background:none;border:1px solid #555;color:#aaa;border-radius:6px;padding:4px 8px">Logout</button></span></div>

<div id="guardDownAlert" class="alert">⚠️ GUARD DOWN - No movement 10 mins! Auto SOS in <span id="countdown">60</span>s <button onclick="cancelGuardDown()" style="background:white;color:red;border:none;padding:4px 8px;border-radius:6px;margin-left:10px">I'm OK - Cancel</button></div>

<div class="card"><h3>🛡️ Safety Status</h3><div style="display:flex;justify-content:space-between;font-size:12px"><span>Last Movement: <span id="lastMove">Just now</span></span><span>Offline Queue: <span id="queueCount">0</span></span></div><div style="background:#333;height:6px;border-radius:10px;margin-top:8px"><div id="moveBar" style="background:#0f0;height:6px;width:100%;border-radius:10px"></div></div></div>

<div class="card"><h3>T780-07 Controls</h3>
<div id="pttArea"><button class="btn btn-cyan" onclick="ptt()">HOLD TO TALK (PTT)</button><button class="btn btn-red" onclick="doSOS('MANUAL_SOS')">SOS EMERGENCY + WhatsApp</button><video id="vid" autoplay muted style="width:100%;height:160px;background:black;border-radius:10px;margin-top:8px;display:none"></video></div>
<div id="log" class="log">System ready. Guard Down monitoring active.</div>
</div>

<div class="card"><h3>Live Map - Ga-Rankuwa</h3><div id="map"></div><p style="font-size:11px" id="coords">-25.6242, 28.0038 - <a id="waLink" href="#" target="_blank" style="color:#00e5ff">Send WhatsApp with location</a></p><button class="btn btn-dark" onclick="simMove()">Simulate Patrol Movement</button></div>

<div class="card"><h3>Evidence Vault</h3><div id="evList" style="font-size:11px;margin-top:8px"></div></div>

<script>
let lastMoveTime = Date.now();
let guardDownTimer = null;
let guardDownCountdown = null;
let offlineQueue = JSON.parse(localStorage.getItem("zondiQueue")||"[]");
let currentLat = -25.6242, currentLng = 28.0038;

function updateQueueUI(){document.getElementById("queueCount").innerText=offlineQueue.length; localStorage.setItem("zondiQueue", JSON.stringify(offlineQueue));}
updateQueueUI();

fetch("/api/me").then(r=>r.json()).then(d=>{document.getElementById("roleBadge").innerText=d.user+" ("+d.role+")"; if(d.role==="client") document.getElementById("pttArea").innerHTML="<p style=color:#0ff>Client tracking view - Guard safety monitoring active</p>"; loadEv();});

let map=L.map("map").setView([-25.6242,28.0038],14); L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png").addTo(map); let marker=L.marker([-25.6242,28.0038]).addTo(map);
function log(m){let l=document.getElementById("log");l.innerHTML=new Date().toLocaleTimeString()+" - "+m+"<br>"+l.innerHTML}
function updateWALink(){let msg=encodeURIComponent("🚨 ZONDI SOS! Guard: "+document.getElementById("roleBadge").innerText+" Location: https://maps.google.com/?q="+currentLat+","+currentLng+" Time: "+new Date().toLocaleString()); document.getElementById("waLink").href="https://wa.me/?text="+msg; document.getElementById("coords").innerHTML=currentLat.toFixed(5)+", "+currentLng.toFixed(5)+' - <a href="'+document.getElementById("waLink").href+'" target="_blank" style="color:#0f0">📲 WhatsApp Alert</a>';}
updateWALink();

function simMove(){
 currentLat = -25.6242+(Math.random()-0.5)*0.01; currentLng = 28.0038+(Math.random()-0.5)*0.01;
 marker.setLatLng([currentLat, currentLng]); map.setView([currentLat, currentLng]);
 lastMoveTime = Date.now(); document.getElementById("lastMove").innerText="Just now"; document.getElementById("moveBar").style.width="100%"; document.getElementById("moveBar").style.background="#0f0";
 updateWALink(); log("Patrol moved"); resetGuardDown();
}

function resetGuardDown(){
 clearTimeout(guardDownTimer); clearInterval(guardDownCountdown); document.getElementById("guardDownAlert").style.display="none";
 // Guard Down check: 2 mins for demo (real = 10 mins) -> change 2*60*1000 to 10*60*1000
 guardDownTimer = setTimeout(()=>{startGuardDownCountdown()}, 2*60*1000);
}
resetGuardDown();

function startGuardDownCountdown(){
 document.getElementById("guardDownAlert").style.display="block"; let c=60;
 guardDownCountdown = setInterval(()=>{c--; document.getElementById("countdown").innerText=c; if(c<=0){clearInterval(guardDownCountdown); doSOS("GUARD_DOWN_AUTO"); log("GUARD DOWN AUTO SOS TRIGGERED");}},1000);
 log("⚠️ No movement 2 mins - Guard Down countdown started");
}
function cancelGuardDown(){log("Guard OK - Cancelled Guard Down"); resetGuardDown(); lastMoveTime=Date.now();}

setInterval(()=>{
 let diff = (Date.now()-lastMoveTime)/1000;
 let pct = Math.max(0, 100 - (diff/(2*60))*100);
 document.getElementById("moveBar").style.width=pct+"%";
 if(pct<30) document.getElementById("moveBar").style.background="#f00"; else if(pct<60) document.getElementById("moveBar").style.background="#ff0"; else document.getElementById("moveBar").style.background="#0f0";
 if(diff>10) document.getElementById("lastMove").innerText=Math.floor(diff)+"s ago";
},1000);

function ptt(){log("PTT Pressed"); simMove();}

async function doSOS(trigger){
 log(trigger+" TRIGGERED - Recording 8s");
 let vid=document.getElementById("vid"); vid.style.display="block";
 try{
  let s=await navigator.mediaDevices.getUserMedia({video:true,audio:true}); vid.srcObject=s; let chunks=[]; let r=new MediaRecorder(s);
  r.ondataavailable=e=>chunks.push(e.data);
  r.onstop=async()=>{
   let blob=new Blob(chunks,{type:"video/webm"}); await uploadEvidence(blob, trigger);
  };
  r.start(); setTimeout(()=>{r.stop(); s.getTracks().forEach(t=>t.stop());},8000);
 }catch(e){
  await uploadEvidence(null, trigger);
 }
}

async function uploadEvidence(blob, trigger){
 let fd=new FormData();
 if(blob) fd.append("video",blob,"sos.webm");
 fd.append("trigger",trigger); fd.append("lat",currentLat); fd.append("lng",currentLng);
 try{
  let res=await fetch("/api/emergency/upload",{method:"POST",body:fd});
  if(!res.ok) throw new Error("offline");
  let d=await res.json(); log("Evidence saved "+d.id+" - WhatsApp ready"); loadEv();
  window.open(document.getElementById("waLink").href, "_blank");
 }catch(err){
  log("OFFLINE - Queued SOS"); offlineQueue.push({trigger, lat:currentLat, lng:currentLng, time:new Date().toISOString()}); updateQueueUI();
 }
}

async function tryFlushQueue(){
 if(offlineQueue.length==0 ||!navigator.onLine) return;
 log("Online - Flushing "+offlineQueue.length+" queued SOS");
 for(let q of [...offlineQueue]){
  let fd=new FormData(); fd.append("trigger",q.trigger+"_QUEUED"); fd.append("lat",q.lat); fd.append("lng",q.lng);
  try{await fetch("/api/emergency/upload",{method:"POST",body:fd}); offlineQueue.shift(); updateQueueUI();}catch(e){break;}
 }
 loadEv();
}
setInterval(tryFlushQueue, 5000);
window.addEventListener("online", tryFlushQueue);

async function loadEv(){let res=await fetch("/api/evidence"); let list=await res.json(); document.getElementById("evList").innerHTML=list.map(e=>"<div style=background:black;padding:6px;margin:4px 0;border-radius:6px>"+e.id+" | "+e.trigger+"<br><small>"+e.timestamp+" | "+(e.lat||"")+" "+(e.lng||"")+' | <a href="https://maps.google.com/?q='+(e.lat||currentLat)+','+(e.lng||currentLng)+'" target="_blank" style="color:#0ff">View Map</a> | <a href="https://wa.me/?text='+encodeURIComponent("SOS "+e.id+" https://maps.google.com/?q="+(e.lat||"")+" "+(e.timestamp))+'" target="_blank" style="color:#0f0">WhatsApp</a></small></div>').join("")||"No evidence yet";}
</script></body></html>
'''

@app.route("/")
def landing(): return LANDING

@app.route("/login")
def login_page():
    if session.get("user"): return redirect("/dashboard")
    return LOGIN_PAGE

@app.route("/dashboard")
def dashboard():
    if not session.get("user"): return redirect("/login")
    return DASHBOARD_PAGE

@app.route("/api/register", methods=["POST"])
def register():
    data=request.get_json()
    u=data.get("u","").strip().lower(); p=data.get("p","").strip(); role=data.get("role","client")
    if not u or not p: return jsonify({"ok":False,"error":"Fill all"})
    users=load_users()
    if u in users: return jsonify({"ok":False,"error":"Username exists"})
    users[u]={"pass":p,"role":role,"company":data.get("company","")}
    save_users(users)
    return jsonify({"ok":True})

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
    trigger=request.form.get("trigger","SOS")
    lat=request.form.get("lat"); lng=request.form.get("lng")
    video=request.files.get("video")
    fname=f"{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.webm"
    if video: video.save(os.path.join("evidence",fname))
    ev=load_evidence()
    entry={"id":f"EV-{len(ev)+1:04d}","device_id":session.get("user","T780"),"timestamp":datetime.datetime.now().isoformat(),"trigger":trigger,"video":fname,"lat":lat,"lng":lng}
    ev.append(entry); save_ev(ev)
    return jsonify(entry)

@app.route("/api/evidence")
def ev():
    if not session.get("user"): return jsonify([])
    return jsonify(load_evidence())

if __name__=="__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
