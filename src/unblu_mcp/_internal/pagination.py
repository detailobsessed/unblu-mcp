from __future__ import annotations

from typing import Any


def build_query_body(
    offset: int = 0,
    limit: int = 25,
    search_filters: list[dict[str, Any]] | None = None,
    order_by: list[dict[str, Any]] | None = None,
    query_type: str = "Query",
) -> dict[str, Any]:
    """Build an Unblu search/query request body with pagination.

    Args:
        offset: Zero-based item offset for the current page.
        limit: Maximum number of items to return.
        search_filters: List of filter dicts (Unblu SearchFilter schema).
        order_by: List of order-by dicts (Unblu OrderBy schema).
        query_type: The $_type discriminator for the query body.

    Returns:
        Dict ready to pass as the JSON body to a search endpoint.
    """
    body: dict[str, Any] = {
        "$_type": query_type,
        "offset": offset,
        "limit": limit,
    }
    if search_filters:
        body["searchFilters"] = search_filters
    if order_by:
        body["orderBy"] = order_by
    return body


def parse_pagination(result: dict[str, Any]) -> tuple[bool, int | None]:
    """Extract pagination info from an Unblu search result.

    Args:
        result: Raw JSON response from an Unblu search endpoint.

    Returns:
        Tuple of (has_more, next_offset). next_offset is None when has_more is False.
    """
    has_more = bool(result.get("hasMoreItems"))
    next_offset: int | None = result.get("nextOffset") if has_more else None
    return has_more, next_offset


def make_string_filter(field: str, value: str, operator: str = "EQUALS") -> dict[str, Any]:
    """Build an Unblu string equality search filter.

    Args:
        field: The EConversationSearchFilterField / EPersonSearchFilterField value.
        value: The value to match.
        operator: String operator (EQUALS, CONTAINS, STARTS_WITH, etc.).

    Returns:
        SearchFilter dict.
    """
    return {
        "$_type": "StringSearchFilter",
        "field": field,
        "operator": {"$_type": "StringOperator", "type": operator, "value": value},
    }


def make_id_filter(field: str, value: str) -> dict[str, Any]:
    """Build an Unblu ID equality search filter."""
    return {
        "$_type": "IdSearchFilter",
        "field": field,
        "operator": {"$_type": "IdOperator", "type": "EQUALS", "value": value},
    }


def make_enum_filter(
    field: str,
    value: str,
    filter_type: str = "ConversationStateSearchFilter",
    operator_type: str = "EConversationStateOperator",
) -> dict[str, Any]:
    """Build an Unblu enum equality search filter."""
    return {
        "$_type": filter_type,
        "field": field,
        "operator": {"$_type": operator_type, "type": "EQUALS", "value": value},
    }
