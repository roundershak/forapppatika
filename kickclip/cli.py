"""Komut satırı arayüzü.

Örnek:
    python -m kickclip https://kick.com/kanal/videos/xxxx --count 8 --length 30
    python -m kickclip web            # web arayüzünü başlatır
    python -m kickclip upload output/.../klip_01.mp4 --privacy public
"""

from __future__ import annotations

import argparse
import sys

from .config import ClipConfig


def build_parser() -> argparse.ArgumentParser:
    d = ClipConfig()
    p = argparse.ArgumentParser(prog="kickclip", description="Kick yayınlarından otomatik dikey klip üretici")
    p.add_argument("source", help="Kick linki (canlı/VOD/klip) veya yerel video dosyası. 'web' => arayüz")
    p.add_argument("-o", "--output", default=d.output_dir, help="çıktı klasörü")
    p.add_argument("--work", default=d.work_dir, help="geçici/indirme klasörü")
    p.add_argument("--mode", choices=["highlights", "split"], default=d.mode,
                   help="highlights: en hareketli anlar, split: sırayla parçala")
    p.add_argument("-n", "--count", type=int, default=d.max_clips, help="en fazla klip sayısı")
    p.add_argument("-l", "--length", type=float, default=d.clip_length, help="klip süresi (sn)")
    p.add_argument("--range", dest="time_range", default=None, help="sadece bu aralık, ör. 1:00:00-2:00:00")
    p.add_argument("--live-minutes", type=float, default=d.live_minutes, help="canlı yayında kayıt süresi (dk)")
    p.add_argument("--max-height", type=int, default=d.max_height)
    p.add_argument("--download", choices=["stream", "full"], default=d.download,
                   help="stream: yayını indirmeden akıştan analiz et, sadece klipleri çek (varsayılan); full: tümünü indir")
    p.add_argument("--select", choices=["viral", "tepki"], default=d.selection,
                   help="viral: tüm yayını yazıya döküp önemli/viral anları seç (varsayılan); tepki: sadece gülme/bağırma anları (hızlı)")
    p.add_argument("--no-ai", action="store_true", help="Whisper+Claude değerlendirmesini kapat (sadece ses analizi)")
    p.add_argument("--candidates", type=int, default=0, help="AI'ın inceleyeceği aday sayısı (0=otomatik)")
    p.add_argument("--fixed-length", action="store_true", help="klip süresini sabit tut (AI esnetmesin)")

    g = p.add_argument_group("yerleşim")
    g.add_argument("--cam", default=d.cam,
                   help="auto | top-left | top-right | bottom-left | bottom-right | none | x,y,w,h (piksel ya da 0-1 oran)")
    g.add_argument("--cam-ratio", type=float, default=d.cam_ratio, help="üst kamera panelinin yükseklik oranı")
    g.add_argument("--cam-size", type=float, default=d.cam_size, help="köşe preset'inde kamera genişliği oranı")
    g.add_argument("--cam-zoom", type=float, default=d.cam_zoom, help="auto modda yüz etrafı genişlik çarpanı")
    g.add_argument("--screen", default=d.screen, help="crop | fit | x,y,w,h")
    g.add_argument("--screen-zoom", type=float, default=d.screen_zoom)

    s = p.add_argument_group("altyazı")
    s.add_argument("--no-subs", action="store_true", help="altyazı ekleme")
    s.add_argument("--model", default=d.whisper_model, help="whisper modeli: tiny/base/small/medium/large-v3")
    s.add_argument("--lang", default=d.language, help="dil kodu (tr, en...) ya da 'auto'")
    s.add_argument("--device", default=d.device, help="auto/cpu/cuda")
    s.add_argument("--font", default=d.font)
    s.add_argument("--font-size", type=int, default=d.font_size)
    s.add_argument("--words", type=int, default=d.words_per_line, help="ekranda aynı anda kelime sayısı")
    s.add_argument("--color", default=d.highlight_color, help="vurgulanan kelime rengi")
    s.add_argument("--sub-pos", type=float, default=d.sub_position, help="altyazı konumu 0-1")

    t = p.add_argument_group("youtube başlığı")
    t.add_argument("--no-titles", action="store_true", help="Shorts başlığı üretme")
    t.add_argument("--streamer", default=None, help="hashtag'ler için yayıncı adı")

    i = p.add_argument_group("giriş efekti")
    i.add_argument("--no-intro", action="store_true", help="zil + blur girişini kapat")
    i.add_argument("--bell", default=None, help="kendi zil sesi dosyan")
    i.add_argument("--bell-volume", type=float, default=d.bell_volume)
    i.add_argument("--hold", type=float, default=d.intro_hold, help="başta bulanık kalma süresi (sn)")
    i.add_argument("--fade", type=float, default=d.intro_fade, help="blur kalkma süresi (sn)")
    i.add_argument("--blur", type=float, default=d.blur_strength)

    e = p.add_argument_group("kodlama")
    e.add_argument("--resolution", choices=["4k", "1080p"], default=d.resolution,
                   help="çıktı çözünürlüğü: 4k = 2160x3840 (varsayılan), 1080p = 1080x1920")
    e.add_argument("--crf", type=int, default=d.crf)
    e.add_argument("--preset", default=d.preset)
    e.add_argument("--fps", type=int, default=d.fps)
    return p


def args_to_config(a: argparse.Namespace) -> ClipConfig:
    return ClipConfig(
        source=a.source, output_dir=a.output, work_dir=a.work, max_height=a.max_height,
        time_range=a.time_range, live_minutes=a.live_minutes, download=a.download, ai=not a.no_ai, selection=a.select,
        ai_candidates=a.candidates, flex_length=not a.fixed_length, mode=a.mode, clip_length=a.length,
        max_clips=a.count, cam=a.cam, cam_ratio=a.cam_ratio, cam_size=a.cam_size, cam_zoom=a.cam_zoom,
        screen=a.screen, screen_zoom=a.screen_zoom, subtitles=not a.no_subs, whisper_model=a.model,
        language=None if (a.lang or "").lower() in ("", "auto") else a.lang, device=a.device,
        font=a.font, font_size=a.font_size, words_per_line=a.words, highlight_color=a.color,
        sub_position=a.sub_pos, titles=not a.no_titles, streamer=a.streamer, intro=not a.no_intro, bell_file=a.bell, bell_volume=a.bell_volume,
        intro_hold=a.hold, intro_fade=a.fade, blur_strength=a.blur, crf=a.crf, resolution=a.resolution, preset=a.preset, fps=a.fps,
    )


def upload_main(argv: list[str]) -> None:
    """python -m kickclip upload <klip.mp4 | klip.json | klasör> ... [--privacy] [--at]"""
    import glob
    import json
    import os

    from .youtube import upload_short

    p = argparse.ArgumentParser(prog="kickclip upload", description="Klipleri YouTube Shorts olarak yükle")
    p.add_argument("paths", nargs="+", help="klip .mp4/.json dosyaları veya klip klasörü (yüklenmemiş hepsi)")
    p.add_argument("--privacy", default="public", choices=["public", "unlisted", "private"])
    p.add_argument("--at", default=None, help="zamanlanmış yayın, ör. 2026-11-20T18:00:00+03:00")
    p.add_argument("--title", default=None, help="başlığı geçersiz kıl (tek klipte)")
    p.add_argument("--force", action="store_true", help="daha önce yüklenmişleri de yükle")
    a = p.parse_args(argv)

    jsons: list[str] = []
    for path in a.paths:
        if os.path.isdir(path):
            jsons += sorted(glob.glob(os.path.join(path, "klip_*.json")))
        else:
            jsons.append(os.path.splitext(path)[0] + ".json")
    for jp in jsons:
        with open(jp, encoding="utf-8") as f:
            meta = json.load(f)
        if meta.get("youtube") and not a.force:
            print(f"Atlandı (zaten yüklü): {meta['name']} -> {meta['youtube']['url']}")
            continue
        title = a.title or meta.get("title") or meta.get("name")
        res = upload_short(os.path.splitext(jp)[0] + ".mp4", title, meta.get("description", ""),
                           meta.get("tags", []), a.privacy, a.at)
        meta["youtube"] = res
        with open(jp, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)


def _load_env() -> None:
    """Proje klasöründeki .env dosyasını okur (ör. ANTHROPIC_API_KEY=...). Zaten tanımlı olanı ezmez."""
    import os
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(root, ".env")
    if not os.path.isfile(path):
        return
    with open(path, encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip().strip('"').strip("'")
            if k and v and not os.environ.get(k):
                os.environ[k] = v


def main(argv: list[str] | None = None) -> None:
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] == "upload":
        try:
            upload_main(argv[1:])
        except Exception as e:
            print(f"HATA: {e}", file=sys.stderr)
            sys.exit(1)
        return
    _load_env()
    if argv and argv[0] == "guncelle":
        from . import updater
        info = updater.check()
        if not info.get("available"):
            print(info.get("error") or "Zaten en güncel sürüm.")
            return
        res = updater.apply()
        print(f"Güncellendi: {res['message']} ({res['changed_files']} dosya)")
        return
    if argv and argv[0] == "uzun":
        lp = argparse.ArgumentParser(prog="kickclip uzun", description="Video izleme bölümlerini bul (uzun video)")
        lp.add_argument("source")
        lp.add_argument("--range", dest="time_range", default=None)
        lp.add_argument("--min", type=float, default=4.0, help="en kısa bölüm (dk)")
        lp.add_argument("--max", type=float, default=40.0, help="en uzun bölüm (dk)")
        lp.add_argument("--manual", default="", help="elle aralıklar, ör. '1:02:00-1:25:00 Madara Olduk'")
        lp.add_argument("--streamer", default=None)
        lp.add_argument("-o", "--output", default="output")
        la = lp.parse_args(argv[1:])
        from .longform import LongConfig, run_longform
        try:
            secs = run_longform(LongConfig(source=la.source, output_dir=la.output, time_range=la.time_range,
                                           min_minutes=la.min, max_minutes=la.max, manual=la.manual.replace(";", "\n"),
                                           streamer=la.streamer))
        except Exception as e:
            print(f"HATA: {e}", file=sys.stderr)
            sys.exit(1)
        for s_ in secs:
            print(f"  {s_['start_hms']}-{s_['end_hms']}  {s_['title']}")
        print("\nYüklemek için web arayüzünü kullan: python -m kickclip web")
        return
    if argv and argv[0] == "web":
        from .web import serve
        nums = [a for a in argv[1:] if a.isdigit()]
        serve(port=int(nums[0]) if nums else 7860, open_browser="--open" in argv)
        return
    args = build_parser().parse_args(argv)
    from .pipeline import run_pipeline
    try:
        clips = run_pipeline(args_to_config(args))
    except KeyboardInterrupt:
        print("\nİptal edildi.")
        sys.exit(130)
    except Exception as e:
        print(f"HATA: {e}", file=sys.stderr)
        sys.exit(1)
    for c in clips:
        print(f"  {c['name']}  [{c['start_hms']}]  {c['file']}")
        if c.get("title"):
            print(f"      Başlık: {c['title']}")
    if clips:
        print("\nYüklemek için: python -m kickclip upload <klip.mp4>  (veya web arayüzü)")


if __name__ == "__main__":
    main()
