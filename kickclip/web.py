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


@app.get("/api/youtube/status")
def yt_status():
    return jsonify(client_secret=youtube.has_client_secret(), authorized=youtube.is_authorized(),
                   claude_titles=bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")))


@app.get("/media/<run>/<fname>")
def media(run, fname):
    if not (library._safe(run) and library._safe(fname)):
        abort(404)
    return send_from_directory(os.path.join(OUTPUT_DIR, run), fname, conditional=True,
                               as_attachment=request.args.get("dl") == "1")


def serve(host: str = "127.0.0.1", port: int = 7860) -> None:
    threading.Thread(target=_worker, daemon=True).start()
    print(f"KickClip arayüzü: http://{host}:{port}")
    app.run(host=host, port=port, debug=False, threaded=True)
