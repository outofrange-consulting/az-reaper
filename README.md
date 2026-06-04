# gh-reaper

[![99% Vibe_Coded](https://img.shields.io/badge/99%25-Vibe_Coded-ff69b4?style=for-the-badge&logo=claude&logoColor=white)](https://github.com/ai-ecoverse/vibe-coded-badge-action)

> _"Seasons don't fear the reaper / Nor do the wind, the sun, or the rain..."_
> — and neither do the dozen git worktrees you spun up six months ago and forgot about.

**`gh reaper`** is a [GitHub CLI](https://cli.github.com/) extension that hunts down stale **git worktrees** across your machine, tells you how long each has been gathering dust and how much disk it's hoarding, then offers to reap the ones you've left behind.

```
AGE      SIZE  STATUS    BRANCH                 PATH
8mo    160.7M  clean     opencode-blog-archive  ~/Developer/helix-website/.conductor/opencode-blog-archive
7mo    116.1M  dirty     submit-to-zed-registry ~/Developer/zed-elvish/.conductor/islamabad
7mo      6.0M  orphan    ?                      ~/Developer/tree-sitter-fountain-forced-scene-headings
6mo      544K  clean     renovate/actions-check ~/Developer/aem-boilerplate/.yolo/claude-1
```

Worktrees are wonderful — until you have forty of them. Tools like [Conductor](https://conductor.build), `git worktree add`, and various AI agents scatter checkouts all over your disk, and `git worktree prune` only cleans up the ones whose directories are *already gone*. `gh reaper` finds the living-but-forgotten ones.

## Features

- **Machine-wide discovery** — sweeps your usual code roots (`~/Developer`, `~/conductor`, `~/Projects`, `~/go/src`, …) for linked worktrees, not just the repo you're standing in.
- **Age & size at a glance** — every worktree shows when it was last touched and how much disk it occupies, sorted oldest-first.
- **Safety classification** — each worktree is tagged `clean`, `dirty`, `unpushed`, or `orphan`. Risky ones are never reaped without `--force`.
- **macOS-friendly** — scans a curated set of dev directories by default, so it's fast and **never trips macOS privacy (TCC) permission prompts** for Desktop, Documents, Downloads, Photos, and friends.
- **Reaps the right way** — uses `git worktree remove` (run from the main worktree) so git's bookkeeping stays consistent; `--prune` tidies the admin entries afterward.
- **Interactive or unattended** — confirm each one, `[a]ll` at once, or `--yes` to sweep without prompts. `--dry-run` and `--json` for the cautious and the scripty.

## Installation

```bash
gh extension install ai-ecoverse/gh-reaper
```

Upgrade later with:

```bash
gh extension upgrade reaper
```

**Requirements:** `git`, plus the usual POSIX suspects (`find`, `du`, `stat`, `awk`). `jq` is only needed for `--json`. Works on macOS (BSD tools) and Linux (GNU tools).

## Usage

```bash
# Survey forgotten worktrees in your usual code dirs
gh reaper

# Only the truly stale: untouched 30+ days and bigger than 100 MB
gh reaper --min-age 30 --min-size 100

# Look but don't touch
gh reaper --dry-run

# Scan a specific spot and reap interactively
gh reaper ~/work/monorepo

# Reap everything 2+ weeks old, no questions asked
gh reaper --min-age 14 --yes

# Machine-wide sweep (still skips TCC-protected dirs)
gh reaper --all --dry-run

# Pipe the inventory into your own tooling
gh reaper --json | jq '.[] | select(.sizeKb > 100000) | .path'
```

### Options

```
gh reaper [OPTIONS] [PATH...]

  -d, --min-age DAYS   Only show worktrees untouched for at least DAYS (default: 0)
  -s, --min-size MB    Only show worktrees at least MB megabytes in size (default: 0)
  -p, --path DIR       Add a scan root (repeatable; also accepted as PATH args)
  -a, --all            Scan all of $HOME (still skips TCC-protected dirs)
      --dry-run        List only; never remove anything
  -y, --yes            Reap every matching worktree without prompting
  -f, --force          Allow reaping dirty, unpushed, or orphaned worktrees
      --prune          Run 'git worktree prune' on touched repos afterward
      --json           Emit results as JSON (implies --dry-run)
      --no-color       Disable colored output
  -v, --version        Show version
  -h, --help           Show this help
```

### Status flags

| Status     | Meaning                                                        | Reaped by default? |
| ---------- | ------------------------------------------------------------- | ------------------ |
| `clean`    | No local changes; HEAD exists on a remote — safe to delete     | ✅ yes              |
| `dirty`    | Uncommitted or untracked changes present                       | 🔒 needs `--force` |
| `unpushed` | Commits that exist nowhere on a remote (would be lost)         | 🔒 needs `--force` |
| `orphan`   | The main repository is gone; only the lonely checkout remains  | 🔒 needs `--force` |

## How it works

**Discovery.** A linked worktree is marked by a `.git` *file* (not a directory) whose contents point into `…/worktrees/…`. `gh reaper` finds those with a single pruned `find` per root, skipping `node_modules`, caches, `Library`, `*.noindex`, and the like — and skipping submodules (whose `.git` files point into `…/modules/…`).

**Scan roots.** By default it only walks well-known developer directories that actually exist on your machine, plus your current directory. This keeps it fast and, on macOS, keeps it clear of the TCC-protected folders (Desktop, Documents, Downloads, Pictures, Movies, Music, `Library`, iCloud Drive, external `/Volumes`) that would otherwise pop a permission dialog. `--all` opts into a full `$HOME` sweep but **still** hard-skips those protected locations. Point it anywhere explicitly with a `PATH` argument or `--path`.

**"Last touched."** Age is the most recent of: the working directory's mtime, the worktree's reflog (`logs/HEAD`), and the last commit date. It deliberately **ignores the git index**, because `git status` rewrites the index — so inspecting a worktree would otherwise reset its own apparent age.

**Reaping.** Clean worktrees are removed with `git worktree remove` executed from the *main* worktree (so git won't refuse to remove "the current working tree"). Dirty/unpushed worktrees get `--force` only when you pass `--force`. True orphans — whose main repo is gone, so git can't help — are removed with `rm -rf`, and also only under `--force`.

## Safety

- Nothing is removed in `--dry-run` or `--json` mode.
- `dirty`, `unpushed`, and `orphan` worktrees are **skipped unless `--force`** — your uncommitted edits and unpushed commits are safe by default.
- Interactive mode asks per worktree (`[y]es / [n]o / [a]ll / [q]uit`); only `--yes` skips the prompts.
- It only ever targets linked worktrees — it will never offer to delete a main repository.

> _More cowbell strongly recommended but not required._

## Uninstall

```bash
gh extension remove reaper
```

## License

[Apache-2.0](LICENSE) © the AI Ecoverse contributors.
