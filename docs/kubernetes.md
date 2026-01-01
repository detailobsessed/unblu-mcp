---
title: Kubernetes Provider
---

# Kubernetes Provider

The K8s provider automatically manages `kubectl port-forward` connections to your Unblu deployment. This is the recommended configuration for internal/development deployments.

## Prerequisites

- `kubectl` installed and in PATH
- Authenticated to your K8s cluster (`kubectl auth login` or valid kubeconfig)
- Permissions to access services in the target namespace

The provider will check authentication before starting port-forward and provide helpful error messages if something is misconfigured.

## Configuration

K8s environments are configured in `~/.unblu-mcp/k8s_environments.yaml`:

```yaml
environments:
  dev:
    local_port: 8084
    namespace: unblu-dev
    service: haproxy
    service_port: 8080
    api_path: /app/rest/v4

  staging:
    local_port: 8085
    namespace: unblu-staging
    service: haproxy
    service_port: 8080
    api_path: /app/rest/v4

  prod:
    local_port: 8086
    namespace: unblu-prod
    service: haproxy
    service_port: 8080
    api_path: /app/rest/v4
```

### Configuration Options

| Field | Required | Description |
|-------|----------|-------------|
| `local_port` | Yes | Local port for the port-forward |
| `namespace` | Yes | Kubernetes namespace |
| `service` | Yes | Service name to forward to |
| `service_port` | No | Service port (default: 8080) |
| `api_path` | No | API path prefix (default: `/app/rest/v4`) |

## Usage

### Command Line

```bash
# Use the dev environment
unblu-mcp --provider k8s --environment dev

# Use a custom config file
unblu-mcp --provider k8s --environment my-env --k8s-config /path/to/config.yaml
```

### Programmatic

```python
from unblu_mcp import create_server, K8sConnectionProvider

# Connect to a K8s environment (starts kubectl port-forward automatically)
provider = K8sConnectionProvider(environment="dev")
server = create_server(provider=provider)
```

With custom environments:

```python
from unblu_mcp import K8sConnectionProvider, K8sEnvironmentConfig

environments = {
    "custom": K8sEnvironmentConfig(
        name="custom",
        local_port=9000,
        namespace="my-namespace",
        service="my-service",
    )
}

provider = K8sConnectionProvider(
    environment="custom",
    environments=environments,
)
```

## How It Works

1. **On startup**: The provider checks if the configured local port is already in use
2. **If port is free**: Starts a new `kubectl port-forward` process
3. **If port is in use**: Reuses the existing connection (from another MCP instance or manual port-forward)
4. **Before each API call**: Checks if the connection is still alive, restarts if needed
5. **On shutdown**: Terminates the port-forward process (only if this instance started it)

### Auto-Restart

If the port-forward dies while the server is running, it will automatically restart on the next API call. This handles:

- Network interruptions
- Kubernetes pod restarts
- kubectl process crashes

### Multiple Instances

Multiple MCP server instances can safely share the same port-forward:

- First instance starts the port-forward
- Subsequent instances detect the port is in use and reuse it
- When the owning instance shuts down, others continue working until they need to restart

## Troubleshooting

### kubectl not found

```text
ConfigurationError: kubectl not found in PATH
```

**Solution**: Ensure kubectl is installed and add its directory to the PATH in your MCP client config:

```json
{
  "env": {
    "PATH": "/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin"
  }
}
```

### Authentication failure

```text
ConfigurationError: kubectl is not authenticated or lacks permissions
```

**Solution**: Authenticate to your cluster:

```bash
kubectl auth login  # or your cluster's auth method
kubectl get pods -n your-namespace  # verify access
```

### Port-forward timeout

```text
ConfigurationError: Port-forward timed out for dev - port did not become available
```

**Possible causes**:

1. Service doesn't exist in the namespace
2. Network connectivity issues
3. Firewall blocking the connection

**Debug steps**:

```bash
# Verify the service exists
kubectl get svc -n unblu-dev

# Try manual port-forward
kubectl port-forward -n unblu-dev svc/haproxy 8084:8080

# Check for errors in kubectl output
```
