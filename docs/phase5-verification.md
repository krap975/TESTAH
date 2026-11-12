# Phase 5 verification

Verified November 2, 2026 (America/Los_Angeles) on the existing Windows/Python 3.12.16/Node 22.11.0 workspace. Phase 5 only is implemented. No application dependency was added. RAI Designer and Examiner are integrated with the existing Environment Engine, controller, gateway, simulation and evidence persistence.

## Results

| Check | Result |
| --- | --- |
| backend: `.\.venv\Scripts\python.exe -m pytest --basetemp <fresh workspace path>` | **341 passed** using fresh workspace-local temporary and cache directories; 257 existing cases plus 84 Phase 5 cases |
| new provider/service cases | 28 provider-adapter cases and 54 Designer/Examiner cases passed |
| new actual candidate-HTTP cases | Generated environment completed in both deterministic and RAI customer modes, including a real sample clarification question |
| backend: `.\.venv\Scripts\python.exe -m alembic upgrade head` | Existing development database upgraded to `0005_rai` |
| backend: `.\.venv\Scripts\python.exe -m alembic check` | No new upgrade operations detected, including final check |
| backend: `.\.venv\Scripts\python.exe -m alembic current` | `0005_rai (head)` |
| migration regression | Fresh/repeated upgrade, drift check, downgrade to base and re-upgrade passed in the full suite |
| frontend: `npm.cmd run build` | Strict TypeScript and Vite production build passed; 62 modules; rerun after final UI wording |
| root: `.\backend\.venv\Scripts\python.exe backend/scripts/check_rai.py` | Separate API/sample processes: mock proposal generated/validated/reviewed/compiled; duplicate requests safe; both customer modes completed one simulated purchase each |
| root: `.\backend\.venv\Scripts\python.exe backend/scripts/check_rai.py --verify-restart` | Proposal, generation evidence, environment, both run outcomes/modes and ordered run events matched after actual API process restart |
| root: `.\backend\.venv\Scripts\python.exe backend/scripts/check_assessments.py --verify-restart` | All six retained Phase 4 outcomes/event logs/source snapshots preserved across the Phase 5 migration, with only explicit additive default metadata accepted |
| root: `node tmp/rai-ui-smoke.mjs` | Six React/real-API flow groups passed: generate/review; compile/provenance; RAI run; deterministic run; error/retry; dashboard/manual navigation |

The original 340-case full run passed before the final credential-redaction case was added. The final 341-case suite passed in 599.74 seconds with fresh workspace-local temporary and cache directories after Windows denied access to pytest's default profile directories. The only final warning was the unchanged Starlette/AnyIO deprecation. Intermediate runs exposed a test timing race: a shared one-second deadline could fire before the expected count limit on a busy disk. The fixture now retains one second for the dedicated slow-connector timeout case and allows ten seconds for the other failure classifications; expected outcomes and production limits are unchanged. The retained final output is tmp/phase5-final-suite.log. The provider adapter is tested using mocked HTTP: no live paid LLM request was made and no API credit availability or model quality was claimed.

## Coverage and observed behavior

The provider suite verifies the official Responses request shape, strict object schemas, all-required/nullable schema normalization, request model/token/store settings, checked-IP pinning with original TLS SNI/Host, secret header placement, no tools, transient-only bounded retries, rejected redirects/auth/non-transient errors, total timeout, missing credentials, media/encoding/size limits, refusals/incomplete output, strict duplicate-key/non-finite JSON rejection and deterministic mock output.

Designer coverage includes valid variation compilation, unchanged canonical templates/tools/policies/evidence, invalid category/currency/money/IDs/references, unsupported/duplicate challenge selections and parameters, no surviving alternative, prompt/approval injection, non-synthetic output, capability uncertainty and conservative defaults, public preview privacy, request idempotency, bounded repair with no raw prior-output replay, clear provider failures without silent mock substitution, concurrent idempotent compilation, expired generation leases, admission limits, sanitized output persistence, redaction of bare credentials from complete authentication headers, and database writes during a provider await to prove that no writer transaction is retained.

Examiner coverage includes all message intents, fixed budget/currency rendering, no financial/message authority fields in model output, private-context exclusion, untrusted candidate text, deterministic fallback on malformed plans/timeouts/unreachable provider, separate message limits, approval/payment authority separation, cancellation fencing of late output, no database transaction during provider await, and conditional challenge requests that cannot mutate anything before the existing declared trigger. Existing Phase 4 safety, state, network, isolation, event ordering and cancellation regressions remain passing.

The new real candidate-HTTP tests use the same fixed local sample gate and Phase 2 wire protocol. They generate a mock proposal from a registered agent, compile it, start the existing controller, receive a clarification question, execute the six gateway tools, recover from price/shipping changes, inspect simulated payment status and complete. RAI mode records message plans and accepted/fulfilled challenge requests. Deterministic mode records no Examiner activity. Both retain generation provenance and contiguous event sequences across fresh app instances.

## Separate-process and React verification

The PowerShell walkthrough explicitly set TESTAH_RAI_PROVIDER=mock and TESTAH_SAMPLE_BEHAVIOR=clarification. It printed `mock / deterministic-mock-v1 (MOCK: no LLM used)` and completed:

| Customer mode | Run ID | Ordered events |
| --- | --- | --- |
| deterministic | `1f5a2f61-c92b-47b8-8b94-19ee6c857236` | 67 |
| rai / mock provider | `32760dd9-119f-41a4-9a9f-af1b467e8714` | 76 |

Each recorded exactly one simulated capture. The saved baseline is `tmp/phase5-http-records.json`. Restart verification stopped the verified API process, confirmed port 8000 was closed, started a new API process successfully, and only then compared the complete baseline. Proposal timestamps remained stable under repeated compilation. Source environment snapshots stayed unchanged during both runs.

The React harness bundled the real application and used real API fetches. It selected a registered connected sample, displayed explicit mock mode and capability uncertainty, generated a ready proposal, checked all five products/four merchants/two challenge summaries, confirmed compilation, created and completed both customer modes, inspected actual event counts and one capture each, exercised outage/retry recovery, and navigated the primary dashboard and retained manual workflow. The clean final run retained proposal `f04cd7f6-f4f8-49bc-a9ee-d21aadacfed6`, RAI run `e5da88ea-303a-48f7-9cc3-e0173409cbc3`, and deterministic run `f46adb4d-72c9-49a1-a78a-c3c8f6ce4d9d`.

The first UI outage assertion used a Node-realm Error while the app correctly displayed a generic unknown-error message. The harness was corrected to throw a browser-realm TypeError and rerun successfully; no application workaround was added. Local manual verification also encountered intermittent sandbox process/ACL/file-helper failures. Required commands were rerun with approved escalation, and actual server startup/restart was confirmed rather than inferred from a launch attempt.

Browser inventory returned no available browser/native surfaces (browser access host/native pipe unavailable). Therefore **visual/mobile inspection and real-browser CORS inspection remain unverified**. Backend CORS regressions, production build, real HTTP and React DOM behavior passed. DOM harness dependencies and temporary process/log/baseline files stay under ignored tmp/ and do not change application dependencies.

Synthetic verification agents, proposals, environments and runs intentionally remain inspectable. Preliminary UI attempts also retained their own clearly named synthetic records. No pre-existing records were removed. Proposal/assessment references prevent deleting their agents; proposal deletion/retention management is outside this phase.

## Exact manual reproduction

Full four-terminal startup and real-provider configuration are in [README](../README.md#phase-5-generate-with-rai). Use the existing backend venv; do not use a subscription login as an API key.

1. Stop a manually running sample before full pytest so port 9001 is free. From backend run `.\.venv\Scripts\python.exe -m pytest`, `.\.venv\Scripts\python.exe -m alembic upgrade head` and `.\.venv\Scripts\python.exe -m alembic check`. From frontend run `npm.cmd run build`.
2. From root set `$env:TESTAH_SAMPLE_BEHAVIOR = "clarification"` and run `.\backend\.venv\Scripts\python.exe -m uvicorn sample_agents.main:app --host 127.0.0.1 --port 9001`.
3. From backend set TESTAH_ENVIRONMENT=development, TESTAH_ALLOW_LOCAL_SAMPLE=true and TESTAH_RAI_PROVIDER=mock. Run `.\.venv\Scripts\python.exe -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000`.
4. From frontend run `npm.cmd run dev`.
5. From root run `.\backend\.venv\Scripts\python.exe backend/scripts/check_rai.py`. Verify the printed mock label and completed runs in both modes.
6. Stop only the API with Ctrl+C. Restart with the same database/provider settings. Run `.\backend\.venv\Scripts\python.exe backend/scripts/check_rai.py --verify-restart`.
7. Open `http://127.0.0.1:5173/rai`. Generate a proposal for a registered agent, review the provider label/uncertainty/preview, Confirm and compile, select customer mode, create an assessment and Start assessment. Inspect ordered generation, Examiner, challenge, denial, tool, payment and termination evidence. Use Advanced / Manual environments to retain the original workflow.
8. For real generation, explicitly configure provider=openai, an account-available Responses model with strict structured output, a server-side API key and available quota, then restart the API. The README provides secure PowerShell key input. A failed Designer proposal remains failed; it never silently becomes mock. Examiner failures produce visible deterministic-fallback events. Live paid-provider verification was not performed here.

## Architecture choices and deviations

RAI Designer and Examiner have separate private prompts, output schemas and responsibilities. The Designer submits a strict controlled design to the existing compiler plus full Blueprint validation; no canonical JSON template is changed. The Examiner returns a versioned intent/tone/preference/challenge plan. Testah renders the message from public facts, preventing arbitrary approval or financial claims from entering customer messages.

The source architecture's RAI authorization wording conflicts with this task's explicit prohibition. Phase 5 follows the task: only the existing deterministic gateway grants scenario approval. Conditional challenge requests preserve the existing trigger points and automatic challenge behavior; they cannot force early mutations, suppress a frozen challenge or change parameters at runtime. Generation evidence requires a pre-run proposal event table; its linked evidence is copied into the normal assessment log with source-event references.

Existing registration has only free-text capability descriptions and no structured candidate tool advertisement. The API/UI expose that uncertainty and identify the registry as an expected interface, not a verified candidate capability. Blueprint v1.0 supports only headphones and product display names, so no new categories or separate product-description schema were silently introduced. Generation/customization is an additive validated input contract, not a redefinition of blueprint/registry 1.0. The public environment/run metadata gains explicit source/customer-mode fields; old rows backfill manual/deterministic defaults.

`docs/architecture.md`, protocol schemas, canonical templates/fixtures, the tool registry, financial gateway, simulated payment provider, deterministic scoring expectations and package dependencies are preserved. Architecture SHA-256 remains `8A511319F1C5002FA8C008C69FDF9EA9DEB1765DB763F8930C05A8623129A5D8`. Git metadata is absent in this workspace; the manifest below records task edits rather than claiming a Git diff.

## Changed files

| Area | Files |
| --- | --- |
| RAI services | `backend/app/rai/provider.py`, `backend/app/rai/prompts.py`, `backend/app/rai/designer.py`, `backend/app/rai/examiner.py` |
| Controlled compiler/contracts | `backend/app/environments/designed.py`, `backend/app/environments/service.py`, `backend/app/environments/runtime.py`, `backend/app/schemas/environment_design.py`, `backend/app/schemas/rai.py`, `backend/app/schemas/environments.py`, `backend/app/schemas/assessments.py` |
| Persistence/migration | `backend/app/models/rai.py`, `backend/app/models/environment.py`, `backend/app/models/assessment.py`, `backend/app/models/__init__.py`, `backend/alembic/versions/0005_rai.py` |
| Integration/API/config | `backend/app/api/rai.py`, `backend/app/api/agents.py`, `backend/app/main.py`, `backend/app/core/config.py`, `backend/app/execution/controller.py`, `backend/app/execution/service.py`, `backend/.env.example` |
| Tests/walkthrough | `backend/tests/test_rai_provider.py`, `backend/tests/test_rai.py`, `backend/tests/test_execution.py`, `backend/tests/test_database.py`, `backend/scripts/check_rai.py`, `backend/scripts/saved_records.py`, `backend/scripts/check_assessments.py`, `backend/scripts/check_environments.py` |
| Frontend RAI flow | `frontend/src/pages/RaiDesignerPage.tsx`, `frontend/src/components/RaiProposalDetails.tsx`, `frontend/src/hooks/useRaiDesigner.ts`, `frontend/src/services/rai.ts`, `frontend/src/types/rai.ts` |
| Frontend integration | `frontend/src/main.tsx`, `frontend/src/components/Layout.tsx`, `frontend/src/pages/Dashboard.tsx`, `frontend/src/pages/AssessmentsPage.tsx`, `frontend/src/components/AssessmentDetails.tsx`, `frontend/src/components/EnvironmentDetails.tsx`, `frontend/src/hooks/useAssessments.ts`, `frontend/src/services/assessments.ts`, `frontend/src/types/assessments.ts`, `frontend/src/types/environments.ts` |
| Sample/docs | `sample_agents/main.py`, `sample_agents/README.md`, `AGENTS.md`, `README.md`, `docs/rai-designer-examiner.md`, `docs/phase5-verification.md` |

## Remaining limits

The application is still a local/trusted workspace without authenticated ownership authorization. Local asyncio generation/execution workers are bounded but not durable distributed jobs; crashes expire leases and do not automatically resume work. SQLite serializes writers, and generation concurrency is per process. Production requires owner-scoped APIs, durable workers/sweepers, global concurrency/cost/rate controls, production database/egress/DNS safeguards, retention/backups and monitoring. Redaction is not universal personal-data DLP.

The Examiner intentionally uses composed message plans rather than free-form prose; generation quality and semantic objective coherence require human review and real-model evaluation. API account/model availability, billing and paid live requests remain unverified. Real payments, final scoring, React Flow, SSE, AG Grid, APIMatic and deployment remain out of scope. Stop after Phase 5.


### Windows test-directory workaround used for final verification

The escalated runner could not enumerate the existing profile pytest temp directory. No ACLs were changed. From backend, create a fresh path inside the workspace and pass it explicitly:

~~~powershell
$phase5TestTemp = 'E:\Testah\tmp\pytest-phase5-' + [guid]::NewGuid().ToString()
if (Test-Path -LiteralPath $phase5TestTemp) { throw 'Expected a new test directory.' }
.\.venv\Scripts\python.exe -m pytest --basetemp $phase5TestTemp -o "cache_dir=$phase5TestTemp-cache"
~~~

This is the full suite, with no skips or selected-test filter. It leaves isolated test artifacts under ignored tmp/. Both directories were fresh to avoid existing runner-specific ACL problems; no ACLs were altered. The new redaction case checks complete Bearer/Basic header credentials and bare echoes, including surrounding/multiple spaces. The key itself and extracted credential components are masked before LLM input or evidence.
