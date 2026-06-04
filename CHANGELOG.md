# Changelog

All notable changes to `gh-reaper` are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [1.0.0] - 2026-06-04

### Added
- Initial release.
- Machine-wide discovery of linked git worktrees across curated developer roots
  (`~/Developer`, `~/conductor`, `~/Projects`, `~/go/src`, …) plus the current directory.
- Per-worktree reporting of last-touched age and disk size, sorted oldest-first.
- Status classification: `clean`, `dirty`, `unpushed`, `orphan`.
- Safe interactive reaping (`[y]es / [n]o / [a]ll / [q]uit`) with `git worktree remove`,
  plus `--yes`, `--dry-run`, and `--json` modes.
- `--force` gate for dirty/unpushed/orphan worktrees; `--prune` to tidy admin entries.
- `--min-age`, `--min-size`, `--path`, and `--all` filters.
- macOS TCC-safe scanning: protected directories (Desktop, Documents, Downloads,
  Pictures, Library, Volumes, …) are never traversed.
