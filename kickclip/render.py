"""ffmpeg ile 9:16 klibi oluşturur: üstte kamera, altta ekran, altyazı, zil + blur girişi."""

from __future__ import annotations

import os
from typing import Optional

from .config import ClipConfig
from .layout import Rect
from .utils import run


def _even(v: float) -> int:
    return int(round(v / 2)) * 2


def _crop(r: Rect) -> str:
    return f"crop={r.w}:{r.h}:{r.x}:{r.y}"


def _fill(w: int, h: int) -> str:
    return f"scale={w}:{h}:force_original_aspect_ratio=increase:flags=lanczos,crop={w}:{h},setsar=1"


def _fit_with_blur_bg(src: str, w: int, h: int, out: str, tag: str) -> str:
    """Kaynağı (w,h) kutusuna tamamen sığdırır, boşlukları bulanık kopyasıyla doldurur."""
    return (
        f"[{src}]split=2[{tag}a][{tag}b];"
        f"[{tag}a]{_fill(w, h)},gblur=sigma=28,eq=brightness=-0.12:saturation=1.2[{tag}bg];"
        f"[{tag}b]scale={w}:{h}:force_original_aspect_ratio=decrease:flags=lanczos,setsar=1[{tag}fg];"
        f"[{tag}bg][{tag}fg]overlay=(W-w)/2:(H-h)/2[{out}]"
    )


def build_filtergraph(cfg: ClipConfig, cam: Optional[Rect], screen_mode: str, screen: Rect,
                      has_audio: bool, bell: Optional[str], ass_file: Optional[str],
                      fonts_dir: Optional[str]) -> tuple[str, str, str]:
    W, H = _even(cfg.width), _even(cfg.height)
    parts: list[str] = []
    parts.append(f"[0:v]fps={cfg.fps},setpts=PTS-STARTPTS[src]")

    if cam is not None:
        top_h = _even(H * cfg.cam_ratio)
        bot_h = H - top_h
        parts.append("[src]split=2[camsrc][scrsrc]")
        parts.append(f"[camsrc]{_crop(cam)},{_fill(W, top_h)}[top]")
        if screen_mode == "fit":
            parts.append(f"[scrsrc]{_crop(screen)}[scrc]")
            parts.append(_fit_with_blur_bg("scrc", W, bot_h, "bot", "f"))
        else:
            parts.append(f"[scrsrc]{_crop(screen)},{_fill(W, bot_h)}[bot]")
        parts.append(f"[top][bot]vstack=inputs=2,"
                     f"drawbox=x=0:y={top_h - 3}:w={W}:h=6:color=black@0.85:t=fill[base]")
    else:
        # kamera yok: tüm ekranı ortala, arka planı bulanık doldur
        if screen_mode == "custom":
            parts.append(f"[src]{_crop(screen)},{_fill(W, H)}[base]")
        else:
            parts.append(_fit_with_blur_bg("src", W, H, "base", "n"))

    last = "base"
    if cfg.intro and cfg.intro_hold + cfg.intro_fade > 0:
        parts.append(f"[{last}]split=2[sharp][toblur]")
        parts.append(
            f"[toblur]gblur=sigma={cfg.blur_strength:g},format=yuva420p,"
            f"fade=t=out:st={cfg.intro_hold:g}:d={max(cfg.intro_fade, 0.04):g}:alpha=1[blurred]"
        )
        parts.append("[sharp][blurred]overlay=shortest=1:format=auto[intro]")
        last = "intro"

    if ass_file:
        opt = f"ass={ass_file}"
        if fonts_dir:
            opt += f":fontsdir={fonts_dir}"
        parts.append(f"[{last}]{opt}[subbed]")
        last = "subbed"
    parts.append(f"[{last}]format=yuv420p[vout]")

    # --- ses ---
    hold = cfg.intro_hold if cfg.intro else 0.0
    if has_audio:
        duck = f",volume='if(lt(t,{hold:g}),0.35,1)':eval=frame" if (cfg.intro and bell) else ""
        parts.append(f"[0:a]asetpts=PTS-STARTPTS,aresample=48000,aformat=channel_layouts=stereo{duck}[a0]")
    else:
        parts.append("anullsrc=r=48000:cl=stereo[a0]")
    if cfg.intro and bell:
        delay = int(max(0.0, hold - 0.03) * 1000)
        parts.append(f"[1:a]aresample=48000,aformat=channel_layouts=stereo,volume={cfg.bell_volume:g},"
                     f"adelay={delay}:all=1[bell]")
        parts.append("[a0][bell]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.97[aout]")
    else:
        parts.append("[a0]anull[aout]")
    return ";\n".join(parts), "[vout]", "[aout]"


def render_clip(cfg: ClipConfig, src: str, start: float, duration: float, out_path: str,
                cam: Optional[Rect], screen_mode: str, screen: Rect, has_audio: bool,
                bell: Optional[str], ass_path: Optional[str], fonts_dir: Optional[str]) -> None:
    clip_dir = os.path.dirname(os.path.abspath(ass_path or out_path))
    # Windows'ta 'C:' gibi yollar filtre sözdizimini bozar; göreli yol kullanıyoruz
    rel = lambda p: os.path.relpath(p, clip_dir).replace("\\", "/") if p else None  # noqa: E731
    ass_rel = rel(ass_path) if ass_path else None
    fonts_rel = None
    if fonts_dir and os.path.isdir(fonts_dir):
        try:
            fonts_rel = rel(os.path.abspath(fonts_dir))
        except ValueError:  # farklı sürücü
            fonts_rel = None

    graph, vlabel, alabel = build_filtergraph(cfg, cam, screen_mode, screen, has_audio,
                                              bell, ass_rel, fonts_rel)
    graph_file = os.path.join(clip_dir, os.path.splitext(os.path.basename(out_path))[0] + "_filter.txt")
    with open(graph_file, "w", encoding="utf-8") as f:
        f.write(graph)

    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
           "-ss", f"{start:.3f}", "-t", f"{duration:.3f}", "-i", os.path.abspath(src)]
    if cfg.intro and bell:
        cmd += ["-i", os.path.abspath(bell)]
    cmd += ["-filter_complex_script", os.path.basename(graph_file),
            "-map", vlabel, "-map", alabel,
            "-c:v", "libx264", "-preset", cfg.preset, "-crf", str(cfg.crf),
            "-profile:v", "high", "-pix_fmt", "yuv420p", "-r", str(cfg.fps),
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
            "-t", f"{duration:.3f}", "-movflags", "+faststart",
            os.path.abspath(out_path)]
    run(cmd, cwd=clip_dir)
    try:
        os.remove(graph_file)
    except OSError:
        pass


def make_thumbnail(video: str, out_jpg: str, at: float = 1.5) -> None:
    run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{at:.2f}", "-i", video,
         "-frames:v", "1", "-q:v", "3", "-vf", "scale=360:-2", out_jpg])
