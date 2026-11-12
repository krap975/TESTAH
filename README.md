# Testah

Publication/deployment preparation adds shared workspace access for invited demo users,
PostgreSQL support, startup migrations and an undeployed Render Blueprint. See the
[GitHub/Render runbook](docs/render-deployment.md) and
[security and verification report](docs/deployment-verification.md).
Nothing has been pushed or deployed. Local startup below is unchanged.


Phase 10 (reduced hackathon scope) adds a
[developer quickstart](docs/developer-quickstart.md), an accurate
[candidate protocol reference](docs/agent-protocol.md), and a reproducible
[candidate-only OpenAPI](docs/developer/candidate-agent.openapi.json).
See [APIMatic artifact status/provenance](docs/apimatic.md),
[verification and remaining tasks](docs/phase10-verification.md), and
[undeployed Render preparation](docs/render-readiness.md).
No new business schema migration is required. Separate user accounts remain future work;
the hosted demo requires a separately configured shared workspace token.

Phase 9 adds read-only assessment reports with a focused performance overview,
AG Grid Community findings/listings/evidence inspection, deterministic improvement
guidance, complete sanitized JSON downloads and browser **Print / Save as PDF**.
Open `http://127.0.0.1:5173/reports` or the report link in assessment details.
Reports reuse persisted Phase 8 evaluations; opening or exporting one never scores,
reconciles or captures a payment. No migration or new configuration is required.
See [reporting architecture and APIs](docs/phase9-reporting.md) and
[verification](docs/phase9-verification.md). Authentication and checkout polish
remain future work.

Phase 8 adds deterministic five-dimension commerce scoring and separate versioned
certification. See [the scoring rules and evidence contract](docs/phase8-scoring.md).
Upgrade the database with `python -m alembic upgrade head` using the backend virtual
environment before restarting the API. Current migration head: `0008_evaluation`.
New terminal assessments are scored automatically. Historical assessments retain
their original evidence; use **Evaluate recorded evidence** in assessment details
to request a clearly labeled retrospective score. Scoring never invokes a payment,
agent or LLM. The details show missing evidence and untested recovery explicitly.

Testah tests financial AI agents in controlled simulated environments. Phase 5 adds separated RAI Designer and RAI Examiner services. Phase 6 adds live monitoring and historical replay from committed evidence using authenticated SSE and React Flow. Phase 7 adds an optional PayPal Sandbox Orders adapter and interactive buyer approval alongside existing simulated payments. Reference assessment `448a13ed-d692-4355-acb3-0a7de6117529` records a verified completed USD 80 Sandbox capture. Phase 8 adds deterministic scoring and independent certification from persisted evidence. Generate and compile an environment, choose a customer mode, then observe its actual execution.

Implemented: agent management/protocol testing; deterministic environments; all six commerce tools; exact scenario approvals and idempotent simulated purchases; isolated runtime challenges; assessment APIs/dashboard; ordered durable evidence; authenticated live monitoring with a React Flow graph, timeline and replay; guarded HTTPX communication; and an independent no-LLM sample agent. Execution completion is not a safety score.

RAI supports controlled proposals and constrained customer-message plans. Phase 8 scores recorded commerce evidence deterministically, with a separate safety gate and certification. Phase 9 presents those results in evidence-linked reports and AG Grid Community. Real-money payments and separate user ownership remain unimplemented. Hosted shared-workspace access requires a distinct runtime token covering operational APIs; monitoring and Sandbox payments still require their separate operator tokens. This does not establish tenant ownership. The in-process workers are not production distributed queues. Local development stays on loopback; follow the Render runbook for the invited demo.

## Project layout
- frontend/src/: React components, route pages, services, hooks, and types.
- backend/app/agents/: agent configuration service; api/agents.py: HTTP management endpoints.
- backend/app/execution/: controller, central state machine, fenced database claims, local worker, protocol connector and destination validation.
- backend/app/schemas/protocol.py: shared versioned wire contract.
- backend/app/models/: SQLAlchemy entities; backend/alembic/: versioned migrations.
- backend/tests/: API, protocol, connector, network-policy, and migration tests.
- sample_agents/: independent deterministic FastAPI sample and opt-in HTTP integration check.
- docs/: [architecture](docs/architecture.md), [agent protocol](docs/agent-protocol.md), and implementation verification notes.

Read [AGENTS.md](AGENTS.md) before changing code. The canonical architecture was copied in Phase 1 from the supplied complete Markdown design; original references are preserved. The architecture describes future capabilities as well as current foundations.

## Windows PowerShell setup
Prerequisites: Python 3.12 with the Windows launcher (py), Node.js 22+, and npm. Render and current verification use Python 3.12.16. Replace E:\Testah with your checkout path.

~~~powershell
Set-Location E:\Testah
py -3.12 -m venv backend/.venv
.\backend\.venv\Scripts\python.exe -m pip install -r backend/requirements-dev.txt
if (-not (Test-Path backend/.env)) { Copy-Item backend/.env.example backend/.env }
if (-not (Test-Path frontend/.env)) { Copy-Item frontend/.env.example frontend/.env }
Set-Location backend
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m alembic current
Set-Location ../frontend
npm.cmd ci
~~~

If py is unavailable, substitute your installed Python 3.12 executable for py -3.12. Direct virtual-environment invocation avoids activation-policy changes; npm.cmd avoids PowerShell npm shim restrictions. On an existing checkout, install updated requirements and run alembic upgrade head, but preserve existing .env files and data. Do not reinstall node_modules while Vite is using esbuild on Windows.

Start Testah backend, terminal 1:

~~~powershell
Set-Location E:\Testah\backend
.\scripts\start_backend.cmd
~~~

Start frontend, terminal 2:

~~~powershell
Set-Location E:\Testah\frontend
npm.cmd run dev
~~~

Open http://127.0.0.1:5173 and choose My Agents or Environments. Open http://127.0.0.1:8000/docs for API contracts. The dashboard's health check remains available.

Start the backend in an ordinary authorized PowerShell terminal, or through explicitly approved execution outside a restricted coding-agent sandbox. The CMD launcher fixes the working directory, uses the existing virtual environment and starts one loopback API without reload. It changes no security policy or privileges. A shell's inherited network-disabled marker is only a warning: actual access must be checked inside FastAPI. Do not run a second backend on port 8000. Stop the current API with Ctrl+C before restarting; settings load once from `backend/.env`, with process environment taking precedence.

In **Generate with RAI**, press **Check provider connectivity and authentication** before diagnosing a failed generation. This development-only action reports the serving PID, Python executable, environment file, override names, effective limits, verified outbound HTTPS and one small authenticated Gemini generation. It may consume API usage and never runs automatically on page load or startup. The same check from PowerShell is:

~~~powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/rai/diagnostics -ContentType application/json -Body '{"run_smoke_test":true}' -TimeoutSec 75 | ConvertTo-Json -Depth 10
~~~

The diagnostics route and OpenAPI entry exist only when `TESTAH_ENVIRONMENT=development`; test/production return 404. Keep this unauthenticated development API on loopback. Mock mode is explicitly labeled and makes no diagnostic Gemini calls. `provider_network_denied` requires correcting the authorized API launch environment, not a longer timeout. TLS, DNS, proxy, connection and timeout failures have distinct sanitized classifications. Environment proxies remain disabled; no TLS, DNS-pinning or destination rules are bypassed. Failed proposals retain their category and inputs; **Retry generation with the same agent** submits a new job, while compilation remains limited to validated ready proposals. See [the reliability investigation](docs/gemini-reliability-verification.md) for evidence and limits.

## Standalone sample and real local integration
The sample uses shared wire schemas only and runs in its own server process. It needs no LLM account, database access, or payment credentials. Assessment requests drive the six tools through the server gateway and recover to legal alternatives after challenges. It demonstrates message, tool_call, and completed responses. The backend environment already includes its dependencies; sample_agents/requirements.txt is available for an independently installed environment.

Start the sample, terminal 1:

~~~powershell
Set-Location E:\Testah
.\backend\.venv\Scripts\python.exe -m uvicorn sample_agents.main:app --host 127.0.0.1 --port 9001
~~~

Start or restart Testah with the explicit local gate, terminal 2:

~~~powershell
Set-Location E:\Testah\backend
$env:TESTAH_ENVIRONMENT = "development"
$env:TESTAH_ALLOW_LOCAL_SAMPLE = "true"
.\.venv\Scripts\python.exe -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000
~~~

Run the integration check, terminal 3:

~~~powershell
Set-Location E:\Testah
.\backend\.venv\Scripts\python.exe sample_agents/integration_check.py
~~~

It registers a temporary sample record, exchanges all three response types over real HTTP, verifies the persisted status, and removes its own record. For manual UI use, register an agent in Local sample mode; its fixed endpoint is http://127.0.0.1:9001/agent. External mode always requires public HTTPS. Stop the sample and press Test connection to see an actual unreachable error. Remove TESTAH_ALLOW_LOCAL_SAMPLE from the process environment when finished, or leave its default false in .env. Production/test settings reject the local gate.

## Configuration and secrets
backend/.env loads independently of working directory; process environment values take precedence. Relative SQLite paths resolve under backend/. Both migrations and the API use TESTAH_DATABASE_URL (default sqlite:///./testah.db). Migrations own all schema changes; startup never creates tables automatically. Current head: 0008_evaluation.

TESTAH_CORS_ORIGINS is a JSON array of exact frontend origins. frontend/.env sets the public VITE_API_BASE_URL without /api. Restart Vite after changing it. VITE_ settings are embedded in browser bundles and must never contain secrets.

TESTAH_AGENT_TIMEOUT_SECONDS defaults to 10 (range 1-60), including DNS and full streamed response time. TESTAH_AGENT_MAX_RESPONSE_BYTES defaults to 65536. Health/general browser API calls have an eight-second timeout; connection tests allow up to 65 seconds for the server deadline.

Optional authentication uses TESTAH_AGENT_SECRETS, a server-only JSON map of reference keys to complete header values. Configure it only in the uncommitted backend environment or a secret manager, then enter the reference key in My Agents. Supported headers: Authorization and X-API-Key. Values are not stored in SQLite, returned by APIs, entered into UI forms, or included in logs. See [authentication details](docs/agent-protocol.md) for rotation and the sample's optional TESTAH_SAMPLE_TOKEN setting.

## Checks

~~~powershell
Set-Location E:\Testah\backend
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m alembic check
Set-Location ../frontend
npm.cmd run build
npm.cmd run typecheck
npm.cmd test
~~~

With the backend running:

~~~powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health
Invoke-RestMethod http://127.0.0.1:8000/api/agents
~~~

Tests use isolated temporary databases. Connector unit tests mock public requests; Phase 4 tests start a real sample HTTP listener on 127.0.0.1:9001. Stop any manual sample before pytest so this fixed port is free. The documented sample integration check is explicit and uses real local HTTP. No tests contact arbitrary public agents. Production builds include strict TypeScript checks. Vite supports route fallback; a future static host must serve index.html for client-side routes.

## Security and limitations

Frontend tests use Node's built-in test runner with `tsx`. A restricted Windows coding-agent runner can deny Node's account lookup (`uv_os_get_passwd`) before tests execute; run them in an ordinary authorized terminal or explicitly approved execution. Do not change system security settings to run tests.

## Phase 6 live monitoring and historical replay

With the frontend dev server stopped, update dependencies using `npm.cmd ci` from `frontend/`. Configure a **separate monitoring token** once, from the repository root:

~~~powershell
.\backend\.venv\Scripts\python.exe backend/scripts/configure_monitor.py
~~~

This appends a random credential to the existing uncommitted `backend/.env`, or preserves an existing token. It never prints it and does not change Gemini settings. Open that local file yourself and copy only `TESTAH_MONITOR_TOKEN` into the monitor's password field. Never use a Gemini/agent key, put the token in `VITE_`, a URL or source control. Restart the API using `backend/scripts/start_backend.cmd` in an authorized network-enabled terminal; start the frontend with `npm.cmd run dev` from `frontend/`.

Open `http://127.0.0.1:5173/monitor`, select a saved assessment and connect. The token stays in browser memory and must be re-entered after refresh. Opening a page or replay never starts execution. Use **Start assessment** explicitly for a created run; the existing cancel action remains available for created/running runs. Assessment details link to `/monitor/{run_id}`.

Select a graph node/edge to inspect its supporting events, then select an event for sanitized details. Colors distinguish active, successful, rejected, failed and interrupted interactions. Payment labels distinguish simulation, Sandbox order creation, pending buyer approval, capture and failure using actual persisted evidence. Scrolling upward or selecting an earlier event pauses auto-follow; **Follow latest** resumes it. The slider and Previous/Next controls reconstruct an event prefix without contacting an agent or executing payments. Current saved lifecycle metadata remains separate from the replay prefix. The separate Sandbox checkout panel displays current payment state and requires its own token for explicit actions.

`GET /api/assessments/{run_id}/stream` requires `Authorization: Bearer <monitoring token>`. Resume using `Last-Event-ID` with a previously accepted event UUID, or `after_sequence=N`; the header takes precedence. URL-token authentication is unsupported. `assessment_event` frames carry canonical UUIDs and the same public JSON as REST history. `snapshot`, `settled` and `stream_error` frames are transport controls, not evidence. Heartbeats are SSE comments. Terminal history drains before the stream closes. Fetch streaming supports authentication headers, deduplication and bounded buffers.

Defaults: `TESTAH_MONITOR_POLL_SECONDS=0.5`, `TESTAH_MONITOR_HEARTBEAT_SECONDS=10`, `TESTAH_MONITOR_MAX_STREAMS=16`. An empty token disables streaming with a safe 503. A valid token grants shared operator access to the selected assessment. **Per-user ownership is not implemented**; existing REST/management routes remain unauthenticated local/trusted APIs. This is not a production security model. See [Phase 6 architecture](docs/phase6-monitoring.md) and [verification](docs/phase6-verification.md).

## Phase 7 — optional PayPal Sandbox

For a new US Sandbox merchant and USD account/currency troubleshooting, follow the [safe merchant cutover procedure](docs/phase7-us-merchant-cutover.md). Stage credentials and validate the account/app association plus OAuth before activating them. Existing intents keep their original app/merchant; never redirect them during credential rotation.

**No real money. Automated tests use mocked responses; one credentialed Sandbox capture is verified pending, with completed capture still unverified.** The default `simulated` mode keeps the existing payment engine. `paypal_sandbox` uses official PayPal Server SDK 2.4.0 Orders/Payments operations with a constrained HTTPX transport. Mode is fixed when an assessment is created. Sandbox errors never fall back to simulation.

With the API stopped, update dependencies and migrate:

~~~powershell
Set-Location E:\Testah\backend
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m alembic check
Set-Location E:\Testah
.\backend\.venv\Scripts\python.exe backend/scripts/configure_monitor.py
.\backend\.venv\Scripts\python.exe backend/scripts/configure_payments.py
~~~

The scripts preserve existing tokens and never print them. In your local uncommitted `backend/.env`, add these values from your **Sandbox** application and its Sandbox business account. Never enter these credentials in chat, candidate configuration or frontend files:

~~~dotenv
TESTAH_PAYMENT_MODE=paypal_sandbox
TESTAH_PAYPAL_ENVIRONMENT=sandbox
TESTAH_PAYPAL_CLIENT_ID=your-sandbox-app-client-id
TESTAH_PAYPAL_CLIENT_SECRET=your-sandbox-app-client-secret
# Optional exact seller pin; blank uses this Sandbox app's own merchant.
TESTAH_PAYPAL_MERCHANT_ID=
TESTAH_PAYPAL_API_BASE_URL=https://api-m.sandbox.paypal.com
TESTAH_PAYPAL_TIMEOUT_SECONDS=10
TESTAH_PAYPAL_RETRIES=1
TESTAH_PAYPAL_CALLBACK_BASE_URL=http://127.0.0.1:8000
TESTAH_PAYPAL_APPROVAL_WAIT_SECONDS=600
~~~

The environment, API origin and callback origin are fixed to Sandbox/loopback in Phase 7. Only USD/EUR/GBP are supported. All policy-verified synthetic merchants map to the one configured Sandbox business account; no physical fulfillment occurs. A Sandbox **personal buyer account** must approve interactively; keep it separate from the business account. Missing configuration prevents Sandbox assessment creation, and invalid credentials fail safely during OAuth.

Local credential placeholders are treated as missing configuration: the API can start, but Sandbox assessment creation returns `503 / paypal_not_configured`, and the adapter refuses OAuth without making a PayPal request. Fill `TESTAH_PAYPAL_CLIENT_ID` and `TESTAH_PAYPAL_CLIENT_SECRET` in your local `.env`. For this single-merchant integration, leave `TESTAH_PAYPAL_MERCHANT_ID=` blank (remove any placeholder) or supply the actual business merchant ID as an optional exact seller pin. Apply `alembic upgrade head` and restart the API. Existing assessments retain their frozen payment mode; create a new Sandbox assessment after configuration.

Get the client ID/secret from **PayPal Developer Dashboard → Apps & Credentials → Sandbox → your app**. Use the app associated with the intended Sandbox business account. PayPal's [Orders request](https://developer.paypal.com/api/orders/v2/orders-create) makes `payee` optional. With no seller pin, Testah omits `payee`, binds the actual merchant ID returned in the authenticated create response, and requires the same ID on every subsequent order verification. New intents also store a private SHA-256 binding of the app client ID; changing apps blocks creation/capture for an existing intent. This digest is never used as a merchant ID or exposed publicly. Legacy intents without this binding retain their original explicit seller-pin requirement. A supplied seller pin still requires an exact match. Never substitute an email, Classic API username, Client ID or guessed identifier. See [Phase 7 merchant configuration](docs/phase7-merchant-id.md) for the full audit and verification results.

Start the API and frontend in two terminals:

~~~powershell
Set-Location E:\Testah\backend
.\scripts\start_backend.cmd
~~~

~~~powershell
Set-Location E:\Testah\frontend
npm.cmd run dev
~~~

For the deterministic local sample, set `TESTAH_ALLOW_LOCAL_SAMPLE=true` in backend/.env before restarting the API, then in a third terminal:

~~~powershell
Set-Location E:\Testah
.\backend\.venv\Scripts\python.exe -m uvicorn sample_agents.main:app --host 127.0.0.1 --port 9001
~~~

In My Agents, register/test the fixed Local sample endpoint. Compile an environment (for example **Price change before checkout**), create a new assessment, confirm `payment_mode=paypal_sandbox` in its details and start it. Old assessments retain their original payment mode. The active worker pauses candidate turns while awaiting payment. A pending intent reserves budget and purchase capacity; only verified capture counts as a purchase. The overall Sandbox deadline is execution duration plus approval wait; the checkout also has its own approval expiry.

Open `/monitor/{run_id}` and enter `TESTAH_MONITOR_TOKEN` for read-only streaming. In the separate **PayPal Sandbox checkout** panel, enter `TESTAH_PAYMENT_OPERATOR_TOKEN` from the local file. Tokens must differ; both stay in browser memory. The monitoring token cannot capture. The payment token is a shared local operator capability, not user ownership/authentication for the rest of the app.

Once the gateway has authorized the exact cart and PayPal has returned an order, click **Approve with PayPal Sandbox**. Manually sign in as the Sandbox personal buyer and approve. Testah validates callback state and fetches the order server-side; browser return alone never proves approval and never captures. Return to Testah and click **Verify approval and capture**. The server verifies order identity, assessment binding, merchant, exact amount/currency and current scenario policy, sends the capture with a stable request ID, then independently retrieves capture status. The candidate must inspect `get_payment_status` before its completion can complete the assessment. No score is produced.

The panel refreshes persisted state only. **Check provider status** explicitly performs reconciliation without capture. Unknown create results are never automatically recreated; uncertain captures are reconciled by GET without another later POST. Cancelling an assessment prevents new captures but cannot undo a provider request already sent. Known-order reconciliation remains available after interruption; terminal assessments never resume. Reload terminal history to see late payment reconciliation evidence.

New operator APIs: `GET /api/assessments/{id}/payments` and `POST /api/assessments/{id}/payments/{checkout_id}/reconcile` (body: `{"capture_if_approved":false}`), using the separate payment bearer token. Never submit browser amounts/statuses/merchant IDs. PayPal credentials, OAuth tokens, raw provider bodies and buyer information are excluded from public responses/events/logs.

Check the ordered events and graph for order → buyer pending → buyer approved → capture requested → verified captured, then test reconnect/replay and duplicate calls. Order creation alone is never shown as capture. If approval is unavailable, leave it pending; if credentials/PayPal callback behavior prevent verification, record that stage as untested. Full security details, state diagram, tests, limitations and the manual verification checklist are in [docs/phase7-verification.md](docs/phase7-verification.md). The [pending capture investigation](docs/phase7-capture-diagnostic.md) documents the verified pending Sandbox capture, evidence fix and capture-disabled diagnostic command; completed capture remains unverified. Phase 8 remains out of scope.

For real local verification, first start the independent sample on port 9001 and the API with the explicit development local-sample gate, as documented below. From root:

~~~powershell
.\backend\.venv\Scripts\python.exe backend/scripts/check_monitoring.py
~~~

This retains a synthetic agent/environment/run, connects two observers before execution, reconnects one with its last UUID, and requires both streams and historical replay to equal REST history exactly. It uses actual candidate HTTP, deterministic customer messages and simulated payments, with no Gemini request. Stop the standalone sample before pytest, whose fixtures own port 9001. After restarting only the API, verify persistence without replaying execution:

~~~powershell
.\backend\.venv\Scripts\python.exe backend/scripts/check_monitoring.py --verify-restart
~~~

## General security limitations
External destinations are re-resolved and checked on every exchange, then pinned to an approved IP while preserving TLS hostname verification. Private/mixed DNS answers, metadata destinations, redirects, inherited proxies, compressed responses, and unsafe retries are blocked. These application controls do not replace infrastructure egress deny rules, a trusted resolver, concurrency/rate limits, and isolation from internal services. See [network security](docs/agent-protocol.md) for details.

The API has no user authentication/tenant isolation; keep it bound to loopback and trusted users. Do not publicly deploy it as-is. Connection tests validate protocol structure and advertised tool-name membership; assessment tools additionally pass schema, current-state, financial, approval and idempotency checks. A completed response alone cannot complete a run. Saved assessments prevent deletion of referenced agents.

## Environment engine and Phase 3 checks
Three JSON templates are available: Budget-Constrained Purchase, Merchant Trust Verification, and Price Change Before Checkout. Create environments from the dashboard at http://127.0.0.1:5173/environments. Customize name, synthetic customer, objective, budget, and currency. Supported currencies are USD, EUR, and GBP; creation budgets are integer minor units from 1000 to 1000000. The UI accepts two-decimal currency amounts and converts them to integer minor units.

Each saved environment has its own catalog, synthetic merchant attributes, policies, frozen tool schemas, challenge declarations, and private versioned evidence expectations. Prices and challenges scale deterministically with the chosen budget; no FX conversion, LLM, or real merchant data is used. Status compiled means validated snapshot, not agent-tested or ready for payment execution. Public details contain safe challenge summaries while exact triggers and evaluation expectations remain internal.

With the migrated API running, create two independent snapshots:

~~~powershell
Set-Location E:\Testah
.\backend\.venv\Scripts\python.exe backend/scripts/check_environments.py
~~~

This check intentionally leaves two synthetic environments in the development database and saves their representations under ignored tmp/. Stop and restart the API with the same database configuration, then verify persistence without creating additional records:

~~~powershell
.\backend\.venv\Scripts\python.exe backend/scripts/check_environments.py --verify-restart
~~~

See [environment-engine.md](docs/environment-engine.md) for the blueprint, registry, challenge contracts, API examples, privacy boundary, and integration instructions. The registry validates argument shapes; the Phase 4 gateway executes tools against isolated run state. A nullable indexed owner scope prepares for future authorization; it provides no tenant security today. Environment APIs support create/read only, not unrestricted JSON updates.

## Phase 4 reproducible assessment walkthrough

Run checks above with the sample stopped. Then start three terminals (no LLM or payment credentials).

Terminal 1, sample:

~~~powershell
Set-Location E:\Testah
$env:TESTAH_SAMPLE_BEHAVIOR = "safe"
.\backend\.venv\Scripts\python.exe -m uvicorn sample_agents.main:app --host 127.0.0.1 --port 9001
~~~

Terminal 2, API:

~~~powershell
Set-Location E:\Testah\backend
$env:TESTAH_ENVIRONMENT = "development"
$env:TESTAH_ALLOW_LOCAL_SAMPLE = "true"
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000
~~~

Terminal 3, UI:

~~~powershell
Set-Location E:\Testah\frontend
npm.cmd run dev
~~~

Terminal 4, complete real-HTTP walkthrough:

~~~powershell
Set-Location E:\Testah
.\backend\.venv\Scripts\python.exe backend/scripts/check_assessments.py
~~~

This registers/tests a sample agent and compiles all three templates. Two isolated runs per environment must each complete one simulated purchase, record challenges and policy denials, preserve ordered events/source snapshots, and safely handle duplicate starts. It intentionally retains one agent, three environments and six runs and saves an ignored baseline under tmp/.

Stop only the API with Ctrl+C. Restart using Terminal 2's uvicorn command and the same database settings, then verify:

~~~powershell
Set-Location E:\Testah
.\backend\.venv\Scripts\python.exe backend/scripts/check_assessments.py --verify-restart
~~~

Open http://127.0.0.1:5173/assessments. Select a saved run to inspect IDs, agent/environment, status, timestamps, termination reason, ordered tool results and highlighted denials. Expand event payloads. To run another assessment, select a protocol-connected agent and compiled environment, click Create assessment, then Start assessment. Running details poll every two seconds; Refresh status and Cancel assessment are available. Completed records a simulated purchase and payment inspection, not a safety score. Source environments remain compiled snapshots.

For adversarial manual checks, stop the sample, set TESTAH_SAMPLE_BEHAVIOR in its terminal to `unauthorized`, `over_budget`, `unverified`, `duplicate`, `invalid_arguments`, `timeout`, or `malformed`, and restart the same sample command. Create/start a new run. Invalid requests produce gateway denials without purchases. Duplicate mode replays the first checkout and rejects a second key without buying twice. Malformed responses are protocol failures; timeouts are inconclusive infrastructure. Restore `safe` afterward. This controls only the standalone sample, never a controller bypass.

Controller settings freeze at creation: TESTAH_EXECUTION_DURATION_SECONDS, TESTAH_EXECUTION_MAX_TURNS, TESTAH_EXECUTION_MAX_TOOL_CALLS, TESTAH_EXECUTION_MAX_IDENTICAL_CALLS, TESTAH_EXECUTION_MAX_HTTP_REQUESTS, TESTAH_EXECUTION_MAX_MESSAGE_RESPONSES. See .env.example and [execution-controller.md](docs/execution-controller.md) for defaults/ranges. Connector time/size bounds still apply. No POST retries occur.

Short serialized transactions protect approvals, purchases and event sequences. Cancellation fences late responses. SQLite serializes all writers. Graceful worker interruption or an abandoned expired lease becomes inconclusive; reads/list/start/cancel recover expired leases after the duration plus 30 seconds. Unknown HTTP outcomes are never replayed. This is persistent evidence with bounded failure recovery, not durable distributed job execution. Authentication, owner-scoped authorization, durable jobs and infrastructure egress/global concurrency controls remain production requirements.

See [execution-controller.md](docs/execution-controller.md) for exact transitions, trigger mapping, contracts, architecture discrepancies and limitations; [phase4-verification.md](docs/phase4-verification.md) records validation and changed files. Phase 5 is implemented; do not begin later phases automatically.

## Phase 5: Generate with RAI

RAI Designer proposes controlled variations of the three existing commerce templates. The Environment Engine independently validates and compiles reviewed proposals. RAI Examiner selects constrained customer-message plans and cannot grant approval or change financial state. The Tool Gateway remains the sole commerce authority. Default mock mode uses no LLM/API credentials and is labeled throughout the UI/API/evidence. Manual environments and deterministic customer mode remain available.

Stop a manual sample before full pytest, which uses fixed port 9001. After migration, use these four PowerShell terminals.

Terminal 1, existing sample with one clarification question:

~~~powershell
Set-Location E:\Testah
$env:TESTAH_SAMPLE_BEHAVIOR = "clarification"
.\backend\.venv\Scripts\python.exe -m uvicorn sample_agents.main:app --host 127.0.0.1 --port 9001
~~~

Terminal 2, API in explicit credential-free mock mode:

~~~powershell
Set-Location E:\Testah\backend
$env:TESTAH_ENVIRONMENT = "development"
$env:TESTAH_ALLOW_LOCAL_SAMPLE = "true"
$env:TESTAH_RAI_PROVIDER = "mock"
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000
~~~

Terminal 3, frontend:

~~~powershell
Set-Location E:\Testah\frontend
npm.cmd run dev
~~~

Terminal 4, real candidate-HTTP walkthrough:

~~~powershell
Set-Location E:\Testah
.\backend\.venv\Scripts\python.exe backend/scripts/check_rai.py
~~~

This registers/tests a sample, generates and validates a proposal, checks duplicate generation/compilation, compiles one environment, and completes assessments in deterministic and RAI Examiner modes. It prints provider provenance and explicitly identifies mock mode. Synthetic records remain available in the dashboard. A restart baseline is saved under ignored tmp/.

Stop only the API with Ctrl+C, restart with the same database/provider settings, then verify:

~~~powershell
Set-Location E:\Testah
.\backend\.venv\Scripts\python.exe backend/scripts/check_rai.py --verify-restart
~~~

Open http://127.0.0.1:5173. Choose Generate with RAI, select a registered agent, and generate a proposal. Review mode/model, capability uncertainty, template, customer, budget, catalog, merchants and challenge summaries. Confirm and compile. Select RAI Examiner (mock) or Deterministic customer, create the assessment, then click Start assessment. Expand generation, Examiner, challenge, denial, tool and termination events. Advanced / Manual environments opens the existing manual editor. A protocol connection is required before creating an assessment, not before designing a proposal.

### Gemini configuration in the existing backend .env

Task 05.5 extended the existing `E:\Testah\backend\.env` in place, preserving its application name, database URL and CORS settings. Task 05.5.1 verified authenticated Designer generation with `gemini-3.5-flash-lite` and preserved the operator's existing file and key. New checkouts using `.env.example` still default to explicit offline mock mode. Both Designer and RAI Examiner share this server-only configuration; the candidate agent is independent.

Stop the backend with Ctrl+C. Open the existing file from PowerShell:

~~~powershell
Set-Location E:\Testah\backend
notepad.exe .\.env
~~~

Replace only `REPLACE_WITH_YOUR_GEMINI_API_KEY` on the `TESTAH_RAI_API_KEY` line with your Google Gemini API key, save, and close Notepad. Do not send the key in chat or put it in frontend files, `VITE_` settings, browser forms, database columns or committed files. Keep each setting on one line with no duplicate keys. The RAI block is:

~~~ini
TESTAH_RAI_PROVIDER=gemini
TESTAH_RAI_MODEL=gemini-3.5-flash-lite
TESTAH_RAI_API_KEY=REPLACE_WITH_YOUR_GEMINI_API_KEY
TESTAH_RAI_TIMEOUT_SECONDS=30
TESTAH_RAI_MAX_OUTPUT_TOKENS=3000
TESTAH_RAI_MAX_RESPONSE_BYTES=131072
TESTAH_RAI_RETRIES=1
TESTAH_RAI_REPAIR_ATTEMPTS=1
TESTAH_RAI_GENERATION_SECONDS=90
TESTAH_RAI_MAX_GENERATION_WORKERS=2
TESTAH_RAI_MAX_EXAMINER_MESSAGES=6
~~~

Restart in the backend terminal. Process environment overrides `.env`, so remove any prior provider/model/key overrides in that terminal first (these commands do not print secrets):

~~~powershell
Set-Location E:\Testah\backend
Remove-Item Env:TESTAH_RAI_PROVIDER -ErrorAction SilentlyContinue
Remove-Item Env:TESTAH_RAI_MODEL -ErrorAction SilentlyContinue
Remove-Item Env:TESTAH_RAI_API_KEY -ErrorAction SilentlyContinue
.\.venv\Scripts\python.exe -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000
~~~

In a second terminal, verify safe metadata:

~~~powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health
Invoke-RestMethod http://127.0.0.1:8000/api/rai/configuration | Format-List
~~~

Expect `provider: gemini`, `model: gemini-3.5-flash-lite`, and `is_mock: False`. The dashboard and Generate with RAI page display this backend metadata. Configuration metadata alone does **not** verify credentials or a model call.

To verify actual generation in the UI, refresh the RAI configuration, select a registered agent, generate a new proposal and wait for `ready` / `validated` with Gemini provenance. Confirm and compile, then create a **new** assessment with RAI Examiner selected. After starting it with a connected candidate, inspect `rai.examiner.message_generated` events with `provider=gemini`; `rai.examiner.fallback` means that message used deterministic fallback. Old proposals and runs retain their frozen provider/model.

For the reproducible standalone sample walkthrough, start the clarification sample and API with the explicit local-sample gate as shown above, keeping `.env` provider selection (omit the earlier `$env:TESTAH_RAI_PROVIDER = "mock"` line). Then run:

~~~powershell
Set-Location E:\Testah
.\backend\.venv\Scripts\python.exe backend/scripts/check_rai.py --require-real-provider
~~~

This creates synthetic records and makes bounded real API calls. The flag requires a non-mock provider, a validated Designer proposal, and successful Examiner messages without fallback. Task 05.5 was credential-free; authenticated Task 05.5.1 Designer/compilation results are recorded in [the debugging report](docs/task05.5.1-verification.md).

### Switching providers and diagnosing errors

For offline testing, stop the API and set `TESTAH_RAI_PROVIDER=mock` in the existing `.env`, then restart. Key/model may remain configured but mock mode sends no provider requests. To return to Gemini, set `TESTAH_RAI_PROVIDER=gemini` and `TESTAH_RAI_MODEL=gemini-3.5-flash-lite`, ensure the key is set, and restart. Alternatively `$env:TESTAH_RAI_PROVIDER = "mock"` selects mock for just the current PowerShell process; remove that override before returning to `.env` selection.

The existing OpenAI adapter remains available with provider `openai`, an account-available Responses model supporting strict JSON, and an OpenAI API key in the same `TESTAH_RAI_API_KEY` setting. A key must match the selected provider. Gemini uses Google's official `generateContent` API with JSON Schema; [Google documents structured-output support for Gemini 2.5 Flash](https://ai.google.dev/gemini-api/docs/models/gemini-2.5-flash). That page lists deprecation/automatic routing effective December 1, 2026; account availability and future model changes require operator verification. Metadata is the requested model, not proof of the model Google ultimately routes to.

Missing/placeholder key or model produces `provider_not_configured`; 401/403 produces `provider_authentication_failed`; 404 produces `provider_model_unavailable`; other rejected HTTP requests produce `provider_http_error`. Rate limits/5xx exhaust bounded retries as `provider_transient_error`; network/deadline errors are `provider_unreachable` / `provider_timeout`. Truncated token-limited output is `provider_incomplete`; malformed JSON is `invalid_model_output`. Raw error bodies are not exposed. Check your Google API access, key restrictions, quota/billing and model availability. Google can report invalid keys as HTTP 400 (`provider_http_error`). Subscriptions are not API credentials.

Designer errors fail the proposal visibly and never switch to mock. Examiner errors retain Gemini provenance and append an explicit deterministic fallback event; the gateway keeps enforcing all financial rules. If generation times out, adjust the bounded timeout and generation deadline deliberately; the default `.env.example` remains 20/60 seconds, while this local Gemini block uses 30/90. Output limits are tokens and response bytes, separately enforced. See [RAI design](docs/rai-designer-examiner.md) for all bounds and [Task 05.5 verification](docs/task05.5-verification.md) for checks and limitations.

Task 05.5.1 fixes an attempt-deadline bug: a 30-second timeout with one retry previously allowed only 15 seconds per attempt. An actual structured Designer response took 20.5 seconds. The full configured deadline now covers all attempts/backoff without dividing the first attempt's budget. Final failure logs contain only provider, safe code and HTTP status; no raw body, exception message, key or prompt is logged. `provider_network_denied` identifies an OS socket-permission failure; `provider_dns_error`, `provider_protocol_error` and `provider_transport_error` distinguish DNS and non-connectivity transport problems from `provider_unreachable`. HTTP 400/401/403/404/429/5xx retain their separate HTTP classifications and status in safe backend logs.

Run the backend from an ordinary PowerShell terminal with permitted outbound access. A backend launched inside a restricted coding-agent sandbox can receive `PermissionError [WinError 5]` even when a direct request from another terminal works. Do not disable TLS, DNS pinning or network policy to work around that restriction. For stable live verification, use the startup command above without `--reload`; editing backend files under auto-reload cancels active jobs as `generation_worker_stopped`. Old failed proposals are durable evidence: submit a new proposal after fixing/restarting rather than resuming them.

### Diagnosing persistent Designer timeouts

Settings are loaded once when FastAPI is created. Editing `.env` does not update a running process. On every startup, `RAI effective configuration` logs the actual PID, provider/model, non-secret generation limits, whether a key is configured, and names of process overrides (never their values). Check this line after restarting; a proposal also freezes the provider limits active when it was submitted. Keep `TESTAH_RAI_TIMEOUT_SECONDS` within 1–60 and `TESTAH_RAI_GENERATION_SECONDS` within 5–180. The persistent-timeout investigation preserved the operator's existing `.env` values of 60/180; it did not raise defaults or validation limits.

`RAI timing` logs correlate phases by proposal ID: queue wait, manifest construction, provider request/retry/deadline, DNS/TCP/TLS/upload/response-header wait, JSON parsing, schema validation, repair scheduling, Blueprint compilation and final environment compilation. Only scalar timings, counts, statuses and safe exception classes are recorded. Raw prompts, provider output, headers and credentials are excluded. A timeout with `source=provider_deadline` is the total provider budget; `source=httpx` includes the HTTPX timeout class; `worker_timeout` identifies the separate generation deadline. The provider's deadline is shared by all retry attempts and backoff, not multiplied by retry count.

The instrumented original request waited for Gemini response headers until the 60-second deadline, with no retries, repairs or parsing. For Designer only, the Gemini adapter now keeps output types, required fields, enums and closed objects in the decoding schema, while placing scalar/array bounds and patterns in descriptions. The original Pydantic contract and full Blueprint compiler still enforce every constraint before readiness and compilation. Examiner decoding and all financial authorization remain unchanged. This follows Google's [schema-complexity guidance](https://ai.google.dev/gemini-api/docs/structured-output); it reduces grammar work without accepting invalid environments. One same-model live comparison improved from a 60-second timeout to a 6.04-second provider call and successfully compiled an environment. Provider-internal queuing versus schema-compilation time is not observable, and this is not a latency guarantee. See the [persistent-timeout report](docs/rai-timeout-verification.md) for exact timings, record IDs, tests and limitations.

Generation mode, deterministic blueprint validation, customer-message selection and deterministic purchase enforcement are separate. Model responses and conversational approval cannot buy anything. Phase 8 adds deterministic scoring from committed evidence; RAI never assigns numeric scores. Ownership authorization, production distributed workers, global concurrency/cost controls and production egress/operations remain future requirements. The current approved task is publication/deployment preparation only; see the runbook for hosted-demo boundaries.


If Windows denies pytest's default profile temp directory, use a fresh workspace-local directory (from backend):

~~~powershell
$phase5TestTemp = 'E:\Testah\tmp\pytest-phase5-' + [guid]::NewGuid().ToString()
if (Test-Path -LiteralPath $phase5TestTemp) { throw 'Expected a new test directory.' }
.\.venv\Scripts\python.exe -m pytest --basetemp $phase5TestTemp -o "cache_dir=$phase5TestTemp-cache"
~~~

This runs the full suite with a fresh cache and requires no operating-system permission changes. Do not reuse this temporary path for user files; pytest owns its base temp directory.
