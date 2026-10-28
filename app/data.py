"""Data access for the dashboard.

This module is a placeholder seam: it returns mock values today, shaped the
way the real gateway API responses are shaped (see knowledge/ for the spec).
When auth and the trust model are decided, the functions here get replaced
with real calls through a single gateway client — nothing else in the app
should need to change.
"""

from dataclasses import dataclass


@dataclass
class DashboardData:
    username: str
    model_tier: str
    weekly_usage: str
    reset_period: str
    team: str
    budget_limit: float
    budget_used: float
    budget_unit: str


def get_current_user() -> dict:
    """Stand-in for the signed-in user's key/session record.

    Shaped after ApiKeyObject from the gateway spec: `defaults.metadata` is
    where workspace admins put custom key/value pairs, including the
    `model_tier` convention used on the dashboard.
    """
    return {
        "user_id": "demo-user",
        "name": "Jordan Rivera",
        "workspace_id": "demo-workspace",
        "defaults": {
            "metadata": {
                "model_tier": "tier1",
            },
        },
    }


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
            "intro": "Point Claude Code at AI Gateway using the token helper.",
            "command": "aigw token-helper install --tool claude-code",
            "note": (
                "This writes a short-lived credential into Claude Code's "
                "config so requests route through AI Gateway."
            ),
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


def get_dashboard_data() -> DashboardData:
    user = get_current_user()
    return DashboardData(
        username=user["name"],
        model_tier=user["defaults"]["metadata"]["model_tier"],
        weekly_usage="$42.17",
        reset_period="Every week on Monday 0 UTC",
        team=user["name"],
        budget_limit=200.00,
        budget_used=42.17,
        budget_unit="USD",
    )
