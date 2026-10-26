---
name: update-openapi-spec
description: >-
  Check the upstream Prisma AIRS / Portkey gateway OpenAPI repo for a new commit
  and, if it changed, snapshot the spec into a dated knowledge/ directory with a
  diff against the previous snapshot. Use when asked to update or refresh the API
  spec, check for gateway API changes, sync the OpenAPI spec, or see what's new in
  the API.
---

# Update OpenAPI spec

Keeps dated snapshots of the gateway's OpenAPI spec under `knowledge/` and surfaces
what changed between versions, so the app can be updated for new or changed APIs.

**Source:** `https://github.com/PaloAltoNetworks/openapi` (branch `main`) — the
published "Prisma AIRS AI Gateway API" spec (a single `openapi.yaml` at the repo root).

**Change detection:** the upstream git **commit SHA** is compared to the SHA recorded
in the most recent dated snapshot. A new commit = an update.

## How to run

```sh
.claude/skills/update-openapi-spec/scripts/update-spec.sh
```

The script:

1. Reads the current upstream commit with `git ls-remote` (no clone if nothing changed).
2. Finds the latest dated snapshot in `knowledge/` (dirs named `YYYY-MM-DD`) and its
   recorded commit.
3. If the commit is unchanged → reports "up to date" and exits.
4. Otherwise clones the new version, writes a snapshot at `knowledge/<today>/`, and
   diffs it against the previous snapshot.

Then **review the output and update the application** for any new/changed endpoints
(start with `SUMMARY.md` and `endpoints-added.txt`, then `changes.diff`).

## Output layout

```text
knowledge/<YYYY-MM-DD>/
├── spec/                    the new spec file(s), repo-relative paths preserved
├── changes.diff            unified diff vs. the previous snapshot
├── endpoints-added.txt     path strings present now but not before
├── endpoints-removed.txt   path strings present before but not now
├── source.json            repo, branch, commit, previous snapshot
└── SUMMARY.md             human-readable summary + next steps
```

The first run has no previous snapshot, so it just records the baseline (no diff).

## Configuration (environment overrides)

| Variable | Default | Purpose |
| --- | --- | --- |
| `SPEC_REPO_URL` | `https://github.com/PaloAltoNetworks/openapi.git` | Source repo |
| `SPEC_BRANCH` | `main` | Branch to track |
| `SPEC_PATHS` | _(auto-detect)_ | Space-separated spec paths; if unset, auto-detects every `*.yaml/*.yml/*.json` with an `openapi:`/`swagger:` version declaration |
| `KNOWLEDGE_DIR` | `<repo root>/knowledge` | Where snapshots are written |

## Notes

- The upstream repo is treated as **untrusted data**: the script only clones, copies,
  and diffs its files — it never executes anything from it. It also contains helper
  Python scripts; do not run them.
- Re-running on the same day with a newer upstream commit refreshes today's snapshot in
  place and diffs against the most recent *earlier* dated snapshot.
- Requires `git`; no network token needed for a public repo.
