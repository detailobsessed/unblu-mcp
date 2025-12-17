from __future__ import annotations

import importlib.resources
import json
import re
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.server.middleware.caching import CallToolSettings, ResponseCachingMiddleware
from fastmcp.server.middleware.error_handling import ErrorHandlingMiddleware
from fastmcp.server.middleware.logging import LoggingMiddleware
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from unblu_mcp._internal.providers import ConnectionProvider

# Constants for magic values
_MAX_REF_DEPTH = 3
_HTTP_NO_CONTENT = 204


class ServiceInfo(BaseModel):
    """Information about an API service category."""

    name: str = Field(description="Service name (tag)")
    description: str = Field(description="Service description")
    operation_count: int = Field(description="Number of operations in this service")


class OperationInfo(BaseModel):
    """Brief information about an API operation."""

    operation_id: str = Field(description="Unique operation identifier")
    method: str = Field(description="HTTP method (GET, POST, DELETE, etc.)")
    path: str = Field(description="API path")
    summary: str = Field(description="Brief description of the operation")


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
        # Parse tags (services)
        for tag in self.spec.get("tags", []):
            name = tag.get("name", "")
            # Skip webhook/event schema tags
            if name.startswith("For ") or name == "Schemas":
                continue
            self.services[name] = ServiceInfo(
                name=name,
                description=tag.get("description", "")[:200],  # Truncate long descriptions
                operation_count=0,
            )
            self.operations_by_service[name] = []

        # Parse paths (operations)
        for path, path_item in self.spec.get("paths", {}).items():
            for method, operation in path_item.items():
                if method in ("get", "post", "put", "delete", "patch"):
                    op_id = operation.get("operationId", f"{method}_{path}")
                    tags = operation.get("tags", ["Other"])
                    primary_tag = tags[0] if tags else "Other"

                    # Skip webhook/event operations
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
                    }

                    if primary_tag in self.operations_by_service:
                        self.operations_by_service[primary_tag].append(op_id)
                        self.services[primary_tag].operation_count += 1

    def list_services(self) -> list[ServiceInfo]:
        """List all available API services."""
        return sorted(self.services.values(), key=lambda s: s.name)

    def list_operations(self, service: str) -> list[OperationInfo]:
        """List operations for a specific service."""
        op_ids = self.operations_by_service.get(service, [])
        result = []
        for op_id in op_ids:
            op = self.operations[op_id]
            result.append(
                OperationInfo(
                    operation_id=op["operation_id"],
                    method=op["method"],
                    path=op["path"],
                    summary=op["summary"],
                ),
            )
        return result

    def search_operations(self, query: str, limit: int = 20) -> list[OperationInfo]:
        """Search operations by name, path, or description."""
        query_lower = query.lower()
        results = []
        for op_id, op in self.operations.items():
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
            )
            for _, op in results[:limit]
        ]

    def get_operation_schema(self, operation_id: str) -> OperationSchema | None:
        """Get full schema for an operation."""
        op = self.operations.get(operation_id)
        if not op:
            return None

        # Check cache first
        if operation_id in self._schema_cache:
            cached = self._schema_cache[operation_id]
            return OperationSchema(**cached)

        # Resolve $ref references in parameters and request body
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

        # Cache the resolved schema
        self._schema_cache[operation_id] = schema.model_dump()

        return schema

    def _resolve_refs(self, obj: Any, depth: int = 0) -> Any:
        """Resolve $ref references in OpenAPI objects (limited depth to avoid huge expansions)."""
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


def create_server(
    spec_path: str | Path | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
    username: str | None = None,
    password: str | None = None,
    provider: ConnectionProvider | None = None,
    policy_file: str | Path | None = None,
) -> FastMCP:
    """Create the Unblu MCP server with progressive disclosure tools.

    Args:
        spec_path: Path to swagger.json. Defaults to swagger.json in package root.
        base_url: Unblu API base URL. Defaults to UNBLU_BASE_URL env var.
        api_key: API key for authentication. Defaults to UNBLU_API_KEY env var.
        username: Username for basic auth. Defaults to UNBLU_USERNAME env var.
        password: Password for basic auth. Defaults to UNBLU_PASSWORD env var.
        provider: Optional connection provider for complex connectivity (e.g., K8s port-forward).
                  If provided, overrides base_url/api_key/username/password.
        policy_file: Optional path to Eunomia policy JSON file for authorization.
                     Requires the 'safety' extra: pip install unblu-mcp[safety]

    Returns:
        Configured FastMCP server instance.
    """
    from unblu_mcp._internal.providers import DefaultConnectionProvider  # noqa: PLC0415

    # Use provider if given, otherwise create default provider from args/env
    if provider is None:
        provider = DefaultConnectionProvider(
            base_url=base_url,
            api_key=api_key,
            username=username,
            password=password,
        )

    # Create lifespan context manager to handle provider setup/teardown
    # This is critical for K8s provider which needs to start port-forward on startup
    @asynccontextmanager
    async def lifespan(_mcp: FastMCP) -> AsyncIterator[None]:
        await provider.setup()
        try:
            yield
        finally:
            await provider.teardown()

    # Get connection config from provider
    # Note: For K8s provider, the port may not be available yet until setup() is called
    # but get_config() just returns the expected URL, it doesn't connect
    config = provider.get_config()

    # Load OpenAPI spec
    if spec_path is None:
        # Try to load from package resources first (works when installed from PyPI)
        try:
            spec_file = importlib.resources.files("unblu_mcp").joinpath("swagger.json")
            spec_content = spec_file.read_text(encoding="utf-8")
            spec = json.loads(spec_content)
        except (FileNotFoundError, TypeError):
            # Fall back to file system for development
            candidates = [
                Path.cwd() / "swagger.json",
            ]
            for candidate in candidates:
                if candidate.exists():
                    with open(candidate, encoding="utf-8") as f:
                        spec = json.load(f)
                    break
            else:
                raise FileNotFoundError("swagger.json not found. Please provide spec_path.")
    else:
        with open(spec_path, encoding="utf-8") as f:
            spec = json.load(f)

    registry = UnbluAPIRegistry(spec)

    # Create HTTP client from provider config
    client = httpx.AsyncClient(
        base_url=config.base_url,
        headers=config.headers,
        auth=config.auth,
        timeout=config.timeout,
    )

    # Create FastMCP server with lifespan for provider setup/teardown
    mcp = FastMCP(
        name="unblu-mcp",
        lifespan=lifespan,
        instructions="""Unblu MCP Server - Token-Efficient API Access

This server provides access to 300+ Unblu API endpoints using progressive disclosure
to minimize token usage. Instead of loading all tool definitions upfront, use these
discovery tools to find and execute the operations you need:

1. list_services() - See available API service categories
2. list_operations(service) - See operations in a specific service
3. search_operations(query) - Find operations by keyword
4. get_operation_schema(operation_id) - Get full details for an operation
5. call_api(operation_id, ...) - Execute any API operation

Example workflow:
1. list_services() to see categories like "Conversations", "Users", "Bots"
2. list_operations("Conversations") to see available conversation operations
3. get_operation_schema("conversationsGetById") to see required parameters
4. call_api("conversationsGetById", path_params={"conversationId": "abc123"})
""",
    )

    # Add response caching for discovery tools (static spec data)
    # Cache list_services, list_operations, search_operations, get_operation_schema
    # but NOT call_api (live API data)
    mcp.add_middleware(
        ResponseCachingMiddleware(
            call_tool_settings=CallToolSettings(
                included_tools=[
                    "list_services",
                    "list_operations",
                    "search_operations",
                    "get_operation_schema",
                ],
            ),
        )
    )

    # Add error handling middleware for consistent error logging and tracking
    # This catches exceptions, logs them, and converts to proper MCP error responses
    mcp.add_middleware(ErrorHandlingMiddleware())

    # Add logging middleware for observability
    # Logs tool calls with payloads to help identify usage patterns and errors
    mcp.add_middleware(
        LoggingMiddleware(
            include_payloads=True,
            max_payload_length=1000,
        )
    )

    # Add Eunomia authorization middleware if policy file is provided
    if policy_file is not None:
        try:
            from eunomia_mcp import create_eunomia_middleware  # noqa: PLC0415

            policy_path = Path(policy_file) if isinstance(policy_file, str) else policy_file
            if not policy_path.exists():
                raise FileNotFoundError(f"Policy file not found: {policy_path}")
            middleware = create_eunomia_middleware(policy_file=str(policy_path))
            mcp.add_middleware(middleware)
        except ImportError as e:
            raise ImportError(
                "eunomia-mcp is required for policy-based authorization. Install with: pip install unblu-mcp[safety]"
            ) from e

    @mcp.tool(
        annotations={
            "title": "List API Services",
            "readOnlyHint": True,
            "openWorldHint": False,
        },
    )
    async def list_services() -> list[dict[str, Any]]:
        """List all available Unblu API service categories.

        Returns a list of services (API tags) with their descriptions and
        operation counts. Use this to discover what API capabilities are available.

        Returns:
            List of services with name, description, and operation_count.
        """
        services = registry.list_services()
        return [s.model_dump() for s in services]

    @mcp.tool(
        annotations={
            "title": "List Service Operations",
            "readOnlyHint": True,
            "openWorldHint": False,
        },
    )
    async def list_operations(service: str) -> list[dict[str, Any]]:
        """List all operations available in a specific service.

        Args:
            service: Service name (e.g., "Conversations", "Users", "Bots").
                    Use list_services() to see available services.

        Returns:
            List of operations with operation_id, method, path, and summary.
        """
        operations = registry.list_operations(service)
        if not operations:
            available = [s.name for s in registry.list_services()][:5]
            raise ToolError(f"Service '{service}' not found. Available services include: {available}")
        return [op.model_dump() for op in operations]

    @mcp.tool(
        annotations={
            "title": "Search Operations",
            "readOnlyHint": True,
            "openWorldHint": False,
        },
    )
    async def search_operations(query: str, limit: int = 20) -> list[dict[str, Any]]:
        """Search for API operations by keyword.

        Searches operation IDs, paths, summaries, and descriptions.

        Args:
            query: Search term (e.g., "conversation", "create user", "bot").
            limit: Maximum number of results to return (default 20).

        Returns:
            List of matching operations with operation_id, method, path, and summary.
        """
        operations = registry.search_operations(query, limit)
        return [op.model_dump() for op in operations]

    @mcp.tool(
        annotations={
            "title": "Get Operation Schema",
            "readOnlyHint": True,
            "openWorldHint": False,
        },
    )
    async def get_operation_schema(operation_id: str) -> dict[str, Any]:
        """Get the full schema for a specific API operation.

        Use this to understand the required parameters and request body
        before calling an operation.

        Args:
            operation_id: The operation ID (e.g., "conversationsGetById").
                         Use list_operations() or search_operations() to find IDs.

        Returns:
            Full operation schema including parameters, request body, and responses.
        """
        schema = registry.get_operation_schema(operation_id)
        if not schema:
            raise ToolError(
                f"Operation '{operation_id}' not found. Use search_operations() to find valid operation IDs."
            )
        return schema.model_dump()

    @mcp.tool(
        annotations={
            "title": "Execute API Call",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
            "openWorldHint": True,
        },
    )
    async def call_api(
        operation_id: str,
        path_params: dict[str, str] | None = None,
        query_params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        fields: list[str] | None = None,
        max_response_size: int | None = None,
    ) -> dict[str, Any]:
        """Execute an Unblu API operation.

        Args:
            operation_id: The operation ID to execute.
            path_params: Path parameters (e.g., {"conversationId": "abc123"}).
            query_params: Query string parameters.
            body: Request body for POST/PUT/PATCH operations.
            headers: Additional headers to include.
            fields: Optional list of field paths to include in response (e.g., ["id", "name", "items.id"]).
            max_response_size: Maximum response size in bytes (approximate). Responses exceeding this
                             will be truncated and marked as truncated.

        Returns:
            API response as JSON, or error details if the request failed.
        """
        op = registry.operations.get(operation_id)
        if not op:
            raise ToolError(
                f"Operation '{operation_id}' not found. Use search_operations() to find valid operation IDs."
            )

        def _filter_fields(data: Any, fields: list[str]) -> Any:
            """Filter response data to include only specified field paths.

            Args:
                data: The response data to filter
                fields: List of field paths (e.g., ["id", "name", "items.id"])

            Returns:
                Filtered data with only the requested fields
            """
            if not fields or not isinstance(data, dict):
                return data

            result = {}
            for field_path in fields:
                parts = field_path.split(".")
                current = data
                current_result = result

                # Navigate through the path
                for i, part in enumerate(parts):
                    if isinstance(current, dict) and part in current:
                        if i == len(parts) - 1:
                            # Last part - include the value
                            current_result[part] = current[part]
                        else:
                            # Intermediate part - ensure dict exists
                            if part not in current_result:
                                current_result[part] = {}
                            current_result = current_result[part]
                            current = current[part]
                    else:
                        # Path doesn't exist - skip
                        break

            return result

        # Build URL with path parameters
        path = op["path"]
        if path_params:
            for key, value in path_params.items():
                path = path.replace(f"{{{key}}}", str(value))

        # Check for unresolved path parameters
        if "{" in path:
            missing = re.findall(r"\{(\w+)\}", path)[:3]
            raise ToolError(
                f"Missing required path parameters: {missing}. Use get_operation_schema() to see required parameters."
            )

        # Build request
        method = op["method"].lower()
        request_headers = dict(headers or {})

        try:
            response = await client.request(
                method=method,
                url=path,
                params=query_params,
                json=body if body else None,
                headers=request_headers,
            )

            # Parse response
            if response.status_code == _HTTP_NO_CONTENT:
                return {"status": "success", "status_code": _HTTP_NO_CONTENT}

            try:
                raw_text = response.text
                data = json.loads(raw_text)
            except json.JSONDecodeError:
                data = {"raw": response.text[:200]}

            # Apply field filtering if requested
            if fields and response.is_success and isinstance(data, dict):
                data = _filter_fields(data, fields)

            # Check response size and truncate if necessary
            if max_response_size and response.is_success:
                response_str = json.dumps(data, separators=(",", ":"))
                if len(response_str.encode("utf-8")) > max_response_size:
                    # Truncate to fit within limit
                    truncated_data = {
                        "_truncated": True,
                        "_size": len(response_str.encode("utf-8")),
                        "_limit": max_response_size,
                        "data": None,
                    }

                    # Try to include a summary or first few items
                    if isinstance(data, dict):
                        truncated_data["data"] = {"keys": list(data.keys())[:10]}
                    elif isinstance(data, list):
                        truncated_data["data"] = {"count": len(data), "first_items": data[:3] if data else []}

                    data = truncated_data

            if response.is_success:
                return {"status": "success", "status_code": response.status_code, "data": data}
            return {
                "status": "error",
                "code": response.status_code,
                "error": str(data)[:300] if data else "Unknown error",
            }

        except httpx.RequestError as e:
            raise ToolError(f"API request failed: {e!s}") from e

    return mcp


class _ServerHolder:
    """Holder for global server instance to avoid global statement."""

    instance: FastMCP | None = None


def get_server() -> FastMCP:
    """Get or create the global server instance."""
    if _ServerHolder.instance is None:
        _ServerHolder.instance = create_server()
    return _ServerHolder.instance
