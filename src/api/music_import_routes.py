"""
Music Import API — POST /api/v1/music/import-tiktok

Flow:
1. Nhận TikTok URL từ frontend
2. yt-dlp download + extract MP3 vào /tmp
3. shazamio nhận diện title/artist (timeout 30s)
4. Upload MP3 lên R2  →  tiktok-audio/user-imports/{user_id}/{track_id}.mp3
5. Trả về metadata để frontend lưu vào D1
"""

import asyncio
import logging
import os
import re
import subprocess
import tempfile
import uuid
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.config.r2_storage import AIVungtauR2StorageConfig
from src.middleware.firebase_auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/music", tags=["Music Import"])

R2_STATIC = "https://static.aivungtau.com"
TIKTOK_URL_RE = re.compile(r"tiktok\.com/.*?/video/(\d+)")


class TikTokImportRequest(BaseModel):
    url: str
    channel_id: Optional[str] = None  # optional: gắn vào channel nào


class TrackMeta(BaseModel):
    track_id: str
    title: Optional[str]
    artist: Optional[str]
    audio_url: str          # R2 public URL
    cover_url: Optional[str]
    duration_sec: int
    source: str             # "tiktok"
    source_id: str          # TikTok video ID
    shazam_matched: bool


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run_ytdlp(url: str, out_mp3: str) -> Dict[str, Any]:
    """
    Chạy yt-dlp đồng bộ trong subprocess.
    Trả về dict metadata (title, uploader, duration, thumbnail).
    """
    cmd = [
        "yt-dlp",
        "-x", "--audio-format", "mp3",
        "--audio-quality", "192K",
        "--no-playlist",
        "--no-warnings",
        "--print-json",          # in JSON metadata ra stdout
        "-o", out_mp3.replace(".mp3", ".%(ext)s"),
        url,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        raise RuntimeError(f"yt-dlp failed: {result.stderr[:500]}")

    # yt-dlp --print-json prints metadata BEFORE download, parse first line
    import json
    meta_line = ""
    for line in result.stdout.splitlines():
        line = line.strip()
        if line.startswith("{"):
            meta_line = line
            break

    meta = {}
    if meta_line:
        try:
            meta = json.loads(meta_line)
        except Exception:
            pass

    return {
        "title": meta.get("title") or meta.get("fulltitle"),
        "uploader": meta.get("uploader") or meta.get("channel"),
        "duration": int(meta.get("duration") or 0),
        "thumbnail": meta.get("thumbnail"),
        "video_id": meta.get("id", ""),
    }


async def _shazam_recognize(mp3_path: str) -> Dict[str, Any]:
    """
    Nhận diện title/artist qua shazamio (wrap async 30s timeout).
    Trả về {"title": ..., "artist": ..., "spotify_id": ..., "matched": bool}
    """
    try:
        from shazamio import Shazam  # lazy import — may not be installed locally

        shazam = Shazam()
        result = await asyncio.wait_for(shazam.recognize(mp3_path), timeout=30)
        track = result.get("track", {})
        if not track:
            return {"matched": False}

        title = track.get("title", "")
        artist = track.get("subtitle", "")
        hub = track.get("hub") or {}
        spotify_id = ""
        for p in (hub.get("providers") or []):
            for act in (p.get("actions") or []):
                uri = act.get("uri", "")
                if "spotify:track:" in uri:
                    spotify_id = uri.split("spotify:track:")[-1]

        return {"matched": True, "title": title, "artist": artist, "spotify_id": spotify_id}

    except asyncio.TimeoutError:
        logger.warning("shazam recognize timeout")
        return {"matched": False}
    except Exception as e:
        logger.warning(f"shazam error: {e}")
        return {"matched": False}


async def _upload_to_r2(mp3_bytes: bytes, r2_key: str) -> str:
    """Upload MP3 bytes lên R2, trả về public URL."""
    r2 = AIVungtauR2StorageConfig()
    result = await r2.upload_file_from_buffer(
        file_buffer=mp3_bytes,
        file_key=r2_key,
        content_type="audio/mpeg",
    )
    if not result.get("success"):
        raise RuntimeError(f"R2 upload failed: {result}")
    return f"{R2_STATIC}/{r2_key}"


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.post("/import-tiktok", response_model=TrackMeta)
async def import_tiktok(
    body: TikTokImportRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Import 1 TikTok video:
    - Trích MP3 bằng yt-dlp (ffmpeg trong container)
    - Nhận diện nhạc bằng Shazam (best-effort, không bắt buộc)
    - Upload lên R2
    - Trả về metadata để frontend lưu D1

    Nếu Shazam không nhận diện được → vẫn trả về track với title = TikTok title.
    """
    url = body.url.strip()
    if "tiktok.com" not in url:
        raise HTTPException(status_code=400, detail="Chỉ hỗ trợ TikTok URL. YouTube sẽ được thêm sau.")

    # Extract video ID from URL for logging/key naming
    vid_match = TIKTOK_URL_RE.search(url)
    video_id = vid_match.group(1) if vid_match else str(uuid.uuid4().hex[:16])

    user_id = current_user["uid"]
    track_id = f"tt_{video_id}"

    # R2 key
    r2_key = f"tiktok-audio/user-imports/{user_id}/{track_id}.mp3"
    audio_url = f"{R2_STATIC}/{r2_key}"

    # Use a temp dir for the whole operation
    with tempfile.TemporaryDirectory() as tmpdir:
        mp3_path = os.path.join(tmpdir, f"{track_id}.mp3")

        # 1. Download + extract MP3
        logger.info(f"[music-import] yt-dlp {url} → {mp3_path}")
        try:
            loop = asyncio.get_event_loop()
            ytdlp_meta = await loop.run_in_executor(
                None, lambda: _run_ytdlp(url, mp3_path)
            )
        except Exception as e:
            logger.error(f"[music-import] yt-dlp error: {e}")
            raise HTTPException(status_code=422, detail=f"Không thể tải video: {str(e)[:200]}")

        if not os.path.exists(mp3_path):
            raise HTTPException(status_code=422, detail="yt-dlp chạy xong nhưng không tạo được file MP3")

        # 2. Shazam recognition
        shazam_result = await _shazam_recognize(mp3_path)

        # Decide final title/artist
        if shazam_result["matched"]:
            title = shazam_result["title"]
            artist = shazam_result["artist"]
        else:
            # Fall back to yt-dlp metadata title (TikTok uploader / caption)
            title = ytdlp_meta.get("title") or ""
            artist = ytdlp_meta.get("uploader") or ""

        # 3. Upload to R2
        with open(mp3_path, "rb") as f:
            mp3_bytes = f.read()

        logger.info(f"[music-import] uploading {len(mp3_bytes)//1024}KB to R2: {r2_key}")
        try:
            audio_url = await _upload_to_r2(mp3_bytes, r2_key)
        except Exception as e:
            logger.error(f"[music-import] R2 upload error: {e}")
            raise HTTPException(status_code=500, detail="Upload R2 thất bại")

    return TrackMeta(
        track_id=track_id,
        title=title or None,
        artist=artist or None,
        audio_url=audio_url,
        cover_url=ytdlp_meta.get("thumbnail"),
        duration_sec=ytdlp_meta.get("duration", 0),
        source="tiktok",
        source_id=video_id,
        shazam_matched=shazam_result["matched"],
    )
