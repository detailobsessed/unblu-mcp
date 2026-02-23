# unblu-mcp

<!-- mcp-name: io.github.detailobsessed/unblu -->

[![ci](https://github.com/detailobsessed/unblu-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/detailobsessed/unblu-mcp/actions/workflows/ci.yml)
[![documentation](https://img.shields.io/badge/docs-zensical-708FCC.svg?style=flat)](https://detailobsessed.github.io/unblu-mcp/)
[![pypi version](https://img.shields.io/pypi/v/unblu-mcp.svg)](https://pypi.org/project/unblu-mcp/)
[![python versions](https://img.shields.io/pypi/pyversions/unblu-mcp.svg)](https://pypi.org/project/unblu-mcp/)
[![license](https://img.shields.io/pypi/l/unblu-mcp.svg)](https://github.com/detailobsessed/unblu-mcp/blob/main/LICENSE)
[![FastMCP](https://img.shields.io/badge/FastMCP-2.14+-00ADD8.svg)](https://github.com/jlowin/fastmcp)

A [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server for debugging and operating [Unblu](https://www.unblu.com/) deployments. Optimised for debugging workflows — curated typed tools for common operations, plus an escape hatch for the full 300+ endpoint API.

**📚 [Full Documentation](https://detailobsessed.github.io/unblu-mcp/)**

## Design

The server exposes three layers, each progressively more powerful:

| Layer | What it is | When to use |
|-------|-----------|-------------|
| **Curated tools** | Typed, token-efficient tools for common debugging tasks | 90% of debugging sessions |
| **`execute_operation`** | Generic escape hatch for any of 331 Unblu API operations | When a curated tool doesn't exist |
| **Resources** | Read-only `api://` URIs for browsing the API surface | Discovery and schema inspection |

## Quick Start

### Installation

```bash
uv tool install unblu-mcp
```

### MCP Client Configuration

Direct API access with an API key:

```json
{
  "mcpServers": {
    "unblu": {
      "command": "unblu-mcp",
      "env": {
        "UNBLU_BASE_URL": "https://your-instance.unblu.cloud/app/rest/v4",
        "UNBLU_API_KEY": "your-api-key"
      }
    }
  }
}
```

Kubernetes port-forward (auto-managed):

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

## Tools

### Curated tools (read-only)

| Tool | Description |
|------|-------------|
| `get_current_account` | Current account info — good first call to verify connectivity |
| `search_conversations(status?, topic?, assignee_id?, limit?)` | Search conversations with filters |
| `get_conversation(conversation_id)` | Full conversation detail with participants |
| `search_persons(query?, email?, limit?)` | Find persons (visitors, agents) |
| `get_person(person_id)` | Full person detail |
| `search_users(query?, email?, limit?)` | Find registered users |
| `get_user(user_id)` | Full user detail |
| `check_agent_availability(named_area_id?)` | Check agent availability per named area |
| `search_named_areas(query?, limit?)` | List named areas (routing targets) |
| `find_operation(query, service?, include_schema?, limit?)` | Discover API operations by keyword |

### Mutation tools

| Tool | Description |
|------|-------------|
| `assign_conversation(conversation_id, agent_id)` | Assign a conversation to an agent |
| `end_conversation(conversation_id)` | End an active conversation |

### Escape hatch

| Tool | Description |
|------|-------------|
| `execute_operation(operation_id, path_params?, query_params?, body?, fields?, confirm_destructive?)` | Execute any of the 331 Unblu API operations |

### Resources

| URI | Description |
|-----|-------------|
| `api://services` | JSON list of all API service groups |
| `api://operations/{operation_id}` | Full resolved schema for a specific operation |

### Prompts

| Prompt | Description |
|--------|-------------|
| `debug_conversation(conversation_id)` | Step-by-step debugging workflow for a conversation |
| `find_agent(criteria)` | Locate an agent and check their availability |
| `account_health_check` | Validate account configuration and connectivity |

## Safety

By default, `execute_operation` blocks `DELETE` operations unless `confirm_destructive=True` is passed. For stricter control, install the optional Eunomia policy engine:

```bash
uv tool install "unblu-mcp[safety]"
```

Then point to a policy file:

```json
{
  "mcpServers": {
    "unblu": {
      "command": "unblu-mcp",
      "args": ["--policy", "config/mcp_policies.json"],
      "env": { "UNBLU_BASE_URL": "...", "UNBLU_API_KEY": "..." }
    }
  }
}
```

The bundled `config/mcp_policies.json` allows all read-only and curated tools while blocking destructive `execute_operation` calls by operation ID pattern.

## Development

```bash
git clone https://github.com/detailobsessed/unblu-mcp.git
cd unblu-mcp
uv sync --all-extras --dev
uv run poe test
```

## License

ISC License
