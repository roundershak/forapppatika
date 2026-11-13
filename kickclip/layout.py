"""Yayıncı kamerasının ve ekran içeriğinin kaynak videodaki konumunu belirler."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np

from .utils import Logger, default_log, parse_rect


@dataclass
class Rect:
    x: int
    y: int
    w: int
    h: int

    def even(self) -> "Rect":
        return Rect(self.x // 2 * 2, self.y // 2 * 2, max(2, self.w // 2 * 2), max(2, self.h // 2 * 2))


def _clamp_rect(cx: float, cy: float, w: float, h: float, W: int, H: int) -> Rect:
    w, h = min(w, W), min(h, H)
    x = min(max(0.0, cx - w / 2), W - w)
    y = min(max(0.0, cy - h / 2), H - h)
    return Rect(int(x), int(y), int(w), int(h)).even()


def _rect_from_spec(spec: str, W: int, H: int) -> Optional[Rect]:
    vals = parse_rect(spec)
    if not vals:
        return None
    x, y, w, h = vals
    if max(vals) <= 1.0:  # oran olarak verilmiş
        x, y, w, h = x * W, y * H, w * W, h * H
    return Rect(int(x), int(y), int(w), int(h)).even()


def detect_face_region(path: str, duration: float, start: float = 0.0, end: Optional[float] = None,
                       samples: int = 24, log: Logger = default_log) -> Optional[tuple[float, float, float, float]]:
    """Videodan örnek kareler alıp sabit duran yüzü (webcam) bulur. (cx, cy, fw, fh) döner."""
    try:
        import cv2
    except ImportError:
        log("OpenCV yüklü değil, kamera otomatik bulunamıyor.")
        return None

    cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    alt = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_alt2.xml")
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        return None
    end = end if end is not None else duration
    span = max(1.0, end - start)
    dets: list[tuple[float, float, float, float]] = []
    W = H = 0
    for i in range(samples):
        t = start + span * (i + 0.5) / samples
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ok, frame = cap.read()
        if not ok:
            continue
        H, W = frame.shape[:2]
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.equalizeHist(gray)
        min_side = max(24, int(H * 0.04))
        faces = []
        for cc in (cascade, alt):
            faces = cc.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=6, minSize=(min_side, min_side))
            if len(faces):
                break
        for (x, y, w, h) in faces:
            dets.append((x + w / 2, y + h / 2, float(w), float(h)))
    cap.release()
    if not dets or W == 0:
        return None

    # Kümeleme: webcam sabit durduğu için en çok tekrar eden konumu al
    arr = np.array(dets)
    best_idx, best_cnt = 0, 0
    for i, (cx, cy, fw, fh) in enumerate(arr):
        near = np.hypot(arr[:, 0] - cx, arr[:, 1] - cy) < max(fw, fh) * 0.8
        if near.sum() > best_cnt:
            best_cnt, best_idx = int(near.sum()), i
    cx, cy, fw, fh = arr[best_idx]
    cluster = arr[np.hypot(arr[:, 0] - cx, arr[:, 1] - cy) < max(fw, fh) * 0.8]
    if best_cnt < max(2, samples * 0.2):
        log(f"Yüz yeterince tutarlı bulunamadı ({best_cnt}/{samples} kare).")
        return None
    med = np.median(cluster, axis=0)
    log(f"Kamera bulundu: yüz merkezi ({med[0]:.0f},{med[1]:.0f}), {best_cnt}/{samples} karede.")
    return float(med[0]), float(med[1]), float(med[2]), float(med[3])


def resolve_cam_rect(spec: str, W: int, H: int, panel_aspect: float, face=None,
                     cam_size: float = 0.28, cam_zoom: float = 3.2) -> Optional[Rect]:
    """Üst panel için kaynak videodan kırpılacak kamera alanı. None => kamera yok."""
    spec = (spec or "auto").strip().lower()
    if spec == "none":
        return None
    custom = _rect_from_spec(spec, W, H)
    if custom:
        return custom
    if spec == "auto":
        if face is None:
            return None
        cx, cy, fw, fh = face
        w = fw * cam_zoom
        h = w / panel_aspect
        # yüz kırpmanın biraz üst kısmında dursun (omuzlar da görünsün)
        return _clamp_rect(cx, cy + h * 0.08, w, h, W, H)
    # köşe presetleri
    w = W * cam_size
    h = w / panel_aspect
    corners = {
        "top-left": (w / 2, h / 2),
        "top-right": (W - w / 2, h / 2),
        "bottom-left": (w / 2, H - h / 2),
        "bottom-right": (W - w / 2, H - h / 2),
    }
    if spec not in corners:
        raise ValueError(f"Bilinmeyen kamera ayarı: {spec}")
    cx, cy = corners[spec]
    return _clamp_rect(cx, cy, w, h, W, H)


def resolve_screen_rect(spec: str, W: int, H: int, panel_aspect: float, zoom: float = 1.0,
                        cam: Optional[Rect] = None) -> tuple[str, Rect]:
    """Alt panel için kırpılacak ekran alanı. Dönüş: (mod, rect) mod = crop|fit|custom."""
    spec = (spec or "crop").strip().lower()
    custom = _rect_from_spec(spec, W, H)
    if custom:
        return "custom", custom
    if spec == "fit":
        return "fit", Rect(0, 0, W, H)
    # crop: panel oranında, ortadan
    h = H / max(zoom, 1.0)
    w = h * panel_aspect
    if w > W:
        w = W
        h = w / panel_aspect
    cx, cy = W / 2, H / 2
    # kamera alanı ortalanmış kırpmaya giriyorsa, kırpmayı kameradan uzağa kaydır
    if cam is not None:
        r = _clamp_rect(cx, cy, w, h, W, H)
        overlap_x = min(r.x + r.w, cam.x + cam.w) - max(r.x, cam.x)
        overlap_y = min(r.y + r.h, cam.y + cam.h) - max(r.y, cam.y)
        if overlap_x > 0 and overlap_y > 0 and overlap_x < r.w * 0.5:
            cam_cx = cam.x + cam.w / 2
            cx = cx + overlap_x if cam_cx < cx else cx - overlap_x
    return "crop", _clamp_rect(cx, cy, w, h, W, H)
