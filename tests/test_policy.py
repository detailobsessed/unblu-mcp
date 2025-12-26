"""Tests for the default MCP policy file."""

import json
import re
from pathlib import Path

import pytest

# Load the policy file
POLICY_PATH = Path(__file__).parent.parent / "config" / "mcp_policies.json"
SWAGGER_PATH = Path(__file__).parent.parent / "src" / "unblu_mcp" / "swagger.json"


@pytest.fixture
def policy() -> dict:
    """Load the default policy."""
    with POLICY_PATH.open() as f:
        return json.load(f)


@pytest.fixture
def all_operation_ids() -> list[str]:
    """Get all operation IDs from swagger.json."""
    with SWAGGER_PATH.open() as f:
        swagger = json.load(f)

    operation_ids = []
    for path_data in swagger.get("paths", {}).values():
        for method_data in path_data.values():
            if isinstance(method_data, dict) and "operationId" in method_data:
                operation_ids.append(method_data["operationId"])
    return sorted(set(operation_ids))


class TestPolicyStructure:
    """Tests for policy file structure."""

    def test_policy_has_required_fields(self, policy: dict) -> None:
        """Policy has all required fields."""
        assert policy["version"] == "1.0"
        assert "name" in policy
        assert policy["default_effect"] == "deny"
        assert "rules" in policy
        assert len(policy["rules"]) >= 3

    def test_policy_has_discovery_rule(self, policy: dict) -> None:
        """Policy allows MCP discovery methods."""
        rule = next(r for r in policy["rules"] if r["name"] == "allow-discovery-tools")
        assert rule["effect"] == "allow"
        conditions = rule["resource_conditions"]
        mcp_methods = next(c for c in conditions if c["path"] == "attributes.mcp_method")
        assert "tools/list" in mcp_methods["value"]

    def test_policy_has_read_only_tools_rule(self, policy: dict) -> None:
        """Policy allows read-only discovery tools."""
        rule = next(r for r in policy["rules"] if r["name"] == "allow-read-only-tools")
        assert rule["effect"] == "allow"
        conditions = rule["resource_conditions"]
        tool_names = next(c for c in conditions if c["path"] == "attributes.tool_name")
        assert "list_services" in tool_names["value"]
        assert "get_operation_schema" in tool_names["value"]

    def test_policy_has_read_api_rule(self, policy: dict) -> None:
        """Policy allows read-only API calls."""
        rule = next(r for r in policy["rules"] if r["name"] == "allow-read-api-calls")
        assert rule["effect"] == "allow"
        conditions = rule["resource_conditions"]
        op_condition = next(c for c in conditions if c["path"] == "attributes.args.operation_id")
        assert op_condition["operator"] == "regex"

    def test_policy_has_deny_destructive_rule(self, policy: dict) -> None:
        """Policy denies destructive API calls."""
        rule = next(r for r in policy["rules"] if r["name"] == "deny-destructive-api-calls")
        assert rule["effect"] == "deny"
        conditions = rule["resource_conditions"]
        op_condition = next(c for c in conditions if c["path"] == "attributes.args.operation_id")
        assert op_condition["operator"] == "regex"


class TestPolicyPatterns:
    """Tests for policy regex patterns against actual operations."""

    def _get_allow_pattern(self, policy: dict) -> str:
        """Extract the allow regex pattern from policy."""
        rule = next(r for r in policy["rules"] if r["name"] == "allow-read-api-calls")
        conditions = rule["resource_conditions"]
        return next(c for c in conditions if c["path"] == "attributes.args.operation_id")["value"]

    def _get_deny_pattern(self, policy: dict) -> str:
        """Extract the deny regex pattern from policy."""
        rule = next(r for r in policy["rules"] if r["name"] == "deny-destructive-api-calls")
        conditions = rule["resource_conditions"]
        return next(c for c in conditions if c["path"] == "attributes.args.operation_id")["value"]

    def test_read_operations_allowed(self, policy: dict, all_operation_ids: list[str]) -> None:
        """Read-only operations match the allow pattern."""
        allow_pattern = re.compile(self._get_allow_pattern(policy))

        # These should all be allowed
        read_ops = [op for op in all_operation_ids if allow_pattern.match(op)]

        # Verify we have a reasonable number of read operations
        assert len(read_ops) >= 140, f"Expected at least 140 read ops, got {len(read_ops)}"

        # Spot check some expected read operations
        expected_allowed = [
            "accountsRead",
            "accountsSearch",
            "usersGetById",
            "conversationHistoryRead",
            "globalPing",
            "globalProductVersion",
        ]
        for op in expected_allowed:
            assert allow_pattern.match(op), f"{op} should match allow pattern"

    def test_destructive_operations_denied(self, policy: dict, all_operation_ids: list[str]) -> None:
        """Destructive operations match the deny pattern."""
        deny_pattern = re.compile(self._get_deny_pattern(policy))

        # These should all be denied
        destructive_ops = [op for op in all_operation_ids if deny_pattern.search(op)]

        # Verify we have a reasonable number of destructive operations
        assert len(destructive_ops) >= 100, f"Expected at least 100 destructive ops, got {len(destructive_ops)}"

        # Spot check some expected denied operations
        expected_denied = [
            "accountsCreate",
            "accountsDelete",
            "usersUpdate",
            "authenticatorLogin",
            "conversationsStartRecording",
            "invitationsRevoke",
        ]
        for op in expected_denied:
            assert deny_pattern.search(op), f"{op} should match deny pattern"

    def test_allow_pattern_takes_precedence(self, policy: dict, all_operation_ids: list[str]) -> None:
        """Operations matching allow pattern are allowed (allow rule evaluated first).

        Note: Some operations like 'botsSendPing' match both patterns.
        Since allow rule comes first in the policy, these are allowed.
        """
        allow_pattern = re.compile(self._get_allow_pattern(policy))
        deny_pattern = re.compile(self._get_deny_pattern(policy))

        # Count operations that match both patterns (these are allowed due to rule order)
        both_patterns = [op for op in all_operation_ids if allow_pattern.match(op) and deny_pattern.search(op)]

        # These are expected edge cases - operations ending in Ping but containing Send
        expected_both = [
            "botsSendPing",
            "customActionsSendPing",
            "externalMessengersSendPing",
            "fileUploadGlobalInterceptorsSendPing",
            "fileUploadInterceptorsSendPing",
            "messageInterceptorsSendPing",
            "suggestionSourcesSendPing",
            "webhookRegistrationsSendPing",
        ]
        for op in both_patterns:
            assert op in expected_both, f"Unexpected operation matching both patterns: {op}"

    def test_all_operations_covered(self, policy: dict, all_operation_ids: list[str]) -> None:
        """Every operation should match either allow or deny pattern."""
        allow_pattern = re.compile(self._get_allow_pattern(policy))
        deny_pattern = re.compile(self._get_deny_pattern(policy))

        uncovered = []
        for op in all_operation_ids:
            if not allow_pattern.match(op) and not deny_pattern.search(op):
                uncovered.append(op)

        assert not uncovered, f"Operations not covered by any pattern: {uncovered}"


class TestSpecificOperations:
    """Tests for specific operation classifications."""

    @pytest.mark.parametrize(
        "operation_id",
        [
            "accountsRead",
            "accountsReadMultiple",
            "accountsSearch",
            "accountsGetByName",
            "accountsGetCurrentAccount",
            "usersGetById",
            "usersSearch",
            "conversationsGetById",
            "conversationHistoryRead",
            "conversationHistorySearch",
            "teamsRead",
            "teamsSearch",
            "botsRead",
            "botsGetByName",
            "globalPing",
            "globalProductVersion",
            "availabilityGetAgentAvailability",
        ],
    )
    def test_read_operation_allowed(self, policy: dict, operation_id: str) -> None:
        """Specific read operations should be allowed."""
        rule = next(r for r in policy["rules"] if r["name"] == "allow-read-api-calls")
        conditions = rule["resource_conditions"]
        pattern = next(c for c in conditions if c["path"] == "attributes.args.operation_id")["value"]
        assert re.match(pattern, operation_id), f"{operation_id} should be allowed"

    @pytest.mark.parametrize(
        "operation_id",
        [
            "accountsCreate",
            "accountsDelete",
            "accountsUpdate",
            "usersCreate",
            "usersDelete",
            "usersUpdate",
            "conversationsSetVisibility",
            "authenticatorLogin",
            "authenticatorLogout",
            "authenticatorImpersonate",
            "invitationsRevoke",
            "invitationsForwardConversationToAgent",
            "conversationsStartRecording",
            "conversationsStopRecording",
            "botsCreate",
            "botsDelete",
            "botsSendMessage",
        ],
    )
    def test_destructive_operation_denied(self, policy: dict, operation_id: str) -> None:
        """Specific destructive operations should be denied."""
        rule = next(r for r in policy["rules"] if r["name"] == "deny-destructive-api-calls")
        conditions = rule["resource_conditions"]
        pattern = next(c for c in conditions if c["path"] == "attributes.args.operation_id")["value"]
        assert re.search(pattern, operation_id), f"{operation_id} should be denied"
