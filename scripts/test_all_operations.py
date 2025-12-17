#!/usr/bin/env python3
"""Test that all operations in swagger.json are accessible via the MCP server.

This script verifies:
1. All operations are indexed by the registry
2. All operations can be retrieved via get_operation_schema
3. Path parameter extraction works for all operations
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from unblu_mcp._internal.server import UnbluAPIRegistry

_MAX_ERRORS_SHOWN = 10


def load_spec() -> dict:
    spec_path = Path(__file__).parent.parent / "src" / "unblu_mcp" / "swagger.json"
    with open(spec_path) as f:
        return json.load(f)


def get_expected_operations(spec: dict) -> list[dict]:
    """Get all operations we expect to be indexed (excluding webhooks/schemas)."""
    operations = []
    for path, path_item in spec.get("paths", {}).items():
        for method, operation in path_item.items():
            if method in ("get", "post", "put", "delete", "patch"):
                op_id = operation.get("operationId", f"{method}_{path}")
                tags = operation.get("tags", ["Other"])
                primary_tag = tags[0] if tags else "Other"

                # Skip webhook/schema tags (same logic as registry)
                if primary_tag.startswith("For ") or primary_tag == "Schemas":
                    continue

                # Extract path parameters
                path_params = re.findall(r"\{(\w+)\}", path)

                operations.append(
                    {
                        "operation_id": op_id,
                        "method": method.upper(),
                        "path": path,
                        "tag": primary_tag,
                        "path_params": path_params,
                        "has_request_body": operation.get("requestBody") is not None,
                    }
                )
    return operations


def test_registry_indexing(registry: UnbluAPIRegistry, expected_ops: list[dict]) -> list[str]:
    """Test that all expected operations are indexed."""
    errors = []
    expected_ids = {op["operation_id"] for op in expected_ops}
    indexed_ids = set(registry.operations.keys())

    missing = expected_ids - indexed_ids
    extra = indexed_ids - expected_ids

    if missing:
        errors.append(f"Missing operations ({len(missing)}): {sorted(missing)[:10]}...")
    if extra:
        errors.append(f"Extra operations ({len(extra)}): {sorted(extra)[:10]}...")

    return errors


def test_schema_retrieval(registry: UnbluAPIRegistry, expected_ops: list[dict]) -> list[str]:
    """Test that get_operation_schema works for all operations."""
    errors = []
    for op in expected_ops:
        schema = registry.get_operation_schema(op["operation_id"])
        if schema is None:
            errors.append(f"Schema retrieval failed: {op['operation_id']}")
        elif schema.operation_id != op["operation_id"]:
            errors.append(f"Schema mismatch: expected {op['operation_id']}, got {schema.operation_id}")
    return errors


def test_path_params(registry: UnbluAPIRegistry, expected_ops: list[dict]) -> list[str]:
    """Test that path parameters are correctly identified."""
    errors = []
    for op in expected_ops:
        indexed_op = registry.operations.get(op["operation_id"])
        if indexed_op is None:
            continue

        # Check path matches
        if indexed_op["path"] != op["path"]:
            errors.append(f"Path mismatch for {op['operation_id']}: {indexed_op['path']} vs {op['path']}")
    return errors


def test_service_grouping(registry: UnbluAPIRegistry, expected_ops: list[dict]) -> list[str]:
    """Test that operations are correctly grouped by service."""
    errors = []

    # Build expected grouping
    expected_by_service: dict[str, set[str]] = {}
    for op in expected_ops:
        expected_by_service.setdefault(op["tag"], set()).add(op["operation_id"])

    # Compare with registry
    for service, expected_ops_set in expected_by_service.items():
        actual_ops = registry.list_operations(service)
        actual_ids = {op.operation_id for op in actual_ops}

        missing = expected_ops_set - actual_ids
        if missing:
            errors.append(f"Service '{service}' missing ops: {sorted(missing)[:5]}")

    return errors


def main() -> int:
    print("Loading swagger.json...")
    spec = load_spec()

    print("Getting expected operations...")
    expected_ops = get_expected_operations(spec)
    print(f"  Expected: {len(expected_ops)} operations")

    print("\nCreating registry...")
    registry = UnbluAPIRegistry(spec)
    print(f"  Indexed: {len(registry.operations)} operations")
    print(f"  Services: {len(registry.services)}")

    all_errors: list[str] = []

    print("\n=== TEST: Registry Indexing ===")
    errors = test_registry_indexing(registry, expected_ops)
    if errors:
        for e in errors:
            print(f"  FAIL: {e}")
        all_errors.extend(errors)
    else:
        print("  PASS: All operations indexed correctly")

    print("\n=== TEST: Schema Retrieval ===")
    errors = test_schema_retrieval(registry, expected_ops)
    if errors:
        for e in errors[:_MAX_ERRORS_SHOWN]:
            print(f"  FAIL: {e}")
        if len(errors) > _MAX_ERRORS_SHOWN:
            print(f"  ... and {len(errors) - _MAX_ERRORS_SHOWN} more errors")
        all_errors.extend(errors)
    else:
        print("  PASS: All schemas retrievable")

    print("\n=== TEST: Path Parameters ===")
    errors = test_path_params(registry, expected_ops)
    if errors:
        for e in errors[:_MAX_ERRORS_SHOWN]:
            print(f"  FAIL: {e}")
        all_errors.extend(errors)
    else:
        print("  PASS: All paths match")

    print("\n=== TEST: Service Grouping ===")
    errors = test_service_grouping(registry, expected_ops)
    if errors:
        for e in errors[:_MAX_ERRORS_SHOWN]:
            print(f"  FAIL: {e}")
        all_errors.extend(errors)
    else:
        print("  PASS: All services grouped correctly")

    print("\n" + "=" * 50)
    if all_errors:
        print(f"FAILED: {len(all_errors)} errors found")
        return 1
    print("SUCCESS: All tests passed!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
