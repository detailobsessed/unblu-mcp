"""Tests for the CLI."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from unblu_mcp import main
from unblu_mcp._internal import debug


def test_main() -> None:
    """Basic CLI test."""
    assert main([]) == 0


def test_show_help(capsys: pytest.CaptureFixture) -> None:
    """Show help.

    Parameters:
        capsys: Pytest fixture to capture output.
    """
    with pytest.raises(SystemExit):
        main(["-h"])
    captured = capsys.readouterr()
    assert "unblu-mcp" in captured.out


def test_show_version(capsys: pytest.CaptureFixture) -> None:
    """Show version.

    Parameters:
        capsys: Pytest fixture to capture output.
    """
    with pytest.raises(SystemExit):
        main(["-V"])
    captured = capsys.readouterr()
    assert debug._get_version() in captured.out


def test_show_debug_info(capsys: pytest.CaptureFixture) -> None:
    """Show debug information.

    Parameters:
        capsys: Pytest fixture to capture output.
    """
    with pytest.raises(SystemExit):
        main(["--debug-info"])
    captured = capsys.readouterr().out.lower()
    assert "python" in captured
    assert "system" in captured
    assert "environment" in captured
    assert "packages" in captured


def test_help_shows_policy_option(capsys: pytest.CaptureFixture) -> None:
    """Help shows --policy option.

    Parameters:
        capsys: Pytest fixture to capture output.
    """
    with pytest.raises(SystemExit):
        main(["-h"])
    captured = capsys.readouterr()
    assert "--policy" in captured.out
    assert "Eunomia" in captured.out


def test_help_shows_provider_options(capsys: pytest.CaptureFixture) -> None:
    """Help shows --provider, --environment, and --k8s-config options.

    Parameters:
        capsys: Pytest fixture to capture output.
    """
    with pytest.raises(SystemExit):
        main(["-h"])
    captured = capsys.readouterr()
    assert "--provider" in captured.out
    assert "--environment" in captured.out
    assert "--k8s-config" in captured.out
    assert "k8s" in captured.out


def test_get_provider_default() -> None:
    """Test _get_provider returns None for default provider."""
    from unblu_mcp._internal.cli import _get_provider

    provider = _get_provider("default", "t1")
    assert provider is None


def test_get_provider_k8s() -> None:
    """Test _get_provider returns K8sConnectionProvider for k8s provider."""
    from unblu_mcp._internal.cli import _get_provider
    from unblu_mcp._internal.providers_k8s import K8sConnectionProvider

    provider = _get_provider("k8s", "dev")
    assert isinstance(provider, K8sConnectionProvider)
    assert provider.environment == "dev"


def test_get_provider_k8s_custom_environment() -> None:
    """Test _get_provider with custom environment."""
    from unblu_mcp._internal.cli import _get_provider
    from unblu_mcp._internal.providers_k8s import K8sConnectionProvider

    provider = _get_provider("k8s", "prod")
    assert isinstance(provider, K8sConnectionProvider)
    assert provider.environment == "prod"


def test_get_provider_k8s_with_config_file(tmp_path: Path) -> None:
    """Test _get_provider with custom config file."""
    from unblu_mcp._internal.cli import _get_provider
    from unblu_mcp._internal.providers_k8s import K8sConnectionProvider

    config_file = tmp_path / "k8s_envs.yaml"
    config_file.write_text("""
environments:
  custom-env:
    local_port: 9999
    namespace: my-namespace
    service: my-service
    service_port: 8080
    api_path: /api/v1
""")
    provider = _get_provider("k8s", "custom-env", str(config_file))
    assert isinstance(provider, K8sConnectionProvider)
    assert provider.environment == "custom-env"
    assert provider.local_port == 9999


def test_get_provider_k8s_with_empty_config_file(tmp_path: Path) -> None:
    """Test _get_provider raises error for empty config file."""
    from unblu_mcp._internal.cli import _get_provider

    config_file = tmp_path / "empty.yaml"
    config_file.write_text("environments: {}")

    with pytest.raises(ValueError, match="No environments found"):
        _get_provider("k8s", "dev", str(config_file))
