# Changelog

All notable changes to `az-reaper` are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added
- **Windows support** (Git Bash / WSL). CPU detection falls back to
  `NUMBER_OF_PROCESSORS`; the macOS TCC directory pruning is now scoped to macOS
  only, so Windows clones under `Documents\GitHub` or `source\repos` are no longer
  hidden (and `source/repos` is a default scan root); `.git` worktree pointers are
  matched with path separators normalized and Windows drive paths (`C:/...`)
  recognized as absolute. A `.gitattributes` keeps the script (and shell files)
  LF-only so the shebang survives a Windows checkout. CI now also runs on
  `windows-latest`.

## [2.0.0] - 2026-06-06

### Changed
- **Rebranded `gh-reaper` → `az-reaper`.** The tool is now a companion to the
  **Azure DevOps CLI** (`az`) instead of the GitHub CLI (`gh`). The worktree
  engine — discovery, age/size, `clean`/`dirty`/`unpushed`/`merged`/`orphan`
  classification, parallel inspection, and safe reaping — is unchanged. It stays
  a single portable Bash script; install by putting `az-reaper` on your `PATH`
  (Azure CLI extensions are Python wheels, so this ships as a standalone CLI
  rather than an `az extension add` package).
- **`--check-prs` now queries Azure DevOps** via `az repos pr list --status
  completed` (run from inside the worktree so org/project/repository are
  auto-detected from the remote), replacing `gh pr list --state merged`. Azure
  DevOps calls a merged PR "completed"; matching branches are tagged `pr-merged`
  exactly as before. The check is optional and degrades offline: without `az` or
  an Azure DevOps remote, `az-reaper` still lists and reaps on local git signals.

## [1.5.1] - 2026-06-05

### Fixed
- Reaping a `merged`/`clean` worktree that still carried regenerable lock-file
  churn failed: `git worktree remove` refused it with "contains modified or
  untracked files." `reap_one` now forces past that mechanical check for
  worktrees already judged reapable, so the 1.5.0 lock-file feature can actually
  delete them. Added a test that reaps a lock-only merged worktree end-to-end.

## [1.5.0] - 2026-06-05

### Added
- **Lock files are treated like `.gitignore`d files.** A worktree whose only
  uncommitted change is a regenerable dependency lock file (`package-lock.json`,
  `yarn.lock`, `pnpm-lock.yaml`, `Cargo.lock`, `go.sum`, `Gemfile.lock`,
  `poetry.lock`, `composer.lock`, `flake.lock`, …) is no longer flagged `dirty`,
  and lock-file mtimes no longer count toward its age. A stray `npm install` can't
  pin an otherwise-done worktree as un-reapable. Lock changes alongside any real
  edit still count as dirty.
- **`--no-ignore-locks`** to opt out and treat lock-file changes as dirty (the
  pre-1.5 behavior).

## [1.4.0] - 2026-06-05

### Added
- **`merged` status.** Each worktree is now checked for whether its `HEAD` is
  already contained in the repo's default branch (`git merge-base --is-ancestor`),
  an age-independent "this work is done" signal. Merged worktrees are reapable
  without `--force` (when otherwise clean).
- **`-m, --merged` filter.** Show (and with `--reap`, sweep) only worktrees whose
  work is already merged — e.g. `gh reaper --merged --reap`.
- **`--check-prs` (opt-in, networked).** For branches that aren't ancestors of the
  default branch, ask `gh` whether their pull request was merged, tagging them
  `pr-merged`. Catches GitHub squash/rebase-merges that rewrite commit history.
- `merged` boolean field in `--json` output.

### Changed
- **`AGE` now tracks the newest _non-gitignored_ change** (tracked/unignored file
  mtime, or last commit), instead of `max(dir-mtime, reflog, commit)`. A routine
  `npm install`, build, or automated `git checkout` no longer resets a worktree's
  apparent age — fixing worktrees that looked "0 days old" while their actual work
  was months stale. `--min-age` filters on this corrected value. Orphans (no usable
  git) still fall back to the working-dir / reflog mtime.

## [1.3.0] - 2026-06-04

### Added
- Scan Codex's worktree pool by default: `~/.codex/worktrees/<id>/<repo>` is now a
  default root. Codex creates these on demand in the home dotdir (not nested under a
  code root), so it needs an explicit root — unlike Claude Code, whose
  `<repo>/.claude/worktrees/<slug>` checkouts are already discovered inside scanned
  repos.

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
