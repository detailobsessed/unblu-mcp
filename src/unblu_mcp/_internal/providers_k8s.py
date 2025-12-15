from __future__ import annotations

import asyncio
import shutil
import socket
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any

from unblu_mcp._internal.providers import ConnectionConfig, ConnectionProvider


@dataclass
class K8sEnvironmentConfig:
    """Configuration for a Kubernetes environment."""

    name: str
    """Environment name (e.g., dev, staging, prod)."""

    local_port: int
    """Local port for port-forwarding."""

    namespace: str
    """Kubernetes namespace."""

    service: str = "haproxy"
    """Kubernetes service name."""

    service_port: int = 8080
    """Service port to forward."""

    api_path: str = "/app/rest/v4"
    """API path prefix."""


# Config file paths (relative to project root)
_CONFIG_DIR = Path(__file__).parent.parent.parent.parent / "config"
_USER_CONFIG = _CONFIG_DIR / "k8s_environments.yaml"
_EXAMPLE_CONFIG = _CONFIG_DIR / "k8s_environments.example.yaml"


def _load_environments_from_yaml(path: Path) -> dict[str, K8sEnvironmentConfig]:
    """Load environment configurations from a YAML file."""
    try:
        import yaml  # noqa: PLC0415
    except ImportError as e:
        msg = "PyYAML is required for K8s environments. Install with: pip install pyyaml"
        raise ImportError(msg) from e

    if not path.exists():
        return {}

    with path.open(encoding="utf-8") as f:
        data: dict[str, Any] = yaml.safe_load(f) or {}

    environments: dict[str, K8sEnvironmentConfig] = {}
    for name, config in data.get("environments", {}).items():
        environments[name] = K8sEnvironmentConfig(
            name=name,
            local_port=config["local_port"],
            namespace=config["namespace"],
            service=config.get("service", "haproxy"),
            service_port=config.get("service_port", 8080),
            api_path=config.get("api_path", "/app/rest/v4"),
        )
    return environments


def _get_default_environments() -> dict[str, K8sEnvironmentConfig]:
    """Get environment configurations from user config or example file."""
    # Try user config first (gitignored, may contain sensitive data)
    if _USER_CONFIG.exists():
        return _load_environments_from_yaml(_USER_CONFIG)
    # Fall back to example config
    return _load_environments_from_yaml(_EXAMPLE_CONFIG)


class K8sConnectionProvider(ConnectionProvider):
    """Connection provider for Kubernetes deployments using port-forwarding.

    This provider:
    - Automatically starts kubectl port-forward on setup
    - Cleans up the port-forward process on teardown
    - Configures trusted headers authentication
    - Supports multiple environments with different ports

    Args:
        environment: Environment name (dev, staging, prod) or custom K8sEnvironmentConfig.
        trusted_user_id: User ID for trusted headers auth (default: superadmin).
        trusted_user_role: User role for trusted headers auth (default: SUPER_ADMIN).
        environments: Custom environment configurations (overrides defaults).

    Example:
        provider = K8sConnectionProvider(environment="dev")
        await provider.setup()  # Starts port-forward
        config = provider.get_config()  # Returns connection config
        await provider.teardown()  # Stops port-forward
    """

    def __init__(
        self,
        environment: str | K8sEnvironmentConfig = "dev",
        trusted_user_id: str = "superadmin",
        trusted_user_role: str = "SUPER_ADMIN",
        environments: dict[str, K8sEnvironmentConfig] | None = None,
    ) -> None:
        self._environments = environments or _get_default_environments()

        if isinstance(environment, str):
            if environment not in self._environments:
                valid = ", ".join(self._environments.keys())
                msg = f"Unknown environment '{environment}'. Valid: {valid}"
                raise ValueError(msg)
            self._env_config = self._environments[environment]
        else:
            self._env_config = environment

        self._trusted_user_id = trusted_user_id
        self._trusted_user_role = trusted_user_role
        self._port_forward_process: subprocess.Popen[bytes] | None = None

    @property
    def environment(self) -> str:
        """Return the current environment name."""
        return self._env_config.name

    @property
    def local_port(self) -> int:
        """Return the local port for this environment."""
        return self._env_config.local_port

    async def setup(self) -> None:
        """Start kubectl port-forward if not already running."""
        if self._is_port_in_use():
            # Port-forward already running (maybe from another process)
            return

        if not shutil.which("kubectl"):
            msg = "kubectl not found in PATH"
            raise RuntimeError(msg)

        cmd = [
            "kubectl",
            "port-forward",
            "-n",
            self._env_config.namespace,
            f"svc/{self._env_config.service}",
            f"{self._env_config.local_port}:{self._env_config.service_port}",
        ]

        self._port_forward_process = subprocess.Popen(  # noqa: S603
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        # Wait for port to become available
        for _ in range(20):  # 10 seconds max
            await asyncio.sleep(0.5)
            if self._is_port_in_use():
                return

        # Failed to start
        self._port_forward_process.kill()
        self._port_forward_process = None
        msg = f"Failed to start port-forward to {self._env_config.namespace}"
        raise RuntimeError(msg)

    async def teardown(self) -> None:
        """Stop the port-forward process if we started it."""
        if self._port_forward_process is not None:
            self._port_forward_process.terminate()
            try:
                self._port_forward_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._port_forward_process.kill()
            self._port_forward_process = None

    def get_config(self) -> ConnectionConfig:
        """Return connection config with trusted headers."""
        return ConnectionConfig(
            base_url=f"http://localhost:{self._env_config.local_port}{self._env_config.api_path}",
            headers={
                "x-unblu-trusted-user-id": self._trusted_user_id,
                "x-unblu-trusted-user-role": self._trusted_user_role,
            },
        )

    async def health_check(self) -> bool:
        """Check if the port-forward is healthy."""
        return self._is_port_in_use()

    def _is_port_in_use(self) -> bool:
        """Check if the local port is in use."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex(("localhost", self._env_config.local_port)) == 0


def detect_environment_from_context() -> str | None:
    """Detect the environment from the current kubectl context.

    Matches environment names from the loaded configuration against
    patterns in the current kubectl context name.

    Returns:
        Environment name or None if not detected.
    """
    try:
        result = subprocess.run(
            ["kubectl", "config", "current-context"],  # noqa: S607
            capture_output=True,
            text=True,
            check=True,
        )
        context = result.stdout.strip()

        # Match against configured environment names
        environments = _get_default_environments()
        for env in environments:
            if f"-{env}-" in context or context.endswith(f"-{env}"):
                return env
        return None  # noqa: TRY300
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
