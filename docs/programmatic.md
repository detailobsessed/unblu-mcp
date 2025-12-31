---
title: Programmatic Usage
---

# Programmatic Usage

The server can be used programmatically in your Python applications.

## Connection Providers

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

## Custom Connection Providers

Implement the `ConnectionProvider` interface for custom connectivity:

```python
from unblu_mcp import ConnectionProvider, ConnectionConfig

class MyProvider(ConnectionProvider):
    async def setup(self) -> None:
        """Initialize connection (e.g., start tunnel)."""
        pass

    async def teardown(self) -> None:
        """Clean up resources."""
        pass

    async def ensure_connection(self) -> None:
        """Ensure connection is alive, restart if needed.

        Called before each API request. Override this if your
        provider needs to handle connection recovery.
        """
        pass

    def get_config(self) -> ConnectionConfig:
        """Return current connection configuration."""
        return ConnectionConfig(
            base_url="https://api.example.com",
            headers={"X-Custom-Header": "value"},
        )

    async def health_check(self) -> bool:
        """Check if connection is healthy."""
        return True
```

## ConnectionConfig

The `ConnectionConfig` dataclass defines connection parameters:

```python
from unblu_mcp import ConnectionConfig

config = ConnectionConfig(
    base_url="https://api.example.com/v4",
    headers={"X-Custom-Header": "value"},
    auth=("username", "password"),  # Optional basic auth tuple
    timeout=30.0,  # Request timeout in seconds
)
```

## Running the Server

```python
from unblu_mcp import create_server

server = create_server()

# Run with stdio transport (for MCP clients)
server.run()

# Or run with SSE transport for web clients
server.run(transport="sse", host="127.0.0.1", port=8000)
```

## Custom OpenAPI Spec

You can provide a custom OpenAPI specification:

```python
from unblu_mcp import create_server

server = create_server(spec_path="/path/to/custom-swagger.json")
```

## With Policy Enforcement

```python
from unblu_mcp import create_server

server = create_server(policy_file="/path/to/mcp_policies.json")
```
