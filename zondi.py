# zondi.py - RESTORED ORIGINAL + V9 SOS added
from flask import Flask, request, jsonify, send_from_directory, render_template_string
import os, json, datetime

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

# === YOUR ORIGINAL LANDING - FROM VIDEO ===
HOME_HTML = """
<!DOCTYPE html><html><head><title>Zondi Services</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>body{font-family:system-ui;margin:0;padding:0;background:#fff} .nav{padding:12px 24px;display:flex;justify-content:space-between;font-size:12px;color:#666}
.hero{padding:80px 24px;text-align:center} .hero h1{font-size:28px;font-weight:800} .hero h1 span{color:#2563eb}
.btn{background:#2563eb;color:#fff;padding:10px 20px;border-radius:8px;border:0;font-weight:700;text-decoration:none}
.shop{padding:24px;display:flex;gap:16px;justify-content:center;flex-wrap:wrap}
.card{border:1px solid #eee;border-radius:12px;padding:16px;width:200px;text-align:center}
</style></head><body>
<div class="nav"><span>GA-RANKUWA • SOSHANGUVE • MABOPANE</span><span>Zondi Services</span></div>
<div class="hero">
<p style="font-size:10px;color:#888;letter-spacing:2px">GA-RANKUWA • SOSHANGUVE • MABOPANE</p>
<h1>Security that feels like family<br><span>protects like SAPS.</span></h1>
<p style="color:#666;font-size:14px">No more black screens. Clean, friendly, works offline. Buy protection in<br>our Shop, live online.</p>
<br>
<a href="/shop" class="btn">Go to Shop</a> <a href="/login" style="margin-left:12px;text-decoration:none;color:#333">Login</a>
<br><br>
<div style="display:flex;justify-content:center;gap:40px;font-size:12px;color:#888;margin-top:40px">
<div>✓ Works Offline</div><div>✓ Video Proof Vault</div><div>✓ Own auto SOS</div>
</div>
</div>
</body></html>
"""

SHOP_HTML = """
<!DOCTYPE html><html><head><title>Zondi Shop</title><meta name="viewport" content="width=device-width,initial-scale=1">
<style>body{font-family:system-ui;padding:24px} .cards{display:flex;gap:16px;flex-wrap:wrap} .card{border:1px solid #eee;border-radius:12px;padding:20px;width:220px}
.price{font-size:24px;font-weight:800} .btn{background:#2563eb;color:#fff;padding:8px 16px;border-radius:6px;border:0;width:100%;margin-top:10px}
</style></head><body>
<h2>Zondi Shop</h2><p>Buy security for your shop - works offline</p>
<div class="cards">
<div class="card"><h4>Starter Pack</h4><div class="price">R499</div><button class="btn">Add to Cart</button></div>
<div class="card" style="border-color:#2563eb"><h4>Growth Pack</h4><div style="background:#2563eb;color:#fff;font-size:10px;display:inline-block;padding:2px 6px;border-radius:4px">POPULAR</div><div class="price">R1,499</div><button class="btn">Buy Growth Pack</button></div>
<div class="card"><h4>Enterprise</h4><div class="price">R3,999</div><button class="btn">Buy Enterprise</button></div>
</div>
<br><a href="/">← Home</a> | <a href="/sos">New: /sos Panic Button (No Login)</a>
</body></html>
"""

LOGIN_HTML = """
<!DOCTYPE html><html><head><title>Login - Zondi</title><meta name="viewport" content="width=device-width,initial-scale=1">
<style>body{font-family:system-ui;display:flex;justify-content:center;padding:80px 20px} .box{width:300px;text-align:center}
input{width:100%;padding:10px;margin:6px 0;border:1px solid #ddd;border-radius:6px} .btn{background:#2563eb;color:#fff;padding:10px;width:100%;border:0;border-radius:6px;margin-top:10px}
</style></head><body>
<div class="box"><h2>Welcome</h2><p style="color:#666;font-size:13px">Login to your shop</p>
<div style="display:flex;gap:20px;justify-content:center;font-size:13px;margin:12px 0"><span style="font-weight:700;border-bottom:2px solid #2563eb">Login</span><a href="#" style="text-decoration:none;color:#666">Register</a></div>
<input placeholder="Username / Email"><input type="password" placeholder="Password"><button class="btn">Login</button>
<br><br><a href="/">← Back Home</a>
</div>
</body></html>
"""

@app.route("/")
def home():
    return render_template_string(HOME_HTML)

@app.route("/shop")
def shop():
    return render_template_string(SHOP_HTML)

@app.route("/login")
def login():
    return render_template_string(LOGIN_HTML)

# === NEW FEATURES - DON'T BREAK OLD ===
@app.route("/api/sos", methods=["POST"])
def api_sos():
    data = request.get_json(force=True) or {}
    db = load_db()
    evt = {**data, "time": datetime.datetime.now().isoformat()}
    db["locations"].append(evt)
    db["locations"] = db["locations"][-1000:]
    db["sos_events"].append(evt)
    save_db(db)
    return jsonify({"ok":True})

@app.route("/sos")
def sos_page():
    return send_from_directory(".", "sos.html")

@app.route("/clients")
@app.route("/client")
def clients_page():
    return send_from_directory(".", "clients.html")

@app.route("/manifest.json")
def mf(): return send_from_directory(".", "manifest.json")
@app.route("/sw.js")
def sw(): return send_from_directory(".", "sw.js")

@app.route("/api/tracking/<phoneId>")
def trail(phoneId):
    db = load_db()
    return jsonify([l for l in db["locations"] if l.get("phoneId")==phoneId][-20:])

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
