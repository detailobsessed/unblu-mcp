"""unblu-mcp package.

A model context protocol server for interacting with Unblu deployments.
"""

from __future__ import annotations

# Also expose at package level for entry point
from unblu_mcp._internal import cli
from unblu_mcp._internal.cli import get_parser, main
from unblu_mcp._internal.server import (
    OperationInfo,
    OperationSchema,
    ServiceInfo,
    UnbluAPIRegistry,
    create_server,
    get_server,
)

__all__: list[str] = [
    "OperationInfo",
    "OperationSchema",
    "ServiceInfo",
    "UnbluAPIRegistry",
    "cli",
    "create_server",
    "get_parser",
    "get_server",
    "main",
]
