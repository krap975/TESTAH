# Persistent Gemini Designer timeout investigation

## Confirmed findings and remaining uncertainty

1. The existing FastAPI process froze **30 seconds** for new proposal requests, while the operator's current `.env` specified **60 seconds** and a **180-second** generation job. The persisted proposal configuration independently established the process value. A startup settings object does not reload after a file edit; any old process override would likewise take precedence until changed/restarted. After restarting, diagnostics from the actual serving PID confirmed 60/180 and **no RAI process overrides**. The existing `.env` was not edited.
2. Reloading those settings alone did not fix every request. The original structured Designer request was reproduced at 60 seconds. Its trace shows public DNS, TCP, verified TLS and upload completed in about 0.3 seconds, followed by **59.702 seconds waiting for response headers**. The outer **provider total deadline** canceled attempt 1. This was not queue starvation, a retry loop, repair, JSON parsing, schema validation, compilation or the worker's 180-second deadline. No HTTP error status was returned.
3. The selected model's thinking default is already minimal according to Google's [thinking documentation](https://ai.google.dev/gemini-api/docs/thinking). No thinking override or arbitrary output-token reduction was added. The request contained a 17,848-byte payload with a bounded but complex structured-output grammar. Google's [structured-output documentation](https://ai.google.dev/gemini-api/docs/structured-output) recommends simplifying scalar/array bounds to reduce grammar state complexity. A Designer-only grammar optimization moved these bounds to descriptions and preserved all original server validation. The next same-model request returned HTTP 200 in about six seconds and compiled successfully.

**The confirmed timeout origin is the provider total deadline while waiting for Gemini.** Whether the upstream delay came from schema compilation/decoding, serving load, or another Google-internal component remains unconfirmed. The measured improvement supports the schema-cost change but is not proof of the internal cause or a latency guarantee.

## Changes and safety boundary

- `backend/app/rai/diagnostics.py`: new scalar-only phase timing, context-local proposal correlation and safe startup configuration logging.
- `backend/app/main.py`: log the actual serving process's effective RAI settings at startup.
- `backend/app/rai/provider.py`: HTTP attempt/retry/network/deadline/JSON timing and numeric usage counters; Designer-only grammar optimization via `gemini_json_schema`.
- `backend/app/rai/designer.py`: queue, manifest, worker budget, schema validation, repairs, Blueprint and final persisted-compilation timing.
- `backend/tests/test_rai_diagnostics.py`: startup settings versus file edits/process overrides; hard-limit validation; timing isolation/redaction; HTTPX versus provider deadline; retry budget regression tests.
- `backend/tests/test_gemini.py`: grammar shape/non-mutation and unchanged strict budget validation coverage.
- `backend/tests/test_rai.py`: repair, validation and compilation timing coverage through the existing lifecycle.
- `README.md`, `docs/rai-designer-examiner.md`, this report: operations, measurements and limitations.

The provider grammar keeps types, property names, required fields, enums and closed objects. Only Designer's provider-side decoding bounds/patterns move into descriptions. The original strict `EnvironmentDesign` validation and full Environment Engine compilation still reject invalid numeric types/ranges, identifiers/references, unsafe text, changed policies/tools and unaffordable alternatives. Examiner's provider schema and deterministic fallback behavior are unchanged. There is no new financial authority, API contract, migration, Phase 6 work or configurable arbitrary destination.

No timeout bounds/defaults were raised. `app/core/config.py` is unchanged: provider max 60 seconds, generation max 180 seconds. The operator's existing 60/180 settings are now active. Model remains `gemini-3.5-flash-lite`; output ceiling remains 3000 tokens; HTTP/response limits, retries, TLS/SNI and checked-IP controls remain in effect. The `.env` was checked byte-for-byte unchanged around live verification. Existing database records were not reset or edited; testing added new proposal evidence and one compiled environment. Test databases are isolated under ignored `tmp/`.

## Before/after measurements

| Measurement | Original grammar, effective 60/180 | Optimized grammar, same 60/180 |
| --- | --- | --- |
| Queue wait | 78.0 ms | 117.0 ms |
| Manifest construction | 29.5 ms | 43.2 ms |
| Request bytes | 17,848 | 18,295 (includes textual bound guidance) |
| Provider HTTP attempt | Canceled at 60,006.5 ms | 6,042.1 ms, HTTP 200 |
| Response-header wait | 59,702.2 ms, canceled | 5,833.4 ms |
| Retry requests | None | None |
| Repair attempts beyond initial call | None | None |
| Envelope + model JSON parsing | Not reached | 0.159 + 0.064 ms |
| Original Pydantic validation | Not reached | 0.972 ms |
| Full draft Blueprint compilation | Not reached | 20.424 ms |
| Worker total | 60,161.1 ms, failed | 6,324.3 ms, validated |
| Polling client elapsed | 60.469 seconds | 6.485 seconds |
| Final saved-environment compilation | Not reached | 92.193 ms, committed |

The earlier baseline request on the stale 30-second process narrowly succeeded in 29.218 seconds; preceding saved failures repeatedly ended at approximately 30.17 seconds. These observations show variable latency rather than an invariably broken key/model.

Failed instrumented proposal: `17808981-7bda-4c83-8d26-0f2a7763da48`.

Successful verified proposal: `c41f38d9-a6d8-4f57-be38-8893c826a5ca`.

Compiled environment: `67b6bd42-c268-43e0-9ae1-750201e2934b`.

Gemini actually reported 3,668 prompt tokens and 464 candidate tokens, 4,132 total. No thought-token count was returned, so none is invented. The 3000-token ceiling was not forced or exhausted. No prompt, output body, thought text/signature, API key or sensitive header was logged. No additional paid calls were made after successful compilation.

## Safe diagnostics and reproduction

With the existing backend startup command, inspect `RAI effective configuration` to verify settings in the actual PID. Check `process_override_names` without printing environment values. If the file has changed, stop and restart the backend before submitting a **new** proposal; previously failed/frozen jobs retain their evidence.

For this run, diagnostics are in ignored `tmp/backend-timeout.stderr.log` (original 60-second failure) and `tmp/backend-timeout-fixed.stderr.log` (successful optimized call). `RAI timing` records contain scalar times/counts/statuses, a proposal ID, and safe exception class/deadline-source labels. They never contain request/response bodies or sensitive headers. INFO logging for `uvicorn.error.rai` must be enabled under custom logging configuration.

The provider deadline covers DNS, HTTP, attempts and retry backoff together. It is not multiplied by retries. `provider_timeout` timing records distinguish `source=provider_deadline` from `source=httpx` and its timeout class. The worker separately logs `worker_timeout` with `source=generation_deadline`. Repair attempts are distinct from transient HTTP retries and remain within the same bounded job. Tests force each failure path without paying for provider failures.

Read the verified result without another model request:

~~~powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health
Invoke-RestMethod http://127.0.0.1:8000/api/rai/configuration
Invoke-RestMethod http://127.0.0.1:8000/api/rai/proposals/c41f38d9-a6d8-4f57-be38-8893c826a5ca | Select-Object id,status,provider,model,validation,environment_id
~~~

To reproduce a paid generation, use Generate with RAI for the existing agent in the dashboard, then review/compile a ready proposal. Do not paste keys into browser fields or logs. Keep startup without `--reload` during live checks so file changes cannot cancel the job.

## Checks

- Focused diagnostics/provider/Phase 5 suite: **134 passed** after the grammar optimization.
- Final full backend run: **381 passed**, with 12 fixture setup errors because an existing standalone sample agent occupied port 9001 (`WinError 10048`). The README requires stopping that sample before pytest. The verified standalone process was temporarily stopped; the 12 affected real-HTTP cases then **all passed** on rerun in 71.06 seconds, and its original documented startup command was restored. **All 393 current backend cases passed across the full run and the port-fixture rerun.** No application test assertion failed in the full run.
- Alembic check: passed, no new upgrade operations.
- Frontend production build: passed, including strict TypeScript checking; frontend source/contracts were unchanged.
- Initial full run was stopped after the final request optimization so the complete suite could be rerun against the final implementation.

Remaining limits: provider internals and future latency are not guaranteed, failures still produce explicit safe codes and no silent mock fallback, workers remain in-process, and final scoring/real payments/deployment remain future work. Real authenticated Designer generation and compilation **were** verified in this run; no real Examiner assessment was necessary.
