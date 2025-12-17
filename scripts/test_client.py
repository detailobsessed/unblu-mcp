#!/usr/bin/env python3
"""Test client for unblu-mcp server.

This script tests the MCP server by connecting as a client and calling tools.
Useful for debugging the server without needing Windsurf/Claude Desktop.

Usage:
    # Test with default provider (requires UNBLU_BASE_URL env var)
    uv run scripts/test_client.py

    # Test with K8s provider
    uv run scripts/test_client.py --provider k8s --environment t1

    # Test specific tools
    uv run scripts/test_client.py --provider k8s --environment t1 --tool list_services
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path


async def run_client(
    provider: str = "default",
    environment: str = "dev",
    k8s_config: str | None = None,
    tool: str | None = None,
) -> int:
    """Run the test client."""
    # Import here to avoid issues if fastmcp not installed
    from fastmcp import Client

    from unblu_mcp._internal.cli import _create_server, _get_provider

    # Build the provider
    provider_instance = _get_provider(provider, environment, k8s_config)

    # Create the server
    server = _create_server(provider=provider_instance)

    print(f"Connecting to unblu-mcp server (provider={provider}, environment={environment})...")

    # Use FastMCP's client to connect to our server directly (in-process)
    async with Client(server) as client:
        print("Connected!")

        # List available tools
        tools = await client.list_tools()
        print(f"\nAvailable tools ({len(tools)}):")
        for t in tools:
            print(f"  - {t.name}: {t.description[:60]}..." if len(t.description) > 60 else f"  - {t.name}: {t.description}")

        if tool:
            # Call specific tool
            print(f"\nCalling tool: {tool}")
            result = await client.call_tool(tool, {})
            print(f"Result:\n{result}")
        else:
            # Default: call list_services
            print("\nCalling list_services()...")
            result = await client.call_tool("list_services", {})
            print(f"Result:\n{result}")

    print("\nClient disconnected cleanly.")
    return 0


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Test client for unblu-mcp")
    parser.add_argument(
        "--provider",
        choices=["default", "k8s"],
        default="default",
        help="Connection provider (default: default)",
    )
    parser.add_argument(
        "--environment",
        default="dev",
        help="K8s environment (default: dev)",
    )
    parser.add_argument(
        "--k8s-config",
        default=None,
        help="Path to K8s environments YAML",
    )
    parser.add_argument(
        "--tool",
        default=None,
        help="Specific tool to call (default: list_services)",
    )
    args = parser.parse_args()

    # Default k8s-config path
    if args.provider == "k8s" and not args.k8s_config:
        default_config = Path(__file__).parent.parent / "config" / "k8s_environments.yaml"
        if default_config.exists():
            args.k8s_config = str(default_config)

    try:
        return asyncio.run(
            run_client(
                provider=args.provider,
                environment=args.environment,
                k8s_config=args.k8s_config,
                tool=args.tool,
            )
        )
    except KeyboardInterrupt:
        print("\nInterrupted.")
        return 130
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
