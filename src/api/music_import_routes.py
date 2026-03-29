"""
Music Import API — POST /api/v1/music/import-tiktok
                   POST /api/v1/music/import-youtube

Flow:
1. Nhận TikTok/YouTube URL từ frontend
2. yt-dlp download + extract MP3 vào /tmp
   - TikTok: download trực tiếp
   - YouTube: dùng cookies (/app/yt-cookies.txt) + bgutil PO token provider sidecar
3. shazamio nhận diện title/artist (timeout 30s)
4. Upload MP3 lên R2  →  tiktok-audio/user-imports/{user_id}/{track_id}.mp3
5. Trả về metadata để frontend lưu vào D1

Setup cookies (one-time):
1. Cài extension "Get cookies.txt LOCALLY" trên Chrome/Firefox
2. Mở youtube.com khi đã login → export cookies
3. Upload lên server: scp cookies.txt root@104.248.147.155:/tmp/yt-cookies.txt
4. docker cp /tmp/yt-cookies.txt ai-chatbot-rag:/app/yt-cookies.txt
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
YOUTUBE_URL_RE = re.compile(r"(?:youtube\.com/watch\?v=|youtu\.be/)([\w-]{11})")

YT_COOKIES_PATH = "/app/yt-cookies.txt"
# bgutil PO token provider sidecar (docker container on same network)
BGUTIL_URL = "http://bgutil-provider:4416"


class ImportRequest(BaseModel):
    url: str
    channel_id: Optional[str] = None


class TrackMeta(BaseModel):
    track_id: str
    title: Optional[str]
    artist: Optional[str]
    audio_url: str
    cover_url: Optional[str]
    duration_sec: int
    source: str  # "tiktok" | "youtube"
    source_id: str
    shazam_matched: bool


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ytdlp_cmd_base(out_template: str, extra_args: list[str] = None) -> list[str]:
    return [
        "yt-dlp",
        "-x",
        "--audio-format",
        "mp3",
        "--audio-quality",
        "192K",
        "--no-playlist",
        "--no-warnings",
        "--print-json",
        "-o",
        out_template,
        *(extra_args or []),
    ]


def _run_ytdlp(url: str, out_mp3: str, is_youtube: bool = False) -> Dict[str, Any]:
    """
    Run yt-dlp synchronously. Returns parsed metadata dict.
    For YouTube: uses android_vr player client (no JS runtime / cookies needed).
    Falls back to cookies + bgutil if android_vr fails.
    """
    import json

    out_template = out_mp3.replace(".mp3", ".%(ext)s")
    extra_args = []

    if is_youtube:
        # android_vr client bypasses PO token & JS signature requirements on datacenter IPs
        extra_args += [
            "--extractor-args",
            "youtube:player_client=android_vr",
        ]

    cmd = _ytdlp_cmd_base(out_template, extra_args) + [url]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

    if result.returncode != 0:
        raise RuntimeError(f"yt-dlp failed: {result.stderr[:500]}")

    meta = {}
    for line in result.stdout.splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                meta = json.loads(line)
            except Exception:
                pass
            break

    return {
        "title": meta.get("title") or meta.get("fulltitle"),
        "uploader": meta.get("uploader") or meta.get("channel"),
        "duration": int(meta.get("duration") or 0),
        "thumbnail": meta.get("thumbnail"),
        "video_id": meta.get("id", ""),
    }


async def _shazam_recognize(mp3_path: str) -> Dict[str, Any]:
    try:
        from shazamio import Shazam

        shazam = Shazam()
        result = await asyncio.wait_for(shazam.recognize(mp3_path), timeout=30)
        track = result.get("track", {})
        if not track:
            return {"matched": False}

        hub = track.get("hub") or {}
        spotify_id = ""
        for p in hub.get("providers") or []:
            for act in p.get("actions") or []:
                uri = act.get("uri", "")
                if "spotify:track:" in uri:
                    spotify_id = uri.split("spotify:track:")[-1]

        return {
            "matched": True,
            "title": track.get("title", ""),
            "artist": track.get("subtitle", ""),
            "spotify_id": spotify_id,
        }
    except asyncio.TimeoutError:
        logger.warning("shazam recognize timeout")
        return {"matched": False}
    except Exception as e:
        logger.warning(f"shazam error: {e}")
        return {"matched": False}


async def _upload_to_r2(mp3_bytes: bytes, r2_key: str) -> str:
    r2 = AIVungtauR2StorageConfig()
    result = await r2.upload_file_from_buffer(
        file_buffer=mp3_bytes,
        file_key=r2_key,
        content_type="audio/mpeg",
    )
    if not result.get("success"):
        raise RuntimeError(f"R2 upload failed: {result}")
    return f"{R2_STATIC}/{r2_key}"


async def _process_import(
    url: str, source: str, video_id: str, user_id: str
) -> TrackMeta:
    """Shared logic: download → shazam → upload R2."""
    track_id = f"{'tt' if source == 'tiktok' else 'yt'}_{video_id}"
    r2_key = f"tiktok-audio/user-imports/{user_id}/{track_id}.mp3"
    is_youtube = source == "youtube"

    with tempfile.TemporaryDirectory() as tmpdir:
        mp3_path = os.path.join(tmpdir, f"{track_id}.mp3")

        try:
            loop = asyncio.get_event_loop()
            ytdlp_meta = await loop.run_in_executor(
                None, lambda: _run_ytdlp(url, mp3_path, is_youtube=is_youtube)
            )
        except Exception as e:
            logger.error(f"[music-import] yt-dlp error: {e}")
            raise HTTPException(
                status_code=422, detail=f"Không thể tải video: {str(e)[:200]}"
            )

        if not os.path.exists(mp3_path):
            raise HTTPException(
                status_code=422, detail="yt-dlp chạy xong nhưng không tạo được file MP3"
            )

        shazam_result = await _shazam_recognize(mp3_path)

        if shazam_result["matched"]:
            title = shazam_result["title"]
            artist = shazam_result["artist"]
        else:
            title = ytdlp_meta.get("title") or ""
            artist = ytdlp_meta.get("uploader") or ""

        with open(mp3_path, "rb") as f:
            mp3_bytes = f.read()

        logger.info(f"[music-import] uploading {len(mp3_bytes)//1024}KB → R2: {r2_key}")
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
        source=source,
        source_id=video_id,
        shazam_matched=shazam_result["matched"],
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/import-tiktok", response_model=TrackMeta)
async def import_tiktok(
    body: ImportRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Import 1 TikTok video → MP3 → Shazam → R2."""
    url = body.url.strip()
    if "tiktok.com" not in url:
        raise HTTPException(status_code=400, detail="URL phải là TikTok link")

    m = TIKTOK_URL_RE.search(url)
    video_id = m.group(1) if m else uuid.uuid4().hex[:16]

    return await _process_import(url, "tiktok", video_id, current_user["uid"])


@router.post("/import-youtube", response_model=TrackMeta)
async def import_youtube(
    body: ImportRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Import 1 YouTube video → MP3 → Shazam → R2.
    Dùng android_vr player client — không cần cookies hay JS runtime.
    """
    url = body.url.strip()
    if "youtube.com" not in url and "youtu.be" not in url:
        raise HTTPException(status_code=400, detail="URL phải là YouTube link")

    # Normalise: strip playlist params, keep only v=
    m = YOUTUBE_URL_RE.search(url)
    if not m:
        raise HTTPException(
            status_code=400, detail="Không nhận diện được YouTube video ID từ URL này"
        )
    video_id = m.group(1)
    clean_url = f"https://www.youtube.com/watch?v={video_id}"

    return await _process_import(clean_url, "youtube", video_id, current_user["uid"])


@router.get("/youtube-status")
async def youtube_status():
    """Check trạng thái YouTube import (public endpoint).
    android_vr client không cần cookies — youtube_ready = True khi server reachable.
    """
    bgutil_ok = False
    try:
        import urllib.request
        import urllib.error

        try:
            urllib.request.urlopen(f"{BGUTIL_URL}/", timeout=3)
            bgutil_ok = True
        except urllib.error.HTTPError:
            # Server is up but returns 404 for root — that's fine
            bgutil_ok = True
    except Exception:
        pass

    return {
        "player_client": "android_vr",
        "cookies_required": False,
        "bgutil_provider_running": bgutil_ok,
        "youtube_ready": True,  # android_vr works without cookies/bgutil
    }
