"""
AI Content Edit API
API endpoints for AI-powered content editing
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from typing import Dict, Any, Optional
import logging
import time
import uuid
import os
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
from src.services.file_download_service import FileDownloadService
from src.services.user_manager import get_user_manager as get_global_user_manager
from src.providers.ai_provider_manager import AIProviderManager
from src.middleware.auth import verify_firebase_token
from src.core.config import get_app_config

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/ai/content", tags=["AI Content Editing"])

# Initialize services
APP_CONFIG = get_app_config()

# R2 Configuration
R2_PUBLIC_URL = os.getenv("R2_PUBLIC_URL", "https://static.wordai.pro")
R2_BUCKET_NAME = os.getenv("R2_BUCKET_NAME", "wordai")


def resolve_r2_url_from_file_id(user_id: str, file_id: str) -> Optional[str]:
    """
    Resolve R2 URL from fileId.

    In production, this should query the database to get the actual file path.
    For now, using standard R2 path pattern: users/{user_id}/files/{file_id}

    Args:
        user_id: Firebase UID
        file_id: File ID (e.g., "abc123.pdf")

    Returns:
        Full R2 URL or None if resolution fails

    Example:
        >>> resolve_r2_url_from_file_id("user123", "doc.pdf")
        "https://static.wordai.pro/users/user123/files/doc.pdf"
    """
    try:
        logger.info(f"🔍 [Content Edit] Resolving R2 URL for fileId: {file_id}")

        # TODO: In production, query database to get actual file path
        # For now, construct URL from standard pattern
        r2_key = f"users/{user_id}/files/{file_id}"
        r2_url = f"{R2_PUBLIC_URL}/{r2_key}"

        logger.info(f"✅ [Content Edit] Resolved URL: {r2_url[:80]}...")
        return r2_url

    except Exception as e:
        logger.error(
            f"❌ [Content Edit] Failed to resolve R2 URL for fileId {file_id}: {e}"
        )
        return None


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


async def _save_content_edit_history(
    user_id: str,
    conversation_id: Optional[str],
    user_query: str,
    html_input: str,
    html_output: str,
    operation_type: str,
    provider: str,
    metadata: Dict[str, Any],
):
    """
    Save content edit interaction to user's conversation history

    Args:
        user_id: Firebase UID
        conversation_id: Conversation ID (will be generated if None)
        user_query: User's query/instruction
        html_input: Input HTML content
        html_output: Generated HTML output
        operation_type: Type of operation performed
        provider: AI provider used
        metadata: Additional metadata
    """
    try:
        user_manager = get_global_user_manager()

        # Generate conversation_id if not provided
        if not conversation_id:
            conversation_id = f"edit_{user_id}_{uuid.uuid4().hex[:8]}"

        # Create or update conversation (this will create if not exists)
        await user_manager.save_conversation(
            user_id=user_id,
            conversation_id=conversation_id,
            messages=[],  # Will add messages below
            ai_provider=provider,
            metadata=metadata,
        )

        # Create user message with HTML input
        user_message = (
            f"[{operation_type}] {user_query}\n\nInput HTML:\n{html_input[:500]}..."
        )

        # Add user message
        await user_manager.add_message_to_conversation(
            conversation_id=conversation_id,
            user_id=user_id,
            role="user",
            content=user_message,
            metadata={
                "provider": provider,
                "operationType": operation_type,
                **metadata,
            },
        )

        # Add AI response with HTML output
        await user_manager.add_message_to_conversation(
            conversation_id=conversation_id,
            user_id=user_id,
            role="assistant",
            content=html_output,
            metadata={
                "provider": provider,
                "operationType": operation_type,
                **metadata,
            },
        )

        logger.info(f"   💾 Saved content edit to conversation {conversation_id}")

    except Exception as e:
        logger.error(f"   ⚠️ Failed to save content edit history: {e}")


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

        # ===== STEP 1: Resolve R2 URL from fileId if needed =====
        if request.currentFile and request.currentFile.fileId:
            # Check if we need to resolve URL from fileId
            if (
                not request.currentFile.filePath
                or not request.currentFile.filePath.startswith("http")
            ):
                logger.info(
                    f"📂 [Content Edit] No URL provided, resolving from fileId: {request.currentFile.fileId}"
                )

                resolved_url = resolve_r2_url_from_file_id(
                    user_id=user_id, file_id=request.currentFile.fileId
                )

                if resolved_url:
                    request.currentFile.filePath = resolved_url
                    logger.info(f"✅ [Content Edit] Resolved R2 URL from fileId")
                else:
                    logger.error(
                        f"❌ [Content Edit] Could not resolve R2 URL for fileId: {request.currentFile.fileId}"
                    )
                    raise HTTPException(status_code=404, detail="File not found")

        # ===== STEP 2: Download and Parse File if URL provided =====
        if (
            request.currentFile
            and request.currentFile.filePath
            and request.currentFile.filePath.startswith("http")
        ):
            logger.info(f"📥 File URL detected, downloading from R2...")

            text_content, temp_file_path = (
                await FileDownloadService.download_and_parse_file(
                    file_url=request.currentFile.filePath,
                    file_type=request.currentFile.fileType,
                    user_id=user_id,
                    provider=request.provider,
                )
            )

            # For PDF + Gemini: use temp_file_path directly
            if (
                request.provider.lower() == "gemini"
                and request.currentFile.fileType == "pdf"
            ):
                if temp_file_path:
                    logger.info(f"✅ PDF for Gemini: Using temp file path")
                    request.currentFile.filePath = (
                        temp_file_path  # Update to local path
                    )
                else:
                    logger.error(f"❌ Failed to download PDF for Gemini")
                    raise HTTPException(
                        status_code=500, detail="Failed to download PDF file"
                    )

            # For other cases: inject parsed text into fullContent
            elif text_content:
                logger.info(
                    f"✅ Parsed {len(text_content)} chars, injecting into fullContent"
                )
                request.currentFile.fullContent = text_content
            else:
                logger.error(f"❌ Failed to parse file from R2")
                raise HTTPException(
                    status_code=500, detail="Failed to parse file content"
                )

        # ===== STEP 3: SPECIAL CASE: PDF with Gemini =====
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

            # Save to history
            await _save_content_edit_history(
                user_id=user_id,
                conversation_id=request.conversationId,
                user_query=request.userQuery,
                html_input=request.selectedContent.html or "",
                html_output=sanitized_output,
                operation_type=request.operationType,
                provider=request.provider,
                metadata={
                    "apiType": "content_edit",
                    "pdfDirectUpload": True,
                    "fileName": request.currentFile.fileName,
                    "processingTime": processing_time,
                },
            )

            return AIContentEditResponse(
                generatedHTML=sanitized_output, metadata=response_metadata
            )

        # ===== NORMAL FLOW: Text-based processing =====
        # All non-PDF files OR non-Gemini providers

        # ===== Step 4: Validate input =====
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

        # ===== Step 5: Build AI prompt =====
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

        # ===== Step 6: Call AI provider =====
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

        # ===== Step 7: Extract and sanitize HTML from response =====
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

        # ===== Step 8: Build response =====
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

        # Save to history
        await _save_content_edit_history(
            user_id=user_id,
            conversation_id=request.conversationId,
            user_query=request.userQuery,
            html_input=selected_html,
            html_output=sanitized_output,
            operation_type=request.operationType,
            provider=request.provider,
            metadata={
                "apiType": "content_edit",
                "fileName": request.currentFile.fileName,
                "processingTime": processing_time,
                "tokensUsed": total_tokens,
            },
        )

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
