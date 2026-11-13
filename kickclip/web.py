"""Web arayüzü: link yapıştır → klipleri üret → başlığı düzenle → YouTube Shorts'a yükle."""

from __future__ import annotations

import os
import threading
import time
import traceback
import uuid
from queue import Queue

from flask import Flask, abort, jsonify, render_template, request, send_from_directory

from . import library, youtube
from .config import ClipConfig
from .longform import LongConfig, make_cover, run_longform, source_for, upload_section, export
from .utils import parse_time, fmt_time
from .pipeline import run_pipeline
from .titles import generate_title

app = Flask(__name__)
OUTPUT_DIR = os.path.abspath(ClipConfig().output_dir)
WORK_DIR = os.path.abspath(ClipConfig().work_dir)
JOBS: dict[str, dict] = {}
QUEUE: "Queue[str]" = Queue()
LOCK = threading.Lock()
UPLOADS: dict[str, dict] = {}   # "run/name" -> {status, log, url, error}


# ---------------------------------------------------------------- klip üretimi
def _worker():
    while True:
        jid = QUEUE.get()
        job = JOBS[jid]
        job["status"] = "running"

        def log(msg, job=job):
            with LOCK:
                job["logs"].append(f"{time.strftime('%H:%M:%S')}  {msg}")
                job["logs"] = job["logs"][-400:]

        def prog(p, job=job):
            job["progress"] = round(float(p), 3)

        def on_clip(meta, job=job):
            with LOCK:
                job["clips"] += 1

        try:
            if job.get("kind") == "long":
                run_longform(job["config"], log=log, progress=prog, on_section=on_clip,
                             should_stop=lambda job=job: job["cancel"])
            else:
                run_pipeline(job["config"], log=log, progress=prog, on_clip=on_clip,
                             should_stop=lambda job=job: job["cancel"])
            job["status"] = "cancelled" if job["cancel"] else "done"
        except Exception as e:
            log(f"HATA: {e}")
            traceback.print_exc()
            job["status"] = "error"
            job["error"] = str(e)


def _num(v, cast, default):
    try:
        return cast(v)
    except (TypeError, ValueError):
        return default


@app.get("/")
def index():
    return render_template("index.html", d=ClipConfig())


@app.post("/api/jobs")
def create_job():
    f = request.get_json(force=True) or {}
    d = ClipConfig()
    src = (f.get("source") or "").strip()
    if not src:
        return jsonify(error="Link boş olamaz"), 400
    lang = (f.get("language") or "tr").strip()
    cfg = ClipConfig(
        source=src, output_dir=OUTPUT_DIR, work_dir=WORK_DIR,
        mode=f.get("mode", d.mode),
        clip_length=_num(f.get("clip_length"), float, d.clip_length),
        max_clips=_num(f.get("max_clips"), int, d.max_clips),
        time_range=(f.get("time_range") or "").strip() or None,
        live_minutes=_num(f.get("live_minutes"), float, d.live_minutes),
        download=f.get("download", d.download) if f.get("download") in ("stream", "full") else d.download,
        ai=bool(f.get("ai", True)),
        selection="tepki" if f.get("selection") == "tepki" else "viral",
        resolution="1080p" if f.get("resolution") == "1080p" else "4k",
        cam=(f.get("cam") or "auto").strip(),
        cam_ratio=_num(f.get("cam_ratio"), float, d.cam_ratio),
        cam_zoom=_num(f.get("cam_zoom"), float, d.cam_zoom),
        screen=(f.get("screen") or "crop").strip(),
        subtitles=bool(f.get("subtitles", True)),
        whisper_model=f.get("whisper_model", d.whisper_model),
        language=None if lang.lower() == "auto" else lang,
        font_size=_num(f.get("font_size"), int, d.font_size),
        words_per_line=_num(f.get("words_per_line"), int, d.words_per_line),
        highlight_color=f.get("highlight_color", d.highlight_color),
        titles=bool(f.get("titles", True)),
        streamer=(f.get("streamer") or "").strip() or None,
        intro=bool(f.get("intro", True)),
        intro_hold=_num(f.get("intro_hold"), float, d.intro_hold),
        bell_volume=_num(f.get("bell_volume"), float, d.bell_volume),
    )
    jid = uuid.uuid4().hex[:10]
    JOBS[jid] = {"id": jid, "status": "queued", "progress": 0.0, "logs": [], "clips": 0,
                 "error": None, "cancel": False, "config": cfg, "source": src, "created": time.time()}
    QUEUE.put(jid)
    return jsonify(id=jid)


@app.post("/api/longjobs")
def create_longjob():
    f = request.get_json(force=True) or {}
    src = (f.get("source") or "").strip()
    if not src:
        return jsonify(error="Link boş olamaz"), 400
    d = LongConfig()
    cfg = LongConfig(
        source=src, output_dir=OUTPUT_DIR, work_dir=WORK_DIR,
        time_range=(f.get("time_range") or "").strip() or None,
        min_minutes=_num(f.get("min_minutes"), float, d.min_minutes),
        max_minutes=_num(f.get("max_minutes"), float, d.max_minutes),
        merge_gap=_num(f.get("merge_gap"), float, d.merge_gap),
        split_by_video=bool(f.get("split_by_video", True)),
        manual=f.get("manual") or "",
        streamer=(f.get("streamer") or "").strip() or None,
    )
    jid = uuid.uuid4().hex[:10]
    JOBS[jid] = {"id": jid, "kind": "long", "status": "queued", "progress": 0.0, "logs": [], "clips": 0,
                 "error": None, "cancel": False, "config": cfg, "source": src, "created": time.time()}
    QUEUE.put(jid)
    return jsonify(id=jid)


@app.get("/api/jobs/<jid>")
def get_job(jid):
    job = JOBS.get(jid) or abort(404)
    with LOCK:
        out = {k: v for k, v in job.items() if k != "config"}
        out["logs"] = list(job["logs"])
    return jsonify(out)


@app.post("/api/jobs/<jid>/cancel")
def cancel_job(jid):
    job = JOBS.get(jid) or abort(404)
    job["cancel"] = True
    return jsonify(ok=True)


# ---------------------------------------------------------------- kütüphane
def _public_clip(m: dict) -> dict:
    key = f"{m['run']}/{m['name']}"
    return {
        "key": key, "run": m["run"], "name": m["name"],
        "title": m.get("title", ""), "description": m.get("description", ""),
        "tags": m.get("tags", []), "transcript": m.get("transcript", ""),
        "start_hms": m.get("start_hms", ""), "streamer": m.get("streamer", ""),
        "reason": m.get("reason", ""), "category": m.get("category", ""),
        "video": f"/media/{m['run']}/{m['name']}.mp4",
        "thumb": f"/media/{m['run']}/{m['name']}.jpg" if m.get("thumbnail") else None,
        "youtube": m.get("youtube"), "upload": UPLOADS.get(key),
    }


@app.get("/api/library")
def get_library():
    return jsonify([_public_clip(m) for m in library.list_clips(OUTPUT_DIR)])


def _clip_or_404(run, name) -> dict:
    return library.load_clip(OUTPUT_DIR, run, name) or abort(404)


def _apply_edits(meta: dict, f: dict) -> None:
    if "title" in f:
        meta["title"] = str(f["title"])[:100]
    if "description" in f:
        meta["description"] = str(f["description"])[:4900]
    if "tags" in f:
        tags = f["tags"]
        if isinstance(tags, str):
            tags = [t.strip().lstrip("#") for t in tags.split(",")]
        meta["tags"] = [t for t in tags if t][:30]


@app.post("/api/clips/<run>/<name>")
def update_clip(run, name):
    meta = _clip_or_404(run, name)
    _apply_edits(meta, request.get_json(force=True) or {})
    library.save_clip(OUTPUT_DIR, meta)
    return jsonify(_public_clip(meta))


@app.post("/api/clips/<run>/<name>/retitle")
def retitle_clip(run, name):
    meta = _clip_or_404(run, name)
    meta.update(generate_title(meta.get("transcript", ""), meta.get("streamer", ""),
                               meta.get("source_title", ""), log=lambda m: None))
    library.save_clip(OUTPUT_DIR, meta)
    return jsonify(_public_clip(meta))


@app.post("/api/clips/<run>/<name>/upload")
def upload_clip(run, name):
    meta = _clip_or_404(run, name)
    f = request.get_json(force=True) or {}
    key = f"{run}/{name}"
    if UPLOADS.get(key, {}).get("status") == "running":
        return jsonify(error="Zaten yükleniyor"), 409
    if meta.get("youtube") and not f.get("force"):
        return jsonify(error="Bu klip zaten yüklendi", youtube=meta["youtube"]), 409
    if not youtube.has_client_secret() and not youtube.is_authorized():
        return jsonify(error="YouTube bağlı değil: client_secret.json eksik (README → YouTube kurulumu)"), 400
    _apply_edits(meta, f)
    library.save_clip(OUTPUT_DIR, meta)
    privacy = f.get("privacy", "public")
    publish_at = (f.get("publish_at") or "").strip() or None
    state = {"status": "running", "log": [], "url": None, "error": None}
    UPLOADS[key] = state

    def work():
        try:
            res = youtube.upload_short(meta["video_path"], meta.get("title", ""), meta.get("description", ""),
                                       meta.get("tags", []), privacy, publish_at,
                                       log=lambda m: state["log"].append(m))
            fresh = library.load_clip(OUTPUT_DIR, run, name) or meta
            fresh["youtube"] = {**res, "uploaded_at": time.strftime("%Y-%m-%d %H:%M")}
            library.save_clip(OUTPUT_DIR, fresh)
            state.update(status="done", url=res["url"])
        except Exception as e:
            traceback.print_exc()
            state.update(status="error", error=str(e))

    threading.Thread(target=work, daemon=True).start()
    return jsonify(ok=True)


YT_CONNECT: dict = {"status": "idle", "error": None}


# ---------------------------------------------------------------- uzun video bölümleri
def _public_section(m: dict) -> dict:
    key = f"{m['run']}/{m['name']}"
    thumb = None
    tp = os.path.join(OUTPUT_DIR, m["run"], f"{m['name']}.jpg")
    if os.path.isfile(tp):
        thumb = f"/media/{m['run']}/{m['name']}.jpg?v={int(os.path.getmtime(tp))}"
    mp4 = os.path.join(OUTPUT_DIR, m["run"], f"{m['name']}.mp4")
    return {
        "key": key, "run": m["run"], "name": m["name"], "title": m.get("title", ""),
        "description": m.get("description", ""), "tags": m.get("tags", []),
        "thumb_text": m.get("thumb_text", ""), "watched": m.get("watched", ""),
        "start_hms": fmt_time(m.get("start", 0)), "end_hms": fmt_time(m.get("end", 0)),
        "minutes": round((m.get("end", 0) - m.get("start", 0)) / 60, 1),
        "thumb": thumb, "youtube": m.get("youtube"), "upload": UPLOADS.get(key),
        "file": f"/media/{m['run']}/{m['name']}.mp4" if os.path.isfile(mp4) and not UPLOADS.get(key, {}).get(
            "status") == "running" else None,
    }


@app.get("/api/sections")
def get_sections():
    return jsonify([_public_section(m) for m in library.list_sections(OUTPUT_DIR)])


def _apply_section_edits(meta: dict, f: dict) -> None:
    _apply_edits(meta, f)
    if "thumb_text" in f:
        meta["thumb_text"] = str(f["thumb_text"])[:60]
    try:
        if f.get("start_hms"):
            meta["start"] = parse_time(f["start_hms"])
        if f.get("end_hms"):
            meta["end"] = parse_time(f["end_hms"])
    except ValueError:
        pass
    if meta["end"] <= meta["start"]:
        raise ValueError("Bitiş, başlangıçtan sonra olmalı")


@app.post("/api/sections/<run>/<name>")
def update_section(run, name):
    meta = _clip_or_404(run, name)
    try:
        _apply_section_edits(meta, request.get_json(force=True) or {})
    except ValueError as e:
        return jsonify(error=str(e)), 400
    library.save_clip(OUTPUT_DIR, meta)
    return jsonify(_public_section(meta))


@app.post("/api/sections/<run>/<name>/cover")
def recover_section(run, name):
    meta = _clip_or_404(run, name)
    f = request.get_json(force=True) or {}
    try:
        _apply_section_edits(meta, f)
        if f.get("new_background"):
            # bölüm içinden farklı bir sahne dene
            import random
            meta["background_time"] = meta["start"] + (meta["end"] - meta["start"]) * random.uniform(0.1, 0.9)
            meta["player_box"] = []
        src = source_for(meta, WORK_DIR, log=lambda m: None)
        out = os.path.join(OUTPUT_DIR, run, f"{name}.jpg")
        make_cover(src, meta, meta.get("cam"), out)
        meta["thumbnail"] = out
    except Exception as e:
        traceback.print_exc()
        return jsonify(error=f"Kapak oluşturulamadı: {e}"), 500
    library.save_clip(OUTPUT_DIR, meta)
    return jsonify(_public_section(meta))


def _section_task(run, name, f, do_upload: bool):
    meta = _clip_or_404(run, name)
    key = f"{run}/{name}"
    if UPLOADS.get(key, {}).get("status") == "running":
        return jsonify(error="Bu bölüm için zaten bir işlem sürüyor"), 409
    if do_upload:
        if meta.get("youtube") and not f.get("force"):
            return jsonify(error="Bu bölüm zaten yüklendi", youtube=meta["youtube"]), 409
        if not youtube.is_authorized():
            return jsonify(error="Önce YouTube'u bağla (sağ üstteki buton)"), 400
    try:
        _apply_section_edits(meta, f)
    except ValueError as e:
        return jsonify(error=str(e)), 400
    library.save_clip(OUTPUT_DIR, meta)
    state = {"status": "running", "log": [], "url": None, "error": None,
             "action": "upload" if do_upload else "download"}
    UPLOADS[key] = state
    lg = lambda m: state["log"].append(m)  # noqa: E731

    def work():
        try:
            if do_upload:
                res = upload_section(meta, WORK_DIR, f.get("privacy", "public"),
                                     (f.get("publish_at") or "").strip() or None, log=lg)
                fresh = library.load_clip(OUTPUT_DIR, run, name) or meta
                fresh["youtube"] = {**res, "uploaded_at": time.strftime("%Y-%m-%d %H:%M")}
                library.save_clip(OUTPUT_DIR, fresh)
                state.update(status="done", url=res["url"])
            else:
                src = source_for(meta, WORK_DIR, lg)
                export(src, meta["start"], meta["end"], os.path.join(OUTPUT_DIR, run, f"{name}.mp4"), lg)
                state.update(status="done")
        except Exception as e:
            traceback.print_exc()
            state.update(status="error", error=str(e))

    threading.Thread(target=work, daemon=True).start()
    return jsonify(ok=True)


@app.post("/api/sections/<run>/<name>/upload")
def upload_section_ep(run, name):
    return _section_task(run, name, request.get_json(force=True) or {}, True)


@app.post("/api/sections/<run>/<name>/download")
def download_section_ep(run, name):
    return _section_task(run, name, request.get_json(force=True) or {}, False)


# ---------------------------------------------------------------- uygulama güncelleme
UPDATE: dict = {"status": "idle", "log": [], "error": None, "result": None}


@app.get("/api/update/check")
def update_check():
    from . import updater
    info = updater.check()
    info["state"] = UPDATE
    info["auto_restart"] = os.environ.get("KICKCLIP_LAUNCHER") == "2"
    return jsonify(info)


@app.post("/api/update/apply")
def update_apply():
    from . import updater
    if UPDATE["status"] == "running":
        return jsonify(ok=True)
    if any(j["status"] in ("queued", "running") for j in JOBS.values()) or \
            any(u.get("status") == "running" for u in UPLOADS.values()):
        return jsonify(error="Devam eden bir iş/yükleme var. Bitince güncelle."), 409
    UPDATE.update(status="running", log=[], error=None, result=None)

    def work():
        try:
            res = updater.apply(log=lambda m: UPDATE["log"].append(m))
            UPDATE.update(status="done", result=res)
            if os.environ.get("KICKCLIP_LAUNCHER") == "2":
                # baslat.bat/sh çıkış kodu 3'ü görünce uygulamayı yeni kodla yeniden açar
                threading.Timer(1.5, lambda: os._exit(3)).start()
        except Exception as e:
            traceback.print_exc()
            UPDATE.update(status="error", error=str(e))

    threading.Thread(target=work, daemon=True).start()
    return jsonify(ok=True)


@app.get("/api/system")
def system_status():
    from . import gpu
    return jsonify(gpu.status())


@app.get("/api/youtube/status")
def yt_status():
    return jsonify(client_secret=youtube.has_client_secret(), authorized=youtube.is_authorized(),
                   channel=youtube.channel(), connect=YT_CONNECT,
                   claude_titles=bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")))


@app.post("/api/youtube/connect")
def yt_connect():
    if not youtube.has_client_secret():
        return jsonify(error="client_secret.json bulunamadı. Önce Google Cloud kurulumunu yap (README)."), 400
    if YT_CONNECT["status"] == "running":
        return jsonify(ok=True)
    YT_CONNECT.update(status="running", error=None)

    def work():
        try:
            youtube.connect()
            YT_CONNECT.update(status="done")
        except Exception as e:
            traceback.print_exc()
            YT_CONNECT.update(status="error", error=str(e))

    threading.Thread(target=work, daemon=True).start()
    return jsonify(ok=True)


@app.post("/api/youtube/client_secret")
def yt_client_secret():
    """Google Cloud'dan indirilen OAuth JSON dosyasını tarayıcıdan yükleyip proje klasörüne kaydeder."""
    import json as _json
    f = request.files.get("file")
    if not f:
        return jsonify(error="Dosya seçilmedi"), 400
    try:
        data = _json.loads(f.read().decode("utf-8-sig"))
    except Exception:
        return jsonify(error="Bu bir JSON dosyası değil. Google Cloud'dan indirdiğin client_secret_....json dosyasını seç."), 400
    if "installed" not in data:
        if "web" in data:
            return jsonify(error="Bu 'Web uygulaması' türünde bir istemci. Google Cloud'da istemci türünü "
                                 "'Masaüstü uygulaması' seçerek yeni bir istemci oluşturup onun JSON'unu yükle."), 400
        return jsonify(error="Dosya bir Google OAuth istemci dosyası gibi görünmüyor."), 400
    with open(youtube.CLIENT_SECRET, "w", encoding="utf-8") as out:
        _json.dump(data, out)
    return jsonify(ok=True)


@app.post("/api/youtube/disconnect")
def yt_disconnect():
    youtube.disconnect()
    YT_CONNECT.update(status="idle", error=None)
    return jsonify(ok=True)


@app.get("/media/<run>/<fname>")
def media(run, fname):
    if not (library._safe(run) and library._safe(fname)):
        abort(404)
    return send_from_directory(os.path.join(OUTPUT_DIR, run), fname, conditional=True,
                               as_attachment=request.args.get("dl") == "1")


def _free_port(host: str, port: int) -> int:
    import socket
    for p in range(port, port + 20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind((host, p))
                return p
            except OSError:
                continue
    return port


def serve(host: str = "127.0.0.1", port: int = 7860, open_browser: bool = False) -> None:
    port = _free_port(host, port)
    threading.Thread(target=_worker, daemon=True).start()
    url = f"http://{host}:{port}"
    print("=" * 52)
    print(f"  KickClip hazır:  {url}")
    print("  Tarayıcı açılmazsa bu adresi kendin aç.")
    print("  Kapatmak için bu pencereyi kapat (veya Ctrl+C).")
    print("=" * 52, flush=True)
    if open_browser and not os.environ.get("KICKCLIP_NO_OPEN"):
        import webbrowser
        threading.Timer(1.5, lambda: webbrowser.open(url)).start()
    app.run(host=host, port=port, debug=False, threaded=True)
