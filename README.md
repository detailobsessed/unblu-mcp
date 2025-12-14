# unblu-mcp

[![ci](https://github.com/ichoosetoaccept/unblu-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/ichoosetoaccept/unblu-mcp/actions/workflows/ci.yml)
[![documentation](https://img.shields.io/badge/docs-mkdocs-708FCC.svg?style=flat)](https://ichoosetoaccept.github.io/unblu-mcp/)

A [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server for interacting with [Unblu](https://www.unblu.com/) deployments. This server provides AI assistants with token-efficient access to 300+ Unblu API endpoints through progressive disclosure.

## Features

This server implements best practices from Anthropic's guide on [building effective agents](https://www.anthropic.com/engineering/building-effective-agents):

- **Progressive Disclosure**: 5 discovery tools instead of 300+ API definitions upfront, dramatically reducing token usage
- **Clear Tool Interfaces**: Descriptive parameters with examples, helpful error messages that suggest alternatives
- **Full API Coverage**: Access to all Unblu REST API v4 endpoints
- **Smart Discovery**: Search and browse operations by service category or keyword
- **Field Filtering**: Request only the fields you need to reduce response size
- **Response Truncation**: Limit response sizes to prevent token overflow

Built with [FastMCP 2.14+](https://github.com/jlowin/fastmcp), leveraging cutting-edge features:

- **MCP Annotations**: Tools include `readOnlyHint` and `openWorldHint` metadata for smarter AI decision-making
- **Response Caching**: Discovery tools cache results via FastMCP middleware for faster repeated queries
- **MCP 2025-11-25 Spec**: Full support for the latest Model Context Protocol specification

## Installation

### From source (recommended)

```bash
git clone https://github.com/ichoosetoaccept/unblu-mcp.git
cd unblu-mcp
uv sync
```

## Configuration

### Environment Variables

The server requires the following environment variables:

| Variable | Required | Description |
|----------|----------|-------------|
| `UNBLU_BASE_URL` | No | Your Unblu API base URL (default: `https://unblu.cloud/app/rest/v4`) |
| `UNBLU_API_KEY` | One of these | API key for authentication (Bearer token) |
| `UNBLU_USERNAME` | One of these | Username for basic authentication |
| `UNBLU_PASSWORD` | With username | Password for basic authentication |

### MCP Client Configuration

Add the following to your MCP client configuration:

#### Claude Desktop / Windsurf (macOS)

Edit `~/Library/Application Support/Claude/claude_desktop_config.json` or your IDE's MCP config:

```json
{
  "mcpServers": {
    "unblu": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/unblu-mcp", "unblu-mcp"],
      "env": {
        "UNBLU_BASE_URL": "https://your-instance.unblu.cloud/app/rest/v4",
        "UNBLU_API_KEY": "your-api-key"
      }
    }
  }
}
```

> **Note**: Replace `/path/to/unblu-mcp` with the actual path where you cloned the repository.

#### Claude Desktop (Windows)

Edit `%APPDATA%\Claude\claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "unblu": {
      "command": "uv",
      "args": ["run", "--directory", "C:\\path\\to\\unblu-mcp", "unblu-mcp"],
      "env": {
        "UNBLU_BASE_URL": "https://your-instance.unblu.cloud/app/rest/v4",
        "UNBLU_API_KEY": "your-api-key"
      }
    }
  }
}
```

#### With Basic Authentication

```json
{
  "mcpServers": {
    "unblu": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/unblu-mcp", "unblu-mcp"],
      "env": {
        "UNBLU_BASE_URL": "https://your-instance.unblu.cloud/app/rest/v4",
        "UNBLU_USERNAME": "your-username",
        "UNBLU_PASSWORD": "your-password"
      }
    }
  }
}
```

## Available Tools

The server exposes 5 tools for progressive API discovery and execution:

| Tool | Description |
|------|-------------|
| `list_services()` | List all API service categories (e.g., Conversations, Users, Bots) |
| `list_operations(service)` | List operations in a specific service |
| `search_operations(query)` | Search for operations by keyword |
| `get_operation_schema(operation_id)` | Get full schema for an operation |
| `call_api(operation_id, ...)` | Execute any API operation |

### Example Workflow

1. **Discover services**: `list_services()` → See categories like "Conversations", "Users", "Bots"
2. **Browse operations**: `list_operations("Conversations")` → See available conversation operations
3. **Get details**: `get_operation_schema("conversationsGetById")` → See required parameters
4. **Execute**: `call_api("conversationsGetById", path_params={"conversationId": "abc123"})`

### Advanced Options

The `call_api` tool supports additional parameters for token efficiency:

```python
call_api(
    operation_id="conversationsSearch",
    body={"query": "support"},
    fields=["id", "topic", "creationTimestamp"],  # Only return these fields
    max_response_size=10000  # Truncate response if larger than 10KB
)
```

## Command Line Usage

```bash
# Run with stdio transport (default, for MCP clients)
unblu-mcp

# Run with SSE transport (for web-based clients)
unblu-mcp --transport sse

# Use a custom swagger.json location
unblu-mcp --spec /path/to/swagger.json

# Show version
unblu-mcp --version

# Show debug info
unblu-mcp --debug-info
```

## Development

```bash
# Clone the repository
git clone https://github.com/ichoosetoaccept/unblu-mcp.git
cd unblu-mcp

# Install dependencies
uv sync --all-extras --dev

# Run tests
uv run poe test

# Run linting
uv run poe lint

# Build documentation
uv run poe docs
```

## License

ISC License
