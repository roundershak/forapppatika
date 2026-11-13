"""2. aşama: aday anları yapay zekâ ile değerlendirip en iyi klipleri seçer.

1) Her aday anın çevresindeki pencerenin sesi akıştan çekilir (sadece o kısım).
2) Whisper ile kelime zamanlı yazıya dökülür.
3) Claude (ANTHROPIC_API_KEY varsa) tüm adayları birlikte okuyup gerçekten klip olacak anları
   (gülme, şok, sinir, komik laf, epik oyun anı...) seçer, puanlar ve başlangıç/bitişi belirler.
   Anahtar yoksa ses puanı + metindeki tepki işaretleri (hahaha, !, 'olamaz' vb.) ile seçilir.
Bu aşamada çıkarılan kelimeler sonradan altyazı için tekrar kullanılır (ikinci kez Whisper çalışmaz).
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from .highlights import Segment
from .subtitles import Transcriber, Word
from .utils import Logger, default_log, fmt_time

MODEL = os.environ.get("KICKCLIP_MODEL", "claude-opus-5-5")

RANK_SCHEMA = {
    "type": "object",
    "properties": {
        "clips": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "candidate_id": {"type": "integer"},
                    "score": {"type": "integer"},
                    "start": {"type": "number"},
                    "end": {"type": "number"},
                    "category": {"type": "string"},
                    "reason": {"type": "string"},
                },
                "required": ["candidate_id", "score", "start", "end", "category", "reason"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["clips"],
    "additionalProperties": False,
}

RANK_SYSTEM = """Sen Kick/Twitch yayınlarından viral TikTok/Shorts klipleri seçen deneyimli bir klip editörüsün.
Sana bir yayından otomatik bulunmuş aday anlar verilecek. Her adayın zaman damgalı konuşma dökümü ve
ses analizinden gelen bir 'ses puanı' (yüksek = ani bağırma/gülme/heyecan) var.

Görevin: izleyicinin durup izleyeceği en iyi anları seçmek ve her biri için klibin başlangıç/bitişini belirlemek.
İyi klip: yayıncının gerçek tepkisi (kahkaha, şok, sinir krizi, çığlık), komik/iddialı/alıntılanabilir bir söz,
chat'e ya da birine verilen sert/komik cevap, epik ya da rezil bir oyun anı, kendi içinde anlaşılan kısa bir hikâye.
Kötü klip: sıradan oyun anlatımı, bağlamsız yarım cümle, uzun sessizlik, reklam/bağış okuma, teknik ayar konuşması.

ÖNCELİK: Bu kanal için en değerli anlar yayıncının BAĞIRDIĞI, sesin aniden YÜKSELDİĞİ, GERİLİMİN tırmandığı
(kavga, sinir, panik, büyük heyecan, şok) anlardır. 'ses puanı' bunu ölçer: ses puanı yüksek adayları, metni
çok sıradan değilse, öne al. Sakin konuşmayı ancak gerçekten çok güçlü bir içerikse seç.

Kurallar:
- Klip olmaya değmeyen adayları LİSTEYE KOYMA. En fazla istenen sayı kadar seç, en iyiden kötüye sırala.
- start/end mutlak saniye cinsinden ve adayın penceresi içinde olmalı. Süre verilen minimum-maksimum arasında olmalı.
- Klip olayın hemen öncesinde (kurulumla) başlasın, tepkiden/punchline'dan hemen sonra bitsin; cümle ortasında kesme.
- score 0-100 (viral olma potansiyeli). category: kahkaha | şok | sinir | komik söz | epik an | duygusal | diğer.
- reason: tek kısa Türkçe cümle, klipte ne olduğu."""


def _extract_audio(src, start: float, dur: float, out: str) -> bool:
    cmd = ["ffmpeg", "-y", "-v", "error", *src.ff_input("analysis", start, dur),
           "-vn", "-ac", "1", "-ar", "16000", out]
    r = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return r.returncode == 0 and os.path.exists(out) and os.path.getsize(out) > 1000


def windows_for(cands: list[Segment], window: float, lo: float, hi: float) -> list[tuple[float, float]]:
    out = []
    for c in cands:
        s = max(lo, c.peak - window * 0.6)
        e = min(hi, s + window)
        s = max(lo, e - window)
        out.append((s, e))
    return out


def transcribe_candidates(src, cands: list[Segment], wins: list[tuple[float, float]],
                          transcriber: Transcriber, log: Logger = default_log,
                          should_stop=lambda: False) -> list[list[Word]]:
    tmp = tempfile.mkdtemp(prefix="kickclip_")
    paths = [os.path.join(tmp, f"c{i}.wav") for i in range(len(cands))]
    log(f"{len(cands)} aday anın sesi çekiliyor...")
    with ThreadPoolExecutor(max_workers=6) as ex:
        ok = list(ex.map(lambda a: _extract_audio(src, a[1][0], a[1][1] - a[1][0], a[0]), zip(paths, wins)))
    result: list[list[Word]] = []
    for i, ((s, e), p, good) in enumerate(zip(wins, paths, ok), 1):
        if should_stop():
            break
        words: list[Word] = []
        if good:
            log(f"Konuşma çözümleniyor {i}/{len(cands)} ({fmt_time(s)})")
            try:
                words = [Word(w.start + s, w.end + s, w.text) for w in transcriber.words(p)]
            except Exception as ex_:
                log(f"Whisper hatası: {ex_}")
        result.append(words)
        try:
            os.remove(p)
        except OSError:
            pass
    try:
        os.rmdir(tmp)
    except OSError:
        pass
    return result


def _lines(words: list[Word], gap: float = 0.7, max_words: int = 14) -> list[tuple[float, str]]:
    lines, cur, t0 = [], [], 0.0
    for w in words:
        if cur and (w.start - prev_end > gap or len(cur) >= max_words):
            lines.append((t0, " ".join(cur)))
            cur = []
        if not cur:
            t0 = w.start
        cur.append(w.text)
        prev_end = w.end
    if cur:
        lines.append((t0, " ".join(cur)))
    return lines


LAUGH = re.compile(r"\b(a?h[aeı]h[aeı](h[aeı])*|kah+kah+a|lo+l|xd+|ahah\w*|hah\w*)\b", re.I)
HYPE = ("olamaz", "inanılmaz", "efsane", "yok artık", "vay", "aman", "hayır", "nasıl", "neden",
        "oha", "lan", "abi", "kanka", "bitti", "kazandık", "öldüm", "deli", "şaka", "yuh", "allah")


def _text_score(words: list[Word]) -> float:
    text = " ".join(w.text for w in words).lower()
    s = 2.0 * len(LAUGH.findall(text)) + 0.6 * text.count("!") + 0.4 * text.count("?")
    s += sum(text.count(h) for h in HYPE) * 0.5
    return s


def _heuristic(cands, wins, words_list, n, clip_len, lead_ratio) -> list[Segment]:
    import numpy as np
    a = np.array([c.score for c in cands], dtype=float)
    t = np.array([_text_score(w) for w in words_list], dtype=float)
    z = lambda x: (x - x.mean()) / (x.std() if x.std() > 1e-6 else 1.0)  # noqa: E731
    total = 0.8 * z(a) + 0.2 * z(t)  # ses (bağırma/gerilim) ağırlıklı
    order = np.argsort(total)[::-1][:n]
    out = []
    for i in order:
        c = cands[int(i)]
        c.score = float(total[i])
        c.words = words_list[int(i)]
        if _text_score(c.words) > 2:
            c.reason = (c.reason + ", tepki sözleri").strip(", ")
        out.append(_snap(c, wins[int(i)], c.start, c.end))
    return out


def _snap(seg: Segment, win: tuple[float, float], start: float, end: float) -> Segment:
    """Kesimi kelimelerin ortasına denk getirmemek için sınırları sessizliğe kaydırır."""
    words = seg.words
    for w in words:
        if w.start < start < w.end:
            start = w.start - 0.1
        if w.start < end < w.end:
            end = w.end + 0.15
    seg.start, seg.end = max(win[0], start), min(win[1], end)
    seg.words = [w for w in words if w.end > seg.start and w.start < seg.end]
    return seg


def _claude(cands, wins, words_list, n, min_len, max_len, log) -> Optional[list[dict]]:
    if not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
        return None
    try:
        import anthropic
    except ImportError:
        return None
    blocks = []
    for i, (c, (s, e), words) in enumerate(zip(cands, wins, words_list)):
        lines = "\n".join(f"  [{t:.1f}] {txt}" for t, txt in _lines(words)) or "  (konuşma yok)"
        blocks.append(f"ADAY {i} | pencere {s:.1f}-{e:.1f} sn | ses puanı {c.score:.2f} "
                      f"({c.reason}) | zirve {c.peak:.1f} sn\n{lines}")
    user = (f"İstenen en fazla klip sayısı: {n}\nKlip süresi: en az {min_len:.0f} sn, en fazla {max_len:.0f} sn\n\n"
            + "\n\n".join(blocks))
    log(f"Claude {len(cands)} adayı değerlendiriyor...")
    try:
        client = anthropic.Anthropic()
        resp = client.beta.messages.create(
            model=MODEL,
            max_tokens=8000,
            system=RANK_SYSTEM,
            messages=[{"role": "user", "content": user}],
            output_config={"effort": "medium", "format": {"type": "json_schema", "schema": RANK_SCHEMA}},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
        if resp.stop_reason == "refusal":
            raise RuntimeError("model isteği reddetti")
        if resp.stop_reason == "max_tokens":
            raise RuntimeError("yanıt yarıda kesildi")
        text = next(b.text for b in resp.content if b.type == "text")
        return json.loads(text)["clips"]
    except Exception as e:
        log(f"Claude ile seçim yapılamadı ({e}); ses + metin puanı kullanılıyor.")
        return None


def rank(src, cands: list[Segment], n: int, clip_len: float, lead_ratio: float,
         transcriber: Optional[Transcriber], window: float, flex: bool = True,
         log: Logger = default_log, should_stop=lambda: False) -> list[Segment]:
    lo, hi = src.start, src.end
    wins = windows_for(cands, window, lo, hi)
    if transcriber is None:
        words_list: list[list[Word]] = [[] for _ in cands]
    else:
        words_list = transcribe_candidates(src, cands, wins, transcriber, log, should_stop)
        words_list += [[] for _ in range(len(cands) - len(words_list))]

    min_len = clip_len * (0.5 if flex else 1.0)
    max_len = min(175.0, clip_len * (1.6 if flex else 1.0))
    picks = _claude(cands, wins, words_list, n, min_len, max_len, log)
    if picks is None:
        return _heuristic(cands, wins, words_list, n, clip_len, lead_ratio)

    out: list[Segment] = []
    used: list[tuple[float, float]] = []
    for p in picks:
        i = p.get("candidate_id")
        if not isinstance(i, int) or not (0 <= i < len(cands)):
            continue
        w = wins[i]
        s, e = float(p["start"]), float(p["end"])
        s, e = max(w[0], min(s, w[1])), max(w[0], min(e, w[1]))
        if e - s < min_len:
            e = min(w[1], s + min_len)
            s = max(w[0], e - min_len)
        if e - s > max_len:
            e = s + max_len
        if any(min(e, b) - max(s, a) > 0.5 * (e - s) for a, b in used):
            continue
        seg = Segment(s, e, float(p.get("score", 0)), cands[i].peak, p.get("reason", ""), p.get("category", ""),
                      words_list[i])
        out.append(_snap(seg, w, s, e))
        used.append((s, e))
        if len(out) >= n:
            break
    if not out:
        log("Claude uygun klip seçmedi; ses + metin puanı kullanılıyor.")
        return _heuristic(cands, wins, words_list, n, clip_len, lead_ratio)
    log(f"Claude {len(out)} klip seçti.")
    return out
