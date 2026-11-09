import os
import pandas as pd

PLUGIN = {
    "name": "kazakhstan_construction_cost_optimizer",
    "description": "Reads Excel take-off (metraj) lists and planned material quantities for construction sites in Kazakhstan, optimizes inventory costs, and reports real-time budget variances.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Path to the Excel file containing material quantities and budget data."
            },
            "currency": {
                "type": "string",
                "description": "Currency code for reporting (e.g., KZT, USD). Defaults to KZT."
            }
        },
        "required": [
            "file_path"
        ]
    }
}

def run(parameters: dict, player=None, session_memory=None) -> str:
    try:
        file_path = parameters.get("file_path")
        currency = parameters.get("currency", "KZT")

        if not file_path or not os.path.exists(file_path):
            return "Şantiye metraj Excel dosyası bulunamadı. Lütfen geçerli bir dosya yolu belirtin."

        df = pd.read_excel(file_path)
        
        required_columns = ["Material", "PlannedQty", "ActualQty", "UnitCost"]
        for col in required_columns:
            if col not in df.columns:
                return f"Excel dosyası gerekli sütunu içermiyor: {col}. Dosya yapısını kontrol edin."

        df["PlannedCost"] = df["PlannedQty"] * df[
            "UnitCost"
        ]
        df["ActualCost"] = df["ActualQty"] * df[
            "UnitCost"
        ]
        df["Variance"] = df["ActualCost"] - df["PlannedCost"]

        total_planned = df["PlannedCost"].sum()
        total_actual = df["ActualCost"].sum()
        total_variance = total_actual - total_planned

        over_budget_items = df[df["Variance"] > 0]
        optimization_potential = over_budget_items["Variance"].sum()

        summary = (
            f"Kazakistan şantiye bütçe ve stok analizi tamamlandı. "
            f"Toplam Planlanan Maliyet: {total_planned:,.2f} {currency}, "
            f"Gerçekleşen Maliyet: {total_actual:,.2f} {currency}. "
            f"Toplam Bütçe Sapması: {total_variance:,.2f} {currency}. "
            f"Stok maliyeti optimizasyonu için tespit edilen potansiyel tasarruf: {optimization_potential:,.2f} {currency} düzeyindedir."
        )
        return summary
    except Exception as e:
        return f"Metraj ve bütçe analizi sırasında bir hata oluştu: {str(e)}"
