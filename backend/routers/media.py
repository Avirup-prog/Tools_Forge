"""
routers/media.py — 7 video/audio tool endpoints
POST /api/media/video-compress
POST /api/media/video-convert
POST /api/media/extract-audio
POST /api/media/audio-convert
POST /api/media/gif-maker
POST /api/media/trim
POST /api/media/volume-boost
"""

import io
import os
import subprocess
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import Response

from utils.helpers import save_upload, temp_path, cleanup, require_mime, tool_error

router = APIRouter()

# ── ffmpeg helper ──────────────────────────────────────────────────────────────

def _ffmpeg(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    """Run ffmpeg with the given args, raise tool_error on failure."""
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *args]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if check and result.returncode != 0:
        raise tool_error(f"ffmpeg error: {result.stderr.strip()}", 500)
    return result


# ─────────────────────────────────────────────────────────────────────────────
# 1. Video Compressor  /api/media/video-compress
# ─────────────────────────────────────────────────────────────────────────────
@router.post("/video-compress", summary="Compress a video file using H.264")
async def video_compress(
    file: UploadFile = File(...),
    crf: int = Form(28),           # 18-51; higher = smaller/worse
    preset: str = Form("fast"),    # ultrafast|fast|medium|slow
    max_height: int = Form(720),   # max vertical resolution
):
    require_mime(file, "video")
    src = await save_upload(file, Path(file.filename or "v.mp4").suffix or ".mp4")
    out = temp_path(".mp4")

    try:
        scale_filter = f"scale=-2:min({max_height}\\,ih)"
        _ffmpeg(
            "-i", str(src),
            "-vf", scale_filter,
            "-c:v", "libx264",
            "-crf", str(crf),
            "-preset", preset,
            "-c:a", "aac",
            "-b:a", "128k",
            "-movflags", "+faststart",
            str(out),
        )
        stem = Path(file.filename or "video").stem
        return Response(
            content=out.read_bytes(),
            media_type="video/mp4",
            headers={"Content-Disposition": f'attachment; filename="{stem}_compressed.mp4"'},
        )
    except Exception as e:
        raise tool_error(f"Video compress failed: {e}")
    finally:
        cleanup(src, out)


# ─────────────────────────────────────────────────────────────────────────────
# 2. Video Format Converter  /api/media/video-convert
# ─────────────────────────────────────────────────────────────────────────────
@router.post("/video-convert", summary="Convert video to MP4, WEBM, or MOV")
async def video_convert(
    file: UploadFile = File(...),
    to_format: str = Form("mp4"),   # mp4 | webm | mov | avi
):
    require_mime(file, "video")
    src_ext = Path(file.filename or "v.mp4").suffix or ".mp4"
    src = await save_upload(file, src_ext)

    fmt_map = {
        "mp4":  (".mp4",  "libx264", "aac",       "video/mp4"),
        "webm": (".webm", "libvpx",  "libvorbis",  "video/webm"),
        "mov":  (".mov",  "libx264", "aac",        "video/quicktime"),
        "avi":  (".avi",  "mpeg4",   "mp3",        "video/x-msvideo"),
    }
    to_format = to_format.lower()
    if to_format not in fmt_map:
        raise tool_error(f"Unsupported format: {to_format}")

    ext, vcodec, acodec, mime = fmt_map[to_format]
    out = temp_path(ext)
    try:
        _ffmpeg(
            "-i", str(src),
            "-c:v", vcodec,
            "-c:a", acodec,
            str(out),
        )
        stem = Path(file.filename or "video").stem
        return Response(
            content=out.read_bytes(),
            media_type=mime,
            headers={"Content-Disposition": f'attachment; filename="{stem}{ext}"'},
        )
    except Exception as e:
        raise tool_error(f"Video convert failed: {e}")
    finally:
        cleanup(src, out)


# ─────────────────────────────────────────────────────────────────────────────
# 3. Extract Audio from Video  /api/media/extract-audio
# ─────────────────────────────────────────────────────────────────────────────
@router.post("/extract-audio", summary="Extract audio track from a video file")
async def extract_audio(
    file: UploadFile = File(...),
    to_format: str = Form("mp3"),   # mp3 | wav | ogg | aac
):
    require_mime(file, "video")
    src = await save_upload(file, Path(file.filename or "v.mp4").suffix or ".mp4")

    fmt_map = {
        "mp3": (".mp3", "libmp3lame", "128k", "audio/mpeg"),
        "wav": (".wav", "pcm_s16le",  None,   "audio/wav"),
        "ogg": (".ogg", "libvorbis",  "128k", "audio/ogg"),
        "aac": (".aac", "aac",        "128k", "audio/aac"),
    }
    to_format = to_format.lower()
    if to_format not in fmt_map:
        raise tool_error(f"Unsupported audio format: {to_format}")

    ext, codec, bitrate, mime = fmt_map[to_format]
    out = temp_path(ext)
    try:
        extra = ["-b:a", bitrate] if bitrate else []
        _ffmpeg(
            "-i", str(src),
            "-vn",
            "-c:a", codec,
            *extra,
            str(out),
        )
        stem = Path(file.filename or "video").stem
        return Response(
            content=out.read_bytes(),
            media_type=mime,
            headers={"Content-Disposition": f'attachment; filename="{stem}{ext}"'},
        )
    except Exception as e:
        raise tool_error(f"Extract audio failed: {e}")
    finally:
        cleanup(src, out)


# ─────────────────────────────────────────────────────────────────────────────
# 4. Audio Format Converter  /api/media/audio-convert
# ─────────────────────────────────────────────────────────────────────────────
@router.post("/audio-convert", summary="Convert audio between MP3, WAV, OGG, FLAC")
async def audio_convert(
    file: UploadFile = File(...),
    to_format: str = Form("mp3"),
):
    require_mime(file, "audio")
    src = await save_upload(file, Path(file.filename or "a.mp3").suffix or ".mp3")

    fmt_map = {
        "mp3":  (".mp3",  "libmp3lame", "192k", "audio/mpeg"),
        "wav":  (".wav",  "pcm_s16le",  None,   "audio/wav"),
        "ogg":  (".ogg",  "libvorbis",  "192k", "audio/ogg"),
        "flac": (".flac", "flac",       None,   "audio/flac"),
        "aac":  (".aac",  "aac",        "192k", "audio/aac"),
    }
    to_format = to_format.lower()
    if to_format not in fmt_map:
        raise tool_error(f"Unsupported format: {to_format}")

    ext, codec, bitrate, mime = fmt_map[to_format]
    out = temp_path(ext)
    try:
        extra = ["-b:a", bitrate] if bitrate else []
        _ffmpeg(
            "-i", str(src),
            "-c:a", codec,
            *extra,
            str(out),
        )
        stem = Path(file.filename or "audio").stem
        return Response(
            content=out.read_bytes(),
            media_type=mime,
            headers={"Content-Disposition": f'attachment; filename="{stem}{ext}"'},
        )
    except Exception as e:
        raise tool_error(f"Audio convert failed: {e}")
    finally:
        cleanup(src, out)


# ─────────────────────────────────────────────────────────────────────────────
# 5. GIF Maker  /api/media/gif-maker
# ─────────────────────────────────────────────────────────────────────────────
@router.post("/gif-maker", summary="Convert a video clip to an animated GIF")
async def gif_maker(
    file: UploadFile = File(...),
    start: float = Form(0),       # seconds
    duration: float = Form(5),    # seconds
    fps: int = Form(10),
    width: int = Form(480),
):
    require_mime(file, "video")
    src = await save_upload(file, Path(file.filename or "v.mp4").suffix or ".mp4")
    palette = temp_path(".png")
    out = temp_path(".gif")

    try:
        # Two-pass GIF: generate palette first for quality
        _ffmpeg(
            "-ss", str(start),
            "-t", str(duration),
            "-i", str(src),
            "-vf", f"fps={fps},scale={width}:-1:flags=lanczos,palettegen",
            str(palette),
        )
        _ffmpeg(
            "-ss", str(start),
            "-t", str(duration),
            "-i", str(src),
            "-i", str(palette),
            "-lavfi", f"fps={fps},scale={width}:-1:flags=lanczos [x]; [x][1:v] paletteuse",
            str(out),
        )
        stem = Path(file.filename or "video").stem
        return Response(
            content=out.read_bytes(),
            media_type="image/gif",
            headers={"Content-Disposition": f'attachment; filename="{stem}.gif"'},
        )
    except Exception as e:
        raise tool_error(f"GIF maker failed: {e}")
    finally:
        cleanup(src, palette, out)


# ─────────────────────────────────────────────────────────────────────────────
# 6. Trim Video & Audio  /api/media/trim
# ─────────────────────────────────────────────────────────────────────────────
@router.post("/trim", summary="Trim a video or audio file to a time range")
async def trim_media(
    file: UploadFile = File(...),
    start: float = Form(0),
    end: Optional[float] = Form(None),
    duration: Optional[float] = Form(None),
):
    ct = (file.content_type or "").split(";")[0].lower()
    is_audio = ct.startswith("audio/")
    is_video = ct.startswith("video/")
    if not is_audio and not is_video:
        raise tool_error("Only video or audio files are accepted.")

    src_ext = Path(file.filename or ("a.mp3" if is_audio else "v.mp4")).suffix or ".mp4"
    src = await save_upload(file, src_ext)
    out = temp_path(src_ext)

    try:
        dur_args = []
        if end is not None:
            dur_args = ["-to", str(end)]
        elif duration is not None:
            dur_args = ["-t", str(duration)]

        _ffmpeg(
            "-ss", str(start),
            "-i", str(src),
            *dur_args,
            "-c", "copy",
            str(out),
        )
        stem = Path(file.filename or "media").stem
        mime = ct if ct else "video/mp4"
        return Response(
            content=out.read_bytes(),
            media_type=mime,
            headers={"Content-Disposition": f'attachment; filename="{stem}_trimmed{src_ext}"'},
        )
    except Exception as e:
        raise tool_error(f"Trim failed: {e}")
    finally:
        cleanup(src, out)


# ─────────────────────────────────────────────────────────────────────────────
# 7. Volume Booster  /api/media/volume-boost
# ─────────────────────────────────────────────────────────────────────────────
@router.post("/volume-boost", summary="Increase or decrease audio volume")
async def volume_boost(
    file: UploadFile = File(...),
    db: float = Form(6.0),   # positive = louder, negative = quieter; range -40 to +40
):
    require_mime(file, "audio")
    if not (-40 <= db <= 40):
        raise tool_error("Volume change must be between -40 and +40 dB.")

    src_ext = Path(file.filename or "a.mp3").suffix or ".mp3"
    src = await save_upload(file, src_ext)
    out = temp_path(src_ext)

    try:
        ct = (file.content_type or "audio/mpeg").split(";")[0]
        fmt_codec = {
            "audio/mpeg": "libmp3lame",
            "audio/wav":  "pcm_s16le",
            "audio/ogg":  "libvorbis",
            "audio/flac": "flac",
        }
        codec = fmt_codec.get(ct, "libmp3lame")

        _ffmpeg(
            "-i", str(src),
            "-af", f"volume={db}dB",
            "-c:a", codec,
            str(out),
        )
        stem = Path(file.filename or "audio").stem
        direction = "boosted" if db >= 0 else "reduced"
        return Response(
            content=out.read_bytes(),
            media_type=ct,
            headers={"Content-Disposition": f'attachment; filename="{stem}_{direction}{src_ext}"'},
        )
    except Exception as e:
        raise tool_error(f"Volume boost failed: {e}")
    finally:
        cleanup(src, out)
