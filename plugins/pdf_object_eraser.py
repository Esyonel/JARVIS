"""
JARVIS plugin -- permanently erases an embedded image, logo, stamp, or wet-signature
graphic from inside a PDF, keeping the result as a real PDF (not a rasterized image).

Two ways to target what gets erased:
  1. By image: page_number + image_index (from action="list") -- deletes exactly
     that embedded raster image. This is the common case: a scanned stamp/logo
     dropped onto an otherwise digital PDF.
  2. By region: a "x0,y0,x1,y1" rectangle in PDF point coordinates -- erases
     everything inside it (text, vector drawings, images), for stamps that are
     drawn as vector paths rather than an embedded image.

Uses PyMuPDF's page.add_redact_annot()/apply_redactions(), the standard technique
for permanently removing content from a specific area of a PDF page without
touching the rest of the page or converting anything to an image.
"""

from pathlib import Path

import pymupdf as fitz

PLUGIN = {
    "name": "pdf_object_eraser",
    "description": (
        "PDF içindeki bir kaşeyi, logoyu, ıslak imza görselini veya herhangi bir "
        "gömülü resmi kalıcı olarak siler; sonucu yeni bir PDF dosyası olarak "
        "kaydeder (PDF'i resme çevirip geri dönüştürmeden). Önce action='list' ile "
        "PDF'teki gömülü resimlerin sayfa numarasını, index'ini ve konumunu (bbox) "
        "öğren; sonra action='remove' ile page_number + image_index vererek tam o "
        "resmi sil. image_index verilmezse belirtilen sayfadaki TÜM gömülü resimler "
        "silinir. Kaşe/logo gömülü resim değil de çizim (vektör grafik) ise, "
        "region parametresiyle ('x0,y0,x1,y1' -- list çıktısındaki bbox'tan "
        "alınabilir) o alandaki her şeyi temizle. Kullanım örnekleri: 'bu PDF'teki "
        "kaşeyi kaldır', 'PDF'in ilk sayfasındaki logoyu sil', 'bu belgedeki resmi "
        "temizle'."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "file_path": {"type": "STRING", "description": "PDF dosyasının yolu."},
            "action": {
                "type": "STRING",
                "enum": ["list", "remove"],
                "description": (
                    "'list': PDF'teki gömülü resimleri sayfa/konum bilgisiyle "
                    "listeler. 'remove': resmi veya alanı siler (varsayılan)."
                ),
            },
            "page_number": {
                "type": "NUMBER",
                "description": (
                    "1 tabanlı sayfa numarası. remove için boş bırakılırsa tüm "
                    "sayfalar taranır; list için boş bırakılırsa tüm sayfalar "
                    "listelenir. region kullanılıyorsa zorunludur."
                ),
            },
            "image_index": {
                "type": "NUMBER",
                "description": (
                    "list çıktısındaki 'index' değeri -- sayfadaki belirli bir "
                    "resmi hedeflemek için. remove'da boş bırakılırsa hedef "
                    "sayfa(lar)daki tüm resimler silinir."
                ),
            },
            "region": {
                "type": "STRING",
                "description": (
                    "'x0,y0,x1,y1' formatında bir dikdörtgen (PDF punto "
                    "koordinatı). Verilirse image_index yerine bu alan içindeki "
                    "her şey (resim, çizim, metin) silinir. page_number zorunludur."
                ),
            },
        },
        "required": ["file_path"],
    },
}


def _fmt_rect(r: "fitz.Rect") -> str:
    return f"{r.x0:.0f},{r.y0:.0f},{r.x1:.0f},{r.y1:.0f}"


def _list_images(doc, only_page: int | None) -> list[str]:
    lines = []
    for pno in range(len(doc)):
        page_num_1 = pno + 1
        if only_page and page_num_1 != only_page:
            continue
        page = doc[pno]
        for idx, img in enumerate(page.get_images(full=True), start=1):
            xref = img[0]
            rects = page.get_image_rects(xref)
            bbox = _fmt_rect(rects[0]) if rects else "bilinmiyor"
            width, height = img[2], img[3]
            lines.append(f"Sayfa {page_num_1}, index {idx}: {width}x{height} px, konum (bbox) {bbox}")
    return lines


def _remove_by_image(doc, page_num_1: int | None, image_index: int | None) -> int:
    total_removed = 0
    pages = [page_num_1 - 1] if page_num_1 else range(len(doc))
    for pno in pages:
        if pno < 0 or pno >= len(doc):
            continue
        page = doc[pno]
        page_removed = 0
        for idx, img in enumerate(page.get_images(full=True), start=1):
            if image_index and idx != image_index:
                continue
            xref = img[0]
            for rect in page.get_image_rects(xref):
                page.add_redact_annot(rect, fill=(1, 1, 1))
                page_removed += 1
        if page_removed:
            page.apply_redactions()
            total_removed += page_removed
    return total_removed


def _remove_by_region(doc, page_num_1: int, region: str) -> int:
    try:
        x0, y0, x1, y1 = (float(v.strip()) for v in region.split(","))
    except Exception:
        raise ValueError("region 'x0,y0,x1,y1' formatında dört sayı olmalı.")
    if page_num_1 < 1 or page_num_1 > len(doc):
        raise ValueError(f"Sayfa {page_num_1} bu PDF'te yok (toplam {len(doc)} sayfa).")
    page = doc[page_num_1 - 1]
    page.add_redact_annot(fitz.Rect(x0, y0, x1, y1), fill=(1, 1, 1))
    page.apply_redactions()
    return 1


def run(parameters: dict, player=None, session_memory=None) -> str:
    try:
        file_path = parameters.get("file_path")
        action = (parameters.get("action") or "remove").lower()
        page_number = parameters.get("page_number")
        image_index = parameters.get("image_index")
        region = parameters.get("region")

        if not file_path:
            return "Dosya yolu eksik. Lütfen bir PDF dosya yolu belirtin."

        path = Path(file_path).expanduser().resolve()
        if not path.is_file():
            return f"Dosya bulunamadı: {file_path}."
        if path.suffix.lower() != ".pdf":
            return "Bu araç sadece PDF dosyalarıyla çalışır."

        page_num_1 = int(page_number) if page_number not in (None, "") else None
        img_idx = int(image_index) if image_index not in (None, "") else None

        def log(m: str) -> None:
            if player:
                try:
                    player.write_log(f"JARVIS: {m}")
                except Exception:
                    pass

        doc = fitz.open(str(path))
        try:
            if action == "list":
                lines = _list_images(doc, page_num_1)
                if not lines:
                    scope = f"sayfa {page_num_1}'de" if page_num_1 else "hiçbir sayfada"
                    return f"'{path.name}' içinde {scope} gömülü resim bulamadım."
                return f"'{path.name}' içindeki resimler:\n" + "\n".join(lines)

            if region:
                if not page_num_1:
                    return "region belirttiğinizde page_number de belirtmelisiniz."
                removed = _remove_by_region(doc, page_num_1, region)
            else:
                removed = _remove_by_image(doc, page_num_1, img_idx)

            if not removed:
                return f"'{path.name}' içinde silinecek bir resim bulamadım."

            output_path = path.with_name(f"{path.stem}_temizlendi.pdf")
            doc.save(str(output_path))
            log(f"{removed} öge silindi, kaydedildi: {output_path}")
            return (
                f"'{path.name}' içinden {removed} öge kalıcı olarak silindi. "
                f"Temizlenmiş PDF şuraya kaydedildi: {output_path}."
            )
        finally:
            doc.close()
    except Exception as exc:
        return f"PDF üzerinden resim/kaşe silme sırasında bir hata oluştu: {exc}"
