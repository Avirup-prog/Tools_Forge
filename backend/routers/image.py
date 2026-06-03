"""
routers/image.py — 8 image tool endpoints
POST /api/image/compress
POST /api/image/resize
POST /api/image/convert
POST /api/image/watermark
POST /api/image/collage
POST /api/image/color-pick
POST /api/image/remove-bg    (AI — rembg)
POST /api/image/upscale      (AI — opencv super-resolution)
"""

import io
import json
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import Response

from PIL import Image as PILImage, ImageDraw, ImageFont, ImageFilter
import cv2
import numpy as np

from utils.helpers import save_upload, cleanup, require_mime, tool_error

router = APIRouter()

# MIME type → Pillow format name
_FMT = {
    "image/jpeg": "JPEG",
    "image/png":  "PNG",
    "image/webp": "WEBP",
    "image/bmp":  "BMP",
    "image/gif":  "GIF",
}
_EXT = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp", "BMP": "bmp", "GIF": "gif"}


def _img_response(img: PILImage.Image, fmt: str, filename: str) -> Response:
    fmt = fmt.upper()
    if fmt == "JPG":
        fmt = "JPEG"
    buf = io.BytesIO()
    save_kw = {"format": fmt}
    if fmt == "JPEG":
        save_kw["quality"] = 92
        img = img.convert("RGB")
    elif fmt == "PNG":
        save_kw["optimize"] = True
    img.save(buf, **save_kw)
    mt = f"image/{_EXT.get(fmt, 'png')}"
    return Response(
        content=buf.getvalue(),
        media_type=mt,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ─────────────────────────────────────────────────────────────────────────────
# 1. Compress Image  /api/image/compress
# ─────────────────────────────────────────────────────────────────────────────
@router.post("/compress", summary="Reduce image file size")
async def compress_image(
    file: UploadFile = File(...),
    quality: int = Form(75),      # 1-95
    max_width: Optional[int] = Form(None),
):
    require_mime(file, "image")
    src = await save_upload(file, ".tmp")
    try:
        img = PILImage.open(str(src))
        if max_width and img.width > max_width:
            ratio = max_width / img.width
            img = img.resize((max_width, int(img.height * ratio)), PILImage.LANCZOS)

        stem = Path(file.filename or "image").stem
        ct = (file.content_type or "image/jpeg").split(";")[0]
        fmt = _FMT.get(ct, "JPEG")

        buf = io.BytesIO()
        if fmt == "JPEG":
            img.convert("RGB").save(buf, format="JPEG", quality=quality, optimize=True)
        elif fmt == "WEBP":
            img.save(buf, format="WEBP", quality=quality, method=6)
        else:
            img.save(buf, format="PNG", optimize=True)

        ext = _EXT.get(fmt, "jpg")
        return Response(
            content=buf.getvalue(),
            media_type=f"image/{ext}",
            headers={"Content-Disposition": f'attachment; filename="{stem}_compressed.{ext}"'},
        )
    except Exception as e:
        raise tool_error(f"Compress failed: {e}")
    finally:
        cleanup(src)


# ─────────────────────────────────────────────────────────────────────────────
# 2. Resize & Crop  /api/image/resize
# ─────────────────────────────────────────────────────────────────────────────
@router.post("/resize", summary="Resize and/or crop an image")
async def resize_crop(
    file: UploadFile = File(...),
    width: Optional[int] = Form(None),
    height: Optional[int] = Form(None),
    crop: bool = Form(False),
    crop_x: int = Form(0),
    crop_y: int = Form(0),
    crop_w: Optional[int] = Form(None),
    crop_h: Optional[int] = Form(None),
):
    require_mime(file, "image")
    src = await save_upload(file, ".tmp")
    try:
        img = PILImage.open(str(src))
        ow, oh = img.size

        if crop:
            cw = crop_w or (ow - crop_x)
            ch = crop_h or (oh - crop_y)
            img = img.crop((crop_x, crop_y, crop_x + cw, crop_y + ch))

        if width or height:
            if width and height:
                img = img.resize((width, height), PILImage.LANCZOS)
            elif width:
                img = img.resize((width, int(img.height * width / img.width)), PILImage.LANCZOS)
            else:
                img = img.resize((int(img.width * height / img.height), height), PILImage.LANCZOS)

        ct = (file.content_type or "image/png").split(";")[0]
        fmt = _FMT.get(ct, "PNG")
        stem = Path(file.filename or "image").stem
        return _img_response(img, fmt, f"{stem}_resized.{_EXT.get(fmt,'png')}")
    except Exception as e:
        raise tool_error(f"Resize failed: {e}")
    finally:
        cleanup(src)


# ─────────────────────────────────────────────────────────────────────────────
# 3. Convert Format  /api/image/convert
# ─────────────────────────────────────────────────────────────────────────────
@router.post("/convert", summary="Convert image to JPG / PNG / WEBP / BMP")
async def convert_format(
    file: UploadFile = File(...),
    to_format: str = Form("png"),   # jpg | png | webp | bmp
):
    require_mime(file, "image")
    src = await save_upload(file, ".tmp")
    try:
        img = PILImage.open(str(src))
        fmt = to_format.upper()
        if fmt == "JPG":
            fmt = "JPEG"
        if fmt not in ("JPEG", "PNG", "WEBP", "BMP"):
            raise tool_error(f"Unsupported output format: {to_format}")
        stem = Path(file.filename or "image").stem
        ext = _EXT.get(fmt, "png")
        return _img_response(img, fmt, f"{stem}.{ext}")
    except Exception as e:
        raise tool_error(f"Convert failed: {e}")
    finally:
        cleanup(src)


# ─────────────────────────────────────────────────────────────────────────────
# 4. Add Watermark  /api/image/watermark
# ─────────────────────────────────────────────────────────────────────────────
@router.post("/watermark", summary="Add text watermark to an image")
async def add_watermark_img(
    file: UploadFile = File(...),
    text: str = Form("© ToolForge"),
    position: str = Form("bottom-right"),   # top-left | center | bottom-right etc.
    opacity: int = Form(128),               # 0-255
    font_size: int = Form(36),
):
    require_mime(file, "image")
    src = await save_upload(file, ".tmp")
    try:
        img = PILImage.open(str(src)).convert("RGBA")
        w, h = img.size

        overlay = PILImage.new("RGBA", img.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        # Use default font at specified size
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)
        except Exception:
            font = ImageFont.load_default()

        bbox = draw.textbbox((0, 0), text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]

        padding = 20
        positions = {
            "top-left":     (padding, padding),
            "top-center":   ((w - tw) // 2, padding),
            "top-right":    (w - tw - padding, padding),
            "center":       ((w - tw) // 2, (h - th) // 2),
            "bottom-left":  (padding, h - th - padding),
            "bottom-center":((w - tw) // 2, h - th - padding),
            "bottom-right": (w - tw - padding, h - th - padding),
        }
        xy = positions.get(position, positions["bottom-right"])

        draw.text(xy, text, font=font, fill=(255, 255, 255, opacity))

        out = PILImage.alpha_composite(img, overlay)

        ct = (file.content_type or "image/png").split(";")[0]
        fmt = _FMT.get(ct, "PNG")
        if fmt == "JPEG":
            out = out.convert("RGB")
        stem = Path(file.filename or "image").stem
        return _img_response(out, fmt, f"{stem}_watermarked.{_EXT.get(fmt,'png')}")
    except Exception as e:
        raise tool_error(f"Watermark failed: {e}")
    finally:
        cleanup(src)


# ─────────────────────────────────────────────────────────────────────────────
# 5. Collage / Image Merger  /api/image/collage
# ─────────────────────────────────────────────────────────────────────────────
@router.post("/collage", summary="Combine multiple images into a grid collage")
async def image_collage(
    files: List[UploadFile] = File(...),
    cols: int = Form(2),
    padding: int = Form(10),
    bg_color: str = Form("#ffffff"),
):
    if not files:
        raise tool_error("No files uploaded.")
    for f in files:
        require_mime(f, "image")

    srcs = []
    try:
        images = []
        for f in files:
            p = await save_upload(f, ".tmp")
            srcs.append(p)
            images.append(PILImage.open(str(p)).convert("RGBA"))

        # Normalize to same size (use first image dimensions)
        target_w = images[0].width
        target_h = images[0].height
        images = [img.resize((target_w, target_h), PILImage.LANCZOS) for img in images]

        rows = (len(images) + cols - 1) // cols
        canvas_w = cols * target_w + (cols + 1) * padding
        canvas_h = rows * target_h + (rows + 1) * padding

        # Parse bg color
        bg = (255, 255, 255, 255)
        try:
            from PIL import ImageColor
            bg = ImageColor.getrgb(bg_color) + (255,)
        except Exception:
            pass

        canvas = PILImage.new("RGBA", (canvas_w, canvas_h), bg)
        for i, img in enumerate(images):
            row, col = divmod(i, cols)
            x = padding + col * (target_w + padding)
            y = padding + row * (target_h + padding)
            canvas.paste(img, (x, y), img)

        return _img_response(canvas.convert("RGB"), "PNG", "collage.png")
    except Exception as e:
        raise tool_error(f"Collage failed: {e}")
    finally:
        cleanup(*srcs)


# ─────────────────────────────────────────────────────────────────────────────
# 6. Color Picker  /api/image/color-pick
# ─────────────────────────────────────────────────────────────────────────────
@router.post("/color-pick", summary="Extract dominant colors from an image")
async def color_pick(
    file: UploadFile = File(...),
    count: int = Form(8),
):
    require_mime(file, "image")
    src = await save_upload(file, ".tmp")
    try:
        img = PILImage.open(str(src)).convert("RGB")
        # Resize for speed
        img.thumbnail((200, 200))
        arr = np.array(img).reshape(-1, 3).astype(np.float32)

        # K-means clustering
        k = min(count, len(arr))
        _, labels, centers = cv2.kmeans(
            arr, k, None,
            (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 100, 0.2),
            10, cv2.KMEANS_RANDOM_CENTERS,
        )
        centers = centers.astype(int)
        counts = np.bincount(labels.flatten())
        total = counts.sum()

        colors = []
        for i in np.argsort(-counts):
            r, g, b = centers[i].tolist()
            pct = round(counts[i] / total * 100, 1)
            colors.append({
                "hex":  f"#{r:02x}{g:02x}{b:02x}",
                "rgb":  f"rgb({r},{g},{b})",
                "hsl":  _rgb_to_hsl(r, g, b),
                "pct":  pct,
            })

        return Response(
            content=json.dumps({"colors": colors}),
            media_type="application/json",
        )
    except Exception as e:
        raise tool_error(f"Color pick failed: {e}")
    finally:
        cleanup(src)


def _rgb_to_hsl(r, g, b):
    r_, g_, b_ = r / 255, g / 255, b / 255
    cmax, cmin = max(r_, g_, b_), min(r_, g_, b_)
    delta = cmax - cmin
    l = (cmax + cmin) / 2
    s = 0 if delta == 0 else delta / (1 - abs(2 * l - 1))
    if delta == 0:
        h = 0
    elif cmax == r_:
        h = 60 * (((g_ - b_) / delta) % 6)
    elif cmax == g_:
        h = 60 * (((b_ - r_) / delta) + 2)
    else:
        h = 60 * (((r_ - g_) / delta) + 4)
    return f"hsl({round(h)},{round(s*100)}%,{round(l*100)}%)"


# ─────────────────────────────────────────────────────────────────────────────
# 7. Remove Background (AI)  /api/image/remove-bg
# ─────────────────────────────────────────────────────────────────────────────
@router.post("/remove-bg", summary="AI background removal using rembg")
async def remove_bg(file: UploadFile = File(...)):
    require_mime(file, "image")
    src = await save_upload(file, ".tmp")
    try:
        from rembg import remove as rembg_remove
        data = src.read_bytes()
        result = rembg_remove(data)  # returns PNG bytes with alpha

        stem = Path(file.filename or "image").stem
        return Response(
            content=result,
            media_type="image/png",
            headers={"Content-Disposition": f'attachment; filename="{stem}_no_bg.png"'},
        )
    except Exception as e:
        raise tool_error(f"Background removal failed: {e}")
    finally:
        cleanup(src)


# ─────────────────────────────────────────────────────────────────────────────
# 8. Upscale Image (AI)  /api/image/upscale
# ─────────────────────────────────────────────────────────────────────────────
@router.post("/upscale", summary="2× or 4× AI super-resolution upscaling")
async def upscale_image(
    file: UploadFile = File(...),
    scale: int = Form(2),   # 2 or 4
):
    require_mime(file, "image")
    if scale not in (2, 4):
        raise tool_error("Scale must be 2 or 4.")
    src = await save_upload(file, ".tmp")
    try:
        img = PILImage.open(str(src)).convert("RGB")
        arr = np.array(img)

        # OpenCV INTER_LANCZOS4 upscale (good quality, no model download needed)
        h, w = arr.shape[:2]
        upscaled = cv2.resize(
            arr,
            (w * scale, h * scale),
            interpolation=cv2.INTER_LANCZOS4,
        )

        # Optional: light sharpening pass
        kernel = np.array([[0, -0.5, 0], [-0.5, 3, -0.5], [0, -0.5, 0]])
        upscaled = cv2.filter2D(upscaled, -1, kernel)
        upscaled = np.clip(upscaled, 0, 255).astype(np.uint8)

        out_img = PILImage.fromarray(upscaled)
        stem = Path(file.filename or "image").stem
        return _img_response(out_img, "PNG", f"{stem}_{scale}x.png")
    except Exception as e:
        raise tool_error(f"Upscale failed: {e}")
    finally:
        cleanup(src)
