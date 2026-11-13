# SIFIRDAN EV YAPIYORUZ! — Üretim Paketi (v2)

30 sn · 9:16 · 1080×1920 · 30 FPS · Türkçe TTS + senkron Türkçe altyazı · keskin, low-poly geometrik 3D

> **Bu klasörde iki şey var:**
> 1. AI video araçları (Runway, Kling, Veo, Sora, Pika, Hailuo vb.) ile yeniden üretmek için hazır **promptlar ve plan** (bölüm 1–7).
> 2. Aynı senaryoyu izleyen, **kodla render edilmiş bitmiş bir MP4** (`build/ev-yapiyoruz.mp4`). Görüntü Three.js ile kare kare çizildi; seslendirme ElevenLabs ile üretildi; efektler ve müzik kodla sentezlendi. Ayrıntılar en altta.

**v2'deki değişiklikler:** keskin kenarlı low-poly stil; yeni renkler; çimen, toprak arsa, ağaçlar ve çalılar. Ev en baştan gerçek boyutta. Parçalar havada ayrık dururken kendiliğinden birleşiyor: temel → tuğla → çatı iskeleti → yalıtım → sıva → kiremit → kapı ve pencere. Sahne 4–6 yeni esprilerle yeniden yazıldı.

Video promptları İngilizce yazıldı, çünkü video modelleri İngilizce promptlarda daha tutarlı sonuç veriyor. Seslendirme ve altyazılar Türkçe.

---

## 1. Karakter — sabit görsel referans promptu

```text
Character reference sheet: front, 3/4, side and back view of the same character, plain light-gray background,
crisp low-poly geometric 3D style, sharp clean edges with only a tiny bevel, soft studio light, no outlines.

Character: a friendly young man built from simple blocky shapes, realistic-ish proportions (about 6 heads tall).
- Head: slightly rounded box, warm skin (#EFC3A0), small box ears, short dark-brown hair visible under the hat.
- Face: two small black rectangular eyes with a white highlight, thin dark-brown brows, small box nose,
  pink cheek dots, simple expressive mouth.
- Hat: red beanie (#C9433A) with a darker folded band and a small cream low-poly pompom.
- Scarf: teal (#2E7D82) wrapped around the neck, one tail hanging at the front.
- Jacket: mustard-yellow (#E6A93A) boxy jacket, darker hem and cuffs, zipper line, two small pockets.
- Pants: navy (#34495E) straight box legs. Shoes: dark-brown blocky shoes.
- Arms: box arms in jacket color, small box hands.
Matte materials, consistent colors, no text, no logo.
```

**Kilitlenecek özellikler:** kırmızı bere + krem ponpon, petrol mavisi atkı, hardal sarısı mont, lacivert pantolon, kutu kafa, siyah dikdörtgen gözler.

**Negatif prompt:** `realistic human, fingers, long hair, extra limbs, text, logo, watermark, outline, anime, different outfit, different colors, soft blobby shapes`

---

## 2. Ev — sabit görsel referans promptu

Ev 5 aşamada değişiyor. Her aşama için bir referans görsel üret ve ilgili sahnelerde kullan.

```text
House construction reference, crisp low-poly geometric 3D style, same camera (front, slightly high), sunny day.
Setting: a brown soil building lot on green grass, low-poly round and pine trees, a few bushes, a low cream wooden fence
behind the lot, a pale paved sidewalk and a road in front, a small distant town with red roofs.

House (real size, about 1.5x the character's height at the walls):
- Foundation: gray concrete slab made of four pieces. Corner posts: four square gray concrete posts.
- Walls: stacked red-orange bricks in slightly varied shades, small mortar gaps. Front wall has a door opening
  in the middle and two square window openings.
- Roof frame: wooden rafters, ridge beam and plank deck boards with visible gaps; wooden triangular gables.
- Insulation: yellow foam boards on the outside of the walls. Plaster: smooth off-white render over them.
- Roof: terracotta tiles in rows, ridge cap, small brick chimney.
- Door: teal plank door with a brass knob, white frame, small lamp above. Windows: white frames with a cross, pale-blue glass, gray sills.

STAGE A: four foundation pieces + four short posts with a flat corrugated cardboard sheet on top.
STAGE B: red brick walls + bare wooden roof frame and deck boards (no tiles, no insulation).
STAGE C: same house, walls covered by yellow insulation boards, then off-white plaster.
STAGE D: finished house: tiled roof, chimney, teal door, two windows, door lamp.
```

---

## 3. Yedi sahnenin video üretim promptları

**Ortak sabitler** (her promptun başına ekle):

```text
Vertical 9:16, 1080x1920, 30fps, crisp low-poly geometric 3D animation, sharp clean edges, matte materials,
palette: grass green, soil brown, sky blue, brick red, terracotta, mustard yellow, teal, off-white.
Smooth gentle camera, no text on screen, no subtitles, consistent character and house from the reference images.
Building parts are never carried by hand: they float in the air separated (exploded view), then fly in and snap together.
```

Her sahnenin **son karesini** bir sonraki sahnenin **ilk karesi** (image-to-video / start frame) olarak kullan. Böylece ev ve karakter devamlılığı korunur.

### SAHNE 1 (0–4 sn) — Üşüyen karakter, karar anı
```text
A cold, slightly bluish morning on a sidewalk next to a green park with low-poly trees. Tiny white specks drift in the wind.
The character walks in from the left, shivering, arms crossed and rubbing them, teeth chattering.
He stops, turns to camera, eyes go wide, raises one hand — an orange 3D exclamation mark pops above his head.
Camera: medium tracking shot, then a slow push-in on his excited face.
```

### SAHNE 2 (4–8 sn) — Karton çatı ve yağmur
```text
On an empty soil lot, four gray concrete foundation pieces float in the air apart from each other, then fly in and lock
together. Four short concrete posts rise from the corners. A big corrugated cardboard sheet drops on top as a roof.
The character walks underneath and does two happy hops. Rain starts; the cardboard darkens, sags in the middle,
folds into a V and collapses — the character jumps out just in time, shocked, mouth an "O".
Camera: wide front shot, slightly high; the sky turns gray when it rains.
```

### SAHNE 3 (8–12 sn) — Duvarlar ve çatı iskeleti kendiliğinden kurulur
```text
Rain stops, the soggy cardboard flips away. The posts grow to full wall height. Hundreds of red bricks rise into the air
around the lot like an exploded diagram, hover, then fly in row by row and click into place, forming walls with a door
opening and two window openings. Wooden rafters, a ridge beam and deck boards float above and snap together into a
gable roof frame. The character conducts it all like a magician, then stands proudly, hands on hips.
Camera: wide, slightly high, slow drift.
```

### SAHNE 4 (12–16 sn) — İçerisi buz gibi!
```text
The character walks confidently through the door opening into the bare brick house. An icy gust with white snow
specks blows straight through the gaps of the bare walls. He walks back out frozen: frost on his hat and shoulders,
bluish skin, shivering hard, teeth chattering, staring at the camera in disbelief.
Camera: front, character height, push-in on the frozen character.
```

### SAHNE 5 (16–20 sn) — Yalıtım, sıva… ve çatı akıyor
```text
Yellow insulation boards float out around the house, then fly in and cover every outer wall. Smooth off-white plaster
sweeps up over them from bottom to top; the house now looks clean and warm. The frost melts off the character, he hops happily.
He steps into the doorway — rain starts, and water drips through the gaps in the bare roof boards right onto his head;
a small puddle forms at his feet. He looks up, then facepalms.
Camera: wide for the insulation, then a close shot of the character in the doorway.
```

### SAHNE 6 (20–25 sn) — Kiremit, kapı, pencereler
```text
Terracotta roof tiles float above the house in rows, then rain down and click into place from the eaves up to the ridge;
a ridge cap and a brick chimney snap on. Rain stops, the puddle dries. Teal door planks fly together into a door with a
white frame and a lamp; two window frames assemble piece by piece with glass — the right window ends up crooked.
The character taps it; it wobbles and snaps straight. He steps back and presents the house with open arms.
Camera: wide, slightly high, slowly moving closer.
```

### SAHNE 7 (25–30 sn) — Final
```text
The finished house on its green lot among trees. The character walks to the door, opens it, turns and waves happily
at the camera, walks inside, the door closes. Windows and the door lamp light up warm yellow, smoke puffs from the
chimney. A light rain starts again outside — the house is cozy and dry.
Camera: slow pull-back to a wide shot of the whole house.
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
| 4 | 13.20 sn | Bir dakika… İçerisi dışarıdan bile soğuk! | 2.65 sn |
| 5 | 16.10 sn | Duvarları yalıttım, sıvadım. Ama bu sefer de çatı akıyor! | 3.90 sn |
| 6 | 20.00 sn | Kiremitleri dizdim, pencereleri taktım. Biraz mimarlık, biraz sabır! | 4.55 sn |
| 7 | 24.58 sn | Ve işte! Tebrikler, artık bir ev inşa ettin. Artık yağmurda ıslanmak yok! | 5.39 sn |

Ses dosyaları: `audio/s1.mp3 … s7.mp3`. Her birinin yanındaki `.json` dosyası kelime kelime zamanlama içeriyor. Yeniden üretmek için: `python3 ../../tts/elevenlabs_tts.py script narration.json -o audio`

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
00:00:13,150 --> 00:00:14,128
Bir dakika…

9
00:00:14,148 --> 00:00:16,030
İçerisi dışarıdan
bile soğuk!

10
00:00:16,050 --> 00:00:18,068
Duvarları
yalıttım, sıvadım.

11
00:00:18,314 --> 00:00:19,930
Ama bu sefer
de çatı akıyor!

12
00:00:19,950 --> 00:00:22,444
Kiremitleri dizdim,
pencereleri taktım.

13
00:00:22,551 --> 00:00:24,510
Biraz mimarlık,
biraz sabır!

14
00:00:24,530 --> 00:00:25,527
Ve işte!

15
00:00:25,772 --> 00:00:28,202
Tebrikler, artık
bir ev inşa ettin.

16
00:00:28,222 --> 00:00:29,980
Artık yağmurda
ıslanmak yok!
```

**Stilli sürüm** (`build/altyazi.ass`, videoya gömülü):
- Inter Display Bold, 86 px, beyaz
- Koyu kontur (6 px) ve yarı saydam gölge
- Anahtar kelimeler turuncu: *ev, çatı(yı), Yağmur, duvarları, hazırım, soğuk, yalıttım, sıvadım, akıyor, Kiremitleri, pencereleri, sabır, Tebrikler, inşa, ıslanmak, yok*
- Alttan 420 px yukarıda, sosyal medya arayüzünün üstündeki güvenli bölgede
- Her satır hafif büyüyerek ve fade ile girer

---

## 6. Ses efektleri ve müzik planı

| Zaman | Olay | Ses |
|---|---|---|
| 0.0–4.6 | Soğuk sokak | Esintili rüzgâr + ayak sesleri |
| 2.45 | "!" fikir anı | Parlak "ding" |
| 4.15–4.95 | Temel parçaları kenetlenir | 4 whoosh + 4 tok "thud" |
| 4.95 | Direkler yükselir | Kısa "boing" |
| 5.3–5.5 | Karton çatı | Hışırtı + "fump" |
| 5.97 / 6.17 | Sevinç zıplaması | Küçük boing'ler |
| 6.15–8.4 | Yağmur | Yağmur hışırtısı + damlalar |
| 7.05–7.3 | Karton çöker | Islak "şlap" + yere düşüş |
| 7.42–9.2 | Komik tepki | "Womp womp" (inen trombon) |
| 8.0–10.4 | Tuğlalar havalanıp yerine oturur | Whoosh + 26 hafif "tık" |
| 10.3–11.3 | Çatı iskeleti, kaplama | Tahta "tok"lar |
| 12.6 | Çıplak duvarlardan buzlu rüzgâr | Sert whoosh + cıvıltı |
| 16.5–17.2 | Yalıtım levhaları | Yumuşak "fump"lar |
| 16.95 | Sıva | Uzun "şuuu" |
| 18.2–20.9 | Yağmur + çatı akıyor | Yağmur + kafaya "plip"ler |
| 18.95 | Facepalm | Şaplak |
| 20.4–21.5 | Kiremitler | 24 seramik "tık" |
| 21.5–22.1 | Baca, kapı, pencereler | Tahta "tok" + iki pop |
| 23.0 | Yamuk pencere | Cam "tink" + boing |
| 25.4 | Kapı açılır | Gıcırtı |
| 26.0–30.0 | **Final müziği** | Neşeli ukulele arpeji (C–G–Am–F → C) + glockenspiel |
| 28.3 / 28.45 | Kapı kapanır, ışık yanar | Tok ses + klik + sıcak "ding" |
| 28.3–30 | Dışarıda yağmur | İçeriden duyulan boğuk yağmur |

**Miks:** Seslendirme −2 dBFS tepe. Müzik ve ortam sesi, konuşma sırasında ~%45 kısılıyor (ducking). Final ses −14 LUFS, −1 dBTP. Stem'ler: `build/stems/`.

---

## 7. Son montaj ve dışa aktarma ayarları

1. Timeline: 1080×1920, 30 fps sabit, 30.00 sn.
2. 7 klibi sırayla diz (0–4–8–12–16–20–25–30). Geçişler düz kesme, sahne içi kamera hareketleri yumuşak.
3. Seslendirmeyi tablodaki zamanlara koy (ya da `build/mix.wav`'ı tek parça kullan). Efektleri ve müziği ekle.
4. Altyazıyı montajda ekle: `altyazi.srt` (platform altyazısı) veya `altyazi.ass` (gömülü, stilli).

| Ayar | Değer |
|---|---|
| Kapsayıcı | MP4 (`+faststart`) |
| Video | H.264 High, yuv420p, 1080×1920, 30 fps CFR, CRF 18 |
| Ses | AAC-LC 192 kbps, 48 kHz, stereo, −14 LUFS, −1 dBTP |
| Altyazı | Gömülü (ASS) + ayrıca SRT |

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
| Görüntü | `scene/main.js` (Three.js) + `render.mjs` (headless Chromium) | Kodla modellenmiş low-poly 3D sahne, 900 kare deterministik render. Bir AI video modeli kullanılmadı. |
| Seslendirme | ElevenLabs TTS (`tts/elevenlabs_tts.py`) | Gerçek ElevenLabs çıktısı, kelime zamanlamaları API'den |
| Efektler ve müzik | `build_audio.py` (numpy sentez) | Mevcut ElevenLabs anahtarının ses efekti ve müzik izni yok |
| Altyazı | `build_subs.py` | ElevenLabs kelime zamanlarından SRT ve ASS |
| Montaj | ffmpeg | ASS gömme, loudnorm, H.264/AAC |

**Yeniden üretmek için:**
```bash
cd animasyon/ev-yapiyoruz && npm install
node render.mjs --out frames --workers 4       # 900 kare (~11 dk)
python3 build_audio.py && python3 build_subs.py
# sonra yukarıdaki ffmpeg komutu
```
Önizleme kareleri: `node render.mjs --out prev --scale 0.4 --times 2.9,7.2,14.5`
