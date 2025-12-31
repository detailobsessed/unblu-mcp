---
title: Safety & Authorization
---

# Safety & Authorization

The `call_api` tool can execute **any** Unblu API operation, including destructive ones (DELETE, PUT, POST). This is a powerful capability that requires appropriate controls.

## Two Layers of Protection

| Layer | Type | Description |
|-------|------|-------------|
| **MCP Annotations** | Client-side | `destructiveHint: true` signals clients to prompt for confirmation |
| **Eunomia Policies** | Server-side | Block unauthorized operations before they execute |

## Layer 1: Tool Annotations (Built-in)

The `call_api` tool includes these MCP annotations:

- `destructiveHint: true` — Signals this tool may modify data
- `idempotentHint: false` — Repeated calls may have different effects
- `openWorldHint: true` — Interacts with external systems

Well-behaved MCP clients (like Claude Desktop) will prompt for user confirmation before executing tools marked as destructive.

## Layer 2: Policy-Based Authorization (Optional)

For **server-side enforcement**, use [Eunomia](https://github.com/whataboutyou-ai/eunomia) — a FastMCP middleware library for policy-based authorization — to define what operations are allowed:

```bash
# Install with safety features
pip install unblu-mcp[safety]

# Run with policy enforcement
unblu-mcp --policy config/mcp_policies.json
```

The included `config/mcp_policies.json` provides a sensible default using **regex pattern matching**:

| Operation Type | Policy | Pattern |
|----------------|--------|---------|
| Discovery tools | ✅ Allowed | Exact match: `list_services`, `list_operations`, `search_operations`, `get_operation_schema` |
| Read-only API calls | ✅ Allowed | Regex: operations ending with `Get`, `Search`, `List`, `Read`, `Find`, `Check`, `Count`, `Exists`, `Ping` |
| Destructive API calls | ❌ Blocked | Regex: operations containing `Create`, `Update`, `Delete`, `Set`, `Send`, `Login`, `Logout`, etc. |

This pattern-based approach automatically handles new API operations without policy updates.

### Programmatic Usage

You can also enable policy enforcement programmatically:

```python
from unblu_mcp import create_server

server = create_server(policy_file="/path/to/mcp_policies.json")
```

## Custom Policies

To allow additional operations beyond read-only, create a custom policy file.

### Example: Allow conversation operations

```json
{
  "version": "1.0",
  "name": "custom-policy",
  "default_effect": "deny",
  "rules": [
    {
      "name": "allow-all-discovery",
      "effect": "allow",
      "resource_conditions": [
        {"path": "attributes.tool_name", "operator": "in",
         "value": ["list_services", "list_operations", "search_operations", "get_operation_schema"]}
      ],
      "actions": ["execute"]
    },
    {
      "name": "allow-conversation-operations",
      "effect": "allow",
      "resource_conditions": [
        {"path": "attributes.tool_name", "operator": "eq", "value": "call_api"},
        {"path": "attributes.args.operation_id", "operator": "regex",
         "value": "^conversations(Get|Search|Read|Create|Update|Set)[A-Za-z]*$"}
      ],
      "actions": ["execute"]
    }
  ]
}
```

### Example: Allow all operations

To allow **all** operations (no restrictions):

```json
{
  "version": "1.0",
  "name": "allow-all",
  "default_effect": "allow",
  "rules": []
}
```

See the [Eunomia documentation](https://github.com/whataboutyou-ai/eunomia) for advanced policy configuration.
