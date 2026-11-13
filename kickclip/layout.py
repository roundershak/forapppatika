"""Yayıncı kamerasının ve ekran içeriğinin kaynak videodaki konumunu belirler."""

from __future__ import annotations

import os
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


def detect_face_region(frames: list, log: Logger = default_log) -> Optional[tuple[float, float, float, float]]:
    """Örnek karelerde sabit duran yüzü (webcam) bulur. (cx, cy, fw, fh) döner."""
    try:
        import cv2
    except ImportError:
        log("OpenCV yüklü değil, kamera otomatik bulunamıyor.")
        return None
    frames = [f for f in frames if f is not None]
    if not frames:
        return None
    cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    alt = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_alt2.xml")
    dets: list[tuple[float, float, float, float]] = []
    for frame in frames:
        H = frame.shape[0]
        gray = cv2.equalizeHist(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY))
        min_side = max(24, int(H * 0.04))
        faces = []
        for cc in (cascade, alt):
            faces = cc.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=6, minSize=(min_side, min_side))
            if len(faces):
                break
        for (x, y, w, h) in faces:
            dets.append((x + w / 2, y + h / 2, float(w), float(h)))
    samples = len(frames)
    if not dets:
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


# ----------------------------------------------------------------------------- klip bazlı sahne analizi
YUNET_URL = ("https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/"
             "face_detection_yunet/face_detection_yunet_2023mar.onnx")
YUNET_SHA = "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4"
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
YUNET_PATH = os.path.join(_ROOT, "assets", "models", "face_detection_yunet_2023mar.onnx")


def _yunet():
    """Yapay zekâ tabanlı yüz algılayıcı (YuNet, 230 KB). İlk kullanımda indirilir; olmazsa None."""
    if hasattr(_yunet, "det"):
        return _yunet.det
    _yunet.det = None
    try:
        import cv2
        import hashlib
        if not os.path.isfile(YUNET_PATH):
            import urllib.request
            os.makedirs(os.path.dirname(YUNET_PATH), exist_ok=True)
            data = urllib.request.urlopen(YUNET_URL, timeout=60).read()
            if hashlib.sha256(data).hexdigest() != YUNET_SHA:
                raise RuntimeError("model dosyası doğrulanamadı")
            with open(YUNET_PATH, "wb") as f:
                f.write(data)
        _yunet.det = cv2.FaceDetectorYN.create(YUNET_PATH, "", (320, 320), 0.75, 0.3, 5000)
    except Exception as e:  # internet yoksa vs. -> Haar'a düş
        default_log(f"YuNet yüz algılayıcı kullanılamıyor ({e}); basit algılayıcı kullanılacak.")
    return _yunet.det


def _faces(frame) -> list[tuple[float, float, float, float]]:
    """Karedeki yüzler (cx, cy, w, h). Kalabalık/küçük sahte yüzler elenir."""
    import cv2
    H, W = frame.shape[:2]
    min_side = max(28, int(W * 0.02))
    det = _yunet()
    if det is not None:
        det.setInputSize((W, H))
        _, faces = det.detect(frame)
        out = []
        for f in (faces if faces is not None else []):
            x, y, w, h, score = float(f[0]), float(f[1]), float(f[2]), float(f[3]), float(f[14])
            if score >= 0.8 and w >= min_side:
                out.append((x + w / 2, y + h / 2, w, h))
        return out
    if not hasattr(_faces, "cc"):
        _faces.cc = [cv2.CascadeClassifier(cv2.data.haarcascades + n) for n in
                     ("haarcascade_frontalface_default.xml", "haarcascade_frontalface_alt2.xml")]
    gray = cv2.equalizeHist(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY))
    for cc in _faces.cc:
        f = cc.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=6, minSize=(min_side, min_side))
        if len(f):
            return [(x + w / 2, y + h / 2, float(w), float(h)) for (x, y, w, h) in f]
    return []


def find_cam_box(frame, face) -> Optional[Rect]:
    """Yüzün çevresindeki webcam penceresinin (overlay) sınırlarını kenar çizgilerinden bulur."""
    import cv2
    H, W = frame.shape[:2]
    cx, cy, fw, fh = face
    gray = cv2.GaussianBlur(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), (3, 3), 0).astype(np.float32)
    gx = np.abs(cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3))
    gy = np.abs(cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3))
    span_y = (max(0, int(cy - 1.5 * fh)), min(H, int(cy + 1.5 * fh)))
    span_x = (max(0, int(cx - 1.5 * fw)), min(W, int(cx + 1.5 * fw)))

    def line_strength(axis_vals):
        return axis_vals

    col = gx[span_y[0]:span_y[1], :].mean(axis=0)     # dikey çizgiler
    row = gy[:, span_x[0]:span_x[1]].mean(axis=1)     # yatay çizgiler
    # sürekli çizgi: o kolondaki/satırdaki gradyanın çoğu yüksek olmalı
    colc = (gx[span_y[0]:span_y[1], :] > 40).mean(axis=0)
    rowc = (gy[:, span_x[0]:span_x[1]] > 40).mean(axis=1)

    def pick(scores, cont, lo, hi, prefer_near):
        lo, hi = max(0, int(lo)), min(len(scores), int(hi))
        if hi - lo < 2:
            return None
        cand = [i for i in range(lo, hi) if cont[i] > 0.6 and scores[i] > 20]
        if not cand:
            return None
        return min(cand, key=lambda i: abs(i - prefer_near))

    left = pick(col, colc, cx - 6 * fw, cx - 1.2 * fw, cx - 1.2 * fw)
    right = pick(col, colc, cx + 1.2 * fw, cx + 6 * fw, cx + 1.2 * fw)
    top = pick(row, rowc, cy - 5 * fh, cy - 1.0 * fh, cy - 1.0 * fh)
    bottom = pick(row, rowc, cy + 1.0 * fh, cy + 6 * fh, cy + 1.0 * fh)
    # kenar kareye dayanıyorsa çizgi olmayabilir: çerçeve kenarını kabul et
    if left is None and cx - 6 * fw <= 0:
        left = 0
    if right is None and cx + 6 * fw >= W:
        right = W
    if top is None and cy - 5 * fh <= 0:
        top = 0
    if bottom is None and cy + 6 * fh >= H:
        bottom = H
    if None in (left, right, top, bottom):
        return None
    w, h = right - left, bottom - top
    if not (2.2 * fw <= w <= 11 * fw and 2.0 * fh <= h <= 9 * fh and 0.6 <= w / h <= 2.6):
        return None
    if h > w * 0.8:  # webcam genelde 16:9; alt çizgi büyük ihtimalle başka bir panele ait (chat vb.)
        h = w * 0.5625
        top = max(top, min(cy - h * 0.45, bottom - h))
        bottom = top + h
    return Rect(int(left) + 2, int(top) + 2, int(w) - 4, int(h) - 4).even()


def analyze_scene(frames: list, log: Logger = default_log) -> tuple[str, Optional[tuple], Optional[Rect]]:
    """Klipten örnek karelerle sahne türünü belirler.
    Dönüş: (tür, yüz(cx,cy,fw,fh), kamera_penceresi)
      cam     -> köşede webcam penceresi (üst kamera / alt ekran düzeni)
      fullcam -> kamera tüm ekranı kaplıyor (IRL)  -> kişinin etrafından 9:16 kırp
      group   -> birden çok kamera (Discord vb.)    -> tüm ekran, bulanık arka plan
      none    -> yüz yok                            -> tüm ekran, bulanık arka plan
    """
    frames = [f for f in frames if f is not None]
    if not frames:
        return "none", None, None
    H, W = frames[0].shape[:2]
    n = len(frames)
    per = [_faces(f) for f in frames]
    allf = [(i, d) for i, ds in enumerate(per) for d in ds]
    if not allf:
        return "none", None, None
    clusters: list[dict] = []
    for i, (cx, cy, fw, fh) in allf:
        for c in clusters:
            if np.hypot(c["cx"] - cx, c["cy"] - cy) < max(c["fw"], fw) * 0.9:
                c["d"].append((cx, cy, fw, fh)); c["f"].add(i)
                break
        else:
            clusters.append({"cx": cx, "cy": cy, "fw": fw, "d": [(cx, cy, fw, fh)], "f": {i}})
    need = max(2, int(np.ceil(n * 0.5))) if n >= 2 else 1
    strong_need = max(2, int(np.ceil(n * 0.75))) if n >= 2 else 1
    for c in clusters:
        c["size"] = float(np.median([d[2] for d in c["d"]]))
    stable = [c for c in clusters if len(c["f"]) >= need]
    strong = [c for c in clusters if len(c["f"]) >= strong_need]
    # grup görüşmesi: en az 3 yüz neredeyse tüm karelerde aynı yerde ve benzer boyutta (Discord ızgarası)
    if len(strong) >= 3:
        sizes = sorted(c["size"] for c in strong)
        if sizes[-1] / max(1.0, sizes[0]) <= 2.2:
            return "group", None, None
    big = [d for _, d in allf if d[2] >= 0.045 * W]
    if not stable:
        if len({i for i, d in allf if d[2] >= 0.045 * W}) >= need:
            med = tuple(np.median(np.array(big), axis=0))
            return "fullcam", med, None
        return "none", None, None
    # yayıncının kamerası: en sürekli görünen yüz (kayan sayfadaki/videodaki yüzler gelip gider);
    # eşitlikte daha büyük olan
    pool = strong or stable
    best = max(pool, key=lambda c: (len(c["f"]), c["size"]))
    face = tuple(float(v) for v in np.median(np.array(best["d"]), axis=0))
    if face[2] >= 0.06 * W:
        return "fullcam", face, None
    boxes = [b for b in (find_cam_box(f, face) for f in frames) if b is not None]
    box = None
    if boxes:
        arr = np.array([[b.x, b.y, b.w, b.h] for b in boxes])
        m = np.median(arr, axis=0)
        box = Rect(int(m[0]), int(m[1]), int(m[2]), int(m[3])).even()
    return "cam", face, box


def cam_crop(face, box: Optional[Rect], W: int, H: int, aspect: float, cam_zoom: float = 4.5) -> Rect:
    """Üst panel için kamera kırpması. Pencere sınırı biliniyorsa onun içinde kalır."""
    cx, cy, fw, fh = face
    if box is not None:
        h = box.h
        w = h * aspect
        if w > box.w:
            w = box.w
            h = w / aspect
        x = min(max(box.x, cx - w / 2), box.x + box.w - w)
        y = min(max(box.y, cy - h * 0.45), box.y + box.h - h)
        return Rect(int(x), int(y), int(w), int(h)).even()
    return resolve_cam_rect("auto", W, H, aspect, face, cam_zoom=cam_zoom)


def plan_layout(kind: str, face, box, W: int, H: int, top_aspect: float, bot_aspect: float,
                screen_spec: str = "crop", screen_zoom: float = 1.0, cam_zoom: float = 4.5):
    """Sahne türüne göre (cam, screen_mode, screen) döndürür."""
    if kind == "cam" and face is not None:
        cam = cam_crop(face, box, W, H, top_aspect, cam_zoom)
        mode, screen = resolve_screen_rect(screen_spec, W, H, bot_aspect, screen_zoom, box or cam)
        return cam, mode, screen
    if kind == "fullcam" and face is not None:
        # kamera tüm ekranda: kişinin etrafından dikey (9:16) kırp
        w = H * 9 / 16
        return None, "custom", _clamp_rect(face[0], H / 2, w, H, W, H)
    mode, screen = resolve_screen_rect("fit" if screen_spec == "crop" else screen_spec, W, H, 9 / 16, screen_zoom)
    return None, mode, screen
