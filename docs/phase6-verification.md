# Phase 6 verification

Phase 6 implements persisted-event SSE, a React Flow monitor, a chronological timeline and read-only historical replay. No Phase 7, real PayPal/payment integration, scoring, RAI generation change or payment authorization change was introduced. The plan was recorded in [phase6-plan.md](phase6-plan.md) before code changes. [phase6-monitoring.md](phase6-monitoring.md) records the implemented architecture; the canonical `docs/architecture.md` is preserved.

## Results

| Check | Result |
| --- | --- |
| Full backend pytest | **430 passed, 0 failed**, 770.90 seconds. Existing health/safe-error/CORS, migrations, protocol/network, execution/gateway, RAI Designer/Examiner/provider tests and all 14 new streaming cases passed together. |
| Focused initial SSE tests | 13 passed; a missing-tail corruption regression was then added and included in the final full suite. |
| Frontend tests | **26 passed, 0 failed** using Node's built-in test runner and TSX. |
| Actual frontend client against FastAPI | **Passed**, plus all 26 unit tests (**27 total checks passed**): the production Fetch/SSE service accepted the real run's 60 events, settled, and matched REST exactly; the graph had five nodes/seven evidence-backed edges and reconstructed all 61 prefixes identically. |
| Frontend type checking | Passed for application source and the test source through `npm.cmd run build` / `npm.cmd run typecheck`. |
| Production build | Passed. The monitor/React Flow bundle is lazy-loaded: approximately 214 kB minified monitor JS, 317 kB initial application JS. No large-chunk warning remains after splitting. |
| Alembic schema check | Passed: no new upgrade operations. No model/schema migration was needed; full-suite migration round trips passed. |
| Selected dependency audit | React Flow plus TSX/Node type support installed with **0 reported vulnerabilities**. An initially considered old Vitest version was removed after its audit reported vulnerabilities. |
| Real local assessment | Passed: actual sample-agent HTTP, two concurrent observers connected before start, reconnect/resume, exact stream-to-REST equality, one simulated capture and unchanged source snapshot. |
| Historical SSE | Passed: reconnecting to the terminal run reconstructed identical evidence without starting execution or changing its public record. |
| API restart persistence | Passed for the first retained live verification run: run, evidence and source snapshot matched the saved baseline after the API was stopped/restarted. No execution replay occurred. |
| HTTP smoke | API health HTTP 200/database connected; `/monitor` frontend route HTTP 200 with the application root. |
| Interactive browser smoke | **Unavailable**: native computer-use pipe and browser-access host were not available. No visual browser result is claimed. The frontend build, SSR lifecycle tests, pure graph tests and real HTTP/SSE checks are verified evidence. |

The backend suite has one existing dependency warning: Starlette uses AnyIO's deprecated `BlockingPortal` alias. An intermediate full run was stopped after a new stream-integrity regression was added; it was superseded by the complete passing run above. Frontend harness issues were resolved: restricted Windows execution denied Node account lookup before tests ran, the initial TSX invocation used the wrong JSX mode, and a temporary out-of-package live-check harness required an explicit `.mts` ES-module extension. The final commands supply `tsconfig.tests.json` explicitly and all tests passed in authorized execution. There are no remaining failed assertions.

## Backend contract and evidence authority

`GET /api/assessments/{run_id}/stream` requires the separate monitoring bearer token in `Authorization`. Empty configuration returns safe 503; wrong/missing authentication returns 401 before existence/cursor lookup. `Last-Event-ID` is a canonical event UUID scoped to this run and takes precedence over `after_sequence=N`. Replay is exclusive of the accepted cursor. Missing run returns 404; unknown/cross-run/ahead cursors return 422. No URL-token authentication exists.

Evidence frames use `event: assessment_event`, `id: <RunEvent UUID>`, and the same public JSON as REST history. `snapshot`, `settled` and `stream_error` are transport controls and never appear as fabricated timeline events. Heartbeats are comments. The stream supports created runs, waits for committed work, drains every terminal event and closes after settlement for completed/failed/cancelled/inconclusive states.

`run_events` remains the sole event authority, ordered by its unique per-run sequence; `Assessment` remains the lifecycle authority. No controller/gateway event production or financial rules were changed. The reader uses bounded 100-row batches, short sessions off the execution event loop, no session during yields/sleeps, bounded frames and a per-process stream admission cap. Disconnect/cancellation/error cleanup releases the admission lease. Missing history is reported instead of hanging or inventing evidence. Existing expiry recovery remains canonical and does not replay outbound POSTs.

Shared REST/SSE serialization redacts current provider, agent and monitor secrets and excludes private aggregates, connection configuration, blueprint/evaluation data and leases. Simulated payment evidence is retained as simulated evidence.

## Authentication and ownership limitation

The new monitoring token is **shared operator authentication**, not user identity or per-assessment ownership. A valid holder can read the selected run. Assessments currently have no owner to check. Existing management/REST/start/cancel endpoints retain their prior unauthenticated trusted-local behavior. The stream does not make the application production-secure. Keep it on loopback; production needs account authentication, ownership checks across all reads/writes and operational quotas.

A separate random token was appended to the existing uncommitted `backend/.env` with `configure_monitor.py`; its value was never printed. Existing Gemini settings/key and database were retained. The browser holds the monitoring token only in memory, sends it in a Fetch header and requires re-entry after refresh. No token is placed in `VITE_`, browser storage, URLs or evidence. Native EventSource was not used because the selected authentication needs an Authorization header.

Default polling/heartbeat/admission settings are 0.5 seconds / 10 seconds / 16 streams per process. Nominal delivery latency includes polling, database and scheduling time; this is not a hard real-time system. Frontend buffering is explicitly capped and fails visibly instead of silently evicting history. The Windows launcher uses a five-second graceful-shutdown timeout to bound shutdown with idle streaming clients.

## Deterministic graph and timeline mapping

Five fixed roles are always visible: RAI Examiner/Customer, Candidate Agent, Tool Gateway, Environment Engine and Payment Gateway **(simulated)**. Their activity counts and all edges use only supporting IDs from the selected persisted prefix.

| Actual event type | Graph interpretation |
| --- | --- |
| customer message / agent requested | Customer → Candidate; recorded protocol request pending until a matching response |
| agent message / completed | Candidate → Customer; a completion claim remains separate from assessment success |
| agent tool call | Candidate → Gateway; correlation-bound pending operation |
| tool requested | Gateway → Environment for scenario state/policy, or Gateway → simulated Payment for checkout/status |
| tool completed / failed | Resolve correlated operation and show recorded Gateway → Candidate result |
| policy violation / approval denied | Rejected outcome; retained even if a later attempt recovers |
| challenge activated | Environment → Gateway, a recorded declared mutation |
| conditional RAI challenge request | Customer → Environment; explicitly not an activation before its trigger |
| checkout/payment lifecycle | Gateway → simulated Payment, with no real payment claim |
| Examiner requested / generated / fallback | Pending Examiner activity resolved by a recorded plan or explicit fallback |
| assessment finished | Outstanding recorded requests become interrupted, never fabricated successful results |

Edges aggregate supporting UUIDs by service relationship to avoid visual clutter; latest interaction outcomes are distinct from assessment safety scores. A completed lookup reporting an unverified merchant remains a successful tool operation. Unknown/proposal/system evidence stays in the timeline without invented interactions. Selecting nodes/edges filters corresponding events. The pure graph function reconstructs identical data for identical prefixes.

The timeline displays sequence, type, timestamp, actor, fixed readable description and outcome. Clicking an event reveals sanitized details. Manual upward scrolling/event selection pauses auto-follow, and Follow latest resumes it. Replay changes only the selected prefix via slider/step controls; no execution API or payment operation is called. Lifecycle metadata is clearly the current saved assessment, separate from historical prefix selection. Refresh/reconnect never starts a run.

## Real local verification

The independent existing sample agent was started on `127.0.0.1:9001` in safe mode. The API used its existing development-only fixed local-sample gate, the newly configured monitoring token and the same SQLite database. RAI configuration remained Gemini / `gemini-3.5-flash-lite`; this Phase 6 check used deterministic customer mode so no new paid Gemini request was necessary.

`backend/scripts/check_monitoring.py` registered/tested a real local protocol candidate, compiled the canonical price-change environment and created a run. Two authenticated streams connected while it was created. A separate control request started execution only after both observers were ready. One observer intentionally disconnected after five events, then resumed using its last UUID. Both complete arrays equaled paginated REST history exactly: same IDs, sequences, timestamps, types, correlations and payloads; no duplicates or missing events. Historical SSE then returned the same array and left the run unchanged. Source environment JSON was unchanged and exactly one simulated capture was recorded.

Two reproducible checks were performed. The first passed all correctness checks; its latency accumulator also counted later historical replay. That measurement was corrected to exclude historical-only replay, then the complete local check was repeated. Both synthetic datasets are retained; no existing data was reset.

Latest live run:

- Assessment: **`86f42bad-dc4b-4255-922d-21af0a186757`**.
- Agent: `5cf0ea36-0610-4c53-8560-27d9f35b5b13`.
- Environment: `f33574f6-3997-401d-a686-5814738163a9`.
- Outcome: **completed**, **60 ordered events**, **two observers**, **one successful resume**, **one simulated capture**, unchanged source.
- Whole stream/replay verification elapsed: **3.532 seconds**.
- Largest observed live/reconnected event age at delivery: **1434.705 ms**. This includes scheduling, polling and intentional reconnect backlog; it is an observation, not a service-level latency guarantee.
- Sanitized records/summary: ignored `tmp/phase6-http-records.json`.

A temporary Node/TSX check also imported the actual frontend `watchAssessment` and `assessmentGraph` implementations, authenticated to this live FastAPI run with the monitoring token held only in local process memory, and required all 60 parsed events to equal REST history. It settled normally, produced five nodes/seven supported edges, and checked deterministic reconstruction at every prefix (0–60). The combined command passed all 27 checks. Sanitized summary: ignored `tmp/phase6-frontend-http.json`. This establishes the real client transport/parser/projection path, while interactive browser layout and input remain unverified.

First run, additionally verified after actual API restart:

- Assessment: **`55cb7749-7a24-4a76-85fa-c83d4cfd4677`**.
- Source environment: `32abb5c9-ec5f-4371-a9ca-92d289be60bf`.
- Outcome: completed, 60 identical ordered events, one simulated capture, unchanged source.
- `check_monitoring.py --verify-restart` passed after stopping/restarting the API: persisted run/evidence/environment representations were identical, with no execution replay.

During the intentional disconnect, Windows/Python's Proactor transport logged a `ConnectionResetError [WinError 10054]` callback for the closed socket. The API continued, execution completed, reconnect/history checks passed and unit/ASGI cleanup tests passed. This runtime log noise remains a known limitation; no broad network-error suppression or security bypass was added.

## Files changed

Backend:

- `backend/app/core/config.py`, new `backend/app/core/monitor_auth.py`.
- New `backend/app/events/public.py` and `backend/app/events/stream.py`.
- `backend/app/api/assessments.py`, `backend/app/main.py`.
- `backend/app/execution/service.py`: optional run-scoped existing expiry recovery, no new transitions.
- `backend/.env.example`, `backend/scripts/start_backend.cmd`.
- New `backend/scripts/configure_monitor.py`, `backend/scripts/check_monitoring.py`.
- New `backend/tests/test_assessment_stream.py`.

Frontend:

- `frontend/package.json`, `frontend/package-lock.json`, new `frontend/tsconfig.tests.json`.
- `frontend/src/main.tsx`, `frontend/src/styles.css`, `frontend/src/services/api.ts`.
- New `frontend/src/services/assessmentStream.ts`, `frontend/src/services/assessmentGraph.ts`.
- New `frontend/src/hooks/useAssessmentStream.ts`.
- New `frontend/src/pages/MonitorPage.tsx`.
- New `frontend/src/components/AssessmentGraph.tsx`, `AssessmentLifecycle.tsx`, `AssessmentTimeline.tsx`.
- `frontend/src/components/AssessmentDetails.tsx`, `Layout.tsx`.
- New `frontend/tests/phase6.test.tsx`.

Documentation: `README.md`, `AGENTS.md` (scope now stops after Phase 6), `docs/execution-controller.md`, and new `docs/phase6-plan.md`, `docs/phase6-monitoring.md`, this report. The local ignored `.env` gained only the separate monitoring credential. No provider/RAI generation, gateway/payment implementation, model or migration files changed.

## Exact startup and manual verification

Use ordinary authorized PowerShell terminals; stop existing processes before restarting. Keep `.env` server-only and preserve its current Gemini settings.

One-time root setup after dependencies are installed:

```powershell
Set-Location E:\Testah
.\backend\.venv\Scripts\python.exe backend/scripts/configure_monitor.py
```

Open the existing `backend/.env` locally yourself and copy the generated `TESTAH_MONITOR_TOKEN` for the monitor password field. Do not paste it into chat or a URL. An existing non-empty token is preserved; restart after configuration changes.

Backend terminal:

```powershell
Set-Location E:\Testah\backend
.\scripts\start_backend.cmd
```

Frontend terminal:

```powershell
Set-Location E:\Testah\frontend
npm.cmd run dev
```

For a real local sample assessment, ensure the existing backend development-only local-sample gate is enabled, and start the sample in another terminal:

```powershell
Set-Location E:\Testah
$env:TESTAH_SAMPLE_BEHAVIOR = 'safe'
.\backend\.venv\Scripts\python.exe -m uvicorn sample_agents.main:app --host 127.0.0.1 --port 9001
```

1. Open `http://127.0.0.1:5173/monitor/86f42bad-dc4b-4255-922d-21af0a186757` and enter the separate monitoring token. Expect completed status and 60 persisted events; the connection settles after history drains.
2. Select graph nodes/edges and inspect their matching timeline rows and sanitized payloads. Confirm the payment role and descriptions are simulated. Move the replay slider and step backward/forward; no new execution occurs.
3. Refresh, re-enter the token and confirm the same graph, IDs, order and outcome reconstruct. An open historical monitor never calls Start.
4. To observe a new run, register/test the local sample through My Agents, create a compiled environment and assessment, then follow its Open live monitor link while it is created. Connect before pressing Start assessment. Observe actual state/events; Cancel remains the existing explicit action.
5. Scroll upward/select an earlier row during a run; auto-follow pauses. Follow latest resumes it. While a created run is open, restarting the API exercises reconnect without starting execution. The client resumes with its last accepted UUID.
6. Close/navigate away to abort the stream. An invalid monitoring token fails explicitly and cannot access a stream. Inspect old failed/inconclusive/cancelled runs through the same historical path.

Reproducible HTTP verification:

```powershell
Set-Location E:\Testah
.\backend\.venv\Scripts\python.exe backend/scripts/check_monitoring.py
# Stop and restart only the API with the same database and monitoring credential.
.\backend\.venv\Scripts\python.exe backend/scripts/check_monitoring.py --verify-restart
```

Automated checks, with the standalone sample stopped so pytest can own port 9001:

```powershell
Set-Location E:\Testah\backend
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m alembic check
Set-Location E:\Testah\frontend
npm.cmd test
npm.cmd run typecheck
npm.cmd run build
```

If the Windows profile temp directory is restricted, use a fresh workspace-local pytest base/cache as already documented in the README. The final complete run used `tmp/pytest-phase6-full-final` and its separate cache directory. No further phase is authorized automatically.
