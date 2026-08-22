"""
JARVIS plugin — WhatsApp grup yedeklemesinin durumunu bildirir ve elle tetikler.

Yedeklemeyi asil yapan is D:\\nu\\whatsapp-exporter\\yedekle.js; Windows Gorev
Zamanlayici her gun calistiriyor (bkz. whatsapp_yedek_kur.bat). Bu eklenti o
isin sonucunu okur ve gerektiginde yeniden baslatir.

Not: bu eklenti mesaj ICERIGI okumaz. "Su grupta ne konusulmus" gibi sorular
icin whatsapp_reader eklentisi kullanilmali.
"""

import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

PLUGIN = {
    "name": "whatsapp_backup",
    "description": (
        "WhatsApp gruplarinin gunluk otomatik yedeklemesini yonetir. "
        "Kullan: 'whatsapp yedegi alindi mi', 'son yedekleme ne zaman', "
        "'gruplari simdi yedekle', 'yedekleme calisiyor mu', "
        "'whatsapp yedekleme durumu'. "
        "Bu arac mesaj ICERIGINI okumaz — 'X grubunda ne konusulmus', "
        "'grupta su kelimeyi ara' gibi isteklerde bu araci DEGIL "
        "whatsapp_reader eklentisini kullan."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "islem": {
                "type": "STRING",
                "description": (
                    "'durum' = son yedeklemenin sonucunu bildir (varsayilan). "
                    "'yedekle' = yedeklemeyi hemen arka planda baslat."
                ),
            },
        },
        "required": [],
    },
}

_EXPORTER_DIR = Path("D:/nu/whatsapp-exporter")
_DURUM_PATH = _EXPORTER_DIR / "yedek-durum.json"
_RUNNER = _EXPORTER_DIR / "whatsapp_yedek_calistir.bat"
_GOREV_ADI = "JARVIS WhatsApp Yedek"

# Gunluk calistigi icin bu sureyi asan bir yedek "bayat" sayilir.
_BAYAT_SAAT = 36


def run(parameters: dict, player=None, session_memory=None) -> str:
    islem = (parameters.get("islem") or "durum").strip().lower()

    try:
        if islem in ("yedekle", "baslat", "calistir", "run", "backup"):
            sonuc = _yedeklemeyi_baslat()
        else:
            sonuc = _durum_bildir()
    except Exception as e:
        sonuc = f"Sir, whatsapp_backup calisamadi: {e}"

    _log(sonuc, player)
    return sonuc


# ------------------------------------------------------------------ durum

def _durum_bildir() -> str:
    if not _DURUM_PATH.exists():
        return (
            "WhatsApp yedeklemesi henuz hic calismamis. "
            f"Gunluk gorevi kurmak icin {_EXPORTER_DIR}\\whatsapp_yedek_kur.bat "
            "dosyasini calistirin."
        )

    try:
        d = json.loads(_DURUM_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        return f"Yedekleme durum dosyasi okunamadi: {e}"

    durum = d.get("durum", "bilinmiyor")
    bitis = _zaman(d.get("bitis") or d.get("baslangic"))
    ne_zaman = _gecen_sure(bitis)

    if durum == "calisiyor":
        return f"Yedekleme su anda calisiyor ({ne_zaman} basladi)."

    if durum == "hata":
        kod = d.get("cikisKodu")
        mesaj = (d.get("mesaj") or "").strip()
        if kod == 2:
            return (
                f"DIKKAT: WhatsApp oturumu dusmus, yedekleme {ne_zaman} durdu. "
                "QR kodun yeniden okutulmasi gerekiyor: whatsapp-exporter klasorunde "
                "'node server.js' calistirip localhost:3001 adresinden telefonla taratin. "
                "Bu yapilmadan gunluk yedek alinamaz."
            )
        if kod == 3:
            return f"Yedekleme {ne_zaman} zaman asimina ugradi. {mesaj}"
        return f"Son yedekleme {ne_zaman} hata verdi: {mesaj or 'sebep belirtilmemis'}"

    # basarili
    grup = d.get("grupSayisi", 0)
    degisen = d.get("degisenGrup", 0)
    mesaj_sayi = d.get("yeniMesaj", 0)
    medya = d.get("yeniMedya", 0)
    hatali = d.get("hataliGrup", 0)
    sure = d.get("sureSaniye", 0)

    satir = (
        f"Son yedekleme {ne_zaman} basariyla tamamlandi: {grup} grup tarandi, "
        f"{degisen} grupta degisiklik, {mesaj_sayi} yeni mesaj, {medya} yeni medya"
    )
    if hatali:
        satir += f", {hatali} grupta hata"
    if sure:
        satir += f" ({sure} saniye)"
    satir += "."

    if _bayat_mi(bitis):
        satir += (
            f" Ancak uzerinden {_BAYAT_SAAT} saatten fazla gecmis — gunluk gorev "
            "calismiyor olabilir, kontrol edin."
        )

    return satir


def _yedeklemeyi_baslat() -> str:
    if not _RUNNER.exists():
        return f"Yedekleme dosyasi bulunamadi: {_RUNNER}"

    # Yedekleme dakikalar surebilir; JARVIS'i bekletmemek icin ayri surecte baslatiliyor.
    try:
        flags = 0
        if hasattr(subprocess, "CREATE_NO_WINDOW"):
            flags |= subprocess.CREATE_NO_WINDOW
        if hasattr(subprocess, "DETACHED_PROCESS"):
            flags |= subprocess.DETACHED_PROCESS

        subprocess.Popen(
            ["cmd", "/c", str(_RUNNER)],
            cwd=str(_EXPORTER_DIR),
            creationflags=flags,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception as e:
        return f"Yedekleme baslatilamadi: {e}"

    return (
        "WhatsApp grup yedeklemesi arka planda baslatildi. "
        "Sadece yeni mesajlar indiriliyor, birkac dakika surebilir. "
        "Bitince 'yedekleme durumu' diye sorabilirsiniz."
    )


# --------------------------------------------------------------- yardimci

def _zaman(deger):
    """
    yedekle.js zaman damgalarini toISOString() ile, yani UTC olarak yaziyor.
    Saat dilimi bilgisi olmayan bir deger gelirse UTC varsayip yerel saate
    ceviriyoruz; yoksa 'az once' biten bir yedek 'X saat once' gorunuyordu.
    """
    if not deger:
        return None
    try:
        an = datetime.fromisoformat(str(deger).replace("Z", "+00:00"))
    except Exception:
        return None
    if an.tzinfo is None:
        an = an.replace(tzinfo=timezone.utc)
    return an.astimezone()


def _gecen_sure(an) -> str:
    if an is None:
        return "bilinmeyen bir zamanda"
    fark = datetime.now(timezone.utc) - an
    if fark < timedelta(minutes=2):
        return "az once"
    if fark < timedelta(hours=1):
        return f"{int(fark.total_seconds() // 60)} dakika once"
    if fark < timedelta(days=1):
        return f"{int(fark.total_seconds() // 3600)} saat once"
    return f"{fark.days} gun once ({an.strftime('%d.%m.%Y %H:%M')})"


def _bayat_mi(an) -> bool:
    if an is None:
        return True
    return datetime.now(timezone.utc) - an > timedelta(hours=_BAYAT_SAAT)


def _log(mesaj: str, player=None) -> None:
    print(f"[WhatsAppBackup] {mesaj[:200]}")
    if player:
        try:
            player.write_log(f"JARVIS: {mesaj}")
        except Exception:
            pass
