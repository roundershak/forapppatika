"""YouTube kapak fotoğrafı (1280x720): izlenen videodan sahne + yayıncının yüzü + büyük yazı."""

from __future__ import annotations

import glob
import io
import os
from typing import Optional

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W, H = 1280, 720

_FONT_CANDIDATES = [
    *sorted(glob.glob(os.path.join(ROOT, "assets", "fonts", "*.[ot]tf"))),
    "C:/Windows/Fonts/impact.ttf", "C:/Windows/Fonts/ariblk.ttf", "C:/Windows/Fonts/arialbd.ttf",
    "/System/Library/Fonts/Supplemental/Impact.ttf", "/Library/Fonts/Arial Black.ttf",
    "/System/Library/Fonts/Supplemental/Arial Black.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/opentype/inter/Inter-ExtraBold.otf",
]


def _font(size: int) -> ImageFont.FreeTypeFont:
    for p in _FONT_CANDIDATES:
        if os.path.isfile(p):
            try:
                return ImageFont.truetype(p, size)
            except OSError:
                continue
    return ImageFont.load_default(size)


def _upper_tr(s: str) -> str:
    return s.replace("i", "İ").replace("ı", "I").upper()


def _fill(img: Image.Image, w: int, h: int) -> Image.Image:
    r = max(w / img.width, h / img.height)
    img = img.resize((max(w, round(img.width * r)), max(h, round(img.height * r))), Image.LANCZOS)
    x, y = (img.width - w) // 2, (img.height - h) // 2
    return img.crop((x, y, x + w, y + h))


def _crop_norm(img: Image.Image, box) -> Image.Image:
    """box: [x, y, w, h] 0-1 oranları. Geçersizse görüntünün kendisi."""
    try:
        x, y, w, h = [float(v) for v in box]
    except (TypeError, ValueError):
        return img
    if w < 0.15 or h < 0.15 or x < -0.05 or y < -0.05 or x + w > 1.05 or y + h > 1.05:
        return img
    X, Y = img.width, img.height
    return img.crop((max(0, int(x * X)), max(0, int(y * Y)), min(X, int((x + w) * X)), min(Y, int((y + h) * Y))))


def _wrap(draw, text: str, font, max_w: int) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if draw.textlength(t, font=font) <= max_w or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def compose(background: bytes, face: Optional[bytes], face_box=None, text: str = "",
            player_box=None, out_path: str = "kapak.jpg") -> str:
    """background/face: JPEG baytları (1080p kareler). face_box: kameranın piksel alanı (x, y, w, h)."""
    bg = Image.open(io.BytesIO(background)).convert("RGB")
    bg = _fill(_crop_norm(bg, player_box), W, H)
    bg = ImageEnhance.Color(bg).enhance(1.35)
    bg = ImageEnhance.Contrast(bg).enhance(1.12)

    canvas = bg.copy()
    # yazı tarafını okunur yapmak için soldan/alttan karartma
    shade = Image.new("L", (W, H), 0)
    sd = ImageDraw.Draw(shade)
    for i in range(W):
        sd.line([(i, 0), (i, H)], fill=int(170 * max(0.0, 1 - i / (W * 0.62)) ** 1.4))
    canvas = Image.composite(Image.new("RGB", (W, H), (0, 0, 0)), canvas, shade)

    face_right = W
    if face:
        fimg = Image.open(io.BytesIO(face)).convert("RGB")
        if face_box:
            x, y, w, h = [int(v) for v in face_box]
            fimg = fimg.crop((x, y, x + w, y + h))
        fh = int(H * 0.76)
        fw = int(fh * min(1.1, max(0.7, fimg.width / max(1, fimg.height))))
        fimg = _fill(fimg, fw, fh)
        fimg = ImageEnhance.Contrast(fimg).enhance(1.08)
        border = 10
        framed = Image.new("RGB", (fw + 2 * border, fh + 2 * border), (255, 255, 255))
        framed.paste(fimg, (border, border))
        mask = Image.new("L", framed.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, *framed.size], radius=28, fill=255)
        px = W - framed.width - 28
        py = H - framed.height - 22
        shadow = Image.new("L", (W, H), 0)
        ImageDraw.Draw(shadow).rounded_rectangle([px + 10, py + 14, px + framed.width + 10, py + framed.height + 14],
                                                 radius=28, fill=200)
        shadow = shadow.filter(ImageFilter.GaussianBlur(18))
        canvas = Image.composite(Image.new("RGB", (W, H), (0, 0, 0)), canvas, shadow)
        canvas.paste(framed, (px, py), mask)
        face_right = px

    text = _upper_tr((text or "").strip())
    if text:
        draw = ImageDraw.Draw(canvas)
        max_w = max(420, face_right - 70)
        size = 150
        while size > 60:
            font = _font(size)
            lines = _wrap(draw, text, font, max_w)
            if len(lines) <= 3 and all(draw.textlength(ln, font=font) <= max_w for ln in lines):
                break
            size -= 8
        font = _font(size)
        lines = _wrap(draw, text, font, max_w)[:3]
        lh = int(size * 1.05)
        y = H - 40 - lh * len(lines)
        colors = [(255, 230, 0), (255, 255, 255), (255, 255, 255)]
        for i, ln in enumerate(lines):
            draw.text((44, y + i * lh), ln, font=font, fill=colors[i % 3],
                      stroke_width=max(6, size // 13), stroke_fill=(0, 0, 0))

    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    canvas.save(out_path, "JPEG", quality=90, optimize=True)
    return out_path
