# Changelog

All notable changes to `gh-reaper` are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [1.2.0] - 2026-06-04

### Added
- **Parallel inspection.** Worktrees are now sized/classified concurrently across
  workers (default: CPU count), instead of one at a time. A real 238-worktree /
  114 GB scan dropped from ~121s to ~31s (~4× on 16 cores), with identical results.
- `-j, --jobs N` to control worker count (`--jobs 1` restores serial behavior).

### Changed
- `inspect_marker` now emits a TSV record on stdout; main() fans markers out to
  per-PID temp files (no output interleaving, no reliance on pipe atomicity).

## [1.1.0] - 2026-06-04

### Added
- Scan intent's worktree pool by default: `~/intent/workspaces/<workspace>/<repo>`
  is now a default root, alongside Conductor's `.conductor` and yolo's `.yolo`.
- Prune intent's `.workspace/` metadata directories during discovery (they hold no
  worktrees) to keep scanning fast.

### Note
- Reaping an intent worktree removes the `<repo>` checkout but leaves intent's
  sibling `.workspace/` metadata, which may leave the intent app with a dangling
  workspace. Listing is read-only and safe; use `--reap` here deliberately.

## [1.0.0] - 2026-06-04

### Added
- Initial release.
- Machine-wide discovery of linked git worktrees across curated developer roots
  (`~/Developer`, `~/conductor`, `~/Projects`, `~/go/src`, …) plus the current directory.
- Per-worktree reporting of last-touched age and disk size, sorted oldest-first.
- Status classification: `clean`, `dirty`, `unpushed`, `orphan`.
- **Read-only by default**: bare `gh reaper` only lists and changes nothing.
- `--reap` performs deletion via `git worktree remove` — interactive
  (`[y]es / [n]o / [a]ll / [q]uit`), or `--yes` to skip prompts. `--yes`/`--force`
  do nothing without `--reap`.
- `--force` gate for dirty/unpushed/orphan worktrees; `--prune` to tidy admin entries.
- `--json` for machine-readable inventory; `--dry-run` as the explicit form of the
  default read-only behavior.
- `--min-age`, `--min-size`, `--path`, and `--all` filters.
- macOS TCC-safe scanning: protected directories (Desktop, Documents, Downloads,
  Pictures, Library, Volumes, …) are never traversed.
