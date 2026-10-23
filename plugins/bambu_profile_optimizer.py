import logging

logger = logging.getLogger(__name__)

PLUGIN = {
    "name": "bambu_profile_optimizer",
    "description": "Bambu Lab 3D yazicilar icin kopruleme acisi, katman yuksekligi ve dolgu yogunlugu gibi kritik parametreleri optimize ederek malzeme ve zaman tasarrufu saglayan akilli profil öneri araci.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "model_type": {
                "type": "string",
                "description": "Basilacak modelin turu (ornegin: mekanik parca, figur, dekoratif, vb.)"
            },
            "material": {
                "type": "string",
                "description": "Kullanilacak filament (PLA, PETG, ABS, vb.)"
            },
            "priority": {
                "type": "string",
                "description": "Oncelik kriteri: hiz, kalite veya mukavemet"
            }
        },
        "required": ["material"]
    }
}

def run(parameters: dict, player=None, session_memory=None) -> str:
    try:
        material = parameters.get("material", "PLA").upper()
        model_type = parameters.get("model_type", "genel").lower()
        priority = parameters.get("priority", "kalite").lower()
        
        # Akilli parametre optimizasyonu
        layer_height = "0.2mm"
        infill_density = "15%"
        bridge_angle = "45 derece"
        
        if "hiz" in priority:
            layer_height = "0.28mm"
            infill_density = "10%"
        elif "mukavemet" in priority or "mekanik" in model_type:
            layer_height = "0.16mm"
            infill_density = "35%"
        else:
            layer_height = "0.2mm"
            infill_density = "20%"
            
        if material == "PETG":
            bridge_angle = "60 derece"
        elif material == "ABS":
            bridge_angle = "45 derece"
            
        return (f"Bambu Lab {material} baskisi icin ozel profiliniz hazir. "
                f"Katman yuksekligi {layer_height}, dolgu yogunlugu %{infill_density} "
                f"ve kopruleme acisi {bridge_angle} olarak optimize edildi. "
                f"Bu ayarlarla hem zamandan hem de malzemeden tasarruf edeceksiniz.")
    except Exception as e:
        logger.error(f"Bambu profile optimizer error: {e}")
        return "Bambu profil optimizasyonu sirasinda bir hata olustu."
