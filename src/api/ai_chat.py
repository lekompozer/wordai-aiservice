"""
AI Chat API
API endpoints for AI-powered chat with file context (streaming support)
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from typing import Dict, Any, AsyncIterator, Optional
import logging
import time
import json
import asyncio
import uuid
from datetime import datetime

from src.models.ai_chat_models import (
    AIChatRequest,
    AIChatResponse,
    AIChatChunk,
    AIChatErrorResponse,
)
from src.services.chat_context_service import ChatContextService
from src.services.token_management_service import TokenManagementService
from src.services.gemini_pdf_handler import GeminiPDFHandler
from src.services.file_download_service import FileDownloadService
from src.providers.ai_provider_manager import AIProviderManager
from src.services.user_manager import get_user_manager as get_global_user_manager
from src.middleware.auth import verify_firebase_token
from src.core.config import get_app_config

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/ai/chat", tags=["AI Chat"])

# Initialize config
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
        logger.info("✅ AI Chat: AI Provider Manager initialized")

    return _ai_manager


async def _save_chat_history(
    user_id: str,
    conversation_id: Optional[str],
    user_message: str,
    ai_response: str,
    provider: str,
    metadata: Dict[str, Any],
):
    """
    Save chat interaction to user's conversation history

    Args:
        user_id: Firebase UID
        conversation_id: Conversation ID (will be generated if None)
        user_message: User's message
        ai_response: AI's response
        provider: AI provider used
        metadata: Additional metadata
    """
    try:
        user_manager = get_global_user_manager()

        # Generate conversation_id if not provided
        if not conversation_id:
            conversation_id = f"chat_{user_id}_{uuid.uuid4().hex[:8]}"

        # Create or update conversation (this will create if not exists)
        await user_manager.save_conversation(
            user_id=user_id,
            conversation_id=conversation_id,
            messages=[],  # Will add messages below
            ai_provider=provider,
            metadata=metadata,
        )

        # Add user message
        await user_manager.add_message_to_conversation(
            conversation_id=conversation_id,
            user_id=user_id,
            role="user",
            content=user_message,
            metadata={"provider": provider, **metadata},
        )

        # Add AI response
        await user_manager.add_message_to_conversation(
            conversation_id=conversation_id,
            user_id=user_id,
            role="assistant",
            content=ai_response,
            metadata={"provider": provider, **metadata},
        )

        logger.info(f"   💾 Saved chat to conversation {conversation_id}")

    except Exception as e:
        logger.error(f"   ⚠️ Failed to save chat history: {e}")


async def stream_chat_response(
    request: AIChatRequest, user_id: str
) -> AsyncIterator[str]:
    """
    Stream chat response from AI provider

    Yields SSE formatted chunks
    """
    start_time = time.time()
    full_response = ""  # Track full response for saving to history

    try:
        # ===== STEP 1: Download and Parse File if URL provided =====
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
                    yield f"data: {json.dumps({'error': 'Failed to download PDF file', 'done': True})}\n\n"
                    return

            # For other cases: inject parsed text into fullContent
            elif text_content:
                logger.info(
                    f"✅ Parsed {len(text_content)} chars, injecting into fullContent"
                )
                request.currentFile.fullContent = text_content
            else:
                logger.error(f"❌ Failed to parse file from R2")
                yield f"data: {json.dumps({'error': 'Failed to parse file content', 'done': True})}\n\n"
                return

        # ===== STEP 2: SPECIAL CASE: PDF with Gemini =====
        if (
            request.provider.lower() == "gemini"
            and request.currentFile
            and request.currentFile.fileType == "pdf"
            and request.currentFile.filePath
        ):

            logger.info(f"   🔥 Using Gemini PDF direct upload for chat")

            # Process PDF with Gemini (non-streaming for now)
            success, response_text, metadata = (
                await GeminiPDFHandler.process_pdf_with_gemini(
                    pdf_file_path=request.currentFile.filePath,
                    user_query=request.userMessage,
                    highlighted_text=(
                        request.selectedContent.text
                        if request.selectedContent
                        else None
                    ),
                    operation_type="general_edit",  # Chat is general
                    parameters=None,
                )
            )

            if not success:
                error_msg = metadata.get("error", "Unknown error")
                yield f"data: {json.dumps({'error': error_msg, 'done': True})}\n\n"
                return

            full_response = response_text  # Store for history

            # Stream response in chunks (simulate streaming)
            chunk_size = 50
            words = response_text.split()
            for i in range(0, len(words), chunk_size):
                chunk = " ".join(words[i : i + chunk_size])
                yield f"data: {json.dumps({'chunk': chunk, 'done': False})}\n\n"
                await asyncio.sleep(0.05)  # Small delay

            # Final chunk with metadata
            processing_time = int((time.time() - start_time) * 1000)
            final_metadata = {
                "processingTime": processing_time,
                "tokensUsed": metadata.get("tokens_used"),
                "model": "gemini-2.5-pro",
                "provider": "gemini",
                "pdfDirectUpload": True,
            }
            yield f"data: {json.dumps({'chunk': '', 'done': True, 'metadata': final_metadata})}\n\n"

            # Save to chat history
            await _save_chat_history(
                user_id=user_id,
                conversation_id=request.conversationId,
                user_message=request.userMessage,
                ai_response=full_response,
                provider=request.provider,
                metadata={
                    "apiType": "chat",
                    "pdfDirectUpload": True,
                    "fileName": (
                        request.currentFile.fileName if request.currentFile else None
                    ),
                    "processingTime": processing_time,
                },
            )

            return

        # ===== NORMAL FLOW: Text-based chat =====

        # Build context prompt
        selected_text = (
            request.selectedContent.text if request.selectedContent else None
        )
        current_file_name = (
            request.currentFile.fileName if request.currentFile else None
        )
        current_file_content = (
            request.currentFile.fullContent if request.currentFile else None
        )

        # Optimize context for token limits
        if current_file_content:
            token_limit = TokenManagementService.TOKEN_LIMITS.get(
                request.provider.lower(), 32000
            )
            max_chars = int(token_limit * 3.5 * 0.7)  # 70% of token limit

            if len(current_file_content) > max_chars:
                logger.info(
                    f"   Truncating file content from {len(current_file_content)} to {max_chars} chars"
                )
                current_file_content = ChatContextService.truncate_context_if_needed(
                    current_file_content, max_chars
                )

        # Build additional contexts
        additional_contexts = []
        if request.additionalContext:
            for ctx in request.additionalContext:
                additional_contexts.append(
                    {"fileName": ctx.fileName, "content": ctx.content}
                )

        # Build prompt
        prompt = ChatContextService.build_chat_prompt(
            user_message=request.userMessage,
            selected_text=selected_text,
            current_file_name=current_file_name,
            current_file_content=current_file_content,
            additional_contexts=additional_contexts,
        )

        logger.info(f"   Generated chat prompt: {len(prompt)} characters")

        # Prepare messages with conversation history
        messages = []

        # Add conversation history
        if request.conversationHistory:
            formatted_history = ChatContextService.format_conversation_history(
                request.conversationHistory
            )
            messages.extend(formatted_history)

        # Add current prompt
        messages.append({"role": "user", "content": prompt})

        # Map provider names
        provider_map = {
            "deepseek": "deepseek",
            "chatgpt": "chatgpt",
            "gemini": "gemini",
            "qwen": "cerebras",
            "cerebras": "cerebras",
        }

        ai_provider = provider_map.get(request.provider, "deepseek")
        ai_manager = get_ai_manager()

        logger.info(f"   💬 Streaming chat from {ai_provider}...")

        # Stream response
        async for chunk in ai_manager.stream_chat_completion(
            messages=messages, provider=ai_provider
        ):
            full_response += chunk
            yield f"data: {json.dumps({'chunk': chunk, 'done': False})}\n\n"

        # Send final chunk with metadata
        processing_time = int((time.time() - start_time) * 1000)

        # Estimate tokens
        total_chars = len(prompt) + len(full_response)
        estimated_tokens = int(total_chars / 3.5)

        final_metadata = {
            "processingTime": processing_time,
            "tokensUsed": estimated_tokens,
            "model": _get_model_name(request.provider),
            "provider": request.provider,
            "messageCount": len(messages),
        }

        yield f"data: {json.dumps({'chunk': '', 'done': True, 'metadata': final_metadata})}\n\n"

        logger.info(f"   ✅ Chat stream completed in {processing_time}ms")

        # Save to chat history
        await _save_chat_history(
            user_id=user_id,
            conversation_id=request.conversationId,
            user_message=request.userMessage,
            ai_response=full_response,
            provider=request.provider,
            metadata={
                "apiType": "chat",
                "fileName": (
                    request.currentFile.fileName if request.currentFile else None
                ),
                "selectedText": (
                    request.selectedContent.text if request.selectedContent else None
                ),
                "processingTime": processing_time,
                "tokensUsed": estimated_tokens,
            },
        )

    except Exception as e:
        logger.error(f"   ❌ Chat stream error: {e}", exc_info=True)
        yield f"data: {json.dumps({'error': str(e), 'done': True})}\n\n"


@router.post("/stream")
async def chat_stream(
    request: AIChatRequest, user_data: Dict[str, Any] = Depends(verify_firebase_token)
):
    """
    Stream AI chat responses with file context

    Returns Server-Sent Events (SSE) stream
    """
    user_id = user_data.get("uid")
    user_email = user_data.get("email", "unknown")

    logger.info(f"💬 Chat stream request from {user_email}")
    logger.info(f"   Provider: {request.provider}, Stream: {request.stream}")

    if not request.stream:
        # Non-streaming mode
        return await chat_complete(request, user_data)

    # Streaming mode
    return StreamingResponse(
        stream_chat_response(request, user_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/complete", response_model=AIChatResponse)
async def chat_complete(
    request: AIChatRequest, user_data: Dict[str, Any] = Depends(verify_firebase_token)
):
    """
    Complete (non-streaming) AI chat with file context
    """
    user_id = user_data.get("uid")
    user_email = user_data.get("email", "unknown")
    start_time = time.time()

    try:
        logger.info(f"💬 Chat complete request from {user_email}")
        logger.info(f"   Provider: {request.provider}")

        # Build prompt (same as streaming)
        selected_text = (
            request.selectedContent.text if request.selectedContent else None
        )
        current_file_name = (
            request.currentFile.fileName if request.currentFile else None
        )
        current_file_content = (
            request.currentFile.fullContent if request.currentFile else None
        )

        # Optimize context
        if current_file_content:
            token_limit = TokenManagementService.TOKEN_LIMITS.get(
                request.provider.lower(), 32000
            )
            max_chars = int(token_limit * 3.5 * 0.7)

            if len(current_file_content) > max_chars:
                current_file_content = ChatContextService.truncate_context_if_needed(
                    current_file_content, max_chars
                )

        additional_contexts = []
        if request.additionalContext:
            for ctx in request.additionalContext:
                additional_contexts.append(
                    {"fileName": ctx.fileName, "content": ctx.content}
                )

        prompt = ChatContextService.build_chat_prompt(
            user_message=request.userMessage,
            selected_text=selected_text,
            current_file_name=current_file_name,
            current_file_content=current_file_content,
            additional_contexts=additional_contexts,
        )

        # Prepare messages
        messages = []
        if request.conversationHistory:
            formatted_history = ChatContextService.format_conversation_history(
                request.conversationHistory
            )
            messages.extend(formatted_history)

        messages.append({"role": "user", "content": prompt})

        # Call AI
        provider_map = {
            "deepseek": "deepseek",
            "chatgpt": "chatgpt",
            "gemini": "gemini",
            "qwen": "cerebras",
            "cerebras": "cerebras",
        }

        ai_provider = provider_map.get(request.provider, "deepseek")
        ai_manager = get_ai_manager()

        response_text = await ai_manager.chat_completion(
            messages=messages, provider=ai_provider
        )

        processing_time = int((time.time() - start_time) * 1000)
        total_chars = len(prompt) + len(response_text)
        estimated_tokens = int(total_chars / 3.5)

        metadata = {
            "processingTime": processing_time,
            "tokensUsed": estimated_tokens,
            "model": _get_model_name(request.provider),
            "provider": request.provider,
            "messageCount": len(messages),
        }

        logger.info(f"   ✅ Chat complete in {processing_time}ms")

        # Save to chat history
        await _save_chat_history(
            user_id=user_id,
            conversation_id=request.conversationId,
            user_message=request.userMessage,
            ai_response=response_text,
            provider=request.provider,
            metadata={
                "apiType": "chat",
                "fileName": (
                    request.currentFile.fileName if request.currentFile else None
                ),
                "selectedText": (
                    request.selectedContent.text if request.selectedContent else None
                ),
                "processingTime": processing_time,
                "tokensUsed": estimated_tokens,
            },
        )

        return AIChatResponse(success=True, response=response_text, metadata=metadata)

    except Exception as e:
        logger.error(f"   ❌ Chat error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "AI Chat API",
        "timestamp": datetime.utcnow().isoformat(),
    }


def _get_model_name(provider: str) -> str:
    """Get model name for provider"""
    models = {
        "deepseek": "deepseek-chat",
        "chatgpt": "gpt-4o-latest",
        "gemini": "gemini-2.5-pro",
        "qwen": "qwen-235b-instruct",
        "cerebras": "qwen-235b-instruct",
    }
    return models.get(provider.lower(), "unknown")
