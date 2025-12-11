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

from __future__ import annotations

import argparse
import sys
from typing import TYPE_CHECKING, Any

from unblu_mcp._internal import debug

if TYPE_CHECKING:
    from fastmcp import FastMCP


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
        "--transport",
        type=str,
        choices=["stdio", "sse"],
        default="stdio",
        help="MCP transport type (default: stdio).",
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
    opts = parser.parse_args(args=args)

    server = _create_server(spec_path=opts.spec)
    server.run(transport=opts.transport)
    return 0


def _create_server(spec_path: str | None = None) -> FastMCP:
    """Lazy import to avoid circular imports and top-level import issues."""
    from unblu_mcp._internal.server import create_server  # noqa: PLC0415

    return create_server(spec_path=spec_path)
