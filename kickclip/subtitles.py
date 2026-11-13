"""Whisper ile konuşmayı yazıya döker ve TikTok tarzı (kelime vurgulu) ASS altyazı üretir."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Optional

from .utils import Logger, default_log


@dataclass
class Word:
    start: float
    end: float
    text: str


class Transcriber:
    def __init__(self, model: str = "small", device: str = "auto", language: Optional[str] = "tr",
                 log: Logger = default_log):
        self.model_name = model
        self.device = device
        self.language = language or None
        self.log = log
        self._model = None

    def _load(self):
        if self._model is None:
            from faster_whisper import WhisperModel
            device = self.device
            if device == "auto":
                try:
                    import ctranslate2
                    device = "cuda" if ctranslate2.get_cuda_device_count() > 0 else "cpu"
                except Exception:
                    device = "cpu"
            compute = "float16" if device == "cuda" else "int8"
            self.log(f"Whisper modeli yükleniyor: {self.model_name} ({device}) - ilk seferde indirilir...")
            self._model = WhisperModel(self.model_name, device=device, compute_type=compute)
        return self._model

    def words(self, audio_path: str) -> list[Word]:
        model = self._load()
        segments, _info = model.transcribe(
            audio_path, language=self.language, word_timestamps=True, vad_filter=True,
            beam_size=5, condition_on_previous_text=False,
        )
        out: list[Word] = []
        for seg in segments:
            for w in seg.words or []:
                txt = w.word.strip()
                if txt:
                    out.append(Word(float(w.start), float(w.end), txt))
        return out


def _ass_color(hex_color: str, alpha: int = 0) -> str:
    h = hex_color.lstrip("#")
    r, g, b = h[0:2], h[2:4], h[4:6]
    return f"&H{alpha:02X}{b}{g}{r}".upper()


def _ts(t: float) -> str:
    t = max(0.0, t)
    cs = int(round(t * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace("{", "(").replace("}", ")").replace("\n", " ")


def _upper_tr(s: str) -> str:
    return s.replace("i", "İ").replace("ı", "I").upper()


def group_words(words: list[Word], per_line: int = 3, max_gap: float = 0.6,
                max_dur: float = 1.8) -> list[list[Word]]:
    groups: list[list[Word]] = []
    cur: list[Word] = []
    for w in words:
        if cur and (len(cur) >= per_line or w.start - cur[-1].end > max_gap
                    or w.end - cur[0].start > max_dur or re.search(r"[.!?…]$", cur[-1].text)):
            groups.append(cur)
            cur = []
        cur.append(w)
    if cur:
        groups.append(cur)
    return groups


def build_ass(words: list[Word], path: str, width: int, height: int, font: str = "Montserrat ExtraBold",
              font_size: int = 78, per_line: int = 3, uppercase: bool = True,
              highlight: str = "#FFE600", position: float = 0.40) -> str:
    y = int(height * position)
    hl = _ass_color(highlight)[4:]  # override etiketi için &HBBGGRR&
    hl = f"&H{hl}&"
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Main,{font},{font_size},&H00FFFFFF,&H00FFFFFF,&H00000000,&H96000000,-1,0,0,0,100,100,1,0,1,6,3,5,60,60,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = []
    for grp in group_words(words, per_line):
        texts = [_esc(_upper_tr(w.text) if uppercase else w.text) for w in grp]
        g_end = grp[-1].end + 0.08
        for i, w in enumerate(grp):
            start = w.start if i else grp[0].start
            end = grp[i + 1].start if i + 1 < len(grp) else g_end
            if end <= start:
                continue
            parts = []
            for j, t in enumerate(texts):
                if j == i:
                    parts.append(f"{{\\c{hl}\\fscx112\\fscy112}}{t}{{\\c&HFFFFFF&\\fscx100\\fscy100}}")
                else:
                    parts.append(t)
            pop = "{\\fscx92\\fscy92\\t(0,80,\\fscx100\\fscy100)}" if i == 0 else ""
            text = f"{{\\pos({width // 2},{y})}}{pop}" + " ".join(parts)
            lines.append(f"Dialogue: 0,{_ts(start)},{_ts(end)},Main,,0,0,0,,{text}")
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(header + "\n".join(lines) + "\n")
    return path
