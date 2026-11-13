#!/usr/bin/env python3
"""Builds the 30 s soundtrack: TTS narration + synthesized SFX + final jingle.

All sound effects and music are synthesized procedurally with numpy (the
ElevenLabs key in use has no sound-effect / music permission).
Output: build/mix.wav (48 kHz stereo) plus stems in build/stems/.
"""
import json
import os
import subprocess
import wave

import numpy as np

ROOT = os.path.dirname(os.path.abspath(__file__))
SR = 48000
TL = json.load(open(os.path.join(ROOT, "timeline.json"), encoding="utf-8"))
DUR = TL["duration"]
N = int(SR * DUR)
rng = np.random.default_rng(11)


# ---------------------------------------------------------------- helpers
def t_axis(n):
    return np.arange(n) / SR


def band(x, lo, hi, soft=0.15):
    """FFT band-pass with soft edges."""
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    m = np.ones_like(f)
    if lo > 0:
        m *= 1 / (1 + np.exp(-(f - lo) / (lo * soft)))
    if hi < SR / 2:
        m *= 1 / (1 + np.exp((f - hi) / (hi * soft)))
    return np.fft.irfft(X * m, len(x))


def env_ad(n, a=0.005, d=0.2):
    t = t_axis(n)
    e = np.minimum(1, t / max(a, 1e-4)) * np.exp(-np.maximum(0, t - a) / d)
    return e


def sweep(f0, f1, dur, shape="exp"):
    n = int(SR * dur)
    p = np.linspace(0, 1, n)
    f = f0 * (f1 / f0) ** p if shape == "exp" else f0 + (f1 - f0) * p
    return 2 * np.pi * np.cumsum(f) / SR


def norm(x, peak=1.0):
    m = np.max(np.abs(x)) or 1
    return x / m * peak


class Track:
    def __init__(self):
        self.x = np.zeros(N)

    def add(self, sig, at, gain=1.0):
        i = int(at * SR)
        if i >= N:
            return
        sig = sig[: N - i]
        self.x[i:i + len(sig)] += sig * gain


def db(v):
    return 10 ** (v / 20)


# ---------------------------------------------------------------- SFX
def thud(f=85, dur=0.35):
    n = int(SR * dur)
    ph = sweep(f * 1.8, f, dur)
    body = np.sin(ph) * env_ad(n, 0.002, 0.09)
    click = band(rng.standard_normal(n), 800, 4000) * env_ad(n, 0.0005, 0.01)
    return norm(body + 0.4 * click)


def wood_knock(dur=0.4, base=170):
    n = int(SR * dur)
    t = t_axis(n)
    s = sum(a * np.sin(2 * np.pi * base * k * t) * np.exp(-t / d)
            for a, k, d in [(1, 1, 0.08), (0.6, 2.3, 0.05), (0.4, 4.1, 0.03)])
    s += 0.3 * band(rng.standard_normal(n), 500, 3000) * env_ad(n, 0.0005, 0.015)
    return norm(s)


def click(pitch=1.0):
    n = int(SR * 0.06)
    s = band(rng.standard_normal(n), 2000 * pitch, 7000) * env_ad(n, 0.0003, 0.008)
    s += 0.5 * np.sin(2 * np.pi * 1400 * pitch * t_axis(n)) * env_ad(n, 0.0005, 0.012)
    return norm(s)


def bonk():
    dur = 0.45
    n = int(SR * dur)
    tone = np.sin(sweep(720, 140, dur)) * env_ad(n, 0.001, 0.14)
    return norm(tone + 0.7 * wood_knock(dur, 230))


def boing(f0=180, f1=520, dur=0.6, vib=11):
    n = int(SR * dur)
    t = t_axis(n)
    f = f0 * (f1 / f0) ** np.linspace(0, 1, n) * (1 + 0.06 * np.sin(2 * np.pi * vib * t))
    return norm(np.sin(2 * np.pi * np.cumsum(f) / SR) * env_ad(n, 0.01, dur / 2.5))


def ding(f=1320, dur=1.0):
    n = int(SR * dur)
    t = t_axis(n)
    s = sum(a * np.sin(2 * np.pi * f * k * t) * np.exp(-t / d) for a, k, d in [(1, 1, 0.35), (0.5, 2.0, 0.2), (0.3, 3.01, 0.12)])
    return norm(s)


def pop():
    dur = 0.12
    n = int(SR * dur)
    return norm(np.sin(sweep(300, 1100, dur)) * env_ad(n, 0.002, 0.03))


def whoosh(dur=0.5, lo=300, hi=2500):
    n = int(SR * dur)
    w = np.sin(np.linspace(0, np.pi, n)) ** 2
    return norm(band(rng.standard_normal(n), lo, hi) * w)


def squelch():
    dur = 0.5
    n = int(SR * dur)
    s = band(rng.standard_normal(n), 120, 900) * env_ad(n, 0.01, 0.12)
    s += 0.6 * np.sin(sweep(260, 70, dur)) * env_ad(n, 0.005, 0.1)
    return norm(s)


def womp(notes=((233.1, 0.32), (220.0, 0.32), (207.7, 0.32), (196.0, 0.75))):
    """Sad-trombone style descending brass."""
    out = []
    for f, d in notes:
        n = int(SR * d)
        t = t_axis(n)
        vib = 1 + 0.012 * np.sin(2 * np.pi * 5.5 * t) * (t > d * 0.4)
        ph = 2 * np.pi * np.cumsum(f * vib) / SR
        if d > 0.5:
            ph = 2 * np.pi * np.cumsum(f * vib * (1 - 0.06 * np.linspace(0, 1, n) ** 2)) / SR
        saw = sum(np.sin(k * ph) / k for k in range(1, 12))
        e = np.minimum(1, t / 0.04) * np.minimum(1, (d - t) / 0.06)
        out.append(band(saw, 80, 1800) * e)
    return norm(np.concatenate(out))


def creak(dur=0.45):
    n = int(SR * dur)
    t = t_axis(n)
    f = 260 + 120 * np.sin(2 * np.pi * 2.2 * t) + 30 * rng.standard_normal(n).cumsum() / np.sqrt(n)
    ph = 2 * np.pi * np.cumsum(f) / SR
    pulses = (np.sin(ph) > 0.92).astype(float)
    s = band(pulses, 300, 3000) * np.sin(np.linspace(0, np.pi, n))
    return norm(s)


def tink():
    return ding(2600, 0.5)


def plip():
    dur = 0.09
    n = int(SR * dur)
    return norm(np.sin(sweep(700, 1600, dur)) * env_ad(n, 0.001, 0.025))


def chirps(dur=0.8):
    n = int(SR * dur)
    t = t_axis(n)
    s = np.zeros(n)
    for k in range(6):
        i = int(k * n / 6)
        m = int(0.07 * SR)
        if i + m > n:
            break
        s[i:i + m] += np.sin(sweep(2200 + 300 * (k % 3), 3400, 0.07)) * env_ad(m, 0.002, 0.03)
    return norm(s)


# ---------------------------------------------------------------- ambience
def rain_amount(t):
    p = lambda a, b: np.clip((t - a) / (b - a), 0, 1)
    return np.maximum.reduce([p(6.15, 6.6) * (1 - p(8.0, 8.4)),
                              p(18.2, 18.6) * (1 - p(20.5, 20.9)),
                              0.65 * p(28.3, 28.8)])


def rain_bed():
    t = t_axis(N)
    hiss = band(rng.standard_normal(N), 900, 9000) * 0.5 + band(rng.standard_normal(N), 250, 1200) * 0.35
    drops = np.zeros(N)
    idx = rng.integers(0, N - 400, 900)
    for i in idx:
        drops[i:i + 400] += np.sin(2 * np.pi * rng.uniform(1500, 4000) * t_axis(400)) * env_ad(400, 0.0003, 0.003) * rng.uniform(0.2, 1)
    amt = rain_amount(t)
    # final segment heard "from inside": darker
    inside = band(hiss + drops * 0.4, 0, 1800)
    w = np.clip((t - 28.4) / 0.4, 0, 1)
    sig = (hiss + drops * 0.4) * (1 - w) + inside * w * 1.2
    return norm(sig) * amt


def wind_bed():
    t = t_axis(N)
    brown = np.cumsum(rng.standard_normal(N))
    brown -= np.convolve(brown, np.ones(4801) / 4801, mode="same")
    s = band(brown, 150, 1400) + 0.25 * band(rng.standard_normal(N), 600, 2500)
    gust = 0.55 + 0.45 * np.sin(2 * np.pi * 0.45 * t + 1.0) ** 2
    fade = np.clip(1 - (t - 3.8) / 0.9, 0, 1)
    return norm(s) * gust * fade


# ---------------------------------------------------------------- music
def pluck(f, dur=1.2, bright=0.5):
    """Karplus-Strong plucked string (ukulele-ish)."""
    n = int(SR * dur)
    p = int(SR / f)
    buf = rng.uniform(-1, 1, p)
    buf = band(np.concatenate([buf] * 4), 0, 3000 + 4000 * bright)[:p]
    out = np.zeros(n)
    for i in range(n):
        out[i] = buf[i % p]
        buf[i % p] = 0.5 * (buf[i % p] + buf[(i + 1) % p]) * 0.996
    return out * env_ad(n, 0.002, dur * 0.6)


def glock(f, dur=0.9):
    n = int(SR * dur)
    t = t_axis(n)
    return (np.sin(2 * np.pi * f * t) + 0.25 * np.sin(2 * np.pi * f * 2.76 * t) * np.exp(-t / 0.08)) * np.exp(-t / 0.3)


NOTE = lambda m: 440 * 2 ** ((m - 69) / 12)


def jingle(track, start):
    bpm = 150
    e = 60 / bpm / 2  # eighth
    chords = [(60, 64, 67), (55, 59, 62), (57, 60, 64), (53, 57, 60)]  # C G Am F
    t = start
    for ci, ch in enumerate(chords):
        pattern = [ch[0], ch[1], ch[2], ch[1] + 12 if ci % 2 else ch[2], ch[0] + 12, ch[2], ch[1], ch[2]]
        for k, m in enumerate(pattern[:6]):
            track.add(pluck(NOTE(m + 12), 0.9), t + k * e, 0.5)
        track.add(pluck(NOTE(ch[0] - 12), 1.4, 0.2), t, 0.55)
        t += 6 * e
    # final chord + sparkle
    for m in (60, 64, 67, 72):
        track.add(pluck(NOTE(m + 12), 1.6), t, 0.4)
    track.add(pluck(NOTE(48 - 12 + 12), 1.8, 0.2), t, 0.6)
    melody = [(76, 0), (79, 1), (84, 2), (88, 3.2)]
    for m, k in melody:
        track.add(glock(NOTE(m)), t - 0.6 + k * e, 0.35)
    # light glockenspiel motif over the progression
    mot = [72, 76, 79, 76, 74, 79, 76, 72]
    for k, m in enumerate(mot):
        track.add(glock(NOTE(m + 12), 0.6), start + k * 3 * e, 0.18)


# ---------------------------------------------------------------- narration
def load_audio(path):
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", path, "-f", "f32le", "-ac", "1", "-ar", str(SR), "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32).astype(np.float64)


def write_wav(path, x):
    if x.ndim == 1:
        x = np.stack([x, x], 1)
    y = (np.clip(x, -1, 1) * 32767).astype(np.int16)
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(y.tobytes())


def main():
    out = os.path.join(ROOT, "build")
    os.makedirs(os.path.join(out, "stems"), exist_ok=True)

    voice = Track()
    for item in TL["narration"]:
        voice.add(load_audio(os.path.join(ROOT, "audio", f"{item['id']}.mp3")), item["start"], 1.0)
    voice.x = norm(voice.x, db(-2))

    sfx = Track()
    sfx.add(wind_bed(), 0, db(-14))
    sfx.add(ding(1320, 1.2), 2.45, db(-16))                       # idea "!"
    for i in range(4):                                            # foundation slabs lock in
        sfx.add(whoosh(0.3, 300, 2500), 4.3 + i * 0.12 - 0.15, db(-24))
        sfx.add(thud(80, 0.35), 4.3 + i * 0.12 + 0.3, db(-11))
    sfx.add(boing(90, 260, 0.4, 5), 4.95, db(-20))                # posts rise
    sfx.add(whoosh(0.3, 200, 1500), 5.3, db(-18))                 # cardboard
    sfx.add(squelch(), 5.45, db(-18))
    sfx.add(boing(220, 480, 0.2), 5.97, db(-22))
    sfx.add(boing(240, 520, 0.2), 6.17, db(-22))
    sfx.add(squelch(), 7.05, db(-10))                             # cardboard collapse
    sfx.add(thud(70, 0.4), 7.3, db(-10))
    sfx.add(womp(), 7.42, db(-15))                                # "womp womp"
    sfx.add(whoosh(0.5), 8.05, db(-16))                           # cardboard flies away
    sfx.add(boing(120, 300, 0.35, 6), 8.15, db(-22))              # posts grow
    sfx.add(whoosh(1.8, 400, 3000), 8.0, db(-22))                 # bricks lift into the air
    for k in range(26):                                           # bricks click into place
        sfx.add(click(0.7 + 0.6 * rng.random()), 8.4 + k * 2.0 / 26, db(-15))
    for k in range(8):                                            # roof frame
        sfx.add(wood_knock(0.3, 150 + 20 * rng.random()), 10.3 + k * 0.1, db(-16))
    for k in range(6):                                            # deck boards
        sfx.add(wood_knock(0.25, 210), 10.9 + k * 0.07, db(-19))
    sfx.add(ding(1760, 0.6), 11.05, db(-24))                      # proud
    sfx.add(whoosh(0.9, 500, 5000), 12.6, db(-12))                # icy gust through bare walls
    sfx.add(chirps(0.5), 13.25, db(-22))
    for k in range(9):                                            # insulation panels "fump"
        sfx.add(band(thud(160, 0.15), 100, 2500), 16.5 + k * 0.08, db(-16))
    sfx.add(whoosh(0.9, 800, 6000), 16.95, db(-16))               # plaster sweep
    sfx.add(ding(1568, 0.8), 17.35, db(-22))                      # warm & happy
    for k in range(12):                                           # leak drips on his head
        sfx.add(plip(), 18.4 + k * 0.15 + 0.04 * rng.random(), db(-17))
    sfx.add(band(rng.standard_normal(3000), 300, 3000) * env_ad(3000, 0.001, 0.01), 18.95, db(-12))  # facepalm
    for k in range(24):                                           # roof tiles clack
        sfx.add(click(0.5 + 0.3 * rng.random()), 20.4 + k * 0.045, db(-16))
    sfx.add(wood_knock(0.4, 130), 21.5, db(-12))                  # chimney/cap
    sfx.add(wood_knock(0.45, 140), 21.6, db(-11))                 # door planks
    sfx.add(pop(), 21.8, db(-14))
    sfx.add(pop(), 22.1, db(-14))
    sfx.add(tink(), 23.0, db(-14))                                # tap crooked window
    sfx.add(boing(300, 700, 0.4, 14), 23.05, db(-22))
    sfx.add(creak(0.45), 25.4, db(-12))                           # door opens
    sfx.add(wood_knock(0.4, 120), 28.3, db(-12))                  # door closes
    sfx.add(click(0.6), 28.45, db(-14))                           # light switch
    sfx.add(ding(1568, 1.2), 28.5, db(-20))

    for a, b in [(0.05, 2.4), (4.0, 4.35), (5.5, 5.95), (7.0, 7.3), (12.0, 12.9), (13.25, 13.85), (16.0, 16.4),
                 (17.85, 18.3), (20.0, 20.5), (22.4, 22.75), (23.45, 23.85), (24.6, 25.3), (27.45, 28.05)]:  # footsteps
        k = a
        while k < b:
            sfx.add(band(thud(140, 0.12), 80, 2500), k, db(-22))
            k += np.pi / 13

    amb = Track()
    amb.add(rain_bed(), 0, db(-17))

    music = Track()
    jingle(music, 26.0)
    music.x = norm(music.x, db(-14))

    # duck music & ambience under narration
    t = t_axis(N)
    v_env = np.convolve(np.abs(voice.x), np.ones(4800) / 4800, mode="same")
    duck = 1 - 0.45 * np.clip(v_env / (np.max(v_env) * 0.25), 0, 1)

    mix = voice.x + sfx.x + (amb.x + music.x) * duck
    mix = mix / max(1.0, np.max(np.abs(mix)) / db(-1))
    fade = np.clip((DUR - t) / 0.15, 0, 1)
    mix *= fade

    for name, tr in (("voice", voice.x), ("sfx", sfx.x), ("ambience", amb.x), ("music", music.x)):
        write_wav(os.path.join(out, "stems", f"{name}.wav"), tr)
    write_wav(os.path.join(out, "mix.wav"), mix)
    print("wrote", os.path.join(out, "mix.wav"))


if __name__ == "__main__":
    main()
