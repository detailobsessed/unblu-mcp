---
title: Getting Started
---

# Getting Started

This guide covers installation and basic configuration of unblu-mcp.

## Installation

This package is available on [PyPI](https://pypi.org/project/unblu-mcp/). Run directly with `uvx` (no installation needed):

```bash
uvx unblu-mcp
```

Or install persistently so the `unblu-mcp` command is always available:

```bash
uv tool install unblu-mcp
```

### From source

```bash
git clone https://github.com/detailobsessed/unblu-mcp.git
cd unblu-mcp
uv sync
```

## MCP Client Configuration

Add the server to your MCP client configuration (Claude Desktop, Windsurf, etc.):

### With Kubernetes Provider

The K8s provider automatically manages `kubectl port-forward` connections to your Unblu deployment. This is the most tested configuration.

Before using the K8s provider, make sure you have all of the following:

- `kubectl` installed and available to the MCP client process
- a valid Kubernetes login with access to the target namespace
- a K8s environment map in `~/.unblu-mcp/k8s_environments.yaml`, or a custom file passed with `--k8s-config`

The `--environment` value must match a key from that YAML file.

Minimal example:

```yaml
environments:
  dev:
    local_port: 8084
    namespace: unblu-dev
    service: haproxy
    service_port: 8080
    api_path: /app/rest/v4
```

=== "uvx (no install)"

    ```json
    {
      "mcpServers": {
        "unblu": {
          "command": "uvx",
          "args": ["unblu-mcp", "--provider", "k8s", "--environment", "dev"],
          "env": {
            "PATH": "/Users/YOUR_USERNAME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
          }
        }
      }
    }
    ```

    The `env` block is optional if your MCP client already inherits a `PATH` that includes both `uvx` and `kubectl`.

=== "uv tool install"

    After running `uv tool install unblu-mcp`:

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

    The `env` block is optional if your MCP client already inherits a `PATH` that includes both `unblu-mcp` and `kubectl`.

See [Kubernetes Provider](kubernetes.md) for setting up your environments.

### With Environment Variables

For direct API access without Kubernetes:

=== "uvx (no install)"

    ```json
    {
      "mcpServers": {
        "unblu": {
          "command": "uvx",
          "args": ["unblu-mcp"],
          "env": {
            "PATH": "/Users/YOUR_USERNAME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin",
            "UNBLU_BASE_URL": "https://your-instance.unblu.cloud/app/rest/v4",
            "UNBLU_API_KEY": "your-api-key"
          }
        }
      }
    }
    ```

=== "uv tool install"

    After running `uv tool install unblu-mcp`:

    ```json
    {
      "mcpServers": {
        "unblu": {
          "command": "unblu-mcp",
          "args": [],
          "env": {
            "PATH": "/Users/YOUR_USERNAME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin",
            "UNBLU_BASE_URL": "https://your-instance.unblu.cloud/app/rest/v4",
            "UNBLU_API_KEY": "your-api-key"
          }
        }
      }
    }
    ```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `UNBLU_BASE_URL` | No | Your Unblu API base URL (default: `https://unblu.cloud/app/rest/v4`) |
| `UNBLU_API_KEY` | One of these | API key for authentication (Bearer token) |
| `UNBLU_USERNAME` | One of these | Username for basic authentication |
| `UNBLU_PASSWORD` | With username | Password for basic authentication |

## Command Line Usage

```bash
# Run with stdio transport (default, for MCP clients)
unblu-mcp

# Use a custom swagger.json location
unblu-mcp --spec /path/to/swagger.json

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
| `--provider` | `default`, `k8s` | `default` | Connection provider |
| `--environment` | string | `dev` | K8s environment (with `--provider k8s`) |
| `--k8s-config` | path | none | Custom K8s environments YAML file |
