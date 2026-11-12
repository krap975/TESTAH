# Phase 2 verification

## Delivered scope
Persistent agent CRUD and case-insensitive name conflicts; strict framework-agnostic protocol 1.0; bounded HTTPX connector with checked/pinned destinations; reference-based server authentication; development-only fixed sample exception; independently running sample; and real-data My Agents registration, list/detail, edit/delete, and connection tests. No assessment loop, RAI, tools, payments, scoring, or sponsor integration was implemented.

## Commands and observed results
Commands ran from the existing workspace with Python 3.12.16, Node 22.11.0, and npm 10.9.0. Dependencies needed for Phase 2 were already installed; HTTPX and AnyIO are now declared runtime dependencies rather than relying on a test/transitive installation.

| Command | Directory | Result |
| --- | --- | --- |
| .\.venv\Scripts\python.exe -m pytest | backend | 84 passed, one third-party deprecation warning |
| .\.venv\Scripts\python.exe -m alembic upgrade head | backend | Existing Phase 1 database upgraded successfully |
| .\.venv\Scripts\python.exe -m alembic current | backend | 0002_agents (head) |
| .\.venv\Scripts\python.exe -m alembic check | backend | No new upgrade operations detected |
| npm.cmd run build | frontend | Strict TypeScript and Vite production build passed; 49 modules |
| uv pip check --python backend/.venv/Scripts/python.exe | root | Installed environment compatibility checked |
| .\backend\.venv\Scripts\python.exe -m uvicorn sample_agents.main:app --host 127.0.0.1 --port 9001 | root | Standalone sample startup completed |
| .\.venv\Scripts\python.exe -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000 | backend | API startup completed with explicit development sample settings |
| .\backend\.venv\Scripts\python.exe sample_agents/integration_check.py | root | message, tool_call, completed exchanges and persisted status passed; temporary record deleted |
| node tmp/agents-ui-smoke.mjs | root | Five My Agents integration checks passed |
| node tmp/ui-smoke.mjs | root | Four Phase 1 React integration checks passed |
| Invoke-RestMethod http://127.0.0.1:8000/api/health | root | status=ok, database=connected |
| Invoke-WebRequest -UseBasicParsing http://127.0.0.1:5173/agents | root | HTTP 200 |

## Automated coverage
The 84 backend tests cover registration, whitespace/type/length validation, invalid and unsafe URLs, duplicate names, persistence across app instances, pagination, updates/deletion, secret-reference handling, local gate enforcement, all response variants, strict request/response schemas, correlation IDs, malformed/duplicate/nonfinite JSON, unadvertised tools, bounded response bodies and malformed/oversized Content-Length, compression rejection, timeouts, DNS failure, private/mixed/transition-address answers, numeric-IP pinning with original TLS hostname/Host, redirects, authentication rejection, secret echoes, metadata-only edits preserving valid connection results, and concurrent changes during a test. Existing health, CORS, sanitized errors, and migration regressions pass. Migration tests use temporary databases and exercise fresh initialization, repeated upgrade, drift check, downgrade, and re-upgrade.

The separate real HTTP integration starts Testah and the sample as different Uvicorn processes. It exercises every sample response and database status persistence without an LLM. Its temporary agent is removed afterward.

The temporary React/DOM harness bundles the real application and uses the running API. It verifies invalid external URL feedback, real registration/list/details, Test Connection against the sample, persisted edits, and confirmed deletion. The existing harness still verifies health rendering, Reports navigation, unavailable state, and retry recovery. These harnesses and jsdom remain under ignored tmp/ and add no application dependencies. An initial harness readiness check ran before React mounted; the harness was corrected to await the controls. No application workaround was required.

## Limitations
Browser host and native UI automation remain unavailable. Visual, mobile, and real-browser CORS inspection could not be performed. HTTP checks, backend CORS tests, strict frontend build, and DOM integration passed. The third-party Starlette/AnyIO BlockingPortal deprecation warning is unchanged from Phase 1 and does not fail tests.

External requests were tested with deterministic mock transports and DNS, not arbitrary public agent services. The real network test uses only the explicitly enabled fixed local sample. Deployed routing, trust stores, DNS infrastructure, network egress deny rules, rate limits, and service isolation still need deployment validation. Application-level DNS pinning does not provide complete SSRF protection against an unsafe deployment network.

The API intentionally remains a trusted local development service with no login or tenant isolation. Secret values reside only in server settings; SQLite stores references. A public deployment must add appropriate access controls and operational secret management. Tool-call arguments are structurally validated and tool names checked against advertised definitions; financial policy and tool-specific semantic validation remain gateway responsibilities in a later phase. A completed candidate reply is not an evaluated assessment result.

## Phase boundary
Phase 3 may reuse agent IDs and metadata, safe connection-test results, the strict protocol, and the isolated connector when defining approved environment/tool contracts. It has not started.

