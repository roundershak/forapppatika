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


def synth_ding(path: str, freq: float = 2637.0, duration: float = 0.30) -> str:
    """Kısa, parlak 'çın!' sesi: anında vuruş, metalik tını, ~0.3 sn sonra tık diye kesilir."""
    t = np.arange(int(SR * duration)) / SR
    partials = [  # (frekans oranı, genlik, sönüm hızı)
        (1.00, 1.00, 7.0),
        (2.00, 0.32, 12.0),
        (2.76, 0.30, 16.0),
        (4.07, 0.14, 24.0),
        (5.40, 0.10, 30.0),
        (0.50, 0.12, 9.0),
    ]
    y = np.zeros_like(t)
    for ratio, amp, decay in partials:
        y += amp * np.exp(-decay * t) * np.sin(2 * np.pi * freq * ratio * t + ratio * 1.3)
    # vuruş anı: çok kısa, parlak 'tık'
    rng = np.random.default_rng(3)
    noise = rng.standard_normal(len(t))
    noise = noise - np.convolve(noise, np.ones(4) / 4, mode="same")  # kaba yüksek geçiren
    y += 0.55 * noise * np.exp(-t * 700)
    y *= np.minimum(1.0, t / 0.0008)                     # ~1 ms atak
    cut = int(SR * 0.006)                                 # sonda 6 ms: tık diye kesilme
    y[-cut:] *= np.linspace(1.0, 0.0, cut)
    y /= np.max(np.abs(y)) + 1e-9
    y *= 0.95
    pcm = (np.stack([y, y], axis=1) * 32767).astype(np.int16)
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
    p = os.path.join(work_dir, "zil_cin_v1.wav")   # sürüm adı değişince yeniden üretilir
    if not os.path.isfile(p):
        synth_ding(p)
    return os.path.abspath(p)
