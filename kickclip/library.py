"""Üretilmiş klipleri diskten okur/günceller (sunucu yeniden başlasa da klipler kaybolmaz)."""

from __future__ import annotations

import json
import os
import re
from typing import Optional

_SAFE = re.compile(r"^[\w\-.]+$", re.UNICODE)


def _safe(part: str) -> bool:
    return bool(_SAFE.match(part)) and part not in (".", "..")


def clip_json_path(output_dir: str, run: str, name: str) -> Optional[str]:
    if not (_safe(run) and _safe(name)):
        return None
    p = os.path.join(output_dir, run, f"{name}.json")
    return p if os.path.isfile(p) else None


def load_clip(output_dir: str, run: str, name: str) -> Optional[dict]:
    p = clip_json_path(output_dir, run, name)
    if not p:
        return None
    with open(p, encoding="utf-8") as f:
        meta = json.load(f)
    meta["run"], meta["name"] = run, name
    meta["video_path"] = os.path.join(output_dir, run, f"{name}.mp4")
    return meta


def save_clip(output_dir: str, meta: dict) -> None:
    p = clip_json_path(output_dir, meta["run"], meta["name"])
    if not p:
        raise FileNotFoundError("Klip bulunamadı")
    data = {k: v for k, v in meta.items() if k not in ("run", "video_path")}
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, p)


def list_clips(output_dir: str) -> list[dict]:
    out: list[dict] = []
    if not os.path.isdir(output_dir):
        return out
    runs = sorted((d for d in os.listdir(output_dir) if os.path.isdir(os.path.join(output_dir, d))),
                  key=lambda d: os.path.getmtime(os.path.join(output_dir, d)), reverse=True)
    for run in runs:
        rdir = os.path.join(output_dir, run)
        for fn in sorted(os.listdir(rdir)):
            m = re.match(r"^(klip_\d+)\.json$", fn)
            if not m or not os.path.isfile(os.path.join(rdir, m.group(1) + ".mp4")):
                continue
            try:
                meta = load_clip(output_dir, run, m.group(1))
            except (OSError, ValueError):
                continue
            if meta:
                out.append(meta)
    return out
