"""Yayından klip aralıklarını seçer.

highlights modu: ses enerjisini analiz eder; yayıncının bağırdığı, güldüğü, ortamın
coştuğu (yerel ortalamaya göre ani yükselen) anları bulur.
split modu: yayını eşit parçalara böler, neredeyse sessiz parçaları atlar.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass

import numpy as np

from .utils import Logger, default_log

SR = 16000
WIN = 0.5  # saniye


@dataclass
class Segment:
    start: float
    end: float
    score: float = 0.0
    peak: float = 0.0

    @property
    def duration(self) -> float:
        return self.end - self.start


def loudness_curve(path: str, log: Logger = default_log) -> np.ndarray:
    """Her WIN saniyelik pencere için dB cinsinden ses seviyesi (bellek dostu, akış halinde)."""
    log("Ses analizi yapılıyor...")
    cmd = ["ffmpeg", "-v", "error", "-i", path, "-vn", "-ac", "1", "-ar", str(SR), "-f", "s16le", "-"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    win = int(SR * WIN)
    chunk_bytes = win * 2 * 240  # ~2 dakikalık parçalar
    vals: list[np.ndarray] = []
    rest = np.zeros(0, dtype=np.float32)
    assert proc.stdout is not None
    while True:
        buf = proc.stdout.read(chunk_bytes)
        if not buf:
            break
        x = np.frombuffer(buf[: len(buf) // 2 * 2], dtype=np.int16).astype(np.float32) / 32768.0
        x = np.concatenate([rest, x])
        n = len(x) // win
        if n:
            blk = x[: n * win].reshape(n, win)
            vals.append(np.sqrt(np.mean(blk * blk, axis=1) + 1e-10))
        rest = x[n * win:]
    proc.wait()
    if not vals:
        return np.zeros(0)
    rms = np.concatenate(vals)
    return 20 * np.log10(rms + 1e-6)


def _moving(x: np.ndarray, k: int, fn: str = "mean") -> np.ndarray:
    k = max(1, k)
    if fn == "mean":
        pad = np.pad(x, (k // 2, k - 1 - k // 2), mode="edge")
        return np.convolve(pad, np.ones(k) / k, mode="valid")
    # kayan medyan (hızlı yaklaşık: blok medyanı + enterpolasyon)
    step = max(1, k // 8)
    centers = np.arange(0, len(x), step)
    meds = np.array([np.median(x[max(0, c - k // 2): c + k // 2 + 1]) for c in centers])
    return np.interp(np.arange(len(x)), centers, meds)


def find_highlights(path: str, duration: float, clip_len: float, max_clips: int,
                    lead_ratio: float = 0.65, log: Logger = default_log) -> list[Segment]:
    db = loudness_curve(path, log)
    if len(db) < 4:
        return [Segment(0, min(duration, clip_len))]

    db = np.maximum(db, -70)
    smooth = _moving(db, int(2.0 / WIN))                 # 2 sn yumuşatma
    baseline = _moving(db, int(90 / WIN), fn="median")   # 90 sn yerel taban
    excite = smooth - baseline                           # ani yükselme
    loud = smooth

    def z(a):
        s = a.std()
        return (a - a.mean()) / (s if s > 1e-6 else 1.0)

    score = 0.65 * z(excite) + 0.35 * z(loud)
    # konuşma yoğunluğu: pencere içinde sessiz olmayan oran
    active = _moving((db > np.median(db) - 6).astype(float), int(clip_len / WIN))
    score = score + 0.5 * z(active)

    min_gap = int(clip_len / WIN)
    edge = int(min(clip_len * 0.5, duration * 0.05) / WIN)
    order = np.argsort(score)[::-1]
    picked: list[int] = []
    for i in order:
        if i < edge // 2 or i > len(score) - edge // 2:
            continue
        if all(abs(i - p) >= min_gap for p in picked):
            picked.append(int(i))
        if len(picked) >= max_clips:
            break

    segs = []
    for i in picked:
        peak_t = i * WIN
        start = peak_t - clip_len * lead_ratio
        start = min(max(0.0, start), max(0.0, duration - clip_len))
        segs.append(Segment(start, min(duration, start + clip_len), float(score[i]), peak_t))
    log(f"{len(segs)} highlight anı bulundu.")
    return segs


def split_segments(path: str, duration: float, clip_len: float, max_clips: int,
                   log: Logger = default_log) -> list[Segment]:
    db = loudness_curve(path, log)
    segs = []
    t = 0.0
    thr = float(np.percentile(db, 20)) if len(db) else -60
    while t + clip_len * 0.5 < duration and len(segs) < max_clips:
        end = min(duration, t + clip_len)
        a, b = int(t / WIN), int(end / WIN)
        part = db[a:b] if len(db) else np.zeros(0)
        if len(part) and float(np.mean(part > thr)) < 0.25:
            log(f"Sessiz parça atlandı: {t:.0f}s")
        else:
            segs.append(Segment(t, end, float(np.mean(part)) if len(part) else 0.0, t))
        t = end
    log(f"Yayın {len(segs)} parçaya bölündü.")
    return segs
