#!/usr/bin/env python3
"""Analyze swagger.json structure for the MCP server."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path


def main() -> None:
    spec_path = Path(__file__).parent.parent / "src" / "unblu_mcp" / "swagger.json"
    with open(spec_path) as f:
        spec = json.load(f)

    # Get tag groups (x-tagGroups)
    tag_groups = spec.get("x-tagGroups", [])
    print("=== TAG GROUPS (x-tagGroups) ===")
    for group in tag_groups:
        print(f"\n{group['name']}:")
        for tag in group.get("tags", []):
            print(f"  - {tag}")

    # Analyze what we include vs exclude
    print("\n\n=== REGISTRY ANALYSIS ===")

    included_services: set[str] = set()
    excluded_services: set[str] = set()

    for tag in spec.get("tags", []):
        name = tag.get("name", "")
        if name.startswith("For ") or name == "Schemas":
            excluded_services.add(name)
        else:
            included_services.add(name)

    # Count operations per service
    ops_by_service: dict[str, list[str]] = defaultdict(list)
    excluded_ops: list[tuple[str, str]] = []

    for path, path_item in spec.get("paths", {}).items():
        for method, operation in path_item.items():
            if method in ("get", "post", "put", "delete", "patch"):
                op_id = operation.get("operationId", f"{method}_{path}")
                tags = operation.get("tags", ["Other"])
                primary_tag = tags[0] if tags else "Other"

                if primary_tag.startswith("For ") or primary_tag == "Schemas":
                    excluded_ops.append((op_id, primary_tag))
                else:
                    ops_by_service[primary_tag].append(op_id)

    print(f"\nIncluded services: {len(included_services)}")
    print(f"Excluded services: {len(excluded_services)}")
    print(f"Included operations: {sum(len(ops) for ops in ops_by_service.values())}")
    print(f"Excluded operations: {len(excluded_ops)}")

    print("\n\nExcluded services (webhooks/schemas):")
    for svc in sorted(excluded_services):
        print(f"  - {svc}")

    print("\n\n=== OPERATIONS BY SERVICE ===")
    for service in sorted(ops_by_service.keys()):
        ops = ops_by_service[service]
        print(f"\n{service} ({len(ops)} operations):")
        for op in sorted(ops):
            print(f"  - {op}")


if __name__ == "__main__":
    main()
