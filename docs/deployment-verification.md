# Publication and deployment verification

Prepared November 12, 2026. **Nothing has been pushed or deployed.**

**GitHub publication: READY for approval.**
**Render: READY for an approved, supervised shared-workspace demo deployment.**
Public accessibility and hosted end-to-end acceptance are **NOT VERIFIED**.
This is not a readiness claim for a multi-tenant production service.

## Scope and resulting behavior

The existing application is preserved. Deployment preparation adds a production
workspace perimeter, PostgreSQL connection handling, startup migrations, a
Render Blueprint, security dependency fixes, repeatable audit/CI checks and the
[publication/deployment runbook](render-deployment.md).

The user approved a shared workspace for trusted judges/demo users. Invitees
share records and operations; there are no separate tenant accounts. The workspace
header does not replace the existing monitoring/payment Bearer tokens. Public
health checks and the existing capability-protected PayPal return route remain
reachable without workspace headers. Development retains its loopback workflow.

No payment authorization, scoring rules, assessment transitions, evaluator policy,
candidate wire model or PayPal SDK was changed. No new business migration was added.
The current schema head remains 0008_evaluation. No live Gemini request or new
PayPal Sandbox transaction was performed by this preparation task.

## Files added or modified

| Files | Reason |
| --- | --- |
| .gitignore | Exclude runtime databases, environment files, keys, logs, caches, local tooling and backups; retain safe examples and original public artifacts |
| .gitattributes | Consistent source line endings while preserving candidate/APIMatic artifact bytes |
| .gitleaks.toml | Default scanner rules plus three narrowly scoped false-positive rules: an exact Authorization parameter placeholder, provenance SHA-256 checksums and a historical synthetic proposal UUID |
| .github/workflows/checks.yml | Backend/frontend checks, disposable PostgreSQL integration and publication scans; no deployment job |
| render.yaml | Free temporary-demo static frontend, API, PostgreSQL 16 and independent sample service; auto-deploy off |
| README.md | Current readiness links, accurate shared-workspace boundary, Python 3.12 setup and preserved local startup instructions |
| backend/.env.example; frontend/.env.example | Blank workspace token setting, HTTPS callback guidance and public frontend configuration |
| backend/requirements.txt; backend/requirements-dev.txt; sample_agents/requirements.txt | Psycopg 3.3.9; compatible security pins FastAPI 0.135.0, Starlette 1.3.1 and pytest 9.0.3; PayPal SDK unchanged |
| backend/app/core/config.py | Production requires PostgreSQL, a distinct workspace token and exact HTTPS CORS origins; validate configured HTTPS callback origins |
| backend/app/core/workspace_access.py | Constant-time shared workspace perimeter before operational HTTP routing |
| backend/app/main.py | Wire the perimeter/CORS header; disable operator Swagger/raw OpenAPI in production; keep dev diagnostics development-only |
| backend/app/database/session.py | Normalize Render PostgreSQL URLs to psycopg, pre-ping pooled connections and force UTC sessions |
| backend/alembic/env.py; backend/scripts/start_render.py | Run Alembic on the advisory-lock connection before binding one Uvicorn worker to 0.0.0.0 and PORT; fail closed |
| backend/app/rai/provider.py | Add the workspace credential to existing known-secret redaction; generation logic/prompts unchanged |
| backend/scripts/audit_publication.py | Read-only path, known-secret, pattern, ZIP, build-output and reachable-history checks; never print matched values |
| backend/scripts/export_candidate_openapi.py | Normalize framework-added optional validation-error metadata so the published candidate specification remains byte-for-byte unchanged |
| backend/tests/test_deployment.py; backend/tests/test_postgresql.py | Production boundary, credential separation/redaction, PostgreSQL migration/transaction/UTC/persistence and launcher checks |
| backend/tests/test_provider_reliability.py | Valid isolated production settings for diagnostics absence checks; no test database defaults to saved application data |
| backend/tests/test_assessment_stream.py | Measure the stream's dedicated pool independently from background evaluator polling |
| frontend/src/components/WorkspaceAccess.tsx; frontend/src/services/workspaceAccess.ts | Runtime access entry/lock; token in memory only |
| frontend/src/main.tsx; frontend/src/components/Layout.tsx; frontend/src/styles.css | Integrate the access form and truthful shared-demo labels |
| frontend/src/services/api.ts; frontend/src/services/assessmentStream.ts | Add the workspace header to REST/SSE while preserving narrower operator headers |
| frontend/vite.config.ts | Render builds reject missing, loopback, non-HTTPS or non-origin API URLs |
| frontend/tests/workspace-access.test.tsx | Check REST/SSE token transport, removal and separate payment/monitor credentials |
| sample_agents/main.py; sample_agents/README.md | Add a lightweight health endpoint and document public HTTPS deployment; protocol decisions unchanged |
| docs/render-deployment.md; docs/render-readiness.md; this report | Current deployment instructions, security/test evidence, manual actions and limits |

The developer quickstart, candidate OpenAPI, original APIMatic ZIP, generated
portal/provenance and earlier verification documents remain included. The canonical
architecture and all protected original APIMatic files match their baseline hashes.

## Repository and security audit

- The supplied folder initially had no Git repository, commits, branch or remote.
  A new local main repository was initialized. No prior local history was available;
  external/deleted repositories and prior sharing cannot be audited from this folder.
- Reviewed all nonignored publication files, original ZIP contents and the frontend
  production bundle. Exact configured local secret values were read only in memory
  for matching, never printed. No actual credential exposure was found.
- Gitleaks 8.30.1 was downloaded from its official release and verified against the
  published checksum. Six initial findings were reviewed: a generated parameter
  placeholder, three provenance hashes, a synthetic proposal UUID, and the same
  placeholder inside the ZIP. Scoped path/value rules retain normal secret scanning.
- Actual .env files, saved SQLite data, logs, caches, virtual environments,
  node_modules, temporary verification evidence and build output are excluded.
  Safe .env.example files and sponsor/developer artifacts are included.
- No credential rotation is required by the evidence found in this available source
  audit. This does not assess previously published copies or unavailable histories.
- The installed dependency audit initially found advisories in Starlette and pytest.
  They were resolved with compatible pinned updates. The final installed backend
  audit and npm audit report zero known advisories. The PayPal SDK remains 2.4.0.
  The [Starlette form-parser advisory](https://github.com/Kludex/starlette/security/advisories/GHSA-82w8-qh3p-5jfq)
  is one of the reviewed upstream findings.
- No credentials or private runtime records are part of the publication set.
  GitHub CI uses only explicit disposable test credentials and mock/simulated providers.

## Verification results

| Check | Actual result |
| --- | --- |
| Final full backend invocation | 600 passed, 4 failed at the existing 15-second commerce HTTP polling deadline under parallel load |
| Serial recheck of all 12 real HTTP cases | 12 passed with the original deadlines unchanged, including all four full-run failures |
| Unique backend cases covered | All 604 passed across those two invocations; this is not a claim of a single all-green full-suite run |
| Frontend tests | 45 passed |
| Strict TypeScript | Passed as part of the production build |
| Frontend production build | Passed with RENDER=true and an explicit HTTPS API origin |
| Bad Render frontend API origin | HTTP loopback configuration rejected safely |
| SQLite migrations | Isolated upgrade/head check/downgrade/upgrade test passed in the backend suite |
| PostgreSQL 16.11 | Fresh-database migrations/check/round trip, UTC session, JSON/lifecycle claims, cancellation and restart persistence passed |
| Production startup/restart | Final launcher smoke verified migrations before serving, assigned port, workspace access, CORS allow/deny, hidden docs and persisted record retrieval after restart |
| Candidate contract and APIMatic integrity | Passed; published bytes/provenance preserved after dependency updates |
| Render Blueprint validation | Application Blueprint and original docs-only example pass Render's published JSON Schema locally |
| Dependency consistency | pip check passed |
| Dependency advisory checks | Final installed backend and frontend npm audit: zero known advisories |
| Publication secret/path checks | Passed; local values, ZIPs and production bundle checked without printing secrets |
| Browser visual walkthrough | Unverified: browser host failed twice; no visual result is claimed |
| GitHub CI / Render account-level checks | Not run: no push, provisioning or deployment was authorized |
| Hosted HTTPS/SSE/Sandbox/Gemini assessment | Not run; requires approved deployment and private configuration |

The first serial backend attempt additionally exposed the occupied fixed sample
port, an outdated production fixture, and a test assertion that counted the
background evaluator's pooled connection. The fixture and stream measurement were
corrected. The verified idle standalone sample was paused only for the fixed-port
HTTP checks and restored afterward. Temporary xdist/execnet tools used for the full
rerun live only in ignored tmp; they are not application dependencies.

All business checks used mock provider boundaries and simulated or mocked Sandbox
operations. The dedicated PostgreSQL tests use new disposable databases, not the
saved application SQLite database. Full business regression coverage primarily
uses SQLite; hosted PostgreSQL/Sandbox acceptance still needs the runbook walkthrough.

Ignored evidence includes tmp/deploy-backend-final.xml, tmp/deploy-http-final.xml,
tmp/deploy-backend-summary.json, tmp/deploy-postgres-utc.xml, dependency-audit JSON,
redacted scanner reports and production startup logs. Those private runtime files
must not be committed.

## Local data preservation

No local database deletion, reset, replacement or schema migration was performed.
Read-only integrity and foreign-key checks pass. Local .env files, canonical
architecture and original APIMatic artifacts retain all 40 protected baseline hashes.

An unchanged database-content snapshot cannot be claimed: the live application
remained available, and additional records appeared during the task. The read-only
before/after table hashes therefore differ. Detailed counts/hashes remain in ignored
tmp; no attempt was made to roll back, overwrite or publish those runtime records.
A diagnostics test briefly used the default local connection before being corrected
to an explicit isolated database; its diagnostic route made no record-creation calls.
The new agents/environments/payment records cannot be attributed to that diagnostic
route. Subsequent final checks explicitly isolate test databases.

## Render architecture and limits

The [Blueprint](../render.yaml) uses a static frontend, one Python API service,
same-region PostgreSQL 16 and a separately authenticated public HTTPS sample.
PostgreSQL is the persistent data owner; no ephemeral SQLite or paid disk is used.
Startup migrations are serialized with a PostgreSQL advisory lock.

Use the [runbook](render-deployment.md) for exact roots/build/start commands, every
required environment variable, URL/CORS/callback setup, sample authentication,
migration behavior and the end-to-end Sandbox procedure. General per-user ownership,
distributed durable jobs and global abuse controls remain outside this shared-demo scope.

No paid resources are introduced. Free web services sleep, and Free PostgreSQL
expires after 30 days without backups; the two web services share the workspace's
instance-hour allowance. Review [Render's current Free limits](https://render.com/docs/free)
before approving the temporary demo. Paid retention/always-on services need cost approval.

## Required manual actions and remaining gates

1. Approve the GitHub account/repository, visibility and push separately. No remote
   is configured. Exact publication commands are in the runbook.
2. Approve Render provisioning/deployment separately; review the free resource plan.
3. Configure actual frontend/API/sample origins and all private tokens, Gemini and
   Sandbox credentials in Render. Rebuild the frontend after API-origin changes.
4. Map the sample token privately in TESTAH_AGENT_SECRETS and register the external
   HTTPS endpoint. Preserve DNS/IP pinning, TLS verification and zero candidate POST retries.
5. Perform browser navigation, access rejection, SSE reconnect and fresh PostgreSQL
   persistence checks, then the explicit Gemini and Sandbox buyer-approval/capture
   walkthrough. Record actual public URLs/results before claiming deployment success.
6. Plan data export before free-database expiry. Do not use this configuration as an
   unrestricted multi-tenant production service.

No public GitHub repository was created, no code was pushed, and no Render service
was provisioned or deployed. No real-money PayPal operation is permitted.
