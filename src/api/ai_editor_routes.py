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
from src.services.ai_chat_service import ai_chat_service, AIProvider
from src.utils.logger import setup_logger

logger = setup_logger()
router = APIRouter(prefix="/api/ai/editor", tags=["AI Editor"])


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


# ============ MODELS ============


class AIEditRequest(BaseModel):
    document_id: str = Field(..., description="Document ID")
    context_html: str = Field(..., description="HTML content to edit")
    user_prompt: str = Field(..., description="User's editing instruction")
    selection_only: bool = Field(
        False, description="Whether editing only selected text"
    )


class AITranslateRequest(BaseModel):
    document_id: str = Field(..., description="Document ID")
    context_html: str = Field(..., description="HTML content to translate")
    target_language: str = Field(
        ..., description="Target language (e.g., 'Vietnamese', 'English')"
    )
    selection_only: bool = Field(
        False, description="Whether translating only selected text"
    )


class AIFormatRequest(BaseModel):
    document_id: str = Field(..., description="Document ID")
    context_html: str = Field(..., description="HTML content to format")
    scope: str = Field(..., description="'selection' or 'document'")
    document_type: Optional[DocumentType] = Field(
        None, description="Document type for context-aware formatting"
    )
    user_query: Optional[str] = Field(
        None, description="Additional user formatting instruction"
    )


class BilingualConvertRequest(BaseModel):
    document_id: str = Field(..., description="Document ID")
    source_language: str = Field(..., description="Source language (e.g., 'English')")
    target_language: str = Field(
        ..., description="Target language (e.g., 'Vietnamese')"
    )
    style: BilingualStyle = Field(
        BilingualStyle.SLASH_SEPARATED, description="Bilingual format style"
    )


class AIEditorResponse(BaseModel):
    success: bool = Field(..., description="Whether the operation was successful")
    edited_html: Optional[str] = Field(None, description="Edited HTML content")
    error: Optional[str] = Field(None, description="Error message if failed")


# ============ ENDPOINTS ============


@router.post("/edit-by-ai", response_model=AIEditorResponse)
async def edit_by_ai(request: AIEditRequest, user_info: dict = Depends(require_auth)):
    """
    Edit document content based on user's natural language instruction
    Uses Claude Haiku 4.5 for fast and accurate content editing
    """
    try:
        logger.info(f"🎨 Edit by AI request from user {user_info['uid']}")
        logger.info(
            f"Document ID: {request.document_id}, Prompt: {request.user_prompt}"
        )

        # Use Claude service for HTML editing
        from src.services.claude_service import get_claude_service

        claude = get_claude_service()

        # Call Claude with optimized edit_html method
        edited_html = await claude.edit_html(
            html_content=request.context_html,
            user_instruction=request.user_prompt,
        )

        logger.info(f"✅ Edit by AI completed for document {request.document_id}")

        return AIEditorResponse(success=True, edited_html=edited_html.strip())

    except Exception as e:
        logger.error(f"❌ Edit by AI failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/translate")
async def translate(
    request: AITranslateRequest, user_info: dict = Depends(require_auth)
):
    """
    Translate document content to target language (Streaming)
    Uses Deepseek for fast and cost-effective translation
    """
    try:
        logger.info(f"🌍 Translate request from user {user_info['uid']}")
        logger.info(
            f"Document ID: {request.document_id}, Target: {request.target_language}"
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
                    f"✅ Translation completed for document {request.document_id}"
                )

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
    Format and clean up document/slide content with context-aware instructions
    Uses Claude Haiku 4.5 for fast and intelligent formatting
    Supports both A4 documents and presentation slides
    """
    try:
        logger.info(f"✨ Format request from user {user_info['uid']}")
        logger.info(f"Document ID: {request.document_id}, Scope: {request.scope}")

        # Determine document type
        doc_type = request.document_type
        if not doc_type:
            # Fallback: Get from database
            try:
                doc = document_manager.get_document(
                    request.document_id, user_info["uid"]
                )
                doc_type = doc.get("type", "doc")
            except Exception as e:
                logger.warning(
                    f"Could not get document type from DB: {e}, using default 'doc'"
                )
                doc_type = "doc"

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

        logger.info(f"✅ Formatting completed for document {request.document_id}")

        return AIEditorResponse(success=True, edited_html=formatted_html.strip())

    except Exception as e:
        logger.error(f"❌ Formatting failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/bilingual-convert", response_model=AIEditorResponse)
async def bilingual_convert(
    request: BilingualConvertRequest, user_info: dict = Depends(require_auth)
):
    """
    Convert entire document to bilingual format
    Uses Gemini 2.5 Pro for handling large context and complex formatting
    """
    try:
        logger.info(f"🌐 Bilingual conversion request from user {user_info['uid']}")
        logger.info(
            f"Document ID: {request.document_id}, {request.source_language} -> {request.target_language}"
        )

        # Get full document content
        try:
            doc = document_manager.get_document(request.document_id, user_info["uid"])
            content_html = doc.get("content_html", "")
            if not content_html:
                raise HTTPException(
                    status_code=404, detail="Document content not found"
                )
        except Exception as e:
            logger.error(f"❌ Failed to fetch document: {e}")
            raise HTTPException(status_code=404, detail=f"Document not found: {str(e)}")

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
            f"✅ Bilingual conversion completed for document {request.document_id}"
        )

        return AIEditorResponse(success=True, edited_html=bilingual_html.strip())

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Bilingual conversion failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
