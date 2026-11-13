"""Uçtan uca akış: indir -> analiz et -> kamera bul -> altyazı -> render."""

from __future__ import annotations

import json
import os
import re
import time
from typing import Callable, Optional

from .config import ClipConfig
from .downloader import fetch
from .highlights import Segment, find_highlights, split_segments
from .layout import detect_face_region, resolve_cam_rect, resolve_screen_rect
from .render import make_thumbnail, render_clip
from .sfx import get_bell
from .subtitles import Transcriber, build_ass
from .titles import generate_title
from .utils import Logger, default_log, fmt_time, probe, require_ffmpeg, run

ProgressFn = Callable[[float], None]
ClipDoneFn = Callable[[dict], None]

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _slug(s: str) -> str:
    return re.sub(r"[^\w\-]+", "_", s, flags=re.UNICODE).strip("_")[:60] or "klip"


def run_pipeline(cfg: ClipConfig, log: Logger = default_log, progress: Optional[ProgressFn] = None,
                 on_clip: Optional[ClipDoneFn] = None, should_stop: Callable[[], bool] = lambda: False) -> list[dict]:
    require_ffmpeg()
    prog = progress or (lambda p: None)
    os.makedirs(cfg.work_dir, exist_ok=True)
    os.makedirs(cfg.output_dir, exist_ok=True)

    # 1) Kaynak
    prog(0.02)
    src, offset, src_meta = fetch(cfg.source, cfg.work_dir, cfg.max_height, cfg.time_range, cfg.live_minutes, log)
    info = probe(src)
    W, H, dur = info["width"], info["height"], info["duration"]
    log(f"Video: {W}x{H}, süre {fmt_time(dur)}")
    streamer = cfg.streamer or src_meta.get("uploader") or ""
    prog(0.25)

    # 2) Klip aralıkları
    clip_len = min(cfg.clip_length, dur)
    if not info["has_audio"]:
        log("Videoda ses yok; sırayla bölme moduna geçiliyor.")
        segs = [Segment(t, min(dur, t + clip_len)) for t in
                [i * clip_len for i in range(int(dur // clip_len) or 1)]][: cfg.max_clips]
    elif cfg.mode == "split":
        segs = split_segments(src, dur, clip_len, cfg.max_clips, log)
    else:
        segs = find_highlights(src, dur, clip_len, cfg.max_clips, cfg.lead_ratio, log)
    if not segs:
        raise RuntimeError("Hiç klip aralığı bulunamadı.")
    prog(0.32)

    # 3) Yerleşim
    top_h = round(cfg.height * cfg.cam_ratio / 2) * 2
    top_aspect = cfg.width / top_h
    bot_aspect = cfg.width / (cfg.height - top_h)
    face = None
    if cfg.cam.strip().lower() == "auto":
        log("Yayıncı kamerası aranıyor...")
        face = detect_face_region(src, dur, log=log)
        if face is None:
            log("Kamera bulunamadı -> tam ekran (bulanık arka planlı) düzen kullanılacak. "
                "Elle ayarlamak için kamera konumunu seçin (ör. top-left / x,y,w,h).")
    cam = resolve_cam_rect(cfg.cam, W, H, top_aspect, face, cfg.cam_size, cfg.cam_zoom)
    screen_mode, screen = resolve_screen_rect(cfg.screen, W, H, bot_aspect if cam else cfg.width / cfg.height,
                                              cfg.screen_zoom, cam)
    if cam:
        log(f"Kamera alanı: x={cam.x} y={cam.y} w={cam.w} h={cam.h}")
    log(f"Ekran alanı ({screen_mode}): x={screen.x} y={screen.y} w={screen.w} h={screen.h}")
    sub_pos = cfg.sub_position if cam else max(cfg.sub_position, 0.70)

    bell = get_bell(cfg.bell_file, cfg.work_dir) if cfg.intro else None
    transcriber = Transcriber(cfg.whisper_model, cfg.device, cfg.language, log) if cfg.subtitles else None
    fonts_dir = os.path.join(ROOT, "assets", "fonts")

    base = _slug(os.path.splitext(os.path.basename(src))[0])
    run_dir = os.path.join(cfg.output_dir, f"{base}_{time.strftime('%Y%m%d_%H%M%S')}")
    tmp_dir = os.path.join(run_dir, "_tmp")
    os.makedirs(tmp_dir, exist_ok=True)

    results: list[dict] = []
    n = len(segs)
    for idx, seg in enumerate(segs, 1):
        if should_stop():
            log("Durduruldu.")
            break
        name = f"klip_{idx:02d}"
        log(f"[{idx}/{n}] {name}: {fmt_time(seg.start + offset)} - {fmt_time(seg.end + offset)}")
        out_mp4 = os.path.join(run_dir, f"{name}.mp4")
        ass_path = None
        text = ""
        if transcriber and info["has_audio"]:
            wav = os.path.join(tmp_dir, f"{name}.wav")
            run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{seg.start:.3f}", "-t", f"{seg.duration:.3f}",
                 "-i", src, "-vn", "-ac", "1", "-ar", "16000", wav])
            try:
                words = transcriber.words(wav)
            except Exception as e:  # altyazı başarısız olsa da klip üretilsin
                log(f"Altyazı oluşturulamadı: {e}")
                words = []
            text = " ".join(w.text for w in words)
            if words:
                ass_path = build_ass(words, os.path.join(tmp_dir, f"{name}.ass"), cfg.width, cfg.height,
                                     cfg.font, cfg.font_size, cfg.words_per_line, cfg.uppercase,
                                     cfg.highlight_color, sub_pos)
            else:
                log("Konuşma bulunamadı, altyazısız devam.")

        log(f"[{idx}/{n}] Render ediliyor...")
        render_clip(cfg, src, seg.start, seg.duration, out_mp4, cam, screen_mode, screen,
                    info["has_audio"], bell, ass_path, fonts_dir)
        thumb = os.path.join(run_dir, f"{name}.jpg")
        try:
            make_thumbnail(out_mp4, thumb, min(seg.duration / 2, cfg.intro_hold + 1.0))
        except Exception:
            thumb = None

        meta = {
            "name": name,
            "file": os.path.abspath(out_mp4),
            "thumbnail": os.path.abspath(thumb) if thumb else None,
            "start": round(seg.start + offset, 2),
            "end": round(seg.end + offset, 2),
            "start_hms": fmt_time(seg.start + offset),
            "score": round(seg.score, 3),
            "transcript": text,
            "streamer": streamer,
            "source_title": src_meta.get("title", ""),
        }
        if cfg.titles:
            meta.update(generate_title(text, streamer, src_meta.get("title", ""), log))
            log(f"[{idx}/{n}] Başlık: {meta['title']}")
        with open(os.path.join(run_dir, f"{name}.json"), "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
        results.append(meta)
        if on_clip:
            on_clip(meta)
        prog(0.35 + 0.65 * idx / n)

    with open(os.path.join(run_dir, "klipler.json"), "w", encoding="utf-8") as f:
        json.dump({"source": cfg.source, "config": cfg.to_dict(), "clips": results}, f, ensure_ascii=False, indent=2)
    for fn in os.listdir(tmp_dir):
        try:
            os.remove(os.path.join(tmp_dir, fn))
        except OSError:
            pass
    try:
        os.rmdir(tmp_dir)
    except OSError:
        pass
    log(f"Bitti! {len(results)} klip -> {os.path.abspath(run_dir)}")
    prog(1.0)
    return results
