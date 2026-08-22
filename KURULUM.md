# JARVIS Kurulum Rehberi

Bu belge, bu klasördeki JARVIS uygulamasını sıfırdan kurmak, yapılandırmak ve tüm ana özellikleri çalıştırmak için hazırlanmıştır. Ana çalışma dosyası `main.py`'dir.

## 1. Gereksinimler

### Zorunlu

- Windows 10/11, macOS veya Linux
- Python 3.11 veya 3.12
- Mikrofon ve hoparlör
- İnternet bağlantısı
- Gemini API anahtarı
- Git (günlük evrim özelliği kullanılacaksa)

### Özelliğe göre gerekenler

- Kamera: ekran/kamera görüntüsü, kalori sayacı ve şınav sayacı
- Steam: oyun güncelleme özelliği
- WhatsApp dışa aktarma aracı: WhatsApp arşivlerini okuma eklentisi
- Ollama veya LM Studio: yerel metin LLM'i kullanılacaksa
- GitHub erişimi: günlük evrim değişikliklerini otomatik göndermek için
- Windows izinleri: ses, kamera, masaüstü kontrolü ve telefon dashboard'u

## 2. Projeyi hazırlama

PowerShell açın ve proje klasörüne geçin:

```powershell
cd D:\nu\JARVIS
```

Yeni bir sanal ortam oluşturun:

```powershell
py -3.11 -m venv .venv
```

Sanal ortamı etkinleştirin:

```powershell
.\.venv\Scripts\Activate.ps1
```

PowerShell betik çalıştırma politikası engellerse yalnızca mevcut kullanıcı için şu komutu çalıştırın:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Pip'i güncelleyin ve bağımlılıkları kurun:

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m playwright install chromium
```

Alternatif olarak `setup.py`, bağımlılıkları ve Playwright tarayıcılarını kurar:

```powershell
python setup.py
```

`setup.py` mevcut sanal ortamı oluşturmaz; bu nedenle önce `.venv` oluşturulmalıdır.

## 3. API kodlarının bulunduğu dosya ve Gemini kurulumu

JARVIS'in API kodları şu dosyada tutulur:

**`config/api_keys.json`**

Bu dosyada kullanılabilecek anahtar alanları:

- `gemini_api_key`: Canlı sesli görüşme ve Gemini işlemleri için zorunlu
- `openrouter_api_key`: Metin işlemleri için isteğe bağlı yedek sağlayıcı
- `groq_api_key`: Metin işlemleri için isteğe bağlı yedek sağlayıcı
- `cerebras_api_key`: Metin işlemleri için isteğe bağlı yedek sağlayıcı
- `elevenlabs_api_key`: ElevenLabs TTS seçilirse gerekli

Dosya yoksa `config` klasörünün içinde `api_keys.json` adıyla oluşturulmalıdır. En güvenli yöntem anahtarı yardımcı komutla eklemektir.

1. Google AI Studio'dan bir anahtar oluşturun: <https://aistudio.google.com/apikey>
2. Anahtarı güvenli şekilde yapılandırmaya ekleyin:

```powershell
.\.venv\Scripts\python.exe add_provider_key.py
```

Menüden `4) Gemini` seçin. Anahtar yazılırken terminalde görünmez.

İsterseniz `config/api_keys.json` dosyasını elle de oluşturabilirsiniz:

```json
{
  "gemini_api_key": "GEMINI_API_KEY_BURAYA",
  "os_system": "windows",
  "assistant_name": "JARVIS",
  "user_name": "",
  "morning_brief_enabled": true,
  "plugins_enabled": {}
}
```

`config/api_keys.json` dosyasını GitHub'a göndermeyin. Bu dosyada gerçek anahtar varsa anahtarı iptal edip yenisini üretin; API anahtarlarını kaynak kodunda, ekran görüntüsünde veya log dosyasında paylaşmayın.

### İsteğe bağlı metin sağlayıcıları

Gemini kotası dolduğunda metin tabanlı işlemler için otomatik yedek sağlayıcı eklenebilir:

```powershell
.\.venv\Scripts\python.exe add_provider_key.py
```

Desteklenen anahtarlar:

- `openrouter_api_key`
- `groq_api_key`
- `cerebras_api_key`
- `gemini_api_key`

Bu yedekler yalnızca metin üretiminde kullanılır. Canlı Gemini ses oturumu için `gemini_api_key` yine gereklidir.

## 4. İlk çalıştırma

Sanal ortam açıkken:

```powershell
python main.py
```

İlk başlatmada aşağıdakiler gerçekleşebilir:

- Eksik Python paketleri otomatik kurulabilir.
- Playwright Chromium tarayıcısı indirilebilir.
- Whisper modeli ilk kullanımda indirilir. Model boyutu seçime göre yaklaşık 75-290 MB'tır.
- Kokoro seçilirse yaklaşık 330 MB'lık ses modeli ilk kullanımda indirilir.
- Windows'ta masaüstü, ses veya kamera izni istenebilir.

Uygulamayı kapatmak için JARVIS arayüzünü normal şekilde kapatın veya terminalde `Ctrl+C` kullanın.

Windows'ta pencere göstermeden başlatmak için:

```powershell
.\start_jarvis.bat
```

## 5. Ses tanıma ve ses üretimi

### Ses kilidi, isteğe bağlı

JARVIS'in yalnızca kayıtlı kullanıcıyı dinlemesini istiyorsanız uygulama kapalıyken çalıştırın:

```powershell
.\.venv\Scripts\python.exe enroll_voice.py
```

Yaklaşık 8 saniye doğal konuşun. Profil `config/voice_id.npy` içine kaydedilir. Test etmek için:

```powershell
.\.venv\Scripts\python.exe test_voice_id.py
```

Ses profilini kaldırmak için `config/voice_id.npy` dosyasını silin. Mikrofonun sessiz kalması veya yanlış eşleşme durumunda kaydı yenileyin.

### STT seçenekleri

Varsayılan motor Whisper'dır ve çevrimdışı çalışır. Alternatif olarak Vosk kullanılabilir. Seçimi `config/api_keys.json` içine ekleyin:

```json
{
  "stt_engine": "whisper"
}
```

Vosk için:

```powershell
python -m pip install vosk
```

Ardından yapılandırmada `"stt_engine": "vosk"` kullanın. Vosk modelinin ayrıca kurulup `core/stt.py` tarafından erişilebilir olması gerekir.

### TTS seçenekleri

Varsayılan motor internet gerektiren ücretsiz Microsoft Edge TTS'tir:

```json
{
  "tts_engine": "edgetts"
}
```

Çevrimdışı Kokoro:

```powershell
python -m pip install "kokoro>=0.9" soundfile
```

```json
{
  "tts_engine": "kokoro"
}
```

Kokoro ilk çalıştırmada modeli indirir. CUDA destekli PyTorch varsa daha hızlı çalışır; CPU ile de kullanılabilir.

ElevenLabs kullanmak için:

```json
{
  "tts_engine": "elevenlabs",
  "elevenlabs_api_key": "ELEVENLABS_API_KEY_BURAYA",
  "elevenlabs_voice_id": "VOICE_ID_BURAYA"
}
```

## 6. Yerel metin LLM'i, isteğe bağlı

JARVIS'in bazı metin işlemlerini yerel modelle yapmasını istiyorsanız iki seçenek vardır.

### Ollama

1. <https://ollama.com> adresinden Ollama'yı kurun.
2. Bir model indirin:

```powershell
ollama pull llama3.2
```

3. Yapılandırmaya ekleyin:

```json
{
  "llm_provider": "ollama",
  "llm_url": "http://localhost:11434",
  "llm_model": "llama3.2"
}
```

JARVIS, Ollama sunucusu çalışmıyorsa `ollama serve` komutunu başlatmayı dener.

### LM Studio veya OpenAI uyumlu sunucu

LM Studio, LocalAI, Jan, llama.cpp server veya vLLM kullanabilirsiniz. Sunucuyu başlatın ve modelin araç/function calling desteklediğinden emin olun:

```json
{
  "llm_provider": "openai",
  "llm_url": "http://localhost:1234",
  "llm_model": "MODEL_ADI"
}
```

## 7. Telefon dashboard'u

1. JARVIS'i başlatın.
2. Arayüzde `REMOTE CONTROL` düğmesine basın.
3. Oluşturulan QR kodu telefonla tarayın veya gösterilen adresi açın.
4. Telefon ve bilgisayar aynı yerel ağda olmalıdır.
5. İlk kullanımda Windows güvenlik duvarı için UAC izni istenebilir; dashboard TCP `47291` portunu kullanır.

Dashboard bağımlılıkları normal `requirements.txt` içinde bulunur. Eksikse:

```powershell
python -m pip install fastapi "uvicorn[standard]" cryptography python-multipart
```

Dashboard'u yalnızca güvenilir yerel ağlarda kullanın. QR anahtarını paylaşmayın ve kullanılmadığında dashboard'u kapatın.

## 8. Tüm özelliklerin kullanım koşulları

### Çekirdek özellikler

- Canlı sesli sohbet: Gemini API anahtarı, mikrofon, hoparlör ve internet
- Türkçe/çok dilli konuşma: Gemini Live ve seçilen STT/TTS motoru
- Kalıcı hafıza: `memory/long_term.json`; bu dosyayı silmek hafızayı sıfırlar
- Sabah brifingi ve proaktif bildirimler: internet ve etkinleştirilmiş ayarlar
- Ekran farkındalığı: ekran yakalama izni
- Kamera farkındalığı: çalışan kamera ve kamera izni
- Masaüstü kontrolü: Windows'ta ek erişilebilirlik/masaüstü izinleri gerekebilir

### Arama, medya ve iletişim

- Web, haber, fiyat ve karşılaştırma araması: internet; Gemini araması veya DuckDuckGo yedeği
- Hava durumu, uçuş ve piyasa verileri: internet; bazı kaynaklar API anahtarı olmadan çalışır
- YouTube ve tarayıcı kontrolü: kurulu ve kullanılabilir bir tarayıcı
- WhatsApp/Telegram mesajı: ilgili platformda açık oturum ve tarayıcı erişimi
- YouTube transkriptleri: internet ve videonun erişilebilir transkripti

### Dosya ve ofis

- Dosya okuma/özetleme: yerel dosya erişimi ve Gemini anahtarı
- Excel okuma/yazma/birleştirme/formül yardımcısı: `openpyxl`; Excel uygulamasının kurulu olması her işlem için zorunlu değildir
- PowerPoint işlemleri: `python-pptx`
- Dosya silme/taşıma: işletim sistemi izinleri; silinen dosyalar mümkün olduğunda Geri Dönüşüm Kutusu'na gönderilir

### Sistem ve donanım

- CPU/RAM/disk/ağ izlemesi: `psutil`
- GPU/sıcaklık: işletim sisteminin ve donanım sürücüsünün sunduğu sensörler; her bilgisayarda tüm değerler bulunmayabilir
- Ses seviyesi ve parlaklık: özellikle Windows'ta `pycaw`, `comtypes` ve üretici sürücüleri
- Kamera işlemleri: `opencv-python`, çalışan kamera; kamera meşgulse diğer uygulamaları kapatın
- Şınav sayacı: kamera, yeterli ışık ve doğru kamera açısı
- Oyun güncelleme: Steam kurulumunun bulunması; Epic desteği kullanılan sisteme göre sınırlı olabilir

### WhatsApp arşivi

`plugins/whatsapp_reader.py`, WhatsApp'a doğrudan bağlanmaz; yerel dışa aktarma dosyalarını okur. Varsayılan klasör:

```text
D:\nu\whatsapp-exporter\exports
```

Kendi WhatsApp dışa aktarma aracınızın ürettiği `messages.json` dosyalarını bu yapıya yerleştirin veya eklentideki yolu kendi klasörünüze göre düzenleyin.

## 9. Eklentiler

JARVIS başlangıçta `plugins/` klasörünü tarar. Yeni bir eklenti eklemek için:

1. `plugins/_template.py` dosyasını kopyalayın.
2. Eklentinin `PLUGIN` tanımını ve `run()` fonksiyonunu doldurun.
3. Dosyayı `plugins/` klasörüne koyun.
4. JARVIS'i yeniden başlatın.

Mevcut eklentiler:

- Kalori sayacı
- Günlük brifing
- Disk kullanımı
- Excel okuma, yazma, birleştirme ve formül yardımcısı
- Git özeti
- Log izleme
- Piyasa verileri
- Ağ taraması
- Proje başlatıcı
- Öz evrim ve öz geliştirme
- Saat/tarih
- Anlık çeviri
- WhatsApp arşiv okuyucu

Arayüzde eklentiler açılıp kapatılabilir. Ayarlar `config/api_keys.json` içindeki `plugins_enabled` alanına kaydedilir.

## 10. Günlük otomatik evrim

Bu özellik yeni eklenti önerir, doğrulama yapar ve başarılı değişikliği GitHub'a gönderebilir. Çalışma klasörünün Git deposu olması ve `origin` uzak deposunun yapılandırılmış olması gerekir.

Önce elle test edin:

```powershell
.\.venv\Scripts\python.exe daily_evolution.py
```

Windows Görev Zamanlayıcı'ya her gün 09:00 kaydetmek için:

```powershell
.\gunluk_evrim_kur.bat
```

Görevi hemen çalıştırmak için:

```powershell
schtasks /run /tn "JARVIS Gunluk Evrim"
```

Görevi kaldırmak için:

```powershell
schtasks /delete /tn "JARVIS Gunluk Evrim" /f
```

Günlük çıktı `evolution.log` dosyasına yazılır. Betik, mevcut kaydedilmemiş Git değişiklikleri varsa çalışmayı atlar; böylece devam eden çalışmalar otomatik commit'e karışmaz.

## 11. Kontrol listesi

- [ ] Python 3.11/3.12 kuruldu
- [ ] `.venv` oluşturuldu ve etkinleştirildi
- [ ] `requirements.txt` kuruldu
- [ ] Playwright Chromium kuruldu
- [ ] Gemini anahtarı `config/api_keys.json` içine eklendi
- [ ] Mikrofon ve hoparlör test edildi
- [ ] `python main.py` ile JARVIS açıldı
- [ ] Kamera özellikleri kullanılacaksa kamera testi yapıldı
- [ ] Ses kilidi isteniyorsa `enroll_voice.py` çalıştırıldı
- [ ] Telefon dashboard'u kullanılacaksa aynı ağ ve güvenlik duvarı kontrol edildi
- [ ] Günlük evrim kullanılacaksa GitHub `origin` bağlantısı ve temiz çalışma ağacı doğrulandı

## 12. Sorun giderme

### `ModuleNotFoundError`

Sanal ortamın açık olduğunu kontrol edin ve kurulumu tekrarlayın:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

### Mikrofon veya kamera bulunamıyor

Windows Ayarlar > Gizlilik ve güvenlik > Mikrofon/Kamera izinlerini açın. Mikrofonu veya kamerayı kullanan diğer uygulamaları kapatıp JARVIS'i yeniden başlatın.

### Playwright tarayıcı hatası

```powershell
python -m playwright install chromium
```

### Ollama bağlantı hatası

```powershell
ollama serve
ollama list
ollama pull llama3.2
```

`llm_url`, çalışan Ollama adresiyle aynı olmalıdır.

### Dashboard telefondan açılmıyor

Telefon ve bilgisayarın aynı Wi-Fi ağında olduğunu kontrol edin. İlk UAC penceresini onaylayın. Windows güvenlik duvarında TCP `47291` portuna izin verilmesi gerekebilir.

### Ses profili eşleşmiyor

Mikrofonun sessiz olmadığını kontrol edin, gürültüyü azaltın ve `enroll_voice.py` ile profili yeniden kaydedin. Karşılaştırma puanını görmek için `test_voice_id.py` çalıştırın.

### Anahtar veya kota hatası

`config/api_keys.json` içindeki Gemini anahtarını kontrol edin. Gerçek anahtar sızdıysa hemen iptal edip yeni bir anahtar oluşturun. Metin işlemleri için `add_provider_key.py` ile isteğe bağlı yedek sağlayıcı eklenebilir.

## 13. Güvenlik ve yedekleme

- `config/api_keys.json`, `config/voice_id.npy`, `memory/long_term.json`, `evolution.log` ve kişisel dışa aktarma dosyalarını paylaşmayın.
- API anahtarlarını Git'e eklemeyin; anahtarların geçmişe girmiş olması durumunda yalnızca dosyayı silmek yeterli değildir, anahtarları sağlayıcı panelinden döndürün.
- `memory/long_term.json` ve `config/` klasörünü düzenli olarak yedekleyin.
- Masaüstü kontrolü ve uzaktan dashboard'u yalnızca güvendiğiniz cihazlar ve ağlarda kullanın.

## 14. Kaldırma

JARVIS'i kaldırmak için önce günlük görevi silin, ardından sanal ortamı ve isteğe bağlı yerel verileri kaldırın:

```powershell
schtasks /delete /tn "JARVIS Gunluk Evrim" /f
Remove-Item -Recurse -Force .venv
```

Kişisel ayarları ve hafızayı da silmek istiyorsanız `config/api_keys.json`, `config/voice_id.npy`, `memory/long_term.json` ve oluşmuş `uploads/` klasörünü ayrıca kaldırın.
