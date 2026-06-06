# Contributing to az-reaper

Thanks for helping tend the fields! 🌾

## Development

`az-reaper` is a single Bash script (`az-reaper`) plus a test suite. There's no
build step.

```bash
git clone https://github.com/outofrange-consulting/az-reaper
cd az-reaper
./az-reaper --help
```

To run it from your working copy, just call the script directly, or drop it on
your `PATH`:

```bash
ln -s "$PWD/az-reaper" /usr/local/bin/az-reaper
```

The only Azure DevOps touchpoint is `--check-prs`, which shells out to
`az repos pr list`. Everything else is local `git`, so you can develop and test
the bulk of the tool entirely offline.

## Before you open a PR

1. **Lint** with ShellCheck (warnings are treated as errors in CI):

   ```bash
   shellcheck --severity=warning az-reaper tests/test.sh
   ```

   Or install the pre-commit hook: `pre-commit install`.

2. **Test** — the suite spins up a throwaway worktree sandbox and exercises
   discovery, classification, dry-run safety, and real reaping:

   ```bash
   tests/test.sh
   ```

   It runs on both macOS (BSD tools) and Linux (GNU tools); please keep it that way.

## Guidelines

- Keep it portable: no GNU-only flags without a BSD fallback (see `file_mtime`).
- Never traverse macOS TCC-protected directories by default — that list lives in
  `TCC_DENY` and must stay comprehensive.
- Safety first: anything that could lose work (`dirty`, `unpushed`, `orphan`) must
  stay behind `--force`.
- The Azure DevOps integration must stay **optional and offline-degrading**: if
  `az` is absent or the repo has no Azure DevOps remote, `az-reaper` must still
  list and reap based on the local `git` signals alone.
- Match the surrounding style; update the README and CHANGELOG with user-facing changes.

## Reporting bugs

Open an issue with your OS, `git --version`, the command you ran, and what you
expected versus what happened. An `az-reaper --json --dry-run` snippet of the
affected worktree (paths redacted as you like) helps a lot.
