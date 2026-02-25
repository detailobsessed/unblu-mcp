from __future__ import annotations

import contextlib
import importlib.resources
import json
import re
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

import httpx
from fastmcp import Context, FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.server.middleware.caching import CallToolSettings, ResponseCachingMiddleware
from fastmcp.server.middleware.error_handling import ErrorHandlingMiddleware
from fastmcp.server.middleware.logging import LoggingMiddleware
from pydantic import BaseModel, Field

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
    parse_pagination,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from unblu_mcp._internal.providers import ConnectionProvider

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

_MAX_REF_DEPTH = 3
_HTTP_NO_CONTENT = 204
_HTTP_NOT_FOUND = 404
_HTTP_CLIENT_ERROR = 400
_DEFAULT_TRUNCATE_CHARS = 10_000

# Services hidden from find_operation by default (infra / security-sensitive)
_INFRA_SERVICES: frozenset[str] = frozenset({
    "Authentication",
    "Audit Log",
    "Feature Flags",
    "System",
    "Product",
})

# Services that have dedicated curated tools
_CURATED_SERVICES: frozenset[str] = frozenset({
    "Accounts",
    "Conversations",
    "Persons",
    "Users",
    "Named Areas",
    "Availability",
})

# ---------------------------------------------------------------------------
# Simple registry data classes (exposed for tests and public API)
# ---------------------------------------------------------------------------


class ServiceInfo(BaseModel):
    """Service/tag grouping of API operations."""

    name: str = Field(description="Service name (tag)")
    description: str = Field(description="Service description")
    operation_count: int = Field(description="Number of operations in this service")
    tier: str = Field(
        default="long-tail",
        description="curated = typed tools exist; long-tail = use execute_operation; infra = hidden by default",
    )


class OperationInfo(BaseModel):
    """Brief information about an API operation."""

    operation_id: str = Field(description="Unique operation identifier")
    method: str = Field(description="HTTP method (GET, POST, DELETE, etc.)")
    path: str = Field(description="API path")
    summary: str = Field(description="Brief description of the operation")
    service: str = Field(default="", description="Service/tag this belongs to")


class OperationSchema(BaseModel):
    """Full schema for an API operation."""

    operation_id: str
    method: str
    path: str
    summary: str
    description: str | None
    parameters: list[dict[str, Any]]
    request_body: dict[str, Any] | None
    responses: dict[str, Any]


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class UnbluAPIRegistry:
    """Registry for Unblu API operations parsed from OpenAPI spec."""

    def __init__(self, spec: dict[str, Any]) -> None:
        self.spec = spec
        self.services: dict[str, ServiceInfo] = {}
        self.operations: dict[str, dict[str, Any]] = {}
        self.operations_by_service: dict[str, list[str]] = {}
        self._schema_cache: dict[str, dict[str, Any]] = {}
        self._parse_spec()

    def _parse_spec(self) -> None:
        """Parse OpenAPI spec into indexed structures."""
        for tag in self.spec.get("tags", []):
            name = tag.get("name", "")
            if name.startswith("For ") or name == "Schemas":
                continue
            if name in _CURATED_SERVICES:
                tier = "curated"
            elif name in _INFRA_SERVICES:
                tier = "infra"
            else:
                tier = "long-tail"
            self.services[name] = ServiceInfo(
                name=name,
                description=tag.get("description", "")[:200],
                operation_count=0,
                tier=tier,
            )
            self.operations_by_service[name] = []

        for path, path_item in self.spec.get("paths", {}).items():
            for method, operation in path_item.items():
                if method not in {"get", "post", "put", "delete", "patch"}:
                    continue
                op_id = operation.get("operationId", f"{method}_{path}")
                tags = operation.get("tags", ["Other"])
                primary_tag = tags[0] if tags else "Other"
                if primary_tag.startswith("For ") or primary_tag == "Schemas":
                    continue

                self.operations[op_id] = {
                    "operation_id": op_id,
                    "method": method.upper(),
                    "path": path,
                    "summary": operation.get("summary", ""),
                    "description": operation.get("description", ""),
                    "parameters": operation.get("parameters", []),
                    "request_body": operation.get("requestBody"),
                    "responses": operation.get("responses", {}),
                    "tags": tags,
                    "service": primary_tag,
                }

                if primary_tag in self.operations_by_service:
                    self.operations_by_service[primary_tag].append(op_id)
                    self.services[primary_tag].operation_count += 1

    def list_services(self) -> list[ServiceInfo]:
        """List all available API services."""
        return sorted(self.services.values(), key=lambda s: s.name)

    def search_operations(
        self,
        query: str,
        service: str | None = None,
        include_infra: bool = False,
        limit: int = 10,
    ) -> list[OperationInfo]:
        """Search operations by keyword with optional service + infra filtering."""
        query_lower = query.lower()
        results: list[tuple[int, dict[str, Any]]] = []
        for op_id, op in self.operations.items():
            svc = op.get("service", "")
            if service and svc.lower() != service.lower():
                continue
            if not include_infra and svc in _INFRA_SERVICES:
                continue
            score = 0
            if query_lower in op_id.lower():
                score += 3
            if query_lower in op["path"].lower():
                score += 2
            if query_lower in op["summary"].lower():
                score += 1
            if query_lower in (op.get("description") or "").lower():
                score += 1
            if score > 0:
                results.append((score, op))

        results.sort(key=lambda x: -x[0])
        return [
            OperationInfo(
                operation_id=op["operation_id"],
                method=op["method"],
                path=op["path"],
                summary=op["summary"],
                service=op.get("service", ""),
            )
            for _, op in results[:limit]
        ]

    def list_operations(self, service: str) -> list[OperationInfo]:
        """List all operations for a service (returns empty list for unknown service)."""
        key = self._find_service_key(service)
        if not key:
            return []
        return [
            OperationInfo(
                operation_id=op_id,
                method=self.operations[op_id]["method"],
                path=self.operations[op_id]["path"],
                summary=self.operations[op_id]["summary"],
                service=key,
            )
            for op_id in self.operations_by_service.get(key, [])
            if op_id in self.operations
        ]

    def get_operation_schema(self, operation_id: str) -> OperationSchema | None:
        """Get full schema for an operation."""
        op = self.operations.get(operation_id)
        if not op:
            return None
        if operation_id in self._schema_cache:
            return OperationSchema(**self._schema_cache[operation_id])
        parameters = self._resolve_refs(op["parameters"])
        request_body = self._resolve_refs(op["request_body"]) if op["request_body"] else None
        schema = OperationSchema(
            operation_id=op["operation_id"],
            method=op["method"],
            path=op["path"],
            summary=op["summary"],
            description=op.get("description"),
            parameters=parameters,
            request_body=request_body,
            responses=op["responses"],
        )
        self._schema_cache[operation_id] = schema.model_dump()
        return schema

    def _resolve_refs(self, obj: Any, depth: int = 0) -> Any:
        """Resolve $ref references in OpenAPI objects (limited depth)."""
        if depth > _MAX_REF_DEPTH:
            return {"$ref": "...truncated for brevity..."}
        if isinstance(obj, dict):
            if "$ref" in obj:
                ref_path = obj["$ref"]
                resolved = self._get_ref(ref_path)
                if resolved:
                    return self._resolve_refs(resolved, depth + 1)
                return obj
            return {k: self._resolve_refs(v, depth) for k, v in obj.items()}
        if isinstance(obj, list):
            return [self._resolve_refs(item, depth) for item in obj]
        return obj

    def _find_service_key(self, service: str) -> str | None:
        """Find the actual service key (case-insensitive)."""
        if service in self.operations_by_service:
            return service
        service_lower = service.lower()
        for key in self.operations_by_service:
            if key.lower() == service_lower:
                return key
        return None

    def _get_ref(self, ref_path: str) -> Any:
        """Get object at $ref path."""
        if not ref_path.startswith("#/"):
            return None
        parts = ref_path[2:].split("/")
        obj = self.spec
        for part in parts:
            if isinstance(obj, dict) and part in obj:
                obj = obj[part]
            else:
                return None
        return obj


# ---------------------------------------------------------------------------
# Server factory
# ---------------------------------------------------------------------------

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def create_server(  # noqa: PLR0913, PLR0917, PLR0915
    spec_path: str | Path | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
    username: str | None = None,
    password: str | None = None,
    provider: ConnectionProvider | None = None,
    policy_file: str | Path | None = None,
) -> FastMCP:
    """Create the Unblu MCP server.

    Args:
        spec_path: Path to swagger.json. Defaults to package-bundled swagger.json.
        base_url: Unblu API base URL. Defaults to UNBLU_BASE_URL env var.
        api_key: API key for authentication. Defaults to UNBLU_API_KEY env var.
        username: Username for basic auth. Defaults to UNBLU_USERNAME env var.
        password: Password for basic auth. Defaults to UNBLU_PASSWORD env var.
        provider: Optional connection provider (e.g. K8s port-forward).
        policy_file: Optional Eunomia policy JSON for authorization.
    """
    from unblu_mcp._internal.providers import DefaultConnectionProvider  # noqa: PLC0415

    if provider is None:
        provider = DefaultConnectionProvider(
            base_url=base_url,
            api_key=api_key,
            username=username,
            password=password,
        )

    @asynccontextmanager
    async def lifespan(_mcp: FastMCP) -> AsyncIterator[None]:
        await provider.setup()
        try:
            yield
        finally:
            await provider.teardown()

    config = provider.get_config()

    # Load OpenAPI spec
    if spec_path is None:
        try:
            spec_file = importlib.resources.files("unblu_mcp").joinpath("swagger.json")
            spec_content = spec_file.read_text(encoding="utf-8")
            spec = json.loads(spec_content)
        except FileNotFoundError, TypeError:
            candidates = [Path.cwd() / "swagger.json"]
            for candidate in candidates:
                if candidate.exists():
                    with Path(candidate).open(encoding="utf-8") as f:
                        spec = json.load(f)
                    break
            else:
                msg = "swagger.json not found. Please provide spec_path."
                raise FileNotFoundError(msg)
    else:
        with Path(spec_path).open(encoding="utf-8") as f:
            spec = json.load(f)

    registry = UnbluAPIRegistry(spec)

    client = httpx.AsyncClient(
        base_url=config.base_url,
        headers=config.headers,
        auth=config.auth,
        timeout=config.timeout,
    )

    mcp = FastMCP(
        name="unblu-mcp",
        lifespan=lifespan,
        mask_error_details=True,
        instructions="""Unblu MCP Server — Debugging-Optimised API Access

Primary use: find conversations, inspect participants, verify user/bot/agent state, audit activity.

## Quick start
1. get_current_account()          — confirm which Unblu account you're connected to
2. search_conversations(status=)  — list/filter conversations
3. get_conversation(id)           — full details of a single conversation
4. search_persons(person_type=)   — find agents, visitors, bots
5. get_person(identifier)         — lookup by UUID, email, or display name
6. check_agent_availability()     — see who is online

## Discover other operations
- find_operation(query)           — search all 300+ API ops by keyword; returns schema inline
- execute_operation(operation_id) — run any op with path/query/body params

## Resources (read without a tool call)
- api://services                  — full service catalog
- api://operations/{operation_id} — full schema for any operation
""",
    )

    # ------------------------------------------------------------------
    # Middleware
    # ------------------------------------------------------------------
    mcp.add_middleware(
        ResponseCachingMiddleware(
            call_tool_settings=CallToolSettings(
                included_tools=["find_operation"],
            ),
        )
    )
    mcp.add_middleware(ErrorHandlingMiddleware())
    mcp.add_middleware(
        LoggingMiddleware(
            include_payloads=True,
            max_payload_length=1000,
        )
    )

    if policy_file is not None:
        try:
            from eunomia_mcp import create_eunomia_middleware  # noqa: PLC0415

            policy_path = Path(policy_file) if isinstance(policy_file, str) else policy_file
            if not policy_path.exists():
                msg = f"Policy file not found: {policy_path}"
                raise FileNotFoundError(msg)
            mcp.add_middleware(create_eunomia_middleware(policy_file=str(policy_path)))
        except ImportError as e:
            msg = "eunomia-mcp is required for policy-based authorization. Install with: pip install unblu-mcp[safety]"
            raise ImportError(msg) from e

    # ------------------------------------------------------------------
    # Resources
    # ------------------------------------------------------------------

    @mcp.resource(
        "api://services",
        name="Unblu API Service Catalog",
        description=("Full catalog of all Unblu API services with name, description, operation count, and tier (curated/long-tail/infra)."),
        mime_type="application/json",
    )
    def services_catalog() -> str:
        return json.dumps([s.model_dump() for s in registry.list_services()], indent=2)

    @mcp.resource(
        "api://operations/{operation_id}",
        name="Unblu API Operation Schema",
        description=("Full resolved schema for any Unblu API operation: method, path, parameters, request body, and response shapes."),
        mime_type="application/json",
    )
    def operation_schema_resource(operation_id: str) -> str:
        schema = registry.get_operation_schema(operation_id)
        if not schema:
            return json.dumps({"error": f"Operation '{operation_id}' not found."})
        return json.dumps(schema.model_dump(), indent=2)

    # ------------------------------------------------------------------
    # Tool helpers
    # ------------------------------------------------------------------

    async def _ctx_log(ctx: Context, message: str) -> None:
        """Log to context; silently no-ops when no MCP session is established."""
        with contextlib.suppress(RuntimeError):
            await ctx.info(message)

    async def _request(
        method: str,
        path: str,
        query_params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
    ) -> tuple[int, Any]:
        """Send an HTTP request and return (status_code, parsed_body)."""
        await provider.ensure_connection()
        try:
            response = await client.request(
                method=method,
                url=path,
                params=query_params,
                json=body or None,
            )
        except httpx.RequestError as e:
            msg = f"API request failed: {e!s}"
            raise ToolError(msg) from e

        if response.status_code == _HTTP_NO_CONTENT:
            return _HTTP_NO_CONTENT, {}

        try:
            data = response.json()
        except Exception:
            data = {"raw": response.text[:500]}

        return response.status_code, data

    def _truncate(data: Any, max_chars: int = _DEFAULT_TRUNCATE_CHARS) -> tuple[Any, bool]:
        """Truncate a response to max_chars of JSON. Returns (data, was_truncated)."""
        serialised = json.dumps(data, separators=(",", ":"))
        if len(serialised) <= max_chars:
            return data, False
        if isinstance(data, dict):
            return {"_truncated": True, "_keys": list(data.keys())[:20]}, True
        if isinstance(data, list):
            return {"_truncated": True, "_count": len(data), "_first_3": data[:3]}, True
        return {"_truncated": True}, True

    def _filter_fields(data: Any, fields: list[str]) -> Any:
        """Filter response data to include only specified dot-notation field paths."""
        if not fields or not isinstance(data, dict):
            return data
        result: dict[str, Any] = {}
        for field_path in fields:
            parts = field_path.split(".")
            current = data
            current_result = result
            for i, part in enumerate(parts):
                if isinstance(current, dict) and part in current:
                    if i == len(parts) - 1:
                        current_result[part] = current[part]
                    else:
                        if part not in current_result:
                            current_result[part] = {}
                        current_result = current_result[part]
                        current = current[part]
                else:
                    break
        return result

    # ------------------------------------------------------------------
    # Tool 1 — find_operation
    # ------------------------------------------------------------------

    @mcp.tool(
        annotations={
            "title": "Find API Operation",
            "readOnlyHint": True,
            "openWorldHint": False,
        },
    )
    async def find_operation(  # noqa: PLR0913, PLR0917
        ctx: Context,
        query: str,
        service: str | None = None,
        include_schema: bool = True,
        include_infra: bool = False,
        limit: int = 10,
    ) -> OperationSearchResult:
        """Search Unblu API operations by keyword and return their schemas.

        Replaces list_services(), list_operations(), search_operations(), and
        get_operation_schema() — one call is enough for debugging.

        Args:
            query: Keyword to search — matches operation IDs, paths, summaries,
                   and descriptions. Examples: "conversation", "search agents",
                   "create user", "bot message", "audit".
            service: Optional service name to restrict the search (e.g. "Conversations",
                     "Persons", "Users"). Read api://services for the full list.
            include_schema: When True (default), embeds the full resolved schema
                            (parameters, request body) in each match so you can
                            call execute_operation() without a separate lookup.
            include_infra: When True, includes infrastructure/security-sensitive
                           services (WebhookRegistrations, ApiKeys, Authenticator,
                           etc.) that are hidden by default.
            limit: Maximum number of results to return (default 10).

        Returns:
            Ranked matching operations with schema_resource URIs. Call
            execute_operation(operation_id=...) to run any of them.
        """
        await _ctx_log(ctx, f"Searching {len(registry.operations)} operations for '{query}'")
        matches_info = registry.search_operations(
            query=query,
            service=service,
            include_infra=include_infra,
            limit=limit,
        )

        matches: list[OperationMatch] = []
        for info in matches_info:
            schema_data: dict[str, Any] | None = None
            if include_schema:
                full = registry.get_operation_schema(info.operation_id)
                if full:
                    schema_data = full.model_dump()
            matches.append(
                OperationMatch(
                    operation_id=info.operation_id,
                    method=info.method,
                    path=info.path,
                    summary=info.summary,
                    service=info.service,
                    schema_resource=f"api://operations/{info.operation_id}",
                    full_schema=schema_data,
                )
            )

        next_steps = [
            "Call execute_operation(operation_id='<id>') to run any matched operation.",
            "Read api://services to browse all available service categories.",
        ]
        if not matches:
            next_steps.insert(0, f"No results for '{query}'. Try a broader term or set include_infra=True.")
        return OperationSearchResult(
            matches=matches,
            total_searched=len(registry.operations),
            next_steps=next_steps,
        )

    # ------------------------------------------------------------------
    # Tool 2 — execute_operation  (improved call_api escape hatch)
    # ------------------------------------------------------------------

    @mcp.tool(
        annotations={
            "title": "Execute API Operation",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
            "openWorldHint": True,
        },
    )
    async def execute_operation(  # noqa: PLR0913, PLR0917, PLR0912
        ctx: Context,
        operation_id: str,
        path_params: dict[str, str] | None = None,
        query_params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
        fields: list[str] | None = None,
        offset: int | None = None,
        limit: int | None = None,
        confirm_destructive: bool = False,
        max_response_size: int | None = None,
    ) -> ExecuteResult:
        """Execute any Unblu API operation by its operation_id.

        Use find_operation(query) first to discover operation_ids and their
        required parameters. This is the escape hatch for the 300+ operations
        that do not have dedicated curated tools.

        Args:
            operation_id: The operation to run (e.g. "conversationsRead").
                          Use find_operation() to discover valid operation IDs.
            path_params: Path parameters as a dict (e.g. {"conversationId": "abc"}).
                         Required when the path contains placeholders.
            query_params: Query string parameters as a dict.
            body: JSON request body for POST/PUT/PATCH operations.
            fields: Optional list of dot-notation field paths to include in the
                    response (e.g. ["id", "topic", "participants.personId"]).
                    Use to reduce response size for large payloads.
            offset: Page offset for paginated operations. Auto-merged into body
                    for POST search endpoints.
            limit: Page size for paginated operations. Auto-merged into body
                   for POST search endpoints.
            confirm_destructive: Must be True for destructive operations (DELETE).
                                 This is a safety gate — the error message will tell you
                                 exactly what will be deleted before you confirm.
            max_response_size: Optional maximum size of the response in characters.
                               If the response exceeds this size, it will be truncated.

        Returns:
            status_code, data (shaped by fields if provided), has_more, next_offset,
            and next_steps hints.
        """
        op = registry.operations.get(operation_id)
        if not op:
            msg = f"Operation '{operation_id}' not found. Call find_operation(query='...') to search for valid operation IDs."
            raise ToolError(msg)

        await _ctx_log(ctx, f"Executing {op['method']} {op['path']}")

        # Build URL with path parameters (validate before destructive check)
        path = op["path"]
        if path_params:
            for key, value in path_params.items():
                path = path.replace(f"{{{key}}}", str(value))

        if "{" in path:
            missing = re.findall(r"\{(\w+)\}", path)[:3]
            msg = (
                f"Missing required path parameters: {missing}. "
                f"Call find_operation(query='{operation_id}', include_schema=True) "
                "to see all required parameters."
            )
            raise ToolError(msg)

        # Safety gate for destructive operations
        if op["method"] == "DELETE" and not confirm_destructive:
            msg = (
                f"Operation '{operation_id}' is a DELETE ({op['path']}). "
                "This will permanently remove data. "
                "Call again with confirm_destructive=True to proceed."
            )
            raise ToolError(msg)

        # Merge offset/limit into body for POST search-style operations
        method = op["method"]
        request_body = dict(body or {})
        if (offset is not None or limit is not None) and method in {"POST", "PUT", "PATCH"}:
            if offset is not None:
                request_body["offset"] = offset
            if limit is not None:
                request_body["limit"] = limit
        effective_body = request_body or None

        # For GET operations, merge offset/limit into query params
        effective_query = dict(query_params or {})
        if (offset is not None or limit is not None) and method == "GET":
            if offset is not None:
                effective_query["offset"] = offset
            if limit is not None:
                effective_query["limit"] = limit

        status_code, data = await _request(
            method=method,
            path=path,
            query_params=effective_query or None,
            body=effective_body,
        )

        # Apply field filtering
        if fields and isinstance(data, dict):
            data = _filter_fields(data, fields)

        # Parse pagination from response
        has_more: bool | None = None
        next_offset_val: int | None = None
        if isinstance(data, dict) and "hasMoreItems" in data:
            has_more, next_offset_val = parse_pagination(data)
            # Unwrap items for cleaner response
            if "items" in data:
                items_data = data.get("items", [])
                data = {"items": items_data, "total_in_page": len(items_data)}

        # Truncate large responses
        data, truncated = _truncate(
            data,
            max_chars=max_response_size if max_response_size is not None else _DEFAULT_TRUNCATE_CHARS,
        )

        next_steps: list[str] = []
        if has_more and next_offset_val is not None:
            next_steps.append(f"Call execute_operation('{operation_id}', offset={next_offset_val}) for the next page.")
        if status_code >= _HTTP_CLIENT_ERROR:
            next_steps.append(
                f"Request failed (HTTP {status_code}). "
                f"Call find_operation('{operation_id}', include_schema=True) to verify required parameters."
            )

        return ExecuteResult(
            status_code=status_code,
            data=data,
            has_more=has_more,
            next_offset=next_offset_val,
            truncated=truncated,
            next_steps=next_steps,
        )

    # ------------------------------------------------------------------
    # Tool 3 — get_current_account
    # ------------------------------------------------------------------

    @mcp.tool(
        annotations={
            "title": "Get Current Account",
            "readOnlyHint": True,
            "openWorldHint": False,
        },
    )
    async def get_current_account(
        ctx: Context,
    ) -> AccountInfo:
        """Get information about the Unblu account you are connected to.

        Always a good first call to confirm connectivity and identify the account.

        Returns:
            Account id, name, and next_steps pointing to other useful tools.
        """
        await _ctx_log(ctx, "Fetching current account info")
        status_code, data = await _request("GET", "/accounts/getCurrentAccount")
        if status_code >= _HTTP_CLIENT_ERROR:
            msg = f"Failed to get current account (HTTP {status_code}). Verify UNBLU_BASE_URL, UNBLU_API_KEY, or UNBLU_USERNAME/PASSWORD."
            raise ToolError(msg)
        return AccountInfo(
            id=data.get("id", ""),
            name=data.get("name") or data.get("displayName"),
        )

    # ------------------------------------------------------------------
    # Tool 4 — search_conversations
    # ------------------------------------------------------------------

    @mcp.tool(
        annotations={
            "title": "Search Conversations",
            "readOnlyHint": True,
            "openWorldHint": False,
        },
    )
    async def search_conversations(  # noqa: PLR0913, PLR0917
        ctx: Context,
        status: Literal["CREATED", "ONBOARDING", "REBOARDING", "QUEUED", "ACTIVE", "UNASSIGNED", "OFFBOARDING", "ENDED"] | None = None,
        assignee_person_id: str | None = None,
        topic: str | None = None,
        offset: int = 0,
        limit: int = 25,
    ) -> ConversationPage:
        """Search and list Unblu conversations with optional filters.

        Args:
            status: Filter by conversation state. Common values: ACTIVE (agent is
                    engaged), QUEUED (waiting for agent), ENDED (completed).
                    ONBOARDING/OFFBOARDING are transition states.
            assignee_person_id: Filter by assigned agent person ID (UUID).
                                 Use search_persons(person_type="AGENT") to find IDs.
            topic: Filter by topic text (case-insensitive contains match).
            offset: Page offset for pagination (default 0).
            limit: Number of conversations to return (default 25, max ~100).

        Returns:
            Paginated list of conversations with id, topic, status, timestamps,
            participant count, and pagination info.
        """
        await _ctx_log(ctx, f"Searching conversations (status={status}, offset={offset})")

        search_filters: list[dict[str, Any]] = []

        if status:
            search_filters.append({
                "$_type": "ConversationStateSearchFilter",
                "field": "STATE",
                "operator": {
                    "$_type": "EConversationStateOperator",
                    "type": "EQUALS",
                    "value": status,
                },
            })

        if assignee_person_id:
            search_filters.append({
                "$_type": "AssigneePersonIdConversationSearchFilter",
                "field": "ASSIGNEE_PERSON_ID",
                "operator": {
                    "$_type": "IdOperator",
                    "type": "EQUALS",
                    "value": assignee_person_id,
                },
            })

        if topic:
            search_filters.append({
                "$_type": "TopicConversationSearchFilter",
                "field": "TOPIC",
                "operator": {
                    "$_type": "StringOperator",
                    "type": "CONTAINS",
                    "value": topic,
                },
            })

        body = build_query_body(
            offset=offset,
            limit=limit,
            search_filters=search_filters or None,
            query_type="ConversationQuery",
        )

        status_code, data = await _request("POST", "/conversations/search", body=body)
        if status_code >= _HTTP_CLIENT_ERROR:
            msg = f"Conversation search failed (HTTP {status_code}): {str(data)[:200]}"
            raise ToolError(msg)

        has_more, next_offset_val = parse_pagination(data)
        raw_items: list[dict[str, Any]] = data.get("items", [])

        items = [
            ConversationSummary(
                id=c.get("id", ""),
                topic=c.get("topic"),
                state=c.get("state", ""),
                created_at=c.get("creationTimestamp"),
                ended_at=c.get("endTimestamp"),
                awaited_person_type=c.get("awaitedPersonType"),
                participant_count=len(c.get("participants", [])),
                bot_participant_count=len(c.get("botParticipants", [])),
                source_url=c.get("sourceUrl"),
            )
            for c in raw_items
        ]

        next_steps = ["Call get_conversation(conversation_id='<id>') for full details."]
        if has_more:
            next_steps.append(f"Call search_conversations(offset={next_offset_val}) to get the next page.")

        return ConversationPage(
            items=items,
            has_more=has_more,
            next_offset=next_offset_val,
            next_steps=next_steps,
        )

    # ------------------------------------------------------------------
    # Tool 5 — get_conversation
    # ------------------------------------------------------------------

    @mcp.tool(
        annotations={
            "title": "Get Conversation",
            "readOnlyHint": True,
            "openWorldHint": False,
        },
    )
    async def get_conversation(
        ctx: Context,
        conversation_id: str,
    ) -> ConversationDetail:
        """Get full details of a specific conversation for debugging.

        Args:
            conversation_id: UUID of the conversation. Use search_conversations()
                             to find valid IDs.

        Returns:
            Full conversation details: state, timestamps, participants list
            (person IDs and types), source URL, metadata, and suggested next steps.
            Note: raw configuration and text blobs are excluded to reduce noise.
        """
        await _ctx_log(ctx, f"Fetching conversation {conversation_id}")
        status_code, data = await _request("GET", f"/conversations/{conversation_id}")
        if status_code == _HTTP_NOT_FOUND:
            msg = f"Conversation '{conversation_id}' not found. Call search_conversations() to find valid IDs."
            raise ToolError(msg)
        if status_code >= _HTTP_CLIENT_ERROR:
            msg = f"Failed to get conversation (HTTP {status_code}): {str(data)[:200]}"
            raise ToolError(msg)

        participants = [
            ConversationParticipant(
                person_id=p.get("personId", ""),
                participation_type=p.get("participationType"),
                state=p.get("state"),
                hidden=p.get("hidden", False),
            )
            for p in data.get("participants", [])
        ]

        return ConversationDetail(
            id=data.get("id", ""),
            topic=data.get("topic"),
            state=data.get("state", ""),
            created_at=data.get("creationTimestamp"),
            ended_at=data.get("endTimestamp"),
            visibility=data.get("conversationVisibility"),
            locale=data.get("locale"),
            awaited_person_type=data.get("awaitedPersonType"),
            source_url=data.get("sourceUrl"),
            source_id=data.get("sourceId"),
            initial_engagement_type=data.get("initialEngagementType"),
            end_reason=data.get("endReason"),
            participants=participants,
            bot_participant_count=len(data.get("botParticipants", [])),
            metadata=data.get("metadata"),
            next_steps=[
                "Call get_person(identifier='<personId>') to inspect any participant.",
                "Call assign_conversation(conversation_id, assignee_person_id) to reassign.",
                "Call end_conversation(conversation_id) to close this conversation.",
                "Call search_conversations() to list other conversations.",
            ],
        )

    # ------------------------------------------------------------------
    # Tool 6 — assign_conversation
    # ------------------------------------------------------------------

    @mcp.tool(
        annotations={
            "title": "Assign Conversation",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def assign_conversation(
        ctx: Context,
        conversation_id: str,
        assignee_person_id: str,
    ) -> OperationResult:
        """Assign a conversation to a specific agent person.

        Useful during debugging to test assignment logic or reassign
        conversations for investigation purposes.

        Args:
            conversation_id: UUID of the conversation to reassign.
            assignee_person_id: UUID of the agent person to assign to.
                                Use search_persons(person_type="AGENT") to find valid IDs.

        Returns:
            Success status and confirmation message.
        """
        await _ctx_log(ctx, f"Assigning conversation {conversation_id} to {assignee_person_id}")
        status_code, data = await _request(
            "POST",
            f"/conversations/{conversation_id}/setAssigneePerson",
            body={"personId": assignee_person_id},
        )
        if status_code >= _HTTP_CLIENT_ERROR:
            msg = (
                f"Failed to assign conversation (HTTP {status_code}): {str(data)[:200]}. "
                "Verify conversation_id with get_conversation() and "
                "assignee_person_id with search_persons(person_type='AGENT')."
            )
            raise ToolError(msg)
        return OperationResult(
            success=True,
            message=f"Conversation {conversation_id} assigned to {assignee_person_id}.",
            conversation_id=conversation_id,
            next_steps=[
                f"Call get_conversation('{conversation_id}') to verify the new assignment.",
            ],
        )

    # ------------------------------------------------------------------
    # Tool 7 — end_conversation
    # ------------------------------------------------------------------

    @mcp.tool(
        annotations={
            "title": "End Conversation",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    )
    async def end_conversation(
        ctx: Context,
        conversation_id: str,
    ) -> OperationResult:
        """End (close) a conversation. This action is irreversible.

        Useful during debugging to clean up test conversations.
        The conversation transitions to ENDED state.

        Args:
            conversation_id: UUID of the conversation to end.
                             Use search_conversations() to find valid IDs.

        Returns:
            Success status and confirmation message.
        """
        await _ctx_log(ctx, f"Ending conversation {conversation_id}")
        status_code, data = await _request(
            "POST",
            f"/conversations/{conversation_id}/end",
            body={"$_type": "ConversationsEndBody"},
        )
        if status_code >= _HTTP_CLIENT_ERROR:
            msg = (
                f"Failed to end conversation (HTTP {status_code}): {str(data)[:200]}. "
                "Verify the conversation exists and is not already ended "
                f"with get_conversation('{conversation_id}')."
            )
            raise ToolError(msg)
        return OperationResult(
            success=True,
            message=f"Conversation {conversation_id} has been ended.",
            conversation_id=conversation_id,
            next_steps=[
                f"Call get_conversation('{conversation_id}') to verify the ENDED state.",
            ],
        )

    # ------------------------------------------------------------------
    # Tool 8 — search_persons
    # ------------------------------------------------------------------

    @mcp.tool(
        annotations={
            "title": "Search Persons",
            "readOnlyHint": True,
            "openWorldHint": False,
        },
    )
    async def search_persons(
        ctx: Context,
        query: str | None = None,
        person_type: Literal["AGENT", "VISITOR", "BOT", "SYSTEM"] | None = None,
        offset: int = 0,
        limit: int = 25,
    ) -> PersonPage:
        """Search Unblu persons (real-time session participants).

        Persons are the live participants in conversations: agents handling chats,
        visitors initiating conversations, bots, and system users.
        For admin-level Unblu user accounts, use search_users() instead.

        Args:
            query: Free-text search across display name, email, username, first/last name.
            person_type: Filter by type. AGENT = human support agents,
                         VISITOR = end-users/customers, BOT = automated bots,
                         SYSTEM = internal system persons.
            offset: Page offset for pagination (default 0).
            limit: Number of persons to return (default 25).

        Returns:
            Paginated list of persons with id, display_name, type, email, team.
        """
        await _ctx_log(ctx, f"Searching persons (type={person_type}, query={query}, offset={offset})")

        # Choose the most specific endpoint based on person_type
        if person_type == "AGENT":
            endpoint = "/persons/searchAgents"
            query_type = "PersonTypedQuery"
        elif person_type == "BOT":
            endpoint = "/persons/searchBots"
            query_type = "PersonTypedQuery"
        elif person_type == "VISITOR":
            endpoint = "/persons/searchVisitors"
            query_type = "PersonTypedQuery"
        else:
            endpoint = "/persons/search"
            query_type = "PersonQuery"

        search_filters: list[dict[str, Any]] = []

        if query:
            search_filters.append({
                "$_type": "CompoundPersonSearchFilter",
                "field": "COMPOUND",
                "operator": {
                    "$_type": "StringOperator",
                    "type": "CONTAINS",
                    "value": query,
                },
            })

        # Add type filter only when using the generic /persons/search endpoint
        if person_type and endpoint == "/persons/search":
            search_filters.append({
                "$_type": "PersonTypePersonSearchFilter",
                "field": "PERSON_TYPE",
                "operator": {
                    "$_type": "EPersonTypeOperator",
                    "type": "EQUALS",
                    "value": person_type,
                },
            })

        body = build_query_body(
            offset=offset,
            limit=limit,
            search_filters=search_filters or None,
            query_type=query_type,
        )

        status_code, data = await _request("POST", endpoint, body=body)
        if status_code >= _HTTP_CLIENT_ERROR:
            msg = f"Person search failed (HTTP {status_code}): {str(data)[:200]}"
            raise ToolError(msg)

        has_more, next_offset_val = parse_pagination(data)
        raw_items: list[dict[str, Any]] = data.get("items", [])

        items = [
            PersonSummary(
                id=p.get("id", ""),
                display_name=p.get("displayName"),
                person_type=p.get("personType"),
                email=p.get("email"),
                team_id=p.get("teamId"),
                authorization_role=p.get("authorizationRole"),
            )
            for p in raw_items
        ]

        next_steps = ["Call get_person(identifier='<id>') for full person details."]
        if has_more:
            next_steps.append(f"Call search_persons(offset={next_offset_val}) to get the next page.")

        return PersonPage(
            items=items,
            has_more=has_more,
            next_offset=next_offset_val,
            next_steps=next_steps,
        )

    # ------------------------------------------------------------------
    # Tool 9 — get_person
    # ------------------------------------------------------------------

    @mcp.tool(
        annotations={
            "title": "Get Person",
            "readOnlyHint": True,
            "openWorldHint": False,
        },
    )
    async def get_person(
        ctx: Context,
        identifier: str,
    ) -> PersonDetail | PersonAmbiguousResult:
        """Get full details of a person by UUID, email, or display name.

        Accepts natural identifiers — you do not need to know the internal UUID:
        - UUID (e.g. "a1b2c3d4-..."):  direct lookup
        - Email (contains "@"):         email search
        - Any other string:             compound text search (name, username, etc.)

        If multiple persons match a name search, returns a list of candidates so
        you can call again with the exact person_id.

        Args:
            identifier: Person UUID, email address, or display name / username.

        Returns:
            PersonDetail with id, type, display_name, email, team, labels, note.
            Or PersonAmbiguousResult if multiple name matches are found.
        """
        await _ctx_log(ctx, f"Looking up person: {identifier}")

        # Strategy 1: UUID direct lookup
        if _UUID_RE.match(identifier):
            status_code, data = await _request("GET", f"/persons/{identifier}")
            if status_code == _HTTP_NOT_FOUND:
                msg = f"Person '{identifier}' not found. Call search_persons() to browse available persons."
                raise ToolError(msg)
            if status_code >= _HTTP_CLIENT_ERROR:
                msg = f"Failed to fetch person (HTTP {status_code}): {str(data)[:200]}"
                raise ToolError(msg)
            return _person_detail(data)

        # Strategy 2: Email search
        if "@" in identifier:
            body = build_query_body(
                offset=0,
                limit=5,
                search_filters=[
                    {
                        "$_type": "EmailPersonSearchFilter",
                        "field": "EMAIL",
                        "operator": {
                            "$_type": "StringOperator",
                            "type": "EQUALS",
                            "value": identifier,
                        },
                    }
                ],
                query_type="PersonQuery",
            )
            status_code, data = await _request("POST", "/persons/search", body=body)
            items: list[dict[str, Any]] = data.get("items", []) if status_code < _HTTP_CLIENT_ERROR else []
            if len(items) == 1:
                return _person_detail(items[0])
            if len(items) > 1:
                return PersonAmbiguousResult(
                    candidates=[
                        PersonSummary(
                            id=p.get("id", ""),
                            display_name=p.get("displayName"),
                            person_type=p.get("personType"),
                            email=p.get("email"),
                            team_id=p.get("teamId"),
                        )
                        for p in items
                    ],
                    next_steps=["Call get_person(identifier='<person_id>') with the exact UUID."],
                )
            msg = f"No person found with email '{identifier}'. Call search_persons() to browse available persons."
            raise ToolError(msg)

        # Strategy 3: Compound text search (name, username, etc.)
        body = build_query_body(
            offset=0,
            limit=10,
            search_filters=[
                {
                    "$_type": "CompoundPersonSearchFilter",
                    "field": "COMPOUND",
                    "operator": {
                        "$_type": "StringOperator",
                        "type": "CONTAINS",
                        "value": identifier,
                    },
                }
            ],
            query_type="PersonQuery",
        )
        status_code, data = await _request("POST", "/persons/search", body=body)
        items = data.get("items", []) if status_code < _HTTP_CLIENT_ERROR else []

        if len(items) == 1:
            return _person_detail(items[0])
        if len(items) > 1:
            return PersonAmbiguousResult(
                candidates=[
                    PersonSummary(
                        id=p.get("id", ""),
                        display_name=p.get("displayName"),
                        person_type=p.get("personType"),
                        email=p.get("email"),
                        team_id=p.get("teamId"),
                    )
                    for p in items
                ],
                next_steps=["Call get_person(identifier='<person_id>') with the exact UUID."],
            )
        msg = f"No person found matching '{identifier}'. Try search_persons(query='...') for a broader search."
        raise ToolError(msg)

    def _person_detail(data: dict[str, Any]) -> PersonDetail:
        return PersonDetail(
            id=data.get("id", ""),
            display_name=data.get("displayName"),
            person_type=data.get("personType"),
            email=data.get("email"),
            phone=data.get("phone"),
            username=data.get("username"),
            team_id=data.get("teamId"),
            labels=[str(lbl) for lbl in data.get("labels", [])],
            note=data.get("note"),
            authorization_role=data.get("authorizationRole"),
            source_id=data.get("sourceId"),
            source_url=data.get("sourceUrl"),
            next_steps=[
                "Call search_conversations(assignee_person_id='<id>') to see their conversations.",
                "Call search_persons() to find other persons.",
            ],
        )

    # ------------------------------------------------------------------
    # Tool 10 — search_users
    # ------------------------------------------------------------------

    @mcp.tool(
        annotations={
            "title": "Search Users",
            "readOnlyHint": True,
            "openWorldHint": False,
        },
    )
    async def search_users(
        ctx: Context,
        query: str | None = None,
        offset: int = 0,
        limit: int = 25,
    ) -> UserPage:
        """Search Unblu admin-level user accounts.

        Users are the Unblu administrator/operator accounts (not real-time participants).
        For conversation participants (agents/visitors/bots), use search_persons() instead.

        Args:
            query: Free-text search across username, display name, email.
            offset: Page offset for pagination (default 0).
            limit: Number of users to return (default 25).

        Returns:
            Paginated list of users with id, username, display_name, email, role.
        """
        await _ctx_log(ctx, f"Searching users (query={query}, offset={offset})")

        search_filters: list[dict[str, Any]] = []
        if query:
            search_filters.append({
                "$_type": "CompoundUserSearchFilter",
                "field": "COMPOUND",
                "operator": {
                    "$_type": "StringOperator",
                    "type": "CONTAINS",
                    "value": query,
                },
            })

        body = build_query_body(
            offset=offset,
            limit=limit,
            search_filters=search_filters or None,
            query_type="UserQuery",
        )

        status_code, data = await _request("POST", "/users/search", body=body)
        if status_code >= _HTTP_CLIENT_ERROR:
            msg = f"User search failed (HTTP {status_code}): {str(data)[:200]}"
            raise ToolError(msg)

        has_more, next_offset_val = parse_pagination(data)
        raw_items: list[dict[str, Any]] = data.get("items", [])

        items = [
            UserSummary(
                id=u.get("id", ""),
                username=u.get("username"),
                display_name=u.get("displayName"),
                email=u.get("email"),
                authorization_role=u.get("authorizationRole"),
            )
            for u in raw_items
        ]

        next_steps = ["Call get_user(identifier='<id>') for full user details."]
        if has_more:
            next_steps.append(f"Call search_users(offset={next_offset_val}) to get the next page.")

        return UserPage(
            items=items,
            has_more=has_more,
            next_offset=next_offset_val,
            next_steps=next_steps,
        )

    # ------------------------------------------------------------------
    # Tool 11 — get_user
    # ------------------------------------------------------------------

    @mcp.tool(
        annotations={
            "title": "Get User",
            "readOnlyHint": True,
            "openWorldHint": False,
        },
    )
    async def get_user(
        ctx: Context,
        identifier: str,
    ) -> UserDetail:
        """Get full details of an Unblu user account by UUID, username, or email.

        - UUID (e.g. "a1b2c3d4-..."): direct lookup
        - Username (no "@"):           username lookup
        - Email (contains "@"):        search by email

        For real-time session participants (agents/visitors), use get_person() instead.

        Args:
            identifier: User UUID, username, or email address.

        Returns:
            UserDetail with id, username, display_name, email, role, team.
        """
        await _ctx_log(ctx, f"Looking up user: {identifier}")

        # UUID direct lookup
        if _UUID_RE.match(identifier):
            status_code, data = await _request("GET", f"/users/{identifier}")
            if status_code == _HTTP_NOT_FOUND:
                msg = f"User '{identifier}' not found. Call search_users() to browse available users."
                raise ToolError(msg)
            if status_code >= _HTTP_CLIENT_ERROR:
                msg = f"Failed to fetch user (HTTP {status_code}): {str(data)[:200]}"
                raise ToolError(msg)
            return _user_detail(data)

        # Email → search
        if "@" in identifier:
            body = build_query_body(
                offset=0,
                limit=5,
                search_filters=[
                    {
                        "$_type": "EmailUserSearchFilter",
                        "field": "EMAIL",
                        "operator": {
                            "$_type": "StringOperator",
                            "type": "EQUALS",
                            "value": identifier,
                        },
                    }
                ],
                query_type="UserQuery",
            )
            status_code, data = await _request("POST", "/users/search", body=body)
            items: list[dict[str, Any]] = data.get("items", []) if status_code < _HTTP_CLIENT_ERROR else []
            if items:
                return _user_detail(items[0])
            msg = f"No user found with email '{identifier}'. Call search_users() to browse available users."
            raise ToolError(msg)

        # Username lookup
        status_code, data = await _request("GET", "/users/getByUsername", query_params={"username": identifier})
        if status_code == _HTTP_NOT_FOUND:
            msg = f"No user found with username '{identifier}'. Call search_users(query='{identifier}') to search more broadly."
            raise ToolError(msg)
        if status_code >= _HTTP_CLIENT_ERROR:
            msg = f"Failed to fetch user (HTTP {status_code}): {str(data)[:200]}"
            raise ToolError(msg)
        return _user_detail(data)

    def _user_detail(data: dict[str, Any]) -> UserDetail:
        return UserDetail(
            id=data.get("id", ""),
            username=data.get("username"),
            display_name=data.get("displayName"),
            email=data.get("email"),
            phone=data.get("phone"),
            team_id=data.get("teamId"),
            authorization_role=data.get("authorizationRole"),
            virtual_user=data.get("virtualUser"),
            externally_managed=data.get("externallyManaged"),
            next_steps=[
                "Call search_users() to find other users.",
                "Call search_persons() to find real-time session participants.",
            ],
        )

    # ------------------------------------------------------------------
    # Tool 12 — check_agent_availability
    # ------------------------------------------------------------------

    @mcp.tool(
        annotations={
            "title": "Check Agent Availability",
            "readOnlyHint": True,
            "openWorldHint": False,
        },
    )
    async def check_agent_availability(
        ctx: Context,
        named_area_site_id: str | None = None,
    ) -> AvailabilityInfo:
        """Check agent availability in Unblu — who is online and able to handle conversations.

        Args:
            named_area_site_id: Optional named area / site ID to filter availability
                                by a specific area. Leave empty for account-wide availability.
                                Use find_operation("named areas") to discover named area IDs.

        Returns:
            Availability status and raw availability data from the Unblu API.
        """
        await _ctx_log(ctx, f"Checking agent availability (named_area={named_area_site_id})")
        params: dict[str, Any] = {}
        if named_area_site_id:
            params["namedAreaSiteId"] = named_area_site_id

        status_code, data = await _request("GET", "/availability/getAgentAvailability", query_params=params or None)
        if status_code >= _HTTP_CLIENT_ERROR:
            msg = f"Failed to get agent availability (HTTP {status_code}): {str(data)[:200]}"
            raise ToolError(msg)

        return AvailabilityInfo(
            named_area_site_id=named_area_site_id,
            availability=data.get("agentAvailability") or data.get("availability"),
            raw=data,
            next_steps=[
                "Call search_persons(person_type='AGENT') to list active agents.",
                "Call search_conversations(status='QUEUED') to see waiting conversations.",
            ],
        )

    # ------------------------------------------------------------------
    # Tool 13 — search_named_areas  (bonus: named areas are key for debugging)
    # ------------------------------------------------------------------

    @mcp.tool(
        annotations={
            "title": "Search Named Areas",
            "readOnlyHint": True,
            "openWorldHint": False,
        },
    )
    async def search_named_areas(
        ctx: Context,
        query: str | None = None,
        offset: int = 0,
        limit: int = 25,
    ) -> ExecuteResult:
        """Search Unblu named areas (routing targets for conversations).

        Named areas are the primary way conversations are routed to queues.
        Their IDs are needed for check_agent_availability() and search_conversations().

        Args:
            query: Optional text to filter named areas by name.
            offset: Page offset for pagination (default 0).
            limit: Number of named areas to return (default 25).

        Returns:
            List of named areas with id, name, and site ID.
        """
        await _ctx_log(ctx, f"Searching named areas (query={query}, offset={offset})")
        search_filters: list[dict[str, Any]] = []
        if query:
            search_filters.append({
                "$_type": "NamedAreaSearchFilter",
                "field": "COMPOUND",
                "operator": {
                    "$_type": "StringOperator",
                    "type": "CONTAINS",
                    "value": query,
                },
            })

        body = build_query_body(
            offset=offset,
            limit=limit,
            search_filters=search_filters or None,
            query_type="NamedAreaQuery",
        )

        status_code, data = await _request("POST", "/namedAreas/search", body=body)
        if status_code >= _HTTP_CLIENT_ERROR:
            msg = f"Named area search failed (HTTP {status_code}): {str(data)[:200]}"
            raise ToolError(msg)

        has_more, next_offset_val = parse_pagination(data)
        items = data.get("items", [])
        data_out: dict[str, Any] = {
            "items": [
                {
                    "id": a.get("id"),
                    "name": a.get("name"),
                    "site_id": a.get("siteId"),
                }
                for a in items
            ]
        }

        next_steps: list[str] = [
            "Use the 'id' as named_area_site_id in check_agent_availability().",
        ]
        if has_more:
            next_steps.append(f"Call search_named_areas(offset={next_offset_val}) for the next page.")

        return ExecuteResult(
            status_code=status_code,
            data=data_out,
            has_more=has_more,
            next_offset=next_offset_val,
            next_steps=next_steps,
        )

    # ------------------------------------------------------------------
    # Prompts — debugging workflow fast-paths
    # ------------------------------------------------------------------

    @mcp.prompt()
    def debug_conversation(conversation_id: str) -> str:
        """Step-by-step debugging workflow for a specific conversation."""
        return (
            f"Debug conversation {conversation_id} step by step:\n\n"
            f"1. Call get_conversation(conversation_id='{conversation_id}') to get full details.\n"
            "2. For each participant in the response, call get_person(identifier='<personId>') "
            "to inspect their state, type, labels, and note.\n"
            "3. Check agent availability with check_agent_availability() "
            "to see if agents are online.\n"
            "4. If the conversation state seems wrong (e.g. QUEUED with no agents), "
            "report the issue with the details you found.\n"
            "5. If needed to reset: assign_conversation() to reassign or "
            "end_conversation() to close.\n\n"
            "Summarise: conversation state, assignee, participant types, awaited_person_type, "
            "and any anomalies found."
        )

    @mcp.prompt()
    def find_agent(identifier: str) -> str:
        """Debugging workflow to locate and inspect an agent."""
        return (
            f"Locate and inspect agent '{identifier}':\n\n"
            f"1. Call get_person(identifier='{identifier}') — accepts UUID, email, or name.\n"
            "2. Note the person_type (should be AGENT), team_id, and authorization_role.\n"
            "3. Call search_conversations(assignee_person_id='<id>') to see "
            "their current and recent conversations.\n"
            "4. Call check_agent_availability() to see account-wide agent status.\n\n"
            "Summarise: agent found or not, their state, assigned conversations, "
            "and any anomalies."
        )

    @mcp.prompt()
    def account_health_check() -> str:
        """Debugging workflow for an account-wide health overview."""
        return (
            "Perform an Unblu account health check:\n\n"
            "1. Call get_current_account() — confirm connectivity and account identity.\n"
            "2. Call check_agent_availability() — are agents online?\n"
            "3. Call search_conversations(status='QUEUED', limit=10) "
            "— any conversations waiting without an agent?\n"
            "4. Call search_conversations(status='ACTIVE', limit=10) "
            "— how many active conversations right now?\n"
            "5. If queued conversations exist and availability is low, flag this.\n\n"
            "Summarise: account name, agent availability, queued count, "
            "active count, and any anomalies."
        )

    return mcp


# ---------------------------------------------------------------------------
# Singleton holder (for CLI / test reuse)
# ---------------------------------------------------------------------------


class _ServerHolder:
    """Lazy singleton to avoid re-creating the server on repeated imports."""

    _instance: FastMCP | None = None

    @classmethod
    def get(cls, **kwargs: Any) -> FastMCP:
        if cls._instance is None:
            cls._instance = create_server(**kwargs)
        return cls._instance


def get_server(**kwargs: Any) -> FastMCP:
    """Get (or create) the singleton Unblu MCP server instance."""
    return _ServerHolder.get(**kwargs)
