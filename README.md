# KickClip — Kick yayınlarından otomatik dikey klip üretici

Kick yayın linkini ver, uygulama yayını parçalara bölüp **TikTok / Shorts / Reels** formatında (1080x1920) klipler üretsin:

- **Üstte yayıncı kamerası**, **altta ekran / oyun** (önemli içerik)
- **Otomatik altyazı** (Whisper, Türkçe destekli, konuşulan kelime sarı vurgulu, TikTok tarzı)
- **Giriş efekti:** klip bulanık başlar, **zil sesiyle birlikte blur kalkar**
- **En hareketli anları bulma:** ses analiziyle yayıncının bağırdığı/güldüğü, ortamın coştuğu anlar seçilir
  (ya da yayını sırayla eşit parçalara bölme modu)
- Kick **canlı yayın**, **VOD** ve **klip** linkleri + yerel video dosyaları desteklenir
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
Windows'ta `baslat.bat` dosyasına çift tıklaman yeterli.

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
zaman damgası + konuşma metni içeren `klip_01.json` (başlık/açıklama yazarken işine yarar).

## Ayarlar

| Ayar | Açıklama |
|---|---|
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
| `--no-subs`, `--no-intro` | Altyazıyı / giriş efektini kapat |

**Yazı tipi:** varsayılan `Montserrat ExtraBold`. İstediğin `.ttf`/`.otf` dosyasını `assets/fonts/` içine koyup
`--font "Yazı Tipi Adı"` ile seçebilirsin. Bulunamazsa sistemdeki benzer bir font kullanılır.

## Nasıl çalışır?

1. `yt-dlp` ile Kick yayını indirilir (canlıysa ffmpeg ile belirtilen süre kaydedilir).
2. Ses enerjisi 0.5 sn'lik pencerelerle analiz edilir; yerel ortalamaya göre ani yükselişler + konuşma
   yoğunluğu puanlanır, en yüksek puanlı ve birbirinden uzak anlar seçilir.
3. OpenCV yüz tespitiyle webcam bölgesi bulunur.
4. Her klip için `faster-whisper` kelime zamanlı transkript çıkarır, ASS altyazı oluşturulur.
5. ffmpeg tek geçişte: kamera + ekran dikey birleştirme → blur giriş (zil anında kalkar) → altyazı → ses miksajı.

## Sorun giderme

- **Kick linki indirilmiyor (403 / Cloudflare):** `pip install -U "yt-dlp[default,curl-cffi]"` ile yt-dlp'yi güncelle.
- **Kamera yanlış yerde:** web arayüzünde köşe seç ya da `--cam x,y,w,h` ile elle ver.
- **Altyazı yavaş:** `--model base` veya `tiny` kullan; ya da NVIDIA GPU ile çalıştır.

> Sadece içerik üreticisinin izin verdiği yayınlarda / kendi yayınlarında kullan; telif ve platform kurallarına dikkat et.
