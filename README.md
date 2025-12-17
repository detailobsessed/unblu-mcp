# unblu-mcp

[![ci](https://github.com/detailobsessed/unblu-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/detailobsessed/unblu-mcp/actions/workflows/ci.yml)
[![documentation](https://img.shields.io/badge/docs-mkdocs-708FCC.svg?style=flat)](https://detailobsessed.github.io/unblu-mcp/)
[![pypi version](https://img.shields.io/pypi/v/unblu-mcp.svg)](https://pypi.org/project/unblu-mcp/)
[![python versions](https://img.shields.io/pypi/pyversions/unblu-mcp.svg)](https://pypi.org/project/unblu-mcp/)
[![license](https://img.shields.io/pypi/l/unblu-mcp.svg)](https://github.com/detailobsessed/unblu-mcp/blob/main/LICENSE)
[![FastMCP](https://img.shields.io/badge/FastMCP-2.14+-00ADD8.svg)](https://github.com/jlowin/fastmcp)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)

A [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server for interacting with [Unblu](https://www.unblu.com/) deployments. This server provides AI assistants with token-efficient access to 300+ Unblu API endpoints through progressive disclosure.

## Table of Contents

- [Features](#features)
- [Installation](#installation)
- [Configuration](#configuration)
- [Available Tools](#available-tools)
- [Command Line Usage](#command-line-usage)
- [Logging & Observability](#logging--observability)
- [Safety & Authorization](#safety--authorization)
- [Programmatic Usage](#programmatic-usage)
- [Troubleshooting](#troubleshooting)
- [Development](#development)
- [License](#license)

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

This package is available on [PyPI](https://pypi.org/project/unblu-mcp/) and designed to be run directly via `uvx` - no installation required. See [MCP Client Configuration](#mcp-client-configuration) below.

For development or customization, clone from source:

### From source

```bash
git clone https://github.com/detailobsessed/unblu-mcp.git
cd unblu-mcp
uv sync
```

## Configuration

### MCP Client Configuration

Add the server to your MCP client configuration (Claude Desktop, Windsurf, etc.):

#### With Kubernetes Provider (recommended for internal deployments)

The K8s provider automatically manages `kubectl port-forward` connections to your Unblu deployment. This is the most tested configuration.

**macOS** (`~/Library/Application Support/Claude/claude_desktop_config.json` or IDE MCP config):

```json
{
  "mcpServers": {
    "unblu": {
      "command": "uvx",
      "args": ["unblu-mcp", "--provider", "k8s", "--environment", "dev"]
    }
  }
}
```

**Windows** (`%APPDATA%\Claude\claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "unblu": {
      "command": "uvx",
      "args": ["unblu-mcp", "--provider", "k8s", "--environment", "dev"]
    }
  }
}
```

See [K8s Provider Configuration](#kubernetes-provider) below for setting up your environments.

#### With Environment Variables

For direct API access without Kubernetes:

```json
{
  "mcpServers": {
    "unblu": {
      "command": "uvx",
      "args": ["unblu-mcp"],
      "env": {
        "UNBLU_BASE_URL": "https://your-instance.unblu.cloud/app/rest/v4",
        "UNBLU_API_KEY": "your-api-key"
      }
    }
  }
}
```

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `UNBLU_BASE_URL` | No | Your Unblu API base URL (default: `https://unblu.cloud/app/rest/v4`) |
| `UNBLU_API_KEY` | One of these | API key for authentication (Bearer token) |
| `UNBLU_USERNAME` | One of these | Username for basic authentication |
| `UNBLU_PASSWORD` | With username | Password for basic authentication |

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

# Use a custom swagger.json location
unblu-mcp --spec /path/to/swagger.json

# Run with Eunomia authorization policy (requires unblu-mcp[safety])
unblu-mcp --policy /path/to/mcp_policies.json

# Run with K8s provider (auto-starts kubectl port-forward)
unblu-mcp --provider k8s --environment dev

# Run with K8s provider using custom config file
unblu-mcp --provider k8s --environment my-env --k8s-config /path/to/k8s_environments.yaml

# Show version
unblu-mcp --version

# Show debug info
unblu-mcp --debug-info
```

### CLI Arguments

| Argument | Values | Default | Description |
|----------|--------|---------|-------------|
| `--spec` | path | auto-detect | Path to swagger.json |
| `--policy` | path | none | Eunomia policy file |
| `--provider` | `default`, `k8s` | `default` | Connection provider |
| `--environment` | string | `dev` | K8s environment (with `--provider k8s`) |
| `--k8s-config` | path | none | Custom K8s environments YAML file |

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
- **Request duration** (`duration_ms`) for performance analysis

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

For **server-side enforcement**, use [Eunomia](https://github.com/whataboutyou-ai/eunomia) — a FastMCP middleware library for policy-based authorization — to define what operations are allowed:

```bash
# Install with safety features
pip install unblu-mcp[safety]

# Run with policy enforcement
unblu-mcp --policy config/mcp_policies.json
```

The included `config/mcp_policies.json` provides a sensible default:

| Operation Type | Policy | Examples |
|----------------|--------|----------|
| Discovery tools | ✅ Allowed | `list_services`, `list_operations`, `search_operations`, `get_operation_schema` |
| Read-only API calls | ✅ Allowed | ~190 operations like `*Get*`, `*Search*`, `*List*`, `*Read*`, `*Find*`, `*Check*` |
| Destructive API calls | ❌ Blocked | ~140 operations like `*Create*`, `*Update*`, `*Delete*`, `*Send*`, `*Login*`, etc. |

#### Custom Policies

To allow additional operations beyond read-only, create a custom policy file. For example, to allow creating and updating conversations:

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
         "value": "^conversations(Get|Search|Read|Create|Update|Set)"}
      ],
      "actions": ["execute"]
    }
  ]
}
```

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

**Prerequisites:**
- `kubectl` installed and in PATH
- Authenticated to your K8s cluster (`kubectl auth login` or valid kubeconfig)
- Permissions to access services in the target namespace

The provider will check authentication before starting port-forward and provide helpful error messages if something is misconfigured.

```python
from unblu_mcp import create_server, K8sConnectionProvider

# Connect to a K8s environment (starts kubectl port-forward automatically)
provider = K8sConnectionProvider(environment="dev")
server = create_server(provider=provider)
```

K8s environments are configured in `~/.unblu-mcp/k8s_environments.yaml`:

```yaml
environments:
  t1:
    local_port: 8084
    namespace: unblu-dev
    service: haproxy
    service_port: 8080
    api_path: /app/rest/v4
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

## Troubleshooting

### GUI Apps Don't Inherit Shell Environment (macOS)

**Problem:** MCP servers fail to start in Windsurf, Claude Desktop, or other GUI apps with errors like:
- `kubectl not found in PATH`
- `invalid peer certificate: UnknownIssuer` (TLS/proxy issues)
- Package installation failures from corporate PyPI mirrors

**Cause:** macOS GUI applications launch from `launchd` with a minimal environment, not from your shell. They don't inherit PATH or other environment variables from `~/.zshrc` or `~/.bashrc`.

**Solution:** Add the `env` block to your MCP configuration:

```json
{
  "mcpServers": {
    "unblu": {
      "command": "uvx",
      "args": ["unblu-mcp", "--provider", "k8s", "--environment", "dev"],
      "env": {
        "PATH": "/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin"
      }
    }
  }
}
```

Add any directories containing tools your setup needs (e.g., kubectl, docker) to the PATH.

### Corporate Proxy/PyPI Mirror Issues

**Problem:** When using `uvx`, you get TLS certificate errors or timeouts connecting to corporate PyPI mirrors.

**Solution:** Use `--no-config` to bypass `uv.toml` settings and `--native-tls` to use system certificates:

```json
{
  "mcpServers": {
    "unblu": {
      "command": "uvx",
      "args": [
        "--no-config",
        "--native-tls",
        "unblu-mcp",
        "--provider", "k8s",
        "--environment", "dev"
      ],
      "env": {
        "PATH": "/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin"
      }
    }
  }
}
```

### Finding MCP Server Logs

Different clients store logs in different locations:

| Client | Log Location |
|--------|--------------|
| **Windsurf** | Check Output panel → select "MCP" or "Windsurf" |
| **Claude Desktop** | `~/Library/Logs/Claude/` (macOS) |
| **Warp** | `~/Library/Group Containers/2BBY89MBSN.dev.warp/Library/Application Support/dev.warp.Warp-Stable/mcp/*.log` |

### Testing the Server Locally

To debug without an MCP client, use the included test script:

```bash
# Test with K8s provider
uv run scripts/test_client.py --provider k8s --environment dev

# Test with default provider (requires UNBLU_BASE_URL)
UNBLU_BASE_URL=https://your-instance.unblu.cloud/app/rest/v4 \
UNBLU_API_KEY=your-key \
uv run scripts/test_client.py
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
