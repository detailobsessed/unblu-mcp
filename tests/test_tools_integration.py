"""Integration tests for MCP tools using FastMCP client.

These tests verify that all tools work correctly when called through the MCP protocol,
catching issues that unit tests might miss (like schema validation, serialization, etc.).
"""

from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
import respx
from fastmcp import FastMCP
from fastmcp.client import Client
from fastmcp.client.transports import FastMCPTransport
from fastmcp.exceptions import ToolError

from unblu_mcp._internal.server import create_server


@pytest.fixture(scope="module")
def server() -> FastMCP:
    """Create server with real swagger.json."""
    spec_path = Path(__file__).parent.parent / "src" / "unblu_mcp" / "swagger.json"
    if not spec_path.exists():
        pytest.skip("swagger.json not found")
    return create_server(spec_path=spec_path, base_url="https://test.unblu.cloud/app/rest/v4")


@pytest.fixture
async def client(server: FastMCP) -> AsyncIterator[Client[FastMCPTransport]]:
    """Create MCP client connected to server."""
    async with Client(transport=server) as c:
        yield c


@pytest.mark.asyncio
class TestListServices:
    """Integration tests for list_services tool."""

    async def test_returns_services(self, client: Client[FastMCPTransport]) -> None:
        """list_services returns a list of services."""
        result = await client.call_tool("list_services", {})

        assert result.structured_content is not None
        services = result.structured_content["result"]
        assert isinstance(services, list)
        assert len(services) > 40  # Should have 40+ services

    async def test_service_structure(self, client: Client[FastMCPTransport]) -> None:
        """Each service has required fields."""
        result = await client.call_tool("list_services", {})

        assert result.structured_content is not None
        services = result.structured_content["result"]
        for service in services:
            assert "name" in service
            assert "description" in service
            assert "operation_count" in service
            assert isinstance(service["name"], str)
            assert isinstance(service["operation_count"], int)
            assert service["operation_count"] > 0

    async def test_known_services_present(self, client: Client[FastMCPTransport]) -> None:
        """Known Unblu services are present."""
        result = await client.call_tool("list_services", {})

        assert result.structured_content is not None
        service_names = [s["name"] for s in result.structured_content["result"]]
        assert "Accounts" in service_names
        assert "Conversations" in service_names
        assert "Users" in service_names
        assert "Bots" in service_names
        assert "Persons" in service_names

    async def test_excludes_webhook_services(self, client: Client[FastMCPTransport]) -> None:
        """Webhook/schema services are excluded."""
        result = await client.call_tool("list_services", {})

        assert result.structured_content is not None
        service_names = [s["name"] for s in result.structured_content["result"]]
        assert "For bots" not in service_names
        assert "For webhooks" not in service_names
        assert "Schemas" not in service_names


@pytest.mark.asyncio
class TestListOperations:
    """Integration tests for list_operations tool."""

    async def test_returns_operations(self, client: Client[FastMCPTransport]) -> None:
        """list_operations returns operations for a service."""
        result = await client.call_tool("list_operations", {"service": "Accounts"})

        assert result.structured_content is not None
        operations = result.structured_content["result"]
        assert isinstance(operations, list)
        assert len(operations) > 0

    async def test_operation_structure(self, client: Client[FastMCPTransport]) -> None:
        """Each operation has required fields."""
        result = await client.call_tool("list_operations", {"service": "Accounts"})

        assert result.structured_content is not None
        operations = result.structured_content["result"]
        for op in operations:
            assert "operation_id" in op
            assert "method" in op
            assert "path" in op
            assert "summary" in op
            assert op["method"] in ("GET", "POST", "PUT", "DELETE", "PATCH")

    async def test_case_insensitive_exact(self, client: Client[FastMCPTransport]) -> None:
        """list_operations works with exact case."""
        result = await client.call_tool("list_operations", {"service": "Accounts"})
        assert result.structured_content is not None
        assert len(result.structured_content["result"]) > 0

    async def test_case_insensitive_lowercase(self, client: Client[FastMCPTransport]) -> None:
        """list_operations works with lowercase."""
        result = await client.call_tool("list_operations", {"service": "accounts"})
        assert result.structured_content is not None
        assert len(result.structured_content["result"]) > 0

    async def test_case_insensitive_uppercase(self, client: Client[FastMCPTransport]) -> None:
        """list_operations works with uppercase."""
        result = await client.call_tool("list_operations", {"service": "ACCOUNTS"})
        assert result.structured_content is not None
        assert len(result.structured_content["result"]) > 0

    async def test_case_insensitive_mixed(self, client: Client[FastMCPTransport]) -> None:
        """list_operations works with mixed case."""
        result = await client.call_tool("list_operations", {"service": "aCcOuNtS"})
        assert result.structured_content is not None
        assert len(result.structured_content["result"]) > 0

    async def test_unknown_service_raises_error(self, client: Client[FastMCPTransport]) -> None:
        """list_operations raises ToolError for unknown service."""
        with pytest.raises(ToolError, match=r"Service 'NonExistent' not found"):
            await client.call_tool("list_operations", {"service": "NonExistent"})

    async def test_error_suggests_alternatives(self, client: Client[FastMCPTransport]) -> None:
        """Error message includes available services."""
        with pytest.raises(ToolError, match=r"Available services include"):
            await client.call_tool("list_operations", {"service": "NonExistent"})


@pytest.mark.asyncio
class TestSearchOperations:
    """Integration tests for search_operations tool."""

    async def test_finds_by_operation_id(self, client: Client[FastMCPTransport]) -> None:
        """search_operations finds operations by ID."""
        result = await client.call_tool("search_operations", {"query": "accountsRead"})

        assert result.structured_content is not None
        operations = result.structured_content["result"]
        assert len(operations) > 0
        assert any("accountsRead" in op["operation_id"] for op in operations)

    async def test_finds_by_keyword(self, client: Client[FastMCPTransport]) -> None:
        """search_operations finds operations by keyword."""
        result = await client.call_tool("search_operations", {"query": "conversation"})

        assert result.structured_content is not None
        operations = result.structured_content["result"]
        assert len(operations) > 0

    async def test_case_insensitive(self, client: Client[FastMCPTransport]) -> None:
        """search_operations is case-insensitive."""
        result_lower = await client.call_tool("search_operations", {"query": "account"})
        result_upper = await client.call_tool("search_operations", {"query": "ACCOUNT"})
        result_mixed = await client.call_tool("search_operations", {"query": "AcCoUnT"})

        # All should return results
        assert result_lower.structured_content is not None
        assert result_upper.structured_content is not None
        assert result_mixed.structured_content is not None
        assert len(result_lower.structured_content["result"]) > 0
        assert len(result_upper.structured_content["result"]) > 0
        assert len(result_mixed.structured_content["result"]) > 0

    async def test_respects_limit(self, client: Client[FastMCPTransport]) -> None:
        """search_operations respects the limit parameter."""
        result = await client.call_tool("search_operations", {"query": "get", "limit": 5})

        assert result.structured_content is not None
        operations = result.structured_content["result"]
        assert len(operations) <= 5

    async def test_empty_query_returns_all(self, client: Client[FastMCPTransport]) -> None:
        """search_operations with empty query returns all operations."""
        result = await client.call_tool("search_operations", {"query": "", "limit": 1000})

        assert result.structured_content is not None
        operations = result.structured_content["result"]
        # Should return many operations (up to limit)
        assert len(operations) > 100

    async def test_no_matches_returns_empty(self, client: Client[FastMCPTransport]) -> None:
        """search_operations returns empty list for no matches."""
        result = await client.call_tool("search_operations", {"query": "xyznonexistent123"})

        assert result.structured_content is not None
        operations = result.structured_content["result"]
        assert operations == []

    async def test_results_ordered_by_relevance(self, client: Client[FastMCPTransport]) -> None:
        """search_operations orders results by relevance."""
        result = await client.call_tool("search_operations", {"query": "accountsCreate"})

        assert result.structured_content is not None
        operations = result.structured_content["result"]
        assert len(operations) > 0
        # Exact match in operation_id should be first
        assert "accountsCreate" in operations[0]["operation_id"]


@pytest.mark.asyncio
class TestGetOperationSchema:
    """Integration tests for get_operation_schema tool."""

    async def test_returns_schema(self, client: Client[FastMCPTransport]) -> None:
        """get_operation_schema returns full schema."""
        result = await client.call_tool("get_operation_schema", {"operation_id": "accountsRead"})

        schema = result.structured_content
        assert schema is not None
        assert schema["operation_id"] == "accountsRead"

    async def test_schema_structure(self, client: Client[FastMCPTransport]) -> None:
        """Schema has all required fields."""
        result = await client.call_tool("get_operation_schema", {"operation_id": "accountsRead"})

        schema = result.structured_content
        assert schema is not None
        assert "operation_id" in schema
        assert "method" in schema
        assert "path" in schema
        assert "summary" in schema
        assert "description" in schema
        assert "parameters" in schema
        assert "request_body" in schema
        assert "responses" in schema

    async def test_parameters_resolved(self, client: Client[FastMCPTransport]) -> None:
        """Schema parameters have $refs resolved."""
        result = await client.call_tool("get_operation_schema", {"operation_id": "accountsRead"})

        schema = result.structured_content
        assert schema is not None
        # Parameters should be a list
        assert isinstance(schema["parameters"], list)
        # If there are parameters, they should have resolved structure
        for param in schema["parameters"]:
            assert "name" in param or "$ref" in param

    async def test_unknown_operation_raises_error(self, client: Client[FastMCPTransport]) -> None:
        """get_operation_schema raises ToolError for unknown operation."""
        with pytest.raises(ToolError, match=r"Operation 'nonExistentOp' not found"):
            await client.call_tool("get_operation_schema", {"operation_id": "nonExistentOp"})

    async def test_error_suggests_search(self, client: Client[FastMCPTransport]) -> None:
        """Error message suggests using search_operations."""
        with pytest.raises(ToolError, match=r"search_operations"):
            await client.call_tool("get_operation_schema", {"operation_id": "nonExistentOp"})


@pytest.mark.asyncio
class TestCallApi:
    """Integration tests for call_api tool."""

    async def test_get_request_success(self, client: Client[FastMCPTransport]) -> None:
        """call_api handles successful GET request."""
        with respx.mock:
            respx.get("https://test.unblu.cloud/app/rest/v4/accounts/123/read").mock(
                return_value=httpx.Response(200, json={"id": "123", "name": "Test Account"})
            )

            result = await client.call_tool(
                "call_api",
                {"operation_id": "accountsRead", "path_params": {"accountId": "123"}},
            )

            response = result.structured_content
            assert response is not None
            assert response["status"] == "success"
            assert response["status_code"] == 200
            assert response["data"]["id"] == "123"

    async def test_post_request_with_body(self, client: Client[FastMCPTransport]) -> None:
        """call_api handles POST request with body."""
        with respx.mock:
            respx.post("https://test.unblu.cloud/app/rest/v4/accounts/create").mock(
                return_value=httpx.Response(201, json={"id": "new-123"})
            )

            result = await client.call_tool(
                "call_api",
                {"operation_id": "accountsCreate", "body": {"name": "New Account"}},
            )

            response = result.structured_content
            assert response is not None
            assert response["status"] == "success"
            assert response["status_code"] == 201

    async def test_delete_request_no_content(self, client: Client[FastMCPTransport]) -> None:
        """call_api handles 204 No Content response."""
        with respx.mock:
            respx.delete("https://test.unblu.cloud/app/rest/v4/accounts/123/delete").mock(
                return_value=httpx.Response(204)
            )

            result = await client.call_tool(
                "call_api",
                {"operation_id": "accountsDelete", "path_params": {"accountId": "123"}},
            )

            response = result.structured_content
            assert response is not None
            assert response["status"] == "success"
            assert response["status_code"] == 204

    async def test_error_response(self, client: Client[FastMCPTransport]) -> None:
        """call_api handles error responses."""
        with respx.mock:
            respx.get("https://test.unblu.cloud/app/rest/v4/accounts/notfound/read").mock(
                return_value=httpx.Response(404, json={"error": "Account not found"})
            )

            result = await client.call_tool(
                "call_api",
                {"operation_id": "accountsRead", "path_params": {"accountId": "notfound"}},
            )

            response = result.structured_content
            assert response is not None
            assert response["status"] == "error"
            assert response["code"] == 404

    async def test_missing_path_params_raises_error(self, client: Client[FastMCPTransport]) -> None:
        """call_api raises ToolError when required path params are missing."""
        with pytest.raises(ToolError, match=r"Missing required path parameters"):
            await client.call_tool("call_api", {"operation_id": "accountsRead"})

    async def test_unknown_operation_raises_error(self, client: Client[FastMCPTransport]) -> None:
        """call_api raises ToolError for unknown operation."""
        with pytest.raises(ToolError, match=r"Operation 'nonExistentOp' not found"):
            await client.call_tool("call_api", {"operation_id": "nonExistentOp"})

    async def test_connection_error_raises_tool_error(self, client: Client[FastMCPTransport]) -> None:
        """call_api raises ToolError on connection failure."""
        with respx.mock:
            respx.get("https://test.unblu.cloud/app/rest/v4/accounts/123/read").mock(
                side_effect=httpx.ConnectError("Connection refused")
            )

            with pytest.raises(ToolError, match=r"API request failed"):
                await client.call_tool(
                    "call_api",
                    {"operation_id": "accountsRead", "path_params": {"accountId": "123"}},
                )

    async def test_field_filtering(self, client: Client[FastMCPTransport]) -> None:
        """call_api filters response fields when requested."""
        with respx.mock:
            respx.get("https://test.unblu.cloud/app/rest/v4/accounts/123/read").mock(
                return_value=httpx.Response(
                    200,
                    json={
                        "id": "123",
                        "name": "Test",
                        "description": "Long description",
                        "metadata": {"key": "value"},
                    },
                )
            )

            result = await client.call_tool(
                "call_api",
                {
                    "operation_id": "accountsRead",
                    "path_params": {"accountId": "123"},
                    "fields": ["id", "name"],
                },
            )

            response = result.structured_content
            assert response is not None
            assert response["status"] == "success"
            # Only requested fields should be present
            assert "id" in response["data"]
            assert "name" in response["data"]
            assert "description" not in response["data"]
            assert "metadata" not in response["data"]

    async def test_response_truncation(self, client: Client[FastMCPTransport]) -> None:
        """call_api truncates large responses when max_response_size is set."""
        large_data = {"items": [{"id": str(i), "data": "x" * 100} for i in range(100)]}

        with respx.mock:
            respx.get("https://test.unblu.cloud/app/rest/v4/accounts/123/read").mock(
                return_value=httpx.Response(200, json=large_data)
            )

            result = await client.call_tool(
                "call_api",
                {
                    "operation_id": "accountsRead",
                    "path_params": {"accountId": "123"},
                    "max_response_size": 500,
                },
            )

            response = result.structured_content
            assert response is not None
            assert response["status"] == "success"
            assert response["data"]["_truncated"] is True


@pytest.mark.asyncio
class TestToolAnnotations:
    """Test that tools have correct MCP annotations."""

    async def test_discovery_tools_are_read_only(self, client: Client[FastMCPTransport]) -> None:
        """Discovery tools should have readOnlyHint=True."""
        tools = await client.list_tools()

        read_only_tools = ["list_services", "list_operations", "search_operations", "get_operation_schema"]
        for tool in tools:
            if tool.name in read_only_tools:
                assert tool.annotations is not None
                assert tool.annotations.readOnlyHint is True, f"{tool.name} should be read-only"

    async def test_call_api_is_destructive(self, client: Client[FastMCPTransport]) -> None:
        """call_api should have destructiveHint=True."""
        tools = await client.list_tools()

        call_api_tool = next(t for t in tools if t.name == "call_api")
        assert call_api_tool.annotations is not None
        assert call_api_tool.annotations.destructiveHint is True


@pytest.mark.asyncio
class TestEndToEndWorkflow:
    """Test realistic end-to-end workflows."""

    async def test_discovery_workflow(self, client: Client[FastMCPTransport]) -> None:
        """Test the typical discovery workflow: services -> operations -> schema."""
        # Step 1: List services
        services_result = await client.call_tool("list_services", {})
        assert services_result.structured_content is not None
        services = services_result.structured_content["result"]
        assert len(services) > 0

        # Step 2: Pick a service and list its operations
        service_name = "Accounts"
        ops_result = await client.call_tool("list_operations", {"service": service_name})
        assert ops_result.structured_content is not None
        operations = ops_result.structured_content["result"]
        assert len(operations) > 0

        # Step 3: Get schema for first operation
        first_op_id = operations[0]["operation_id"]
        schema_result = await client.call_tool("get_operation_schema", {"operation_id": first_op_id})
        schema = schema_result.structured_content
        assert schema is not None
        assert schema["operation_id"] == first_op_id

    async def test_search_workflow(self, client: Client[FastMCPTransport]) -> None:
        """Test the search workflow: search -> schema -> call."""
        # Step 1: Search for operations
        search_result = await client.call_tool("search_operations", {"query": "account", "limit": 5})
        assert search_result.structured_content is not None
        operations = search_result.structured_content["result"]
        assert len(operations) > 0

        # Step 2: Get schema for a GET operation (to avoid needing body)
        get_ops = [op for op in operations if op["method"] == "GET"]
        if get_ops:
            op_id = get_ops[0]["operation_id"]
            schema_result = await client.call_tool("get_operation_schema", {"operation_id": op_id})
            assert schema_result.structured_content is not None
            assert schema_result.structured_content["operation_id"] == op_id
