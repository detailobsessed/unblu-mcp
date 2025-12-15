"""Tests for the Unblu MCP server."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from unblu_mcp._internal.server import (
    OperationInfo,
    OperationSchema,
    ServiceInfo,
    UnbluAPIRegistry,
    _ServerHolder,
    create_server,
    get_server,
)

if TYPE_CHECKING:
    from fastmcp import FastMCP


@pytest.fixture(scope="module")
def swagger_spec() -> dict:
    """Load the swagger.json spec."""
    spec_path = Path(__file__).parent.parent / "src" / "unblu_mcp" / "swagger.json"
    if not spec_path.exists():
        pytest.skip("swagger.json not found")
    with open(spec_path, encoding="utf-8") as f:
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
        assert "conversationsGetById" in registry.operations or any(
            "conversation" in op_id.lower() for op_id in registry.operations
        )

    def test_list_operations_for_service(self, registry: UnbluAPIRegistry) -> None:
        """list_operations returns operations for a specific service."""
        ops = registry.list_operations("Conversations")
        assert len(ops) > 0
        assert all(isinstance(op, OperationInfo) for op in ops)

    def test_list_operations_unknown_service(self, registry: UnbluAPIRegistry) -> None:
        """list_operations returns empty list for unknown service."""
        ops = registry.list_operations("NonExistentService")
        assert ops == []

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
        assert schema.method in ("GET", "POST", "PUT", "DELETE", "PATCH")

    def test_get_operation_schema_unknown(self, registry: UnbluAPIRegistry) -> None:
        """get_operation_schema returns None for unknown operation."""
        schema = registry.get_operation_schema("nonExistentOperation")
        assert schema is None

    def test_operation_count_matches(self, registry: UnbluAPIRegistry) -> None:
        """Service operation_count matches actual operations."""
        for service in registry.list_services():
            ops = registry.list_operations(service.name)
            assert len(ops) == service.operation_count


class TestMCPServer:
    """Tests for the MCP server creation."""

    def test_server_creation(self, server: FastMCP) -> None:
        """Server is created successfully."""
        assert server is not None
        assert server.name == "unblu-mcp"

    def test_server_has_tools(self, server: FastMCP) -> None:
        """Server has the expected tools."""
        tools = server._tool_manager._tools
        expected_tools = [
            "list_services",
            "list_operations",
            "search_operations",
            "get_operation_schema",
            "call_api",
        ]
        for tool_name in expected_tools:
            assert tool_name in tools, f"Missing tool: {tool_name}"

    def test_server_tool_count(self, server: FastMCP) -> None:
        """Server has exactly 5 tools (progressive disclosure pattern)."""
        tools = server._tool_manager._tools
        assert len(tools) == 5


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

    def test_progressive_disclosure_ratio(self, registry: UnbluAPIRegistry) -> None:
        """Verify the token efficiency claim.

        Instead of 331 tool definitions, we expose 5 meta-tools.
        This is a ~98% reduction in initial tool definition tokens.
        """
        total_operations = len(registry.operations)
        meta_tools = 5
        reduction_ratio = (total_operations - meta_tools) / total_operations
        assert reduction_ratio > 0.98, f"Expected >98% reduction, got {reduction_ratio:.2%}"


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


class TestEunomiaIntegration:
    """Tests for Eunomia authorization middleware integration."""

    def test_create_server_with_policy_file(self, tmp_path: Path) -> None:
        """create_server accepts policy_file parameter."""
        # Create a minimal policy file
        policy_file = tmp_path / "test_policy.json"
        policy_file.write_text(
            json.dumps(
                {
                    "version": "1.0",
                    "name": "test-policy",
                    "default_effect": "allow",
                    "rules": [],
                }
            )
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
        _ServerHolder.instance = None

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
        _ServerHolder.instance = mock_server

        result = get_server()
        assert result == mock_server

        # Reset for other tests
        _ServerHolder.instance = None
