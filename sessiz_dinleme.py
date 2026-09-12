"""
sessiz_dinleme.py — JARVIS'in ana uygulamasından TAMAMEN BAĞIMSIZ, arka planda
çalışan gizli dinleme modu.

NE YAPAR
    Mikrofonu sürekli dinler (webrtcvad ile konuşma başlangıcı/bitişini
    algılar), her konuşma parçasını YEREL Whisper modeliyle (faster-whisper,
    tamamen bu bilgisayarda, internete/API'ye gitmeden) METNİNİ ÇEVİRMEDEN,
    DUYULDUĞU DİLDE deşifre eder ve aynı JARVIS Telegram botu üzerinden
    sahibine yollar. main.py'deki `telegram_relay_enabled` modundan farkı:
    o mod duyduğunu Türkçe'ye çevirir (bkz. main.py:_relay_to_telegram),
    bu script ise hiçbir çeviri yapmadan orijinal dilde gönderir.

    JARVIS'in ana penceresi/oturumu açık olmasına gerek yoktur — kendi
    mikrofon akışını açar, kendi Telegram gönderimini yapar. Sadece Telegram
    icin config/api_keys.json'daki telegram_bot_token/telegram_chat_id
    kullanılır (bkz. memory/config_manager.py). Deşifre için bulut API/Gemini
    kotası KULLANILMAZ — ilk çalıştırmada Whisper modeli internetten bir kez
    indirilip yerel önbelleğe alınır, sonrası tamamen çevrimdışı çalışır.

GİZLİ / OTOMATİK BAŞLATMA
    Bu script tek başına konsol penceresi açmaz. `.venv\\Scripts\\pythonw.exe`
    ile çalıştırıldığında (python.exe DEĞİL) hiçbir pencere belirmez — bkz.
    sessiz_dinleme_kur.vbs, bunu PC açılışında/oturum açılışında otomatik
    çalışacak şekilde Başlangıç klasörüne kaydeder.

GÜRÜLTÜ FİLTRESİ
    VAD (Voice Activity Detection) çok kısa sesleri (öksürük, tık sesi vb.)
    ve düşük dil-güven skorlu (muhtemelen konuşma olmayan) parçaları eler.

GÜNLÜK / TEK ÖRNEK
    Tüm olaylar sessiz_dinleme.log dosyasına yazılır (konsol yok, hata ayıklama
    için başka yer yok). sessiz_dinleme.lock ile aynı anda iki kopyanın
    çalışması engellenir (ör. birden fazla oturum açılışı tetiklerse).
"""

from __future__ import annotations

import logging
import os
import queue
import re
import sys
import threading
import time
from collections import deque
from pathlib import Path

import numpy as np
import requests
import sounddevice as sd
import webrtcvad

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from config import get_config  # noqa: E402
from core import audio_devices  # noqa: E402
from memory.config_manager import get_audio_device  # noqa: E402

LOCK_FILE = BASE_DIR / "sessiz_dinleme.lock"
LOG_FILE = BASE_DIR / "sessiz_dinleme.log"

WHISPER_MODEL_SIZE = "small"           # hiz/dogruluk dengesi - CPU'da birkac saniyede bir kisa parcayi cozer
MIN_LANGUAGE_CONFIDENCE = 0.5          # bunun altinda muhtemelen konusma degildir, at

SAMPLE_RATE = 16000
FRAME_MS = 30
FRAME_SAMPLES = SAMPLE_RATE * FRAME_MS // 1000        # 480 örnek = 960 bayt
VAD_AGGRESSIVENESS = 2                                # 0-3 - 3 konusma kenarlarini fazla kirpip parcali/anlamsiz kayit uretiyordu
PADDING_FRAMES = 10                                   # konuşma başlamadan önceki ~300ms'lik pay
START_TRIGGER_FRAMES = 6                              # PADDING_FRAMES icinde en az bu kadar sesli kare olmali (yanlis tetiklemeyi azaltir)
SILENCE_END_FRAMES = 40                               # ~1.2sn sessizlik = konuşma bitti (kisa duraklamalarda cumleyi yarida kesmesin)
MIN_SPEECH_FRAMES = 27                                # ~800ms altı: gürültü/tıklama/yarim kelime say, at
MAX_SEGMENT_FRAMES = 25_000 // FRAME_MS               # ~25 saniyede segmenti zorla kapat
COOLDOWN_FRAMES = 15                                  # bir segment bitince ~450ms'lik "yankı" penceresi - yeni tetiklemeyi bekletir
QUEUE_IDLE_TIMEOUT = 5.0                              # bu kadar süre veri gelmezse mikrofon koptu say

logging.basicConfig(
    filename=str(LOG_FILE),
    level=logging.INFO,
    encoding="utf-8",
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("sessiz_dinleme")


# ── tek örnek kilidi ─────────────────────────────────────────────────────────

def _already_running() -> bool:
    if not LOCK_FILE.exists():
        return False
    try:
        pid = int(LOCK_FILE.read_text(encoding="utf-8").strip())
    except Exception:
        return False
    try:
        import psutil
        return psutil.pid_exists(pid)
    except Exception:
        return False


def _write_lock() -> None:
    LOCK_FILE.write_text(str(os.getpid()), encoding="utf-8")


def _release_lock() -> None:
    try:
        if LOCK_FILE.exists() and LOCK_FILE.read_text(encoding="utf-8").strip() == str(os.getpid()):
            LOCK_FILE.unlink()
    except Exception:
        pass


# ── Telegram ─────────────────────────────────────────────────────────────────

def _telegram_creds() -> tuple[str, str]:
    cfg = get_config()
    return str(cfg.get("telegram_bot_token") or ""), str(cfg.get("telegram_chat_id") or "")


def _send_telegram(text: str) -> None:
    token, chat_id = _telegram_creds()
    if not token or not chat_id:
        log.warning("Telegram bilgileri (token/chat_id) config/api_keys.json içinde yok — mesaj gönderilemedi.")
        return
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data={"chat_id": chat_id, "text": text},
            timeout=15,
        )
        if resp.status_code != 200:
            log.warning("Telegram gönderimi başarısız: %s %s", resp.status_code, resp.text[:200])
    except Exception as e:
        log.warning("Telegram gönderimi sırasında hata: %s", e)


# ── deşifre (yerel Whisper, çevirisiz, duyulan dilde) ────────────────────────

_LANG_NAMES = {
    "tr": "Türkçe", "en": "İngilizce", "ar": "Arapça", "fa": "Farsça",
    "ru": "Rusça", "de": "Almanca", "fr": "Fransızca", "es": "İspanyolca",
    "it": "İtalyanca", "az": "Azerice", "ku": "Kürtçe", "ur": "Urduca",
    "hi": "Hintçe", "zh": "Çince", "ja": "Japonca", "ko": "Korece",
    "nl": "Felemenkçe", "pt": "Portekizce", "pl": "Lehçe", "uk": "Ukraynaca",
    "el": "Yunanca", "he": "İbranice", "sv": "İsveççe", "no": "Norveççe",
    "ro": "Rumence", "bg": "Bulgarca", "cs": "Çekçe", "hu": "Macarca",
}


def _lang_name(code: str) -> str:
    return _LANG_NAMES.get(code, code.upper()) if code else "?"


# Whisper'in sessizlik/gurultude uydurdugu (halusinasyon) klasik cumleler -
# YouTube altyazi verisinden ogrenilmis klise ifadeler, gercek konusma degil.
_HALLUCINATION_PHRASES = {
    "thank you", "thank you.", "thank you very much", "thank you so much",
    "thanks for watching", "thanks for watching!", "thank you for watching",
    "please subscribe", "subscribe to my channel", "don't forget to subscribe",
    "see you next time", "see you in the next video", "bye bye", "bye bye.",
    "goodbye", "the end", "okay, bye", "subtitles by", "translated by",
    "amara.org", "www.amara.org",
}


def _looks_like_hallucination(text: str) -> bool:
    norm = text.strip().lower().strip(".!? ")
    if norm in _HALLUCINATION_PHRASES:
        return True
    # ayni kisa ifadenin ust uste 3+ kez tekrari - klasik "donguye girme" halusinasyonu
    parts = [p.strip().lower() for p in re.split(r"[.!?,]", text) if p.strip()]
    if len(parts) >= 3:
        most_common = max(set(parts), key=parts.count)
        if parts.count(most_common) >= 3 and len(most_common) <= 30:
            return True
    return False


_whisper_model = None
_whisper_lock = threading.Lock()


def _load_whisper_model():
    """Whisper modelini bir kez yukler (ilk calistirmada internetten indirir,
    sonrasi ~/.cache/huggingface icinde yerel kalir - tamamen cevrimdisi)."""
    global _whisper_model
    with _whisper_lock:
        if _whisper_model is None:
            from faster_whisper import WhisperModel
            log.info("Whisper modeli (%s) yükleniyor...", WHISPER_MODEL_SIZE)
            _whisper_model = WhisperModel(WHISPER_MODEL_SIZE, device="cpu", compute_type="int8")
            log.info("Whisper modeli hazır.")
    return _whisper_model


def _transcribe(frames: list[np.ndarray]) -> tuple[str, str] | None:
    """Ses karesini yerel Whisper ile desifre eder. Konusma yoksa/dil guveni
    dusukse None doner. Cevirmez - Whisper zaten orijinal dilde yazar."""
    audio = np.concatenate(frames).astype(np.float32) / 32768.0
    model = _whisper_model or _load_whisper_model()

    segments, info = model.transcribe(
        audio,
        beam_size=5,
        condition_on_previous_text=False,
        vad_filter=True,  # Silero VAD ile sessizligi ayrica ele - webrtcvad'den daha guclu, halusinasyonu azaltir
    )

    kept: list[str] = []
    for seg in segments:
        if seg.no_speech_prob > 0.6:      # yuksek "konusma yok" ihtimali
            continue
        if seg.avg_logprob < -1.0:        # dusuk guven - muhtemelen uydurma
            continue
        if seg.compression_ratio > 2.4:   # asiri tekrarli/donguye giren metin
            continue
        t = seg.text.strip()
        if t:
            kept.append(t)

    text = " ".join(kept).strip()
    if not text:
        return None
    if info.language_probability is not None and info.language_probability < MIN_LANGUAGE_CONFIDENCE:
        return None
    if _looks_like_hallucination(text):
        return None
    return _lang_name(info.language), text


def _handle_segment(frames: list[np.ndarray]) -> None:
    try:
        result = _transcribe(frames)
    except Exception as e:
        log.warning("Transkripsiyon hatası: %s", e)
        return

    if not result:
        return

    lang, text = result
    log.info("Duyuldu [%s]: %s", lang, text)
    _send_telegram(f"🎤 [{lang}] {text}")


# ── mikrofon + VAD döngüsü ───────────────────────────────────────────────────

def _capture_loop() -> None:
    vad = webrtcvad.Vad(VAD_AGGRESSIVENESS)
    audio_q: "queue.Queue[bytes]" = queue.Queue()

    def _callback(indata, frames_count, time_info, status):
        if status:
            log.debug("Audio status: %s", status)
        audio_q.put(indata.tobytes())

    device = audio_devices.resolve(get_audio_device("input"), "input")

    with sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="int16",
        blocksize=FRAME_SAMPLES,
        device=device,
        callback=_callback,
    ):
        log.info("Mikrofon açıldı, gizli dinleme modu aktif.")
        ring: deque = deque(maxlen=PADDING_FRAMES)
        voiced: list[np.ndarray] = []
        in_speech = False
        silence_run = 0
        cooldown = 0  # bir segment bittikten sonra kalan "yankı" kare sayisi

        while True:
            try:
                raw = audio_q.get(timeout=QUEUE_IDLE_TIMEOUT)
            except queue.Empty:
                raise RuntimeError("Mikrofon akışından veri gelmiyor — yeniden başlatılacak.")

            if len(raw) != FRAME_SAMPLES * 2:
                continue  # akışın kenarındaki eksik bir kare — atla

            frame_np = np.frombuffer(raw, dtype=np.int16)
            is_speech = vad.is_speech(raw, SAMPLE_RATE)

            if not in_speech:
                if cooldown > 0:
                    cooldown -= 1
                    continue
                ring.append((frame_np, is_speech))
                if is_speech and sum(1 for _, sp in ring if sp) >= START_TRIGGER_FRAMES:
                    in_speech = True
                    voiced = [f for f, _ in ring]
                    silence_run = 0
            else:
                voiced.append(frame_np)
                silence_run = 0 if is_speech else silence_run + 1

                if silence_run >= SILENCE_END_FRAMES or len(voiced) >= MAX_SEGMENT_FRAMES:
                    in_speech = False
                    silence_run = 0
                    cooldown = COOLDOWN_FRAMES
                    segment, voiced = voiced, []
                    ring.clear()
                    if len(segment) >= MIN_SPEECH_FRAMES:
                        threading.Thread(target=_handle_segment, args=(segment,), daemon=True).start()


def main() -> None:
    if _already_running():
        log.info("Zaten çalışıyor (pid kilidi mevcut) — çıkılıyor.")
        return

    cfg = get_config()
    if not cfg.get("telegram_bot_token") or not cfg.get("telegram_chat_id"):
        log.error("config/api_keys.json içinde telegram_bot_token/telegram_chat_id yok — çıkılıyor.")
        return

    _write_lock()
    log.info("Gizli dinleme modu başlatıldı (pid=%s).", os.getpid())
    try:
        _load_whisper_model()  # mikrofon acilmadan once yukle - ilk konusma bekletilmesin
        backoff = 5
        while True:
            try:
                _capture_loop()
            except Exception as e:
                log.error("Dinleme döngüsü çöktü: %s — %s sn sonra yeniden denenecek.", e, backoff)
                time.sleep(backoff)
                backoff = min(backoff * 2, 300)
    finally:
        _release_lock()


if __name__ == "__main__":
    main()
