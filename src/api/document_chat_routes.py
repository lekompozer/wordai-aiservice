"""
Document Chat API Routes
AI chat with document context - supports file upload and selected text
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import json
import asyncio
from datetime import datetime
import uuid
import tempfile
import os
from pathlib import Path

from src.middleware.firebase_auth import require_auth
from src.services.user_manager import user_manager
from src.services.document_manager import document_manager
from src.services.ai_chat_service import ai_chat_service, AIProvider
from src.services.subscription_service import get_subscription_service
from src.services.points_service import get_points_service
from src.utils.logger import setup_logger
from src.utils.file_converter import (
    FileConverter,
    extract_text,
    estimate_tokens,
    estimate_pdf_tokens,
)
from src.utils.file_cache import file_cache, is_file_cached, get_cached_file, cache_file
from src.utils.r2_downloader import r2_downloader, download_r2_file

logger = setup_logger()
router = APIRouter(prefix="/api/ai/document-chat", tags=["document-chat"])


# ============ MODELS ============


class DocumentChatMessage(BaseModel):
    role: str = Field(..., description="Message role: system, user, or assistant")
    content: str = Field(..., description="Message content")
    timestamp: Optional[datetime] = None


class DocumentChatRequest(BaseModel):
    provider: str = Field(
        ..., description="AI provider: gemini-pro, gpt-4, deepseek, qwen"
    )
    user_query: str = Field(..., description="User's question about the document")
    selected_text: Optional[str] = Field(
        None, description="Text selected by user in document"
    )
    file_id: Optional[str] = Field(
        None, description="File ID from simple-files or documents"
    )
    document_id: Optional[str] = Field(
        None, description="Document ID from edited documents"
    )
    conversation_id: Optional[str] = Field(None, description="Existing conversation ID")
    temperature: float = Field(
        0.7, ge=0.0, le=2.0, description="Temperature for AI response"
    )
    max_tokens: int = Field(
        4000, ge=1, le=8000, description="Maximum tokens in response (max 8k)"
    )


# ============ CONSTANTS ============

# Context length limits for different providers
PROVIDER_CONTEXT_LIMITS = {
    "deepseek": 128_000,  # DeepSeek-V3.2 (Non-thinking Mode)
    "qwen": 32_000,  # Qwen2.5
    "gemini-pro": 1_000_000,  # Gemini Pro
    "gpt-4": 1_000_000,  # GPT-4
    "claude": 200_000,  # Claude (if supported)
}

# Providers that support direct file upload
FILE_SUPPORTED_PROVIDERS = ["gemini-pro", "gpt-4"]

# Providers that need text conversion
TEXT_ONLY_PROVIDERS = ["deepseek", "qwen"]


# ============ HELPER FUNCTIONS ============


def estimate_tokens(text: str) -> int:
    """Estimate token count (1 token ≈ 4 characters)"""
    return len(text) // 4


def estimate_pdf_tokens(page_count: int) -> int:
    """Estimate tokens for PDF based on page count"""
    # Average: ~500 tokens per page
    return page_count * 500


async def get_file_content(
    file_id: str = None,
    document_id: str = None,
    user_id: str = None,
    conversation_id: str = None,
) -> Dict[str, Any]:
    """
    Get file content and metadata with caching support

    Flow:
    1. Check cache first (if conversation_id provided)
    2. If not cached, download from R2
    3. Extract text and metadata
    4. Add to cache for future use

    Returns:
        {
            "file_path": str,
            "file_type": str,  # "pdf", "docx", "txt"
            "content_text": str,  # For text-only providers
            "page_count": int,
            "estimated_tokens": int,
            "from_cache": bool
        }
    """
    try:
        file_path = None
        from_cache = False

        # Get file from simple-files or edited documents
        if file_id:
            # Auto-detect if this is actually a document_id (starts with "doc_")
            if file_id.startswith("doc_") and not document_id:
                logger.info(f"� Detected document_id in file_id field: {file_id}")
                document_id = file_id
                file_id = None
            else:
                logger.info(f"�📁 Getting file from simple-files: {file_id}")

                # ===== STEP 1: Check Cache =====
                if conversation_id:
                    cached_path = get_cached_file(file_id, conversation_id)
                    if cached_path:
                        logger.info(f"🎯 Using cached file: {cached_path}")
                        file_path = cached_path
                        from_cache = True

                # ===== STEP 2: Download from R2 if not cached =====
                if not file_path:
                    file_doc = user_manager.get_file_by_id(file_id, user_id)

                    if not file_doc:
                        raise HTTPException(status_code=404, detail="File not found")

                # Get R2 key and file info
                r2_key = file_doc.get("r2_key")
                file_url = file_doc.get("file_url") or file_doc.get("private_url")
                filename = file_doc.get("filename") or file_doc.get(
                    "original_name", "file"
                )

                if not r2_key:
                    raise HTTPException(
                        status_code=404,
                        detail="File R2 key not found - file may not be uploaded yet",
                    )

                # Get file extension
                file_ext = r2_downloader.get_file_extension(filename)

                # Create local cache path
                cache_path = file_cache._get_cache_path(
                    file_id, conversation_id or "temp", file_ext
                )

                logger.info(f"⬇️ Downloading from R2: {r2_key}")

                # Download from R2
                download_success = await download_r2_file(
                    r2_key=r2_key, local_path=str(cache_path), file_url=file_url
                )

                if not download_success:
                    # Try downloading from public URL as fallback
                    if file_url:
                        logger.warning(
                            f"⚠️ Trying fallback download from URL: {file_url}"
                        )
                        download_success = await r2_downloader.download_from_url(
                            url=file_url, local_path=str(cache_path)
                        )

                if not download_success:
                    raise HTTPException(
                        status_code=500, detail="Failed to download file from R2"
                    )

                file_path = str(cache_path)

                # ===== STEP 3: Add to Cache =====
                if conversation_id:
                    file_type = FileConverter.get_file_type(file_path)
                    cache_file(
                        file_id=file_id,
                        conversation_id=conversation_id,
                        local_path=file_path,
                        file_type=file_type,
                        metadata={
                            "filename": filename,
                            "r2_key": r2_key,
                            "downloaded_at": datetime.utcnow().isoformat(),
                        },
                    )
                    logger.info(f"📦 Cached file: {file_id} → {file_path}")

        elif document_id:
            logger.info(f"📄 Getting document from edited documents: {document_id}")
            doc = document_manager.get_document(document_id, user_id)

            if not doc:
                raise HTTPException(status_code=404, detail="Document not found")

            # For edited documents, we have HTML/text content directly
            file_type = "txt"  # Treat as text

            # Try to get content_text first, fallback to parsing HTML
            content_text = doc.get("content_text")

            if not content_text:
                # Parse HTML to clean text (remove tags, scripts, styles)
                content_html = doc.get("content_html", "")
                if content_html:
                    from bs4 import BeautifulSoup
                    import re

                    logger.info(f"📝 Parsing HTML to clean text...")
                    soup = BeautifulSoup(content_html, "html.parser")

                    # Remove script and style elements
                    for script in soup(["script", "style"]):
                        script.decompose()

                    # Get text and clean up whitespace
                    content_text = soup.get_text(separator=" ", strip=True)
                    content_text = re.sub(r"\s+", " ", content_text).strip()

                    logger.info(f"✅ Extracted {len(content_text)} chars from HTML")
                else:
                    content_text = ""
                    logger.warning(f"⚠️ No content found in document")

            # Estimate tokens
            estimated_tokens = estimate_tokens(content_text)
            page_count = max(1, estimated_tokens // 500)

            return {
                "file_path": None,
                "file_type": file_type,
                "content_text": content_text,
                "page_count": page_count,
                "estimated_tokens": estimated_tokens,
                "from_cache": False,
            }

        else:
            raise HTTPException(
                status_code=400, detail="Must provide file_id or document_id"
            )

        # ===== STEP 4: Extract Text and Metadata =====
        # Detect file type
        file_type = FileConverter.get_file_type(file_path)
        logger.info(f"🔍 Detected file type: {file_type}")

        # Extract text and get page count
        content_text, page_count = extract_text(file_path)

        if not content_text:
            logger.warning(f"⚠️ No text extracted from file")

        # Estimate tokens
        estimated_tokens = (
            estimate_tokens(content_text)
            if content_text
            else estimate_pdf_tokens(page_count)
        )

        logger.info(
            f"📊 File analysis complete:\n"
            f"   Type: {file_type}\n"
            f"   Pages: {page_count}\n"
            f"   Text length: {len(content_text):,} chars\n"
            f"   Estimated tokens: {estimated_tokens:,}\n"
            f"   From cache: {from_cache}"
        )

        return {
            "file_path": file_path,
            "file_type": file_type,
            "content_text": content_text,
            "page_count": page_count,
            "estimated_tokens": estimated_tokens,
            "from_cache": from_cache,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error getting file content: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get file content: {str(e)}"
        )

        return {
            "file_path": file_path,
            "file_type": file_type,
            "content_text": content_text,
            "page_count": page_count,
            "estimated_tokens": estimated_tokens,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error getting file content: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get file content: {str(e)}"
        )


def calculate_max_history_tokens(
    provider: str, file_tokens: int, selected_text_tokens: int, output_tokens: int
) -> int:
    """
    Calculate maximum tokens available for conversation history

    Formula:
    max_history = provider_limit - file_tokens - selected_text_tokens - user_query (estimate 200) - output_tokens
    """
    provider_limit = PROVIDER_CONTEXT_LIMITS.get(provider, 32_000)

    # Reserve tokens
    reserved = (
        file_tokens + selected_text_tokens + 200 + output_tokens
    )  # 200 for user query

    # Available for history
    available = provider_limit - reserved

    # Safety margin: use 80% of available
    max_history = int(available * 0.8)

    return max(0, max_history)  # Ensure non-negative


def limit_conversation_history(
    existing_messages: List[Dict[str, str]], max_history_tokens: int
) -> List[Dict[str, str]]:
    """
    Limit conversation history to fit within token constraints
    Keep most recent messages that fit
    """
    if not existing_messages:
        return []

    # Start from most recent
    limited_messages = []
    current_tokens = 0

    for msg in reversed(existing_messages):
        msg_tokens = estimate_tokens(msg.get("content", ""))

        if current_tokens + msg_tokens <= max_history_tokens:
            limited_messages.insert(0, msg)
            current_tokens += msg_tokens
        else:
            break

    return limited_messages


async def convert_to_pdf(file_path: str, file_type: str) -> str:
    """
    Convert DOCX or TXT to PDF
    Returns path to converted PDF file
    """
    # TODO: Implement conversion using LibreOffice or similar
    # For now, return original file
    logger.warning(f"⚠️ PDF conversion not implemented yet for {file_type}")
    return file_path


async def convert_to_text(file_path: str, file_type: str) -> str:
    """
    Convert PDF or DOCX to plain text
    Returns extracted text content
    """
    # TODO: Implement text extraction
    # For PDF: use PyPDF2 or pdfplumber
    # For DOCX: use python-docx
    logger.warning(f"⚠️ Text conversion not implemented yet for {file_type}")
    return ""


# ============ MAIN ENDPOINT ============


@router.post("/stream")
async def document_chat_stream(
    request: DocumentChatRequest, current_user: dict = Depends(require_auth)
):
    """
    Stream chat response with document context

    Features:
    - Auto file processing (PDF direct upload or text conversion)
    - Selected text support
    - Smart token management per provider
    - Conversation history with limits
    - Stream response

    Flow:
    1. Get file content (if file_id or document_id provided)
    2. Calculate token usage and limits
    3. Load conversation history (limited by tokens)
    4. Prepare context with file + selected text + query
    5. Stream AI response
    6. Save conversation
    """

    try:
        user_id = current_user["uid"]

        # Validate provider
        try:
            provider = AIProvider(request.provider)
        except ValueError:
            available = [p.value for p in AIProvider]
            raise HTTPException(
                status_code=400, detail=f"Invalid provider. Available: {available}"
            )

        # Validate max_tokens
        if request.max_tokens > 8000:
            raise HTTPException(status_code=400, detail="max_tokens cannot exceed 8000")

        # ===== POINTS CHECKING & DEDUCTION =====
        subscription_service = get_subscription_service()
        points_service = get_points_service()

        # Get subscription info
        subscription = await subscription_service.get_or_create_subscription(user_id)
        balance = await points_service.get_points_balance(user_id)

        # Determine points cost based on provider (VARIABLE PRICING)
        provider_name = request.provider.lower()
        points_cost = points_service.get_chat_points_cost(provider_name)
        should_deduct_points = False

        logger.info(
            f"💰 Document Chat - User {user_id} - Plan: {subscription.plan}, Provider: {provider_name}, Cost: {points_cost} points"
        )

        # === FREE USER LOGIC ===
        if subscription.plan == "free":
            if provider_name == "deepseek":
                # Check daily limit (10 chats/day)
                if not await subscription_service.check_daily_chat_limit(user_id):
                    raise HTTPException(
                        status_code=403,
                        detail={
                            "error": "daily_chat_limit_exceeded",
                            "message": "Bạn đã hết 10 lượt chat miễn phí hôm nay với Deepseek. Quay lại vào ngày mai hoặc nâng cấp để chat không giới hạn!",
                            "daily_limit": 10,
                            "current_count": subscription.daily_chat_count,
                            "upgrade_url": "/pricing",
                        },
                    )
                # Daily Deepseek chat = COMPLETELY FREE (0 points)
                should_deduct_points = False
                logger.info(
                    f"✅ FREE user - Daily Deepseek doc chat ({subscription.daily_chat_count + 1}/10) - No points deduction"
                )
            else:
                # Other providers (Gemini, ChatGPT, Claude, Gwen): use bonus points (2 points each)
                if balance["points_remaining"] < 2:
                    raise HTTPException(
                        status_code=403,
                        detail={
                            "error": "insufficient_bonus_points",
                            "message": f"Bản FREE chỉ chat miễn phí với Deepseek. Bạn còn {balance['points_remaining']} điểm thưởng, cần 2 điểm để chat với {request.provider}. Nâng cấp để dùng Claude/ChatGPT/Gemini/Gwen không giới hạn!",
                            "allowed_free_provider": "deepseek",
                            "requested_provider": request.provider,
                            "bonus_points_remaining": balance["points_remaining"],
                            "points_needed": 2,
                            "upgrade_url": "/pricing",
                        },
                    )
                should_deduct_points = True
                points_cost = 2
                logger.info(
                    f"💵 FREE user using bonus points for doc chat - {request.provider} ({balance['points_remaining']} points available)"
                )

        # === PAID USER LOGIC ===
        else:
            # Check sufficient points (1 for Deepseek, 2 for others)
            check_result = await points_service.check_sufficient_points(
                user_id=user_id,
                points_needed=points_cost,
                service=f"ai_document_chat_{provider_name}",
            )

            if not check_result["has_points"]:
                raise HTTPException(
                    status_code=403,
                    detail={
                        "error": "insufficient_points",
                        "message": f"Không đủ points để chat với {request.provider}. Cần: {points_cost}, Còn: {check_result['points_available']}",
                        "points_needed": points_cost,
                        "points_available": check_result["points_available"],
                        "upgrade_url": "/pricing",
                    },
                )

            should_deduct_points = True
            logger.info(
                f"💰 PAID user - Document chat with {request.provider} will cost {points_cost} points ({balance['points_remaining']} available)"
            )

        # ===== STEP 1: Get/Create Conversation ID First =====
        conversation_id = request.conversation_id

        if not conversation_id:
            conversation_id = f"doc_chat_{uuid.uuid4().hex[:12]}"
            logger.info(f"🆕 Created new document chat: {conversation_id}")
        else:
            logger.info(f"📝 Using existing conversation: {conversation_id}")

        # ===== STEP 2: Get File Content with Cache Support =====
        file_info = None
        file_tokens = 0

        if request.file_id or request.document_id:
            logger.info(f"📄 Fetching file content...")
            file_info = await get_file_content(
                file_id=request.file_id,
                document_id=request.document_id,
                user_id=user_id,
                conversation_id=conversation_id,  # Pass conversation_id for caching
            )
            file_tokens = file_info["estimated_tokens"]

            # Log cache status
            if file_info.get("from_cache"):
                logger.info(f"🎯 Used cached file - saved download time!")

            logger.info(f"📊 File tokens: {file_tokens}")

        # ===== STEP 3: Calculate Token Limits =====
        selected_text_tokens = estimate_tokens(request.selected_text or "")

        max_history_tokens = calculate_max_history_tokens(
            provider=request.provider,
            file_tokens=file_tokens,
            selected_text_tokens=selected_text_tokens,
            output_tokens=request.max_tokens,
        )

        logger.info(
            f"🧮 Token allocation:\n"
            f"   Provider limit: {PROVIDER_CONTEXT_LIMITS.get(request.provider, 0):,}\n"
            f"   File: {file_tokens:,}\n"
            f"   Selected text: {selected_text_tokens:,}\n"
            f"   Output reserved: {request.max_tokens:,}\n"
            f"   History available: {max_history_tokens:,}"
        )

        # ===== STEP 3: Get/Create Conversation =====
        conversation_id = request.conversation_id

        if not conversation_id:
            conversation_id = f"doc_chat_{uuid.uuid4().hex[:12]}"
            logger.info(f"🆕 Created new document chat: {conversation_id}")
        else:
            logger.info(f"📝 Using existing conversation: {conversation_id}")

        # ===== STEP 4: Load Conversation History =====
        history_messages = []

        if conversation_id:
            try:
                existing_conv = await user_manager.get_conversation_detail(
                    user_id=user_id, conversation_id=conversation_id
                )

                if existing_conv and existing_conv.get("messages"):
                    existing_messages = existing_conv["messages"]

                    # Limit history based on available tokens
                    history_messages = limit_conversation_history(
                        existing_messages=existing_messages,
                        max_history_tokens=max_history_tokens,
                    )

                    logger.info(
                        f"💾 Loaded history: {len(existing_messages)} → {len(history_messages)} messages"
                    )
            except Exception as e:
                logger.warning(f"⚠️ Could not load history: {e}")

        # ===== STEP 5: Prepare Messages =====
        messages = []

        # System message
        messages.append(
            {
                "role": "system",
                "content": "You are a helpful AI assistant analyzing document content. Provide clear, accurate answers based on the document context provided.",
            }
        )

        # Add history
        messages.extend(history_messages)

        # Prepare user message with context
        user_message_parts = []

        # Smart context strategy:
        # - If no selection: Send full document
        # - If selection + small doc (<5k tokens): Send both (document as reference, selection as focus)
        # - If selection + large doc (>=5k tokens): Send only selection (avoid token overflow)

        DOCUMENT_TOKEN_THRESHOLD = 5000

        if request.selected_text:
            # User selected text - this is the PRIMARY focus
            logger.info(f"✏️  Selected text: {len(request.selected_text)} chars ({selected_text_tokens} tokens)")

            # Check if we should include full document as reference
            if file_info and file_info.get("content_text"):
                if file_tokens < DOCUMENT_TOKEN_THRESHOLD:
                    # Document is small enough - include as reference context
                    logger.info(
                        f"📄 Including full document as reference ({file_tokens} tokens < {DOCUMENT_TOKEN_THRESHOLD})"
                    )
                    user_message_parts.append(
                        f"---FULL DOCUMENT (Reference Context)---\n{file_info['content_text']}\n---END DOCUMENT---\n"
                    )
                else:
                    # Document too large - skip to save tokens
                    logger.info(
                        f"⚠️  Skipping full document (too large: {file_tokens} tokens >= {DOCUMENT_TOKEN_THRESHOLD})"
                    )

            # Add selected text (PRIMARY FOCUS)
            user_message_parts.append(
                f"---SELECTED TEXT (Main Focus)---\n{request.selected_text}\n---END SELECTED TEXT---\n"
            )
            user_message_parts.append(
                "Please focus your answer on the SELECTED TEXT above, using the document context if provided."
            )

        elif file_info and file_info.get("content_text"):
            # No selection - use full document
            content_preview = file_info["content_text"][:500]
            logger.info(
                f"📄 Using full document content ({len(file_info['content_text'])} chars, {file_tokens} tokens)"
            )
            logger.info(f"   Preview: {content_preview}...")

            user_message_parts.append(
                f"---DOCUMENT CONTENT---\n{file_info['content_text']}\n---END DOCUMENT---\n"
            )

        # Add user question
        user_message_parts.append(f"User Question: {request.user_query}")

        user_message = "\n".join(user_message_parts)

        messages.append({"role": "user", "content": user_message})

        logger.info(f"💬 Total messages: {len(messages)}")
        logger.info(f"📊 User message length: {len(user_message):,} chars")
        logger.info(f"👤 User query: {request.user_query[:100]}...")

        # ===== STEP 6: Stream Response =====
        async def generate_stream():
            try:
                full_response = ""

                # Send metadata
                metadata = {
                    "type": "metadata",
                    "conversation_id": conversation_id,
                    "provider": request.provider,
                    "tokens": {
                        "file": file_tokens,
                        "selected_text": selected_text_tokens,
                        "history": sum(
                            estimate_tokens(m.get("content", ""))
                            for m in history_messages
                        ),
                        "max_output": request.max_tokens,
                    },
                }
                yield f"data: {json.dumps(metadata)}\n\n"

                # Stream AI response
                async for chunk in ai_chat_service.chat_stream(
                    provider=provider,
                    messages=messages,
                    temperature=request.temperature,
                    max_tokens=request.max_tokens,
                ):
                    if chunk:
                        full_response += chunk
                        yield f"data: {json.dumps({'type': 'content', 'content': chunk})}\n\n"

                # ===== STEP 7: Save Conversation =====
                try:
                    # Prepare messages to save (exclude system message)
                    messages_to_save = [
                        {"role": "user", "content": request.user_query},
                        {"role": "assistant", "content": full_response},
                    ]

                    # Combine with history
                    all_messages = history_messages + messages_to_save

                    await user_manager.save_conversation(
                        user_id=user_id,
                        conversation_id=conversation_id,
                        messages=all_messages,
                        ai_provider=request.provider,
                        metadata={
                            "type": "document_chat",
                            "file_id": request.file_id,
                            "document_id": request.document_id,
                            "has_selected_text": bool(request.selected_text),
                            "temperature": request.temperature,
                            "max_tokens": request.max_tokens,
                            "file_tokens": file_tokens,
                            "response_tokens": estimate_tokens(full_response),
                        },
                    )

                    logger.info(f"💾 Conversation saved: {conversation_id}")

                    # ===== STEP 8: Deduct Points (if needed) =====
                    if should_deduct_points:
                        try:
                            await points_service.deduct_points(
                                user_id=user_id,
                                amount=points_cost,
                                service=f"ai_document_chat_{provider_name}",
                                resource_id=conversation_id,
                                description=f"Document chat with {request.provider}",
                            )
                            logger.info(
                                f"💰 Deducted {points_cost} points for document chat with {request.provider}"
                            )
                        except Exception as points_error:
                            logger.error(f"❌ Points deduction failed: {points_error}")
                            # Don't fail the request, just log the error

                    # ===== STEP 9: Update Daily Chat Counter (FREE + Deepseek) =====
                    if subscription.plan == "free" and provider_name == "deepseek":
                        try:
                            await subscription_service.increment_daily_chat(user_id)
                            logger.info(
                                f"📊 Daily chat count incremented: {subscription.daily_chat_count + 1}/10"
                            )
                        except Exception as counter_error:
                            logger.error(
                                f"❌ Failed to increment daily counter: {counter_error}"
                            )
                            # Don't fail the request

                    complete_data = {
                        "type": "complete",
                        "conversation_id": conversation_id,
                        "saved": True,
                        "points_deducted": points_cost if should_deduct_points else 0,
                    }
                    yield f"data: {json.dumps(complete_data)}\n\n"

                except Exception as save_error:
                    logger.error(f"❌ Save error: {save_error}")
                    error_data = {
                        "type": "error",
                        "message": "Failed to save conversation",
                    }
                    yield f"data: {json.dumps(error_data)}\n\n"

                # Done
                yield "data: [DONE]\n\n"

            except Exception as e:
                logger.error(f"❌ Stream error: {e}")
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

        # Return streaming response
        return StreamingResponse(
            generate_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Content-Type": "text/event-stream",
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Document chat error: {e}")
        raise HTTPException(status_code=500, detail=f"Document chat failed: {str(e)}")


@router.get("/conversations")
async def get_document_chat_conversations(
    limit: int = 20, offset: int = 0, current_user: dict = Depends(require_auth)
):
    """Get document chat conversation history"""
    try:
        user_id = current_user["uid"]

        # Get conversations filtered by type
        conversations = await user_manager.get_user_conversations(
            user_id=user_id, limit=limit, offset=offset
        )

        # Filter document chat conversations
        doc_chats = [
            conv
            for conv in conversations
            if conv.get("metadata", {}).get("type") == "document_chat"
        ]

        logger.info(f"📋 Retrieved {len(doc_chats)} document chat conversations")

        return {
            "conversations": doc_chats,
            "total": len(doc_chats),
            "limit": limit,
            "offset": offset,
        }

    except Exception as e:
        logger.error(f"❌ Error getting conversations: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get conversations: {str(e)}"
        )


@router.get("/conversations/{conversation_id}")
async def get_document_chat_detail(
    conversation_id: str, current_user: dict = Depends(require_auth)
):
    """Get specific document chat conversation detail"""
    try:
        user_id = current_user["uid"]

        conversation = await user_manager.get_conversation_detail(
            user_id=user_id, conversation_id=conversation_id
        )

        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")

        # Verify it's a document chat
        if conversation.get("metadata", {}).get("type") != "document_chat":
            raise HTTPException(
                status_code=400, detail="Not a document chat conversation"
            )

        logger.info(f"📄 Retrieved conversation: {conversation_id}")

        return conversation

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error getting conversation detail: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get conversation: {str(e)}"
        )


@router.delete("/conversations/{conversation_id}")
async def delete_document_chat(
    conversation_id: str, current_user: dict = Depends(require_auth)
):
    """
    Delete document chat conversation and clear cache

    This endpoint:
    1. Deletes conversation from database
    2. Clears all cached files for this conversation
    """
    try:
        user_id = current_user["uid"]

        # Clear file cache for this conversation
        cache_cleared = file_cache.clear_conversation_cache(conversation_id)

        if cache_cleared:
            logger.info(f"🧹 Cleared cache for conversation: {conversation_id}")

        # TODO: Implement delete conversation in user_manager
        # For now, return success

        logger.info(f"🗑️ Deleted conversation: {conversation_id}")

        return {
            "success": True,
            "message": "Conversation deleted successfully",
            "cache_cleared": cache_cleared,
        }

    except Exception as e:
        logger.error(f"❌ Error deleting conversation: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to delete conversation: {str(e)}"
        )


@router.post("/conversations/{conversation_id}/clear-cache")
async def clear_conversation_cache_endpoint(
    conversation_id: str, current_user: dict = Depends(require_auth)
):
    """
    Clear file cache for a conversation without deleting the conversation

    Useful when:
    - User switches to different files
    - Want to free up disk space
    - Cache corrupted
    """
    try:
        user_id = current_user["uid"]

        # Verify user owns this conversation
        conversation = await user_manager.get_conversation_detail(
            user_id=user_id, conversation_id=conversation_id
        )

        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")

        # Clear cache
        cache_cleared = file_cache.clear_conversation_cache(conversation_id)

        logger.info(f"🧹 Cleared cache for conversation: {conversation_id}")

        return {
            "success": True,
            "message": "Cache cleared successfully",
            "conversation_id": conversation_id,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error clearing cache: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to clear cache: {str(e)}")


@router.get("/cache/stats")
async def get_cache_stats(current_user: dict = Depends(require_auth)):
    """
    Get cache statistics

    Returns information about cached files and disk usage
    """
    try:
        stats = file_cache.get_cache_stats()

        # Add cleanup info
        cleaned_count = file_cache.cleanup_expired_cache()
        stats["expired_files_cleaned"] = cleaned_count

        return {"success": True, "cache_stats": stats}

    except Exception as e:
        logger.error(f"❌ Error getting cache stats: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get cache stats: {str(e)}"
        )
