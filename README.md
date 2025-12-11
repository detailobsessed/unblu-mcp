# unblu-mcp

[![ci](https://github.com/ichoosetoaccept/unblu-mcp/workflows/ci/badge.svg)](https://github.com/ichoosetoaccept/unblu-mcp/actions?query=workflow%3Aci)
[![documentation](https://img.shields.io/badge/docs-mkdocs-708FCC.svg?style=flat)](https://ichoosetoaccept.github.io/unblu-mcp/)
[![pypi version](https://img.shields.io/pypi/v/unblu-mcp.svg)](https://pypi.org/project/unblu-mcp/)
[![gitter](https://img.shields.io/badge/matrix-chat-4DB798.svg?style=flat)](https://app.gitter.im/#/room/#unblu-mcp:gitter.im)

A **token-efficient** Model Context Protocol (MCP) server for interacting with [Unblu](https://www.unblu.com/) deployments.

## Features

- **Progressive Disclosure**: Instead of exposing all 331 API endpoints as individual tools (which would consume ~150k+ tokens), this server uses 5 meta-tools for discovery and execution
- **~98% Token Reduction**: Based on [Anthropic's code execution patterns](https://www.anthropic.com/engineering/code-execution-with-mcp) for efficient agent-tool interaction
- **Full API Coverage**: Access to all Unblu Web API v4 endpoints across 44 service categories
- **Built with FastMCP**: Modern, async MCP server implementation

## Architecture

This server implements the "progressive disclosure" pattern recommended by Anthropic:

| Tool | Purpose |
|------|---------|
| `list_services()` | Discover available API service categories (44 services) |
| `list_operations(service)` | List operations within a specific service |
| `search_operations(query)` | Find operations by keyword |
| `get_operation_schema(operation_id)` | Get full parameter schema for an operation |
| `call_api(operation_id, ...)` | Execute any API operation |

## Installation

```bash
pip install unblu-mcp
```

With [`uv`](https://docs.astral.sh/uv/):

```bash
uv tool install unblu-mcp
```

## Configuration

Set environment variables for authentication:

```bash
# Option 1: API Key (Bearer token)
export UNBLU_API_KEY="your-api-key"

# Option 2: Basic Auth
export UNBLU_USERNAME="your-username"
export UNBLU_PASSWORD="your-password"

# Optional: Custom base URL (defaults to https://unblu.cloud/app/rest/v4)
export UNBLU_BASE_URL="https://your-instance.unblu.cloud/app/rest/v4"
```

## Usage

### As an MCP Server

Add to your MCP client configuration (e.g., Claude Desktop):

```json
{
  "mcpServers": {
    "unblu": {
      "command": "unblu-mcp",
      "args": ["--spec", "/path/to/swagger.json"],
      "env": {
        "UNBLU_API_KEY": "your-api-key"
      }
    }
  }
}
```

### Example Workflow

```
User: List all conversations for user X

Agent:
1. list_services() → sees "Conversations" service
2. list_operations("Conversations") → finds "conversationsSearch"
3. get_operation_schema("conversationsSearch") → learns required parameters
4. call_api("conversationsSearch", body={"personId": "X"}) → gets results
```

### CLI

```bash
# Run with stdio transport (default)
unblu-mcp

# Run with SSE transport
unblu-mcp --transport sse

# Specify custom OpenAPI spec
unblu-mcp --spec /path/to/swagger.json
```
