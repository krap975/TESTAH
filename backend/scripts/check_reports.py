"""Real local HTTP read-only acceptance check. No scoring or payment action URLs."""
import json
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[2]
RUN = "448a13ed-d692-4355-acb3-0a7de6117529"
BASE = "http://127.0.0.1:8000"


def get(path: str) -> dict | list:
    with urlopen(BASE + path, timeout=20) as response:
        assert response.status == 200
        return json.load(response)


def main() -> None:
    prefix = f"/api/assessments/{RUN}/report"
    report = get(prefix)
    result = report["evaluation"]["result"]
    assert result["overall_score"] == 100
    assert result["certification"]["decision"] == "pass"
    assert result["version"] == "commerce-scoring-v1.0.0"
    assert result["assignment"] == "retrospective"
    assert not report["evaluation"]["stale"]
    assert report["evidence_complete"] and report["evidence_total"] == 68
    assert len(report["recovery"]) == 1 and report["recovery"][0]["points"] == 100
    assert report["recommendations"] == []
    payment = report["payments"][0]
    assert payment["total_minor"] == 8000 and payment["currency"] == "USD"
    assert payment["provider"] == "paypal_sandbox" and payment["status"] == "completed"
    assert payment["capture_id"] and payment["authorization_event_ids"] and payment["buyer_approval_event_ids"]
    events = []; after = 0
    while True:
        page = get(prefix + "/events?" + urlencode({"evaluation_id": result["id"], "after_sequence": after, "limit": 7}))
        assert page["evaluation_id"] == result["id"] and page["cutoff_sequence"] == 68
        events.extend(page["events"])
        if page["next_after_sequence"] is None:
            break
        after = page["next_after_sequence"]
    exported = get(prefix + "/export?" + urlencode({"evaluation_id": result["id"]}))
    assert exported["evidence"] == events
    assert exported["evaluation"]["result"] == result
    assert [e["sequence"] for e in events] == list(range(1, 69))
    assert events[29]["event_type"] == "policy.violation"
    assert events[57]["event_type"] == "payment.captured"
    # Refresh the report and listing; neither is an operational assessment read.
    assert get(prefix)["evaluation"]["result"] == result
    listings = get('/api/reports?offset=0&limit=100')
    assert any(row["run_id"] == RUN and row["overall_score"] == 100 for row in listings["items"])
    for route in ("/reports", f"/reports/{RUN}", "/logs?run=" + RUN, "/monitor/" + RUN):
        with urlopen("http://127.0.0.1:5173" + route, timeout=20) as response:
            assert response.status == 200
    output = ROOT / "tmp/phase9-reference-report.json"
    output.write_text(json.dumps(exported, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = {"reference": RUN, "evaluation": result["id"], "score": 100, "certification": "pass",
        "events": len(events), "sandbox_amount_minor": 8000, "currency": "USD", "http_checks_passed": True}
    (ROOT / "tmp/phase9-http-verification.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
