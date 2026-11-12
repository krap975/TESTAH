# Tool Call

Source: /#/http/x-redirect/JTI0bSUyRlRvb2xDYWxs

A fresh run-scoped correlation, advertised tool name and argument object.


# Fields

| Name | Type | Tags | Description |
|  --- | --- | --- | --- |
| `arguments` | [`map<String \| Decimal \| Boolean \| Any \| Object>`](/llms-pages/http/models/oneof-anyof-definitions/json-value.md) | Required | - |
| `correlation_id` | `String` | Required | **Constraints**: *Minimum Length*: `1`, *Maximum Length*: `128`, *Pattern*: `^[A-Za-z0-9_.:-]+$` |
| `name` | `String` | Required | **Constraints**: *Minimum Length*: `1`, *Maximum Length*: `128`, *Pattern*: `^[A-Za-z0-9_.:-]+$` |


# Example (as JSON)

```json
{
  "arguments": {
    "key0": "String8",
    "key1": "String7",
    "key2": "String6"
  },
  "correlation_id": "correlation_id0",
  "name": "name6"
}
```



