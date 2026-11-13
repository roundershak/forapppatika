from __future__ import annotations

import json
import shutil
import subprocess
from typing import Callable, Optional

Logger = Callable[[str], None]


def default_log(msg: str) -> None:
    print(msg, flush=True)


def require_ffmpeg() -> None:
    for tool in ("ffmpeg", "ffprobe"):
        if shutil.which(tool) is None:
            raise RuntimeError(
                f"'{tool}' bulunamadı. ffmpeg kurup PATH'e ekleyin: https://ffmpeg.org/download.html"
            )


def run(cmd: list[str], cwd: Optional[str] = None) -> None:
    proc = subprocess.run(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                          encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        tail = "\n".join(proc.stderr.strip().splitlines()[-25:])
        raise RuntimeError(f"Komut başarısız ({proc.returncode}): {' '.join(cmd[:4])} ...\n{tail}")


def probe(path: str) -> dict:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", path],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True,
    ).stdout
    data = json.loads(out)
    v = next((s for s in data["streams"] if s.get("codec_type") == "video"), None)
    a = next((s for s in data["streams"] if s.get("codec_type") == "audio"), None)
    if v is None:
        raise RuntimeError(f"Video akışı bulunamadı: {path}")
    duration = float(data["format"].get("duration") or v.get("duration") or 0)
    return {
        "width": int(v["width"]),
        "height": int(v["height"]),
        "duration": duration,
        "has_audio": a is not None,
    }


def parse_time(s: str) -> float:
    """'1:02:03', '62:03', '3723', '3723.5' -> saniye"""
    s = s.strip()
    parts = [float(p) for p in s.split(":")]
    total = 0.0
    for p in parts:
        total = total * 60 + p
    return total


def parse_range(r: Optional[str]) -> Optional[tuple[float, float]]:
    if not r:
        return None
    a, b = r.split("-", 1)
    start, end = parse_time(a), parse_time(b)
    if end <= start:
        raise ValueError(f"Geçersiz zaman aralığı: {r}")
    return start, end


def fmt_time(t: float) -> str:
    t = max(0, int(t))
    return f"{t // 3600:02d}:{(t % 3600) // 60:02d}:{t % 60:02d}"


def parse_rect(s: str) -> Optional[tuple[float, float, float, float]]:
    """'x,y,w,h' -> tuple; değerler <=1 ise oran olarak yorumlanır."""
    try:
        vals = [float(v) for v in s.split(",")]
    except ValueError:
        return None
    if len(vals) != 4:
        return None
    return tuple(vals)  # type: ignore[return-value]
