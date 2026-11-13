"""Kaynağı çözer: yayını indirmeden, doğrudan Kick'in akış (HLS) adresinden okumayı sağlar.

- analiz girdisi: en düşük kaliteli akış (sadece sesi okunur, çok az veri)
- medya girdisi: en yüksek kaliteli akış (sadece seçilen klip aralıkları çekilir)
Yerel dosya, canlı yayın ya da 'full' modunda dosya diske alınır ve aynı arayüzle kullanılır.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from .downloader import _record_live, _safe_name, fetch, is_url
from .utils import Logger, default_log, parse_range


@dataclass
class Source:
    kind: str                       # "local" | "stream"
    media: str                      # en iyi kalite: dosya yolu ya da HLS adresi
    analysis: str                   # analiz için: dosya yolu ya da düşük kalite HLS adresi
    duration: float                 # toplam süre (sn)
    start: float = 0.0              # işlenecek aralığın başı (mutlak sn)
    end: float = 0.0                # işlenecek aralığın sonu (mutlak sn)
    headers: dict = field(default_factory=dict)
    analysis_headers: dict = field(default_factory=dict)
    preview: str = ""               # kare örnekleme için orta kalite (480p civarı) akış
    preview_headers: dict = field(default_factory=dict)
    uploader: str = ""
    title: str = ""
    name: str = "yayin"
    has_audio: bool = True
    display_offset: float = 0.0     # 'full' + aralık modunda dosya 0'dan başlar; gösterilen zamana eklenir

    def _target(self, which: str) -> str:
        if which == "analysis":
            return self.analysis
        if which == "preview":
            return self.preview or self.media
        return self.media

    def _hdr(self, which: str) -> list[str]:
        h = {"media": self.headers, "analysis": self.analysis_headers,
             "preview": self.preview_headers or self.headers}[which]
        if self.kind != "stream" or not h:
            return []
        return ["-headers", "".join(f"{k}: {v}\r\n" for k, v in h.items())]

    def ff_input(self, which: str = "media", start: Optional[float] = None,
                 dur: Optional[float] = None) -> list[str]:
        """ffmpeg giriş argümanları (-ss/-t/-headers/-i). which: media | analysis"""
        args: list[str] = []
        if self.kind == "stream":
            args += ["-rw_timeout", "30000000"]
        args += self._hdr(which)
        if start is not None:
            args += ["-ss", f"{max(0.0, start):.3f}"]
        if dur is not None:
            args += ["-t", f"{dur:.3f}"]
        args += ["-i", self._target(which)]
        return args

    def grab_jpeg(self, t: float, which: str = "media", width: Optional[int] = None,
                  quality: int = 3) -> Optional[bytes]:
        """t anındaki kareyi JPEG baytı olarak döndürür (width verilirse küçültülür)."""
        vf = ["-vf", f"scale={width}:-2"] if width else []
        cmd = ["ffmpeg", "-v", "error", *self.ff_input(which, t), "-frames:v", "1", *vf,
               "-q:v", str(quality), "-f", "image2pipe", "-vcodec", "mjpeg", "-"]
        for _ in range(2):
            try:
                out = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=90).stdout
            except subprocess.TimeoutExpired:
                continue
            if out:
                return out
        return None

    def grab_frame(self, t: float, which: str = "media") -> Optional[np.ndarray]:
        """t anındaki kareyi (BGR) döndürür."""
        try:
            import cv2
        except ImportError:
            return None
        data = self.grab_jpeg(t, which, quality=2)
        if not data:
            return None
        return cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)


def _probe_duration(target: str, headers: dict) -> float:
    cmd = ["ffprobe", "-v", "error"]
    if headers:
        cmd += ["-headers", "".join(f"{k}: {v}\r\n" for k, v in headers.items())]
    cmd += ["-show_entries", "format=duration:stream=codec_type", "-of", "json", target]
    import json
    out = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, timeout=120).stdout
    data = json.loads(out or "{}")
    return float((data.get("format") or {}).get("duration") or 0)


def _local(path: str, rng, uploader="", title="") -> Source:
    import json
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type",
                          "-of", "json", path], stdout=subprocess.PIPE, text=True).stdout
    data = json.loads(out or "{}")
    dur = float((data.get("format") or {}).get("duration") or 0)
    has_audio = any(s.get("codec_type") == "audio" for s in data.get("streams", []))
    start, end = (rng if rng else (0.0, dur))
    title = title or os.path.splitext(os.path.basename(path))[0]
    return Source("local", path, path, dur, max(0.0, start), min(dur, end) if dur else end,
                  uploader=uploader, title=title, name=_safe_name(title), has_audio=has_audio)


def _pick_preview_format(formats: list[dict], target: int = 480) -> Optional[dict]:
    """Kare örnekleme için ~480p video akışı."""
    vids = [f for f in formats if f.get("url") and f.get("vcodec") != "none" and f.get("height")]
    if not vids:
        return None
    return min(vids, key=lambda f: (abs(f["height"] - target), f.get("tbr") or 0))


def _pick_analysis_format(formats: list[dict]) -> Optional[dict]:
    """Sesi olan en düşük kaliteli format (varsa sadece-ses)."""
    usable = [f for f in formats if f.get("url") and f.get("acodec") != "none"
              and (f.get("protocol") or "").startswith(("m3u8", "http"))]
    if not usable:
        return None
    audio_only = [f for f in usable if f.get("vcodec") == "none"]
    pool = audio_only or usable
    return min(pool, key=lambda f: (f.get("height") or 0, f.get("tbr") or 1e9))


def resolve(source: str, work_dir: str, max_height: int = 1080, time_range: Optional[str] = None,
            live_minutes: float = 30.0, download: str = "stream", log: Logger = default_log) -> Source:
    rng = parse_range(time_range)
    if not is_url(source):
        if not os.path.isfile(source):
            raise FileNotFoundError(f"Dosya bulunamadı: {source}")
        return _local(os.path.abspath(source), rng)

    if download == "full":
        path, offset, meta = fetch(source, work_dir, max_height, time_range, live_minutes, log)
        # aralıklı indirmede dosya zaten kesik; zamanlar dosya içinde 0'dan başlar
        src = _local(path, None, meta.get("uploader", ""), meta.get("title", ""))
        src.display_offset = offset
        return src

    import yt_dlp
    fmt = f"bv*[height<={max_height}]+ba/b[height<={max_height}]/bv*+ba/b"
    log(f"Bağlantı çözümleniyor: {source}")
    with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True, "format": fmt}) as ydl:
        info = ydl.extract_info(source, download=False)
    uploader = info.get("uploader") or info.get("channel") or ""
    title = info.get("title") or info.get("id") or "yayin"
    name = _safe_name(f"{uploader}_{title}" if uploader else title)
    log(f"Bulundu: {uploader} - {title}")

    if info.get("is_live"):
        os.makedirs(work_dir, exist_ok=True)
        path = _record_live(info, work_dir, name, live_minutes, log)
        return _local(path, None, uploader, title)

    req = info.get("requested_formats")
    if req and len(req) > 1:
        # video ve ses ayrı akışlarsa doğrudan okuma karmaşıklaşır -> dosyaya indir
        log("Akış ayrık ses/video; indirme moduna geçiliyor.")
        return resolve(source, work_dir, max_height, time_range, live_minutes, "full", log)
    best = (req[0] if req else info)
    media_url = best.get("url")
    ana = _pick_analysis_format(info.get("formats") or []) or best
    if not media_url:
        log("Akış adresi alınamadı; indirme moduna geçiliyor.")
        return resolve(source, work_dir, max_height, time_range, live_minutes, "full", log)

    headers = best.get("http_headers") or info.get("http_headers") or {}
    a_headers = ana.get("http_headers") or headers
    dur = float(info.get("duration") or 0) or _probe_duration(media_url, headers)
    if dur <= 0:
        raise RuntimeError("Yayın süresi alınamadı.")
    start, end = rng if rng else (0.0, dur)
    log(f"İndirmeden işlenecek: analiz {ana.get('height') or 'ses'}p akıştan, klipler "
        f"{best.get('height') or '?'}p akıştan sadece gereken kısımlar çekilecek.")
    prev = _pick_preview_format(info.get("formats") or []) or best
    return Source("stream", media_url, ana["url"], dur, max(0.0, start), min(dur, end),
                  headers=headers, analysis_headers=a_headers, uploader=uploader, title=title, name=name,
                  preview=prev["url"], preview_headers=prev.get("http_headers") or headers)
