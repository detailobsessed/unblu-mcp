from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import httpx


@dataclass
class ConnectionConfig:
    """Configuration returned by a connection provider."""

    base_url: str
    """The base URL for API requests (e.g., http://localhost:8084/kop/rest/v4)."""

    headers: dict[str, str] = field(default_factory=dict)
    """Additional headers to include in all requests (e.g., trusted headers)."""

    auth: httpx.Auth | None = None
    """Optional httpx auth handler for basic auth, etc."""

    timeout: float = 30.0
    """Request timeout in seconds."""


class ConnectionProvider(ABC):
    """Abstract base class for connection providers.

    Connection providers handle the complexity of connecting to Unblu deployments
    in various environments. They can:

    - Start/stop port-forwards or tunnels
    - Manage authentication (API keys, basic auth, trusted headers)
    - Handle environment switching
    - Refresh credentials when needed

    Example implementation for Kubernetes:

        class K8sConnectionProvider(ConnectionProvider):
            def __init__(self, environment: str = "t1"):
                self.environment = environment
                self._port_forward_process = None

            async def setup(self) -> None:
                # Start kubectl port-forward
                ...

            async def teardown(self) -> None:
                # Stop port-forward
                ...

            def get_config(self) -> ConnectionConfig:
                return ConnectionConfig(
                    base_url=f"http://localhost:{self.port}/kop/rest/v4",
                    headers={
                        "x-unblu-trusted-user-id": "superadmin",
                        "x-unblu-trusted-user-role": "SUPER_ADMIN",
                    },
                )
    """

    @abstractmethod
    async def setup(self) -> None:
        """Initialize the connection (start port-forward, refresh auth, etc.).

        Called once when the MCP server starts, before any API requests.
        Should be idempotent - safe to call multiple times.
        """

    @abstractmethod
    async def teardown(self) -> None:
        """Clean up resources (stop port-forward, close connections, etc.).

        Called when the MCP server shuts down.
        Should be safe to call even if setup() was never called.
        """

    @abstractmethod
    def get_config(self) -> ConnectionConfig:
        """Return the current connection configuration.

        This is called for each API request, allowing dynamic configuration
        (e.g., refreshing tokens, switching environments).

        Returns:
            ConnectionConfig with base_url, headers, auth, and timeout.
        """

    async def health_check(self) -> bool:
        """Check if the connection is healthy.

        Override this to implement custom health checks (e.g., ping the API).

        Returns:
            True if the connection is healthy, False otherwise.
        """
        return True


class DefaultConnectionProvider(ConnectionProvider):
    """Default provider using environment variables.

    This is the standard provider for direct connections to Unblu Cloud
    or self-hosted deployments with direct network access.

    Environment variables:
        UNBLU_BASE_URL: API base URL (default: https://unblu.cloud/app/rest/v4)
        UNBLU_API_KEY: Bearer token for API key auth
        UNBLU_USERNAME: Username for basic auth
        UNBLU_PASSWORD: Password for basic auth
        UNBLU_TRUSTED_HEADERS: Trusted headers (format: "key:value,key:value")
    """

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        username: str | None = None,
        password: str | None = None,
        trusted_headers: dict[str, str] | None = None,
    ) -> None:
        self._base_url = base_url
        self._api_key = api_key
        self._username = username
        self._password = password
        self._trusted_headers = trusted_headers

    async def setup(self) -> None:
        """No setup needed for direct connections."""

    async def teardown(self) -> None:
        """No teardown needed for direct connections."""

    def get_config(self) -> ConnectionConfig:
        """Build config from environment variables and constructor args."""
        # Load from environment if not provided
        base_url = self._base_url or os.environ.get(
            "UNBLU_BASE_URL", "https://unblu.cloud/app/rest/v4"
        )
        api_key = self._api_key or os.environ.get("UNBLU_API_KEY")
        username = self._username or os.environ.get("UNBLU_USERNAME")
        password = self._password or os.environ.get("UNBLU_PASSWORD")
        trusted_headers = self._trusted_headers
        if trusted_headers is None:
            trusted_headers = _parse_trusted_headers(
                os.environ.get("UNBLU_TRUSTED_HEADERS")
            )

        # Build headers and auth
        headers: dict[str, str] = {}
        auth: httpx.Auth | None = None

        if trusted_headers:
            headers.update(trusted_headers)
        elif api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        elif username and password:
            auth = httpx.BasicAuth(username, password)

        return ConnectionConfig(
            base_url=base_url,
            headers=headers,
            auth=auth,
        )


def _parse_trusted_headers(headers_str: str | None) -> dict[str, str]:
    """Parse trusted headers from comma-separated key:value pairs."""
    if not headers_str:
        return {}
    headers = {}
    for pair in headers_str.split(","):
        if ":" in pair:
            key, value = pair.split(":", 1)
            headers[key.strip()] = value.strip()
    return headers
