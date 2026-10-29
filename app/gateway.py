"""One client for the gateway's management and analytics APIs.

Auth and base-URL handling live here only, per CLAUDE.md. Two auth paths:

- Admin APIs (analytics, policies, and similar): a client-credentials
  token, fetched from AIGW_TOKEN_URL and cached until it expires.
- Config data scoped to one user: the signed-in user's own access token,
  forwarded as-is (see app/auth.py for why it's the access token, not the
  ID token). No function here uses this path yet; `get_with_user_jwt` is
  ready for the first endpoint that needs it.

The client-credentials exchange (POST AIGW_TOKEN_URL) is confirmed against
real docs, not assumed — see knowledge/admin-api-auth.md. Two details that
are easy to get wrong because they are not standard OAuth2:
- The client ID and secret go over HTTP Basic Auth, not as form fields.
- The request needs scope=tsg_id:<AIGW_TSG_ID> — the tenant the token
  will act on. Omitting it, or using the wrong tenant, is rejected.
Tokens last 15 minutes (expires_in in the response); this module reads
that value rather than hard-coding it.

Every real HTTP call this module makes is recorded to a per-request debug
trace (start_debug_trace/get_debug_trace), one entry per call, title
first — this is what the dashboard's collapsible debug panels show.
Bearer tokens and the client secret are never recorded: headers and the
Basic Auth credential are left out of every entry, and the token
endpoint's response has its access_token field redacted before recording.
"""

import contextvars
from datetime import datetime, timedelta, timezone

import httpx

from app.config import settings

_admin_token: str | None = None
_admin_token_expires_at: datetime | None = None

_debug_trace: contextvars.ContextVar[list[dict] | None] = contextvars.ContextVar(
    "aigw_debug_trace", default=None
)


def start_debug_trace() -> None:
    """Start a fresh trace of every real API call made from here on."""
    _debug_trace.set([])


def get_debug_trace() -> list[dict]:
    """Return the trace started by start_debug_trace(), or an empty list."""
    return _debug_trace.get() or []


def _record(title: str, **fields) -> None:
    trace = _debug_trace.get()
    if trace is not None:
        trace.append({"title": title, **fields})


def _get_json(url: str, title: str, *, headers: dict, params: dict | None = None) -> dict | None:
    """GET url, record the call, return parsed JSON on 2xx or None on any failure.

    Only params, the status code, and the body go into the debug trace —
    never headers, since the only header here is always the bearer token.
    """
    try:
        response = httpx.get(url, headers=headers, params=params, timeout=10.0)
    except httpx.HTTPError as exc:
        _record(title, params=params, error=str(exc))
        return None

    try:
        body = response.json()
    except ValueError:
        body = response.text

    _record(title, params=params, status_code=response.status_code, body=body)
    return body if response.is_success else None


def _get_admin_access_token() -> str:
    """Return a cached client-credentials token, fetching a new one if needed."""
    global _admin_token, _admin_token_expires_at

    now = datetime.now(timezone.utc)
    if _admin_token and _admin_token_expires_at and now < _admin_token_expires_at:
        return _admin_token

    url = settings.aigw_token_url
    data = {"grant_type": "client_credentials", "scope": f"tsg_id:{settings.aigw_tsg_id}"}
    try:
        response = httpx.post(
            url,
            auth=(settings.aigw_client_id, settings.aigw_client_secret),
            data=data,
            timeout=10.0,
        )
    except httpx.HTTPError as exc:
        _record(f"POST {url}", data=data, error=str(exc))
        raise

    try:
        body = response.json()
    except ValueError:
        body = response.text

    recorded_body = body
    if isinstance(body, dict) and "access_token" in body:
        recorded_body = {**body, "access_token": "<redacted>"}
    _record(f"POST {url}", data=data, status_code=response.status_code, body=recorded_body)

    response.raise_for_status()

    _admin_token = body["access_token"]
    expires_in = body.get("expires_in", 300)
    # Tokens last 15 minutes; refresh about a minute early, per the docs.
    _admin_token_expires_at = now + timedelta(seconds=max(expires_in - 60, 0))
    return _admin_token


def _start_of_this_week_utc() -> datetime:
    """Return this Monday 00:00 UTC, the start of the current budget window."""
    now = datetime.now(timezone.utc)
    return (now - timedelta(days=now.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0
    )


def get_weekly_cost(workspace_slug: str) -> float | None:
    """Return this week's total cost for the workspace, or None on failure.

    Calls GET /analytics/graphs/cost as an admin API, using the
    client-credentials token. Returns None rather than a guessed number if
    the call fails — the caller shows "Not configured" instead.
    """
    start = _start_of_this_week_utc()
    now = datetime.now(timezone.utc)
    try:
        token = _get_admin_access_token()
    except httpx.HTTPError:
        return None

    body = _get_json(
        f"{settings.aigw_base_url.rstrip('/')}/analytics/graphs/cost",
        "GET /analytics/graphs/cost",
        headers={"Authorization": f"Bearer {token}"},
        params={
            "workspace_slug": workspace_slug,
            "time_of_generation_min": start.isoformat(),
            "time_of_generation_max": now.isoformat(),
        },
    )
    if body is None:
        return None
    return body.get("summary", {}).get("total")


def resolve_workspace_id(workspace_slug: str) -> str | None:
    """Resolve a workspace slug (the portkey_workspace claim) to its UUID.

    GET /policies/usage-limits's workspace_id filter rejects a slug —
    confirmed by a real "Invalid value" response — it wants the UUID.
    The only place in the spec pairing a workspace's slug with its UUID
    is a deployment's `workspaces` list (GET /deployments/{id}), on
    AIGW_ADMIN_BASE_URL — a different host from AIGW_BASE_URL. Returns
    None if no deployment's workspace list contains a matching slug.
    """
    try:
        token = _get_admin_access_token()
    except httpx.HTTPError:
        return None

    list_body = _get_json(
        f"{settings.aigw_admin_base_url.rstrip('/')}/deployments",
        "GET /deployments",
        headers={"Authorization": f"Bearer {token}"},
        params={"workspace_slug": workspace_slug},
    )
    if list_body is None:
        return None

    for deployment in list_body.get("data", []):
        deployment_id = deployment.get("id")
        detail_body = _get_json(
            f"{settings.aigw_admin_base_url.rstrip('/')}/deployments/{deployment_id}",
            f"GET /deployments/{deployment_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        if detail_body is None:
            continue
        for workspace in detail_body.get("workspaces", []):
            if workspace.get("slug") == workspace_slug:
                return workspace.get("id")
    return None


def get_cost_usage_limit_policy(workspace_id: str) -> dict | None:
    """Return the workspace's first active cost-type usage-limit policy, or None.

    workspace_id must be the resolved UUID (see resolve_workspace_id), not
    the portkey_workspace slug — the endpoint rejects a slug outright.

    Calls GET /policies/usage-limits, filtered server-side with
    type=cost&status=active. Returns None on failure or if the workspace
    has no such policy — the caller shows "Not configured" instead of a
    guessed value.

    NOTE: if a workspace has more than one active cost policy, this
    returns whichever the API lists first. Picking the *right* one by
    matching its conditions/group_by against the signed-in user is the
    open "usage-limit-policy matching logic" item in CLAUDE.md — not
    solved here yet.
    """
    try:
        token = _get_admin_access_token()
    except httpx.HTTPError:
        return None

    body = _get_json(
        f"{settings.aigw_base_url.rstrip('/')}/policies/usage-limits",
        "GET /policies/usage-limits",
        headers={"Authorization": f"Bearer {token}"},
        params={"workspace_id": workspace_id, "type": "cost", "status": "active"},
    )
    if body is None:
        return None
    data = body.get("data", [])
    return data[0] if data else None


def get_usage_limit_policy_entity(policy_id: str, local_part: str) -> dict | None:
    """Return the usage-limit-policy entity matching local_part, or None.

    Calls GET /policies/usage-limits/{policy_id}/entities and matches
    client-side — the endpoint has no filter param for this.
    page_size=100, one page only: fine for a demo-scale entity list, not
    a full pagination loop.

    An entity's value_key is not just the identity's local part — a real
    example: "metadata._user:eric.partington+oktaeric". It carries a
    "<metadata key>:" prefix ahead of the value. Not documented in the
    spec; match on everything after the last ":" instead of exact
    equality, since the prefix itself isn't something this app controls
    or can predict.
    """
    try:
        token = _get_admin_access_token()
    except httpx.HTTPError:
        return None

    body = _get_json(
        f"{settings.aigw_base_url.rstrip('/')}/policies/usage-limits/{policy_id}/entities",
        f"GET /policies/usage-limits/{policy_id}/entities",
        headers={"Authorization": f"Bearer {token}"},
        params={"page_size": 100},
    )
    if body is None:
        return None
    for entity in body.get("data", []):
        key = entity.get("value_key") or ""
        if key.rsplit(":", 1)[-1] == local_part:
            return entity
    return None


def list_integrations(workspace_id: str | None) -> list[dict] | None:
    """Return the integrations (AI providers) list, or None on failure.

    GET /integrations lives on AIGW_ADMIN_BASE_URL — a different host from
    AIGW_BASE_URL, same as /deployments. Scoped to workspace_id when
    resolved (see resolve_workspace_id); called without it otherwise,
    which lists organisation-wide instead of workspace-scoped — visible
    in the debug trace either way, not silently different behavior.
    """
    try:
        token = _get_admin_access_token()
    except httpx.HTTPError:
        return None

    params = {"workspace_id": workspace_id} if workspace_id else None
    body = _get_json(
        f"{settings.aigw_admin_base_url.rstrip('/')}/integrations",
        "GET /integrations",
        headers={"Authorization": f"Bearer {token}"},
        params=params,
    )
    if body is None:
        return None
    return body.get("data", [])


def get_integration_models(slug: str) -> list[dict] | None:
    """Return the models configured for one integration (provider), or None.

    GET /integrations/{slug}/models, also on AIGW_ADMIN_BASE_URL. Not
    workspace-scoped itself — workspace scoping already happened at the
    /integrations list step.
    """
    try:
        token = _get_admin_access_token()
    except httpx.HTTPError:
        return None

    body = _get_json(
        f"{settings.aigw_admin_base_url.rstrip('/')}/integrations/{slug}/models",
        f"GET /integrations/{slug}/models",
        headers={"Authorization": f"Bearer {token}"},
    )
    if body is None:
        return None
    return body.get("models", [])


def list_mcp_servers(workspace_id: str | None) -> list[dict] | None:
    """Return the MCP servers list, or None on failure.

    GET /mcp-servers lives on AIGW_BASE_URL — unlike /integrations and
    /deployments, this one is not on the admin host. workspace_id here is
    unconfirmed: passed as the resolved UUID, on the same pattern as
    /policies/usage-limits's identically-named param, not verified
    against a real response yet.
    """
    try:
        token = _get_admin_access_token()
    except httpx.HTTPError:
        return None

    params = {"workspace_id": workspace_id} if workspace_id else None
    body = _get_json(
        f"{settings.aigw_base_url.rstrip('/')}/mcp-servers",
        "GET /mcp-servers",
        headers={"Authorization": f"Bearer {token}"},
        params=params,
    )
    if body is None:
        return None
    return body.get("data", [])


def get_with_user_jwt(path: str, access_token: str, params: dict | None = None) -> dict | None:
    """Call a gateway endpoint as the signed-in user, forwarding their access token.

    For config data scoped to one user, where the gateway's own
    authorization for that user's workspace should apply — not a
    privileged, org-wide call. Returns None on failure, same convention
    as get_weekly_cost.
    """
    return _get_json(
        f"{settings.aigw_base_url.rstrip('/')}{path}",
        f"GET {path}",
        headers={"Authorization": f"Bearer {access_token}"},
        params=params,
    )
