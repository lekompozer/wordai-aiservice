"""
Unified Chat API Routes
API routes cho hệ thống chat thống nhất đa ngành
"""

import json
from fastapi import APIRouter, HTTPException, Request, Header
from fastapi.responses import StreamingResponse
from typing import Dict, Any, Optional
from datetime import datetime

from src.models.unified_models import (
    UnifiedChatRequest,
    UnifiedChatResponse,
    Industry,
    Language,
    CompanyConfig,
    ChannelType,
    LeadSourceInfo,
)
from src.services.unified_chat_service import unified_chat_service
from src.middleware.auth import verify_company_access
from src.utils.logger import setup_logger

logger = setup_logger()

router = APIRouter()


@router.post("/api/unified/chat-stream")
async def unified_chat_stream(
    http_request: Request,
    x_company_id: Optional[str] = Header(
        None, description="Company ID for frontend access"
    ),
):
    """
    ✅ OPTIMIZED: Unified streaming chat endpoint with 7-step optimization
    Endpoint chat streaming thống nhất tối ưu theo 7 bước
    """
    try:
        # First, let's get the raw request body to debug validation issues
        request_body = await http_request.json()
        logger.info(f"🔍 [DEBUG] Raw request body received")

        # Try to parse the request with better error handling
        try:
            request = UnifiedChatRequest(**request_body)
        except Exception as validation_error:
            logger.error(
                f"❌ [VALIDATION] Pydantic validation failed: {validation_error}"
            )
            raise HTTPException(
                status_code=422,
                detail={
                    "error": "Request validation failed",
                    "message": str(validation_error),
                    "received_data": request_body,
                },
            )
        # Get company ID from header (for frontend) or request body (for backend)
        company_id = x_company_id or request.company_id
        if not company_id:
            raise HTTPException(
                status_code=400,
                detail="Company ID required. Include X-Company-Id header or company_id in request body.",
            )

        # Update request with company ID from header if provided
        if x_company_id:
            request.company_id = x_company_id

        # Validate required fields
        if not request.message or not request.message.strip():
            raise HTTPException(
                status_code=400,
                detail="Message is required and cannot be empty.",
            )

        # NEW: Validate channel field and set default
        channel = request.channel or ChannelType.CHATDEMO
        request.channel = channel

        # Log channel information
        logger.info(f"📡 [CHANNEL_VALIDATION] Channel: {channel.value}")

        # Validate channel-specific requirements
        if channel in [
            ChannelType.MESSENGER,
            ChannelType.INSTAGRAM,
            ChannelType.WHATSAPP,
        ]:
            # Backend channels require specific user_info
            if not request.user_info or not request.user_info.user_id:
                raise HTTPException(
                    status_code=400,
                    detail=f"Channel '{channel.value}' requires valid user_info with user_id",
                )

        # Validate lead_source for backend channels
        if channel != ChannelType.CHATDEMO and not request.lead_source:
            logger.warning(
                f"⚠️ [CHANNEL_VALIDATION] Backend channel {channel.value} missing lead_source"
            )

        # Auto-set session_id if not provided
        if not request.session_id:
            user_id = (
                request.user_info.user_id
                if request.user_info and request.user_info.user_id
                else f"anonymous_{int(datetime.now().timestamp())}"
            )
            request.session_id = user_id

        # Get client IP for logging
        client_ip = http_request.client.host
        logger.info(f"🚀 [OPTIMIZED_STREAM] Request from {client_ip}")
        logger.info(f"   Company: {company_id} | Industry: {request.industry.value}")
        logger.info(f"   Channel: {channel.value} | Session: {request.session_id}")

        # Enhanced user info logging with channel context
        if request.user_info:
            user_id = request.user_info.user_id or "anonymous"
            source = (
                request.user_info.source.value
                if request.user_info.source
                else "chatdemo"
            )
            logger.info(f"   User: {user_id} | Source: {source}")
            if request.user_info.name:
                logger.info(f"   User Name: {request.user_info.name}")
        else:
            logger.info(f"   User: anonymous | Source: chatdemo")

        # Log lead source if provided
        if request.lead_source:
            logger.info(
                f"   Lead Source: {request.lead_source.sourceCode} - {request.lead_source.name}"
            )

        logger.info(f"   Message: {request.message[:100]}...")
        logger.info(f"   🔍 Using: Comprehensive Hybrid Search Strategy")

        # Call the new optimized stream method
        return await unified_chat_service.stream_response_optimized(request)

    except HTTPException:
        # Re-raise HTTP exceptions (including our validation error)
        raise
    except Exception as e:
        logger.error(f"❌ [OPTIMIZED_STREAM] Error: {e}")
        logger.error(f"Optimized streaming failed: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Optimized streaming setup failed",
                "message": str(e),
                "company_id": x_company_id if x_company_id else "unknown",
            },
        )


@router.get("/api/unified/industries")
async def get_supported_industries():
    """
    Get list of supported industries
    Lấy danh sách các ngành được hỗ trợ
    """
    try:
        industries = [
            {
                "code": industry.value,
                "name_vi": _get_industry_name_vi(industry),
                "name_en": _get_industry_name_en(industry),
                "supported_features": _get_industry_features(industry),
            }
            for industry in Industry
        ]

        return {"industries": industries, "total": len(industries)}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/unified/languages")
async def get_supported_languages():
    """
    Get list of supported languages
    Lấy danh sách ngôn ngữ được hỗ trợ
    """
    try:
        languages = [
            {
                "code": Language.VIETNAMESE.value,
                "name": "Tiếng Việt",
                "name_en": "Vietnamese",
                "is_default": True,
            },
            {
                "code": Language.ENGLISH.value,
                "name": "English",
                "name_en": "English",
                "is_default": False,
            },
            {
                "code": Language.AUTO_DETECT.value,
                "name": "Tự động phát hiện",
                "name_en": "Auto-detect",
                "is_default": False,
            },
        ]

        return {"languages": languages, "total": len(languages)}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/unified/detect-intent")
async def detect_intent_only(request: UnifiedChatRequest):
    """
    Detect intent only without generating response
    Chỉ phát hiện ý định mà không tạo phản hồi
    """
    try:
        from src.services.intent_detector import intent_detector
        from src.services.language_detector import language_detector

        # Detect language / Phát hiện ngôn ngữ
        language_result = language_detector.detect_language(request.message)

        # Detect intent / Phát hiện ý định
        intent_result = await intent_detector.detect_intent(
            message=request.message,
            industry=request.industry,
            company_id=request.company_id,
            conversation_history=None,
            context=request.context,
        )

        return {
            "language_detection": {
                "language": language_result.language.value,
                "confidence": language_result.confidence,
                "indicators": language_result.indicators,
            },
            "intent_detection": {
                "intent": intent_result.intent.value,
                "confidence": intent_result.confidence,
                "reasoning": intent_result.reasoning,
                "extracted_info": intent_result.extracted_info,
            },
            "suggested_routing": _get_routing_suggestion(
                intent_result.intent, request.industry
            ),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/unified/session/{session_id}")
async def get_session_info(session_id: str):
    """
    Get session information and conversation history
    Lấy thông tin phiên và lịch sử hội thoại
    """
    try:
        # Get session data from unified chat service / Lấy dữ liệu phiên từ unified chat service
        session_data = unified_chat_service._get_session_data(session_id)
        conversation_history = unified_chat_service._get_conversation_history(
            session_id
        )

        return {
            "session_id": session_id,
            "data": session_data,
            "conversation_history": [
                {
                    "role": msg.role,
                    "content": msg.content,
                    "intent": msg.intent.value if msg.intent else None,
                    "language": msg.language.value if msg.language else None,
                    "timestamp": msg.timestamp.isoformat(),
                }
                for msg in conversation_history
            ],
            "message_count": len(conversation_history),
            "last_activity": (
                conversation_history[-1].timestamp.isoformat()
                if conversation_history
                else None
            ),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/api/unified/session/{session_id}")
async def clear_session(session_id: str):
    """
    Clear session data and conversation history
    Xóa dữ liệu phiên và lịch sử hội thoại
    """
    try:
        # Clear session from unified chat service / Xóa phiên từ unified chat service
        if session_id in unified_chat_service.sessions:
            del unified_chat_service.sessions[session_id]

        return {"message": "Session cleared successfully", "session_id": session_id}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/unified/stats")
async def get_system_stats():
    """
    Get system statistics
    Lấy thống kê hệ thống
    """
    try:
        total_sessions = len(unified_chat_service.sessions)
        active_sessions = sum(
            1
            for session in unified_chat_service.sessions.values()
            if session.get("history") and len(session["history"]) > 0
        )

        # Calculate intent distribution / Tính phân bố ý định
        intent_counts = {}
        for session in unified_chat_service.sessions.values():
            for msg in session.get("history", []):
                if hasattr(msg, "intent") and msg.intent:
                    intent = msg.intent.value
                    intent_counts[intent] = intent_counts.get(intent, 0) + 1

        return {
            "total_sessions": total_sessions,
            "active_sessions": active_sessions,
            "intent_distribution": intent_counts,
            "supported_industries": len(Industry),
            "supported_languages": len(Language),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/unified/webhook/test")
async def test_webhook_connection():
    """
    Test webhook connection to backend
    Test kết nối webhook tới backend
    """
    try:
        from src.services.webhook_service import webhook_service

        success = await webhook_service.test_webhook_connection()

        return {
            "webhook_enabled": not webhook_service.disabled,
            "webhook_url": webhook_service.webhook_url,
            "connection_test": "success" if success else "failed",
            "message": "Webhook connection test completed",
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail={"error": "Webhook test failed", "message": str(e)}
        )


# Helper functions / Các hàm hỗ trợ


def _get_industry_name_vi(industry: Industry) -> str:
    """Get Vietnamese name for industry / Lấy tên tiếng Việt cho ngành"""
    names = {
        Industry.BANKING: "Ngân hàng",
        Industry.INSURANCE: "Bảo hiểm",
        Industry.RESTAURANT: "Nhà hàng",
        Industry.HOTEL: "Khách sạn",
        Industry.RETAIL: "Bán lẻ",
        Industry.FASHION: "Thời trang",
        Industry.INDUSTRIAL: "Công nghiệp",
        Industry.HEALTHCARE: "Y tế",
        Industry.EDUCATION: "Giáo dục",
        Industry.OTHER: "Khác",
    }
    return names.get(industry, industry.value)


def _get_industry_name_en(industry: Industry) -> str:
    """Get English name for industry / Lấy tên tiếng Anh cho ngành"""
    names = {
        Industry.BANKING: "Banking",
        Industry.INSURANCE: "Insurance",
        Industry.RESTAURANT: "Restaurant",
        Industry.HOTEL: "Hotel",
        Industry.RETAIL: "Retail",
        Industry.FASHION: "Fashion",
        Industry.INDUSTRIAL: "Industrial",
        Industry.HEALTHCARE: "Healthcare",
        Industry.EDUCATION: "Education",
        Industry.OTHER: "Other",
    }
    return names.get(industry, industry.value.title())


def _get_industry_features(industry: Industry) -> Dict[str, bool]:
    """Get supported features for industry / Lấy tính năng hỗ trợ cho ngành"""
    return {
        "information_agent": True,  # All industries support information queries
        "sales_agent": industry
        in [Industry.BANKING, Industry.RESTAURANT, Industry.HOTEL, Industry.RETAIL],
        "booking_system": industry in [Industry.RESTAURANT, Industry.HOTEL],
        "loan_assessment": industry == Industry.BANKING,
        "inventory_check": industry in [Industry.RETAIL, Industry.FASHION],
        "appointment_booking": industry in [Industry.HEALTHCARE, Industry.EDUCATION],
    }


def _get_routing_suggestion(intent, industry: Industry) -> Dict[str, str]:
    """Get routing suggestion based on intent and industry / Lấy gợi ý định tuyến dựa trên ý định và ngành"""
    suggestions = {
        "information": "Route to Information Agent for RAG-based responses",
        "sales_inquiry": f"Route to {industry.value} Sales Agent for transaction handling",
        "support": "Route to Support Agent for customer service",
        "general_chat": "Route to General Chat Agent for casual conversation",
    }

    if intent.value in suggestions:
        return {
            "agent": suggestions[intent.value],
            "endpoint": f"/api/{industry.value}/agent",
            "priority": "high" if intent.value == "sales_inquiry" else "medium",
        }

    return {
        "agent": "Default Information Agent",
        "endpoint": "/api/unified/chat",
        "priority": "low",
    }
