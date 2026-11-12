# Task 05.5: Gemini configuration verification

Scope: existing Phase 5 only. The existing backend `.env` was opened in append mode; no existing bytes were changed. Application name, database URL and CORS values were independently checked after loading settings from the repository root. No API key was supplied and no authenticated Gemini request was made.

## Configuration

Both Designer and RAI Examiner select Google's fixed `generateContent` endpoint through the existing provider factory. The existing separate prompts, strict output contracts, full Environment Engine validation and deterministic Tool Gateway remain authoritative. Gemini is never replaced with mock on failure. Designer fails visibly; Examiner retains the existing explicit, persisted deterministic fallback with Gemini provenance.

| Variable | Local backend/.env value |
| --- | --- |
| TESTAH_RAI_PROVIDER | gemini |
| TESTAH_RAI_MODEL | gemini-2.5-flash |
| TESTAH_RAI_API_KEY | REPLACE_WITH_YOUR_GEMINI_API_KEY |
| TESTAH_RAI_TIMEOUT_SECONDS | 30 |
| TESTAH_RAI_MAX_OUTPUT_TOKENS | 3000 |
| TESTAH_RAI_MAX_RESPONSE_BYTES | 131072 |
| TESTAH_RAI_RETRIES | 1 |
| TESTAH_RAI_REPAIR_ATTEMPTS | 1 |
| TESTAH_RAI_GENERATION_SECONDS | 90 |
| TESTAH_RAI_MAX_GENERATION_WORKERS | 2 |
| TESTAH_RAI_MAX_EXAMINER_MESSAGES | 6 |

These are Testah settings, including the generic server-only API-key field. Testah does not read `GEMINI_API_KEY` or expose a credential form to the browser. `.env.example` retains explicit mock defaults and an empty key. The existing absolute `.env` path now has explicit UTF-8 decoding; process environment still takes precedence.

## Changed files

- `backend/.env` — appended the Gemini block; existing settings preserved, key placeholder only; ignored local file.
- `backend/.env.example` — documented Gemini selection and the shared server-only key.
- `backend/app/core/config.py` — Gemini provider choice and explicit UTF-8 loading.
- `backend/app/rai/provider.py` — shared bounded HTTP transport, Gemini request/response adapter, explicit provider factory, safe error codes.
- `backend/app/schemas/rai.py`, `backend/app/schemas/environments.py` — additive Gemini provenance values.
- `backend/tests/test_gemini.py`, `backend/tests/test_rai.py` — configuration, transport, error, validation and lifecycle tests using mocked Gemini HTTP.
- `backend/scripts/check_rai.py` — optional `--require-real-provider` check requiring successful Designer/Examiner generation without fallback.
- `frontend/src/components/RaiProviderStatus.tsx`, `frontend/src/hooks/useRaiConfiguration.ts` — backend metadata display with refresh and safe unavailable state.
- `frontend/src/hooks/useRaiDesigner.ts` — clear stale configuration during reload.
- `frontend/src/pages/Dashboard.tsx`, `frontend/src/pages/RaiDesignerPage.tsx` — active provider/model display and Examiner model label.
- `frontend/src/types/rai.ts`, `frontend/src/types/environments.ts` — additive Gemini contracts.
- `README.md`, `docs/rai-designer-examiner.md`, this file — exact PowerShell setup, switching, restart, verification and limitations.

The existing `.gitignore` already excludes `.env` and `.env.*` while allowing `.env.example`. Its rules were verified with Git `check-ignore --no-index` using an isolated temporary Git directory under ignored `tmp/`. This workspace has no root Git metadata, so actual tracked-file/index status could not be audited. No repository was initialized at the project root. Temporary edit/smoke helpers, logs, test databases and ignore-check metadata are under ignored `tmp/`.

## Checks

Final checks on November 3, 2026:

| Check | Result |
| --- | --- |
| Full backend suite | 377 passed in 506.73 seconds; one existing Starlette/AnyIO deprecation warning |
| Gemini-specific tests | All 33 passed within the full suite; both role contracts, settings, limits, parsing, credentials and provider failures |
| Existing Phase 5 tests plus Gemini lifecycle coverage | Passed, including validation, compilation, persistence, explicit fallback and gateway compatibility |
| Frontend production build | Passed; includes strict TypeScript checking; Vite built 64 modules |
| Alembic schema check | Passed; no new upgrade operations |

Reproduction from Windows PowerShell (the unique workspace-local base temp avoids profile-temp restrictions):

~~~powershell
Set-Location E:\Testah\backend
$task55TestTemp = 'E:\Testah\tmp\pytest-task55-' + [guid]::NewGuid().ToString()
.\.venv\Scripts\python.exe -m pytest --basetemp $task55TestTemp -o "cache_dir=$task55TestTemp-cache"
.\.venv\Scripts\python.exe -m alembic check
Set-Location E:\Testah\frontend
npm.cmd run build
~~~

The full suite includes migration upgrade/downgrade round trips, health success/failure, CORS, safe errors, network restrictions, existing manual/mock workflows and real local-sample HTTP tests. Gemini transport tests use `httpx.MockTransport`, not a paid provider. Gemini lifecycle tests traverse generation, validation, compilation and fenced Examiner execution through the actual provider factory, verify Gemini provenance and secret exclusion, and explicitly test authentication-error fallback evidence. Initial test-fixture issues were corrected before the final all-passing run.

Additional verification passed:

- `alembic check`: no new upgrade operations detected; no schema migration is required.
- Actual local `.env` settings loaded from repository root; original file prefix SHA-256 remained unchanged.
- Live isolated loopback API `/api/health` and `/api/rai/configuration` returned health and Gemini metadata without credential fields.
- Vite production preview returned the application for `/`, `/rai`, `/environments`, `/assessments` and `/agents`.
- `.env.example` has an empty API key; frontend source and built JavaScript contain no `TESTAH_RAI_API_KEY` setting.
- Git ignore rules exclude backend/frontend `.env` and allow `.env.example`.

## Limits and operator steps

No authenticated Gemini call, account access, quota/billing or live model quality is verified. Replace the placeholder locally, restart the API, verify safe configuration metadata, and generate a new proposal plus a new RAI Examiner assessment as described in [README](../README.md#gemini-configuration-in-the-existing-backend-env). The strict integration command requires the README sample/local gate and can incur API usage.

Google's [Gemini 2.5 Flash page](https://ai.google.dev/gemini-api/docs/models/gemini-2.5-flash) documents structured output and lists deprecation/automatic routing effective December 1, 2026. Testah records the requested model identifier; operators must verify serving-model availability and future migration.

The computer/browser UI host was unavailable, so visual browser health/navigation could not be checked. HTTP route responses are verified but do not establish rendered UI behavior. Existing Phase 5 limits remain: local/trusted operation, an in-process worker, constrained Examiner message plans and conditional deterministic challenges. No Phase 6, real payments, scoring, SSE, React Flow or deployment was implemented.
