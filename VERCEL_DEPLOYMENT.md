# Zondi deployment notes

## Important: Render is the full Zondi deployment

Use Render for the production Zondi service because Zondi includes Flask-SocketIO, persistent database storage, live location updates, and WebRTC signaling/PTT control.

Recommended Render settings:

- Build: `pip install -r requirements.txt`
- Start: `gunicorn --worker-class eventlet --workers 1 --bind 0.0.0.0:$PORT zondi:app`
- `DATABASE_URL`: managed PostgreSQL connection string
- `SECRET_KEY`: generated secret
- `DEV_PORTAL_PASSWORD`: private server-side secret
- `CORS_ORIGINS`: your production frontend origin(s), or `*` during initial testing

## Vercel

Vercel can serve the Flask HTTP routes using `zondi.py`, but it is not the recommended host for the full Zondi realtime service. If `DATABASE_URL` is missing on Vercel, the code now falls back to `/tmp/zondi_dev.db` so the HTTP function can boot instead of crashing on a read-only filesystem.

That `/tmp` database is temporary and must **not** be treated as production persistence. Set `DATABASE_URL` to PostgreSQL if Vercel HTTP deployment is being used for testing.

The realtime Socket.IO/WebRTC radio should remain on the Render deployment.
