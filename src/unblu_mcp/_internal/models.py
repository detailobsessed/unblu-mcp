from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Shared base
# ---------------------------------------------------------------------------


class _NextSteps(BaseModel):
    """Mixin that adds next_steps hints to every response."""

    next_steps: list[str] = Field(
        default_factory=list,
        description="Suggested follow-up tool calls to continue your investigation.",
    )


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------


class OperationMatch(BaseModel):
    """A single matching API operation returned by find_operation."""

    operation_id: str = Field(description="Pass this to execute_operation() to run it.")
    method: str = Field(description="HTTP method: GET, POST, DELETE, etc.")
    path: str = Field(description="API path template (may contain {param} placeholders).")
    summary: str = Field(description="Short description of what this operation does.")
    service: str = Field(description="API service / tag this operation belongs to.")
    schema_resource: str = Field(
        description="MCP resource URI for the full resolved schema. Read this resource to get parameters and request body details.",
    )
    full_schema: dict[str, Any] | None = Field(
        default=None,
        description="Full resolved schema (parameters, request body, responses). "
        "Included when find_operation is called with include_schema=True.",
    )


class OperationSearchResult(_NextSteps):
    """Result from find_operation."""

    matches: list[OperationMatch] = Field(description="Ranked list of matching operations.")
    total_searched: int = Field(description="Total number of operations searched.")


# ---------------------------------------------------------------------------
# Account
# ---------------------------------------------------------------------------


class AccountInfo(_NextSteps):
    """Current Unblu account information."""

    id: str
    name: str | None = None
    next_steps: list[str] = Field(
        default_factory=lambda: [
            "Call search_conversations() to list active conversations.",
            "Call search_persons() to find agents or visitors.",
            "Call check_agent_availability() to see who is online.",
        ],
    )


# ---------------------------------------------------------------------------
# Conversations
# ---------------------------------------------------------------------------


class ConversationParticipant(BaseModel):
    """A participant in a conversation."""

    person_id: str
    participation_type: str | None = None
    state: str | None = None
    hidden: bool = False


class ConversationSummary(BaseModel):
    """Compact conversation info for list results."""

    id: str
    topic: str | None = None
    state: str = Field(description="EConversationState: CREATED, QUEUED, ACTIVE, UNASSIGNED, ENDED, etc.")
    created_at: int | None = Field(default=None, description="Unix ms timestamp.")
    ended_at: int | None = Field(default=None, description="Unix ms timestamp. Null if not ended.")
    awaited_person_type: str | None = Field(default=None, description="AGENT, VISITOR, or NONE.")
    participant_count: int = 0
    bot_participant_count: int = 0
    source_url: str | None = None


class ConversationPage(_NextSteps):
    """Paginated list of conversations."""

    items: list[Any]
    has_more: bool = False
    next_offset: int | None = Field(
        default=None,
        description="Pass as offset= on your next call to get the next page.",
    )


class ConversationDetail(_NextSteps):
    """Full conversation details for debugging."""

    id: str
    topic: str | None = None
    state: str
    created_at: int | None = None
    ended_at: int | None = None
    visibility: str | None = None
    locale: str | None = None
    awaited_person_type: str | None = None
    source_url: str | None = None
    source_id: str | None = None
    initial_engagement_type: str | None = None
    end_reason: str | None = None
    participants: list[ConversationParticipant] = Field(default_factory=list)
    bot_participant_count: int = 0
    metadata: dict[str, Any] | None = None
    gui_url: str | None = Field(default=None, description="Unblu admin console URL for this conversation.")


# ---------------------------------------------------------------------------
# Persons
# ---------------------------------------------------------------------------


class PersonSummary(BaseModel):
    """Compact person info for list results."""

    id: str
    display_name: str | None = None
    person_type: str | None = Field(default=None, description="AGENT, VISITOR, BOT, or SYSTEM.")
    email: str | None = None
    team_id: str | None = None
    authorization_role: str | None = None


class PersonPage(_NextSteps):
    """Paginated list of persons."""

    items: list[Any]
    has_more: bool = False
    next_offset: int | None = Field(
        default=None,
        description="Pass as offset= on your next call to get the next page.",
    )


class PersonDetail(_NextSteps):
    """Full person details for debugging."""

    id: str
    display_name: str | None = None
    person_type: str | None = None
    email: str | None = None
    phone: str | None = None
    username: str | None = None
    team_id: str | None = None
    labels: list[str] = Field(default_factory=list)
    note: str | None = None
    authorization_role: str | None = None
    source_id: str | None = None
    source_url: str | None = None
    gui_url: str | None = Field(default=None, description="Unblu admin console URL for this person.")


class PersonAmbiguousResult(_NextSteps):
    """Returned when get_person finds multiple candidates."""

    message: str = "Multiple persons matched. Call get_person() again with the exact person_id from candidates."
    candidates: list[PersonSummary]


# ---------------------------------------------------------------------------
# Users (admin accounts, distinct from Persons)
# ---------------------------------------------------------------------------


class UserSummary(BaseModel):
    """Compact user info for list results."""

    id: str
    username: str | None = None
    display_name: str | None = None
    email: str | None = None
    authorization_role: str | None = None


class UserPage(_NextSteps):
    """Paginated list of users."""

    items: list[Any]
    has_more: bool = False
    next_offset: int | None = Field(
        default=None,
        description="Pass as offset= on your next call to get the next page.",
    )


class UserDetail(_NextSteps):
    """Full user details."""

    id: str
    username: str | None = None
    display_name: str | None = None
    email: str | None = None
    phone: str | None = None
    team_id: str | None = None
    authorization_role: str | None = None
    virtual_user: bool | None = None
    externally_managed: bool | None = None
    gui_url: str | None = Field(default=None, description="Unblu admin console URL for this user.")


# ---------------------------------------------------------------------------
# Persons — batch lookup
# ---------------------------------------------------------------------------


class PersonBatchEntry(BaseModel):
    """One entry in a get_persons() batch result."""

    identifier: str = Field(description="The identifier that was looked up.")
    result: PersonDetail | PersonAmbiguousResult | None = None
    error: str | None = Field(default=None, description="Error message if the lookup failed.")


class PersonBatchResult(_NextSteps):
    """Result from get_persons() batch lookup."""

    entries: list[PersonBatchEntry]
    total: int = Field(description="Total number of identifiers requested.")
    succeeded: int = Field(description="Number of successful lookups.")
    failed: int = Field(description="Number of failed lookups (not found or error).")


# ---------------------------------------------------------------------------
# Availability
# ---------------------------------------------------------------------------


class AvailabilityInfo(_NextSteps):
    """Agent availability status."""

    named_area_site_id: str | None = None
    availability: str | None = Field(
        default=None,
        description="Raw availability value from the Unblu API.",
    )
    raw: dict[str, Any] = Field(
        default_factory=dict,
        description="Full raw availability response for additional fields.",
    )


# ---------------------------------------------------------------------------
# Mutations
# ---------------------------------------------------------------------------


class OperationResult(_NextSteps):
    """Result of a write operation (assign, end, etc.)."""

    success: bool
    message: str
    conversation_id: str | None = None


# ---------------------------------------------------------------------------
# Escape hatch (execute_operation)
# ---------------------------------------------------------------------------


class ExecuteResult(_NextSteps):
    """Result from execute_operation."""

    status_code: int
    data: Any = None
    has_more: bool | None = None
    next_offset: int | None = Field(
        default=None,
        description="Pass as offset= on your next call to get the next page.",
    )
    truncated: bool = False


# ---------------------------------------------------------------------------
# Deployment health check
# ---------------------------------------------------------------------------


class HealthCheck(BaseModel):
    """Result of a single deployment health sub-check."""

    name: str = Field(description="Check identifier (connectivity, license, product_version, bots, webhooks, interceptors, availability).")
    status: str = Field(description="OK, WARN, or ERROR.")
    message: str = Field(description="Human-readable result summary.")
    details: list[dict[str, Any]] | None = Field(
        default=None,
        description="Per-item breakdown (e.g., list of bots with their webhook_status).",
    )


class DeploymentHealthReport(_NextSteps):
    """Full health report from check_deployment_health()."""

    overall_status: str = Field(description="OK if all checks pass, WARN if any warn, ERROR if any error.")
    checks: list[HealthCheck] = Field(description="Individual check results in order.")
    ok_count: int = Field(description="Number of passing checks.")
    warn_count: int = Field(description="Number of warning checks.")
    error_count: int = Field(description="Number of failing checks.")
