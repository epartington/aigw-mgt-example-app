# knowledge/

Reference material for the Portkey / Prisma AIRS AI Gateway — the OpenAPI spec plus
supporting notes used to build the demo app.

> This folder is **reference input, not application code.** Nothing here is imported at
> runtime. Treat the specs as the source of truth for endpoint shapes.

## Source

The spec is the published **Prisma AIRS AI Gateway API** OpenAPI document:

- Repo: <https://github.com/PaloAltoNetworks/openapi> (branch `main`)
- The repo builds a single bundled `openapi.yaml` at its root.

Supporting docs: Portkey API docs (<https://portkey.ai/docs>) and the Prisma AIRS
(Palo Alto Networks AI Runtime Security) vendor portal.

## Dated snapshots

Each pull of the spec is stored in its own **`YYYY-MM-DD/`** directory, created by the
`update-openapi-spec` skill only when the upstream commit has changed:

```text
knowledge/<YYYY-MM-DD>/
├── spec/                 the spec file(s) as pulled (repo-relative paths preserved)
├── changes.diff         unified diff vs. the previous snapshot
├── endpoints-added.txt  path strings added since the previous snapshot
├── endpoints-removed.txt path strings removed since the previous snapshot
├── source.json          repo, branch, commit SHA, previous snapshot
└── SUMMARY.md           human-readable summary + next steps
```

The most recent dated directory is the current spec. Older directories are kept as
history so changes between versions stay auditable.

## Updating the spec

Run the skill (see `.claude/skills/update-openapi-spec/`):

```sh
.claude/skills/update-openapi-spec/scripts/update-spec.sh
```

It checks the upstream commit, and if it changed, writes a new dated snapshot and diffs
it against the previous one. Then review the diff and update the app for new/changed
APIs.

## Other files

- `notes.md` — auth model, base URLs, environments, and gotchas (fill in as you learn
  the API).

## Rules

- **No secrets.** Strip API keys, tokens, account IDs, and PII from any note or example
  before committing. (Snapshots come from a public repo and are safe to commit as-is.)
- Don't hand-edit files inside a dated snapshot — they represent a specific upstream
  commit. Pull a new snapshot instead.
