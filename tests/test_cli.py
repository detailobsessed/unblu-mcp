"""Tests for the CLI."""

import runpy
import sys
from pathlib import Path

import pytest

from unblu_mcp import main
from unblu_mcp._internal import debug
from unblu_mcp._internal.exceptions import ConfigurationError
from unblu_mcp._internal.providers_k8s import _get_k8s_config_template


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


def test_print_k8s_config_template(capsys: pytest.CaptureFixture) -> None:
    """Print the canonical K8s config template."""
    with pytest.raises(SystemExit):
        main(["--print-k8s-config-template"])
    captured = capsys.readouterr()
    assert captured.out == _get_k8s_config_template()


def test_module_entrypoint_invokes_cli_main(monkeypatch: pytest.MonkeyPatch) -> None:
    """python -m unblu_mcp delegates to the CLI main function."""
    from unblu_mcp._internal import cli

    captured: dict[str, list[str]] = {}

    def fake_main(args: list[str]) -> int:
        captured["args"] = args
        return 7

    monkeypatch.setattr(cli, "main", fake_main)
    monkeypatch.setattr(sys, "argv", ["python", "--provider", "k8s"])

    with pytest.raises(SystemExit, match="7"):
        runpy.run_module("unblu_mcp.__main__", run_name="__main__")

    assert captured["args"] == ["--provider", "k8s"]


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
    assert "--print-k8s-config-template" in captured.out
    assert "k8s" in captured.out


def test_get_provider_default() -> None:
    """Test _get_provider returns None for default provider."""
    from unblu_mcp._internal.cli import _get_provider

    provider = _get_provider("default", "dev")
    assert provider is None


def test_main_runs_server_and_returns_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    """main() returns zero after a successful server run."""
    from unblu_mcp._internal import cli

    provider = object()
    calls: dict[str, object] = {}

    class FakeServer:
        def run(self) -> None:
            calls["ran"] = True

    def fake_get_provider(provider_type: str, environment: str, k8s_config: str | None = None) -> object:
        calls["provider_type"] = provider_type
        calls["environment"] = environment
        calls["k8s_config"] = k8s_config
        return provider

    def fake_create_server(spec_path: str | None = None, provider: object | None = None) -> FakeServer:
        calls["spec_path"] = spec_path
        calls["provider"] = provider
        return FakeServer()

    monkeypatch.setattr(cli, "_get_provider", fake_get_provider)
    monkeypatch.setattr(cli, "_create_server", fake_create_server)

    assert cli.main(["--provider", "default"]) == 0
    assert calls == {
        "provider_type": "default",
        "environment": "dev",
        "k8s_config": None,
        "spec_path": None,
        "provider": provider,
        "ran": True,
    }


def test_main_configuration_error_prints_message(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """main() returns one and prints a clean error for configuration failures."""
    from unblu_mcp._internal import cli

    msg = "broken config"

    class FakeServer:
        def run(self) -> None:
            raise ConfigurationError(msg)

    monkeypatch.setattr(cli, "_get_provider", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(cli, "_create_server", lambda **_kwargs: FakeServer())

    assert cli.main(["--provider", "default"]) == 1
    captured = capsys.readouterr()
    assert "Configuration Error: broken config" in captured.err


def test_get_provider_k8s(tmp_path: Path) -> None:
    """Test _get_provider returns K8sConnectionProvider for k8s provider."""
    from unblu_mcp._internal.cli import _get_provider
    from unblu_mcp._internal.providers_k8s import K8sConnectionProvider

    # Create a test config file with dev environment
    config_file = tmp_path / "k8s_envs.yaml"
    config_file.write_text(
        """
environments:
  dev:
    local_port: 8084
    namespace: unblu-dev
""",
        encoding="utf-8",
    )
    provider = _get_provider("k8s", "dev", str(config_file))
    assert isinstance(provider, K8sConnectionProvider)
    assert provider.environment == "dev"


def test_get_provider_k8s_custom_environment(tmp_path: Path) -> None:
    """Test _get_provider with custom environment."""
    from unblu_mcp._internal.cli import _get_provider
    from unblu_mcp._internal.providers_k8s import K8sConnectionProvider

    # Create a test config file with prod environment
    config_file = tmp_path / "k8s_envs.yaml"
    config_file.write_text(
        """
environments:
  prod:
    local_port: 8086
    namespace: unblu-prod
""",
        encoding="utf-8",
    )
    provider = _get_provider("k8s", "prod", str(config_file))
    assert isinstance(provider, K8sConnectionProvider)
    assert provider.environment == "prod"


def test_get_provider_k8s_with_config_file(tmp_path: Path) -> None:
    """Test _get_provider with custom config file."""
    from unblu_mcp._internal.cli import _get_provider
    from unblu_mcp._internal.providers_k8s import K8sConnectionProvider

    config_file = tmp_path / "k8s_envs.yaml"
    config_file.write_text(
        """
environments:
  custom-env:
    local_port: 9999
    namespace: my-namespace
    service: my-service
    service_port: 8080
    api_path: /api/v1
""",
        encoding="utf-8",
    )
    provider = _get_provider("k8s", "custom-env", str(config_file))
    assert isinstance(provider, K8sConnectionProvider)
    assert provider.environment == "custom-env"
    assert provider.local_port == 9999


def test_get_provider_k8s_with_empty_config_file(tmp_path: Path) -> None:
    """Test _get_provider raises error for empty config file."""
    from unblu_mcp._internal.cli import _get_provider

    config_file = tmp_path / "empty.yaml"
    config_file.write_text("environments: {}", encoding="utf-8")

    with pytest.raises(ConfigurationError, match="No environments found"):
        _get_provider("k8s", "dev", str(config_file))


def test_create_server_lazy_import(monkeypatch: pytest.MonkeyPatch) -> None:
    """_create_server delegates to the server module lazily."""
    from unblu_mcp._internal import cli, server

    provider = object()
    expected = object()

    def fake_create_server(spec_path: str | None = None, provider: object | None = None) -> object:
        assert spec_path == "swagger.json"
        assert provider is provider_arg
        return expected

    provider_arg = provider
    monkeypatch.setattr(server, "create_server", fake_create_server)

    assert cli._create_server(spec_path="swagger.json", provider=provider) is expected
