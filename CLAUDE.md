# CLAUDE.md

Guidance for Claude Code (and humans) working in this repository.

## Working procedure

Before any change, Claude Code follows the generic workflows under
[`.claude/shared/`](.claude/shared/):

- [`.claude/shared/system/base.md`](.claude/shared/system/base.md) — base operating rules
  (plan first, never guess, never add scope, tag assumptions `VERIFIED`/`ASSUMED`/`UNKNOWN`).
- [`.claude/shared/workflows/plan-first.md`](.claude/shared/workflows/plan-first.md) — before
  any code/config/infra change: investigate, plan, get explicit approval.
- [`.claude/shared/workflows/implement.md`](.claude/shared/workflows/implement.md) — only
  after a plan is approved: execute, verify, commit only on explicit ask.
- [`.claude/shared/workflows/review.md`](.claude/shared/workflows/review.md) — read-only
  review/audit requests: no edits, findings only.

These files are generic and carry no project specifics. **This file (`CLAUDE.md`) wins on
any conflict** with them.

## Communication style

All communication — chat replies, plans, and explanations, not only written
documentation (READMEs, this file, inline code comments) — must follow Simplified
Technical English (ASD-STE100). Before writing or editing documentation, and before
replying, read
[`.claude/output-styles/asd_ste100_style_guide.md`](.claude/output-styles/asd_ste100_style_guide.md)
and apply its vocabulary, sentence-length, and active-voice rules. Check your own output
against the guide before finalizing it.

## What this project is

A demo application that exposes the **management and reporting** functions of the
Portkey / Prisma AIRS AI Gateway. It is a reference/demo, not production software.

Two planes of functionality:

- **Management** — create and read gateway configuration: configs, virtual keys,
  routes, guardrails, workspaces, etc.
- **Reporting** — read usage, cost, latency, and request-level analytics and present
  them in a simple dashboard / report view.

The app does **not** need to proxy live LLM traffic; it talks to the gateway's
management and analytics APIs.

**Deliverable:** a **Docker image**, with an **optional Kubernetes deployment**
(manifests under `deploy/`).

## Current state

- Early scaffolding. Only `README.md`, `CLAUDE.md`, `knowledge/`, and `LICENSE` exist.
- **Tech stack: not yet decided.** Do not assume a framework. If you need to write app
  code, propose the stack first and record the decision in this file.

## Repository conventions

- `knowledge/` holds **API specs and reference material** (OpenAPI/Swagger, docs,
  notes). It is reference input, not application code — do not import from it at
  runtime. See `knowledge/README.md`.
- The gateway spec is stored as **dated snapshots** under `knowledge/<YYYY-MM-DD>/`,
  produced by the `update-openapi-spec` skill. The most recent dated dir is the current
  spec; don't hand-edit files inside a snapshot. To refresh, run the skill (it only
  creates a snapshot when the upstream commit changed) and work from the diff.
- Keep the demo small and readable; clarity over cleverness.
- Never commit secrets. API keys, gateway base URLs with embedded tokens, and the like
  belong in environment variables / a gitignored `.env`, never in source or in
  `knowledge/`.

## When writing code (once a stack is chosen)

- Centralize gateway API access in one client/module so auth and base-URL handling live
  in a single place.
- Treat the files in `knowledge/` as the source of truth for endpoint shapes; prefer
  generating or deriving types from the spec where practical.
- Separate the **management** calls from the **reporting** calls so each can be demoed
  independently.

## Packaging & deployment

- The app ships as a **Docker image**; keep the `Dockerfile` at the repo root.
- Kubernetes manifests (optional) live under `deploy/`, applied with
  `kubectl apply -f deploy/`.
- All gateway config (credentials, base URLs) is injected at **runtime** via environment
  variables — a `.env` file locally, a Kubernetes Secret on a cluster. Never bake secrets
  into the image or commit them.
- Prefer a small, reproducible image (multi-stage build, pinned base image).

## Decisions log

Record notable choices here as they are made (stack, auth approach, which gateway
endpoints are in scope).

- **Spec source:** the gateway OpenAPI spec comes from
  <https://github.com/PaloAltoNetworks/openapi> (branch `main`) — the published "Prisma
  AIRS AI Gateway API", a single bundled `openapi.yaml`. Tracked via dated snapshots and
  the `update-openapi-spec` skill; change detection is by upstream commit SHA.
- **Stack:** Python, FastAPI + Jinja2 + HTMX. Server-rendered pages, no JS build step,
  one small process — fits a small Docker image. App code lives under `app/`.
- **Portal URL:** `aigw-portal.<domain>`, domain supplied at deploy time.
- **Site name:** "AI Developer Portal" — the FastAPI app title, the `<title>` on every
  page, and the sidenav brand. Not the same thing as the gateway product itself
  ("AI Gateway" / "Portkey / Prisma AIRS AI Gateway"), which this site manages —
  don't conflate the two when editing copy.
- **Auth:** two modes, picked by `AUTH_MODE` (`app/config.py`, `app/auth.py`).
  - **`AUTH_MODE=oidc` (default):** the app runs its own OIDC login (Authorization
    Code flow, via `authlib`). No upstream proxy does this step. `OIDC_ISSUER_URL`,
    `OIDC_CLIENT_ID`, `OIDC_CLIENT_SECRET`, `OIDC_REDIRECT_URI` are required in this
    mode — config fails loudly at startup if any is missing or empty.
  - **`AUTH_MODE=header`:** this app's own login is skipped entirely. An upstream
    proxy (nginx, Traefik, oauth2-proxy, ...) must already have authenticated the
    request and set the bearer token on every request, under the header named by
    `AUTH_HEADER_NAME` (default `Authorization`, the standard convention —
    **see the incident below before assuming the default is right for your proxy**).
    `/login` and `/callback` return `404` in this mode; a missing header on any
    other route returns `401`, not a redirect into a login flow that may not even
    be configured. The four `OIDC_*` values above become optional.
    - **Incident: a working, non-empty `Authorization` header is not proof it's
      the right token.** On EKS, fronted by a central oauth2-proxy in Traefik
      ForwardAuth mode, the default config looked like it worked — the app loaded,
      a token was present — but every tier/workspace/budget feature had nothing to
      read. Cause: in ForwardAuth mode, `--set-authorization-header` is the only
      way oauth2-proxy can put anything on a literal `Authorization` *response*
      header (there's no real reverse-proxied upstream to attach a request header
      to instead), and that flag relays the **ID token**, not the access token.
      Confirmed by decoding the token the app actually received: `jti` prefixed
      `ID.` (not `AT.`), `aud` was the OAuth client ID (not the API resource), and
      it carried an `at_hash` claim — which only exists on ID tokens, by OIDC spec.
      The ID token carries none of this app's custom claims (`email_id`,
      `portkey_workspace`, `scope`, `portkey_oid`, `defaults`). The real access
      token, with every custom claim, was available from the same proxy under a
      *different* header — `X-Auth-Request-Access-Token` (the same mechanism
      `--set-xauthrequest` already uses, proven working in that environment).
      **Lesson: decode and check `jti`/`aud` before trusting that a populated
      `Authorization` header is carrying the token you think it is.**
      Fixed by making the header name configurable (`AUTH_HEADER_NAME`,
      `app/config.py`); `get_header_access_token` (`app/auth.py`) also strips a
      leading `"Bearer "` prefix only if present, since a custom header like
      `X-Auth-Request-Access-Token` carries the raw token with no prefix, while
      the standard `Authorization` convention always has one.
    - **The real tradeoff, stated plainly:** this app does **not** verify the
      header's token signature in this mode — the trust boundary is the network
      path, not this code. Only use this mode where the proxy is the sole way to
      reach this app; if the app is ever reachable directly, anyone can forge the
      header and walk in as anyone.
    - **What this mode does not get:** no refresh (`POST /ui/token/refresh` always
      reports the proxy owns that, not this app), no local sign-out (the "Sign out"
      links are hidden in `base.html` via the `auth_mode` Jinja global — clicking
      one couldn't end a session this app doesn't own), no landing page (a missing
      header is a deployment misconfiguration, not a "please sign in" moment).
  - **`GET /healthz` is unauthenticated in both modes, on purpose — do not add
    `Depends(require_login)` to it.** Kubernetes liveness/readiness probes never
    send an `Authorization` header, so in `AUTH_MODE=header` a protected `/healthz`
    would permanently fail probes and the pod would never go Ready. It's a plain
    top-level route next to `root()`, not under `/ui/`, and does nothing beyond
    returning `{"status": "ok"}` — no DB check, no call to the gateway's admin
    token endpoint. A deeper check belongs on a separate `/readyz`, not here: tying
    liveness to an external service (e.g. Strata Cloud Manager) being reachable
    would restart a healthy pod over someone else's outage.
  - `SESSION_SECRET`, `AIGW_BASE_URL`, `AIGW_TOKEN_URL`, `AIGW_CLIENT_ID`,
    `AIGW_CLIENT_SECRET`, `AIGW_TSG_ID` are required in **both** modes — the admin
    APIs need their own credential regardless of how the signed-in user
    authenticated. All of this comes from the environment (`.env` locally; a vault
    or secret manager injects the same names in a real deployment). See
    `.env.example`.
  - **Two auth paths into the gateway**, both in `app/gateway.py`:
    - **Admin APIs** (analytics, policies, and similar): a client-credentials
      token from Strata Cloud Manager's auth service — see
      `knowledge/admin-api-auth.md` for the full confirmed flow. Not standard
      OAuth2: `AIGW_CLIENT_ID`/`AIGW_CLIENT_SECRET` go over **HTTP Basic Auth**,
      not as form fields, and the request needs `scope=tsg_id:<AIGW_TSG_ID>` —
      the tenant the token will act on. `AIGW_TOKEN_URL` is
      `https://auth.apps.paloaltonetworks.com/oauth2/access_token`, a different
      host from `AIGW_BASE_URL`. Tokens last 15 minutes; cached and refreshed
      about a minute early. `get_weekly_cost`, `get_cost_usage_limit_policy`,
      and `get_usage_limit_policy_entity` use this path.
    - **Config data scoped to one user**: the signed-in user's own **access token**
      (not the ID token — see below), forwarded as-is as `Authorization: Bearer
      <JWT>`. `get_with_user_jwt` is the mechanism; no endpoint uses it yet.
  - **ID token vs. access token:** the ID token proves the login event happened
    (`authlib` checks its signature, issuer, audience, expiry, nonce) but its
    claims are not used further. The **access token** carries this app's custom
    claims in this Okta org's configuration, and is what the app decodes for its
    own use (`app/data.py`, `app/token_panel.py`) and relays to the gateway.
    Standard OAuth2 practice: access tokens go to resource servers, ID tokens
    do not. This app does not re-verify the access token's signature — the
    gateway does that itself, as the resource server receiving it.
  - **Confirmed custom claims** (verified against a real Okta access token;
    not in standard OIDC, don't guess alternate names):
    - `defaults.metadata.tier` — model tier.
    - `portkey_workspace` — workspace slug.
    - `email_id` — identity claim (`sub` is also present, and in this Okta org
      happens to equal the email too).
    - `scope` — an array of app-specific scope strings (e.g. `mcp.invoke`,
      `agents.invoke`), separate from the standard `scp` grant-scope claim.
    - `portkey_oid` — a stable opaque identifier, masked by default in the
      token sidecar panel.
- **Token sidecar panel** (`app/token_panel.py`, `GET /ui/token.json`, right-hand
  sidebar in `app/templates/base.html`): shows the decoded access token for
  demo/debug visibility. Spec in `knowledge/token-sidecar.md` — written for a
  different project with different claim names; the mapping onto this
  project's confirmed claims above is what the code implements.
  - **Refresh button gets a genuinely new token**, not a re-read of the old
    one — unlike the original spec's project, nothing external rotates this
    app's token for it. `POST /ui/token/refresh` (`app/auth.py:refresh_access_token`)
    does a real `refresh_token` grant against the IDP's token endpoint and
    updates the session.
  - **This needs the `offline_access` scope**, added to the login's
    `client_kwargs`. A session created before this was added has no
    refresh token — sign out and back in once. `refresh_access_token` is a
    plain `httpx` call, not `authlib`'s session-bound client, since it runs
    from a button click, not the browser's own OIDC redirect.
  - **NOTE, a real tradeoff, not an oversight:** the refresh token — a
    long-lived, sensitive credential — is stored in the same signed-but-not-
    encrypted session cookie as the access token. Accepted for this demo;
    revisit before this app handles anything more sensitive.
- **Dashboard budget data** (`app/data.py:get_dashboard_data`, `app/gateway.py`):
  - **Workspace slug vs. workspace ID — these are not interchangeable.**
    `portkey_workspace` (e.g. `ws-aws-ga-2a753e`) is a **slug**. Confirmed against
    the real API: `/analytics/graphs/cost`'s `workspace_slug` param accepts it
    directly, but `/policies/usage-limits`'s `workspace_id` param rejects it
    outright (`400`, `"Invalid value"`) — it wants the workspace's **UUID**.
    `resolve_workspace_id()` in `app/gateway.py` resolves slug → UUID via
    `GET /deployments?workspace_slug=<slug>` (on `AIGW_ADMIN_BASE_URL`, a third
    host — `/ai_gw/admin/v2`, different from `AIGW_BASE_URL`'s `/ai_gw/v2`) and
    then `GET /deployments/{id}`, whose `workspaces[]` array is the only place
    in the spec pairing a slug with its UUID. `AIGW_ADMIN_BASE_URL` defaults to
    the documented managed host; override only for a self-hosted gateway.
  - **Model tier cell:** `GET /policies/usage-limits?workspace_id=<resolved UUID>
    &type=cost&status=active` — the first matching policy's `credit_limit` and
    `alert_threshold` render as "credit_limit / alert_threshold" below the tier.
  - **Usage tile and budget tile share one entity lookup:** `GET
    /policies/usage-limits/{id}/entities`, matched client-side (the endpoint has
    no filter param for this) against the identity claim's email with
    everything from `@` onward stripped — e.g.
    `eric.partington+oktaeric@gmail.com` → `eric.partington+oktaeric`.
    **Confirmed real shape:** an entity's `value_key` is not just that local
    part — it carries a metadata-key prefix, e.g.
    `"metadata._user:eric.partington+oktaeric"`. Not documented in the spec.
    `get_usage_limit_policy_entity` matches on everything after the last `:`,
    not exact equality. If this ever shows `<unresolved>` for a real user,
    check the debug panel's `value_key` against the "Computed: identity local
    part" panel before assuming the matching logic itself is wrong again.
    The matched entity's `current_usage` drives **both** the usage-tile value
    and the budget-consumption bar (with the policy's `credit_limit`) — one
    call, not two. Shows `<unresolved>` (usage tile) or "Not configured"
    (budget tile) rather than a guessed number if no cost policy or no
    matching entity exists. (This replaced an earlier version that pulled the
    usage-tile value from `GET /analytics/graphs/cost` — that call is no
    longer made here; `get_weekly_cost` in `app/gateway.py` is kept as an
    unused, available
    utility.)
  - **Reset period and usage label, both dynamic from the policy — not hard-coded.**
    `periodic_reset` ("weekly"/"monthly") drives both the usage-tile label
    ("Weekly Usage" / "Monthly Usage") and the reset-period text, which reads
    "{periodic_reset} on {next_usage_reset_at}", friendly-formatted (e.g.
    "Monthly on December 1, 2026 at 12:00 AM UTC"). `format_friendly_datetime`
    in `app/data.py` does the formatting; falls back to the raw string if it
    can't parse, never raises.
  - **Known simplification:** if a workspace has more than one active cost policy,
    the first one returned is used. Picking the *right* one by matching its
    `conditions`/`group_by` against the signed-in user is still open (see below).
  - **Debug trace:** every real HTTP call `app/gateway.py` makes is recorded via
    `start_debug_trace()`/`get_debug_trace()` (a contextvar-backed, per-request
    list) and rendered as one collapsible panel per call, titled with the
    method and path, on the dashboard. Bearer tokens and the client secret are
    never recorded — only params, status code, and body, and the token
    endpoint's response has `access_token` redacted before recording. This is
    a demo-visibility aid, not hidden behind a flag; remove it once the
    integration is stable, or gate it later if this ever runs somewhere semi-public.
- **Claude Code setup card** (`app/data.py:get_claude_code_setup_steps`, rendered in
  `app/templates/integrations.html`): a richer step-by-step layout than Cursor/VS Code,
  which still use the plain intro/command/note format — the template branches on
  whether a tool dict has a `setup_steps` key. Step 1's download table is deliberately
  blank (no real download links exist yet); Step 2's four platform tabs
  (`app/static/js/integrations.js` handles the tab-switching and the copy buttons, page-
  scoped via `base.html`'s `extra_scripts` block) all show the same `settings.json`
  snippet, since its content doesn't vary by OS. `XXX` and `<XXXX>` in that snippet are
  intentional placeholders, not real values — don't fill them in without being asked.
- **Catalog page** (`GET /catalog`, `app/templates/catalog.html`): Models and MCP Tools
  tabs, switched via `?tab=` (a full page reload per tab, not client-side JS — each tab
  needs its own data and its own debug trace). Both tabs call
  `start_debug_trace()`/`get_debug_trace()` from `app/gateway.py` and render the same
  collapsible per-call debug panel used on the dashboard.
  - **Models tab** (`app/data.py:get_catalog_models`) is wired to real calls, both on
    `AIGW_ADMIN_BASE_URL` (a third host, same one `/deployments` uses — not
    `AIGW_BASE_URL`): `GET /integrations?workspace_id=<resolved UUID>` lists the
    providers enabled for the workspace, then `GET /integrations/{slug}/models` is
    called once per provider (`get_integration_models`) to list its models. Shows
    "No models found for this workspace" when the real list is empty — not a
    fabricated row.
    - **Confirmed against a real response:** a model has no `name` field, only
      `slug` — the "Model" column shows `slug`. Only `enabled: true` models are
      kept; disabled ones are filtered out entirely, not shown greyed out. The
      "Status" column always shows the literal word "enabled" (not the raw
      boolean) as a green pill — given the filter above, every row qualifies.
      `pricing_config` can be `null` for a model (handled).
    - **Status pills** (`.status-pill`/`.status-pill-green`/`.status-pill-neutral`
      in `styles.css`): green when positive, neutral gray otherwise. For MCP Tools,
      "positive" is a heuristic in `app/data.py:_is_positive_status` (`active`,
      `enabled`, `healthy`, `connected`) — `McpServerListItem.status` has no
      documented enum, so this isn't exhaustive; adjust it once more real status
      values are seen.
    - **NOTE, a real unit question, not resolved:** each model's
      `pricing_config.pay_as_you_go.{request_token,response_token}.price` is shown
      as-is. The spec doesn't document whether `price` is per-token or per-million-
      tokens — don't assume the column headers' "/1M tokens" framing is already
      correct; confirm against real numbers once this tab is checked against a live
      tenant, and scale the display then if needed.
  - **MCP Tools tab** (`app/data.py:get_catalog_mcp_tools`) is wired to
    `GET /mcp-servers` — on `AIGW_BASE_URL`, unlike `/integrations` and
    `/deployments` which are on `AIGW_ADMIN_BASE_URL`. Field mapping (Server=`name`,
    Auth=`auth_type`, Gateway URL=`url`, Status=`status`) is a first guess from the
    spec's `McpServerListItem`, not yet confirmed against a real response — check the
    debug panel before trusting it. `workspace_id` here is passed as the resolved
    UUID on the same pattern as `/policies/usage-limits`'s identically-named param,
    also unconfirmed. Shows "No MCP servers found for this workspace" when empty.
- **Open decisions (not yet made):** what "agents" maps to in the gateway API (no
  agents resource exists in the spec yet); the usage-limit-policy matching logic
  when a workspace has more than one active cost policy; a real value for
  `TOKEN_SIDECAR_CAPABILITY_SCOPE` (currently unset — which of the `scope` claim's
  values, if any, should be highlighted); real download links for the Claude Code
  token-helper table.
