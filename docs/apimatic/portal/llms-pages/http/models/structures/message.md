# Message

Source: /#/http/x-redirect/JTI0bSUyRk1lc3NhZ2U

An ordered public history message; tool content contains serialized JSON.


# Fields

| Name | Type | Tags | Description |
|  --- | --- | --- | --- |
| `content` | `String` | Required | **Constraints**: *Minimum Length*: `1`, *Maximum Length*: `16000` |
| `role` | [`Role`](/llms-pages/http/models/enumerations/role.md) | Required | - |


# Example (as JSON)

```json
{
  "content": "content0",
  "role": "assistant"
}
```



