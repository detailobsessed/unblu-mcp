# unblu-mcp

[![ci](https://github.com/detailobsessed/unblu-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/detailobsessed/unblu-mcp/actions/workflows/ci.yml)
[![documentation](https://img.shields.io/badge/docs-mkdocs-708FCC.svg?style=flat)](https://detailobsessed.github.io/unblu-mcp/)

A [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server for interacting with [Unblu](https://www.unblu.com/) deployments. This server provides AI assistants with token-efficient access to 300+ Unblu API endpoints through progressive disclosure.

> **🔒 Security First**: This server includes built-in safety controls. The `call_api` tool is marked with `destructiveHint: true` to trigger client confirmations, and optional [Eunomia](https://github.com/whataboutyou-ai/eunomia) integration provides server-side policy enforcement to block destructive operations. [Learn more →](#safety--authorization)

## Features

This server implements best practices from Anthropic's guide on [building effective agents](https://www.anthropic.com/engineering/building-effective-agents):

- **Progressive Disclosure**: 5 discovery tools instead of 300+ API definitions upfront, dramatically reducing token usage
- **Clear Tool Interfaces**: Descriptive parameters with examples, helpful error messages that suggest alternatives
- **Full API Coverage**: Access to all Unblu REST API v4 endpoints
- **Smart Discovery**: Search and browse operations by service category or keyword
- **Field Filtering**: Request only the fields you need to reduce response size
- **Response Truncation**: Limit response sizes to prevent token overflow

Built with [FastMCP 2.14+](https://github.com/jlowin/fastmcp), leveraging cutting-edge features:

- **MCP Annotations**: Tools include `readOnlyHint`, `destructiveHint`, and `openWorldHint` metadata for smarter AI decision-making
- **Response Caching**: Discovery tools cache results via FastMCP middleware for faster repeated queries
- **Policy-Based Authorization**: Optional [Eunomia](https://github.com/whataboutyou-ai/eunomia) integration for controlling which API operations are allowed
- **Built-in Logging**: Automatic file-based logging with daily rotation for debugging and usage analysis
- **MCP 2025-11-25 Spec**: Full support for the latest Model Context Protocol specification

## Installation

### From source (recommended)

```bash
git clone https://github.com/detailobsessed/unblu-mcp.git
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

# Run with Eunomia authorization policy (requires unblu-mcp[safety])
unblu-mcp --policy /path/to/mcp_policies.json

# Show version
unblu-mcp --version

# Show debug info
unblu-mcp --debug-info
```

## Logging & Observability

The server automatically logs all tool calls to help with debugging and usage analysis.

### Log Location

Logs are written to `~/.unblu-mcp/logs/` with daily rotation:

```
~/.unblu-mcp/logs/
├── unblu-mcp.log              # Current log
├── unblu-mcp.log.2025-01-14   # Yesterday
├── unblu-mcp.log.2025-01-13   # Day before
└── ...
```

### Configuration

| Environment Variable | Description |
|---------------------|-------------|
| `UNBLU_MCP_LOG_DIR` | Custom log directory (default: `~/.unblu-mcp/logs`) |
| `UNBLU_MCP_LOG_DISABLE` | Set to `1`, `true`, or `yes` to disable file logging |

### Log Format

```
2025-01-15 14:30:22 | INFO     | fastmcp | tools/call request: call_api(operation_id="conversationsGetById", ...)
```

Logs include:
- Timestamp (UTC)
- Log level
- Tool name and arguments
- Response summaries

Logs are retained for 30 days and automatically rotated at midnight UTC.

## Safety & Authorization

The `call_api` tool can execute **any** Unblu API operation, including destructive ones (DELETE, PUT, POST). This is a powerful capability that requires appropriate controls.

### Two Layers of Protection

| Layer | Type | Description |
|-------|------|-------------|
| **MCP Annotations** | Client-side | `destructiveHint: true` signals clients to prompt for confirmation |
| **Eunomia Policies** | Server-side | Block unauthorized operations before they execute |

### Layer 1: Tool Annotations (Built-in)

The `call_api` tool includes these MCP annotations:
- `destructiveHint: true` — Signals this tool may modify data
- `idempotentHint: false` — Repeated calls may have different effects
- `openWorldHint: true` — Interacts with external systems

Well-behaved MCP clients (like Claude Desktop) will prompt for user confirmation before executing tools marked as destructive.

### Layer 2: Policy-Based Authorization (Optional)

For **server-side enforcement**, use [Eunomia](https://github.com/whataboutyou-ai/eunomia) to define what operations are allowed:

```bash
# Install with safety features
pip install unblu-mcp[safety]

# Run with policy enforcement
unblu-mcp --policy config/mcp_policies.json
```

The included `config/mcp_policies.json` provides a sensible default:

| Operation Type | Policy |
|----------------|--------|
| Discovery tools | ✅ Allowed |
| Read-only API calls (GET) | ✅ Allowed |
| Destructive API calls (DELETE) | ❌ Blocked |

#### Custom Policies

Generate a policy tailored to your server:

```bash
eunomia-mcp init --custom-mcp "unblu_mcp._internal.server:mcp"
eunomia-mcp validate mcp_policies.json
```

See the [Eunomia documentation](https://github.com/whataboutyou-ai/eunomia) for advanced policy configuration.

## Programmatic Usage

### Connection Providers

The server supports pluggable connection providers for different deployment scenarios:

```python
from unblu_mcp import create_server, DefaultConnectionProvider

# Default provider (uses environment variables)
server = create_server()

# Custom provider with explicit credentials
provider = DefaultConnectionProvider(
    base_url="https://my-instance.unblu.cloud/app/rest/v4",
    api_key="my-api-key",
)
server = create_server(provider=provider)
```

#### Kubernetes Port-Forward Provider

For Kubernetes deployments, use the built-in K8s provider:

```python
from unblu_mcp import create_server, K8sConnectionProvider

# Connect to a K8s environment (starts kubectl port-forward automatically)
provider = K8sConnectionProvider(environment="t1")
server = create_server(provider=provider)
```

K8s environments are configured in `~/.unblu-mcp/k8s_environments.yaml`:

```yaml
environments:
  t1:
    local_port: 8084
    namespace: unblu-t1
    service: haproxy
    service_port: 8080
    api_path: /kop/rest/v4
```

#### Custom Connection Providers

Implement the `ConnectionProvider` interface for custom connectivity:

```python
from unblu_mcp import ConnectionProvider, ConnectionConfig

class MyProvider(ConnectionProvider):
    async def setup(self) -> None:
        # Initialize connection (e.g., start tunnel)
        pass

    async def teardown(self) -> None:
        # Clean up resources
        pass

    def get_config(self) -> ConnectionConfig:
        return ConnectionConfig(
            base_url="https://api.example.com",
            headers={"X-Custom-Header": "value"},
        )
```

## Development

```bash
# Clone the repository
git clone https://github.com/detailobsessed/unblu-mcp.git
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
