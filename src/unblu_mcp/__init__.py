"""unblu-mcp package.

A model context protocol server for interacting with Unblu deployments.
"""

# Also expose at package level for entry point
from unblu_mcp._internal import cli
from unblu_mcp._internal.cli import get_parser, main
from unblu_mcp._internal.exceptions import ConfigurationError
from unblu_mcp._internal.models import (
    AccountInfo,
    AvailabilityInfo,
    ConversationDetail,
    ConversationPage,
    ConversationParticipant,
    ConversationSummary,
    ExecuteResult,
    OperationMatch,
    OperationResult,
    OperationSearchResult,
    PersonAmbiguousResult,
    PersonDetail,
    PersonPage,
    PersonSummary,
    UserDetail,
    UserPage,
    UserSummary,
)
from unblu_mcp._internal.pagination import (
    build_query_body,
    make_enum_filter,
    make_id_filter,
    make_string_filter,
    parse_pagination,
)
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
    "AccountInfo",
    "AvailabilityInfo",
    "ConfigurationError",
    "ConnectionConfig",
    "ConnectionProvider",
    "ConversationDetail",
    "ConversationPage",
    "ConversationParticipant",
    "ConversationSummary",
    "DefaultConnectionProvider",
    "ExecuteResult",
    "K8sConnectionProvider",
    "K8sEnvironmentConfig",
    "OperationInfo",
    "OperationMatch",
    "OperationResult",
    "OperationSchema",
    "OperationSearchResult",
    "PersonAmbiguousResult",
    "PersonDetail",
    "PersonPage",
    "PersonSummary",
    "ServiceInfo",
    "UnbluAPIRegistry",
    "UserDetail",
    "UserPage",
    "UserSummary",
    "build_query_body",
    "cli",
    "create_server",
    "detect_environment_from_context",
    "get_parser",
    "get_server",
    "main",
    "make_enum_filter",
    "make_id_filter",
    "make_string_filter",
    "parse_pagination",
]
