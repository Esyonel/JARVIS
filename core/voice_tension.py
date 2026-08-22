"""
Sesten akustik gerilim göstergesi.

DÜRÜSTLÜK NOTU — bu bir duygu ölçer DEĞİLDİR. Sesten "sinirlilik" ya da
duygusal durum ölçtüğünü iddia eden sistemler bilimsel olarak güvenilir
değildir; aynı akustik desen heyecan, öfke, telaş, hatta sadece yüksek sesle
konuşma anlamına gelebilir. Burada ölçülen şey gerçek ve doğrulanabilir olan:

    ses yüksekliği (RMS enerji)   — ne kadar güçlü konuşuluyor
    perde / temel frekans (F0)    — ne kadar tiz konuşuluyor
    perde değişkenliği            — ses ne kadar iniş çıkışlı

Bu üçü birlikte "akustik uyarılma" (arousal) denen şeyi verir: sakin konuşma
alçak, düz ve pes; gergin/heyecanlı konuşma yüksek, tiz ve dalgalıdır. Ekranda
gösterilen yüzde bunun bileşkesidir — "ne kadar gerginsin" değil, "sesin ne
kadar yüksek uyarılmış" sorusunun cevabı.

Kişisel taban çizgisi: herkesin doğal ses tonu farklı olduğu için ölçüm, o
oturumda görülen kendi sessizlik/konuşma aralığına göre normalize edilir.
"""

import numpy as np

SAMPLE_RATE = 16000

# Konuşma sesinin temel frekansı bu aralıkta olur; dışı gürültü kabul edilir.
_F0_MIN_HZ = 70
_F0_MAX_HZ = 350

# Sessizlik eşiği — bunun altındaki blok "konuşma yok" sayılır.
_SILENCE_RMS = 250.0


class TensionMeter:
    """Akustik uyarılmayı 0-100 arası bir sayıya çevirir.

    Durum tutar: kişinin kendi normal perdesini ve ses yüksekliğini oturum
    boyunca öğrenir, ölçümü ona göre normalize eder. Sabit eşikler kullanmak
    pes sesli birini sürekli "sakin", tiz sesli birini sürekli "gergin"
    gösterirdi — ki bu ölçümü anlamsız kılar.
    """

    def __init__(self, history: int = 40):
        self._history = history
        self._rms_seen: list[float] = []
        self._f0_seen: list[float] = []
        self._recent_f0: list[float] = []
        self._value = 0.0

    def update(self, pcm_int16: np.ndarray) -> float | None:
        """Bir ses bloğu işler. Konuşma yoksa None döner (değer değişmez)."""
        samples = pcm_int16.astype(np.float32).flatten()
        if samples.size < 512:
            return None

        rms = float(np.sqrt(np.mean(samples ** 2)))
        if rms < _SILENCE_RMS:
            return None

        f0 = _estimate_f0(samples)

        self._rms_seen.append(rms)
        self._rms_seen = self._rms_seen[-self._history:]
        if f0:
            self._f0_seen.append(f0)
            self._f0_seen = self._f0_seen[-self._history:]
            self._recent_f0.append(f0)
            self._recent_f0 = self._recent_f0[-8:]

        # Kişisel taban çizgisi oluşana kadar ölçüm verme — erken gösterilen
        # sayı, henüz karşılaştıracak bir şey olmadığı için anlamsız olur.
        if len(self._rms_seen) < 5:
            return None

        loud = _percentile_position(rms, self._rms_seen)

        pitch = 0.5
        if f0 and len(self._f0_seen) >= 5:
            pitch = _percentile_position(f0, self._f0_seen)

        variability = 0.0
        if len(self._recent_f0) >= 4:
            mean_f0 = float(np.mean(self._recent_f0))
            if mean_f0 > 0:
                variability = min(1.0, float(np.std(self._recent_f0)) / mean_f0 * 4)

        raw = (0.45 * loud) + (0.35 * pitch) + (0.20 * variability)
        target = max(0.0, min(100.0, raw * 100))

        # Yumuşatma: tek bir yüksek hece göstergeyi zıplatmasın.
        self._value = self._value * 0.7 + target * 0.3
        return round(self._value, 1)

    @property
    def value(self) -> float:
        return round(self._value, 1)

    def label(self) -> str:
        v = self._value
        if v < 30:
            return "sakin"
        if v < 55:
            return "normal"
        if v < 75:
            return "yüksek"
        return "çok yüksek"


def _estimate_f0(samples: np.ndarray) -> float | None:
    """Otokorelasyonla temel frekans tahmini. Konuşma aralığı dışını eler."""
    samples = samples - np.mean(samples)
    if not np.any(samples):
        return None

    corr = np.correlate(samples, samples, mode="full")[len(samples) - 1:]
    if corr[0] <= 0:
        return None

    min_lag = int(SAMPLE_RATE / _F0_MAX_HZ)
    max_lag = int(SAMPLE_RATE / _F0_MIN_HZ)
    if max_lag >= len(corr):
        max_lag = len(corr) - 1
    if min_lag >= max_lag:
        return None

    window = corr[min_lag:max_lag]
    peak = int(np.argmax(window)) + min_lag

    # Zayıf tepe = periyodik konuşma yok (gürültü/nefes) — sayı uydurma.
    if corr[peak] < corr[0] * 0.3:
        return None
    return SAMPLE_RATE / peak


def _percentile_position(value: float, history: list[float]) -> float:
    """value'nun kendi geçmişi içindeki yeri (0=en düşük, 1=en yüksek)."""
    if not history:
        return 0.5
    arr = np.array(history)
    return float(np.mean(arr <= value))
