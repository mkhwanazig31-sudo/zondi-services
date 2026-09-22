# zondi.py V7 - Welcoming Theme (not Matrix)
from flask import Flask, request, jsonify, session, redirect
import os, datetime, json
from pathlib import Path

app = Flask(__name__)
app.secret_key = "zondi-v7-welcoming"
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

STYLE = '''
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
*{font-family:'Inter', Arial, sans-serif}
body{margin:0;background:#f6f8fb;color:#1a2a3a}
.nav{display:flex;justify-content:space-between;align-items:center;padding:14px 24px;background:white;position:sticky;top:0;box-shadow:0 2px 12px rgba(0,0,0,0.06);z-index:10}
.logo{font-weight:800;color:#0b5fff;font-size:18px;letter-spacing:-0.5px}
.nav a{color:#5a6a7a;text-decoration:none;margin-right:18px;font-size:14px;font-weight:500}
.nav a.active{color:#0b5fff;font-weight:700}
.btn{padding:12px 22px;border-radius:12px;font-weight:700;border:none;cursor:pointer;text-decoration:none;display:inline-block;transition:0.2s}
.btn-primary{background:#0b5fff;color:white;box-shadow:0 4px 14px rgba(11,95,255,0.25)}
.btn-primary:hover{transform:translateY(-1px);box-shadow:0 6px 18px rgba(11,95,255,0.35)}
.btn-out{border:1.5px solid #dde5f0;color:#0b5fff;background:white}
.btn-dark{background:#1a2a3a;color:white}
.card{background:white;border-radius:20px;padding:22px;box-shadow:0 4px 20px rgba(0,0,0,0.05);border:1px solid #eef2f7}
.badge{background:#e8f0ff;color:#0b5fff;padding:6px 12px;border-radius:100px;font-size:11px;font-weight:700;letter-spacing:0.5px}
.hero{background:linear-gradient(180deg,#ffffff 0%,#f0f5ff 100%);padding:70px 24px 40px;text-align:center}
.hero h1{font-size:42px;line-height:1.05;color:#10203a;margin:0;letter-spacing:-1.5px}
.hero h1 span{color:#0b5fff}
.hero p{color:#6a7a8a;max-width:580px;margin:18px auto;font-size:17px;line-height:1.5}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:18px;padding:24px;max-width:1100px;margin:auto}
</style>
'''

LANDING = f'''
<html><head><title>Zondi Services - Trusted Security</title><meta name="viewport" content="width=device-width, initial-scale=1">{STYLE}</head>
<body>
<div class="nav"><div class="logo">🛡️ ZONDI SERVICES</div><div><a href="/" class="active">Home</a><a href="/pricing">Pricing</a><a href="/login" class="btn btn-primary" style="padding:8px 16px;margin-left:8px">Login</a></div></div>

<div class="hero">
<span class="badge">SERVING GA-RANKUWA • SOSHANGUVE • MABOPANE SINCE 2023</span>
<h1>Security that <span>feels like family,</span><br>protects like SAPS.</h1>
<p>No more scary black screens. Just clean tracking, instant WhatsApp alerts when guard needs help, and video proof that stands in court. Built for kasi shops by kasi people.</p>
<div style="margin-top:26px"><a class="btn btn-primary" href="/login">Open Dashboard</a> <a class="btn btn-out" href="/pricing" style="margin-left:10px">See Pricing</a></div>
<div style="margin-top:18px;color:#8a9aaa;font-size:12px">✓ No contract • ✓ Pay with Cash/EFT • ✓ Works even without data</div>
</div>

<div class="grid">
<div class="card"><div style="font-size:28px">🤝</div><h3 style="margin:10px 0 6px">Friendly, Not Scary</h3><p style="color:#6a7a8a;font-size:14px;line-height:1.5">Mama in shop can use it. Big buttons, clear English + Setswana, no hacker codes. If guard falls, we call you, not confuse you.</p></div>
<div class="card"><div style="font-size:28px">🚨</div><h3 style="margin:10px 0 6px">Guard Down Safety</h3><p style="color:#6a7a8a;font-size:14px;line-height:1.5">If guard stops moving 10 mins, auto SOS with live Google Maps link sent to your WhatsApp. You know exactly where to help.</p></div>
<div class="card"><div style="font-size:28px">📹</div><h3 style="margin:10px 0 6px">Video Proof Vault</h3><p style="color:#6a7a8a;font-size:14px;line-height:1.5">Every SOS saves 8s video. Cannot be deleted. Share with SAPS in one click. No more "he said, she said".</p></div>
<div class="card"><div style="font-size:28px">📶</div><h3 style="margin:10px 0 6px">Works Offline</h3><p style="color:#6a7a8a;font-size:14px;line-height:1.5">Data finished? No problem. T780 queues evidence, auto-uploads when back online. Perfect for Zone 4B.</p></div>
</div>

<div style="max-width:1100px;margin:20px auto;padding:0 24px">
<div class="card" style="background:#10203a;color:white;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:16px">
<div><h3 style="margin:0">Trusted by 12 shops in Zone 4B</h3><p style="margin:6px 0 0;color:#aab8ca;font-size:13px">"Before Zondi we had 3 break-ins. Now 0 in 4 months. And my wife can check guard on phone." - Mr Molefe, General Dealer</p></div><a class="btn" style="background:white;color:#10203a" href="/pricing">Join them from R499</a>
</div>
</div>

<div style="text-align:center;padding:40px;color:#9aabbb;font-size:12px">Zondi Services (Pty) Ltd • Ga-Rankuwa • 060 123 4567 • Friendly security for kasi business</div>
</body></html>
'''

PRICING = f'''
<html><head><title>Pricing - Zondi</title><meta name="viewport" content="width=device-width, initial-scale=1">{STYLE}
<style>.grid3{{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:20px;margin-top:28px}}
.price{{font-size:36px;font-weight:800;color:#10203a}}.price span{{font-size:14px;color:#6a7a8a;font-weight:500}}
ul{{color:#4a5a6a;font-size:14px;line-height:2;padding-left:18px}}
.popular{{border:2px solid #0b5fff!important;transform:scale(1.02)}}
</style></head><body>
<div class="nav"><div class="logo">🛡️ ZONDI SERVICES</div><div><a href="/">Home</a><a href="/pricing" class="active">Pricing</a><a href="/login" class="btn btn-primary" style="padding:8px 16px;margin-left:8px">Login</a></div></div>
<div style="max-width:1100px;margin:auto;padding:30px 24px">
<h1 style="text-align:center;color:#10203a;font-size:36px;letter-spacing:-1px;margin-bottom:8px">Simple, honest pricing</h1>
<p style="text-align:center;color:#6a7a8a">Start small, grow when ready. No scary contracts. Cancel with WhatsApp.</p>

<div class="grid3">
<div class="card"><h3>Starter</h3><div class="price">R499 <span>/mo</span></div><p style="color:#8a9aaa;font-size:12px">Perfect for 1 shop</p>
<ul><li>Live guard on map</li><li>Daily PDF report 06:00</li><li>Video evidence viewer</li><li>WhatsApp SOS</li><li>1 x T780 bodycam</li></ul>
<a class="btn btn-out" href="/login" style="width:100%;text-align:center;box-sizing:border-box;margin-top:14px">Start Starter</a></div>

<div class="card popular"><span class="badge">MOST POPULAR IN GA-RANKUWA</span><h3 style="margin-top:12px">Growth</h3><div class="price">R1,499 <span>/mo</span></div><p style="color:#8a9aaa;font-size:12px">3 shops + patrol car</p>
<ul><li><b>Everything in Starter +</b></li><li>Guard Down auto SOS</li><li>Offline queue mode</li><li>Face unlock for T780</li><li>3 x T780 + dashcam</li><li>SAPS export for docket</li></ul>
<a class="btn btn-primary" href="/login" style="width:100%;text-align:center;box-sizing:border-box;margin-top:14px">Start Growth - Best Value</a></div>

<div class="card"><h3>Enterprise</h3><div class="price">R3,999 <span>/mo</span></div><p style="color:#8a9aaa;font-size:12px">Complex / Mall</p>
<ul><li>Everything in Growth +</li><li>Unlimited zones</li><li>Control room dashboard</li><li>24/7 Zondi call center</li><li>10+ devices included</li></ul>
<a class="btn btn-out" href="/login" style="width:100%;text-align:center;box-sizing:border-box;margin-top:14px">Talk to us</a></div>
</div>

<div class="card" style="margin-top:28px;background:#f0f5ff;border:1px dashed #0b5fff44;text-align:center">
<h3 style="margin:0;color:#10203a">Pay how you want - Kasi friendly</h3><p style="color:#5a6a7a;font-size:13px">EFT • Cash at Ga-Rankuwa office (Zone 15) • PayShap • Monthly debit. No credit card needed. Receipt on WhatsApp.</p>
<p style="color:#0b5fff;font-weight:700;font-size:13px">📞 060 123 4567 - Activate today, guard tomorrow</p>
</div>
</div>
</body></html>
'''

LOGIN_PAGE = f'''
<html><head><title>Login - Zondi</title><meta name="viewport" content="width=device-width, initial-scale=1">{STYLE}
<style>body{{display:flex;align-items:center;justify-content:center;min-height:100vh;background:#f0f5ff}}
.box{{background:white;padding:32px;border-radius:24px;box-shadow:0 12px 40px rgba(0,0,0,0.08);width:90%;max-width:380px;text-align:center;margin-top:40px}}
input,select{{width:100%;padding:14px;margin:8px 0;border-radius:12px;border:1.5px solid #dde5f0;background:#f9fbff;box-sizing:border-box;font-size:15px}}
input:focus{{border-color:#0b5fff;outline:none;background:white}}
.tab{{display:flex;margin:16px 0;background:#f0f5ff;border-radius:100px;padding:4px}}.tab div{{flex:1;padding:10px;border-radius:100px;cursor:pointer;font-size:14px;font-weight:600;color:#6a7a8a}}.active{{background:white;color:#0b5fff!important;box-shadow:0 2px 8px rgba(0,0,0,0.08)}}
</style></head><body>
<div class="nav" style="position:absolute;top:0;left:0;right:0"><div class="logo">🛡️ ZONDI SERVICES</div><div><a href="/">Home</a><a href="/pricing">Pricing</a></div></div>
<div class="box">
<div style="font-size:36px">👋</div>
<h2 style="margin:8px 0 4px;color:#10203a">Welcome back</h2><p style="margin:0 0 12px;color:#6a7a8a;font-size:14px">Login to protect your shop</p>
<div class="tab"><div id="t1" class="active" onclick="showTab(1)">Login</div><div id="t2" onclick="showTab(2)">Register</div></div>
<div id="loginForm"><input id="u" placeholder="Username (lowercase)"><input id="p" type="password" placeholder="Password"><button class="btn btn-primary" style="width:100%;margin-top:12px" onclick="doLogin()">Login securely</button><p id="msg1" style="color:#d00;font-size:12px"></p><p style="font-size:12px;color:#8a9aaa;margin-top:12px">Demo: guard1 / 1234</p></div>
<div id="regForm" style="display:none"><input id="ru" placeholder="Choose username"><input id="rp" type="password" placeholder="Choose password"><select id="rr"><option value="client">I'm a Shop Owner (Client)</option><option value="guard">I'm a Guard</option></select><input id="rc" placeholder="Shop name / Zone"><button class="btn btn-primary" style="width:100%;margin-top:12px" onclick="doReg()">Create account</button><p id="msg2" style="font-size:12px"></p></div>
</div>
<script>
function showTab(n){{document.getElementById("loginForm").style.display=n==1?"block":"none";document.getElementById("regForm").style.display=n==2?"block":"none";document.getElementById("t1").className=n==1?"active":"";document.getElementById("t2").className=n==2?"active":"";}}
async function doLogin(){{let u=document.getElementById("u").value.trim().toLowerCase();let p=document.getElementById("p").value.trim();let res=await fetch("/api/login",{{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify({{u,p}})}});let d=await res.json();if(d.ok)location="/dashboard";else document.getElementById("msg1").innerText="Wrong username or password";}}
async function doReg(){{let u=document.getElementById("ru").value.trim().toLowerCase();let p=document.getElementById("rp").value.trim();let r=document.getElementById("rr").value;let c=document.getElementById("rc").value;if(!u||!p){{document.getElementById("msg2").innerText="Fill all";return;}}let res=await fetch("/api/register",{{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify({{u,p,role:r,company:c}})}});let d=await res.json();if(d.ok){{document.getElementById("msg2").style.color="#0a0";document.getElementById("msg2").innerText="Account created! Now login.";showTab(1);document.getElementById("u").value=u;}}else{{document.getElementById("msg2").style.color="#d00";document.getElementById("msg2").innerText=d.error;}}}}
</script>
</body></html>
'''

DASHBOARD_PAGE = f'''
<html><head><title>Dashboard - Zondi</title><meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
{STYLE}
<style>
body{{background:#f6f8fb}}.top{{background:white;padding:14px 20px;display:flex;justify-content:space-between;box-shadow:0 2px 10px rgba(0,0,0,0.04);align-items:center}}
.card{{margin:14px;border-radius:20px}}
.log{{background:#10203a;color:#7aff9a;height:90px;overflow-y:auto;font-size:11px;padding:10px;border-radius:12px;font-family:monospace}}
#map{{height:280px;border-radius:16px}}
.alert{{background:#ff3b3b;color:white;padding:14px;border-radius:16px;margin:14px;display:none;box-shadow:0 4px 16px rgba(255,59,59,0.3)}}
</style></head><body>
<div class="nav"><div class="logo">🛡️ ZONDI</div><div><a href="/">Home</a><a href="/pricing">Pricing</a><span id="roleBadge" style="font-weight:700;color:#0b5fff;margin-right:10px;font-size:13px"></span><button onclick="fetch('/api/logout').then(()=>location='/')" style="background:#f0f5ff;border:none;padding:8px 14px;border-radius:10px;font-weight:600">Logout</button></div></div>

<div id="guardDownAlert" class="alert">⚠️ Guard Down - No movement 2 mins! Auto SOS in <span id="countdown">60</span>s <button onclick="cancelGuardDown()" style="background:white;color:#ff3b3b;border:none;padding:6px 12px;border-radius:100px;margin-left:12px;font-weight:700">I'm OK - Cancel</button></div>

<div class="card"><h3 style="margin:0 0 10px">🛡️ Safety Status</h3><div style="display:flex;justify-content:space-between;font-size:13px;color:#5a6a7a"><span>Last movement: <b id="lastMove" style="color:#10203a">Just now</b></span><span>Offline queue: <b id="queueCount">0</b></span></div><div style="background:#e8eef7;height:8px;border-radius:100px;margin-top:10px"><div id="moveBar" style="background:#0b5fff;height:8px;width:100%;border-radius:100px;transition:0.5s"></div></div></div>

<div class="card"><h3>🎙️ T780 Radio</h3><button class="btn btn-primary" style="width:100%" onclick="simMove()">Simulate Patrol (PTT)</button><button class="btn btn-dark" style="width:100%;margin-top:10px;background:#ff3b3b" onclick="doSOS('MANUAL_SOS')">🚨 SOS + WhatsApp Alert</button><video id="vid" autoplay muted style="width:100%;height:180px;background:#10203a;border-radius:16px;margin-top:12px;display:none"></video><div id="log" class="log" style="margin-top:12px">System ready. Guard Down monitoring active.</div></div>

<div class="card"><h3>📍 Live Map - Ga-Rankuwa</h3><div id="map"></div><p style="font-size:12px;color:#5a6a7a;margin-top:8px" id="coords"></p></div>

<div class="card"><h3>📂 Evidence Vault</h3><div id="evList" style="font-size:12px"></div></div>

<script>
let lastMoveTime=Date.now(), guardDownTimer=null, guardDownCountdown=null, offlineQueue=JSON.parse(localStorage.getItem("zondiQueue")||"[]"), currentLat=-25.6242, currentLng=28.0038;
function updateQueueUI(){{document.getElementById("queueCount").innerText=offlineQueue.length; localStorage.setItem("zondiQueue",JSON.stringify(offlineQueue));}} updateQueueUI();
fetch("/api/me").then(r=>r.json()).then(d=>{{document.getElementById("roleBadge").innerText=d.user+" ("+d.role+")"; loadEv();}});
let map=L.map("map").setView([-25.6242,28.0038],14); L.tileLayer("https://{s}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png").addTo(map); let marker=L.marker([-25.6242,28.0038]).addTo(map);
function log(m){{let l=document.getElementById("log");l.innerHTML=new Date().toLocaleTimeString()+" - "+m+"<br>"+l.innerHTML}}
function updateWALink(){{document.getElementById("coords").innerHTML=currentLat.toFixed(5)+", "+currentLng.toFixed(5)+' - <a href="https://wa.me/?text='+encodeURIComponent("🚨 ZONDI SOS! "+currentLat+","+currentLng+" https://maps.google.com/?q="+currentLat+","+currentLng)+'" target="_blank" style="color:#0b5fff;font-weight:700">📲 Send WhatsApp Alert</a>';}}
updateWALink();
function simMove(){{currentLat=-25.6242+(Math.random()-0.5)*0.01; currentLng=28.0038+(Math.random()-0.5)*0.01; marker.setLatLng([currentLat,currentLng]); map.setView([currentLat,currentLng]); lastMoveTime=Date.now(); document.getElementById("lastMove").innerText="Just now"; document.getElementById("moveBar").style.width="100%"; document.getElementById("moveBar").style.background="#0b5fff"; updateWALink(); log("Patrol moved"); resetGuardDown();}}
function resetGuardDown(){{clearTimeout(guardDownTimer); clearInterval(guardDownCountdown); document.getElementById("guardDownAlert").style.display="none"; guardDownTimer=setTimeout(()=>{{startGuardDownCountdown()}}, 2*60*1000);}} resetGuardDown();
function startGuardDownCountdown(){{document.getElementById("guardDownAlert").style.display="block"; let c=60; guardDownCountdown=setInterval(()=>{{c--; document.getElementById("countdown").innerText=c; if(c<=0){{clearInterval(guardDownCountdown); doSOS("GUARD_DOWN_AUTO");}}}},1000); log("Guard Down countdown");}}
function cancelGuardDown(){{log("Guard OK"); resetGuardDown(); lastMoveTime=Date.now();}}
setInterval(()=>{{let diff=(Date.now()-lastMoveTime)/1000; let pct=Math.max(0,100-(diff/(2*60))*100); document.getElementById("moveBar").style.width=pct+"%"; if(pct<30)document.getElementById("moveBar").style.background="#ff3b3b"; else if(pct<60)document.getElementById("moveBar").style.background="#ffaa00"; else document.getElementById("moveBar").style.background="#0b5fff"; if(diff>10)document.getElementById("lastMove").innerText=Math.floor(diff)+"s ago";}},1000);
async function doSOS(trigger){{log(trigger+" SOS"); let vid=document.getElementById("vid"); vid.style.display="block"; try{{let s=await navigator.mediaDevices.getUserMedia({{video:true,audio:true}}); vid.srcObject=s; let chunks=[]; let r=new MediaRecorder(s); r.ondataavailable=e=>chunks.push(e.data); r.onstop=async()=>{{let blob=new Blob(chunks,{{type:"video/webm"}}); await uploadEvidence(blob,trigger);}}; r.start(); setTimeout(()=>{{r.stop(); s.getTracks().forEach(t=>t.stop());}},8000);}}catch(e){{await uploadEvidence(null,trigger);}}}}
async function uploadEvidence(blob,trigger){{let fd=new FormData(); if(blob)fd.append("video",blob,"sos.webm"); fd.append("trigger",trigger); fd.append("lat",currentLat); fd.append("lng",currentLng); try{{let res=await fetch("/api/emergency/upload",{{method:"POST",body:fd}}); if(!res.ok)throw new Error(); let d=await res.json(); log("Saved "+d.id); loadEv(); window.open("https://wa.me/?text="+encodeURIComponent("🚨 ZONDI SOS "+trigger+" https://maps.google.com/?q="+currentLat+","+currentLng),"_blank");}}catch(err){{log("OFFLINE queued"); offlineQueue.push({{trigger,lat:currentLat,lng:currentLng,time:new Date().toISOString()}}); updateQueueUI();}}}}
async function loadEv(){{let res=await fetch("/api/evidence"); let list=await res.json(); document.getElementById("evList").innerHTML=list.map(e=>"<div style=background:#f6f8fb;padding:10px;margin:6px 0;border-radius:12px;border:1px solid #eef2f7><b>"+e.id+"</b> | "+e.trigger+"<br><small style=color:#6a7a8a>"+e.timestamp+" | "+(e.lat||"")+"</small></div>").join("")||"<p style=color:#8a9aaa>No evidence yet - stay safe</p>";}}
</script></body></html>
'''

@app.route("/")
def landing(): return LANDING
@app.route("/pricing")
def pricing(): return PRICING
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
    
