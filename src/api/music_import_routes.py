"""
Music API:
  GET  /api/v1/music/search              — tìm kiếm YouTube, trả về 10 kết quả (no download)
  POST /api/v1/music/import-youtube      — download MP3 + lưu MongoDB cache + upload R2
  POST /api/v1/music/import-tiktok       — download TikTok MP3 + upload R2 (per-user)

YouTube import flow:
  1. Kiểm tra MongoDB collection `music_tracks` theo youtube_id
     → Cache hit: trả về ngay, không download lại
     → Cache miss: tiếp tục
  2. yt-dlp download MP3 (android_vr client)
  3. shazamio nhận diện title/artist (timeout 30s)
  4. Upload lên R2 tại music/youtube/{video_id}.mp3  (shared, không phân theo user)
  5. Lưu vào MongoDB `music_tracks`
  6. Trả về TrackMeta
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

from src.config.r2_storage import WordAiR2StorageConfig
from src.database.db_manager import DBManager
from src.middleware.firebase_auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/music", tags=["Music Import"])

R2_STATIC = "https://static.wordai.pro"
TIKTOK_URL_RE = re.compile(r"tiktok\.com/.*?/video/(\d+)")
YOUTUBE_URL_RE = re.compile(r"(?:youtube\.com/watch\?v=|youtu\.be/)([\w-]{11})")

YT_COOKIES_PATH = "/app/yt-cookies.txt"
# bgutil PO token provider sidecar (docker container on same network)
BGUTIL_URL = "http://bgutil-provider:4416"


def _get_db():
    return DBManager().db


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
    from_cache: bool = False  # True nếu lấy từ MongoDB, không download lại


class SearchResult(BaseModel):
    youtube_id: str
    title: str
    artist: str  # uploader/channel name
    duration_sec: int
    thumbnail: Optional[str]
    youtube_url: str


class LyricsResult(BaseModel):
    youtube_id: str
    title: str
    artist: str
    english_lyrics: Optional[str]
    vietnamese_lyrics: Optional[str]
    has_lyrics: bool


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
    For YouTube: mweb client + bgutil-provider sidecar for PO token (auto via plugin).
    Falls back to android_vr if bgutil not reachable.
    """
    import json

    out_template = out_mp3.replace(".mp3", ".%(ext)s")
    extra_args = []

    if is_youtube:
        # android client: works on datacenter IPs without cookies or PO token
        # Uses YouTube's mobile API — harder to block, no login required
        # GVS PO Token warning for https formats is harmless — falls back to format 18 (360p+audio)
        extra_args += ["--extractor-args", "youtube:player_client=android"]

    cmd = _ytdlp_cmd_base(out_template, extra_args) + [url]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

    if result.returncode != 0:
        # Filter out urllib3 warning noise, show the real error
        stderr_lines = [
            l
            for l in result.stderr.splitlines()
            if "RequestsDependencyWarning" not in l and "warnings.warn(" not in l
        ]
        raise RuntimeError(f"yt-dlp failed: {chr(10).join(stderr_lines)[-1500:]}")

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
    r2 = WordAiR2StorageConfig()
    result = await r2.upload_file_from_buffer(
        file_buffer=mp3_bytes,
        file_key=r2_key,
        content_type="audio/mpeg",
    )
    if not result.get("success"):
        raise RuntimeError(f"R2 upload failed: {result}")
    return f"{R2_STATIC}/{r2_key}"


def _search_youtube(query: str, limit: int) -> list:
    """Synchronous: call yt-dlp flat-playlist search, return list of dicts."""
    import json

    cmd = [
        "yt-dlp",
        "--no-warnings",
        "--print-json",
        "--flat-playlist",
        "--no-playlist",
        f"ytsearch{limit}:{query}",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    items = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            m = json.loads(line)
            vid_id = m.get("id", "")
            if not vid_id:
                continue
            items.append(
                {
                    "youtube_id": vid_id,
                    "title": m.get("title") or "",
                    "artist": m.get("uploader") or m.get("channel") or "",
                    "duration_sec": int(m.get("duration") or 0),
                    "thumbnail": m.get("thumbnail"),
                    "youtube_url": f"https://www.youtube.com/watch?v={vid_id}",
                }
            )
        except Exception:
            pass
    return items


async def _process_import(
    url: str, source: str, video_id: str, user_id: str
) -> TrackMeta:
    """Shared logic: (cache check for YouTube) → download → shazam → upload R2."""
    track_id = f"{'tt' if source == 'tiktok' else 'yt'}_{video_id}"
    is_youtube = source == "youtube"

    # ── YouTube: check MongoDB cache first ────────────────────────────────────
    if is_youtube:
        db = _get_db()
        cached = db.music_tracks.find_one({"youtube_id": video_id}, {"_id": 0})
        if cached:
            logger.info(f"[music-import] cache hit: {video_id}")
            return TrackMeta(
                track_id=cached["track_id"],
                title=cached.get("title"),
                artist=cached.get("artist"),
                audio_url=cached["audio_url"],
                cover_url=cached.get("cover_url"),
                duration_sec=cached.get("duration_sec", 0),
                source="youtube",
                source_id=video_id,
                shazam_matched=cached.get("shazam_matched", False),
                from_cache=True,
            )

    # YouTube tracks go to shared path; TikTok tracks are per-user
    if is_youtube:
        r2_key = f"music/youtube/{video_id}.mp3"
    else:
        r2_key = f"tiktok-audio/user-imports/{user_id}/{track_id}.mp3"

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

    track = TrackMeta(
        track_id=track_id,
        title=title or None,
        artist=artist or None,
        audio_url=audio_url,
        cover_url=ytdlp_meta.get("thumbnail"),
        duration_sec=ytdlp_meta.get("duration", 0),
        source=source,
        source_id=video_id,
        shazam_matched=shazam_result["matched"],
        from_cache=False,
    )

    # ── Save to MongoDB cache (YouTube only) ──────────────────────────────────
    if is_youtube:
        try:
            from datetime import datetime, timezone

            db = _get_db()
            doc = {
                "track_id": track.track_id,
                "youtube_id": video_id,
                "youtube_url": f"https://www.youtube.com/watch?v={video_id}",
                "audio_url": track.audio_url,  # R2 static URL
                "cover_url": track.cover_url,
                "title": track.title,
                "artist": track.artist,
                "duration_sec": track.duration_sec,
                "source": "youtube",
                "source_id": video_id,
                "shazam_matched": track.shazam_matched,
                "created_at": datetime.now(timezone.utc),
            }
            db.music_tracks.update_one(
                {"youtube_id": video_id},
                {
                    "$set": doc,
                    "$setOnInsert": {"first_imported_at": datetime.now(timezone.utc)},
                },
                upsert=True,
            )
            logger.info(f"[music-import] saved to music_tracks: {video_id}")
        except Exception as e:
            logger.warning(f"[music-import] MongoDB save failed (non-fatal): {e}")

    return track


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/search", response_model=list[SearchResult])
async def search_youtube(
    q: str,
    limit: int = 10,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Tìm kiếm YouTube theo tên bài hát/nghệ sĩ.
    Trả về tối đa `limit` kết quả (mặc định 10, tối đa 20).
    Không download gì — chỉ trả metadata để frontend hiển thị.
    """
    q = q.strip()
    if not q:
        raise HTTPException(status_code=400, detail="Query không được để trống")
    limit = min(max(limit, 1), 20)

    loop = asyncio.get_event_loop()
    try:
        results = await loop.run_in_executor(None, lambda: _search_youtube(q, limit))
    except Exception as e:
        logger.error(f"[music-search] error: {e}")
        raise HTTPException(status_code=500, detail="Lỗi khi tìm kiếm YouTube")

    return results


@router.get("/lyrics/{youtube_id}", response_model=LyricsResult)
async def get_lyrics(
    youtube_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Lấy lyrics EN+VI cho bài hát theo youtube_id.
    Tra cứu trong collection `song_lyrics` — trả 404 nếu không có.
    """
    db = _get_db()
    doc = db.song_lyrics.find_one(
        {"youtube_id": youtube_id},
        {
            "_id": 0,
            "title": 1,
            "artist": 1,
            "youtube_id": 1,
            "english_lyrics": 1,
            "vietnamese_lyrics": 1,
        },
    )
    if not doc:
        raise HTTPException(
            status_code=404, detail="Không tìm thấy lyrics cho bài hát này"
        )

    return LyricsResult(
        youtube_id=doc["youtube_id"],
        title=doc.get("title", ""),
        artist=doc.get("artist", ""),
        english_lyrics=doc.get("english_lyrics") or None,
        vietnamese_lyrics=doc.get("vietnamese_lyrics") or None,
        has_lyrics=bool(doc.get("english_lyrics")),
    )


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
    Dùng android_vr player client.
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
    Báo cáo: cookies có sẵn không + bgutil provider có chạy không.
    """
    cookies_ok = os.path.exists(YT_COOKIES_PATH)

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
        "cookies_path": YT_COOKIES_PATH,
        "cookies_present": cookies_ok,
        "bgutil_url": BGUTIL_URL,
        "bgutil_running": bgutil_ok,
        "youtube_ready": cookies_ok and bgutil_ok,
        "fallback_mode": not cookies_ok,  # True = dùng android_vr thay vì cookies+bgutil
    }
