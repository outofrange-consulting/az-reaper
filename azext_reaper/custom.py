"""Implementation of the ``az reaper`` commands.

Thin Azure CLI wrappers over :mod:`azext_reaper._reaper`. Output objects are
returned as plain dicts so the CLI can render them as table or JSON via the
standard ``--output`` flag.
"""

from knack.log import get_logger
from knack.prompting import prompt_y_n, NoTTYException
from knack.util import CLIError

from azext_reaper import _reaper

logger = get_logger(__name__)


def reaper_list(paths=None, scan_all=False, min_age=0, min_size=0,
                merged_only=False, check_prs=False, ignore_locks=True,
                jobs=None):
    """List stale git worktrees (read-only)."""
    return _reaper.scan(
        paths=paths, scan_all=scan_all, min_age=min_age, min_size=min_size,
        merged_only=merged_only, check_prs=check_prs, ignore_locks=ignore_locks,
        jobs=jobs)


def reaper_reap(paths=None, scan_all=False, min_age=0, min_size=0,
                merged_only=False, check_prs=False, ignore_locks=True,
                jobs=None, yes=False, force=False, prune=False):
    """Delete stale git worktrees.

    clean/merged/pr-merged worktrees are removed; dirty/unpushed/orphan ones need
    --force. Without --yes, each candidate is confirmed interactively.
    """
    records = _reaper.scan(
        paths=paths, scan_all=scan_all, min_age=min_age, min_size=min_size,
        merged_only=merged_only, check_prs=check_prs, ignore_locks=ignore_locks,
        jobs=jobs)

    if not records:
        logger.warning("Nothing to reap. The fields are clean.")
        return {"reaped": 0, "reclaimedKb": 0, "details": []}

    reaped = 0
    freed_kb = 0
    touched_mains = []
    details = []

    for rec in records:
        path = rec["path"]
        status = rec["status"]
        main = rec["mainWorktree"]

        if _reaper.is_risky(status) and not force:
            details.append({"path": path, "action": "skipped",
                            "reason": "{} (needs --force)".format(status)})
            continue

        if not yes:
            try:
                if not prompt_y_n("Reap {} [{}, {} KB]?".format(
                        path, status, rec["sizeKb"])):
                    details.append({"path": path, "action": "skipped",
                                    "reason": "declined"})
                    continue
            except NoTTYException:
                raise CLIError(
                    "No TTY for confirmation. Re-run with --yes to reap "
                    "non-interactively.")

        ok, message = _reaper.reap_one(path, main, status)
        if ok:
            reaped += 1
            freed_kb += rec["sizeKb"]
            if main:
                touched_mains.append(main)
            details.append({"path": path, "action": "reaped"})
        else:
            details.append({"path": path, "action": "failed",
                            "reason": message})

    if prune:
        for main in dict.fromkeys(touched_mains):
            _reaper.prune_main(main)

    logger.warning("Reaped %d worktree(s), reclaimed %d KB.", reaped, freed_kb)
    return {"reaped": reaped, "reclaimedKb": freed_kb, "details": details}
