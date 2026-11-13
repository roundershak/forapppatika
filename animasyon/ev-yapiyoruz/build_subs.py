#!/usr/bin/env python3
"""Creates synced Turkish subtitles from the ElevenLabs word timings.

Outputs build/altyazi.srt (plain, for platforms) and build/altyazi.ass
(styled: big white text, dark outline/shadow, orange key words, bottom safe area).
"""
import json
import os
import re

ROOT = os.path.dirname(os.path.abspath(__file__))
TL = json.load(open(os.path.join(ROOT, "timeline.json"), encoding="utf-8"))
KEY = {"ev", "çatı", "çatıyı", "yağmur", "duvarları", "hazırım", "sığacağım", "unuttum",
       "pencereleri", "sabır", "tebrikler", "inşa", "ıslanmak", "yok"}
MAX_LINE = 22


def clean(w):
    return re.sub(r"[^\wçğıöşüÇĞİÖŞÜ]", "", w).lower()


def cues():
    out = []
    for item in TL["narration"]:
        meta = json.load(open(os.path.join(ROOT, "audio", f"{item['id']}.json"), encoding="utf-8"))
        cur = []
        for w in meta["words"]:
            cur.append(w)
            if re.search(r"[.!?…]$", w["word"]):
                out.append((item["start"], cur)); cur = []
        if cur:
            out.append((item["start"], cur))
    res = []
    for i, (off, ws) in enumerate(out):
        s = off + ws[0]["start"] - 0.05
        e = off + ws[-1]["end"] + 0.25
        res.append([s, e, [w["word"] for w in ws]])
    for a, b in zip(res, res[1:]):
        a[1] = min(a[1], b[0] - 0.02)
    res[-1][1] = min(res[-1][1], TL["duration"] - 0.02)
    return res


def wrap(words):
    text = " ".join(words)
    if len(text) <= MAX_LINE:
        return [words]
    best, split = 1e9, 1
    for k in range(1, len(words)):
        a, b = len(" ".join(words[:k])), len(" ".join(words[k:]))
        if max(a, b) < best:
            best, split = max(a, b), k
    return [words[:split], words[split:]]


def ts_srt(t):
    ms = int(round(t * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def ts_ass(t):
    cs = int(round(t * 100))
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


def main():
    os.makedirs(os.path.join(ROOT, "build"), exist_ok=True)
    cs = cues()
    with open(os.path.join(ROOT, "build", "altyazi.srt"), "w", encoding="utf-8") as f:
        for i, (s, e, ws) in enumerate(cs, 1):
            f.write(f"{i}\n{ts_srt(s)} --> {ts_srt(e)}\n" + "\n".join(" ".join(l) for l in wrap(ws)) + "\n\n")
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {TL['width']}
PlayResY: {TL['height']}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Ana,Inter Display,86,&H00FFFFFF,&H00FFFFFF,&H00241C16,&H8C000000,-1,0,0,0,100,100,0,0,1,6,5,2,90,90,420,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = []
    for s, e, ws in cs:
        rows = []
        for row in wrap(ws):
            rows.append(" ".join(("{\\c&H3C96F5&}" + w + "{\\c&HFFFFFF&}") if clean(w) in KEY else w for w in row))
        text = "{\\fad(70,90)\\fscx88\\fscy88\\t(0,140,\\fscx100\\fscy100)}" + "\\N".join(rows)
        lines.append(f"Dialogue: 0,{ts_ass(s)},{ts_ass(e)},Ana,,0,0,0,,{text}")
    with open(os.path.join(ROOT, "build", "altyazi.ass"), "w", encoding="utf-8") as f:
        f.write(head + "\n".join(lines) + "\n")
    print(open(os.path.join(ROOT, "build", "altyazi.srt"), encoding="utf-8").read())


if __name__ == "__main__":
    main()
