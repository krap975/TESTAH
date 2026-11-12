# Testah candidate-agent protocol 1.0

The developer implements `POST /agent` on an independent service. Testah calls
it, validates its response, and executes requested tools through its server-side
gateway. The candidate needs no Testah database, PayPal credentials, scoring
inputs, model upload or SDK. The wire models in
[protocol.py](../backend/app/schemas/protocol.py) are authoritative. The
[candidate-only OpenAPI](developer/candidate-agent.openapi.json) is generated from
those unchanged models, separately from the backend's operator Swagger interface.
Start with the [developer quickstart](developer-quickstart.md).

## Transport and authentication

External endpoints require an ASCII HTTPS URL on port 443 with a valid public
certificate. Register the final URL: redirects are rejected. URL credentials,
query strings, fragments, localhost/internal names and non-public destinations
are rejected. Every exchange rechecks DNS, rejects any non-public answer, and
pins a checked IP while preserving original TLS SNI, certificate verification
and Host. Environment proxies are disabled. Application checks are not a network firewall.

Return HTTP 200 (the connector also accepts other successful 2xx) with
`Content-Type: application/json` and uncompressed UTF-8 JSON. The connector
rejects unknown fields, coercion, duplicate JSON keys and non-finite numbers.
JSON Schema alone cannot express all these parser rules.

Optional authentication uses a complete `Authorization` or `X-API-Key` header
value configured by the operator in server-only `TESTAH_AGENT_SECRETS`. Testah
adds no automatic `Bearer ` prefix. Only a reference is persisted; keys match
`[A-Z][A-Z0-9_]{0,63}` and values must be nonempty printable ASCII. Never place
values in browser metadata, `VITE_` settings, URLs, context or source control.
Restart the API and retest after changing secrets. The standalone sample accepts
the exact Authorization value configured through optional `TESTAH_SAMPLE_TOKEN`.

Candidate authentication does not authenticate Testah users. Operational APIs
have no general authentication or enforced tenant ownership. Keep them on
loopback for trusted operators.

## Request

| Field | Contract |
| --- | --- |
| `protocol_version` | Exactly the string `1.0` |
| `request_id` | Unique per exchange; echo it in the response |
| `session_id` | Stable run ID; probes use a fresh connection-test session |
| `message` | `role=user`; nonempty `content`, at most 16000 characters |
| `history` | At most 100 user/assistant/tool messages, each with the same text bound; default `[]` |
| `available_tools` | At most 50 name/description/input_schema definitions; default `[]` |
| `previous_tool_result` | Last structured tool result or `null`; default `null` |
| `context` | Public JSON map; default `{}` |

Identifiers contain 1–128 letters, digits, `_`, `.`, `:` or `-`. Tool descriptions
contain 1–2000 characters. Objects reject unknown fields except explicit JSON
maps: context, arguments, results and tool input schemas.

```json
{
  "protocol_version": "1.0",
  "request_id": "request-demo-001",
  "session_id": "connection-test-demo-001",
  "message": {"role": "user", "content": "Please confirm protocol compatibility."},
  "history": [],
  "available_tools": [{
    "name": "test_echo",
    "description": "Protocol-only demonstration; never executed by a connection probe.",
    "input_schema": {
      "type": "object",
      "properties": {"text": {"type": "string"}},
      "required": ["text"],
      "additionalProperties": false
    }
  }],
  "previous_tool_result": null,
  "context": {"purpose": "connection_test", "sample_response_mode": "message"}
}
```

Assessment context currently includes `purpose=assessment`, `turn`, `simulation`,
`payment_mode`, `currency`, `budget_minor` and `cart_version`. Hidden triggers,
expected answers, scoring inputs and credentials are excluded. History includes
tool-call/result JSON encoded in message content. It is public continuity, not
the candidate's private reasoning. Testah observes responses and actions routed
through it; it cannot inspect arbitrary private model calls.

## Responses

Echo protocol/request/session identifiers exactly. Return exactly one variant:

```json
{"protocol_version":"1.0","request_id":"request-demo-001","session_id":"connection-test-demo-001","type":"message","message":"Protocol request received."}
```

```json
{"protocol_version":"1.0","request_id":"request-demo-001","session_id":"connection-test-demo-001","type":"tool_call","tool_call":{"correlation_id":"call-demo-001","name":"test_echo","arguments":{"text":"Example only."}}}
```

```json
{"protocol_version":"1.0","request_id":"request-demo-001","session_id":"connection-test-demo-001","type":"completed","summary":"Protocol demonstration finished; no purchase was performed."}
```

Message/summary text is nonempty and at most 16000 characters. A tool call needs
a fresh correlation ID within the run, an advertised name and a JSON argument
object. Do not mix variant fields. Completion is a claim; the controller checks
server-recorded outcomes independently.

## Tool cycle

1. Read the objective, public history and advertised tool schemas.
2. Return one tool request. Do not execute Testah financial actions yourself.
3. Testah validates argument shape, current state, permissions and financial policy.
4. Inspect `previous_tool_result` on a subsequent exchange and choose the next action.

Example result:

```json
{"correlation_id":"call-demo-002","name":"get_budget","status":"success","result":{"budget_minor":10000,"remaining_minor":10000,"currency":"USD","purchases":0,"cart_version":1}}
```

An error uses `status=error` and a result with safe `code`, message and current
cart version. A denial is evidence to handle, not a purchase. Re-read changed
facts and obtain fresh approval when the cart changes. Correlation identifiers
and checkout idempotency keys have separate purposes.

| Tool | Arguments / responsibility |
| --- | --- |
| `search_products` | Optional `query`, `category`, `max_price_minor`; current synthetic products/cart version |
| `get_merchant_details` | `merchant_id`; verification, shipping and checkout support |
| `get_budget` | `{}`; authoritative budget/remaining minor units and currency |
| `request_approval` | `merchant_id`, unique product/quantity `items`, `total_minor`, `currency`, `cart_version`; exact scenario authorization |
| `create_checkout` | `approval_id`, stable `idempotency_key`, `cart_version`; server-bound checkout |
| `get_payment_status` | `checkout_id`; recorded server-verified payment state |

Use the supplied argument schema: extra fields are rejected. Money is integer
minor units, never browser/model authority. Approval binds exact items, quantity,
merchant, prices, shipping, currency and cart version. Common denials include
`stale_cart`, `amount_changed`, `budget_exceeded`, `unverified_merchant`,
`approval_required`, `approval_invalidated`, `approval_consumed`,
`invalid_tool_arguments` and `idempotency_conflict`.

Two frozen v1 registry descriptions retain historical "not implemented" payment
wording; the gateway implements these tools. Editing those definitions would
invalidate old snapshots, so this phase leaves them unchanged.
Modes are explicitly `simulated` or `paypal_sandbox`. Scenario authorization does
not replace buyer approval. Sandbox order creation, buyer approval and verified
capture are distinct. The controller pauses candidate calls for pending checkout;
the candidate never receives operator credentials. Inspect verified payment state
before claiming success. Real-money processing is unsupported.

## Connection testing, limits and errors

Use **My Agents → Test connection** in the trusted local UI. A probe sends fresh
IDs, a fixed compatibility message, empty history, the non-executable `test_echo`
definition and connection-test context. `sample_response_mode` is a sample-only
hint; another candidate may return any valid variant. No tools, assessments,
payments or scores are executed/created by the probe. Only safe fixed metadata
and response type are returned; raw remote responses are excluded. Endpoint or
authentication changes invalidate the previous connected status. Compatibility
does not prove agent safety.

| Limit | Current behavior |
| --- | --- |
| Serialized request | At most 65536 UTF-8 bytes |
| Response | Default 65536 bytes; configurable 1024–1048576 |
| Total exchange | Default 10 seconds; configurable 1–60, including DNS and full streamed body |
| Agent POST retries | Zero automatic retries |
| Redirects / compression | Rejected |
| Assessment active allowance | Default 120 seconds plus separate bounded Sandbox approval wait |
| Assessment turns / tools / HTTP requests | Defaults 30 / 25 / 30; frozen per run |

Testah connection-test errors use its safe envelope
`{"error":{"code":"...","message":"..."}}`. These are Testah statuses,
not required response payloads from the external agent:

| Code | HTTP | Meaning |
| --- | --- | --- |
| `destination_blocked`, `local_sample_disabled`, `secret_unavailable` | 400 | Destination/gate/credential configuration rejected |
| `request_too_large` | 400 | Serialized request exceeds 64 KiB |
| `dns_error`, `unreachable` | 502 | DNS, connection or verified TLS failure |
| `redirect_rejected`, `authentication_rejected`, `agent_http_error` | 502 | Remote redirect, 401/403 or other unsuccessful status |
| `response_too_large`, `invalid_protocol` | 502 | Size, JSON/schema/encoding, identifier or tool-name violation |
| `timeout` | 504 | Total deadline expired |

The standalone sample returns `{"detail":"Authentication required."}` for 401
and FastAPI's validation-detail array for 422; the candidate OpenAPI documents
those separately from Testah's safe management envelope. Candidate error bodies
are never treated as financial authority. Never echo credentials or raw provider errors.

## Local exception and deployment limits

The only local exception is exactly `http://127.0.0.1:9001/agent`, local-sample
connection mode, development environment and the explicit local sample flag.
Production/test reject that flag. It never relaxes external HTTPS checks.

Public multi-tenant onboarding, general user authentication, infrastructure egress
policy, global abuse controls, PostgreSQL verification and public HTTPS callbacks
remain deployment prerequisites. Keep operational APIs local/trusted. Evidence
persists locally; in-process execution is not a distributed queue and uncertain
agent POSTs are never automatically replayed.
