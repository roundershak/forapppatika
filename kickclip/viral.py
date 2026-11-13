"""'Viral anlar' seçimi: yayının TAMAMI yazıya dökülür, Claude tüm konuşmayı okuyup
viral olabilecek önemli anları (drama, itiraf, tartışma, olay yaratacak görüş, duyuru, hikâye,
komik söz, büyük tepki...) seçer. Ses analizi yalnızca ipucu olarak verilir.

Döküm diske kaydedilir; aynı yayın/aralık için tekrar çalıştırınca yeniden yazıya dökülmez.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

import numpy as np

from . import llm
from .highlights import Features, Segment, pick_peaks, reaction_score, _describe
from .subtitles import Transcriber, Word
from .utils import Logger, default_log, fmt_time

CHUNK = 600.0  # yazıya dökme parça uzunluğu (sn)

VIRAL_SYSTEM = """Sen Türk Kick/Twitch yayınlarından TikTok/YouTube Shorts için VİRAL klipler seçen, çok deneyimli bir
klip kanalı editörüsün. Sana bir yayının zaman damgalı tam konuşma dökümü ([saniye] metin) ve ses analizinin
işaretlediği yüksek tepki anları verilecek.

Görevin: izleyicinin kaydırmayı bırakıp izleyeceği, paylaşacağı, yorum yazacağı anları bulmak.
Öncelik sırası:
- BAĞIRMA, sesin aniden yükseldiği, GERİLİMİN tırmandığı anlar (kavga, sinir krizi, panik, şok, büyük heyecan) -
  'yüksek tepki anları' listesindeki zamanlar bunun ipucudur, bunlara özellikle bak
- ÖNEMLİ ve KONUŞULACAK anlar:
- drama / ifşa / itiraf / gizli bilgi, başka yayıncı veya ünlüler hakkında söylenenler
- tartışma, kavga, sert cevap, chat'le ya da biriyle atışma
- olay yaratacak görüş (hot take), tartışmalı açıklama
- duyuru / haber / önemli gelişme (bırakıyorum, yeni proje, ayrılık, para/kazanç rakamları...)
- kendi içinde anlaşılan kısa hikâye / anı, şaşırtıcı bilgi
- çok komik söz, punchline, efsane tepki, rezil/epik an
Kötü klip: bağlamsız yarım konuşma, sıradan oyun anlatımı, bağış/abonelik okuma, teknik ayar, reklam.

Kurallar:
- Her klip TEK BAŞINA anlaşılmalı: konunun kurulumuyla başla, punchline/sonuçtan hemen sonra bitir; cümle ortasında kesme.
- start/end saniye cinsinden, dökümdeki zaman damgalarına dayansın. Süre verilen min-maks arasında olsun.
- Klipler birbiriyle çakışmasın. En fazla istenen sayı kadar seç; daha az iyi an varsa daha az seç.
- En iyiden kötüye sırala. score 0-100 viral potansiyel.
- category: drama | itiraf | tartışma | hot take | duyuru | hikaye | komik | tepki | bilgi | diger
- hook: klibin ilk saniyelerinde izleyiciyi tutacak cümle (dökümden, kısa).
- reason: tek kısa Türkçe cümle, neden viral olur."""

VIRAL_SCHEMA = {
    "type": "object",
    "properties": {
        "clips": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "start": {"type": "number"},
                    "end": {"type": "number"},
                    "score": {"type": "integer"},
                    "category": {"type": "string"},
                    "hook": {"type": "string"},
                    "reason": {"type": "string"},
                },
                "required": ["start", "end", "score", "category", "hook", "reason"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["clips"],
    "additionalProperties": False,
}

VIRAL_WORDS = ("itiraf", "açıklıyorum", "gerçek", "yalan", "ifşa", "kavga", "tartış", "ayrıl", "bırakıyorum",
               "son dakika", "haber", "milyon", "bin dolar", "para", "ban", "dava", "polis", "skandal",
               "rezil", "efsane", "inanılmaz", "olamaz", "yok artık", "bak şimdi", "size bir şey",
               "kimse bilmiyor", "ilk defa", "söylemeyecektim", "hayatımda")


def _cache_path(work_dir: str, src, model: str, lang) -> str:
    key = f"{src.media}|{src.title}|{src.start:.0f}|{src.end:.0f}|{model}|{lang}"
    if src.kind == "stream":  # akış adresleri imzalı/değişken olabilir: başlık + süre ile anahtarla
        key = f"{src.uploader}|{src.title}|{src.duration:.0f}|{src.start:.0f}|{src.end:.0f}|{model}|{lang}"
    h = hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]
    return os.path.join(work_dir, "dokumler", f"{h}.json")


def transcribe_all(src, transcriber: Transcriber, work_dir: str, log: Logger = default_log,
                   should_stop=lambda: False) -> list[Word]:
    """[src.start, src.end] aralığının tamamını yazıya döker (önbellekli)."""
    cache = _cache_path(work_dir, src, transcriber.model_name, transcriber.language)
    if os.path.isfile(cache):
        with open(cache, encoding="utf-8") as f:
            data = json.load(f)
        log(f"Kayıtlı döküm kullanılıyor ({len(data)} kelime).")
        return [Word(*w) for w in data]

    chunks = []
    t = src.start
    while t < src.end - 1:
        chunks.append((t, min(CHUNK, src.end - t)))
        t += CHUNK
    tmp = tempfile.mkdtemp(prefix="kickclip_dokum_")

    def extract(i):
        s, d = chunks[i]
        p = os.path.join(tmp, f"{i}.wav")
        r = subprocess.run(["ffmpeg", "-y", "-v", "error", *src.ff_input("analysis", s, d),
                            "-vn", "-ac", "1", "-ar", "16000", p], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return p if r.returncode == 0 and os.path.exists(p) else None

    words: list[Word] = []
    t0 = time.time()
    log(f"Yayının tamamı yazıya dökülüyor: {len(chunks)} parça x {CHUNK / 60:.0f} dk "
        f"(model: {transcriber.model_name}). Ekran kartı yoksa uzun sürebilir.")
    with ThreadPoolExecutor(max_workers=3) as ex:  # sesi önden çek, Whisper sırayla çalışsın
        futs = [ex.submit(extract, i) for i in range(len(chunks))]
        for i, fut in enumerate(futs):
            if should_stop():
                break
            p = fut.result()
            if p:
                try:
                    s = chunks[i][0]
                    words += [Word(w.start + s, w.end + s, w.text) for w in transcriber.words(p)]
                finally:
                    try:
                        os.remove(p)
                    except OSError:
                        pass
            el = time.time() - t0
            eta = el / (i + 1) * (len(chunks) - i - 1)
            log(f"Döküm {i + 1}/{len(chunks)} ({fmt_time(chunks[i][0])}) · kalan ~{eta / 60:.0f} dk")
    try:
        os.rmdir(tmp)
    except OSError:
        pass
    if not should_stop() and words:
        os.makedirs(os.path.dirname(cache), exist_ok=True)
        with open(cache, "w", encoding="utf-8") as f:
            json.dump([[round(w.start, 2), round(w.end, 2), w.text] for w in words], f, ensure_ascii=False)
    return words


def _transcript_text(words: list[Word], gap: float = 0.8, max_words: int = 18) -> str:
    lines, cur, t0, prev = [], [], 0.0, 0.0
    for w in words:
        if cur and (w.start - prev > gap or len(cur) >= max_words):
            lines.append(f"[{int(t0)}] {' '.join(cur)}")
            cur = []
        if not cur:
            t0 = w.start
        cur.append(w.text)
        prev = w.end
    if cur:
        lines.append(f"[{int(t0)}] {' '.join(cur)}")
    return "\n".join(lines)


def _snap(start: float, end: float, words: list[Word], lo: float, hi: float) -> tuple[float, float]:
    for w in words:
        if w.start < start < w.end:
            start = w.start - 0.1
        if w.start < end < w.end:
            end = w.end + 0.15
    return max(lo, start), min(hi, end)


def _heuristic(words: list[Word], feats: Optional[Features], n: int, clip_len: float, lo: float,
               hi: float) -> list[Segment]:
    """Claude yoksa: metindeki viral işaretler + ses tepkisi."""
    step = 5.0
    times = np.arange(lo, max(lo + step, hi - clip_len), step)
    text_sc = np.zeros(len(times))
    wi = 0
    for i, t in enumerate(times):
        while wi < len(words) and words[wi].end < t:
            wi += 1
        j, txt = wi, []
        while j < len(words) and words[j].start < t + clip_len:
            txt.append(words[j].text.lower())
            j += 1
        s = " ".join(txt)
        text_sc[i] = sum(s.count(k) for k in VIRAL_WORDS) + 0.4 * s.count("!") + 0.3 * s.count("?") + len(txt) / 150
    if feats is not None and len(feats.db):
        rs = reaction_score(feats, clip_len)
        idx = np.clip(((times + clip_len / 2 - feats.t0) / 0.5).astype(int), 0, len(rs) - 1)
        audio = rs[idx]
    else:
        audio = np.zeros(len(times))
    z = lambda a: (a - a.mean()) / (a.std() if a.std() > 1e-6 else 1.0)  # noqa: E731
    total = 0.35 * z(text_sc) + 0.65 * z(audio)
    peaks = pick_peaks(total, 1.5 * clip_len / step * 0.5, n)  # pick_peaks saniyeyi 0.5 sn/indeks sayar
    out = []
    for i in sorted(peaks, key=lambda k: -total[k]):
        s, e = _snap(times[i], times[i] + clip_len, words, lo, hi)
        out.append(Segment(s, e, float(total[i]), s + clip_len / 2, "metin + ses işaretleri", "",
                           [w for w in words if w.end > s and w.start < e]))
    return out


def rank_viral(src, feats: Optional[Features], words: list[Word], n: int, clip_len: float, flex: bool,
               log: Logger = default_log) -> list[Segment]:
    lo, hi = src.start, src.end
    min_len = clip_len * (0.5 if flex else 1.0)
    max_len = min(175.0, clip_len * (2.0 if flex else 1.0))
    if not words:
        raise RuntimeError("Yayında yazıya dökülecek konuşma bulunamadı.")
    if not llm.available():
        log("Claude anahtarı yok: viral anlar metin + ses işaretleriyle seçiliyor (daha zayıf).")
        return _heuristic(words, feats, n, clip_len, lo, hi)

    hints = ""
    if feats is not None and len(feats.db):
        rs = reaction_score(feats, clip_len)
        peaks = pick_peaks(rs, 30, 40)
        hints = "\n".join(f"[{int(feats.time(i))}] {_describe(feats, i)} (puan {rs[i]:.1f})"
                          for i in sorted(peaks))
    text = _transcript_text(words)
    user = (f"Yayıncı: {src.uploader or 'bilinmiyor'}\nYayın başlığı: {src.title}\n"
            f"İstenen en fazla klip: {n}\nKlip süresi: en az {min_len:.0f} sn, en fazla {max_len:.0f} sn "
            f"(hedef ~{clip_len:.0f} sn)\nYayın aralığı: {int(lo)}-{int(hi)} sn\n\n"
            f"SES ANALİZİ - YÜKSEK TEPKİ ANLARI (ipucu):\n{hints or '(yok)'}\n\n"
            f"TAM DÖKÜM ([saniye] metin):\n{text}")
    log(f"Claude yayının tüm dökümünü okuyor ({len(words)} kelime)... Bu 1-3 dk sürebilir.")
    try:
        data = llm.ask_json(VIRAL_SYSTEM, user, VIRAL_SCHEMA, effort="high", max_tokens=16000)
    except Exception as e:
        log(f"Claude ile seçim yapılamadı ({e}); metin + ses işaretleri kullanılıyor.")
        return _heuristic(words, feats, n, clip_len, lo, hi)

    out: list[Segment] = []
    for c in data.get("clips", []):
        try:
            s, e = float(c["start"]), float(c["end"])
        except (KeyError, TypeError, ValueError):
            continue
        s, e = max(lo, s), min(hi, e)
        if e - s < min_len:
            e = min(hi, s + min_len)
            s = max(lo, e - min_len)
        if e - s > max_len:
            e = s + max_len
        s, e = _snap(s, e, words, lo, hi)
        if any(min(e, o.end) - max(s, o.start) > 0.3 * (e - s) for o in out):
            continue
        reason = c.get("reason", "")
        if c.get("hook"):
            reason = f"{reason} — “{c['hook']}”"
        out.append(Segment(s, e, float(c.get("score", 0)), s, reason, c.get("category", ""),
                           [w for w in words if w.end > s and w.start < e]))
        if len(out) >= n:
            break
    if not out:
        log("Claude uygun an seçmedi; metin + ses işaretleri kullanılıyor.")
        return _heuristic(words, feats, n, clip_len, lo, hi)
    log(f"Claude {len(out)} viral an seçti.")
    return out
