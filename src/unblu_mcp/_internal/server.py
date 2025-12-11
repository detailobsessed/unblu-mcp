from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

import httpx
from fastmcp import FastMCP
from pydantic import BaseModel, Field

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

        # Resolve $ref references in parameters and request body
        parameters = self._resolve_refs(op["parameters"])
        request_body = self._resolve_refs(op["request_body"]) if op["request_body"] else None

        return OperationSchema(
            operation_id=op["operation_id"],
            method=op["method"],
            path=op["path"],
            summary=op["summary"],
            description=op.get("description"),
            parameters=parameters,
            request_body=request_body,
            responses=op["responses"],
        )

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
) -> FastMCP:
    """Create the Unblu MCP server with progressive disclosure tools.

    Args:
        spec_path: Path to swagger.json. Defaults to swagger.json in package root.
        base_url: Unblu API base URL. Defaults to UNBLU_BASE_URL env var.
        api_key: API key for authentication. Defaults to UNBLU_API_KEY env var.
        username: Username for basic auth. Defaults to UNBLU_USERNAME env var.
        password: Password for basic auth. Defaults to UNBLU_PASSWORD env var.

    Returns:
        Configured FastMCP server instance.
    """
    # Load configuration from environment
    base_url = base_url or os.environ.get("UNBLU_BASE_URL", "https://unblu.cloud/app/rest/v4")
    api_key = api_key or os.environ.get("UNBLU_API_KEY")
    username = username or os.environ.get("UNBLU_USERNAME")
    password = password or os.environ.get("UNBLU_PASSWORD")

    # Load OpenAPI spec
    if spec_path is None:
        # Look for swagger.json in common locations
        candidates = [
            Path(__file__).parent.parent.parent.parent.parent / "swagger.json",
            Path.cwd() / "swagger.json",
        ]
        for candidate in candidates:
            if candidate.exists():
                spec_path = candidate
                break
        else:
            raise FileNotFoundError("swagger.json not found. Please provide spec_path.")

    with open(spec_path) as f:
        spec = json.load(f)

    registry = UnbluAPIRegistry(spec)

    # Create HTTP client with authentication
    headers = {}
    auth = None
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    elif username and password:
        auth = httpx.BasicAuth(username, password)

    client = httpx.AsyncClient(
        base_url=base_url,
        headers=headers,
        auth=auth,
        timeout=30.0,
    )

    # Create FastMCP server
    mcp = FastMCP(
        name="unblu-mcp",
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

    @mcp.tool()
    async def list_services() -> list[dict[str, Any]]:
        """List all available Unblu API service categories.

        Returns a list of services (API tags) with their descriptions and
        operation counts. Use this to discover what API capabilities are available.

        Returns:
            List of services with name, description, and operation_count.
        """
        services = registry.list_services()
        return [s.model_dump() for s in services]

    @mcp.tool()
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
            available = [s.name for s in registry.list_services()]
            return [{"error": f"Service '{service}' not found. Available: {available}"}]
        return [op.model_dump() for op in operations]

    @mcp.tool()
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

    @mcp.tool()
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
            return {"error": f"Operation '{operation_id}' not found."}
        return schema.model_dump()

    @mcp.tool()
    async def call_api(
        operation_id: str,
        path_params: dict[str, str] | None = None,
        query_params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Execute an Unblu API operation.

        Args:
            operation_id: The operation ID to execute.
            path_params: Path parameters (e.g., {"conversationId": "abc123"}).
            query_params: Query string parameters.
            body: Request body for POST/PUT/PATCH operations.
            headers: Additional headers to include.

        Returns:
            API response as JSON, or error details if the request failed.
        """
        op = registry.operations.get(operation_id)
        if not op:
            return {"error": f"Operation '{operation_id}' not found."}

        # Build URL with path parameters
        path = op["path"]
        if path_params:
            for key, value in path_params.items():
                path = path.replace(f"{{{key}}}", str(value))

        # Check for unresolved path parameters
        if "{" in path:
            missing = re.findall(r"\{(\w+)\}", path)
            return {"error": f"Missing required path parameters: {missing}"}

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
                data = response.json()
            except json.JSONDecodeError:
                data = {"raw_response": response.text[:1000]}

            if response.is_success:
                return {"status": "success", "status_code": response.status_code, "data": data}
            return {  # noqa: TRY300
                "status": "error",
                "status_code": response.status_code,
                "error": data,
            }

        except httpx.RequestError as e:
            return {"status": "error", "error": str(e)}

    return mcp


class _ServerHolder:
    """Holder for global server instance to avoid global statement."""

    instance: FastMCP | None = None


def get_server() -> FastMCP:
    """Get or create the global server instance."""
    if _ServerHolder.instance is None:
        _ServerHolder.instance = create_server()
    return _ServerHolder.instance
