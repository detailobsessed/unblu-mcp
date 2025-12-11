"""unblu-mcp package.

A model context protocol server for interacting with Unblu deployments.
"""

from __future__ import annotations

from unblu_mcp._internal.cli import get_parser, main

__all__: list[str] = ["get_parser", "main"]
