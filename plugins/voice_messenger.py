"""
Sesli Slack/Teams/Mail Yanıtlama (Voice Messenger)
Hareket halindeyken gelen iş mesajlarını okur ve sesle yanıtlar.
"""

class VoiceMessenger:
    def __init__(self):
        pass

    def read_unread_messages(self, platform: str) -> list:
        """Seçilen platformdaki (Slack/Teams) okunmamış mesajları getirir."""
        # TODO: Slack/Teams API Entegrasyonu
        print(f"{platform} platformundan mesajlar çekiliyor...")
        return [{"sender": "Patron", "text": "Rapor nerede?"}]

    def send_voice_reply(self, platform: str, recipient: str, audio_file: str) -> bool:
        """Ses dosyasını metne çevirip veya doğrudan ses olarak yanıt gönderir."""
        # TODO: Speech-to-text ve ardından API ile mesaj gönderme
        print(f"{recipient} kişisine {platform} üzerinden yanıt gönderildi.")
        return True
