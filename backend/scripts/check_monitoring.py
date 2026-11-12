"""Real local HTTP/SSE verification. Requires the API and the documented standalone sample."""
import argparse
import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from time import monotonic
from uuid import uuid4
import httpx

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
sys.path.insert(0, str(BACKEND))
from app.core.config import Settings

BASELINE = ROOT / "tmp" / "phase6-http-records.json"


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-restart", action="store_true")
    arguments = parser.parse_args()
    settings = Settings()
    token = settings.monitor_token.get_secret_value()
    if not token:
        raise SystemExit("Configure the separate monitoring token and restart the API first.")
    headers = {"Authorization": "Bearer " + token, "Accept": "text/event-stream"}
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8000", trust_env=False, timeout=httpx.Timeout(15, read=45)) as client:
        async def get(path: str):
            response = await client.get(path); response.raise_for_status(); return response.json()
        async def post(path: str, data=None):
            response = await client.post(path, json=data); response.raise_for_status(); return response.json()
        if arguments.verify_restart:
            baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
            for path, value in baseline["records"].items():
                assert await get(path) == value, path
            print("PASS historical assessment, ordered evidence and source environment survived restart; no execution replayed.")
            return
        candidate = await post("/api/agents", {"name": "Phase 6 HTTP sample " + str(uuid4()),
            "description": "Synthetic commerce shopping with budget, merchant and price comparisons.",
            "connection_mode": "local_sample", "endpoint_url": "http://127.0.0.1:9001/agent"})
        await post("/api/agents/" + candidate["id"] + "/test", {})
        environment = await post("/api/environments", {"name": "Phase 6 streaming scenario", "template_id": "price_change_before_checkout"})
        environment_path = "/api/environments/" + environment["id"]
        before = await get(environment_path)
        run = await post("/api/assessments", {"agent_id": candidate["id"], "environment_id": environment["id"], "examiner_mode": "deterministic"})
        path = "/api/assessments/" + run["id"]
        first_ready = asyncio.Event(); second_ready = asyncio.Event()
        first_events = []; second_events = []; latencies = []; resumed = False

        async def collect(target: list, ready: asyncio.Event | None = None, stop_after: int | None = None, after_id: str | None = None, measure_latency: bool = True):
            fields = {}; payload = []
            async with client.stream("GET", path + "/stream?after_sequence=0", headers={**headers, **({"Last-Event-ID": after_id} if after_id else {})}) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line == "":
                        if payload:
                            data = json.loads("\n".join(payload)); kind = fields.get("event")
                            if kind == "snapshot" and ready and data["run"]["status"] == "created": ready.set()
                            if kind == "assessment_event":
                                assert data["id"] == fields["id"] and data["run_id"] == run["id"]
                                target.append(data)
                                created = datetime.fromisoformat(data["created_at"].replace("Z", "+00:00"))
                                if measure_latency:
                                    latencies.append(max(0, (datetime.now(timezone.utc) - created).total_seconds() * 1000))
                                if stop_after and len(target) >= stop_after: return
                            if kind == "stream_error": raise AssertionError(data["code"])
                            if kind == "settled":
                                assert data["status"] == "completed"
                                if target: assert data["last_sequence"] == target[-1]["sequence"]
                                return
                        fields = {}; payload = []
                    elif not line.startswith(":"):
                        name, _, value = line.partition(":")
                        if name == "data": payload.append(value.lstrip(" "))
                        else: fields[name] = value.lstrip(" ")
            raise AssertionError("Stream closed without settlement")

        async def first_observer():
            nonlocal resumed
            await collect(first_events, first_ready, stop_after=5)
            await asyncio.sleep(.1)
            resumed = True
            await collect(first_events, after_id=first_events[-1]["id"])

        async def control():
            await first_ready.wait(); await second_ready.wait()
            await post(path + "/start")

        started = monotonic()
        await asyncio.wait_for(asyncio.gather(first_observer(), collect(second_events, second_ready), control()), timeout=180)
        current = await get(path)
        history = []
        while True:
            page = await get(path + "/events?limit=500&after_sequence=" + str(history[-1]["sequence"] if history else 0))
            history.extend(page)
            if len(page) < 500: break
        assert resumed and first_events == second_events == history
        assert [event["sequence"] for event in history] == list(range(1, len(history) + 1))
        assert len({event["id"] for event in history}) == len(history)
        assert current["status"] == "completed"
        assert sum(event["event_type"] == "payment.captured" for event in history) == 1
        assert await get(environment_path) == before
        historical = []; await collect(historical, measure_latency=False)
        assert historical == history and await get(path) == current
        result = {"run_id": run["id"], "agent_id": candidate["id"], "environment_id": environment["id"], "status": current["status"],
            "event_count": len(history), "simulated_captures": 1, "concurrent_observers": 2, "reconnected": resumed,
            "elapsed_seconds": round(monotonic() - started, 3), "max_observed_delivery_ms": round(max(latencies), 3),
            "source_unchanged": True, "records": {path: current, path + "/events?limit=500": history, environment_path: before}}
        BASELINE.parent.mkdir(exist_ok=True)
        BASELINE.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print("PASS real local assessment:", run["id"], "-", len(history), "ordered events; two observers, reconnect and historical SSE match REST exactly.")
        print("One simulated capture; source snapshot unchanged. Customer mode deterministic; no Gemini call was needed for this monitoring check.")
        print("Retained synthetic records and sanitized restart baseline: tmp/phase6-http-records.json")


if __name__ == "__main__":
    asyncio.run(main())
