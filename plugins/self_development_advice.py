'''Plugin: self_development_advice
Provides advice on personal development in Turkish.
'''

PLUGIN = {
    "name": "self_development_advice",
    "description": "Kendini geliştirmek için öneriler sunar.",
    "parameters": {
        "type": "OBJECT",
        "properties": {},
        "required": []
    }
}

def run(parameters: dict, player=None, session_memory=None) -> str:
    """
    Returns a short spoken advice string in Turkish about self-improvement.
    """
    try:
        advice = (
            "Kendini geliştirmek için şu adımları izleyebilirsin: "
            "1. Hedeflerini net bir şekilde belirle. "
            "2. Her gün biraz zaman ayırarak yeni bir şey öğren. "
            "3. Kitap okuyarak bilgi birikimini artır. "
            "4. Fiziksel aktivite yaparak beden ve zihnini sağlıklı tut. "
            "5. Geri bildirim alıp sürekli kendini değerlendir."
        )
        return advice
    except Exception as e:
        return f"Üzgünüm, bir hata oluştu: {e}"