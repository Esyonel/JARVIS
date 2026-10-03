"""
Akıllı Aşçı (Chef Jarvis)
Evdeki malzemelere göre yemek tarifleri bulur ve sesli olarak adım adım yönlendirir.
"""

class ChefJarvis:
    def __init__(self):
        pass

    def suggest_recipe(self, ingredients: list) -> str:
        """Verilen malzemelere uygun yemek tarifi önerir."""
        # TODO: Recipe API veya LLM entegrasyonu
        print(f"Şu malzemelerle tarif aranıyor: {ingredients}")
        return "Menemen"

    def read_recipe_step_by_step(self, recipe_name: str, step_index: int) -> str:
        """Tarifin belirli bir adımını sesli okunmak üzere döndürür."""
        # TODO: Tarif veritabanından adım çekme
        steps = ["Soğanları doğrayın.", "Domatesleri ekleyin.", "Yumurtaları kırın."]
        if step_index < len(steps):
            return steps[step_index]
        return "Afiyet olsun!"
