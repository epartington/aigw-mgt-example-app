# aigw-mgt-example-app

A demo application that surfaces the **management and reporting** functions of the
Portkey / Prisma AIRS AI Gateway.

The goal is to show, in a small self-contained app, how to:

- Call the gateway's management APIs (configs, virtual keys, routes, guardrails, etc.)
- Pull usage, cost, and request/response analytics for reporting
- Present that data in a simple dashboard / reporting view

This is a **demo/reference** project, not a production tool.

## Status

Early scaffolding. The tech stack is not yet fixed — see [CLAUDE.md](CLAUDE.md) for
current decisions and conventions.

## Project layout

```text
.
├── CLAUDE.md        # Guidance for Claude Code and contributors
├── README.md        # This file
├── knowledge/       # API specs and reference material for the gateway (not app code)
├── Dockerfile       # Builds the app container image (planned)
├── deploy/          # Optional Kubernetes manifests (planned)
└── LICENSE
```

## Background

- **Portkey** — an AI gateway that sits in front of LLM providers, offering routing,
  caching, guardrails, observability, and cost/usage tracking.
- **Prisma AIRS** — Palo Alto Networks' AI Runtime Security, which integrates with the
  gateway to add security/guardrail controls over AI traffic.

This demo focuses on the **management plane** (configuring the gateway) and the
**reporting plane** (reading analytics back out), rather than on proxying live LLM
traffic.

## Getting started

Setup steps will be added once the stack is chosen. API specs and reference docs for
the gateway live in [knowledge/](knowledge/).

## Deployment

The app is packaged as a **Docker image**, with an **optional Kubernetes deployment**.

- **Container** — a `Dockerfile` builds the app image:

  ```sh
  docker build -t aigw-mgt-example-app .
  docker run --rm -p 8080:8080 --env-file .env aigw-mgt-example-app
  ```

  (Image name, exposed port, and env vars are placeholders until the stack is chosen.)

- **Kubernetes (optional)** — manifests live under `deploy/` for running the image on a
  cluster:

  ```sh
  kubectl apply -f deploy/
  ```

Gateway credentials and base URLs are supplied at runtime via environment variables
(a `.env` file locally, a Secret in Kubernetes) — never baked into the image.

## License

MIT — see [LICENSE](LICENSE).
