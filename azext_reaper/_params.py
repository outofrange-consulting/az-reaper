"""Argument definitions for the ``az reaper`` command group."""

from azure.cli.core.commands.parameters import get_three_state_flag


def load_arguments(self, _command):
    # Shared discovery/filter arguments (used by both list and reap).
    with self.argument_context("reaper") as c:
        c.argument(
            "paths", options_list=["--path", "-p"], nargs="*",
            help="Scan root(s). Repeatable. Defaults to a curated set of "
                 "developer directories plus the current directory.")
        c.argument(
            "scan_all", options_list=["--all", "-a"],
            arg_type=get_three_state_flag(),
            help="Scan all of $HOME (still skips macOS TCC-protected dirs).")
        c.argument(
            "min_age", options_list=["--min-age", "-d"], type=int,
            help="Only worktrees untouched for at least this many DAYS.")
        c.argument(
            "min_size", options_list=["--min-size", "-s"], type=int,
            help="Only worktrees at least this many MB in size.")
        c.argument(
            "merged_only", options_list=["--merged", "-m"],
            arg_type=get_three_state_flag(),
            help="Only worktrees whose work is already merged.")
        c.argument(
            "check_prs", options_list=["--check-prs"],
            arg_type=get_three_state_flag(),
            help="For non-merged branches, ask Azure DevOps (az repos pr list) "
                 "whether their pull request was completed. Needs the "
                 "azure-devops extension, an Azure DevOps remote, auth + network.")
        c.argument(
            "ignore_locks", options_list=["--no-ignore-locks"],
            action="store_false",
            help="Count regenerable lock-file changes (package-lock.json, "
                 "yarn.lock, Cargo.lock, ...) as dirty. By default they are not.")
        c.argument(
            "jobs", options_list=["--jobs", "-j"], type=int,
            help="Parallel inspection workers (default: CPU count; 1 = serial).")

    # Reap-only arguments.
    with self.argument_context("reaper reap") as c:
        c.argument(
            "yes", options_list=["--yes", "-y"],
            arg_type=get_three_state_flag(),
            help="Delete without prompting for each worktree.")
        c.argument(
            "force", options_list=["--force", "-f"],
            arg_type=get_three_state_flag(),
            help="Also remove dirty, unpushed, or orphaned worktrees.")
        c.argument(
            "prune", options_list=["--prune"],
            arg_type=get_three_state_flag(),
            help="Run 'git worktree prune' on touched repos afterward.")
