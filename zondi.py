"""
Zondi API v3
PTT Radio + SOS + Live Patrol + Developer Portal Approval

Install:
    pip install flask flask-cors flask-socketio eventlet

Run locally:
    python zondi_v3.py

Render:
    Use the Render PORT environment variable.
"""

from flask import (
    Flask,
    request,
    jsonify,
    send_from_directory,
    session,
    redirect,
)
from flask_cors import CORS
from flask_socketio import (
    SocketIO,
    emit,
    join_room,
    leave_room,
)
import json
import os
import threading
from datetime import datetime, timedelta
from werkzeug.security import (
    generate_password_hash,
    check_password_hash,
)
import uuid


# ============================================================
# APP CONFIG
# ============================================================

app = Flask(__name__, static_folder=".")


# IMPORTANT:
# Set SECRET_KEY in Render.
# Example:
# SECRET_KEY = Generate from Render
#
# Never change SECRET_KEY while you expect existing sessions
# to remain valid.
app.config.update(
    SECRET_KEY=os.environ.get(
        "SECRET_KEY",
        "zondi-secret-change-me",
    ),

    # Developer session cookie
    SESSION_COOKIE_NAME="zondi_dev_session",

    # JavaScript cannot directly read the cookie
    SESSION_COOKIE_HTTPONLY=True,

    # Works correctly for your same-site Render app
    SESSION_COOKIE_SAMESITE="Lax",

    # Render runs over HTTPS.
    # For local HTTP testing, set:
    # SESSION_COOKIE_SECURE=false
    SESSION_COOKIE_SECURE=(
        os.environ.get(
            "SESSION_COOKIE_SECURE",
            "true",
        ).lower()
        == "true"
    ),

    # 8 hour developer session
    PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
)


# API CORS
CORS(
    app,
    resources={
        r"/api/*": {
            "origins": "*",
        }
    },
)


# Socket.IO
socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode="eventlet",
    logger=False,
)


# ============================================================
# DATA FILES
# ============================================================

FILES = {
    "sos": "sos_feed.json",
    "users": "users.json",
    "patrollers": "patrollers_live.json",
    "voice": "radio_talk.json",
}


file_lock = threading.Lock()


# ============================================================
# RADIO STATE
# ============================================================

# channel -> {
#     "email": "...",
#     "started_at": datetime(...)
# }
active_talkers = {}

channel_lock = threading.Lock()


# ============================================================
# JSON STORAGE
# ============================================================

def load_json(filename):
    """
    Safely load a JSON list.
    """
    if not os.path.exists(filename):
        return []

    try:
        with file_lock:
            with open(
                filename,
                "r",
                encoding="utf-8",
            ) as fh:
                data = json.load(fh)

                return (
                    data
                    if isinstance(data, list)
                    else []
                )

    except Exception:
        return []


def save_json(filename, data):
    """
    Atomic JSON save.
    """
    with file_lock:

        temp_file = filename + ".tmp"

        with open(
            temp_file,
            "w",
            encoding="utf-8",
        ) as fh:

            json.dump(
                data,
                fh,
                indent=2,
                ensure_ascii=False,
            )

        os.replace(
            temp_file,
            filename,
        )


def init_files():
    """
    Create empty JSON files if they don't exist.
    """
    for filename in FILES.values():

        if not os.path.exists(filename):
            save_json(
                filename,
                [],
            )


# ============================================================
# USER HELPERS
# ============================================================

def sanitize_user(user):
    """
    Never send password hashes to the frontend.
    """
    return {
        key: value
        for key, value in user.items()
        if key != "password"
    }


def find_user_by_email(email):
    """
    Find a user by email.
    """
    email = (
        str(email or "")
        .lower()
        .strip()
    )

    users = load_json(
        FILES["users"]
    )

    return next(
        (
            user
            for user in users
            if user.get("email", "").lower()
            == email
        ),
        None,
    )


# ============================================================
# PAGES
# ============================================================

@app.route("/")
def home():
    """
    Main Zondi entry page.
    """
    if os.path.exists("login.html"):
        return send_from_directory(
            ".",
            "login.html",
        )

    return jsonify(
        {
            "name": "Zondi API v3",
            "status": "running",
        }
    )


# Every frontend page is served from the same Flask app.
PAGE_ROUTES = [
    "/login",
    "/login.html",
    "/register",
    "/register.html",
    "/clients",
    "/clients.html",
    "/patrollers",
    "/patrol",
    "/patrollers.html",
    "/patrol.html",
    "/admin",
    "/admin.html",
    "/dev",
    "/dev.html",
    "/radio",
    "/radio.html",
]


for route in PAGE_ROUTES:

    @app.route(
        route,
        endpoint=route,
    )
    def page_handler(route=route):

        # Convert:
        # /login -> login.html
        # /dev -> dev.html
        # /patrol -> patrol.html
        filename = (
            route
            .strip("/")
            .split(".")[0]
            + ".html"
        )


        # ====================================================
        # DEVELOPER PORTAL PROTECTION
        # ====================================================

        if route in [
            "/dev",
            "/dev.html",
            "/admin",
            "/admin.html",
        ]:

            authenticated = (
                session.get(
                    "dev_authenticated"
                )
                is True
            )

            if not authenticated:

                return redirect(
                    "/login?dev=1"
                )


        # ====================================================
        # DEV / ADMIN FILE MAPPING
        # ====================================================

        if filename in [
            "admin.html",
            "dev.html",
        ]:

            if os.path.exists(
                "dev_portal.html"
            ):

                return send_from_directory(
                    ".",
                    "dev_portal.html",
                )


            if os.path.exists(
                "admin.html"
            ):

                return send_from_directory(
                    ".",
                    "admin.html",
                )


        # ====================================================
        # NORMAL PAGE
        # ====================================================

        if os.path.exists(filename):

            return send_from_directory(
                ".",
                filename,
            )


        # ====================================================
        # FALLBACK
        # ====================================================

        base = filename.split("/")[0]

        if os.path.exists(base):

            return send_from_directory(
                ".",
                base,
            )


        if os.path.exists(
            "login.html"
        ):

            return send_from_directory(
                ".",
                "login.html",
            )


        return (
            f"Missing {filename}",
            404,
        )


# ============================================================
# AUTH — REGISTRATION
# ============================================================

@app.route(
    "/api/signup",
    methods=["POST"],
)
@app.route(
    "/api/register",
    methods=["POST"],
)
def api_register():

    data = (
        request.get_json(
            silent=True
        )
        or {}
    )


    email = (
        str(data.get("email", ""))
        .lower()
        .strip()
    )

    password = data.get(
        "password",
        "",
    )

    requested_role = (
        str(
            data.get(
                "role",
                "client",
            )
        )
        .lower()
        .strip()
    )


    # Only allow public registration
    # as client or patroller.
    if requested_role not in [
        "client",
        "patroller",
    ]:

        requested_role = "client"


    if not email or not password:

        return jsonify(
            {
                "error":
                    "Email and password required"
            }
        ), 400


    if len(password) < 6:

        return jsonify(
            {
                "error":
                    "Password min 6 chars"
            }
        ), 400


    users = load_json(
        FILES["users"]
    )


    # Duplicate account check
    if any(
        user.get(
            "email",
            "",
        ).lower()
        == email
        for user in users
    ):

        return jsonify(
            {
                "error":
                    "Email already registered"
            }
        ), 400


    now = datetime.now().isoformat()


    new_user = {
        "id":
            str(uuid.uuid4()),

        "email":
            email,

        "password":
            generate_password_hash(
                password
            ),

        "role":
            requested_role,

        "name":
            str(
                data.get(
                    "name",
                    "",
                )
            ).strip(),

        "phone":
            str(
                data.get(
                    "phone",
                    "",
                )
            ).strip(),

        "address":
            str(
                data.get(
                    "address",
                    "",
                )
            ).strip(),

        # Clients can log in immediately.
        # Patrollers wait for developer approval.
        "status":
            (
                "approved"
                if requested_role == "client"
                else "pending"
            ),

        "created_at":
            now,

        "approved_at":
            (
                now
                if requested_role == "client"
                else None
            ),
    }


    users.append(
        new_user
    )

    save_json(
        FILES["users"],
        users,
    )


    return jsonify(
        {
            "ok": True,

            "user":
                sanitize_user(
                    new_user
                ),

            "message":
                (
                    "Patroller account pending approval by admin"
                    if requested_role == "patroller"
                    else
                    "Registered"
                ),
        }
    ), 201


# ============================================================
# AUTH — LOGIN
# ============================================================

@app.route(
    "/api/login",
    methods=["POST"],
)
def api_login():

    data = (
        request.get_json(
            silent=True
        )
        or {}
    )


    email = (
        str(
            data.get(
                "email",
                "",
            )
        )
        .lower()
        .strip()
    )

    password = data.get(
        "password",
        "",
    )


    users = load_json(
        FILES["users"]
    )


    user = next(
        (
            item
            for item in users
            if item.get(
                "email",
                "",
            ).lower()
            == email
        ),
        None,
    )


    # Wrong user/password
    if not user:

        return jsonify(
            {
                "error":
                    "Wrong email or password"
            }
        ), 401


    stored_password = user.get(
        "password",
        "",
    )


    valid_password = False


    # Modern hashed password
    try:

        valid_password = check_password_hash(
            stored_password,
            password,
        )

    except Exception:

        valid_password = False


    # Legacy plaintext migration
    if not valid_password:

        if stored_password == password:

            user["password"] = (
                generate_password_hash(
                    password
                )
            )

            save_json(
                FILES["users"],
                users,
            )

            valid_password = True


    if not valid_password:

        return jsonify(
            {
                "error":
                    "Wrong email or password"
            }
        ), 401


    # ========================================================
    # PATROLLER APPROVAL CHECK
    # ========================================================

    if (
        user.get("role")
        == "patroller"
    ):

        if (
            user.get("status")
            != "approved"
        ):

            return jsonify(
                {
                    "error":
                        (
                            f"Account "
                            f"{user.get('status', 'pending')}. "
                            f"Wait for admin approval"
                        ),

                    "status":
                        user.get(
                            "status",
                            "pending",
                        ),
                }
            ), 403


    return jsonify(
        sanitize_user(
            user
        )
    )


# ============================================================
# DEVELOPER PORTAL AUTH
# ============================================================

@app.route(
    "/api/dev-login",
    methods=["POST"],
)
def dev_login():

    data = (
        request.get_json(
            silent=True
        )
        or {}
    )


    password = str(
        data.get(
            "password",
            "",
        )
    )


    expected_password = os.environ.get(
        "DEV_PORTAL_PASSWORD",
        "",
    )


    # Password must exist in Render
    if not expected_password:

        return jsonify(
            {
                "error":
                    (
                        "Developer portal password "
                        "is not configured on the server"
                    )
            }
        ), 503


    # Wrong developer password
    if password != expected_password:

        session.clear()

        return jsonify(
            {
                "error":
                    "Incorrect developer password"
            }
        ), 401


    # ========================================================
    # IMPORTANT SESSION CREATION
    # ========================================================

    # Clear any old/invalid session data.
    session.clear()

    # Create permanent Flask session.
    session.permanent = True

    # Authentication flag.
    session["dev_authenticated"] = True

    # Useful for debugging/auditing.
    session["dev_login_at"] = (
        datetime.now().isoformat()
    )

    # Tell Flask that the session changed.
    session.modified = True


    return jsonify(
        {
            "ok":
                True,

            "authenticated":
                True,

            "redirect":
                "/dev",
        }
    )


@app.route(
    "/api/dev-status",
    methods=["GET"],
)
def dev_status():

    authenticated = (
        session.get(
            "dev_authenticated"
        )
        is True
    )


    return jsonify(
        {
            "authenticated":
                authenticated,

            "login_at":
                session.get(
                    "dev_login_at"
                ),
        }
    )


@app.route(
    "/api/dev-logout",
    methods=["POST"],
)
def dev_logout():

    session.clear()

    return jsonify(
        {
            "ok":
                True
        }
    )


def require_dev_auth():
    """
    Return an error response if
    the Developer Portal session is missing.
    """

    if (
        session.get(
            "dev_authenticated"
        )
        is not True
    ):

        return jsonify(
            {
                "error":
                    "developer authentication required"
            }
        ), 401


    return None


# ============================================================
# DEVELOPER PORTAL — PATROLLER MANAGEMENT
# ============================================================

@app.route(
    "/api/admin/pending",
    methods=["GET"],
)
def admin_pending():

    auth_error = require_dev_auth()

    if auth_error:
        return auth_error


    users = load_json(
        FILES["users"]
    )


    pending = [
        sanitize_user(user)
        for user in users
        if (
            user.get("role")
            == "patroller"
            and
            user.get("status")
            == "pending"
        )
    ]


    all_patrollers = [
        sanitize_user(user)
        for user in users
        if user.get("role")
        == "patroller"
    ]


    return jsonify(
        {
            "pending":
                pending,

            "all_patrollers":
                all_patrollers,

            "counts":
                {
                    "pending":
                        len(pending),

                    "all":
                        len(all_patrollers),

                    "approved":
                        sum(
                            1
                            for user in all_patrollers
                            if user.get(
                                "status"
                            )
                            == "approved"
                        ),

                    "rejected":
                        sum(
                            1
                            for user in all_patrollers
                            if user.get(
                                "status"
                            )
                            == "rejected"
                        ),
                },
        }
    )


@app.route(
    "/api/admin/approve",
    methods=["POST"],
)
def admin_approve():

    auth_error = require_dev_auth()

    if auth_error:
        return auth_error


    data = (
        request.get_json(
            silent=True
        )
        or {}
    )


    # New portal uses email.
    # We also accept username for backward compatibility.
    email = (
        str(
            data.get(
                "email",
                "",
            )
        )
        .lower()
        .strip()
    )

    username = (
        str(
            data.get(
                "username",
                "",
            )
        )
        .strip()
    )


    action = (
        str(
            data.get(
                "action",
                "approve",
            )
        )
        .lower()
        .strip()
    )


    allowed_actions = {
        "approve",
        "reject",
        "revoke",
    }


    if action not in allowed_actions:

        return jsonify(
            {
                "error":
                    "Invalid action"
            }
        ), 400


    users = load_json(
        FILES["users"]
    )


    found = False

    matched_user = None


    for user in users:

        if (
            user.get(
                "role"
            )
            != "patroller"
        ):
            continue


        user_email = (
            str(
                user.get(
                    "email",
                    "",
                )
            )
            .lower()
            .strip()
        )

        user_name = (
            str(
                user.get(
                    "name",
                    "",
                )
            )
            .strip()
        )


        matches_email = (
            bool(email)
            and user_email == email
        )

        matches_username = (
            bool(username)
            and user_name.lower()
            == username.lower()
        )


        if not (
            matches_email
            or
            matches_username
        ):
            continue


        found = True
        matched_user = user


        # ==============================================
        # APPROVE
        # ==============================================

        if action == "approve":

            user["status"] = "approved"

            # Approval does not expire.
            # It remains until explicitly revoked.
            user["approved_at"] = (
                user.get(
                    "approved_at"
                )
                or
                datetime.now().isoformat()
            )

            user.pop(
                "rejected_at",
                None,
            )


        # ==============================================
        # REJECT
        # ==============================================

        elif action == "reject":

            user["status"] = "rejected"

            user["rejected_at"] = (
                datetime.now().isoformat()
            )


        # ==============================================
        # REVOKE
        # ==============================================

        elif action == "revoke":

            user["status"] = "pending"

            user["revoked_at"] = (
                datetime.now().isoformat()
            )


        break


    if not found:

        return jsonify(
            {
                "error":
                    "Patroller not found"
            }
        ), 404


    save_json(
        FILES["users"],
        users,
    )


    return jsonify(
        {
            "ok":
                True,

            "action":
                action,

            "email":
                matched_user.get(
                    "email"
                ),

            "status":
                matched_user.get(
                    "status"
                ),
        }
    )


# ============================================================
# SOS
# ============================================================

@app.route(
    "/api/sos",
    methods=["POST"],
)
def api_sos():

    data = (
        request.get_json(
            silent=True
        )
        or {}
    )


    if not data.get(
        "phoneId"
    ):

        return jsonify(
            {
                "error":
                    "phoneId required"
            }
        ), 400


    data["id"] = str(
        uuid.uuid4()
    )

    data["time"] = (
        datetime.now().isoformat()
    )


    feed = load_json(
        FILES["sos"]
    )

    feed.append(
        data
    )


    # Keep most recent 1000
    if len(feed) > 1000:

        feed = feed[-1000:]


    save_json(
        FILES["sos"],
        feed,
    )


    # Broadcast immediately
    socketio.emit(
        "new_sos",
        data,
        room="patrollers_room",
    )


    return jsonify(
        {
            "ok":
                True,

            "id":
                data["id"],
        }
    )


@app.route(
    "/api/sos-feed",
    methods=["GET"],
)
def api_feed():

    return jsonify(
        load_json(
            FILES["sos"]
        )[-300:]
    )


@app.route(
    "/api/tracking/<phone_id>",
    methods=["GET"],
)
def api_tracking(phone_id):

    feed = load_json(
        FILES["sos"]
    )


    return jsonify(
        [
            item
            for item in feed
            if (
                item.get("phoneId")
                == phone_id
                and
                item.get("lat")
            )
        ][-100:]
    )


# ============================================================
# PATROLLER LOCATION
# ============================================================

@app.route(
    "/api/patroller-ping",
    methods=["POST"],
)
def patroller_ping():

    data = (
        request.get_json(
            silent=True
        )
        or {}
    )


    if not data.get(
        "email"
    ):

        return jsonify(
            {
                "error":
                    "email required"
            }
        ), 400


    email = (
        str(
            data.get(
                "email",
                "",
            )
        )
        .lower()
        .strip()
    )


    # Always use server time.
    data["time"] = (
        datetime.now().isoformat()
    )

    data["email"] = email


    # Only approved patrollers
    users = load_json(
        FILES["users"]
    )


    user = next(
        (
            item
            for item in users
            if (
                item.get(
                    "email",
                    ""
                ).lower()
                == email
                and
                item.get(
                    "role"
                )
                == "patroller"
                and
                item.get(
                    "status"
                )
                == "approved"
            )
        ),
        None,
    )


    if not user:

        return jsonify(
            {
                "error":
                    "Not an approved patroller"
            }
        ), 403


    # Keep useful server-side identity info.
    data["name"] = (
        user.get("name")
        or data.get("name")
        or email
    )


    existing = load_json(
        FILES["patrollers"]
    )


    existing = [
        item
        for item in existing
        if item.get(
            "email"
        ) != email
    ]


    existing.append(
        data
    )


    save_json(
        FILES["patrollers"],
        existing,
    )


    socketio.emit(
        "patroller_update",
        data,
        room="patrollers_room",
    )


    return jsonify(
        {
            "ok":
                True
        }
    )


@app.route(
    "/api/patrollers-live",
    methods=["GET"],
)
def patrollers_live():

    data = load_json(
        FILES["patrollers"]
    )


    cutoff = (
        datetime.now()
        -
        timedelta(
            minutes=5
        )
    )


    fresh = []


    for patroller in data:

        try:

            timestamp = (
                datetime.fromisoformat(
                    patroller.get(
                        "time",
                        "",
                    )
                )
            )


            if timestamp > cutoff:

                fresh.append(
                    patroller
                )

        except Exception:

            pass


    return jsonify(
        fresh
    )


# ============================================================
# SOCKET.IO RADIO
# ============================================================

@socketio.on(
    "join_channel"
)
def handle_join(data):

    data = data or {}


    channel = str(
        data.get(
            "channel",
            "1",
        )
    )


    email = str(
        data.get(
            "email",
            "anonymous",
        )
    )


    join_room(
        f"channel_{channel}"
    )

    join_room(
        "patrollers_room"
    )


    emit(
        "channel_joined",
        {
            "channel":
                channel,

            "email":
                email,
        },
        room=request.sid,
    )


    emit(
        "user_joined_channel",
        {
            "channel":
                channel,

            "email":
                email,
        },
        room=f"channel_{channel}",
        include_self=False,
    )


    print(
        f"{email} joined channel {channel}"
    )


@socketio.on(
    "leave_channel"
)
def handle_leave(data):

    data = data or {}


    channel = str(
        data.get(
            "channel",
            "1",
        )
    )


    email = data.get(
        "email"
    )


    leave_room(
        f"channel_{channel}"
    )


    emit(
        "user_left_channel",
        {
            "channel":
                channel,

            "email":
                email,
        },
        room=f"channel_{channel}",
    )


@socketio.on(
    "ptt_start"
)
def handle_ptt_start(data):

    data = data or {}


    channel = str(
        data.get(
            "channel",
            "1",
        )
    )


    email = str(
        data.get(
            "email",
            "",
        )
    )


    # ========================================================
    # ONLY APPROVED PATROLLERS CAN USE PTT
    # ========================================================

    user = find_user_by_email(
        email
    )


    if not user:

        emit(
            "ptt_denied",
            {
                "reason":
                    "Account not found"
            },
            room=request.sid,
        )

        return


    if (
        user.get("role")
        != "patroller"
        or
        user.get("status")
        != "approved"
    ):

        emit(
            "ptt_denied",
            {
                "reason":
                    "Approved patroller account required"
            },
            room=request.sid,
        )

        return


    with channel_lock:

        current = (
            active_talkers.get(
                channel
            )
        )


        if current:

            elapsed = (
                datetime.now()
                -
                current["started_at"]
            ).total_seconds()


            # Current talker gets up to 30 seconds.
            if elapsed < 30:

                emit(
                    "channel_busy",
                    {
                        "channel":
                            channel,

                        "busy_by":
                            current["email"],
                    },
                    room=request.sid,
                )

                return


            # Expired lock
            active_talkers.pop(
                channel,
                None,
            )


        # Claim channel
        active_talkers[channel] = {
            "email":
                email,

            "started_at":
                datetime.now(),
        }


    emit(
        "ptt_started",
        {
            "channel":
                channel,

            "email":
                email,
        },
        room=f"channel_{channel}",
        include_self=False,
    )


    emit(
        "ptt_granted",
        {
            "channel":
                channel,
        },
        room=request.sid,
    )


@socketio.on(
    "ptt_audio"
)
def handle_ptt_audio(data):

    data = data or {}


    channel = str(
        data.get(
            "channel",
            "1",
        )
    )


    email = str(
        data.get(
            "email",
            "",
        )
    )


    # Verify channel ownership.
    with channel_lock:

        owner = (
            active_talkers.get(
                channel
            )
        )


        if not owner:

            emit(
                "ptt_denied",
                {
                    "reason":
                        "Channel is not currently owned"
                },
                room=request.sid,
            )

            return


        if owner["email"] != email:

            emit(
                "ptt_denied",
                {
                    "reason":
                        "You do not own this channel"
                },
                room=request.sid,
            )

            return


        # Prevent a stale speaker from talking
        # beyond the maximum lock period.
        elapsed = (
            datetime.now()
            -
            owner["started_at"]
        ).total_seconds()


        if elapsed >= 30:

            active_talkers.pop(
                channel,
                None,
            )


            emit(
                "ptt_denied",
                {
                    "reason":
                        "30 second talk limit reached"
                },
                room=request.sid,
            )

            return


    # Broadcast to others.
    emit(
        "audio_chunk",
        data,
        room=f"channel_{channel}",
        include_self=False,
    )


@socketio.on(
    "ptt_end"
)
def handle_ptt_end(data):

    data = data or {}


    channel = str(
        data.get(
            "channel",
            "1",
        )
    )


    email = str(
        data.get(
            "email",
            "",
        )
    )


    with channel_lock:

        owner = (
            active_talkers.get(
                channel
            )
        )


        if (
            owner
            and
            owner["email"]
            == email
        ):

            del active_talkers[
                channel
            ]


    emit(
        "ptt_ended",
        {
            "channel":
                channel,

            "email":
                email,
        },
        room=f"channel_{channel}",
        include_self=False,
    )


    emit(
        "ptt_released",
        {
            "channel":
                channel,
        },
        room=request.sid,
    )


# ============================================================
# TEXT RADIO
# ============================================================

@app.route(
    "/api/radio/talk",
    methods=["POST", "GET"],
)
def radio_http():

    if request.method == "POST":

        data = (
            request.get_json(
                silent=True
            )
            or {}
        )


        data["id"] = str(
            uuid.uuid4()
        )

        data["time"] = (
            datetime.now().isoformat()
        )


        feed = load_json(
            FILES["voice"]
        )


        feed.append(
            data
        )


        if len(feed) > 50:

            feed = feed[-50:]


        save_json(
            FILES["voice"],
            feed,
        )


        socketio.emit(
            "text_message",
            data,
            room=(
                f"channel_"
                f"{data.get('channel', '1')}"
            ),
        )


        return jsonify(
            {
                "ok":
                    True
            }
        )


    # GET
    channel = request.args.get(
        "channel"
    )


    feed = load_json(
        FILES["voice"]
    )[-20:]


    if channel:

        feed = [
            item
            for item in feed
            if str(
                item.get(
                    "channel"
                )
            )
            ==
            str(channel)
        ]


    return jsonify(
        feed
    )


# ============================================================
# START SERVER
# ============================================================

if __name__ == "__main__":

    init_files()


    print(
        "Zondi v3 - T2770 Radio Running"
    )

    print(
        "Developer Portal: "
        "protected by DEV_PORTAL_PASSWORD"
    )

    print(
        "Dev portal: "
        "/dev.html or /admin.html"
    )

    print(
        "Radio: "
        "/radio.html"
    )


    port = int(
        os.environ.get(
            "PORT",
            10000,
        )
    )


    socketio.run(
        app,
        host="0.0.0.0",
        port=port,
        debug=False,
    )
