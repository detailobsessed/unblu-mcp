"""Integration tests for MCP tools using FastMCP client.

These tests verify that all tools work correctly when called through the MCP protocol,
catching issues that unit tests might miss (like schema validation, serialization, etc.).
"""

import time
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
class TestFindOperation:
    """Integration tests for find_operation tool."""

    async def test_returns_matches(self, client: Client[FastMCPTransport]) -> None:
        """find_operation returns matches for a keyword."""
        result = await client.call_tool("find_operation", {"query": "accounts"})

        assert result.structured_content is not None
        matches = result.structured_content["matches"]
        assert isinstance(matches, list)
        assert len(matches) > 0

    async def test_match_structure(self, client: Client[FastMCPTransport]) -> None:
        """Each match has required fields."""
        result = await client.call_tool("find_operation", {"query": "accounts"})

        assert result.structured_content is not None
        for match in result.structured_content["matches"]:
            assert "operation_id" in match
            assert "method" in match
            assert "path" in match
            assert "summary" in match
            assert "service" in match
            assert "schema_resource" in match
            assert match["method"] in ("GET", "POST", "PUT", "DELETE", "PATCH")

    async def test_schema_resource_uri(self, client: Client[FastMCPTransport]) -> None:
        """Each match includes schema_resource URI."""
        result = await client.call_tool("find_operation", {"query": "accountsRead"})

        assert result.structured_content is not None
        matches = result.structured_content["matches"]
        assert len(matches) > 0
        for match in matches:
            assert match["schema_resource"].startswith("api://operations/")

    async def test_include_schema_true(self, client: Client[FastMCPTransport]) -> None:
        """include_schema=True embeds the full resolved schema."""
        result = await client.call_tool("find_operation", {"query": "accountsRead", "include_schema": True, "limit": 1})

        assert result.structured_content is not None
        matches = result.structured_content["matches"]
        assert len(matches) > 0
        first = matches[0]
        assert first["full_schema"] is not None
        assert "parameters" in first["full_schema"]

    async def test_include_schema_false(self, client: Client[FastMCPTransport]) -> None:
        """include_schema=False omits the full_schema field."""
        result = await client.call_tool("find_operation", {"query": "accountsRead", "include_schema": False})

        assert result.structured_content is not None
        for match in result.structured_content["matches"]:
            assert match["full_schema"] is None

    async def test_respects_limit(self, client: Client[FastMCPTransport]) -> None:
        """find_operation respects the limit parameter."""
        result = await client.call_tool("find_operation", {"query": "get", "limit": 3})

        assert result.structured_content is not None
        assert len(result.structured_content["matches"]) <= 3

    async def test_no_matches_returns_empty(self, client: Client[FastMCPTransport]) -> None:
        """find_operation returns empty matches for no results."""
        result = await client.call_tool("find_operation", {"query": "xyznonexistent123"})

        assert result.structured_content is not None
        assert result.structured_content["matches"] == []

    async def test_total_searched_reported(self, client: Client[FastMCPTransport]) -> None:
        """find_operation reports total_searched count."""
        result = await client.call_tool("find_operation", {"query": "accounts"})

        assert result.structured_content is not None
        assert "total_searched" in result.structured_content
        assert result.structured_content["total_searched"] >= 300

    async def test_service_filter(self, client: Client[FastMCPTransport]) -> None:
        """find_operation service filter restricts results."""
        result = await client.call_tool("find_operation", {"query": "search", "service": "Conversations"})

        assert result.structured_content is not None
        for match in result.structured_content["matches"]:
            assert match["service"] == "Conversations"

    async def test_infra_excluded_by_default(self, client: Client[FastMCPTransport]) -> None:
        """Infra services are excluded from find_operation by default."""
        result_default = await client.call_tool("find_operation", {"query": "webhook", "include_infra": False})
        result_infra = await client.call_tool("find_operation", {"query": "webhook", "include_infra": True})
        assert result_default.structured_content is not None
        assert result_infra.structured_content is not None
        default_count = len(result_default.structured_content["matches"])
        infra_count = len(result_infra.structured_content["matches"])
        assert infra_count >= default_count

    async def test_next_steps_provided(self, client: Client[FastMCPTransport]) -> None:
        """find_operation includes next_steps hints."""
        result = await client.call_tool("find_operation", {"query": "accounts"})

        assert result.structured_content is not None
        assert "next_steps" in result.structured_content
        assert len(result.structured_content["next_steps"]) > 0

    async def test_results_ordered_by_relevance(self, client: Client[FastMCPTransport]) -> None:
        """find_operation orders results by relevance."""
        result = await client.call_tool("find_operation", {"query": "accountsRead"})

        assert result.structured_content is not None
        matches = result.structured_content["matches"]
        assert len(matches) > 0
        # Exact match in operation_id should be first or near top
        top_ids = [m["operation_id"] for m in matches[:3]]
        assert any("accountsRead" in op_id for op_id in top_ids)


@pytest.mark.asyncio
class TestGetOperationSchema:
    """Integration tests for find_operation with include_schema=True (replaces get_operation_schema)."""

    async def test_returns_schema(self, client: Client[FastMCPTransport]) -> None:
        """find_operation with include_schema returns full schema."""
        result = await client.call_tool("find_operation", {"query": "accountsRead", "include_schema": True})

        assert result.structured_content is not None
        matches = result.structured_content["matches"]
        assert len(matches) > 0
        schema = matches[0]["full_schema"]
        assert schema is not None
        assert "operation_id" in schema

    async def test_schema_structure(self, client: Client[FastMCPTransport]) -> None:
        """Schema has all required fields."""
        result = await client.call_tool("find_operation", {"query": "accountsRead", "include_schema": True, "limit": 1})

        assert result.structured_content is not None
        schema = result.structured_content["matches"][0]["full_schema"]
        assert schema is not None
        assert "operation_id" in schema
        assert "method" in schema
        assert "path" in schema
        assert "summary" in schema
        assert "parameters" in schema

    async def test_parameters_resolved(self, client: Client[FastMCPTransport]) -> None:
        """Schema parameters have $refs resolved."""
        result = await client.call_tool("find_operation", {"query": "accountsRead", "include_schema": True, "limit": 1})

        assert result.structured_content is not None
        schema = result.structured_content["matches"][0]["full_schema"]
        assert schema is not None
        assert isinstance(schema["parameters"], list)

    async def test_unknown_operation_returns_empty(self, client: Client[FastMCPTransport]) -> None:
        """find_operation returns empty matches for unknown operation ID."""
        result = await client.call_tool("find_operation", {"query": "nonExistentOperation_xyz123"})

        assert result.structured_content is not None
        assert result.structured_content["matches"] == []

    async def test_error_suggests_search(self, client: Client[FastMCPTransport]) -> None:
        """When no matches found, next_steps suggests broader search."""
        result = await client.call_tool("find_operation", {"query": "nonExistentOperation_xyz123"})

        assert result.structured_content is not None
        next_steps = result.structured_content.get("next_steps", [])
        assert len(next_steps) > 0


@pytest.mark.asyncio
class TestExecuteOperation:
    """Integration tests for execute_operation tool."""

    async def test_get_request_success(self, client: Client[FastMCPTransport]) -> None:
        """execute_operation handles successful GET request."""
        with respx.mock:
            respx.get("https://test.unblu.cloud/app/rest/v4/accounts/123/read").mock(
                return_value=httpx.Response(200, json={"id": "123", "name": "Test Account"})
            )

            result = await client.call_tool(
                "execute_operation",
                {"operation_id": "accountsRead", "path_params": {"accountId": "123"}},
            )

            response = result.structured_content
            assert response is not None
            assert response["status_code"] == 200
            assert response["data"]["id"] == "123"

    async def test_post_request_with_body(self, client: Client[FastMCPTransport]) -> None:
        """execute_operation handles POST request with body."""
        with respx.mock:
            respx.post("https://test.unblu.cloud/app/rest/v4/accounts/create").mock(
                return_value=httpx.Response(201, json={"id": "new-123"})
            )

            result = await client.call_tool(
                "execute_operation",
                {"operation_id": "accountsCreate", "body": {"name": "New Account"}},
            )

            response = result.structured_content
            assert response is not None
            assert response["status_code"] == 201

    async def test_delete_requires_confirm(self, client: Client[FastMCPTransport]) -> None:
        """execute_operation blocks DELETE without confirm_destructive=True."""
        with pytest.raises(ToolError, match=r"destructive"):
            await client.call_tool(
                "execute_operation",
                {
                    "operation_id": "accountsDelete",
                    "path_params": {"accountId": "123"},
                    "confirm_destructive": False,
                },
            )

    async def test_delete_with_confirm_succeeds(self, client: Client[FastMCPTransport]) -> None:
        """execute_operation allows DELETE with confirm_destructive=True."""
        with respx.mock:
            respx.delete("https://test.unblu.cloud/app/rest/v4/accounts/123/delete").mock(return_value=httpx.Response(204))

            result = await client.call_tool(
                "execute_operation",
                {
                    "operation_id": "accountsDelete",
                    "path_params": {"accountId": "123"},
                    "confirm_destructive": True,
                },
            )

            response = result.structured_content
            assert response is not None
            assert response["status_code"] == 204

    async def test_error_response(self, client: Client[FastMCPTransport]) -> None:
        """execute_operation surfaces 4xx error responses."""
        with respx.mock:
            respx.get("https://test.unblu.cloud/app/rest/v4/accounts/notfound/read").mock(
                return_value=httpx.Response(404, json={"error": "Account not found"})
            )

            result = await client.call_tool(
                "execute_operation",
                {"operation_id": "accountsRead", "path_params": {"accountId": "notfound"}},
            )

            response = result.structured_content
            assert response is not None
            assert response["status_code"] == 404

    async def test_missing_path_params_raises_error(self, client: Client[FastMCPTransport]) -> None:
        """execute_operation raises ToolError when required path params are missing."""
        with pytest.raises(ToolError, match=r"Missing required path parameters"):
            await client.call_tool("execute_operation", {"operation_id": "accountsRead"})

    async def test_unknown_operation_raises_error(self, client: Client[FastMCPTransport]) -> None:
        """execute_operation raises ToolError for unknown operation."""
        with pytest.raises(ToolError, match=r"not found"):
            await client.call_tool("execute_operation", {"operation_id": "nonExistentOp"})

    async def test_connection_error_raises_tool_error(self, client: Client[FastMCPTransport]) -> None:
        """execute_operation raises ToolError on connection failure."""
        with respx.mock:
            respx.get("https://test.unblu.cloud/app/rest/v4/accounts/123/read").mock(side_effect=httpx.ConnectError("Connection refused"))

            with pytest.raises(ToolError, match=r"API request failed"):
                await client.call_tool(
                    "execute_operation",
                    {"operation_id": "accountsRead", "path_params": {"accountId": "123"}},
                )

    async def test_field_filtering(self, client: Client[FastMCPTransport]) -> None:
        """execute_operation filters response fields when requested."""
        with respx.mock:
            respx.get("https://test.unblu.cloud/app/rest/v4/accounts/123/read").mock(
                return_value=httpx.Response(
                    200,
                    json={"id": "123", "name": "Test", "description": "Long", "metadata": {}},
                )
            )

            result = await client.call_tool(
                "execute_operation",
                {
                    "operation_id": "accountsRead",
                    "path_params": {"accountId": "123"},
                    "fields": ["id", "name"],
                },
            )

            response = result.structured_content
            assert response is not None
            assert "id" in response["data"]
            assert "name" in response["data"]
            assert "description" not in response["data"]
            assert "metadata" not in response["data"]

    async def test_response_includes_next_steps(self, client: Client[FastMCPTransport]) -> None:
        """execute_operation includes next_steps hints."""
        with respx.mock:
            respx.get("https://test.unblu.cloud/app/rest/v4/accounts/123/read").mock(return_value=httpx.Response(200, json={"id": "123"}))

            result = await client.call_tool(
                "execute_operation",
                {"operation_id": "accountsRead", "path_params": {"accountId": "123"}},
            )

            assert result.structured_content is not None
            assert "next_steps" in result.structured_content

    async def test_response_truncation(self, client: Client[FastMCPTransport]) -> None:
        """execute_operation truncates large responses."""
        large_data = {"items": [{"id": str(i), "data": "x" * 100} for i in range(100)]}

        with respx.mock:
            respx.get("https://test.unblu.cloud/app/rest/v4/accounts/123/read").mock(return_value=httpx.Response(200, json=large_data))

            result = await client.call_tool(
                "execute_operation",
                {
                    "operation_id": "accountsRead",
                    "path_params": {"accountId": "123"},
                    "max_response_size": 500,
                },
            )

            response = result.structured_content
            assert response is not None
            assert response["truncated"] is True


@pytest.mark.asyncio
class TestToolAnnotations:
    """Test that tools have correct MCP annotations."""

    async def test_read_only_tools_annotated(self, client: Client[FastMCPTransport]) -> None:
        """Read-only tools have readOnlyHint=True."""
        tools = await client.list_tools()
        read_only = {
            "find_operation",
            "get_current_account",
            "search_conversations",
            "get_conversation",
            "search_persons",
            "get_person",
            "search_users",
            "get_user",
            "check_agent_availability",
            "search_named_areas",
            "check_deployment_health",
        }
        for tool in tools:
            if tool.name in read_only:
                assert tool.annotations is not None
                assert tool.annotations.readOnlyHint is True, f"{tool.name} should be read-only"

    async def test_end_conversation_is_destructive(self, client: Client[FastMCPTransport], server: FastMCP) -> None:
        """end_conversation has destructiveHint=True.

        Checks via BM25 search_tools (hidden tool discoverable by unique term 'irreversible'),
        with fallback to raw server tool list for robustness.
        """
        result = await client.call_tool("search_tools", {"query": "irreversible"})
        assert result.structured_content is not None
        tools_data = result.structured_content.get("result", [])
        if isinstance(tools_data, str):
            import json

            tools_data = json.loads(tools_data)
        end_conv = next((t for t in tools_data if isinstance(t, dict) and t.get("name") == "end_conversation"), None)
        if end_conv is None:
            raw = await server._local_provider.list_tools()
            end_conv_raw = next((t for t in raw if t.name == "end_conversation"), None)
            assert end_conv_raw is not None, "end_conversation not found in server tool registry"
            assert end_conv_raw.annotations is not None
            assert end_conv_raw.annotations.destructiveHint is True
        else:
            annotations = end_conv.get("annotations") or {}
            assert annotations.get("destructiveHint") is True

    async def test_assign_conversation_not_destructive(self, client: Client[FastMCPTransport], server: FastMCP) -> None:
        """assign_conversation is not destructive.

        Checks via BM25 search_tools (hidden tool discoverable by unique term 'reassign'),
        with fallback to raw server tool list for robustness.
        """
        result = await client.call_tool("search_tools", {"query": "reassign investigation"})
        assert result.structured_content is not None
        tools_data = result.structured_content.get("result", [])
        if isinstance(tools_data, str):
            import json

            tools_data = json.loads(tools_data)
        assign_conv = next((t for t in tools_data if isinstance(t, dict) and t.get("name") == "assign_conversation"), None)
        if assign_conv is None:
            raw = await server._local_provider.list_tools()
            assign_conv_raw = next((t for t in raw if t.name == "assign_conversation"), None)
            assert assign_conv_raw is not None, "assign_conversation not found in server tool registry"
            assert assign_conv_raw.annotations is not None
            assert assign_conv_raw.annotations.destructiveHint is not True
        else:
            annotations = assign_conv.get("annotations") or {}
            assert annotations.get("destructiveHint") is not True


@pytest.mark.asyncio
class TestEndToEndWorkflow:
    """Test realistic end-to-end debugging workflows."""

    async def test_discovery_workflow(self, client: Client[FastMCPTransport]) -> None:
        """Typical workflow: find_operation -> read resource -> execute_operation."""
        # Step 1: Find operations
        result = await client.call_tool("find_operation", {"query": "accountsRead", "include_schema": False, "limit": 5})
        assert result.structured_content is not None
        matches = result.structured_content["matches"]
        assert len(matches) > 0

        # Step 2: Get schema via resource
        first_op = matches[0]
        schema_result = await client.read_resource(first_op["schema_resource"])
        assert schema_result is not None

        # Step 3: Execute the operation with mock
        with respx.mock:
            path_url = first_op["path"].replace("{accountId}", "123")
            respx.request(
                first_op["method"],
                f"https://test.unblu.cloud/app/rest/v4{path_url}",
            ).mock(return_value=httpx.Response(200, json={"id": "123"}))

            exec_result = await client.call_tool(
                "execute_operation",
                {
                    "operation_id": first_op["operation_id"],
                    "path_params": {"accountId": "123"},
                },
            )
            assert exec_result.structured_content is not None

    async def test_search_conversations_workflow(self, client: Client[FastMCPTransport]) -> None:
        """Typical debugging: search conversations by status."""
        with respx.mock:
            respx.post("https://test.unblu.cloud/app/rest/v4/conversations/search").mock(
                return_value=httpx.Response(
                    200,
                    json={
                        "items": [
                            {"id": "c1", "state": "ACTIVE", "topic": "Help needed"},
                        ],
                        "offset": 0,
                        "limit": 25,
                        "total": 1,
                    },
                )
            )

            result = await client.call_tool("search_conversations", {"status": "ACTIVE", "limit": 10})

            assert result.structured_content is not None
            data = result.structured_content
            assert "items" in data
            assert "has_more" in data


@pytest.mark.asyncio
class TestCheckDeploymentHealth:
    """Integration tests for check_deployment_health tool."""

    BASE_URL = "https://test.unblu.cloud/app/rest/v4"

    def _responses(self, overrides: dict | None = None) -> dict:
        future_ms = int((time.time() + 90 * 86400) * 1000)
        defaults: dict = {
            "connectivity": httpx.Response(200, json={"id": "acc-1", "name": "Test Account"}),
            "license": httpx.Response(
                200,
                json={
                    "serverIdentifier": "test-server",
                    "currentLicense": {
                        "state": "ACTIVE",
                        "licenseId": "lic-123",
                        "expirationTimestamp": future_ms,
                    },
                },
            ),
            "version": httpx.Response(200, json={"version": "10.0.0"}),
            "bots": httpx.Response(
                200,
                json={
                    "items": [{"id": "bot-1", "name": "My Bot", "webhookStatus": "ACTIVE", "webhookEndpoint": "https://bot.example.com"}]
                },
            ),
            "webhooks": httpx.Response(
                200,
                json={"items": [{"id": "wh-1", "name": "My Webhook", "apiVersion": "V4", "endpoint": "https://wh.example.com"}]},
            ),
            "interceptors": httpx.Response(
                200,
                json={
                    "items": [
                        {"id": "ic-1", "name": "My Interceptor", "webhookStatus": "ACTIVE", "webhookEndpoint": "https://ic.example.com"}
                    ]
                },
            ),
            "availability": httpx.Response(200, json={"agentAvailability": "AVAILABLE"}),
        }
        if overrides:
            defaults.update(overrides)
        return defaults

    def _register(self, responses: dict) -> None:
        base = self.BASE_URL
        respx.get(f"{base}/accounts/getCurrentAccount").mock(return_value=responses["connectivity"])
        respx.get(f"{base}/global/read").mock(return_value=responses["license"])
        respx.get(f"{base}/global/productVersion").mock(return_value=responses["version"])
        respx.post(f"{base}/bots/search").mock(return_value=responses["bots"])
        respx.post(f"{base}/webhookregistrations/search").mock(return_value=responses["webhooks"])
        respx.post(f"{base}/messageinterceptors/search").mock(return_value=responses["interceptors"])
        respx.get(f"{base}/availability/getAgentAvailability").mock(return_value=responses["availability"])

    async def test_all_healthy_returns_ok(self, client: Client[FastMCPTransport]) -> None:
        """check_deployment_health returns OK when all checks pass."""
        with respx.mock:
            self._register(self._responses())
            result = await client.call_tool("check_deployment_health", {})

        assert result.structured_content is not None
        data = result.structured_content
        assert data["overall_status"] == "OK"
        assert data["ok_count"] == 7
        assert data["warn_count"] == 0
        assert data["error_count"] == 0
        assert len(data["checks"]) == 7

    async def test_check_structure(self, client: Client[FastMCPTransport]) -> None:
        """Each check has name, status, and message fields."""
        with respx.mock:
            self._register(self._responses())
            result = await client.call_tool("check_deployment_health", {})

        assert result.structured_content is not None
        for check in result.structured_content["checks"]:
            assert "name" in check
            assert "status" in check
            assert "message" in check
            assert check["status"] in ("OK", "WARN", "ERROR")

    async def test_all_check_names_present(self, client: Client[FastMCPTransport]) -> None:
        """All seven check names appear in the result."""
        with respx.mock:
            self._register(self._responses())
            result = await client.call_tool("check_deployment_health", {})

        assert result.structured_content is not None
        names = {c["name"] for c in result.structured_content["checks"]}
        assert names == {"connectivity", "license", "product_version", "bots", "webhooks", "interceptors", "availability"}

    async def test_inactive_bot_warns(self, client: Client[FastMCPTransport]) -> None:
        """Inactive bot webhookStatus triggers WARN overall status."""
        with respx.mock:
            self._register(
                self._responses({
                    "bots": httpx.Response(200, json={"items": [{"id": "bot-1", "name": "My Bot", "webhookStatus": "INACTIVE"}]}),
                })
            )
            result = await client.call_tool("check_deployment_health", {})

        assert result.structured_content is not None
        data = result.structured_content
        assert data["overall_status"] == "WARN"
        bots_check = next(c for c in data["checks"] if c["name"] == "bots")
        assert bots_check["status"] == "WARN"
        assert "INACTIVE" in bots_check["message"] or "not ACTIVE" in bots_check["message"]

    async def test_connectivity_error(self, client: Client[FastMCPTransport]) -> None:
        """HTTP 500 from connectivity check sets ERROR overall status."""
        with respx.mock:
            self._register(
                self._responses({
                    "connectivity": httpx.Response(500, json={"error": "Internal Server Error"}),
                })
            )
            result = await client.call_tool("check_deployment_health", {})

        assert result.structured_content is not None
        data = result.structured_content
        assert data["overall_status"] == "ERROR"
        conn = next(c for c in data["checks"] if c["name"] == "connectivity")
        assert conn["status"] == "ERROR"
        assert data["error_count"] >= 1

    async def test_expired_license_is_error(self, client: Client[FastMCPTransport]) -> None:
        """Expired license timestamp triggers ERROR in license check."""
        past_ms = int((time.time() - 5 * 86400) * 1000)
        with respx.mock:
            self._register(
                self._responses({
                    "license": httpx.Response(
                        200,
                        json={
                            "serverIdentifier": "test-server",
                            "currentLicense": {"state": "ACTIVE", "licenseId": "lic-123", "expirationTimestamp": past_ms},
                        },
                    ),
                })
            )
            result = await client.call_tool("check_deployment_health", {})

        assert result.structured_content is not None
        lic = next(c for c in result.structured_content["checks"] if c["name"] == "license")
        assert lic["status"] == "ERROR"
        assert "EXPIRED" in lic["message"]

    async def test_license_expiring_soon_warns(self, client: Client[FastMCPTransport]) -> None:
        """License expiring within 30 days triggers WARN."""
        soon_ms = int((time.time() + 10 * 86400) * 1000)
        with respx.mock:
            self._register(
                self._responses({
                    "license": httpx.Response(
                        200,
                        json={
                            "serverIdentifier": "test-server",
                            "currentLicense": {"state": "ACTIVE", "licenseId": "lic-123", "expirationTimestamp": soon_ms},
                        },
                    ),
                })
            )
            result = await client.call_tool("check_deployment_health", {})

        assert result.structured_content is not None
        lic = next(c for c in result.structured_content["checks"] if c["name"] == "license")
        assert lic["status"] == "WARN"

    async def test_unknown_license_state_warns(self, client: Client[FastMCPTransport]) -> None:
        """Unrecognised license state (not ACTIVE/VALID) triggers WARN."""
        with respx.mock:
            self._register(
                self._responses({
                    "license": httpx.Response(
                        200,
                        json={
                            "serverIdentifier": "test-server",
                            "currentLicense": {"state": "SUSPENDED"},
                        },
                    ),
                })
            )
            result = await client.call_tool("check_deployment_health", {})

        assert result.structured_content is not None
        lic = next(c for c in result.structured_content["checks"] if c["name"] == "license")
        assert lic["status"] == "WARN"

    async def test_no_bots_is_ok(self, client: Client[FastMCPTransport]) -> None:
        """Deployment with no bots configured is healthy."""
        with respx.mock:
            self._register(self._responses({"bots": httpx.Response(200, json={"items": []})}))
            result = await client.call_tool("check_deployment_health", {})

        assert result.structured_content is not None
        bots = next(c for c in result.structured_content["checks"] if c["name"] == "bots")
        assert bots["status"] == "OK"

    async def test_inactive_interceptor_warns(self, client: Client[FastMCPTransport]) -> None:
        """Inactive interceptor webhookStatus triggers WARN."""
        with respx.mock:
            self._register(
                self._responses({
                    "interceptors": httpx.Response(
                        200, json={"items": [{"id": "ic-1", "name": "My Interceptor", "webhookStatus": "INACTIVE"}]}
                    ),
                })
            )
            result = await client.call_tool("check_deployment_health", {})

        assert result.structured_content is not None
        ic = next(c for c in result.structured_content["checks"] if c["name"] == "interceptors")
        assert ic["status"] == "WARN"

    async def test_no_agents_available_warns(self, client: Client[FastMCPTransport]) -> None:
        """Unavailable agents triggers WARN (expected outside business hours)."""
        with respx.mock:
            self._register(
                self._responses({
                    "availability": httpx.Response(200, json={"agentAvailability": "UNAVAILABLE"}),
                })
            )
            result = await client.call_tool("check_deployment_health", {})

        assert result.structured_content is not None
        avail = next(c for c in result.structured_content["checks"] if c["name"] == "availability")
        assert avail["status"] == "WARN"

    async def test_global_read_failure_warns(self, client: Client[FastMCPTransport]) -> None:
        """HTTP error from /global/read produces WARN (not ERROR) for license check."""
        with respx.mock:
            self._register(
                self._responses({
                    "license": httpx.Response(403, json={"error": "Forbidden"}),
                })
            )
            result = await client.call_tool("check_deployment_health", {})

        assert result.structured_content is not None
        lic = next(c for c in result.structured_content["checks"] if c["name"] == "license")
        assert lic["status"] == "WARN"

    async def test_next_steps_lists_issues(self, client: Client[FastMCPTransport]) -> None:
        """Issues populate next_steps with ERROR/WARN prefixes."""
        with respx.mock:
            self._register(
                self._responses({
                    "connectivity": httpx.Response(503, json={"error": "Unavailable"}),
                })
            )
            result = await client.call_tool("check_deployment_health", {})

        assert result.structured_content is not None
        next_steps = result.structured_content.get("next_steps", [])
        assert len(next_steps) > 0
        assert any("[ERROR:connectivity]" in step for step in next_steps)

    async def test_next_steps_all_ok(self, client: Client[FastMCPTransport]) -> None:
        """When all checks pass, next_steps suggests further investigation."""
        with respx.mock:
            self._register(self._responses())
            result = await client.call_tool("check_deployment_health", {})

        assert result.structured_content is not None
        next_steps = result.structured_content.get("next_steps", [])
        assert len(next_steps) > 0
        assert any("passed" in step.lower() or "search_conversations" in step for step in next_steps)

    async def test_bot_details_in_response(self, client: Client[FastMCPTransport]) -> None:
        """Bot check details include name, id, webhook_status."""
        with respx.mock:
            self._register(self._responses())
            result = await client.call_tool("check_deployment_health", {})

        assert result.structured_content is not None
        bots = next(c for c in result.structured_content["checks"] if c["name"] == "bots")
        assert bots["details"] is not None
        bot = bots["details"][0]
        assert "name" in bot
        assert "id" in bot
        assert "webhook_status" in bot

    async def test_webhook_details_in_response(self, client: Client[FastMCPTransport]) -> None:
        """Webhook check details include name, id, api_version, endpoint."""
        with respx.mock:
            self._register(self._responses())
            result = await client.call_tool("check_deployment_health", {})

        assert result.structured_content is not None
        wh = next(c for c in result.structured_content["checks"] if c["name"] == "webhooks")
        assert wh["details"] is not None
        item = wh["details"][0]
        assert "name" in item
        assert "api_version" in item

    async def test_no_interceptors_is_ok(self, client: Client[FastMCPTransport]) -> None:
        """Deployment with no interceptors configured is healthy."""
        with respx.mock:
            self._register(self._responses({"interceptors": httpx.Response(200, json={"items": []})}))
            result = await client.call_tool("check_deployment_health", {})

        assert result.structured_content is not None
        ic = next(c for c in result.structured_content["checks"] if c["name"] == "interceptors")
        assert ic["status"] == "OK"

    async def test_no_webhooks_is_ok(self, client: Client[FastMCPTransport]) -> None:
        """Deployment with no webhook registrations configured is healthy."""
        with respx.mock:
            self._register(self._responses({"webhooks": httpx.Response(200, json={"items": []})}))
            result = await client.call_tool("check_deployment_health", {})

        assert result.structured_content is not None
        wh = next(c for c in result.structured_content["checks"] if c["name"] == "webhooks")
        assert wh["status"] == "OK"

    async def test_product_version_failure_warns(self, client: Client[FastMCPTransport]) -> None:
        """HTTP error from /global/productVersion produces WARN for product_version check."""
        with respx.mock:
            self._register(self._responses({"version": httpx.Response(403, json={"error": "Forbidden"})}))
            result = await client.call_tool("check_deployment_health", {})

        assert result.structured_content is not None
        ver = next(c for c in result.structured_content["checks"] if c["name"] == "product_version")
        assert ver["status"] == "WARN"

    async def test_availability_failure_warns(self, client: Client[FastMCPTransport]) -> None:
        """HTTP error from /availability endpoint produces WARN for availability check."""
        with respx.mock:
            self._register(self._responses({"availability": httpx.Response(503, json={"error": "Unavailable"})}))
            result = await client.call_tool("check_deployment_health", {})

        assert result.structured_content is not None
        avail = next(c for c in result.structured_content["checks"] if c["name"] == "availability")
        assert avail["status"] == "WARN"

    async def test_bots_failure_warns(self, client: Client[FastMCPTransport]) -> None:
        """HTTP error from /bots/search produces WARN for bots check."""
        with respx.mock:
            self._register(self._responses({"bots": httpx.Response(403, json={"error": "Forbidden"})}))
            result = await client.call_tool("check_deployment_health", {})

        assert result.structured_content is not None
        bots = next(c for c in result.structured_content["checks"] if c["name"] == "bots")
        assert bots["status"] == "WARN"

    async def test_network_error_caught(self, client: Client[FastMCPTransport]) -> None:
        """ConnectError on connectivity check is caught and reported as ERROR."""
        base = self.BASE_URL
        responses = self._responses()
        with respx.mock:
            respx.get(f"{base}/accounts/getCurrentAccount").mock(side_effect=httpx.ConnectError("Connection refused"))
            respx.get(f"{base}/global/read").mock(return_value=responses["license"])
            respx.get(f"{base}/global/productVersion").mock(return_value=responses["version"])
            respx.post(f"{base}/bots/search").mock(return_value=responses["bots"])
            respx.post(f"{base}/webhookregistrations/search").mock(return_value=responses["webhooks"])
            respx.post(f"{base}/messageinterceptors/search").mock(return_value=responses["interceptors"])
            respx.get(f"{base}/availability/getAgentAvailability").mock(return_value=responses["availability"])
            result = await client.call_tool("check_deployment_health", {})

        assert result.structured_content is not None
        conn = next(c for c in result.structured_content["checks"] if c["name"] == "connectivity")
        assert conn["status"] == "ERROR"
        assert "Connection failed" in conn["message"]
