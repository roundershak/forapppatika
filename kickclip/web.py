"""Basit web arayüzü: link yapıştır, ayarla, klipleri izle/indir."""

from __future__ import annotations

import os
import threading
import time
import traceback
import uuid
from queue import Queue

from flask import Flask, abort, jsonify, render_template, request, send_file

from .config import ClipConfig
from .pipeline import run_pipeline

app = Flask(__name__)
JOBS: dict[str, dict] = {}
QUEUE: "Queue[str]" = Queue()
LOCK = threading.Lock()
FILES: dict[str, str] = {}  # id -> mutlak yol (sadece üretilen dosyalar servis edilir)


def _register(path: str | None) -> str | None:
    if not path:
        return None
    fid = uuid.uuid4().hex
    FILES[fid] = path
    return fid


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
            c = dict(meta)
            c["video_id"] = _register(meta["file"])
            c["thumb_id"] = _register(meta.get("thumbnail"))
            with LOCK:
                job["clips"].append(c)

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
        source=src,
        output_dir=os.path.abspath(d.output_dir), work_dir=os.path.abspath(d.work_dir),
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
        intro=bool(f.get("intro", True)),
        intro_hold=_num(f.get("intro_hold"), float, d.intro_hold),
        bell_volume=_num(f.get("bell_volume"), float, d.bell_volume),
    )
    jid = uuid.uuid4().hex[:10]
    JOBS[jid] = {"id": jid, "status": "queued", "progress": 0.0, "logs": [], "clips": [],
                 "error": None, "cancel": False, "config": cfg, "source": src, "created": time.time()}
    QUEUE.put(jid)
    return jsonify(id=jid)


def _public(job: dict) -> dict:
    with LOCK:
        out = {k: v for k, v in job.items() if k != "config"}
        out["logs"], out["clips"] = list(job["logs"]), list(job["clips"])
        return out


@app.get("/api/jobs")
def list_jobs():
    jobs = sorted(JOBS.values(), key=lambda j: j["created"], reverse=True)
    return jsonify([{"id": j["id"], "status": j["status"], "source": j["source"],
                     "progress": j["progress"], "clips": len(j["clips"])} for j in jobs])


@app.get("/api/jobs/<jid>")
def get_job(jid):
    job = JOBS.get(jid) or abort(404)
    return jsonify(_public(job))


@app.post("/api/jobs/<jid>/cancel")
def cancel_job(jid):
    job = JOBS.get(jid) or abort(404)
    job["cancel"] = True
    return jsonify(ok=True)


@app.get("/files/<fid>")
def files(fid):
    path = FILES.get(fid) or abort(404)
    if not os.path.isfile(path):
        abort(404)
    return send_file(path, as_attachment=request.args.get("dl") == "1",
                     download_name=os.path.basename(path), conditional=True)


def serve(host: str = "127.0.0.1", port: int = 7860) -> None:
    threading.Thread(target=_worker, daemon=True).start()
    print(f"KickClip arayüzü: http://{host}:{port}")
    app.run(host=host, port=port, debug=False, threaded=True)
