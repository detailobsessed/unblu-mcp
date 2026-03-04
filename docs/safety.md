---
title: Safety
---

# Safety

`execute_operation` can run **any** Unblu API operation, including destructive ones. Two built-in mechanisms protect against accidental damage.

## MCP Annotations (client-side)

`execute_operation` is annotated with:

- `destructiveHint: true` — Signals to MCP clients that this tool may modify data
- `idempotentHint: false` — Repeated calls may have different effects
- `openWorldHint: true` — Interacts with external systems

Well-behaved MCP clients (e.g. Claude Desktop) will prompt for user confirmation before calling tools marked as destructive.

## DELETE safety gate (server-side)

`execute_operation` enforces an explicit confirmation step for all `DELETE` operations. Calling a DELETE without acknowledgement returns an error describing exactly what would be deleted:

```
Operation 'botDelete' is a DELETE (/bots/{botId}/delete).
This will permanently remove data.
Call again with confirm_destructive=True to proceed.
```

Re-calling with `confirm_destructive=True` executes the operation. This prevents accidental data deletion even if an MCP client ignores the destructive annotation.
