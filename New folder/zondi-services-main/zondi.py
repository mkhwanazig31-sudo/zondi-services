"""Zondi backend v5

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
  python zondi.py
"""

import os
import threading
import uuid

from sqlalchemy import JSON, DateTime, Integer, String, UniqueConstraint, create_engine, delete, select, update
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column
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
CLIENT_LIVE_WINDOW_SECONDS = int(os.environ.get("CLIENT_LIVE_WINDOW_SECONDS", "120"))


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
# DATABASE STORAGE
# -----------------------------------------------------------------------------
# Production: set DATABASE_URL to a managed PostgreSQL connection string.
# Development: if DATABASE_URL is absent, a local SQLite database is used.
# JSON remains the API format; it is no longer used as Zondi's persistent DB.
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = "postgresql+psycopg://" + DATABASE_URL[len("postgres://"):]
elif DATABASE_URL.startswith("postgresql://") and "+psycopg" not in DATABASE_URL:
    DATABASE_URL = "postgresql+psycopg://" + DATABASE_URL[len("postgresql://"):]
if not DATABASE_URL:
    DATABASE_URL = "sqlite:///zondi_dev.db"

engine_kwargs = {"pool_pre_ping": True}
if DATABASE_URL.startswith("postgresql+"):
    engine_kwargs.update({"pool_size": int(os.environ.get("DB_POOL_SIZE", "10")), "max_overflow": int(os.environ.get("DB_MAX_OVERFLOW", "20"))})
else:
    engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, **engine_kwargs)


class Base(DeclarativeBase):
    pass


class ZondiRecord(Base):
    __tablename__ = "zondi_records"
    __table_args__ = (UniqueConstraint("collection", "record_key", name="uq_zondi_collection_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    collection: Mapped[str] = mapped_column(String(80), index=True)
    record_key: Mapped[str] = mapped_column(String(255), default="", index=True)
    payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


COLLECTIONS = {
    "users": "users",
    "locations": "locations_history",
    "sos": "sos",
    "patrollers": "patrollers_latest",
    "radio": "radio",
    "scans": "scans",
    "password_resets": "password_resets",
}

# Used by the route layer for atomic latest-location writes.
LATEST_LOCATION_COLLECTION = "locations_latest"
LATEST_PATROLLER_COLLECTION = "patrollers_latest"

# Legacy path aliases retained so existing route code and older integrations
# continue to work; these are logical names only, not on-disk database files.
FILES = {
    "users": "users.json",
    "locations": "locations.json",
    "sos": "sos_feed.json",
    "patrollers": "patrollers_live.json",
    "radio": "radio_talk.json",
    "scans": "scans.json",
    "password_resets": "password_resets.json",
}

db_lock = threading.RLock()
channel_lock = threading.RLock()

# channel -> {sid, email, started_at}
active_talkers = {}
# sid -> set(channel)
socket_channels = {}
# channel -> {sid: {email, name}} for WebRTC peer discovery.
channel_members = {}


def db_init():
    Base.metadata.create_all(engine)


def _collection_for_path(path):
    name = os.path.basename(str(path))
    return {
        "users.json": "users",
        "locations.json": "locations_history",
        "sos_feed.json": "sos",
        "patrollers_live.json": "patrollers_latest",
        "radio_talk.json": "radio",
        "scans.json": "scans",
        "password_resets.json": "password_resets",
    }.get(name, name.rsplit(".", 1)[0])


def load_collection(collection):
    with db_lock, Session(engine) as db:
        rows = db.scalars(
            select(ZondiRecord)
            .where(ZondiRecord.collection == collection)
            .order_by(ZondiRecord.created_at.asc(), ZondiRecord.id.asc())
        ).all()
        return [dict(row.payload or {}) for row in rows]


def load_json(path):
    return load_collection(_collection_for_path(path))


def save_collection(collection, data):
    # Compatibility helper for low-frequency collections. High-frequency
    # location updates use atomic upserts below instead of replacing a table.
    now = now_utc()
    with db_lock, Session(engine) as db:
        db.execute(delete(ZondiRecord).where(ZondiRecord.collection == collection))
        for item in data:
            payload = dict(item or {})
            key = str(payload.get("id") or uuid.uuid4())
            db.add(ZondiRecord(collection=collection, record_key=key, payload=payload, created_at=now, updated_at=now))
        db.commit()


def save_json(path, data):
    save_collection(_collection_for_path(path), data)


def upsert_record(collection, key, payload):
    now = now_utc()
    key = str(key)
    with db_lock, Session(engine) as db:
        row = db.scalar(
            select(ZondiRecord).where(
                ZondiRecord.collection == collection,
                ZondiRecord.record_key == key,
            )
        )
        if row:
            row.payload = dict(payload)
            row.updated_at = now
        else:
            db.add(ZondiRecord(collection=collection, record_key=key, payload=dict(payload), created_at=now, updated_at=now))
        db.commit()


def append_record(collection, payload, max_rows=None):
    now = now_utc()
    key = str(payload.get("id") or uuid.uuid4())
    with db_lock, Session(engine) as db:
        db.add(ZondiRecord(collection=collection, record_key=key, payload=dict(payload), created_at=now, updated_at=now))
        db.commit()
        if max_rows:
            ids = db.scalars(
                select(ZondiRecord.id)
                .where(ZondiRecord.collection == collection)
                .order_by(ZondiRecord.created_at.desc(), ZondiRecord.id.desc())
                .offset(max_rows)
            ).all()
            if ids:
                db.execute(delete(ZondiRecord).where(ZondiRecord.id.in_(ids)))
                db.commit()


def get_record(collection, key):
    with db_lock, Session(engine) as db:
        row = db.scalar(select(ZondiRecord).where(ZondiRecord.collection == collection, ZondiRecord.record_key == str(key)))
        return dict(row.payload or {}) if row else None


def delete_record(collection, key):
    with db_lock, Session(engine) as db:
        db.execute(delete(ZondiRecord).where(ZondiRecord.collection == collection, ZondiRecord.record_key == str(key)))
        db.commit()


def init_files():
    # Kept as a compatibility name so older startup scripts do not break.
    db_init()


db_init()

# -----------------------------------------------------------------------------
# AUTH HELPERS
# -----------------------------------------------------------------------------
def sanitize_user(user):
    return {k: v for k, v in user.items() if k not in {"password"}}


def find_user(email):
    email = (email or "").strip().lower()
    if not email:
        return None
    return get_record("users", email)


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
    if os.path.exists(os.path.join(BASE_DIR, "index.html")):
        return send_from_directory(BASE_DIR, "index.html")
    if os.path.exists(os.path.join(BASE_DIR, "login.html")):
        return send_from_directory(BASE_DIR, "login.html")
    return jsonify({"name": "Zondi", "status": "running"})


PAGE_ALIASES = {
    "/login": "login.html",
    "/login.html": "login.html",
    "/register": "register.html",
    "/register.html": "register.html",
    "/dashboard": "dashboard.html",
    "/dashboard.html": "dashboard.html",
    "/forgot-password": "forgot-password.html",
    "/forgot-password.html": "forgot-password.html",
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


@app.route("/<path:path>")
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
    if len(password) < 8:
        return jsonify({"ok": False, "error": "Password must be at least 8 characters"}), 400
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
    upsert_record("users", user["email"], user)

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
        upsert_record("users", user.get("email"), user)
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

    user = find_user(email)
    if not user or user.get("role") != "patroller":
        return jsonify({"ok": False, "error": "Patroller not found"}), 404
    user["status"] = {"approve": "approved", "reject": "rejected", "revoke": "pending"}[action]
    upsert_record("users", email, user)
    return jsonify({"ok": True, "action": action, "email": email})



# -----------------------------------------------------------------------------
# PASSWORD RECOVERY
# -----------------------------------------------------------------------------
@app.route("/api/forgot-password", methods=["POST"])
def forgot_password():
    data = request.get_json(silent=True) or {}
    email = str(data.get("email", "")).strip().lower()

    # Always return the same public response to avoid account enumeration.
    generic = {
        "ok": True,
        "message": "If that email is registered, a protected password-reset request has been created for Developer/Admin review."
    }
    if not email or "@" not in email:
        return jsonify(generic), 200

    user = find_user(email)
    if not user:
        return jsonify(generic), 200

    requests = load_json(FILES["password_resets"])
    requests = [x for x in requests if not (x.get("email") == email and x.get("status") == "pending")]
    requests.append({
        "id": str(uuid.uuid4()),
        "email": email,
        "user_id": user.get("id"),
        "requested_at": iso_now(),
        "status": "pending",
    })
    save_json(FILES["password_resets"], requests[-500:])
    return jsonify(generic), 200


@app.route("/api/admin/password-reset-requests")
@require_dev
def admin_password_reset_requests():
    requests = load_json(FILES["password_resets"])
    return jsonify({"ok": True, "requests": [x for x in requests if x.get("status") == "pending"][-100:]})


@app.route("/api/admin/password-reset", methods=["POST"])
@require_dev
def admin_password_reset():
    data = request.get_json(silent=True) or {}
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))
    if not email or len(password) < 8:
        return jsonify({"ok": False, "error": "Email and a password of at least 8 characters are required"}), 400

    found = find_user(email)
    if not found:
        return jsonify({"ok": False, "error": "Account not found"}), 404

    found["password"] = generate_password_hash(password)
    upsert_record("users", email, found)

    requests = load_json(FILES["password_resets"])
    for item in requests:
        if item.get("email") == email and item.get("status") == "pending":
            item["status"] = "completed"
            item["completed_at"] = iso_now()
    save_json(FILES["password_resets"], requests[-500:])
    return jsonify({"ok": True, "email": email})

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

    # Atomic latest-location record: concurrent phones do not overwrite each
    # other's data. A separate history row is retained for auditing/history.
    upsert_record(LATEST_LOCATION_COLLECTION, subject_id, record)
    append_record("locations_history", record, max_rows=10000)

    # Patrol portal receives live client movement.
    if user.get("role") == "client":
        socketio.emit("client_location_update", record, room="patrollers_room")
    elif user.get("role") == "patroller":
        socketio.emit("patroller_location_update", record, room="patrollers_room")

    return jsonify({"ok": True, "location": record})


@app.route("/api/location/live")
@require_patroller
def location_live(user):
    # Return the most recent stored coordinate for every client. A stale
    # client stays visible on the Patrol map as LAST SEEN instead of disappearing.
    locations = load_collection(LATEST_LOCATION_COLLECTION)
    cutoff = now_utc() - timedelta(seconds=CLIENT_LIVE_WINDOW_SECONDS)
    latest = []

    for record in locations:
        if record.get("role") != "client":
            continue

        timestamp = parse_time(record.get("time"))
        if not timestamp:
            continue

        item = dict(record)
        item["last_seen"] = record.get("time")
        item["live"] = timestamp >= cutoff
        latest.append(item)

    latest.sort(key=lambda x: x.get("last_seen", ""), reverse=True)
    return jsonify(latest)


@app.route("/api/location/<user_id>")
@require_user
def location_history(user, user_id):
    # Clients can inspect themselves; approved patrollers can inspect clients.
    if user.get("role") == "client" and user.get("id") != user_id:
        return jsonify({"ok": False, "error": "Forbidden"}), 403
    if user.get("role") not in {"client", "patroller"}:
        return jsonify({"ok": False, "error": "Forbidden"}), 403

    records = [x for x in load_collection("locations_history") if x.get("user_id") == user_id]
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
    upsert_record(LATEST_PATROLLER_COLLECTION, user.get("id"), record)
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
    append_record("scans", record, max_rows=2000)
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
        append_record("radio", record, max_rows=500)
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
                socketio.emit("ptt_ended", {"channel": channel, "email": owner.get("email"), "sid": sid}, room=f"channel_{channel}")
        for channel, members in list(channel_members.items()):
            if sid in members:
                members.pop(sid, None)
            if not members:
                channel_members.pop(channel, None)
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
    with channel_lock:
        members = channel_members.setdefault(channel, {})
        peers = [dict(info, sid=sid) for sid, info in members.items() if sid != request.sid]
        members[request.sid] = {"email": user.get("email", ""), "name": user.get("name", "")}
    emit("channel_joined", {"channel": channel, "email": user.get("email"), "name": user.get("name", ""), "sid": request.sid})
    emit("radio_peers", {"channel": channel, "peers": peers})
    emit("user_joined_channel", {"channel": channel, "email": user.get("email"), "name": user.get("name", ""), "sid": request.sid}, room=room, include_self=False)


@socketio.on("leave_channel")
def handle_leave(data):
    channel = str((data or {}).get("channel", "1"))
    leave_room(f"channel_{channel}")
    socket_channels.setdefault(request.sid, set()).discard(channel)
    with channel_lock:
        members = channel_members.get(channel, {})
        members.pop(request.sid, None)
        if not members:
            channel_members.pop(channel, None)
    emit("user_left_channel", {"channel": channel, "sid": request.sid}, room=f"channel_{channel}")

    with channel_lock:
        owner = active_talkers.get(channel)
        if owner and owner.get("sid") == request.sid:
            del active_talkers[channel]
            emit("ptt_ended", {"channel": channel, "email": owner.get("email"), "sid": request.sid}, room=f"channel_{channel}")


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

    emit("ptt_started", {"channel": channel, "email": user.get("email"), "name": user.get("name", ""), "sid": request.sid}, room=f"channel_{channel}")
    emit("ptt_granted", {"channel": channel, "sid": request.sid})


@socketio.on("ptt_audio")
def handle_ptt_audio(data):
    # Kept as a compatibility event for older clients, but no longer used by
    # the bundled radio UI. Live microphone media is carried by WebRTC.
    emit("ptt_denied", {"reason": "Legacy audio chunks are disabled; use the WebRTC radio client."})


def _valid_radio_peer(channel, sid):
    return sid in channel_members.get(channel, {})


@socketio.on("webrtc_offer")
def handle_webrtc_offer(data):
    data = data or {}
    user = socket_user_from_auth(data.get("auth", data))
    target = str(data.get("target", ""))
    channel = str(data.get("channel", "1"))
    if not user or not _valid_radio_peer(channel, target):
        emit("webrtc_error", {"reason": "Invalid radio peer or authentication"})
        return
    with channel_lock:
        owner = active_talkers.get(channel)
    if not owner or owner.get("sid") != request.sid:
        emit("webrtc_error", {"reason": "Only the current talker may send an offer"})
        return
    socketio.emit("webrtc_offer", {"channel": channel, "from": request.sid, "name": user.get("name", ""), "email": user.get("email", ""), "description": data.get("description")}, to=target)


@socketio.on("webrtc_answer")
def handle_webrtc_answer(data):
    data = data or {}
    user = socket_user_from_auth(data.get("auth", data))
    target = str(data.get("target", ""))
    channel = str(data.get("channel", "1"))
    if not user or not _valid_radio_peer(channel, target):
        emit("webrtc_error", {"reason": "Invalid radio peer or authentication"})
        return
    with channel_lock:
        owner = active_talkers.get(channel)
    if not owner or owner.get("sid") != target:
        emit("webrtc_error", {"reason": "Answer target is not the current talker"})
        return
    socketio.emit("webrtc_answer", {"channel": channel, "from": request.sid, "description": data.get("description")}, to=target)


@socketio.on("webrtc_ice")
def handle_webrtc_ice(data):
    data = data or {}
    user = socket_user_from_auth(data.get("auth", data))
    target = str(data.get("target", ""))
    channel = str(data.get("channel", "1"))
    if not user or not _valid_radio_peer(channel, target):
        return
    with channel_lock:
        owner = active_talkers.get(channel)
    if not owner or request.sid != owner.get("sid") and target != owner.get("sid"):
        return
    socketio.emit("webrtc_ice", {"channel": channel, "from": request.sid, "candidate": data.get("candidate")}, to=target)


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
# HEALTH
# -----------------------------------------------------------------------------
@app.route("/api/health")
def api_health():
    try:
        with Session(engine) as db:
            db.execute(select(1))
        return jsonify({"ok": True, "service": "zondi", "database": "connected"})
    except Exception:
        return jsonify({"ok": False, "service": "zondi", "database": "unavailable"}), 503


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
