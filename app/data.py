"""Data access for the dashboard.

Tier and the display name come from the signed-in user's OIDC claims.
Weekly usage and the budget figures come from app/gateway.py.
"""

from dataclasses import dataclass
from datetime import datetime

from app.gateway import (
    get_cost_usage_limit_policy,
    get_integration_models,
    get_usage_limit_policy_entity,
    get_debug_trace,
    list_integrations,
    list_mcp_servers,
    resolve_workspace_id,
    start_debug_trace,
)


@dataclass
class DashboardData:
    username: str
    model_tier: str
    credit_alert_label: str | None
    credit_alert_value: str | None
    weekly_usage_label: str
    weekly_usage: str
    reset_period: str
    team: str
    budget_configured: bool
    budget_limit: float
    budget_used: float
    budget_unit: str
    debug_calls: list[dict]


@dataclass
class CatalogTabData:
    rows: list[dict]
    debug_calls: list[dict]


def get_display_name(claims: dict) -> str:
    """Return a display name from the access token's claims.

    `email_id` is this project's confirmed identity claim (see
    CLAUDE.md) — not a standard OIDC claim name.
    """
    return claims.get("email_id") or claims.get("name") or claims.get("email") or claims.get(
        "sub", "Unknown user"
    )


def get_model_tier(claims: dict) -> str:
    """Read the tier from the custom claim defaults.metadata.tier.

    NOTE: this is a custom claim, confirmed present on the access token
    (see CLAUDE.md). Standard OIDC does not carry it.
    """
    return claims.get("defaults", {}).get("metadata", {}).get("tier", "Unknown")


def get_workspace_slug(claims: dict) -> str | None:
    """Read the workspace from the custom claim portkey_workspace.

    NOTE: this is a custom claim, confirmed present on the access token
    (see CLAUDE.md). It is not a standard OIDC claim.
    """
    return claims.get("portkey_workspace")


def get_identity_local_part(claims: dict) -> str | None:
    """Return the identity claim's email, stripped from "@" onward.

    This is the matching convention given for usage-limit-policy
    entities: an entity's value_key is expected to equal this local part,
    not the full email address. Uses the same email-ish claims as
    get_display_name, but skips "name" — that claim is not an email.
    """
    identity = claims.get("email_id") or claims.get("email") or claims.get("sub")
    if not identity or "@" not in identity:
        return None
    return identity.split("@", 1)[0]


def format_friendly_datetime(iso_string: str | None) -> str | None:
    """Return a friendly date/time string from an ISO-8601 value, or None.

    e.g. "2026-12-01T00:00:00Z" -> "December 1, 2026 at 12:00 AM UTC".
    Falls back to the raw string if it doesn't parse — never raises.
    """
    if not iso_string:
        return None
    try:
        dt = datetime.fromisoformat(iso_string.replace("Z", "+00:00"))
    except ValueError:
        return iso_string
    return dt.strftime("%B %-d, %Y at %-I:%M %p UTC")


def get_claude_code_setup_steps() -> dict:
    """Step-by-step setup content for the Claude Code integration card.

    Step 1's table is deliberately blank — no real download links exist
    for the token helper yet. The settings.json block is the same across
    all four platform tabs (it's OS-independent); the placeholders
    (`XXX`, `<XXXX>`) are intentional, not real values, and are not filled
    in here.
    """
    settings_json = """{
  "apiKeyHelper": "XXX",
  "env": {
    "ANTHROPIC_BASE_URL": "https://<XXXX>",
    "ENABLE_TOOL_SEARCH": true,
    "ANTHROPIC_MODEL": "sonnet",
    "CLAUDE_CODE_EFFORT_LEVEL": "medium",
    "CLAUDE_CODE_SUBAGENT_MODEL": "sonnet",
    "CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS": "5",
    "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
    "CLAUDE_CODE_ENABLE_AWAY_SUMMARY": "0",
    "CLAUDE_CODE_USE_VERTEX": "0"
  }
}"""
    platforms = [
        {"id": "macos-arm", "label": "macOS (ARM)"},
        {"id": "macos-intel", "label": "macOS (Intel)"},
        {"id": "linux", "label": "Linux"},
        {"id": "windows", "label": "Windows"},
    ]
    return {
        "title": "Setup",
        "step1": {
            "title": "Step 1",
            "subtitle": "Download the token helper",
            # Blank for now — no real download links exist yet.
            "table_rows": [{}, {}],
        },
        "step2": {
            "title": "Step 2",
            "subtitle": "Install and configure",
            "description": (
                "Move the helper script to ~/.claude/, make it executable, "
                "then update ~/.claude/settings.json"
            ),
            "tabs": [
                {
                    "id": platform["id"],
                    "label": platform["label"],
                    "code_title": "Update ~/.claude/settings.json",
                    "code": settings_json,
                }
                for platform in platforms
            ],
        },
    }


def get_catalog_models(claims: dict) -> CatalogTabData:
    """Models approved for this workspace.

    GET /integrations lists the providers enabled for the resolved
    workspace, then GET /integrations/{slug}/models is called once per
    provider to get its models. Only enabled models are kept — confirmed
    against a real response that models have no `name` field, only
    `slug`; the "Model" column shows that. `price` in each model's
    pricing_config is shown as-is — the spec doesn't document its unit
    (per-token vs. per-million-tokens), so this isn't scaled or guessed
    at. Confirm the real unit once real numbers come back, before
    trusting the column headers' "/1M tokens" framing literally.
    """
    start_debug_trace()

    workspace_slug = get_workspace_slug(claims)
    workspace_id = resolve_workspace_id(workspace_slug) if workspace_slug else None

    integrations = list_integrations(workspace_id) or []
    rows = []
    for integration in integrations:
        slug = integration.get("slug")
        provider_name = integration.get("name")
        if not slug:
            continue
        for model in get_integration_models(slug) or []:
            if not model.get("enabled"):
                continue
            pay_as_you_go = (model.get("pricing_config") or {}).get("pay_as_you_go") or {}
            input_price = (pay_as_you_go.get("request_token") or {}).get("price")
            output_price = (pay_as_you_go.get("response_token") or {}).get("price")
            rows.append(
                {
                    "model": model.get("slug"),
                    "provider": provider_name,
                    "input_per_1m": input_price,
                    "output_per_1m": output_price,
                    # Rows are already filtered to enabled=true above, so
                    # this is always "enabled" — the key name itself, not
                    # the raw boolean value.
                    "status": "enabled",
                    "status_positive": True,
                }
            )

    return CatalogTabData(rows=rows, debug_calls=get_debug_trace())


def _is_positive_status(status: str | None) -> bool:
    """Return whether a status string should render as a green pill.

    A heuristic, not from the spec — McpServerListItem.status has no
    documented enum. Treat the common positive-sounding values as green;
    everything else (including values we haven't seen yet) is neutral.
    """
    return (status or "").strip().lower() in {"active", "enabled", "healthy", "connected"}


def get_catalog_mcp_tools(claims: dict) -> CatalogTabData:
    """MCP servers approved for this workspace.

    GET /mcp-servers, resolved-workspace-scoped like get_catalog_models.
    Field mapping is a first guess from the spec, not yet confirmed
    against a real response — check the debug panel before trusting it:
    Server=name, Auth=auth_type, Gateway URL=url, Status=status.
    """
    start_debug_trace()

    workspace_slug = get_workspace_slug(claims)
    workspace_id = resolve_workspace_id(workspace_slug) if workspace_slug else None

    servers = list_mcp_servers(workspace_id) or []
    rows = [
        {
            "server": server.get("name"),
            "auth": server.get("auth_type"),
            "gateway_url": server.get("url"),
            "status": server.get("status"),
            "status_positive": _is_positive_status(server.get("status")),
        }
        for server in servers
    ]
    return CatalogTabData(rows=rows, debug_calls=get_debug_trace())


def get_integration_tools() -> list[dict]:
    """Mock dev-tool integrations shown on the Integrations page.

    Each entry drives one tile and its setup card. `command` is illustrative —
    the real token-helper mechanics aren't built yet.
    """
    return [
        {
            "slug": "claude-code",
            "name": "Claude Code",
            "summary": "CLI coding agent",
            "warning": (
                "apiKeyHelper is bypassed if ANTHROPIC_API_KEY or ANTHROPIC_AUTH_TOKEN "
                "is set in your environment. Both env vars take precedence over the "
                "helper per Claude Code’s credential precedence rules. If either is "
                "set in your shell profile, unset it before running Claude Code with "
                "this recipe: unset ANTHROPIC_API_KEY ANTHROPIC_AUTH_TOKEN."
            ),
            "setup_steps": get_claude_code_setup_steps(),
        },
        {
            "slug": "cursor",
            "name": "Cursor",
            "summary": "AI code editor",
            "intro": "Point Cursor at AI Gateway using the token helper.",
            "command": "aigw token-helper install --tool cursor",
            "note": (
                "This writes a short-lived credential into Cursor's model "
                "provider settings so requests route through AI Gateway."
            ),
        },
        {
            "slug": "vscode",
            "name": "VS Code",
            "summary": "Editor extension",
            "intro": "Point the VS Code AI extension at AI Gateway using the token helper.",
            "command": "aigw token-helper install --tool vscode",
            "note": (
                "This writes a short-lived credential into the extension's "
                "settings so requests route through AI Gateway."
            ),
        },
    ]


def get_dashboard_data(claims: dict) -> DashboardData:
    start_debug_trace()

    name = get_display_name(claims)
    workspace_slug = get_workspace_slug(claims)

    # GET /policies/usage-limits's workspace_id param rejects the slug —
    # it wants the UUID. Resolve it once, reuse for both policy calls.
    workspace_id = resolve_workspace_id(workspace_slug) if workspace_slug else None

    policy = get_cost_usage_limit_policy(workspace_id) if workspace_id else None

    credit_alert_label = None
    credit_alert_value = None
    if policy and policy.get("credit_limit") is not None:
        alert_threshold = policy.get("alert_threshold")
        if alert_threshold is not None:
            credit_alert_label = "max/alert"
            credit_alert_value = f"{policy['credit_limit']} / {alert_threshold}"
        else:
            credit_alert_label = "max"
            credit_alert_value = str(policy["credit_limit"])

    # periodic_reset ("weekly" / "monthly") drives both the usage-tile
    # label and the reset-period text below — whatever the real policy
    # says, not a hard-coded "this week".
    periodic_reset = policy.get("periodic_reset") if policy else None
    weekly_usage_label = f"{periodic_reset.capitalize()} Usage" if periodic_reset else "Usage"

    next_reset_at = format_friendly_datetime(policy.get("next_usage_reset_at") if policy else None)
    if periodic_reset and next_reset_at:
        reset_period = f"{periodic_reset.capitalize()} on {next_reset_at}"
    elif periodic_reset:
        reset_period = periodic_reset.capitalize()
    else:
        reset_period = "Not configured"

    # The usage tile and the budget tile share one entity lookup — both
    # read current_usage from GET /policies/usage-limits/{id}/entities,
    # matched to the signed-in user. One call, not two.
    local_part = get_identity_local_part(claims)
    entity = get_usage_limit_policy_entity(policy["id"], local_part) if policy and local_part else None
    current_usage = entity.get("current_usage") if entity is not None else None

    weekly_usage = f"${current_usage:.2f}" if current_usage is not None else "<unresolved>"

    budget_configured = entity is not None
    budget_limit = policy["credit_limit"] if (policy and entity is not None) else 0.0
    budget_used = current_usage if current_usage is not None else 0.0

    debug_calls = get_debug_trace()
    debug_calls.append(
        {"title": "Computed: identity local part for entity matching", "value": local_part}
    )

    return DashboardData(
        username=name,
        model_tier=get_model_tier(claims),
        credit_alert_label=credit_alert_label,
        credit_alert_value=credit_alert_value,
        weekly_usage_label=weekly_usage_label,
        weekly_usage=weekly_usage,
        reset_period=reset_period,
        team=name,
        budget_configured=budget_configured,
        budget_limit=budget_limit,
        budget_used=budget_used,
        budget_unit="USD",
        debug_calls=debug_calls,
    )
