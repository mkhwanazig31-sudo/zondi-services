# main.py - ZONDI SERVICES PLATFORM - FULL VERSION
# eTera T780 as a Feature Tab
# Run: pip install flask flask-cors && python main.py
# Open: http://127.0.0.1:5000

from flask import Flask, request, jsonify, render_template_string, send_from_directory
from flask_cors import CORS
import datetime, os, json, base64
from pathlib import Path

app = Flask(__name__)
CORS(app)

# Setup folders
Path("evidence").mkdir(exist_ok=True)
Path("faces").mkdir(exist_ok=True)

class ZondiServices:
    def __init__(self):
        self.devices = {
            "T780-07": {
                "id": "T780-07", "model": "eTera T780-NFC", "status": "ONLINE",
                "battery": 78, "signal": "-73 dBm", "lat": -25.6242, "lng": 28.0038,
                "zone": "Ga-Rankuwa - Zone 4B", "guard": "Alex Davis",
                "nfc_last_tap": None, "sos_count": 0
            }
        }
        self.evidence = self.load_evidence()
        self.registered_faces = {} # guard_name -> face encoding path

    def load_evidence(self):
        try:
            with open("evidence/log.json", "r") as f: return json.load(f)
        except: return []

    def save_evidence_log(self):
        with open("evidence/log.json", "w") as f: json.dump(self.evidence, f, indent=2)

    def add_evidence(self, device_id, lat, lng, video_filename=None):
        entry = {
            "id": f"EV-{len(self.evidence)+1:04d}",
            "device_id": device_id,
            "guard": self.devices[device_id]["guard"],
            "timestamp": datetime.datetime.now().isoformat(),
            "location": {"lat": lat, "lng": lng, "zone": self.devices[device_id]["zone"]},
            "video": video_filename or f"no-video-{datetime.datetime.now().strftime('%H%M%S')}.mp4",
            "status": "Uploaded to Dev",
            "type": "SOS Emergency + 30s Recording"
        }
        self.evidence.append(entry)
        self.devices[device_id]["sos_count"] += 1
        self.save_evidence_log()
        print(f"🚨 EVIDENCE SAVED: {entry['id']} from {device_id} at {lat},{lng}")
        return entry

    def face_auth(self, guard_name, image_data):
        # For demo: if guard has registered face file, accept
        # In production: use face_recognition library to compare encodings
        face_path = f"faces/{guard_name}.json"
        if os.path.exists(face_path):
            return {"match": True, "confidence": 96.4, "guard": guard_name}
        # First time - auto register for demo
        with open(face_path, "w") as f: f.write(json.dumps({"registered": datetime.datetime.now().isoformat()}))
        return {"match": True, "confidence": 98.1, "guard": guard_name, "new_registration": True}

zondi = ZondiServices()

# ============ FRONTEND - ALL TABS ============
HTML = """
<!DOCTYPE html>
<html><head><title>Zondi Services - main.py FULL</title>
<script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-[#050a0f] text-white">
<div class="max-w-7xl mx-auto p-4">
  <div class="flex justify-between items-center border-b border-cyan-900/30 pb-3 mb-4">
    <h1 class="text-2xl font-black text-cyan-400">ZONDI SERVICES <span class="text-xs font-normal text-gray-500">main.py • Python • T780 Feature</span></h1>
    <div class="flex gap-2 text-xs"><span class="bg-green-900/40 text-green-300 px-2 py-1 rounded">● Backend Live</span><span class="bg-cyan-900/40 text-cyan-300 px-2 py-1 rounded">{{dev.battery}}% • 4G</span></div>
  </div>

  <div class="flex gap-2 mb-5">
    <button onclick="tab('t780')" id="b-t780" class="bg-cyan-500 text-black px-4 py-2 rounded font-bold">PTT Devices - T780</button>
    <button onclick="tab('live')" id="b-live" class="bg-gray-800 px-4 py-2 rounded">Live Radio</button>
    <button onclick="tab('evidence')" id="b-evidence" class="bg-gray-800 px-4 py-2 rounded">Evidence Locker ({{ev_count}})</button>
    <button onclick="tab('face')" id="b-face" class="bg-gray-800 px-4 py-2 rounded">Face Auth</button>
  </div>

  <!-- T780 FEATURE TAB -->
  <div id="tab-t780" class="grid lg:grid-cols-3 gap-4">
    <div class="lg:col-span-2 bg-[#0f1a24] border border-cyan-800/30 rounded-xl p-5">
      <div class="flex justify-between"><h2 class="font-bold">eTera {{dev.model}} - {{dev.id}}</h2><span class="text-green-400 text-xs">● {{dev.status}} • {{dev.signal}}</span></div>
      <div class="grid grid-cols-3 gap-2 my-4 text-[10px]">
        <div class="bg-black p-2 rounded border border-gray-800">🛡️ IP68 Water/Dust</div>
        <div class="bg-black p-2 rounded border border-gray-800">🔋 5200mAh Battery</div>
        <div class="bg-black p-2 rounded border border-gray-800">📶 NFC Contactless</div>
        <div class="bg-black p-2 rounded border border-gray-800">📡 4G LTE Cellular</div>
        <div class="bg-black p-2 rounded border border-gray-800">📱 Dual SIM</div>
        <div class="bg-black p-2 rounded border border-gray-800">🔌 M6 Connector</div>
      </div>

      <!-- Face Auth Status -->
      <div id="faceStatus" class="bg-black/60 p-3 rounded mb-3 text-xs border border-yellow-800/30">👤 Face Auth: <span id="faceText" class="text-yellow-300">Not authenticated - Go to Face Auth tab first</span></div>

      <!-- PTT -->
      <button id="ptt" class="w-full py-8 rounded-xl font-black text-xl bg-cyan-500 text-black">🎙️ HOLD TO TALK - PTT</button>

      <div class="grid grid-cols-2 gap-2 mt-3">
        <button onclick="startEmergencyRec()" id="sosBtn" class="py-4 bg-red-900/40 border border-red-700 rounded-xl font-black text-red-300">🆘 SOS - EMERGENCY RECORD (30s)</button>
        <button onclick="sendGPS()" class="py-4 bg-gray-800 rounded-xl font-bold text-sm">📍 Send Live GPS</button>
      </div>

      <div class="mt-3">
        <video id="preview" autoplay muted class="w-full h-40 bg-black rounded hidden"></video>
        <div id="recStatus" class="text-xs text-red-400 mt-1"></div>
      </div>

      <div id="log" class="mt-3 bg-black p-2 rounded h-24 overflow-y-auto text-[11px] text-gray-400 font-mono"></div>
    </div>

    <div class="space-y-3">
      <div class="bg-[#0f1a24] rounded-xl p-4 border border-cyan-800/20">
        <h3 class="font-bold text-sm">📍 Live Tracking</h3>
        <p class="text-xs text-cyan-300">{{dev.zone}}</p>
        <p class="text-[10px] text-gray-500" id="coords">{{dev.lat}}, {{dev.lng}}</p>
        <div class="bg-black h-32 rounded mt-2 flex items-center justify-center text-[10px] text-gray-600">Leaflet Map<br>Ga-Rankuwa</div>
        <div class="text-[10px] mt-2 text-gray-500">Updates every 5s → /api/zondi/location</div>
      </div>
      <div class="bg-[#0f1a24] rounded-xl p-4">
        <h3 class="font-bold text-sm">📁 Dev Evidence View</h3>
        <div class="text-[11px] text-gray-400">SOS videos auto-upload here for developer to see</div>
        <div id="evPreview" class="mt-2 text-xs"></div>
      </div>
      <div class="bg-[#0f1a24] rounded-xl p-4 border border-green-900/30">
        <h3 class="font-bold text-xs">Battery & NFC</h3>
        <div class="w-full bg-gray-800 h-1.5 rounded-full mt-2"><div class="bg-cyan-400 h-1.5 rounded-full" style="width:{{dev.battery}}%"></div></div>
        <div class="text-[10px] text-gray-500 mt-1">78% • ~11h left • Last NFC tap: {{dev.nfc_last_tap or 'Never'}}</div>
      </div>
    </div>
  </div>

  <!-- Face Auth Tab -->
  <div id="tab-face" class="hidden bg-[#0f1a24] rounded-xl p-6">
    <h2 class="font-bold mb-3">👤 Face Recognition Auth - T780 Guard Login</h2>
    <div class="grid md:grid-cols-2 gap-4">
      <div><video id="faceVideo" autoplay class="w-full bg-black rounded h-64"></video><button onclick="startFaceCam()" class="mt-2 w-full bg-gray-800 py-2 rounded">Start Camera</button></div>
      <div class="space-y-3"><input id="guardName" value="Alex Davis" class="w-full bg-black border border-gray-700 p-2 rounded text-sm"><button onclick="registerFace()" class="w-full bg-cyan-600 py-2 rounded font-bold">Register Face (1st time)</button><button onclick="authFace()" class="w-full bg-green-700 py-2 rounded font-bold">Authenticate Face - Unlock T780</button><div id="faceResult" class="bg-black p-3 rounded text-xs h-32 overflow-y-auto"></div></div>
    </div>
  </div>

  <div id="tab-evidence" class="hidden bg-[#0f1a24] rounded-xl p-5"><h2 class="font-bold mb-3">Evidence Locker - Developer Account</h2><div id="evList" class="space-y-2"></div></div>
  <div id="tab-live" class="hidden bg-[#0f1a24] rounded-xl p-10 text-center text-gray-500">Live Radio PTT Channel - All T780 devices can talk here. Feature coming after T780 tab.</div>
</div>

<script>
let faceStream=null, mediaRecorder=null, recordedChunks=[];
function tab(t){document.querySelectorAll('[id^=tab-]').forEach(e=>e.classList.add('hidden'));document.getElementById('tab-'+t).classList.remove('hidden');document.querySelectorAll('[id^=b-]').forEach(e=>e.className='bg-gray-800 px-4 py-2 rounded');document.getElementById('b-'+t).className='bg-cyan-500 text-black px-4 py-2 rounded font-bold'; if(t==='evidence') loadEv();}
