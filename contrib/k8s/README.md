# Kubernetes Port-Forward Wrapper

This wrapper script enables `unblu-mcp` to work with Unblu deployments that are only accessible via Kubernetes port-forwarding.

## Use Case

Enterprise deployments often run Unblu behind Kubernetes services that aren't directly accessible from developer machines. This wrapper:

1. Automatically detects the target environment from your kubectl context
2. Starts a port-forward to the Unblu haproxy service
3. Configures trusted headers authentication
4. Launches the MCP server

## Installation

```bash
# Make the script executable
chmod +x contrib/k8s/unblu-mcp-k8s

# Optionally, symlink to your PATH
ln -s $(pwd)/contrib/k8s/unblu-mcp-k8s ~/.local/bin/unblu-mcp-k8s
```

## Usage

```bash
# Auto-detect environment from kubectl context
./contrib/k8s/unblu-mcp-k8s

# Specify environment explicitly
./contrib/k8s/unblu-mcp-k8s t1
./contrib/k8s/unblu-mcp-k8s t2
./contrib/k8s/unblu-mcp-k8s p1
./contrib/k8s/unblu-mcp-k8s e1
```

## MCP Client Configuration

### Windsurf / Claude Desktop

```json
{
  "mcpServers": {
    "unblu": {
      "command": "/path/to/unblu-mcp/contrib/k8s/unblu-mcp-k8s",
      "args": ["t1"]
    }
  }
}
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `UNBLU_MCP_PATH` | Path to unblu-mcp repo if not installed globally | - |
| `UNBLU_K8S_NAMESPACE` | Override namespace pattern | `appl-kop-{env}` |
| `UNBLU_K8S_SERVICE` | Override service name | `haproxy` |
| `UNBLU_K8S_PORT` | Override service port | `8080` |

## Port Mapping

Each environment uses a different local port to allow multiple environments simultaneously:

| Environment | Local Port |
|-------------|------------|
| t1 | 8084 |
| t2 | 8085 |
| p1 | 8086 |
| e1 | 8087 |

## Prerequisites

- `kubectl` configured with appropriate contexts
- `unblu-mcp` installed (`uv tool install unblu-mcp`) or available via `UNBLU_MCP_PATH`
- Network access to the Kubernetes cluster

## Customization

To adapt this for your environment:

1. Modify the `ENV_PORTS` array for your port preferences
2. Adjust `detect_environment()` to match your kubectl context naming
3. Change the namespace pattern in `UNBLU_K8S_NAMESPACE` if needed
4. Update the service name if your Unblu deployment uses a different ingress

## Related

- [GitHub Issue #17](https://github.com/ichoosetoaccept/unblu-mcp/issues/17) - Long-term plan for connection provider plugin system
