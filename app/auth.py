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

AUTH_MODE=header is a second, simpler mode: an upstream proxy (nginx,
Traefik, oauth2-proxy, ...) already authenticated the request and sets
Authorization: Bearer <token> on every request. This app does not verify
that token's signature in this mode — the trust boundary is the network
path, not this code. get_current_claims/get_current_access_token pick
between this and the session-based functions above depending on
settings.auth_mode; everything else in the app goes through those two,
not the mode-specific functions directly.
"""

import httpx
import jwt
from authlib.integrations.starlette_client import OAuth
from fastapi import HTTPException, Request
from starlette.responses import RedirectResponse

from app.config import settings

oauth = OAuth()
if settings.auth_mode == "oidc":
    # Config validation already guarantees these four are set when
    # auth_mode is "oidc" (see app/config.py); the assert below just
    # makes that guarantee visible to the type checker too. In "header"
    # mode this client is never registered — /login and /callback 404
    # instead of reaching code that assumes it exists.
    assert settings.oidc_issuer_url and settings.oidc_client_id and settings.oidc_client_secret
    oauth.register(
        name="oidc",
        client_id=settings.oidc_client_id,
        client_secret=settings.oidc_client_secret,
        server_metadata_url=f"{settings.oidc_issuer_url.rstrip('/')}/.well-known/openid-configuration",
        client_kwargs={"scope": "openid profile email offline_access", "code_challenge_method": "S256"},
    )


async def start_login(request: Request) -> RedirectResponse:
    """Redirect the browser to the IDP's login page. AUTH_MODE=oidc only."""
    assert settings.oidc_redirect_uri, "start_login requires AUTH_MODE=oidc"
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

    Only meaningful in AUTH_MODE=oidc — header mode never stores a
    refresh token (nothing populates the session there), so this is
    never reached in that mode in practice. Guarded explicitly anyway,
    since oidc_issuer_url is typed Optional now that header mode exists.
    """
    issuer_url = settings.oidc_issuer_url
    client_id = settings.oidc_client_id
    client_secret = settings.oidc_client_secret
    if not issuer_url or not client_id or not client_secret:
        raise RuntimeError("refresh_access_token requires AUTH_MODE=oidc config")

    async with httpx.AsyncClient(timeout=10.0) as client:
        metadata = await client.get(f"{issuer_url.rstrip('/')}/.well-known/openid-configuration")
        metadata.raise_for_status()
        token_endpoint = metadata.json()["token_endpoint"]

        response = await client.post(
            token_endpoint,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": client_id,
                "client_secret": client_secret,
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


def get_header_access_token(request: Request) -> str | None:
    """Read the bearer token an upstream proxy already put on the request.

    Only meaningful when settings.auth_mode == "header". No custom header
    name — literally the standard Authorization header, per the request
    this was built for.
    """
    header = request.headers.get("authorization")
    if not header or not header.lower().startswith("bearer "):
        return None
    return header[len("Bearer ") :].strip() or None


def get_header_claims(request: Request) -> dict | None:
    """Decode the header-supplied token's claims, or None if absent/invalid.

    Not verified here — see the module docstring's AUTH_MODE=header note.
    """
    token = get_header_access_token(request)
    if not token:
        return None
    try:
        return dict(jwt.decode(token, options={"verify_signature": False}))
    except jwt.InvalidTokenError:
        return None


def get_current_claims(request: Request) -> dict | None:
    """Return the signed-in user's claims for either auth mode."""
    if settings.auth_mode == "header":
        return get_header_claims(request)
    return get_session_claims(request)


def get_current_access_token(request: Request) -> str | None:
    """Return the signed-in user's access token for either auth mode."""
    if settings.auth_mode == "header":
        return get_header_access_token(request)
    return get_session_access_token(request)


def require_login(request: Request) -> dict:
    """FastAPI dependency: return claims, or fail, depending on auth mode.

    AUTH_MODE=header: a missing/invalid header is a deployment
    misconfiguration, not a "please sign in" moment — there is no local
    login to redirect to, so this raises a plain 401 instead.
    AUTH_MODE=oidc: raises RedirectToLogin, which app/main.py turns into
    a redirect to the landing page's Sign in button.
    """
    claims = get_current_claims(request)
    if claims is not None:
        return claims
    if settings.auth_mode == "header":
        raise HTTPException(
            status_code=401,
            detail=(
                "No Authorization header from the upstream proxy. "
                "AUTH_MODE=header expects one on every request."
            ),
        )
    raise RedirectToLogin()


class RedirectToLogin(Exception):
    """Raised by require_login; converted to a redirect in app/main.py."""
