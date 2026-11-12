# Message Response

Source: /#/http/x-redirect/JTI0bSUyRk1lc3NhZ2VSZXNwb25zZQ

A conversational reply, without a tool request or completion claim.


# Fields

| Name | Type | Tags | Description |
|  --- | --- | --- | --- |
| `message` | `String` | Required | **Constraints**: *Minimum Length*: `1`, *Maximum Length*: `16000` |
| `protocol_version` | `String` | Required, Constant | **Value**: `1.0` |
| `request_id` | `String` | Required | **Constraints**: *Minimum Length*: `1`, *Maximum Length*: `128`, *Pattern*: `^[A-Za-z0-9_.:-]+$` |
| `session_id` | `String` | Required | **Constraints**: *Minimum Length*: `1`, *Maximum Length*: `128`, *Pattern*: `^[A-Za-z0-9_.:-]+$` |
| `type` | `String` | Required, Constant | **Value**: `message` |


# Example (as JSON)

```json
{
  "message": "Protocol request received.",
  "protocol_version": "1.0",
  "request_id": "request-demo-001",
  "session_id": "connection-test-demo-001",
  "type": "message"
}
```



