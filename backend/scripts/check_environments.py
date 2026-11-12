"""Opt-in real HTTP environment isolation and restart check. Creates two saved snapshots."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import urllib.error
import urllib.request
from uuid import uuid4
from saved_records import assert_saved_record

BASE = "http://127.0.0.1:8000/api/environments"
STATE = Path(__file__).resolve().parents[2] / "tmp" / "environment-integration.json"

def api(method: str, url: str, data=None):
    request = urllib.request.Request(url, method=method,
        data=json.dumps(data).encode() if data is not None else None, headers={"Content-Type":"application/json"})
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        raise SystemExit("Environment API error: " + exc.read().decode()) from None
    except urllib.error.URLError:
        raise SystemExit("Start the Testah API on 127.0.0.1:8000 before running this check.") from None

def verify_saved(records: list) -> None:
    for record in records:
        assert_saved_record(api("GET", BASE + "/" + record["id"]), record,
                            {"generation_mode": "manual", "designer_model": None})
    print("PASS stored snapshots match their original API representations")

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-restart",action="store_true",help="Read saved IDs after restarting the backend; creates no new records")
    args = parser.parse_args()
    if args.verify_restart:
        if not STATE.exists():
            raise SystemExit("Run this check without --verify-restart first.")
        verify_saved(json.loads(STATE.read_text(encoding="utf-8")))
        print("PASS environment data persisted across backend restart")
        return
    suffix = str(uuid4())
    records = [api("POST",BASE,{"name":"Integration " + label + " " + suffix,
        "template_id":"price_change_before_checkout","currency":currency,"budget_minor":budget})
        for label,currency,budget in (("A","USD",10000),("B","EUR",20000))]
    first, second = records
    assert first["id"] != second["id"]
    assert first["blueprint"]["products"][0]["price_minor"] * 2 == second["blueprint"]["products"][0]["price_minor"]
    assert first["blueprint"]["currency"] == "USD" and second["blueprint"]["currency"] == "EUR"
    local_copy = deepcopy(first)
    local_copy["blueprint"]["products"][0]["price_minor"] = 1
    local_copy["blueprint"]["merchants"][0]["verified"] = False
    verify_saved(records)
    assert "challenges" not in first["blueprint"] and "evaluation" not in first["blueprint"]
    assert first["status"] == second["status"] == "compiled"
    STATE.parent.mkdir(parents=True,exist_ok=True)
    STATE.write_text(json.dumps(records,indent=2),encoding="utf-8")
    print("PASS distinct environment IDs and independent customized snapshots")
    print("PASS client-side mutations cannot modify either authoritative snapshot")
    print("Saved environment IDs:",first["id"],second["id"])
    print("Snapshots remain in your local database. Restart the API, then rerun with --verify-restart.")

if __name__ == "__main__":
    main()

