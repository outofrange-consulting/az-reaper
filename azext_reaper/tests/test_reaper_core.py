"""Unit tests for the azure-cli-free reaper engine (azext_reaper._reaper).

These build throwaway git worktree sandboxes and exercise discovery,
classification, the gitignore-aware age signal, lock-file handling, and real
reaping -- mirroring the Bash test suite. They need only Python + git (no
azure-cli), so the engine can be validated in plain CI.

The ``_reaper`` module is loaded by file path so importing it does not pull in
``azext_reaper/__init__.py`` (which requires azure.cli.core).
"""

import importlib.util
import os
import subprocess
import tempfile
import time
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_CORE_PATH = os.path.normpath(os.path.join(_HERE, "..", "_reaper.py"))
_spec = importlib.util.spec_from_file_location("reaper_core", _CORE_PATH)
reaper = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(reaper)


def _git(cwd, *args, env=None):
    base = [
        "git",
        "-c", "init.defaultBranch=main",
        "-c", "user.email=test@example.com",
        "-c", "user.name=test",
        "-c", "advice.detachedHead=false",
        "-c", "protocol.file.allow=always",
    ]
    full_env = dict(os.environ)
    if env:
        full_env.update(env)
    subprocess.run(base + list(args), cwd=cwd, check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                   env=full_env)


def _have_git():
    try:
        subprocess.run(["git", "--version"], stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, check=True)
        return True
    except (OSError, subprocess.CalledProcessError):
        return False


@unittest.skipUnless(_have_git(), "git not available")
class ClassificationTests(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(self._cleanup)
        self.sbx = os.path.join(self.tmp, "sbx")
        os.makedirs(self.sbx)
        self._build_sandbox()

    def _cleanup(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _build_sandbox(self):
        sbx = self.sbx
        _git(sbx, "init", "--bare", "remote.git")
        _git(sbx, "init", "repo")
        repo = os.path.join(sbx, "repo")
        _git(repo, "remote", "add", "origin", os.path.join(sbx, "remote.git"))
        with open(os.path.join(repo, "a.txt"), "w") as fh:
            fh.write("hi\n")
        _git(repo, "add", "a.txt")
        _git(repo, "commit", "-qm", "init")
        with open(os.path.join(repo, ".gitignore"), "w") as fh:
            fh.write("node_modules/\ndist/\n")
        _git(repo, "add", ".gitignore")
        _git(repo, "commit", "-qm", "ignore")
        _git(repo, "push", "-q", "-u", "origin", "main")
        _git(repo, "remote", "set-head", "origin", "main")

        # clean: pushed, unmerged branch + clean worktree
        _git(repo, "worktree", "add", "-q", "../wt-clean", "-b", "feat-clean")
        wt = os.path.join(sbx, "wt-clean")
        with open(os.path.join(wt, "c.txt"), "w") as fh:
            fh.write("c\n")
        _git(wt, "add", "c.txt")
        _git(wt, "commit", "-qm", "clean work")
        _git(wt, "push", "-q", "-u", "origin", "feat-clean")

        # dirty: pushed, unmerged branch + uncommitted edit
        _git(repo, "worktree", "add", "-q", "../wt-dirty", "-b", "feat-dirty")
        wt = os.path.join(sbx, "wt-dirty")
        with open(os.path.join(wt, "d.txt"), "w") as fh:
            fh.write("d\n")
        _git(wt, "add", "d.txt")
        _git(wt, "commit", "-qm", "dirty work")
        _git(wt, "push", "-q", "-u", "origin", "feat-dirty")
        with open(os.path.join(wt, "d.txt"), "a") as fh:
            fh.write("more\n")

        # unpushed: local commit, never pushed, not merged
        _git(repo, "worktree", "add", "-q", "../wt-unpushed", "-b",
             "feat-unpushed")
        wt = os.path.join(sbx, "wt-unpushed")
        with open(os.path.join(wt, "u.txt"), "w") as fh:
            fh.write("u\n")
        _git(wt, "add", "u.txt")
        _git(wt, "commit", "-qm", "local only")

        # merged: branch merged into main
        _git(repo, "worktree", "add", "-q", "../wt-merged", "-b", "feat-merged")
        wt = os.path.join(sbx, "wt-merged")
        with open(os.path.join(wt, "m.txt"), "w") as fh:
            fh.write("m\n")
        _git(wt, "add", "m.txt")
        _git(wt, "commit", "-qm", "feature m")
        _git(repo, "merge", "-q", "--no-ff", "feat-merged", "-m",
             "merge feat-merged")
        _git(repo, "push", "-q", "origin", "main")

    def _by_branch(self, records):
        return {r["branch"]: r for r in records}

    def test_discovers_four_worktrees(self):
        records = reaper.scan(paths=[self.sbx])
        self.assertEqual(len(records), 4)

    def test_classification(self):
        recs = self._by_branch(reaper.scan(paths=[self.sbx]))
        self.assertEqual(recs["feat-clean"]["status"], "clean")
        self.assertEqual(recs["feat-dirty"]["status"], "dirty")
        self.assertEqual(recs["feat-unpushed"]["status"], "unpushed")
        self.assertEqual(recs["feat-merged"]["status"], "merged")

    def test_merged_boolean(self):
        recs = reaper.scan(paths=[self.sbx])
        merged = [r["branch"] for r in recs if r["merged"]]
        self.assertEqual(merged, ["feat-merged"])

    def test_merged_only_filter(self):
        recs = reaper.scan(paths=[self.sbx], merged_only=True)
        self.assertEqual([r["branch"] for r in recs], ["feat-merged"])

    def test_sorted_oldest_first(self):
        recs = reaper.scan(paths=[self.sbx])
        touched = [r["touched"] for r in recs]
        self.assertEqual(touched, sorted(touched))

    def test_reap_clean_and_merged_skips_risky(self):
        # Reap without force: clean + merged go; dirty + unpushed stay.
        reaped = []
        for rec in reaper.scan(paths=[self.sbx]):
            if reaper.is_risky(rec["status"]):
                continue
            ok, _ = reaper.reap_one(rec["path"], rec["mainWorktree"],
                                    rec["status"])
            if ok:
                reaped.append(rec["branch"])
        self.assertFalse(os.path.isdir(os.path.join(self.sbx, "wt-clean")))
        self.assertFalse(os.path.isdir(os.path.join(self.sbx, "wt-merged")))
        self.assertTrue(os.path.isdir(os.path.join(self.sbx, "wt-dirty")))
        self.assertTrue(os.path.isdir(os.path.join(self.sbx, "wt-unpushed")))

    def test_reap_force_removes_risky(self):
        for rec in reaper.scan(paths=[self.sbx]):
            if rec["status"] == "orphan":
                continue
            reaper.reap_one(rec["path"], rec["mainWorktree"], rec["status"])
        self.assertFalse(os.path.isdir(os.path.join(self.sbx, "wt-dirty")))
        self.assertFalse(os.path.isdir(os.path.join(self.sbx, "wt-unpushed")))


@unittest.skipUnless(_have_git(), "git not available")
class AgeSignalTests(unittest.TestCase):

    def test_age_ignores_gitignored_churn(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(lambda: __import__("shutil").rmtree(tmp,
                                                            ignore_errors=True))
        sbx = os.path.join(tmp, "age")
        os.makedirs(sbx)
        old = "2020-01-01T00:00:00"
        env = {"GIT_AUTHOR_DATE": old, "GIT_COMMITTER_DATE": old}
        _git(sbx, "init", "--bare", "remote.git")
        _git(sbx, "init", "repo")
        repo = os.path.join(sbx, "repo")
        _git(repo, "remote", "add", "origin", os.path.join(sbx, "remote.git"))
        with open(os.path.join(repo, "a.txt"), "w") as fh:
            fh.write("hi\n")
        _git(repo, "add", "a.txt", env=env)
        _git(repo, "commit", "-qm", "init", env=env)
        with open(os.path.join(repo, ".gitignore"), "w") as fh:
            fh.write("node_modules/\n")
        _git(repo, "add", ".gitignore", env=env)
        _git(repo, "commit", "-qm", "ignore", env=env)
        _git(repo, "push", "-q", "-u", "origin", "main", env=env)
        _git(repo, "remote", "set-head", "origin", "main")
        _git(repo, "worktree", "add", "-q", "../wt-old", "-b", "feat-old",
             env=env)
        wt = os.path.join(sbx, "wt-old")
        # Backdate tracked files (checkout stamps them "now").
        old_ts = time.mktime(time.strptime("2020-01-01", "%Y-%m-%d"))
        out = subprocess.run(["git", "-C", wt, "ls-files"],
                             stdout=subprocess.PIPE, check=True)
        for rel in out.stdout.decode().split():
            os.utime(os.path.join(wt, rel), (old_ts, old_ts))
        # Fresh gitignored churn -- must be ignored by the age signal.
        os.makedirs(os.path.join(wt, "node_modules"))
        with open(os.path.join(wt, "node_modules", "x"), "w") as fh:
            fh.write("junk\n")

        recs = reaper.scan(paths=[sbx])
        self.assertTrue(recs)
        self.assertGreater(recs[0]["ageDays"], 365)


@unittest.skipUnless(_have_git(), "git not available")
class LockFileTests(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(lambda: __import__("shutil").rmtree(
            self.tmp, ignore_errors=True))
        self.sbx = os.path.join(self.tmp, "lock")
        os.makedirs(self.sbx)
        sbx = self.sbx
        _git(sbx, "init", "--bare", "remote.git")
        _git(sbx, "init", "repo")
        repo = os.path.join(sbx, "repo")
        _git(repo, "remote", "add", "origin", os.path.join(sbx, "remote.git"))
        with open(os.path.join(repo, "a.txt"), "w") as fh:
            fh.write("hi\n")
        _git(repo, "add", "a.txt")
        _git(repo, "commit", "-qm", "init")
        with open(os.path.join(repo, "package-lock.json"), "w") as fh:
            fh.write("{}\n")
        _git(repo, "add", "package-lock.json")
        _git(repo, "commit", "-qm", "lock")
        _git(repo, "push", "-q", "-u", "origin", "main")
        _git(repo, "remote", "set-head", "origin", "main")

        # merged branch, then lock-only churn in the worktree
        _git(repo, "worktree", "add", "-q", "../wt-lock", "-b", "feat-lock")
        wt = os.path.join(sbx, "wt-lock")
        with open(os.path.join(wt, "m.txt"), "w") as fh:
            fh.write("m\n")
        _git(wt, "add", "m.txt")
        _git(wt, "commit", "-qm", "feature")
        _git(repo, "merge", "-q", "--no-ff", "feat-lock", "-m", "merge feat-lock")
        _git(repo, "push", "-q", "origin", "main")
        with open(os.path.join(wt, "package-lock.json"), "w") as fh:
            fh.write('{"changed":1}\n')

        # merged branch, lock churn + a real edit
        _git(repo, "worktree", "add", "-q", "../wt-lock-real", "-b",
             "feat-lock-real")
        wt = os.path.join(sbx, "wt-lock-real")
        with open(os.path.join(wt, "n.txt"), "w") as fh:
            fh.write("n\n")
        _git(wt, "add", "n.txt")
        _git(wt, "commit", "-qm", "feature2")
        _git(repo, "merge", "-q", "--no-ff", "feat-lock-real", "-m",
             "merge feat-lock-real")
        _git(repo, "push", "-q", "origin", "main")
        with open(os.path.join(wt, "package-lock.json"), "w") as fh:
            fh.write('{"changed":1}\n')
        with open(os.path.join(wt, "a.txt"), "a") as fh:
            fh.write("real\n")

    def _status(self, branch, ignore_locks=True):
        recs = {r["branch"]: r for r in
                reaper.scan(paths=[self.sbx], ignore_locks=ignore_locks)}
        return recs[branch]["status"]

    def test_lock_only_not_dirty_by_default(self):
        self.assertEqual(self._status("feat-lock"), "merged")

    def test_no_ignore_locks_marks_dirty(self):
        self.assertEqual(self._status("feat-lock", ignore_locks=False),
                         "dirty merged")

    def test_lock_plus_real_stays_dirty(self):
        self.assertEqual(self._status("feat-lock-real"), "dirty merged")


if __name__ == "__main__":
    unittest.main()
