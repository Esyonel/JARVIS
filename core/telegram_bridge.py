"""
Two-way Telegram bridge for JARVIS: lets the owner text (or send a voice
note to) JARVIS from anywhere in the world and get replies back as Telegram
text messages. Telegram's own servers handle the connection (long-polling),
so unlike the web dashboard this needs no port forwarding, VPN, or the PC
being reachable from outside — it works the moment the PC is on and
connected to the internet, wherever the owner is.

Reuses the same config/api_keys.json keys as plugins/telegram_notify.py
(telegram_bot_token, telegram_chat_id) — one bot handles both outbound
notifications and this two-way chat.

Voice notes are transcribed via a one-shot Gemini call (same technique as
actions/file_processor.py's audio "transcribe" action — inline audio bytes,
no local Whisper/ffmpeg needed) and then handled exactly like a text message.

Security: only messages from the configured telegram_chat_id are accepted;
everything else is silently ignored so a leaked/guessed bot username can't
be used to inject commands. Sensitive tools (shutdown, send_message, file
delete, dangerous computer_settings, sensitive plugins) are still refused
for Telegram-originated turns even from the right chat_id — see main.py's
_pending_turn_source / _sensitive_action_permitted — because a text message
(or a transcript of a voice note) can never carry a voice sample to verify
against the enrolled owner.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Awaitable, Callable, Optional

from memory.config_manager import load_api_keys

_UPLOADS_DIR = Path(__file__).resolve().parent.parent / "uploads"
_SUPPORTED_DOC_EXTS = {".pdf", ".docx", ".txt"}


def _detect_output_format(caption: Optional[str]) -> str:
    """PDF/DOCX/TXT gönderirken caption'da 'word'/'docx' -> Word, 'csv' -> CSV,
    aksi halde varsayılan Excel (en sık istenen format)."""
    c = (caption or "").lower()
    if "word" in c or "docx" in c:
        return "docx"
    if "csv" in c:
        return "csv"
    return "xlsx"


def _get_gemini_api_key() -> str:
    from core.gemini_keys import available_keys

    keys = available_keys()
    if keys:
        return keys[0]
    return load_api_keys().get("gemini_api_key", "")


class TelegramBridge:
    def __init__(
        self,
        on_message: Callable[[str], Awaitable[None]],
        logger: Callable[[str], None] = print,
    ):
        self._on_message = on_message
        self._logger = logger
        self._app = None
        self._chat_id: Optional[str] = None

    @staticmethod
    def is_configured() -> bool:
        keys = load_api_keys()
        return bool(keys.get("telegram_bot_token") and keys.get("telegram_chat_id"))

    async def start(self) -> None:
        from telegram.ext import Application, MessageHandler, filters

        keys = load_api_keys()
        token = keys.get("telegram_bot_token")
        self._chat_id = str(keys.get("telegram_chat_id") or "")
        if not token or not self._chat_id:
            self._logger(
                "SYS: Telegram köprüsü devre dışı — config/api_keys.json'da "
                "telegram_bot_token/telegram_chat_id yok."
            )
            return

        self._app = Application.builder().token(token).build()
        self._app.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message)
        )
        self._app.add_handler(MessageHandler(filters.VOICE, self._handle_voice))
        self._app.add_handler(MessageHandler(filters.Document.ALL, self._handle_document))

        await self._app.initialize()
        await self._app.start()
        await self._app.updater.start_polling(drop_pending_updates=True)
        self._logger("SYS: Telegram köprüsü aktif.")

    def _is_authorized(self, update) -> bool:
        if str(update.effective_chat.id) != self._chat_id:
            self._logger(
                f"SEC: Yetkisiz Telegram sohbetinden mesaj reddedildi (chat_id={update.effective_chat.id})."
            )
            return False
        return True

    async def _handle_message(self, update, context) -> None:
        if not update.message or not update.message.text:
            return
        if not self._is_authorized(update):
            return
        await self._on_message(update.message.text)

    async def _handle_voice(self, update, context) -> None:
        if not update.message or not update.message.voice:
            return
        if not self._is_authorized(update):
            return
        try:
            tg_file = await context.bot.get_file(update.message.voice.file_id)
            audio_bytes = bytes(await tg_file.download_as_bytearray())
            text = await asyncio.to_thread(self._transcribe, audio_bytes)
        except Exception as e:
            self._logger(f"SYS: Telegram sesli mesajı işlenemedi: {e}")
            return
        if not text:
            self._logger("SYS: Telegram sesli mesajından metin çıkarılamadı.")
            return
        self._logger(f"SYS: Telegram sesli mesaj: {text}")
        await self._on_message(text)

    async def _handle_document(self, update, context) -> None:
        """A PDF/DOCX/TXT sent to the bot gets OCR'd (if scanned) and turned
        into an Excel or Word file via plugins.document_extractor, which is
        sent straight back as a Telegram document -- caption 'word'/'docx' or
        'csv' picks the output format, default is xlsx. Handled here directly
        (not routed through the live session's tool-calling loop) since the
        useful reply is a FILE, not spoken/text confirmation."""
        if not update.message or not update.message.document:
            return
        if not self._is_authorized(update):
            return

        doc = update.message.document
        name = doc.file_name or "belge"
        ext = Path(name).suffix.lower()
        if ext not in _SUPPORTED_DOC_EXTS:
            await self.send(f"Sir, '{name}' desteklenmiyor. PDF, DOCX veya TXT gönderin.")
            return

        output_format = _detect_output_format(update.message.caption)
        self._logger(f"SYS: Telegram'dan '{name}' alındı, {output_format.upper()} olarak işleniyor…")
        await self.send(f"'{name}' alındı, {output_format.upper()} olarak işleniyor… Taranmış sayfalar varsa biraz sürebilir.")

        try:
            _UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
            dest = _UPLOADS_DIR / name
            tg_file = await context.bot.get_file(doc.file_id)
            await tg_file.download_to_drive(str(dest))
            message, output_path = await asyncio.to_thread(
                self._extract_document, str(dest), output_format
            )
        except Exception as e:
            self._logger(f"SYS: Telegram belgesi işlenemedi: {e}")
            await self.send(f"Sir, '{name}' işlenirken hata oluştu: {e}")
            return

        if output_path and Path(output_path).is_file():
            with open(output_path, "rb") as f:
                await self._app.bot.send_document(
                    chat_id=self._chat_id, document=f, filename=Path(output_path).name
                )
        else:
            await self.send(message)

    @staticmethod
    def _extract_document(file_path: str, output_format: str):
        from plugins.document_extractor import run_and_get_path
        return run_and_get_path({"file_path": file_path, "output_format": output_format})

    @staticmethod
    def _transcribe(audio_bytes: bytes) -> str:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=_get_gemini_api_key())
        response = client.models.generate_content(
            model="gemini-flash-latest",
            contents=[
                "Transcribe all speech in this audio file accurately, in its original language. "
                "Output ONLY the transcript, nothing else.",
                types.Part.from_bytes(data=audio_bytes, mime_type="audio/ogg"),
            ],
        )
        return (response.text or "").strip()

    async def send(self, text: str) -> None:
        if not self._app or not self._chat_id:
            return
        try:
            await self._app.bot.send_message(chat_id=self._chat_id, text=text)
        except Exception as e:
            self._logger(f"SYS: Telegram mesajı gönderilemedi: {e}")

    async def stop(self) -> None:
        if not self._app:
            return
        try:
            await self._app.updater.stop()
            await self._app.stop()
            await self._app.shutdown()
        except Exception:
            pass
