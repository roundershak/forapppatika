"""Uygulama içinden güncelleme: GitHub'daki son sürümü indirir, kod dosyalarını değiştirir.

Kişisel dosyalara dokunulmaz: .env, client_secret*.json, youtube_token.json, youtube_channel.json,
output/, work/, .venv/ ve assets/ içine senin eklediğin dosyalar (zil sesi, yazı tipi) korunur.
"""

from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from typing import Optional

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.environ.get("KICKCLIP_REPO", "roundershak/forapppatika")
BRANCH = os.environ.get("KICKCLIP_BRANCH", "claude/kick-auto-clip-generator-925yij")
VERSION_FILE = os.path.join(ROOT, ".surum")

PROTECTED_DIRS = {".venv", "venv", "output", "work", ".git", "__pycache__"}
PROTECTED_FILES = {".env", "youtube_token.json", "youtube_channel.json", ".surum"}


def _get(url: str, timeout: int = 30) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "kickclip-updater", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def current() -> Optional[dict]:
    try:
        with open(VERSION_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def latest() -> dict:
    data = json.loads(_get(f"https://api.github.com/repos/{REPO}/commits/{BRANCH}"))
    return {"sha": data["sha"], "date": data["commit"]["committer"]["date"],
            "message": data["commit"]["message"].splitlines()[0]}


def check() -> dict:
    cur = current()
    try:
        lat = latest()
    except Exception as e:
        return {"available": False, "error": f"GitHub'a ulaşılamadı: {e}", "current": cur}
    available = not cur or cur.get("sha") != lat["sha"]
    return {"available": available, "current": cur, "latest": lat}


def _protected(rel: str) -> bool:
    parts = rel.replace("\\", "/").split("/")
    if parts[0] in PROTECTED_DIRS:
        return True
    name = parts[-1]
    if name in PROTECTED_FILES or (name.startswith("client_secret") and name.endswith(".json")):
        return True
    # assets/ altına kullanıcının eklediği dosyalar korunur (depoda olanlar güncellenir)
    return False


def apply(log=print) -> dict:
    """Son sürümü indirip uygular. Dönüş: {sha, changed_files, requirements_changed}"""
    lat = latest()
    log("Yeni sürüm indiriliyor...")
    data = _get(f"https://codeload.github.com/{REPO}/zip/{lat['sha']}", timeout=120)
    zf = zipfile.ZipFile(io.BytesIO(data))
    prefix = zf.namelist()[0].split("/")[0] + "/"
    req_path = os.path.join(ROOT, "requirements.txt")
    old_req = open(req_path, "rb").read() if os.path.exists(req_path) else b""
    changed = 0
    for info in zf.infolist():
        if info.is_dir() or not info.filename.startswith(prefix):
            continue
        rel = info.filename[len(prefix):]
        if not rel or _protected(rel):
            continue
        dest = os.path.join(ROOT, *rel.split("/"))
        content = zf.read(info)
        if os.path.exists(dest):
            with open(dest, "rb") as f:
                if f.read() == content:
                    continue
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        tmp = dest + ".yeni"
        with open(tmp, "wb") as f:
            f.write(content)
        os.replace(tmp, dest)
        changed += 1
    req_changed = (open(req_path, "rb").read() if os.path.exists(req_path) else b"") != old_req
    if req_changed:
        log("Yeni paketler kuruluyor...")
        r = subprocess.run([sys.executable, "-m", "pip", "install", "-r", req_path],
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        if r.returncode != 0:
            raise RuntimeError("Paket kurulumu başarısız:\n" + r.stdout[-800:])
        stamp = os.path.join(ROOT, ".venv", "req.stamp")
        if os.path.isdir(os.path.dirname(stamp)):
            shutil.copyfile(req_path, stamp)
    with open(VERSION_FILE, "w", encoding="utf-8") as f:
        json.dump(lat, f, ensure_ascii=False)
    log(f"Güncellendi: {changed} dosya değişti.")
    return {"sha": lat["sha"], "message": lat["message"], "changed_files": changed,
            "requirements_changed": req_changed}
