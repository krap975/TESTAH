# Previous Tool Result

Source: /#/http/x-redirect/JTI0bSUyRlByZXZpb3VzVG9vbFJlc3VsdA


# Fields

| Name | Type | Tags | Description |
|  --- | --- | --- | --- |
| `correlation_id` | `String` | Optional | **Constraints**: *Minimum Length*: `1`, *Maximum Length*: `128`, *Pattern*: `^[A-Za-z0-9_.:-]+$` |
| `name` | `String` | Optional | **Constraints**: *Minimum Length*: `1`, *Maximum Length*: `128`, *Pattern*: `^[A-Za-z0-9_.:-]+$` |
| `result` | [`map<String \| Decimal \| Boolean \| Any \| Object>`](/llms-pages/http/models/oneof-anyof-definitions/json-value.md) | Optional | - |
| `status` | [`Status`](/llms-pages/http/models/enumerations/status.md) | Optional | - |


# Example (as JSON)

```json
{
  "correlation_id": "correlation_id2",
  "name": "name8",
  "result": {
    "key0": "String7",
    "key1": "String6",
    "key2": "String5"
  },
  "status": "success"
}
```



