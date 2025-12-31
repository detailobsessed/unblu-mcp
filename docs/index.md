---
title: Overview
hide:
- feedback
---

# unblu-mcp

A [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server for interacting with [Unblu](https://www.unblu.com/) deployments. This server provides AI assistants with token-efficient access to 300+ Unblu API endpoints through progressive disclosure.

## Features

This server implements best practices from Anthropic's guide on [building effective agents](https://www.anthropic.com/engineering/building-effective-agents):

- **Progressive Disclosure** — 5 discovery tools instead of 300+ API definitions upfront, dramatically reducing token usage
- **Clear Tool Interfaces** — Descriptive parameters with examples, helpful error messages that suggest alternatives
- **Full API Coverage** — Access to all Unblu REST API v4 endpoints
- **Smart Discovery** — Search and browse operations by service category or keyword
- **Field Filtering** — Request only the fields you need to reduce response size
- **Response Truncation** — Limit response sizes to prevent token overflow

Built with [FastMCP 2.14+](https://github.com/jlowin/fastmcp), leveraging cutting-edge features:

- **MCP Annotations** — Tools include `readOnlyHint`, `destructiveHint`, and `openWorldHint` metadata for smarter AI decision-making
- **Response Caching** — Discovery tools cache results via FastMCP middleware for faster repeated queries
- **Policy-Based Authorization** — Optional [Eunomia](https://github.com/whataboutyou-ai/eunomia) integration for controlling which API operations are allowed
- **Built-in Logging** — Automatic file-based logging with daily rotation for debugging and usage analysis
- **MCP 2025-11-25 Spec** — Full support for the latest Model Context Protocol specification

## Quick Start

```bash
# Install
uv tool install unblu-mcp

# Run with K8s provider
unblu-mcp --provider k8s --environment dev

# Or with environment variables
UNBLU_BASE_URL=https://your-instance.unblu.cloud/app/rest/v4 \
UNBLU_API_KEY=your-key \
unblu-mcp
```

See [Getting Started](getting-started.md) for detailed installation and configuration instructions.

## Available Tools

| Tool | Description |
|------|-------------|
| `list_services()` | List all API service categories |
| `list_operations(service)` | List operations in a specific service |
| `search_operations(query)` | Search for operations by keyword |
| `get_operation_schema(operation_id)` | Get full schema for an operation |
| `call_api(operation_id, ...)` | Execute any API operation |

See [Available Tools](tools.md) for detailed usage examples.

## Security

!!! warning "Security First"
    This server includes built-in safety controls. The `call_api` tool is marked with `destructiveHint: true` to trigger client confirmations, and optional [Eunomia](https://github.com/whataboutyou-ai/eunomia) integration provides server-side policy enforcement to block destructive operations.

See [Safety & Authorization](safety.md) for details on configuring access controls.
