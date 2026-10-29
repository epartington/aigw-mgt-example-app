"""OIDC login, handled by this app — no upstream proxy needed.

Uses the Authorization Code flow. `authlib` fetches the issuer's discovery
document, so only the four OIDC_* values in `app/config.py` are needed.
`authlib` also sets up CSRF (`state`) and replay (`nonce`) protection.

Two tokens come back from the exchange, with two different jobs:
- The **ID token** proves the login event happened. `authlib` checks its
  signature, issuer, audience, expiry, and nonce. Its claims are not used
  beyond this check.
- The **access token** is this app's source of claims (tier, workspace,
  scope, the sensitive identifier — see CLAUDE.md for the confirmed claim
  names) and is what gets relayed to the gateway as
  `Authorization: Bearer <token>` (see app/gateway.py:get_with_user_jwt).
  This app does not re-verify its signature — the gateway does that
  itself, as the resource server receiving it. This split matches
  standard OAuth2 practice: access tokens go to resource servers, ID
  tokens do not.

A third token, the refresh token, is requested via the `offline_access`
scope so the token sidecar's refresh button can get a genuinely new
access token, not just re-read the one already in the session. It is a
long-lived, sensitive credential — stored in the same signed (not
encrypted) session cookie as the access token. Flagged here deliberately,
not hidden: see CLAUDE.md for the tradeoff this accepts for a demo app.
"""

import httpx
import jwt
from authlib.integrations.starlette_client import OAuth
from fastapi import HTTPException, Request
from starlette.responses import RedirectResponse

from app.config import settings

oauth = OAuth()
oauth.register(
    name="oidc",
    client_id=settings.oidc_client_id,
    client_secret=settings.oidc_client_secret,
    server_metadata_url=f"{settings.oidc_issuer_url.rstrip('/')}/.well-known/openid-configuration",
    client_kwargs={"scope": "openid profile email offline_access", "code_challenge_method": "S256"},
)


async def start_login(request: Request) -> RedirectResponse:
    """Redirect the browser to the IDP's login page."""
    return await oauth.oidc.authorize_redirect(request, settings.oidc_redirect_uri)


async def handle_callback(request: Request) -> tuple[dict, str, str | None]:
    """Exchange the auth code for tokens.

    Returns the access token's claims, the raw access token string, and
    the refresh token (None if the IDP didn't issue one — e.g. if this
    Okta app isn't configured for the refresh-token grant, offline_access
    being requested is not on its own a guarantee). `authorize_access_token`
    validates the ID token first (signature, issuer, audience, expiry,
    nonce) as proof the login event is legitimate; this function then
    decodes the access token separately for its claims, per the module
    docstring above.
    """
    token = await oauth.oidc.authorize_access_token(request)
    if not token.get("userinfo"):
        raise HTTPException(status_code=401, detail="No ID token claims returned")

    access_token = token.get("access_token")
    if not access_token:
        raise HTTPException(status_code=401, detail="No access token returned")

    try:
        claims = jwt.decode(access_token, options={"verify_signature": False})
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Access token could not be decoded")

    return dict(claims), access_token, token.get("refresh_token")


async def refresh_access_token(refresh_token: str) -> tuple[dict, str, str | None]:
    """Use the refresh_token grant to get a genuinely new access token.

    A plain httpx call, not authlib's session-bound client — this runs
    from a button click, not from the browser's own OIDC redirect flow.
    Raises httpx.HTTPError on failure; the caller decides how to surface
    it. Returns (new_claims, new_access_token, new_refresh_token) — some
    IDPs rotate the refresh token on every use, some don't, so the
    original is passed back if the response omits one.
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        metadata = await client.get(
            f"{settings.oidc_issuer_url.rstrip('/')}/.well-known/openid-configuration"
        )
        metadata.raise_for_status()
        token_endpoint = metadata.json()["token_endpoint"]

        response = await client.post(
            token_endpoint,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": settings.oidc_client_id,
                "client_secret": settings.oidc_client_secret,
            },
        )
        response.raise_for_status()
        token = response.json()

    new_access_token = token["access_token"]
    new_refresh_token = token.get("refresh_token", refresh_token)
    try:
        new_claims = jwt.decode(new_access_token, options={"verify_signature": False})
    except jwt.InvalidTokenError:
        new_claims = {}
    return new_claims, new_access_token, new_refresh_token


def get_session_claims(request: Request) -> dict | None:
    """Read the signed-in user's claims from the session, or None."""
    return request.session.get("claims")


def get_session_access_token(request: Request) -> str | None:
    """Read the signed-in user's raw access token from the session, or None."""
    return request.session.get("access_token")


def get_session_refresh_token(request: Request) -> str | None:
    """Read the signed-in user's refresh token from the session, or None.

    None here means either this session predates the offline_access
    scope being added (sign out and back in), or the IDP didn't issue
    one at all.
    """
    return request.session.get("refresh_token")


def require_login(request: Request) -> dict:
    """FastAPI dependency: return claims, or redirect to /login."""
    claims = get_session_claims(request)
    if claims is None:
        raise RedirectToLogin()
    return claims


class RedirectToLogin(Exception):
    """Raised by require_login; converted to a redirect in app/main.py."""
