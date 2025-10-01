"""
AI Content Edit API
API endpoints for AI-powered content editing
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from typing import Dict, Any
import logging
import time
from datetime import datetime

from src.models.ai_content_edit_models import (
    AIContentEditRequest,
    AIContentEditResponse,
    AIContentEditErrorResponse,
    ResponseMetadata,
    SourceAttribution,
)
from src.services.html_sanitization_service import HTMLSanitizationService
from src.services.prompt_engineering_service import PromptEngineeringService
from src.services.token_management_service import TokenManagementService
from src.services.gemini_pdf_handler import GeminiPDFHandler
from src.providers.ai_provider_manager import AIProviderManager
from src.middleware.auth import verify_firebase_token
from src.core.config import get_app_config

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/ai/content", tags=["AI Content Editing"])

# Initialize services
APP_CONFIG = get_app_config()

# Global AI manager instance
_ai_manager = None


def get_ai_manager() -> AIProviderManager:
    """Get or create AI provider manager instance"""
    global _ai_manager

    if _ai_manager is None:
        _ai_manager = AIProviderManager(
            deepseek_api_key=APP_CONFIG.get("deepseek_api_key"),
            chatgpt_api_key=APP_CONFIG.get("chatgpt_api_key"),
            gemini_api_key=APP_CONFIG.get("gemini_api_key"),
            cerebras_api_key=APP_CONFIG.get("cerebras_api_key"),
        )
        logger.info("✅ AI Content Edit: AI Provider Manager initialized")

    return _ai_manager


@router.post("/edit", response_model=AIContentEditResponse)
async def edit_content(
    request: AIContentEditRequest,
    user_data: Dict[str, Any] = Depends(verify_firebase_token),
):
    """
    AI-powered content editing endpoint

    Supports operations: summarize, change_tone, fix_grammar, create_table,
    transform_format, continue_writing, expand_content, simplify, translate,
    create_structure, general_edit, custom
    """
    start_time = time.time()
    user_id = user_data.get("uid")
    user_email = user_data.get("email", "unknown")

    try:
        logger.info(f"📝 Content edit request from {user_email}")
        logger.info(
            f"   Operation: {request.operationType}, Provider: {request.provider}"
        )

        # ===== SPECIAL CASE: PDF with Gemini =====
        # Only PDF files can be sent directly to Gemini
        # Other formats (DOCX, TXT, MD) must be parsed to text first
        if (
            request.provider.lower() == "gemini"
            and request.currentFile
            and request.currentFile.fileType == "pdf"
            and request.currentFile.filePath
        ):

            logger.info(
                f"   🔥 Using Gemini PDF direct upload for {request.currentFile.fileName}"
            )

            # Extract highlighted text
            highlighted_text = (
                request.selectedContent.text if request.selectedContent else None
            )

            # Process PDF with Gemini
            success, generated_html, metadata = (
                await GeminiPDFHandler.process_pdf_with_gemini(
                    pdf_file_path=request.currentFile.filePath,
                    user_query=request.userQuery,
                    highlighted_text=highlighted_text,
                    operation_type=request.operationType,
                    parameters=(
                        request.parameters.dict() if request.parameters else None
                    ),
                )
            )

            if not success:
                error_msg = metadata.get("error", "Unknown error")
                logger.error(f"   ❌ Gemini PDF processing failed: {error_msg}")
                raise HTTPException(status_code=500, detail=error_msg)

            # Sanitize output
            is_valid, sanitized_output, error = (
                HTMLSanitizationService.validate_and_sanitize(generated_html)
            )

            if not is_valid:
                logger.warning(f"   ⚠️ Gemini output needs sanitization: {error}")
                try:
                    text = HTMLSanitizationService.extract_text_from_html(
                        generated_html
                    )
                    sanitized_output = f"<p>{text}</p>"
                except:
                    raise HTTPException(
                        status_code=500, detail="AI generated invalid HTML content"
                    )

            processing_time = int((time.time() - start_time) * 1000)

            response_metadata = ResponseMetadata(
                provider=request.provider,
                operationType=request.operationType,
                processingTime=processing_time,
                tokensUsed=metadata.get("tokens_used"),
                model=_get_model_name(request.provider),
                contentWasTruncated=False,  # Gemini handles full PDF
                pdfDirectUpload=True,
            )

            logger.info(f"   ✅ PDF processing complete in {processing_time}ms")

            return AIContentEditResponse(
                generatedHTML=sanitized_output, metadata=response_metadata
            )

        # ===== NORMAL FLOW: Text-based processing =====
        # All non-PDF files OR non-Gemini providers

        # ===== Step 1: Validate input =====
        if not request.selectedContent.html and not request.selectedContent.text:
            raise HTTPException(
                status_code=400, detail="No content selected for editing"
            )

        # ===== Step 2: Sanitize input HTML =====
        selected_html = request.selectedContent.html or ""
        selected_text = request.selectedContent.text or ""

        if selected_html:
            is_valid, sanitized_input, error = (
                HTMLSanitizationService.validate_and_sanitize(selected_html)
            )
            if not is_valid:
                logger.warning(f"Invalid input HTML, using text version: {error}")
                selected_html = f"<p>{selected_text}</p>"
            else:
                selected_html = sanitized_input
        else:
            selected_html = f"<p>{selected_text}</p>"

        # ===== Step 3: Optimize content for token limits =====
        # Collect all context
        full_content = request.currentFile.fullContent if request.currentFile else None
        additional_contexts = []

        if request.additionalContext:
            for ctx in request.additionalContext:
                additional_contexts.append(ctx.content)

        # Optimize to fit provider's token limit
        optimized_selected, optimized_full, optimized_additional, total_tokens = (
            TokenManagementService.optimize_context_for_provider(
                provider=request.provider,
                selected_content=selected_html,
                full_content=full_content,
                additional_contexts=additional_contexts,
            )
        )

        logger.info(f"   Total tokens after optimization: {total_tokens}")

        # ===== Step 4: Build AI prompt =====
        # Rebuild additional context with optimized content
        optimized_context_list = []
        if request.additionalContext and optimized_additional:
            for i, ctx in enumerate(request.additionalContext):
                if i < len(optimized_additional):
                    optimized_context_list.append(
                        {
                            "fileId": ctx.fileId,
                            "fileName": ctx.fileName,
                            "content": optimized_additional[i],
                            "startLine": ctx.startLine,
                            "endLine": ctx.endLine,
                        }
                    )

        prompt = PromptEngineeringService.build_prompt(
            operation_type=request.operationType,
            user_query=request.userQuery,
            selected_html=optimized_selected,
            selected_text=selected_text,
            parameters=request.parameters.dict() if request.parameters else None,
            additional_context=optimized_context_list,
            current_file_name=(
                request.currentFile.fileName if request.currentFile else None
            ),
        )

        logger.info(f"   Generated prompt: {len(prompt)} characters")

        # ===== Step 5: Call AI provider =====
        messages = [{"role": "user", "content": prompt}]

        # Map provider names
        provider_map = {
            "deepseek": "deepseek",
            "chatgpt": "chatgpt",
            "gemini": "gemini",
            "qwen": "cerebras",  # Qwen runs on Cerebras
            "cerebras": "cerebras",
        }

        ai_provider = provider_map.get(request.provider, "deepseek")
        ai_manager = get_ai_manager()

        logger.info(f"   Calling {ai_provider} provider...")

        # Get response from AI (non-streaming)
        try:
            ai_response = await ai_manager.chat_completion(
                messages=messages, provider=ai_provider
            )
        except Exception as ai_error:
            logger.error(f"   AI provider error: {ai_error}")
            raise HTTPException(
                status_code=500, detail=f"AI provider error: {str(ai_error)}"
            )

        logger.info(f"   AI response received: {len(ai_response)} characters")

        # ===== Step 6: Extract and sanitize HTML from response =====
        generated_html = PromptEngineeringService.extract_html_from_response(
            ai_response
        )

        logger.info(f"   Extracted HTML: {len(generated_html)} characters")

        # Sanitize output HTML
        is_valid, sanitized_output, error = (
            HTMLSanitizationService.validate_and_sanitize(generated_html)
        )

        if not is_valid:
            logger.error(f"   AI generated unsafe HTML: {error}")
            # Try to salvage by extracting text and wrapping in p tags
            try:
                text = HTMLSanitizationService.extract_text_from_html(generated_html)
                sanitized_output = f"<p>{text}</p>"
                logger.warning(f"   Fallback: wrapped in <p> tags")
            except:
                raise HTTPException(
                    status_code=500, detail="AI generated invalid HTML content"
                )

        # ===== Step 7: Build response =====
        processing_time = int((time.time() - start_time) * 1000)

        metadata = ResponseMetadata(
            provider=request.provider,
            operationType=request.operationType,
            processingTime=processing_time,
            tokensUsed=total_tokens,
            model=_get_model_name(request.provider),
            contentWasTruncated=(
                total_tokens
                >= TokenManagementService.TOKEN_LIMITS.get(
                    request.provider.lower(), 32000
                )
                * 0.9
            ),
            pdfDirectUpload=False,  # Normal text processing
        )

        # Track sources used
        sources = []
        if request.additionalContext:
            for ctx in request.additionalContext:
                sources.append(
                    SourceAttribution(
                        fileId=ctx.fileId,
                        fileName=ctx.fileName,
                        relevance=0.8,  # Default relevance score
                    )
                )

        # Generate warnings if content was truncated
        warnings = []
        if (
            total_tokens
            > TokenManagementService.TOKEN_LIMITS.get(request.provider, 32000) * 0.8
        ):
            warnings.append(
                "Content was close to token limit and may have been truncated"
            )

        response = AIContentEditResponse(
            success=True,
            generatedHTML=sanitized_output,
            metadata=metadata,
            alternatives=[],  # Can be added in future
            warnings=warnings if warnings else None,
            sources=sources if sources else None,
        )

        logger.info(f"✅ Content edit completed in {processing_time}ms")

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Content edit failed: {e}", exc_info=True)

        # Return error response
        error_response = AIContentEditErrorResponse(
            success=False,
            error={
                "code": "INTERNAL_ERROR",
                "message": str(e),
                "details": type(e).__name__,
            },
            fallback={
                "suggestion": "Try with a different AI provider or reduce content size",
                "action": "retry",
            },
        )

        return JSONResponse(status_code=500, content=error_response.dict())


def _get_model_name(provider: str) -> str:
    """Get model name for provider"""
    model_map = {
        "deepseek": "deepseek-chat",
        "chatgpt": "gpt-4o-latest",
        "gemini": "gemini-2.5-pro",
        "qwen": "qwen-3-235b-instruct",
        "cerebras": "qwen-3-235b-instruct",
    }
    return model_map.get(provider, "unknown")


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "AI Content Editing API",
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/providers")
async def get_available_providers(
    user_data: Dict[str, Any] = Depends(verify_firebase_token),
):
    """Get list of available AI providers"""
    try:
        ai_manager = get_ai_manager()
        available = await ai_manager.get_available_providers()

        providers_info = [
            {
                "id": "deepseek",
                "name": "DeepSeek Chat",
                "description": "DeepSeek's advanced reasoning model",
                "available": "deepseek" in available,
                "contextWindow": "32k tokens",
            },
            {
                "id": "chatgpt",
                "name": "ChatGPT-4o Latest",
                "description": "OpenAI's latest GPT-4o model",
                "available": "chatgpt" in available,
                "contextWindow": "128k tokens",
            },
            {
                "id": "gemini",
                "name": "Gemini 2.5 Pro",
                "description": "Google's most capable model with 1M+ context",
                "available": "gemini" in available,
                "contextWindow": "1M tokens",
            },
            {
                "id": "qwen",
                "name": "Qwen 235B Instruct",
                "description": "Alibaba's large instruction model",
                "available": "cerebras" in available,
                "contextWindow": "32k tokens",
            },
        ]

        return {"providers": providers_info, "default": "deepseek"}

    except Exception as e:
        logger.error(f"Failed to get providers: {e}")
        return {"providers": [], "default": "deepseek"}


@router.get("/operations")
async def get_available_operations():
    """Get list of supported operations"""
    return {
        "operations": [
            {
                "id": "summarize",
                "name": "Summarize",
                "description": "Create a concise summary of the content",
                "icon": "📄",
            },
            {
                "id": "change_tone",
                "name": "Change Tone",
                "description": "Adjust the tone (professional, friendly, formal, etc.)",
                "icon": "🎭",
            },
            {
                "id": "fix_grammar",
                "name": "Fix Grammar",
                "description": "Fix spelling and grammar errors",
                "icon": "✏️",
            },
            {
                "id": "continue_writing",
                "name": "Continue Writing",
                "description": "Continue writing from where you left off",
                "icon": "✍️",
            },
            {
                "id": "expand_content",
                "name": "Expand Content",
                "description": "Add more details and explanations",
                "icon": "📝",
            },
            {
                "id": "simplify",
                "name": "Simplify",
                "description": "Make the content easier to understand",
                "icon": "🔍",
            },
            {
                "id": "translate",
                "name": "Translate",
                "description": "Translate to another language",
                "icon": "🌐",
            },
            {
                "id": "create_table",
                "name": "Create Table",
                "description": "Convert data into a table format",
                "icon": "📊",
            },
            {
                "id": "transform_format",
                "name": "Transform Format",
                "description": "Change format (list to numbered, etc.)",
                "icon": "🔄",
            },
            {
                "id": "create_structure",
                "name": "Create Structure",
                "description": "Create document structures (layouts, sections)",
                "icon": "🏗️",
            },
            {
                "id": "general_edit",
                "name": "General Edit",
                "description": "Perform any editing task",
                "icon": "✨",
            },
            {
                "id": "custom",
                "name": "Custom",
                "description": "Custom instructions",
                "icon": "⚡",
            },
        ]
    }
