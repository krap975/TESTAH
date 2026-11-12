# Task 05.5.1: Gemini failure diagnosis and verification

## Findings

The configured key and Gemini request schema were usable. Two distinct failure mechanisms were reproduced; they must not be conflated with authentication or HTTP validation failures.

1. In the restricted coding-agent execution context, the exact checked-IP transport failed before receiving HTTP: `httpx.ConnectError -> httpcore.ConnectError -> OSError -> PermissionError [WinError 5] Access is denied`. The previous broad `except httpx.HTTPError` collapsed this into `provider_unreachable`. Outside that sandbox, the same pinned endpoint, TLS verification and key returned HTTP 200. This explains why a direct request from an ordinary terminal can work while a sandbox-launched backend cannot. Historical failed records retained only the generic code, so their original exception chains cannot be reconstructed conclusively from those records alone.
2. With the current model, the live API reproduced `provider_timeout` after approximately 30 seconds. The adapter divided `TESTAH_RAI_TIMEOUT_SECONDS` by `(TESTAH_RAI_RETRIES + 1)`: 30 seconds plus one retry meant two attempts capped at 15 seconds each. An isolated, single-attempt request using the **exact Designer body** returned HTTP 200 at 20.531 seconds and passed both `EnvironmentDesign` and full Blueprint compilation checks. The old per-attempt cutoff could cancel a valid response before completion, then repeat the same generation.

The first post-edit API check was interrupted by Uvicorn auto-reload and persisted `generation_worker_stopped`. Logs confirmed a source-change reload. The backend was restarted outside the sandbox without `--reload`; the subsequent complete API workflow succeeded. No TLS, checked-DNS, SNI, certificate verification, proxy or redirect protections were weakened. IPv6 was selected and successfully used outside the sandbox; no address-family workaround was needed.

## Effective configuration

- Live metadata: `provider=gemini`, `model=gemini-3.5-flash-lite`, `is_mock=false`.
- Local settings: non-placeholder API key configured and equal to the existing `.env` value; no key value was printed.
- Current PowerShell execution environment contained no `TESTAH_RAI_*` overrides. For the stable backend restart, provider/model/key overrides were explicitly removed before launch, making `.env` authoritative for them. Successful generation through that running process independently confirms usable effective credentials.
- Timeout 30 seconds, output 3000 tokens / 131072 bytes, one transient retry, one repair, generation deadline 90 seconds.
- The existing `.env` was not modified. Its complete bytes were verified unchanged before and after live checks. SQLite was retained; verification added proposal/evidence records and one compiled environment, without resets or schema changes.

## Request comparison and results

| Property | Verified Testah request |
| --- | --- |
| Endpoint | `https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent` |
| Authentication | Server-only `x-goog-api-key` header; no key in URL/body |
| Connection | Public DNS validation, checked-IP connection, original Host and TLS SNI/certificate verification |
| HTTPX | Fresh transport, `retries=0`, `trust_env=false`, redirects disabled |
| Minimal prompt | `Reply with only OK.`; 64 output tokens; HTTP 200, text `OK`, 13.297 seconds |
| Designer input | Existing separate private system instruction and bounded `untrusted_data` manifest; prompts/body not logged |
| Structured output | `responseMimeType=application/json`, existing strict schema in `responseJsonSchema`, `candidateCount=1` |
| Output limit | Existing configured `maxOutputTokens=3000`; no 2.5-specific thinking settings for 3.5 |
| Parsing | Existing single-candidate/STOP checks, strict JSON parsing, Pydantic proposal validation and full Environment Engine validation |
| Diagnostic Designer | HTTP 200 at 20.531 seconds; proposal schema and Blueprint valid |
| Final live API Designer | Ready / validated on attempt 1, 14.14 seconds |
| Compilation | Successful; provider/model provenance persisted |

Successful live API proposal: `0c1edc44-0db5-41f7-b9a5-7deb6efa4972`.

Compiled environment: `2d55de95-c80e-44f4-a401-b456792e9838`.

Its committed proposal events are ordered 1–4: `rai.generation.requested`, `rai.template.selected`, `rai.proposal.validation`, `rai.environment.compiled`. Provenance is Gemini / `gemini-3.5-flash-lite`, never mock. Stored proposal JSON and Blueprint were independently validated before compilation. No real Examiner assessment or financial action was needed for this verification.

No live HTTP 400, 401/403, 404, 429 or 5xx response was observed during the successful checks. These cases are exercised using synthetic HTTP responses in tests; their bodies are not mistaken for connectivity failures. Canceled generation attempts can consume provider quota; no additional paid probes were made after the complete workflow succeeded.

## Exact fix and changed files

- `backend/app/rai/provider.py`: remove the artificial per-attempt fraction; one total deadline still bounds every attempt/backoff. Restrict `provider_unreachable` to actual network errors; detect nested socket permission denial, DNS errors, HTTP status errors, protocol errors and other transport errors separately. Preserve terminal HTTP status, including exhausted 429/5xx retries. Log only provider, safe code and HTTP status, never exception messages, raw bodies, keys, headers or prompts.
- `backend/tests/test_gemini.py`: regression coverage for a response slower than the old attempt fraction but faster than the total deadline, 3.5 Flash Lite request shape, safe status logging, HTTP versus nonnetwork failure classification, denied sockets and DNS errors.
- `backend/.env.example`: update the model-selection comment to the verified model; mock default and empty key/model remain unchanged.
- `README.md`, `docs/rai-designer-examiner.md`, this report: verified configuration, timeout semantics, safe diagnostics, launch-context distinction and manual instructions.

Existing Designer/Examiner schemas and prompts, Environment Engine validation, Tool Gateway authorization, SQLite schema, mock selection, candidate networking and all Phase 1–5 functionality remain in place. No Phase 6 work was begun.

## Automated checks

- Focused Gemini/OpenAI provider tests after the final changes: **70 passed** in 9.32 seconds.
- Full backend suite: **386 passed** in 487.80 seconds, including health/CORS/safe errors, migration round trips, networking, execution/gateway, mock workflows and Phase 5 compatibility.
- `alembic check`: passed; no new upgrade operations detected.
- Final live backend health: HTTP 200, database connected; verified proposal remains compiled with the expected Gemini/model/environment references.
- Frontend source/contracts were unchanged; a new frontend build is not required for this backend-only fix.
- Existing dependency warning: Starlette references a deprecated AnyIO `BlockingPortal` alias.

The regression test waits 0.6 seconds with a total budget of 1 second and one retry. It requires one successful request. The old implementation canceled at 0.5 seconds. Existing deadline, retry-count, strict parsing, secret-redaction and Phase 5 tests remain active.

## Manual verification

Start from an ordinary PowerShell terminal that permits outbound Gemini access. Stop any existing backend first. Preserve `.env`; it already contains the selected model and operator key. Clear stale provider/model/key overrides and launch without file watching:

~~~powershell
Set-Location E:\Testah\backend
Remove-Item Env:TESTAH_RAI_PROVIDER -ErrorAction SilentlyContinue
Remove-Item Env:TESTAH_RAI_MODEL -ErrorAction SilentlyContinue
Remove-Item Env:TESTAH_RAI_API_KEY -ErrorAction SilentlyContinue
.\.venv\Scripts\python.exe -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000
~~~

In a second terminal, inspect metadata and the already verified record without incurring another model call:

~~~powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health
Invoke-RestMethod http://127.0.0.1:8000/api/rai/configuration | Format-List
Invoke-RestMethod http://127.0.0.1:8000/api/rai/proposals/0c1edc44-0db5-41f7-b9a5-7deb6efa4972 | Select-Object id,status,provider,model,validation,environment_id
Invoke-RestMethod http://127.0.0.1:8000/api/rai/proposals/0c1edc44-0db5-41f7-b9a5-7deb6efa4972/events
~~~

To make one new generation request, open `http://127.0.0.1:5173/rai`, select a registered agent and choose Generate with RAI. Require Gemini / `gemini-3.5-flash-lite`, ready / validated, then Confirm and compile. Previously failed jobs retain their evidence; create a new job instead of retrying an old request key.

For command-line generation without a sample agent or assessment (this can incur model usage):

~~~powershell
$raiAgents = Invoke-RestMethod http://127.0.0.1:8000/api/agents
$raiAgent = @($raiAgents)[0]
if (-not $raiAgent) { throw 'Register an agent before generation.' }
$raiRequest = @{ agent_id = $raiAgent.id; request_key = [guid]::NewGuid().ToString() } | ConvertTo-Json
$raiProposal = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/rai/proposals -ContentType 'application/json' -Body $raiRequest
do {
    Start-Sleep -Milliseconds 500
    $raiProposal = Invoke-RestMethod ("http://127.0.0.1:8000/api/rai/proposals/" + $raiProposal.id)
} while ($raiProposal.status -eq 'generating')
$raiProposal | Select-Object id,status,provider,model,validation
if ($raiProposal.status -ne 'ready') { throw ("Generation failed: " + $raiProposal.validation.code) }
Invoke-RestMethod -Method Post -Uri ("http://127.0.0.1:8000/api/rai/proposals/" + $raiProposal.id + '/compile')
~~~

Backend failures now distinguish socket permission denial (`provider_network_denied`), DNS (`provider_dns_error`), network (`provider_unreachable`), deadline (`provider_timeout`), HTTP status (`provider_http_error` / authentication / model / transient codes), protocol (`provider_protocol_error`), other transport (`provider_transport_error`) and strict JSON/output failures. Check the safe code/status log fields; never enable logging of authentication headers or private prompts.
