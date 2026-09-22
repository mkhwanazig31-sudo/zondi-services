# zondi.py - FULL FINAL - WHITE THEME + Shop + Patrollers trace + Topo/Satellite Map
from flask import Flask, request, jsonify, send_from_directory, render_template_string
import os, json, datetime

app = Flask(__name__)

DB_FILE = "zondi_db.json"
if not os.path.exists(DB_FILE):
    with open(DB_FILE,"w") as f: json.dump({"locations":[],"sos_events":[],"users":[]}, f)

def load_db():
    try:
        with open(DB_FILE) as f: return json.load(f)
    except: return {"locations":[],"sos_events":[],"users":[]}
def save_db(db):
    with open(DB_FILE,"w") as f: json.dump(db,f,indent=2)

# === WHITE THEME NAV - SAME AS YOUR VIDEO ===
NAV = """
<div style="padding:12px 20px;display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #eee;background:#fff;position:sticky;top:0;z-index:10;font-family:system-ui">
<div style="font-size:10px;color:#888;letter-spacing:1px">GA-RANKUWA • SOSHANGUVE • MABOPANE</div>
<div style="display:flex;gap:12px;font-size:13px;align-items:center;overflow-x:auto">
<a href="/" style="text-decoration:none;color:#333">Home</a>
<a href="/shop" style="text-decoration:none;color:#333">Shop</a>
<a href="/patrollers" style="text-decoration:none;color:#fff;background:#0f172a;padding:5px 12px;border-radius:20px;font-weight:600">Patrollers</a>
<a href="/sos" style="text-decoration:none;color:#fff;background:#e11d48;padding:5px 12px;border-radius:20px">SOS</a>
<a href="/login" style="text-decoration:none;color:#333">Login</a>
</div>
</div>
"""

HOME_HTML = NAV + """
<div style="font-family:system-ui;padding:80px 24px;text-align:center;background:#fff;min-height:80vh">
<p style="font-size:10px;color:#888;letter-spacing:2px">GA-RANKUWA • SOSHANGUVE • MABOPANE</p>
<h1 style="font-size:28px;font-weight:800;line-height:1.2;color:#111">Security that feels like family<br><span style="color:#2563eb">protects like SAPS.</span></h1>
<p style="color:#666;font-size:14px">No more black screens. Clean, friendly, works offline. Buy protection in our Shop, live online.</p>
<br>
<a href="/shop" style="background:#2563eb;color:#fff;padding:10px 20px;border-radius:8px;text-decoration:none;font-weight:700">Go to Shop</a>
<a href="/login" style="margin-left:12px;color:#333;text-decoration:none">Login</a>
<br><br>
<div style="display:flex;justify-content:center;gap:40px;font-size:12px;color:#888;margin-top:40px">
<div>✓ Works Offline</div><div>✓ Video Proof Vault</div><div>✓ One tap SOS</div>
</div>
<br><br>
<div style="display:flex;justify-content:center;gap:12px;font-size:13px">
<a href="/sos" style="color:#e11d48;text-decoration:none">→ SOS panic (no login)</a>
<span style="color:#ddd">|</span>
<a href="/patrollers" style="color:#0f172a;text-decoration:none">→ Patrollers Portal</a>
</div>
</div>
"""

SHOP_HTML = NAV + """
<div style="font-family:system-ui;padding:24px;max-width:900px;margin:auto;background:#fff;min-height:80vh">
<h2 style="color:#111">Zondi Shop</h2><p style="color:#666;font-size:13px">Buy protection - works offline</p>
<div style="display:flex;gap:16px;flex-wrap:wrap;margin-top:20px">
<div style="border:1px solid #eee;border-radius:12px;padding:20px;width:220px;text-align:center;background:#fff"><h4>Starter Pack</h4><div style="font-size:24px;font-weight:800">R499</div><p style="font-size:12px;color:#666">For 1 shop</p><button style="background:#2563eb;color:#fff;padding:8px 16px;border-radius:6px;border:0;width:100%;margin-top:10px">Add to Cart</button></div>
<div style="border:2px solid #2563eb;border-radius:12px;padding:20px;width:220px;text-align:center;background:#fff"><h4>Growth Pack</h4><div style="background:#2563eb;color:#fff;font-size:10px;display:inline-block;padding:2px 6px;border-radius:4px">POPULAR</div><div style="font-size:24px;font-weight:800">R1,499</div><p style="font-size:12px;color:#666">For 3 shops + SOS</p><button style="background:#2563eb;color:#fff;padding:8px 16px;border-radius:6px;border:0;width:100%;margin-top:10px">Buy Growth Pack</button></div>
<div style="border:1px solid #eee;border-radius:12px;padding:20px;width:220px;text-align:center;background:#fff"><h4>Enterprise</h4><div style="font-size:24px;font-weight:800">R3,999</div><p style="font-size:12px;color:#666">Unlimited + T780 radio</p><button style="background:#000;color:#fff;padding:8px 16px;border-radius:6px;border:0;width:100%;margin-top:10px">Buy Enterprise</button></div>
</div>
</div>
"""

# === PATROLLERS PORTAL WITH TOPO + SATELLITE + TRACE CLIENTS ===
PATROLLERS_HTML = NAV + """
<div style="font-family:system-ui;padding:12px;max-width:1200px;margin:auto;background:#f8fafc;min-height:90vh">
<div style="display:flex;justify-content:space-between;align-items:center">
<h2 style="color:#111">🛡️ Patrollers Portal - Trace Clients</h2>
<div style="font-size:11px;color:#fff;background:#16a34a;padding:4px 10px;border-radius:12px">● LIVE TRACE</div>
</div>
<p style="color:#666;font-size:13px">White theme kept. See houses with Satellite.</p>

<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>

<div style="display:grid;grid-template-columns:1fr 300px;gap:12px;margin-top:12px">
<div style="background:#fff;border:1px solid #e5e7eb;border-radius:12px;padding:10px">
<div style="display:flex;justify-content:space-between;margin-bottom:6px;flex-wrap:wrap;gap:6px">
<b id="mapTitle" style="color:#111">Tracing: All Clients + Shops</b>
<select id="layerSelect" style="padding:4px 8px;border-radius:8px;border:1px solid #ddd;font-size:12px"><option value="satellite">Satellite (see houses)</option><option value="topo">Topographic</option><option value="street">Street</option></select>
</div>
<div id="map" style="height:520px;border-radius:10px"></div>
<div style="font-size:11px;color:#666;margin-top:4px">Satellite = see roofs / Topo = contours. Click client to trace blue trail live.</div>
</div>

<div style="display:flex;flex-direction:column;gap:10px">
<div style="background:#fff;border:1px solid #e5e7eb;border-radius:12px;padding:10px">
<h4 style="margin:0;color:#111">🚨 Live SOS (click to trace)</h4>
<div id="sosFeed" style="font-size:12px;max-height:220px;overflow-y:auto">Loading...</div>
</div>
<div style="background:#fff;border:1px solid #e5e7eb;border-radius:12px;padding:10px">
<h4 style="margin:0;color:#111">📱 Clients to Trace</h4>
<div id="clientList" style="font-size:12px;margin-top:6px">Loading clients...</div>
<div id="trailBox" style="margin-top:8px;font-size:11px;background:#f8fafc;padding:6px;border-radius:8px">Select client to see trail</div>
</div>
<div style="background:#fff;border:1px solid #e5e7eb;border-radius:12px;padding:10px">
<h4 style="margin:0;color:#111">🎙️ PTT - T780 Inside Portal</h4>
<button id="pttBtn" style="margin-top:8px;padding:12px 20px;background:#2563eb;color:#fff;border:0;border-radius:8px;font-weight:700;width:100%">🎙️ HOLD TO TRANSMIT</button>
<div id="pttLog" style="font-size:11px;color:#888;margin-top:6px">Ready...</div>
</div>
</div>
</div>
</div>
<script>
let map = L.map('map').setView([-25.6242,28.0038], 16);
let street=L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{attribution:'OSM'});
let satellite=L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',{attribution:'Esri'}).addTo(map);
let topo=L.tileLayer('https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png',{attribution:'Topo'});
let cur=satellite;
document.getElementById('layerSelect').onchange=e=>{map.removeLayer(cur); if(e.target.value=='satellite') cur=satellite.addTo(map); else if(e.target.value=='topo') cur=topo.addTo(map); else cur=street.addTo(map);};
let markers={}; let poly=null;
function loadSOS(){
 fetch('/api/sos-feed').then(r=>r.json()).then(list=>{
  let uniq={}; list.forEach(e=>{if(e.phoneId) uniq[e.phoneId]=e});
  document.getElementById('sosFeed').innerHTML=list.slice(-15).reverse().map(e=>`<div onclick="traceClient('${e.phoneId}')" style="padding:6px;border-bottom:1px solid #eee;cursor:pointer"><b style="color:#e11d48">${e.type||'SOS'}</b> ${e.phoneId}<br><span style="color:#666">${e.time?.slice(11,19)} ${e.lat?e.lat.toFixed(4):''}</span></div>`).join('')||'No SOS yet';
  document.getElementById('clientList').innerHTML=Object.values(uniq).map(e=>`<div onclick="traceClient('${e.phoneId}')" style="padding:8px;border:1px solid #eee;border-radius:8px;margin-bottom:4px;cursor:pointer;background:${e.type?.includes('SOS')?'#fef2f2':'#fff'}"><b>${e.phoneId}</b><br><span style="color:#666">${e.shop||''} ${e.lat?e.lat.toFixed(4)+','+e.lng.toFixed(4):''}</span><br><span style="font-size:10px;color:#2563eb">▶ Trace Live</span></div>`).join('')||'No clients yet - open /clients on phone';
  list.forEach(e=>{if(e.lat && e.lng){ if(!markers[e.phoneId]) markers[e.phoneId]=L.marker([e.lat,e.lng]).addTo(map).bindPopup(e.phoneId+'<br>'+e.type); else markers[e.phoneId].setLatLng([e.lat,e.lng]); }});
 });
}
function traceClient(phoneId){
 document.getElementById('mapTitle').innerText='Tracing: '+phoneId+' - last 20';
 fetch('/api/tracking/'+phoneId).then(r=>r.json()).then(trail=>{
  if(poly) map.removeLayer(poly);
  if(trail.length){
   let latlngs=trail.map(p=>[p.lat,p.lng]).filter(p=>p[0]&&p[1]);
   poly=L.polyline(latlngs,{color:'#2563eb',weight:4}).addTo(map);
   map.fitBounds(poly.getBounds(),{padding:[20,20]});
   document.getElementById('trailBox').innerHTML=trail.slice(-10).reverse().map(e=>`<div>${e.time?.slice(11,19)} ${e.type} ${e.lat?.toFixed(5)}</div>`).join('');
   let last=trail[trail.length-1]; if(last.lat){ if(!markers[phoneId]) markers[phoneId]=L.marker([last.lat,last.lng]).addTo(map); else markers[phoneId].setLatLng([last.lat,last.lng]).openPopup(); }
  } else document.getElementById('trailBox').innerText='No trail - client needs Always-on ON in /clients';
 });
}
setInterval(loadSOS,4000); loadSOS();
const btn=document.getElementById('pttBtn'); btn.onmousedown=()=>{btn.innerText='● TRANSMITTING...';}; btn.onmouseup=()=>{btn.innerText='🎙️ HOLD TO TRANSMIT';};
</script>
"""

AUTH_HTML = NAV + """
<div style="font-family:system-ui;display:flex;justify-content:center;padding:60px 20px;background:#fff;min-height:80vh">
<div style="width:340px;text-align:center">
<h2 style="color:#111">Welcome</h2><p style="color:#666;font-size:13px">Login to your shop</p>
<div style="display:flex;gap:20px;justify-content:center;font-size:13px;margin:16px 0">
<button id="tab-login" onclick="showTab('login')" style="font-weight:700;border:0;background:0;border-bottom:2px solid #2563eb;padding-bottom:4px">Login</button>
<button id="tab-register" onclick="showTab('register')" style="border:0;background:0;color:#666;padding-bottom:4px">Register</button>
</div>
<div id="login-form">
<input id="l_user" placeholder="Username / Email" style="width:100%;padding:10px;margin:6px 0;border:1px solid #ddd;border-radius:6px">
<input id="l_pass" type="password" placeholder="Password" style="width:100%;padding:10px;margin:6px 0;border:1px solid #ddd;border-radius:6px">
<button onclick="doLogin()" style="background:#2563eb;color:#fff;padding:10px;width:100%;border:0;border-radius:6px;margin-top:10px">Login</button>
</div>
<div id="register-form" style="display:none">
<input id="r_name" placeholder="Full Name" style="width:100%;padding:10px;margin:6px 0;border:1px solid #ddd;border-radius:6px">
<input id="r_email" placeholder="Email" style="width:100%;padding:10px;margin:6px 0;border:1px solid #ddd;border-radius:6px">
<input id="r_phone" placeholder="Phone - e.g. 071..." style="width:100%;padding:10px;margin:6px 0;border:1px solid #ddd;border-radius:6px">
<input id="r_pass" type="password" placeholder="Create Password" style="width:100%;padding:10px;margin:6px 0;border:1px solid #ddd;border-radius:6px">
<button onclick="doRegister()" style="background:#000;color:#fff;padding:10px;width:100%;border:0;border-radius:6px;margin-top:10px">Create Account</button>
</div>
<div id="msg" style="font-size:12px;margin-top:10px;color:green"></div>
</div>
</div>
<script>
function showTab(t){
 document.getElementById('login-form').style.display=t=='login'?'block':'none';
 document.getElementById('register-form').style.display=t=='register'?'block':'none';
 document.getElementById('tab-login').style.borderBottom=t=='login'?'2px solid #2563eb':'none';
 document.getElementById('tab-register').style.borderBottom=t=='register'?'2px solid #2563eb':'none';
}
function doLogin(){
 fetch('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({user:document.getElementById('l_user').value})}).then(r=>r.json()).then(d=>{document.getElementById('msg').innerText=d.ok?'Logged in! -> /patrollers':'Not found - Register first'; if(d.ok) setTimeout(()=>location.href='/patrollers',800)});
}
function doRegister(){
 fetch('/api/register',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:document.getElementById('r_name').value,email:document.getElementById('r_email').value,phone:document.getElementById('r_phone').value,pass:document.getElementById('r_pass').value})}).then(r=>r.json()).then(d=>{document.getElementById('msg').innerText=d.ok?'Account created! Login now':d.error; if(d.ok) showTab('login')});
}
if(location.pathname=='/register') showTab('register');
</script>
"""

@app.route("/")
def home(): return render_template_string(HOME_HTML)
@app.route("/shop")
def shop(): return render_template_string(SHOP_HTML)
@app.route("/login")
def login(): return render_template_string(AUTH_HTML)
@app.route("/register")
def reg(): return render_template_string(AUTH_HTML)
@app.route("/patrollers")
def patrollers(): return render_template_string(PATROLLERS_HTML)

@app.route("/api/register", methods=["POST"])
def api_register():
    data=request.get_json() or {}
    db=load_db()
    db["users"].append({**data,"created":datetime.datetime.now().isoformat()})
    save_db(db)
    return jsonify({"ok":True})

@app.route("/api/login", methods=["POST"])
def api_login(): return jsonify({"ok":True})

@app.route("/api/sos", methods=["POST"])
def api_sos():
    data=request.get_json(force=True) or {}
    db=load_db()
    evt={**data,"time":datetime.datetime.now().isoformat()}
    db["locations"].append(evt)
    db["locations"]=db["locations"][-1000:]
    db["sos_events"].append(evt)
    save_db(db)
    return jsonify({"ok":True})

@app.route("/api/sos-feed")
def sos_feed(): return jsonify(load_db()["sos_events"][-100:])

@app.route("/sos")
def sos_page(): return send_from_directory(".", "sos.html")
@app.route("/clients")
@app.route("/client")
def clients_page(): return send_from_directory(".", "clients.html")
@app.route("/manifest.json")
def mf(): return send_from_directory(".", "manifest.json")
@app.route("/sw.js")
def sw(): return send_from_directory(".", "sw.js")
@app.route("/api/tracking/<phoneId>")
def trail(phoneId):
    db=load_db()
    return jsonify([l for l in db["locations"] if l.get("phoneId")==phoneId][-20:])

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
