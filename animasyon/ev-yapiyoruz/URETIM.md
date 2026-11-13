# SIFIRDAN EV YAPIYORUZ! — Üretim Paketi

30 sn · 9:16 · 1080×1920 · 30 FPS · Türkçe TTS + senkron Türkçe altyazı · minimalist geometrik 3D

> **Bu klasörde iki şey var:**
> 1. AI video araçları (Runway, Kling, Veo, Sora, Pika, Hailuo vb.) ile yeniden üretmek için hazır **promptlar ve plan** (bölüm 1–7).
> 2. Bu promptlarla aynı senaryoyu izleyen, **kodla render edilmiş bitmiş bir MP4** (`build/ev-yapiyoruz.mp4`). Görüntü Three.js ile kare kare çizildi; seslendirme ElevenLabs ile üretildi; efektler ve müzik kodla sentezlendi. Ayrıntılar en altta.

Video promptları İngilizce yazıldı, çünkü video modelleri İngilizce promptlarda daha tutarlı sonuç veriyor. Seslendirme ve altyazılar Türkçe.

---

## 1. Karakter — sabit görsel referans promptu

Önce bu promptla **tek bir karakter referans görseli** (karakter sayfası) üret. Sonra her sahne üretiminde bu görseli *image reference / character reference* olarak ver.

```text
Character reference sheet, front view, 3/4 view, side view and back view of the same character,
neutral light-gray background, minimalist geometric 3D toy style, soft studio lighting, clean render.

Character: a small cute stylized person built from simple geometric shapes.
- Head: a rounded-corner cube (soft bevelled box), warm peach skin tone (#F6D5B5).
- Face: two glossy black dot eyes with a tiny white highlight, thin brown eyebrows, small rosy cheek circles,
  simple curved line mouth. Very readable, friendly expression.
- Hat: chunky orange beanie (#F29E4C) shaped like a rounded box, cream pompom on top.
- Scarf: thick orange ring scarf around the neck with one short tail hanging at the front right.
- Body: simple cylinder, pastel light-blue sweater (#9CC7EA) with a small lighter-blue rectangular pocket.
- Arms: short thin cylinders in the same light blue, round peach ball hands, no fingers.
- Legs: short brown-gray cylinders (#8A7563), small dark-brown rounded-box shoes.
- Proportions: head is about 1/3 of total height, chunky and toy-like, total height ~2 heads wide.
Matte plastic / clay material, no texture noise, no outlines, no text.
```

**Kilitlenecek özellikler (her sahnede aynı kalmalı):** turuncu bere + krem ponpon, turuncu atkı, açık mavi silindir gövde, kahverengi bacaklar, yuvarlak köşeli küp kafa, siyah nokta gözler.

**Negatif prompt (destekleyen araçlarda):** `realistic human, fingers, hair, extra limbs, text, logo, watermark, outline, anime style, different outfit, different colors`

---

## 2. Ev — sabit görsel referans promptu

Ev 4 aşamada değişiyor. Her aşama için **aynı promptun** ilgili kısmıyla birer referans görseli üret, sonra sahnelerde sırasıyla kullan.

```text
House construction reference, minimalist geometric 3D toy style, same camera (front 3/4 view, slightly high),
soft daylight, light-brown dirt lot on a pale sidewalk, simple pastel city blocks in the background.

Building language (same in every stage):
- Corner posts: four cream (#F3E6CF) rounded-corner square pillars.
- Walls: stacked rounded concrete blocks in light gray / cool gray / cream variations, slight gaps between blocks.
- Roof: gable roof made of two orange-brown wooden plank slabs (#E79A5A) with a rounded orange ridge beam,
  cream triangular gable on the front.
- Door: brown wooden plank door with a small orange knob and a small round lamp above it.
- Windows: square white frames with a cross bar, pale-blue glass (#BFE0F5), orange window sills.
Materials readable but simple: cardboard = corrugated tan with tape strip, wood = plank stripes,
glass = smooth pale blue, concrete = matte gray blocks.

STAGE A: four cream cube blocks on the lot with a flat corrugated cardboard sheet on top.
STAGE B: tiny house — cream pillars, gray block walls only ~waist height of the character, small wooden gable roof,
         a small rough doorway.
STAGE C: the same house stretched wide and tall (about 2x wider, 2.5x taller) but the roof is still the OLD small size,
         sitting in the middle; the open top edges of the walls are visible.
STAGE D: finished cute house — big roof covering everything, brown door, two square windows, door lamp.
```

---

## 3. Yedi sahnenin video üretim promptları

**Her sahne için ortak sabitler** (her promptun başına ekle):

```text
Vertical 9:16, 1080x1920, 30fps, minimalist geometric 3D animation, toy-like matte materials,
pastel palette (pastel blue, cream, light gray, orange, brown), soft daylight, smooth gentle camera,
no text on screen, no subtitles, consistent character from the reference image, consistent house from the reference image.
```

Her sahne 4–5 sn. Araç 5 sn'lik klip üretiyorsa tam üret, montajda kırp. Her sahnenin **son karesini** bir sonraki sahnenin **ilk kare referansı** (image-to-video / start frame) olarak kullanırsan ev ve karakter devamlılığı korunur.

### SAHNE 1 (0–4 sn) — Üşüyen karakter, karar anı
```text
A cold pale-blue city street with simple geometric pastel buildings. Light wind, a few tiny white specks drift sideways.
The character walks in from the left along the sidewalk, shivering, arms crossed and rubbing its arms, teeth chattering,
squinting eyes. Halfway across the frame it suddenly stops, turns to camera, eyes go wide and it raises one hand
in an "aha!" gesture; an orange 3D exclamation mark pops above its head.
Camera: medium shot tracking sideways with the character, then a slow push-in on its excited face.
```

### SAHNE 2 (4–8 sn) — Karton çatı ve yağmur
```text
On an empty light-brown dirt lot, the character places four cream cube blocks one by one; each drops and bounces into
place. A big corrugated cardboard sheet drops on top as a roof. The character does two happy little hops, arms up.
Rain starts. The cardboard darkens as it gets wet, sags in the middle, then folds into a V and collapses onto the ground.
The character jumps back in shock, eyes wide, mouth a small "O".
Camera: wide front shot, slightly high, character on the left, lot in the center; the sky turns grayer when rain starts.
```

### SAHNE 3 (8–12 sn) — Çatıyı düzeltir, duvarları örer
```text
Rain stops. The soggy cardboard flips away out of frame. The four corner blocks grow taller into pillars.
A small orange wooden gable roof drops onto the pillars with a bounce. The character hammers with one arm while
gray concrete blocks pop into place row by row, building the walls up to the roof, leaving a small doorway.
A tiny cute house is finished — it only reaches the character's waist. The character stands proudly, hands on hips,
happy closed-eye smile.
Camera: same wide front angle, slow drift to the right.
```

### SAHNE 4 (12–16 sn) — Sığmıyor!
```text
The character walks confidently to the tiny doorway and tries to enter: its head bonks into the wall above the door,
the body squashes, yellow cartoon stars circle its head. It crouches and tries again — bonk, more stars.
It steps back, turns to camera with one eyebrow raised and a flat mouth; an orange 3D question mark pops above its head.
It holds a flat hand above its own head, comparing its height to the house which only reaches its waist.
Camera: 3/4 side angle at character height, so the size mismatch is obvious.
```

### SAHNE 5 (16–20 sn) — Evi büyütür, çatıyı unutur
```text
The character stands at the side of the house and pushes the wall; the whole house stretches like rubber —
wider, deeper and much taller, with a springy overshoot. The roof stays its old small size, sitting in the middle
of the big walls, leaving the top of the house open. Rain starts again; drops fall through the open part into the house
and a pale-blue puddle grows on the wooden floor. The character looks up, then facepalms.
Camera: rises to a high front angle looking down so the gap around the small roof and the puddle are clearly visible.
```

### SAHNE 6 (20–25 sn) — Çatı uzar, kapı ve pencereler
```text
The character raises both arms and the roof stretches outward with a springy bounce until it covers the whole house;
the rain stops and the puddle shrinks away. A brown wooden door drops into the doorway; two square windows pop onto
the front wall — the right one is crooked. The character walks up and taps it; it wobbles and snaps straight.
The character steps back, faces the camera and presents the house with both arms open, big happy smile.
Camera: front view at slightly above eye level, gentle push-in.
```

### SAHNE 7 (25–30 sn) — Final: eve giriş
```text
The finished cute geometric house. The character walks to the door, opens it, turns to the camera and waves happily,
then walks inside; the door closes. The windows and the small lamp above the door light up warm yellow.
A light rain starts again outside, but the house is cozy and dry.
Camera: slow pull-back from medium to a wide shot of the whole house on the city street.
```

---

## 4. Türkçe TTS seslendirme metni

**Ses:** ElevenLabs — Liam (`TX3LPaxmHKxFdv7VOQHJ`), model `eleven_multilingual_v2`, dil `tr`
**Ayarlar:** stability 0.45 · similarity 0.80 · style 0.45 · speaker boost açık · hız 1.10
**Ton:** samimi, hafif alaycı, eğlenceli, enerjik. Üç nokta (…) kısa komik duraklama verir.

| # | Başlangıç | Metin | Süre |
|---|---|---|---|
| 1 | 0.25 sn | Dışarıda kalmaktan sıkıldım. Kendime bir ev yapmaya karar verdim! | 3.58 sn |
| 2 | 4.10 sn | Önce basit bir çatı yaptım. Ama küçük bir sorun var… Yağmur! | 3.76 sn |
| 3 | 8.20 sn | Çatıyı düzelttim, duvarları da ördüm. Artık hazırım! | 3.02 sn |
| 4 | 12.85 sn | Bir dakika… Ben bu eve nasıl sığacağım? | 2.65 sn |
| 5 | 16.25 sn | Evi büyüttüm. Ama bu sefer de çatıyı unuttum! | 2.93 sn |
| 6 | 20.15 sn | Çatıyı uzattım, pencereleri taktım. Biraz mimarlık, biraz sabır! | 4.23 sn |
| 7 | 24.50 sn | Ve işte! Tebrikler, artık bir ev inşa ettin. Artık yağmurda ıslanmak yok! | 5.39 sn |

Son replik 5.4 sn sürdüğü için 25. saniyeden yarım saniye önce başlıyor ve 29.89'da bitiyor.

Ses dosyaları: `audio/s1.mp3 … s7.mp3`. Her birinin yanındaki `.json` dosyası kelime kelime zamanlama içeriyor. Yeniden üretmek için:
```bash
python3 ../../tts/elevenlabs_tts.py script narration.json -o audio
```

---

## 5. Altyazı (SRT)

`build/altyazi.srt` — ElevenLabs kelime zamanlamalarından otomatik üretildi, seslendirmeyle birebir senkron.

```srt
1
00:00:00,200 --> 00:00:01,829
Dışarıda kalmaktan
sıkıldım.

2
00:00:01,849 --> 00:00:04,030
Kendime bir ev
yapmaya karar verdim!

3
00:00:04,050 --> 00:00:05,690
Önce basit bir
çatı yaptım.

4
00:00:05,710 --> 00:00:07,107
Ama küçük bir
sorun var…

5
00:00:07,127 --> 00:00:08,112
Yağmur!

6
00:00:08,150 --> 00:00:10,173
Çatıyı düzelttim,
duvarları da ördüm.

7
00:00:10,193 --> 00:00:11,469
Artık hazırım!

8
00:00:12,800 --> 00:00:13,871
Bir dakika…

9
00:00:13,891 --> 00:00:15,747
Ben bu eve
nasıl sığacağım?

10
00:00:16,200 --> 00:00:17,220
Evi büyüttüm.

11
00:00:17,268 --> 00:00:19,426
Ama bu sefer de
çatıyı unuttum!

12
00:00:20,100 --> 00:00:22,390
Çatıyı uzattım,
pencereleri taktım.

13
00:00:22,410 --> 00:00:24,430
Biraz mimarlık,
biraz sabır!

14
00:00:24,450 --> 00:00:25,447
Ve işte!

15
00:00:25,692 --> 00:00:28,122
Tebrikler, artık
bir ev inşa ettin.

16
00:00:28,142 --> 00:00:29,980
Artık yağmurda
ıslanmak yok!
```

**Stilli sürüm** (`build/altyazi.ass`, montajda videoya gömülür):
- Inter Display Bold, 86 px, beyaz
- Koyu kontur (6 px) ve yarı saydam gölge (5 px)
- Anahtar kelimeler turuncu (#F5963C): *ev, çatı(yı), Yağmur, duvarları, hazırım, sığacağım, unuttum, pencereleri, sabır, Tebrikler, inşa, ıslanmak, yok*
- Alttan 420 px yukarıda, yani Reels/TikTok/Shorts arayüzünün üstündeki güvenli bölgede
- Her satır hafif büyüyerek (%88 → %100) ve fade ile girer

---

## 6. Ses efektleri ve müzik planı

| Zaman | Olay | Ses |
|---|---|---|
| 0.0–4.6 | Soğuk sokak | Hafif rüzgâr (kahverengi gürültü, esintili) + ayak sesleri |
| 2.45 | "!" fikir anı | Parlak "ding" |
| 4.5–5.3 | Bloklar düşer | 4 tok "thud" + küçük sekme |
| 5.3 | Karton çatı | Hışırtı + yumuşak "fump" |
| 5.5 / 5.8 | Sevinç zıplaması | Küçük "boing"ler |
| 6.0–8.5 | Yağmur | Yağmur hışırtısı + damla tıkırtıları |
| 7.12–7.4 | Karton çöker | Islak "şlap" + yere düşüş |
| 7.42–9.2 | Komik tepki | "Womp womp" (inen trombon) |
| 8.05 | Karton uçar | Whoosh |
| 8.75 | Ahşap çatı oturur | Tahta "tok" |
| 9.0–10.6 | Duvar örülür | 18 hafif "tık" (rastgele perde) |
| 12.65 / 13.68 | Kafa kapıya çarpar | Komik "bonk" + yıldız cıvıltısı |
| 14.7 | "?" | Pop |
| 16.3–17.2 | Ev esner | Yükselen "boooing" + gıcırtı |
| 17.25–21.0 | Yağmur tekrar | Yağmur + içeri damlayan "plip"ler |
| 18.5 | Facepalm | Şaplak |
| 20.3 | Çatı uzar | Boing |
| 21.2 / 21.4 / 21.8 | Kapı, pencereler | Tahta "tok" + iki pop |
| 23.0 | Yamuk pencere | Cam "tink" + titreşim boing |
| 25.4 | Kapı açılır | Gıcırtı |
| 26.0–30.0 | **Final müziği** | Neşeli ukulele arpeji (C–G–Am–F → C) + glockenspiel |
| 28.3 | Kapı kapanır | Tok ses |
| 28.45 | Işık yanar | Klik + sıcak "ding" |
| 28.3–30 | Dışarıda yağmur | İçeriden duyulan boğuk yağmur |

**Miks:** Seslendirme −2 dBFS tepe. Müzik ve ortam sesi, konuşma sırasında ~%45 kısılıyor (ducking). Final ses −14 LUFS'e normalize ediliyor (sosyal medya standardı), gerçek tepe −1 dBTP.
Stem'ler: `build/stems/voice.wav`, `sfx.wav`, `ambience.wav`, `music.wav`.

---

## 7. Son montaj ve dışa aktarma ayarları

**Montaj sırası (herhangi bir editörde: CapCut, Premiere, DaVinci, Final Cut):**
1. Timeline: 1080×1920, 30 fps (sabit), 30.00 sn.
2. 7 sahne klibini sırayla diz (0–4–8–12–16–20–25–30). Geçişler düz kesme. Sadece 4→5 ve 6→7 arasında 6–8 karelik (0.2–0.27 sn) hızlı kaydırma veya zoom geçişi.
3. `audio/s1…s7.mp3` dosyalarını tablodaki başlangıç zamanlarına yerleştir (ya da hazır `build/mix.wav`'ı tek parça kullan).
4. Efekt ve müzik stem'lerini ekle, konuşma altında müziği kıs.
5. Altyazıyı **montajda** ekle: `build/altyazi.srt` (platform altyazısı) veya `build/altyazi.ass` (gömülü, stilli).
6. İlk 1 saniyede kanca: karakterin titremesi ve rüzgâr. Kesme yapmadan direkt başla.

**Dışa aktarma:**

| Ayar | Değer |
|---|---|
| Kapsayıcı | MP4 (`+faststart`) |
| Video | H.264 High, yuv420p, 1080×1920, 30 fps CFR, CRF 18 (≈ 8–12 Mbps) |
| Ses | AAC-LC 192 kbps, 48 kHz, stereo, −14 LUFS, −1 dBTP |
| Süre | 30.0 sn |
| Altyazı | Gömülü (ASS) + ayrıca SRT dosyası |

Bu klasördeki betiklerin kullandığı ffmpeg komutu:
```bash
ffmpeg -framerate 30 -i frames/f_%04d.jpg -i build/mix.wav \
  -vf "ass=build/altyazi.ass" -c:v libx264 -profile:v high -preset slow -crf 18 -pix_fmt yuv420p \
  -af "loudnorm=I=-14:TP=-1:LRA=11" -c:a aac -b:a 192k -ar 48000 \
  -t 30 -movflags +faststart build/ev-yapiyoruz.mp4
```

---

## Bu klasördeki MP4 nasıl üretildi?

| Parça | Araç | Not |
|---|---|---|
| Görüntü | `scene/main.js` (Three.js) + `render.mjs` (headless Chromium) | Kodla modellenmiş geometrik 3D sahne, 900 kare deterministik render. Bir AI video modeli kullanılmadı. |
| Seslendirme | ElevenLabs TTS (`tts/elevenlabs_tts.py`) | Gerçek ElevenLabs çıktısı, kelime zamanlamaları API'den |
| Efektler ve müzik | `build_audio.py` (numpy sentez) | Mevcut ElevenLabs anahtarının ses efekti ve müzik izni yok, o yüzden prosedürel sentezlendi |
| Altyazı | `build_subs.py` | ElevenLabs kelime zamanlarından SRT ve ASS |
| Montaj | ffmpeg | ASS gömme, loudnorm, H.264/AAC |

**Yeniden üretmek için:**
```bash
cd animasyon/ev-yapiyoruz
npm install                                    # three.js
python3 ../../tts/elevenlabs_tts.py script narration.json -o audio   # (isteğe bağlı) sesi yeniden üret
node render.mjs --out frames --workers 4       # 900 kare (~10 dk)
python3 build_audio.py && python3 build_subs.py
# sonra yukarıdaki ffmpeg komutu
```
Önizleme için tek kareler: `node render.mjs --out prev --scale 0.4 --times 2.9,7.4,13.7`
