# unblu-mcp

<!-- mcp-name: io.github.detailobsessed/unblu -->

[![ci](https://github.com/detailobsessed/unblu-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/detailobsessed/unblu-mcp/actions/workflows/ci.yml)
[![documentation](https://img.shields.io/badge/docs-mkdocs-708FCC.svg?style=flat)](https://detailobsessed.github.io/unblu-mcp/)
[![pypi version](https://img.shields.io/pypi/v/unblu-mcp.svg)](https://pypi.org/project/unblu-mcp/)
[![python versions](https://img.shields.io/pypi/pyversions/unblu-mcp.svg)](https://pypi.org/project/unblu-mcp/)
[![license](https://img.shields.io/pypi/l/unblu-mcp.svg)](https://github.com/detailobsessed/unblu-mcp/blob/main/LICENSE)
[![FastMCP](https://img.shields.io/badge/FastMCP-2.14+-00ADD8.svg)](https://github.com/jlowin/fastmcp)

A [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server for interacting with [Unblu](https://www.unblu.com/) deployments. Provides AI assistants with token-efficient access to 300+ Unblu API endpoints through progressive disclosure.

**📚 [Full Documentation](https://detailobsessed.github.io/unblu-mcp/)**

## Features

- **Progressive Disclosure** — 5 discovery tools instead of 300+ API definitions upfront
- **Full API Coverage** — Access to all Unblu REST API v4 endpoints
- **Smart Discovery** — Search and browse operations by service category or keyword
- **Safety Controls** — MCP annotations + optional [Eunomia](https://github.com/whataboutyou-ai/eunomia) policy enforcement
- **K8s Integration** — Built-in `kubectl port-forward` management with auto-restart

## Quick Start

### Installation

```bash
uv tool install unblu-mcp
```

### MCP Client Configuration

Add to your MCP client config (Claude Desktop, Windsurf, etc.):

```json
{
  "mcpServers": {
    "unblu": {
      "command": "unblu-mcp",
      "args": ["--provider", "k8s", "--environment", "dev"],
      "env": {
        "PATH": "/Users/YOUR_USERNAME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
      }
    }
  }
}
```

Or with environment variables for direct API access:

```json
{
  "mcpServers": {
    "unblu": {
      "command": "unblu-mcp",
      "env": {
        "PATH": "/Users/YOUR_USERNAME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin",
        "UNBLU_BASE_URL": "https://your-instance.unblu.cloud/app/rest/v4",
        "UNBLU_API_KEY": "your-api-key"
      }
    }
  }
}
```

## Available Tools

| Tool | Description |
|------|-------------|
| `list_services()` | List all API service categories |
| `list_operations(service)` | List operations in a specific service |
| `search_operations(query)` | Search for operations by keyword |
| `get_operation_schema(operation_id)` | Get full schema for an operation |
| `call_api(operation_id, ...)` | Execute any API operation |

## Documentation

For complete documentation including:

- Detailed configuration options
- Kubernetes provider setup
- Safety & authorization policies
- Programmatic usage
- Troubleshooting

Visit **[detailobsessed.github.io/unblu-mcp](https://detailobsessed.github.io/unblu-mcp/)**

## Development

```bash
git clone https://github.com/detailobsessed/unblu-mcp.git
cd unblu-mcp
uv sync --all-extras --dev
uv run poe test
```

## License

ISC License
