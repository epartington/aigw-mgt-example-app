# CLAUDE.md

Guidance for Claude Code (and humans) working in this repository.

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
