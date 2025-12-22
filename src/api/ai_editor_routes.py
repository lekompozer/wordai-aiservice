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
from src.services.online_test_utils import get_mongodb_service
from src.queue.queue_dependencies import get_ai_editor_queue
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

# MongoDB service for job tracking
mongo_service = get_mongodb_service()


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


@router.post("/edit-by-ai", response_model=AIEditorResponse)
async def edit_by_ai(request: AIEditRequest, user_info: dict = Depends(require_auth)):
    """
    Edit document or chapter content based on user's natural language instruction
    Uses Claude Haiku 4.5 for fast and accurate content editing
    Context-aware: automatically adapts for A4 documents vs Slides

    **Cost: 2 points** (AI operation)

    **Supports**: document_id OR chapter_id
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

        # === CHECK POINTS (AI OPERATION: 2 points) ===
        points_service = get_points_service()
        points_needed = 2

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
        resource_id = context["resource_id"]

        logger.info(f"📄 {resource_type.capitalize()} type: {doc_type}")

        # Log content size for debugging
        content_length = len(request.context_html)
        logger.info(f"📊 Content HTML length: {content_length:,} chars")

        # Check content size
        MAX_CONTENT_SIZE = 500_000  # 500K chars safety limit
        if content_length > MAX_CONTENT_SIZE:
            logger.error(f"❌ Content too large: {content_length:,} chars")
            raise HTTPException(
                status_code=400,
                detail=f"Content too large ({content_length:,} chars). Please edit in smaller chunks or use selection mode.",
            )

        # AI Provider Strategy:
        # - Gemini: For documents & chapters (faster, more stable, 120s timeout)
        # - Claude: For slides only (better editing for presentations)

        if doc_type == "slide":
            # Use Claude for slide editing
            logger.info("📊 Editing SLIDE with Claude Sonnet")
            from src.services.claude_service import get_claude_service

            claude = get_claude_service()
            edited_html = await claude.edit_html(
                html_content=request.context_html,
                user_instruction=request.user_prompt,
                document_type=doc_type,
            )
        else:
            # Use Gemini 2.5 Pro for document & chapter editing
            logger.info(f"📄 Editing DOCUMENT (type: {doc_type}) with Gemini 2.5 Pro")
            from src.providers.gemini_provider import gemini_provider

            if not gemini_provider.enabled:
                raise HTTPException(
                    status_code=503,
                    detail="Gemini service is not available. Please contact support.",
                )

            edited_html = await gemini_provider.edit_document_html(
                html_content=request.context_html,
                user_instruction=request.user_prompt,
            )

        logger.info(f"✅ Edit by AI completed for {resource_type} {resource_id}")

        # === DEDUCT POINTS AFTER SUCCESS ===
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
            # Don't fail the request if points deduction fails

        return AIEditorResponse(success=True, edited_html=edited_html.strip())

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"❌ Edit by AI failed: {e}")
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

    **Cost: 2 points** (deducted immediately)

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

        # === CHECK POINTS (AI OPERATION: 2 points) ===
        points_service = get_points_service()
        points_needed = 2

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
        # Worker will create job in MongoDB when processing starts
        import uuid

        task_id = str(uuid.uuid4())
        queue = await get_ai_editor_queue()

        task = AIEditorTask(
            task_id=task_id,
            job_id=task_id,  # Worker will create job with this ID
            user_id=user_id,
            document_id=resource_id,
            job_type="format",
            content_type=content_type,
            content=request.context_html,
            user_query=request.user_query,
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

        # Get job from MongoDB
        job = await mongo_service.db["ai_editor_jobs"].find_one({"job_id": job_id})

        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

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


@router.post("/bilingual-convert", response_model=AIEditorResponse)
async def bilingual_convert(
    request: BilingualConvertRequest, user_info: dict = Depends(require_auth)
):
    """
    Convert entire document or chapter to bilingual format
    Uses Gemini 2.5 Pro for handling large context and complex formatting

    **Cost: 3 points** (AI operation with large output)

    **Supports**: document_id OR chapter_id

    **NEW: Auto-generate feature**
    - For chapters: Creates NEW chapter with bilingual content in same book
    - For documents: Creates NEW document with bilingual content
    - Original content unchanged
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

        # Build style-specific examples
        if request.style == BilingualStyle.SLASH_SEPARATED:
            style_description = "'Original / Translated' for slash_separated"
            example_input = "<td>Item 1</td>"
            example_output = "<td>Item 1 / Mục 1</td>"
        else:  # LINE_BREAK
            style_description = (
                "place translation on a new line with <br> for line_break"
            )
            example_input = "<p>This is a paragraph.</p>"
            example_output = "<p>This is a paragraph.<br>Đây là một đoạn văn.</p>"

        # Build prompt for AI
        prompt = f"""You are an expert document translator specializing in creating bilingual documents. Your task is to convert the provided HTML document into a bilingual version, combining the source and target languages while preserving the original HTML structure.

- Source Language: '{request.source_language}'
- Target Language: '{request.target_language}'
- Bilingual Format Style: '{request.style.value}' (e.g., {style_description}).

**CRITICAL RULES:**
1.  **ONLY return the modified bilingual HTML content.**
2.  **DO NOT translate HTML tags, attributes, or CSS styles.**
3.  **Preserve the original HTML structure meticulously (e.g., <h1>, <p>, <li>, <table>, <span>).**
4.  For every piece of text inside a tag, provide both the original and the translation according to the specified style.

**Example:**
- Input: `{example_input}`
- Output: `{example_output}`

Now, convert the following HTML document:
{content_html}"""

        # Call AI service (Gemini Pro)
        messages = [
            {
                "role": "system",
                "content": "You are an expert bilingual document converter. You only return clean bilingual HTML without any markdown or explanations.",
            },
            {"role": "user", "content": prompt},
        ]

        # Get response from AI (non-streaming)
        try:
            bilingual_html = await ai_chat_service.chat(
                provider=AIProvider.GEMINI_PRO,
                messages=messages,
                temperature=0.3,
                max_tokens=16000,  # Larger token limit for full documents
            )
        except Exception as ai_error:
            error_msg = str(ai_error).lower()
            # Check if error is due to content length
            if any(
                keyword in error_msg
                for keyword in ["too long", "token", "length", "size", "quota", "limit"]
            ):
                logger.error(f"❌ AI error (likely content too large): {ai_error}")
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": "content_processing_failed",
                        "message": "Nội dung quá dài hoặc phức tạp để xử lý. Vui lòng thử với nội dung ngắn hơn hoặc chia nhỏ tài liệu.",
                        "suggestion": "Hãy chuyển đổi từng phần nhỏ thay vì toàn bộ tài liệu.",
                        "technical_details": "AI model token limit exceeded",
                    },
                )
            else:
                # Other AI errors
                logger.error(f"❌ AI service error: {ai_error}")
                raise HTTPException(
                    status_code=500, detail=f"AI service error: {str(ai_error)}"
                )

        logger.info(
            f"✅ Bilingual conversion completed for {resource_type} {resource_id}"
        )

        # === AUTO-GENERATE NEW CHAPTER/DOCUMENT ===
        new_resource_id = None
        new_resource_title = None

        if request.chapter_id:
            # Auto-generate NEW chapter with bilingual content
            try:
                chapter = db.book_chapters.find_one({"chapter_id": request.chapter_id})
                if chapter:
                    import uuid
                    from datetime import datetime

                    book_id = chapter["book_id"]
                    original_title = chapter["title"]

                    # Generate unique title
                    suffix = f" ({request.source_language[:2].upper()}/{request.target_language[:2].upper()})"
                    attempt = 0
                    while True:
                        if attempt == 0:
                            new_title = f"{original_title}{suffix}"
                        else:
                            new_title = f"{original_title}{suffix}_{attempt}"

                        existing = db.book_chapters.find_one(
                            {"book_id": book_id, "title": new_title}
                        )
                        if not existing:
                            break
                        attempt += 1

                    # Generate unique slug
                    import re

                    def slugify(text: str) -> str:
                        # Vietnamese character mapping
                        vietnamese_map = {
                            "à": "a",
                            "á": "a",
                            "ạ": "a",
                            "ả": "a",
                            "ã": "a",
                            "â": "a",
                            "ầ": "a",
                            "ấ": "a",
                            "ậ": "a",
                            "ẩ": "a",
                            "ẫ": "a",
                            "ă": "a",
                            "ằ": "a",
                            "ắ": "a",
                            "ặ": "a",
                            "ẳ": "a",
                            "ẵ": "a",
                            "è": "e",
                            "é": "e",
                            "ẹ": "e",
                            "ẻ": "e",
                            "ẽ": "e",
                            "ê": "e",
                            "ề": "e",
                            "ế": "e",
                            "ệ": "e",
                            "ể": "e",
                            "ễ": "e",
                            "ì": "i",
                            "í": "i",
                            "ị": "i",
                            "ỉ": "i",
                            "ĩ": "i",
                            "ò": "o",
                            "ó": "o",
                            "ọ": "o",
                            "ỏ": "o",
                            "õ": "o",
                            "ô": "o",
                            "ồ": "o",
                            "ố": "o",
                            "ộ": "o",
                            "ổ": "o",
                            "ỗ": "o",
                            "ơ": "o",
                            "ờ": "o",
                            "ớ": "o",
                            "ợ": "o",
                            "ở": "o",
                            "ỡ": "o",
                            "ù": "u",
                            "ú": "u",
                            "ụ": "u",
                            "ủ": "u",
                            "ũ": "u",
                            "ư": "u",
                            "ừ": "u",
                            "ứ": "u",
                            "ự": "u",
                            "ử": "u",
                            "ữ": "u",
                            "ỳ": "y",
                            "ý": "y",
                            "ỵ": "y",
                            "ỷ": "y",
                            "ỹ": "y",
                            "đ": "d",
                            "À": "A",
                            "Á": "A",
                            "Ạ": "A",
                            "Ả": "A",
                            "Ã": "A",
                            "Â": "A",
                            "Ầ": "A",
                            "Ấ": "A",
                            "Ậ": "A",
                            "Ẩ": "A",
                            "Ẫ": "A",
                            "Ă": "A",
                            "Ằ": "A",
                            "Ắ": "A",
                            "Ặ": "A",
                            "Ẳ": "A",
                            "Ẵ": "A",
                            "È": "E",
                            "É": "E",
                            "Ẹ": "E",
                            "Ẻ": "E",
                            "Ẽ": "E",
                            "Ê": "E",
                            "Ề": "E",
                            "Ế": "E",
                            "Ệ": "E",
                            "Ể": "E",
                            "Ễ": "E",
                            "Ì": "I",
                            "Í": "I",
                            "Ị": "I",
                            "Ỉ": "I",
                            "Ĩ": "I",
                            "Ò": "O",
                            "Ó": "O",
                            "Ọ": "O",
                            "Ỏ": "O",
                            "Õ": "O",
                            "Ô": "O",
                            "Ồ": "O",
                            "Ố": "O",
                            "Ộ": "O",
                            "Ổ": "O",
                            "Ỗ": "O",
                            "Ơ": "O",
                            "Ờ": "O",
                            "Ớ": "O",
                            "Ợ": "O",
                            "Ở": "O",
                            "Ỡ": "O",
                            "Ù": "U",
                            "Ú": "U",
                            "Ụ": "U",
                            "Ủ": "U",
                            "Ũ": "U",
                            "Ư": "U",
                            "Ừ": "U",
                            "Ứ": "U",
                            "Ự": "U",
                            "Ử": "U",
                            "Ữ": "U",
                            "Ỳ": "Y",
                            "Ý": "Y",
                            "Ỵ": "Y",
                            "Ỷ": "Y",
                            "Ỹ": "Y",
                            "Đ": "D",
                        }
                        for vn_char, en_char in vietnamese_map.items():
                            text = text.replace(vn_char, en_char)
                        text = text.lower()
                        text = re.sub(r"[^\w\s-:]", "", text)
                        text = re.sub(r"[-\s]+", "-", text)
                        return text.strip("-")[:100]

                    base_slug = slugify(new_title)
                    slug_attempt = 0
                    while True:
                        if slug_attempt == 0:
                            new_slug = base_slug
                        else:
                            new_slug = f"{base_slug}-{slug_attempt}"

                        existing_slug = db.book_chapters.find_one(
                            {"book_id": book_id, "slug": new_slug}
                        )
                        if not existing_slug:
                            break
                        slug_attempt += 1

                    # Create new chapter
                    new_chapter_id = f"chapter_{uuid.uuid4().hex[:12]}"
                    now = datetime.utcnow()

                    new_chapter = {
                        "chapter_id": new_chapter_id,
                        "book_id": book_id,
                        "parent_id": chapter.get("parent_id"),
                        "title": new_title,
                        "slug": new_slug,
                        "order_index": chapter.get("order_index", 0) + 1,
                        "depth": chapter.get("depth", 0),
                        "content_source": "inline",
                        "document_id": None,
                        "content_html": bilingual_html.strip(),
                        "content_json": None,
                        "is_published": True,
                        "is_preview_free": chapter.get("is_preview_free", False),
                        "created_at": now,
                        "updated_at": now,
                    }

                    db.book_chapters.insert_one(new_chapter)
                    new_resource_id = new_chapter_id
                    new_resource_title = new_title

                    logger.info(
                        f"✅ Auto-generated bilingual chapter: {new_chapter_id} "
                        f"(title: '{new_title}')"
                    )
            except Exception as chapter_error:
                logger.error(f"❌ Failed to auto-generate chapter: {chapter_error}")

        elif request.document_id:
            # Auto-generate NEW document with bilingual content
            try:
                document = db.documents.find_one({"document_id": request.document_id})
                if document:
                    import uuid
                    from datetime import datetime

                    original_name = document.get("name") or document.get(
                        "title", "Untitled"
                    )

                    # Generate unique name
                    suffix = f" ({request.source_language[:2].upper()}/{request.target_language[:2].upper()})"
                    attempt = 0
                    while True:
                        if attempt == 0:
                            new_name = f"{original_name}{suffix}"
                        else:
                            new_name = f"{original_name}{suffix}_{attempt}"

                        existing = db.documents.find_one(
                            {"user_id": user_id, "name": new_name}
                        )
                        if not existing:
                            break
                        attempt += 1

                    # Create new document
                    new_document_id = f"doc_{uuid.uuid4().hex[:12]}"
                    now = datetime.utcnow()

                    new_document = {
                        "document_id": new_document_id,
                        "user_id": user_id,
                        "name": new_name,
                        "title": new_name,
                        "content_html": bilingual_html.strip(),
                        "content_json": None,
                        "doc_type": document.get("doc_type", "doc"),
                        "folder_id": document.get("folder_id"),
                        "created_at": now,
                        "updated_at": now,
                    }

                    db.documents.insert_one(new_document)
                    new_resource_id = new_document_id
                    new_resource_title = new_name

                    logger.info(
                        f"✅ Auto-generated bilingual document: {new_document_id} "
                        f"(name: '{new_name}')"
                    )
            except Exception as doc_error:
                logger.error(f"❌ Failed to auto-generate document: {doc_error}")

        # === DEDUCT POINTS AFTER SUCCESS ===
        try:
            await points_service.deduct_points(
                user_id=user_id,
                amount=points_needed,
                service="ai_dual_language",
                resource_id=resource_id,
                description=f"AI Bilingual {resource_type}: {request.source_language} -> {request.target_language}",
            )
            logger.info(f"💸 Deducted {points_needed} points for AI Bilingual Convert")
        except Exception as points_error:
            logger.error(f"❌ Error deducting points: {points_error}")

        return AIEditorResponse(
            success=True,
            edited_html=bilingual_html.strip(),
            new_resource_id=new_resource_id,
            new_resource_title=new_resource_title,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Bilingual conversion failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
