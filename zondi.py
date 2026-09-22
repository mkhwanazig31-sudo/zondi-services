from flask import Flask, request, jsonify, send_from_directory, redirect
from flask_cors import CORS
from datetime import datetime
import os

app = Flask(__name__)
CORS(app)

# --- STORAGE (RAM, auto clears on restart - good for demo) ---
sos_feed = [] # all SOS + live locations - patrol reads this
clients_db = {} # email -> {name, lat, lng, corrected_pin}

# --- ROUTES ---

@app.route('/')
def home():
    return redirect('/login')

@app.route('/login')
def login():
    # If you have login.html in repo, it will serve, else fallback simple
    if os.path.exists('login.html'):
        return send_from_directory('.', 'login.html')
    return """
<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width,initial-scale=1">
<style>body{font-family:system-ui;padding:20px}input{width:100%;padding:14px;margin:8px 0;border-radius:12px;border:1px solid #ddd}button{width:100%;padding:14px;background:#111;color:#fff;border-radius:12px;border:0;font-weight:800}</style></head>
<body><h2>ZONDI Login</h2>
<input id="email" placeholder="Email e.g. mkhwanazig31@gmail.com">
<input id="name" placeholder="Full Name">
<button onclick="go()">Continue</button>
<script>
function go(){
 let e=document.getElementById('email').value.trim();
 let n=document.getElementById('name').value.trim();
 if(!e) return alert('Enter email');
 localStorage.setItem('zondi_auth', JSON.stringify({email:e, name:n||e, shopName:n||e}));
 if(e.toLowerCase().includes('patrol') || e.toLowerCase().includes('admin')) location.href='/patrollers';
 else location.href='/clients';
}
</script></body></html>
"""

@app.route('/clients')
def clients():
    if os.path.exists('clients.html'):
        return send_from_directory('.', 'clients.html')
    return "clients.html not found - upload it"

@app.route('/patrollers')
@app.route('/patrol')
@app.route('/t')
def patrollers():
    if os.path.exists('patrol.html'):
        return send_from_directory('.', 'patrol.html')
    return "patrol.html not found"

@app.route('/shop')
def shop():
    return "<h3 style='font-family:system-ui;padding:20px'>Shop coming soon - back to <a href='/clients'>Client</a></h3>"

# --- API: CLIENT SENDS LOCATION / SOS ---

@app.route('/api/sos', methods=['POST', 'OPTIONS'])
def api_sos():
    data = request.json or {}
    print("SOS IN:", data)

    try:
        lat = data.get('lat') or data.get('latitude')
        lng = data.get('lng') or data.get('longitude')
        if lat is None or lng is None:
            return jsonify({"ok": False, "error": "no lat/lng"}), 400

        lat = float(lat)
        lng = float(lng)
        email = data.get('email', 'unknown')
        name = data.get('name') or data.get('shopName') or email
        is_sos = bool(data.get('sos') or data.get('urgent'))

        entry = {
            "email": email,
            "name": name,
            "shopName": data.get('shopName') or name,
            "lat": lat,
            "lng": lng,
            "address": data.get('address') or f"{lat},{lng}",
            "sos": is_sos,
            "live": True,
            "time": data.get('time') or datetime.now().strftime("%H:%M:%S"),
            "timestamp": datetime.now().isoformat()
        }

        # Update clients_db (last location)
        clients_db[email] = entry

        # Keep only last 50 entries per email to avoid flood, but keep all SOS
        # Remove old live entries from same email
        global sos_feed
        sos_feed = [x for x in sos_feed if not (x['email']==email and not x.get('sos'))]

        sos_feed.append(entry)
        # Keep last 100 total
        if len(sos_feed) > 100:
            sos_feed = sos_feed[-100:]

        return jsonify({"ok": True, "saved": entry})

    except Exception as e:
        print("SOS ERROR:", e)
        return jsonify({"ok": False, "error": str(e)}), 500

# --- API: PATROL READS ---

@app.route('/api/sos-feed')
def api_sos_feed():
    # Return newest first
    return jsonify(list(reversed(sos_feed)))

@app.route('/api/pins')
@app.route('/api/clients')
def api_pins():
    # Return unique clients last location
    return jsonify(list(clients_db.values()))

@app.route('/api/clear', methods=['POST'])
def api_clear():
    global sos_feed
    sos_feed = []
    clients_db.clear()
    return jsonify({"ok": True, "cleared": True})

# --- HEALTH ---
@app.route('/health')
def health():
    return jsonify({"ok": True, "clients": len(clients_db), "feed": len(sos_feed)})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
