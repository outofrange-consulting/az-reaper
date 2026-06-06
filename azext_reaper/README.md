# az reaper — Azure CLI extension

`reaper` is an [Azure CLI](https://learn.microsoft.com/cli/azure/) extension that
harvests stale **git worktrees** across your machine and tells you how long each
has been gathering dust and how much disk it's hoarding — with **Azure DevOps**
pull-request awareness. `az reaper list` is **read-only**; `az reaper reap`
deletes.

This is the full, idiomatic `az extension` packaging of
[`az-reaper`](https://github.com/outofrange-consulting/az-reaper) (the standalone
Bash script lives at the repo root). The worktree engine
(`azext_reaper/_reaper.py`) is deliberately free of any `azure.cli` imports, so
it can be unit-tested with nothing but Python and `git`.

## Install

The extension ships as a wheel. Build and install it locally:

```bash
pip install wheel
python setup.py bdist_wheel
az extension add --source dist/reaper-0.1.0-py3-none-any.whl
```

For extension development with [`azdev`](https://github.com/Azure/azure-cli-dev-tools):

```bash
azdev extension add reaper        # from a clone of this repo
```

Remove it with:

```bash
az extension remove --name reaper
```

**Requirements:** `git`, plus the usual POSIX tools (`find`/`du`/`stat` behavior
is reproduced in Python; `du` is shelled out for sizing). The `--check-prs`
signal additionally needs the [Azure DevOps
CLI](https://learn.microsoft.com/azure/devops/cli/) (`az` + the `azure-devops`
extension, signed in, with an Azure DevOps remote). Works on macOS and Linux.

## Usage

```bash
# Survey forgotten worktrees -- read-only
az reaper list

# Only the truly stale: untouched 30+ days and bigger than 100 MB
az reaper list --min-age 30 --min-size 100

# Only worktrees already merged, consulting Azure DevOps for squash-merges
az reaper list --merged --check-prs

# Pipe into jq via JSON output
az reaper list -o json | jq '.[] | select(.sizeKb > 100000) | .path'

# Reap clean + merged worktrees, prompting for each
az reaper reap

# Reap everything 2+ weeks old, no prompts
az reaper reap --min-age 14 --yes

# Sweep only completed Azure DevOps PRs, including risky ones, then prune
az reaper reap --merged --check-prs --yes --force --prune
```

### Arguments

| Argument | Applies to | Meaning |
| --- | --- | --- |
| `--path, -p` | both | Scan root(s); repeatable. Default: curated dev dirs + CWD. |
| `--all, -a` | both | Scan all of `$HOME` (still skips macOS TCC dirs). |
| `--min-age, -d` | both | Only worktrees untouched for at least N days. |
| `--min-size, -s` | both | Only worktrees at least N MB. |
| `--merged, -m` | both | Only worktrees whose work is already merged. |
| `--check-prs` | both | Ask Azure DevOps whether the branch's PR was completed. |
| `--no-ignore-locks` | both | Count regenerable lock-file churn as dirty. |
| `--jobs, -j` | both | Parallel inspection workers (default: CPU count). |
| `--yes, -y` | reap | Delete without prompting per worktree. |
| `--force, -f` | reap | Also remove dirty / unpushed / orphan worktrees. |
| `--prune` | reap | `git worktree prune` touched repos afterward. |

### Status flags

| Status | Meaning | Reaped without `--force`? |
| --- | --- | --- |
| `merged` | HEAD already in the default branch | ✅ |
| `pr-merged` | Azure DevOps PR completed (`--check-prs`) | ✅ |
| `clean` | No local changes; HEAD on a remote | ✅ |
| `dirty` | Uncommitted/untracked changes | 🔒 needs `--force` |
| `unpushed` | Commits that exist nowhere on a remote | 🔒 needs `--force` |
| `orphan` | Main repo gone; only the checkout remains | 🔒 needs `--force` |

## How it works

Same engine as the script: a linked worktree is a `.git` **file** pointing into
`…/worktrees/…`; discovery prunes `node_modules`, caches, and macOS
TCC-protected dirs. "Last touched" is the newest non-gitignored change
(`git ls-files` + last commit), so installs/builds don't reset age. `merged` is
`git merge-base --is-ancestor HEAD <default-branch>`; `--check-prs` consults
`az repos pr list --status completed` for squash/rebase completions. Reaping uses
`git worktree remove` from the main worktree; orphans are removed with `rmtree`.
Inspection runs in parallel across worker threads.

## Tests

The engine has azure-cli-free unit tests (Python + git only):

```bash
python -m unittest azext_reaper.tests.test_reaper_core -v
```

## License

[Apache-2.0](../LICENSE)
