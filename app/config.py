"""App config, all from the environment.

Read every value here, nowhere else. A vault or secret manager can inject
these same variable names at deploy time with no code change.
"""

from pydantic import field_validator
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

    oidc_issuer_url: str
    oidc_client_id: str
    oidc_client_secret: str
    oidc_redirect_uri: str

    session_secret: str

    # Admin APIs (e.g. analytics, policies): client-credentials grant against
    # Strata Cloud Manager's auth service, not the gateway itself. See
    # knowledge/admin-api-auth.md. aigw_tsg_id is the tenant service group
    # the service account's token is scoped to — required on every token
    # request (POST /oauth2/access_token, scope=tsg_id:<aigw_tsg_id>).
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
    def _must_be_a_real_url(cls, value: str, info) -> str:
        # Plain `str` accepts an empty value silently — this app hit that
        # exact gap with an empty AIGW_TOKEN_URL, which only failed later,
        # deep inside an httpx call, with a confusing error. Catch it here
        # instead, at startup, with the same "fails loudly" behavior as a
        # missing variable.
        if not value or not value.startswith(("http://", "https://")):
            raise ValueError(
                f"{info.field_name} must be a full http(s) URL, got {value!r}"
            )
        return value


settings = Settings()
