"""
Authentication API Routes
API endpoints cho Firebase authentication và user management
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import time

from src.middleware.firebase_auth import get_current_user, require_auth
from src.services.user_manager import get_user_manager, UserManager
from src.services.subscription_service import get_subscription_service
from src.config.firebase_config import firebase_config
from src.utils.logger import setup_logger

logger = setup_logger()

# Create router
router = APIRouter(prefix="/api/auth", tags=["Authentication"])


# Pydantic models
class UserProfileResponse(BaseModel):
    """User profile response model"""

    firebase_uid: str
    email: Optional[str]
    display_name: Optional[str]
    photo_url: Optional[str]
    email_verified: bool
    provider: str
    created_at: datetime
    last_login: datetime
    subscription_plan: str = "free"
    total_conversations: int = 0
    total_files: int = 0
    preferences: Dict[str, Any] = {}


class RegisterResponse(BaseModel):
    """Registration response model"""

    success: bool
    message: str
    user: UserProfileResponse


class ConversationMessage(BaseModel):
    """Single message in conversation"""

    message_id: str
    role: str  # user, assistant, system
    content: str
    timestamp: datetime
    metadata: Dict[str, Any] = {}


class ConversationDetail(BaseModel):
    """Full conversation with all messages"""

    conversation_id: str
    user_id: str
    ai_provider: Optional[str]
    created_at: datetime
    updated_at: datetime
    messages: List[ConversationMessage]
    metadata: Dict[str, Any] = {}


class AuthConversationSummary(BaseModel):
    """
    Corrected conversation summary model for auth routes.
    This reflects the actual data available in the conversation documents.
    """

    conversation_id: str
    created_at: datetime
    updated_at: datetime
    message_count: int
    last_message: Optional[str] = None
    ai_provider: Optional[str] = None


@router.post("/register", response_model=RegisterResponse)
async def register_user(
    user_data: Dict[str, Any] = Depends(get_current_user),
    user_manager: UserManager = Depends(get_user_manager),
):
    """
    Register or login user with Firebase authentication
    Frontend sẽ gửi Firebase ID token trong Authorization header
    """
    try:
        # Create or update user in database
        user_doc = await user_manager.create_or_update_user(user_data)
        
        firebase_uid = user_doc["firebase_uid"]
        
        # === AUTO-CREATE FREE SUBSCRIPTION WITH 10 BONUS POINTS ===
        subscription_service = get_subscription_service()
        
        # Check if user already has a subscription
        try:
            existing_subscription = await subscription_service.get_or_create_subscription(firebase_uid)
            
            # If this is a new subscription (just created), log it
            if existing_subscription.plan == "free" and existing_subscription.points_total == 10:
                logger.info(f"🎁 New FREE subscription created for user {firebase_uid} with 10 bonus points")
            else:
                logger.info(f"✅ User {firebase_uid} already has {existing_subscription.plan} subscription")
                
        except Exception as sub_error:
            logger.error(f"❌ Error creating subscription for user {firebase_uid}: {sub_error}")
            # Don't fail registration if subscription creation fails
            existing_subscription = None

        # Convert to response model
        user_profile = UserProfileResponse(
            firebase_uid=user_doc["firebase_uid"],
            email=user_doc.get("email"),
            display_name=user_doc.get("display_name"),
            photo_url=user_doc.get("photo_url"),
            email_verified=user_doc.get("email_verified", False),
            provider=user_doc.get("provider", "unknown"),
            created_at=user_doc.get("created_at", datetime.now()),
            last_login=user_doc.get("last_login", datetime.now()),
            subscription_plan=existing_subscription.plan if existing_subscription else "free",
            total_conversations=user_doc.get("total_conversations", 0),
            total_files=user_doc.get("total_files", 0),
            preferences=user_doc.get("preferences", {}),
        )

        return RegisterResponse(
            success=True,
            message="User registered/updated successfully with FREE plan (10 bonus points)",
            user=user_profile,
        )

    except Exception as e:
        logger.error(f"❌ Registration error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Registration failed: {str(e)}",
        )


@router.get("/profile", response_model=UserProfileResponse)
async def get_user_profile(
    user_data: Dict[str, Any] = Depends(require_auth),
    user_manager: UserManager = Depends(get_user_manager),
):
    """
    Get current user profile
    Requires valid Firebase token
    """
    try:
        firebase_uid = user_data["firebase_uid"]

        # Get user from database
        user_doc = await user_manager.get_user(firebase_uid)

        if not user_doc:
            # User not found, create new user
            user_doc = await user_manager.create_or_update_user(user_data)

        # Convert to response model
        return UserProfileResponse(
            firebase_uid=user_doc["firebase_uid"],
            email=user_doc.get("email"),
            display_name=user_doc.get("display_name"),
            photo_url=user_doc.get("photo_url"),
            email_verified=user_doc.get("email_verified", False),
            provider=user_doc.get("provider", "unknown"),
            created_at=user_doc.get("created_at", datetime.now()),
            last_login=user_doc.get("last_login", datetime.now()),
            subscription_plan=user_doc.get("subscription_plan", "free"),
            total_conversations=user_doc.get("total_conversations", 0),
            total_files=user_doc.get("total_files", 0),
            preferences=user_doc.get("preferences", {}),
        )

    except Exception as e:
        logger.error(f"❌ Profile fetch error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch profile: {str(e)}",
        )


@router.post("/logout")
async def logout_user():
    """
    Logout endpoint
    Firebase logout is handled on client side
    This endpoint can be used for logging or cleanup
    """
    return {
        "success": True,
        "message": "Logout successful. Please clear Firebase token on client side.",
    }


@router.get("/conversations", response_model=List[AuthConversationSummary])
async def get_user_conversations(
    limit: int = 20,
    offset: int = 0,
    user_data: Dict[str, Any] = Depends(require_auth),
    user_manager: UserManager = Depends(get_user_manager),
):
    """
    Get user's conversations list
    Returns conversation summaries without full message history
    """
    try:
        firebase_uid = user_data["firebase_uid"]

        conversations = await user_manager.get_user_conversations(
            user_id=firebase_uid, limit=limit, offset=offset
        )

        # Convert to response models
        conversation_summaries = []
        for conv in conversations:
            last_message = None
            if conv.get("messages") and len(conv["messages"]) > 0:
                last_msg = conv["messages"][-1]
                last_message = (
                    last_msg.get("content", "")[:100] + "..."
                    if len(last_msg.get("content", "")) > 100
                    else last_msg.get("content", "")
                )

            conversation_summaries.append(
                AuthConversationSummary(
                    conversation_id=conv["conversation_id"],
                    created_at=conv["created_at"],
                    updated_at=conv["updated_at"],
                    message_count=len(conv.get("messages", [])),
                    last_message=last_message,
                    ai_provider=conv.get("ai_provider"),
                )
            )

        return conversation_summaries

    except Exception as e:
        logger.error(f"❌ Error fetching conversations: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch conversations: {str(e)}",
        )


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
async def get_conversation_detail(
    conversation_id: str,
    user_data: Dict[str, Any] = Depends(require_auth),
    user_manager: UserManager = Depends(get_user_manager),
):
    """
    Get full conversation detail with all messages

    This endpoint returns the complete conversation history including:
    - All messages (user and assistant)
    - Message metadata (timestamps, provider info, etc.)
    - Conversation metadata (apiType, operation type, file context, etc.)

    Use this to:
    1. Load chat history when user opens a conversation
    2. Build conversationHistory array for continuing the chat
    3. Display conversation context in UI
    """
    try:
        firebase_uid = user_data["firebase_uid"]

        conversation = await user_manager.get_conversation(
            conversation_id=conversation_id, user_id=firebase_uid
        )

        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Conversation {conversation_id} not found",
            )

        # Convert messages to response model
        messages = []
        for msg in conversation.get("messages", []):
            messages.append(
                ConversationMessage(
                    message_id=msg.get("message_id", ""),
                    role=msg.get("role", "user"),
                    content=msg.get("content", ""),
                    timestamp=msg.get("timestamp", datetime.utcnow()),
                    metadata=msg.get("metadata", {}),
                )
            )

        return ConversationDetail(
            conversation_id=conversation["conversation_id"],
            user_id=conversation["user_id"],
            ai_provider=conversation.get("ai_provider"),
            created_at=conversation.get("created_at", datetime.utcnow()),
            updated_at=conversation.get("updated_at", datetime.utcnow()),
            messages=messages,
            metadata=conversation.get("metadata", {}),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error fetching conversation {conversation_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch conversation: {str(e)}",
        )


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    user_data: Dict[str, Any] = Depends(require_auth),
    user_manager: UserManager = Depends(get_user_manager),
):
    """
    Delete a conversation

    Permanently removes a conversation and all its messages.
    """
    try:
        firebase_uid = user_data["firebase_uid"]

        success = await user_manager.delete_conversation(
            conversation_id=conversation_id, user_id=firebase_uid
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Conversation {conversation_id} not found or could not be deleted",
            )

        return {
            "success": True,
            "message": f"Conversation {conversation_id} deleted successfully",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error deleting conversation {conversation_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete conversation: {str(e)}",
        )


@router.get("/validate")
async def validate_token(user_data: Dict[str, Any] = Depends(require_auth)):
    """
    Validate Firebase token
    Useful for frontend to check if token is still valid
    """
    return {
        "valid": True,
        "firebase_uid": user_data["firebase_uid"],
        "email": user_data.get("email"),
        "display_name": user_data.get("display_name"),
    }


@router.get("/health")
async def auth_health_check():
    """
    Health check endpoint for authentication service
    """
    try:
        # Try to initialize Firebase config
        from src.config.firebase_config import firebase_config

        firebase_status = "configured" if firebase_config.app else "development_mode"

        return {
            "status": "healthy",
            "firebase_initialized": firebase_config.app is not None,
            "firebase_status": firebase_status,
            "development_mode": firebase_config.app is None,
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"❌ Auth health check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Authentication service unhealthy: {str(e)}",
        )


# ===== END OF AUTHENTICATION ENDPOINTS =====
# Session cookie endpoints removed - frontend uses ID tokens only
