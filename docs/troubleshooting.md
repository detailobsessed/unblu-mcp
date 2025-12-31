---
title: Troubleshooting
---

# Troubleshooting

## GUI Apps Don't Inherit Shell Environment (macOS)

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
      "command": "unblu-mcp",
      "args": ["--provider", "k8s", "--environment", "dev"],
      "env": {
        "PATH": "/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin"
      }
    }
  }
}
```

Add any directories containing tools your setup needs (e.g., kubectl, docker) to the PATH.

## `uvx` Blocks uv Cache Cleaning

**Problem:** If you're using `uvx unblu-mcp` instead of the recommended `uv tool install`, tools like `topgrade` or `uv cache prune` will hang with:

```text
Cache is currently in-use, waiting for other uv processes to finish
```

**Cause:** This is a [known uv limitation](https://github.com/astral-sh/uv/issues/11694) affecting all long-running `uvx` processes.

**Solution:** Follow the recommended [installation method](getting-started.md#installation) using `uv tool install unblu-mcp`.

## Corporate Proxy/PyPI Mirror Issues

**Problem:** When installing with `uv tool install`, you get TLS certificate errors or timeouts connecting to corporate PyPI mirrors.

**Solution:** Use `--no-config` to bypass `uv.toml` settings and `--native-tls` to use system certificates:

```bash
uv tool install --no-config --native-tls unblu-mcp
```

## Finding MCP Server Logs

Different clients store logs in different locations:

| Client | Log Location |
|--------|--------------|
| **Windsurf** | Check Output panel → select "MCP" or "Windsurf" |
| **Claude Desktop** | `~/Library/Logs/Claude/` (macOS) |
| **Warp** | `~/Library/Group Containers/2BBY89MBSN.dev.warp/Library/Application Support/dev.warp.Warp-Stable/mcp/*.log` |

The unblu-mcp server also writes its own logs to `~/.unblu-mcp/logs/`. See [Logging & Observability](logging.md) for details.

## Testing the Server Locally

To debug without an MCP client, use the included test script:

```bash
# Test with K8s provider
uv run scripts/test_client.py --provider k8s --environment dev

# Test with default provider (requires UNBLU_BASE_URL)
UNBLU_BASE_URL=https://your-instance.unblu.cloud/app/rest/v4 \
UNBLU_API_KEY=your-key \
uv run scripts/test_client.py
```

## Common Error Messages

### ConfigurationError: kubectl not found in PATH

kubectl is not installed or not in the PATH visible to the MCP client.

**Solution:** Install kubectl and add its directory to the `env.PATH` in your MCP config.

### ConfigurationError: kubectl is not authenticated

Your kubectl context is not authenticated to the cluster.

**Solution:** Run `kubectl auth login` or configure your kubeconfig.

### ConfigurationError: Port-forward timed out

The port-forward process started but the port never became available.

**Possible causes:**

1. The service doesn't exist in the namespace
2. Network connectivity issues
3. The service is not responding

**Debug:**

```bash
# Check if service exists
kubectl get svc -n your-namespace

# Try manual port-forward to see errors
kubectl port-forward -n your-namespace svc/your-service 8084:8080
```

### ToolError: Operation 'xyz' not found

The operation ID doesn't exist in the OpenAPI spec.

**Solution:** Use `search_operations("keyword")` to find valid operation IDs.
