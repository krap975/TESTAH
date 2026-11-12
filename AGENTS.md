# Testah engineering conventions

## Architecture and scope
Testah tests financial AI agents in controlled simulated environments and evaluates recorded behavior. Read docs/architecture.md completely before implementing a phase. Use one FastAPI modular monolith and a React client. Preserve existing functionality. Implement one approved scoped phase at a time; never begin the next phase automatically.

## Responsibilities
- app/api: thin HTTP routers and dependency wiring.
- app/core: settings and safe shared errors. app/database: engines and request-scoped sessions.
- app/models: SQLAlchemy entities and metadata. app/schemas: public Pydantic contracts.
- app/rai: separate constrained Designer/Examiner prompts, provider boundary, validated versioned outputs and bounded generation jobs.
- app/environments: blueprint validation, isolated scenario data, deterministic hidden challenges.
- app/execution: external connector, central execution state machine, controller and fenced worker claims.
- app/tools: versioned registry and transactional policy-enforcing gateway.
- app/payments: exclusive server-side owner of all future PayPal operations and credentials.
- app/events: append-only ordered evidence, committed with state before future streaming.
- app/evaluation: future deterministic versioned scoring from evidence.
- app/reports: future evidence-linked summaries. RAI may explain scores, never invent them.
- frontend/src/services: Fetch API client; hooks: request lifecycle; types: contracts; components: reusable UI; pages: route views.
- sample_agents: future protocol examples, never an execution backdoor.
Phase 4 implements isolated run execution, commerce tools, ordered durable evidence and an explicitly simulated server-side payment provider. Phase 5 adds controlled RAI proposals and customer-message plans. Phase 6 adds authenticated persisted-event SSE, React Flow monitoring, a timeline and read-only replay. Real payments/PayPal, evaluation and reports remain future work. Do not implement fake services or label simulation as real payment. Agent registration lives in app/agents. Read docs/execution-controller.md and docs/phase6-monitoring.md before changing execution, gateway, claims or events. Read docs/rai-designer-examiner.md before changing RAI. Stop after Phase 6; never begin a later phase automatically.

## Coding and persistence
Use Python 3.11+, type hints on public interfaces, snake_case Python, PascalCase React components, and strict TypeScript. Keep business logic in its owning module. Prefer existing dependencies and simple functions. Use Alembic for schema changes; never run metadata.create_all on application startup. Import new models into shared metadata for migration discovery. Sessions are request-scoped; writes require explicit transactions and rollback handling. Relative SQLite paths resolve against backend/.

## Security and truthful state
Never hardcode credentials or commit .env files. Maintain safe .env.example files. TESTAH_ settings are server-side. VITE_ values are public bundle contents and must never contain secrets. Do not expose secrets, raw sensitive inputs, hidden rules, or private prompts in responses or logs. CORS is an explicit allowlist and does not provide authorization.
All payment operations must pass through the server-side payment service and tool gateway. Keep scenario authorization separate from PayPal buyer approval. Never trust browser-provided amounts, payment status, or scores. Future external endpoints require SSRF controls and validated responses. Persist evidence before streaming. Never fabricate counts, live events, completed assessments, scores, or payment successes. Unimplemented features require explicit empty states.

## Commands and checks
From backend/ in PowerShell:

~~~powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m alembic check
~~~

From frontend/:

~~~powershell
npm.cmd ci
npm.cmd run build
npm.cmd run typecheck
~~~

Run meaningful tests of health success/failure, safe errors, CORS, and migration round trips. Run backend tests and frontend production build after relevant changes, fix failures, and report any unverified checks. Smoke-test browser health and navigation when possible. Update README and environment examples when configuration changes. Preserve docs/architecture.md.


## Phase 2 protocol and network boundary
Read docs/agent-protocol.md before changing agent integration. Preserve strict versioned schemas and matching response identifiers. Never retry an outbound POST automatically. Keep response/request size and total timeout limits. Revalidate every external destination, reject any non-public DNS answer, and pin the connection to a checked IP while preserving original TLS SNI/certificate verification. Disable redirects and environment proxy inheritance. Preserve the dedicated fixed local-sample gate; never turn it into an arbitrary host/port exception. Production requires additional network egress and API access controls.

Authentication configuration stores server-secret reference keys only. Never add credential values to database columns or management responses. Connection tests expose safe fixed metadata, not raw agent responses which may echo secrets. Changes to endpoint/authentication invalidate prior connection status. Keep unique normalized agent names, safe conflict errors, and optimistic concurrency checks. Connection probes never execute tools; Phase 4 assessment calls execute only through the fenced gateway.

Opt-in local integration (both servers must be started using README instructions), from root:

~~~powershell
.\backend\.venv\Scripts\python.exe sample_agents/integration_check.py
~~~

## Phase 3 environment boundary
Read docs/environment-engine.md before changing environments. Templates and synthetic fixtures are declarative versioned JSON. Use strict Blueprint validation, integer minor-unit money, supported currencies, valid references, registered schemas, mandatory policies, and a surviving affordable legal alternative. Never silently alter version 1.0 semantics. Compilation is deterministic except for new IDs and creation timestamps.

Every environment owns a full independent authoritative JSON snapshot and a versioned template reference. Never regenerate an old snapshot from current templates or expose unrestricted client JSON updates. Preserve the safe preview boundary: exact challenge triggers/mutations and evaluation expectations stay server-side. compiled means snapshot validation only; never label it assessed or runtime-ready.

The tool registry only validates metadata and argument shapes. It does not execute tools or replace future ownership, live state, authorization, approval binding, or financial checks. owner_scope_id is server-controlled future preparation; nullable scope is not multi-tenant authorization. Future runs must use isolated run state and leave source blueprints intact.

Real HTTP integration from root (creates two saved local snapshots):

~~~powershell
.\backend\.venv\Scripts\python.exe backend/scripts/check_environments.py
~~~

After restarting the API with the same database:

~~~powershell
.\backend\.venv\Scripts\python.exe backend/scripts/check_environments.py --verify-restart
~~~

## Phase 5 RAI boundary
Designer output passes controlled customization and the existing full Blueprint validation. Templates, tools, mandatory policies and canonical evidence remain immutable. Examiner output is a strict versioned message plan rendered from public facts, never financial authority. Model inputs exclude hidden triggers/evaluation and credentials; candidate/catalog text is untrusted data. Challenge requests wait for existing deterministic triggers. Mock mode must remain visibly labeled. Provider retries apply only to bounded generation; never replay financial actions. Proposal/run evidence commits before future streaming.
