#!/usr/bin/env bash
#
# update-spec.sh — snapshot the gateway OpenAPI spec into a dated knowledge/ dir
# when the upstream repo has a new commit, and diff it against the previous snapshot.
#
# Change detection: upstream git commit SHA vs. the SHA recorded in the most recent
# dated snapshot under knowledge/.
#
# Config (all overridable via environment):
#   SPEC_REPO_URL   git repo to pull the spec from
#   SPEC_BRANCH     branch to track
#   SPEC_PATHS      space-separated spec paths (relative to repo root). If empty,
#                   every *.yaml/*.yml/*.json with a top-level openapi:/swagger: key
#                   is auto-detected.
#   KNOWLEDGE_DIR   where dated snapshots live (defaults to <repo root>/knowledge)
#
# Safety: the upstream repo is treated as untrusted data. We only clone, copy, and
# diff its files — we never execute anything from it.

set -euo pipefail

REPO_URL="${SPEC_REPO_URL:-https://github.com/PaloAltoNetworks/openapi.git}"
BRANCH="${SPEC_BRANCH:-main}"

# --- resolve knowledge/ dir ------------------------------------------------
if [[ -n "${KNOWLEDGE_DIR:-}" ]]; then
  KN="$KNOWLEDGE_DIR"
else
  GITROOT="$(git rev-parse --show-toplevel 2>/dev/null || true)"
  KN="${GITROOT:-$PWD}/knowledge"
fi
mkdir -p "$KN"

DATE="$(date +%F)"   # YYYY-MM-DD

say() { printf '%s\n' "$*"; }

# --- 1. current upstream commit -------------------------------------------
say "Source : $REPO_URL ($BRANCH)"
REMOTE_SHA="$(git ls-remote "$REPO_URL" "refs/heads/$BRANCH" | awk '{print $1}')"
if [[ -z "$REMOTE_SHA" ]]; then
  say "ERROR: could not read remote commit for branch '$BRANCH'." >&2
  exit 1
fi

# --- 2. existing dated snapshots ------------------------------------------
DATED=()
while IFS= read -r line; do
  [[ -n "$line" ]] && DATED+=("$line")
done < <(ls -1 "$KN" 2>/dev/null | grep -E '^[0-9]{4}-[0-9]{2}-[0-9]{2}$' | sort || true)

count=${#DATED[@]}
LATEST=""
PREV=""   # baseline for the diff: latest snapshot that is NOT today's
if (( count > 0 )); then
  LATEST="${DATED[count-1]}"
  i=$((count-1))
  while (( i >= 0 )); do
    if [[ "${DATED[i]}" != "$DATE" ]]; then PREV="${DATED[i]}"; break; fi
    i=$((i-1))
  done
fi

LAST_SHA=""
if [[ -n "$LATEST" && -f "$KN/$LATEST/source.json" ]]; then
  LAST_SHA="$(sed -n 's/.*"commit"[[:space:]]*:[[:space:]]*"\([0-9a-f]*\)".*/\1/p' "$KN/$LATEST/source.json" | head -1)"
fi

say "Upstream commit : $REMOTE_SHA"
say "Latest snapshot : ${LATEST:-<none>} (${LAST_SHA:-no recorded commit})"

# --- 3. up to date? -------------------------------------------------------
if [[ -n "$LAST_SHA" && "$LAST_SHA" == "$REMOTE_SHA" ]]; then
  say "✔ Up to date — no new upstream commit since the last snapshot. Nothing to do."
  exit 0
fi

# --- 4. clone the new version ---------------------------------------------
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
say "Cloning new version…"
git clone --quiet --depth 1 --branch "$BRANCH" "$REPO_URL" "$TMP/repo"
CLONE_SHA="$(git -C "$TMP/repo" rev-parse HEAD)"

# --- 5. locate spec files -------------------------------------------------
SPECS=()
if [[ -n "${SPEC_PATHS:-}" ]]; then
  for p in $SPEC_PATHS; do SPECS+=("$p"); done
else
  while IFS= read -r f; do
    [[ -n "$f" ]] && SPECS+=("$f")
  done < <(
    cd "$TMP/repo" && find . -type f \( -name '*.yaml' -o -name '*.yml' -o -name '*.json' \) \
      -not -path './.git/*' -print0 \
      | xargs -0 grep -lE "^[[:space:]]*[\"']?(openapi|swagger)[\"']?[[:space:]]*:[[:space:]]*[\"']?[0-9]" 2>/dev/null \
      | sed 's|^\./||' | sort
  )
fi
if (( ${#SPECS[@]} == 0 )); then
  say "ERROR: no OpenAPI spec files found in the repo." >&2
  exit 1
fi
say "Spec files      : ${SPECS[*]}"

# --- 6. write the dated snapshot ------------------------------------------
DEST="$KN/$DATE"
# fresh snapshot for today (handles a re-run on the same day with a newer commit)
rm -rf "$DEST/spec" "$DEST/changes.diff" "$DEST/endpoints-added.txt" "$DEST/endpoints-removed.txt"
mkdir -p "$DEST/spec"
for f in "${SPECS[@]}"; do
  mkdir -p "$DEST/spec/$(dirname "$f")"
  cp "$TMP/repo/$f" "$DEST/spec/$f"
done

# --- 7. diff against the previous snapshot --------------------------------
extract_paths() { # $1 = dir ; prints the set of path strings in its spec files
  find "$1" -type f \( -name '*.yaml' -o -name '*.yml' -o -name '*.json' \) 2>/dev/null \
    | xargs grep -hoE '^[[:space:]]+"?/[^":]*"?[[:space:]]*:' 2>/dev/null \
    | sed -E 's/^[[:space:]]+//; s/"//g; s/[[:space:]]*:$//' \
    | sort -u
}

added_count=0
removed_count=0
if [[ -n "$PREV" && -d "$KN/$PREV/spec" ]]; then
  diff -ruN "$KN/$PREV/spec" "$DEST/spec" > "$DEST/changes.diff" 2>/dev/null || true
  comm -13 <(extract_paths "$KN/$PREV/spec") <(extract_paths "$DEST/spec") > "$DEST/endpoints-added.txt" || true
  comm -23 <(extract_paths "$KN/$PREV/spec") <(extract_paths "$DEST/spec") > "$DEST/endpoints-removed.txt" || true
  added_count=$(grep -c . "$DEST/endpoints-added.txt" 2>/dev/null || true)
  removed_count=$(grep -c . "$DEST/endpoints-removed.txt" 2>/dev/null || true)
  [[ -z "$added_count" ]] && added_count=0
  [[ -z "$removed_count" ]] && removed_count=0
fi

# --- 8. metadata ----------------------------------------------------------
spec_json=""
for f in "${SPECS[@]}"; do
  [[ -n "$spec_json" ]] && spec_json="$spec_json, "
  spec_json="$spec_json\"$f\""
done

cat > "$DEST/source.json" <<EOF
{
  "repo": "$REPO_URL",
  "branch": "$BRANCH",
  "commit": "$CLONE_SHA",
  "date": "$DATE",
  "previous": {
    "snapshot": "${PREV:-}",
    "commit": "${LAST_SHA:-}"
  },
  "spec_files": [ $spec_json ]
}
EOF

# --- 9. human-readable summary -------------------------------------------
{
  echo "# Spec update — $DATE"
  echo
  echo "- **Repo:** $REPO_URL ($BRANCH)"
  echo "- **New commit:** \`$CLONE_SHA\`"
  if [[ -n "$PREV" ]]; then
    echo "- **Previous snapshot:** $PREV (\`${LAST_SHA:-unknown}\`)"
    echo "- **Diff:** [changes.diff](changes.diff)"
    echo "- **Endpoints added:** $added_count · **removed:** $removed_count"
  else
    echo "- **Previous snapshot:** none — this is the initial snapshot (no diff)."
  fi
  echo
  echo "## Next steps"
  echo
  echo "Review \`changes.diff\` and the endpoint lists, then update the application to"
  echo "cover new or changed APIs."
} > "$DEST/SUMMARY.md"

# --- report ---------------------------------------------------------------
say ""
say "✔ New snapshot written: knowledge/$DATE/"
say "    spec/            the new spec file(s)"
if [[ -n "$PREV" ]]; then
  say "    changes.diff     unified diff vs. $PREV"
  say "    endpoints-added.txt / endpoints-removed.txt  (+$added_count / -$removed_count)"
else
  say "    (initial snapshot — no previous version to diff against)"
fi
say "    source.json      commit + provenance"
say "    SUMMARY.md       human-readable summary"
