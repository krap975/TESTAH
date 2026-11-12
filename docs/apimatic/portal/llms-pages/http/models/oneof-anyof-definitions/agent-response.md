# Agent Response

Source: /#/http/x-redirect/JTI0bSUyRkFnZW50UmVzcG9uc2U

Exactly one response variant, selected by type; identifiers must match the request.


# Data Type

`Message Response | Tool Call Response | Completed Response`


# Cases

| Type |
|  --- |
| [`Message Response`](/llms-pages/http/models/structures/message-response.md) |
| [`Tool Call Response`](/llms-pages/http/models/structures/tool-call-response.md) |
| [`Completed Response`](/llms-pages/http/models/structures/completed-response.md) |


# Message Response

## Initialization Code

### Example

```bash
{
  "message": "Protocol request received.",
  "protocol_version": "1.0",
  "request_id": "request-demo-001",
  "session_id": "connection-test-demo-001",
  "type": "message"
}
```


# Tool Call Response

## Initialization Code

### Example

```bash
{
  "protocol_version": "1.0",
  "request_id": "request-demo-001",
  "session_id": "connection-test-demo-001",
  "tool_call": {
    "arguments": {
      "text": "Example only."
    },
    "correlation_id": "call-demo-001",
    "name": "test_echo"
  },
  "type": "tool_call"
}
```


# Completed Response

## Initialization Code

### Example

```bash
{
  "protocol_version": "1.0",
  "request_id": "request-demo-001",
  "session_id": "connection-test-demo-001",
  "summary": "Protocol demonstration finished; no purchase was performed.",
  "type": "completed"
}
```



