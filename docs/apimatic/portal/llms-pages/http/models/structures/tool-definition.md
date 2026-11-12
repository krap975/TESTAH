# Tool Definition

Source: /#/http/x-redirect/JTI0bSUyRlRvb2xEZWZpbml0aW9u

An advertised name, description and argument schema; not execution authority.


# Fields

| Name | Type | Tags | Description |
|  --- | --- | --- | --- |
| `description` | `String` | Required | **Constraints**: *Minimum Length*: `1`, *Maximum Length*: `2000` |
| `input_schema` | [`map<String \| Decimal \| Boolean \| Any \| Object>`](/llms-pages/http/models/oneof-anyof-definitions/json-value.md) | Required | - |
| `name` | `String` | Required | **Constraints**: *Minimum Length*: `1`, *Maximum Length*: `128`, *Pattern*: `^[A-Za-z0-9_.:-]+$` |


# Example (as JSON)

```json
{
  "description": "description8",
  "input_schema": {
    "key0": "String7"
  },
  "name": "name8"
}
```



