# Phase 4 verification

Verified November 2, 2026 (America/Los_Angeles) on Windows PowerShell, Python 3.12.16, Node 22.11.0 and npm 10.9.0. No application dependencies were added. Phase 4 only is implemented; Phase 5 has not started.

## Delivered behavior and architecture decisions

The existing modular monolith now runs a registered external agent through the actual Phase 2 JSON/HTTP protocol against an isolated copy of a saved Phase 3 blueprint. All six registry tools execute through the gateway. Exact cart approvals, current-state/budget/merchant enforcement, checkout idempotency, purchase limits, all four declarative challenges, terminal outcomes, and ordered sanitized evidence persist transactionally. The React assessment page creates, starts, polls, cancels and inspects actual runs/events. Dashboard activity comes from the API.

Claims use a transactional UPDATE before reading the run, a private lease token, and fenced writes. HTTP awaits occur outside database transactions. SQLite serializes writers. An abandoned lease becomes inconclusive and is never reclaimed to replay a POST. The local asyncio worker is explicitly not a durable distributed queue. Approvals/checkouts are private JSON members of the locked run aggregate; events have their own durable table and unique run/sequence constraint. The server-owned payment provider explicitly simulates created/authorized/completed transitions without PayPal or real money. Details, APIs, settings, continuation policy and trigger mapping are in [execution-controller.md](execution-controller.md).

## Commands and results

| Command/check | Result |
| --- | --- |
| backend: `.\.venv\Scripts\python.exe -m pytest` | **257 passed**, one unchanged Starlette/AnyIO deprecation warning; 160 existing tests plus 97 Phase 4 cases |
| backend: `.\.venv\Scripts\python.exe -m alembic upgrade head` | Existing development database upgraded to `0004_execution` |
| backend: `.\.venv\Scripts\python.exe -m alembic current` | `0004_execution (head)` |
| backend: `.\.venv\Scripts\python.exe -m alembic check` | No new upgrade operations detected |
| migration regression | Fresh upgrade, repeated upgrade, schema drift check, downgrade to base and re-upgrade passed inside full pytest |
| frontend: `npm.cmd run build` | Strict TypeScript and Vite build passed; 58 modules |
| root: `.\backend\.venv\Scripts\python.exe backend/scripts/check_assessments.py` | Six completed real-HTTP runs, two independent runs per source snapshot, all three templates |
| root: `.\backend\.venv\Scripts\python.exe backend/scripts/check_assessments.py --verify-restart` | All six outcomes, ordered event payloads, and source environment previews identical after verified API process restart |
| root: `.\backend\.venv\Scripts\python.exe sample_agents/integration_check.py` | Existing message/tool_call/completed probes and connection-status persistence passed; its temporary agent was removed |
| root: `node tmp/assessments-ui-smoke.mjs` | Six React/real-API checks passed: creation, start/poll/events/denials, refresh, error/retry, cancellation, navigation/dashboard/health |
| HTTP health | `/api/health` reports connected database and ok status |
| frontend route | `/assessments` serves successfully from the development server |

Backend coverage includes all 36 state-transition pairs; strict tool arguments and references; allowlist rejection; merchant verification/checkout support; unavailable products; exact totals, shipping and currencies; budget enforcement; approval binding including offsetting price/shipping changes; fresh approval after an affordable mutation; idempotent checkout replay/conflict; two outstanding legal approvals unable to bypass purchase count; all four once-only challenge kinds; isolated runs/source snapshots; concurrent claims, checkouts and event allocation; paginated evidence; secret redaction; independent turn/HTTP/tool/repetition/message limits; response-size/contract errors; late-response cancellation fencing; worker cancellation and expired leases; and infrastructure failure classification. Existing connector tests retain SSRF, DNS pinning, TLS, redirect, proxy, size, timeout, envelope and safe error coverage. Existing health, failure, CORS, agent and environment regressions pass.

Ten Phase 4 integration cases use a real sample HTTP listener on the dedicated fixed 127.0.0.1:9001 gate: safe completion on each template, unauthorized checkout, over-budget cart, unverified merchant, duplicate checkout, invalid arguments, malformed response and timeout. Testah's loop is never replaced with a hardcoded passing outcome. The sample's behavior is selected only in the sample process; the controller follows real returned protocol actions.

## Process restart and live results

The successful walkthrough produced:

| Template | Run IDs | Events per run |
| --- | --- | --- |
| budget_constrained_purchase | `01e497d2-2ca1-4507-855c-7a6daac8ef20`, `4bca1a83-cab8-442b-b18b-51dadc2acad6` | 54 |
| merchant_trust_verification | `57119aa4-1d7f-43d7-b9f3-c279d3fb3af1`, `e8673cbf-9e18-416e-9ae1-303bdb49cd67` | 47 |
| price_change_before_checkout | `8ceabc50-ff22-492d-bee4-61d64f19d049`, `4cd0bde1-667f-4fa2-942f-f1a121f2548f` | 60 |

Each run recorded exactly one simulated capture and payment inspection, stable contiguous event sequences and unchanged source environment data. All six checkout IDs differ. Duplicate starts did not create duplicate execution. The baseline is retained under ignored `tmp/phase4-http-records.json`. The API was actually stopped, port 8000 was verified closed, and a new API process successfully bound before the restart comparison passed. The full test suite also verifies persistence across fresh app instances.

The first external walkthrough harness incorrectly required a policy denial on the merchant-trust path. The sample correctly observed the newly unverified merchant and selected a legal alternative without attempting an illegal purchase. The harness assertion was corrected to require denials only for availability/price-change paths, and all six runs passed. The first process-restart attempt hit Windows process-control errors and left the original listener alive; its reread was not counted as restart evidence. The subsequent attempt verified port closure and a newly bound API before checking persistence.

The React harness was rerun cleanly after correcting its synthetic click to be cancelable. It exercised the actual bundled application, actual API fetches, completed and cancelled persisted runs, ordered event payloads, highlighted denials, timestamps/reasons, outage/retry behavior, agent/environment navigation, recent dashboard records and backend health. Harness dependencies remain in ignored tmp/ and do not alter application dependencies. Actual browser access and native UI connection were unavailable, so visual/mobile inspection and real-browser CORS inspection remain **unverified**. Backend CORS tests and React DOM behavior passed.

The walkthrough and React checks intentionally retain clearly named synthetic agents, environments and runs for inspection. A preliminary harness attempt also retained its partial synthetic test records. No existing records were deleted. Referenced agents cannot be deleted through management APIs. No .env files or credentials were committed/changed by this work.

## Exact manual reproduction

The root [README](../README.md#phase-4-reproducible-assessment-walkthrough) contains complete four-terminal Windows PowerShell commands. From a migrated installation:

1. Stop a manual sample before running backend pytest, which needs the fixed sample port.
2. Start the sample from root with `TESTAH_SAMPLE_BEHAVIOR=safe`, using `python -m uvicorn sample_agents.main:app --host 127.0.0.1 --port 9001` through the backend venv.
3. Start the API from backend with `TESTAH_ENVIRONMENT=development`, `TESTAH_ALLOW_LOCAL_SAMPLE=true`, and `.\.venv\Scripts\python.exe -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000`.
4. Start the UI from frontend with `npm.cmd run dev`.
5. From root run `.\backend\.venv\Scripts\python.exe backend/scripts/check_assessments.py`.
6. Stop only the API with Ctrl+C, restart it with the same command/database, and run `.\backend\.venv\Scripts\python.exe backend/scripts/check_assessments.py --verify-restart`.
7. Open `http://127.0.0.1:5173/assessments`; inspect a saved run and expand its approval, challenge, denial, checkout, payment and termination events. Create another run by selecting a connected agent and compiled environment, then Start assessment. Refresh status or cancel a created/running run.
8. To inspect deliberate failures, restart only the sample with `TESTAH_SAMPLE_BEHAVIOR=unauthorized`, `over_budget`, `unverified`, `duplicate`, `invalid_arguments`, `timeout`, or `malformed`, then create a new assessment. Restore safe mode afterward.

## Changed-file manifest

| Area | Files |
| --- | --- |
| Run/event persistence | `backend/app/models/assessment.py`, `backend/app/models/__init__.py`, `backend/alembic/versions/0004_execution.py`, `backend/app/schemas/assessments.py` |
| Controller and API | `backend/app/execution/service.py`, `backend/app/execution/controller.py`, `backend/app/api/assessments.py`, `backend/app/api/agents.py`, `backend/app/main.py`, `backend/app/core/config.py` |
| Gateway/runtime/provider/evidence | `backend/app/tools/gateway.py`, `backend/app/environments/runtime.py`, `backend/app/payments/simulation.py`, `backend/app/events/store.py` |
| Tests and HTTP verification | `backend/tests/test_execution.py`, `backend/tests/test_database.py`, `backend/scripts/check_assessments.py` |
| React flow and contracts | `frontend/src/pages/AssessmentsPage.tsx`, `frontend/src/hooks/useAssessments.ts`, `frontend/src/services/assessments.ts`, `frontend/src/types/assessments.ts`, `frontend/src/components/AssessmentDetails.tsx`, `frontend/src/components/AssessmentActivity.tsx`, `frontend/src/main.tsx`, `frontend/src/styles.css` |
| Truthful existing UI copy | `frontend/src/pages/Dashboard.tsx`, `frontend/src/pages/EnvironmentsPage.tsx`, `frontend/src/components/EnvironmentDetails.tsx`, `frontend/src/components/Layout.tsx` |
| Standalone sample | `sample_agents/main.py`, `sample_agents/README.md` |
| Configuration/docs | `backend/.env.example`, `AGENTS.md`, `README.md`, `docs/execution-controller.md`, `docs/phase4-verification.md` |

No changes were made to protocol 1.0 schemas, registry 1.0 definitions, Phase 3 templates/fixtures/blueprint validation, existing environment APIs, network protections, dependencies, or `docs/architecture.md`. Architecture SHA-256 remains `8A511319F1C5002FA8C008C69FDF9EA9DEB1765DB763F8930C05A8623129A5D8`. Git metadata is absent in this workspace; the manifest records the files edited during this task rather than claiming a Git diff.

## Known limits and deviations

The source architecture is a proposed end-state. Phase 4 deliberately uses the existing request/correlation identifiers and integer-money snapshots, the requested six statuses, deterministic customer messages, simulated payments, and polling. It does not add RAI, PayPal, scoring, SSE, React Flow, AG Grid or Phase 5. Frozen registry descriptions still contain Phase 3's stale unimplemented wording; changing those version 1.0 strings would invalidate saved blueprints. This investigated discrepancy is documented in the execution design.

Run-local approval/payment aggregates replace separate proposed approval/payment tables for this transactional simulation. Intermediate simulation transitions are durable ordered events in one transaction; there is no external pending payment or reconciliation. Existing arbitrary objective text is descriptive, not a general natural-language completion evaluator. Completion means a server-recorded simulated purchase with payment inspection, not a claim that every semantic objective or future safety rule passed.

Production still requires authentication and owner-scoped authorization, durable queue/workers/sweepers, bounded global concurrency/rate limits, PostgreSQL, verified real-provider buyer approval/reconciliation, trusted bounded DNS/egress controls, backups/retention and monitoring. The current lease expires after duration plus 30 seconds; management requests reconcile expired leases, and no uncertain POST is replayed. SQLite contention can return safe errors, and PostgreSQL behavior has not been integration-tested. Redaction is not a general DLP system. The service is not ready for unrestricted public deployment.
