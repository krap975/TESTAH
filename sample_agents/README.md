# Independent sample agent

Start with the [developer quickstart](../docs/developer-quickstart.md) and
[candidate-only OpenAPI](../docs/developer/candidate-agent.openapi.json).
This is the endpoint you implement; backend Swagger describes a separate,
trusted operator API.

A deterministic FastAPI server demonstrating candidate protocol 1.0 without an LLM account. It imports only the shared wire schemas from backend/app/schemas/protocol.py and does not use the Testah API application or database.

From the repository root in Windows PowerShell:

~~~powershell
Set-Location E:\Testah
.\backend\.venv\Scripts\python.exe -m uvicorn sample_agents.main:app --host 127.0.0.1 --port 9001
~~~

The existing backend environment supplies dependencies. For a separate environment, use Python 3.11+ to create a venv and install sample_agents/requirements.txt. Run from the repository root so the shared schema import is available.

POST /agent accepts the documented request. context.sample_response_mode selects message (default), tool_call (requests the advertised test_echo tool), or completed. These are protocol demonstrations; no tool, payment, or assessment is executed. An optional TESTAH_SAMPLE_TOKEN requires an identical complete Authorization header value. No token is configured by default; never commit a real token.

Start Testah separately with TESTAH_ENVIRONMENT=development and TESTAH_ALLOW_LOCAL_SAMPLE=true. Register connection_mode=local_sample with exactly http://127.0.0.1:9001/agent. These flags do not relax external endpoint validation.

With both servers running:

~~~powershell
.\backend\.venv\Scripts\python.exe sample_agents/integration_check.py
~~~

This creates and removes only its own temporary record. It verifies all three responses and persisted connection status. For complete setup, authentication, network boundaries, and examples, see [agent protocol](../docs/agent-protocol.md).


## Phase 4 assessment behavior

For context.purpose=assessment, this endpoint plans a deterministic purchase using only the ordered public protocol transcript. It searches products, checks budget and merchants, requests approval, checks out, inspects payment status and completes. Rejected/challenged offers lead to an observed legal alternative. Stable session IDs and complete tool history let it reconstruct observations without Testah database access.

Set the sample process's TESTAH_SAMPLE_BEHAVIOR before starting uvicorn: `safe` (default), `unauthorized`, `over_budget`, `unverified`, `duplicate`, `invalid_arguments`, `timeout`, or `malformed`. Connection probes remain valid. Duplicate mode demonstrates identical checkout replay and a rejected second key. The sample never processes real money or receives private challenge declarations.

With both servers running in safe mode:

~~~powershell
.\backend\.venv\Scripts\python.exe backend/scripts/check_assessments.py
# Stop/restart only the API with the same database, then:
.\backend\.venv\Scripts\python.exe backend/scripts/check_assessments.py --verify-restart
~~~

The walkthrough retains the agent and six runs for inspection. See the root README for startup/UI steps. Stop the manual sample before pytest, which uses port 9001 for actual HTTP tests.

## Phase 5 clarification walkthrough

Set TESTAH_SAMPLE_BEHAVIOR=clarification before starting the same server. It asks one budget/currency/approval question on the first assessment turn, then continues the safe commerce flow. Existing safe/adversarial/probe behaviors remain available. Category search allows generated product names to vary.

With the API in TESTAH_RAI_PROVIDER=mock and the sample active:

~~~powershell
Set-Location E:\Testah
.\backend\.venv\Scripts\python.exe backend/scripts/check_rai.py
# Restart only the API with the same database/provider settings, then:
.\backend\.venv\Scripts\python.exe backend/scripts/check_rai.py --verify-restart
~~~

This compiles a controlled generated environment and tests both customer modes through actual candidate HTTP. Mock generation is explicitly labeled and uses no LLM. The sample receives no model keys, private prompts, hidden triggers or evaluation expectations. The gateway alone grants scenario approval and simulates purchases. See the root README for complete startup and optional real-provider configuration.

## Render deployment

Use the repository root so the shared schema import works. Build with
pip install -r sample_agents/requirements.txt; start with
uvicorn sample_agents.main:app --host 0.0.0.0 --port $PORT --workers 1 --no-access-log.
The unauthenticated health path is /health. Configure TESTAH_SAMPLE_TOKEN
privately and register the public HTTPS /agent URL as an external candidate.
See [the deployment runbook](../docs/render-deployment.md) for authentication and
cold-start handling. No local-sample network exception is permitted in production.
