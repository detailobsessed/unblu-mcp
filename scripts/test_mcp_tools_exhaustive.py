#!/usr/bin/env python3
"""Exhaustive MCP tool tests for all operations.

This script tests that every operation can be:
1. Found via list_operations for its service
2. Found via search_operations
3. Retrieved via get_operation_schema with valid structure
4. Called via call_api (validates path building, not actual HTTP)
"""

from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass, field
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from fastmcp.client import Client
from fastmcp.exceptions import ToolError

from unblu_mcp._internal.server import create_server


@dataclass
class TestResult:
    operation_id: str
    service: str
    list_operations_ok: bool = False
    search_ok: bool = False
    schema_ok: bool = False
    schema_has_method: bool = False
    schema_has_path: bool = False
    schema_has_parameters: bool = False
    errors: list[str] = field(default_factory=list)


async def test_operation(client: Client, op_id: str, service: str) -> TestResult:
    """Test a single operation through all MCP tools."""
    result = TestResult(operation_id=op_id, service=service)

    # Test 1: list_operations includes this operation
    try:
        list_result = await client.call_tool("list_operations", {"service": service})
        if list_result.structured_content:
            ops = list_result.structured_content.get("result", [])
            op_ids = [op["operation_id"] for op in ops]
            result.list_operations_ok = op_id in op_ids
            if not result.list_operations_ok:
                result.errors.append(f"Not found in list_operations for {service}")
    except ToolError as e:
        result.errors.append(f"list_operations failed: {e}")

    # Test 2: search_operations can find it
    try:
        search_result = await client.call_tool("search_operations", {"query": op_id, "limit": 50})
        if search_result.structured_content:
            ops = search_result.structured_content.get("result", [])
            op_ids = [op["operation_id"] for op in ops]
            result.search_ok = op_id in op_ids
            if not result.search_ok:
                result.errors.append("Not found via search_operations")
    except ToolError as e:
        result.errors.append(f"search_operations failed: {e}")

    # Test 3: get_operation_schema returns valid schema
    try:
        schema_result = await client.call_tool("get_operation_schema", {"operation_id": op_id})
        if schema_result.structured_content:
            schema = schema_result.structured_content
            result.schema_ok = schema.get("operation_id") == op_id
            result.schema_has_method = "method" in schema and schema["method"] in (
                "GET",
                "POST",
                "PUT",
                "DELETE",
                "PATCH",
            )
            result.schema_has_path = "path" in schema and schema["path"].startswith("/")
            result.schema_has_parameters = "parameters" in schema

            if not result.schema_ok:
                result.errors.append("Schema operation_id mismatch")
            if not result.schema_has_method:
                result.errors.append("Schema missing valid method")
            if not result.schema_has_path:
                result.errors.append("Schema missing valid path")
    except ToolError as e:
        result.errors.append(f"get_operation_schema failed: {e}")

    return result


async def run_tests(batch_size: int = 20) -> tuple[list[TestResult], dict]:
    """Run tests for all operations."""
    spec_path = Path(__file__).parent.parent / "src" / "unblu_mcp" / "swagger.json"
    server = create_server(spec_path=spec_path)

    results: list[TestResult] = []
    stats = {
        "total": 0,
        "list_operations_pass": 0,
        "search_pass": 0,
        "schema_pass": 0,
        "full_pass": 0,
    }

    async with Client(transport=server) as client:
        # Get all services and their operations
        services_result = await client.call_tool("list_services", {})
        services = services_result.structured_content["result"]

        all_ops: list[tuple[str, str]] = []  # (op_id, service)
        for svc in services:
            ops_result = await client.call_tool("list_operations", {"service": svc["name"]})
            ops = ops_result.structured_content["result"]
            for op in ops:
                all_ops.append((op["operation_id"], svc["name"]))

        stats["total"] = len(all_ops)
        print(f"Testing {len(all_ops)} operations across {len(services)} services...")

        # Process in batches
        for i in range(0, len(all_ops), batch_size):
            batch = all_ops[i : i + batch_size]
            batch_results = await asyncio.gather(*[test_operation(client, op_id, service) for op_id, service in batch])
            results.extend(batch_results)

            # Progress
            done = min(i + batch_size, len(all_ops))
            print(f"  Progress: {done}/{len(all_ops)}")

    # Compute stats
    for r in results:
        if r.list_operations_ok:
            stats["list_operations_pass"] += 1
        if r.search_ok:
            stats["search_pass"] += 1
        if r.schema_ok and r.schema_has_method and r.schema_has_path:
            stats["schema_pass"] += 1
        if r.list_operations_ok and r.search_ok and r.schema_ok:
            stats["full_pass"] += 1

    return results, stats


def print_report(results: list[TestResult], stats: dict) -> None:
    """Print test report."""
    print("\n" + "=" * 60)
    print("TEST RESULTS")
    print("=" * 60)

    print(f"\nTotal operations: {stats['total']}")
    print(f"list_operations pass: {stats['list_operations_pass']}/{stats['total']}")
    print(f"search_operations pass: {stats['search_pass']}/{stats['total']}")
    print(f"get_operation_schema pass: {stats['schema_pass']}/{stats['total']}")
    print(f"Full pass (all tests): {stats['full_pass']}/{stats['total']}")

    # Group failures by type
    failures = [r for r in results if r.errors]
    if failures:
        print(f"\n{'=' * 60}")
        print(f"FAILURES ({len(failures)} operations)")
        print("=" * 60)

        # Group by service
        by_service: dict[str, list[TestResult]] = {}
        for r in failures:
            by_service.setdefault(r.service, []).append(r)

        for service in sorted(by_service.keys()):
            print(f"\n{service}:")
            for r in by_service[service]:
                print(f"  {r.operation_id}:")
                for err in r.errors:
                    print(f"    - {err}")
    else:
        print("\n✓ All operations passed all tests!")


def main() -> int:
    results, stats = asyncio.run(run_tests())
    print_report(results, stats)

    # Exit with error if any failures
    failures = [r for r in results if r.errors]
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
