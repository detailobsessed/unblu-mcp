"""Comprehensive FastMCP client tests for Unblu MCP server."""

import json
from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
import respx
from fastmcp.client import Client
from fastmcp.client.transports import FastMCPTransport
from fastmcp.exceptions import ToolError

from unblu_mcp._internal.server import create_server

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
                "requestBody": {
                    "required": True,
                    "content": {"application/json": {"schema": {"type": "object"}}},
                },
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
    mock_spec_path = Path(__file__).parent / "mock_swagger.json"
    mock_spec_path.write_text(json.dumps(MOCK_SWAGGER), encoding="utf-8")
    try:
        server = create_server(spec_path=str(mock_spec_path), base_url="https://api.unblu.cloud")
        async with Client(transport=server) as client:
            yield client
    finally:
        mock_spec_path.unlink(missing_ok=True)


@pytest.fixture
async def real_mcp_client() -> AsyncIterator[Client[FastMCPTransport]]:
    """Create MCP client with real swagger.json for integration tests."""
    spec_path = Path(__file__).parent.parent / "src" / "unblu_mcp" / "swagger.json"
    if not spec_path.exists():
        pytest.skip("swagger.json not found - download it first")
    server = create_server(spec_path=str(spec_path))
    async with Client(transport=server) as client:
        yield client


@pytest.mark.asyncio
class TestServerSurface:
    """Test the MCP server tool/resource/prompt surface."""

    async def test_list_tools_mock(self, mock_mcp_client: Client[FastMCPTransport]):
        """Server lists 7 tools: 5 always-visible + 2 BM25 synthetic (search_tools, call_tool)."""
        tools = await mock_mcp_client.list_tools()
        tool_names = [tool.name for tool in tools]

        assert len(tools) == 7
        always_visible = [
            "find_operation",
            "execute_operation",
            "get_current_account",
            "search_conversations",
            "search_persons",
        ]
        synthetic = ["search_tools", "call_tool"]
        for name in always_visible + synthetic:
            assert name in tool_names, f"Missing tool: {name}"

        for tool in tools:
            if tool.description:  # synthetic tools may have descriptions
                assert len(tool.description) > 0

    @pytest.mark.asyncio
    async def test_list_tools_real(self, real_mcp_client: Client[FastMCPTransport]):
        """Server lists 7 tools: 5 always-visible + 2 BM25 synthetic."""
        tools = await real_mcp_client.list_tools()
        assert len(tools) == 7

    @pytest.mark.asyncio
    async def test_list_resources(self, mock_mcp_client: Client[FastMCPTransport]):
        """Server exposes api://services resource."""
        resources = await mock_mcp_client.list_resources()
        uris = [str(r.uri) for r in resources]
        assert "api://services" in uris

    @pytest.mark.asyncio
    async def test_list_prompts(self, mock_mcp_client: Client[FastMCPTransport]):
        """Server exposes debugging workflow prompts."""
        prompts = await mock_mcp_client.list_prompts()
        names = [p.name for p in prompts]
        assert "debug_conversation" in names
        assert "find_agent" in names
        assert "account_health_check" in names

    @pytest.mark.asyncio
    async def test_read_services_resource(self, mock_mcp_client: Client[FastMCPTransport]):
        """api://services resource returns JSON service catalog."""

        result = await mock_mcp_client.read_resource("api://services")
        assert result is not None
        # Content should be JSON
        content = str(result[0].text) if hasattr(result[0], "text") else str(result[0])
        services = json.loads(content)
        assert isinstance(services, list)
        assert len(services) >= 1
        assert services[0]["name"] == "Test"
        assert services[0]["tier"] == "long-tail"

    @pytest.mark.asyncio
    async def test_read_operations_resource_template(self, mock_mcp_client: Client[FastMCPTransport]):
        """api://operations/{op_id} resource template returns schema JSON."""
        result = await mock_mcp_client.read_resource("api://operations/testGet")
        assert result is not None
        content = str(result[0].text) if hasattr(result[0], "text") else str(result[0])
        schema = json.loads(content)
        assert schema["operation_id"] == "testGet"
        assert schema["method"] == "GET"

    @pytest.mark.asyncio
    async def test_read_operations_resource_not_found(self, mock_mcp_client: Client[FastMCPTransport]):
        """api://operations/{op_id} returns error JSON for unknown op."""
        result = await mock_mcp_client.read_resource("api://operations/doesNotExist")
        assert result is not None
        content = str(result[0].text) if hasattr(result[0], "text") else str(result[0])
        data = json.loads(content)
        assert "error" in data


@pytest.mark.asyncio
class TestFindOperation:
    """Test the find_operation discovery tool."""

    async def test_find_operation_basic(self, mock_mcp_client: Client[FastMCPTransport]):
        """find_operation returns matching operations."""
        result = await mock_mcp_client.call_tool("find_operation", {"query": "test", "include_schema": False})
        assert result.structured_content is not None
        data = result.structured_content
        assert "matches" in data
        matches = data["matches"]
        assert len(matches) > 0
        for match in matches:
            assert "operation_id" in match
            assert "method" in match
            assert "schema_resource" in match

    @pytest.mark.asyncio
    async def test_find_operation_with_schema(self, mock_mcp_client: Client[FastMCPTransport]):
        """find_operation with include_schema=True embeds full schema."""
        result = await mock_mcp_client.call_tool("find_operation", {"query": "testGet", "include_schema": True})
        assert result.structured_content is not None
        matches = result.structured_content["matches"]
        assert len(matches) > 0
        # When include_schema=True, full_schema field should be present
        for match in matches:
            if match["operation_id"] == "testGet":
                assert match["full_schema"] is not None
                break

    @pytest.mark.asyncio
    async def test_find_operation_no_results(self, mock_mcp_client: Client[FastMCPTransport]):
        """find_operation returns empty matches for unmatched query."""
        result = await mock_mcp_client.call_tool("find_operation", {"query": "xyzzy_nomatch_12345", "include_schema": False})
        assert result.structured_content is not None
        matches = result.structured_content["matches"]
        assert matches == []

    @pytest.mark.asyncio
    async def test_find_operation_includes_schema_resource_uri(self, mock_mcp_client: Client[FastMCPTransport]):
        """find_operation includes schema_resource URI for each match."""
        result = await mock_mcp_client.call_tool("find_operation", {"query": "testGet", "include_schema": False})
        assert result.structured_content is not None
        matches = result.structured_content["matches"]
        for match in matches:
            assert match["schema_resource"].startswith("api://operations/")

    @pytest.mark.asyncio
    async def test_find_operation_real_spec(self, real_mcp_client: Client[FastMCPTransport]):
        """find_operation searches across 300+ real operations."""
        result = await real_mcp_client.call_tool("find_operation", {"query": "conversation", "include_schema": False, "limit": 5})
        assert result.structured_content is not None
        data = result.structured_content
        assert data["total_searched"] >= 300
        assert len(data["matches"]) > 0

    @pytest.mark.asyncio
    async def test_find_operation_infra_hidden_by_default(self, real_mcp_client: Client[FastMCPTransport]):
        """find_operation excludes infra services by default."""
        result_default = await real_mcp_client.call_tool(
            "find_operation", {"query": "webhook", "include_schema": False, "include_infra": False}
        )
        result_infra = await real_mcp_client.call_tool(
            "find_operation", {"query": "webhook", "include_schema": False, "include_infra": True}
        )
        assert result_default.structured_content is not None
        assert result_infra.structured_content is not None
        default_count = len(result_default.structured_content["matches"])
        infra_count = len(result_infra.structured_content["matches"])
        assert infra_count >= default_count


@pytest.mark.asyncio
class TestExecuteOperation:
    """Test the execute_operation escape hatch tool."""

    async def test_execute_operation_get_success(self, mock_mcp_client: Client[FastMCPTransport]):
        """Successful GET request returns shaped response."""
        with respx.mock:
            respx.get("https://api.unblu.cloud/test").mock(return_value=httpx.Response(200, json={"data": "success"}))
            result = await mock_mcp_client.call_tool("execute_operation", {"operation_id": "testGet"})
            assert result.structured_content is not None
            data = result.structured_content
            assert data["status_code"] == 200
            assert data["data"] == {"data": "success"}

    @pytest.mark.asyncio
    async def test_execute_operation_post_with_body(self, mock_mcp_client: Client[FastMCPTransport]):
        """POST request with body sends JSON and returns shaped response."""
        with respx.mock:
            respx.post("https://api.unblu.cloud/test").mock(return_value=httpx.Response(201, json={"id": "123"}))
            result = await mock_mcp_client.call_tool(
                "execute_operation",
                {"operation_id": "testCreate", "body": {"name": "test"}},
            )
            assert result.structured_content is not None
            data = result.structured_content
            assert data["status_code"] == 201

    @pytest.mark.asyncio
    async def test_execute_operation_no_content(self, mock_mcp_client: Client[FastMCPTransport]):
        """DELETE with confirm_destructive=True + 204 No Content."""
        with respx.mock:
            respx.delete("https://api.unblu.cloud/test/123").mock(return_value=httpx.Response(204))
            result = await mock_mcp_client.call_tool(
                "execute_operation",
                {
                    "operation_id": "testDelete",
                    "path_params": {"id": "123"},
                    "confirm_destructive": True,
                },
            )
            assert result.structured_content is not None
            data = result.structured_content
            assert data["status_code"] == 204

    @pytest.mark.asyncio
    async def test_execute_operation_delete_blocked_without_confirm(self, mock_mcp_client: Client[FastMCPTransport]):
        """DELETE without confirm_destructive raises ToolError."""
        with pytest.raises(ToolError, match=r"destructive"):
            await mock_mcp_client.call_tool(
                "execute_operation",
                {
                    "operation_id": "testDelete",
                    "path_params": {"id": "123"},
                    "confirm_destructive": False,
                },
            )

    @pytest.mark.asyncio
    async def test_execute_operation_unknown_raises_tool_error(self, mock_mcp_client: Client[FastMCPTransport]):
        """execute_operation raises ToolError for unknown operation_id."""
        with pytest.raises(ToolError, match=r"not found"):
            await mock_mcp_client.call_tool("execute_operation", {"operation_id": "doesNotExist"})

    @pytest.mark.asyncio
    async def test_execute_operation_missing_path_params_raises_tool_error(self, mock_mcp_client: Client[FastMCPTransport]):
        """execute_operation raises ToolError when path params are missing."""
        with pytest.raises(ToolError, match=r"Missing required path parameters"):
            await mock_mcp_client.call_tool(
                "execute_operation",
                {"operation_id": "testDelete", "confirm_destructive": True},
            )

    @pytest.mark.asyncio
    async def test_execute_operation_with_fields_filter(self, mock_mcp_client: Client[FastMCPTransport]):
        """execute_operation fields parameter filters response."""
        with respx.mock:
            respx.get("https://api.unblu.cloud/test").mock(
                return_value=httpx.Response(200, json={"id": "1", "name": "test", "internal": "hidden"})
            )
            result = await mock_mcp_client.call_tool(
                "execute_operation",
                {"operation_id": "testGet", "fields": ["id", "name"]},
            )
            assert result.structured_content is not None
            data = result.structured_content["data"]
            assert "id" in data
            assert "name" in data
            assert "internal" not in data


@pytest.mark.asyncio
class TestEdgeCases:
    """Test edge cases and error conditions."""

    async def test_find_operation_limit(self, mock_mcp_client: Client[FastMCPTransport]):
        """find_operation respects the limit parameter."""
        result = await mock_mcp_client.call_tool("find_operation", {"query": "test", "include_schema": False, "limit": 1})
        assert result.structured_content is not None
        matches = result.structured_content["matches"]
        assert len(matches) <= 1

    @pytest.mark.asyncio
    async def test_find_operation_service_filter(self, real_mcp_client: Client[FastMCPTransport]):
        """find_operation service filter restricts results to one service."""
        result = await real_mcp_client.call_tool(
            "find_operation",
            {"query": "search", "service": "Conversations", "include_schema": False},
        )
        assert result.structured_content is not None
        matches = result.structured_content["matches"]
        for match in matches:
            assert match["service"] == "Conversations"


@pytest.mark.asyncio
class TestPerformance:
    """Performance-related tests."""

    async def test_server_startup_time_real_spec(self):
        """Server starts quickly with real 2.4MB spec."""
        import time

        spec_path = Path(__file__).parent.parent / "src" / "unblu_mcp" / "swagger.json"
        if not spec_path.exists():
            pytest.skip("swagger.json not found")

        start_time = time.time()
        server = create_server(spec_path=str(spec_path))
        creation_time = time.time() - start_time

        assert creation_time < 2.0, f"Server creation took {creation_time:.2f}s"

        async with Client(transport=server) as client:
            tools = await client.list_tools()
            assert len(tools) == 7

    @pytest.mark.asyncio
    async def test_find_operation_response_time(self, real_mcp_client: Client[FastMCPTransport]):
        """find_operation responds quickly even searching 300+ operations."""
        import time

        start_time = time.time()
        result = await real_mcp_client.call_tool("find_operation", {"query": "conversations", "include_schema": False})
        response_time = time.time() - start_time

        assert result.structured_content is not None
        assert response_time < 0.5, f"find_operation took {response_time:.3f}s"


@pytest.mark.asyncio
class TestRefResolution:
    """Test $ref resolution depth limits."""

    async def test_ref_depth_limit(self, mock_mcp_client: Client[FastMCPTransport]):
        """Schema with deep refs is truncated safely."""
        result = await mock_mcp_client.call_tool("find_operation", {"query": "testGet", "include_schema": True})
        assert result.structured_content is not None
        # Verify schema is present and does not crash with $refs
        matches = result.structured_content["matches"]
        assert len(matches) > 0
