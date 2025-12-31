import asyncio
import shutil
import socket
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from fastmcp.utilities.logging import get_logger

from unblu_mcp._internal.exceptions import ConfigurationError
from unblu_mcp._internal.providers import ConnectionConfig, ConnectionProvider

_logger = get_logger(__name__)

if TYPE_CHECKING:
    from typing import Any


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
        self._owns_port_forward = False  # Whether we started the port-forward

    @property
    def environment(self) -> str:
        """Return the current environment name."""
        return self._env_config.name

    @property
    def local_port(self) -> int:
        """Return the local port for this environment."""
        return self._env_config.local_port

    async def setup(self) -> None:
        """Start kubectl port-forward if not already running.

        Uses a simple port-check approach: if the port is already in use,
        assume another instance is handling it. Otherwise, start our own.
        """
        if self._is_port_in_use():
            # Port already in use - another instance or external process has it
            _logger.debug(
                "Port %d already in use, reusing existing connection",
                self._env_config.local_port,
            )
            self._owns_port_forward = False
        else:
            # Port not in use - we need to start port-forward
            _logger.debug("Port %d not in use, starting port-forward", self._env_config.local_port)
            self._owns_port_forward = True
            await self._start_port_forward()

    async def _start_port_forward(self) -> None:
        """Start the kubectl port-forward process."""
        if not shutil.which("kubectl"):
            msg = "kubectl not found in PATH. Install kubectl to use the K8s provider."
            raise ConfigurationError(msg)

        # Check if kubectl is authenticated (with timeout to avoid hanging)
        try:
            auth_check = subprocess.run(  # noqa: S603
                ["kubectl", "auth", "can-i", "get", "pods", "-n", self._env_config.namespace],  # noqa: S607
                capture_output=True,
                text=True,
                check=False,
                timeout=5,  # 5 second timeout to avoid hanging on OIDC prompts
            )
        except subprocess.TimeoutExpired:
            msg = (
                f"kubectl auth check timed out for namespace '{self._env_config.namespace}'. "
                f"This usually means kubectl is waiting for authentication (e.g., OIDC login). "
                f"Please authenticate using your cluster's auth method (e.g., cloud CLI, kubelogin, or kubeconfig)"
            )
            raise ConfigurationError(msg) from None
        if auth_check.returncode != 0:
            stderr = auth_check.stderr.strip()
            msg = (
                f"kubectl is not authenticated or lacks permissions for namespace '{self._env_config.namespace}'. "
                f"Please authenticate using your cluster's auth method (e.g., cloud CLI, kubelogin). "
                f"Error: {stderr or 'unknown'}"
            )
            raise ConfigurationError(msg)

        cmd = [
            "kubectl",
            "port-forward",
            "-n",
            self._env_config.namespace,
            f"svc/{self._env_config.service}",
            f"{self._env_config.local_port}:{self._env_config.service_port}",
        ]

        _logger.debug("Starting port-forward: %s", " ".join(cmd))

        self._port_forward_process = subprocess.Popen(  # noqa: S603
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # Wait for port to become available
        await self._wait_for_port()

    async def _wait_for_port(self, timeout: float = 10.0) -> None:
        """Wait for the port to become available after starting port-forward."""
        iterations = int(timeout / 0.5)
        for _ in range(iterations):
            await asyncio.sleep(0.5)
            if self._is_port_in_use():
                _logger.debug("Port %d is now available", self._env_config.local_port)
                return

            # Check if process died early
            if self._port_forward_process is not None:
                retcode = self._port_forward_process.poll()
                if retcode is not None:
                    # Process exited - get the error
                    _, stderr = self._port_forward_process.communicate()
                    stderr_text = stderr.decode().strip() if stderr else "unknown error"
                    self._port_forward_process = None
                    msg = (
                        f"kubectl port-forward failed for {self._env_config.name}: {stderr_text}. "
                        f"Ensure you are authenticated to the K8s cluster and have access to namespace '{self._env_config.namespace}'."
                    )
                    raise ConfigurationError(msg)

        # Timeout - clean up the process we started
        if self._port_forward_process is not None:
            self._port_forward_process.kill()
            _, stderr = self._port_forward_process.communicate()
            stderr_text = stderr.decode().strip() if stderr else ""
            self._port_forward_process = None
            msg = (
                f"Port-forward timed out for {self._env_config.name} - port did not become available. "
                f"kubectl stderr: {stderr_text or 'none'}. "
                f"Ensure kubectl is authenticated and the service '{self._env_config.service}' exists in namespace '{self._env_config.namespace}'."
            )
            raise ConfigurationError(msg)

    async def teardown(self) -> None:
        """Stop the port-forward process only if we started it."""
        if self._owns_port_forward and self._port_forward_process is not None:
            _logger.debug("Stopping port-forward for %s", self._env_config.name)
            self._port_forward_process.terminate()
            try:
                self._port_forward_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._port_forward_process.kill()
            self._port_forward_process = None
        elif not self._owns_port_forward:
            _logger.debug("Not owner, skipping port-forward cleanup for %s", self._env_config.name)

    async def ensure_connection(self) -> None:
        """Ensure the port-forward is running, restarting if needed.

        Call this before making API requests to handle cases where:
        - Our port-forward process died
        - An external port-forward we were using is no longer available
        """
        if self._is_port_in_use():
            return  # Port is available, nothing to do

        # Port is not available - need to (re)start port-forward
        if self._owns_port_forward and self._port_forward_process is not None:
            # Clean up existing process (dead or malfunctioning)
            retcode = self._port_forward_process.poll()
            if retcode is not None:
                _logger.warning(
                    "Port-forward process died (exit code %d), restarting...",
                    retcode,
                )
            else:
                _logger.warning("Port-forward process alive but port not available, killing and restarting...")
                self._port_forward_process.kill()
                try:
                    self._port_forward_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    _logger.warning("Process did not terminate after kill, continuing anyway")
            self._port_forward_process = None

        # Start a new port-forward
        _logger.info("Restarting port-forward for %s", self._env_config.name)
        self._owns_port_forward = True
        await self._start_port_forward()

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
            timeout=5,  # 5 second timeout to avoid hanging
        )
        context = result.stdout.strip()

        # Match against configured environment names
        environments = _get_default_environments()
        for env in environments:
            if f"-{env}-" in context or context.endswith(f"-{env}"):
                return env
        return None  # noqa: TRY300
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return None
