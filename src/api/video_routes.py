"""
AI Video Generation API — Step-by-Step Flow

Step 1: POST /create            → create task with params
Step 2: POST /{id}/step1        → generate script (synchronous, ~10s)
        PUT  /{id}/step1        → user edits script
Step 3: POST /{id}/step2        → generate images in background (all scenes)
        POST /{id}/step2/{i}/regenerate → regenerate single image (sync)
Step 4: POST /{id}/step3        → generate audio in background (all scenes)
        POST /{id}/step3/{i}/regenerate → regenerate single audio (sync)
Step 5: POST /{id}/render       → enqueue final render job → worker handles it
        GET  /{id}              → poll task state at any time
        GET  /list              → user's video list
        DELETE /{id}            → delete task
"""

import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field

from src.database.db_manager import DBManager
from src.middleware.firebase_auth import get_current_user
from src.services.video_generation_service import DURATION_PRESETS

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/video", tags=["AI Video Generation"])

# ─────────────────────────────────────────────
# Pydantic models
# ─────────────────────────────────────────────

VALID_DURATIONS = list(DURATION_PRESETS.keys())  # [18, 30, 42, 60]
VALID_TTS = {"edge", "gemini"}
VALID_VOICES = {"NM1", "NM2", "NF", "SM", "SF"}
EDGE_VOICE_MAP = {
    "NM1": "vi-VN-NamMinhNeural",
    "NM2": "vi-VN-NamMinhNeural",
    "SM": "vi-VN-NamMinhNeural",
    "NF": "vi-VN-HoaiMyNeural",
    "SF": "vi-VN-HoaiMyNeural",
}


class CreateTaskRequest(BaseModel):
    topic: str = Field(..., min_length=3, max_length=300, description="Chủ đề video")
    duration_preset: int = Field(
        default=30,
        description="Thời lượng video: 18 | 30 | 42 | 60 (giây)",
    )
    tts_provider: str = Field(
        default="edge",
        description="TTS: edge (free multi-lang) | gemini (paid)",
    )
    voice: str = Field(
        default="NM1",
        description="Giọng đọc: NM1/NM2 → vi-VN-NamMinhNeural | NF/SF → vi-VN-HoaiMyNeural",
    )
    language: str = Field(default="vi", description="Ngôn ngữ: vi | en")
    mode: str = Field(
        default="slideshow",
        description="slideshow (Ken Burns + audio + subtitles) | ai_video (xAI images + Ken Burns)",
    )
    video_style: str = Field(
        default="cinematic",
        description="cinematic | anime | ads | documentary | cartoon",
    )
    target_audience: str = Field(
        default="general",
        description="Đối tượng khán giả (VD: học sinh phổ thông, công sở, ...)",
    )
    image_provider: str = Field(
        default="gemini",
        description="gemini (flash-image-preview) | xai (Grok Aurora)",
    )
    n_storyboards: int = Field(
        default=2,
        ge=1,
        le=3,
        description="Số kịch bản để chọn: 1 (single), 2–3 (có nhiều lựa chọn)",
    )


class EditScriptRequest(BaseModel):
    # Pick a storyboard variant (exclusive with title/scenes editing)
    variant_id: Optional[int] = Field(
        None,
        description="Chọn variant kịch bản (0/1/2) — khi status là 'step1_picking'",
    )
    # Direct script editing (requires title + scenes together)
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    scenes: Optional[List[Dict[str, str]]] = Field(
        None,
        description="List of scenes with narration, image_prompt, text_overlay",
    )


class EditImagePromptRequest(BaseModel):
    image_prompt: str = Field(..., min_length=5, max_length=1000)


# ─────────────────────────────────────────────
# DB helper
# ─────────────────────────────────────────────


def _get_db():
    return DBManager().db


# ─────────────────────────────────────────────
# Background task helpers
# ─────────────────────────────────────────────


async def _bg_generate_images(task_id: str, user_id: str) -> None:
    """Background: generate all scene images → upload to R2 → update MongoDB per scene."""
    import tempfile
    from pathlib import Path
    from src.services.video_generation_service import get_video_generation_service

    db = _get_db()
    svc = get_video_generation_service()

    task = db.video_tasks.find_one({"task_id": task_id})
    if not task:
        return

    scenes = task["step1"]["scenes"]
    n_scenes = len(scenes)
    image_provider = task.get("image_provider", "gemini")
    style_anchor = (task.get("step1") or {}).get("style_anchor", "")
    task_dir = Path(tempfile.mkdtemp(prefix=f"video_img_{task_id}_"))

    try:
        for i, scene in enumerate(scenes):
            try:
                db.video_tasks.update_one(
                    {"task_id": task_id},
                    {
                        "$set": {
                            f"step2.{i}.status": "generating",
                            "updated_at": datetime.utcnow(),
                        }
                    },
                )

                if image_provider == "xai":
                    img_path = await svc.generate_scene_image_xai(
                        prompt=scene["image_prompt"],
                        scene_index=i,
                        task_dir=task_dir,
                        style_anchor=style_anchor,
                    )
                else:
                    img_path = await svc.generate_scene_image(
                        prompt=scene["image_prompt"],
                        scene_index=i,
                        task_dir=task_dir,
                    )

                r2_key = f"video-assets/{user_id}/{task_id}/scene_{i:02d}.png"
                image_url = await svc.upload_asset_to_r2(img_path, r2_key, "image/png")
                img_path.unlink(missing_ok=True)

                db.video_tasks.update_one(
                    {"task_id": task_id},
                    {
                        "$set": {
                            f"step2.{i}.status": "done",
                            f"step2.{i}.image_url": image_url,
                            f"step2.{i}.image_r2_key": r2_key,
                            f"step2.{i}.error": None,
                            "updated_at": datetime.utcnow(),
                        }
                    },
                )
                logger.info(f"[{task_id[:8]}] Image {i}/{n_scenes-1} done")

            except Exception as e:
                logger.error(f"[{task_id[:8]}] Image {i} failed: {e}")
                db.video_tasks.update_one(
                    {"task_id": task_id},
                    {
                        "$set": {
                            f"step2.{i}.status": "failed",
                            f"step2.{i}.error": str(e)[:300],
                            "updated_at": datetime.utcnow(),
                        }
                    },
                )

        # Check if all done (no failed)
        task = db.video_tasks.find_one({"task_id": task_id})
        all_done = all(s["status"] == "done" for s in task.get("step2", []))
        any_failed = any(s["status"] == "failed" for s in task.get("step2", []))

        new_status = (
            "step2_done"
            if all_done
            else ("step2_partial" if not any_failed else "step2_failed")
        )
        db.video_tasks.update_one(
            {"task_id": task_id},
            {"$set": {"status": new_status, "updated_at": datetime.utcnow()}},
        )

    finally:
        import shutil

        shutil.rmtree(task_dir, ignore_errors=True)


async def _bg_generate_audio(task_id: str, user_id: str) -> None:
    """Background: generate all scene audio → upload to R2 → update MongoDB per scene."""
    import tempfile
    from pathlib import Path
    from src.services.video_generation_service import get_video_generation_service

    db = _get_db()
    svc = get_video_generation_service()

    task = db.video_tasks.find_one({"task_id": task_id})
    if not task:
        return

    scenes = task["step1"]["scenes"]
    n_scenes = len(scenes)
    tts_provider = task.get("tts_provider", "edge")
    voice = task.get("voice", "NM1")
    task_dir = Path(tempfile.mkdtemp(prefix=f"video_audio_{task_id}_"))

    try:
        for i, scene in enumerate(scenes):
            try:
                db.video_tasks.update_one(
                    {"task_id": task_id},
                    {
                        "$set": {
                            f"step3.{i}.status": "generating",
                            "updated_at": datetime.utcnow(),
                        }
                    },
                )

                audio_path = await svc.generate_scene_audio(
                    text=scene["narration"],
                    scene_index=i,
                    task_dir=task_dir,
                    tts_provider=tts_provider,
                    voice=voice,
                    edge_voice=EDGE_VOICE_MAP.get(voice, "vi-VN-NamMinhNeural"),
                )

                # Get audio duration
                import subprocess, json as json_lib

                probe = subprocess.run(
                    [
                        "ffprobe",
                        "-v",
                        "quiet",
                        "-print_format",
                        "json",
                        "-show_streams",
                        str(audio_path),
                    ],
                    capture_output=True,
                    text=True,
                )
                duration_sec = 0.0
                try:
                    streams = json_lib.loads(probe.stdout).get("streams", [])
                    if streams:
                        duration_sec = float(streams[0].get("duration", 0))
                except Exception:
                    pass

                r2_key = f"video-assets/{user_id}/{task_id}/scene_{i:02d}_audio.wav"
                audio_url = await svc.upload_asset_to_r2(
                    audio_path, r2_key, "audio/wav"
                )
                audio_path.unlink(missing_ok=True)

                db.video_tasks.update_one(
                    {"task_id": task_id},
                    {
                        "$set": {
                            f"step3.{i}.status": "done",
                            f"step3.{i}.audio_url": audio_url,
                            f"step3.{i}.audio_r2_key": r2_key,
                            f"step3.{i}.duration_seconds": round(duration_sec, 2),
                            f"step3.{i}.error": None,
                            "updated_at": datetime.utcnow(),
                        }
                    },
                )
                logger.info(
                    f"[{task_id[:8]}] Audio {i}/{n_scenes-1} done ({duration_sec:.1f}s)"
                )

            except Exception as e:
                logger.error(f"[{task_id[:8]}] Audio {i} failed: {e}")
                db.video_tasks.update_one(
                    {"task_id": task_id},
                    {
                        "$set": {
                            f"step3.{i}.status": "failed",
                            f"step3.{i}.error": str(e)[:300],
                            "updated_at": datetime.utcnow(),
                        }
                    },
                )

        task = db.video_tasks.find_one({"task_id": task_id})
        all_done = all(s["status"] == "done" for s in task.get("step3", []))
        any_failed = any(s["status"] == "failed" for s in task.get("step3", []))
        new_status = (
            "step3_done"
            if all_done
            else ("step3_partial" if not any_failed else "step3_failed")
        )
        db.video_tasks.update_one(
            {"task_id": task_id},
            {"$set": {"status": new_status, "updated_at": datetime.utcnow()}},
        )

    finally:
        import shutil

        shutil.rmtree(task_dir, ignore_errors=True)


# ─────────────────────────────────────────────
# Routes (static paths BEFORE parameterized)
# ─────────────────────────────────────────────


@router.get(
    "/list",
    summary="List User Videos",
    description="Danh sách video đã tạo của user (mới nhất trước).",
)
async def list_videos(
    limit: int = 20,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    user_id = current_user["uid"]
    db = _get_db()

    tasks = list(
        db.video_tasks.find(
            {"user_id": user_id},
            {
                "_id": 0,
                "task_id": 1,
                "topic": 1,
                "status": 1,
                "duration_preset": 1,
                "n_scenes": 1,
                "tts_provider": 1,
                "final_video_url": 1,
                "step1.title": 1,
                "created_at": 1,
                "updated_at": 1,
            },
        )
        .sort("created_at", -1)
        .limit(min(limit, 50))
    )

    for t in tasks:
        t.pop("_id", None)
        if t.get("created_at"):
            t["created_at"] = t["created_at"].isoformat()
        if t.get("updated_at"):
            t["updated_at"] = t["updated_at"].isoformat()

    return {"videos": tasks, "total": len(tasks)}


@router.post(
    "/create",
    summary="Create Video Task",
    description="""
Bước 0: Khởi tạo task video và xác nhận thông số.

**Duration presets:**
- 15s → 2 cảnh
- 30s → 4 cảnh
- 45s → 6 cảnh
- 60s → 8 cảnh

Sau khi tạo, gọi `POST /{task_id}/step1` để sinh kịch bản.
""",
)
async def create_task(
    request: CreateTaskRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    user_id = current_user["uid"]

    if request.duration_preset not in DURATION_PRESETS:
        raise HTTPException(400, f"duration_preset must be one of: {VALID_DURATIONS}")
    if request.tts_provider not in VALID_TTS:
        raise HTTPException(400, f"tts_provider must be one of: {VALID_TTS}")
    if request.voice.upper() not in VALID_VOICES:
        raise HTTPException(400, f"voice must be one of: {VALID_VOICES}")
    if request.image_provider not in ("gemini", "xai"):
        raise HTTPException(400, "image_provider must be 'gemini' or 'xai'")
    if request.mode not in ("slideshow", "ai_video"):
        raise HTTPException(400, "mode must be 'slideshow' or 'ai_video'")

    n_scenes = DURATION_PRESETS[request.duration_preset]["n_scenes"]
    task_id = str(uuid.uuid4())
    now = datetime.utcnow()

    db = _get_db()
    db.video_tasks.insert_one(
        {
            "task_id": task_id,
            "user_id": user_id,
            "topic": request.topic,
            "duration_preset": request.duration_preset,
            "n_scenes": n_scenes,
            "tts_provider": request.tts_provider,
            "voice": request.voice.upper(),
            "language": request.language,
            "mode": request.mode,
            "video_style": request.video_style,
            "target_audience": request.target_audience,
            "image_provider": request.image_provider,
            "n_storyboards": request.n_storyboards,
            "status": "created",
            "storyboards": None,
            "step1": None,
            "step2": None,
            "step3": None,
            "final_video_url": None,
            "render_error": None,
            "created_at": now,
            "updated_at": now,
        }
    )

    logger.info(
        f"🎬 New video task {task_id} — topic='{request.topic}', {request.duration_preset}s/{n_scenes} scenes, mode={request.mode}, provider={request.image_provider}"
    )

    return {
        "task_id": task_id,
        "status": "created",
        "topic": request.topic,
        "duration_preset": request.duration_preset,
        "n_scenes": n_scenes,
        "tts_provider": request.tts_provider,
        "voice": request.voice.upper(),
        "language": request.language,
        "mode": request.mode,
        "video_style": request.video_style,
        "image_provider": request.image_provider,
        "n_storyboards": request.n_storyboards,
        "created_at": now.isoformat(),
    }


# ── Step 1: Script ─────────────────────────────────────────────────────────


@router.post(
    "/{task_id}/step1",
    summary="Step 1 — Generate Script",
    description="""
**Sinh kịch bản video** bằng DeepSeek AI (~5–15 giây).

Trả về kịch bản gồm tiêu đề + danh sách cảnh (narration, image_prompt, text_overlay).

Sau khi nhận kịch bản, user có thể dùng `PUT /{task_id}/step1` để chỉnh sửa trước khi sang bước 2.
""",
)
async def generate_script(
    task_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    user_id = current_user["uid"]
    db = _get_db()

    task = db.video_tasks.find_one({"task_id": task_id, "user_id": user_id})
    if not task:
        raise HTTPException(404, "Task not found")
    if task["status"] not in ("created", "step1_done", "step1_picking", "step1_failed"):
        raise HTTPException(400, f"Cannot run step1 from status '{task['status']}'")

    db.video_tasks.update_one(
        {"task_id": task_id},
        {"$set": {"status": "step1_generating", "updated_at": datetime.utcnow()}},
    )

    try:
        from src.services.video_generation_service import get_video_generation_service

        svc = get_video_generation_service()
        n_storyboards = task.get("n_storyboards", 1)

        if n_storyboards > 1:
            # Generate multiple storyboard variants with DeepSeek Reasoner
            variants = await svc.generate_storyboards(
                topic=task["topic"],
                n_scenes=task["n_scenes"],
                language=task.get("language", "vi"),
                video_style=task.get("video_style", "cinematic"),
                target_audience=task.get("target_audience", "general"),
                n_variants=n_storyboards,
            )
            db.video_tasks.update_one(
                {"task_id": task_id},
                {
                    "$set": {
                        "storyboards": variants,
                        "step1": None,
                        "status": "step1_picking",
                        "updated_at": datetime.utcnow(),
                    }
                },
            )
            logger.info(f"[{task_id[:8]}] Step1 picking: {len(variants)} variants")
            return {
                "task_id": task_id,
                "status": "step1_picking",
                "storyboards": variants,
                "message": f'Có {len(variants)} kịch bản. Dùng PUT /{task_id}/step1 với {{"variant_id": 0}} để chọn.',
            }
        else:
            # Single script generation
            script = await svc.generate_script(
                topic=task["topic"],
                n_scenes=task["n_scenes"],
                language=task.get("language", "vi"),
            )

            scenes = script["scenes"][: task["n_scenes"]]
            for i, s in enumerate(scenes):
                s["scene_index"] = i

            step1 = {"title": script["title"], "style_anchor": "", "scenes": scenes}
            db.video_tasks.update_one(
                {"task_id": task_id},
                {
                    "$set": {
                        "step1": step1,
                        "status": "step1_done",
                        "updated_at": datetime.utcnow(),
                    }
                },
            )
            logger.info(
                f"[{task_id[:8]}] Step1 done: '{script['title']}' ({len(scenes)} scenes)"
            )
            return {
                "task_id": task_id,
                "status": "step1_done",
                "step1": step1,
            }

    except Exception as e:
        logger.error(f"[{task_id[:8]}] Step1 failed: {e}")
        db.video_tasks.update_one(
            {"task_id": task_id},
            {
                "$set": {
                    "status": "step1_failed",
                    "render_error": str(e)[:500],
                    "updated_at": datetime.utcnow(),
                }
            },
        )
        raise HTTPException(500, f"Script generation failed: {str(e)[:200]}")


@router.put(
    "/{task_id}/step1",
    summary="Step 1 — Edit Script",
    description="User chỉnh sửa kịch bản (title + scenes). Sau khi lưu, sang bước 2.",
)
async def update_script(
    task_id: str,
    body: EditScriptRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    user_id = current_user["uid"]
    db = _get_db()

    task = db.video_tasks.find_one({"task_id": task_id, "user_id": user_id})
    if not task:
        raise HTTPException(404, "Task not found")

    valid_statuses = (
        "step1_done",
        "step1_picking",
        "step2_generating",
        "step2_done",
        "step2_partial",
        "step2_failed",
    )
    if task["status"] not in valid_statuses:
        raise HTTPException(400, f"Cannot edit step1 from status '{task['status']}'")

    # ── Option 1: Pick storyboard variant ──────────────────────────────────
    if body.variant_id is not None:
        storyboards = task.get("storyboards") or []
        if body.variant_id >= len(storyboards):
            raise HTTPException(
                400,
                f"variant_id {body.variant_id} out of range (have {len(storyboards)})",
            )
        chosen = storyboards[body.variant_id]
        step1 = {
            "title": chosen["title"],
            "style_anchor": chosen.get("style_anchor", ""),
            "mood": chosen.get("mood", ""),
            "scenes": chosen["scenes"],
        }
        db.video_tasks.update_one(
            {"task_id": task_id},
            {
                "$set": {
                    "step1": step1,
                    "status": "step1_done",
                    "updated_at": datetime.utcnow(),
                }
            },
        )
        logger.info(
            f"[{task_id[:8]}] Step1: picked variant {body.variant_id} '{chosen['title']}'"
        )
        return {"task_id": task_id, "status": "step1_done", "step1": step1}

    # ── Option 2: Direct script edit (title + scenes) ──────────────────────
    if not body.title or not body.scenes:
        raise HTTPException(
            400,
            "Provide either variant_id (to pick storyboard) or both title + scenes (to edit)",
        )

    if len(body.scenes) != task["n_scenes"]:
        raise HTTPException(
            400,
            f"Expected {task['n_scenes']} scenes, got {len(body.scenes)}",
        )

    # Preserve existing style_anchor if not provided in edit
    existing_style_anchor = (task.get("step1") or {}).get("style_anchor", "")
    scenes = [dict(s, scene_index=i) for i, s in enumerate(body.scenes)]
    step1 = {
        "title": body.title,
        "style_anchor": existing_style_anchor,
        "scenes": scenes,
    }

    db.video_tasks.update_one(
        {"task_id": task_id},
        {
            "$set": {
                "step1": step1,
                "status": "step1_done",
                "updated_at": datetime.utcnow(),
            }
        },
    )

    return {"task_id": task_id, "status": "step1_done", "step1": step1}


# ── Step 2: Images ─────────────────────────────────────────────────────────


@router.post(
    "/{task_id}/step2",
    summary="Step 2 — Generate Images",
    description="""
**Sinh ảnh cho từng cảnh** bằng Gemini AI (~15-30s/cảnh, chạy background).

Poll `GET /{task_id}` mỗi 3s để xem tiến trình. Mỗi cảnh có trạng thái: pending → generating → done/failed.

Sau khi hoàn thành (`step2_done`), có thể dùng `POST /{task_id}/step2/{i}/regenerate` để sinh lại ảnh từng cảnh.
""",
)
async def generate_images(
    task_id: str,
    background_tasks: BackgroundTasks,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    user_id = current_user["uid"]
    db = _get_db()

    task = db.video_tasks.find_one({"task_id": task_id, "user_id": user_id})
    if not task:
        raise HTTPException(404, "Task not found")
    if task["status"] != "step1_done":
        raise HTTPException(
            400, f"Must complete step1 first (current: '{task['status']}')"
        )

    n = task["n_scenes"]
    step2_init = [
        {
            "scene_index": i,
            "status": "pending",
            "image_url": None,
            "image_r2_key": None,
            "error": None,
        }
        for i in range(n)
    ]
    db.video_tasks.update_one(
        {"task_id": task_id},
        {
            "$set": {
                "step2": step2_init,
                "status": "step2_generating",
                "updated_at": datetime.utcnow(),
            }
        },
    )

    background_tasks.add_task(_bg_generate_images, task_id, user_id)

    return {
        "task_id": task_id,
        "status": "step2_generating",
        "message": f"Đang sinh {n} ảnh... Poll GET /{task_id} để xem tiến trình.",
    }


@router.post(
    "/{task_id}/step2/{scene_index}/regenerate",
    summary="Step 2 — Regenerate Single Image",
    description="Sinh lại ảnh cho 1 cảnh cụ thể (dùng image_prompt hiện tại hoặc sau khi PUT để đổi prompt).",
)
async def regenerate_image(
    task_id: str,
    scene_index: int,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    user_id = current_user["uid"]
    db = _get_db()

    task = db.video_tasks.find_one({"task_id": task_id, "user_id": user_id})
    if not task:
        raise HTTPException(404, "Task not found")
    if task["status"] not in (
        "step2_done",
        "step2_partial",
        "step2_failed",
        "step3_done",
        "step3_partial",
        "step3_failed",
    ):
        raise HTTPException(400, f"Regenerate only available after step2")
    if scene_index < 0 or scene_index >= task["n_scenes"]:
        raise HTTPException(400, f"scene_index must be 0–{task['n_scenes']-1}")

    import tempfile
    from pathlib import Path
    from src.services.video_generation_service import get_video_generation_service

    svc = get_video_generation_service()
    scene = task["step1"]["scenes"][scene_index]

    db.video_tasks.update_one(
        {"task_id": task_id},
        {
            "$set": {
                f"step2.{scene_index}.status": "generating",
                "updated_at": datetime.utcnow(),
            }
        },
    )

    try:
        task_dir = Path(tempfile.mkdtemp(prefix=f"video_regen_{task_id}_"))
        try:
            image_provider = task.get("image_provider", "gemini")
            style_anchor = (task.get("step1") or {}).get("style_anchor", "")
            if image_provider == "xai":
                img_path = await svc.generate_scene_image_xai(
                    prompt=scene["image_prompt"],
                    scene_index=scene_index,
                    task_dir=task_dir,
                    style_anchor=style_anchor,
                )
            else:
                img_path = await svc.generate_scene_image(
                    prompt=scene["image_prompt"],
                    scene_index=scene_index,
                    task_dir=task_dir,
                )
            r2_key = f"video-assets/{user_id}/{task_id}/scene_{scene_index:02d}.png"
            image_url = await svc.upload_asset_to_r2(img_path, r2_key, "image/png")
        finally:
            import shutil

            shutil.rmtree(task_dir, ignore_errors=True)

        db.video_tasks.update_one(
            {"task_id": task_id},
            {
                "$set": {
                    f"step2.{scene_index}.status": "done",
                    f"step2.{scene_index}.image_url": image_url,
                    f"step2.{scene_index}.image_r2_key": r2_key,
                    f"step2.{scene_index}.error": None,
                    "updated_at": datetime.utcnow(),
                }
            },
        )

        return {
            "task_id": task_id,
            "scene_index": scene_index,
            "image_url": image_url,
            "status": "done",
        }

    except Exception as e:
        db.video_tasks.update_one(
            {"task_id": task_id},
            {
                "$set": {
                    f"step2.{scene_index}.status": "failed",
                    f"step2.{scene_index}.error": str(e)[:300],
                    "updated_at": datetime.utcnow(),
                }
            },
        )
        raise HTTPException(500, f"Image regeneration failed: {str(e)[:200]}")


@router.put(
    "/{task_id}/step2/{scene_index}",
    summary="Step 2 — Update Image Prompt",
    description="Cập nhật image_prompt của 1 cảnh, sau đó tự động sinh lại ảnh.",
)
async def update_image_prompt(
    task_id: str,
    scene_index: int,
    body: EditImagePromptRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    user_id = current_user["uid"]
    db = _get_db()

    task = db.video_tasks.find_one({"task_id": task_id, "user_id": user_id})
    if not task:
        raise HTTPException(404, "Task not found")
    if scene_index < 0 or scene_index >= task["n_scenes"]:
        raise HTTPException(400, "Invalid scene_index")

    # Update prompt in step1
    db.video_tasks.update_one(
        {"task_id": task_id},
        {
            "$set": {
                f"step1.scenes.{scene_index}.image_prompt": body.image_prompt,
                "updated_at": datetime.utcnow(),
            }
        },
    )

    # Re-use the regenerate logic by calling it directly
    from fastapi import Request as FRequest

    import tempfile
    from pathlib import Path
    from src.services.video_generation_service import get_video_generation_service

    svc = get_video_generation_service()
    db.video_tasks.update_one(
        {"task_id": task_id},
        {
            "$set": {
                f"step2.{scene_index}.status": "generating",
                "updated_at": datetime.utcnow(),
            }
        },
    )

    try:
        task_dir = Path(tempfile.mkdtemp(prefix=f"video_regen_{task_id}_"))
        try:
            image_provider = task.get("image_provider", "gemini")
            style_anchor = (task.get("step1") or {}).get("style_anchor", "")
            if image_provider == "xai":
                img_path = await svc.generate_scene_image_xai(
                    prompt=body.image_prompt,
                    scene_index=scene_index,
                    task_dir=task_dir,
                    style_anchor=style_anchor,
                )
            else:
                img_path = await svc.generate_scene_image(
                    prompt=body.image_prompt,
                    scene_index=scene_index,
                    task_dir=task_dir,
                )
            r2_key = f"video-assets/{user_id}/{task_id}/scene_{scene_index:02d}.png"
            image_url = await svc.upload_asset_to_r2(img_path, r2_key, "image/png")
        finally:
            import shutil

            shutil.rmtree(task_dir, ignore_errors=True)

        db.video_tasks.update_one(
            {"task_id": task_id},
            {
                "$set": {
                    f"step2.{scene_index}.status": "done",
                    f"step2.{scene_index}.image_url": image_url,
                    f"step2.{scene_index}.image_r2_key": r2_key,
                    f"step2.{scene_index}.error": None,
                    "updated_at": datetime.utcnow(),
                }
            },
        )
        return {
            "task_id": task_id,
            "scene_index": scene_index,
            "image_prompt": body.image_prompt,
            "image_url": image_url,
            "status": "done",
        }

    except Exception as e:
        db.video_tasks.update_one(
            {"task_id": task_id},
            {
                "$set": {
                    f"step2.{scene_index}.status": "failed",
                    f"step2.{scene_index}.error": str(e)[:300],
                    "updated_at": datetime.utcnow(),
                }
            },
        )
        raise HTTPException(500, f"Image generation failed: {str(e)[:200]}")


# ── Step 3: Audio ──────────────────────────────────────────────────────────


@router.post(
    "/{task_id}/step3",
    summary="Step 3 — Generate Audio",
    description="""
**Sinh audio TTS cho từng cảnh** (chạy background).

Poll `GET /{task_id}` mỗi 3s để xem tiến trình.

Sau khi hoàn thành (`step3_done`), dùng `POST /{task_id}/render` để export video.
""",
)
async def generate_audio(
    task_id: str,
    background_tasks: BackgroundTasks,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    user_id = current_user["uid"]
    db = _get_db()

    task = db.video_tasks.find_one({"task_id": task_id, "user_id": user_id})
    if not task:
        raise HTTPException(404, "Task not found")
    if task["status"] not in ("step2_done", "step2_partial"):
        raise HTTPException(
            400, f"Must complete step2 first (current: '{task['status']}')"
        )

    n = task["n_scenes"]
    step3_init = [
        {
            "scene_index": i,
            "status": "pending",
            "audio_url": None,
            "audio_r2_key": None,
            "duration_seconds": None,
            "error": None,
        }
        for i in range(n)
    ]
    db.video_tasks.update_one(
        {"task_id": task_id},
        {
            "$set": {
                "step3": step3_init,
                "status": "step3_generating",
                "updated_at": datetime.utcnow(),
            }
        },
    )

    background_tasks.add_task(_bg_generate_audio, task_id, user_id)

    return {
        "task_id": task_id,
        "status": "step3_generating",
        "message": f"Đang sinh {n} audio... Poll GET /{task_id} để xem tiến trình.",
    }


@router.post(
    "/{task_id}/step3/{scene_index}/regenerate",
    summary="Step 3 — Regenerate Single Audio",
    description="Sinh lại audio TTS cho 1 cảnh cụ thể.",
)
async def regenerate_audio(
    task_id: str,
    scene_index: int,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    user_id = current_user["uid"]
    db = _get_db()

    task = db.video_tasks.find_one({"task_id": task_id, "user_id": user_id})
    if not task:
        raise HTTPException(404, "Task not found")
    if task["status"] not in ("step3_done", "step3_partial", "step3_failed"):
        raise HTTPException(400, "Regenerate only available after step3")
    if scene_index < 0 or scene_index >= task["n_scenes"]:
        raise HTTPException(400, f"scene_index must be 0–{task['n_scenes']-1}")

    import tempfile
    from pathlib import Path
    from src.services.video_generation_service import get_video_generation_service

    svc = get_video_generation_service()
    scene = task["step1"]["scenes"][scene_index]
    tts_provider = task.get("tts_provider", "edge")
    voice = task.get("voice", "NM1")

    db.video_tasks.update_one(
        {"task_id": task_id},
        {
            "$set": {
                f"step3.{scene_index}.status": "generating",
                "updated_at": datetime.utcnow(),
            }
        },
    )

    try:
        task_dir = Path(tempfile.mkdtemp(prefix=f"video_audio_{task_id}_"))
        try:
            audio_path = await svc.generate_scene_audio(
                text=scene["narration"],
                scene_index=scene_index,
                task_dir=task_dir,
                tts_provider=tts_provider,
                voice=voice,
                edge_voice=EDGE_VOICE_MAP.get(voice, "vi-VN-NamMinhNeural"),
            )

            import subprocess, json as json_lib

            probe = subprocess.run(
                [
                    "ffprobe",
                    "-v",
                    "quiet",
                    "-print_format",
                    "json",
                    "-show_streams",
                    str(audio_path),
                ],
                capture_output=True,
                text=True,
            )
            duration_sec = 0.0
            try:
                streams = json_lib.loads(probe.stdout).get("streams", [])
                if streams:
                    duration_sec = float(streams[0].get("duration", 0))
            except Exception:
                pass

            r2_key = (
                f"video-assets/{user_id}/{task_id}/scene_{scene_index:02d}_audio.wav"
            )
            audio_url = await svc.upload_asset_to_r2(audio_path, r2_key, "audio/wav")
        finally:
            import shutil

            shutil.rmtree(task_dir, ignore_errors=True)

        db.video_tasks.update_one(
            {"task_id": task_id},
            {
                "$set": {
                    f"step3.{scene_index}.status": "done",
                    f"step3.{scene_index}.audio_url": audio_url,
                    f"step3.{scene_index}.audio_r2_key": r2_key,
                    f"step3.{scene_index}.duration_seconds": round(duration_sec, 2),
                    f"step3.{scene_index}.error": None,
                    "updated_at": datetime.utcnow(),
                }
            },
        )

        return {
            "task_id": task_id,
            "scene_index": scene_index,
            "audio_url": audio_url,
            "duration_seconds": round(duration_sec, 2),
            "status": "done",
        }

    except Exception as e:
        db.video_tasks.update_one(
            {"task_id": task_id},
            {
                "$set": {
                    f"step3.{scene_index}.status": "failed",
                    f"step3.{scene_index}.error": str(e)[:300],
                    "updated_at": datetime.utcnow(),
                }
            },
        )
        raise HTTPException(500, f"Audio regeneration failed: {str(e)[:200]}")


# ── Step 4: Render ─────────────────────────────────────────────────────────


@router.post(
    "/{task_id}/render",
    summary="Step 4 — Render Final Video",
    description="""
**Bắt đầu render video** (Playwright + FFmpeg).

Job được đẩy vào Redis queue `queue:video_generation` và xử lý bởi `video_generation_worker`.

Poll `GET /{task_id}` cho đến khi status = `completed` hoặc `failed`.
""",
)
async def render_video(
    task_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    user_id = current_user["uid"]
    db = _get_db()

    task = db.video_tasks.find_one({"task_id": task_id, "user_id": user_id})
    if not task:
        raise HTTPException(404, "Task not found")
    if task["status"] not in ("step3_done", "step3_partial"):
        raise HTTPException(
            400, f"Must complete step3 first (current: '{task['status']}')"
        )

    # Push render job to Redis queue
    import redis.asyncio as aioredis

    redis_url = __import__("os").getenv("REDIS_URL", "redis://redis-server:6379")
    redis_client = aioredis.from_url(redis_url, decode_responses=True)

    job_payload = json.dumps({"task_id": task_id, "user_id": user_id})
    await redis_client.lpush("queue:video_generation", job_payload)
    await redis_client.aclose()

    db.video_tasks.update_one(
        {"task_id": task_id},
        {
            "$set": {
                "status": "rendering",
                "render_error": None,
                "updated_at": datetime.utcnow(),
            }
        },
    )

    logger.info(f"[{task_id[:8]}] Render job queued")

    return {
        "task_id": task_id,
        "status": "rendering",
        "message": "Video đang được render... Poll GET /{task_id} cho đến khi completed.",
    }


# ── Task state & delete ────────────────────────────────────────────────────


@router.get(
    "/{task_id}",
    summary="Get Video Task State",
    description="Lấy toàn bộ trạng thái task (dùng để poll tiến trình).",
)
async def get_task(
    task_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    user_id = current_user["uid"]
    db = _get_db()

    task = db.video_tasks.find_one({"task_id": task_id, "user_id": user_id}, {"_id": 0})
    if not task:
        raise HTTPException(404, "Task not found")

    if task.get("created_at"):
        task["created_at"] = task["created_at"].isoformat()
    if task.get("updated_at"):
        task["updated_at"] = task["updated_at"].isoformat()

    return task


@router.delete(
    "/{task_id}",
    summary="Delete Video Task",
    description="Xóa task (chỉ khi không đang processing/rendering).",
)
async def delete_task(
    task_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    user_id = current_user["uid"]
    db = _get_db()

    task = db.video_tasks.find_one({"task_id": task_id, "user_id": user_id})
    if not task:
        raise HTTPException(404, "Task not found")
    if task["status"] in (
        "step1_generating",
        "step2_generating",
        "step3_generating",
        "rendering",
    ):
        raise HTTPException(400, "Cannot delete a task that is currently processing")

    db.video_tasks.delete_one({"task_id": task_id, "user_id": user_id})
    return {"message": "Task deleted", "task_id": task_id}
