"""Uzun video modu: yayıncının video izlediği (react) bölümleri bulur, kapak/başlık hazırlar,
1080p olarak yeniden kodlamadan YouTube'a yükler.

Akış:
1) Yayından her ~20-30 sn'de bir 480p kare alınır (yayın indirilmez).
2) Claude kareleri görüp her an için ne yapıldığını etiketler: video izliyor / oyun / sohbet / ara / diğer
   ve ekranda okunabiliyorsa izlenen videonun adını yazar.
3) Ardışık 'video' anları bölüm olur; bölüm sınırları 5 sn'lik ek karelerle hassaslaştırılır.
4) Her bölüm için 1080p karelerden kapak (sahne + yayıncı yüzü + yazı), başlık, açıklama üretilir.
5) Yüklerken bölüm 1080p akıştan birebir kopyalanır (-c copy), yüklenir, geçici dosya silinir.
"""

from __future__ import annotations

import difflib
import json
import os
import re
import subprocess
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field, replace
from typing import Callable, Optional

from . import llm
from .layout import analyze_scene, resolve_cam_rect
from .source import Source, resolve
from .thumbnail import compose
from .utils import Logger, default_log, fmt_time, parse_range, parse_time

ACTIVITIES = ("video", "oyun", "sohbet", "ara", "diger")


@dataclass
class LongConfig:
    source: str = ""
    output_dir: str = "output"
    work_dir: str = "work"
    max_height: int = 1080
    time_range: Optional[str] = None
    step: float = 0.0               # kare aralığı (sn). 0 = otomatik (20 sn, en fazla 1000 kare)
    min_minutes: float = 4.0        # bundan kısa izleme bölümleri atlanır
    max_minutes: float = 40.0       # bundan uzun bölümler parçalara ayrılır
    merge_gap: float = 150.0        # iki izleme arası bu kadar kısaysa (yorum molası) birleştir (sn)
    split_by_video: bool = True     # izlenen video değişince ayrı bölüm yap
    manual: str = ""                # elle aralıklar: "1:02:00-1:25:00 Madara Olduk" (satır satır)
    streamer: Optional[str] = None


@dataclass
class Section:
    start: float
    end: float
    watched: str = ""
    platform: str = ""
    player_box: list = field(default_factory=list)
    part: int = 1
    parts: int = 1
    frames: list = field(default_factory=list)     # [(t, label)] bölüm içindeki örnek kareler

    @property
    def duration(self) -> float:
        return self.end - self.start


# ----------------------------------------------------------------------------- kare örnekleme
def sample(src: Source, times: list[float], which: str = "preview", width: int = 512,
           log: Logger = default_log, label: str = "Kareler alınıyor") -> list[tuple[float, bytes]]:
    out: dict[float, bytes] = {}
    done = [0]

    def job(t):
        b = src.grab_jpeg(t, which, width=width, quality=4)
        done[0] += 1
        if done[0] % 50 == 0:
            log(f"{label}: {done[0]}/{len(times)}")
        return t, b

    with ThreadPoolExecutor(max_workers=8) as ex:
        for t, b in ex.map(job, times):
            if b:
                out[t] = b
    return sorted(out.items())


# ----------------------------------------------------------------------------- sınıflandırma
CLASSIFY_SYSTEM = """Bir Kick/Twitch yayınından alınmış ekran görüntülerini sınıflandırıyorsun. Her kare için
yayıncının o an ne yaptığını belirle:

- video: yayıncı başka bir içeriği İZLİYOR - YouTube/TikTok/Instagram/Twitter videosu, başka bir yayın,
  klip, film/dizi/anime, haber. Ekranın büyük bölümünde bir video oynatıcı ya da izlenen içerik var.
  (Yayıncının kendi oyunu bu değildir.)
- oyun: yayıncı oyun oynuyor (oyun arayüzü, HUD, oyun dünyası).
- sohbet: just chatting; kamera büyük/tam ekran, chat okuma, sohbet, çekiliş vb.
- ara: "başlıyor/mola/AFK/bitti" ekranı, reklam, siyah/donmuş ekran.
- diger: web sitesi gezme, alışveriş, ayar ekranı, masaüstü vb.

'watched': kare 'video' ise, ekranda OKUNABİLEN video başlığını / kanal adını aynen yaz (ör. "Madara Olduk #129").
Okunmuyorsa içeriği 2-5 kelimeyle tarif et (ör. "Naruto anime sahnesi", "trafik kazası haberi"). Diğer
kategorilerde boş bırak.
'platform': youtube | tiktok | instagram | twitter | twitch | kick | film | diger | (boş)
'player_box': 'video' ise izlenen içeriğin ekrandaki yaklaşık alanı [x, y, genişlik, yükseklik], 0-1 oranları;
yayıncı kamerası ve chat bu alanın dışında kalsın. Diğer kategorilerde boş liste."""

CLASSIFY_SCHEMA = {
    "type": "object",
    "properties": {
        "frames": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "index": {"type": "integer"},
                    "activity": {"type": "string", "enum": list(ACTIVITIES)},
                    "watched": {"type": "string"},
                    "platform": {"type": "string"},
                    "player_box": {"type": "array", "items": {"type": "number"}},
                },
                "required": ["index", "activity", "watched", "platform", "player_box"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["frames"],
    "additionalProperties": False,
}


def classify(frames: list[tuple[float, bytes]], streamer: str = "", log: Logger = default_log,
             batch: int = 40) -> dict[float, dict]:
    """{t: {"activity", "watched", "platform", "player_box"}}"""
    batches = [frames[i:i + batch] for i in range(0, len(frames), batch)]
    result: dict[float, dict] = {}
    done = [0]

    def job(b):
        content: list = [{"type": "text", "text": f"Yayıncı: {streamer or 'bilinmiyor'}. {len(b)} kare, sırayla:"}]
        for i, (t, jpg) in enumerate(b):
            content.append({"type": "text", "text": f"Kare {i} (yayının {fmt_time(t)} anı)"})
            content.append(llm.image_block(jpg))
        last = None
        for _ in range(2):
            try:
                data = llm.ask_json(CLASSIFY_SYSTEM, content, CLASSIFY_SCHEMA, effort="low", max_tokens=12000)
                break
            except Exception as e:
                last = e
        else:
            raise RuntimeError(f"Kare sınıflandırma başarısız: {last}")
        out = {}
        for fr in data.get("frames", []):
            i = fr.get("index")
            if isinstance(i, int) and 0 <= i < len(b):
                act = fr.get("activity") if fr.get("activity") in ACTIVITIES else "diger"
                out[b[i][0]] = {"activity": act, "watched": (fr.get("watched") or "").strip(),
                                "platform": (fr.get("platform") or "").strip(),
                                "player_box": fr.get("player_box") or []}
        done[0] += 1
        log(f"Claude kareleri inceliyor: {done[0]}/{len(batches)}")
        return out

    with ThreadPoolExecutor(max_workers=4) as ex:
        for part in ex.map(job, batches):
            result.update(part)
    return result


# ----------------------------------------------------------------------------- bölümleme
def _norm(s: str) -> str:
    return re.sub(r"[^\w]+", " ", s.lower(), flags=re.UNICODE).strip()


def _same(a: str, b: str) -> bool:
    a, b = _norm(a), _norm(b)
    if not a or not b:
        return True
    return a in b or b in a or difflib.SequenceMatcher(None, a, b).ratio() > 0.55


def _smooth(acts: list[str]) -> list[str]:
    """Tek karelik sapmaları düzelt (A B A -> A A A)."""
    out = list(acts)
    for i in range(1, len(acts) - 1):
        if acts[i - 1] == acts[i + 1] != acts[i]:
            out[i] = acts[i - 1]
    return out


def build_sections(labels: dict[float, dict], step: float, cfg: LongConfig, lo: float, hi: float) -> list[Section]:
    ts = sorted(labels)
    acts = _smooth([labels[t]["activity"] for t in ts])
    runs: list[list[float]] = []
    cur: list[float] = []
    for t, a in zip(ts, acts):
        if a == "video":
            if cur and t - cur[-1] > cfg.merge_gap + step:
                runs.append(cur)
                cur = []
            cur.append(t)
    if cur:
        runs.append(cur)

    sections: list[Section] = []
    for run in runs:
        # izlenen video değişiyorsa böl (değişim en az 3 kare sürmeli)
        groups = [[run[0]]]
        if cfg.split_by_video:
            for t in run[1:]:
                prev_w = Counter(labels[x]["watched"] for x in groups[-1] if labels[x]["watched"]).most_common(1)
                w = labels[t]["watched"]
                if prev_w and w and not _same(prev_w[0][0], w):
                    nxt = [x for x in run if t <= x <= t + 3 * step]
                    if len(nxt) >= 3 and all(_same(w, labels[x]["watched"]) for x in nxt if labels[x]["watched"]):
                        groups.append([t])
                        continue
                groups[-1].append(t)
        else:
            groups[-1] += run[1:]
        for g in groups:
            ws = [labels[t]["watched"] for t in g if labels[t]["watched"]]
            ps = [labels[t]["platform"] for t in g if labels[t]["platform"]]
            boxes = [labels[t]["player_box"] for t in g if len(labels[t]["player_box"]) == 4]
            box = [sorted(b[i] for b in boxes)[len(boxes) // 2] for i in range(4)] if boxes else []
            sections.append(Section(max(lo, g[0] - step / 2), min(hi, g[-1] + step / 2),
                                    Counter(ws).most_common(1)[0][0] if ws else "",
                                    Counter(ps).most_common(1)[0][0] if ps else "", box,
                                    frames=[(t, labels[t]["activity"]) for t in g]))
    return sections


def refine(src: Source, sections: list[Section], step: float, streamer: str, log: Logger) -> None:
    """Bölüm sınırlarını 5 sn'lik ek karelerle hassaslaştırır.
    Sadece 'video -> başka şey' geçişleri incelenir; iki bölümün bitiştiği (izlenen video değişen) sınırlar korunur."""
    fine = 5.0
    sections.sort(key=lambda x: x.start)
    touch_prev = [i > 0 and s.start - sections[i - 1].end < step * 1.5 for i, s in enumerate(sections)]
    touch_next = [i + 1 < len(sections) and sections[i + 1].start - s.end < step * 1.5 for i, s in enumerate(sections)]
    times: list[float] = []
    for i, s in enumerate(sections):
        for b, skip in ((s.start, touch_prev[i]), (s.end, touch_next[i])):
            if not skip:
                times += [b - step + k * fine for k in range(int(2 * step / fine) + 1)]
    times = sorted({round(min(src.end, max(src.start, t)), 1) for t in times})
    if not times:
        return
    log(f"Bölüm sınırları hassaslaştırılıyor ({len(times)} ek kare)...")
    labels = classify(sample(src, times, log=log, label="Sınır kareleri"), streamer, log)
    for i, s in enumerate(sections):
        if not touch_prev[i]:
            win = sorted(t for t in labels if s.start - step - 1 <= t <= s.start + step + 1)
            # başlangıç: pencerede 'video' olan ilk kare (öncesi video değil)
            vids = [t for t in win if labels[t]["activity"] == "video"]
            if vids:
                s.start = max(src.start, vids[0] - fine / 2)
        if not touch_next[i]:
            win = sorted(t for t in labels if s.end - step - 1 <= t <= s.end + step + 1)
            vids = [t for t in win if labels[t]["activity"] == "video"]
            if vids:
                s.end = min(src.end, vids[-1] + fine / 2)
    # güvenlik: çakışma kalmasın
    for a, b in zip(sections, sections[1:]):
        if b.start < a.end:
            mid = (a.end + b.start) / 2
            a.end, b.start = mid, mid


def finalize(sections: list[Section], cfg: LongConfig) -> list[Section]:
    out: list[Section] = []
    for s in sections:
        if s.duration < cfg.min_minutes * 60:
            continue
        n = max(1, int(-(-s.duration // (cfg.max_minutes * 60))))
        if n == 1:
            out.append(s)
            continue
        size = s.duration / n
        for i in range(n):
            out.append(replace(s, start=s.start + i * size, end=s.start + (i + 1) * size, part=i + 1, parts=n,
                               frames=[f for f in s.frames if s.start + i * size <= f[0] < s.start + (i + 1) * size]))
    return out


def manual_sections(text: str, lo: float, hi: float) -> list[Section]:
    out = []
    for line in (text or "").splitlines():
        line = line.strip()
        m = re.match(r"^([\d:.]+)\s*-\s*([\d:.]+)\s*(.*)$", line)
        if not m:
            continue
        a, b = parse_time(m.group(1)), parse_time(m.group(2))
        if b > a:
            out.append(Section(max(lo, a), min(hi, b), m.group(3).strip()))
    return out


# ----------------------------------------------------------------------------- başlık + kapak
META_SYSTEM = """Sen Türk Kick/Twitch yayıncılarının "react" (video izleme) bölümlerini YouTube'a yükleyen bir kanal
editörüsün. Sana bir bölümden kareler ve izlenen içerik bilgisi verilecek. YouTube için:

- title: en fazla 90 karakter. Kalıp: "<Yayıncı> - <İzlenen içerik> İzliyor!" ya da daha çarpıcı doğal bir varyasyon
  (ör. "Eray - Madara Olduk #129 İzliyor!"). İzlenen içeriğin gerçek adını kullan, uydurma. Parça numarası
  verilmişse sona "(Bölüm X)" ekle.
- description: 2-4 cümle; yayıncının neyi izlediği ve tepkisi, ardından boş satır, "İzlenen içerik: <ad/kanal>",
  "Yayın: <yayın başlığı>", sonra 3-6 hashtag.
- tags: 8-15 YouTube etiketi (yayıncı adı, izlenen içerik, react, tepki, kick yayını...), # işaretsiz.
- thumb_text: kapak yazısı, 2-4 kelime, BÜYÜK HARF, merak uyandıran (ör. "BU NE BÖYLE?!", "MADARA GELDİ").
- background_frame: kapak arka planı için en çarpıcı karenin numarası (izlenen içerikten net bir sahne).
- player_box: o karede izlenen içeriğin alanı [x, y, w, h] 0-1 oranları (kamera ve chat hariç)."""

META_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "description": {"type": "string"},
        "tags": {"type": "array", "items": {"type": "string"}},
        "thumb_text": {"type": "string"},
        "background_frame": {"type": "integer"},
        "player_box": {"type": "array", "items": {"type": "number"}},
    },
    "required": ["title", "description", "tags", "thumb_text", "background_frame", "player_box"],
    "additionalProperties": False,
}


def _fallback_meta(sec: Section, streamer: str, src_title: str) -> dict:
    what = sec.watched or "Video"
    part = f" (Bölüm {sec.part})" if sec.parts > 1 else ""
    who = streamer or "Yayıncı"
    tag = re.sub(r"[^\w]", "", who.lower())
    return {
        "title": f"{who} - {what} İzliyor!{part}"[:100],
        "description": f"{who}, {what} izliyor ve tepki veriyor.\n\nİzlenen içerik: {what}\n"
                       f"Yayın: {src_title}\n\n#{tag} #react #kick",
        "tags": [t for t in [who.lower(), what.lower(), "react", "tepki", "kick", "yayın"] if t],
        "thumb_text": what if len(what) <= 22 else "BU NE BÖYLE?!",
    }


def section_meta(src: Source, sec: Section, streamer: str, log: Logger) -> tuple[dict, list[tuple[float, bytes]]]:
    """Başlık/açıklama/kapak yazısı + 1080p örnek kareler."""
    times = [sec.start + sec.duration * f for f in (0.08, 0.22, 0.38, 0.55, 0.72, 0.88)]
    hi_frames = sample(src, times, which="media", width=1280, log=log)
    meta = _fallback_meta(sec, streamer, src.title)
    meta["background_time"] = hi_frames[len(hi_frames) // 2][0] if hi_frames else sec.start + sec.duration / 2
    meta["player_box"] = sec.player_box
    if not (llm.available() and hi_frames):
        return meta, hi_frames
    content: list = [{"type": "text", "text":
                      f"Yayıncı: {streamer or 'bilinmiyor'}\nYayın başlığı: {src.title}\n"
                      f"Bölüm: {fmt_time(sec.start)} - {fmt_time(sec.end)} ({sec.duration / 60:.0f} dk)"
                      + (f", parça {sec.part}/{sec.parts}" if sec.parts > 1 else "")
                      + f"\nEkrandan okunan izlenen içerik: {sec.watched or 'bilinmiyor'} ({sec.platform or '?'})"}]
    for i, (t, jpg) in enumerate(hi_frames):
        content.append({"type": "text", "text": f"Kare {i} ({fmt_time(t)})"})
        content.append(llm.image_block(jpg))
    try:
        data = llm.ask_json(META_SYSTEM, content, META_SCHEMA, effort="medium", max_tokens=4000)
        meta.update({k: data[k] for k in ("title", "description", "tags", "thumb_text")})
        bi = data.get("background_frame")
        if isinstance(bi, int) and 0 <= bi < len(hi_frames):
            meta["background_time"] = hi_frames[bi][0]
        if len(data.get("player_box") or []) == 4:
            meta["player_box"] = data["player_box"]
    except Exception as e:
        log(f"Claude başlık üretemedi ({e}); basit başlık kullanılıyor.")
    meta["title"] = meta["title"].strip()[:100]
    return meta, hi_frames


def reaction_time(src: Source, sec: Section, log: Logger) -> float:
    """Bölümde yayıncının en çok tepki verdiği an (yüz karesi için)."""
    try:
        from .highlights import analyze, reaction_score, WIN
        import numpy as np
        f = analyze(replace(src, start=sec.start, end=sec.end), log=lambda m: None)
        sc = reaction_score(f, 20)
        return f.time(int(np.argmax(sc))) + WIN
    except Exception:
        return sec.start + sec.duration / 2


def make_cover(src: Source, meta: dict, cam: Optional[dict], out_path: str) -> str:
    bg = src.grab_jpeg(meta["background_time"], "media", quality=2)
    if not bg:
        raise RuntimeError("Kapak için kare alınamadı.")
    face = src.grab_jpeg(meta.get("face_time", meta["background_time"]), "media", quality=2) if cam else None
    box = (cam["x"], cam["y"], cam["w"], cam["h"]) if cam else None
    return compose(bg, face, box, meta.get("thumb_text", ""), meta.get("player_box"), out_path)


# ----------------------------------------------------------------------------- dışa aktarma
def export(src: Source, start: float, end: float, out_path: str, log: Logger = default_log) -> str:
    """Bölümü yeniden kodlamadan (orijinal 1080p kalite) mp4 olarak kopyalar."""
    dur = end - start
    log(f"1080p bölüm çekiliyor ({dur / 60:.0f} dk, yeniden kodlama yok)...")
    cmd = ["ffmpeg", "-y", "-v", "error", "-progress", "pipe:1",
           *src.ff_input("media", start, dur), "-map", "0:v:0", "-map", "0:a:0?", "-c", "copy",
           "-bsf:a", "aac_adtstoasc", "-movflags", "+faststart", out_path]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    last = -1
    assert proc.stdout is not None
    for line in proc.stdout:
        if line.startswith("out_time_us="):
            try:
                pct = int(int(line.split("=")[1]) / 1e6 * 100 / dur)
            except ValueError:
                continue
            if pct >= last + 10:
                last = pct
                log(f"Çekiliyor %{min(100, pct)}")
    proc.wait()
    if proc.returncode != 0 or not os.path.isfile(out_path) or os.path.getsize(out_path) < 1000:
        err = (proc.stderr.read() if proc.stderr else "")[-400:]
        log(f"Kopyalama başarısız, yeniden kodlanarak deneniyor... {err}")
        cmd = ["ffmpeg", "-y", "-v", "error", *src.ff_input("media", start, dur),
               "-map", "0:v:0", "-map", "0:a:0?", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
               "-vf", "scale=-2:'min(1080,ih)'", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", out_path]
        r = subprocess.run(cmd, stderr=subprocess.PIPE, text=True)
        if r.returncode != 0:
            raise RuntimeError(f"Bölüm çekilemedi: {r.stderr[-400:]}")
    log(f"Hazır: {os.path.getsize(out_path) / 1e6:.0f} MB")
    return out_path


# ----------------------------------------------------------------------------- ana akış
def _slug(s: str) -> str:
    return re.sub(r"[^\w\-]+", "_", s, flags=re.UNICODE).strip("_")[:60] or "yayin"


def run_longform(cfg: LongConfig, log: Logger = default_log, progress: Optional[Callable[[float], None]] = None,
                 on_section: Optional[Callable[[dict], None]] = None,
                 should_stop: Callable[[], bool] = lambda: False) -> list[dict]:
    prog = progress or (lambda p: None)
    t0 = time.time()
    os.makedirs(cfg.output_dir, exist_ok=True)
    src = resolve(cfg.source, cfg.work_dir, cfg.max_height, cfg.time_range, 30.0, "stream", log)
    streamer = cfg.streamer or src.uploader or ""
    span = src.end - src.start
    log(f"İşlenecek süre: {fmt_time(span)}")
    prog(0.05)

    if cfg.manual.strip():
        sections = manual_sections(cfg.manual, src.start, src.end)
        log(f"Elle verilen {len(sections)} aralık kullanılıyor.")
        step = 20.0
    else:
        if not llm.available():
            raise RuntimeError("Video izleme bölümlerini otomatik bulmak için Claude gerekli: .env dosyasına "
                               "ANTHROPIC_API_KEY yaz. Ya da 'Elle aralıklar' kutusuna 1:02:00-1:25:00 gibi aralık gir.")
        step = cfg.step or max(20.0, span / 1000)
        times = [src.start + step / 2 + i * step for i in range(int(span // step))]
        log(f"Yayından {len(times)} kare alınacak (her {step:.0f} sn'de bir, 480p)...")
        frames = sample(src, times, log=log)
        prog(0.30)
        if should_stop():
            return []
        log(f"Claude {len(frames)} kareyi inceliyor (ne izleniyor, oyun mu, sohbet mi)...")
        labels = classify(frames, streamer, log)
        counts = Counter(v["activity"] for v in labels.values())
        log("Yayın dökümü: " + ", ".join(f"{k} %{100 * v // max(1, len(labels))}" for k, v in counts.most_common()))
        prog(0.55)
        sections = build_sections(labels, step, cfg, src.start, src.end)
        if sections:
            refine(src, sections, step, streamer, log)
        sections = finalize(sections, cfg)
    if not sections:
        log("Video izleme bölümü bulunamadı.")
        return []
    for i, s in enumerate(sections, 1):
        log(f"  Bölüm {i}: {fmt_time(s.start)} - {fmt_time(s.end)} ({s.duration / 60:.0f} dk) {s.watched}")
    prog(0.62)

    # kamera yeri her bölüm için ayrı bulunur (yayıncı kamerayı yayında taşıyabiliyor)
    def section_cam(sec: Section) -> Optional[dict]:
        with ThreadPoolExecutor(max_workers=4) as ex:
            frames = list(ex.map(src.grab_frame, [sec.start + sec.duration * f for f in (0.2, 0.4, 0.6, 0.8)]))
        frames = [f for f in frames if f is not None]
        if not frames:
            return None
        Hh, Ww = frames[0].shape[:2]
        kind, face, box = analyze_scene(frames, log)
        if kind not in ("cam", "fullcam") or face is None:
            return None
        if box is not None:
            r = box
        else:
            r = resolve_cam_rect("auto", Ww, Hh, 0.85, face, cam_zoom=3.0 if kind == "cam" else 2.2)
        return {"x": r.x, "y": r.y, "w": r.w, "h": r.h} if r else None

    run_dir = os.path.join(cfg.output_dir, f"uzun_{_slug(src.name)}_{time.strftime('%Y%m%d_%H%M%S')}")
    os.makedirs(run_dir, exist_ok=True)
    results = []
    for i, s in enumerate(sections, 1):
        if should_stop():
            break
        name = f"bolum_{i:02d}"
        log(f"[{i}/{len(sections)}] Kapak ve başlık hazırlanıyor...")
        meta, _ = section_meta(src, s, streamer, log)
        cam = section_cam(s)
        if cam is None:
            log(f"[{i}/{len(sections)}] Yayıncı kamerası bulunamadı; kapak yüzsüz hazırlanacak.")
        meta["face_time"] = reaction_time(src, s, log) if cam else meta["background_time"]
        cover = os.path.join(run_dir, f"{name}.jpg")
        try:
            make_cover(src, meta, cam, cover)
        except Exception as e:
            log(f"Kapak oluşturulamadı: {e}")
            cover = None
        data = {
            "kind": "long", "name": name, "start": round(s.start, 1), "end": round(s.end, 1),
            "start_hms": fmt_time(s.start), "end_hms": fmt_time(s.end),
            "watched": s.watched, "platform": s.platform, "part": s.part, "parts": s.parts,
            "title": meta["title"], "description": meta["description"], "tags": meta["tags"],
            "thumb_text": meta["thumb_text"], "background_time": meta["background_time"],
            "face_time": meta["face_time"], "player_box": meta.get("player_box") or [], "cam": cam,
            "thumbnail": os.path.abspath(cover) if cover else None,
            "streamer": streamer, "source_title": src.title, "source_url": cfg.source,
        }
        with open(os.path.join(run_dir, f"{name}.json"), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        log(f"[{i}/{len(sections)}] {data['title']}")
        results.append(data)
        if on_section:
            on_section(data)
        prog(0.62 + 0.38 * i / len(sections))
    log(f"Bitti! {len(results)} bölüm hazır ({fmt_time(time.time() - t0)}). Kontrol edip 'YouTube'a yükle'ye bas.")
    prog(1.0)
    return results


def source_for(meta: dict, work_dir: str = "work", log: Logger = default_log) -> Source:
    """Kayıtlı bölüm için kaynağı yeniden çözer (akış adresleri zamanla değişebilir)."""
    return resolve(meta["source_url"], work_dir, 1080, None, 30.0, "stream", log)


def upload_section(meta: dict, work_dir: str, privacy: str = "public", publish_at: Optional[str] = None,
                   keep_file: Optional[str] = None, log: Logger = default_log) -> dict:
    """Bölümü 1080p kopyalar, YouTube'a yükler, kapağı ayarlar, geçici dosyayı siler."""
    from .youtube import upload_video
    src = source_for(meta, work_dir, log)
    os.makedirs(work_dir, exist_ok=True)
    tmp = keep_file or os.path.join(work_dir, f"yukleme_{int(time.time())}.mp4")
    try:
        export(src, meta["start"], meta["end"], tmp, log)
        return upload_video(tmp, meta["title"], meta.get("description", ""), meta.get("tags", []), privacy,
                            publish_at, category_id="24", shorts=False, thumbnail=meta.get("thumbnail"), log=log)
    finally:
        if not keep_file:
            try:
                os.remove(tmp)
                log("Geçici dosya silindi.")
            except OSError:
                pass
