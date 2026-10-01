# Zondi Protect — Native Client App

This repository contains the Zondi web portals plus the native **Zondi Protect** Client companion.

## Current production backend

Render service:
`https://zondi-radio-1.onrender.com`

The Flask entry point is **`zondi.py`**. Do not rename it to `zondi_v5.py` or `app.py`; the deployment files in this package are aligned to `zondi.py`.

### Render settings

Build command:
```bash
pip install -r requirements.txt
```

Start command:
```bash
gunicorn --worker-class eventlet --workers 1 --bind 0.0.0.0:$PORT zondi:app
```

Recommended Render environment variables:
- `SECRET_KEY` — a long random production secret.
- `DEV_PORTAL_PASSWORD` — private developer portal password; never put this value in source or frontend code.
- `DATABASE_URL` — managed PostgreSQL connection string for production persistence.
- `CORS_ORIGINS` — allowed web/native origins; `*` can be used temporarily during initial testing.

## Web portals

- `/` — Zondi home
- `/login` — login
- `/register` — registration
- `/forgot-password` — protected password-reset request
- `/dashboard` — role dashboard
- `/clients` — Client portal
- `/patrol` — Patrol portal with live client map and PTT radio
- `/radio` — full Patrol radio
- `/dev` — Developer/Admin portal
- `/health` and `/api/health` — health checks

## Radio transport

The bundled radio uses:
- **Socket.IO** for approved-patroller authentication, channel membership, PTT locking, peer discovery and WebRTC signaling.
- **WebRTC** for live microphone audio.
- A Google STUN server for initial peer discovery.

The previous MediaRecorder/300 ms `ptt_audio` chunk path has been removed from the bundled UI. This avoids treating base64 audio chunks as the production voice transport.

## Native Zondi Protect

The native app uses:
- `POST /api/login`
- `POST /api/location/update`
- `POST /api/sos`

Set `EXPO_PUBLIC_ZONDI_API_URL` if the backend hostname changes.

Create the Expo project with:
```bash
npx create-expo-app@latest zondi-protect
cd zondi-protect
npx expo install expo-location expo-task-manager expo-secure-store expo-linking expo-intent-launcher expo-image expo-status-bar
```

Replace the generated `App.js` and `app.json` with the versions in this repository and copy `assets/zondi-logo.png` into the native project's `assets/` directory.

Background location requires a native development/production build rather than Expo Go.

## Database migration

The migration helper imports the actual `zondi.py` module and preserves the source JSON files. Run it with:
```bash
export DATABASE_URL='postgresql://USER:PASSWORD@HOST:5432/DATABASE'
python migrate_json_to_postgres.py /path/to/old/data-directory
```

## Vercel note

`vercel.json` is aligned to `zondi.py` for HTTP deployment compatibility. **Use Render for the production Zondi service**, because Socket.IO/WebRTC signaling and long-lived realtime connections are part of the Patrol radio design.
