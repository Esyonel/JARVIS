"""Gantt Şeması Oluşturucu Eklentisi.
CSV veya Excel dosyasından proje görevlerini okuyarak görsel bir Gantt şeması üretir ve Masaüstüne kaydeder.
"""

import os
import sys
from datetime import datetime

PLUGIN = {
    "name": "generate_gantt_chart",
    "description": "CSV veya Excel dosyasındaki proje görevlerini okuyup şık bir Gantt şeması görseli üretir ve kullanıcının masaüstüne kaydeder.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Görevlerin bulunduğu CSV (.csv) veya Excel (.xlsx, .xls) dosyasının dosya yolu."
            },
            "title": {
                "type": "string",
                "description": "Grafiğin başlığı (örn: Proje Zaman Çizelgesi, opsiyonel)."
            },
            "output_filename": {
                "type": "string",
                "description": "Masaüstüne kaydedilecek PNG dosya adı (varsayılan: gantt_semasi.png)."
            }
        },
        "required": ["file_path"]
    }
}


def _get_desktop_dir() -> str:
    user_home = os.path.expanduser("~")
    candidates = [
        os.path.join(user_home, "Desktop"),
        os.path.join(user_home, "OneDrive", "Desktop"),
        os.path.join(user_home, "OneDrive", "Masaüstü"),
        os.path.join(user_home, "Masaüstü"),
    ]
    for c in candidates:
        if os.path.isdir(c):
            return c
    return user_home


def _find_column(df, candidates):
    lower_cols = {str(col).strip().lower(): col for col in df.columns}
    for cand in candidates:
        if cand in lower_cols:
            return lower_cols[cand]
    return None


def run(parameters: dict, player=None, session_memory=None) -> str:
    raw_file = parameters.get("file_path", "").strip('"\' ')
    if not raw_file:
        return "Lütfen bir CSV veya Excel dosya yolu belirtin."

    # Dosya yolu çözümleme
    target_path = raw_file
    if not os.path.isabs(target_path):
        desktop = _get_desktop_dir()
        candidates = [
            os.path.abspath(target_path),
            os.path.join(desktop, target_path),
            os.path.join(os.path.expanduser("~"), target_path),
            os.path.join(os.path.expanduser("~"), "Downloads", target_path),
            os.path.join(os.path.expanduser("~"), "Documents", target_path),
        ]
        for c in candidates:
            if os.path.isfile(c):
                target_path = c
                break

    if not os.path.isfile(target_path):
        return f"Belirtilen dosya bulunamadı: {raw_file}"

    try:
        import pandas as pd
    except ImportError:
        return "Pandas kütüphanesi yüklü değil. 'pip install pandas openpyxl' komutunu çalıştırabilirsiniz."

    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates
        import matplotlib.cm as cm
    except ImportError:
        return "Matplotlib kütüphanesi yüklü değil. 'pip install matplotlib' komutunu çalıştırabilirsiniz."

    # Dosyayı oku
    try:
        ext = os.path.splitext(target_path)[1].lower()
        if ext == '.csv':
            try:
                df = pd.read_csv(target_path, encoding='utf-8')
            except UnicodeDecodeError:
                df = pd.read_csv(target_path, encoding='latin1')
        elif ext in ('.xlsx', '.xls'):
            df = pd.read_excel(target_path)
        else:
            return f"Desteklenmeyen dosya türü: {ext}. Lütfen CSV veya Excel dosyası sağlayın."
    except Exception as e:
        return f"Dosya okunurken hata oluştu: {str(e)}"

    if df.empty:
        return "Dosya içerisinde herhangi bir veri bulunamadı."

    # Sütunları tanı
    task_col = _find_column(df, ["task", "gorev", "görev", "name", "isim", "is", "iş", "activity", "aktivite", "title"])
    start_col = _find_column(df, ["start", "start_date", "start date", "baslangic", "başlangıç", "baslama", "başlama", "begin"])
    end_col = _find_column(df, ["end", "end_date", "end date", "bitis", "bitiş", "finish", "deadline"])
    duration_col = _find_column(df, ["duration", "sure", "süre", "gun", "gün", "days", "day", "zaman"])

    if not task_col:
        # İlk string sütununu görev olarak varsay
        task_col = df.columns[0]

    if not start_col:
        return "Görev başlangıç tarihini belirten bir sütun (örn: Başlangıç, Start, Start_Date) bulunamadı."

    # Tarih dönüşümleri
    try:
        df['parsed_start'] = pd.to_datetime(df[start_col], errors='coerce')
    except Exception as e:
        return f"Başlangıç tarihleri işlenirken hata oluştu: {str(e)}"

    if end_col:
        try:
            df['parsed_end'] = pd.to_datetime(df[end_col], errors='coerce')
        except Exception as e:
            return f"Bitiş tarihleri işlenirken hata oluştu: {str(e)}"
    elif duration_col:
        try:
            # Gün bazlı süre hesabı
            durations = pd.to_numeric(df[duration_col], errors='coerce').fillna(1)
            df['parsed_end'] = df['parsed_start'] + pd.to_timedelta(durations, unit='D')
        except Exception as e:
            return f"Süre bilgisi tarihe çevrilirken hata oluştu: {str(e)}"
    else:
        return "Bitiş tarihini veya görev süresini belirten bir sütun (End, Bitiş, Duration, Gün) bulunamadı."

    # Hatalı/boş satırları filtrele
    valid_df = df.dropna(subset=['parsed_start', 'parsed_end']).copy()
    if valid_df.empty:
        return "Geçerli başlangıç ve bitiş tarihine sahip hiçbir görev satırı bulunamadı."

    # Bitişin başlangıçtan önce olduğu durumları düzelt (en az 1 gün)
    mask_invalid_duration = valid_df['parsed_end'] <= valid_df['parsed_start']
    valid_df.loc[mask_invalid_duration, 'parsed_end'] = valid_df.loc[mask_invalid_duration, 'parsed_start'] + pd.Timedelta(days=1)

    # Başlangıç tarihine göre sırala (aşağıdan yukarıya görsel için ters çevrilir)
    valid_df = valid_df.sort_values(by='parsed_start', ascending=False).reset_index(drop=True)

    # Grafik çizimi
    try:
        chart_title = parameters.get("title") or f"Gantt Şeması - {os.path.basename(target_path)}"
        output_name = parameters.get("output_filename") or "gantt_semasi.png"
        if not output_name.lower().endswith(('.png', '.jpg', '.jpeg', '.pdf')):
            output_name += ".png"

        desktop_dir = _get_desktop_dir()
        save_path = os.path.join(desktop_dir, output_name)

        num_tasks = len(valid_df)
        fig_height = max(5, num_tasks * 0.45 + 2)
        fig, ax = plt.subplots(figsize=(12, fig_height), dpi=150)

        tasks = valid_df[task_col].astype(str).tolist()
        starts = [mdates.date2num(d) for d in valid_df['parsed_start']]
        ends = [mdates.date2num(d) for d in valid_df['parsed_end']]
        durations = [e - s for s, e in zip(starts, ends)]

        # Renk paleti
        colors = cm.get_cmap('Spectral')(range(0, 256, max(1, 256 // max(num_tasks, 1))))[:num_tasks]

        bars = ax.barh(range(num_tasks), durations, left=starts, height=0.55, align='center',
                        color=colors, edgecolor='#2c3e50', linewidth=1, alpha=0.85)

        # Gün etiketlerini çubukların üzerine yaz
        for i, bar in enumerate(bars):
            day_count = int(round(durations[i]))
            text_label = f"{day_count} gün"
            text_x = starts[i] + durations[i] / 2
            ax.text(text_x, i, text_label, ha='center', va='center', color='#1a1a1a',
                    fontsize=8, fontweight='bold', alpha=0.9)

        ax.set_yticks(range(num_tasks))
        ax.set_yticklabels(tasks, fontsize=9, fontweight='medium')
        ax.xaxis_date()
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%d.%m.%Y'))
        fig.autofmt_xdate()

        ax.grid(True, axis='x', linestyle='--', alpha=0.6, color='#95a5a6')
        ax.set_axisbelow(True)
        ax.set_title(chart_title, fontsize=13, fontweight='bold', pad=15, color='#2c3e50')
        ax.set_xlabel("Zaman Çizelgesi", fontsize=10, labelpad=10)

        # Şık kenarlıklar
        for spine in ['top', 'right']:
            ax.spines[spine].set_visible(False)
        ax.spines['left'].set_color('#bdc3c7')
        ax.spines['bottom'].set_color('#bdc3c7')

        plt.tight_layout()
        plt.savefig(save_path, bbox_inches='tight')
        plt.close(fig)

        return f"{num_tasks} görev içeren Gantt şeması başarıyla oluşturuldu ve masaüstünüze '{output_name}' olarak kaydedildi."
    except Exception as e:
        return f"Gantt şeması oluşturulurken hata meydana geldi: {str(e)}"
