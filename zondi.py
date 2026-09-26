"""Zondi backend v4

Production-oriented Flask + Socket.IO backend for the Zondi platform.

Portals:
  - Client
  - Patrol
  - Developer/Admin

Core services:
  - Registration/login with patroller approval
  - Client live-location tracking
  - SOS broadcasting
  - Patroller live location
  - Developer approval portal
  - Socket.IO PTT channel control
  - HTTP radio text compatibility endpoint

Important:
  Set DEV_PORTAL_PASSWORD on the server to the private developer password.
  Do not put that password in HTML/JavaScript or commit it to source control.

Install:
  pip install -r requirements.txt

Run locally:
  python zondi_v4.py
"""

import os
import threading
import uuid
from datetime import datetime, timedelta, timezone
from functools import wraps

from flask import Flask, jsonify, redirect, request, send_from_directory, session
from flask_cors import CORS
from flask_socketio import SocketIO, emit, join_room, leave_room
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from werkzeug.security import check_password_hash, generate_password_hash


# -----------------------------------------------------------------------------
# APP / CONFIG
# -----------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__, static_folder=BASE_DIR)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY")
if not app.config["SECRET_KEY"]:
    # Development fallback only. Render/production should always set SECRET_KEY.
    app.config["SECRET_KEY"] = "CHANGE-ME-IN-PRODUCTION"

app.permanent_session_lifetime = timedelta(hours=8)

# CORS is intentionally limited by environment in production. For a first
# deployment, CORS_ORIGINS may be '*' or a comma-separated list of origins.
cors_origins = os.environ.get("CORS_ORIGINS", "*")
CORS(
    app,
    resources={r"/api/*": {"origins": cors_origins}},
    supports_credentials=True,
)

socketio = SocketIO(
    app,
    cors_allowed_origins=cors_origins,
    async_mode=os.environ.get("SOCKETIO_ASYNC_MODE", "eventlet"),
    logger=False,
    engineio_logger=False,
)

DEV_TOKEN_MAX_AGE = 8 * 60 * 60
USER_TOKEN_MAX_AGE = 12 * 60 * 60


def now_utc():
    return datetime.now(timezone.utc)


def iso_now():
    return now_utc().isoformat()


def parse_time(value):
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (TypeError, ValueError):
        return None


# -----------------------------------------------------------------------------
# FILE STORAGE
# -----------------------------------------------------------------------------
# This keeps the current deployment simple. For multiple Render instances,
# move these collections to MongoDB/PostgreSQL because local disk is ephemeral.
DATA_DIR = os.environ.get("ZONDI_DATA_DIR", BASE_DIR)
os.makedirs(DATA_DIR, exist_ok=True)

FILES = {
    "users": os.path.join(DATA_DIR, "users.json"),
    "locations": os.path.join(DATA_DIR, "locations.json"),
    "sos": os.path.join(DATA_DIR, "sos_feed.json"),
    "patrollers": os.path.join(DATA_DIR, "patrollers_live.json"),
    "radio": os.path.join(DATA_DIR, "radio_talk.json"),
    "scans": os.path.join(DATA_DIR, "scans.json"),
}

file_lock = threading.RLock()
channel_lock = threading.RLock()

# channel -> {sid, email, started_at}
active_talkers = {}
# sid -> set(channel)
socket_channels = {}


def load_json(path):
    with file_lock:
        if not os.path.exists(path):
            return []
        try:
            with open(path, "r", encoding="utf-8") as fh:
                value = __import__("json").load(fh)
            return value if isinstance(value, list) else []
        except (OSError, ValueError):
            return []


def save_json(path, data):
    import json

    tmp = f"{path}.tmp"
    with file_lock:
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
        os.replace(tmp, path)


def init_files():
    for path in FILES.values():
        if not os.path.exists(path):
            save_json(path, [])


# -----------------------------------------------------------------------------
# AUTH HELPERS
# -----------------------------------------------------------------------------
def sanitize_user(user):
    return {k: v for k, v in user.items() if k not in {"password"}}


def find_user(email):
    email = (email or "").strip().lower()
    if not email:
        return None
    users = load_json(FILES["users"])
    return next((u for u in users if u.get("email", "").lower() == email), None)


def create_token(scope, subject, max_age):
    serializer = URLSafeTimedSerializer(app.config["SECRET_KEY"], salt=f"zondi-{scope}-v1")
    return serializer.dumps({"scope": scope, "sub": subject, "v": 1}), max_age


def read_token(token, scope, max_age):
    if not token:
        return None
    serializer = URLSafeTimedSerializer(app.config["SECRET_KEY"], salt=f"zondi-{scope}-v1")
    try:
        payload = serializer.loads(token, max_age=max_age)
        if payload.get("scope") != scope:
            return None
        return payload
    except (BadSignature, SignatureExpired, TypeError, ValueError):
        return None


def bearer_token():
    value = request.headers.get("Authorization", "")
    return value[7:].strip() if value.startswith("Bearer ") else ""


def current_user():
    # Session auth
    email = session.get("user_email")
    if email:
        user = find_user(email)
        if user:
            return user

    # Bearer auth
    payload = read_token(bearer_token(), "user", USER_TOKEN_MAX_AGE)
    if payload:
        user = find_user(payload.get("sub"))
        if user:
            return user
    return None


def require_user(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        user = current_user()
        if not user:
            return jsonify({"ok": False, "error": "Authentication required"}), 401
        if user.get("role") == "patroller" and user.get("status") != "approved":
            return jsonify({"ok": False, "error": "Patroller account is not approved"}), 403
        return f(user, *args, **kwargs)

    return wrapper


def require_patroller(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        user = current_user()
        if not user:
            return jsonify({"ok": False, "error": "Authentication required"}), 401
        if user.get("role") != "patroller" or user.get("status") != "approved":
            return jsonify({"ok": False, "error": "Approved patroller access required"}), 403
        return f(user, *args, **kwargs)

    return wrapper


def require_dev_auth():
    if session.get("dev_authenticated") is True:
        return True
    payload = read_token(bearer_token(), "developer", DEV_TOKEN_MAX_AGE)
    return payload is not None


def require_dev(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not require_dev_auth():
            return jsonify({"ok": False, "error": "Developer authentication required"}), 401
        return f(*args, **kwargs)

    return wrapper


# -----------------------------------------------------------------------------
# PAGE ROUTES
# -----------------------------------------------------------------------------
@app.route("/")
def home():
    if os.path.exists(os.path.join(BASE_DIR, "login.html")):
        return send_from_directory(BASE_DIR, "login.html")
    return jsonify({"name": "Zondi", "status": "running"})


PAGE_ALIASES = {
    "/login": "login.html",
    "/login.html": "login.html",
    "/register": "register.html",
    "/register.html": "register.html",
    "/clients": "clients.html",
    "/clients.html": "clients.html",
    "/patrol": "patrol.html",
    "/patrol.html": "patrol.html",
    "/admin": "dev_portal.html",
    "/admin.html": "dev_portal.html",
    "/dev": "dev_portal.html",
    "/dev.html": "dev_portal.html",
    "/radio": "radio.html",
    "/radio.html": "radio.html",
}


@app.route("/health")
def health():
    return jsonify({"ok": True, "service": "zondi", "time": iso_now()})


@app.route("<path:path>")
def static_pages(path):
    route = "/" + path
    filename = PAGE_ALIASES.get(route)
    if filename and os.path.exists(os.path.join(BASE_DIR, filename)):
        return send_from_directory(BASE_DIR, filename)
    if os.path.isfile(os.path.join(BASE_DIR, path)):
        return send_from_directory(BASE_DIR, path)
    return jsonify({"ok": False, "error": "Not found"}), 404


# -----------------------------------------------------------------------------
# REGISTRATION / LOGIN
# -----------------------------------------------------------------------------
@app.route("/api/register", methods=["POST"])
@app.route("/api/signup", methods=["POST"])
def api_register():
    data = request.get_json(silent=True) or {}
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))
    role = str(data.get("role", "client")).strip().lower()

    if role not in {"client", "patroller"}:
        return jsonify({"ok": False, "error": "Public registration supports client or patroller only"}), 400
    if not email or not password:
        return jsonify({"ok": False, "error": "Email and password required"}), 400
    if len(password) < 6:
        return jsonify({"ok": False, "error": "Password must be at least 6 characters"}), 400
    if find_user(email):
        return jsonify({"ok": False, "error": "Email already registered"}), 409

    user = {
        "id": str(uuid.uuid4()),
        "email": email,
        "password": generate_password_hash(password),
        "role": role,
        "name": str(data.get("name", "")).strip(),
        "phone": str(data.get("phone", "")).strip(),
        "status": "approved" if role == "client" else "pending",
        "created_at": iso_now(),
    }
    users = load_json(FILES["users"])
    users.append(user)
    save_json(FILES["users"], users)

    return jsonify({
        "ok": True,
        "user": sanitize_user(user),
        "message": "Registered" if role == "client" else "Patroller account pending developer approval",
    }), 201


@app.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json(silent=True) or {}
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))
    user = find_user(email)

    if not user:
        return jsonify({"ok": False, "error": "Wrong email or password"}), 401

    stored = str(user.get("password", ""))
    valid = False
    try:
        valid = check_password_hash(stored, password)
    except (ValueError, TypeError):
        valid = False

    # Legacy plain-text migration support; replace it immediately with a hash.
    if not valid and stored == password and password:
        user["password"] = generate_password_hash(password)
        users = load_json(FILES["users"])
        for index, item in enumerate(users):
            if item.get("id") == user.get("id"):
                users[index] = user
                break
        save_json(FILES["users"], users)
        valid = True

    if not valid:
        return jsonify({"ok": False, "error": "Wrong email or password"}), 401

    if user.get("role") == "patroller" and user.get("status") != "approved":
        return jsonify({
            "ok": False,
            "error": f"Account {user.get('status', 'pending')}. Wait for developer approval",
            "status": user.get("status", "pending"),
        }), 403

    session.clear()
    session.permanent = True
    session["user_email"] = user["email"]

    token, expires = create_token("user", user["email"], USER_TOKEN_MAX_AGE)
    return jsonify({
        "ok": True,
        "user": sanitize_user(user),
        "token": token,
        "expires_in": expires,
    })


@app.route("/api/logout", methods=["POST"])
def api_logout():
    session.clear()
    return jsonify({"ok": True})


@app.route("/api/me")
@require_user
def api_me(user):
    return jsonify({"ok": True, "user": sanitize_user(user)})


# -----------------------------------------------------------------------------
# DEVELOPER PORTAL
# -----------------------------------------------------------------------------
@app.route("/api/dev-login", methods=["POST"])
def dev_login():
    data = request.get_json(silent=True) or {}
    password = str(data.get("password", ""))

    # Never expose the actual password in source, HTML, logs, or responses.
    expected = os.environ.get("DEV_PORTAL_PASSWORD", "")
    if not expected:
        return jsonify({"ok": False, "error": "Developer portal password is not configured"}), 503
    if password != expected:
        session.clear()
        return jsonify({"ok": False, "error": "Incorrect developer password"}), 401

    session.clear()
    session.permanent = True
    session["dev_authenticated"] = True
    session["dev_login_at"] = iso_now()
    token, expires = create_token("developer", "developer", DEV_TOKEN_MAX_AGE)

    return jsonify({
        "ok": True,
        "authenticated": True,
        "token": token,
        "expires_in": expires,
        "redirect": "/dev",
    })


@app.route("/api/dev-status")
def dev_status():
    authenticated = require_dev_auth()
    return jsonify({
        "ok": True,
        "authenticated": authenticated,
        "login_at": session.get("dev_login_at"),
    })


@app.route("/api/dev-logout", methods=["POST"])
def dev_logout():
    session.clear()
    return jsonify({"ok": True})


@app.route("/api/admin/pending")
@require_dev
def admin_pending():
    users = load_json(FILES["users"])
    pending = [sanitize_user(u) for u in users if u.get("role") == "patroller" and u.get("status") == "pending"]
    all_patrollers = [sanitize_user(u) for u in users if u.get("role") == "patroller"]
    return jsonify({"ok": True, "pending": pending, "all_patrollers": all_patrollers})


@app.route("/api/admin/approve", methods=["POST"])
@require_dev
def admin_approve():
    data = request.get_json(silent=True) or {}
    email = str(data.get("email", "")).strip().lower()
    action = str(data.get("action", "approve")).strip().lower()
    if action not in {"approve", "reject", "revoke"}:
        return jsonify({"ok": False, "error": "Invalid action"}), 400

    users = load_json(FILES["users"])
    found = False
    for user in users:
        if user.get("email", "").lower() == email and user.get("role") == "patroller":
            user["status"] = {"approve": "approved", "reject": "rejected", "revoke": "pending"}[action]
            found = True
            break
    if not found:
        return jsonify({"ok": False, "error": "Patroller not found"}), 404

    save_json(FILES["users"], users)
    return jsonify({"ok": True, "action": action, "email": email})


# -----------------------------------------------------------------------------
# CLIENT LIVE LOCATION
# -----------------------------------------------------------------------------
def validate_coordinates(data):
    try:
        lat = float(data.get("lat"))
        lng = float(data.get("lng", data.get("lon")))
    except (TypeError, ValueError):
        return None
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        return None
    return lat, lng


@app.route("/api/location/update", methods=["POST"])
@require_user
def location_update(user):
    data = request.get_json(silent=True) or {}
    coords = validate_coordinates(data)
    if not coords:
        return jsonify({"ok": False, "error": "Valid lat and lng are required"}), 400

    if user.get("role") == "client":
        subject_id = user.get("id")
    else:
        subject_id = user.get("id")

    record = {
        "id": str(uuid.uuid4()),
        "user_id": subject_id,
        "email": user.get("email"),
        "name": user.get("name", ""),
        "role": user.get("role"),
        "lat": coords[0],
        "lng": coords[1],
        "accuracy": data.get("accuracy"),
        "heading": data.get("heading"),
        "speed": data.get("speed"),
        "time": iso_now(),
    }

    locations = load_json(FILES["locations"])
    locations = [x for x in locations if x.get("user_id") != subject_id]
    locations.append(record)
    # Keep bounded history for simple file storage.
    locations = locations[-2000:]
    save_json(FILES["locations"], locations)

    # Patrol portal receives live client movement.
    if user.get("role") == "client":
        socketio.emit("client_location_update", record, room="patrollers_room")
    elif user.get("role") == "patroller":
        socketio.emit("patroller_location_update", record, room="patrollers_room")

    return jsonify({"ok": True, "location": record})


@app.route("/api/location/live")
@require_patroller
def location_live(user):
    locations = load_json(FILES["locations"])
    cutoff = now_utc() - timedelta(minutes=10)
    latest = []
    for record in locations:
        if record.get("role") != "client":
            continue
        timestamp = parse_time(record.get("time"))
        if timestamp and timestamp >= cutoff:
            latest.append(record)
    return jsonify(latest)


@app.route("/api/location/<user_id>")
@require_user
def location_history(user, user_id):
    # Clients can inspect themselves; approved patrollers can inspect clients.
    if user.get("role") == "client" and user.get("id") != user_id:
        return jsonify({"ok": False, "error": "Forbidden"}), 403
    if user.get("role") not in {"client", "patroller"}:
        return jsonify({"ok": False, "error": "Forbidden"}), 403

    records = [x for x in load_json(FILES["locations"]) if x.get("user_id") == user_id]
    return jsonify(records[-100:])


# -----------------------------------------------------------------------------
# SOS
# -----------------------------------------------------------------------------
@app.route("/api/sos", methods=["POST"])
@require_user
def api_sos(user):
    data = request.get_json(silent=True) or {}
    coords = validate_coordinates(data) if ("lat" in data or "lng" in data or "lon" in data) else None

    event = {
        **data,
        "id": str(uuid.uuid4()),
        "email": user.get("email"),
        "name": user.get("name", ""),
        "user_id": user.get("id"),
        "time": iso_now(),
        "status": "active",
    }
    if coords:
        event["lat"], event["lng"] = coords

    feed = load_json(FILES["sos"])
    feed.append(event)
    save_json(FILES["sos"], feed[-1000:])
    socketio.emit("new_sos", event, room="patrollers_room")
    return jsonify({"ok": True, "id": event["id"]})


@app.route("/api/sos-feed")
@require_patroller
def api_sos_feed(user):
    return jsonify(load_json(FILES["sos"])[-300:])


@app.route("/api/sos/<sos_id>/resolve", methods=["POST"])
@require_patroller
def resolve_sos(user, sos_id):
    feed = load_json(FILES["sos"])
    found = None
    for event in feed:
        if event.get("id") == sos_id:
            event["status"] = "resolved"
            event["resolved_by"] = user.get("email")
            event["resolved_at"] = iso_now()
            found = event
            break
    if not found:
        return jsonify({"ok": False, "error": "SOS not found"}), 404
    save_json(FILES["sos"], feed)
    socketio.emit("sos_resolved", found, room="patrollers_room")
    return jsonify({"ok": True, "sos": found})


# Backward-compatible route: legacy clients used SOS data as tracking.
@app.route("/api/tracking/<phone_id>")
@require_patroller
def api_tracking(user, phone_id):
    feed = load_json(FILES["sos"])
    return jsonify([x for x in feed if x.get("phoneId") == phone_id and x.get("lat")][-100:])


# -----------------------------------------------------------------------------
# PATROLLER LIVE STATUS
# -----------------------------------------------------------------------------
@app.route("/api/patroller-ping", methods=["POST"])
@require_patroller
def patroller_ping(user):
    data = request.get_json(silent=True) or {}
    coords = validate_coordinates(data)
    if not coords:
        return jsonify({"ok": False, "error": "Valid lat and lng are required"}), 400

    record = {
        **data,
        "id": user.get("id"),
        "email": user.get("email"),
        "name": user.get("name", ""),
        "role": "patroller",
        "lat": coords[0],
        "lng": coords[1],
        "time": iso_now(),
    }
    records = [x for x in load_json(FILES["patrollers"]) if x.get("id") != user.get("id")]
    records.append(record)
    save_json(FILES["patrollers"], records[-500:])
    socketio.emit("patroller_update", record, room="patrollers_room")
    return jsonify({"ok": True, "patroller": record})


@app.route("/api/patrollers-live")
@require_patroller
def patrollers_live(user):
    cutoff = now_utc() - timedelta(minutes=5)
    result = []
    for record in load_json(FILES["patrollers"]):
        timestamp = parse_time(record.get("time"))
        if timestamp and timestamp >= cutoff:
            result.append(record)
    return jsonify(result)


# -----------------------------------------------------------------------------
# QR / STICKER CHECK-IN (SECONDARY FEATURE)
# -----------------------------------------------------------------------------
@app.route("/api/scans", methods=["POST"])
@require_patroller
def create_scan(user):
    data = request.get_json(silent=True) or {}
    sticker_id = str(data.get("sticker_id", "")).strip()
    if not sticker_id:
        return jsonify({"ok": False, "error": "sticker_id required"}), 400

    record = {
        "id": str(uuid.uuid4()),
        "sticker_id": sticker_id,
        "patroller_id": user.get("id"),
        "patroller_email": user.get("email"),
        "time": iso_now(),
        "lat": data.get("lat"),
        "lng": data.get("lng"),
        "note": str(data.get("note", "")).strip(),
    }
    scans = load_json(FILES["scans"])
    scans.append(record)
    save_json(FILES["scans"], scans[-2000:])
    return jsonify({"ok": True, "scan": record})


@app.route("/api/scans")
@require_dev
def list_scans():
    return jsonify(load_json(FILES["scans"])[-500:])


# -----------------------------------------------------------------------------
# HTTP RADIO TEXT COMPATIBILITY
# -----------------------------------------------------------------------------
@app.route("/api/radio/talk", methods=["POST", "GET"])
@require_patroller
def radio_http(user):
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        channel = str(data.get("channel", "1"))
        message = str(data.get("message", data.get("text", ""))).strip()
        if not message:
            return jsonify({"ok": False, "error": "message required"}), 400
        record = {
            "id": str(uuid.uuid4()),
            "channel": channel,
            "email": user.get("email"),
            "name": user.get("name", ""),
            "message": message,
            "time": iso_now(),
        }
        feed = load_json(FILES["radio"])
        feed.append(record)
        save_json(FILES["radio"], feed[-500:])
        socketio.emit("text_message", record, room=f"channel_{channel}")
        return jsonify({"ok": True, "message": record})

    channel = request.args.get("channel")
    feed = load_json(FILES["radio"])[-50:]
    if channel is not None:
        feed = [x for x in feed if str(x.get("channel")) == str(channel)]
    return jsonify(feed)


# -----------------------------------------------------------------------------
# SOCKET.IO PTT
# -----------------------------------------------------------------------------
def socket_user_from_auth(data):
    data = data or {}
    token = str(data.get("token", ""))
    payload = read_token(token, "user", USER_TOKEN_MAX_AGE)
    if payload:
        user = find_user(payload.get("sub"))
        if user and user.get("role") == "patroller" and user.get("status") == "approved":
            return user
    return None


@socketio.on("connect")
def socket_connect(auth=None):
    user = socket_user_from_auth(auth)
    if not user:
        return False
    socket_channels[request.sid] = set()
    join_room("patrollers_room")
    emit("connected", {"ok": True, "email": user.get("email"), "name": user.get("name", "")})


@socketio.on("disconnect")
def socket_disconnect():
    sid = request.sid
    with channel_lock:
        for channel, owner in list(active_talkers.items()):
            if owner.get("sid") == sid:
                del active_talkers[channel]
                socketio.emit("ptt_ended", {"channel": channel, "email": owner.get("email")}, room=f"channel_{channel}")
        socket_channels.pop(sid, None)


@socketio.on("join_channel")
def handle_join(data):
    user = socket_user_from_auth((data or {}).get("auth", data or {}))
    if not user:
        emit("error", {"error": "Approved patroller authentication required"})
        return

    channel = str((data or {}).get("channel", "1"))
    room = f"channel_{channel}"
    join_room(room)
    socket_channels.setdefault(request.sid, set()).add(channel)
    emit("channel_joined", {"channel": channel, "email": user.get("email")})
    emit("user_joined_channel", {"channel": channel, "email": user.get("email"), "name": user.get("name", "")}, room=room, include_self=False)


@socketio.on("leave_channel")
def handle_leave(data):
    channel = str((data or {}).get("channel", "1"))
    leave_room(f"channel_{channel}")
    socket_channels.setdefault(request.sid, set()).discard(channel)
    emit("user_left_channel", {"channel": channel}, room=f"channel_{channel}")

    with channel_lock:
        owner = active_talkers.get(channel)
        if owner and owner.get("sid") == request.sid:
            del active_talkers[channel]
            emit("ptt_ended", {"channel": channel, "email": owner.get("email")}, room=f"channel_{channel}")


@socketio.on("ptt_start")
def handle_ptt_start(data):
    data = data or {}
    user = socket_user_from_auth(data.get("auth", data))
    if not user:
        emit("ptt_denied", {"reason": "authentication required"})
        return

    channel = str(data.get("channel", "1"))
    if channel not in socket_channels.get(request.sid, set()):
        emit("ptt_denied", {"reason": "join the channel first", "channel": channel})
        return

    with channel_lock:
        current = active_talkers.get(channel)
        if current:
            age = (now_utc() - current["started_at"]).total_seconds()
            if age < 30:
                emit("channel_busy", {"channel": channel, "busy_by": current["email"]})
                return
            # Stale talker is automatically released after 30 seconds.
            del active_talkers[channel]

        active_talkers[channel] = {
            "sid": request.sid,
            "email": user.get("email"),
            "started_at": now_utc(),
        }

    emit("ptt_started", {"channel": channel, "email": user.get("email"), "name": user.get("name", "")}, room=f"channel_{channel}")
    emit("ptt_granted", {"channel": channel})


@socketio.on("ptt_audio")
def handle_ptt_audio(data):
    data = data or {}
    user = socket_user_from_auth(data.get("auth", data))
    if not user:
        emit("ptt_denied", {"reason": "authentication required"})
        return

    channel = str(data.get("channel", "1"))
    with channel_lock:
        owner = active_talkers.get(channel)
        if not owner or owner.get("sid") != request.sid:
            emit("ptt_denied", {"reason": "not current talker"})
            return

    # The actual WebRTC media path should be used for production audio.
    # This event remains for compatibility/signaling and small audio chunks.
    emit("audio_chunk", {
        "channel": channel,
        "email": user.get("email"),
        "name": user.get("name", ""),
        "audio": data.get("audio"),
    }, room=f"channel_{channel}", include_self=False)


@socketio.on("ptt_end")
def handle_ptt_end(data):
    data = data or {}
    user = socket_user_from_auth(data.get("auth", data))
    if not user:
        emit("ptt_denied", {"reason": "authentication required"})
        return

    channel = str(data.get("channel", "1"))
    released = False
    with channel_lock:
        owner = active_talkers.get(channel)
        if owner and owner.get("sid") == request.sid:
            del active_talkers[channel]
            released = True

    if released:
        emit("ptt_ended", {"channel": channel, "email": user.get("email")}, room=f"channel_{channel}")
        emit("ptt_released", {"channel": channel})


# -----------------------------------------------------------------------------
# ERROR HANDLERS
# -----------------------------------------------------------------------------
@app.errorhandler(404)
def not_found(error):
    if request.path.startswith("/api/"):
        return jsonify({"ok": False, "error": "Not found"}), 404
    return error


@app.errorhandler(500)
def internal_error(error):
    return jsonify({"ok": False, "error": "Internal server error"}), 500


# -----------------------------------------------------------------------------
# STARTUP
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    init_files()
    port = int(os.environ.get("PORT", "10000"))
    print("Zondi backend starting")
    print(f"Port: {port}")
    print("Developer password: configured through DEV_PORTAL_PASSWORD")
    socketio.run(app, host="0.0.0.0", port=port, debug=False)
