---
title: Available Tools
---

# Available Tools

The server exposes 5 tools for progressive API discovery and execution:

| Tool | Description |
|------|-------------|
| `list_services()` | List all API service categories (e.g., Conversations, Users, Bots) |
| `list_operations(service)` | List operations in a specific service |
| `search_operations(query)` | Search for operations by keyword |
| `get_operation_schema(operation_id)` | Get full schema for an operation |
| `call_api(operation_id, ...)` | Execute any API operation |

## Example Workflow

1. **Discover services**: `list_services()` → See categories like "Conversations", "Users", "Bots"
2. **Browse operations**: `list_operations("Conversations")` → See available conversation operations
3. **Get details**: `get_operation_schema("conversationsGetById")` → See required parameters
4. **Execute**: `call_api("conversationsGetById", path_params={"conversationId": "abc123"})`

## Advanced Options

The `call_api` tool supports additional parameters for token efficiency:

```python
call_api(
    operation_id="conversationsSearch",
    body={"query": "support"},
    fields=["id", "topic", "creationTimestamp"],  # Only return these fields
    max_response_size=10000  # Truncate response if larger than 10KB
)
```

### Field Filtering

Use the `fields` parameter to request only specific fields from the response. This dramatically reduces token usage for large responses:

```python
# Instead of getting the full conversation object with all fields
call_api("conversationsGetById", path_params={"conversationId": "abc123"})

# Request only the fields you need
call_api(
    "conversationsGetById",
    path_params={"conversationId": "abc123"},
    fields=["id", "topic", "state", "creationTimestamp"]
)
```

Nested fields are supported using dot notation:

```python
fields=["id", "participant.name", "participant.email"]
```

### Response Truncation

Use `max_response_size` to limit response size in bytes. This prevents token overflow when dealing with large lists:

```python
call_api(
    "conversationsSearch",
    body={"query": "support"},
    max_response_size=5000  # Truncate to ~5KB
)
```

When truncated, the response includes metadata about what was cut:

```json
{
  "_truncated": true,
  "_size": 125000,
  "_limit": 5000,
  "data": {"count": 500, "first_items": [...]}
}
```
