"""Tests for the Unblu MCP server."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest
from fastmcp import FastMCP
from mcp.shared.exceptions import McpError

from unblu_mcp._internal.server import (
    OperationInfo,
    OperationSchema,
    ServiceInfo,
    UnbluAPIRegistry,
    _ServerHolder,
    create_server,
    get_server,
)


@pytest.fixture(scope="module")
def swagger_spec() -> dict:
    """Load the swagger.json spec."""
    spec_path = Path(__file__).parent.parent / "src" / "unblu_mcp" / "swagger.json"
    if not spec_path.exists():
        pytest.skip("swagger.json not found")
    with Path(spec_path).open(encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def registry(swagger_spec: dict) -> UnbluAPIRegistry:
    """Create an API registry from the spec."""
    return UnbluAPIRegistry(swagger_spec)


@pytest.fixture(scope="module")
def server() -> FastMCP:
    """Create an MCP server instance."""
    spec_path = Path(__file__).parent.parent / "src" / "unblu_mcp" / "swagger.json"
    return create_server(spec_path=spec_path)


class TestUnbluAPIRegistry:
    """Tests for the UnbluAPIRegistry class."""

    def test_parse_services(self, registry: UnbluAPIRegistry) -> None:
        """Registry parses services from OpenAPI tags."""
        services = registry.list_services()
        assert len(services) > 0
        assert all(isinstance(s, ServiceInfo) for s in services)

        # Check for expected services
        service_names = [s.name for s in services]
        assert "Conversations" in service_names
        assert "Users" in service_names
        assert "Bots" in service_names

    def test_excludes_webhook_tags(self, registry: UnbluAPIRegistry) -> None:
        """Registry excludes webhook/event schema tags."""
        service_names = [s.name for s in registry.list_services()]
        assert "For bots" not in service_names
        assert "For webhooks" not in service_names
        assert "Schemas" not in service_names

    def test_parse_operations(self, registry: UnbluAPIRegistry) -> None:
        """Registry parses operations from OpenAPI paths."""
        assert len(registry.operations) > 0

        # Check a known operation exists
        assert "conversationsGetById" in registry.operations or any("conversation" in op_id.lower() for op_id in registry.operations)

    def test_list_operations_for_service(self, registry: UnbluAPIRegistry) -> None:
        """list_operations returns operations for a specific service."""
        ops = registry.list_operations("Conversations")
        assert len(ops) > 0
        assert all(isinstance(op, OperationInfo) for op in ops)

    def test_list_operations_unknown_service(self, registry: UnbluAPIRegistry) -> None:
        """list_operations returns empty list for unknown service."""
        ops = registry.list_operations("NonExistentService")
        assert ops == []

    def test_search_operations_excludes_infra_by_default(self, registry: UnbluAPIRegistry) -> None:
        """search_operations excludes infra services unless include_infra=True."""
        results_default = registry.search_operations("webhook", include_infra=False)
        results_with_infra = registry.search_operations("webhook", include_infra=True)
        assert len(results_with_infra) >= len(results_default)

    def test_service_tier_assignment(self, registry: UnbluAPIRegistry) -> None:
        """Services are assigned correct tiers."""
        services_by_name = {s.name: s for s in registry.list_services()}
        assert services_by_name["Conversations"].tier == "curated"
        assert services_by_name["Persons"].tier == "curated"
        assert services_by_name["Accounts"].tier == "curated"

    def test_search_operations(self, registry: UnbluAPIRegistry) -> None:
        """search_operations finds operations by keyword."""
        results = registry.search_operations("create")
        assert len(results) > 0
        assert all(isinstance(op, OperationInfo) for op in results)

    def test_search_operations_limit(self, registry: UnbluAPIRegistry) -> None:
        """search_operations respects the limit parameter."""
        results = registry.search_operations("get", limit=5)
        assert len(results) <= 5

    def test_get_operation_schema(self, registry: UnbluAPIRegistry) -> None:
        """get_operation_schema returns full schema for an operation."""
        # Find any operation
        op_id = next(iter(registry.operations.keys()))
        schema = registry.get_operation_schema(op_id)

        assert schema is not None
        assert isinstance(schema, OperationSchema)
        assert schema.operation_id == op_id
        assert schema.method in {"GET", "POST", "PUT", "DELETE", "PATCH"}

    def test_get_operation_schema_unknown(self, registry: UnbluAPIRegistry) -> None:
        """get_operation_schema returns None for unknown operation."""
        schema = registry.get_operation_schema("nonExistentOperation")
        assert schema is None

    def test_operation_count_matches(self, registry: UnbluAPIRegistry) -> None:
        """Service operation_count matches actual operations."""
        for service in registry.list_services():
            ops = registry.list_operations(service.name)
            assert len(ops) == service.operation_count

    def test_list_operations_returns_operation_info(self, registry: UnbluAPIRegistry) -> None:
        """list_operations returns OperationInfo objects with service field set."""
        ops = registry.list_operations("Conversations")
        assert all(isinstance(op, OperationInfo) for op in ops)
        assert all(op.service == "Conversations" for op in ops)


class TestMCPServer:
    """Tests for the MCP server creation."""

    def test_server_creation(self, server: FastMCP) -> None:
        """Server is created successfully."""
        assert server is not None
        assert server.name == "unblu-mcp"

    @pytest.mark.anyio
    async def test_server_has_tools(self, server: FastMCP) -> None:
        """Server exposes always-visible tools + BM25 synthetic discovery tools."""
        tools = await server.list_tools()
        tool_names = [t.name for t in tools]
        always_visible = [
            "find_operation",
            "execute_operation",
            "get_current_account",
            "search_conversations",
            "search_persons",
        ]
        synthetic = ["search_tools", "call_tool"]
        for tool_name in always_visible + synthetic:
            assert tool_name in tool_names, f"Missing tool: {tool_name}"

    @pytest.mark.anyio
    async def test_server_tool_count(self, server: FastMCP) -> None:
        """Server lists 7 tools: 5 always-visible + 2 BM25 synthetic (search_tools, call_tool)."""
        tools = await server.list_tools()
        assert len(tools) == 7

    @pytest.mark.anyio
    async def test_server_has_resources(self, server: FastMCP) -> None:
        """Server exposes the api://services and api://operations resources."""
        from fastmcp.client import Client

        async with Client(transport=server) as client:
            resources = await client.list_resources()
            uris = [str(r.uri) for r in resources]
            assert "api://services" in uris

    @pytest.mark.anyio
    async def test_server_has_prompts(self, server: FastMCP) -> None:
        """Server exposes the three debugging prompts."""
        from fastmcp.client import Client

        async with Client(transport=server) as client:
            prompts = await client.list_prompts()
            prompt_names = [p.name for p in prompts]
            assert "debug_conversation" in prompt_names
            assert "find_agent" in prompt_names
            assert "account_health_check" in prompt_names


class TestTokenEfficiency:
    """Tests validating the token-efficient architecture."""

    def test_total_operations_indexed(self, registry: UnbluAPIRegistry) -> None:
        """All API operations are indexed for discovery."""
        # The swagger.json has 331 endpoints
        assert len(registry.operations) >= 300

    def test_services_count(self, registry: UnbluAPIRegistry) -> None:
        """Services are properly categorized."""
        services = registry.list_services()
        # Should have 40+ services (excluding webhook/schema tags)
        assert len(services) >= 40

    def test_curated_tools_vs_total_operations(self, registry: UnbluAPIRegistry) -> None:
        """Verify the token efficiency claim.

        Instead of 300+ raw operation definitions, we expose 13 curated typed tools
        plus an escape hatch. This is a >95% reduction in exposed surface area.
        """
        total_operations = len(registry.operations)
        curated_tools = 13  # find_operation, execute_operation, + 11 typed tools
        reduction_ratio = (total_operations - curated_tools) / total_operations
        assert reduction_ratio > 0.95, f"Expected >95% reduction, got {reduction_ratio:.2%}"


class TestUnbluAPIRegistryEdgeCases:
    """Tests for edge cases in UnbluAPIRegistry."""

    def test_schema_caching(self, registry: UnbluAPIRegistry) -> None:
        """Schema is cached after first retrieval."""
        op_id = next(iter(registry.operations.keys()))

        # First call populates cache
        schema1 = registry.get_operation_schema(op_id)
        assert schema1 is not None
        assert op_id in registry._schema_cache

        # Second call uses cache
        schema2 = registry.get_operation_schema(op_id)
        assert schema2 is not None
        assert schema1.operation_id == schema2.operation_id

    def test_resolve_refs_max_depth(self) -> None:
        """_resolve_refs truncates at max depth."""
        spec = {"tags": [], "paths": {}}
        registry = UnbluAPIRegistry(spec)

        # Create deeply nested refs
        deep_obj = {"$ref": "#/components/schemas/Deep"}
        result = registry._resolve_refs(deep_obj, depth=4)  # Beyond MAX_REF_DEPTH (3)
        assert result == {"$ref": "...truncated for brevity..."}

    def test_resolve_refs_unresolvable_ref(self) -> None:
        """_resolve_refs returns original if ref cannot be resolved."""
        spec = {"tags": [], "paths": {}}
        registry = UnbluAPIRegistry(spec)

        obj = {"$ref": "#/nonexistent/path"}
        result = registry._resolve_refs(obj)
        assert result == {"$ref": "#/nonexistent/path"}

    def test_resolve_refs_external_ref(self) -> None:
        """_resolve_refs returns original for external refs."""
        spec = {"tags": [], "paths": {}}
        registry = UnbluAPIRegistry(spec)

        obj = {"$ref": "external.json#/schema"}
        result = registry._resolve_refs(obj)
        assert result == {"$ref": "external.json#/schema"}

    def test_get_ref_invalid_path(self) -> None:
        """_get_ref returns None for invalid paths."""
        spec: dict = {"tags": [], "paths": {}, "components": {"schemas": {}}}
        registry = UnbluAPIRegistry(spec)

        # Path doesn't exist
        assert registry._get_ref("#/components/schemas/NonExistent") is None

        # Path traverses non-dict
        spec["components"]["schemas"]["Test"] = "string_value"
        assert registry._get_ref("#/components/schemas/Test/nested") is None

    def test_parse_operation_without_tags(self) -> None:
        """Operations without tags default to 'Other'."""
        spec = {
            "tags": [{"name": "Other", "description": "Other operations"}],
            "paths": {
                "/test": {
                    "get": {
                        "operationId": "testOp",
                        "summary": "Test operation",
                        # No tags specified
                    }
                }
            },
        }
        registry = UnbluAPIRegistry(spec)
        assert "testOp" in registry.operations
        assert registry.operations["testOp"]["tags"] == ["Other"]

    def test_parse_operation_generates_id(self) -> None:
        """Operations without operationId get generated ID."""
        spec = {
            "tags": [{"name": "Test", "description": "Test"}],
            "paths": {
                "/api/resource": {
                    "post": {
                        "tags": ["Test"],
                        "summary": "Create resource",
                        # No operationId
                    }
                }
            },
        }
        registry = UnbluAPIRegistry(spec)
        # Should generate ID from method and path
        assert "post_/api/resource" in registry.operations

    def test_search_operations_scores_by_relevance(self, registry: UnbluAPIRegistry) -> None:
        """Search results are ordered by relevance score."""
        # Search for something that appears in operation IDs
        results = registry.search_operations("conversation", limit=10)
        assert len(results) > 0
        # Results with "conversation" in ID should be first
        assert "conversation" in results[0].operation_id.lower()


class TestLifespanBehavior:
    """Tests for server lifespan handling of provider setup/teardown."""

    @pytest.mark.anyio
    async def test_lifespan_calls_provider_setup_and_teardown(self) -> None:
        """Lifespan context manager calls provider.setup() and provider.teardown()."""
        from fastmcp.client import Client

        from unblu_mcp._internal.providers import ConnectionConfig, ConnectionProvider

        class MockProvider(ConnectionProvider):
            def __init__(self) -> None:
                self.setup_called = False
                self.teardown_called = False

            async def setup(self) -> None:
                self.setup_called = True

            async def teardown(self) -> None:
                self.teardown_called = True

            def get_config(self) -> ConnectionConfig:
                return ConnectionConfig(base_url="http://localhost:8080/api")

        spec_path = Path(__file__).parent.parent / "src" / "unblu_mcp" / "swagger.json"
        provider = MockProvider()
        server = create_server(spec_path=spec_path, provider=provider)

        # Before client context, setup should not be called
        assert not provider.setup_called
        assert not provider.teardown_called

        # Enter client context (triggers lifespan)
        async with Client(transport=server):
            # Inside context, setup should have been called
            assert provider.setup_called
            assert not provider.teardown_called

        # After exiting context, teardown should have been called
        assert provider.teardown_called

    @pytest.mark.anyio
    async def test_lifespan_teardown_called_on_exception(self) -> None:
        """Teardown is called even if an exception occurs during server operation."""
        from fastmcp.client import Client

        from unblu_mcp._internal.providers import ConnectionConfig, ConnectionProvider

        class MockProvider(ConnectionProvider):
            def __init__(self) -> None:
                self.setup_called = False
                self.teardown_called = False

            async def setup(self) -> None:
                self.setup_called = True

            async def teardown(self) -> None:
                self.teardown_called = True

            def get_config(self) -> ConnectionConfig:
                return ConnectionConfig(base_url="http://localhost:8080/api")

        spec_path = Path(__file__).parent.parent / "src" / "unblu_mcp" / "swagger.json"
        provider = MockProvider()
        server = create_server(spec_path=spec_path, provider=provider)

        # Simulate exception during server operation - use helper to satisfy PT012
        async def _run_and_raise() -> None:
            async with Client(transport=server):
                msg = "Simulated error"
                raise ValueError(msg)

        with pytest.raises(ValueError, match="Simulated error"):
            await _run_and_raise()

        # Teardown should still be called
        assert provider.teardown_called

    @pytest.mark.anyio
    async def test_lifespan_setup_failure_prevents_server_start(self) -> None:
        """If setup() fails, the server should not start."""
        from fastmcp.client import Client

        from unblu_mcp._internal.providers import ConnectionConfig, ConnectionProvider

        class FailingProvider(ConnectionProvider):
            def __init__(self) -> None:
                self.teardown_called = False

            async def setup(self) -> None:
                msg = "Setup failed"
                raise RuntimeError(msg)

            async def teardown(self) -> None:
                self.teardown_called = True

            def get_config(self) -> ConnectionConfig:
                return ConnectionConfig(base_url="http://localhost:8080/api")

        spec_path = Path(__file__).parent.parent / "src" / "unblu_mcp" / "swagger.json"
        provider = FailingProvider()
        server = create_server(spec_path=spec_path, provider=provider)

        with pytest.raises(RuntimeError, match="Setup failed"):
            async with Client(transport=server):
                pass

        # Teardown should NOT be called since setup failed before yield
        assert not provider.teardown_called


class TestCreateServerEdgeCases:
    """Tests for create_server edge cases."""

    def test_create_server_spec_not_found(self, tmp_path: Path) -> None:
        """create_server raises FileNotFoundError if spec not found."""
        # Mock importlib.resources to raise FileNotFoundError (simulating missing package resource)
        mock_files = MagicMock()
        mock_files.return_value.joinpath.return_value.read_text.side_effect = FileNotFoundError()
        with (
            patch("unblu_mcp._internal.server.importlib.resources.files", mock_files),
            patch("unblu_mcp._internal.server.Path.cwd", return_value=tmp_path),
            pytest.raises(FileNotFoundError, match=r"swagger\.json not found"),
        ):
            create_server(spec_path=None)

    def test_create_server_with_custom_provider(self) -> None:
        """create_server accepts custom connection provider."""
        from unblu_mcp._internal.providers import ConnectionConfig, ConnectionProvider

        class CustomProvider(ConnectionProvider):
            async def setup(self) -> None:
                pass

            async def teardown(self) -> None:
                pass

            def get_config(self) -> ConnectionConfig:
                return ConnectionConfig(
                    base_url="http://custom.example.com/api",
                    headers={"X-Custom": "header"},
                )

        spec_path = Path(__file__).parent.parent / "src" / "unblu_mcp" / "swagger.json"
        server = create_server(spec_path=spec_path, provider=CustomProvider())
        assert server is not None


# Check if eunomia_mcp is available
try:
    import eunomia_mcp  # noqa: F401

    HAS_EUNOMIA = True
except ImportError:
    HAS_EUNOMIA = False


@pytest.mark.skipif(not HAS_EUNOMIA, reason="eunomia_mcp not installed")
class TestEunomiaIntegration:
    """Tests for Eunomia authorization middleware integration."""

    def test_create_server_with_policy_file(self, tmp_path: Path) -> None:
        """create_server accepts policy_file parameter."""
        # Create a minimal policy file
        policy_file = tmp_path / "test_policy.json"
        policy_file.write_text(
            json.dumps({
                "version": "1.0",
                "name": "test-policy",
                "default_effect": "allow",
                "rules": [],
            }),
            encoding="utf-8",
        )

        spec_path = Path(__file__).parent.parent / "src" / "unblu_mcp" / "swagger.json"
        server = create_server(spec_path=spec_path, policy_file=policy_file)
        assert server is not None

    def test_create_server_policy_file_not_found(self, tmp_path: Path) -> None:
        """create_server raises FileNotFoundError for missing policy file."""
        spec_path = Path(__file__).parent.parent / "src" / "unblu_mcp" / "swagger.json"
        nonexistent_policy = tmp_path / "nonexistent.json"

        with pytest.raises(FileNotFoundError, match=r"Policy file not found"):
            create_server(spec_path=spec_path, policy_file=nonexistent_policy)

    def test_create_server_without_policy_file(self) -> None:
        """create_server works without policy_file (default behavior)."""
        spec_path = Path(__file__).parent.parent / "src" / "unblu_mcp" / "swagger.json"
        server = create_server(spec_path=spec_path, policy_file=None)
        assert server is not None


class TestGetServer:
    """Tests for get_server singleton function."""

    def test_get_server_creates_instance(self) -> None:
        """get_server creates server instance on first call."""
        # Reset singleton
        _ServerHolder._instance = None

        with patch("unblu_mcp._internal.server.create_server") as mock_create:
            from fastmcp import FastMCP

            mock_server = FastMCP(name="test")
            mock_create.return_value = mock_server

            result = get_server()
            assert result == mock_server
            mock_create.assert_called_once()

    def test_get_server_returns_cached_instance(self) -> None:
        """get_server returns cached instance on subsequent calls."""
        from fastmcp import FastMCP

        mock_server = FastMCP(name="cached")
        _ServerHolder._instance = mock_server

        result = get_server()
        assert result == mock_server

        # Reset for other tests
        _ServerHolder._instance = None


class TestToolErrorHandling:
    """Tests for ToolError handling in MCP tools."""

    @pytest.fixture
    def server_with_tools(self) -> FastMCP:
        """Create server with access to tool functions."""
        spec_path = Path(__file__).parent.parent / "src" / "unblu_mcp" / "swagger.json"
        return create_server(spec_path=spec_path)

    @pytest.mark.anyio
    async def test_execute_operation_unknown_raises_tool_error(self, server_with_tools: FastMCP) -> None:
        """execute_operation raises ToolError for unknown operation."""
        with pytest.raises(McpError, match=r"Operation 'nonExistentOp' not found"):
            await server_with_tools.call_tool("execute_operation", {"operation_id": "nonExistentOp"})

    @pytest.mark.anyio
    async def test_execute_operation_missing_path_params_raises_tool_error(self, server_with_tools: FastMCP) -> None:
        """execute_operation raises ToolError when required path params are missing."""
        # accountsDelete requires accountId path param
        with pytest.raises(McpError, match=r"Missing required path parameters"):
            await server_with_tools.call_tool("execute_operation", {"operation_id": "accountsDelete", "path_params": None})

    @pytest.mark.anyio
    async def test_execute_operation_delete_without_confirm_raises_tool_error(self, server_with_tools: FastMCP) -> None:
        """execute_operation blocks DELETE ops without confirm_destructive=True."""
        with pytest.raises(McpError, match=r"destructive"):
            await server_with_tools.call_tool(
                "execute_operation",
                {"operation_id": "accountsDelete", "path_params": {"accountId": "x"}, "confirm_destructive": False},
            )

    @pytest.mark.anyio
    async def test_execute_operation_request_error_raises_tool_error(self, server_with_tools: FastMCP) -> None:
        """execute_operation raises ToolError on httpx.RequestError."""
        with (
            patch.object(
                httpx.AsyncClient,
                "request",
                side_effect=httpx.ConnectError("Connection refused"),
            ),
            pytest.raises(McpError, match=r"API request failed"),
        ):
            await server_with_tools.call_tool("execute_operation", {"operation_id": "accountsCreate"})

    @pytest.mark.anyio
    async def test_find_operation_returns_matches(self, server_with_tools: FastMCP) -> None:
        """find_operation returns OperationSearchResult with matches."""
        result = await server_with_tools.call_tool("find_operation", {"query": "conversation", "include_schema": False})
        assert result is not None

    @pytest.mark.anyio
    async def test_get_conversation_unknown_raises_tool_error(self, server_with_tools: FastMCP) -> None:
        """get_conversation raises ToolError on 404."""
        with (
            patch.object(
                httpx.AsyncClient,
                "request",
                return_value=httpx.Response(404, json={"error": "not found"}),
            ),
            pytest.raises(McpError, match=r"not found"),
        ):
            await server_with_tools.call_tool("get_conversation", {"conversation_id": "does-not-exist"})

    @pytest.mark.anyio
    async def test_get_person_email_ambiguous_returns_candidates(self, server_with_tools: FastMCP) -> None:
        """get_person returns PersonAmbiguousResult when email matches multiple persons."""
        persons = [
            {"id": "p1", "displayName": "Alice", "personType": "VISITOR", "email": "alice@example.com", "teamId": None},
            {"id": "p2", "displayName": "Alice B", "personType": "VISITOR", "email": "alice@example.com", "teamId": None},
        ]
        with patch.object(
            httpx.AsyncClient,
            "request",
            return_value=httpx.Response(200, json={"items": persons, "offset": 0, "limit": 5, "total": 2}),
        ):
            result = await server_with_tools.call_tool("get_person", {"identifier": "alice@example.com"})
        assert result.structured_content is not None
        # FastMCP wraps union return types under "result"
        data = result.structured_content["result"]
        assert "candidates" in data, "Expected PersonAmbiguousResult with candidates"
        assert len(data["candidates"]) == 2
        assert "next_steps" in data

    @pytest.mark.anyio
    async def test_get_person_name_ambiguous_returns_candidates(self, server_with_tools: FastMCP) -> None:
        """get_person returns PersonAmbiguousResult when name matches multiple persons."""
        persons = [
            {"id": "p1", "displayName": "John Smith", "personType": "VISITOR", "email": None, "teamId": None},
            {"id": "p2", "displayName": "John Smithson", "personType": "AGENT", "email": None, "teamId": "t1"},
        ]
        with patch.object(
            httpx.AsyncClient,
            "request",
            return_value=httpx.Response(200, json={"items": persons, "offset": 0, "limit": 10, "total": 2}),
        ):
            result = await server_with_tools.call_tool("get_person", {"identifier": "John"})
        assert result.structured_content is not None
        # FastMCP wraps union return types under "result"
        data = result.structured_content["result"]
        assert "candidates" in data
        assert len(data["candidates"]) == 2
        ids = {c["id"] for c in data["candidates"]}
        assert ids == {"p1", "p2"}

    @pytest.mark.anyio
    async def test_get_user_username_lookup_success(self, server_with_tools: FastMCP) -> None:
        """get_user resolves a username (no @) via /users/getByUsername."""
        user = {"id": "u1", "username": "bob", "displayName": "Bob", "email": "bob@example.com", "teamId": None}
        with patch.object(
            httpx.AsyncClient,
            "request",
            return_value=httpx.Response(200, json=user),
        ):
            result = await server_with_tools.call_tool("get_user", {"identifier": "bob"})
        assert result.structured_content is not None
        data = result.structured_content
        assert data["id"] == "u1"
        assert data["display_name"] == "Bob"

    @pytest.mark.anyio
    async def test_get_user_username_not_found_raises_tool_error(self, server_with_tools: FastMCP) -> None:
        """get_user raises ToolError when username is not found, with search hint."""
        with (
            patch.object(
                httpx.AsyncClient,
                "request",
                return_value=httpx.Response(404, json={"error": "not found"}),
            ),
            pytest.raises(McpError, match=r"search_users"),
        ):
            await server_with_tools.call_tool("get_user", {"identifier": "ghost"})

    @pytest.mark.anyio
    async def test_ctx_log_no_session_does_not_raise(self, server_with_tools: FastMCP) -> None:
        """Tools using _ctx_log must not raise when called without an MCP session.

        Regression test: _ctx_log previously called itself recursively instead of
        ctx.info(), causing infinite recursion. It now uses contextlib.suppress(RuntimeError)
        around ctx.info() so tools run cleanly in direct call_tool() invocations.
        """
        result = await server_with_tools.call_tool("find_operation", {"query": "accounts", "include_schema": False, "limit": 1})
        assert result is not None


class TestCuratedToolsCoverage:
    """Coverage tests for all curated tools — success and error paths."""

    @pytest.fixture
    def srv(self) -> FastMCP:
        spec_path = Path(__file__).parent.parent / "src" / "unblu_mcp" / "swagger.json"
        return create_server(spec_path=spec_path)

    def _mock(self, status: int, body: object) -> MagicMock:
        return MagicMock(return_value=httpx.Response(status, json=body))

    # ------------------------------------------------------------------
    # get_current_account
    # ------------------------------------------------------------------

    @pytest.mark.anyio
    async def test_get_current_account_success(self, srv: FastMCP) -> None:
        with patch.object(httpx.AsyncClient, "request", return_value=httpx.Response(200, json={"id": "a1", "name": "Acme"})):
            result = await srv.call_tool("get_current_account", {})
        assert result.structured_content is not None
        assert result.structured_content["id"] == "a1"
        assert result.structured_content["name"] == "Acme"

    @pytest.mark.anyio
    async def test_get_current_account_error_raises(self, srv: FastMCP) -> None:
        with (
            patch.object(httpx.AsyncClient, "request", return_value=httpx.Response(401, json={"error": "unauthorized"})),
            pytest.raises(McpError, match=r"UNBLU_BASE_URL"),
        ):
            await srv.call_tool("get_current_account", {})

    # ------------------------------------------------------------------
    # search_conversations
    # ------------------------------------------------------------------

    @pytest.mark.anyio
    async def test_search_conversations_with_filters(self, srv: FastMCP) -> None:
        body = {"items": [{"id": "c1", "state": "ACTIVE"}], "offset": 0, "limit": 25, "total": 1}
        with patch.object(httpx.AsyncClient, "request", return_value=httpx.Response(200, json=body)):
            result = await srv.call_tool("search_conversations", {"status": "ACTIVE", "topic": "help"})
        assert result.structured_content is not None
        assert "items" in result.structured_content

    @pytest.mark.anyio
    async def test_search_conversations_empty(self, srv: FastMCP) -> None:
        body = {"items": [], "offset": 0, "limit": 25, "total": 0}
        with patch.object(httpx.AsyncClient, "request", return_value=httpx.Response(200, json=body)):
            result = await srv.call_tool("search_conversations", {})
        assert result.structured_content is not None
        assert result.structured_content["items"] == []

    # ------------------------------------------------------------------
    # assign_conversation
    # ------------------------------------------------------------------

    @pytest.mark.anyio
    async def test_assign_conversation_success(self, srv: FastMCP) -> None:
        with patch.object(httpx.AsyncClient, "request", return_value=httpx.Response(200, json={})):
            result = await srv.call_tool(
                "assign_conversation",
                {"conversation_id": "c1", "assignee_person_id": "p1"},
            )
        data = result.structured_content
        assert data is not None
        assert data["success"] is True
        assert "c1" in data["message"]

    @pytest.mark.anyio
    async def test_assign_conversation_error_raises(self, srv: FastMCP) -> None:
        with (
            patch.object(httpx.AsyncClient, "request", return_value=httpx.Response(404, json={"error": "not found"})),
            pytest.raises(McpError, match=r"assign"),
        ):
            await srv.call_tool("assign_conversation", {"conversation_id": "bad", "assignee_person_id": "p1"})

    # ------------------------------------------------------------------
    # end_conversation
    # ------------------------------------------------------------------

    @pytest.mark.anyio
    async def test_end_conversation_success(self, srv: FastMCP) -> None:
        with patch.object(httpx.AsyncClient, "request", return_value=httpx.Response(200, json={})):
            result = await srv.call_tool("end_conversation", {"conversation_id": "c1"})
        data = result.structured_content
        assert data is not None
        assert data["success"] is True
        assert "ended" in data["message"].lower()

    @pytest.mark.anyio
    async def test_end_conversation_error_raises(self, srv: FastMCP) -> None:
        with (
            patch.object(httpx.AsyncClient, "request", return_value=httpx.Response(400, json={"error": "bad state"})),
            pytest.raises(McpError, match=r"end conversation"),
        ):
            await srv.call_tool("end_conversation", {"conversation_id": "bad"})

    # ------------------------------------------------------------------
    # search_persons
    # ------------------------------------------------------------------

    @pytest.mark.anyio
    async def test_search_persons_generic(self, srv: FastMCP) -> None:
        body = {"items": [{"id": "p1", "displayName": "Alice", "personType": "AGENT"}], "offset": 0, "limit": 25, "total": 1}
        with patch.object(httpx.AsyncClient, "request", return_value=httpx.Response(200, json=body)):
            result = await srv.call_tool("search_persons", {"query": "alice"})
        assert result.structured_content is not None
        items = result.structured_content["items"]
        assert len(items) == 1
        assert items[0]["id"] == "p1"

    @pytest.mark.anyio
    async def test_search_persons_by_agent_type(self, srv: FastMCP) -> None:
        body = {"items": [], "offset": 0, "limit": 25, "total": 0}
        with patch.object(httpx.AsyncClient, "request", return_value=httpx.Response(200, json=body)):
            result = await srv.call_tool("search_persons", {"person_type": "AGENT"})
        assert result.structured_content is not None
        assert result.structured_content["items"] == []

    @pytest.mark.anyio
    async def test_search_persons_error_raises(self, srv: FastMCP) -> None:
        with (
            patch.object(httpx.AsyncClient, "request", return_value=httpx.Response(500, json={"error": "server error"})),
            pytest.raises(McpError, match=r"Person search failed"),
        ):
            await srv.call_tool("search_persons", {})

    # ------------------------------------------------------------------
    # get_person — UUID path
    # ------------------------------------------------------------------

    @pytest.mark.anyio
    async def test_get_person_by_uuid_success(self, srv: FastMCP) -> None:
        person = {"id": "a1b2c3d4-1234-1234-1234-a1b2c3d4e5f6", "displayName": "Alice", "personType": "AGENT"}
        with patch.object(httpx.AsyncClient, "request", return_value=httpx.Response(200, json=person)):
            result = await srv.call_tool("get_person", {"identifier": "a1b2c3d4-1234-1234-1234-a1b2c3d4e5f6"})
        assert result.structured_content is not None

    @pytest.mark.anyio
    async def test_get_person_by_uuid_not_found(self, srv: FastMCP) -> None:
        with (
            patch.object(httpx.AsyncClient, "request", return_value=httpx.Response(404, json={"error": "not found"})),
            pytest.raises(McpError, match=r"search_persons"),
        ):
            await srv.call_tool("get_person", {"identifier": "a1b2c3d4-1234-1234-1234-a1b2c3d4e5f6"})

    @pytest.mark.anyio
    async def test_get_person_by_email_single_match(self, srv: FastMCP) -> None:
        body = {"items": [{"id": "p1", "displayName": "Alice", "email": "alice@example.com"}], "offset": 0, "limit": 5, "total": 1}
        with patch.object(httpx.AsyncClient, "request", return_value=httpx.Response(200, json=body)):
            result = await srv.call_tool("get_person", {"identifier": "alice@example.com"})
        assert result.structured_content is not None

    @pytest.mark.anyio
    async def test_get_person_by_email_not_found(self, srv: FastMCP) -> None:
        body = {"items": [], "offset": 0, "limit": 5, "total": 0}
        with (
            patch.object(httpx.AsyncClient, "request", return_value=httpx.Response(200, json=body)),
            pytest.raises(McpError, match=r"search_persons"),
        ):
            await srv.call_tool("get_person", {"identifier": "ghost@example.com"})

    @pytest.mark.anyio
    async def test_get_person_by_name_not_found(self, srv: FastMCP) -> None:
        body = {"items": [], "offset": 0, "limit": 10, "total": 0}
        with (
            patch.object(httpx.AsyncClient, "request", return_value=httpx.Response(200, json=body)),
            pytest.raises(McpError, match=r"search_persons"),
        ):
            await srv.call_tool("get_person", {"identifier": "Nobody"})

    # ------------------------------------------------------------------
    # search_users
    # ------------------------------------------------------------------

    @pytest.mark.anyio
    async def test_search_users_success(self, srv: FastMCP) -> None:
        body = {"items": [{"id": "u1", "username": "bob", "displayName": "Bob"}], "offset": 0, "limit": 25, "total": 1}
        with patch.object(httpx.AsyncClient, "request", return_value=httpx.Response(200, json=body)):
            result = await srv.call_tool("search_users", {"query": "bob"})
        assert result.structured_content is not None
        items = result.structured_content["items"]
        assert len(items) == 1

    @pytest.mark.anyio
    async def test_search_users_error_raises(self, srv: FastMCP) -> None:
        with (
            patch.object(httpx.AsyncClient, "request", return_value=httpx.Response(500, json={"error": "err"})),
            pytest.raises(McpError, match=r"User search failed"),
        ):
            await srv.call_tool("search_users", {})

    # ------------------------------------------------------------------
    # get_user — UUID and email paths
    # ------------------------------------------------------------------

    @pytest.mark.anyio
    async def test_get_user_by_uuid_success(self, srv: FastMCP) -> None:
        user = {"id": "a1b2c3d4-1234-1234-1234-a1b2c3d4e5f6", "username": "alice", "displayName": "Alice"}
        with patch.object(httpx.AsyncClient, "request", return_value=httpx.Response(200, json=user)):
            result = await srv.call_tool("get_user", {"identifier": "a1b2c3d4-1234-1234-1234-a1b2c3d4e5f6"})
        assert result.structured_content is not None
        assert result.structured_content["id"] == "a1b2c3d4-1234-1234-1234-a1b2c3d4e5f6"

    @pytest.mark.anyio
    async def test_get_user_by_uuid_not_found(self, srv: FastMCP) -> None:
        with (
            patch.object(httpx.AsyncClient, "request", return_value=httpx.Response(404, json={"error": "not found"})),
            pytest.raises(McpError, match=r"search_users"),
        ):
            await srv.call_tool("get_user", {"identifier": "a1b2c3d4-1234-1234-1234-a1b2c3d4e5f6"})

    @pytest.mark.anyio
    async def test_get_user_by_email_success(self, srv: FastMCP) -> None:
        body = {"items": [{"id": "u1", "username": "bob", "email": "bob@example.com"}], "offset": 0, "limit": 5, "total": 1}
        with patch.object(httpx.AsyncClient, "request", return_value=httpx.Response(200, json=body)):
            result = await srv.call_tool("get_user", {"identifier": "bob@example.com"})
        assert result.structured_content is not None
        assert result.structured_content["id"] == "u1"

    @pytest.mark.anyio
    async def test_get_user_by_email_not_found(self, srv: FastMCP) -> None:
        body = {"items": [], "offset": 0, "limit": 5, "total": 0}
        with (
            patch.object(httpx.AsyncClient, "request", return_value=httpx.Response(200, json=body)),
            pytest.raises(McpError, match=r"search_users"),
        ):
            await srv.call_tool("get_user", {"identifier": "ghost@example.com"})

    # ------------------------------------------------------------------
    # check_agent_availability
    # ------------------------------------------------------------------

    @pytest.mark.anyio
    async def test_check_agent_availability_success(self, srv: FastMCP) -> None:
        with patch.object(httpx.AsyncClient, "request", return_value=httpx.Response(200, json={"agentAvailability": "AVAILABLE"})):
            result = await srv.call_tool("check_agent_availability", {})
        data = result.structured_content
        assert data is not None
        assert data["availability"] == "AVAILABLE"

    @pytest.mark.anyio
    async def test_check_agent_availability_with_named_area(self, srv: FastMCP) -> None:
        with patch.object(httpx.AsyncClient, "request", return_value=httpx.Response(200, json={"agentAvailability": "BUSY"})):
            result = await srv.call_tool("check_agent_availability", {"named_area_site_id": "site-1"})
        data = result.structured_content
        assert data is not None
        assert data["named_area_site_id"] == "site-1"

    @pytest.mark.anyio
    async def test_check_agent_availability_error_raises(self, srv: FastMCP) -> None:
        with (
            patch.object(httpx.AsyncClient, "request", return_value=httpx.Response(500, json={"error": "err"})),
            pytest.raises(McpError, match=r"agent availability"),
        ):
            await srv.call_tool("check_agent_availability", {})

    # ------------------------------------------------------------------
    # search_named_areas
    # ------------------------------------------------------------------

    @pytest.mark.anyio
    async def test_search_named_areas_success(self, srv: FastMCP) -> None:
        body = {"items": [{"id": "na1", "name": "Support", "siteId": "s1"}], "offset": 0, "limit": 25, "total": 1}
        with patch.object(httpx.AsyncClient, "request", return_value=httpx.Response(200, json=body)):
            result = await srv.call_tool("search_named_areas", {"query": "support"})
        assert result.structured_content is not None
        named_area_items = result.structured_content["data"]["items"]
        assert named_area_items[0]["id"] == "na1"
        assert named_area_items[0]["name"] == "Support"

    @pytest.mark.anyio
    async def test_search_named_areas_error_raises(self, srv: FastMCP) -> None:
        with (
            patch.object(httpx.AsyncClient, "request", return_value=httpx.Response(500, json={"error": "err"})),
            pytest.raises(McpError, match=r"Named area search failed"),
        ):
            await srv.call_tool("search_named_areas", {})

    # ------------------------------------------------------------------
    # execute_operation — offset/limit and pagination
    # ------------------------------------------------------------------

    @pytest.mark.anyio
    async def test_execute_operation_with_offset_limit(self, srv: FastMCP) -> None:
        resp = {"items": [{"id": "x"}], "offset": 10, "limit": 5, "total": 100, "hasMoreItems": True, "nextOffset": 15}
        with patch.object(httpx.AsyncClient, "request", return_value=httpx.Response(200, json=resp)):
            result = await srv.call_tool(
                "execute_operation",
                {"operation_id": "conversationsSearch", "offset": 10, "limit": 5},
            )
        assert result.structured_content is not None
        assert result.structured_content["has_more"] is True
        assert result.structured_content["next_offset"] is not None

    @pytest.mark.anyio
    async def test_execute_operation_get_with_offset_limit(self, srv: FastMCP) -> None:
        resp = {"id": "a1", "name": "Acme"}
        with patch.object(httpx.AsyncClient, "request", return_value=httpx.Response(200, json=resp)):
            result = await srv.call_tool(
                "execute_operation",
                {"operation_id": "accountsRead", "path_params": {"accountId": "a1"}, "offset": 0, "limit": 10},
            )
        assert result.structured_content is not None

    # ------------------------------------------------------------------
    # get_conversation — success path
    # ------------------------------------------------------------------

    @pytest.mark.anyio
    async def test_get_conversation_success(self, srv: FastMCP) -> None:
        conv = {
            "id": "c1",
            "topic": "Help request",
            "state": "ACTIVE",
            "creationTimestamp": 1700000000000,
            "endTimestamp": None,
            "assigneePerson": {"personId": "p1"},
            "participants": [{"personId": "p1", "participationType": "AGENT", "state": "ACTIVE", "hidden": False}],
            "initialEngagementType": "CHAT",
            "sourceUrl": "https://example.com",
            "awaitedPersonType": "AGENT",
        }
        with patch.object(httpx.AsyncClient, "request", return_value=httpx.Response(200, json=conv)):
            result = await srv.call_tool("get_conversation", {"conversation_id": "c1"})
        data = result.structured_content
        assert data is not None
        assert data["id"] == "c1"
        assert data["state"] == "ACTIVE"
        assert len(data["participants"]) == 1

    # ------------------------------------------------------------------
    # search_persons — VISITOR and BOT type branches + pagination
    # ------------------------------------------------------------------

    @pytest.mark.anyio
    async def test_search_persons_visitor_type(self, srv: FastMCP) -> None:
        body = {"items": [], "offset": 0, "limit": 25, "total": 0}
        with patch.object(httpx.AsyncClient, "request", return_value=httpx.Response(200, json=body)):
            result = await srv.call_tool("search_persons", {"person_type": "VISITOR"})
        assert result.structured_content is not None

    @pytest.mark.anyio
    async def test_search_persons_bot_type(self, srv: FastMCP) -> None:
        body = {"items": [], "offset": 0, "limit": 25, "total": 0}
        with patch.object(httpx.AsyncClient, "request", return_value=httpx.Response(200, json=body)):
            result = await srv.call_tool("search_persons", {"person_type": "BOT"})
        assert result.structured_content is not None

    @pytest.mark.anyio
    async def test_search_persons_paginated(self, srv: FastMCP) -> None:
        body = {"items": [{"id": "p1"}], "offset": 0, "limit": 5, "total": 100, "hasMoreItems": True, "nextOffset": 5}
        with patch.object(httpx.AsyncClient, "request", return_value=httpx.Response(200, json=body)):
            result = await srv.call_tool("search_persons", {"limit": 5})
        data = result.structured_content
        assert data is not None
        assert data["has_more"] is True
        assert data["next_offset"] == 5
        assert "search_persons(offset=5)" in data["next_steps"][-1]

    # ------------------------------------------------------------------
    # search_users — pagination has_more branch
    # ------------------------------------------------------------------

    @pytest.mark.anyio
    async def test_search_users_paginated(self, srv: FastMCP) -> None:
        body = {"items": [{"id": "u1"}], "offset": 0, "limit": 5, "total": 100, "hasMoreItems": True, "nextOffset": 5}
        with patch.object(httpx.AsyncClient, "request", return_value=httpx.Response(200, json=body)):
            result = await srv.call_tool("search_users", {"limit": 5})
        data = result.structured_content
        assert data is not None
        assert data["has_more"] is True
        assert "search_users(offset=5)" in data["next_steps"][-1]

    # ------------------------------------------------------------------
    # get_user — non-404 client error paths
    # ------------------------------------------------------------------

    @pytest.mark.anyio
    async def test_get_user_uuid_client_error_raises(self, srv: FastMCP) -> None:
        with (
            patch.object(httpx.AsyncClient, "request", return_value=httpx.Response(500, json={"error": "server error"})),
            pytest.raises(McpError, match=r"Failed to fetch user"),
        ):
            await srv.call_tool("get_user", {"identifier": "a1b2c3d4-1234-1234-1234-a1b2c3d4e5f6"})

    @pytest.mark.anyio
    async def test_get_user_username_client_error_raises(self, srv: FastMCP) -> None:
        with (
            patch.object(httpx.AsyncClient, "request", return_value=httpx.Response(500, json={"error": "server error"})),
            pytest.raises(McpError, match=r"Failed to fetch user"),
        ):
            await srv.call_tool("get_user", {"identifier": "problemuser"})

    # ------------------------------------------------------------------
    # search_named_areas — pagination has_more branch
    # ------------------------------------------------------------------

    @pytest.mark.anyio
    async def test_search_named_areas_paginated(self, srv: FastMCP) -> None:
        body = {
            "items": [{"id": "na1", "name": "Support"}],
            "offset": 0,
            "limit": 5,
            "total": 20,
            "hasMoreItems": True,
            "nextOffset": 5,
        }
        with patch.object(httpx.AsyncClient, "request", return_value=httpx.Response(200, json=body)):
            result = await srv.call_tool("search_named_areas", {"limit": 5})
        data = result.structured_content
        assert data is not None
        assert data["has_more"] is True
        assert "search_named_areas(offset=5)" in data["next_steps"][-1]

    @pytest.mark.anyio
    async def test_search_persons_with_fields(self, srv: FastMCP) -> None:
        body = {"items": [{"id": "p1", "displayName": "Alice", "personType": "AGENT"}]}
        with patch.object(httpx.AsyncClient, "request", return_value=httpx.Response(200, json=body)):
            result = await srv.call_tool("search_persons", {"fields": ["id", "displayName"]})
        data = result.structured_content
        assert data is not None
        items = data["items"]
        assert len(items) == 1
        assert items[0]["id"] == "p1"
        assert "personType" not in items[0]

    @pytest.mark.anyio
    async def test_search_users_with_fields(self, srv: FastMCP) -> None:
        body = {"items": [{"id": "u1", "username": "bob", "email": "bob@example.com"}]}
        with patch.object(httpx.AsyncClient, "request", return_value=httpx.Response(200, json=body)):
            result = await srv.call_tool("search_users", {"fields": ["id", "username"]})
        data = result.structured_content
        assert data is not None
        items = data["items"]
        assert len(items) == 1
        assert items[0]["id"] == "u1"
        assert "email" not in items[0]

    @pytest.mark.anyio
    async def test_get_persons_batch_success(self, srv: FastMCP) -> None:
        uuid = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        person_body = {"id": uuid, "displayName": "Alice", "personType": "AGENT"}
        with patch.object(httpx.AsyncClient, "request", return_value=httpx.Response(200, json=person_body)):
            result = await srv.call_tool("get_persons", {"identifiers": [uuid]})
        data = result.structured_content
        assert data is not None
        assert data["total"] == 1
        assert data["succeeded"] == 1
        assert data["failed"] == 0
        assert data["entries"][0]["identifier"] == uuid
        assert data["entries"][0]["error"] is None

    @pytest.mark.anyio
    async def test_get_persons_batch_with_error(self, srv: FastMCP) -> None:
        with patch.object(httpx.AsyncClient, "request", return_value=httpx.Response(404, json={})):
            result = await srv.call_tool("get_persons", {"identifiers": ["bad-id@example.com"]})
        data = result.structured_content
        assert data is not None
        assert data["total"] == 1
        assert data["failed"] == 1
        assert data["entries"][0]["error"] is not None
