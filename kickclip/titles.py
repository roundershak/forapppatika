"""Klip için YouTube Shorts başlığı, açıklaması ve etiketleri üretir.

ANTHROPIC_API_KEY tanımlıysa Claude ile (konuşma metnine göre, dikkat çekici) üretir;
yoksa konuşma metninden kural tabanlı bir başlık çıkarır.
"""

from __future__ import annotations

import json
import os
import re
from typing import Optional

from .utils import Logger, default_log

MODEL = os.environ.get("KICKCLIP_TITLE_MODEL", "claude-opus-5-5")

SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "description": {"type": "string"},
        "tags": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["title", "description", "tags"],
    "additionalProperties": False,
}

SYSTEM = """Sen Türk Kick/Twitch yayıncıları için viral YouTube Shorts başlıkları yazan bir editörsün.
Sana bir yayından kesilmiş kısa klibin konuşma dökümü verilecek. Dökümdeki gerçek olaya dayanan,
merak uyandıran, doğal Türkçe bir başlık yaz.

Kurallar:
- Başlık en fazla 70 karakter, hashtag'ler hariç. Klipte olmayan bir şeyi iddia etme (clickbait ama yalan değil).
- 0-2 emoji kullanabilirsin. Tamamı büyük harf olmasın.
- Başlığın sonuna " #shorts" ekle.
- Açıklama 1-2 kısa cümle, ardından yeni satırda 3-5 hashtag (#shorts, yayıncı adı, oyun/konu).
- tags: YouTube etiketleri, 5-10 adet, # işareti olmadan, küçük harf.
- Döküm boş ya da anlamsızsa, yayıncı adı ve "efsane an" tarzı genel bir başlık yaz."""


def _clean_tag(s: str) -> str:
    return re.sub(r"[^\wçğıöşüÇĞİÖŞÜ]", "", s.lower(), flags=re.UNICODE)


def _fallback(transcript: str, streamer: str, source_title: str) -> dict:
    """API anahtarı yoksa: dökümdeki en vurucu cümleyi başlık yap."""
    text = re.sub(r"\s+", " ", transcript or "").strip()
    sentences = [s.strip(" ,.-") for s in re.split(r"(?<=[.!?…])\s+", text) if len(s.strip()) > 3]

    def punch(s: str) -> float:
        score = s.count("!") * 2 + s.count("?") * 1.5
        score += sum(w in s.lower() for w in ("ne ", "nasıl", "inanılmaz", "olamaz", "efsane", "hayır",
                                               "aman", "vay", "abi", "kanka", "yok artık", "allah"))
        return score - abs(len(s) - 45) / 30

    best = max(sentences, key=punch) if sentences else ""
    words = best.split()
    if len(words) > 8:  # başlık kısa ve vurucu olsun: en "tepkili" 6-8 kelimelik parça
        chunks = [" ".join(words[i:i + 7]) for i in range(0, len(words) - 6)]
        best = max(chunks, key=punch)
    if len(best) > 70:
        best = best[:67].rsplit(" ", 1)[0] + "..."
    who = streamer or "Yayıncı"
    title = f"{best[0].upper() + best[1:]} 😳" if best else f"{who} bu anı unutamayacak 😳"
    st = _clean_tag(streamer) if streamer else ""
    hashtags = ["#shorts", "#kick"] + ([f"#{st}"] if st else []) + ["#yayın"]
    desc = (f"{who} yayınından bir an." + (f" ({source_title})" if source_title else "")
            + "\n" + " ".join(hashtags))
    tags = [t for t in ["shorts", "kick", st, "yayın", "komik anlar", "twitch türkiye", "klip"] if t]
    return {"title": f"{title} #shorts"[:100], "description": desc, "tags": tags}


def generate_title(transcript: str, streamer: str = "", source_title: str = "",
                   log: Logger = default_log) -> dict:
    """{'title', 'description', 'tags'} döner. Her zaman bir sonuç verir."""
    if not os.environ.get("ANTHROPIC_API_KEY") and not os.environ.get("ANTHROPIC_AUTH_TOKEN"):
        return _fallback(transcript, streamer, source_title)
    try:
        import anthropic
    except ImportError:
        return _fallback(transcript, streamer, source_title)

    user = (f"Yayıncı: {streamer or 'bilinmiyor'}\n"
            f"Yayın başlığı: {source_title or 'bilinmiyor'}\n\n"
            f"Klip dökümü:\n\"\"\"\n{(transcript or '').strip()[:4000] or '(konuşma yok)'}\n\"\"\"")
    try:
        client = anthropic.Anthropic()
        resp = client.beta.messages.create(
            model=MODEL,
            max_tokens=2000,
            system=SYSTEM,
            messages=[{"role": "user", "content": user}],
            output_config={"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
        if resp.stop_reason == "refusal":
            raise RuntimeError("model isteği reddetti")
        text = next(b.text for b in resp.content if b.type == "text")
        data = json.loads(text)
    except Exception as e:
        log(f"Claude ile başlık üretilemedi ({e}); basit başlık kullanılıyor.")
        return _fallback(transcript, streamer, source_title)

    title = data["title"].strip()
    if "#shorts" not in title.lower() and len(title) <= 92:
        title += " #shorts"
    desc = data["description"].strip()
    if "#shorts" not in desc.lower():
        desc += "\n#shorts"
    tags = [_clean_tag(t) or t for t in data.get("tags", [])][:15]
    return {"title": title[:100], "description": desc[:4900], "tags": tags}


def ensure_shorts_title(title: str) -> str:
    title = (title or "").strip() or "Efsane an"
    if "#shorts" not in title.lower():
        title = (title[:91] + " #shorts") if len(title) > 91 else title + " #shorts"
    return title[:100]


def apply_to_meta(meta: dict, streamer: Optional[str], source_title: Optional[str], log: Logger) -> dict:
    meta.update(generate_title(meta.get("transcript", ""), streamer or "", source_title or "", log))
    return meta
