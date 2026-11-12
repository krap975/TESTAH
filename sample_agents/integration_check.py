"""Opt-in local integration check. Requires the API and sample to be running."""
import json
import urllib.error
import urllib.request
from uuid import uuid4

BASE = "http://127.0.0.1:8000/api/agents"

def api(method: str, url: str, data=None):
    request = urllib.request.Request(url, method=method, data=json.dumps(data).encode() if data is not None else None,
                                     headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            raw = response.read()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        print(exc.read().decode())
        raise SystemExit("Integration failed. Check migrations, local sample settings, and running servers.") from None

def main() -> None:
    record = api("POST", BASE, {"name": "Local protocol check " + str(uuid4()), "description": "Temporary integration record.",
                               "endpoint_url": "http://127.0.0.1:9001/agent", "connection_mode": "local_sample"})
    try:
        for kind in ("message", "tool_call", "completed"):
            result = api("POST", BASE + "/" + record["id"] + "/test", {"response_mode": kind})
            assert result["status"] == "connected" and result["response_type"] == kind, result
            print("PASS independent sample exchange:", kind)
        details = api("GET", BASE + "/" + record["id"])
        assert details["last_test_status"] == "connected" and details["last_test_at"]
        print("PASS connection test status persisted")
    finally:
        api("DELETE", BASE + "/" + record["id"])
        print("Temporary integration agent deleted")

if __name__ == "__main__":
    main()

