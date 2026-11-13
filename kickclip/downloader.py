"""Kick (canlı yayın / VOD / klip) indirme - yt-dlp ile."""

from __future__ import annotations

import os
import re
import subprocess
from typing import Optional

from .utils import Logger, default_log, parse_range


def is_url(s: str) -> bool:
    return bool(re.match(r"^https?://", s.strip(), re.I))


def _safe_name(s: str) -> str:
    s = re.sub(r"[^\w\-]+", "_", s, flags=re.UNICODE).strip("_")
    return s[:80] or "yayin"


def fetch(source: str, work_dir: str, max_height: int = 1080, time_range: Optional[str] = None,
          live_minutes: float = 30.0, log: Logger = default_log) -> tuple[str, float]:
    """Kaynağı yerel bir video dosyasına dönüştürür.

    Dönüş: (dosya_yolu, zaman_ofseti). Ofset, indirilen dosyanın orijinal yayındaki
    başlangıç saniyesidir (aralıklı indirmede klip zaman damgalarını doğru göstermek için).
    """
    rng = parse_range(time_range)
    if not is_url(source):
        if not os.path.isfile(source):
            raise FileNotFoundError(f"Dosya bulunamadı: {source}")
        return os.path.abspath(source), 0.0

    import yt_dlp

    os.makedirs(work_dir, exist_ok=True)
    fmt = (f"bv*[height<={max_height}]+ba/b[height<={max_height}]/bv*+ba/b")
    base_opts = {"quiet": True, "no_warnings": True, "noprogress": True}

    log(f"Bağlantı çözümleniyor: {source}")
    with yt_dlp.YoutubeDL({**base_opts, "format": fmt}) as ydl:
        info = ydl.extract_info(source, download=False)

    title = info.get("title") or info.get("id") or "yayin"
    uploader = info.get("uploader") or info.get("channel") or ""
    name = _safe_name(f"{uploader}_{title}" if uploader else title)
    log(f"Bulundu: {uploader} - {title}")

    if info.get("is_live"):
        return _record_live(info, work_dir, name, live_minutes, log), 0.0

    out_path = os.path.join(work_dir, f"{name}{'_' + time_range.replace(':', '') if rng else ''}.mp4")
    if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
        log(f"Önceden indirilmiş dosya kullanılıyor: {out_path}")
        return out_path, (rng[0] if rng else 0.0)

    last = {"pct": -10}

    def hook(d):
        if d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            if total:
                pct = int(d.get("downloaded_bytes", 0) * 100 / total)
                if pct >= last["pct"] + 10:
                    last["pct"] = pct
                    log(f"İndiriliyor... %{pct}")
            elif d.get("fragment_index") and d.get("fragment_count"):
                pct = int(d["fragment_index"] * 100 / d["fragment_count"])
                if pct >= last["pct"] + 10:
                    last["pct"] = pct
                    log(f"İndiriliyor... %{pct}")
        elif d.get("status") == "finished":
            log("İndirme tamamlandı, birleştiriliyor...")

    opts = {
        **base_opts,
        "format": fmt,
        "outtmpl": out_path[:-4] + ".%(ext)s",
        "merge_output_format": "mp4",
        "progress_hooks": [hook],
        "concurrent_fragment_downloads": 8,
        "retries": 10,
        "fragment_retries": 10,
    }
    if rng:
        from yt_dlp.utils import download_range_func
        opts["download_ranges"] = download_range_func(None, [rng])
        opts["force_keyframes_at_cuts"] = True
        log(f"Sadece {time_range} aralığı indirilecek")

    log("İndirme başladı (uzun yayınlarda biraz sürebilir)...")
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([source])

    if not os.path.exists(out_path):
        # yt-dlp farklı uzantı ile kaydetmiş olabilir
        stem = os.path.basename(out_path[:-4])
        cands = [f for f in os.listdir(work_dir) if f.startswith(stem) and not f.endswith(".part")]
        if not cands:
            raise RuntimeError("İndirilen dosya bulunamadı.")
        out_path = os.path.join(work_dir, cands[0])
    return out_path, (rng[0] if rng else 0.0)


def _record_live(info: dict, work_dir: str, name: str, minutes: float, log: Logger) -> str:
    url = info.get("url")
    if not url and info.get("requested_formats"):
        url = info["requested_formats"][0]["url"]
    if not url:
        raise RuntimeError("Canlı yayın akış adresi alınamadı.")
    out = os.path.join(work_dir, f"{name}_canli.mp4")
    headers = "".join(f"{k}: {v}\r\n" for k, v in (info.get("http_headers") or {}).items())
    log(f"Canlı yayın kaydediliyor: {minutes:g} dakika...")
    cmd = ["ffmpeg", "-y", "-loglevel", "error"]
    if headers:
        cmd += ["-headers", headers]
    cmd += ["-i", url, "-t", str(minutes * 60), "-c", "copy", "-bsf:a", "aac_adtstoasc", out]
    proc = subprocess.run(cmd, stderr=subprocess.PIPE, text=True)
    if proc.returncode != 0 and not os.path.exists(out):
        raise RuntimeError(f"Canlı kayıt başarısız: {proc.stderr[-800:]}")
    log("Canlı kayıt tamamlandı.")
    return out
