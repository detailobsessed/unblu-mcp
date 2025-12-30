# Why does this file exist, and why not put this in `__main__`?
#
# You might be tempted to import things from `__main__` later,
# but that will cause problems: the code will get executed twice:
#
# - When you run `python -m unblu_mcp` python will execute
#   `__main__.py` as a script. That means there won't be any
#   `unblu_mcp.__main__` in `sys.modules`.
# - When you import `__main__` it will get executed again (as a module) because
#   there's no `unblu_mcp.__main__` in `sys.modules`.


import argparse
import sys
from typing import Any

from fastmcp import FastMCP

from unblu_mcp._internal import debug
from unblu_mcp._internal.exceptions import ConfigurationError


class _DebugInfo(argparse.Action):
    def __init__(self, nargs: int | str | None = 0, **kwargs: Any) -> None:
        super().__init__(nargs=nargs, **kwargs)

    def __call__(self, *args: Any, **kwargs: Any) -> None:  # noqa: ARG002
        debug._print_debug_info()
        sys.exit(0)


def get_parser() -> argparse.ArgumentParser:
    """Return the CLI argument parser.

    Returns:
        An argparse parser.
    """
    parser = argparse.ArgumentParser(
        prog="unblu-mcp",
        description="Unblu MCP Server - Token-efficient access to Unblu API",
    )
    parser.add_argument("-V", "--version", action="version", version=f"%(prog)s {debug._get_version()}")
    parser.add_argument("--debug-info", action=_DebugInfo, help="Print debug information.")
    parser.add_argument(
        "--spec",
        type=str,
        default=None,
        help="Path to swagger.json OpenAPI spec file.",
    )
    parser.add_argument(
        "--policy",
        type=str,
        default=None,
        help="Path to Eunomia policy JSON file for authorization. Requires unblu-mcp[safety].",
    )
    parser.add_argument(
        "--provider",
        type=str,
        choices=["default", "k8s"],
        default="default",
        help="Connection provider to use (default: default).",
    )
    parser.add_argument(
        "--environment",
        type=str,
        default="dev",
        help="K8s environment name (only with --provider k8s). Default: dev.",
    )
    parser.add_argument(
        "--k8s-config",
        type=str,
        default=None,
        help="Path to K8s environments YAML config file (only with --provider k8s).",
    )
    return parser


def main(args: list[str] | None = None) -> int:
    """Run the main program.

    This function is executed when you type `unblu-mcp` or `python -m unblu_mcp`.

    Parameters:
        args: Arguments passed from the command line.

    Returns:
        An exit code.
    """
    parser = get_parser()
    if args == []:
        parser.print_help()
        return 0
    opts = parser.parse_args(args=args)

    provider = _get_provider(opts.provider, opts.environment, opts.k8s_config)
    server = _create_server(spec_path=opts.spec, policy_file=opts.policy, provider=provider)
    try:
        server.run()
    except ConfigurationError as e:
        print(f"\n❌ Configuration Error: {e}\n", file=sys.stderr)
        return 1
    return 0


def _get_provider(provider_type: str, environment: str, k8s_config: str | None = None) -> Any:
    """Get the appropriate connection provider based on CLI args."""
    if provider_type == "k8s":
        from unblu_mcp._internal.providers_k8s import (  # noqa: PLC0415
            K8sConnectionProvider,
            _load_environments_from_yaml,
        )

        environments = None
        if k8s_config:
            from pathlib import Path  # noqa: PLC0415

            environments = _load_environments_from_yaml(Path(k8s_config))
            if not environments:
                msg = f"No environments found in {k8s_config}"
                raise ValueError(msg)

        return K8sConnectionProvider(environment=environment, environments=environments)
    # Default provider will be created by create_server from env vars
    return None


def _create_server(
    spec_path: str | None = None,
    policy_file: str | None = None,
    provider: Any = None,
) -> FastMCP:
    """Lazy import to avoid circular imports and top-level import issues."""
    from unblu_mcp._internal.server import create_server  # noqa: PLC0415

    return create_server(spec_path=spec_path, policy_file=policy_file, provider=provider)
