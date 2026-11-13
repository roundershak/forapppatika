"""Uçtan uca akış.

1) Kaynak çözülür (Kick linkiyse indirilmez; akış adresi alınır)
2) Tüm yayının sesi paralel taranır -> tepki adayları (bağırma, gülme ritmi, ani heyecan)
3) Adaylar Whisper ile yazıya dökülür, Claude en iyilerini seçip sınırlarını belirler
4) Kamera yeri bulunur, sadece seçilen aralıklar yüksek kalitede çekilip 9:16 render edilir
"""

from __future__ import annotations

import json
import os
import re
import time
from typing import Callable, Optional

from .ai import rank
from .config import ClipConfig
from .highlights import Segment, analyze, find_candidates, split_segments
from .layout import detect_face_region, resolve_cam_rect, resolve_screen_rect
from .render import make_thumbnail, render_clip
from .sfx import get_bell
from .source import resolve
from .subtitles import Transcriber, build_ass
from .titles import generate_title
from .utils import Logger, default_log, fmt_time, require_ffmpeg, run

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
    t_begin = time.time()

    # 1) Kaynak
    prog(0.02)
    src = resolve(cfg.source, cfg.work_dir, cfg.max_height, cfg.time_range, cfg.live_minutes, cfg.download, log)
    span = src.end - src.start
    log(f"İşlenecek süre: {fmt_time(span)}")
    streamer = cfg.streamer or src.uploader or ""
    disp = lambda t: t + src.display_offset  # noqa: E731
    prog(0.08)

    # 2) Ses taraması + aday anlar
    clip_len = min(cfg.clip_length, span)
    t0 = time.time()
    feats = analyze(src, log) if src.has_audio else None
    if feats is not None:
        log(f"Ses taraması {time.time() - t0:.0f} sn sürdü.")
    prog(0.25)

    transcriber = Transcriber(cfg.whisper_model, cfg.device, cfg.language, log) \
        if (cfg.subtitles or cfg.ai) and src.has_audio else None

    if feats is None:
        log("Videoda ses yok; sırayla bölme moduna geçiliyor.")
        segs = split_segments(None, src.start, src.end, clip_len, cfg.max_clips, log)
    elif cfg.mode == "split":
        segs = split_segments(feats, src.start, src.end, clip_len, cfg.max_clips, log)
    else:
        k = cfg.ai_candidates or max(cfg.max_clips + 3, int(cfg.max_clips * 2.5))
        k = k if cfg.ai else cfg.max_clips
        cands = find_candidates(feats, clip_len, k, cfg.lead_ratio, src.start, src.end, log)
        if cfg.ai:
            window = cfg.ai_window or max(45.0, clip_len * 2)
            t0 = time.time()
            segs = rank(src, cands, cfg.max_clips, clip_len, cfg.lead_ratio,
                        transcriber if cfg.ai else None, window, cfg.flex_length, log, should_stop)
            log(f"Yapay zekâ seçimi {time.time() - t0:.0f} sn sürdü.")
        else:
            segs = cands[: cfg.max_clips]
    if not segs:
        raise RuntimeError("Hiç klip aralığı bulunamadı.")
    for i, s in enumerate(segs, 1):
        log(f"  #{i} {fmt_time(disp(s.start))} ({s.duration:.0f} sn) {s.category + ': ' if s.category else ''}{s.reason}")
    prog(0.45)

    # 3) Yerleşim: seçilen kliplerden kare örnekleyip kamerayı bul
    log("Kareler örnekleniyor...")
    times = []
    for s in segs[:8]:
        times += [s.start + s.duration * f for f in (0.25, 0.6)]
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=6) as ex:
        frames = [f for f in ex.map(src.grab_frame, times) if f is not None]
    if not frames:
        raise RuntimeError("Videodan kare alınamadı.")
    H, W = frames[0].shape[:2]
    log(f"Video çözünürlüğü: {W}x{H}")
    top_h = round(cfg.height * cfg.cam_ratio / 2) * 2
    top_aspect = cfg.width / top_h
    bot_aspect = cfg.width / (cfg.height - top_h)
    face = None
    if cfg.cam.strip().lower() == "auto":
        log("Yayıncı kamerası aranıyor...")
        face = detect_face_region(frames, log=log)
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
    ow, oh = cfg.out_size()
    log(f"Çıktı: {ow}x{oh}, {cfg.fps} fps")

    bell = get_bell(cfg.bell_file, cfg.work_dir) if cfg.intro else None
    fonts_dir = os.path.join(ROOT, "assets", "fonts")

    run_dir = os.path.join(cfg.output_dir, f"{_slug(src.name)}_{time.strftime('%Y%m%d_%H%M%S')}")
    tmp_dir = os.path.join(run_dir, "_tmp")
    os.makedirs(tmp_dir, exist_ok=True)

    # 4) Klipler
    results: list[dict] = []
    n = len(segs)
    for idx, seg in enumerate(segs, 1):
        if should_stop():
            log("Durduruldu.")
            break
        name = f"klip_{idx:02d}"
        log(f"[{idx}/{n}] {name}: {fmt_time(disp(seg.start))} - {fmt_time(disp(seg.end))}")
        out_mp4 = os.path.join(run_dir, f"{name}.mp4")
        words = [w for w in seg.words if w.end > seg.start and w.start < seg.end]
        if cfg.subtitles and transcriber and not seg.words:
            wav = os.path.join(tmp_dir, f"{name}.wav")
            try:
                run(["ffmpeg", "-y", "-loglevel", "error", *src.ff_input("analysis", seg.start, seg.duration),
                     "-vn", "-ac", "1", "-ar", "16000", wav])
                from .subtitles import Word
                words = [Word(w.start + seg.start, w.end + seg.start, w.text) for w in transcriber.words(wav)]
            except Exception as e:
                log(f"Altyazı oluşturulamadı: {e}")
                words = []
        text = " ".join(w.text for w in words)
        ass_path = None
        if cfg.subtitles and words:
            from .subtitles import Word
            rel = [Word(w.start - seg.start, w.end - seg.start, w.text) for w in words]
            ow, oh = cfg.out_size()
            ass_path = build_ass(rel, os.path.join(tmp_dir, f"{name}.ass"), ow, oh,
                                 cfg.font, round(cfg.font_size * ow / cfg.width), cfg.words_per_line, cfg.uppercase,
                                 cfg.highlight_color, sub_pos)

        log(f"[{idx}/{n}] Render ediliyor (sadece bu {seg.duration:.0f} sn çekiliyor)...")
        render_clip(cfg, src.ff_input("media", seg.start, seg.duration), seg.duration, out_mp4, cam,
                    screen_mode, screen, src.has_audio, bell, ass_path, fonts_dir)
        thumb = os.path.join(run_dir, f"{name}.jpg")
        try:
            make_thumbnail(out_mp4, thumb, min(seg.duration / 2, cfg.intro_hold + 1.0))
        except Exception:
            thumb = None

        meta = {
            "name": name,
            "file": os.path.abspath(out_mp4),
            "thumbnail": os.path.abspath(thumb) if thumb else None,
            "start": round(disp(seg.start), 2),
            "end": round(disp(seg.end), 2),
            "start_hms": fmt_time(disp(seg.start)),
            "score": round(seg.score, 3),
            "category": seg.category,
            "reason": seg.reason,
            "transcript": text,
            "streamer": streamer,
            "source_title": src.title,
            "source_url": cfg.source,
        }
        if cfg.titles:
            meta.update(generate_title(text, streamer, src.title, log))
            log(f"[{idx}/{n}] Başlık: {meta['title']}")
        with open(os.path.join(run_dir, f"{name}.json"), "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
        results.append(meta)
        if on_clip:
            on_clip(meta)
        prog(0.45 + 0.55 * idx / n)

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
    log(f"Bitti! {len(results)} klip, toplam {fmt_time(time.time() - t_begin)} -> {os.path.abspath(run_dir)}")
    prog(1.0)
    return results
