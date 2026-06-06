"""Help content for the ``az reaper`` command group."""

from knack.help_files import helps  # pylint: disable=unused-import


helps["reaper"] = """
type: group
short-summary: Harvest stale git worktrees, with Azure DevOps PR awareness.
long-summary: >
  Scans your developer directories for linked git worktrees and reports how long
  each has been gathering dust and how much disk it occupies. 'az reaper list' is
  read-only; 'az reaper reap' deletes. Each worktree is classified
  clean/dirty/unpushed/merged/pr-merged/orphan; with --check-prs, branches whose
  Azure DevOps pull request was completed are tagged 'pr-merged'.
"""

helps["reaper list"] = """
type: command
short-summary: List stale git worktrees (read-only).
long-summary: >
  Walks well-known code roots (or the paths you pass), sized and classified in
  parallel, sorted oldest-first. Never deletes anything. AGE reflects the newest
  non-gitignored change, so a routine install or build does not reset it.
examples:
  - name: Survey forgotten worktrees (read-only)
    text: az reaper list
  - name: Only the truly stale -- untouched 30+ days and bigger than 100 MB
    text: az reaper list --min-age 30 --min-size 100
  - name: Only worktrees already merged, consulting Azure DevOps for squash-merges
    text: az reaper list --merged --check-prs
  - name: Scan a specific directory
    text: az reaper list --path ~/work/monorepo
"""

helps["reaper reap"] = """
type: command
short-summary: Delete stale git worktrees.
long-summary: >
  Removes worktrees with 'git worktree remove' (run from the main worktree).
  clean/merged/pr-merged worktrees are removed; dirty/unpushed/orphan ones are
  skipped unless you pass --force. Pass --yes to skip the per-worktree prompt.
examples:
  - name: Reap clean and merged worktrees, with confirmation prompts
    text: az reaper reap
  - name: Reap everything 2+ weeks old, no prompts
    text: az reaper reap --min-age 14 --yes
  - name: Sweep only worktrees whose Azure DevOps PR is completed
    text: az reaper reap --merged --check-prs --yes
  - name: Also remove risky (dirty/unpushed/orphan) worktrees and prune afterward
    text: az reaper reap --yes --force --prune
"""
