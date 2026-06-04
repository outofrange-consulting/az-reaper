# Contributing to gh-reaper

Thanks for helping tend the fields! 🌾

## Development

`gh-reaper` is a single Bash script (`gh-reaper`) plus a test suite. There's no
build step.

```bash
git clone https://github.com/ai-ecoverse/gh-reaper
cd gh-reaper
./gh-reaper --help
```

To run it as a real extension from your working copy:

```bash
gh extension install .
```

## Before you open a PR

1. **Lint** with ShellCheck (warnings are treated as errors in CI):

   ```bash
   shellcheck --severity=warning gh-reaper tests/test.sh
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
- Match the surrounding style; update the README and CHANGELOG with user-facing changes.

## Reporting bugs

Open an issue with your OS, `git --version`, the command you ran, and what you
expected versus what happened. A `gh reaper --json --dry-run` snippet of the
affected worktree (paths redacted as you like) helps a lot.
