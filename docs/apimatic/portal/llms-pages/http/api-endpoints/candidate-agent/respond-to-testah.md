# Respond to Testah

Source: /#/http/x-redirect/JTI0ZSUyRkNhbmRpZGF0ZSUyNTIwYWdlbnQlMkZyZXNwb25kVG9UZXN0YWg

Implement this POST on the external candidate service. Send HTTP 200 with uncompressed application/json. Return exactly one message, tool_call, or completed response; echo identifiers exactly. Only advertised tools may be requested. Use a fresh tool correlation_id for each call within a run. Testah sends the gateway result in previous_tool_result on a subsequent exchange. Requests are limited to 65536 serialized UTF-8 bytes; responses default to 65536 bytes. The total exchange deadline defaults to 10 seconds (operator-configurable from 1 to 60). Testah never automatically retries this POST. Redirects and compressed responses are rejected. Authentication and validation errors documented here describe the standalone FastAPI sample; Testah maps non-success HTTP responses to its own safe connector errors.

```http
POST /agent
```


# Authentication

This endpoint requires [CandidateAuthorization]($h/__auth_CustomHeaderAuthentication)


# Parameters

| Parameter | Type | Tags | Description |
|  --- | --- | --- | --- |
| `body` | [`Agent Request`](/llms-pages/http/models/structures/agent-request.md) | Body, Required | Strict candidate request. All examples are synthetic; the probe executes no tools. |


# Response Type

**200**: Successful Response

[`Message Response | Tool Call Response | Completed Response`](/llms-pages/http/models/oneof-anyof-definitions/agent-response.md)


# Example Usage

```bash
curl -X POST \
  --url 'https://candidate.invalid/agent'  \
  -H 'Accept: application/json' \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Authorization' \
  --data-raw '{
  "message": {
    "content": "Please confirm protocol compatibility.",
    "role": "user"
  },
  "protocol_version": "1.0",
  "request_id": "request-demo-001",
  "session_id": "connection-test-demo-001"
}'
```


# Errors

| HTTP Status Code | Error Description | Exception Class |
|  --- | --- | --- |
| 401 | The sample rejects missing or incorrect authentication when its optional token is configured. | [`Agent 401 ErrorException`](/llms-pages/http/models/exceptions/agent-401-error.md) |
| 422 | Validation Error | [`HTTPValidationError_ErrorException`](/llms-pages/http/models/exceptions/http-validation-error-error.md) |



