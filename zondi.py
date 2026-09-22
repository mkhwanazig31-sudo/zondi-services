# zondi.py - V9 Client Safety First
# Run: python zondi.py -> http://localhost:5000

from flask import Flask, request, jsonify, send_from_directory
from datetime import datetime
import json, os

app = Flask(__name__)

# Simple file DB (for kasi - no Postgres needed yet)
DB_FILE = "zondi_db.json"
if not os.path.exists(DB_FILE):
    with open(DB_FILE,"w") as f: json.dump({"locations":[], "shops":{"Shop 4B":{"armed":True, "armed_at":"19:02"}}, "sos_events":[]}, f)

def load_db():
    with open(DB_FILE) as f: return json.load(f)
def save_db(db):
    with open(DB_FILE,"w") as f: json.dump(db,f,indent=2)

# --- NEW: Public SOS API - NO LOGIN NEEDED ---
@app.route("/api/sos", methods=["POST"])
def api_sos():
    data = request.get_json(force=True)
    db = load_db()
    
    event = {
        "phoneId": data.get("phoneId"),
        "shop": data.get("shop","Shop 4B"),
        "lat": data.get("lat"),
        "lng": data.get("lng"),
        "type": data.get("type","CLIENT_SOS"), # CLIENT_SOS, GHOST_TRACK, LAST_GASP, ALWAYS_ON
        "time": datetime.now().isoformat(),
        "battery": data.get("battery")
    }
    db["locations"].append(event)
    # Keep only last 1000 points (save space)
    db["locations"] = db["locations"][-1000:]
    
    if event["type"] in ["CLIENT_SOS","LAST_GASP"]:
        db["sos_events"].append(event)
        # TODO: Send WhatsApp to guards + family here
        print(f"🚨 SOS! {event['shop']} {event['lat']},{event['lng']} Type:{event['type']}")
    
    save_db(db)
    return jsonify({"ok":True, "trail": len(db["locations"])})

@app.route("/api/tracking/<phoneId>")
def tracking_history(phoneId):
    db = load_db()
    trail = [l for l in db["locations"] if l["phoneId"]==phoneId][-20:] # last 20
    return jsonify(trail)

@app.route("/api/shop/arm", methods=["POST"])
def arm_shop():
    db = load_db()
    db["shops"]["Shop 4B"]["armed"] = not db["shops"]["Shop 4B"]["armed"]
    db["shops"]["Shop 4B"]["armed_at"] = datetime.now().strftime("%H:%M")
    save_db(db)
    return jsonify(db["shops"]["Shop 4B"])

# --- Serve PWA files ---
@app.route("/sos")
def sos_page():
    return send_from_directory(".", "sos.html")

@app.route("/client")
def client_page():
    return send_from_directory(".", "client.html")

@app.route("/manifest.json")
def manifest():
    return send_from_directory(".", "manifest.json")

@app.route("/sw.js")
def sw():
    return send_from_directory(".", "sw.js")

@app.route("/")
def home():
    return "<a href='/sos'>/sos - No login SOS</a><br><a href='/client'>/client - Dashboard (login)</a>"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
