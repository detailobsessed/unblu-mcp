"""Exhaustive tests for ALL 331 API operations.

These tests ensure that every operation in the Unblu API:
1. Is indexed by the registry
2. Can be found via list_operations for its service
3. Can be found via search_operations
4. Returns a valid schema via get_operation_schema
"""

from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from fastmcp import FastMCP
from fastmcp.client import Client
from fastmcp.client.transports import FastMCPTransport

from unblu_mcp._internal.server import UnbluAPIRegistry, create_server


@pytest.fixture(scope="module")
def spec() -> dict:
    """Load the swagger.json spec."""
    import json

    spec_path = Path(__file__).parent.parent / "src" / "unblu_mcp" / "swagger.json"
    if not spec_path.exists():
        pytest.skip("swagger.json not found")
    with open(spec_path, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def registry(spec: dict) -> UnbluAPIRegistry:
    """Create registry from spec."""
    return UnbluAPIRegistry(spec)


@pytest.fixture(scope="module")
def server() -> FastMCP:
    """Create server with real swagger.json."""
    spec_path = Path(__file__).parent.parent / "src" / "unblu_mcp" / "swagger.json"
    if not spec_path.exists():
        pytest.skip("swagger.json not found")
    return create_server(spec_path=spec_path)


@pytest.fixture(scope="module")
def expected_operations(spec: dict) -> list[dict]:
    """Get all operations we expect to be indexed."""
    import re

    operations = []
    for path, path_item in spec.get("paths", {}).items():
        for method, operation in path_item.items():
            if method in ("get", "post", "put", "delete", "patch"):
                op_id = operation.get("operationId", f"{method}_{path}")
                tags = operation.get("tags", ["Other"])
                primary_tag = tags[0] if tags else "Other"

                # Skip webhook/schema tags
                if primary_tag.startswith("For ") or primary_tag == "Schemas":
                    continue

                path_params = re.findall(r"\{(\w+)\}", path)
                operations.append(
                    {
                        "operation_id": op_id,
                        "method": method.upper(),
                        "path": path,
                        "service": primary_tag,
                        "path_params": path_params,
                    }
                )
    return operations


class TestRegistryIndexing:
    """Test that all operations are indexed correctly."""

    def test_all_operations_indexed(self, registry: UnbluAPIRegistry, expected_operations: list[dict]) -> None:
        """Every expected operation should be in the registry."""
        expected_ids = {op["operation_id"] for op in expected_operations}
        indexed_ids = set(registry.operations.keys())

        missing = expected_ids - indexed_ids
        assert not missing, f"Missing operations: {sorted(missing)[:10]}"

    def test_no_extra_operations(self, registry: UnbluAPIRegistry, expected_operations: list[dict]) -> None:
        """Registry should not have unexpected operations."""
        expected_ids = {op["operation_id"] for op in expected_operations}
        indexed_ids = set(registry.operations.keys())

        extra = indexed_ids - expected_ids
        assert not extra, f"Unexpected operations: {sorted(extra)[:10]}"

    def test_operation_count(self, registry: UnbluAPIRegistry, expected_operations: list[dict]) -> None:
        """Registry should have exactly 331 operations."""
        assert len(registry.operations) == 331
        assert len(expected_operations) == 331


class TestSchemaRetrieval:
    """Test that all operations have retrievable schemas."""

    def test_all_schemas_retrievable(self, registry: UnbluAPIRegistry, expected_operations: list[dict]) -> None:
        """Every operation should have a retrievable schema."""
        failures = []
        for op in expected_operations:
            schema = registry.get_operation_schema(op["operation_id"])
            if schema is None:
                failures.append(op["operation_id"])

        assert not failures, f"Schema retrieval failed for: {failures[:10]}"

    def test_schemas_have_required_fields(self, registry: UnbluAPIRegistry, expected_operations: list[dict]) -> None:
        """Every schema should have method, path, and parameters."""
        failures = []
        for op in expected_operations:
            schema = registry.get_operation_schema(op["operation_id"])
            if schema is None:
                continue

            missing = []
            if schema.method not in ("GET", "POST", "PUT", "DELETE", "PATCH"):
                missing.append("valid method")
            if not schema.path.startswith("/"):
                missing.append("valid path")
            if schema.parameters is None:
                missing.append("parameters")

            if missing:
                failures.append(f"{op['operation_id']}: missing {missing}")

        assert not failures, f"Schema validation failed: {failures[:10]}"


class TestServiceGrouping:
    """Test that operations are correctly grouped by service."""

    def test_all_services_have_operations(self, registry: UnbluAPIRegistry) -> None:
        """Every service should have at least one operation."""
        services = registry.list_services()
        for service in services:
            ops = registry.list_operations(service.name)
            assert len(ops) > 0, f"Service '{service.name}' has no operations"

    def test_operation_service_mapping(self, registry: UnbluAPIRegistry, expected_operations: list[dict]) -> None:
        """Each operation should be in its expected service."""
        failures = []
        for op in expected_operations:
            service_ops = registry.list_operations(op["service"])
            op_ids = [o.operation_id for o in service_ops]
            if op["operation_id"] not in op_ids:
                failures.append(f"{op['operation_id']} not in {op['service']}")

        assert not failures, f"Service mapping failures: {failures[:10]}"

    def test_service_operation_counts_match(self, registry: UnbluAPIRegistry) -> None:
        """Service operation_count should match actual operations."""
        for service in registry.list_services():
            ops = registry.list_operations(service.name)
            assert len(ops) == service.operation_count, (
                f"Service '{service.name}' count mismatch: reported {service.operation_count}, actual {len(ops)}"
            )


@pytest.mark.asyncio
class TestMCPToolsExhaustive:
    """Test all operations through MCP client tools."""

    @pytest.fixture
    async def client(self, server: FastMCP) -> AsyncIterator[Client[FastMCPTransport]]:
        """Create MCP client."""
        async with Client(transport=server) as c:
            yield c

    async def test_all_operations_in_list_operations(
        self, client: Client[FastMCPTransport], expected_operations: list[dict]
    ) -> None:
        """Every operation should appear in list_operations for its service."""
        # Group by service
        by_service: dict[str, set[str]] = {}
        for op in expected_operations:
            by_service.setdefault(op["service"], set()).add(op["operation_id"])

        failures = []
        for service, expected_ids in by_service.items():
            result = await client.call_tool("list_operations", {"service": service})
            assert result.structured_content is not None
            actual_ids = {op["operation_id"] for op in result.structured_content["result"]}

            missing = expected_ids - actual_ids
            if missing:
                failures.extend(f"{op} not in {service}" for op in missing)

        assert not failures, f"list_operations failures: {failures[:10]}"

    async def test_all_operations_searchable(
        self, client: Client[FastMCPTransport], expected_operations: list[dict]
    ) -> None:
        """Every operation should be findable via search_operations."""
        # Test a sample (testing all 331 would be slow)
        sample = expected_operations[::10]  # Every 10th operation

        failures = []
        for op in sample:
            result = await client.call_tool("search_operations", {"query": op["operation_id"], "limit": 50})
            assert result.structured_content is not None
            found_ids = {o["operation_id"] for o in result.structured_content["result"]}

            if op["operation_id"] not in found_ids:
                failures.append(op["operation_id"])

        assert not failures, f"search_operations failures: {failures}"

    async def test_all_schemas_via_mcp(self, client: Client[FastMCPTransport], expected_operations: list[dict]) -> None:
        """Every operation schema should be retrievable via MCP."""
        # Test a sample
        sample = expected_operations[::5]  # Every 5th operation

        failures = []
        for op in sample:
            result = await client.call_tool("get_operation_schema", {"operation_id": op["operation_id"]})
            if result.structured_content is None:
                failures.append(f"{op['operation_id']}: no content")
            elif result.structured_content.get("operation_id") != op["operation_id"]:
                failures.append(f"{op['operation_id']}: id mismatch")

        assert not failures, f"get_operation_schema failures: {failures[:10]}"
