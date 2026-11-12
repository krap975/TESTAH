# Connect a candidate agent

Testah calls your independent `POST /agent` endpoint. Return a message, a tool
request, or a completion claim. Testah executes permitted tools through its own
gateway. The deterministic sample needs no SDK, LLM account or payment credentials.
Read the [protocol](agent-protocol.md) and
[candidate-only OpenAPI](developer/candidate-agent.openapi.json). Backend Swagger
describes a separate trusted operator API.

## 1. Run the sample locally

From an existing checkout in PowerShell:

```powershell
Set-Location E:\Testah
.\backend\.venv\Scripts\python.exe -m uvicorn sample_agents.main:app --host 127.0.0.1 --port 9001
```

For an independent environment, install `sample_agents/requirements.txt` with
Python 3.11+ and run from the repository root for shared-schema imports. Linux/macOS:

```sh
python3 -m venv .sample-venv
.sample-venv/bin/python -m pip install -r sample_agents/requirements.txt
.sample-venv/bin/python -m uvicorn sample_agents.main:app --host 127.0.0.1 --port 9001
```

The sample imports only wire models, not the Testah application or database.
Optional `TESTAH_SAMPLE_TOKEN` requires the exact complete Authorization header
value. Configure real values privately, never in examples.

## 2. Check the protocol without saved records

Copy the full probe JSON from the [protocol reference](agent-protocol.md) into
`request.json` (or use the OpenAPI's minimal four-field compatibility example), then:

```powershell
curl.exe -i -X POST http://127.0.0.1:9001/agent -H "Content-Type: application/json" --data-binary "@request.json"
```

Linux/macOS uses `curl`. Expect HTTP 200 and `type=message` with matching IDs.
Change `context.sample_response_mode` to `tool_call` or `completed` for the other
variants. The probe tool is never executed. A completed probe is not a purchase.

Automated checks exercise all examples against the sample ASGI application,
including authentication and validation failures:

```powershell
Set-Location E:\Testah\backend
.\.venv\Scripts\python.exe -m pytest tests/test_candidate_contract.py tests/test_protocol.py -q
```

## 3. Connect through the trusted local UI

Keep the existing API running unless its local-sample flag needs changing.
For the fixed loopback sample, start the API in a separate authorized terminal:

```powershell
Set-Location E:\Testah\backend
$env:TESTAH_ENVIRONMENT = "development"
$env:TESTAH_ALLOW_LOCAL_SAMPLE = "true"
.\scripts\start_backend.cmd
```

Preserve `.env`, the database and saved assessments. Initial installation and
migrations are in the root README; this phase requires no new migration.
Start `npm.cmd run dev` from `frontend/`, open `http://127.0.0.1:5173`, choose
**My Agents**, register a unique name with **Local sample** and exactly
`http://127.0.0.1:9001/agent`, then **Test connection**. Compatibility probing
executes no tools or assessments. The existing loopback-only
`sample_agents/integration_check.py` optionally creates one temporary agent,
tests all three variants and deletes only that temporary record.

To observe execution, select a connected agent and compiled environment, create
a **new** assessment and explicitly start it. Reports/replay inspect saved evidence.
These steps create additional records and are unnecessary for the direct check.
Never rerun a historical assessment to demonstrate protocol compatibility.

## 4. Implement your endpoint

1. Accept strict version 1.0 requests; use the stable session ID for continuity.
2. Echo protocol/request/session IDs and return exactly one response variant.
3. Use advertised tool schemas and fresh correlations. Handle structured denials
   and changed cart facts instead of claiming success.
4. Return uncompressed JSON within the total deadline/body limits. Testah rejects
   redirects, unknown tools, mismatched identifiers and malformed responses.
5. Keep credentials, hidden reasoning and raw provider errors out of responses.

External mode needs the final reachable public HTTPS endpoint on port 443.
`https://candidate.invalid/agent` is a non-resolving placeholder. Use public DNS, a valid
certificate and the exact path without query strings or credentials. An operator
configures optional header credentials server-side and registers a reference.
The local sample exception never relaxes external rules. Cold-starting hosts may
exceed the default 10-second deadline; check readiness first without retrying an
uncertain POST.

Testah operational APIs remain local/trusted. Public multi-tenant onboarding and
general authentication are deferred. Read [Render readiness](render-readiness.md)
before exposing any service.

## Rebuild the contract

```powershell
Set-Location E:\Testah
.\backend\.venv\Scripts\python.exe backend/scripts/export_candidate_openapi.py
.\backend\.venv\Scripts\python.exe backend/scripts/export_candidate_openapi.py --check
```

The exporter imports only wire schemas, never settings, `.env`, models or saved
records. [APIMatic provenance](apimatic.md) records actual generation status,
separately from ordinary Markdown and FastAPI Swagger.
