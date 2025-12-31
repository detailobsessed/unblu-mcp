"""Tests for the Kubernetes connection provider."""

import socket
import subprocess
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_subprocess import FakeProcess

from unblu_mcp._internal.exceptions import ConfigurationError
from unblu_mcp._internal.providers_k8s import (
    K8sConnectionProvider,
    K8sEnvironmentConfig,
    _get_default_environments,
    detect_environment_from_context,
)

# Test environments for use in tests
TEST_ENVIRONMENTS = {
    "dev": K8sEnvironmentConfig(name="dev", local_port=8084, namespace="unblu-dev"),
    "test1": K8sEnvironmentConfig(name="test1", local_port=8085, namespace="unblu-test1"),
    "test2": K8sEnvironmentConfig(name="test2", local_port=8087, namespace="unblu-test2"),
    "prod": K8sEnvironmentConfig(name="prod", local_port=8086, namespace="unblu-prod"),
}


class TestK8sEnvironmentConfig:
    """Tests for K8sEnvironmentConfig dataclass."""

    def test_default_values(self) -> None:
        """Config has sensible defaults."""
        config = K8sEnvironmentConfig(name="test", local_port=8080, namespace="test-ns")
        assert config.service == "haproxy"
        assert config.service_port == 8080
        assert config.api_path == "/app/rest/v4"

    def test_custom_values(self) -> None:
        """Config accepts custom values."""
        config = K8sEnvironmentConfig(
            name="custom",
            local_port=9000,
            namespace="custom-ns",
            service="nginx",
            service_port=443,
            api_path="/api/v1",
        )
        assert config.name == "custom"
        assert config.local_port == 9000
        assert config.namespace == "custom-ns"
        assert config.service == "nginx"
        assert config.service_port == 443
        assert config.api_path == "/api/v1"


class TestGetDefaultEnvironments:
    """Tests for environment loading from config files."""

    def test_loads_environments_from_example_config(self) -> None:
        """Loads environments from example config when user config doesn't exist."""
        environments = _get_default_environments()
        # Should load from k8s_environments.example.yaml
        assert len(environments) > 0

    def test_environments_have_unique_ports(self) -> None:
        """Each environment has a unique local port."""
        environments = _get_default_environments()
        if environments:  # Only test if environments are loaded
            ports = [env.local_port for env in environments.values()]
            assert len(ports) == len(set(ports))

    def test_environment_configs_are_valid(self) -> None:
        """All loaded environments have required fields."""
        environments = _get_default_environments()
        for name, config in environments.items():
            assert config.name == name
            assert config.local_port > 0
            assert config.namespace


class TestK8sConnectionProvider:
    """Tests for K8sConnectionProvider."""

    def test_init_with_string_environment(self) -> None:
        """Provider initializes with string environment name."""
        provider = K8sConnectionProvider(environment="dev", environments=TEST_ENVIRONMENTS)
        assert provider.environment == "dev"
        assert provider.local_port == 8084

    def test_init_with_config_object(self) -> None:
        """Provider initializes with K8sEnvironmentConfig object."""
        config = K8sEnvironmentConfig(name="custom", local_port=9999, namespace="custom-ns")
        provider = K8sConnectionProvider(environment=config)
        assert provider.environment == "custom"
        assert provider.local_port == 9999

    def test_init_unknown_environment_raises(self) -> None:
        """Provider raises ValueError for unknown environment."""
        with pytest.raises(ValueError, match="Unknown environment 'invalid'"):
            K8sConnectionProvider(environment="invalid", environments=TEST_ENVIRONMENTS)

    def test_init_custom_environments(self) -> None:
        """Provider accepts custom environment configurations."""
        custom_envs = {
            "dev": K8sEnvironmentConfig(name="dev", local_port=8000, namespace="dev-ns"),
        }
        provider = K8sConnectionProvider(environment="dev", environments=custom_envs)
        assert provider.environment == "dev"
        assert provider.local_port == 8000

    def test_get_config_returns_connection_config(self) -> None:
        """get_config returns properly configured ConnectionConfig."""
        provider = K8sConnectionProvider(
            environment="dev",
            trusted_user_id="testuser",
            trusted_user_role="ADMIN",
            environments=TEST_ENVIRONMENTS,
        )
        config = provider.get_config()

        assert config.base_url == "http://localhost:8084/app/rest/v4"
        assert config.headers["x-unblu-trusted-user-id"] == "testuser"
        assert config.headers["x-unblu-trusted-user-role"] == "ADMIN"

    def test_get_config_default_trusted_headers(self) -> None:
        """get_config uses default trusted headers."""
        provider = K8sConnectionProvider(environment="dev", environments=TEST_ENVIRONMENTS)
        config = provider.get_config()

        assert config.headers["x-unblu-trusted-user-id"] == "superadmin"
        assert config.headers["x-unblu-trusted-user-role"] == "SUPER_ADMIN"

    @pytest.mark.asyncio
    async def test_setup_port_already_in_use(self) -> None:
        """setup() reuses existing port if port is already in use."""
        provider = K8sConnectionProvider(environment="dev", environments=TEST_ENVIRONMENTS)

        with patch.object(provider, "_is_port_in_use", return_value=True):
            await provider.setup()
            # Should not start a new process and should not own the port-forward
            assert provider._port_forward_process is None
            assert provider._owns_port_forward is False

    @pytest.mark.asyncio
    async def test_setup_kubectl_not_found(self) -> None:
        """setup() raises ConfigurationError if kubectl not found."""
        provider = K8sConnectionProvider(environment="dev", environments=TEST_ENVIRONMENTS)

        with (
            patch.object(provider, "_is_port_in_use", return_value=False),
            patch("shutil.which", return_value=None),
            pytest.raises(ConfigurationError, match="kubectl not found"),
        ):
            await provider.setup()

    @pytest.mark.asyncio
    async def test_setup_kubectl_auth_failure(self, fp: FakeProcess) -> None:
        """setup() raises ConfigurationError if kubectl is not authenticated."""
        provider = K8sConnectionProvider(environment="dev", environments=TEST_ENVIRONMENTS)

        # Register auth check failure
        fp.register(
            ["kubectl", "auth", "can-i", "get", "pods", "-n", "unblu-dev"],
            returncode=1,
            stderr="error: You must be logged in to the server",
        )

        with (
            patch.object(provider, "_is_port_in_use", return_value=False),
            patch("shutil.which", return_value="/usr/bin/kubectl"),
            pytest.raises(ConfigurationError, match="kubectl is not authenticated"),
        ):
            await provider.setup()

    @pytest.mark.asyncio
    async def test_setup_port_forward_fails_early(self, fp: FakeProcess) -> None:
        """setup() raises ConfigurationError with stderr if port-forward process dies early."""
        provider = K8sConnectionProvider(environment="dev", environments=TEST_ENVIRONMENTS)

        # Register successful auth check
        fp.register(
            ["kubectl", "auth", "can-i", "get", "pods", "-n", "unblu-dev"],
            returncode=0,
        )
        # Register failing port-forward
        fp.register(
            ["kubectl", "port-forward", "-n", "unblu-dev", "svc/haproxy", "8084:8080"],
            returncode=1,
            stderr="error: services 'haproxy' not found",
        )

        with (
            patch.object(provider, "_is_port_in_use", return_value=False),
            patch("shutil.which", return_value="/usr/bin/kubectl"),
            patch("asyncio.sleep", new_callable=AsyncMock),
            pytest.raises(ConfigurationError, match="kubectl port-forward failed"),
        ):
            await provider.setup()

    @pytest.mark.asyncio
    async def test_setup_starts_port_forward(self, fp: FakeProcess) -> None:
        """setup() starts kubectl port-forward process when port is not in use."""
        provider = K8sConnectionProvider(environment="dev", environments=TEST_ENVIRONMENTS)

        # First call returns False (port not in use), subsequent calls return True (port ready)
        port_check_results = [False, True]

        # Register successful auth check
        fp.register(
            ["kubectl", "auth", "can-i", "get", "pods", "-n", "unblu-dev"],
            returncode=0,
        )
        # Register port-forward (keeps running)
        fp.register(
            ["kubectl", "port-forward", "-n", "unblu-dev", "svc/haproxy", "8084:8080"],
            returncode=0,
        )

        with (
            patch.object(provider, "_is_port_in_use", side_effect=port_check_results),
            patch("shutil.which", return_value="/usr/bin/kubectl"),
        ):
            await provider.setup()

            assert provider._owns_port_forward is True
            # Verify the port-forward command was called
            assert fp.call_count(["kubectl", "port-forward", fp.any()]) == 1

    @pytest.mark.asyncio
    async def test_setup_timeout_kills_process(self, fp: FakeProcess) -> None:
        """setup() kills process and raises if port never becomes available."""
        provider = K8sConnectionProvider(environment="dev", environments=TEST_ENVIRONMENTS)

        # Register successful auth check
        fp.register(
            ["kubectl", "auth", "can-i", "get", "pods", "-n", "unblu-dev"],
            returncode=0,
        )
        # Register port-forward that keeps running (simulated by callback)
        fp.register(
            ["kubectl", "port-forward", "-n", "unblu-dev", "svc/haproxy", "8084:8080"],
            returncode=0,
            wait=0.1,  # Small delay to simulate running process
        )

        with (
            patch.object(provider, "_is_port_in_use", return_value=False),
            patch("shutil.which", return_value="/usr/bin/kubectl"),
            patch("asyncio.sleep", new_callable=AsyncMock),
            pytest.raises(ConfigurationError, match="Port-forward timed out"),
        ):
            await provider.setup()

    @pytest.mark.asyncio
    async def test_teardown_terminates_process_when_owner(self) -> None:
        """teardown() terminates the port-forward process only when we own it."""
        provider = K8sConnectionProvider(environment="dev", environments=TEST_ENVIRONMENTS)
        mock_process = MagicMock()
        provider._port_forward_process = mock_process
        provider._owns_port_forward = True

        await provider.teardown()

        mock_process.terminate.assert_called_once()
        mock_process.wait.assert_called_once_with(timeout=5)
        assert provider._port_forward_process is None

    @pytest.mark.asyncio
    async def test_teardown_kills_on_timeout(self) -> None:
        """teardown() kills process if terminate times out."""
        provider = K8sConnectionProvider(environment="dev", environments=TEST_ENVIRONMENTS)
        mock_process = MagicMock()
        mock_process.wait.side_effect = subprocess.TimeoutExpired(cmd="kubectl", timeout=5)
        provider._port_forward_process = mock_process
        provider._owns_port_forward = True

        await provider.teardown()

        mock_process.terminate.assert_called_once()
        mock_process.kill.assert_called_once()
        assert provider._port_forward_process is None

    @pytest.mark.asyncio
    async def test_teardown_no_process_when_owner(self) -> None:
        """teardown() handles case where no process was started."""
        provider = K8sConnectionProvider(environment="dev", environments=TEST_ENVIRONMENTS)
        provider._port_forward_process = None
        provider._owns_port_forward = True

        # Should not raise
        await provider.teardown()

    @pytest.mark.asyncio
    async def test_teardown_skips_cleanup_when_not_owner(self) -> None:
        """teardown() skips cleanup when we don't own the port-forward."""
        provider = K8sConnectionProvider(environment="dev", environments=TEST_ENVIRONMENTS)
        mock_process = MagicMock()
        provider._port_forward_process = mock_process
        provider._owns_port_forward = False

        await provider.teardown()

        # Should not terminate the process since we don't own it
        mock_process.terminate.assert_not_called()
        # Process reference should remain (it's owned by another instance)
        assert provider._port_forward_process == mock_process

    @pytest.mark.asyncio
    async def test_setup_reuses_existing_port(self) -> None:
        """setup() reuses existing port-forward when port is already in use."""
        provider = K8sConnectionProvider(environment="dev", environments=TEST_ENVIRONMENTS)

        with patch.object(provider, "_is_port_in_use", return_value=True):
            await provider.setup()

            assert provider._owns_port_forward is False
            assert provider._port_forward_process is None

    @pytest.mark.asyncio
    async def test_health_check_delegates_to_port_check(self) -> None:
        """health_check() returns port availability status."""
        provider = K8sConnectionProvider(environment="dev", environments=TEST_ENVIRONMENTS)

        with patch.object(provider, "_is_port_in_use", return_value=True):
            assert await provider.health_check() is True

        with patch.object(provider, "_is_port_in_use", return_value=False):
            assert await provider.health_check() is False

    def test_is_port_in_use_available_port(self) -> None:
        """_is_port_in_use returns False for available port."""
        provider = K8sConnectionProvider(environment="dev", environments=TEST_ENVIRONMENTS)
        # Use a high port that's unlikely to be in use
        provider._env_config = K8sEnvironmentConfig(name="test", local_port=59999, namespace="test")
        assert provider._is_port_in_use() is False

    def test_is_port_in_use_bound_port(self) -> None:
        """_is_port_in_use returns True for bound port."""
        provider = K8sConnectionProvider(environment="dev", environments=TEST_ENVIRONMENTS)

        # Bind a port temporarily
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("localhost", 0))
            port = s.getsockname()[1]
            s.listen(1)

            provider._env_config = K8sEnvironmentConfig(name="test", local_port=port, namespace="test")
            assert provider._is_port_in_use() is True

    @pytest.mark.asyncio
    async def test_ensure_connection_does_nothing_when_port_available(self) -> None:
        """ensure_connection() does nothing when port is already available."""
        provider = K8sConnectionProvider(environment="dev", environments=TEST_ENVIRONMENTS)

        with patch.object(provider, "_is_port_in_use", return_value=True):
            await provider.ensure_connection()
            # Should not have started any process
            assert provider._port_forward_process is None

    @pytest.mark.asyncio
    async def test_ensure_connection_restarts_dead_port_forward(self, fp: FakeProcess) -> None:
        """ensure_connection() restarts port-forward when our process died."""
        provider = K8sConnectionProvider(environment="dev", environments=TEST_ENVIRONMENTS)
        provider._owns_port_forward = True

        # Simulate a dead process
        mock_process = MagicMock()
        mock_process.poll.return_value = 1  # Process exited with code 1
        provider._port_forward_process = mock_process

        # Port check returns False (not available), then True (after restart)
        port_check_results = [False, True]

        # Register successful auth check
        fp.register(
            ["kubectl", "auth", "can-i", "get", "pods", "-n", "unblu-dev"],
            returncode=0,
        )
        # Register port-forward
        fp.register(
            ["kubectl", "port-forward", "-n", "unblu-dev", "svc/haproxy", "8084:8080"],
            returncode=0,
        )

        with (
            patch.object(provider, "_is_port_in_use", side_effect=port_check_results),
            patch("shutil.which", return_value="/usr/bin/kubectl"),
        ):
            await provider.ensure_connection()

            # Should have started a new port-forward
            assert provider._owns_port_forward is True
            assert fp.call_count(["kubectl", "port-forward", fp.any()]) == 1

    @pytest.mark.asyncio
    async def test_ensure_connection_kills_malfunctioning_process(self, fp: FakeProcess) -> None:
        """ensure_connection() kills alive but malfunctioning port-forward."""
        provider = K8sConnectionProvider(environment="dev", environments=TEST_ENVIRONMENTS)
        provider._owns_port_forward = True

        # Simulate alive but malfunctioning process (port not available)
        mock_process = MagicMock()
        mock_process.poll.return_value = None  # Process is alive
        provider._port_forward_process = mock_process

        # Port check returns False (not available), then True (after restart)
        port_check_results = [False, True]

        # Register successful auth check
        fp.register(
            ["kubectl", "auth", "can-i", "get", "pods", "-n", "unblu-dev"],
            returncode=0,
        )
        # Register port-forward
        fp.register(
            ["kubectl", "port-forward", "-n", "unblu-dev", "svc/haproxy", "8084:8080"],
            returncode=0,
        )

        with (
            patch.object(provider, "_is_port_in_use", side_effect=port_check_results),
            patch("shutil.which", return_value="/usr/bin/kubectl"),
        ):
            await provider.ensure_connection()

            # Should have killed the malfunctioning process
            mock_process.kill.assert_called_once()
            mock_process.wait.assert_called_once_with(timeout=5)
            # Should have started a new port-forward
            assert provider._owns_port_forward is True
            assert fp.call_count(["kubectl", "port-forward", fp.any()]) == 1


class TestDetectEnvironmentFromContext:
    """Tests for detect_environment_from_context function."""

    def test_detects_dev_environment(self) -> None:
        """Detects dev from context name."""
        with (
            patch("subprocess.run") as mock_run,
            patch(
                "unblu_mcp._internal.providers_k8s._get_default_environments",
                return_value=TEST_ENVIRONMENTS,
            ),
        ):
            mock_run.return_value = MagicMock(stdout="cluster-dev-context\n")
            assert detect_environment_from_context() == "dev"

    def test_detects_environment_with_suffix(self) -> None:
        """Detects environment from context ending with env name."""
        with (
            patch("subprocess.run") as mock_run,
            patch(
                "unblu_mcp._internal.providers_k8s._get_default_environments",
                return_value=TEST_ENVIRONMENTS,
            ),
        ):
            mock_run.return_value = MagicMock(stdout="my-cluster-prod\n")
            assert detect_environment_from_context() == "prod"

    def test_detects_environment_with_dash_pattern(self) -> None:
        """Detects environment from -env- pattern in context."""
        with (
            patch("subprocess.run") as mock_run,
            patch(
                "unblu_mcp._internal.providers_k8s._get_default_environments",
                return_value=TEST_ENVIRONMENTS,
            ),
        ):
            mock_run.return_value = MagicMock(stdout="prefix-test1-suffix\n")
            assert detect_environment_from_context() == "test1"

    def test_returns_none_for_unknown_context(self) -> None:
        """Returns None if context doesn't match any environment."""
        with (
            patch("subprocess.run") as mock_run,
            patch(
                "unblu_mcp._internal.providers_k8s._get_default_environments",
                return_value=TEST_ENVIRONMENTS,
            ),
        ):
            mock_run.return_value = MagicMock(stdout="unknown-cluster\n")
            assert detect_environment_from_context() is None

    def test_returns_none_on_subprocess_error(self) -> None:
        """Returns None if kubectl command fails."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(1, "kubectl")
            assert detect_environment_from_context() is None

    def test_returns_none_if_kubectl_not_found(self) -> None:
        """Returns None if kubectl is not installed."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError()
            assert detect_environment_from_context() is None
