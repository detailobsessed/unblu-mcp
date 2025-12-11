"""unblu-mcp package.

A model context protocol server for interacting with Unblu deployments.
"""

from __future__ import annotations

# Also expose at package level for entry point
from unblu_mcp._internal import cli
from unblu_mcp._internal.cli import get_parser, main

__all__: list[str] = ["cli", "get_parser", "main"]
