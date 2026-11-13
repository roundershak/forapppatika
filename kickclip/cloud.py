"""GitHub Actions (bulut) çalıştırıcısı: bilgisayar gerekmeden klip/uzun video üretip YouTube'a yükler.

Workflow: .github/workflows/kickclip-bulut.yml  (GitHub -> Actions -> KickClip Bulut -> Run workflow)
Ortam değişkenleri workflow girdilerinden gelir; sonuçlar iş özetine ($GITHUB_STEP_SUMMARY) yazılır.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import time

from .utils import fmt_time

PRIVACY = {"ozel-yukle": "private", "liste-disi-yukle": "unlisted", "herkese-acik-yukle": "public"}


def _env(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


def _summary(md: str) -> None:
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write(md + "\n")
    print(md)


def log(msg: str) -> None:
    print(f"{time.strftime('%H:%M:%S')}  {msg}", flush=True)


def main() -> int:
    from . import llm, youtube
    link = _env("KC_LINK")
    tur = _env("KC_TUR", "shorts")
    yukle = _env("KC_YOUTUBE", "ozel-yukle")
    privacy = PRIVACY.get(yukle)
    out_dir = os.path.abspath("bulut_cikti")
    work_dir = os.path.abspath("work")
    if not link:
        print("Kick linki boş.", file=sys.stderr)
        return 2

    if privacy and not youtube.is_authorized():
        _summary("> ⚠️ **YT_TOKEN secret'ı yok**: videolar üretilecek ama YouTube'a yüklenmeyecek. "
                 "Kurulum: README → *Bulutta çalıştırma*.")
        privacy = None
    _summary(f"## KickClip Bulut — {tur}\n\n**Link:** {link}  \n**Claude:** "
             f"{'açık ✓' if llm.available() else 'kapalı (ANTHROPIC_API_KEY secret yok)'}  \n"
             f"**YouTube:** {('yüklenecek: ' + privacy) if privacy else 'yüklenmeyecek'}\n")

    rows = []
    if tur == "shorts":
        from .config import ClipConfig
        from .pipeline import run_pipeline
        cfg = ClipConfig(
            source=link, output_dir=out_dir, work_dir=work_dir,
            max_clips=int(_env("KC_ADET", "6") or 6), clip_length=float(_env("KC_SURE", "30") or 30),
            time_range=_env("KC_ARALIK") or None, selection=_env("KC_SECIM", "tepki"),
            resolution=_env("KC_COZUNURLUK", "1080p"), whisper_model=_env("KC_MODEL", "small"),
        )
        clips = run_pipeline(cfg, log=log)
        for c in clips:
            row = {"ad": c["name"], "an": c["start_hms"], "baslik": c.get("title", ""), "neden": c.get("reason", "")}
            if privacy:
                try:
                    res = youtube.upload_short(c["file"], c.get("title", ""), c.get("description", ""),
                                               c.get("tags", []), privacy, log=log)
                    row["youtube"] = res["url"]
                except Exception as e:
                    row["youtube"] = f"HATA: {e}"
                    log(f"Yükleme hatası: {e}")
            rows.append(row)
    else:
        from .longform import LongConfig, run_longform, upload_section
        manual = _env("KC_ELLE").replace(";", "\n")
        cfg = LongConfig(source=link, output_dir=out_dir, work_dir=work_dir, time_range=_env("KC_ARALIK") or None,
                         min_minutes=float(_env("KC_MIN_DK", "4") or 4), max_minutes=float(_env("KC_MAX_DK", "40") or 40),
                         manual=manual)
        secs = run_longform(cfg, log=log)
        for s in secs:
            row = {"ad": s["name"], "an": f"{s['start_hms']}–{s['end_hms']}", "baslik": s["title"],
                   "neden": s.get("watched", "")}
            if privacy:
                try:
                    res = upload_section(s, work_dir, privacy, log=log)
                    row["youtube"] = res["url"] + ("" if res.get("thumbnail_set", True) else " (kapak ayarlanamadı)")
                except Exception as e:
                    row["youtube"] = f"HATA: {e}"
                    log(f"Yükleme hatası: {e}")
            rows.append(row)

    if not rows:
        _summary("Hiç sonuç çıkmadı.")
        return 0
    _summary("| # | An | Başlık | Neden / izlenen | YouTube |\n|---|---|---|---|---|")
    for r in rows:
        yt = r.get("youtube", "—")
        if yt.startswith("http"):
            yt = f"[aç]({yt})"
        _summary(f"| {r['ad']} | {r['an']} | {r['baslik'].replace('|', '/')} | {r['neden'].replace('|', '/')[:80]} | {yt} |")
    if privacy == "private":
        _summary("\nVideolar **özel** yüklendi. YouTube Studio'dan beğendiklerini *Herkese açık* yapabilirsin: "
                 "https://studio.youtube.com")
    return 0


if __name__ == "__main__":
    sys.exit(main())
