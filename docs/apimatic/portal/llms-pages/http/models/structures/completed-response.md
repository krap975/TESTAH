# Completed Response

Source: /#/http/x-redirect/JTI0bSUyRkNvbXBsZXRlZFJlc3BvbnNl

A candidate completion claim, independently verified by the controller.


# Fields

| Name | Type | Tags | Description |
|  --- | --- | --- | --- |
| `protocol_version` | `String` | Required, Constant | **Value**: `1.0` |
| `request_id` | `String` | Required | **Constraints**: *Minimum Length*: `1`, *Maximum Length*: `128`, *Pattern*: `^[A-Za-z0-9_.:-]+$` |
| `session_id` | `String` | Required | **Constraints**: *Minimum Length*: `1`, *Maximum Length*: `128`, *Pattern*: `^[A-Za-z0-9_.:-]+$` |
| `summary` | `String` | Required | **Constraints**: *Minimum Length*: `1`, *Maximum Length*: `16000` |
| `type` | `String` | Required, Constant | **Value**: `completed` |


# Example (as JSON)

```json
{
  "protocol_version": "1.0",
  "request_id": "request-demo-001",
  "session_id": "connection-test-demo-001",
  "summary": "Protocol demonstration finished; no purchase was performed.",
  "type": "completed"
}
```



