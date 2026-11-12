# Tool Call Response

Source: /#/http/x-redirect/JTI0bSUyRlRvb2xDYWxsUmVzcG9uc2U

One request for a permitted tool; execution remains with Testah's gateway.


# Fields

| Name | Type | Tags | Description |
|  --- | --- | --- | --- |
| `protocol_version` | `String` | Required, Constant | **Value**: `1.0` |
| `request_id` | `String` | Required | **Constraints**: *Minimum Length*: `1`, *Maximum Length*: `128`, *Pattern*: `^[A-Za-z0-9_.:-]+$` |
| `session_id` | `String` | Required | **Constraints**: *Minimum Length*: `1`, *Maximum Length*: `128`, *Pattern*: `^[A-Za-z0-9_.:-]+$` |
| `tool_call` | [`Tool Call`](/llms-pages/http/models/structures/tool-call.md) | Required | A fresh run-scoped correlation, advertised tool name and argument object. |
| `type` | `String` | Required, Constant | **Value**: `tool_call` |


# Example (as JSON)

```json
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



