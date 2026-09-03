"""
Sends a real WhatsApp voice message in JARVIS's own voice.

How the voice gets in
─────────────────────
WhatsApp records voice notes from the microphone, so the audio is fed to the
browser as a fake capture device: Chromium is launched with
--use-file-for-fake-audio-capture pointing at the WAV that core/voice_note.py
just synthesised. WhatsApp's recorder then "hears" JARVIS instead of a mic,
producing a genuine voice-note bubble rather than a file attachment.

Why WhatsApp Web and not the desktop app
────────────────────────────────────────
actions/send_message.py drives the desktop app with pyautogui — it types a name
into a search box and presses Enter, so a slow window or an unexpected search
hit can silently deliver the message to the WRONG contact. Here the open chat's
title is read back from the DOM and compared to the requested recipient BEFORE
anything is recorded; a mismatch aborts instead of sending.

The browser profile is persistent (config/whatsapp_profile), so the QR login is
a one-time step: run action="login" once, scan the code, and later sends reuse
that session.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

WHATSAPP_URL = "https://web.whatsapp.com"

# Language-independent handles — WhatsApp Web localises aria-labels/titles, so
# matching on the UI language would break on this (Turkish) UI. These were read
# off the live logged-in page rather than assumed: the search field is an
# <input role=textbox data-tab=3> (NOT a contenteditable), and the mic icon is
# "mic-outlined" (not the older "ptt").
_SEARCH_BOX = "[role='textbox'][data-tab='3']"
_CHAT_TITLE = "#main header span[title], header span[title]"
_COMPOSER = "footer [contenteditable='true'][data-tab='10'], [contenteditable='true'][data-tab='10']"
_MIC_BUTTON = "[data-icon='mic-outlined'], [data-icon='ptt'], [data-icon='ptt-refreshed']"

# While recording, WhatsApp's controls carry NO data-icon — they are only
# identifiable by (localised) aria-label, so both the Turkish and English
# labels are listed. Verified live: ['İptal', 'Kaydı duraklat', 'Gönder'].
_SEND_RECORDING = (
    "button[aria-label='Gönder'], button[aria-label='Send'], "
    "[data-icon='send'], [data-icon='audio-send']"
)
_CANCEL_RECORDING = (
    "button[aria-label='İptal'], button[aria-label='Cancel'], "
    "[data-icon='audio-cancel'], [data-icon='x']"
)


def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


def _profile_dir() -> Path:
    path = _base_dir() / "config" / "whatsapp_profile"
    path.mkdir(parents=True, exist_ok=True)
    return path


# Headless Chromium reports "HeadlessChrome/<v>" in its User-Agent, and
# WhatsApp Web answers that with "update your browser" instead of the app — so
# background sending needs the plain Chrome UA. Only the major version is
# checked (WhatsApp requires >= 100), so this string does not need to track the
# bundled Chromium exactly.
_HEADLESS_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36"
)


def _launch(playwright, audio_wav: Path | None, headless: bool):
    """Persistent context so the QR login survives between runs."""
    args = ["--use-fake-ui-for-media-stream"]
    if audio_wav is not None:
        args += [
            "--use-fake-device-for-media-stream",
            f"--use-file-for-fake-audio-capture={audio_wav}",
        ]
    context = playwright.chromium.launch_persistent_context(
        user_data_dir=str(_profile_dir()),
        headless=headless,
        args=args,
        viewport={"width": 1280, "height": 860},
        user_agent=_HEADLESS_UA if headless else None,
    )
    try:
        context.grant_permissions(["microphone"], origin=WHATSAPP_URL)
    except Exception:
        pass  # --use-fake-ui-for-media-stream already auto-accepts the prompt
    return context


def _is_logged_in(page) -> bool:
    """The search box only exists once the chat list has loaded."""
    try:
        page.wait_for_selector(_SEARCH_BOX, timeout=15_000)
        return True
    except Exception:
        return False


def _login(player=None) -> str:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        context = _launch(p, audio_wav=None, headless=False)
        page = context.pages[0] if context.pages else context.new_page()
        page.goto(WHATSAPP_URL, timeout=60_000)
        if player:
            player.write_log("SYS: WhatsApp Web açıldı — QR kodunu telefonunuzdan okutun.")

        # Generous window: the user has to pick up their phone and scan.
        deadline = time.time() + 180
        while time.time() < deadline:
            if _is_logged_in(page):
                context.close()
                return "WhatsApp Web login saved. Voice messages can be sent now."
            time.sleep(2)

        context.close()
        return "Login timed out — the QR code was not scanned. Try again."


def _open_chat(page, receiver: str) -> tuple[bool, str]:
    """Opens the requested chat and returns (verified, title_actually_opened).

    The recipient is verified at SELECTION time: instead of pressing Enter and
    trusting whatever WhatsApp ranked first, the search result whose contact
    name matches `receiver` is located and clicked. If no result carries that
    name the caller aborts — nothing is ever recorded into an unverified chat.
    (Verifying afterwards by chat title does not work in general: opening the
    self-chat shows the title "Kendinize mesaj gönderin", not the contact name.)
    """
    page.wait_for_selector(_SEARCH_BOX, timeout=30_000)
    box = page.locator(_SEARCH_BOX).first
    box.click()
    page.keyboard.press("Control+A")
    page.keyboard.press("Delete")
    box.type(receiver, delay=40)
    page.wait_for_timeout(2500)

    wanted = receiver.casefold().strip()
    rows = page.locator("[role='listitem'], [role='row']")
    for i in range(min(rows.count(), 30)):
        row = rows.nth(i)
        try:
            name = row.locator("span[title]").first.get_attribute("title", timeout=2_000)
        except Exception:
            continue
        if not name:
            continue
        candidate = name.casefold().strip()
        if candidate == wanted or wanted in candidate:
            row.click()
            page.wait_for_timeout(2500)
            try:
                title = page.locator(_CHAT_TITLE).first.get_attribute("title", timeout=10_000)
            except Exception:
                title = name
            return True, (title or name).strip()

    return False, ""


# Each message carries a unique data-id. Counting rows does NOT work: WhatsApp
# virtualises the list, so appending a message at the bottom drops one off the
# top and the count never changes — which made an earlier version report
# "nothing was sent" for messages that had in fact been delivered.
_LAST_ROW_STATE = """
() => {
  const rows = [...document.querySelectorAll('#main div[data-id]')];
  const r = rows[rows.length - 1];
  if (!r) return null;
  return {
    id: r.getAttribute('data-id'),
    text: (r.innerText || '').split('\\n').join(' | '),
    icons: [...r.querySelectorAll('[data-icon]')].map(e => e.getAttribute('data-icon')),
    aria: [...r.querySelectorAll('[aria-label]')].map(e => e.getAttribute('aria-label'))
  };
}
"""

# Status wording is localised, so both Turkish and English markers are matched.
_FAILED_MARKERS = ("bir sorun", "went wrong", "başarısız", "failed")
_DELIVERED_MARKERS = ("okundu", "teslim edildi", "gönderildi", "read", "delivered", "sent")
_DELIVERED_ICONS = ("msg-check", "msg-dblcheck")


def _last_message_id(page) -> str | None:
    state = page.evaluate(_LAST_ROW_STATE)
    return state["id"] if state else None


def _wait_until_delivered(page, baseline_id: str | None, timeout_s: float = 45.0) -> str:
    """Blocks until WhatsApp shows OUR message as actually sent.

    `baseline_id` is the last message's data-id from before sending. Requiring a
    DIFFERENT id is what makes the check meaningful — polling the last bubble
    without a baseline reports success instantly off an older message that is
    already marked "Okundu".

    Waiting matters because closing the browser right after clicking send
    truncates the upload: the bubble renders locally before the media has left
    the machine. Returns "" on success, else a description of what went wrong.
    """
    deadline = time.time() + timeout_s
    last_seen = None
    saw_new_message = False

    while time.time() < deadline:
        state = page.evaluate(_LAST_ROW_STATE)
        if state and state["id"] != baseline_id:
            saw_new_message = True
            last_seen = state
            haystack = " ".join(state["aria"]).casefold() + " " + state["text"].casefold()

            if any(m in haystack for m in _FAILED_MARKERS) or "message-fail" in state["icons"]:
                return "WhatsApp reported the message failed to send."

            if (any(m in haystack for m in _DELIVERED_MARKERS)
                    or any(i in state["icons"] for i in _DELIVERED_ICONS)):
                return ""

        page.wait_for_timeout(1000)

    if not saw_new_message:
        return ("Nothing was actually sent — no new message appeared in the chat "
                f"within {int(timeout_s)}s.")
    return (f"Sent, but delivery was not confirmed within {int(timeout_s)}s "
            f"(last state: {last_seen['text'] if last_seen else 'unknown'}).")


def _record_and_send(page, duration: float) -> str:
    baseline = _last_message_id(page)
    mic = page.locator(_MIC_BUTTON).first
    mic.wait_for(state="visible", timeout=15_000)
    mic.click()

    # The fake capture device starts playing the WAV from the beginning only
    # once the stream is actually open, so record for the clip's full length
    # plus a margin at both ends — stopping early truncates the note (and a
    # note stopped at ~0 s is what produces an empty, undeliverable bubble).
    page.wait_for_timeout(1500)
    page.wait_for_timeout(int((duration + 2.5) * 1000))

    send = page.locator(_SEND_RECORDING).first
    try:
        send.wait_for(state="visible", timeout=10_000)
    except Exception:
        # Never leave a half-recorded note sitting in the composer.
        try:
            page.locator(_CANCEL_RECORDING).first.click(timeout=5_000)
        except Exception:
            pass
        return "Could not find WhatsApp's send button — recording cancelled, nothing was sent."

    send.click()
    return _wait_until_delivered(page, baseline)


def _type_and_send(page, text: str) -> str:
    baseline = _last_message_id(page)
    box = page.locator(_COMPOSER).first
    box.wait_for(state="visible", timeout=15_000)
    box.click()

    # Clear whatever a previous attempt left behind. Without this, leftover
    # text merges with the new message — one earlier test arrived as
    # "Yazili mesaj testi - arka planda gonderildYazili mesaj testi iki.i.".
    page.keyboard.press("Control+A")
    page.keyboard.press("Delete")

    box.type(text, delay=15)
    page.wait_for_timeout(300)
    page.keyboard.press("Enter")
    return _wait_until_delivered(page, baseline)


def _deliver(receiver: str, *, spoken: str | None = None, typed: str | None = None,
             player=None) -> str:
    """Shared send path for both kinds of message.

    Runs headless so nothing steals the user's screen, verifies the recipient
    before composing anything, and — the part that matters — waits for WhatsApp
    to confirm delivery before closing the browser. Tearing the browser down
    straight after clicking send is what leaves a message half-uploaded.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return "Playwright is not installed. Run: pip install playwright && playwright install chromium"

    wav_path = duration = None
    if spoken is not None:
        try:
            from core.voice_note import synthesize
            wav_path, duration = synthesize(spoken)
        except Exception as e:
            return f"Could not synthesise the voice message: {e}"

    kind = "voice msg" if spoken is not None else "text msg"
    if player:
        player.write_log(f"[{kind}] → {receiver}")

    try:
        with sync_playwright() as p:
            context = _launch(p, audio_wav=wav_path, headless=True)
            try:
                page = context.pages[0] if context.pages else context.new_page()
                page.goto(WHATSAPP_URL, timeout=60_000)

                if not _is_logged_in(page):
                    return ("WhatsApp Web is not logged in. Ask me to log in to WhatsApp Web "
                            "first, then scan the QR code with your phone.")

                verified, title = _open_chat(page, receiver)
                if not verified:
                    return (f"Refused to send: no WhatsApp chat matching '{receiver}' was found "
                            "in the search results. Nothing was sent — "
                            "tell me the exact contact name to use.")

                if spoken is not None:
                    failure = _record_and_send(page, duration)
                    sent_label = "Voice message"
                else:
                    failure = _type_and_send(page, typed)
                    sent_label = "Message"

                if failure:
                    return failure
                return f"{sent_label} sent to {title} (delivery confirmed)."
            finally:
                context.close()
    except Exception as e:
        return f"Could not send the message: {e}"


def send_whatsapp_text(receiver: str, text: str, player=None) -> str:
    """Text sibling of whatsapp_voice — used by actions/send_message.py so
    WhatsApp text gets the same background operation, verified recipient and
    delivery confirmation as voice notes."""
    return _deliver(receiver, typed=text, player=player)


def whatsapp_voice(parameters: dict, player=None, session_memory=None) -> str:
    params = parameters or {}
    action = (params.get("action") or "send").strip().lower()
    receiver = (params.get("receiver") or "").strip()
    message_text = (params.get("message_text") or "").strip()

    if action == "login":
        return _login(player=player)

    if not receiver:
        return "Please specify who the voice message should go to."
    if not message_text:
        return "Please specify what the voice message should say."

    from actions.send_message import looks_like_command_to_jarvis
    if looks_like_command_to_jarvis(message_text):
        return ("Refused: that text is the user's instruction to me, not the message body. "
                "Nothing was recorded or sent. Ask the user what they actually want said, "
                "then call this tool again with only those words.")

    return _deliver(receiver, spoken=message_text, player=player)
