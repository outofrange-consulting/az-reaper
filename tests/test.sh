#!/usr/bin/env bash
#
# Test suite for gh-reaper.
# Runs structural checks plus an end-to-end worktree sandbox: discovery,
# classification, JSON output, dry-run safety, and real reaping.
#
set -uo pipefail

GREEN='\033[0;32m'; RED='\033[0;31m'; NC='\033[0m'
RUN=0; PASS=0; FAIL=0

# Resolve repo root (this script lives in tests/).
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
REAPER="$ROOT/gh-reaper"

ok()   { printf "${GREEN}PASS${NC} %s\n" "$1"; PASS=$((PASS+1)); }
no()   { printf "${RED}FAIL${NC} %s\n  -> %s\n" "$1" "$2"; FAIL=$((FAIL+1)); }
check(){ RUN=$((RUN+1)); }

# Local git that works offline with file:// remotes.
g() {
    command git \
        -c init.defaultBranch=main \
        -c user.email=test@example.com -c user.name=test \
        -c advice.detachedHead=false \
        -c protocol.file.allow=always "$@"
}

# ---------------------------------------------------------------------------
# Structural checks
# ---------------------------------------------------------------------------
check; [ -x "$REAPER" ] && ok "script is executable" || no "script is executable" "not found/executable"
check; head -n1 "$REAPER" | grep -q "#!/usr/bin/env bash" && ok "portable shebang" || no "portable shebang" "wrong shebang"
check; grep -q "^set -euo pipefail" "$REAPER" && ok "strict mode" || no "strict mode" "missing set -euo pipefail"
check; grep -q 'VERSION=' "$REAPER" && grep -q 'EXTENSION_NAME=' "$REAPER" && ok "metadata present" || no "metadata present" "missing VERSION/EXTENSION_NAME"

check
if out="$("$REAPER" --version 2>&1)" && [[ "$out" == *"gh-reaper version"* ]]; then
    ok "--version"
else
    no "--version" "$out"
fi

check
help="$("$REAPER" --help 2>&1)"
missing=""
for s in "USAGE:" "OPTIONS:" "STATUS FLAGS:" "EXAMPLES:"; do
    [[ "$help" == *"$s"* ]] || missing="$missing $s"
done
[ -z "$missing" ] && ok "--help has all sections" || no "--help has all sections" "missing:$missing"

check
if "$REAPER" --min-age nope >/dev/null 2>&1; then
    no "rejects bad --min-age" "exit 0 on non-numeric"
else
    ok "rejects bad --min-age"
fi

# ---------------------------------------------------------------------------
# Integration sandbox
# ---------------------------------------------------------------------------
if ! command -v git >/dev/null 2>&1; then
    echo "SKIP integration tests (git not available)"
else
    SBX="$(mktemp -d)/sbx"; mkdir -p "$SBX"
    trap 'rm -rf "$(dirname "$SBX")"' EXIT
    (
        cd "$SBX" || exit 1
        g init --bare remote.git >/dev/null
        g init repo >/dev/null
        cd repo || exit 1
        g remote add origin "$SBX/remote.git"
        echo hi > a.txt; g add a.txt; g commit -qm init; g push -q -u origin main
        # clean worktree (branch pushed)
        g branch feat-clean
        g worktree add -q ../wt-clean feat-clean
        g push -q origin feat-clean
        # dirty worktree
        g worktree add -q ../wt-dirty -b feat-dirty
        echo x > ../wt-dirty/b.txt
    ) >/dev/null 2>&1

    check
    json="$("$REAPER" --json --path "$SBX" 2>/dev/null)"
    if command -v jq >/dev/null 2>&1; then
        n="$(printf '%s' "$json" | jq 'length' 2>/dev/null)"
        [ "$n" = 2 ] && ok "discovers 2 worktrees (JSON)" || no "discovers 2 worktrees (JSON)" "got: $n"
        check
        statuses="$(printf '%s' "$json" | jq -r '.[].status' 2>/dev/null | sort | tr '\n' ',')"
        [ "$statuses" = "clean,dirty," ] && ok "classifies clean + dirty" || no "classifies clean + dirty" "got: $statuses"
    else
        ok "discovers 2 worktrees (JSON) [jq missing, skipped count]"
    fi

    check  # default is read-only
    "$REAPER" --no-color --path "$SBX" >/dev/null 2>&1
    if [ -d "$SBX/wt-clean" ] && [ -d "$SBX/wt-dirty" ]; then
        ok "default is read-only (no deletion)"
    else
        no "default is read-only (no deletion)" "a worktree disappeared without --reap"
    fi

    check  # --yes without --reap must not delete
    "$REAPER" --yes --no-color --path "$SBX" >/dev/null 2>&1
    if [ -d "$SBX/wt-clean" ] && [ -d "$SBX/wt-dirty" ]; then
        ok "--yes without --reap deletes nothing"
    else
        no "--yes without --reap deletes nothing" "a worktree disappeared without --reap"
    fi

    check  # --reap --yes reaps clean, skips dirty
    "$REAPER" --reap --yes --no-color --path "$SBX" >/dev/null 2>&1
    if [ ! -d "$SBX/wt-clean" ] && [ -d "$SBX/wt-dirty" ]; then
        ok "--reap --yes reaps clean, skips dirty"
    else
        no "--reap --yes reaps clean, skips dirty" "clean present? $([ -d "$SBX/wt-clean" ] && echo yes || echo no); dirty present? $([ -d "$SBX/wt-dirty" ] && echo yes || echo no)"
    fi

    check  # --reap --force reaps dirty
    "$REAPER" --reap --yes --force --no-color --path "$SBX" >/dev/null 2>&1
    if [ ! -d "$SBX/wt-dirty" ]; then
        ok "--reap --force reaps dirty"
    else
        no "--reap --force reaps dirty" "dirty worktree still present"
    fi
fi

# ---------------------------------------------------------------------------
echo
printf "Tests run: %d   ${GREEN}passed: %d${NC}   ${RED}failed: %d${NC}\n" "$RUN" "$PASS" "$FAIL"
[ "$FAIL" -eq 0 ]
