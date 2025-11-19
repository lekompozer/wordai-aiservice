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

        # Check content size (Claude Haiku supports 200K tokens ≈ 800K chars)
        MAX_CONTENT_SIZE = 500_000  # 500K chars safety limit
        if content_length > MAX_CONTENT_SIZE:
            logger.error(f"❌ Content too large: {content_length:,} chars")
            raise HTTPException(
                status_code=400,
                detail=f"Content too large ({content_length:,} chars). Please edit in smaller chunks or use selection mode.",
            )

        # Use Claude service for HTML editing with document type context
        from src.services.claude_service import get_claude_service

        claude = get_claude_service()

        # Call Claude with document type awareness
        edited_html = await claude.edit_html(
            html_content=request.context_html,
            user_instruction=request.user_prompt,
            document_type=doc_type,  # Pass document type for context-aware editing
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


@router.post("/format", response_model=AIEditorResponse)
async def format_document(
    request: AIFormatRequest, user_info: dict = Depends(require_auth)
):
    """
    Format and clean up document/slide/chapter content with context-aware instructions
    Uses Claude Haiku 4.5 for fast and intelligent formatting
    Supports both A4 documents and presentation slides

    **Cost: 2 points** (AI operation)

    **Supports**: document_id OR chapter_id
    """
    try:
        user_id = user_info["uid"]
        resource_id = request.document_id or request.chapter_id
        resource_type = "chapter" if request.chapter_id else "document"

        logger.info(f"✨ Format request from user {user_id}")
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

        logger.info(f"📝 {resource_type.capitalize()} type detected: {doc_type}")

        # Log content size for debugging
        content_length = len(request.context_html)
        logger.info(f"📊 Content HTML length: {content_length:,} chars")

        # Check content size (Claude Haiku supports 200K tokens ≈ 800K chars)
        MAX_CONTENT_SIZE = 500_000  # 500K chars safety limit
        if content_length > MAX_CONTENT_SIZE:
            logger.error(
                f"❌ Content too large: {content_length:,} chars (max: {MAX_CONTENT_SIZE:,})"
            )
            raise HTTPException(
                status_code=400,
                detail=f"Content too large ({content_length:,} chars). Please format in smaller chunks or use selection mode.",
            )

        # Use Claude service with appropriate formatting method
        from src.services.claude_service import get_claude_service

        claude = get_claude_service()

        # Call appropriate formatting method based on document type
        if doc_type == DocumentType.SLIDE:
            logger.info("📊 Formatting as SLIDE (presentation)")
            formatted_html = await claude.format_slide_html(
                html_content=request.context_html,
                user_query=request.user_query,
            )
        else:  # doc or note
            logger.info(f"📄 Formatting as DOCUMENT (type: {doc_type})")
            formatted_html = await claude.format_document_html(
                html_content=request.context_html,
                user_query=request.user_query,
            )

        logger.info(f"✅ Formatting completed for {resource_type} {resource_id}")

        # === DEDUCT POINTS AFTER SUCCESS ===
        try:
            await points_service.deduct_points(
                user_id=user_id,
                amount=points_needed,
                service="ai_format",
                resource_id=resource_id,
                description=f"AI Format {doc_type} {resource_type}",
            )
            logger.info(f"💸 Deducted {points_needed} points for AI Format")
        except Exception as points_error:
            logger.error(f"❌ Error deducting points: {points_error}")

        return AIEditorResponse(success=True, edited_html=formatted_html.strip())

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"❌ Formatting failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/bilingual-convert", response_model=AIEditorResponse)
async def bilingual_convert(
    request: BilingualConvertRequest, user_info: dict = Depends(require_auth)
):
    """
    Convert entire document or chapter to bilingual format
    Uses Gemini 2.5 Pro for handling large context and complex formatting

    **Cost: 2 points** (AI operation)

    **Supports**: document_id OR chapter_id
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

        # === CHECK POINTS (AI OPERATION: 2 points) ===
        points_service = get_points_service()
        points_needed = 2

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
        bilingual_html = await ai_chat_service.chat(
            provider=AIProvider.GEMINI_PRO,
            messages=messages,
            temperature=0.3,
            max_tokens=16000,  # Larger token limit for full documents
        )

        logger.info(
            f"✅ Bilingual conversion completed for {resource_type} {resource_id}"
        )

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

        return AIEditorResponse(success=True, edited_html=bilingual_html.strip())

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Bilingual conversion failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
