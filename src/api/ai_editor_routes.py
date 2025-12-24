"""
AI Editor API Routes
AI-powered document editing features: Edit, Translate, Format, Bilingual Conversion
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from enum import Enum
import json
from datetime import datetime

from src.middleware.firebase_auth import require_auth
from src.services.document_manager import document_manager
from src.services.book_chapter_manager import GuideBookBookChapterManager
from src.services.ai_chat_service import ai_chat_service, AIProvider
from src.services.subscription_service import get_subscription_service
from src.services.points_service import get_points_service
from src.queue.queue_dependencies import get_ai_editor_queue
from src.queue.queue_manager import set_job_status, get_job_status
from src.models.ai_queue_tasks import AIEditorTask
from src.models.ai_editor_job_models import (
    CreateAIEditorJobResponse,
    AIEditorJobStatusResponse,
    AIEditorJobType,
    AIEditorJobStatus,
)
from src.utils.logger import setup_logger
from src.database.db_manager import DBManager

logger = setup_logger()
router = APIRouter(prefix="/api/ai/editor", tags=["AI Editor"])

# Initialize database and chapter manager
db_manager = DBManager()
db = db_manager.db
chapter_manager = GuideBookBookChapterManager(db)


# ============ ENUMS ============


class DocumentType(str, Enum):
    """Document types for context-aware formatting"""

    DOC = "doc"
    SLIDE = "slide"
    NOTE = "note"


class BilingualStyle(str, Enum):
    """Bilingual conversion styles"""

    SLASH_SEPARATED = "slash_separated"  # "English / Vietnamese"
    LINE_BREAK = "line_break"  # "English<br>Vietnamese"


# ============ HELPER FUNCTIONS ============


async def get_content_context(
    document_id: Optional[str], chapter_id: Optional[str], user_id: str
) -> Dict[str, Any]:
    """
    Unified content fetching for both documents and chapters.

    Returns:
        dict with keys:
        - content_html: str (full HTML content)
        - resource_id: str (document_id or chapter_id)
        - resource_type: str ('document' or 'chapter')
        - doc_type: str ('doc', 'slide', or 'note')
    """
    # Validate that exactly one ID is provided
    if not document_id and not chapter_id:
        raise HTTPException(
            status_code=400, detail="Either document_id or chapter_id must be provided"
        )
    if document_id and chapter_id:
        raise HTTPException(
            status_code=400, detail="Cannot provide both document_id and chapter_id"
        )

    if chapter_id:
        # Fetch chapter content
        logger.info(f"📖 Fetching content for chapter_id: {chapter_id}")
        try:
            chapter_data = chapter_manager.get_chapter_with_content(
                chapter_id=chapter_id
            )

            if not chapter_data:
                raise HTTPException(
                    status_code=404, detail="Chapter not found or access denied"
                )

            content_html = chapter_data.get("content_html", "")
            if not content_html:
                raise HTTPException(status_code=404, detail="Chapter content is empty")

            logger.info(
                f"✅ Fetched {len(content_html):,} chars from chapter '{chapter_data.get('title')}'"
            )

            return {
                "content_html": content_html,
                "resource_id": chapter_id,
                "resource_type": "chapter",
                "doc_type": "doc",  # Chapters are always treated as documents (not slides)
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"❌ Failed to fetch chapter: {e}")
            raise HTTPException(
                status_code=500, detail=f"Failed to fetch chapter content: {str(e)}"
            )

    else:  # document_id
        # Fetch document content
        logger.info(f"📄 Fetching content for document_id: {document_id}")
        try:
            doc = document_manager.get_document(document_id, user_id)

            if not doc:
                raise HTTPException(status_code=404, detail="Document not found")

            content_html = doc.get("content_html", "")
            doc_type = doc.get("type", "doc")  # "doc", "slide", or "note"

            logger.info(
                f"✅ Fetched {len(content_html):,} chars from document (type: {doc_type})"
            )

            return {
                "content_html": content_html,
                "resource_id": document_id,
                "resource_type": "document",
                "doc_type": doc_type,
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"❌ Failed to fetch document: {e}")
            raise HTTPException(status_code=404, detail=f"Document not found: {str(e)}")


# ============ MODELS ============


class AIEditRequest(BaseModel):
    document_id: Optional[str] = Field(
        None, description="Document ID (use document_id OR chapter_id)"
    )
    chapter_id: Optional[str] = Field(
        None, description="Chapter ID (use document_id OR chapter_id)"
    )
    context_html: str = Field(..., description="HTML content to edit")
    user_prompt: str = Field(..., description="User's editing instruction")
    selection_only: bool = Field(
        False, description="Whether editing only selected text"
    )

    def validate_ids(self):
        """Ensure either document_id or chapter_id is provided"""
        if not self.document_id and not self.chapter_id:
            raise ValueError("Either document_id or chapter_id must be provided")
        if self.document_id and self.chapter_id:
            raise ValueError("Cannot provide both document_id and chapter_id")


class AITranslateRequest(BaseModel):
    document_id: Optional[str] = Field(
        None, description="Document ID (use document_id OR chapter_id)"
    )
    chapter_id: Optional[str] = Field(
        None, description="Chapter ID (use document_id OR chapter_id)"
    )
    context_html: str = Field(..., description="HTML content to translate")
    target_language: str = Field(
        ..., description="Target language (e.g., 'Vietnamese', 'English')"
    )
    selection_only: bool = Field(
        False, description="Whether translating only selected text"
    )

    def validate_ids(self):
        """Ensure either document_id or chapter_id is provided"""
        if not self.document_id and not self.chapter_id:
            raise ValueError("Either document_id or chapter_id must be provided")
        if self.document_id and self.chapter_id:
            raise ValueError("Cannot provide both document_id and chapter_id")


class AIFormatRequest(BaseModel):
    document_id: Optional[str] = Field(
        None, description="Document ID (use document_id OR chapter_id)"
    )
    chapter_id: Optional[str] = Field(
        None, description="Chapter ID (use document_id OR chapter_id)"
    )
    context_html: str = Field(..., description="HTML content to format")
    scope: str = Field(..., description="'selection' or 'document'")
    document_type: Optional[DocumentType] = Field(
        None, description="Document type for context-aware formatting"
    )
    user_query: Optional[str] = Field(
        None, description="Additional user formatting instruction"
    )

    # Slide-specific fields (optional, for slides only)
    slide_index: Optional[int] = Field(None, description="Slide index (for slides)")
    elements: Optional[List[Dict[str, Any]]] = Field(
        None, description="Slide elements (shapes, images, videos, text boxes)"
    )
    background: Optional[Dict[str, Any]] = Field(
        None, description="Slide background (color, gradient, image)"
    )

    def validate_ids(self):
        """Ensure either document_id or chapter_id is provided"""
        if not self.document_id and not self.chapter_id:
            raise ValueError("Either document_id or chapter_id must be provided")
        if self.document_id and self.chapter_id:
            raise ValueError("Cannot provide both document_id and chapter_id")


class BilingualConvertRequest(BaseModel):
    document_id: Optional[str] = Field(
        None, description="Document ID (use document_id OR chapter_id)"
    )
    chapter_id: Optional[str] = Field(
        None, description="Chapter ID (use document_id OR chapter_id)"
    )
    source_language: str = Field(..., description="Source language (e.g., 'English')")
    target_language: str = Field(
        ..., description="Target language (e.g., 'Vietnamese')"
    )
    style: BilingualStyle = Field(
        BilingualStyle.SLASH_SEPARATED, description="Bilingual format style"
    )

    def validate_ids(self):
        """Ensure either document_id or chapter_id is provided"""
        if not self.document_id and not self.chapter_id:
            raise ValueError("Either document_id or chapter_id must be provided")
        if self.document_id and self.chapter_id:
            raise ValueError("Cannot provide both document_id and chapter_id")


class AIEditorResponse(BaseModel):
    success: bool = Field(..., description="Whether the operation was successful")
    edited_html: Optional[str] = Field(None, description="Edited HTML content")
    error: Optional[str] = Field(None, description="Error message if failed")
    new_resource_id: Optional[str] = Field(
        None, description="ID of newly created chapter/document (bilingual only)"
    )
    new_resource_title: Optional[str] = Field(
        None, description="Title of newly created resource (bilingual only)"
    )


# ============ ENDPOINTS ============


@router.post("/edit-by-ai", response_model=CreateAIEditorJobResponse)
async def edit_by_ai(request: AIEditRequest, user_info: dict = Depends(require_auth)):
    """
    Edit document or chapter content based on user's natural language instruction
    Uses Redis queue for async processing - returns job_id immediately

    **Cost: 2 points** (AI operation)
    **Processing time**: 1-5 minutes

    **Supports**: document_id OR chapter_id

    **Returns**: job_id for polling at GET /api/ai/editor/jobs/{job_id}
    """
    try:
        user_id = user_info["uid"]
        resource_id = request.document_id or request.chapter_id
        resource_type = "chapter" if request.chapter_id else "document"

        logger.info(f"🎨 Edit by AI request from user {user_id}")
        logger.info(
            f"{resource_type.capitalize()} ID: {resource_id}, Prompt: {request.user_prompt}"
        )

        # Validate IDs
        request.validate_ids()

        # === CHECK POINTS (AI OPERATION: 5 points for Claude/slides, 2 for others) ===
        points_service = get_points_service()
        # Note: We charge 5 points upfront, but actual cost depends on content type
        # Slides use Claude (5 points), documents use Gemini (2 points)
        # For now, charge maximum to avoid insufficient points errors
        points_needed = 5

        check_result = await points_service.check_sufficient_points(
            user_id=user_id, points_needed=points_needed, service="ai_edit"
        )

        if not check_result["has_points"]:
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "insufficient_points",
                    "message": f"Không đủ points để dùng AI Edit. Cần: {points_needed}, Còn: {check_result['points_available']}",
                    "points_needed": points_needed,
                    "points_available": check_result["points_available"],
                    "upgrade_url": "/pricing",
                },
            )

        logger.info(
            f"✅ Points check passed - {check_result['points_available']} points available"
        )

        # === FETCH CONTENT CONTEXT ===
        context = await get_content_context(
            document_id=request.document_id,
            chapter_id=request.chapter_id,
            user_id=user_id,
        )

        doc_type = context["doc_type"]
        content_length = len(request.context_html)
        logger.info(f"📄 Content type: {doc_type}, size: {content_length:,} chars")

        # Check content size
        MAX_CONTENT_SIZE = 500_000  # 500K chars safety limit
        if content_length > MAX_CONTENT_SIZE:
            logger.error(f"❌ Content too large: {content_length:,} chars")
            raise HTTPException(
                status_code=400,
                detail=f"Content too large ({content_length:,} chars). Please edit in smaller chunks or use selection mode.",
            )

        # === DEDUCT POINTS BEFORE QUEUEING ===
        try:
            await points_service.deduct_points(
                user_id=user_id,
                amount=points_needed,
                service="ai_edit",
                resource_id=resource_id,
                description=f"AI Edit {resource_type}: {request.user_prompt[:50]}...",
            )
            logger.info(f"💸 Deducted {points_needed} points for AI Edit")
        except Exception as points_error:
            logger.error(f"❌ Error deducting points: {points_error}")
            raise HTTPException(status_code=500, detail="Failed to deduct points")

        # === ENQUEUE TASK TO REDIS ===
        import uuid

        task_id = str(uuid.uuid4())
        queue = await get_ai_editor_queue()

        task = AIEditorTask(
            task_id=task_id,
            job_id=task_id,
            user_id=user_id,
            document_id=resource_id,
            job_type="edit",
            content_type=doc_type,
            content=request.context_html,
            user_query=request.user_prompt,
        )

        success = await queue.enqueue_generic_task(task)

        if not success:
            logger.error(f"❌ Failed to enqueue task {task_id}")
            raise HTTPException(
                status_code=500, detail="Failed to enqueue task to Redis"
            )

        logger.info(f"✅ Task {task_id} enqueued to Redis ai_editor queue")

        return CreateAIEditorJobResponse(
            job_id=task_id,
            status=AIEditorJobStatus.PENDING,
            message="Edit job queued. Poll /api/ai/editor/jobs/{job_id} for status.",
            estimated_time="1-5 minutes",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Edit by AI failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/translate")
async def translate(
    request: AITranslateRequest, user_info: dict = Depends(require_auth)
):
    """
    Translate document or chapter content to target language (Streaming)
    Uses Deepseek for fast and cost-effective translation

    **Cost: 2 points** (AI operation)

    **Supports**: document_id OR chapter_id
    """
    try:
        user_id = user_info["uid"]
        resource_id = request.document_id or request.chapter_id
        resource_type = "chapter" if request.chapter_id else "document"

        logger.info(f"🌍 Translate request from user {user_id}")
        logger.info(
            f"{resource_type.capitalize()} ID: {resource_id}, Target: {request.target_language}"
        )

        # Validate IDs
        request.validate_ids()

        # === CHECK POINTS (AI OPERATION: 2 points) ===
        points_service = get_points_service()
        points_needed = 2

        check_result = await points_service.check_sufficient_points(
            user_id=user_id, points_needed=points_needed, service="ai_translate"
        )

        if not check_result["has_points"]:
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "insufficient_points",
                    "message": f"Không đủ points để dùng AI Translate. Cần: {points_needed}, Còn: {check_result['points_available']}",
                    "points_needed": points_needed,
                    "points_available": check_result["points_available"],
                    "upgrade_url": "/pricing",
                },
            )

        logger.info(
            f"✅ Points check passed - {check_result['points_available']} points available"
        )

        # Build prompt for AI
        prompt = f"""You are an expert translator. Your task is to translate the text content within the provided HTML snippet to the target language.
- ONLY return the translated HTML content.
- Preserve the original HTML structure and tags.
- Do not translate HTML tags or attributes.

Target Language: '{request.target_language}'

HTML to translate:
{request.context_html}"""

        # Call AI service (Deepseek) - STREAMING
        messages = [
            {
                "role": "system",
                "content": "You are an expert translator. You only return translated HTML without any markdown or explanations.",
            },
            {"role": "user", "content": prompt},
        ]

        async def generate_stream():
            """Stream translation results"""
            try:
                async for chunk in ai_chat_service.chat_stream(
                    provider=AIProvider.DEEPSEEK_CHAT,
                    messages=messages,
                    temperature=0.3,
                    max_tokens=8000,
                ):
                    yield chunk

                logger.info(
                    f"✅ Translation completed for {resource_type} {resource_id}"
                )

                # === DEDUCT POINTS AFTER SUCCESS ===
                try:
                    await points_service.deduct_points(
                        user_id=user_id,
                        amount=points_needed,
                        service="ai_translate",
                        resource_id=resource_id,
                        description=f"AI Translate {resource_type} to {request.target_language}",
                    )
                    logger.info(f"💸 Deducted {points_needed} points for AI Translate")
                except Exception as points_error:
                    logger.error(f"❌ Error deducting points: {points_error}")

            except Exception as e:
                logger.error(f"❌ Translation streaming failed: {e}")
                yield f"\n\n❌ Error: {str(e)}"

        return StreamingResponse(
            generate_stream(),
            media_type="text/plain",
        )

    except Exception as e:
        logger.error(f"❌ Translation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/format", response_model=CreateAIEditorJobResponse)
async def format_document(
    request: AIFormatRequest, user_info: dict = Depends(require_auth)
):
    """
    Format and clean up document/slide/chapter content with AI (ASYNC with Redis Queue)

    **Returns job_id immediately**, poll /api/ai/editor/jobs/{job_id} for status

    **Cost: 5 points** (deducted immediately for Claude/slides, 2 points for Gemini/docs)

    **Processing Time**: 2-10 minutes depending on content size

    **Workflow**:
    1. POST /format → Get job_id
    2. Poll GET /jobs/{job_id} every 2-5 seconds
    3. When status=completed, get result from response

    **AI Provider Strategy**:
    - **Claude Sonnet 4.5**: For slides (5-minute timeout, chunking support)
    - **Gemini 2.5 Flash**: For documents & chapters (faster, stable)

    **Supports**: document_id OR chapter_id
    """
    try:
        user_id = user_info["uid"]
        resource_id = request.document_id or request.chapter_id
        resource_type = "chapter" if request.chapter_id else "document"

        logger.info(f"✨ Format job request from user {user_id}")
        logger.info(
            f"{resource_type.capitalize()} ID: {resource_id}, Scope: {request.scope}"
        )

        # Validate IDs
        request.validate_ids()

        # === CHECK POINTS (AI OPERATION: 5 points for Claude/slides, 2 for Gemini/docs) ===
        points_service = get_points_service()
        # Note: We charge 5 points upfront for maximum cost (Claude for slides)
        # Documents use Gemini (2 points), but we charge max to avoid issues
        points_needed = 5

        check_result = await points_service.check_sufficient_points(
            user_id=user_id, points_needed=points_needed, service="ai_format"
        )

        if not check_result["has_points"]:
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "insufficient_points",
                    "message": f"Không đủ points để dùng AI Format. Cần: {points_needed}, Còn: {check_result['points_available']}",
                    "points_needed": points_needed,
                    "points_available": check_result["points_available"],
                    "upgrade_url": "/pricing",
                },
            )

        logger.info(
            f"✅ Points check passed - {check_result['points_available']} points available"
        )

        # === FETCH CONTENT CONTEXT ===
        context = await get_content_context(
            document_id=request.document_id,
            chapter_id=request.chapter_id,
            user_id=user_id,
        )

        # Determine document type
        doc_type = request.document_type or context["doc_type"]
        content_type = doc_type.value if hasattr(doc_type, "value") else str(doc_type)

        logger.info(f"📝 {resource_type.capitalize()} type detected: {content_type}")

        # Log content size for debugging
        content_length = len(request.context_html)
        logger.info(f"📊 Content HTML length: {content_length:,} chars")

        # Check content size
        MAX_CONTENT_SIZE = 500_000  # 500K chars safety limit
        if content_length > MAX_CONTENT_SIZE:
            logger.error(
                f"❌ Content too large: {content_length:,} chars (max: {MAX_CONTENT_SIZE:,})"
            )
            raise HTTPException(
                status_code=400,
                detail=f"Content too large ({content_length:,} chars). Please format in smaller chunks or use selection mode.",
            )

        # === DEDUCT POINTS IMMEDIATELY (before job creation) ===
        try:
            await points_service.deduct_points(
                user_id=user_id,
                amount=points_needed,
                service="ai_format",
                resource_id=resource_id,
                description=f"AI Format {content_type} {resource_type}",
            )
            logger.info(f"💸 Deducted {points_needed} points for AI Format")
        except Exception as points_error:
            logger.error(f"❌ Error deducting points: {points_error}")
            raise HTTPException(status_code=500, detail="Failed to deduct points")

        # === ENQUEUE TASK TO REDIS (Pure Redis Pattern) ===
        import uuid

        task_id = str(uuid.uuid4())
        queue = await get_ai_editor_queue()

        # Create job in Redis BEFORE enqueueing task
        await set_job_status(
            redis_client=queue.redis_client,
            job_id=task_id,
            status="pending",
            user_id=user_id,
            job_type="format",
            document_id=resource_id,
            content_type=content_type,
        )

        task = AIEditorTask(
            task_id=task_id,
            job_id=task_id,
            user_id=user_id,
            document_id=resource_id,
            job_type="format",
            content_type=content_type,
            content=request.context_html,
            user_query=request.user_query,
            # Slide-specific fields
            slide_index=request.slide_index,
            elements=request.elements,
            background=request.background,
        )

        success = await queue.enqueue_generic_task(task)

        if not success:
            # TODO: Rollback points if needed
            logger.error(f"❌ Failed to enqueue task {task_id}")
            raise HTTPException(
                status_code=500, detail="Failed to enqueue task to Redis"
            )

        logger.info(f"✅ Task {task_id} enqueued to Redis ai_editor queue")

        return CreateAIEditorJobResponse(
            job_id=task_id,
            status=AIEditorJobStatus.PENDING,
            message="Format job queued. Poll /api/ai/editor/jobs/{job_id} for status.",
            estimated_time="2-10 minutes",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Format job creation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/jobs/{job_id}", response_model=AIEditorJobStatusResponse)
async def get_ai_editor_job_status(
    job_id: str, user_info: dict = Depends(require_auth)
):
    """
    Get AI Editor job status (polling endpoint)

    Poll this endpoint every 2-5 seconds to check job progress

    **Status values**:
    - `pending`: Job queued, waiting for worker
    - `processing`: Worker is processing the job
    - `completed`: Job finished successfully (result available)
    - `failed`: Job failed (error message available)

    **Response includes**:
    - `result`: Formatted HTML (only when status=completed)
    - `error`: Error message (only when status=failed)
    - `created_at`, `started_at`, `completed_at`: Timestamps
    - `message`: Human-readable status message
    """
    try:
        user_id = user_info["uid"]

        # Get job from Redis (Pure Redis pattern)
        queue = await get_ai_editor_queue()
        job = await get_job_status(queue.redis_client, job_id)

        if not job:
            # Job not in Redis - might be expired (24h TTL) or invalid job_id
            return AIEditorJobStatusResponse(
                job_id=job_id,
                status=AIEditorJobStatus.PENDING,
                user_id=user_id,
                message="Job not found - may have expired (24h TTL) or invalid job_id",
                created_at=None,
                started_at=None,
                completed_at=None,
                content_type=None,
                formatted_content=None,
                error=None,
            )

        # Build status message
        status = job["status"]
        if status == "pending":
            message = "Job is queued, waiting for worker to process"
        elif status == "processing":
            message = "AI is formatting your content..."
        elif status == "completed":
            message = "Formatting completed successfully"
        elif status == "failed":
            message = f"Formatting failed: {job.get('error', 'Unknown error')}"
        else:
            message = f"Unknown status: {status}"

        return AIEditorJobStatusResponse(
            job_id=job["job_id"],
            status=AIEditorJobStatus(job["status"]),
            job_type=AIEditorJobType(job["job_type"]),
            document_id=job["document_id"],
            created_at=job["created_at"],
            started_at=job.get("started_at"),
            completed_at=job.get("completed_at"),
            result=job.get("result"),
            error=job.get("error"),
            message=message,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get job status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/bilingual-convert", response_model=CreateAIEditorJobResponse)
async def bilingual_convert(
    request: BilingualConvertRequest, user_info: dict = Depends(require_auth)
):
    """
    Convert entire document or chapter to bilingual format
    Uses Redis queue for async processing - returns job_id immediately

    **Cost: 3 points** (AI operation with large output)
    **Processing time**: 2-10 minutes

    **Supports**: document_id OR chapter_id

    **Returns**: job_id for polling at GET /api/ai/editor/jobs/{job_id}

    **Note**: Result will include:
    - `result`: Bilingual HTML content
    - `new_resource_id`: Auto-generated chapter/document ID (if applicable)
    - `new_resource_title`: Title of new resource
    """
    try:
        user_id = user_info["uid"]
        resource_id = request.document_id or request.chapter_id
        resource_type = "chapter" if request.chapter_id else "document"

        logger.info(f"🌐 Bilingual conversion request from user {user_id}")
        logger.info(
            f"{resource_type.capitalize()} ID: {resource_id}, {request.source_language} -> {request.target_language}"
        )

        # Validate IDs
        request.validate_ids()

        # === CHECK POINTS (AI OPERATION: 3 points) ===
        points_service = get_points_service()
        points_needed = 3

        check_result = await points_service.check_sufficient_points(
            user_id=user_id, points_needed=points_needed, service="ai_dual_language"
        )

        if not check_result["has_points"]:
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "insufficient_points",
                    "message": f"Không đủ points để dùng AI Bilingual Convert. Cần: {points_needed}, Còn: {check_result['points_available']}",
                    "points_needed": points_needed,
                    "points_available": check_result["points_available"],
                    "upgrade_url": "/pricing",
                },
            )

        logger.info(
            f"✅ Points check passed - {check_result['points_available']} points available"
        )

        # === FETCH CONTENT CONTEXT ===
        context = await get_content_context(
            document_id=request.document_id,
            chapter_id=request.chapter_id,
            user_id=user_id,
        )

        content_html = context["content_html"]
        if not content_html:
            raise HTTPException(
                status_code=404,
                detail=f"{resource_type.capitalize()} content not found",
            )

        # Check content length (bilingual output will be ~2x longer)
        content_length = len(content_html)
        MAX_CONTENT_LENGTH = 80000  # Conservative limit for bilingual conversion

        if content_length > MAX_CONTENT_LENGTH:
            logger.warning(
                f"⚠️ Content too large for bilingual conversion: {content_length:,} chars"
            )
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "content_too_large",
                    "message": f"Nội dung quá dài để chuyển sang song ngữ ({content_length:,} ký tự). Vui lòng chia nhỏ nội dung hoặc chọn một phần để chuyển đổi.",
                    "content_length": content_length,
                    "max_length": MAX_CONTENT_LENGTH,
                    "suggestion": "Hãy thử chuyển đổi từng chapter riêng lẻ thay vì toàn bộ document.",
                },
            )

        # === DEDUCT POINTS BEFORE QUEUEING ===
        try:
            await points_service.deduct_points(
                user_id=user_id,
                amount=points_needed,
                service="ai_dual_language",
                resource_id=resource_id,
                description=f"AI Bilingual {resource_type}: {request.source_language}->{request.target_language}",
            )
            logger.info(f"💸 Deducted {points_needed} points for AI Bilingual")
        except Exception as points_error:
            logger.error(f"❌ Error deducting points: {points_error}")
            raise HTTPException(status_code=500, detail="Failed to deduct points")

        # === ENQUEUE TASK TO REDIS ===
        import uuid

        task_id = str(uuid.uuid4())
        queue = await get_ai_editor_queue()

        task = AIEditorTask(
            task_id=task_id,
            job_id=task_id,
            user_id=user_id,
            document_id=resource_id,
            job_type="bilingual",
            content_type=resource_type,
            content=content_html,
            user_query=None,
            source_language=request.source_language,
            target_language=request.target_language,
            bilingual_style=request.style.value,
        )

        success = await queue.enqueue_generic_task(task)

        if not success:
            logger.error(f"❌ Failed to enqueue task {task_id}")
            raise HTTPException(
                status_code=500, detail="Failed to enqueue task to Redis"
            )

        logger.info(f"✅ Task {task_id} enqueued to Redis ai_editor queue")

        return CreateAIEditorJobResponse(
            job_id=task_id,
            status=AIEditorJobStatus.PENDING,
            message="Bilingual conversion job queued. Poll /api/ai/editor/jobs/{job_id} for status.",
            estimated_time="2-10 minutes",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Bilingual conversion failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
