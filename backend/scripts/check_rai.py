"""Reproducible real candidate-HTTP workflow, with explicit provider provenance."""
import argparse
import json
from pathlib import Path
import time
from uuid import uuid4
import httpx

ROOT = Path(__file__).resolve().parents[2]
BASELINE = ROOT / "tmp" / "phase5-http-records.json"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-restart", action="store_true")
    parser.add_argument("--require-real-provider", action="store_true", help="Require real Designer and Examiner generation without fallback.")
    args = parser.parse_args()
    with httpx.Client(base_url="http://127.0.0.1:8000", timeout=70, trust_env=False) as client:
        def get(path: str):
            response = client.get(path); response.raise_for_status(); return response.json()
        def post(path: str, data=None):
            response = client.post(path, json=data); response.raise_for_status(); return response.json()
        if args.verify_restart:
            baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
            for path, expected in baseline.items():
                assert get(path) == expected, path
            print("PASS proposal, generation evidence, compiled environment, customer modes, run outcomes and ordered events survived API restart.")
            return
        config = get("/api/rai/configuration")
        if args.require_real_provider:
            assert not config["is_mock"], "Select a real RAI provider before this verification."
        print("Generation provider:", config["provider"], "/", config["model"], "(MOCK: no LLM used)" if config["is_mock"] else "(configured real LLM API)")
        candidate = post("/api/agents", {"name": "Phase 5 HTTP sample " + str(uuid4()),
            "description": "Commerce shopping, merchant verification, budget and price/shipping comparisons using the Testah protocol.",
            "connection_mode": "local_sample", "endpoint_url": "http://127.0.0.1:9001/agent"})
        post("/api/agents/" + candidate["id"] + "/test", {})
        request = {"agent_id": candidate["id"], "request_key": str(uuid4())}
        proposal = post("/api/rai/proposals", request)
        assert post("/api/rai/proposals", request)["id"] == proposal["id"]
        path = "/api/rai/proposals/" + proposal["id"]
        deadline = time.monotonic() + 185
        while time.monotonic() < deadline:
            proposal = get(path)
            if proposal["status"] != "generating": break
            time.sleep(.2)
        assert proposal["status"] == "ready", proposal["validation"]
        assert proposal["validation"]["valid"] and proposal["preview"]
        if args.require_real_provider:
            assert not proposal["is_mock"] and proposal["provider"] == config["provider"]
            assert proposal["model"] == config["model"]
        proposal = post(path + "/compile")
        assert post(path + "/compile") == proposal
        environment_path = "/api/environments/" + proposal["environment_id"]
        environment = get(environment_path)
        baseline = {path: proposal, path + "/events?limit=500": get(path + "/events?limit=500"), environment_path: environment}
        for mode in ("deterministic", "rai"):
            run = post("/api/assessments", {"agent_id": candidate["id"], "environment_id": environment["id"], "examiner_mode": mode})
            run_path = "/api/assessments/" + run["id"]
            post(run_path + "/start")
            deadline = time.monotonic() + 150
            while time.monotonic() < deadline:
                run = get(run_path)
                if run["status"] != "running": break
                time.sleep(.2)
            evidence = get(run_path + "/events?limit=500")
            assert run["status"] == "completed", run
            assert run["examiner_mode"] == mode
            assert sum(event["event_type"] == "payment.captured" for event in evidence) == 1
            assert [event["sequence"] for event in evidence] == list(range(1, len(evidence) + 1))
            assert any(event["event_type"] == "rai.environment.compiled" for event in evidence)
            if mode == "rai":
                assert any(event["event_type"] in {"rai.examiner.message_generated", "rai.examiner.fallback"} for event in evidence)
                if args.require_real_provider:
                    assert run["examiner_provider"] == config["provider"]
                    assert any(event["event_type"] == "rai.examiner.message_generated" and event["payload"]["provider"] == config["provider"] for event in evidence)
                    assert not any(event["event_type"] == "rai.examiner.fallback" for event in evidence), "Examiner used deterministic fallback; real generation was not fully verified."
            assert get(environment_path) == environment
            baseline[run_path] = run; baseline[run_path + "/events?limit=500"] = evidence
            print("PASS", mode, "customer:", run["id"], "—", len(evidence), "events; provider", run["examiner_provider"])
        BASELINE.parent.mkdir(exist_ok=True)
        BASELINE.write_text(json.dumps(baseline, indent=2), encoding="utf-8")
        print("Retained synthetic sample/proposal/environment/two runs. Restart baseline: tmp/phase5-http-records.json")


if __name__ == "__main__":
    main()
