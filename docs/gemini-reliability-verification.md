# Gemini reliability investigation and verification

Work performed November 4, 2026. Scope remains Phase 5: provider operation, development diagnostics and Designer failure handling. No payment authorization, scoring, reports, blueprint/template semantics or later-phase functionality was changed. The existing server-only `.env`, key, database and old proposal evidence were preserved.

## Confirmed causes and evidence limits

| Observation | Evidence and conclusion |
| --- | --- |
| Current `provider_network_denied` | The original serving API, PID **11568**, successfully resolved Google, then failed TCP connect in about 5–9 ms with `httpx.ConnectError` wrapping permission denial. Its own proposal traces reported this category; no HTTP response or TLS handshake occurred. Its ancestry included Codex's restricted command runner. This is a runtime permission problem, not a slow model response. |
| Different results from different launch environments | The original restricted chain was Codex PID 1116 → sandbox command runner 13056 → PowerShell 2788 → virtual-environment launcher 3604 → Python/API 11568. After explicitly approved execution, the chain was Codex 1116 → PowerShell 13432 → CMD 11356 → virtual-environment launcher 19684 → Python/API **8904**, without the sandbox command runner. An actual diagnostic executed inside API 8904 established verified HTTPS and authenticated Gemini generation. |
| Inherited environment marker | `CODEX_SANDBOX_NETWORK_DISABLED` remained present even in approved execution which demonstrably reached Gemini. It cannot establish the effective OS token/network policy by itself. Startup logs/diagnostics label it as a declaration. The launcher warns, changes no privileges, and does not treat the marker as proof of either connectivity or denial. |
| Historical `provider_unreachable` | [Task 05.5.1](task05.5.1-verification.md) reproduced `ConnectError → httpcore.ConnectError → OSError → PermissionError [WinError 5]`, which the older broad handler mislabeled unreachable. Old database rows which retained only a generic code cannot prove every original exception cause retrospectively. |
| Historical `provider_timeout` | [The timeout investigation](rai-timeout-verification.md) established a stale 30-second serving configuration despite a 60-second `.env`, and separately a request that completed DNS/TCP/TLS/upload then spent 59.702 seconds waiting for Gemini headers before the 60-second provider deadline. An earlier adapter divided the total deadline between retries, producing a premature 15-second attempt cutoff. Those already-fixed defects were audited and their regression coverage preserved. |
| Provider-internal cause of historical latency | Upstream response waiting is established; Google-internal queuing, schema compilation or decoding cannot be distinguished from Testah's observations. The prior Designer schema optimization is retained with full server-side validation. Increasing bounds again would not establish a root cause or fix permission denial. |
| Interrupted jobs | Prior verification recorded `generation_worker_stopped` after auto-reload. The documented default launcher now omits reload, and shutdown regression coverage verifies failed state, released lease and absent partial blueprint/environment. |

No current evidence indicated DNS, proxy, TLS, key/model rejection or HTTP status failure during the successful live checks. Those are distinct tested classifications, not claimed live incidents.

## Actual runtime and configuration

The final API was restarted with the final adapter code as **PID 22360** (virtual-environment launcher parent 20744), using approved execution and the same CMD launcher/environment settings. A real Examiner run subsequently succeeded in this process. The earlier diagnostic/Designer records below belong to serving PID 8904. There is one Uvicorn application without reload or multiple workers. Designer asyncio tasks and the execution worker/Examiner run inside that application process; DNS resolver threads inherit its permissions. There is no provider sidecar, browser request carrying a key, proxy relay, or alternate Gemini integration.

The frontend's Vite listener is a separate Node process (observed PID 12252 under npm/CMD and Codex's frontend command runner). It serves the client and calls local FastAPI; it performs no authenticated Gemini calls. Restricted pytest processes use isolated temporary databases and mocked provider HTTP; their successes do not prove live API connectivity. The standalone clarification sample is an independent loopback process on port 9001, started temporarily for live Examiner verification and stopped before pytest.

Effective settings from the serving application:

| Setting | Value |
| --- | --- |
| Environment source | `E:\Testah\backend\.env`, absolute settings path; no `TESTAH_RAI_*` process override names |
| Python | `E:\Testah\backend\.venv\Scripts\python.exe`; Windows process inspection also identifies the underlying CPython executable under `tmp/python/` |
| Provider / requested model | `gemini` / `gemini-3.5-flash-lite`; `is_mock=false` |
| API key | Configured server-side; value never printed, returned or persisted into proposal/run configuration |
| Provider total operation deadline | 60 seconds, shared by all attempts/backoff |
| Generation job deadline | 180 seconds, including scheduling and bounded repair |
| Output limits | 3000 tokens / 131072 raw response bytes |
| Transient retries / design repairs | 1 / 1 |
| Generation workers | 2 per API process |
| Local sample gate | Existing `.env` has development mode and `TESTAH_ALLOW_LOCAL_SAMPLE=true`; neither was edited |
| Transport policy | Public DNS validation/all-answer rejection, checked-IP pinning, original Host/TLS SNI and certificate verification; redirects and environment proxy inheritance disabled |

Model metadata is the requested identifier; it does not prove Google's internal serving-model routing. No timeouts/defaults/validation bounds were raised.

## Adapter audit and changes

Both Designer and Examiner continue to resolve one `GeminiProvider` through `get_provider`. The fixed official generateContent endpoint accepts only validated model path components. The key is sent only in `x-goog-api-key`; no key appears in URLs, payloads, database configuration or browser inputs. HTTPX creates and closes a fresh transport/client per attempt, disables transport retries/proxies/redirects and revalidates DNS for every explicit attempt. Only generation operations can retry; no candidate or commerce POST replay was added.

Transport classification now traverses typed causes, contexts and nested exception groups. Permission errors and OS permission codes take precedence even inside timeout/DNS wrappers. DNS retains its typed cause internally, while candidate-facing errors remain the same safe strings. TLS and proxy failures are separate non-retryable categories. Quick connection errors, actual HTTPX timeouts and 429/5xx responses retain bounded retries inside the original operation deadline; refusal, invalid output, policy, permission, TLS, proxy and DNS errors fail without repeated network attempts. Raw exception text and provider error bodies remain excluded from responses/logs.

Gemini parsing still requires one candidate, a valid model role, successful finish, text-only structured output, strict JSON, then independent Pydantic/Blueprint validation. A malformed non-string finish reason now returns `invalid_model_output` instead of raising an unhandled type error. Designer decoding preserves its prior schema-cost optimization; Examiner uses its original strict schema. Repair remains bounded and receives no raw invalid output. No deterministic safety policy is delegated to Gemini.

No database transaction spans a provider await. A failed/expired/cancelled generation never stores a partial design or environment. Explicit compilation independently revalidates the complete design and frozen blueprint, then commits the environment, proposal link and event atomically. Failed proposals cannot compile. Regression tests exercise denial, timeout, invalid response, successful generation/compile, explicit recovery, and shutdown during an in-flight generation. Examiner rendering, fallback evidence, cancellation fencing and purchase authority are preserved and exercised by existing tests plus the live run.

## Development diagnostics and UI

`POST /api/rai/diagnostics` requires `{"run_smoke_test":true}`. Its route and OpenAPI entry are installed only in development; test and production return 404. It requires JSON, rejects unapproved browser origins and allows one active diagnostic per API process. This is an unauthenticated loopback development capability, not a production administration API.

The check reports provider/model, key-presence boolean, actual PID/parent/Python/settings source, override names, effective bounds, check latency and fixed sanitized categories/messages. It returns no resolved IPs, proxy values, secrets, raw errors, prompts or provider bodies. A credential-free GET to the fixed Google host verifies HTTPS using the same adapter/transport policy; any HTTP status proves reachability, not authentication. If it succeeds, one authenticated strict-JSON smoke call is capped at 256 output tokens, zero retries and the configured provider deadline. The reachability phase is capped at `min(10, configured_timeout)` seconds. Failed connectivity skips the paid call; non-Gemini/mock selection explicitly skips both.

The Designer page invokes this only when the user presses its labeled button, which explains API usage. It displays each result separately and identifies the process/time scope. No paid check runs on startup or page load. A smoke success does not label a Designer proposal valid.

Failed proposal details show the persisted safe category and fixed actionable guidance. Retry uses the same failed proposal's registered agent input and a new generation job, preserving the failed evidence. Ambiguous submission failures retain their idempotency key for a subsequent attempt. Current form input state is not cleared on failure. Failed status never enables compilation. Configured mock mode stays explicit; Gemini failure never substitutes mock output.

## Live verification results

| Check | Observed result |
| --- | --- |
| Same-process HTTPS, API PID 8904 | **Passed**; HTTP 404 from the credential-free Google root probe; 1392.508 ms. This proves DNS/TCP/verified TLS, not successful generation by itself. |
| Same-process authenticated smoke, API PID 8904 | **Passed**; strict `{"ok":true}` generation; 20654.374 ms; no retry. |
| Real Designer | **Passed**, first attempt; 27.547 seconds measured by the API polling client, provider operation 26.486 seconds; original strict proposal validation and full Blueprint compilation passed. |
| Explicit environment compilation | **Passed**, including repeated compile returning the identical saved result and ordered proposal events 1–4. |
| Real Examiner, final API PID 22360 | **Passed**, completed run in 48.484 seconds; **3** Gemini-generated message events, **0** deterministic fallback events, **70** ordered evidence events, **1 simulated capture**. Source environment representation remained unchanged. This is not a score or a real payment. |

Retained records:

- Designer proposal: `3359f534-98b5-435e-ac07-e3fb7980b897`.
- Compiled environment: `781765dd-f1dc-4160-bbed-0d99eedb8c4b`.
- Examiner assessment: `d6c950a3-fbd2-4cad-ae0a-f08826bf647e`.
- Standalone synthetic sample agent: `9eeb3852-eedb-4d1e-a8f0-3884638a830e`.

Sanitized check results are saved locally in ignored `tmp/provider-diagnostics-real.json`, `tmp/designer-runtime-real.json` and `tmp/examiner-runtime-real.json`. Verification created synthetic records only; existing snapshots/history were not reset. Read the retained records to inspect them without another paid request.

## Automated verification

- Initial focused RAI/provider suite: **155 passed**.
- Final provider/parser/diagnostics regression selection: **71 passed**.
- Initial full run: **408 passed / 6 failed**. All six failures were timing-log capture assertions: earlier embedded Uvicorn servers changed parent logger propagation, so pytest's root capture missed INFO records which were visibly emitted to stderr. A scoped `capture_rai_logs` test fixture now captures/restores this logger directly. It does not change production logging or relax assertions.
- Logging-fix/worker/failure regression selection: **28 passed**.
- Final full backend suite: **416 passed, 0 failed**, one existing dependency deprecation warning, in **532.87 seconds**. This includes all existing health/safe-error/CORS, migration round-trip, protocol/network, real local HTTP, gateway/execution, Designer/Examiner and new reliability regressions. Temporary databases/cache: ignored `tmp/pytest-reliability-full-final` and its separate cache directory.
- Frontend: `npm.cmd run typecheck` **passed**; `npm.cmd run build` **passed**, including its TypeScript check.
- Alembic: `alembic check` **passed**, no new upgrade operations. Full-suite migration tests cover upgrade/downgrade/re-upgrade on isolated databases.
- Live health: HTTP 200, database connected. Frontend `/`, `/rai`, `/agents`, `/environments` and `/assessments` all returned HTTP 200 with the application root. Readback confirmed the live proposal remained compiled, the real Examiner run remained completed, and an old network-denied proposal remained failed with its category/message and no environment. Browser UI automation could not connect: native pipe and browser-access host were unavailable. No interactive browser result is claimed; frontend compilation and HTTP route checks are the available evidence.
- Existing dependency warning: Starlette references AnyIO's deprecated `BlockingPortal` alias.

## Reliable local startup

Use an ordinary authorized PowerShell terminal with outbound HTTPS permitted, or explicitly approved execution outside a restricted runner. Administrator privileges and security-policy changes are not required. The CMD launcher does not elevate, modify network permissions, change `.env`, reset the database or make a paid provider request. It fixes the working directory and avoids PowerShell script-execution-policy changes. Stop an existing API with Ctrl+C before starting another.

Terminal 1:

```powershell
Set-Location E:\Testah\backend
.\scripts\start_backend.cmd
```

Terminal 2:

```powershell
Set-Location E:\Testah\frontend
npm.cmd run dev
```

User-triggered check from terminal 3 (one small paid request when Gemini connectivity succeeds):

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/rai/diagnostics -ContentType application/json -Body '{"run_smoke_test":true}' -TimeoutSec 75 | ConvertTo-Json -Depth 10
```

Open `http://127.0.0.1:5173/rai`. Review the diagnostic's actual PID/settings before retrying a failed proposal. Editing `.env` requires an API restart. If provider/model/key process overrides appear, review them in that terminal; do not print key values or assume `.env` overrides them. A known denied runtime requires authorized launch correction, not longer deadlines or disabled TLS/DNS controls.

For local sample assessments only, the existing development gate must be enabled. In a separate terminal:

```powershell
Set-Location E:\Testah
$env:TESTAH_SAMPLE_BEHAVIOR = 'clarification'
.\backend\.venv\Scripts\python.exe -m uvicorn sample_agents.main:app --host 127.0.0.1 --port 9001
```

Stop the standalone sample before running pytest, whose real-HTTP fixtures own port 9001. Existing dependencies must already be installed and migrations applied as documented in the README.

## Changed files

Backend: `app/rai/provider.py`, `app/rai/diagnostics.py`, `app/rai/errors.py`, `app/rai/provider_diagnostics.py`, `app/rai/designer.py`, `app/execution/network.py`, `app/api/rai.py`, `app/api/rai_diagnostics.py`, `app/main.py`, `scripts/start_backend.cmd`, `.env.example`.

Frontend: `src/pages/RaiDesignerPage.tsx`, `src/components/RaiProposalDetails.tsx`, `src/components/RaiProviderDiagnostics.tsx`, `src/services/api.ts`, `src/services/rai.ts`, `src/types/rai.ts`.

Tests: `tests/conftest.py`, `tests/test_gemini.py`, `tests/test_rai.py`, `tests/test_rai_diagnostics.py`, `tests/test_provider_reliability.py`.

Documentation: root `README.md`, `docs/rai-designer-examiner.md`, this report. Temporary verification scripts/results are under ignored `tmp/`. `docs/architecture.md` is preserved.

## Remaining limits

Successful live calls establish access and contract compatibility at the observed times, not a Gemini availability/latency guarantee. Generic historical codes cannot reconstruct missing exception evidence. The inherited sandbox marker does not identify the precise OS enforcement mechanism. Direct network access remains required; proxy-only corporate environments must provide an authorized direct route or a separately designed approved transport, not silently enable environment proxies. Workers and admission limits are per-process, not a durable distributed queue or global quota. Development APIs still lack user authentication and must remain local/trusted. No production diagnostics/authentication system, real payments or Phase 6 work was introduced.
