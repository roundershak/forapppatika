"""1. aşama: tüm yayının sesini hızlıca tarayıp 'tepki' adaylarını bulur.

Her 0.5 sn için şu özellikler çıkarılır:
  - genel ses seviyesi ve yerel ortalamaya göre ani yükselme
  - konuşma bandı (300-3400 Hz) enerjisi -> yayıncının sesi (oyun sesinden ayırmaya yardım eder)
  - 3-8 Hz ritmik genlik dalgalanması -> gülme ("ha-ha-ha"), bağırma, heyecanlı konuşma
  - konuşma yoğunluğu
Ses, paralel ffmpeg süreçleriyle parça parça okunur (uzun yayınlarda hızlı).
"""

from __future__ import annotations

import subprocess
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from .utils import Logger, default_log

SR = 16000
WIN = 0.5                       # özellik penceresi (sn)
ENV_HZ = 50                     # zarf örnekleme (20 ms)
CHUNK = 900.0                   # paralel okuma parça uzunluğu (sn)


@dataclass
class Segment:
    start: float
    end: float
    score: float = 0.0
    peak: float = 0.0
    reason: str = ""
    category: str = ""
    words: list = field(default_factory=list)   # mutlak zamanlı kelimeler (AI aşamasından)

    @property
    def duration(self) -> float:
        return self.end - self.start


@dataclass
class Features:
    t0: float                   # ilk pencerenin mutlak zamanı
    db: np.ndarray
    voice_db: np.ndarray
    rhythm: np.ndarray

    def time(self, i: int) -> float:
        return self.t0 + i * WIN


def _chunk_features(input_args: list[str], n_win: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    cmd = ["ffmpeg", "-v", "error", *input_args, "-vn", "-ac", "1", "-ar", str(SR), "-f", "s16le", "-"]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    x = np.frombuffer(proc.stdout[: len(proc.stdout) // 2 * 2], dtype=np.int16).astype(np.float32) / 32768.0
    win = int(SR * WIN)
    x = np.pad(x, (0, max(0, n_win * win - len(x))))[: n_win * win]
    blk = x.reshape(n_win, win)
    rms = np.sqrt(np.mean(blk * blk, axis=1) + 1e-10)
    spec = np.abs(np.fft.rfft(blk * np.hanning(win), axis=1)) ** 2
    freqs = np.fft.rfftfreq(win, 1 / SR)
    band = (freqs >= 300) & (freqs <= 3400)
    # konuşma bandının toplam enerjiye oranı (dB): konuşma/gülme ~0, bas ağırlıklı patlama/müzik çok negatif
    ratio_db = 10 * np.log10(spec[:, band].sum(axis=1) / (spec[:, 1:].sum(axis=1) + 1e-12) + 1e-6)
    voice_db = 20 * np.log10(rms + 1e-6) + ratio_db
    hop = SR // ENV_HZ
    env = np.sqrt(np.mean(x.reshape(-1, hop) ** 2, axis=1) + 1e-10)
    return 20 * np.log10(rms + 1e-6), voice_db, env


def _rhythm(env: np.ndarray, n_win: int) -> np.ndarray:
    """Her pencere çevresindeki 2 sn'de 3-8 Hz ritmik dalgalanma oranı (gülme/heyecan göstergesi)."""
    L = 2 * ENV_HZ
    step = int(ENV_HZ * WIN)
    e = np.log(env + 1e-4)
    e = np.pad(e, (L // 2, L))
    from numpy.lib.stride_tricks import sliding_window_view
    frames = sliding_window_view(e, L)[::step][:n_win]
    frames = frames - frames.mean(axis=1, keepdims=True)
    p = np.abs(np.fft.rfft(frames * np.hanning(L), axis=1)) ** 2
    f = np.fft.rfftfreq(L, 1 / ENV_HZ)
    num = p[:, (f >= 3) & (f <= 8)].sum(axis=1)
    den = p[:, (f >= 0.5) & (f <= 15)].sum(axis=1) + 1e-9
    out = num / den
    return np.pad(out, (0, max(0, n_win - len(out))))[:n_win]


def analyze(src, log: Logger = default_log, workers: int = 6) -> Features:
    """src: source.Source. [src.start, src.end] aralığının sesini paralel tarar."""
    total = src.end - src.start
    log(f"Ses taranıyor ({total / 60:.0f} dk, {'akıştan' if src.kind == 'stream' else 'dosyadan'})...")
    chunks = []
    t = src.start
    while t < src.end - 1e-6:
        d = min(CHUNK, src.end - t)
        chunks.append((t, d))
        t += d

    done = [0]

    def job(c):
        s, d = c
        n = max(1, int(round(d / WIN)))
        r = _chunk_features(src.ff_input("analysis", s, d), n)
        done[0] += 1
        if len(chunks) > 2:
            log(f"Ses taraması %{int(done[0] * 100 / len(chunks))}")
        return r

    with ThreadPoolExecutor(max_workers=workers) as ex:
        parts = list(ex.map(job, chunks))
    db = np.concatenate([p[0] for p in parts])
    voice = np.concatenate([p[1] for p in parts])
    env = np.concatenate([p[2] for p in parts])
    return Features(src.start, db, voice, _rhythm(env, len(db)))


def _moving(x: np.ndarray, k: int, fn: str = "mean") -> np.ndarray:
    k = max(1, k)
    if fn == "mean":
        pad = np.pad(x, (k // 2, k - 1 - k // 2), mode="edge")
        return np.convolve(pad, np.ones(k) / k, mode="valid")
    step = max(1, k // 8)
    centers = np.arange(0, len(x), step)
    meds = np.array([np.median(x[max(0, c - k // 2): c + k // 2 + 1]) for c in centers])
    return np.interp(np.arange(len(x)), centers, meds)


def _z(a: np.ndarray) -> np.ndarray:
    s = a.std()
    return (a - a.mean()) / (s if s > 1e-6 else 1.0)


def _rolling_max(x: np.ndarray, k: int) -> np.ndarray:
    from numpy.lib.stride_tricks import sliding_window_view
    k = max(1, k)
    pad = np.pad(x, (k // 2, k - 1 - k // 2), mode="edge")
    return sliding_window_view(pad, k).max(axis=1)


def _shift(x: np.ndarray, n: int) -> np.ndarray:
    """x'i n pencere sağa kaydır (t anında t-n değerini görmek için)."""
    if n <= 0:
        return x
    return np.concatenate([np.full(n, x[0]), x[:-n]])


def reaction_score(f: Features, clip_len: float) -> np.ndarray:
    """Bağırma / ses yükselmesi / gerilim odaklı puan.

    - bağırma: yayıncının sesinin (konuşma bandı) yerel tabanın ne kadar üstüne çıktığı (2 sn tepe)
    - ses patlaması: toplam sesin tabanın üstüne ani çıkışı (2 sn tepe)
    - gerilim: son ~15 sn boyunca sesin yüksek kalması (tek bir 'pat' değil, süren heyecan/kavga)
    - tırmanma: son 10 sn'nin önceki 20 sn'ye göre ne kadar yükseldiği (sakinlikten sonra patlama)
    - gülme ritmi küçük bir ek puan
    """
    db = np.maximum(f.db, -70)
    voice = np.maximum(f.voice_db, -70)
    w = lambda sec: max(1, int(sec / WIN))  # noqa: E731
    base_db = _moving(db, w(90), "median")
    base_v = _moving(voice, w(90), "median")
    voiceness = _moving(np.clip((voice - db + 12) / 9, 0, 1), w(2))

    loud_ex = np.maximum(_moving(db, w(1)) - base_db, 0)
    voice_ex = np.maximum(_moving(voice, w(1)) - base_v, 0) * voiceness

    shout = _rolling_max(voice_ex, w(2))
    burst = _rolling_max(loud_ex, w(2))
    tension = _shift(_moving(np.maximum(loud_ex, voice_ex), w(15)), w(5))  # tepenin öncesi + sonrası
    recent = _shift(_moving(db, w(10)), w(5) - w(5) // 2)
    before = _shift(_moving(db, w(20)), w(15))
    rise = np.maximum(recent - before, 0)
    speaking = (voice > np.median(voice) - 3).astype(float) * voiceness
    rhythm = _moving(f.rhythm * speaking, w(2))
    return (0.35 * _z(shout) + 0.25 * _z(burst) + 0.25 * _z(tension) + 0.10 * _z(rise)
            + 0.05 * _z(rhythm))


def pick_peaks(score: np.ndarray, min_gap_s: float, k: int, edge_s: float = 0.0) -> list[int]:
    min_gap = max(1, int(min_gap_s / WIN))
    edge = int(edge_s / WIN)
    picked: list[int] = []
    for i in np.argsort(score)[::-1]:
        if i < edge or i > len(score) - 1 - edge:
            continue
        if all(abs(i - p) >= min_gap for p in picked):
            picked.append(int(i))
            if len(picked) >= k:
                break
    return picked


def find_candidates(f: Features, clip_len: float, k: int, lead_ratio: float, range_start: float,
                    range_end: float, log: Logger = default_log) -> list[Segment]:
    if len(f.db) < 4:
        return [Segment(range_start, min(range_end, range_start + clip_len))]
    score = reaction_score(f, clip_len)
    peaks = pick_peaks(score, clip_len, k, edge_s=min(clip_len * 0.25, (range_end - range_start) * 0.02))
    segs = []
    for i in peaks:
        peak_t = f.time(i)
        start = peak_t - clip_len * lead_ratio
        start = min(max(range_start, start), max(range_start, range_end - clip_len))
        segs.append(Segment(start, min(range_end, start + clip_len), float(score[i]), peak_t,
                            reason=_describe(f, i)))
    log(f"{len(segs)} aday an bulundu.")
    return segs


def _describe(f: Features, i: int) -> str:
    a, b = max(0, i - 4), i + 5
    voiced = float(np.mean(f.voice_db[a:b] - f.db[a:b])) > -6
    bits = []
    if voiced and float(np.max(f.rhythm[a:b])) > np.percentile(f.rhythm, 95):
        bits.append("ritmik ses (gülme/heyecan)")
    if voiced and float(np.max(f.voice_db[a:b])) > np.percentile(f.voice_db, 97):
        bits.append("yüksek ses/bağırma")
    if not voiced and float(np.max(f.db[a:b])) > np.percentile(f.db, 97):
        bits.append("oyun/ortam sesi patlaması")
    return ", ".join(bits) or "ses yükselmesi"


def split_segments(f: Optional[Features], range_start: float, range_end: float, clip_len: float,
                   max_clips: int, log: Logger = default_log) -> list[Segment]:
    segs = []
    t = range_start
    thr = float(np.percentile(f.db, 20)) if f is not None and len(f.db) else -60
    while t + clip_len * 0.5 < range_end and len(segs) < max_clips:
        end = min(range_end, t + clip_len)
        if f is not None and len(f.db):
            a, b = int((t - f.t0) / WIN), int((end - f.t0) / WIN)
            part = f.db[a:b]
            if len(part) and float(np.mean(part > thr)) < 0.25:
                log(f"Sessiz parça atlandı: {t:.0f}s")
                t = end
                continue
        segs.append(Segment(t, end, 0.0, t))
        t = end
    log(f"Yayın {len(segs)} parçaya bölündü.")
    return segs
