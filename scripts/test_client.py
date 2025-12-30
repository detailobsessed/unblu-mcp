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
import traceback
from pathlib import Path

from fastmcp import Client

from unblu_mcp._internal.cli import _create_server, _get_provider

_DESCRIPTION_MAX_LEN = 60


async def run_client(
    provider: str = "default",
    environment: str = "dev",
    k8s_config: str | None = None,
    tool: str | None = None,
) -> int:
    """
    Connect to an in-process unblu-mcp server, list available tools, optionally invoke a specified tool, and return an exit status.
    
    Parameters:
        provider (str): Provider identifier to build the server (e.g., "default" or "k8s").
        environment (str): Environment name used when building the provider (e.g., "dev").
        k8s_config (str | None): Path to a Kubernetes environments YAML file when using the "k8s" provider, or None to use defaults.
        tool (str | None): Name of a specific tool to invoke; if None, the function calls "list_services".
    
    Returns:
        int: Exit status code; `0` on success.
    """
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
            print(
                f"  - {t.name}: {t.description[:_DESCRIPTION_MAX_LEN]}..."
                if len(t.description) > _DESCRIPTION_MAX_LEN
                else f"  - {t.name}: {t.description}"
            )

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
    """
    Parse command-line arguments, run the test client against an in-process server, and return an appropriate exit code.
    
    If the provider is "k8s" and no --k8s-config is supplied, a default config path within the repository is used when present. Handles interruption and unexpected errors.
    
    Returns:
        int: Exit code — 0 on success, 130 if interrupted by the user (KeyboardInterrupt), 1 for other exceptions.
    """
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
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())