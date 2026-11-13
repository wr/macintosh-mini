#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Wells Riley
# SPDX-License-Identifier: GPL-3.0-or-later
#
# Tells us when upstream Basilisk II / SheepShaver has moved past the commit
# the installer builds.
#
# setup.sh builds both emulators from kanjitalk755/macemu at one fixed commit
# (MACEMU_COMMIT). Upstream has no releases, so the pin moves only on purpose:
# every move makes every Mac recompile on its next update. This script looks at
# what upstream's master has gained since the pin and keeps one GitHub issue in
# step with that:
#
#   - new commits that touch BasiliskII/ or SheepShaver/: open the issue, or
#     update it in place if it's already open
#   - none: close the issue if it's open
#
# It never opens a PR and never changes the pin.
#
# SheepShaver builds from Basilisk II's shared sources (SheepShaver/Makefile
# points at ../BasiliskII), so those two directories are all the code that
# either emulator builds from. The installer doesn't enable cxmon, the only
# other directory upstream has, so it isn't watched.
#
# Usage: check-macemu-upstream.sh [--dry-run] [--setup-file FILE]
#   --dry-run          print what it would do and the issue text, change nothing
#   --setup-file FILE  where to read MACEMU_COMMIT (default: setup.sh at the
#                      top of this repository)
#
# Needs git, gh and jq. gh talks to GITHUB_REPOSITORY (default wr/macintosh-mini)
# with GH_TOKEN, which needs issues: write for a real run. A dry run only reads.

set -euo pipefail

UPSTREAM_URL="https://github.com/kanjitalk755/macemu"
WATCHED_PATHS=(BasiliskII SheepShaver)
ISSUE_TITLE="Basilisk II and SheepShaver: new upstream changes since the installer's pinned version"
MAX_LISTED=50
REPO="${GITHUB_REPOSITORY:-wr/macintosh-mini}"

die() { echo "check-macemu-upstream: $*" >&2; exit 1; }

dry_run=0
setup_file="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/setup.sh"
while [[ $# -gt 0 ]]; do
  case $1 in
    --dry-run) dry_run=1 ;;
    --setup-file) [[ $# -ge 2 ]] || die "--setup-file needs a file"; setup_file=$2; shift ;;
    -h|--help) sed -n '/^# Usage:/,/^$/p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) die "unknown option: $1" ;;
  esac
  shift
done

# --- The pin -----------------------------------------------------------------

[[ -f $setup_file ]] || die "can't read $setup_file"
pin=$(sed -n 's/^MACEMU_COMMIT="\([0-9a-f]\{40\}\)".*/\1/p' "$setup_file" | head -n 1)
[[ -n $pin ]] || die "no MACEMU_COMMIT=\"<40 hex digits>\" line in $setup_file"

# --- Upstream ----------------------------------------------------------------

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
up() { git -C "$work/macemu" "$@"; }

# Commits and trees only. File contents are never needed to list history.
git clone --quiet --filter=blob:none --no-checkout "$UPSTREAM_URL.git" "$work/macemu"

head=$(up rev-parse HEAD)
branch=$(up rev-parse --abbrev-ref HEAD)
up cat-file -e "$pin^{commit}" 2>/dev/null ||
  die "the pinned commit $pin isn't in $UPSTREAM_URL (is it on a branch that was deleted?)"
up merge-base --is-ancestor "$pin" "$head" ||
  die "the pinned commit $pin isn't part of upstream's $branch history, so there's nothing to compare against"

total=$(up rev-list --count "$pin..$head")
relevant=$(up rev-list --count --no-merges "$pin..$head" -- "${WATCHED_PATHS[@]}")

# --- The issue text ----------------------------------------------------------

plural() { if [[ $1 -eq 1 ]]; then echo "$1 $2"; else echo "$1 ${2}s"; fi; }

# A commit title is somebody else's text. Keep it from turning into markup or
# an @-mention, and point "#123" at upstream's issues, not this repository's.
zwsp=$'\xe2\x80\x8b'
clean_title() {
  sed -E \
    -e 's,(^|[^A-Za-z0-9_/])#([0-9]+),\1kanjitalk755/macemu#\2,g' \
    -e 's/([][\\`*_<>~|&])/\\\1/g' \
    -e "s/@/@$zwsp/g"
}

render_body() {
  local sha date title
  echo "The installer builds Basilisk II and SheepShaver from [kanjitalk755/macemu]($UPSTREAM_URL) at one fixed commit, [\`${pin:0:7}\`]($UPSTREAM_URL/commit/$pin). Upstream has moved on: its $branch branch is now at [\`${head:0:7}\`]($UPSTREAM_URL/commit/$head), $(plural "$total" commit) later."
  echo
  echo "Commits that change the Basilisk II or SheepShaver code ($relevant, newest first):"
  echo
  while IFS=$'\t' read -r sha date title; do
    echo "- [\`${sha:0:7}\`]($UPSTREAM_URL/commit/$sha) $(clean_title <<<"$title") ($date)"
  done < <(up log --no-merges --max-count="$MAX_LISTED" --date=short --format='%H%x09%ad%x09%s' "$pin..$head" -- "${WATCHED_PATHS[@]}")
  if [[ $relevant -gt $MAX_LISTED ]]; then
    echo
    echo "That's the newest $MAX_LISTED. The full comparison has the rest."
  fi
  echo
  echo "[Compare the pin with upstream's $branch]($UPSTREAM_URL/compare/$pin...$head)"
  echo
  echo "**What to do:** nothing changes for anyone until \`MACEMU_COMMIT\` in \`setup.sh\` is moved, and moving it makes every Mac recompile both emulators on its next update. So this is only a heads-up. Pick a new pin when one of these changes is worth that."
  echo
  echo "<sub>Kept up to date by the \"Watch upstream emulators\" workflow (\`.github/workflows/watch-macemu-upstream.yml\`), once a week. It edits this issue when the list changes and closes it when the pin has caught up.</sub>"
}

# --- What to do about it -----------------------------------------------------

summary() {
  echo "$*"
  [[ -n ${GITHUB_STEP_SUMMARY:-} ]] && echo "$*" >> "$GITHUB_STEP_SUMMARY"
  return 0
}

# The number of the open issue with our title, or nothing.
find_open_issue() {
  gh issue list --repo "$REPO" --state open --limit 200 --json number,title |
    jq -r --arg title "$ISSUE_TITLE" 'map(select(.title == $title)) | first | .number // empty'
}

issue=""
if ! issue=$(find_open_issue); then
  [[ $dry_run -eq 1 ]] || die "couldn't look for the open issue in $REPO"
  echo "(dry run: couldn't look for the open issue in $REPO, so assuming there is none)" >&2
fi

echo "Pinned:   $pin"
echo "Upstream: $head ($branch), $(plural "$total" commit) later, $relevant touching ${WATCHED_PATHS[*]}"

if [[ $relevant -gt 0 ]]; then
  body_file="$work/body.md"
  render_body > "$body_file"

  if [[ -z $issue ]]; then
    if [[ $dry_run -eq 1 ]]; then
      summary "Dry run: would open an issue."
    else
      url=$(gh issue create --repo "$REPO" --title "$ISSUE_TITLE" --body-file "$body_file")
      summary "Opened $url ($relevant new upstream commits)."
    fi
  else
    # Bodies compared through $(...) so a trailing newline can't make them differ.
    if [[ $(gh issue view "$issue" --repo "$REPO" --json body --jq .body) == "$(cat "$body_file")" ]]; then
      summary "Issue #$issue is already up to date."
    elif [[ $dry_run -eq 1 ]]; then
      summary "Dry run: would update issue #$issue."
    else
      gh issue edit "$issue" --repo "$REPO" --body-file "$body_file" > /dev/null
      summary "Updated issue #$issue ($relevant new upstream commits)."
    fi
  fi

  if [[ $dry_run -eq 1 ]]; then
    echo
    echo "Title: $ISSUE_TITLE"
    echo "----------------------------------------------------------------"
    cat "$body_file"
    echo "----------------------------------------------------------------"
  fi
elif [[ -n $issue ]]; then
  if [[ $total -eq 0 ]]; then
    comment="Closed automatically: the installer's pinned commit is now the latest upstream commit."
  else
    comment="Closed automatically: upstream has $(plural "$total" 'newer commit'), but none of them change Basilisk II or SheepShaver."
  fi
  if [[ $dry_run -eq 1 ]]; then
    summary "Dry run: would close issue #$issue with the comment: $comment"
  else
    gh issue close "$issue" --repo "$REPO" --comment "$comment" > /dev/null
    summary "Closed issue #$issue. $comment"
  fi
else
  summary "Nothing to report: no new upstream changes to Basilisk II or SheepShaver."
fi
