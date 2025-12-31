---
title: Logging & Observability
---

# Logging & Observability

The server automatically logs all tool calls to help with debugging and usage analysis.

## Log Location

Logs are written to `~/.unblu-mcp/logs/` with daily rotation:

```text
~/.unblu-mcp/logs/
├── unblu-mcp.log              # Current log
├── unblu-mcp.log.2025-01-14   # Yesterday
├── unblu-mcp.log.2025-01-13   # Day before
└── ...
```

## Configuration

| Environment Variable | Description |
|---------------------|-------------|
| `UNBLU_MCP_LOG_DIR` | Custom log directory (default: `~/.unblu-mcp/logs`) |
| `UNBLU_MCP_LOG_DISABLE` | Set to `1`, `true`, or `yes` to disable file logging |

## Log Format

```text
2025-01-15 14:30:22 | INFO     | fastmcp | tools/call request: call_api(operation_id="conversationsGetById", ...)
```

Logs include:

- **Timestamp** (UTC)
- **Log level** (DEBUG, INFO, WARNING, ERROR)
- **Tool name and arguments**
- **Response summaries**
- **Request duration** (`duration_ms`) for performance analysis

## Retention

Logs are retained for **30 days** and automatically rotated at midnight UTC.

## Viewing Logs

### macOS/Linux

```bash
# Follow logs in real-time
tail -f ~/.unblu-mcp/logs/unblu-mcp.log

# Search for errors
grep -i error ~/.unblu-mcp/logs/unblu-mcp.log

# View logs from a specific date
cat ~/.unblu-mcp/logs/unblu-mcp.log.2025-01-14
```

### Windows

```powershell
# View recent logs
Get-Content $env:USERPROFILE\.unblu-mcp\logs\unblu-mcp.log -Tail 100

# Follow logs in real-time
Get-Content $env:USERPROFILE\.unblu-mcp\logs\unblu-mcp.log -Wait
```
