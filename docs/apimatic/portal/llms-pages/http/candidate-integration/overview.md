# Overview

Source: /#/http/x-redirect/cGFnZSUzQWd1aWRlcyUyRm92ZXJ2aWV3

You implement `POST /agent`; Testah is the caller. No Testah SDK is required.
This reference is generated from the existing version 1.0 wire schemas and contains
only the candidate interface. The server `https://candidate.invalid` is a deliberately
non-resolving placeholder, not a live Testah or candidate service.


# First exchange

1. Implement an HTTPS JSON endpoint at your final public URL on port 443.
2. Accept the documented request; use session_id for continuity.
3. Echo protocol_version, request_id and session_id exactly.
4. Return exactly one message, tool_call or completed response.
5. Have the trusted operator register the destination and test compatibility.

The compatibility example uses test_echo only as an advertised shape. A connection
probe never executes tools, makes a purchase, creates a score or proves agent safety.
The sample-only context hint sample_response_mode selects its demonstrated response
variant. Other agents may return any valid variant.

The endpoint's generated cURL example intentionally uses only the four required
fields. Optional maps default to empty values and previous_tool_result to null.
For the sample's tool_call demonstration, send this complete synthetic probe:

```json
{
  "protocol_version": "1.0",
  "request_id": "request-demo-001",
  "session_id": "connection-test-demo-001",
  "message": {"role": "user", "content": "Please confirm protocol compatibility."},
  "history": [],
  "available_tools": [{
    "name": "test_echo",
    "description": "Protocol demonstration only; no execution.",
    "input_schema": {
      "type": "object",
      "properties": {"text": {"type": "string"}},
      "required": ["text"],
      "additionalProperties": false
    }
  }],
  "previous_tool_result": null,
  "context": {"purpose": "connection_test", "sample_response_mode": "tool_call"}
}
```

Set sample_response_mode to message or completed for the other probe variants.
Tool-call response examples require their named tool to have been advertised.
Generic auto-generated model snippets illustrate types; this guide and the source
contract supply the concrete, executable tool-schema example.


# Tool continuation

During an assessment, return one structured tool request using the advertised name
and input schema. Testah validates and executes it through its gateway. A later
request carries previous_tool_result with the same correlation_id and name,
status success/error and a structured result. Use a fresh correlation ID per call.
Handle denials and changed cart facts before trying a new legal action.

Your endpoint receives public history and context, not hidden triggers, private
scoring inputs, application credentials or model prompts. Testah cannot inspect
private reasoning or arbitrary calls made inside your agent. A completed response
is a claim checked against actual recorded outcomes.


# Transport and authentication

Return HTTP 200 with uncompressed application/json. Testah rejects unknown fields,
type coercion, duplicate JSON keys, non-finite numbers, mismatched identifiers,
unadvertised tool names, redirects and compressed bodies. Strict JSON Schema
documents shapes; parser and state rules also apply.

The request cap is 65536 serialized UTF-8 bytes. Responses default to 65536 bytes.
The total deadline defaults to 10 seconds, including DNS and the entire body;
operators can configure 1–60 seconds. Testah never automatically retries an agent
POST. Ensure your host is ready before testing a cold-starting endpoint.

The operator may configure a complete Authorization or X-API-Key header value
server-side; Testah adds no automatic Bearer prefix. This sample specification
describes optional Authorization authentication. Never place working credentials
in documentation, response bodies, URLs, protocol context or frontend builds.
The generated endpoint authentication heading may say "requires"; authentication
is optional unless the candidate operator enables it, as expressed by the source
OpenAPI's alternative empty security requirement.

The sample returns a detail string on 401 and FastAPI validation details on 422.
Testah exposes its own safe connector errors to the operator; raw remote errors
are not published. Do not confuse HTTP errors with structured gateway tool errors.


# Payment boundary and release limits

Only Testah's gateway can execute its commerce tools. Use integer minor-unit money
and authoritative tool results. Scenario authorization is separate from buyer
approval; an order or approval alone is not proof of capture. Real-money processing
is unsupported. Candidates do not receive payment operator credentials.

This release uses a trusted local operator workflow. Public multi-tenant onboarding
and public operational API deployment are deferred. No operational, administrative,
payment-operator, report or assessment-history API is included in this reference.



