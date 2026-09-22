# zondi.py - Zondi Services Platform V9 FINAL
# Has: T780 PTT tab + Evidence + NEW client SOS home screen + ghost tracking
# Run: python zondi.py

from flask import Flask, request, jsonify, render_template_string, send_from_directory
from flask_cors import CORS
import datetime, os, json

app = Flask(__name__)
CORS(app)

DB_FILE = "zondi_db.json"
if not os.path.exists(DB_FILE):
    with open(DB_FILE,"w") as f: json.dump({"locations":[],"sos_events":[],"evidence":[]}, f)

def load_db():
    try:
        with open(DB_FILE) as f: return json.load(f)
    except: return {"locations":[],"sos_events":[],"evidence":[]}
def save_db(db):
    with open(DB_FILE,"w") as f: json.dump(db,f,indent=2)

class ZondiServices:
    def __init__(self):
        self.devices = {
            "T780-07": {
                "id": "T780-07", "model": "eTera T780-NFC (PTT)", "type": "PTT Radio",
                "status": "ONLINE", "battery": 78, "signal": "-73 dBm",
                "location": {"lat": -25.6242, "lng": 28.0038, "zone": "Ga-Rankuwa - Zone 4B"},
                "guard": "Alex Davis", "sos_active": False
            }
        }

zondi = ZondiServices()

# === ORIGINAL DASHBOARD + NEW CLIENT SOS ===
DASHBOARD_HTML = """
<!DOCTYPE html>
<html><head><title>Zondi Services</title>
<script src="https://cdn.tailwindcss.com"></script></head>
<body class="bg-[#0a0f14] text-white min-h-screen">
<div class="p-4 max-w-7xl mx-auto">
<div class="flex justify-between mb-6 border-b border-gray-800 pb-4">
<h1 class="text-2xl font-bold text-cyan-400">🛡️ Zondi Services <span class="text-sm text-gray-500">V9</span></h1>
<div class="text-xs"><a href="/sos" class="bg-red-600 px-3 py-1 rounded">/sos No-Login Panic</a> <a href="/clients" class="bg-gray-800 px-3 py-1 rounded">Client View</a></div>
</div>

<div class="flex gap-2 mb-6">
<button onclick="setTab('services')" id="t-services" class="px-4 py-2 rounded bg-gray-800">Services</button>
<button onclick="setTab('t780')" id="t-t780" class="px-4 py-2 rounded bg-cyan-500 text-black font-bold">PTT Devices - T780 [FEATURE]</button>
<button onclick="setTab('evidence')" id="t-evidence" class="px-4 py-2 rounded bg-gray-800">Evidence Locker</button>
<button onclick="setTab('client')" id="t-client" class="px-4 py-2 rounded bg-red-900">Client SOS Live Trail</button>
</div>

<div id="tab-t780" class="grid lg:grid-cols-3 gap-4">
<div class="lg:col-span-2 bg-gray-900 border border-cyan-900/50 rounded-xl p-5">
<h2 class="font-bold">eTera T780 - {{dev.id}} - {{dev.guard}}</h2>
<p class="text-xs text-gray-400">{{dev.location.zone}} - {{dev.signal}} - {{dev.battery}}%</p>
<button id="pttBtn" class="w-full py-7 mt-4 rounded-xl font-black text-xl bg-cyan-500 text-black">🎙️ PRESS & HOLD TO TRANSMIT (PTT)</button>
<div class="grid grid-cols-2 gap-2 mt-3">
<button onclick="triggerSOS()" class="py-3 bg-red-900/50 border border-red-700 rounded font-bold">🆘 HOLD SOS 3s - Emergency Rec</button>
<button class="py-3 bg-gray-800 rounded font-bold">👤 Face Auth</button>
</div>
<div id="log" class="mt-3 text-xs bg-black p-2 rounded h-20 overflow-y-auto">System ready...</div>
</div>
<div class="bg-gray-900 rounded-xl p-4">Live Location<br><span class="text-cyan-300 text-xs">{{dev.location.zone}}</span><div class="bg-black h-40 rounded mt-2 flex items-center justify-center text-xs">MAP</div></div>
</div>

<div id="tab-client" class="hidden">
<h2 class="font-bold mb-2">Client SOS - Always-on Trail (last 20)</h2>
<div id="trail" class="bg-black p-3 rounded text-xs">Loading...</div>
</div>

<div id="tab-evidence" class="hidden bg-gray-900 rounded-xl p-5"><h2>Evidence Locker</h2><div id="ev-list" class="text-xs mt-2"></div></div>

</div>
<script>
function setTab(t){
 document.querySelectorAll('[id^=tab-]').forEach(e=>e.classList.add('hidden'));
 document.getElementById('tab-'+t)?.classList.remove('hidden');
 if(t=='client') loadTrail();
 if(t=='evidence') loadEvidence();
}
function triggerSOS(){fetch('/api/sos',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({phoneId:'T780-07',type:'CLIENT_SOS',lat:-25.6242,lng:28.0038})}).then(r=>r.json()).then(d=>document.getElementById('log').innerHTML='SOS SENT '+JSON.stringify(d));}
function loadTrail(){fetch('/api/tracking/T780-07').then(r=>r.json()).then(list=>{document.getElementById('trail').innerHTML=list.map(e=>`<div>${e.time} - ${e.type} - ${e.lat},${e.lng}</div>`).join('')||'No pings yet - turn on tracking in /sos'});}
function loadEvidence(){fetch('/api/evidence').then(r=>r.json()).then(list=>{document.getElementById('ev-list').innerHTML=list.map(e=>`<div>${e.id} ${e.time}</div>`).join('')||'Empty'});}
setTab('t780');
const btn=document.getElementById('pttBtn'); btn.onmousedown=()=>btn.innerText='● TRANSMITTING...'; btn.onmouseup=()=>btn.innerText='🎙️ PRESS & HOLD TO TRANSMIT (PTT)';
</script></body></html>
"""

@app.route("/")
def dashboard():
    return render_template_string(DASHBOARD_HTML, dev=zondi.devices["T780-07"])

@app.route("/api/sos", methods=["POST"])
def api_sos():
    data = request.get_json(force=True) or {}
    db = load_db()
    evt = {**data, "time": datetime.datetime.now().isoformat()}
    db["locations"].append(evt)
    db["locations"] = db["locations"][-1000:]
    db["sos_events"].append(evt)
    save_db(db)
    print(f"🚨 SOS {evt}")
    return jsonify({"ok":True})

@app.route("/api/tracking/<phoneId>")
def trail(phoneId):
    db = load_db()
    return jsonify([l for l in db["locations"] if l.get("phoneId")==phoneId][-20:])

@app.route("/api/evidence")
def ev():
    return jsonify(load_db()["sos_events"])

# Serve PWA files - your repo already has them
@app.route("/sos")
def sos():
    return send_from_directory(".", "sos.html")

@app.route("/clients")
@app.route("/client")
def clients():
    return send_from_directory(".", "clients.html")

@app.route("/manifest.json")
def man(): return send_from_directory(".", "manifest.json")
@app.route("/sw.js")
def sw(): return send_from_directory(".", "sw.js")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
