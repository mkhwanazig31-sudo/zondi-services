"""Import an existing Zondi JSON-file deployment into the v5 database.

Usage:
    export DATABASE_URL='postgresql://USER:PASSWORD@HOST:5432/DATABASE'
    python migrate_json_to_postgres.py /path/to/old/data-directory

This is a one-time migration helper. It does not delete the source JSON files.
"""
import json
import os
import sys
from pathlib import Path

# zondi_v5 reads DATABASE_URL when imported.
import zondi_v5

FILES = {
    "users.json": "users",
    "sos_feed.json": "sos",
    "patrollers_live.json": "patrollers_latest",
    "radio_talk.json": "radio",
    "scans.json": "scans",
    "password_resets.json": "password_resets",
}


def main():
    source = Path(sys.argv[1] if len(sys.argv) > 1 else os.environ.get("ZONDI_OLD_DATA_DIR", "."))
    if not source.exists():
        raise SystemExit(f"Source directory does not exist: {source}")

    zondi_v5.db_init()
    imported = 0

    for filename, collection in FILES.items():
        path = source / filename
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise SystemExit(f"Could not read {path}: {exc}")
        if not isinstance(data, list):
            continue
        # Users use email as the stable key in v5.
        if collection == "users":
            for item in data:
                key = str(item.get("email", "")).strip().lower()
                if key:
                    zondi_v5.upsert_record(collection, key, item)
                    imported += 1
        else:
            for item in data:
                key = str(item.get("id") or item.get("email") or zondi_v5.uuid.uuid4())
                zondi_v5.upsert_record(collection, key, item)
                imported += 1

    # The old location file becomes history plus latest-by-user in v5.
    loc_path = source / "locations.json"
    if loc_path.exists():
        data = json.loads(loc_path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            for item in data:
                zondi_v5.append_record("locations_history", item, max_rows=10000)
                if item.get("user_id"):
                    zondi_v5.upsert_record("locations_latest", item["user_id"], item)
                    imported += 1

    print(f"Imported {imported} records into {zondi_v5.DATABASE_URL}")
    print("Source JSON files were left untouched.")


if __name__ == "__main__":
    main()
