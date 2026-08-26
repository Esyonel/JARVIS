"""Coverage for core/telegram_bridge.py's configuration check and chat-id
whitelist — the two things that matter before any real Telegram connection
is involved."""

import asyncio

import core.telegram_bridge as tb


def test_is_configured_false_when_keys_missing(monkeypatch):
    monkeypatch.setattr(tb, "load_api_keys", lambda: {})
    assert tb.TelegramBridge.is_configured() is False


def test_is_configured_false_when_only_token_present(monkeypatch):
    monkeypatch.setattr(tb, "load_api_keys", lambda: {"telegram_bot_token": "x"})
    assert tb.TelegramBridge.is_configured() is False


def test_is_configured_true_when_both_present(monkeypatch):
    monkeypatch.setattr(
        tb,
        "load_api_keys",
        lambda: {"telegram_bot_token": "x", "telegram_chat_id": "123"},
    )
    assert tb.TelegramBridge.is_configured() is True


class _FakeMessage:
    def __init__(self, text=None, voice=None):
        self.text = text
        self.voice = voice


class _FakeVoice:
    def __init__(self, file_id="voice-file-id"):
        self.file_id = file_id


class _FakeChat:
    def __init__(self, chat_id):
        self.id = chat_id


class _FakeUpdate:
    def __init__(self, chat_id, text=None, voice=None):
        self.message = _FakeMessage(text=text, voice=voice)
        self.effective_chat = _FakeChat(chat_id)


class _FakeTgFile:
    def __init__(self, data: bytes):
        self._data = data

    async def download_as_bytearray(self):
        return bytearray(self._data)


class _FakeBot:
    def __init__(self, data: bytes):
        self._data = data

    async def get_file(self, file_id):
        return _FakeTgFile(self._data)


class _FakeContext:
    def __init__(self, data: bytes = b"fake-ogg-bytes"):
        self.bot = _FakeBot(data)


def test_message_from_authorized_chat_is_forwarded():
    received = []

    async def on_message(text):
        received.append(text)

    bridge = tb.TelegramBridge(on_message=on_message, logger=lambda m: None)
    bridge._chat_id = "555"

    asyncio.run(bridge._handle_message(_FakeUpdate("555", "merhaba"), None))
    assert received == ["merhaba"]


def test_message_from_unauthorized_chat_is_ignored():
    received = []

    async def on_message(text):
        received.append(text)

    logged = []
    bridge = tb.TelegramBridge(on_message=on_message, logger=logged.append)
    bridge._chat_id = "555"

    asyncio.run(bridge._handle_message(_FakeUpdate("999", "sızma denemesi"), None))
    assert received == []
    assert any("SEC" in m or "999" in m for m in logged)


def test_voice_message_from_authorized_chat_is_transcribed_and_forwarded(monkeypatch):
    received = []

    async def on_message(text):
        received.append(text)

    monkeypatch.setattr(
        tb.TelegramBridge,
        "_transcribe",
        staticmethod(lambda audio: "sesli mesaj metni"),
    )

    bridge = tb.TelegramBridge(on_message=on_message, logger=lambda m: None)
    bridge._chat_id = "555"

    update = _FakeUpdate("555", voice=_FakeVoice())
    asyncio.run(bridge._handle_voice(update, _FakeContext()))
    assert received == ["sesli mesaj metni"]


def test_voice_message_from_unauthorized_chat_is_ignored(monkeypatch):
    received = []

    async def on_message(text):
        received.append(text)

    monkeypatch.setattr(
        tb.TelegramBridge, "_transcribe", staticmethod(lambda audio: "should not run")
    )

    bridge = tb.TelegramBridge(on_message=on_message, logger=lambda m: None)
    bridge._chat_id = "555"

    update = _FakeUpdate("999", voice=_FakeVoice())
    asyncio.run(bridge._handle_voice(update, _FakeContext()))
    assert received == []


def test_voice_message_with_empty_transcript_is_not_forwarded(monkeypatch):
    received = []

    async def on_message(text):
        received.append(text)

    monkeypatch.setattr(
        tb.TelegramBridge, "_transcribe", staticmethod(lambda audio: "")
    )

    bridge = tb.TelegramBridge(on_message=on_message, logger=lambda m: None)
    bridge._chat_id = "555"

    update = _FakeUpdate("555", voice=_FakeVoice())
    asyncio.run(bridge._handle_voice(update, _FakeContext()))
    assert received == []
