# KickClip — Kick yayınlarından otomatik dikey klip üretici

Kick yayın linkini ver, uygulama yayını parçalara bölüp **TikTok / Shorts / Reels** formatında (1080x1920) klipler üretsin:

- **Üstte yayıncı kamerası**, **altta ekran / oyun** (önemli içerik)
- **Otomatik altyazı** (Whisper, Türkçe destekli, konuşulan kelime sarı vurgulu, TikTok tarzı)
- **Giriş efekti:** klip bulanık başlar, **zil sesiyle birlikte blur kalkar**
- **Yapay zekâ ile en iyi anları bulma:** ses analiziyle yayıncının güldüğü/bağırdığı/tepki verdiği aday anlar bulunur,
  Whisper + Claude bunları dinleyip gerçekten klip olacakları seçer ve sınırlarını belirler
  (ya da yayını sırayla eşit parçalara bölme modu)
- **İndirme yok:** yayın Kick'in akışından okunur, sadece seçilen klipler çekilir
- Kick **canlı yayın**, **VOD** ve **klip** linkleri + yerel video dosyaları desteklenir
- **Otomatik YouTube Shorts başlığı + açıklama + etiket** (konuşmaya göre; Claude ile ya da API anahtarı olmadan basit modda)
- İstediğin klibi arayüzden **tek tıkla YouTube Shorts'a yükleme** (herkese açık / liste dışı / özel, ileri tarihe zamanlama)
- Web arayüzü + komut satırı

## Kurulum

1. **Python 3.10+** kur.
2. **ffmpeg** kur ve PATH'e ekle
   - Windows: `winget install Gyan.FFmpeg`
   - macOS: `brew install ffmpeg`
   - Linux: `sudo apt install ffmpeg`
3. Bağımlılıklar:
   ```bash
   pip install -r requirements.txt
   ```
   NVIDIA ekran kartın varsa altyazı çok daha hızlı olur (CUDA otomatik kullanılır).

## Kullanım

### Web arayüzü (önerilen)
```bash
python -m kickclip web
```
Tarayıcıda **http://127.0.0.1:7860** aç, linki yapıştır, *Klipleri üret*. Klipler hazırlandıkça sağda izlenebilir/indirilebilir.
Windows'ta `baslat.bat` dosyasına çift tıklaman yeterli. İlk çalıştırmada:
- Python yoksa nasıl kurulacağını söyler (python.org → kurulumda **"Add python.exe to PATH"** işaretli olmalı; 3.12 önerilir),
- paketleri `.venv` klasörüne kurar (**ilk seferde 5-15 dk**, ilerleme ekranda görünür),
- ffmpeg yoksa `winget` ile kurar (sonra baslat.bat'i bir kez daha çalıştır),
- arayüzü başlatıp tarayıcıyı açar. Sonraki açılışlar birkaç saniye sürer.

ZIP olarak indirdiysen önce **"Tümünü ayıkla"** ile klasöre çıkar; ZIP'in içinden çalıştırma.

Claude anahtarını her seferinde yazmamak için `.env.ornek` dosyasının adını `.env` yapıp içine
`ANTHROPIC_API_KEY=sk-ant-...` yaz.

### Komut satırı
```bash
# VOD'dan en iyi 10 anı, 30'ar saniye
python -m kickclip https://kick.com/kanal/videos/XXXX -n 10 -l 30

# Uzun yayında sadece belli bir aralık
python -m kickclip https://kick.com/kanal/videos/XXXX --range 1:00:00-2:30:00

# Canlı yayını 20 dk kaydedip klip çıkar
python -m kickclip https://kick.com/kanal --live-minutes 20

# Yayını sırayla 45 sn'lik parçalara böl
python -m kickclip yayin.mp4 --mode split -l 45 -n 50

# Kamera sağ altta, kendi zil sesinle
python -m kickclip https://kick.com/... --cam bottom-right --bell zil.mp3
```
Tüm seçenekler: `python -m kickclip --help`

Çıktılar `output/<yayın>_<tarih>/` klasörüne gider: `klip_01.mp4`, kapak `klip_01.jpg`, ve
zaman damgası, konuşma metni, başlık/açıklama/etiket ve YouTube linkini içeren `klip_01.json`.

## Başlık üretimi

Her klip için konuşma metninden Shorts başlığı (`... #shorts`), açıklama ve etiketler otomatik üretilir;
arayüzde kartın altında görünür, düzenleyebilir ya da **✨ Yeni başlık** ile yeniden ürettirebilirsin.

- **ANTHROPIC_API_KEY** tanımlıysa başlıklar Claude ile yazılır (dökümdeki gerçek olaya dayanan, merak uyandıran Türkçe başlık):
  ```bash
  # Windows (PowerShell):  $env:ANTHROPIC_API_KEY="sk-ant-..."
  export ANTHROPIC_API_KEY=sk-ant-...
  ```
  Anahtar: https://console.anthropic.com → API Keys. Klip başına maliyeti çok düşüktür.
  Model `KICKCLIP_TITLE_MODEL` ortam değişkeniyle değiştirilebilir.
- Anahtar yoksa dökümdeki en vurucu cümle başlık yapılır.

## YouTube kurulumu (bir kerelik, ~10 dk)

YouTube, uygulamaların video yükleyebilmesi için senin adına bir "Google Cloud projesi" ister. Ücretsizdir.

1. https://console.cloud.google.com adresine YouTube kanalının olduğu Google hesabıyla gir.
   Üstteki proje seçiciden **Yeni proje** → ad: `KickClip` → Oluştur → projeyi seç.
2. Sol menü **API'ler ve Hizmetler → Kitaplık** → "**YouTube Data API v3**" ara → **Etkinleştir**.
3. Sol menü **Google Auth Platform** (eski adı "OAuth izin ekranı") → **Başlayın**:
   - Uygulama adı: `KickClip`, destek e-postası: kendi e-postan → İleri
   - Kitle: **Harici (External)** → İleri → iletişim e-postası → Bitir
4. **Kitle (Audience)** sekmesi → **Test kullanıcıları → Kullanıcı ekle** → kendi Gmail adresini ekle → Kaydet.
5. **İstemciler (Clients)** sekmesi → **İstemci oluştur** → Uygulama türü: **Masaüstü uygulaması** → Oluştur
   → açılan pencerede **JSON'u indir**.
6. İnen dosyanın adını **`client_secret.json`** yap ve KickClip klasörüne (baslat.bat'ın yanına) koy.
7. KickClip arayüzünü yenile → **YouTube'u bağla** → açılan Google sayfasında hesabını seç:
   - "**Google bu uygulamayı doğrulamadı**" uyarısı normal (uygulamayı sen oluşturdun) →
     **Gelişmiş → KickClip'e git (güvenli değil)** → izinleri işaretle → **Devam**.
   - Arayüzde "✅ YouTube bağlı · kanal: ..." görünür. Bitti.

Önemli notlar:
- **7 günde bir yeniden bağlanma:** Proje "Test" modundayken Google izni 7 günde bir sona erer; o zaman
  **YouTube'u bağla**'ya tekrar basman (ya da ilk yüklemede açılan sayfada izin vermen) yeterli. Bunu kaldırmak için
  Google Auth Platform → Kitle → **Uygulamayı yayınla** (kişisel kullanımda doğrulama gerekmez, uyarı ekranı kalır).
- **Videolar özel yüklenebilir:** Google, denetimden geçmemiş projelerden yüklenen videoları **özel** olarak kilitleyebilir.
  Öyle olursa YouTube Studio'dan tek tıkla herkese açık yaparsın. Kalıcı çözüm: YouTube API denetim formu
  (https://support.google.com/youtube/contact/yt_api_form).
- Varsayılan API kotası günde ~**6 yükleme** (yükleme başına 1600 / 10.000 birim).
- `client_secret.json` ve `youtube_token.json` dosyalarını kimseyle paylaşma (GitHub'a gönderilmez).

### Yükleme

- **Arayüz:** klip kartında başlığı kontrol et → görünürlük seç → (istersen tarih/saat seç) → **YouTube'a yükle**.
  Yüklenen klipler linkiyle işaretlenir, yanlışlıkla iki kez yüklenmez.
- **Komut satırı:**
  ```bash
  python -m kickclip upload output/kanal_20261113_154410/klip_03.mp4
  python -m kickclip upload output/kanal_20261113_154410/klip_01.mp4 klip_05.mp4 --privacy unlisted
  python -m kickclip upload output/kanal_20261113_154410/          # klasördeki yüklenmemiş tüm klipler
  python -m kickclip upload klip_02.mp4 --at 2026-11-20T18:00:00+03:00   # zamanlanmış
  ```

## Ayarlar

| Ayar | Açıklama |
|---|---|
| `--no-ai` | Whisper+Claude seçimini kapat, sadece ses analizi |
| `--candidates 20` | AI'ın inceleyeceği aday sayısı |
| `--fixed-length` | Klip süresi sabit kalsın (AI ±%50 esnetmesin) |
| `--download full` | Önce tüm yayını indir (akıştan okuma sorun çıkarırsa) |
| `--cam auto` | Yüz tespitiyle webcam'i otomatik bulur. Bulamazsa tam ekran (bulanık arka planlı) düzene geçer. |
| `--cam top-left` / `top-right` / `bottom-left` / `bottom-right` | Webcam'in köşesi (boyut: `--cam-size`, kaynak genişliğine oran) |
| `--cam x,y,w,h` | Elle kırpma alanı. Piksel (`1500,700,420,380`) ya da oran (`0.78,0.65,0.22,0.35`) |
| `--cam none` | Kamera yok, tüm ekran |
| `--screen crop` | Alt panel: ekranın ortasından kırpar, paneli doldurur (varsayılan) |
| `--screen fit` | Alt panel: ekranın tamamını sığdırır, boşlukları bulanık doldurur |
| `--screen x,y,w,h` | Ekranın belli bir bölgesini (ör. oyun alanı / önemli içerik) al |
| `--cam-ratio 0.4` | Kamera panelinin dikey oranı |
| `--model small` | Whisper modeli. `medium`/`large-v3` daha doğru ama daha yavaş |
| `--lang tr` | Altyazı dili (`auto` = otomatik) |
| `--words 3` | Ekranda aynı anda gösterilen kelime sayısı |
| `--color "#FFE600"` | Vurgulanan kelime rengi |
| `--hold 0.45` / `--fade 0.2` | Başta bulanık kalma ve blur'un kalkma süresi |
| `--bell dosya.mp3` | Kendi zil sesin. Ya da `assets/bell.wav` / `assets/zil.mp3` olarak koy |
| `--streamer ad` | Hashtag'lerde kullanılacak yayıncı adı (varsayılan: linkten) |
| `--no-titles` | Başlık üretme |
| `--no-subs`, `--no-intro` | Altyazıyı / giriş efektini kapat |

**Yazı tipi:** varsayılan `Montserrat ExtraBold`. İstediğin `.ttf`/`.otf` dosyasını `assets/fonts/` içine koyup
`--font "Yazı Tipi Adı"` ile seçebilirsin. Bulunamazsa sistemdeki benzer bir font kullanılır.

## Nasıl çalışır?

**Yayını indirmez.** Kick linkini verdiğinde yayın bilgisayarına indirilmez; Kick'in video akışından (HLS) okunur:

1. **Ses taraması (tüm yayın):** Kick'in en düşük kaliteli akışından sadece ses okunur (6 saatlik yayın için
   birkaç yüz MB; 1080p'nin ~%5'i). Paralel okunur. Her 0.5 saniye için:
   - konuşma bandındaki (300-3400 Hz) ani yükselme → yayıncı bağırıyor/heyecanlanıyor
   - 3-8 Hz ritmik dalgalanma → gülme ("ha-ha-ha"), hızlı heyecanlı konuşma
   - bas ağırlıklı ses (patlama, müzik) ayrıca ayırt edilir, daha düşük puan alır
   - konuşma yoğunluğu
   En yüksek puanlı, birbirinden uzak anlar **aday** olur (klip sayısının ~2.5 katı).
2. **Yapay zekâ seçimi:** Her adayın çevresindeki ~45-60 sn'lik ses çekilir, **Whisper** ile yazıya dökülür.
   **Claude** tüm adayları okuyup gerçekten klip olacakları (kahkaha, şok, sinir, komik söz, epik an) seçer,
   puanlar ve klibin başlangıç/bitişini olayın kurulumu + punchline'ı kapsayacak, cümle ortasında kesmeyecek
   şekilde belirler. Neden seçildiği kartta 🤖 olarak görünür.
   `ANTHROPIC_API_KEY` yoksa: ses puanı + metindeki tepki işaretleri (hahaha, !, "olamaz", "oha"...) ile seçilir.
3. **Sadece seçilen klipler** yüksek kaliteli (1080p) akıştan çekilir; OpenCV ile webcam bulunur.
4. ffmpeg tek geçişte: kamera üstte + ekran altta → blur giriş (zil anında kalkar) → altyazı (Whisper kelimeleri
   2. adımdan tekrar kullanılır) → ses miksajı.
5. Her klibe Shorts başlığı/açıklaması üretilir.

Canlı yayında akış henüz bitmediği için belirtilen süre (`--live-minutes`) kaydedilir, sonra aynı adımlar uygulanır.
`--download full` ile eski yöntem (önce tüm yayını indir) kullanılabilir.

### Ne kadar sürer? (yaklaşık)

| Adım | 6 saatlik yayın |
|---|---|
| Ses taraması | internet hızına bağlı, genelde 3-10 dk (yerel dosyada ~1 dk) |
| Whisper (25 aday × ~50 sn) | NVIDIA GPU: 1-2 dk · CPU (`small`): 8-15 dk · CPU (`base`): 3-5 dk |
| Claude seçimi | 15-60 sn |
| Klip başına render (30 sn, 1080p) | 15-40 sn |

Hızlandırmak için: `--range` ile aralık seç, `--model base`, `--candidates 15`.

## Sorun giderme

- **Kick linki indirilmiyor (403 / Cloudflare):** `pip install -U "yt-dlp[default,curl-cffi]"` ile yt-dlp'yi güncelle.
- **Kamera yanlış yerde:** web arayüzünde köşe seç ya da `--cam x,y,w,h` ile elle ver.
- **Altyazı yavaş:** `--model base` veya `tiny` kullan; ya da NVIDIA GPU ile çalıştır.

> Sadece içerik üreticisinin izin verdiği yayınlarda / kendi yayınlarında kullan; telif ve platform kurallarına dikkat et.
