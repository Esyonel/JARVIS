"""
Anlık Finans ve Harcama İzleyici (Finance Tracker)
Fiş fotoğraflarını okuyup (OCR) harcamaları otomatik olarak Excel'e işler.
"""

class FinanceTracker:
    def __init__(self):
        pass

    def extract_receipt_data(self, image_path: str) -> dict:
        """Fiş fotoğrafından tutar ve kategori çıkarır."""
        # TODO: OCR API entegrasyonu
        print(f"Fiş analiz ediliyor: {image_path}")
        return {"amount": 150.50, "category": "Gıda", "date": "2026-09-03"}

    def add_to_excel(self, data: dict, excel_file: str) -> bool:
        """Harcama bilgisini muhasebe Excel dosyasına yazar."""
        # TODO: pandas veya openpyxl ile Excel entegrasyonu
        print(f"{data['amount']} TL'lik harcama {excel_file} dosyasına işlendi.")
        return True
