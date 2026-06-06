"""Core worktree-reaping engine for the ``az reaper`` extension.

This module is intentionally free of any ``azure.cli`` / ``knack`` imports so it
can be unit-tested with nothing more than Python and ``git``. The Azure CLI glue
lives in :mod:`azext_reaper.custom` and friends; everything that actually walks
the disk, classifies worktrees, and reaps them lives here.

It is a faithful Python port of the ``az-reaper`` Bash script: same discovery,
the same gitignore-aware "last touched" age signal, the same
clean/dirty/unpushed/merged/pr-merged/orphan classification, and the same
read-only-by-default safety model. The only Azure DevOps touchpoint is
:func:`pr_completed`, which shells out to ``az repos pr list`` exactly like the
script's ``--check-prs``.
"""

import fnmatch
import os
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

# ---------------------------------------------------------------------------
# Constants (kept in lock-step with the az-reaper Bash script)
# ---------------------------------------------------------------------------

# Dependency lock files: regenerated from a manifest, so a lone change carries no
# authored content. Treated like .gitignored files unless ignore_locks is False.
REGENERABLE_LOCKS = [
    "package-lock.json", "npm-shrinkwrap.json", "yarn.lock", "pnpm-lock.yaml",
    "bun.lockb", "bun.lock", "composer.lock", "Gemfile.lock", "Cargo.lock",
    "poetry.lock", "Pipfile.lock", "go.sum", "flake.lock", "gradle.lockfile",
    "packages.lock.json",
]
# Two pathspecs per name: the file at the repo root and at any nesting depth.
LOCK_EXCLUDE = []
for _lock in REGENERABLE_LOCKS:
    LOCK_EXCLUDE.append(":(exclude){}".format(_lock))
    LOCK_EXCLUDE.append(":(exclude)*/{}".format(_lock))

# Directory *names* never descended into (heavy or pure noise).
PRUNE_DIR_NAMES = {
    "node_modules", ".git", ".Trash", "Library", ".cache", "Caches", ".npm",
    ".pnpm-store", ".yarn", ".venv", "venv", ".tox", ".gradle", ".terraform",
    ".next", "DerivedData", "Pods", ".workspace",
}

# Curated, fast, macOS-TCC-safe default scan roots (only those that exist).
# Includes Windows conventions ('source/repos' is Visual Studio's default).
_DEFAULT_ROOT_RELATIVE = [
    "Developer", "Projects", "projects", "Code", "code", "src", "Source",
    "source/repos", "dev", "Dev", "git", "repos", "Repositories", "work",
    "workspace", "Workspace", "conductor", ".conductor", "intent/workspaces",
    ".codex/worktrees", "worktrees", ".worktrees", "go/src",
]


def _tcc_deny():
    """Absolute paths that trigger macOS privacy dialogs or are pure noise.

    macOS-only: TCC (Transparency, Consent, and Control) is an Apple concept, so
    on Linux and Windows there is nothing to avoid -- pruning Desktop/Documents/
    Downloads there would just hide real repos (e.g. Windows users who keep clones
    under ``Documents\\GitHub`` or ``source\\repos``). Returns an empty set off
    macOS. Always pruned on macOS, even under ``scan_all``.
    """
    if sys.platform != "darwin":
        return set()
    home = os.path.expanduser("~")
    paths = [
        os.path.join(home, d) for d in (
            "Library", "Desktop", "Documents", "Downloads", "Pictures",
            "Movies", "Music", "Public", ".Trash", "Applications",
        )
    ]
    paths += ["/Volumes", "/System", "/private", "/Network", "/cores", "/Library"]
    return {os.path.normpath(p) for p in paths}


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------

def detect_jobs():
    """Default parallelism: online CPU count, capped to [1, 16]."""
    n = os.cpu_count() or 4
    return max(1, min(16, n))


def _run_bytes(cmd, cwd=None):
    """Run *cmd*, return stdout bytes, or ``None`` on any failure."""
    try:
        proc = subprocess.run(
            cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        )
    except (OSError, ValueError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout


def _git_bytes(wt, *args):
    return _run_bytes(["git", "-C", wt, *args])


def _git_text(wt, *args):
    out = _git_bytes(wt, *args)
    if out is None:
        return None
    return out.decode("utf-8", "replace").strip()


def _git_ok(wt, *args):
    """True iff ``git -C wt <args>`` exits 0 (for predicate subcommands)."""
    try:
        return subprocess.run(
            ["git", "-C", wt, *args],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        ).returncode == 0
    except OSError:
        return False


def file_mtime(path):
    try:
        return int(os.lstat(path).st_mtime)
    except OSError:
        return 0


# ``du`` exists on macOS/Linux and inside Git Bash/WSL, but not on native
# Windows. Resolve it once; fall back to a pure-Python walk when it's absent.
_DU = shutil.which("du")


def _py_dir_size_kb(path):
    """Recursive apparent size in KiB (Windows / no-``du`` fallback)."""
    total = 0
    for dirpath, _dirnames, filenames in os.walk(path, followlinks=False):
        for name in filenames:
            try:
                total += os.lstat(os.path.join(dirpath, name)).st_size
            except OSError:
                continue
    return (total + 1023) // 1024


def du_size_kb(path):
    """Disk usage in KiB. Uses ``du -sk`` when available (matches the script),
    otherwise a portable Python walk. Returns 0 on failure."""
    if _DU:
        out = _run_bytes([_DU, "-sk", path])
        if out:
            head = out.split(None, 1)[0] if out.split() else b"0"
            try:
                return int(head)
            except ValueError:
                pass
    return _py_dir_size_kb(path)


def newest_unignored_mtime(wt, ignore_locks):
    """Newest mtime among tracked + untracked-but-not-ignored files.

    Mirrors the script: gitignored paths (node_modules, build output, caches)
    are excluded so a routine install/build/checkout does not reset the apparent
    age. Regenerable lock files are excluded too unless *ignore_locks* is False.
    Returns 0 when there are no such files.
    """
    excl = LOCK_EXCLUDE if ignore_locks else []
    newest = 0
    arg_sets = (
        ["ls-files", "-z", "--", ".", *excl],
        ["ls-files", "-z", "--others", "--exclude-standard", "--", ".", *excl],
    )
    for args in arg_sets:
        out = _git_bytes(wt, *args)
        if not out:
            continue
        for rel in out.split(b"\0"):
            if not rel:
                continue
            try:
                p = os.path.join(wt, os.fsdecode(rel))
                m = int(os.lstat(p).st_mtime)
            except OSError:
                continue
            if m > newest:
                newest = m
    return newest


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------

def _should_prune_dir(abspath, name, tcc):
    if name in PRUNE_DIR_NAMES or fnmatch.fnmatch(name, "*.noindex"):
        return True
    return os.path.normpath(abspath) in tcc


def find_git_markers(root):
    """Yield absolute paths to ``.git`` *files* (worktree markers) under *root*.

    Heavy/cache directories and macOS TCC-protected locations are pruned, so the
    walk stays fast and never trips privacy prompts.
    """
    tcc = _tcc_deny()
    root = os.path.normpath(root)
    if root in tcc:
        return
    for dirpath, dirnames, filenames in os.walk(root, topdown=True, followlinks=False):
        # Prune in place so os.walk does not descend.
        dirnames[:] = [
            d for d in dirnames
            if not _should_prune_dir(os.path.join(dirpath, d), d, tcc)
        ]
        if ".git" in filenames:
            yield os.path.join(dirpath, ".git")


def resolve_roots(paths=None, scan_all=False):
    """Resolve scan roots: explicit *paths* win, else $HOME under *scan_all*,
    else the curated set of existing developer directories plus the CWD."""
    home = os.path.expanduser("~")
    if paths:
        candidates = list(paths)
    elif scan_all:
        candidates = [home]
    else:
        candidates = [os.getcwd()]
        candidates += [os.path.join(home, rel) for rel in _DEFAULT_ROOT_RELATIVE]

    seen = set()
    roots = []
    for c in candidates:
        if not os.path.isdir(c):
            continue
        real = os.path.realpath(c)
        if real in seen:
            continue
        seen.add(real)
        roots.append(real)
    return roots


# ---------------------------------------------------------------------------
# Azure DevOps PR check (the only Azure DevOps touchpoint)
# ---------------------------------------------------------------------------

def _az_argv(args):
    """Build an argv that runs the Azure CLI cross-platform, or ``None``.

    On Windows ``az`` is a ``.cmd`` shim, which ``CreateProcess`` cannot launch
    directly, so it is invoked through ``cmd /c``. Elsewhere the resolved
    executable is run as-is. Returns ``None`` when ``az`` is not installed.
    """
    az = shutil.which("az")
    if not az:
        return None
    if os.name == "nt":
        return ["cmd", "/c", az, *args]
    return [az, *args]


def pr_completed(wt, branch):
    """True iff *branch* has a COMPLETED (merged) Azure DevOps pull request.

    Shells out to ``az repos pr list`` from inside *wt* so the org/project/
    repository auto-detect from the worktree's remote. Best-effort and offline-
    degrading: any failure (no ``az``, no Azure DevOps remote, no network, not
    signed in) is treated as "not merged".
    """
    argv = _az_argv(
        ["repos", "pr", "list", "--source-branch", branch,
         "--status", "completed", "--query", "length(@)", "-o", "tsv"])
    if argv is None:
        return False
    out = _run_bytes(argv, cwd=wt)
    if not out:
        return False
    try:
        return int(out.decode("utf-8", "replace").strip() or "0") > 0
    except ValueError:
        return False


# ---------------------------------------------------------------------------
# Inspection
# ---------------------------------------------------------------------------

def _default_branch_ref(wt):
    ref = _git_text(wt, "symbolic-ref", "-q", "refs/remotes/origin/HEAD")
    if ref:
        return ref
    for cand in ("origin/main", "origin/master", "main", "master"):
        if _git_ok(wt, "rev-parse", "-q", "--verify", cand):
            return cand
    return None


def inspect_marker(gitfile, ignore_locks=True, check_prs=False):
    """Inspect one ``.git`` worktree marker.

    Returns a record dict, or ``None`` if *gitfile* is not a linked worktree
    (e.g. a submodule, or an unreadable marker). Record keys:
    ``touched, sizeKb, branch, status, path, mainWorktree, merged``.
    """
    wt = os.path.dirname(gitfile)

    try:
        with open(gitfile, "r", encoding="utf-8", errors="replace") as fh:
            line = fh.readline().strip()
    except OSError:
        return None
    if not line.startswith("gitdir:"):
        return None
    gitdir = line[len("gitdir:"):].strip()
    # Only worktrees -- not submodules ('.../modules/...'). Normalize separators
    # first: on Windows git may write the gitdir with backslashes.
    if "/worktrees/" not in gitdir.replace("\\", "/"):
        return None
    if not os.path.isabs(gitdir):
        gitdir = os.path.join(wt, gitdir)

    size_kb = du_size_kb(wt)
    dir_m = file_mtime(wt)

    dirty = unpushed = merged = prmerged = False
    main = ""

    if _git_ok(wt, "rev-parse", "--is-inside-work-tree"):
        commit_ct = _git_text(wt, "log", "-1", "--format=%ct") or "0"
        try:
            touched = int(commit_ct)
        except ValueError:
            touched = 0
        newest_m = newest_unignored_mtime(wt, ignore_locks)
        touched = max(touched, newest_m)
        if touched <= 0:
            touched = dir_m

        branch = _git_text(wt, "symbolic-ref", "--quiet", "--short", "HEAD")
        if not branch:
            short = _git_text(wt, "rev-parse", "--short", "HEAD") or "?"
            branch = "detached@{}".format(short)

        # Dirty = uncommitted/untracked changes (lock churn excluded by default).
        status_args = ["status", "--porcelain", "--", "."]
        if ignore_locks:
            status_args += LOCK_EXCLUDE
        porcelain = _git_text(wt, *status_args)
        if porcelain:
            dirty = True

        # Unpushed = commits that live nowhere on a remote.
        upstream = _git_text(wt, "rev-parse", "--abbrev-ref",
                             "--symbolic-full-name", "@{u}")
        if upstream:
            ahead = _git_text(wt, "rev-list", "--count",
                              "{}..HEAD".format(upstream)) or "0"
            try:
                if int(ahead) > 0:
                    unpushed = True
            except ValueError:
                pass
        elif not (_git_text(wt, "branch", "-r", "--contains", "HEAD") or ""):
            unpushed = True

        # Merged = HEAD already contained in the default branch (offline).
        ref = _default_branch_ref(wt)
        if ref and _git_ok(wt, "merge-base", "--is-ancestor", "HEAD", ref):
            merged = True

        # Optional, networked: a squash/rebase completion is not an ancestor,
        # yet the PR is completed on Azure DevOps.
        if not merged and check_prs and not branch.startswith("detached@"):
            prmerged = pr_completed(wt, branch)

        first = _git_text(wt, "worktree", "list", "--porcelain") or ""
        first = first.split("\n", 1)[0]
        if first.startswith("worktree "):
            main = first[len("worktree "):]
        if not main:
            main = wt

        status = _assemble_status(dirty, unpushed, merged, prmerged)
    else:
        # Git can't operate -> the main repository is gone.
        logs_m = file_mtime(os.path.join(gitdir, "logs", "HEAD"))
        touched = max(dir_m, logs_m)
        status = "orphan"
        branch = "?"
        head = os.path.join(gitdir, "HEAD")
        try:
            with open(head, "r", encoding="utf-8", errors="replace") as fh:
                hline = fh.readline().strip()
            if hline.startswith("ref: refs/heads/"):
                branch = hline[len("ref: refs/heads/"):]
        except OSError:
            pass
        main = ""

    return {
        "touched": touched,
        "sizeKb": size_kb,
        "branch": branch,
        "status": status,
        "path": wt,
        "mainWorktree": main,
        "merged": "merged" in status,
    }


def _assemble_status(dirty, unpushed, merged, prmerged):
    """Compose the status label. 'merged'/'pr-merged' supersede 'unpushed'."""
    if merged or prmerged:
        unpushed = False
    parts = []
    if dirty:
        parts.append("dirty")
    if unpushed:
        parts.append("unpushed")
    if prmerged:
        parts.append("pr-merged")
    elif merged:
        parts.append("merged")
    return " ".join(parts) if parts else "clean"


# ---------------------------------------------------------------------------
# Scan (discover -> inspect in parallel -> filter -> sort)
# ---------------------------------------------------------------------------

def scan(paths=None, scan_all=False, min_age=0, min_size=0, merged_only=False,
         check_prs=False, ignore_locks=True, jobs=None, now=None):
    """Return a list of worktree records (oldest first) matching the filters.

    Each record is a public dict:
    ``{path, branch, status, merged, sizeKb, touched, ageDays, mainWorktree}``.
    This is always read-only.
    """
    if now is None:
        now = int(time.time())
    roots = resolve_roots(paths, scan_all)
    if not roots:
        return []

    markers = []
    seen = set()
    for root in roots:
        for marker in find_git_markers(root):
            if marker in seen:
                continue
            seen.add(marker)
            markers.append(marker)

    workers = max(1, jobs or detect_jobs())
    records = []
    if markers:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for rec in pool.map(
                lambda m: inspect_marker(m, ignore_locks, check_prs), markers
            ):
                if rec:
                    records.append(rec)

    min_age_secs = max(0, min_age) * 86400
    min_kb = max(0, min_size) * 1024
    out = []
    for rec in records:
        age_secs = now - rec["touched"]
        if age_secs < min_age_secs:
            continue
        if rec["sizeKb"] < min_kb:
            continue
        if merged_only and "merged" not in rec["status"]:
            continue
        out.append({
            "path": rec["path"],
            "branch": rec["branch"],
            "status": rec["status"],
            "merged": rec["merged"],
            "sizeKb": rec["sizeKb"],
            "touched": rec["touched"],
            "ageDays": max(0, age_secs) // 86400,
            "mainWorktree": rec["mainWorktree"],
        })

    out.sort(key=lambda r: r["touched"])
    return out


# ---------------------------------------------------------------------------
# Reaping
# ---------------------------------------------------------------------------

def is_risky(status):
    return any(tag in status for tag in ("dirty", "unpushed", "orphan"))


def reap_one(wt, main, status):
    """Remove one worktree. Returns ``(ok, message)``.

    Orphans (no usable main repo) are removed with ``rmtree``. Everything else
    goes through ``git worktree remove`` run from the main worktree, forcing past
    git's mechanical "modified or untracked files" check when the reap decision
    has already been made (risky statuses, or leftover ignored lock churn).
    """
    if status == "orphan" or not main:
        try:
            shutil.rmtree(wt)
            return True, ""
        except OSError as exc:
            return False, str(exc)

    args = ["worktree", "remove"]
    porcelain = _git_text(wt, "status", "--porcelain")
    if is_risky(status) or porcelain:
        args.append("--force")
    args.append(wt)
    try:
        proc = subprocess.run(
            ["git", "-C", main, *args],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        )
    except OSError as exc:
        return False, str(exc)
    if proc.returncode == 0:
        return True, ""
    return False, proc.stdout.decode("utf-8", "replace").strip()


def prune_main(main):
    """Run ``git worktree prune`` on a main worktree (best-effort)."""
    _git_ok(main, "worktree", "prune")
