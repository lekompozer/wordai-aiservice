"""
Conversation Analysis API Routes
API routes cho phân tích cuộc trò chuyện và remarketing insights
"""

import json
import logging
from fastapi import APIRouter, HTTPException, Request, Header
from typing import Dict, Any, Optional, List
from datetime import datetime

from src.services.unified_chat_service import unified_chat_service

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/api/conversation/analyze")
async def analyze_conversation_deep(
    request: Dict[str, Any],
    http_request: Request,
    x_company_id: Optional[str] = Header(
        None, description="Company ID for frontend access"
    ),
):
    """
    Deep conversation analysis for remarketing and business insights using Google Gemini
    Phân tích chuyên sâu cuộc trò chuyện cho remarketing và thông tin kinh doanh sử dụng Google Gemini
    """
    try:
        # Extract parameters
        session_id = request.get("session_id")
        conversation_id = request.get("conversation_id")
        company_id = x_company_id or request.get("company_id")

        if not company_id:
            raise HTTPException(
                status_code=400,
                detail="Company ID required. Include X-Company-Id header or company_id in request body.",
            )

        if not session_id and not conversation_id:
            raise HTTPException(
                status_code=400,
                detail="Either session_id or conversation_id is required",
            )

        # Get client IP for logging
        client_ip = http_request.client.host
        logger.info(f"🔍 [CONVERSATION_ANALYSIS] Request from {client_ip}")
        logger.info(
            f"   Company: {company_id} | Session: {session_id} | Conversation: {conversation_id}"
        )

        # Get conversation history
        if session_id:
            conversation_history = unified_chat_service._get_conversation_history(
                session_id
            )
            conversation_stats = unified_chat_service.get_conversation_stats(session_id)
        else:
            # In production, you would fetch by conversation_id from database
            conversation_history = []
            conversation_stats = {}

        if not conversation_history:
            return {
                "error": "No conversation data found",
                "session_id": session_id,
                "conversation_id": conversation_id,
            }

        # Perform deep analysis using Google Gemini
        analysis_result = await _perform_deep_conversation_analysis_with_gemini(
            conversation_history=conversation_history,
            company_id=company_id,
            conversation_stats=conversation_stats,
        )

        logger.info(f"✅ [CONVERSATION_ANALYSIS] Analysis completed")

        return {
            "session_id": session_id,
            "conversation_id": conversation_id,
            "company_id": company_id,
            "analysis": analysis_result,
            "conversation_stats": conversation_stats,
            "analyzed_at": datetime.now().isoformat(),
            "ai_provider": "google_gemini",
        }

    except Exception as e:
        logger.error(f"❌ [CONVERSATION_ANALYSIS] Error: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Analysis failed",
                "message": str(e),
                "session_id": request.get("session_id"),
                "conversation_id": request.get("conversation_id"),
            },
        )


@router.get("/api/conversation/{conversation_id}/summary")
async def get_conversation_summary(
    conversation_id: str, company_id: Optional[str] = Header(None, alias="X-Company-Id")
):
    """
    Get quick conversation summary without deep analysis
    Lấy tóm tắt nhanh cuộc trò chuyện mà không cần phân tích sâu
    """
    try:
        if not company_id:
            raise HTTPException(status_code=400, detail="Company ID required")

        logger.info(
            f"📊 [CONVERSATION_SUMMARY] Getting summary for conversation {conversation_id}"
        )

        # Try to find session by conversation_id
        session_data = None
        conversation_history = []
        session_id = None

        # Search through sessions to find matching conversation
        for sid, conv_data in unified_chat_service.sessions.items():
            if conv_data.get("conversation_id") == conversation_id:
                session_data = conv_data
                session_id = sid
                conversation_history = unified_chat_service._get_conversation_history(
                    sid
                )
                break

        if not session_data:
            # Try direct session lookup if conversation_id is actually session_id
            if conversation_id in unified_chat_service.sessions:
                session_data = unified_chat_service.sessions[conversation_id]
                session_id = conversation_id
                conversation_history = unified_chat_service._get_conversation_history(
                    conversation_id
                )

        if not session_data:
            raise HTTPException(status_code=404, detail="Conversation not found")

        # Create quick summary
        user_message_count = len(
            [msg for msg in conversation_history if getattr(msg, "role", "") == "user"]
        )
        ai_message_count = len(
            [
                msg
                for msg in conversation_history
                if getattr(msg, "role", "") == "assistant"
            ]
        )

        last_message = conversation_history[-1] if conversation_history else None
        last_message_preview = (
            getattr(last_message, "content", "")[:100] + "..." if last_message else ""
        )

        # Calculate duration
        created_at = session_data.get("created_at", datetime.now())
        last_activity = session_data.get("last_activity", datetime.now())
        duration_seconds = (
            (last_activity - created_at).total_seconds()
            if isinstance(created_at, datetime)
            else 0
        )

        # Calculate average response length
        ai_messages_content = [
            getattr(msg, "content", "")
            for msg in conversation_history
            if getattr(msg, "role", "") == "assistant"
        ]
        avg_response_length = sum(
            len(content) for content in ai_messages_content
        ) / max(len(ai_messages_content), 1)

        summary = {
            "conversation_id": conversation_id,
            "session_id": session_id,
            "company_id": company_id,
            "status": (
                "ACTIVE" if session_data.get("message_count", 0) > 0 else "INACTIVE"
            ),
            "message_count": len(conversation_history),
            "user_messages": user_message_count,
            "ai_messages": ai_message_count,
            "created_at": (
                created_at.isoformat()
                if isinstance(created_at, datetime)
                else str(created_at)
            ),
            "last_activity": (
                last_activity.isoformat()
                if isinstance(last_activity, datetime)
                else str(last_activity)
            ),
            "duration_seconds": duration_seconds,
            "last_message_preview": last_message_preview,
            "quick_stats": {
                "avg_response_length": round(avg_response_length, 2),
                "conversation_length": len(conversation_history),
                "has_images": any(
                    getattr(msg, "images", None) for msg in conversation_history
                ),
                "languages_detected": list(
                    set(
                        (
                            getattr(msg, "language", "unknown").value
                            if hasattr(getattr(msg, "language", None), "value")
                            else "unknown"
                        )
                        for msg in conversation_history
                    )
                ),
                "intents_detected": list(
                    set(
                        (
                            getattr(msg, "intent", "unknown").value
                            if hasattr(getattr(msg, "intent", None), "value")
                            else "unknown"
                        )
                        for msg in conversation_history
                    )
                ),
            },
        }

        logger.info(
            f"✅ [CONVERSATION_SUMMARY] Summary generated: {user_message_count} user msgs, {ai_message_count} AI msgs"
        )
        return summary

    except Exception as e:
        logger.error(f"❌ Error getting conversation summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/conversation/list")
async def list_conversations(
    company_id: Optional[str] = Header(None, alias="X-Company-Id"),
    limit: int = 50,
    offset: int = 0,
):
    """
    List all conversations for a company
    Liệt kê tất cả cuộc trò chuyện của một công ty
    """
    try:
        if not company_id:
            raise HTTPException(status_code=400, detail="Company ID required")

        logger.info(
            f"📋 [LIST_CONVERSATIONS] Getting conversations for company {company_id}"
        )

        conversations = []

        # Get all sessions and filter by company
        for session_id, session_data in unified_chat_service.sessions.items():
            # In a real system, you would filter by company_id stored in session
            # For now, we'll include all sessions

            conversation_history = unified_chat_service._get_conversation_history(
                session_id
            )
            if not conversation_history:
                continue

            user_message_count = len(
                [
                    msg
                    for msg in conversation_history
                    if getattr(msg, "role", "") == "user"
                ]
            )
            last_message = conversation_history[-1] if conversation_history else None

            conversations.append(
                {
                    "conversation_id": session_data.get("conversation_id", session_id),
                    "session_id": session_id,
                    "message_count": len(conversation_history),
                    "user_messages": user_message_count,
                    "created_at": session_data.get(
                        "created_at", datetime.now()
                    ).isoformat(),
                    "last_activity": session_data.get(
                        "last_activity", datetime.now()
                    ).isoformat(),
                    "last_message_preview": (
                        getattr(last_message, "content", "")[:50] + "..."
                        if last_message
                        else ""
                    ),
                    "status": "ACTIVE" if len(conversation_history) > 0 else "INACTIVE",
                }
            )

        # Sort by last activity (newest first)
        conversations.sort(key=lambda x: x["last_activity"], reverse=True)

        # Apply pagination
        total = len(conversations)
        paginated_conversations = conversations[offset : offset + limit]

        return {
            "conversations": paginated_conversations,
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": offset + limit < total,
        }

    except Exception as e:
        logger.error(f"❌ Error listing conversations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def _perform_deep_conversation_analysis_with_gemini(
    conversation_history: List, company_id: str, conversation_stats: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Perform deep analysis of entire conversation using Google Gemini
    Thực hiện phân tích sâu toàn bộ cuộc trò chuyện sử dụng Google Gemini
    """
    try:
        # Step 1: Initialize Gemini AI service
        from src.providers.gemini_provider import GeminiProvider

        gemini_provider = GeminiProvider()

        # Step 2: Combine all messages into analysis text
        user_messages = []
        ai_messages = []
        full_conversation = []

        for msg in conversation_history:
            role = getattr(msg, "role", "unknown")
            content = getattr(msg, "content", "")
            timestamp = getattr(msg, "timestamp", datetime.now())

            if role == "user":
                user_messages.append(content)
            elif role == "assistant":
                ai_messages.append(content)

            full_conversation.append(f"{role.title()}: {content}")

        combined_conversation = "\n".join(full_conversation)

        logger.info(
            f"📊 Analyzing conversation with Gemini: {len(user_messages)} user messages, {len(ai_messages)} AI responses"
        )

        # Step 3: Create comprehensive analysis prompt for Gemini
        analysis_prompt = f"""
BẠN LÀ CHUYÊN GIA PHÂN TÍCH CUỘC TRÒ CHUYỆN VÀ REMARKETING CHUYÊN NGHIỆP.

TOÀN BỘ CUỘC TRÒ CHUYỆN:
{combined_conversation}

THỐNG KÊ CUỘC TRÒ CHUYỆN:
- Tổng số tin nhắn: {len(conversation_history)}
- Tin nhắn từ khách hàng: {len(user_messages)}
- Phản hồi từ AI: {len(ai_messages)}
- Thời lượng: {conversation_stats.get('duration_seconds', 0)} giây

NHIỆM VỤ PHÂN TÍCH CHUYÊN SÂU:

1. **Phân tích ý định chính (Primary Intent Analysis)**
   - Xác định ý định chính của khách hàng
   - Độ tin cậy của việc phát hiện ý định
   - Sự thay đổi ý định qua cuộc trò chuyện

2. **Đánh giá mức độ hài lòng khách hàng (Customer Satisfaction)**
   - HIGH: Khách hàng hài lòng, có câu trả lời đầy đủ
   - MEDIUM: Khách hàng được hỗ trợ nhưng vẫn có thắc mắc
   - LOW: Khách hàng không hài lòng hoặc vấn đề chưa được giải quyết

3. **Kết quả cuộc trò chuyện (Conversation Outcome)**
   - CONVERTED: Khách hàng đã chuyển đổi (mua hàng, đăng ký)
   - INTERESTED: Khách hàng quan tâm, cần theo dõi
   - NEEDS_FOLLOWUP: Cần liên hệ lại
   - LOST: Khách hàng không quan tâm
   - INCOMPLETE: Cuộc trò chuyện chưa hoàn thành

4. **Cơ hội Remarketing**
   - Email campaigns
   - Phone follow-up
   - Social media targeting
   - Product recommendations

5. **Đề xuất cải thiện hệ thống**

TRẢ VỀ JSON CHÍNH XÁC THEO ĐỊNH DẠNG:
{{
    "primary_intent": "SALES_INQUIRY|INFORMATION|SUPPORT|BOOKING|COMPLAINT|GENERAL_CHAT",
    "intent_confidence": 0.95,
    "intent_evolution": [
        {{"turn": 1, "intent": "INFORMATION", "confidence": 0.8, "message_preview": "Tôi muốn biết về..."}},
        {{"turn": 3, "intent": "SALES_INQUIRY", "confidence": 0.9, "message_preview": "Giá bao nhiều?"}}
    ],
    "customer_satisfaction": "HIGH|MEDIUM|LOW",
    "satisfaction_indicators": [
        "Khách hàng cảm ơn nhiều lần",
        "Hỏi thêm thông tin chi tiết"
    ],
    "conversation_outcome": "CONVERTED|INTERESTED|NEEDS_FOLLOWUP|LOST|INCOMPLETE",
    "outcome_reasoning": "Khách hàng đã hỏi giá và yêu cầu thông tin liên hệ, cho thấy mức độ quan tâm cao",
    "customer_pain_points": [
        "Lo lắng về giá cả",
        "Cần tư vấn về sản phẩm phù hợp"
    ],
    "products_mentioned": [
        "Gói vay mua nhà",
        "Bảo hiểm xe ô tô"
    ],
    "key_requirements": [
        "Lãi suất thấp",
        "Thủ tục nhanh gọn"
    ],
    "unresolved_issues": [
        "Chưa rõ điều kiện vay cụ thể",
        "Chưa có thông tin về phí dịch vụ"
    ],
    "remarketing_opportunities": [
        {{
            "type": "EMAIL_CAMPAIGN",
            "priority": "HIGH",
            "suggestion": "Gửi email ưu đãi lãi suất đặc biệt cho khách hàng mới",
            "timing": "24H",
            "target_products": ["Gói vay mua nhà"],
            "personalization": "Nhắc đến yêu cầu lãi suất thấp của khách hàng"
        }},
        {{
            "type": "PHONE_FOLLOWUP",
            "priority": "MEDIUM",
            "suggestion": "Gọi điện tư vấn chi tiết về điều kiện vay",
            "timing": "WEEK",
            "talking_points": ["Điều kiện vay cụ thể", "Phí dịch vụ"]
        }}
    ],
    "improvement_suggestions": [
        {{
            "category": "PRODUCT_INFO",
            "issue": "Thiếu thông tin chi tiết về phí dịch vụ",
            "solution": "Bổ sung bảng phí chi tiết trong cơ sở dữ liệu",
            "priority": "HIGH"
        }},
        {{
            "category": "RESPONSE_QUALITY",
            "issue": "AI chưa chủ động hỏi về nhu cầu cụ thể",
            "solution": "Cải thiện prompt để AI hỏi thêm về requirements",
            "priority": "MEDIUM"
        }}
    ],
    "next_actions": [
        "Gửi email follow-up trong 24h",
        "Chuẩn bị tài liệu điều kiện vay chi tiết",
        "Lên lịch gọi điện tư vấn"
    ],
    "conversation_sentiment": {{
        "overall": "POSITIVE|NEUTRAL|NEGATIVE",
        "customer_tone": "FRIENDLY|PROFESSIONAL|CONCERNED|FRUSTRATED",
        "engagement_level": "HIGH|MEDIUM|LOW"
    }},
    "business_value": {{
        "potential_revenue": "HIGH|MEDIUM|LOW",
        "conversion_probability": 0.75,
        "customer_lifetime_value": "HIGH|MEDIUM|LOW"
    }},
    "ai_performance": {{
        "response_relevance": 0.85,
        "response_helpfulness": 0.80,
        "response_speed": "GOOD|AVERAGE|SLOW",
        "missed_opportunities": [
            "Không đề xuất sản phẩm bổ sung",
            "Chưa thu thập thông tin liên hệ"
        ],
        "strengths": [
            "Trả lời chính xác các câu hỏi",
            "Thái độ thân thiện"
        ]
    }},
    "summary": "Khách hàng quan tâm đến gói vay mua nhà với yêu cầu lãi suất thấp. Mức độ engagement cao, cần follow-up trong 24h với ưu đãi cụ thể.",
    "analysis_metadata": {{
        "ai_provider": "google_gemini",
        "analysis_timestamp": "{datetime.now().isoformat()}",
        "conversation_length_chars": {len(combined_conversation)},
        "analysis_duration_ms": 0
    }}
}}

YÊU CẦU QUAN TRỌNG:
1. Phân tích khách quan và chi tiết
2. Đưa ra remarketing suggestions thực tế và khả thi
3. Đánh giá hiệu quả AI một cách công bằng
4. Tập trung vào business value và conversion opportunities
5. Trả về JSON hợp lệ, không có text bổ sung
"""

        # Step 4: Get analysis from Gemini
        logger.info("🤖 Sending conversation to Gemini for deep analysis...")

        analysis_response = await gemini_provider.get_completion(
            prompt=analysis_prompt,
            max_tokens=4000,
            temperature=0.3,  # Lower temperature for more consistent analysis
        )

        # Step 5: Parse and validate response
        try:
            # Clean JSON response
            clean_response = _clean_json_response(analysis_response)
            analysis_data = json.loads(clean_response)

            # Add processing metadata
            analysis_data["analysis_metadata"].update(
                {
                    "total_messages": len(conversation_history),
                    "user_messages_count": len(user_messages),
                    "ai_messages_count": len(ai_messages),
                    "company_id": company_id,
                    "analyzer_version": "2.0_gemini",
                }
            )

            logger.info(f"✅ Gemini analysis completed successfully")
            logger.info(
                f"   Primary Intent: {analysis_data.get('primary_intent', 'Unknown')}"
            )
            logger.info(
                f"   Outcome: {analysis_data.get('conversation_outcome', 'Unknown')}"
            )
            logger.info(
                f"   Satisfaction: {analysis_data.get('customer_satisfaction', 'Unknown')}"
            )
            logger.info(
                f"   Remarketing Opportunities: {len(analysis_data.get('remarketing_opportunities', []))}"
            )

            return analysis_data

        except json.JSONDecodeError as e:
            logger.error(f"❌ Failed to parse Gemini analysis JSON: {e}")

            # Return fallback analysis
            return {
                "error": "Analysis parsing failed",
                "raw_analysis": (
                    analysis_response[:500] + "..."
                    if len(analysis_response) > 500
                    else analysis_response
                ),
                "fallback_summary": f"Cuộc trò chuyện có {len(user_messages)} tin nhắn từ khách hàng. Cần phân tích thủ công.",
                "analysis_metadata": {
                    "ai_provider": "google_gemini",
                    "total_messages": len(conversation_history),
                    "user_messages_count": len(user_messages),
                    "ai_messages_count": len(ai_messages),
                    "error": str(e),
                    "analysis_timestamp": datetime.now().isoformat(),
                },
            }

    except Exception as e:
        logger.error(f"❌ Gemini analysis error: {e}")
        return {
            "error": f"Analysis failed: {str(e)}",
            "analysis_metadata": {
                "ai_provider": "google_gemini",
                "total_messages": (
                    len(conversation_history)
                    if "conversation_history" in locals()
                    else 0
                ),
                "error": str(e),
                "analysis_timestamp": datetime.now().isoformat(),
            },
        }


def _clean_json_response(response: str) -> str:
    """
    Clean and extract JSON from Gemini response
    Làm sạch và trích xuất JSON từ phản hồi của Gemini
    """
    try:
        # Remove markdown code blocks
        if "```json" in response:
            response = response.split("```json")[1].split("```")[0]
        elif "```" in response:
            response = response.split("```")[1].split("```")[0]

        # Remove extra whitespace
        response = response.strip()

        # Find JSON object bounds
        start_idx = response.find("{")
        end_idx = response.rfind("}")

        if start_idx != -1 and end_idx != -1:
            response = response[start_idx : end_idx + 1]

        return response

    except Exception as e:
        logger.warning(f"⚠️ JSON cleaning failed: {e}")
        return response
