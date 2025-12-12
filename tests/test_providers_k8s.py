"""Tests for the Kubernetes connection provider."""

from __future__ import annotations

import socket
import subprocess
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from unblu_mcp._internal.providers_k8s import (
    DEFAULT_ENVIRONMENTS,
    K8sConnectionProvider,
    K8sEnvironmentConfig,
    detect_environment_from_context,
)


class TestK8sEnvironmentConfig:
    """Tests for K8sEnvironmentConfig dataclass."""

    def test_default_values(self) -> None:
        """Config has sensible defaults."""
        config = K8sEnvironmentConfig(name="test", local_port=8080, namespace="test-ns")
        assert config.service == "haproxy"
        assert config.service_port == 8080
        assert config.api_path == "/kop/rest/v4"

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


class TestDefaultEnvironments:
    """Tests for default environment configurations."""

    def test_all_environments_defined(self) -> None:
        """All expected environments are defined."""
        assert "t1" in DEFAULT_ENVIRONMENTS
        assert "t2" in DEFAULT_ENVIRONMENTS
        assert "p1" in DEFAULT_ENVIRONMENTS
        assert "e1" in DEFAULT_ENVIRONMENTS

    def test_environments_have_unique_ports(self) -> None:
        """Each environment has a unique local port."""
        ports = [env.local_port for env in DEFAULT_ENVIRONMENTS.values()]
        assert len(ports) == len(set(ports))

    def test_t1_config(self) -> None:
        """T1 environment has correct configuration."""
        t1 = DEFAULT_ENVIRONMENTS["t1"]
        assert t1.name == "t1"
        assert t1.local_port == 8084
        assert t1.namespace == "appl-kop-t1"


class TestK8sConnectionProvider:
    """Tests for K8sConnectionProvider."""

    def test_init_with_string_environment(self) -> None:
        """Provider initializes with string environment name."""
        provider = K8sConnectionProvider(environment="t1")
        assert provider.environment == "t1"
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
            K8sConnectionProvider(environment="invalid")

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
            environment="t1",
            trusted_user_id="testuser",
            trusted_user_role="ADMIN",
        )
        config = provider.get_config()

        assert config.base_url == "http://localhost:8084/kop/rest/v4"
        assert config.headers["x-unblu-trusted-user-id"] == "testuser"
        assert config.headers["x-unblu-trusted-user-role"] == "ADMIN"

    def test_get_config_default_trusted_headers(self) -> None:
        """get_config uses default trusted headers."""
        provider = K8sConnectionProvider(environment="t1")
        config = provider.get_config()

        assert config.headers["x-unblu-trusted-user-id"] == "superadmin"
        assert config.headers["x-unblu-trusted-user-role"] == "SUPER_ADMIN"

    @pytest.mark.asyncio
    async def test_setup_port_already_in_use(self) -> None:
        """setup() returns early if port is already in use."""
        provider = K8sConnectionProvider(environment="t1")

        with patch.object(provider, "_is_port_in_use", return_value=True):
            await provider.setup()
            # Should not start a new process
            assert provider._port_forward_process is None

    @pytest.mark.asyncio
    async def test_setup_kubectl_not_found(self) -> None:
        """setup() raises RuntimeError if kubectl not found."""
        provider = K8sConnectionProvider(environment="t1")

        with (
            patch.object(provider, "_is_port_in_use", return_value=False),
            patch("shutil.which", return_value=None),
            pytest.raises(RuntimeError, match="kubectl not found"),
        ):
            await provider.setup()

    @pytest.mark.asyncio
    async def test_setup_starts_port_forward(self) -> None:
        """setup() starts kubectl port-forward process."""
        provider = K8sConnectionProvider(environment="t1")
        mock_process = MagicMock()

        # First call returns False (port not in use), subsequent calls return True (port ready)
        port_check_results = [False, True]

        with (
            patch.object(provider, "_is_port_in_use", side_effect=port_check_results),
            patch("shutil.which", return_value="/usr/bin/kubectl"),
            patch("subprocess.Popen", return_value=mock_process) as mock_popen,
        ):
            await provider.setup()

            mock_popen.assert_called_once()
            call_args = mock_popen.call_args[0][0]
            assert "kubectl" in call_args
            assert "port-forward" in call_args
            assert "-n" in call_args
            assert "appl-kop-t1" in call_args

    @pytest.mark.asyncio
    async def test_setup_timeout_kills_process(self) -> None:
        """setup() kills process and raises if port never becomes available."""
        provider = K8sConnectionProvider(environment="t1")
        mock_process = MagicMock()

        with (
            patch.object(provider, "_is_port_in_use", return_value=False),
            patch("shutil.which", return_value="/usr/bin/kubectl"),
            patch("subprocess.Popen", return_value=mock_process),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            with pytest.raises(RuntimeError, match="Failed to start port-forward"):
                await provider.setup()

            mock_process.kill.assert_called_once()

    @pytest.mark.asyncio
    async def test_teardown_terminates_process(self) -> None:
        """teardown() terminates the port-forward process."""
        provider = K8sConnectionProvider(environment="t1")
        mock_process = MagicMock()
        provider._port_forward_process = mock_process

        await provider.teardown()

        mock_process.terminate.assert_called_once()
        mock_process.wait.assert_called_once_with(timeout=5)
        assert provider._port_forward_process is None

    @pytest.mark.asyncio
    async def test_teardown_kills_on_timeout(self) -> None:
        """teardown() kills process if terminate times out."""
        provider = K8sConnectionProvider(environment="t1")
        mock_process = MagicMock()
        mock_process.wait.side_effect = subprocess.TimeoutExpired(cmd="kubectl", timeout=5)
        provider._port_forward_process = mock_process

        await provider.teardown()

        mock_process.terminate.assert_called_once()
        mock_process.kill.assert_called_once()
        assert provider._port_forward_process is None

    @pytest.mark.asyncio
    async def test_teardown_no_process(self) -> None:
        """teardown() does nothing if no process was started."""
        provider = K8sConnectionProvider(environment="t1")
        provider._port_forward_process = None

        await provider.teardown()  # Should not raise

    @pytest.mark.asyncio
    async def test_health_check_delegates_to_port_check(self) -> None:
        """health_check() returns port availability status."""
        provider = K8sConnectionProvider(environment="t1")

        with patch.object(provider, "_is_port_in_use", return_value=True):
            assert await provider.health_check() is True

        with patch.object(provider, "_is_port_in_use", return_value=False):
            assert await provider.health_check() is False

    def test_is_port_in_use_available_port(self) -> None:
        """_is_port_in_use returns False for available port."""
        provider = K8sConnectionProvider(environment="t1")
        # Use a high port that's unlikely to be in use
        provider._env_config = K8sEnvironmentConfig(name="test", local_port=59999, namespace="test")
        assert provider._is_port_in_use() is False

    def test_is_port_in_use_bound_port(self) -> None:
        """_is_port_in_use returns True for bound port."""
        provider = K8sConnectionProvider(environment="t1")

        # Bind a port temporarily
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("localhost", 0))
            port = s.getsockname()[1]
            s.listen(1)

            provider._env_config = K8sEnvironmentConfig(name="test", local_port=port, namespace="test")
            assert provider._is_port_in_use() is True


class TestDetectEnvironmentFromContext:
    """Tests for detect_environment_from_context function."""

    def test_detects_t1_environment(self) -> None:
        """Detects t1 from context name."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="cluster-t1-context\n")
            assert detect_environment_from_context() == "t1"

    def test_detects_environment_with_suffix(self) -> None:
        """Detects environment from context ending with env name."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="my-cluster-p1\n")
            assert detect_environment_from_context() == "p1"

    def test_detects_environment_with_dash_pattern(self) -> None:
        """Detects environment from -env- pattern in context."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="prefix-e1-suffix\n")
            assert detect_environment_from_context() == "e1"

    def test_returns_none_for_unknown_context(self) -> None:
        """Returns None if context doesn't match any environment."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="production-cluster\n")
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
