"""Coverage for the pure decision helpers in main.py: the voice-gate
classifier, the turn-source permission gate, and the watchdog's
stuck-session detector. All were extracted from JarvisLive methods
specifically so they're testable without a live Gemini session or a Qt UI."""

import time

import main


class _FakeRegistry:
    def __init__(self, sensitive_names=()):
        self._sensitive_names = set(sensitive_names)

    def is_sensitive(self, name: str) -> bool:
        return name in self._sensitive_names


# ── _tool_requires_voice_check ──────────────────────────────────────────────


def test_shutdown_and_send_message_always_gated():
    reg = _FakeRegistry()
    assert main._tool_requires_voice_check("shutdown_jarvis", {}, reg) is True
    assert (
        main._tool_requires_voice_check("send_message", {"receiver": "x"}, reg) is True
    )


def test_harmless_tools_not_gated():
    reg = _FakeRegistry()
    assert (
        main._tool_requires_voice_check("weather_report", {"city": "Almaty"}, reg)
        is False
    )
    assert main._tool_requires_voice_check("web_search", {"query": "x"}, reg) is False


def test_file_controller_gated_only_for_delete_and_move():
    reg = _FakeRegistry()
    assert (
        main._tool_requires_voice_check("file_controller", {"action": "delete"}, reg)
        is True
    )
    assert (
        main._tool_requires_voice_check("file_controller", {"action": "move"}, reg)
        is True
    )
    assert (
        main._tool_requires_voice_check("file_controller", {"action": "DELETE"}, reg)
        is True
    )  # case-insensitive
    assert (
        main._tool_requires_voice_check("file_controller", {"action": "list"}, reg)
        is False
    )
    assert (
        main._tool_requires_voice_check("file_controller", {"action": "read"}, reg)
        is False
    )


def test_computer_settings_gated_for_dangerous_keywords_in_action_or_description():
    reg = _FakeRegistry()
    assert (
        main._tool_requires_voice_check(
            "computer_settings", {"action": "shutdown"}, reg
        )
        is True
    )
    assert (
        main._tool_requires_voice_check("computer_settings", {"action": "restart"}, reg)
        is True
    )
    assert (
        main._tool_requires_voice_check(
            "computer_settings", {"description": "bilgisayarı kapat"}, reg
        )
        is True
    )
    assert (
        main._tool_requires_voice_check(
            "computer_settings", {"description": "turn on dark mode"}, reg
        )
        is False
    )
    assert (
        main._tool_requires_voice_check(
            "computer_settings", {"action": "volume_set"}, reg
        )
        is False
    )


# ── _sensitive_action_permitted ──────────────────────────────────────────────


def test_mic_source_follows_voice_result():
    assert main._sensitive_action_permitted("mic", True) is True
    assert main._sensitive_action_permitted("mic", False) is False


def test_local_ui_always_permitted_regardless_of_voice_flag():
    assert main._sensitive_action_permitted("local_ui", False) is True
    assert main._sensitive_action_permitted("local_ui", True) is True


def test_remote_channels_never_permitted_even_if_voice_flag_is_true():
    """A text channel can't carry a voice sample — a caller mistakenly
    passing voice_verified=True for a remote turn must still be refused."""
    assert main._sensitive_action_permitted("remote_dashboard", True) is False
    assert main._sensitive_action_permitted("remote_dashboard", False) is False
    assert main._sensitive_action_permitted("remote_telegram", True) is False
    assert main._sensitive_action_permitted("remote_telegram", False) is False


def test_plugin_opt_in_via_registry():
    reg = _FakeRegistry(sensitive_names={"my_risky_plugin"})
    assert main._tool_requires_voice_check("my_risky_plugin", {}, reg) is True
    assert main._tool_requires_voice_check("my_safe_plugin", {}, reg) is False


# ── _watchdog_should_reconnect ───────────────────────────────────────────────


def test_watchdog_false_when_response_came_after_speech():
    now = 1000.0
    last_speech = now - 30
    last_response = now - 5  # activity AFTER the user's speech
    assert main._watchdog_should_reconnect(last_speech, last_response, now) is False


def test_watchdog_false_within_grace_period():
    now = 1000.0
    last_speech = now - 5  # spoke 5s ago
    last_response = now - 100  # last activity was long before that speech
    assert main._watchdog_should_reconnect(last_speech, last_response, now) is False


def test_watchdog_true_when_stuck_past_threshold():
    now = 1000.0
    last_speech = now - 25  # spoke 25s ago
    last_response = now - 100  # nothing back since well before that
    assert main._watchdog_should_reconnect(last_speech, last_response, now) is True


def test_watchdog_respects_custom_threshold():
    now = 1000.0
    last_speech = now - 10
    last_response = now - 50
    assert (
        main._watchdog_should_reconnect(
            last_speech, last_response, now, stuck_after=5.0
        )
        is True
    )
    assert (
        main._watchdog_should_reconnect(
            last_speech, last_response, now, stuck_after=15.0
        )
        is False
    )
