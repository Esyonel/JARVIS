"""Regression coverage for core/plugin_loader.py — this is what silently
swallows a broken or duplicate plugin, so it needs its own safety net."""

from pathlib import Path

from core.plugin_loader import discover_plugins

REAL_PLUGINS_DIR = Path(__file__).resolve().parent.parent / "plugins"


def _write_plugin(tmp_path: Path, filename: str, body: str) -> None:
    (tmp_path / filename).write_text(body, encoding="utf-8")


VALID_PLUGIN = """
PLUGIN = {
    "name": "sample_plugin",
    "description": "A sample plugin for testing.",
    "parameters": {"type": "OBJECT", "properties": {}, "required": []},
}

def run(parameters, player=None, session_memory=None):
    return "ok"
"""

SENSITIVE_PLUGIN = """
PLUGIN = {
    "name": "sample_sensitive_plugin",
    "description": "A sample sensitive plugin for testing.",
    "parameters": {"type": "OBJECT", "properties": {}, "required": []},
    "sensitive": True,
}

def run(parameters, player=None, session_memory=None):
    return "ok"
"""


def test_valid_plugin_loads(tmp_path):
    _write_plugin(tmp_path, "sample_plugin.py", VALID_PLUGIN)
    registry = discover_plugins(tmp_path, core_tool_names=set(), logger=lambda m: None)
    assert registry.has("sample_plugin")
    decls = registry.get_tool_declarations()
    assert any(d["name"] == "sample_plugin" for d in decls)


def test_sensitive_flag_defaults_false(tmp_path):
    _write_plugin(tmp_path, "sample_plugin.py", VALID_PLUGIN)
    registry = discover_plugins(tmp_path, core_tool_names=set(), logger=lambda m: None)
    assert registry.is_sensitive("sample_plugin") is False


def test_sensitive_flag_opt_in(tmp_path):
    _write_plugin(tmp_path, "sample_sensitive_plugin.py", SENSITIVE_PLUGIN)
    registry = discover_plugins(tmp_path, core_tool_names=set(), logger=lambda m: None)
    assert registry.is_sensitive("sample_sensitive_plugin") is True


def test_is_sensitive_unknown_tool_is_false(tmp_path):
    registry = discover_plugins(tmp_path, core_tool_names=set(), logger=lambda m: None)
    assert registry.is_sensitive("does_not_exist") is False


def test_missing_plugin_dict_is_rejected(tmp_path):
    _write_plugin(
        tmp_path, "broken.py", "def run(parameters, **kw):\n    return 'ok'\n"
    )
    registry = discover_plugins(tmp_path, core_tool_names=set(), logger=lambda m: None)
    assert not registry.has("broken")
    rejected = [r for r in registry._all_records if not r.valid]
    assert len(rejected) == 1
    assert "PLUGIN dict" in rejected[0].error


def test_name_collision_between_two_files_is_rejected(tmp_path):
    _write_plugin(tmp_path, "a_plugin.py", VALID_PLUGIN)
    _write_plugin(tmp_path, "b_plugin.py", VALID_PLUGIN)  # same PLUGIN["name"]
    registry = discover_plugins(tmp_path, core_tool_names=set(), logger=lambda m: None)
    valid = [r for r in registry._all_records if r.valid]
    invalid = [r for r in registry._all_records if not r.valid]
    assert len(valid) == 1  # first file wins (sorted by filename)
    assert len(invalid) == 1
    assert "already used by" in invalid[0].error


def test_collision_with_core_tool_name_is_rejected(tmp_path):
    _write_plugin(tmp_path, "sample_plugin.py", VALID_PLUGIN)
    registry = discover_plugins(
        tmp_path, core_tool_names={"sample_plugin"}, logger=lambda m: None
    )
    assert not registry.has("sample_plugin")


def test_underscore_prefixed_files_are_skipped(tmp_path):
    _write_plugin(tmp_path, "_helper.py", VALID_PLUGIN)
    registry = discover_plugins(tmp_path, core_tool_names=set(), logger=lambda m: None)
    assert registry._all_records == []


def test_real_plugins_directory_loads_without_errors():
    """Regression guard: every plugin actually shipped in plugins/ must still
    import cleanly and pass schema validation — this is exactly the kind of
    thing that silently rotted into duplicate document_processing* plugins."""
    registry = discover_plugins(
        REAL_PLUGINS_DIR, core_tool_names=set(), logger=lambda m: None
    )
    errors = [(r.file, r.error) for r in registry._all_records if not r.valid]
    assert errors == [], f"{len(errors)} plugin(s) failed to load: {errors}"
