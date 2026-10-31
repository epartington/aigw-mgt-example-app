"""App config, all from the environment.

Read every value here, nowhere else. A vault or secret manager can inject
these same variable names at deploy time with no code change.
"""

from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_URL_FIELDS = {
    "oidc_issuer_url",
    "oidc_redirect_uri",
    "aigw_base_url",
    "aigw_admin_base_url",
    "aigw_token_url",
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # "oidc" (default): this app runs its own login (see app/auth.py).
    # "header": an upstream proxy (nginx, Traefik, oauth2-proxy, ...)
    # already authenticated the request and sets Authorization: Bearer
    # <token> on every request this app receives. This app does not
    # verify that token's signature in header mode — the trust boundary
    # is the network path. Only put this app behind a proxy that is the
    # sole way to reach it; see CLAUDE.md for the full tradeoff.
    auth_mode: Literal["oidc", "header"] = "oidc"

    # Header name this app reads the bearer token from in AUTH_MODE=header.
    # Default matches the standard convention ("Authorization: Bearer
    # <token>"). Override when the upstream proxy can only expose the
    # usable token under a different header — e.g. oauth2-proxy's
    # ForwardAuth mode, where a literal Authorization response header can
    # only ever carry the OIDC ID token (no custom claims), and the real
    # access token is instead available as X-Auth-Request-Access-Token.
    # See CLAUDE.md "AUTH_MODE=header" for the incident this fixes.
    auth_header_name: str = "Authorization"

    # Required only when auth_mode is "oidc" — see _oidc_required_when_oidc_mode.
    oidc_issuer_url: str | None = None
    oidc_client_id: str | None = None
    oidc_client_secret: str | None = None
    oidc_redirect_uri: str | None = None

    session_secret: str

    # Admin APIs (e.g. analytics, policies): client-credentials grant against
    # Strata Cloud Manager's auth service, not the gateway itself. See
    # knowledge/admin-api-auth.md. aigw_tsg_id is the tenant service group
    # the service account's token is scoped to — required on every token
    # request (POST /oauth2/access_token, scope=tsg_id:<aigw_tsg_id>).
    # Required in both auth modes — the admin APIs need their own
    # credential regardless of how the signed-in user authenticated.
    aigw_base_url: str
    # A different host from aigw_base_url — the spec documents this as a
    # separate "Managed" server for /deployments, /integrations, and
    # similar. Defaulted to the known managed value; override for a
    # self-hosted gateway.
    aigw_admin_base_url: str = "https://api.apps.paloaltonetworks.com/ai_gw/admin/v2"
    aigw_token_url: str
    aigw_client_id: str
    aigw_client_secret: str
    aigw_tsg_id: str

    # Token sidecar panel. Optional: no real scope is defined for this
    # project yet (see knowledge/token-sidecar.md). Leave unset to hide
    # the capability-flag row entirely, rather than show a fabricated one.
    token_sidecar_capability_scope: str | None = None

    @field_validator(*_URL_FIELDS)
    @classmethod
    def _must_be_a_real_url(cls, value: str | None, info) -> str | None:
        # None means "not set" — fine for the two optional OIDC URL
        # fields when auth_mode is "header"; _oidc_required_when_oidc_mode
        # below catches a genuinely missing value when auth_mode is
        # "oidc". An empty string is never fine, in either mode — this
        # app hit that exact gap with an empty AIGW_TOKEN_URL, which only
        # failed later, deep inside an httpx call, with a confusing
        # error. Catch it here instead, at startup.
        if value is None:
            return value
        if not value or not value.startswith(("http://", "https://")):
            raise ValueError(
                f"{info.field_name} must be a full http(s) URL, got {value!r}"
            )
        return value

    @model_validator(mode="after")
    def _oidc_required_when_oidc_mode(self) -> "Settings":
        if self.auth_mode != "oidc":
            return self
        required = {
            "oidc_issuer_url": self.oidc_issuer_url,
            "oidc_client_id": self.oidc_client_id,
            "oidc_client_secret": self.oidc_client_secret,
            "oidc_redirect_uri": self.oidc_redirect_uri,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ValueError(
                f"AUTH_MODE=oidc (the default) requires: {', '.join(missing)}. "
                "Set these, or set AUTH_MODE=header to skip this app's own login."
            )
        return self


settings = Settings()
