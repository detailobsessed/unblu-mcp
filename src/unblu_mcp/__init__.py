"""unblu-mcp package.

A model context protocol server for interacting with Unblu deployments.
"""

# Also expose at package level for entry point
from unblu_mcp._internal import cli
from unblu_mcp._internal.cli import get_parser, main
from unblu_mcp._internal.providers import (
    ConnectionConfig,
    ConnectionProvider,
    DefaultConnectionProvider,
)
from unblu_mcp._internal.providers_k8s import (
    K8sConnectionProvider,
    K8sEnvironmentConfig,
    detect_environment_from_context,
)
from unblu_mcp._internal.server import (
    OperationInfo,
    OperationSchema,
    ServiceInfo,
    UnbluAPIRegistry,
    create_server,
    get_server,
)

__all__: list[str] = [
    "ConnectionConfig",
    "ConnectionProvider",
    "DefaultConnectionProvider",
    "K8sConnectionProvider",
    "K8sEnvironmentConfig",
    "OperationInfo",
    "OperationSchema",
    "ServiceInfo",
    "UnbluAPIRegistry",
    "cli",
    "create_server",
    "detect_environment_from_context",
    "get_parser",
    "get_server",
    "main",
]
