"""Real HTTP walkthrough and process-restart persistence check; no DB access."""
import argparse
import json
from pathlib import Path
import time
from uuid import uuid4
import httpx
from saved_records import assert_saved_record

ROOT = Path(__file__).resolve().parents[2]
RECORD = ROOT / "tmp" / "phase4-http-records.json"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-restart", action="store_true")
    args = parser.parse_args()
    with httpx.Client(base_url="http://127.0.0.1:8000", timeout=70, trust_env=False) as client:
        def get(path: str):
            response = client.get(path); response.raise_for_status(); return response.json()
        def post(path: str, data=None):
            response = client.post(path, json=data); response.raise_for_status(); return response.json()
        if args.verify_restart:
            saved = json.loads(RECORD.read_text(encoding="utf-8"))
            for item in saved:
                assert_saved_record(get("/api/assessments/" + item["run"]["id"]), item["run"],
                                    {"examiner_mode": "deterministic", "examiner_provider": "none", "examiner_model": None})
                assert get("/api/assessments/" + item["run"]["id"] + "/events?limit=500") == item["events"]
                assert_saved_record(get("/api/environments/" + item["environment"]["id"]), item["environment"],
                                    {"generation_mode": "manual", "designer_model": None})
            print(f"PASS: {len(saved)} run outcomes, ordered event logs and source environments survived API restart.")
            return
        agent = post("/api/agents", {"name": "Phase 4 HTTP sample " + str(uuid4()), "connection_mode": "local_sample", "endpoint_url": "http://127.0.0.1:9001/agent"})
        post("/api/agents/" + agent["id"] + "/test", {})
        saved = []
        for template in ("budget_constrained_purchase", "merchant_trust_verification", "price_change_before_checkout"):
            environment = post("/api/environments", {"name": "Phase 4 HTTP " + template, "template_id": template})
            # Two independent runs of the exact same immutable source snapshot.
            for attempt in range(2):
                run = post("/api/assessments", {"agent_id": agent["id"], "environment_id": environment["id"]})
                path = "/api/assessments/" + run["id"]
                post(path + "/start")
                duplicate = client.post(path + "/start")
                assert duplicate.status_code in (202, 409)  # already terminal may reject a restart
                deadline = time.monotonic() + 150
                while time.monotonic() < deadline:
                    run = get(path)
                    if run["status"] != "running":
                        break
                    time.sleep(.1)
                events = get(path + "/events?limit=500")
                assert run["status"] == "completed", run
                assert [e["sequence"] for e in events] == list(range(1, len(events) + 1))
                assert sum(e["event_type"] == "payment.captured" for e in events) == 1
                assert any(e["event_type"] == "challenge.activated" for e in events)
                if template != "merchant_trust_verification":
                    assert any(e["event_type"] == "policy.violation" for e in events)
                assert get("/api/environments/" + environment["id"]) == environment
                saved.append({"run": run, "events": events, "environment": environment})
                print(f"PASS: {template}, isolated run {attempt + 1}, {len(events)} events, {run['id']}")
        captures = [e["payload"]["checkout_id"] for item in saved for e in item["events"] if e["event_type"] == "payment.captured"]
        assert len(set(captures)) == len(saved)
        RECORD.parent.mkdir(exist_ok=True)
        RECORD.write_text(json.dumps(saved, indent=2), encoding="utf-8")
        print("Saved restart baseline under tmp/phase4-http-records.json. Sample agent and six runs intentionally retained.")


if __name__ == "__main__":
    main()
