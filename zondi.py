from flask import Flask, request, jsonify, send_from_directory, redirect
from datetime import datetime
import os

app = Flask(__name__)

# Manual CORS - no lib needed
@app.after_request
def after(r):
    r.headers.add('Access-Control-Allow-Origin', '*')
    r.headers.add('Access-Control-Allow-Headers', 'Content-Type')
    r.headers.add('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')
    return r

sos_feed = []
clients_db = {}

@app.route('/')
def home(): return redirect('/login')

@app.route('/login')
def login():
    if os.path.exists('login.html'):
        return send_from_directory('.', 'login.html')
    return """
<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width,initial-scale=1">
<style>body{font-family:system-ui;padding:20px}input{width:100%;padding:14px;margin:8px 0;border-radius:12px;border:1px solid #ddd}button{width:100%;padding:14px;background:#111;color:#fff;border-radius:12px;border:0;font-weight:800}</style></head>
<body><h2>ZONDI Login</h2>
<input id="email" placeholder="Email"><input id="name" placeholder="Name">
<button onclick="let e=email.value.trim();let n=name.value.trim();localStorage.setItem('zondi_auth',JSON.stringify({email:e,name:n}));location.href=e.includes('patrol')||e.includes('admin')?'/patrollers':'/clients'">Continue</button>
</body></html>
"""

@app.route('/clients')
def clients():
    return send_from_directory('.', 'clients.html') if os.path.exists('clients.html') else "Upload clients.html"

@app.route('/patrollers')
@app.route('/patrol')
def patrol():
    return send_from_directory('.', 'patrol.html') if os.path.exists('patrol.html') else "Upload patrol.html"

@app.route('/api/sos', methods=['POST','OPTIONS'])
def api_sos():
    if request.method == 'OPTIONS': return jsonify({"ok":True})
    data = request.json or {}
    try:
        lat = float(data.get('lat') or data.get('latitude') or 0)
        lng = float(data.get('lng') or data.get('longitude') or 0)
        if not lat: return jsonify({"ok":False}),400
        email = data.get('email','unknown')
        entry = {
            "email": email, "name": data.get('name') or email,
            "lat": lat, "lng": lng,
            "address": data.get('address',f"{lat},{lng}"),
            "sos": bool(data.get('sos')), "live": True,
            "time": datetime.now().strftime("%H:%M:%S"),
            "timestamp": datetime.now().isoformat()
        }
        clients_db[email]=entry
        global sos_feed
        sos_feed = [x for x in sos_feed if not (x['email']==email and not x.get('sos'))]
        sos_feed.append(entry)
        if len(sos_feed)>100: sos_feed=sos_feed[-100:]
        print("SAVED:", entry)
        return jsonify({"ok":True})
    except Exception as e:
        return jsonify({"ok":False,"error":str(e)}),500

@app.route('/api/sos-feed')
def feed(): return jsonify(list(reversed(sos_feed)))

@app.route('/api/pins')
def pins(): return jsonify(list(clients_db.values()))

@app.route('/health')
def health(): return jsonify({"ok":True,"feed":len(sos_feed),"clients":len(clients_db)})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT',10000)))
