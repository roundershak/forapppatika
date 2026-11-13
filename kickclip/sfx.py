"""Klip başı zil sesi: kullanıcı dosyası yoksa sentetik bir 'ding' üretir."""

from __future__ import annotations

import os
import wave

import numpy as np

SR = 48000


def synth_bell(path: str, freq: float = 1318.5, duration: float = 1.6) -> str:
    t = np.arange(int(SR * duration)) / SR
    # gerçek çan seslerindeki uyumsuz (inharmonik) kısmi frekanslar
    partials = [
        (0.50, 0.35, 1.6),
        (1.00, 1.00, 2.2),
        (1.19, 0.45, 3.0),
        (1.56, 0.40, 3.8),
        (2.00, 0.55, 4.5),
        (2.51, 0.25, 6.0),
        (2.66, 0.20, 6.5),
        (3.01, 0.18, 7.5),
        (4.10, 0.10, 10.0),
    ]
    y = np.zeros_like(t)
    for ratio, amp, decay in partials:
        y += amp * np.exp(-decay * t) * np.sin(2 * np.pi * freq * ratio * t + ratio)
    # vuruş anı (strike) - kısa parlak gürültü
    rng = np.random.default_rng(7)
    y += 0.25 * rng.standard_normal(len(t)) * np.exp(-t * 90)
    attack = np.minimum(1.0, t / 0.002)
    y *= attack
    y /= np.max(np.abs(y)) + 1e-9
    y *= 0.9
    stereo = np.stack([y, y], axis=1)
    pcm = (stereo * 32767).astype(np.int16)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    return path


def get_bell(user_file: str | None, work_dir: str) -> str:
    if user_file:
        if not os.path.isfile(user_file):
            raise FileNotFoundError(f"Zil sesi dosyası bulunamadı: {user_file}")
        return os.path.abspath(user_file)
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for name in ("bell.wav", "bell.mp3", "zil.wav", "zil.mp3"):
        p = os.path.join(here, "assets", name)
        if os.path.isfile(p):
            return p
    p = os.path.join(work_dir, "bell_synth.wav")
    if not os.path.isfile(p):
        synth_bell(p)
    return os.path.abspath(p)
