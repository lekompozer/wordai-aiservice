"""
AI Video Studio API Routes
Interactive pipeline: generate-story → generate-narration → generate-script → generate-media

All AI-calling endpoints use Redis Queue pattern (SYSTEM_REFERENCE.md standard).
Stateless for AI steps — frontend stores results in localStorage.
"""

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from src.database.db_manager import DBManager
from src.middleware.firebase_auth import get_current_user
from src.queue.queue_dependencies import get_video_studio_queue
from src.queue.queue_manager import get_job_status, set_job_status
from src.models.ai_queue_tasks import VideoStudioTask
from src.services.video_generation_service import DURATION_PRESETS

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/video-studio", tags=["AI Video Studio"])

VALID_DURATIONS = list(DURATION_PRESETS.keys())


def get_db():
    return DBManager().db


# ─────────────────────────────────────────────
# Pydantic models
# ─────────────────────────────────────────────


class GenerateStoryRequest(BaseModel):
    projectId: str = Field(..., description="Frontend project ID")
    purpose: str = Field(
        ..., description="ads | storytelling | education | software_intro | corporate"
    )
    prompt: str = Field(..., min_length=5, max_length=1000)
    platform: str = Field(
        default="tiktok",
        description="tiktok | youtube_shorts | instagram_reels | youtube",
    )
    duration: int = Field(..., description="12 | 30 | 42 | 60 | 90 | 120 (seconds)")
    language: str = Field(default="vi", description="vi | en")
    visualStyle: Optional[str] = Field(None)


class GenerateNarrationRequest(BaseModel):
    projectId: str
    story: Dict[str, Any] = Field(
        ..., description="Story structure from generate-story"
    )
    duration: int
    language: str = Field(default="vi")
    platform: Optional[str] = Field(None)
    character: Optional[str] = Field(None)
    music: Optional[str] = Field(None)
    extraInstructions: Optional[str] = Field(None)


class GenerateScriptRequest(BaseModel):
    projectId: str
    purpose: str
    prompt: str = Field(..., min_length=5, max_length=1000)
    visualStyle: str = Field(default="Cinematic")
    duration: int
    aspectRatio: str = Field(default="9:16")
    language: str = Field(default="vi")
    narrator: Optional[str] = Field(None)
    platform: Optional[str] = Field(default="tiktok")
    character: Optional[str] = Field(None)
    music: Optional[str] = Field(None)
    narration: str = Field(
        ..., min_length=10, description="Required: narration text from step 1b"
    )
    extraInstructions: Optional[str] = Field(None)


class GenerateImageRequest(BaseModel):
    projectId: str
    sceneIndex: int = Field(..., ge=0)
    imagePrompt: str = Field(..., min_length=10)
    visualStyle: Optional[str] = Field(default="Cinematic")
    aspectRatio: Optional[str] = Field(default="9:16")
    modelHint: Optional[str] = Field(default="gemini", description="gemini | xai")


class TTSRequest(BaseModel):
    projectId: str
    sceneIndex: int = Field(..., ge=0)
    text: str = Field(..., min_length=1)
    narrator: Optional[str] = Field(
        default="Hà Nữ", description="Hà Nữ | Nam | Glen | Sara"
    )
    language: Optional[str] = Field(default="vi")


class SaveStoryboardRequest(BaseModel):
    projectId: str
    brief: Dict[str, Any]
    scenes: List[Dict[str, Any]]


class JobStatusResponse(BaseModel):
    jobId: str
    status: str
    taskType: Optional[str] = None
    projectId: Optional[str] = None
    createdAt: Optional[str] = None
    startedAt: Optional[str] = None
    completedAt: Optional[str] = None
    failedAt: Optional[str] = None
    error: Optional[str] = None
    # Completed result fields (populated based on task_type)
    result: Optional[Dict[str, Any]] = None


# ─────────────────────────────────────────────
# STEP 1a: generate-story
# ─────────────────────────────────────────────


@router.post("/generate-story", summary="Step 1a: Idea → Story Structure")
async def generate_story(
    body: GenerateStoryRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Enqueue a generate_story job.
    Returns job_id to poll via GET /jobs/{job_id}.

    Flow: brief → deepseek-reasoner → {title, hook, beats[], tone, pacing}
    """
    if body.duration not in VALID_DURATIONS:
        raise HTTPException(400, f"Invalid duration. Valid: {VALID_DURATIONS}")

    user_id = current_user["uid"]
    job_id = f"vss_{uuid.uuid4().hex[:12]}"

    queue = await get_video_studio_queue()

    await set_job_status(
        redis_client=queue.redis_client,
        job_id=job_id,
        status="pending",
        user_id=user_id,
        task_type="generate_story",
        project_id=body.projectId,
        created_at=datetime.utcnow().isoformat(),
    )

    task = VideoStudioTask(  # type: ignore[call-arg]
        task_id=job_id,
        job_id=job_id,
        user_id=user_id,
        task_type="generate_story",
        project_id=body.projectId,
        brief={
            "purpose": body.purpose,
            "prompt": body.prompt,
            "platform": body.platform,
            "duration": body.duration,
            "language": body.language,
            "visualStyle": body.visualStyle,
        },
    )
    await queue.enqueue_generic_task(task)

    logger.info(f"✅ generate-story enqueued job={job_id} project={body.projectId}")
    return {
        "jobId": job_id,
        "status": "pending",
        "projectId": body.projectId,
        "estimatedSeconds": 40,
    }


# ─────────────────────────────────────────────
# STEP 1b: generate-narration
# ─────────────────────────────────────────────


@router.post("/generate-narration", summary="Step 1b: Story beats → Narration")
async def generate_narration(
    body: GenerateNarrationRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Enqueue a generate_narration job.

    Requires story object (from generate-story or user-written).
    Returns job_id to poll via GET /jobs/{job_id}.
    """
    if body.duration not in VALID_DURATIONS:
        raise HTTPException(400, f"Invalid duration. Valid: {VALID_DURATIONS}")

    story = body.story
    if not story.get("beats"):
        raise HTTPException(400, "story.beats is required and must not be empty")

    user_id = current_user["uid"]
    job_id = f"vsn_{uuid.uuid4().hex[:12]}"

    queue = await get_video_studio_queue()

    await set_job_status(
        redis_client=queue.redis_client,
        job_id=job_id,
        status="pending",
        user_id=user_id,
        task_type="generate_narration",
        project_id=body.projectId,
        created_at=datetime.utcnow().isoformat(),
    )

    task = VideoStudioTask(  # type: ignore[call-arg]
        task_id=job_id,
        job_id=job_id,
        user_id=user_id,
        task_type="generate_narration",
        project_id=body.projectId,
        story=story,
        brief={
            "duration": body.duration,
            "language": body.language,
            "platform": body.platform,
            "character": body.character,
            "music": body.music,
            "extraInstructions": body.extraInstructions,
        },
    )
    await queue.enqueue_generic_task(task)

    logger.info(f"✅ generate-narration enqueued job={job_id} project={body.projectId}")
    return {
        "jobId": job_id,
        "status": "pending",
        "projectId": body.projectId,
        "estimatedSeconds": 40,
    }


# ─────────────────────────────────────────────
# STEP 2A: generate-script
# ─────────────────────────────────────────────


@router.post("/generate-script", summary="Step 2A: Narration → Scene Script")
async def generate_script(
    body: GenerateScriptRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Enqueue a generate_script job.

    narration field is REQUIRED (from generate-narration or user-written).
    Returns job_id to poll via GET /jobs/{job_id}.
    """
    if body.duration not in VALID_DURATIONS:
        raise HTTPException(400, f"Invalid duration. Valid: {VALID_DURATIONS}")

    user_id = current_user["uid"]
    job_id = f"vsc_{uuid.uuid4().hex[:12]}"

    n_scenes = DURATION_PRESETS[body.duration]["n_scenes"]

    queue = await get_video_studio_queue()

    await set_job_status(
        redis_client=queue.redis_client,
        job_id=job_id,
        status="pending",
        user_id=user_id,
        task_type="generate_script",
        project_id=body.projectId,
        n_scenes=n_scenes,
        created_at=datetime.utcnow().isoformat(),
    )

    task = VideoStudioTask(  # type: ignore[call-arg]
        task_id=job_id,
        job_id=job_id,
        user_id=user_id,
        task_type="generate_script",
        project_id=body.projectId,
        n_scenes=n_scenes,
        brief={
            "purpose": body.purpose,
            "prompt": body.prompt,
            "visualStyle": body.visualStyle,
            "duration": body.duration,
            "aspectRatio": body.aspectRatio,
            "language": body.language,
            "narrator": body.narrator,
            "platform": body.platform,
            "character": body.character,
            "music": body.music,
            "narration": body.narration,
            "extraInstructions": body.extraInstructions,
        },
    )
    await queue.enqueue_generic_task(task)

    logger.info(
        f"✅ generate-script enqueued job={job_id} n_scenes={n_scenes} project={body.projectId}"
    )
    return {
        "jobId": job_id,
        "status": "pending",
        "projectId": body.projectId,
        "nScenes": n_scenes,
        "estimatedSeconds": 90,
    }


# ─────────────────────────────────────────────
# STEP 2B: per-scene generate-image
# ─────────────────────────────────────────────


@router.post("/generate-image", summary="Step 2B: Generate scene image (async)")
async def generate_image(
    body: GenerateImageRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Enqueue a generate_image job for a single scene."""
    user_id = current_user["uid"]
    job_id = f"vsi_{uuid.uuid4().hex[:12]}"

    queue = await get_video_studio_queue()

    await set_job_status(
        redis_client=queue.redis_client,
        job_id=job_id,
        status="pending",
        user_id=user_id,
        task_type="generate_image",
        project_id=body.projectId,
        scene_index=body.sceneIndex,
        created_at=datetime.utcnow().isoformat(),
    )

    task = VideoStudioTask(  # type: ignore[call-arg]
        task_id=job_id,
        job_id=job_id,
        user_id=user_id,
        task_type="generate_image",
        project_id=body.projectId,
        scene_index=body.sceneIndex,
        image_prompt=body.imagePrompt,
        visual_style=body.visualStyle,
        aspect_ratio=body.aspectRatio,
        model_hint=body.modelHint or "gemini",
    )
    await queue.enqueue_generic_task(task)

    return {
        "jobId": job_id,
        "sceneIndex": body.sceneIndex,
        "status": "pending",
        "estimatedSeconds": 15,
    }


# ─────────────────────────────────────────────
# STEP 2B: per-scene TTS
# ─────────────────────────────────────────────


@router.post("/tts", summary="Step 2B: Generate scene TTS audio (async)")
async def generate_tts(
    body: TTSRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Enqueue a TTS job for a single scene."""
    user_id = current_user["uid"]
    job_id = f"vst_{uuid.uuid4().hex[:12]}"

    queue = await get_video_studio_queue()

    await set_job_status(
        redis_client=queue.redis_client,
        job_id=job_id,
        status="pending",
        user_id=user_id,
        task_type="tts",
        project_id=body.projectId,
        scene_index=body.sceneIndex,
        created_at=datetime.utcnow().isoformat(),
    )

    task = VideoStudioTask(  # type: ignore[call-arg]
        task_id=job_id,
        job_id=job_id,
        user_id=user_id,
        task_type="tts",
        project_id=body.projectId,
        scene_index=body.sceneIndex,
        scene_text=body.text,
        narrator=body.narrator,
        language=body.language,
    )
    await queue.enqueue_generic_task(task)

    return {
        "jobId": job_id,
        "sceneIndex": body.sceneIndex,
        "status": "pending",
        "estimatedSeconds": 8,
    }


# ─────────────────────────────────────────────
# Job status polling (all job types)
# ─────────────────────────────────────────────


@router.get(
    "/jobs/{job_id}", response_model=JobStatusResponse, summary="Poll any job status"
)
async def get_job(
    job_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Poll job status for any Video Studio job (story / narration / script / image / tts).

    Status: pending → processing → completed | failed

    Result fields vary by task_type:
      generate_story:     result.title, .hook, .beats, .tone, .pacing
      generate_narration: result.suggestedTitle, .narration, .hookStrengthScore
      generate_script:    result.title, .styleAnchor, .mood, .scenes
      generate_image:     result.imageUrl
      tts:                result.audioUrl, .durationSeconds
    """
    queue = await get_video_studio_queue()
    job = await get_job_status(queue.redis_client, job_id)

    if not job:
        raise HTTPException(404, f"Job {job_id} not found (expired or invalid)")

    if job.get("user_id") != current_user["uid"]:
        raise HTTPException(403, "Not authorized to view this job")

    status = job.get("status", "pending")
    task_type = job.get("task_type", "")

    # Build result payload based on task_type and status
    result = None
    if status == "completed":
        if task_type == "generate_story":
            result = {
                "title": job.get("title"),
                "hook": job.get("hook"),
                "beats": job.get("beats"),
                "tone": job.get("tone"),
                "pacing": job.get("pacing"),
            }
        elif task_type == "generate_narration":
            result = {
                "suggestedTitle": job.get("suggested_title"),
                "narration": job.get("narration"),
                "hookStrengthScore": job.get("hook_strength_score"),
            }
        elif task_type == "generate_script":
            result = {
                "title": job.get("title"),
                "styleAnchor": job.get("style_anchor"),
                "mood": job.get("mood"),
                "scenes": job.get("scenes"),
            }
        elif task_type == "generate_image":
            result = {
                "imageUrl": job.get("image_url"),
                "sceneIndex": job.get("scene_index"),
            }
        elif task_type == "tts":
            result = {
                "audioUrl": job.get("audio_url"),
                "durationSeconds": job.get("duration_seconds"),
                "sceneIndex": job.get("scene_index"),
            }

    return JobStatusResponse(
        jobId=job_id,
        status=status,
        taskType=task_type,
        projectId=job.get("project_id"),
        createdAt=job.get("created_at"),
        startedAt=job.get("started_at"),
        completedAt=job.get("completed_at"),
        failedAt=job.get("failed_at"),
        error=job.get("error") if status == "failed" else None,
        result=result,
    )


# ─────────────────────────────────────────────
# Storyboard save / load (MongoDB — not async)
# ─────────────────────────────────────────────


@router.post("/storyboards", summary="Save storyboard to DB")
async def save_storyboard(
    body: SaveStoryboardRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_db),
):
    user_id = current_user["uid"]

    existing = db.video_studio_storyboards.find_one(
        {"project_id": body.projectId, "user_id": user_id}
    )
    version = (existing.get("version", 0) + 1) if existing else 1
    now = datetime.utcnow()

    db.video_studio_storyboards.update_one(
        {"project_id": body.projectId, "user_id": user_id},
        {
            "$set": {
                "project_id": body.projectId,
                "user_id": user_id,
                "brief": body.brief,
                "scenes": body.scenes,
                "version": version,
                "saved_at": now,
            }
        },
        upsert=True,
    )

    return {
        "projectId": body.projectId,
        "version": version,
        "savedAt": now.isoformat(),
    }


@router.get("/storyboards/{project_id}", summary="Load storyboard from DB")
async def load_storyboard(
    project_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db=Depends(get_db),
):
    user_id = current_user["uid"]
    doc = db.video_studio_storyboards.find_one(
        {"project_id": project_id, "user_id": user_id},
        {"_id": 0},
    )
    if not doc:
        raise HTTPException(404, "Storyboard not found")

    # Convert datetime to ISO string if needed
    if hasattr(doc.get("saved_at"), "isoformat"):
        doc["saved_at"] = doc["saved_at"].isoformat()

    return doc
