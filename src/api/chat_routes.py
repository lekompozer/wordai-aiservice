"""
Chat API Routes
API endpoints for AI chat with streaming support and conversation management
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import json
import asyncio
from datetime import datetime
import uuid

from src.middleware.firebase_auth import require_auth
from src.services.user_manager import user_manager
from src.services.ai_chat_service import ai_chat_service, AIProvider
from src.services.subscription_service import get_subscription_service
from src.services.points_service import get_points_service
from src.utils.logger import setup_logger

logger = setup_logger()
router = APIRouter(tags=["chat"])


def estimate_tokens(text: str) -> int:
    """Estimate token count for text (rough approximation: 1 token ≈ 4 characters)"""
    return len(text) // 4


def limit_conversation_history(
    existing_messages: List[Dict[str, str]],
    new_messages: List[Dict[str, str]],
    max_history_tokens: int = 24000,
    reserved_tokens: int = 8000,
) -> List[Dict[str, str]]:
    """
    Limit conversation history to fit within token constraints

    Args:
        existing_messages: Previous conversation messages
        new_messages: New messages from current request
        max_history_tokens: Maximum tokens allowed for history (default: 24k)
        reserved_tokens: Tokens reserved for new user query and response (default: 8k)

    Returns:
        Limited message history that fits within token constraints
    """
    # Calculate tokens for new messages (these are mandatory)
    new_tokens = sum(estimate_tokens(msg.get("content", "")) for msg in new_messages)

    # Available tokens for existing history
    available_history_tokens = max_history_tokens - min(
        new_tokens, reserved_tokens // 2
    )

    if available_history_tokens <= 0:
        logger.warning(
            f"⚠️ New messages too long ({new_tokens} tokens), using minimal history"
        )
        return new_messages

    # Work backwards through existing messages to fit within token limit
    limited_history = []
    current_tokens = 0

    # Start from most recent messages and work backwards
    for message in reversed(existing_messages):
        message_tokens = estimate_tokens(message.get("content", ""))

        if current_tokens + message_tokens <= available_history_tokens:
            limited_history.insert(0, message)  # Insert at beginning to maintain order
            current_tokens += message_tokens
        else:
            break

    # Combine limited history with new messages
    final_messages = limited_history + new_messages

    total_tokens = sum(
        estimate_tokens(msg.get("content", "")) for msg in final_messages
    )

    logger.info(
        f"📊 Token management: History={len(limited_history)} msgs ({current_tokens} tokens), "
        f"New={len(new_messages)} msgs ({new_tokens} tokens), "
        f"Total={total_tokens} tokens"
    )

    return final_messages


# Pydantic Models
class ChatMessage(BaseModel):
    role: str = Field(..., description="Message role: system, user, or assistant")
    content: str = Field(..., description="Message content")
    timestamp: Optional[datetime] = None


class ChatRequest(BaseModel):
    provider: str = Field(..., description="AI provider to use")
    messages: List[ChatMessage] = Field(..., description="Chat messages")
    conversation_id: Optional[str] = Field(None, description="Existing conversation ID")
    temperature: float = Field(
        0.7, ge=0.0, le=2.0, description="Temperature for AI response"
    )
    max_tokens: int = Field(
        4000, ge=1, le=32000, description="Maximum tokens in response"
    )
    stream: bool = Field(True, description="Enable streaming response")


class ConversationResponse(BaseModel):
    conversation_id: str
    created_at: datetime
    updated_at: datetime
    message_count: int
    last_message: Optional[str] = None


class ProvidersResponse(BaseModel):
    providers: List[Dict[str, Any]]
    total: int


@router.get("/providers", response_model=ProvidersResponse)
async def get_available_providers():
    """Get list of available AI providers (public endpoint)"""

    try:
        providers = ai_chat_service.get_available_providers()

        logger.info("🌐 Public request for AI providers list")

        return ProvidersResponse(providers=providers, total=len(providers))

    except Exception as e:
        logger.error(f"❌ Error getting providers: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get providers: {str(e)}"
        )


@router.post("/stream")
async def chat_stream(request: ChatRequest, current_user: dict = Depends(require_auth)):
    """Stream chat response from AI provider"""

    try:
        # Validate provider
        try:
            provider = AIProvider(request.provider)
        except ValueError:
            available_providers = [p.value for p in AIProvider]
            raise HTTPException(
                status_code=400,
                detail=f"Invalid provider. Available: {available_providers}",
            )

        # Check if provider is available
        available_providers = ai_chat_service.get_available_providers()
        if not any(p["id"] == request.provider for p in available_providers):
            raise HTTPException(
                status_code=400, detail=f"Provider {request.provider} is not available"
            )

        # === SUBSCRIPTION & POINTS ENFORCEMENT ===
        user_id = current_user["uid"]
        provider_name = request.provider.lower()

        # Get services
        subscription_service = get_subscription_service()
        points_service = get_points_service()

        # Get subscription info
        subscription = await subscription_service.get_or_create_subscription(user_id)
        balance = await points_service.get_points_balance(user_id)

        # Determine points cost based on provider (VARIABLE PRICING)
        points_cost = points_service.get_chat_points_cost(provider_name)
        should_deduct_points = False

        logger.info(
            f"💰 User {user_id} - Plan: {subscription.plan}, Provider: {provider_name}, Cost: {points_cost} points"
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
                    f"✅ FREE user - Daily Deepseek chat ({subscription.daily_chat_count + 1}/10) - No points deduction"
                )
            else:
                # Other providers: use bonus points (2 points each)
                if balance["points_remaining"] < 2:
                    raise HTTPException(
                        status_code=403,
                        detail={
                            "error": "insufficient_bonus_points",
                            "message": f"Bản FREE chỉ chat miễn phí với Deepseek. Bạn còn {balance['points_remaining']} điểm thưởng, cần 2 điểm để chat với {request.provider}. Nâng cấp để dùng Claude/ChatGPT không giới hạn!",
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
                    f"💵 FREE user using bonus points - {request.provider} ({balance['points_remaining']} points available)"
                )

        # === PAID USER LOGIC ===
        else:
            # Check sufficient points (1 for Deepseek, 2 for others)
            check_result = await points_service.check_sufficient_points(
                user_id=user_id,
                points_needed=points_cost,
                service=f"ai_chat_{provider_name}",
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
                f"💰 PAID user - {request.provider} will cost {points_cost} points ({balance['points_remaining']} available)"
            )

        # Get or create conversation
        conversation_id = request.conversation_id

        if not conversation_id:
            # No conversation_id provided - get user's latest active conversation or create new one
            try:
                user_conversations = await user_manager.get_user_conversations(
                    user_id=user_id, limit=1, offset=0
                )

                if user_conversations and len(user_conversations) > 0:
                    # Use the most recent conversation
                    latest_conversation = user_conversations[0]
                    conversation_id = latest_conversation["conversation_id"]
                    logger.info(
                        f"🔄 Using existing conversation {conversation_id} for user {user_id}"
                    )
                else:
                    # Create new conversation
                    conversation_id = str(uuid.uuid4())
                    logger.info(
                        f"🆕 Created new conversation {conversation_id} for user {user_id}"
                    )

            except Exception as conv_error:
                logger.warning(f"⚠️ Error getting user conversations: {conv_error}")
                # Fallback: create new conversation
                conversation_id = str(uuid.uuid4())
                logger.info(f"🆕 Fallback: Created new conversation {conversation_id}")
        else:
            logger.info(f"📝 Using provided conversation {conversation_id}")

        # Convert messages to dict format
        messages = [
            {"role": msg.role, "content": msg.content} for msg in request.messages
        ]

        # If conversation exists, load and prepend chat history with token limits
        if conversation_id:
            try:
                existing_conversation = await user_manager.get_conversation_detail(
                    user_id=user_id, conversation_id=conversation_id
                )

                if existing_conversation and existing_conversation.get("messages"):
                    # Get existing messages
                    existing_messages = existing_conversation["messages"]

                    # Check for duplication of the last message
                    if (
                        existing_messages
                        and messages
                        and existing_messages[-1].get("content")
                        == messages[0].get("content")
                    ):
                        # Remove duplicate from new messages
                        new_messages_filtered = messages[1:]
                        logger.info(f"🔄 Removed duplicate message from new request")
                    else:
                        new_messages_filtered = messages

                    # Apply token-based history limiting (24k for history, 8k reserved for new query + response)
                    messages = limit_conversation_history(
                        existing_messages=existing_messages,
                        new_messages=new_messages_filtered,
                        max_history_tokens=24000,
                        reserved_tokens=8000,
                    )

                    logger.info(
                        f"💾 Applied token limits: {len(existing_messages)} → {len(messages) - len(new_messages_filtered)} history messages"
                    )
                else:
                    logger.info(
                        f"📋 New conversation - no existing history for {conversation_id}"
                    )

            except Exception as history_error:
                logger.warning(
                    f"⚠️ Could not load conversation history: {history_error}"
                )
                # Continue with just the new messages if history loading fails

        # Prepare for streaming
        logger.info(f"👤 User {user_id} starting chat stream with {request.provider}")
        logger.info(f"💬 Conversation: {conversation_id}")
        logger.info(f"📝 Total messages (including history): {len(messages)}")

        # Stream response generator
        async def generate_stream():
            try:
                full_response = ""

                # Send initial metadata
                yield f"data: {json.dumps({'type': 'metadata', 'conversation_id': conversation_id, 'provider': request.provider})}\n\n"

                # Stream AI response
                async for chunk in ai_chat_service.chat_stream(
                    provider=provider,
                    messages=messages,
                    temperature=request.temperature,
                    max_tokens=request.max_tokens,
                ):
                    if chunk:
                        full_response += chunk
                        # Send chunk data
                        yield f"data: {json.dumps({'type': 'content', 'content': chunk})}\n\n"

                # Save conversation after streaming completes
                try:
                    # Add assistant response to messages
                    messages.append({"role": "assistant", "content": full_response})

                    # Check if we're in development mode without MongoDB
                    import os

                    env_mode = os.getenv("ENV", "production").lower()
                    mongodb_uri = os.getenv("MONGODB_URI", "")

                    # Skip saving if using Docker MongoDB in local development
                    if (
                        env_mode == "development"
                        and "host.docker.internal" in mongodb_uri
                    ):
                        logger.warning(
                            "⚠️ Skipping conversation save - Development mode with Docker MongoDB"
                        )
                        yield f"data: {json.dumps({'type': 'complete', 'conversation_id': conversation_id, 'saved': False, 'reason': 'development_mode'})}\n\n"
                    else:
                        # Save conversation
                        await user_manager.save_conversation(
                            user_id=user_id,
                            conversation_id=conversation_id,
                            messages=messages,
                            ai_provider=request.provider,
                            metadata={
                                "temperature": request.temperature,
                                "max_tokens": request.max_tokens,
                                "total_tokens": len(
                                    full_response.split()
                                ),  # Approximate
                            },
                        )

                        logger.info(
                            f"💾 Conversation {conversation_id} saved successfully"
                        )

                        # === AFTER STREAMING SUCCESS: Deduct points or increment daily counter ===
                        try:
                            if should_deduct_points:
                                # PAID users or FREE users using bonus points
                                await points_service.deduct_points(
                                    user_id=user_id,
                                    amount=points_cost,
                                    service=f"ai_chat_{provider_name}",
                                    resource_id=conversation_id,
                                    description=f"Chat with {request.provider} ({points_cost} {'point' if points_cost == 1 else 'points'})",
                                )
                                logger.info(
                                    f"💸 Deducted {points_cost} points for {request.provider} chat"
                                )
                            else:
                                # FREE users: Daily Deepseek chat (0 points, just increment counter)
                                await subscription_service.increment_daily_chat(user_id)
                                new_count = subscription.daily_chat_count + 1
                                logger.info(
                                    f"📊 Incremented daily chat counter: {new_count}/10 for FREE user"
                                )

                        except Exception as points_error:
                            logger.error(
                                f"❌ Error processing points/counter: {points_error}"
                            )
                            # Don't fail the request if points processing fails

                        yield f"data: {json.dumps({'type': 'complete', 'conversation_id': conversation_id, 'saved': True, 'points_deducted': points_cost if should_deduct_points else 0})}\n\n"

                except Exception as save_error:
                    logger.error(f"❌ Error saving conversation: {save_error}")
                    yield f"data: {json.dumps({'type': 'error', 'message': 'Failed to save conversation'})}\n\n"

                # Send final done signal
                yield "data: [DONE]\n\n"

            except Exception as e:
                logger.error(f"❌ Stream generation error: {e}")
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

        # Return streaming response
        return StreamingResponse(
            generate_stream(),
            media_type="text/plain",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Content-Type": "text/event-stream",
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Chat stream error: {e}")
        raise HTTPException(status_code=500, detail=f"Chat stream failed: {str(e)}")


@router.get("/conversations")
async def get_conversations(
    limit: int = 20, offset: int = 0, current_user: dict = Depends(require_auth)
):
    """Get user's conversation history"""

    try:
        user_id = current_user["uid"]

        conversations = await user_manager.get_user_conversations(
            user_id=user_id, limit=limit, offset=offset
        )

        # Format conversations for response
        formatted_conversations = []
        for conv in conversations:
            last_message = None
            if conv.get("messages") and len(conv["messages"]) > 0:
                last_msg = conv["messages"][-1]
                last_message = (
                    last_msg.get("content", "")[:100] + "..."
                    if len(last_msg.get("content", "")) > 100
                    else last_msg.get("content", "")
                )

            formatted_conversations.append(
                ConversationResponse(
                    conversation_id=conv["conversation_id"],
                    created_at=conv["created_at"],
                    updated_at=conv["updated_at"],
                    message_count=len(conv.get("messages", [])),
                    last_message=last_message,
                )
            )

        logger.info(
            f"👤 User {user_id} fetched {len(formatted_conversations)} conversations"
        )

        return {
            "conversations": formatted_conversations,
            "total": len(formatted_conversations),
            "limit": limit,
            "offset": offset,
        }

    except Exception as e:
        logger.error(f"❌ Error getting conversations: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get conversations: {str(e)}"
        )


@router.get("/conversations/{conversation_id}")
async def get_conversation_detail(
    conversation_id: str, current_user: dict = Depends(require_auth)
):
    """Get detailed conversation with all messages"""

    try:
        user_id = current_user["uid"]

        conversation = await user_manager.get_conversation_detail(
            user_id=user_id, conversation_id=conversation_id
        )

        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")

        logger.info(f"👤 User {user_id} fetched conversation {conversation_id}")

        return conversation

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error getting conversation detail: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get conversation: {str(e)}"
        )


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str, current_user: dict = Depends(require_auth)
):
    """Delete a conversation"""

    try:
        user_id = current_user["uid"]

        success = await user_manager.delete_conversation(
            user_id=user_id, conversation_id=conversation_id
        )

        if not success:
            raise HTTPException(status_code=404, detail="Conversation not found")

        logger.info(f"👤 User {user_id} deleted conversation {conversation_id}")

        return {"message": "Conversation deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error deleting conversation: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to delete conversation: {str(e)}"
        )


@router.post("/conversations/{conversation_id}/clear")
async def clear_conversation(
    conversation_id: str, current_user: dict = Depends(require_auth)
):
    """Clear all messages from a conversation"""

    try:
        user_id = current_user["uid"]

        success = await user_manager.clear_conversation_messages(
            user_id=user_id, conversation_id=conversation_id
        )

        if not success:
            raise HTTPException(status_code=404, detail="Conversation not found")

        logger.info(f"👤 User {user_id} cleared conversation {conversation_id}")

        return {"message": "Conversation cleared successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error clearing conversation: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to clear conversation: {str(e)}"
        )


@router.get("/stats")
async def get_chat_stats(current_user: dict = Depends(require_auth)):
    """Get user's chat statistics"""

    try:
        user_id = current_user["uid"]

        stats = await user_manager.get_user_chat_stats(user_id)

        logger.info(f"👤 User {user_id} fetched chat stats")

        return stats

    except Exception as e:
        logger.error(f"❌ Error getting chat stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")


# Additional helper endpoints
@router.get("/test")
async def test_endpoint():
    """Test endpoint to verify chat routes work"""
    return {
        "message": "Chat routes working!",
        "timestamp": datetime.now(),
        "endpoints": [
            "GET /api/chat/providers - Get available AI providers",
            "POST /api/chat/stream - Stream chat with AI",
            "GET /api/chat/conversations - Get user conversations",
            "GET /api/chat/conversations/{id} - Get conversation detail",
            "DELETE /api/chat/conversations/{id} - Delete conversation",
            "POST /api/chat/conversations/{id}/clear - Clear conversation messages",
            "GET /api/chat/stats - Get user chat statistics",
        ],
    }
