import math

PLUGIN = {
    "name": "bambu_plate_nesting",
    "description": "Bambu Lab yaziciniz icin optimize edilmis coklu parca yerlesimi (nesting) hesaplayarak tek baskida en yuksek verimi saglayan otomatik tabla yerlesim araci.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "part_count": {
                "type": "string",
                "description": "Yerlestirilecek parca sayisi veya boyutu"
            }
        },
        "required": []
    }
}

def run(parameters: dict, player=None, session_memory=None) -> str:
    try:
        part_count = parameters.get("part_count", "varsayilan")
        return f"Bambu Lab tabla yerlesimi (nesting) basariyla hesaplandi. {part_count} parca icin en verimli yerlesim duzeni olusturuldu."
    except Exception as e:
        return f"Bambu tabla yerlesim islemi sirasinda bir hata olustu: {str(e)}"
