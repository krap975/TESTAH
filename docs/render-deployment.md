# GitHub publication and Render deployment

Prepared November 12, 2026. No GitHub repository or Render resource has been
created. Applying a Blueprint or creating a service starts deployment; wait for
explicit approval. This runbook covers the approved **shared workspace for trusted
judges/demo users**. Invitees share all records and operations; separate user accounts
and tenant isolation are future work.

## Architecture and commands

| Service | Root directory | Build | Start / publish |
| --- | --- | --- | --- |
| React Static Site | frontend | npm ci && npm run build | Publish dist; rewrite /* to /index.html |
| FastAPI Python Web Service | backend | pip install -r requirements.txt | python scripts/start_render.py |
| PostgreSQL 16 | Managed database, same region as API | None | Internal URL in TESTAH_DATABASE_URL |
| Sample Python Web Service | Repository root (leave Root Directory empty) | pip install -r sample_agents/requirements.txt | uvicorn sample_agents.main:app --host 0.0.0.0 --port $PORT --workers 1 --no-access-log |

The [root Blueprint](../render.yaml) defines free temporary-demo resources,
Python 3.12.16, Node 22, one API worker, and auto-deploy off. No paid resource or
persistent disk is required. Render [web services](https://render.com/docs/web-services)
must bind to 0.0.0.0 and PORT; both launch commands do so. The sample's root must
include backend/app/schemas/protocol.py for its shared wire-schema import.

Do not add reload, extra workers or replicas. Persisted PostgreSQL evidence survives
restarts, but in-process assessments do not automatically resume. Avoid deploying
during active runs. The [original docs-only example](../deploy/render-docs.example.yaml)
and APIMatic artifacts remain available independently.

## 1. Publish GitHub source after approval

This folder initially had no .git directory, local history or remote. A new local
main repository is prepared. Other copies and remote/deleted histories are outside
this audit. Review [the verification report](deployment-verification.md) first.
Do not use git add -f or include ignored runtime files.

From E:\Testah in PowerShell:

~~~powershell
git -c safe.directory=E:/Testah status --short
.\backend\.venv\Scripts\python.exe backend/scripts/audit_publication.py --history
git -c safe.directory=E:/Testah log -1 --oneline
~~~

The exact-directory, per-command safe.directory option handles metadata created by
the sandbox account; it does not change global Git trust settings.

After explicit publication approval, create an **empty** GitHub repository in your
chosen account (no generated README/license/gitignore). Use public visibility only
when approved. Substitute the actual owner/repository below:

~~~powershell
git -c safe.directory=E:/Testah remote add origin https://github.com/YOUR_OWNER/YOUR_REPOSITORY.git
git -c safe.directory=E:/Testah remote -v
git -c safe.directory=E:/Testah push -u origin main
~~~

Inspect an existing origin before changing it; do not force-push. The prepared
initial commit includes the application, quickstart, candidate specification and
original APIMatic ZIP/provenance. GitHub CI includes a disposable PostgreSQL service.
Publishing source does not configure or deploy Render.

## 2. Connect and configure Render after approval

Connect the approved GitHub repository via Render's Git provider integration.
Use New > Blueprint with render.yaml, or create the equivalent services manually.
Review plan, region, resource preview and environment values before Apply/Create.
Auto-deploy off prevents later pushes from redeploying automatically; initial
creation still provisions and deploys.

For manual setup:

1. Create PostgreSQL 16 in Oregon, or keep API and database in another identical
   region. Disable external database access (ipAllowList: []).
2. Create the sample service and set its private token. Health path: /health.
3. Create the API with the internal database URL, tokens, exact frontend origin
   and public HTTPS API callback origin. Health path: /api/health.
4. Create the Static Site. Set VITE_API_BASE_URL to the actual API origin without
   /api. Add the SPA rewrite and headers from the Blueprint.
5. Confirm assigned URLs, update CORS/callback/frontend values, and manually
   redeploy after changes. Frontend values require a rebuild.

Blueprint sync:false values are requested during initial creation. Choose service
names or reserved custom domains first, then use the **actual** assigned origins.
If the frontend URL is not yet available during manual API setup, configure an
HTTPS origin you control temporarily and replace it before browser use.

See the [Blueprint specification](https://render.com/docs/blueprint-spec),
[static sites guide](https://render.com/docs/static-sites), and
[PostgreSQL connections](https://render.com/docs/postgresql-creating-connecting).
Local schema validation does not establish account-level plan/resource validation.

## 3. Environment variables

Configure secrets only in Render's Environment panel/secret storage. Never commit
them, place them in VITE_ values, paste them in URLs or publish screenshots/logs.

| API variable | Required setting |
| --- | --- |
| TESTAH_ENVIRONMENT | production; required by launcher |
| TESTAH_DATABASE_URL | PostgreSQL internal connection URL, injected by Blueprint |
| TESTAH_CORS_ORIGINS | Exact JSON array, e.g. ["https://YOUR_FRONTEND.onrender.com"]; no trailing slash/wildcard/localhost |
| TESTAH_WORKSPACE_ACCESS_TOKEN | Distinct random 32-512 printable ASCII characters; Blueprint generates it |
| TESTAH_MONITOR_TOKEN | Different random token for SSE |
| TESTAH_PAYMENT_OPERATOR_TOKEN | Different random token for payment inspection/reconciliation/capture |
| TESTAH_ALLOW_LOCAL_SAMPLE | false; production rejects the development bypass |
| TESTAH_AGENT_SECRETS | Server-only JSON map of reference names to complete Authorization header values |
| TESTAH_PAYPAL_CALLBACK_BASE_URL | Exact HTTPS API origin, e.g. https://YOUR_API.onrender.com; no path/query/credentials |
| TESTAH_RAI_PROVIDER | Start mock; switch to gemini for the Gemini demo |
| TESTAH_RAI_MODEL | A model available to your Gemini API account; confirm the previously verified model is still available |
| TESTAH_RAI_API_KEY | Gemini API key, backend only |
| TESTAH_PAYMENT_MODE | Start simulated; switch to paypal_sandbox for Sandbox checkout |
| TESTAH_PAYPAL_ENVIRONMENT | sandbox, the only supported value |
| TESTAH_PAYPAL_CLIENT_ID / TESTAH_PAYPAL_CLIENT_SECRET | Sandbox app credentials, backend only |
| TESTAH_PAYPAL_MERCHANT_ID | Optional exact business merchant pin; blank uses the app's merchant |
| TESTAH_PAYPAL_API_BASE_URL | Keep https://api-m.sandbox.paypal.com, the only supported origin |
| PYTHON_VERSION | 3.12.16 |
| PORT | Assigned by Render |

The Blueprint deliberately starts in explicit mock/simulated modes. Add Gemini
and PayPal settings privately to the API service before the separately approved
live demo, then restart/redeploy. Old runs retain their frozen modes. The Blueprint
does not contain or automatically transfer local provider credentials.

Generate independent random tokens with a password manager or local secret
generator. Share workspace access only privately with trusted invitees; distribute
monitor/payment tokens only to their operators. Workspace access stays in browser
memory and travels in X-Testah-Workspace-Token on REST/SSE requests. Lock/refresh
clears it. Existing monitoring/payment Bearer tokens remain separate requirements.
This is a shared workspace, not separate user accounts.

Frontend: VITE_API_BASE_URL is the API origin only; NODE_VERSION=22 and
SKIP_INSTALL_DEPS=true (the build already runs npm ci). All VITE_ values are public.
Production builds always show the runtime access form.
VITE_REQUIRE_WORKSPACE_ACCESS=true can test it with the development server.

Other supported limits and defaults remain in
[backend/.env.example](../backend/.env.example): agent time/size limits, bounded RAI
generation/retries, execution limits, monitoring limits and Sandbox approval wait.
Do not relax SSRF, timeout or financial checks for hosting.

## 4. PostgreSQL and startup migrations

Create a **new cloud database**. Never upload, reset, delete or migrate the existing
local SQLite database. Psycopg handles Render postgres:// and postgresql:// URLs;
explicit postgresql+psycopg:// also works. Reused pool connections use pre-ping, and every PostgreSQL session uses UTC so existing execution timestamps retain their meaning.
Keep credentials private. Use the same-region internal connection; approved external
maintenance requires the external TLS URL and a narrow temporary IP allowlist.

The startup launcher acquires a session-level PostgreSQL advisory migration lock
and runs Alembic upgrade head on the same connection **before** opening the HTTP
port. A failure exits safely without serving. Builds do not run migrations.
Current head stays 0008_evaluation; no business-schema migration was added.

This launcher supports Free services without a shell or paid pre-deploy command.
On paid compute, an approved alternative is a pre-deploy command
python -m alembic upgrade head; keep a single migration owner. Paid compute is not
needed just for migrations. See [deployment behavior](https://render.com/docs/deploys).

For local PostgreSQL validation, TESTAH_TEST_POSTGRES_URL must name a new empty
**disposable** database. From backend, run python -m pytest tests/test_postgresql.py -q.
It refuses a database containing tables and performs downgrade/upgrade only in the
disposable database. Without that variable the test is explicitly skipped.

## 5. Independent sample

Register https://YOUR_SAMPLE.onrender.com/agent with connection_mode=external.
Use public HTTPS port 443, not an internal Render hostname or local_sample mode.
Preserve public-IP DNS validation, checked-IP pinning, TLS verification and disabled
redirects/proxies. Never add automatic retries of candidate POSTs.

TESTAH_SAMPLE_TOKEN is the **complete expected Authorization value**, with no
automatic Bearer prefix. In the API's private TESTAH_AGENT_SECRETS map, use a reference
such as SAMPLE_DEMO whose value is that exact token. In agent registration, choose
Authorization as the header name and SAMPLE_DEMO as the server secret key (authentication.secret_key).
The connector passes the mapped header value unchanged. The sample receives no
database URL, hidden rules, Gemini key or payment credentials.

Use TESTAH_SAMPLE_BEHAVIOR=safe. Warm /health before connecting or running on free
compute; a cold start can exceed the default 10-second candidate deadline.

## 6. Hosted verification after approval

Record actual URLs, commit, timestamps and observed results. No public deployment
success is established by local checks.

1. Open frontend /, /agents, /reports and a deep route directly. Refresh to check
   the SPA rewrite. Verify access, lock and refresh behavior.
2. Verify /api/health reports database connected. Operational routes must reject
   missing/wrong workspace tokens. Confirm exact-origin preflight succeeds and an
   unrelated origin fails. Swagger/raw OpenAPI and dev diagnostics must be absent.
3. Warm the sample; register its public HTTPS /agent endpoint with the server-secret
   reference and run the protocol-only connection test.
4. In mock/simulated mode, create/compile an environment and explicitly start one
   assessment. Check committed SSE with the separate monitoring token, ordered
   evidence, deterministic score/certification, AG Grid, replay and JSON export.
5. Configure Gemini, restart and generate a **new** proposal. Require validated
   Gemini provenance; examiner fallback must remain visibly labeled.
6. Configure Sandbox-only credentials/mode and HTTPS callback origin. Restart and
   create a **new** assessment; existing runs keep their original payment mode.
7. Enter the separate payment operator token. Start explicitly, open the stored
   Sandbox approval URL and approve using a Sandbox **personal buyer**, distinct
   from the business merchant. Return to the backend callback: existing
   state/order/expiry validation remains authoritative, and requires no workspace
   header on the PayPal redirect.
8. Return to the checkout panel and explicitly reconcile/capture. Verify the
   recorded capture status, amount/currency, order/capture references and linked
   payment evidence/report. Order creation and redirects alone are not success.
   Unknown outcomes require existing reconciliation, never a new purchase/replay.
9. With no active run, restart and verify persisted records/evidence/evaluations.
   Interrupted jobs do not resume automatically. Review logs, bundles and exports
   for secrets without publishing private runtime files.

Only Sandbox test money is allowed. No real PayPal mode is implemented. This task
does not perform new live Gemini calls or Sandbox transactions. Obtain approval
before remote deployment/demo verification.

## 7. Free-plan limitations

Render's [Free service documentation](https://render.com/docs/free) states:

- Web services sleep after 15 idle minutes and take about a minute to wake.
  Backend/sample cold starts can exceed browser/candidate deadlines.
- Two free web services share 750 instance hours per workspace/month; running
  both continuously all month exceeds that allowance.
- Filesystems are ephemeral: keep application persistence in PostgreSQL, not SQLite.
- Free PostgreSQL has 1 GB, expires after 30 days and has no backups. Export evidence
  before expiry or approve a paid database.
- Free web services have no shell, one-off jobs, persistent disks or horizontal
  scaling and may restart. Bandwidth/build and external-traffic limits also apply.

No paid service is introduced. Paid always-on compute would avoid sleep, and paid
PostgreSQL adds retention/backups; obtain cost approval before changing plans.
Use free resources only for a temporary supervised demo with manual warm-up.

Per-user ownership, global abuse/cost admission controls, distributed durable jobs,
additional infrastructure egress controls and production retention/monitoring
remain future work. Do not advertise this as a multi-tenant production service.
