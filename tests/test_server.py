"""Tests for the Unblu MCP server."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from unblu_mcp._internal.server import (
    OperationInfo,
    OperationSchema,
    ServiceInfo,
    UnbluAPIRegistry,
    create_server,
)

if TYPE_CHECKING:
    from fastmcp import FastMCP


@pytest.fixture(scope="module")
def swagger_spec() -> dict:
    """Load the swagger.json spec."""
    spec_path = Path(__file__).parent.parent / "swagger.json"
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
    spec_path = Path(__file__).parent.parent / "swagger.json"
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
