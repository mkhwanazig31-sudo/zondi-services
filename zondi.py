from flask import Flask, request, jsonify, send_from_directory
from datetime import datetime
import json, os

app = Flask(__name__)

DB_FILE = "zondi_db.json"
if not os.path.exists(DB_FILE):
    with open(DB_FILE,"w") as f: json.dump({"locations":[],"sos_events":[]}, f)

def load_db():
    try:
        with open(DB_FILE) as f: return json.load(f)
    except: return {"locations":[],"sos_events":[]}
def save_db(db):
    with open(DB_FILE,"w") as f: json.dump(db,f,indent=2)

@app.route("/api/sos", methods=["POST"])
def api_sos():
    data = request.get_json(force=True) or {}
    db = load_db()
    event = {
        "phoneId": data.get("phoneId","unknown"),
        "shop": data.get("shop","Shop 4B"),
        "lat": data.get("lat"), "lng": data.get("lng"),
        "type": data.get("type","CLIENT_SOS"),
        "time": datetime.now().isoformat()
    }
    db["locations"].append(event)
    db["locations"] = db["locations"][-1000:]
    if "SOS" in event["type"] or "GASP" in event["type"]:
        db["sos_events"].append(event)
        print(f"🚨 SOS {event}")
    save_db(db)
    return jsonify({"ok":True})

@app.route("/api/tracking/<phoneId>")
def trail(phoneId):
    db = load_db()
    return jsonify([l for l in db["locations"] if l["phoneId"]==phoneId][-20:])

# --- FIXED ROUTES: serve both names so never 404 ---
@app.route("/")
def home():
    return '<h3>ZONDI LIVE</h3><a href="/sos">/sos - No login SOS</a><br><a href="/clients">/clients - Dashboard</a><br><a href="/client">/client (alias)</a>'

@app.route("/sos")
def sos():
    return send_from_directory(".", "sos.html")

@app.route("/clients")
def clients():
    return send_from_directory(".", "clients.html")

@app.route("/client")  # alias for your old link
def client_alias():
    return send_from_directory(".", "clients.html")

@app.route("/manifest.json")
def man():
    return send_from_directory(".", "manifest.json")

@app.route("/sw.js")
def sw():
    return send_from_directory(".", "sw.js")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
