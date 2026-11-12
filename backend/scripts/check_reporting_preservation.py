"""Read-only whole-table baseline for Phase 9; never prints stored row contents."""
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.core.config import Settings
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[2]
BASELINE = ROOT / "tmp/phase9-preservation-baseline.json"
RESULT = ROOT / "tmp/phase9-preservation-result.json"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    url = make_url(Settings().database_url)
    if url.get_backend_name() != "sqlite":
        raise SystemExit("This local verification helper supports SQLite only.")
    path = Path(url.database)
    if not path.is_absolute():
        path = ROOT / "backend" / path
    with sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True) as db:
        db.execute("BEGIN")
        tables = [row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        checksums = {}
        for table in tables:
            quoted = '"' + table.replace('"', '""') + '"'
            rows = sorted(json.dumps(list(row), sort_keys=True, ensure_ascii=True) for row in db.execute("SELECT * FROM " + quoted))
            checksums[table] = {"rows": len(rows), "sha256": hashlib.sha256("\n".join(rows).encode()).hexdigest()}
        checksums["architecture.md"] = hashlib.sha256((ROOT / "docs/architecture.md").read_bytes()).hexdigest()
        if not args.verify:
            if BASELINE.exists():
                raise SystemExit("Baseline already exists; refusing to overwrite it.")
            BASELINE.parent.mkdir(exist_ok=True)
            with sqlite3.connect(ROOT / "tmp/phase9-before.db") as backup:
                db.backup(backup)
            BASELINE.write_text(json.dumps(checksums, indent=2), encoding="utf-8")
            print("Saved whole-table hashes and a local SQLite backup.")
        else:
            original = json.loads(BASELINE.read_text(encoding="utf-8"))
            changes = [name for name in original.keys() | checksums.keys() if original.get(name) != checksums.get(name)]
            RESULT.write_text(json.dumps({"preserved": not changes, "changed": changes, "tables": checksums}, indent=2), encoding="utf-8")
            print(json.dumps({"preserved": not changes, "changed": changes}))
            if changes:
                raise SystemExit(1)


if __name__ == "__main__":
    main()
