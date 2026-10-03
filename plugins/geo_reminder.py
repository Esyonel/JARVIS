"""
Konum Bazlı Hatırlatıcılar (Geo-Fencing)
Belirli bir konuma gelindiğinde tetiklenen eylemler ve hatırlatıcılar.
"""

class GeoReminder:
    def __init__(self):
        pass

    def add_location_reminder(self, location_name: str, radius_meters: int, message: str) -> bool:
        """Yeni bir konum bazlı hatırlatıcı ekler."""
        print(f"'{location_name}' için ({radius_meters}m yarıçap) hatırlatıcı kuruldu: {message}")
        return True

    def check_current_location(self, current_lat: float, current_lon: float) -> list:
        """Mevcut konumu kontrol edip tetiklenen hatırlatıcıları döner."""
        # TODO: Harita API entegrasyonu
        return []
