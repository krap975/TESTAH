# RAI Designer and RAI Examiner — Phase 5

Phase 5 adds two separate constrained services around the existing Environment Engine and execution controller. RAI proposes designs and customer-message plans. Deterministic code validates blueprints, applies declared challenges, grants scenario approval, enforces purchases, simulates payment, and determines execution completion. RAI never computes a score or performs a financial action.

## Modes and provider boundary

`TESTAH_RAI_PROVIDER=mock` is the default. The deterministic mock produces repeatable designs/message plans without an LLM or API credentials. APIs, proposal previews, compiled environment provenance, run metadata, and generation/execution events identify mock mode explicitly. Mock output is not real LLM intelligence. Manual environments retain generation_mode=manual; deterministic customer mode invokes no Examiner provider.

Real modes use `TESTAH_RAI_PROVIDER=gemini` or `openai`, an explicitly configured `TESTAH_RAI_MODEL`, and server-only `TESTAH_RAI_API_KEY`. Both Designer and Examiner resolve the selected provider through the same factory, using separate private prompts and versioned output schemas.

The Gemini adapter uses HTTPX at the fixed official `https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent` endpoint. A validated `gemini-...` model name is a path component, never an arbitrary URL. Authentication uses the `x-goog-api-key` header, never a query parameter. It sends `systemInstruction` separately from bounded `untrusted_data`, `candidateCount=1`, `responseMimeType=application/json`, `responseJsonSchema`, and `maxOutputTokens`. `gemini-2.5-flash` supports structured output and is the requested local model. Thinking is disabled for this exact model (`thinkingBudget=0`, `includeThoughts=false`) to reserve the token budget for JSON; thought parts/signatures, if returned, are discarded. Only one candidate with `finishReason=STOP` is accepted; text parts are concatenated and parsed strictly. Blocks/refusals, truncation, function calls, malformed envelopes, duplicate keys and non-finite numbers fail. See Google's [generateContent contract](https://ai.google.dev/api/generate-content) and [Gemini 2.5 Flash capabilities](https://ai.google.dev/gemini-api/docs/models/gemini-2.5-flash). The model page lists deprecation/automatic routing effective December 1, 2026; the saved model is the requested identifier, not a verified serving-model identity.

The OpenAI adapter remains available at `https://api.openai.com/v1/responses` using `store=false`, strict JSON schema in `text.format`, and bounded `max_output_tokens`. All object fields are required in the provider schemas; nullable fields represent optional values. Pydantic independently validates every response after transport parsing. Wrong content types/encoding and incomplete or ambiguous output are rejected. Reasoning items are ignored and never persisted. The existing adapter follows the [official OpenAI structured-output contract](https://developers.openai.com/api/docs/guides/structured-outputs).

No API key is accepted from the frontend or stored in proposal/run records. Candidate endpoint/auth configuration is excluded from LLM inputs. The adapter uses the existing public-DNS validation and checked-IP pinning while preserving original TLS SNI/certificate checks and Host. Redirects, environment proxies and HTTP transport retries are disabled. Each explicit generation retry revalidates DNS. There is no configurable arbitrary provider URL.

Only transient generation failures (429, 5xx, network errors and bounded attempt timeouts) are retried, up to the configured count. A total provider-operation deadline includes all attempts/backoff. These are generation POSTs; the candidate connector still never retries a POST, and no approval, checkout or payment is replayed. A refusal or non-transient HTTP error fails immediately. Designer failure does not silently switch to mock. Examiner failure may use the explicitly recorded deterministic fallback.

Task 05.5.1 removes division of that deadline by retry count. A generation may use the full remaining total budget; retry capacity does not reduce its first attempt to half the configured time. Quick transient failures can still retry within the same total deadline. Exhausted HTTP errors retain their status, including 429 versus 5xx. Socket permission denial is non-retryable `provider_network_denied`; DNS lookup failure is `provider_dns_error`; HTTP protocol/other transport errors are `provider_protocol_error` / `provider_transport_error`. Only actual network errors map to `provider_unreachable`. Failure logs contain provider, safe code and HTTP status, never raw exception messages/bodies/headers, credentials or prompts.

ChatGPT, Claude or Gemini subscriptions are not credentials for this adapter. Operators must configure API access and confirm available quota/billing independently. No subscription-derived API credits are assumed. Live paid-provider calls were not part of credential-free verification; the real adapter is exercised with mocked HTTP.

## RAI Designer and capability uncertainty

The current registration schema stores a free-text description, not a structured candidate capability/tool-advertisement record. The Designer captures a sanitized snapshot of that stored description and labels it **self-declared and unverified**. It never invents verified capabilities. The prompt receives Testah's registry interface as the expected assessment interface, explicitly not evidence of the candidate's tool support.

Missing or unrecognized commerce evidence adds an uncertainty and forces the conservative `budget_constrained_purchase` template. Commerce-related description words are only a selection hint, not proof. Descriptions suggesting merchant trust or price/shipping comparison can select the other existing templates. These inputs are untrusted data under fixed private Designer instructions; embedded commands cannot add executable permissions.

`EnvironmentDesign` is a strict, versioned proposal schema. The browser supplies only registered agent ID and request key; it cannot submit a trusted design/Blueprint. The provider can customize:

- One existing template/version; synthetic customer name, description, preferences and objective.
- Supported currency USD/EUR/GBP and budget 1000–1000000 integer minor units.
- Existing products' display names and positive integer prices; existing merchants' display names and nonnegative shipping fees.
- A subset of the selected template's existing challenges and optional positive integer price/shipping increases, at most the scenario budget.

Blueprint v1.0 supports only headphones and has product display names rather than a separate product-description field. Phase 5 preserves those semantics. Product/merchant IDs, membership, availability, verification, checkout capability, attributes, mandatory policies, all six tool definitions, and evidence-rule contents remain server-controlled. New entities, currencies/categories, executable tools, arbitrary mutations and hidden evaluation rules are rejected. Descriptive generated copy is conservatively screened for instruction/credential/approval claims; this filter is not the financial authority.

The existing compiler first builds the selected canonical template. A new Environment Engine adapter applies only those allowed field variations to a fresh copy, selects canonical challenge declarations, retains all four mandatory base evidence expectations and each selected challenge's exact recovery expectation, then runs the existing full `Blueprint` validation. It validates IDs/references, integer money, unchanged schemas and policies, challenge consistency and an affordable legal alternative surviving all selected mutations. Canonical JSON templates/fixtures are never edited.

Invalid output gets at most one repair cycle by default. Repairs receive the same safe manifest and attempt number, not raw invalid output or unrestricted errors. Repeated invalid output yields a clear failed proposal. Successful redacted structured output, validation result, provider/model metadata, capability uncertainty and a private validated draft snapshot are persisted. Raw invalid bodies and full prompts are discarded.

## Proposal jobs, approval and compilation

Alembic `0005_rai` adds `rai_proposals` and `rai_proposal_events`, environment provenance columns and backwards-compatible Examiner fields on assessments. Existing environments backfill manual provenance; existing runs backfill deterministic customer / provider=none / empty private config. Existing blueprints and event payloads are unchanged.

Proposal states are `generating -> ready -> compiled`, or `generating -> failed`. `ready` is a validated preview, not a saved compiled environment. The explicit Confirm and compile action performs independent validation again and inserts an ordinary environment through the existing Environment Engine persistence boundary. Its frozen draft must exactly match recompilation; changed/corrupt definitions are rejected. Template reference rows must exist. Compilation and its proposal event/reference commit atomically. Repeated compilation returns the same environment and leaves the visible saved timestamp/evidence unchanged.

`(agent_id, request_key)` is unique. Duplicate generation submissions return the original job without another provider request. Successful UI submission consumes the key; a network failure retains it for retry. Failed/expired jobs require an explicit new key to try a new generation. Per-process admission limits bound active jobs (default two); excess new work returns 503 with a fixed retry message. There is no unbounded in-memory backlog.

Workers use a durable lease and token-fenced updates. Proposal mutations and sequence allocation start with a transactional UPDATE, as in Phase 4. No transaction spans a provider await. Generation duration includes scheduling time; cancellation/shutdown or expiry records a failed job rather than pretending a proposal is ready. Reads/lists/new submissions recover expired generation leases. Jobs do not automatically resume after a process crash. These in-process workers are local-development mechanisms, not a durable distributed job queue or a global cross-process concurrency limit.

## RAI Examiner: versioned message plans

Assessment creation accepts `examiner_mode=deterministic` (default) or `rai`. Existing clients omitting it preserve Phase 4 behavior. RAI runs freeze provider selection, requested model and non-secret provider limits. API keys remain process settings, never frozen into database JSON. Run responses show customer mode, configured provider and requested model.

The controller calls the Examiner for the initial customer message, a candidate conversational response, and after a challenge mutation. Ordinary tool continuations keep the existing fixed continuation. The existing run duration, turn, message-response, tool, repetition and candidate-HTTP limits still apply. A separate maximum Examiner provider-message count defaults to six. Exhaustion uses recorded deterministic fallback rather than making more provider calls.

The Examiner receives an explicit public context allowlist: version, sanitized objective/name/preferences, frozen budget/currency, a bounded untrusted candidate question, a narrow public tool observation and remaining public challenge IDs/kinds/summaries. It receives no authoritative mutable state, approval IDs, candidate auth/endpoint data, private trigger/mutation declarations, evaluation expectations or Designer prompt. Candidate/tool text is data under a separate private Examiner prompt, never instructions.

`ExaminerPlan` v1.0 contains only a bounded intent, tone, existing preference indexes and an optional supported challenge ID. Supported intents present the objective, restate preferences, clarify budget/currency, explain the authorization process, suggest catalog inspection, ask for rechecking current details, or decline out-of-scope requests. There is **no free-form message, commerce tool, approval, amount, policy or success field** in model output. Invalid fields/intents/indexes cause fallback.

Testah renders the plan from validated public facts, with the actual budget/currency and an explicit statement that messages never approve purchases. Initial requests always contain the compiled objective. Generated descriptive text is handled conservatively; unsafe text in a manually created objective/preferences falls back to safe shopping language for the RAI message. The existing deterministic customer path remains unchanged. The LLM's contribution is contextual message-plan selection, not unrestricted customer prose. This deliberately narrower interface makes approval and prompt-injection boundaries enforceable without relying on a model to obey them.

Provider errors, invalid plans and exhausted Examiner message limits record `rai.examiner.fallback` with provider metadata, a safe code and fallback_mode=deterministic. They do not manufacture an approval or safety violation. An overall run deadline can still terminate inconclusive under Phase 4's infrastructure policy. Cancellation fences late Examiner output just as it fences late candidate output. No database transaction remains open while the Examiner awaits a provider.

## Challenge requests

The Examiner can request only a challenge present in the frozen blueprint with a still-eligible target and no completed purchase. Unknown, already applied, unsupported or no-longer-eligible requests are rejected and recorded. Accepted requests are conditional: `awaiting_declared_trigger` means no mutation has happened yet. The request cannot reveal/replace/advance the trigger, suppress automatic challenges, or bypass gateway checks.

The existing Phase 4 gateway actions remain the actual trigger points. When an accepted request's original declared condition later matches, the unchanged mutation logic applies once and records request fulfillment plus normal challenge activation. Approval invalidation, cart versions, current totals, merchant/availability checks and purchase limits remain deterministic. Phase 4 runs without requests retain their existing automatic challenge behavior. RAI's runtime request is an auditable conditional cue, not a new challenge scheduler with authority to alter frozen semantics.

## APIs and evidence

| Method | Path | Contract |
| --- | --- | --- |
| GET | /api/rai/configuration | Safe provider/model/mock flag and supported customer modes |
| POST | /api/rai/proposals | `agent_id`, `request_key`; return 202 and persisted job |
| GET | /api/rai/proposals | Newest first; offset >=0, limit 1–100 |
| GET | /api/rai/proposals/{id} | Status, validation, uncertainty, mode/model and safe preview |
| GET | /api/rai/proposals/{id}/events | Ordered evidence; after_sequence >=0, limit 1–500 |
| POST | /api/rai/proposals/{id}/compile | Independently validate and compile a ready proposal idempotently |
| POST | /api/assessments | Existing agent/environment IDs plus optional examiner_mode |

Public proposal views exclude raw design JSON, hidden draft fields, lease/configuration secrets and private evaluation/trigger declarations. Compiled environments remain ordinary saved environment snapshots with explicit provenance. Old Phase 3/4 HTTP baseline scripts accept only the newly added default metadata fields when comparing older baselines; all prior facts and events still compare exactly.

Before a run exists, generation evidence lives in ordered proposal events with UUIDs, per-proposal unique sequence numbers, UTC times and sanitized structured payloads. Events include generation request, template selection, validation outcomes/repair scheduling and environment compilation. At assessment creation, the linked compiled proposal's event evidence is copied into the existing run event log with original source-event references. Examiner request/generated-message/fallback and challenge accepted/rejected/fulfilled events append through the existing fenced run transaction and ordering rules. The gateway's tool, approval, denial, payment and termination evidence remains authoritative.

Configured model/candidate keys, credential-like strings and URLs are redacted using the existing sanitizer plus the new provider key. Neither raw provider exceptions/bodies nor full prompts/reasoning are stored. Metadata records requested/configured model names, not invented usage or proof that a paid call succeeded. Redaction is not a general personal-data DLP system; operator descriptions should contain capability information, not sensitive customer data.

## Configuration and reproduction

| Setting | Default | Bounds |
| --- | --- | --- |
| TESTAH_RAI_PROVIDER | mock | mock / openai / gemini |
| TESTAH_RAI_MODEL | empty | Explicit account-available model for real mode |
| TESTAH_RAI_API_KEY | empty | Server-only SecretStr; Google key for Gemini, OpenAI key for OpenAI |
| TESTAH_RAI_TIMEOUT_SECONDS | 20 | 1–60 total seconds per provider operation |
| TESTAH_RAI_MAX_OUTPUT_TOKENS | 3000 | 256–8000 |
| TESTAH_RAI_MAX_RESPONSE_BYTES | 131072 | 4096–262144 |
| TESTAH_RAI_RETRIES | 1 | 0–2 transient retries |
| TESTAH_RAI_REPAIR_ATTEMPTS | 1 | 0–1 design repairs |
| TESTAH_RAI_GENERATION_SECONDS | 60 | 5–180; abandoned lease adds five seconds |
| TESTAH_RAI_MAX_GENERATION_WORKERS | 2 | 1–4 per process |
| TESTAH_RAI_MAX_EXAMINER_MESSAGES | 6 | 1–10 per run |

The root README supplies exact PowerShell startup and secret-input commands. Run `backend/scripts/check_rai.py` with the API and standalone sample active, then restart only the API and run it with `--verify-restart`. It uses actual candidate HTTP in both customer modes and explicitly prints the generation provider. `TESTAH_SAMPLE_BEHAVIOR=clarification` adds one real candidate question without changing existing safe/adversarial sample behaviors. The sample searches the supported category so generated display names need not contain a fixed query word.

Task 05.5.1 additionally verified authenticated structured Designer output and environment compilation using `gemini-3.5-flash-lite`. The operator's existing `.env` and SQLite database are preserved. See [the diagnostic report](task05.5.1-verification.md) for reproduced failures, exact request comparison, live record IDs, tests and manual verification. Earlier Task 05.5 model/setup notes below describe that original setup; current model selection and verification commands are in the root README.

### Persistent-timeout diagnostics and Designer schema cost

The later persistent-timeout investigation found an active 30-second process configuration despite an edited `.env` specifying 60 seconds. FastAPI settings are startup snapshots; restart and inspect the safe `RAI effective configuration` line, including process override names, actual PID and limits. No automatic secret/config hot reload is implemented. The bounds in `app/core/config.py` remain 60 seconds per provider operation and 180 seconds per generation job.

With the operator's existing 60/180 limits loaded, timing isolated another failure: one request spent 59.7 seconds waiting for Gemini response headers, then the total provider deadline canceled it. The worker still had budget and no retries, repairs, parsing or validation had run. The internal Gemini reason cannot be established from client timing alone.

For Designer requests only, `gemini_json_schema` now retains all object fields/types, required fields, enums and `additionalProperties=false`, while moving range/length/array bounds and patterns into descriptions. Google's [structured-output guidance](https://ai.google.dev/gemini-api/docs/structured-output) identifies these bounds as contributors to decoding state complexity. This is a provider grammar optimization, not a change to `EnvironmentDesign` or Blueprint v1.0: the exact original strict Pydantic schema, text checks, reference checks and full compiler validation remain mandatory. Examiner requests retain their existing provider schema. Invalid output still requires bounded repair or fails; it never becomes a trusted environment.

`app/rai/diagnostics.py` sends scalar-only INFO diagnostics through `uvicorn.error.rai`, using a context-local proposal ID for asynchronous isolation. Phases cover queue wait, HTTP attempts/retries, network steps, deadline source, JSON parsing, original schema validation, repairs, Blueprint compilation and final persisted compilation. Numeric token counts are logged only when actually supplied by Gemini; thought text/signatures are ignored. No prompts, model bodies, sensitive headers, key values, invalid input details or hidden rules are logged or added to database events. Existing event ordering and transaction boundaries are unchanged. Custom logging configurations must enable this logger at INFO to retain timings.

The same model and 3000-token ceiling successfully generated and compiled an environment after the change, with a 6.04-second provider call. This single observed improvement supports the optimization but does not prove which provider-internal stage was slow or guarantee future latency. Exact before/after measurements and final checks are in [rai-timeout-verification.md](rai-timeout-verification.md).

### Existing Windows .env setup for Gemini (Task 05.5)

The local `backend/.env` was appended in place; its app name, SQLite URL and CORS origins remain unchanged. Settings resolve that file by its absolute backend path with UTF-8 encoding from any working directory. Process environment takes precedence. `.env`/`.env.*` are ignored by Git, with `.env.example` explicitly allowed. The example remains credential-free and defaults to mock; no Google-specific alias such as `GEMINI_API_KEY` is read by Testah.

Stop the API with Ctrl+C, then open the existing file:

~~~powershell
Set-Location E:\Testah\backend
notepad.exe .\.env
~~~

Keep `TESTAH_RAI_PROVIDER=gemini` and `TESTAH_RAI_MODEL=gemini-2.5-flash`. Replace only `REPLACE_WITH_YOUR_GEMINI_API_KEY` on `TESTAH_RAI_API_KEY` with your Google API key and save. Do not recreate the file. The placeholder is rejected before any network operation. This local setup uses timeout 30 seconds, output 3000 tokens / 131072 bytes, one transient retry, one design repair, and generation deadline 90 seconds. All other limits and validation remain as in the table.

Remove old terminal overrides and restart:

~~~powershell
Remove-Item Env:TESTAH_RAI_PROVIDER -ErrorAction SilentlyContinue
Remove-Item Env:TESTAH_RAI_MODEL -ErrorAction SilentlyContinue
Remove-Item Env:TESTAH_RAI_API_KEY -ErrorAction SilentlyContinue
.\.venv\Scripts\python.exe -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000
~~~

From another PowerShell terminal:

~~~powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health
Invoke-RestMethod http://127.0.0.1:8000/api/rai/configuration | Format-List
~~~

Expect Gemini, the requested model and `is_mock=False`. The dashboard and RAI workspace read these fields from the backend; they indicate configuration, not authenticated access. Generate a **new** proposal and require `ready`/`validated` with Gemini provenance. Compile it, then create/start a new assessment with RAI Examiner. Require `rai.examiner.message_generated` events with Gemini metadata and inspect for fallback events. Existing runs/proposals retain their frozen provider selection. With the README clarification sample and local gate active, run the strict integration check:

~~~powershell
Set-Location E:\Testah
.\backend\.venv\Scripts\python.exe backend/scripts/check_rai.py --require-real-provider
~~~

This flag requires real Designer generation and Examiner messages without deterministic fallback. API credentials, quota/billing, model access and response quality remain unverified until that authenticated workflow succeeds. Credential-free tests use mocked HTTP; they do not establish real Gemini availability.

For offline mode, stop the API, change only `TESTAH_RAI_PROVIDER=mock` in `.env`, and restart. To return, use `gemini` and the matching Google key/model, then restart. A temporary `$env:TESTAH_RAI_PROVIDER = "mock"` overrides the file until removed or the terminal exits. No code path silently selects mock for a Gemini failure. Designer records a failed proposal; Examiner records `rai.examiner.fallback` with Gemini metadata and `fallback_mode=deterministic`, preserving Phase 5 behavior.

Safe error codes distinguish missing/placeholder configuration (`provider_not_configured`), Gemini 401/403 (`provider_authentication_failed`), 404 (`provider_model_unavailable`), other rejected HTTP requests (`provider_http_error`, including Google's possible HTTP 400 invalid-key errors), exhausted 429/5xx retries (`provider_transient_error`), network/deadline errors (`provider_unreachable`/`provider_timeout`), token truncation (`provider_incomplete`) and malformed JSON (`invalid_model_output`). Raw provider error text, credentials and prompts are never returned or persisted. The existing full Blueprint validation and deterministic Tool Gateway authority are unchanged.

In the UI, Generate with RAI is the primary dashboard workflow. Select an agent, generate, inspect the mock/real label, uncertainty and full safe preview, confirm/compile, choose RAI Examiner or deterministic customer, and create/start the existing assessment flow. Ordered run events show generated messages, fallback and challenge decisions. Advanced / Manual environments remains available, with the existing manual editor and deterministic assessment mode intact.

## Remaining requirements and deliberate deviations

### Same-process development provider check

`POST /api/rai/diagnostics` with `{"run_smoke_test":true}` is installed only for `TESTAH_ENVIRONMENT=development`, including its OpenAPI entry. It rejects unapproved browser origins, requires JSON, and admits one check at a time per API process. Nothing invokes it automatically at startup or on page load. It reports safe configuration, key presence, actual serving PID/parent/Python, absolute `.env` source, process override names, effective bounds and measured check latencies. No keys, proxy values, resolved addresses, raw exceptions or response bodies are returned.

With Gemini selected, an uncredentialed fixed-host GET proves DNS/TCP/verified TLS reached Google (any HTTP status establishes transport reachability). It then uses the same `GeminiProvider` adapter for one authenticated strict JSON smoke test, capped at 256 output tokens, zero retries and the existing provider deadline. Connectivity is capped at the smaller of ten seconds and the configured deadline; if it fails, the paid request is skipped. Mock/non-Gemini configuration is explicitly skipped, never substituted. This smoke test does not replace Designer validation and compilation.

Typed exception chains distinguish `provider_network_denied`, `provider_dns_error`, `provider_tls_error`, `provider_proxy_error`, `provider_unreachable` and `provider_timeout`. Permission denial takes precedence over wrappers and is never retried or logged as a timeout. DNS retains a typed cause for classification without exposing exception text. TLS/DNS/proxy/policy errors fail immediately; quick transient connection/timeouts and 429/5xx retain bounded retries sharing the original total deadline. Malformed Gemini finish-reason types yield `invalid_model_output`. Existing schema, repair, worker lease, cancellation and atomic compilation rules remain intact.

The Designer displays fixed actionable guidance and a failed proposal's exact category. Explicit retry preserves its registered agent input and creates a new idempotent generation job; a lost submission response retains its request key. Old failed evidence is preserved. The root README and CMD launcher define the ordinary network-enabled local startup. An inherited sandbox environment marker alone is not evidence of effective OS permissions; use the actual API check. See [verification and root causes](gemini-reliability-verification.md).

`docs/architecture.md` is unchanged. Its end-state prose permits an RAI customer to grant authorization; this task explicitly forbids that, so the deterministic gateway alone grants scenario approval. Phase 5 uses strict message plans instead of unrestricted Examiner prose and conditional requests instead of LLM-triggered state mutations. Blueprint v1.0's category and product-text limits are preserved. Capability confidence is explicitly limited by existing registration metadata. Proposal evidence needs its own pre-run table; linked evidence enters the existing run log afterward.

There is no ownership authentication/authorization, durable distributed generation/execution queue, global worker/rate quota, production sweeper, final scoring, PayPal, React Flow, SSE, AG Grid, APIMatic or deployment. SQLite serializes writers. Public deployment requires owner-scoped APIs, durable workers, production database/egress/DNS controls, cost and concurrency limits, retention/backups and monitoring. Live model quality, account access, billing and real-provider availability require operator validation. Stop after Phase 5.
