# Tool Result

Source: /#/http/x-redirect/JTI0bSUyRlRvb2xSZXN1bHQ

A correlated gateway success or safe error, supplied on a subsequent exchange.


# Fields

| Name | Type | Tags | Description |
|  --- | --- | --- | --- |
| `correlation_id` | `String` | Required | **Constraints**: *Minimum Length*: `1`, *Maximum Length*: `128`, *Pattern*: `^[A-Za-z0-9_.:-]+$` |
| `name` | `String` | Required | **Constraints**: *Minimum Length*: `1`, *Maximum Length*: `128`, *Pattern*: `^[A-Za-z0-9_.:-]+$` |
| `result` | [`map<String \| Decimal \| Boolean \| Any \| Object>`](/llms-pages/http/models/oneof-anyof-definitions/json-value.md) | Required | - |
| `status` | [`Status`](/llms-pages/http/models/enumerations/status.md) | Required | - |


# Example (as JSON)

```json
{
  "correlation_id": "correlation_id4",
  "name": "name0",
  "result": {
    "key0": "String3"
  },
  "status": "success"
}
```



