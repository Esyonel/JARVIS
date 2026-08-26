"""Coverage for plugins/self_improve.py's file-scoped safety net.

This used to do `git add -A` + a whole-tree checkpoint commit before every
change, and `git reset --hard` to revert — which swept up any unrelated
uncommitted work in the repo and was the root cause of daily_evolution.py
refusing to run for days at a time. These tests pin down the replacement:
snapshot/restore + git operations scoped to exactly the one touched file.
"""

import subprocess

import pytest

import plugins.self_improve as si


def _git(cwd, *args):
    return subprocess.run(
        ["git", *args], cwd=str(cwd), capture_output=True, text=True, check=True
    )


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """A throwaway git repo standing in for the JARVIS checkout, with one
    unrelated file already dirty — simulating in-progress human edits that
    must never be touched by self_improve's own git operations."""
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "test@example.com")
    _git(tmp_path, "config", "user.name", "Test")
    (tmp_path / "plugins").mkdir()
    (tmp_path / "committed.txt").write_text("v1", encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "initial")

    # Unrelated uncommitted work that must survive untouched.
    (tmp_path / "committed.txt").write_text("v2 - work in progress", encoding="utf-8")

    monkeypatch.setattr(si, "BASE_DIR", tmp_path)
    return tmp_path


def _dirty_files(repo_dir) -> set[str]:
    out = _git(repo_dir, "status", "--porcelain").stdout
    return {line[3:] for line in out.splitlines()}


def test_snapshot_new_file_is_none(repo):
    assert si._snapshot_before_edit("plugins/brand_new.py") is None


def test_snapshot_existing_file_returns_content(repo):
    (repo / "plugins" / "existing.py").write_text("PLUGIN = {}\n", encoding="utf-8")
    assert si._snapshot_before_edit("plugins/existing.py") == "PLUGIN = {}\n"


def test_restore_snapshot_removes_new_file(repo):
    target = repo / "plugins" / "brand_new.py"
    target.write_text("junk", encoding="utf-8")
    si._restore_snapshot("plugins/brand_new.py", None)
    assert not target.exists()


def test_restore_snapshot_reverts_edited_file(repo):
    target = repo / "plugins" / "existing.py"
    target.write_text("original", encoding="utf-8")
    original = si._snapshot_before_edit("plugins/existing.py")
    target.write_text("mutated by a bad edit", encoding="utf-8")
    si._restore_snapshot("plugins/existing.py", original)
    assert target.read_text(encoding="utf-8") == "original"


def test_finalize_only_commits_the_touched_file_not_unrelated_wip(repo):
    """The core regression test: an unrelated dirty file in the tree must
    remain uncommitted and untouched after self_improve finalizes its own
    change — this is exactly what `git add -A` used to break."""
    new_file = repo / "plugins" / "new_capability.py"
    new_file.write_text("PLUGIN = {'name': 'x'}\n", encoding="utf-8")

    si._git_finalize("add a test capability", "plugins/new_capability.py")

    log = _git(repo, "log", "--oneline", "-1").stdout
    assert "self-improve:" in log

    # The new plugin file is committed...
    dirty = _dirty_files(repo)
    assert "plugins/new_capability.py" not in dirty
    # ...but the unrelated in-progress file is still dirty, untouched.
    assert any("committed.txt" in f for f in dirty)
    assert (repo / "committed.txt").read_text(
        encoding="utf-8"
    ) == "v2 - work in progress"


def test_validate_plan_rejects_forbidden_paths(repo):
    ok, detail = si._validate_plan(
        {"mode": "new_file", "file": "config/api_keys.json", "content": "{}"}
    )
    assert ok is False


def test_validate_plan_rejects_path_escaping_repo(repo):
    ok, detail = si._validate_plan(
        {"mode": "new_file", "file": "../outside.py", "content": "x"}
    )
    assert ok is False
    assert "escapes" in detail


def test_validate_plan_accepts_new_file(repo):
    ok, detail = si._validate_plan(
        {"mode": "new_file", "file": "plugins/foo.py", "content": "PLUGIN={}"}
    )
    assert ok is True


def test_validate_plan_rejects_edit_of_nonexistent_file(repo):
    ok, detail = si._validate_plan(
        {
            "mode": "edit",
            "file": "plugins/does_not_exist.py",
            "old_string": "a",
            "new_string": "b",
        }
    )
    assert ok is False


def test_apply_plan_new_file_writes_content(repo):
    file_rel = si._apply_plan(
        {"mode": "new_file", "file": "plugins/foo.py", "content": "PLUGIN = {}\n"}
    )
    assert file_rel == "plugins/foo.py"
    assert (repo / "plugins" / "foo.py").read_text(encoding="utf-8") == "PLUGIN = {}\n"


def test_apply_plan_edit_requires_unique_match(repo):
    target = repo / "plugins" / "existing.py"
    target.write_text("x = 1\nx = 1\n", encoding="utf-8")  # "x = 1" appears twice
    with pytest.raises(RuntimeError):
        si._apply_plan(
            {
                "mode": "edit",
                "file": "plugins/existing.py",
                "old_string": "x = 1",
                "new_string": "x = 2",
            }
        )


def test_check_syntax_flags_bad_python(repo):
    target = repo / "plugins" / "broken.py"
    target.write_text("def run(:\n", encoding="utf-8")
    error = si._check_syntax("plugins/broken.py")
    assert error is not None


def test_check_syntax_passes_good_python(repo):
    target = repo / "plugins" / "good.py"
    target.write_text("def run(parameters):\n    return 'ok'\n", encoding="utf-8")
    assert si._check_syntax("plugins/good.py") is None
