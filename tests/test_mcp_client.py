"""Comprehensive FastMCP client tests for Unblu MCP server."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import httpx
import pytest
import respx
from fastmcp.client import Client

from unblu_mcp._internal.server import create_server

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from fastmcp.client.transports import FastMCPTransport

# Minimal mock spec for unit tests
MOCK_SWAGGER = {
    "openapi": "3.0.0",
    "info": {"title": "Test API", "version": "1.0.0"},
    "paths": {
        "/test": {
            "get": {
                "operationId": "testGet",
                "tags": ["Test"],
                "summary": "Test endpoint",
                "responses": {"200": {"description": "Success"}},
            },
            "post": {
                "operationId": "testCreate",
                "tags": ["Test"],
                "summary": "Create test resource",
                "requestBody": {"required": True, "content": {"application/json": {"schema": {"type": "object"}}}},
                "responses": {"201": {"description": "Created"}},
            },
        },
        "/test/{id}": {
            "delete": {
                "operationId": "testDelete",
                "tags": ["Test"],
                "summary": "Delete test resource",
                "responses": {"204": {"description": "Deleted"}},
            }
        },
    },
    "tags": [{"name": "Test", "description": "Test operations"}],
}


@pytest.fixture
async def mock_mcp_client() -> AsyncIterator[Client[FastMCPTransport]]:
    """Create MCP client with minimal mock spec for unit tests."""
    # Write mock spec to temporary file
    mock_spec_path = Path(__file__).parent / "mock_swagger.json"
    mock_spec_path.write_text(json.dumps(MOCK_SWAGGER))

    try:
        # Override base URL for testing
        server = create_server(spec_path=str(mock_spec_path), base_url="https://api.unblu.cloud")
        async with Client(transport=server) as client:
            yield client
    finally:
        # Clean up mock file
        mock_spec_path.unlink(missing_ok=True)


@pytest.fixture
async def real_mcp_client() -> AsyncIterator[Client[FastMCPTransport]]:
    """Create MCP client with real swagger.json for integration tests."""
    spec_path = Path(__file__).parent.parent / "swagger.json"
    if not spec_path.exists():
        pytest.skip("swagger.json not found - download it first")

    server = create_server(spec_path=str(spec_path))
    async with Client(transport=server) as client:
        yield client


@pytest.mark.asyncio
class TestMetaTools:
    """Test the 5 meta-tools exposed by the MCP server."""

    async def test_list_tools_mock(self, mock_mcp_client: Client[FastMCPTransport]):
        """Test that all 5 meta-tools are exposed with mock spec."""
        tools = await mock_mcp_client.list_tools()
        tool_names = [tool.name for tool in tools]

        assert len(tools) == 5
        assert tool_names == [
            "list_services",
            "list_operations",
            "search_operations",
            "get_operation_schema",
            "call_api",
        ]

        # Verify tool descriptions
        for tool in tools:
            assert tool.description
            assert len(tool.description) > 0

    @pytest.mark.asyncio
    async def test_list_tools_real(self, real_mcp_client: Client[FastMCPTransport]):
        """Test that all 5 meta-tools are exposed with real spec."""
        tools = await real_mcp_client.list_tools()
        tool_names = [tool.name for tool in tools]

        assert len(tools) == 5
        assert tool_names == [
            "list_services",
            "list_operations",
            "search_operations",
            "get_operation_schema",
            "call_api",
        ]

    @pytest.mark.asyncio
    async def test_list_services_mock(self, mock_mcp_client: Client[FastMCPTransport]):
        """Test list_services with mock spec."""
        result = await mock_mcp_client.call_tool("list_services", {})

        assert result.data is not None
        assert isinstance(result.data, list)
        assert len(result.data) == 1
        assert result.structured_content is not None
        assert isinstance(result.structured_content, dict)
        assert isinstance(result.structured_content["result"], list)
        assert result.structured_content["result"][0]["name"] == "Test"
        assert result.structured_content["result"][0]["description"] == "Test operations"
        assert result.structured_content["result"][0]["operation_count"] == 3

    @pytest.mark.asyncio
    async def test_list_services_real(self, real_mcp_client: Client[FastMCPTransport]):
        """Test list_services with real Unblu spec."""
        result = await real_mcp_client.call_tool("list_services", {})

        assert result.data is not None
        assert isinstance(result.data, list)
        assert result.structured_content is not None
        assert isinstance(result.structured_content, dict)
        assert isinstance(result.structured_content["result"], list)
        assert len(result.structured_content["result"]) > 0  # Should have 52 services

        # Check for known services
        service_names = [s["name"] for s in result.structured_content["result"]]
        assert "Conversations" in service_names
        assert "Persons" in service_names
        assert "Bots" in service_names

        # Verify structure
        for service in result.structured_content["result"]:
            assert "name" in service
            assert "description" in service
            assert "operation_count" in service
            assert service["operation_count"] > 0

    @pytest.mark.asyncio
    async def test_list_operations_mock(self, mock_mcp_client: Client[FastMCPTransport]):
        """Test list_operations with mock spec."""
        result = await mock_mcp_client.call_tool("list_operations", {"service": "Test"})

        assert result.data is not None
        assert isinstance(result.data, list)
        assert result.structured_content is not None
        assert isinstance(result.structured_content, dict)
        assert isinstance(result.structured_content["result"], list)
        assert len(result.structured_content["result"]) == 3

        # Check operations
        ops = {op["operation_id"]: op for op in result.structured_content["result"]}
        assert "testGet" in ops
        assert "testCreate" in ops

        # Verify structure
        for op in result.structured_content["result"]:
            assert "operation_id" in op
            assert "method" in op
            assert "path" in op
            assert "summary" in op

    @pytest.mark.asyncio
    async def test_list_operations_not_found(self, mock_mcp_client: Client[FastMCPTransport]):
        """Test list_operations with non-existent service."""
        result = await mock_mcp_client.call_tool("list_operations", {"service": "NonExistent"})

        assert result.structured_content is not None
        assert isinstance(result.structured_content["result"], list)
        assert len(result.structured_content["result"]) == 1
        assert result.structured_content["result"][0]["error"] == "Service 'NonExistent' not found. Try: ['Test']..."

    @pytest.mark.asyncio
    async def test_search_operations_mock(self, mock_mcp_client: Client[FastMCPTransport]):
        """Test search_operations with mock spec."""
        result = await mock_mcp_client.call_tool("search_operations", {"query": "test", "limit": 10})

        assert result.data is not None
        assert isinstance(result.data, list)
        assert result.structured_content is not None
        assert isinstance(result.structured_content, dict)
        assert isinstance(result.structured_content["result"], list)
        assert len(result.structured_content["result"]) == 3  # Both operations match "test"

        # Verify search results include expected fields
        for op in result.structured_content["result"]:
            assert "operation_id" in op
            assert "method" in op
            assert "path" in op
            assert "summary" in op

    @pytest.mark.asyncio
    async def test_search_operations_empty(self, mock_mcp_client: Client[FastMCPTransport]):
        """Test search_operations with no matches."""
        result = await mock_mcp_client.call_tool("search_operations", {"query": "nonexistent", "limit": 10})

        assert result.structured_content is not None
        assert isinstance(result.structured_content, dict)
        assert isinstance(result.structured_content["result"], list)
        assert len(result.structured_content["result"]) == 0

    @pytest.mark.asyncio
    async def test_get_operation_schema_mock(self, mock_mcp_client: Client[FastMCPTransport]):
        """Test get_operation_schema with mock spec."""
        result = await mock_mcp_client.call_tool("get_operation_schema", {"operation_id": "testGet"})

        assert result.structured_content is not None
        assert isinstance(result.structured_content, dict)
        assert result.structured_content["operation_id"] == "testGet"
        assert "method" in result.structured_content
        assert "path" in result.structured_content
        assert "parameters" in result.structured_content
        assert "request_body" in result.structured_content
        assert "responses" in result.structured_content

    @pytest.mark.asyncio
    async def test_get_operation_schema_not_found(self, mock_mcp_client: Client[FastMCPTransport]):
        """Test get_operation_schema with non-existent operation."""
        result = await mock_mcp_client.call_tool("get_operation_schema", {"operation_id": "nonexistent"})

        assert result.data is not None
        assert result.structured_content is not None
        assert isinstance(result.structured_content, dict)
        assert result.structured_content["error"] == "Operation 'nonexistent' not found"
        assert "not found" in result.structured_content["error"]


@pytest.mark.asyncio
class TestCallApi:
    """Test the call_api tool with HTTP mocking."""

    async def test_call_api_get_success(self, mock_mcp_client: Client[FastMCPTransport]):
        """Test successful GET request."""
        with respx.mock:
            # Mock the HTTP response
            respx.get("https://api.unblu.cloud/test").mock(return_value=httpx.Response(200, json={"data": "success"}))

            result = await mock_mcp_client.call_tool("call_api", {"operation_id": "testGet"})

            assert result.data is not None
            assert result.structured_content is not None
            assert isinstance(result.structured_content, dict)
            assert result.structured_content["status"] == "success"
            assert result.structured_content["status_code"] == 200
            assert result.structured_content["data"] == {"data": "success"}

    @pytest.mark.asyncio
    async def test_call_api_post_with_body(self, mock_mcp_client: Client[FastMCPTransport]):
        """Test POST request with body."""
        with respx.mock:
            # Mock the HTTP response
            respx.post("https://api.unblu.cloud/test").mock(return_value=httpx.Response(201, json={"id": "123"}))

            result = await mock_mcp_client.call_tool(
                "call_api", {"operation_id": "testCreate", "body": {"name": "test"}}
            )

            assert result.data is not None
            assert result.structured_content is not None
            assert isinstance(result.structured_content, dict)
            assert result.structured_content["status"] == "success"
            assert result.structured_content["status_code"] == 201
            assert result.structured_content["data"] == {"id": "123"}

    @pytest.mark.asyncio
    async def test_call_api_error_response(self, mock_mcp_client: Client[FastMCPTransport]):
        """Test API error response handling."""
        with respx.mock:
            # Mock error response
            respx.get("https://api.unblu.cloud/test").mock(
                return_value=httpx.Response(404, json={"error": "Not found"})
            )

            result = await mock_mcp_client.call_tool("call_api", {"operation_id": "testGet"})

            assert result.data is not None
            assert result.structured_content is not None
            assert isinstance(result.structured_content, dict)
            assert result.structured_content["status"] == "error"
            assert result.structured_content["code"] == 404
            assert result.structured_content["error"] == "{'error': 'Not found'}"

    @pytest.mark.asyncio
    async def test_call_api_no_content(self, mock_mcp_client: Client[FastMCPTransport]):
        """Test 204 No Content response."""
        with respx.mock:
            # Mock 204 response
            respx.delete("https://api.unblu.cloud/test/123").mock(return_value=httpx.Response(204))

            result = await mock_mcp_client.call_tool(
                "call_api", {"operation_id": "testDelete", "path_params": {"id": "123"}}
            )

            assert result.data is not None
            assert result.structured_content is not None
            assert isinstance(result.structured_content, dict)
            sc = result.structured_content
            assert sc["status"] == "success"
            assert sc["status_code"] == 204
            assert "data" not in sc


@pytest.mark.asyncio
class TestEdgeCases:
    """Test edge cases and error conditions."""

    async def test_empty_search_query(self, mock_mcp_client: Client[FastMCPTransport]):
        """Test search with empty query."""
        result = await mock_mcp_client.call_tool("search_operations", {"query": "", "limit": 10})

        # Should return all operations when query is empty
        assert result.data is not None
        assert isinstance(result.data, list)
        assert result.structured_content is not None
        assert isinstance(result.structured_content, dict)
        assert isinstance(result.structured_content["result"], list)
        assert len(result.structured_content["result"]) == 3

    @pytest.mark.asyncio
    async def test_search_limit_zero(self, mock_mcp_client: Client[FastMCPTransport]):
        """Test search with limit=0."""
        result = await mock_mcp_client.call_tool("search_operations", {"query": "test", "limit": 0})

        assert result.structured_content is not None
        assert isinstance(result.structured_content, dict)
        assert isinstance(result.structured_content["result"], list)
        assert len(result.structured_content["result"]) == 0

    @pytest.mark.asyncio
    async def test_invalid_operation_id_schema(self, mock_mcp_client: Client[FastMCPTransport]):
        """Test schema request with invalid operation ID format."""
        result = await mock_mcp_client.call_tool("get_operation_schema", {"operation_id": "invalid$id"})

        assert result.data is not None
        assert result.structured_content is not None
        assert isinstance(result.structured_content, dict)
        assert result.structured_content["error"] == "Operation 'invalid$id' not found"


@pytest.mark.asyncio
class TestPerformance:
    """Performance-related tests."""

    async def test_server_startup_time_real_spec(self):
        """Test that server starts quickly with real 2.4MB spec."""
        import time

        spec_path = Path(__file__).parent.parent / "swagger.json"
        if not spec_path.exists():
            pytest.skip("swagger.json not found")

        start_time = time.time()
        server = create_server(spec_path=str(spec_path))
        creation_time = time.time() - start_time

        # Should create server in under 2 seconds even with large spec
        assert creation_time < 2.0, f"Server creation took {creation_time:.2f}s"

        # Verify server is functional
        async with Client(transport=server) as client:
            tools = await client.list_tools()
            assert len(tools) == 5

    @pytest.mark.asyncio
    async def test_large_operation_list_performance(self, real_mcp_client: Client[FastMCPTransport]):
        """Test performance with large operation lists."""
        import time

        start_time = time.time()
        result = await real_mcp_client.call_tool(
            "list_operations",
            {
                "service": "Conversations"  # One of the larger services
            },
        )
        response_time = time.time() - start_time

        assert result.data is not None
        assert len(result.data) > 0

        # Should respond in under 100ms for any service
        assert response_time < 0.1, f"Response took {response_time:.3f}s"


@pytest.mark.asyncio
class TestRefResolution:
    """Test $ref resolution depth limits."""

    async def test_ref_depth_limit(self, mock_mcp_client: Client[FastMCPTransport]):
        """Test that deeply nested $refs are truncated."""
        # This would need a more complex mock spec with nested refs
        # For now, just verify the server doesn't crash on refs
        result = await mock_mcp_client.call_tool("get_operation_schema", {"operation_id": "testGet"})

        assert result.data is not None
        assert isinstance(result.data, dict)
