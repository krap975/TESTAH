# Phase 3 verification

Verified on November 1, 2026 (America/Los_Angeles), with Python 3.12.16, Node 22.11.0, npm 10.9.0, and Windows PowerShell. No new dependencies were required.

## Delivered scope
Three approved versioned commerce templates; strict integer-money blueprints; clearly synthetic catalog/personas/merchants; six schema-only tool definitions and argument validation; four declarative challenge kinds; private versioned evidence expectations; independent persisted environment snapshots and template references; create/list/detail APIs; and the Environments dashboard.

No RAI, assessment loop, agent tool execution, runtime challenge activation, payment, scoring, monitoring, reporting integration, or deployment was implemented. Status compiled means a validated data snapshot, not an agent-tested assessment or runtime readiness.

## Commands and results

| Command | Directory | Result |
| --- | --- | --- |
| .\.venv\Scripts\python.exe -m pytest | backend | 160 passed, one unchanged third-party deprecation warning |
| .\.venv\Scripts\python.exe -m alembic upgrade head | backend | Existing database upgraded from 0002_agents to 0003_environments |
| .\.venv\Scripts\python.exe -m alembic current | backend | 0003_environments (head) |
| .\.venv\Scripts\python.exe -m alembic check | backend | No new upgrade operations detected |
| npm.cmd run build | frontend | Strict TypeScript and Vite production build passed; 53 modules |
| .\.venv\Scripts\python.exe -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000 | backend | API startup completed |
| .\backend\.venv\Scripts\python.exe backend/scripts/check_environments.py | root | Two distinct customized snapshots created and verified independent through real HTTP |
| .\backend\.venv\Scripts\python.exe backend/scripts/check_environments.py --verify-restart | root | Saved snapshots identical after stopping and restarting the API process |
| node tmp/environments-ui-smoke.mjs | root | Seven real-API React integration checks passed |
| node tmp/agents-ui-smoke.mjs | root | Five Phase 2 React management regressions passed |
| node tmp/ui-smoke.mjs | root | Four Phase 1 React regressions passed |
| .\backend\.venv\Scripts\python.exe sample_agents/integration_check.py | root | Independent sample message/tool_call/completed exchanges and status persistence passed |
| Invoke-RestMethod http://127.0.0.1:8000/api/health | root | status=ok, database=connected |
| Invoke-WebRequest -UseBasicParsing http://127.0.0.1:5173/environments | root | HTTP 200 |

The frontend build was rerun after final form wording changes. The last backend run includes all blueprint/evidence validation changes. The architecture document remains byte-identical to the supplied source Markdown reference.

## Backend coverage
The 160 tests include all existing Phase 1/2 behavior plus template loading, deterministic compilation across all three supported currencies and boundary budgets, strict integer money, invalid currencies/versions, unique identifiers, entity/challenge references, modified or unsupported tools, mandatory policies, private evidence consistency, static feasibility, synthetic flags, environment creation and safe previews, pagination, forbidden unrestricted state updates, persistence across app instances, and independent JSON snapshots.

The registry suite checks all six Phase 2-compatible ToolDefinition structures, strict argument schemas, unknown fields, missing required fields, unknown/disallowed tools, invalid money/currency, duplicate cart items, and fresh schema copies. No test executes a financial tool.

Migration tests cover a fresh temporary database, reference seeding, repeated upgrade, schema drift, downgrade, and re-upgrade. The working development database was upgraded separately without deleting agent records. Each environment test uses its own temporary database. A trusted internal test changes one snapshot JSON and confirms another remains unchanged; the public API has no corresponding mutation endpoint.

## Live integration and UI behavior
The HTTP check created two saved environments with distinct UUIDs and different currency/budget values, checked deterministic scaled products, verified local response modifications could not change either saved record, and saved their original API representations under ignored tmp/. The API process was then stopped and restarted with the same database URL; the --verify-restart check confirmed both representations persisted unchanged.

The React DOM check bundled the real application and used Fetch against the running API. It loaded all three templates, rejected fractional minor units, created one environment from each template (GBP 12345, USD 8001, EUR 15000 minor units), displayed five products/four merchants/six schemas and compiled/not-assessed status, verified safe preview privacy, confirmed later customizations did not change the first snapshot, and exercised connection-error/retry states.

The UI and HTTP checks intentionally leave their clearly named synthetic environments in the development database, because no environment deletion API is part of Phase 3. Agent regression checks remove only their own temporary agent records. The My Agents harness initially matched another existing agent's connected status while waiting; the temporary harness was corrected to scope the selected-agent panel and rerun successfully. No application workaround was required.

All DOM harnesses and jsdom remain under ignored tmp/ and add no application dependency. No synthetic fixture value is presented as a real merchant record, agent result, live execution event, or completed payment.

## Remaining limitations
Browser access host and native UI automation are unavailable. Visual/mobile inspection and real-browser CORS inspection were not performed. HTTP, backend CORS tests, production build, and DOM behavior checks passed.

The API remains a local/trusted application without login or tenant authorization. owner_scope_id is an indexed nullable server-controlled preparation field, not implemented multi-tenant isolation. External connector deployment egress restrictions and operational controls remain requirements from Phase 2.

Currencies are limited to USD/EUR/GBP and creation budgets to 1000-1000000 minor units. Prices are nominal deterministic simulation values, not real offers or FX conversions. Templates and registry version 1.0 must not be silently redefined; future version changes require compatible readers/migrations for old snapshots.

Static blueprint validation does not replace future live gateway policy checks, readiness validation, runtime state transitions, challenge events, or deterministic evidence evaluation. Exact triggers and expectations are persisted privately and excluded from API previews. The existing Starlette/AnyIO BlockingPortal deprecation warning does not fail tests.

## Next boundary
Phase 4 may build on persisted authoritative environment IDs/snapshots, frozen tool schemas, validated challenge declarations, private evidence versions, and the existing candidate connector. It must preserve immutable source environments and create separately controlled run state, permission checks, and committed evidence. Phase 4 has not started.

