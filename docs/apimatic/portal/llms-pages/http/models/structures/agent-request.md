# Agent Request

Source: /#/http/x-redirect/JTI0bSUyRkFnZW50UmVxdWVzdA

One bounded version 1.0 exchange sent by Testah to the candidate.


# Fields

| Name | Type | Tags | Description |
|  --- | --- | --- | --- |
| `available_tools` | [`array<Tool Definition>`](/llms-pages/http/models/structures/tool-definition.md) | Optional | **Constraints**: *Maximum Items*: `50` |
| `context` | [`map<String \| Decimal \| Boolean \| Any \| Object>`](/llms-pages/http/models/oneof-anyof-definitions/json-value.md) | Optional | - |
| `history` | [`array<Message>`](/llms-pages/http/models/structures/message.md) | Optional | **Constraints**: *Maximum Items*: `100` |
| `message` | [`Customer Message`](/llms-pages/http/models/structures/customer-message.md) | Required | The current customer message supplied by Testah. |
| `previous_tool_result` | [`Tool Result`](/llms-pages/http/models/oneof-anyof-definitions/agent-request-previous-tool-result.md) | Optional | - |
| `protocol_version` | `String` | Required, Constant | **Value**: `1.0` |
| `request_id` | `String` | Required | **Constraints**: *Minimum Length*: `1`, *Maximum Length*: `128`, *Pattern*: `^[A-Za-z0-9_.:-]+$` |
| `session_id` | `String` | Required | **Constraints**: *Minimum Length*: `1`, *Maximum Length*: `128`, *Pattern*: `^[A-Za-z0-9_.:-]+$` |


# Example (as JSON)

```json
{
  "message": {
    "content": "Please confirm protocol compatibility.",
    "role": "user"
  },
  "protocol_version": "1.0",
  "request_id": "request-demo-001",
  "session_id": "connection-test-demo-001"
}
```



