"""Shapes the signed-in user's access token for the right-hand sidecar panel.

See knowledge/token-sidecar.md for the original spec, and CLAUDE.md for
how its claim names map onto this project's confirmed claims
(portkey_workspace, portkey_oid, email_id, defaults, scope). This module
does not verify the token's signature — the gateway does that itself when
this same token is relayed to it as Authorization: Bearer. This module
decodes independently only to show what the token literally contains.

Response contract (3 states), matching the spec:
- {"present": False} — no token in the session.
- {"present": True, "decodable": False, "raw": "<token>"} — present but
  not a parseable JWT.
- {"present": True, "decodable": True, "raw": ..., "claims": {...}, ...}
  — the full happy path, with curated fields split out for the panel.
"""

import jwt

from app.config import settings

# Claims already surfaced as their own curated field below. Everything
# else falls into "standard_claims" for the collapsed disclosure.
_CURATED_CLAIM_KEYS = {
    "email_id",
    "email",
    "sub",
    "portkey_workspace",
    "portkey_oid",
    "defaults",
    "scope",
    "iat",
    "nbf",
    "exp",
}


def _parse_scopes(claims: dict) -> list[str] | None:
    """Return the scope list, or None if the claim is absent entirely.

    None and [] are different: None means "this token carries no scope
    claim at all," which the panel should say plainly, not render as an
    empty row.
    """
    scope = claims.get("scope")
    if scope is None:
        return None
    if isinstance(scope, str):
        return scope.split()
    if isinstance(scope, list):
        return scope
    return None


def _capability_flag(scopes: list[str] | None) -> dict | None:
    """Return the derived capability-flag row, or None if not configured.

    Not configured means: no real scope is defined for this project yet.
    Showing a flag with no real scope behind it would be a fabricated
    value, so the panel omits the row instead.
    """
    scope_of_interest = settings.token_sidecar_capability_scope
    if not scope_of_interest or scopes is None:
        return None
    return {"scope": scope_of_interest, "present": scope_of_interest in scopes}


def build_token_panel_response(id_token: str | None) -> dict:
    """Build the panel's JSON response from the session's raw ID token."""
    if not id_token:
        return {"present": False}

    try:
        claims = jwt.decode(id_token, options={"verify_signature": False})
    except jwt.InvalidTokenError:
        return {"present": True, "decodable": False, "raw": id_token}

    scopes = _parse_scopes(claims)
    standard_claims = {k: v for k, v in claims.items() if k not in _CURATED_CLAIM_KEYS}

    return {
        "present": True,
        "decodable": True,
        "raw": id_token,
        "claims": claims,
        "scopes": scopes,
        "capability": _capability_flag(scopes),
        "identity": claims.get("email_id") or claims.get("email") or claims.get("sub"),
        "workspace": claims.get("portkey_workspace"),
        "sensitive_id": claims.get("portkey_oid"),
        "structured": claims.get("defaults"),
        "iat": claims.get("iat"),
        "nbf": claims.get("nbf"),
        "exp": claims.get("exp"),
        "standard_claims": standard_claims,
    }
