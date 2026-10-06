"""Python cProfile Profiler & Performance Visualization Plugin for JARVIS."""

import os
import sys
import time
import cProfile
import pstats
from pathlib import Path

PLUGIN = {
    "name": "python_profiler",
    "description": "Python kodunu veya betiğini cProfile ile profiller; pandas ve matplotlib kullanarak çalışma süresi ve çağrı frekanslarını detaylı grafik olarak raporlar.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "code": {
                "type": "string",
                "description": "Profillenecek doğrudan Python kod parçacığı (file_path belirtilmediğinde kullanılır)."
            },
            "file_path": {
                "type": "string",
                "description": "Profillenecek yerel .py dosyasının tam veya göreli dosya yolu."
            },
            "sort_by": {
                "type": "string",
                "description": "Sıralama kriteri: 'cumulative' (kümülatif süre), 'tottime' (fonksiyonun kendi süresi) veya 'calls' (çağrı sayısı). Varsayılan: 'cumulative'."
            },
            "top_n": {
                "type": "integer",
                "description": "Grafikte ve raporda listelenecek tepe fonksiyon sayısı. Varsayılan: 10."
            }
        },
        "required": []
    }
}


def _ensure_dependencies():
    try:
        import pandas as pd  # noqa: F401
        import matplotlib  # noqa: F401
        import matplotlib.pyplot as plt  # noqa: F401
    except ImportError:
        import subprocess
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "pandas", "matplotlib"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=90
        )


def run(parameters: dict, player=None, session_memory=None) -> str:
    code_str = parameters.get("code", "").strip()
    file_path = parameters.get("file_path", "").strip()
    sort_by = parameters.get("sort_by", "cumulative").strip().lower()
    top_n = int(parameters.get("top_n", 10))

    if not code_str and not file_path:
        return "Hata: Profillenecek bir kod parçası veya dosya yolu belirtilmedi."

    target_name = "kod_parcasi"
    if file_path:
        path_obj = Path(file_path)
        if not path_obj.is_file():
            return f"Hata: Belirtilen Python dosyası bulunamadı: {file_path}"
        try:
            code_str = path_obj.read_text(encoding="utf-8")
            target_name = path_obj.name
        except Exception as e:
            return f"Dosya okunamadı: {e}"

    try:
        _ensure_dependencies()
        import pandas as pd
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as e:
        return f"Gereksinim kütüphaneleri (pandas, matplotlib) hazırlanamadı: {e}"

    # cProfile ile çalıştırma
    profiler = cProfile.Profile()
    scope = {"__name__": "__main__"}

    start_wall = time.perf_counter()
    try:
        compiled_code = compile(code_str, f"<{target_name}>", "exec")
        profiler.enable()
        exec(compiled_code, scope)
        profiler.disable()
    except Exception as e:
        profiler.disable()
        return f"Kod çalıştırılırken hata oluştu: {e}"
    wall_time = time.perf_counter() - start_wall

    try:
        ps = pstats.Stats(profiler)
        raw_data = []
        for (fpath, lineno, func_name), (cc, nc, tottime, cumtime, _callers) in ps.stats.items():
            fname_label = f"{func_name} ({Path(fpath).name}:{lineno})"
            raw_data.append({
                "function": fname_label,
                "raw_func": func_name,
                "calls": nc,
                "tottime": tottime,
                "cumtime": cumtime,
                "percall": (cumtime / nc) if nc > 0 else 0.0
            })

        if not raw_data:
            return "Profilleme tamamlandı ancak herhangi bir fonksiyon çağrısı kaydedilmedi."

        df = pd.DataFrame(raw_data)

        col_map = {
            "cumulative": "cumtime",
            "tottime": "tottime",
            "calls": "calls"
        }
        sort_col = col_map.get(sort_by, "cumtime")

        top_df = df.sort_values(by=sort_col, ascending=False).head(top_n)
        top_df = top_df.iloc[::-1]  # Bar grafiğinde en büyük üstte olsun

        # Rapor ve grafik çıktı dizini
        output_dir = Path.cwd() / "profile_reports"
        output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        report_image = output_dir / f"profil_{timestamp}.png"

        # Matplotlib Görselleştirme
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
        fig.suptitle(f"JARVIS Profil Analizi: {target_name} ({wall_time:.3f} sn)", fontsize=14, fontweight="bold")

        # Grafik 1: Süreler (Kümülatif ve Kendi Süresi)
        y_indices = range(len(top_df))
        bar_height = 0.4
        ax1.barh([y - bar_height / 2 for y in y_indices], top_df["cumtime"], height=bar_height, label="Kümülatif Süre (sn)", color="#3498db")
        ax1.barh([y + bar_height / 2 for y in y_indices], top_df["tottime"], height=bar_height, label="Kendi Süresi (sn)", color="#e74c3c")
        ax1.set_yticks(list(y_indices))
        ax1.set_yticklabels(top_df["function"], fontsize=8)
        ax1.set_xlabel("Süre (saniye)")
        ax1.set_title("En Çok Zaman Harcayan Fonksiyonlar")
        ax1.grid(axis="x", linestyle="--", alpha=0.6)
        ax1.legend()

        # Grafik 2: Çağrı Sayıları
        ax2.barh(list(y_indices), top_df["calls"], height=0.6, color="#2ecc71")
        ax2.set_yticks(list(y_indices))
        ax2.set_yticklabels(top_df["raw_func"], fontsize=8)
        ax2.set_xlabel("Çağrı Adedi")
        ax2.set_title("Fonksiyon Çağrı Frekansı")
        ax2.grid(axis="x", linestyle="--", alpha=0.6)

        plt.tight_layout()
        plt.savefig(report_image, dpi=200)
        plt.close(fig)

        # Windows ortamında grafiği otomatik aç
        if os.name == "nt":
            try:
                os.startfile(str(report_image))
            except Exception:
                pass

        slowest = df.sort_values(by="cumtime", ascending=False).iloc[0]
        slowest_name = slowest["raw_func"]
        slowest_cum = slowest["cumtime"]

        return (
            f"Profilleme tamamlandı efendim. Toplam çalışma süresi {wall_time:.3f} saniye. "
            f"En kritik darboğaz {slowest_cum:.3f} saniye ile '{slowest_name}' fonksiyonunda tespit edildi. "
            f"Detaylı zaman ve çağrı grafiği açıldı."
        )
    except Exception as e:
        return f"Profilleme analizi ve grafik oluşturma sırasında hata oluştu: {e}"
