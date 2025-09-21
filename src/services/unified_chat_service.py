"""
Unified Chat Service
Dịch vụ chat thống nhất với phát hiện ý định và định tuyến thông minh
"""

import json
import re
import asyncio
import uuid
import time
from typing import Dict, Any, Optional, List, AsyncGenerator
from datetime import datetime
from fastapi.responses import StreamingResponse

from src.models.unified_models import (
    UnifiedChatRequest,
    UnifiedChatResponse,
    ChatIntent,
    Language,
    Industry,
    ConversationHistory,
    ChannelType,
    LeadSourceInfo,
)
from src.services.language_detector import language_detector
from src.services.intent_detector import intent_detector
from src.services.admin_service import AdminService
from src.services.qdrant_company_service import get_qdrant_service
from src.services.product_catalog_service import get_product_catalog_service
from src.providers.ai_provider_manager import AIProviderManager
from src.services.webhook_service import webhook_service
from src.core.config import APP_CONFIG
from src.utils.logger import setup_logger

logger = setup_logger()


class UnifiedChatService:
    """
    Unified chat service with intelligent routing
    Dịch vụ chat thống nhất với định tuyến thông minh
    """

    def __init__(self):
        # Initialize AI provider / Khởi tạo AI provider
        from src.core.config import APP_CONFIG

        self.ai_manager = AIProviderManager(
            deepseek_api_key=APP_CONFIG.get("deepseek_api_key"),
            chatgpt_api_key=APP_CONFIG.get("chatgpt_api_key"),
            gemini_api_key=APP_CONFIG.get("gemini_api_key"),
            cerebras_api_key=APP_CONFIG.get("cerebras_api_key"),
        )

        # Initialize Admin Service for company data search / Khởi tạo Admin Service cho tìm kiếm dữ liệu công ty
        self.admin_service = AdminService()

        # Initialize Qdrant service for hybrid search / Khởi tạo Qdrant service cho hybrid search
        self.qdrant_service = get_qdrant_service()

        # ✅ STEP 3: Initialize ProductCatalogService for inventory data
        self.catalog_service = None  # Will be initialized async
        logger.info("🔄 ProductCatalogService will be initialized on first use")

        # Initialize MongoDB conversation manager / Khởi tạo MongoDB conversation manager
        try:
            from src.database.db_manager import DBManager
            from src.database.conversation_manager import ConversationManager

            self.db_manager = DBManager()
            # Increase token limit to ensure complete chat history display
            self.conversation_manager = ConversationManager(
                self.db_manager,
                max_token_limit=128000,  # Increased from 64K to 128K
                system_reserved_tokens=2000,  # Increased reserved tokens
            )
            logger.info(
                "✅ MongoDB conversation manager initialized with enhanced token limits"
            )
        except Exception as e:
            logger.warning(f"⚠️ MongoDB conversation manager failed to initialize: {e}")
            self.conversation_manager = None

        # Session storage (in production, use Redis/Database) / Lưu trữ phiên (production dùng Redis/Database)
        self.sessions = {}

        # Conversation tracking for webhooks / Theo dõi conversation cho webhooks
        self.conversations = {}

        # Information agent for RAG-based responses / Information agent cho phản hồi dựa trên RAG
        from src.services.information_agent import InformationAgent

        self.info_agent = InformationAgent()

        # Sales agent manager for industry-specific sales / Sales agent manager cho bán hàng chuyên biệt theo ngành
        from src.services.industry_sales_agents import SalesAgentManager

        self.sales_agent_manager = SalesAgentManager(self.ai_manager)

    async def _ensure_catalog_service(self):
        """✅ STEP 3: Ensure catalog service is initialized"""
        if self.catalog_service is None:
            try:
                self.catalog_service = await get_product_catalog_service()
                logger.info("✅ ProductCatalogService initialized successfully")
            except Exception as e:
                logger.error(f"❌ Failed to initialize ProductCatalogService: {e}")
                self.catalog_service = None

    def _get_webhook_channel_from_channel_type(self, channel) -> str:
        """
        Convert ChannelType to webhook channel name for Backend validation
        Chuyển đổi ChannelType thành tên kênh cho Backend validation
        Backend expects: [WEB, FACEBOOK, WHATSAPP, ZALO, INSTAGRAM, PLUGIN]
        """
        from src.models.unified_models import ChannelType

        channel_to_webhook = {
            ChannelType.CHATDEMO: "chatdemo",  # ✅ Exact value
            ChannelType.MESSENGER: "messenger",  # ✅ Exact value
            ChannelType.INSTAGRAM: "instagram",  # ✅ Exact value
            ChannelType.WHATSAPP: "whatsapp",  # ✅ Exact value
            ChannelType.ZALO: "zalo",  # ✅ Exact value
            ChannelType.CHAT_PLUGIN: "chat-plugin",  # ✅ Exact value
        }
        return channel_to_webhook.get(channel, "chatdemo")  # Default to chatdemo

    def _get_channel_from_source(self, source) -> str:
        """
        Convert UserSource to channel name for webhook (LEGACY SUPPORT)
        Chuyển đổi UserSource thành tên kênh cho webhook (HỖ TRỢ CŨ)
        """
        source_to_channel = {
            "chatdemo": "chatdemo",
            "messenger": "messenger",
            "whatsapp": "whatsapp",
            "zalo": "zalo",
            "instagram": "instagram",
            "chat_plugin": "chat-plugin",
        }
        return source_to_channel.get(
            source.value if hasattr(source, "value") else str(source),
            "chatdemo",  # Default to chatdemo
        )

    def _generate_conversation_id(
        self, company_id: str, device_id: str, plugin_id: str = None
    ) -> str:
        """
        Generate standardized conversation ID following format: conv_{companyId}_{deviceId}_{pluginId}
        Tạo conversation ID chuẩn theo format: conv_{companyId}_{deviceId}_{pluginId}
        IMPORTANT: Keep UUID format intact for compatibility with chat-plugin
        """
        # Keep company_id EXACTLY as is - NO CLEANING
        final_company_id = company_id if company_id else "unknown"

        # Keep device_id EXACTLY as is - NO CLEANING
        final_device_id = device_id if device_id else "unknown"

        # Keep plugin_id EXACTLY as is - NO CLEANING
        final_plugin_id = plugin_id if plugin_id else "default"

        conversation_id = f"conv_{final_company_id}_{final_device_id}_{final_plugin_id}"

        logger.info(f"🆔 Generated conversation ID: {conversation_id}")
        return conversation_id

    def get_or_create_conversation(
        self, session_id: str, company_id: str, device_id: str = None, request=None
    ) -> str:
        """
        Get existing conversation or create new one
        Supports device-based conversation tracking for anonymous users
        Lấy conversation hiện có hoặc tạo mới, hỗ trợ theo dõi conversation dựa trên device
        """
        # Use device_id for conversation key if available (for anonymous users)
        conversation_key = device_id if device_id else session_id

        if conversation_key not in self.conversations:
            # Get plugin_id from request
            plugin_id = getattr(request, "plugin_id", None) if request else None

            # Generate standardized conversation ID
            conversation_id = self._generate_conversation_id(
                company_id=company_id,
                device_id=device_id or session_id,
                plugin_id=plugin_id,
            )

            self.conversations[conversation_key] = {
                "conversation_id": conversation_id,
                "company_id": company_id,
                "session_id": session_id,
                "device_id": device_id,
                "created_at": datetime.now(),
                "message_count": 0,
                "last_activity": datetime.now(),
                "user_type": (
                    "anonymous"
                    if device_id and not session_id.startswith("firebase_")
                    else "authenticated"
                ),
            }
            logger.info(
                f"🆕 New conversation created: {conversation_id} (key: {conversation_key})"
            )

            return conversation_id
        else:
            # Update last activity
            self.conversations[conversation_key]["last_activity"] = datetime.now()
            return self.conversations[conversation_key]["conversation_id"]

    async def _send_conversation_created_webhook(
        self, company_id: str, conversation_id: str, session_id: str, request
    ):
        """Send conversation_created webhook with user info and detected intent"""
        try:
            # Extract user info for webhook
            user_info = webhook_service._extract_user_info_for_webhook(request)

            # ✨ Use channel first, fallback to source for legacy support
            channel = "chatdemo"  # Default to chatdemo instead of WEB
            if request.channel:
                # Prefer channel (new way)
                channel = self._get_webhook_channel_from_channel_type(request.channel)
            elif request.user_info and request.user_info.source:
                # Fallback to source (legacy support)
                channel = self._get_channel_from_source(request.user_info.source)

            # 🎯 Detect intent from first message before sending webhook
            detected_intent = "general_chat"  # Default fallback
            try:
                intent_result = await intent_detector.detect_intent(
                    message=request.message,
                    industry=request.industry,
                    company_id=company_id,
                    conversation_history=None,
                    context=request.context,
                )
                detected_intent = intent_result.intent.value
                logger.info(
                    f"🎯 Detected intent for conversation {conversation_id}: {detected_intent}"
                )
            except Exception as e:
                logger.warning(f"⚠️ Intent detection failed, using default: {e}")

            # Prepare context with plugin data for PLUGIN channel
            context_data = {}
            if request.channel == ChannelType.CHAT_PLUGIN:
                context_data = {
                    "plugin_id": request.plugin_id,
                    "customer_domain": request.customer_domain,
                }

            await webhook_service.notify_conversation_created(
                company_id=company_id,
                conversation_id=conversation_id,
                session_id=session_id,
                channel=channel,
                intent=detected_intent,  # Use detected intent instead of None
                metadata={},
                context=context_data,  # Pass plugin data via context
                user_info=user_info,
            )
            logger.info(
                f"🔔 Conversation created webhook sent for {conversation_id} with intent: {detected_intent}"
            )
        except Exception as e:
            logger.error(f"❌ Failed to send conversation created webhook: {e}")

    def is_new_conversation(self, session_id: str, device_id: str = None) -> bool:
        """Check if this is a new conversation"""
        conversation_key = device_id if device_id else session_id
        return (
            conversation_key not in self.conversations
            or self.conversations[conversation_key]["message_count"] == 0
        )

    def _extract_user_context(self, request: UnifiedChatRequest) -> Dict[str, Any]:
        """
        Extract comprehensive user context for AI prompt enhancement
        Trích xuất ngữ cảnh người dùng toàn diện để cải thiện AI prompt
        """
        context = {
            "user_id": request.user_info.user_id,
            "device_id": request.user_info.device_id,
            "source": request.user_info.source.value,
            "session_id": request.session_id,
        }

        # Add user profile if available
        if request.user_info.name:
            context["user_name"] = request.user_info.name
        if request.user_info.email:
            context["user_email"] = request.user_info.email

        # Add platform-specific data
        if request.user_info.platform_specific_data:
            platform_data = request.user_info.platform_specific_data
            context.update(
                {
                    "browser": getattr(platform_data, "browser", None),
                    "platform": getattr(platform_data, "platform", None),
                    "user_language": getattr(platform_data, "language", None),
                    "timezone": getattr(platform_data, "timezone", None),
                }
            )

        # Add context data
        if request.context:
            context_data = request.context
            context.update(
                {
                    "page_url": getattr(context_data, "page_url", None),
                    "referrer": getattr(context_data, "referrer", None),
                    "session_duration": getattr(context_data, "session_duration", None),
                    "previous_intent": getattr(context_data, "previous_intent", None),
                }
            )

        # Add metadata
        if request.metadata:
            metadata = request.metadata
            context.update(
                {
                    "app_source": getattr(metadata, "source", None),
                    "app_version": getattr(metadata, "version", None),
                    "request_id": getattr(metadata, "request_id", None),
                }
            )

        return context

    async def end_conversation(self, session_id: str, summary: str = None) -> bool:
        """
        End a conversation and notify backend
        Kết thúc conversation và thông báo backend
        """
        if session_id not in self.conversations:
            return False

        conversation = self.conversations[session_id]
        company_id = conversation["company_id"]
        conversation_id = conversation["conversation_id"]
        message_count = conversation["message_count"]

        # Notify conversation ended
        success = await webhook_service.notify_conversation_updated(
            company_id=company_id,
            conversation_id=conversation_id,
            status="COMPLETED",
            message_count=message_count,
            ended_at=datetime.now(),
            summary=summary or f"Conversation completed with {message_count} messages",
        )

        if success:
            # Remove from active conversations
            del self.conversations[session_id]
            logger.info(f"🏁 Conversation ended: {conversation_id}")

        return success

    def get_conversation_stats(self, session_id: str) -> Dict[str, Any]:
        """
        Get conversation statistics
        Lấy thống kê conversation
        """
        if session_id not in self.conversations:
            return {}

        conversation = self.conversations[session_id]
        duration = (datetime.now() - conversation["created_at"]).total_seconds()

        return {
            "conversation_id": conversation["conversation_id"],
            "company_id": conversation["company_id"],
            "message_count": conversation["message_count"],
            "duration_seconds": duration,
            "created_at": conversation["created_at"].isoformat(),
            "last_activity": conversation["last_activity"].isoformat(),
        }

    # Helper methods continue... / Các phương thức hỗ trợ tiếp tục...

    def _get_conversation_history(self, session_id: str) -> List[ConversationHistory]:
        """Get conversation history for session from MongoDB / Lấy lịch sử hội thoại cho phiên từ MongoDB"""
        if self.conversation_manager:
            try:
                # Use get_optimized_messages instead of get_messages / Sử dụng get_optimized_messages thay vì get_messages
                messages = self.conversation_manager.get_optimized_messages(
                    user_id=session_id, rag_context="", current_query=""
                )
                history = []
                for msg in messages:
                    history.append(
                        ConversationHistory(
                            role=msg.get("role", "user"),
                            content=msg.get("content", ""),
                            intent=None,  # Will be populated if available
                            language=None,  # Will be populated if available
                            timestamp=msg.get("timestamp", datetime.now()),
                        )
                    )
                if history:
                    print(
                        f"📚 [CHAT_HISTORY] Loaded {len(history)} messages from MongoDB for session: {session_id}"
                    )
                    return history
            except Exception as e:
                logger.warning(f"⚠️ Failed to load history from MongoDB: {e}")

        # Fallback to in-memory / Fallback về memory
        return self.sessions.get(session_id, {}).get("history", [])

    def _get_session_data(self, session_id: str) -> Dict[str, Any]:
        """Get session data / Lấy dữ liệu phiên"""
        return self.sessions.get(session_id, {}).get("data", {})

    def _update_session_data(self, session_id: str, data: Dict[str, Any]):
        """Update session data / Cập nhật dữ liệu phiên"""
        if session_id not in self.sessions:
            self.sessions[session_id] = {"history": [], "data": {}}
        self.sessions[session_id]["data"].update(data)

    def _build_conversation_context(self, history: List[ConversationHistory]) -> str:
        """Build conversation context string / Xây dựng chuỗi ngữ cảnh hội thoại"""
        if not history:
            return ""

        context_lines = []
        for msg in history[-5:]:  # Last 5 messages
            role = "User" if msg.role == "user" else "AI"
            context_lines.append(f"{role}: {msg.content}")

        return "\n".join(context_lines)

    def _generate_suggestions(
        self, intent_result, industry: Industry, language: Language
    ) -> List[str]:
        """Generate follow-up suggestions / Tạo gợi ý theo dõi"""
        suggestions = []

        if language == Language.VIETNAMESE:
            if intent_result.intent == ChatIntent.INFORMATION:
                if industry == Industry.BANKING:
                    suggestions = [
                        "Tìm hiểu về lãi suất vay",
                        "Điều kiện vay vốn",
                        "Các sản phẩm cho vay",
                    ]
                elif industry == Industry.RESTAURANT:
                    suggestions = ["Xem thực đơn", "Đặt bàn", "Dịch vụ giao hàng"]
            elif intent_result.intent == ChatIntent.SALES_INQUIRY:
                suggestions = [
                    "Tôi cần hỗ trợ gì thêm?",
                    "Thông tin chi tiết sản phẩm",
                    "Liên hệ tư vấn trực tiếp",
                ]
        else:
            if intent_result.intent == ChatIntent.INFORMATION:
                if industry == Industry.BANKING:
                    suggestions = [
                        "Learn about interest rates",
                        "Loan requirements",
                        "Available loan products",
                    ]
                elif industry == Industry.RESTAURANT:
                    suggestions = ["View menu", "Make reservation", "Delivery options"]
            elif intent_result.intent == ChatIntent.SALES_INQUIRY:
                suggestions = [
                    "What else can I help with?",
                    "Product details",
                    "Contact advisor",
                ]

        return suggestions

    def _get_error_message(self, language: Language) -> str:
        """Get error message in appropriate language / Lấy thông báo lỗi bằng ngôn ngữ phù hợp"""
        if language == Language.VIETNAMESE:
            return "Xin lỗi, tôi gặp sự cố kỹ thuật. Vui lòng thử lại sau ít phút."
        else:
            return "Sorry, I'm experiencing technical difficulties. Please try again in a few minutes."

    # Streaming methods will be implemented next... / Các phương thức streaming sẽ được triển khai tiếp theo...

    async def _hybrid_search_company_data(
        self,
        company_id: str,
        query: str,
        limit: int = 3,
        score_threshold: float = 0.2,  # Lowered default threshold for better results
        industry: Industry = Industry.OTHER,
        data_types: Optional[List] = None,
    ) -> List[Dict[str, Any]]:
        """
        UPDATED: Use comprehensive hybrid search from QdrantCompanyDataService
        SỬ DỤNG: Tìm kiếm hybrid toàn diện từ QdrantCompanyDataService
        """
        try:
            logger.info(
                f"🔍 Using comprehensive hybrid search for company {company_id}: {query[:50]}..."
            )

            # Convert legacy data_types format if needed
            qdrant_data_types = None
            if data_types:
                from src.models.unified_models import IndustryDataType

                qdrant_data_types = []
                for dt in data_types:
                    if isinstance(dt, str):
                        try:
                            qdrant_data_types.append(IndustryDataType(dt))
                        except ValueError:
                            logger.warning(f"Unknown data type: {dt}")
                    elif hasattr(dt, "value"):
                        qdrant_data_types.append(dt)

            # Use comprehensive hybrid search from Qdrant service with provided threshold
            logger.info(f"🔍 [DEBUG] Using score_threshold: {score_threshold}")
            search_results = await self.qdrant_service.comprehensive_hybrid_search(
                company_id=company_id,
                query=query,
                industry=industry,
                data_types=qdrant_data_types,
                score_threshold=score_threshold,  # Use the provided parameter!
                max_chunks=limit * 3,  # Get more chunks for better context
            )

            # Format results to match expected format
            formatted_results = []
            for result in search_results:
                formatted_result = {
                    "chunk_id": result.get("chunk_id", ""),
                    "score": result.get("score", 0.0),
                    "content_for_rag": result.get("content_for_rag", ""),
                    "data_type": result.get("data_type", ""),
                    "content_type": result.get("content_type", ""),
                    "structured_data": result.get("structured_data", {}),
                    "file_id": result.get("file_id", ""),
                    "language": result.get("language", ""),
                    "created_at": result.get("created_at", ""),
                    "search_source": result.get("search_source", "comprehensive"),
                    "original_score": result.get(
                        "original_score", result.get("score", 0.0)
                    ),
                }
                formatted_results.append(formatted_result)

            # Limit final results
            final_results = formatted_results[:limit]

            logger.info(
                f"🎯 Comprehensive hybrid search returned {len(final_results)} chunks"
            )
            for i, result in enumerate(final_results, 1):
                logger.info(
                    f"   {i}. {result['content_type']} (score: {result['score']:.3f}, "
                    f"source: {result['search_source']})"
                )

            return final_results

        except Exception as e:
            logger.error(f"❌ Comprehensive hybrid search failed: {e}")
            logger.error(f"❌ Exception type: {type(e)}")
            logger.error(f"❌ Exception details: {str(e)}")

            # Fallback to basic admin service search
            try:
                logger.info(f"🔄 Falling back to admin_service search...")
                fallback_result = await self.admin_service.search_company_data(
                    company_id=company_id,
                    query=query,
                    data_types=data_types,
                    limit=limit,
                    score_threshold=score_threshold,
                )
                logger.info(
                    f"🔄 Admin service fallback returned {len(fallback_result) if fallback_result else 0} results"
                )
                return fallback_result
            except Exception as fallback_error:
                logger.error(f"❌ Admin service fallback also failed: {fallback_error}")
                return []

    async def stream_response_optimized(
        self, request: UnifiedChatRequest
    ) -> StreamingResponse:
        """
        ✅ FRONTEND OPTIMIZED: 7-step streamlined chat processing with channel routing
        Xử lý chat tối ưu hóa theo 7 bước với routing theo kênh
        """
        # Track processing start time for metrics
        processing_start_time = time.time()

        try:
            company_id = getattr(request, "company_id", "unknown")
            device_id = request.user_info.device_id if request.user_info else "unknown"
            user_query = request.message

            # NEW: Extract channel for routing logic
            channel = request.channel or ChannelType.CHATDEMO

            logger.info(
                f"🚀 [FRONTEND_OPTIMIZED] Starting optimized stream for company {company_id}, device {device_id}"
            )
            logger.info(f"📡 [CHANNEL_ROUTING] Channel: {channel.value}")

            # Extract user information for optimization
            user_id = request.user_info.user_id if request.user_info else None
            user_name = request.user_info.name if request.user_info else None
            session_id = request.session_id

            # NEW: Log lead source if provided
            if request.lead_source:
                logger.info(
                    f"📊 [LEAD_SOURCE] {request.lead_source.sourceCode} - {request.lead_source.name}"
                )

            logger.info(
                f"🚀 [FRONTEND_OPTIMIZED] User info - user_id: {user_id}, name: {user_name}"
            )

            # Steps 1, 2, 3, 4: Parallel data fetching with user name support and products list
            # Bước 1, 2, 3, 4: Thu thập dữ liệu song song với hỗ trợ tên người dùng và danh sách sản phẩm
            company_data, user_context, company_context, products_list = (
                await asyncio.gather(
                    self._hybrid_search_company_data_optimized(company_id, user_query),
                    self._get_user_context_optimized(
                        device_id, session_id, user_id, user_name
                    ),
                    self._get_company_context_optimized(company_id),
                    self._get_products_list_for_prompt(company_id, user_query),
                    return_exceptions=True,
                )
            )

            # Handle exceptions from parallel tasks
            if isinstance(company_data, Exception):
                logger.warning(f"⚠️ Company data search failed: {company_data}")
                company_data = "No relevant company data found."

            if isinstance(user_context, Exception):
                logger.warning(f"⚠️ User context retrieval failed: {user_context}")
                user_context = "New user - no previous conversation history."

            if isinstance(company_context, Exception):
                logger.warning(f"⚠️ Company context retrieval failed: {company_context}")
                company_context = "No company context available."

            if isinstance(products_list, Exception):
                logger.warning(f"⚠️ Products list retrieval failed: {products_list}")
                products_list = "No products data available."

            # Step 4: Build unified prompt with intent detection and user name support
            # Bước 4: Xây dựng prompt thông minh với hỗ trợ tên người dùng

            # Get company name directly from MongoDB instead of parsing text
            company_name = self._get_company_name_from_db(company_id)

            unified_prompt = self._build_unified_prompt_with_intent(
                user_context=user_context,
                company_data=company_data,
                company_context=company_context,
                products_list=products_list,
                user_query=user_query,
                industry=request.industry.value if request.industry else "general",
                company_id=company_id,
                session_id=request.session_id or "unknown",
                user_name=user_name,
                company_name=company_name,
            )

            logger.info(f"📝 Unified prompt built: {len(unified_prompt)} characters")

            # Step 5: Send to AI Provider with channel-specific routing
            # Bước 5: Gửi yêu cầu đến AI Provider với routing theo kênh
            full_ai_response = ""  # Collect full response for saving
            webhook_response_data = None  # Store webhook response for final message

            async def generate_response():
                nonlocal full_ai_response, webhook_response_data
                try:
                    # CRITICAL: Channel-based response routing
                    # QUAN TRỌNG: Routing response theo channel

                    if channel in [ChannelType.CHATDEMO, ChannelType.CHAT_PLUGIN]:
                        # FRONTEND CHANNELS: Stream directly to frontend + send callback to backend
                        # CÁC KÊNH FRONTEND: Stream trực tiếp về frontend + gửi callback về backend
                        logger.info(
                            f"📡 [CHANNEL_ROUTING] ✅ FRONTEND channel detected: {channel.value} - streaming to frontend"
                        )

                        async for chunk in self.ai_manager.stream_response(
                            question=unified_prompt,
                            user_id=(
                                request.user_info.user_id if request.user_info else None
                            ),
                            provider="cerebras",  # Default provider
                        ):
                            if chunk.strip():
                                # Accumulate full response for database saving
                                full_ai_response += chunk

                                # Frontend will parse the full JSON response to extract final_answer
                                # AI Service just streams the raw chunks and sends complete JSON at end
                                # Frontend tự parse JSON để extract final_answer, AI Service chỉ stream raw chunks
                                yield f"data: {json.dumps({'chunk': chunk, 'type': 'content'})}\n\n"

                        # Parse final response and send structured data
                        parsed_ai_response = self._parse_ai_json_response(
                            full_ai_response
                        )

                        # 🔄 CHECK: If we have webhook response, use it to override final_answer
                        # 🔄 KIỂM TRA: Nếu có webhook response, sử dụng nó để thay thế final_answer
                        if webhook_response_data and webhook_response_data.get(
                            "user_message"
                        ):
                            logger.info(
                                "🎯 [WEBHOOK_OVERRIDE] Using webhook response as final answer"
                            )
                            parsed_ai_response["final_answer"] = webhook_response_data[
                                "user_message"
                            ]
                            # Also update the original response for database saving
                            full_ai_response = json.dumps(
                                {
                                    **parsed_ai_response,
                                    "webhook_data": webhook_response_data,
                                    "original_ai_response": full_ai_response,
                                }
                            )

                        # Send completion with structured data
                        completion_data = {
                            "type": "done",
                            "structured_response": parsed_ai_response,
                        }
                        yield f"data: {json.dumps(completion_data)}\n\n"

                        # ✨ NEW: Send callback to backend for both chatdemo and chat-plugin
                        # ✨ MỚI: Gửi callback về backend cho cả chatdemo và chat-plugin
                        if channel in [ChannelType.CHATDEMO, ChannelType.CHAT_PLUGIN]:
                            logger.info(
                                f"📤 [CHANNEL_ROUTING] Sending callback to backend for {channel.value}"
                            )
                            # Send structured response to backend as callback
                            await self._send_response_to_backend(
                                request=request,
                                ai_response=full_ai_response,
                                parsed_response=parsed_ai_response,
                                channel=channel,
                                processing_start_time=processing_start_time,
                            )

                    else:
                        # BACKEND CHANNELS: Collect full response and send to backend (messenger, instagram, whatsapp, zalo)
                        # CÁC KÊNH BACKEND: Thu thập full response và gửi về backend
                        logger.info(
                            f"📡 [CHANNEL_ROUTING] ✅ BACKEND channel detected: {channel.value}"
                        )
                        logger.info(
                            "📡 [CHANNEL_ROUTING] Collecting full response for backend processing"
                        )

                        # Collect full AI response without streaming to requester
                        async for chunk in self.ai_manager.stream_response(
                            question=unified_prompt,
                            user_id=(
                                request.user_info.user_id if request.user_info else None
                            ),
                            provider="cerebras",
                        ):
                            if chunk.strip():
                                full_ai_response += chunk

                        # Parse the full JSON response
                        parsed_ai_response = self._parse_ai_json_response(
                            full_ai_response
                        )

                        # 🔍 DEBUG: Log raw AI response for analysis
                        logger.info(
                            f"🔍 [AI_RESPONSE_DEBUG] Raw AI response length: {len(full_ai_response)} chars"
                        )
                        logger.info(
                            f"🔍 [AI_RESPONSE_DEBUG] Raw AI response preview: {full_ai_response[:500]}..."
                        )
                        if "webhook_data" in full_ai_response:
                            logger.info(
                                f"🔍 [AI_RESPONSE_DEBUG] Raw response contains 'webhook_data'"
                            )
                        else:
                            logger.info(
                                f"🔍 [AI_RESPONSE_DEBUG] Raw response MISSING 'webhook_data'"
                            )

                        # 🔍 DEBUG: Log parsed structure
                        logger.info(
                            f"🔍 [AI_RESPONSE_DEBUG] Parsed response keys: {list(parsed_ai_response.keys())}"
                        )
                        if "webhook_data" in parsed_ai_response:
                            webhook_data = parsed_ai_response["webhook_data"]
                            logger.info(
                                f"🔍 [AI_RESPONSE_DEBUG] webhook_data keys: {list(webhook_data.keys())}"
                            )
                        else:
                            logger.info(
                                f"🔍 [AI_RESPONSE_DEBUG] Parsed response MISSING 'webhook_data'"
                            )

                        # 🔄 CHECK: If we have webhook response, use it to override final_answer
                        # 🔄 KIỂM TRA: Nếu có webhook response, sử dụng nó để thay thế final_answer
                        if webhook_response_data and webhook_response_data.get(
                            "user_message"
                        ):
                            logger.info(
                                "🎯 [WEBHOOK_OVERRIDE] Using webhook response as final answer for backend"
                            )
                            parsed_ai_response["final_answer"] = webhook_response_data[
                                "user_message"
                            ]
                            # Also update the original response for database saving
                            full_ai_response = json.dumps(
                                {
                                    **parsed_ai_response,
                                    "webhook_data": webhook_response_data,
                                    "original_ai_response": full_ai_response,
                                }
                            )

                        # Send structured response to backend for channel processing
                        await self._send_response_to_backend(
                            request=request,
                            ai_response=full_ai_response,
                            parsed_response=parsed_ai_response,
                            channel=channel,
                            processing_start_time=processing_start_time,
                        )

                        # Return success signal to backend caller with structured data
                        success_response = {
                            "type": "backend_processed",
                            "channel": channel.value,
                            "success": True,
                            "structured_response": parsed_ai_response,
                        }
                        yield f"data: {json.dumps(success_response)}\n\n"

                    # Save conversation to database after processing - CRITICAL for user_context
                    logger.info(
                        f"💾 [STREAM_COMPLETE] Full AI response collected: {len(full_ai_response)} chars"
                    )
                    logger.info(
                        f"💾 [STREAM_COMPLETE] Saving conversation for future user_context retrieval"
                    )

                    # Use await instead of create_task to ensure conversation is saved
                    # Sử dụng await thay vì create_task để đảm bảo conversation được lưu
                    await self._save_complete_conversation_async(
                        request=request,
                        company_id=company_id,
                        user_query=user_query,
                        ai_response=full_ai_response,
                    )

                    logger.info(
                        f"✅ [STREAM_COMPLETE] Conversation saved successfully for user_context"
                    )

                except Exception as e:
                    logger.error(f"❌ [STREAM_ERROR] Error in generate_response: {e}")
                    yield f"data: {json.dumps({'chunk': f'Error: {str(e)}', 'type': 'error'})}\n\n"

            # Step 6: Create streaming response
            # Bước 6: Stream dữ liệu về caller (frontend hoặc backend)
            response = StreamingResponse(
                generate_response(),
                media_type="text/plain",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                    "X-Channel-Type": channel.value,  # NEW: Include channel in response headers
                },
            )

            return response

        except Exception as e:
            logger.error(f"❌ Optimized stream failed: {e}")
            raise

    async def _send_response_to_backend(
        self,
        request: UnifiedChatRequest,
        ai_response: str,
        channel: ChannelType,
        parsed_response: Dict[str, Any] = None,
        processing_start_time: float = None,
    ):
        """
        Send AI response to backend for channel-specific processing
        Gửi AI response về backend để xử lý theo kênh cụ thể
        """
        try:
            logger.info(
                f"📤 [BACKEND_ROUTING] Sending response to backend for channel: {channel.value}"
            )

            # Here you would implement the actual backend communication
            # Ở đây bạn sẽ implement giao tiếp thực tế với backend

            # This could be:
            # 1. HTTP POST to backend endpoint
            # 2. Message queue (Redis/RabbitMQ)
            # 3. WebSocket to backend
            # 4. Direct function call if backend and AI service are in same codebase

            # Use parsed response if provided, otherwise parse from raw response
            if parsed_response is None:
                parsed_response = self._parse_ai_json_response(ai_response)

            logger.info(
                f"🧠 [BACKEND_ROUTING] Using parsed response - Intent: {parsed_response.get('intent', 'unknown')}"
            )
            logger.info(
                f"🎯 [BACKEND_ROUTING] Language: {parsed_response.get('language', 'unknown')}"
            )
            logger.info(
                f"📝 [BACKEND_ROUTING] Final answer length: {len(parsed_response.get('final_answer', ''))}"
            )

            # Calculate actual processing time
            processing_time_ms = 0
            if processing_start_time:
                processing_time_ms = int((time.time() - processing_start_time) * 1000)

            # Get actual token usage from AI response metadata if available
            # Calculate token usage based on word count (approximate)
            prompt_tokens = len(request.message.split()) if request.message else 0
            completion_tokens = len(ai_response.split()) if ai_response else 0

            token_usage = {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            }

            # Try to extract token usage from parsed response metadata (if AI provides it)
            if parsed_response and "metadata" in parsed_response:
                metadata = parsed_response["metadata"]
                if "token_usage" in metadata:
                    # Use AI provider's actual token count if available
                    provider_tokens = metadata["token_usage"]
                    if provider_tokens.get("total_tokens", 0) > 0:
                        token_usage = provider_tokens

            # Log actual metrics for monitoring
            logger.info(f"📊 [METRICS] Processing time: {processing_time_ms}ms")
            logger.info(f"📊 [METRICS] Token usage: {token_usage}")

            # 🛒 NEW: Check intent types and handle accordingly
            detected_intent = parsed_response.get("thinking", {}).get(
                "intent", "unknown"
            )
            logger.info(f"🎯 [INTENT_CHECK] Detected intent: {detected_intent}")

            # PLACE_ORDER intent handling (updated to use complete flag)
            if detected_intent == "PLACE_ORDER":
                logger.info(
                    "🔍 [PLACE_ORDER_CHECK] PLACE_ORDER intent detected, checking if ready for webhook..."
                )
                is_order_ready = self._is_order_ready_for_webhook(parsed_response)
                logger.info(
                    f"🔍 [PLACE_ORDER_CHECK] Order webhook ready: {is_order_ready}"
                )
                is_order_completion = is_order_ready
            else:
                is_order_completion = False

            # UPDATE_ORDER intent handling (new)
            is_update_order = detected_intent == "UPDATE_ORDER"

            # CHECK_QUANTITY intent handling (new) - CHỈ gửi webhook khi có đủ thông tin liên hệ
            is_check_quantity = (
                detected_intent == "CHECK_QUANTITY"
                and self._is_check_quantity_webhook_ready(
                    parsed_response, request.message
                )
            )

            # Log detected intents
            if is_order_completion:
                logger.info(
                    "🛒 [ORDER_DETECTION] Order completion detected, will send order.created webhook"
                )
            elif is_update_order:
                logger.info(
                    "🔄 [UPDATE_ORDER_DETECTION] Update order intent detected, will send update webhook"
                )
            elif is_check_quantity:
                logger.info(
                    "📊 [CHECK_QUANTITY_DETECTION] Check quantity intent detected, will send quantity check webhook"
                )

            # Build payload theo documentation schema với chat-plugin support
            if channel in [ChannelType.CHATDEMO, ChannelType.CHAT_PLUGIN]:
                # Frontend channels callback with full JSON structure
                # Different event types for different frontend channels
                event_type = (
                    "ai.response.plugin.completed"  # Unified event for frontend
                )

                # 🔍 DEBUG: Check AI response parsing for frontend
                response_content = parsed_response.get("final_answer", "")
                logger.info(
                    f"🔍 [FRONTEND_WEBHOOK] Response content length: {len(response_content)}"
                )
                logger.info(
                    f"🔍 [FRONTEND_WEBHOOK] Response preview: {response_content[:100]}..."
                )
                logger.info(
                    f"🔍 [FRONTEND_WEBHOOK] Parsed keys: {list(parsed_response.keys())}"
                )

                # Extract user info from frontend request
                user_info_data = None
                if request.user_info:
                    user_info_data = {
                        "user_id": request.user_info.user_id,
                        "device_id": request.user_info.device_id,
                        "source": (
                            request.user_info.source.value
                            if hasattr(request.user_info.source, "value")
                            else str(request.user_info.source)
                        ),
                        "name": request.user_info.name,
                        "email": request.user_info.email,
                    }
                    # Filter out None values
                    user_info_data = {
                        k: v for k, v in user_info_data.items() if v is not None
                    }

                # Extract thinking details from AI response
                thinking_data = parsed_response.get("thinking", {})
                if isinstance(thinking_data, dict):
                    thinking_extracted = {
                        "intent": thinking_data.get("intent", "unknown"),
                        "persona": thinking_data.get("persona", "unknown"),
                        "reasoning": thinking_data.get("reasoning", ""),
                    }
                else:
                    thinking_extracted = {
                        "intent": "unknown",
                        "persona": "unknown",
                        "reasoning": str(thinking_data) if thinking_data else "",
                    }

                webhook_data = {
                    "messageId": request.message_id,
                    "conversationId": getattr(
                        request, "conversation_id", request.session_id
                    ),
                    "processingTime": processing_time_ms / 1000,  # Convert to seconds
                    "channel": channel.value,
                    "userInfo": user_info_data,  # ✅ Added user info from frontend
                    "thinking": thinking_extracted,  # ✅ Added thinking details from AI
                    # 🆕 STRUCTURED: User message and AI response for full conversation context
                    "userMessage": {
                        "content": request.message,
                        "messageId": request.message_id,
                        "timestamp": datetime.now().isoformat(),
                    },
                    "aiResponse": {
                        "content": parsed_response.get("final_answer", ai_response),
                        "messageId": f"{request.message_id}_ai",
                        "timestamp": datetime.now().isoformat(),
                    },
                    "metadata": {
                        "streaming": True,
                        "language": parsed_response.get("language", "VIETNAMESE"),
                        "ai_provider": "cerebras",
                        "model": "qwen-3-235b-a22b-instruct-2507",
                        "token_usage": token_usage,
                    },
                }

                # Add plugin-specific fields for chat-plugin channel
                if channel == ChannelType.CHAT_PLUGIN:
                    webhook_data["pluginId"] = request.plugin_id
                    webhook_data["customerDomain"] = request.customer_domain

                backend_payload = {
                    "event": event_type,
                    "companyId": request.company_id,
                    "timestamp": datetime.now().isoformat(),
                    "data": webhook_data,
                    "metadata": {},
                }
            else:
                # Backend channels (messenger, instagram, whatsapp, zalo)

                # Extract user info from frontend request for backend channels too
                user_info_data = None
                if request.user_info:
                    user_info_data = {
                        "user_id": request.user_info.user_id,
                        "device_id": request.user_info.device_id,
                        "source": (
                            request.user_info.source.value
                            if hasattr(request.user_info.source, "value")
                            else str(request.user_info.source)
                        ),
                        "name": request.user_info.name,
                        "email": request.user_info.email,
                    }
                    # Filter out None values
                    user_info_data = {
                        k: v for k, v in user_info_data.items() if v is not None
                    }

                # Extract thinking details from AI response
                thinking_data = parsed_response.get("thinking", {})
                if isinstance(thinking_data, dict):
                    thinking_extracted = {
                        "intent": thinking_data.get("intent", "unknown"),
                        "persona": thinking_data.get("persona", "unknown"),
                        "reasoning": thinking_data.get("reasoning", ""),
                    }
                else:
                    thinking_extracted = {
                        "intent": "unknown",
                        "persona": "unknown",
                        "reasoning": str(thinking_data) if thinking_data else "",
                    }

                webhook_data = {
                    "messageId": request.message_id,
                    "conversationId": getattr(
                        request, "conversation_id", request.session_id
                    ),
                    "response": parsed_response.get("final_answer", ""),
                    "processingTime": processing_time_ms / 1000,  # Convert to seconds
                    "channel": channel.value,
                    "userInfo": user_info_data,  # ✅ Added user info from frontend
                    "thinking": thinking_extracted,  # ✅ Added thinking details from AI
                    "metadata": {
                        "language": parsed_response.get("language", "VIETNAMESE"),
                        "ai_provider": "cerebras",
                        "model": "qwen-3-235b-a22b-instruct-2507",
                        "token_usage": token_usage,
                    },
                }

                # ✅ Add plugin-specific fields for chat-plugin channel (backend processing too)
                if channel == ChannelType.CHAT_PLUGIN:
                    webhook_data["pluginId"] = request.plugin_id
                    webhook_data["customerDomain"] = request.customer_domain

                backend_payload = {
                    "event": "ai.response.completed",
                    "companyId": request.company_id,
                    "timestamp": datetime.now().isoformat(),
                    "data": webhook_data,
                    "metadata": {},
                }

            # Send webhook to backend với updated schema
            import httpx
            import os

            backend_url = os.getenv("BACKEND_WEBHOOK_URL", "http://localhost:8001")
            endpoint = f"{backend_url}/api/webhooks/ai/conversation"  # Updated endpoint

            # Simple webhook secret as header (from .env)
            webhook_secret = os.getenv("WEBHOOK_SECRET", "webhook-secret-for-signature")

            headers = {
                "Content-Type": "application/json",
                "X-Webhook-Source": "ai-service",
                "X-Webhook-Secret": webhook_secret,
                "User-Agent": "Agent8x-AI-Service/1.0",
            }

            # 🔍 Log full webhook payload for debugging
            logger.info(f"🔍 [WEBHOOK_PAYLOAD] Sending to backend: {endpoint}")
            logger.info(f"🔍 [WEBHOOK_PAYLOAD] Event: {backend_payload['event']}")
            logger.info(f"🔍 [WEBHOOK_PAYLOAD] Company: {backend_payload['companyId']}")
            logger.info(
                f"🔍 [WEBHOOK_PAYLOAD] Data keys: {list(backend_payload['data'].keys())}"
            )

            # Log userMessage and aiResponse specifically
            if "userMessage" in backend_payload["data"]:
                user_msg = backend_payload["data"]["userMessage"]
                logger.info(
                    f"🔍 [WEBHOOK_PAYLOAD] userMessage.content: '{user_msg.get('content', 'MISSING')[:100]}...'"
                )
                logger.info(
                    f"🔍 [WEBHOOK_PAYLOAD] userMessage.messageId: {user_msg.get('messageId', 'MISSING')}"
                )
            else:
                logger.error(f"❌ [WEBHOOK_PAYLOAD] userMessage field is MISSING!")

            if "aiResponse" in backend_payload["data"]:
                ai_msg = backend_payload["data"]["aiResponse"]
                logger.info(
                    f"🔍 [WEBHOOK_PAYLOAD] aiResponse.content: '{ai_msg.get('content', 'MISSING')[:100]}...'"
                )
                logger.info(
                    f"🔍 [WEBHOOK_PAYLOAD] aiResponse.messageId: {ai_msg.get('messageId', 'MISSING')}"
                )
            else:
                logger.error(f"❌ [WEBHOOK_PAYLOAD] aiResponse field is MISSING!")

            # 📄 Save full payload to file for debugging
            import json
            import os

            # Create debug directory if it doesn't exist
            debug_dir = "debug_webhook_payloads"
            os.makedirs(debug_dir, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            payload_filename = f"webhook_payload_{request.company_id}_{request.session_id}_{timestamp}.json"
            full_path = os.path.join(debug_dir, payload_filename)

            try:
                with open(full_path, "w", encoding="utf-8") as f:
                    json.dump(backend_payload, f, indent=2, ensure_ascii=False)
                logger.info(f"📄 [WEBHOOK_PAYLOAD] Full payload saved to: {full_path}")
            except Exception as e:
                logger.error(f"❌ [WEBHOOK_PAYLOAD] Failed to save payload file: {e}")

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    endpoint,
                    json=backend_payload,
                    headers=headers,
                    timeout=30.0,
                )

                if response.status_code == 200:
                    logger.info(
                        f"✅ [BACKEND_ROUTING] Successfully sent to backend for {channel.value}"
                    )

                    # 🛒 DUAL WEBHOOK: Send order creation webhook if this is a completed order
                    if is_order_completion:
                        logger.info(
                            "🛒 [DUAL_WEBHOOK] Sending order creation webhook after conversation webhook success"
                        )

                        # Try to get order data directly from AI response webhook_data first
                        order_data = None
                        if parsed_response.get("webhook_data", {}).get("order_data"):
                            order_data = parsed_response["webhook_data"]["order_data"]
                            logger.info(
                                "✅ [DUAL_WEBHOOK] Using webhook_data from AI response"
                            )
                        else:
                            # Fallback: Extract order data using secondary AI call
                            logger.info(
                                "⚠️ [DUAL_WEBHOOK] No webhook_data, falling back to extraction"
                            )
                            order_data = await self._extract_order_data_from_response(
                                parsed_response, request.message
                            )

                        if order_data:
                            order_webhook_success = (
                                await self._send_order_created_webhook(
                                    request=request,
                                    order_data=order_data,
                                    processing_start_time=processing_start_time,
                                )
                            )

                            if order_webhook_success:
                                logger.info(
                                    "✅ [DUAL_WEBHOOK] Order creation webhook sent successfully"
                                )
                            else:
                                logger.error(
                                    "❌ [DUAL_WEBHOOK] Failed to send order creation webhook"
                                )
                        else:
                            logger.error(
                                "❌ [DUAL_WEBHOOK] Could not extract order data from AI response"
                            )

                    # 🔄 UPDATE_ORDER WEBHOOK: Handle order update requests
                    elif is_update_order:
                        logger.info(
                            "🔄 [UPDATE_ORDER_WEBHOOK] Sending order update webhook after conversation webhook success"
                        )

                        # Try to get update data directly from AI response webhook_data first
                        update_data = None
                        if parsed_response.get("webhook_data", {}).get("update_data"):
                            update_data = parsed_response["webhook_data"]["update_data"]
                            logger.info(
                                "✅ [UPDATE_ORDER_WEBHOOK] Using webhook_data from AI response"
                            )
                            logger.info(
                                f"🔄 [UPDATE_ORDER_WEBHOOK] Complete flag: {update_data.get('complete', False)}"
                            )
                        else:
                            # Fallback: Extract update data using secondary AI call
                            logger.info(
                                "⚠️ [UPDATE_ORDER_WEBHOOK] No webhook_data, falling back to extraction"
                            )
                            update_data = await self._extract_update_order_data(
                                parsed_response, request.message
                            )

                        # Validate update data has complete flag and valid order code
                        if (
                            update_data
                            and update_data.get("complete", False) == True
                            and update_data.get("order_code")
                            and update_data.get("order_code") != "UNKNOWN"
                        ):

                            logger.info(
                                f"✅ [UPDATE_ORDER_WEBHOOK] Valid update data - Order: {update_data.get('order_code')}"
                            )
                            webhook_response_data = (
                                await self._handle_update_order_webhook(
                                    request=request,
                                    update_data=update_data,
                                    processing_start_time=processing_start_time,
                                )
                            )
                            logger.info(
                                f"🔄 [UPDATE_ORDER_WEBHOOK] Webhook response received: {webhook_response_data.get('success', False)}"
                            )
                        else:
                            logger.error(
                                f"❌ [UPDATE_ORDER_WEBHOOK] Invalid update data - Complete: {update_data.get('complete', False) if update_data else 'No data'}, Order Code: {update_data.get('order_code', 'Missing') if update_data else 'No data'}"
                            )

                    # 📊 CHECK_QUANTITY WEBHOOK: Handle quantity check requests
                    elif is_check_quantity:
                        logger.info(
                            "📊 [CHECK_QUANTITY_WEBHOOK] Sending quantity check webhook after conversation webhook success"
                        )

                        # Try to get quantity data directly from AI response webhook_data first
                        quantity_data = None
                        if parsed_response.get("webhook_data", {}).get(
                            "check_quantity_data"
                        ):
                            quantity_data = parsed_response["webhook_data"][
                                "check_quantity_data"
                            ]
                            logger.info(
                                "✅ [CHECK_QUANTITY_WEBHOOK] Using webhook_data from AI response"
                            )
                        else:
                            # Fallback: Extract quantity data using secondary AI call
                            logger.info(
                                "⚠️ [CHECK_QUANTITY_WEBHOOK] No webhook_data, falling back to extraction"
                            )
                            quantity_data = await self._extract_check_quantity_data(
                                parsed_response, request.message
                            )

                        if quantity_data:
                            webhook_response_data = (
                                await self._handle_check_quantity_webhook(
                                    request=request,
                                    quantity_data=quantity_data,
                                    processing_start_time=processing_start_time,
                                )
                            )
                            logger.info(
                                f"📊 [CHECK_QUANTITY_WEBHOOK] Webhook response received: {webhook_response_data.get('success', False)}"
                            )
                        else:
                            logger.error(
                                "❌ [CHECK_QUANTITY_WEBHOOK] Could not extract quantity check data"
                            )

                    # 🎯 Update conversation intent from AI response after successful webhook
                    try:
                        intent_updated = await webhook_service.update_conversation_intent_from_ai_response(
                            company_id=request.company_id,
                            conversation_id=getattr(
                                request, "conversation_id", request.session_id
                            ),
                            full_ai_response=ai_response,
                        )
                        if intent_updated:
                            logger.info(
                                f"✅ Intent updated from AI response for conversation"
                            )
                        else:
                            logger.warning(
                                f"⚠️ Could not update intent from AI response"
                            )
                    except Exception as intent_error:
                        logger.error(
                            f"❌ Error updating intent from AI response: {intent_error}"
                        )

                else:
                    logger.error(
                        f"❌ [BACKEND_ROUTING] Backend returned {response.status_code}: {response.text}"
                    )

        except Exception as e:
            logger.error(f"❌ [BACKEND_ROUTING] Failed to send to backend: {e}")
            # Don't raise exception - this shouldn't break the main flow
            # Không raise exception - điều này không nên phá vỡ luồng chính

    def _is_check_quantity_webhook_ready(
        self, parsed_response: Dict[str, Any], user_message: str
    ) -> bool:
        """
        Check if CHECK_QUANTITY intent should trigger webhook
        Chỉ gửi webhook khi khách hàng đã cung cấp thông tin liên hệ và xác nhận gửi yêu cầu
        """
        try:
            # 1. Kiểm tra xem có webhook_data trong AI response không
            webhook_data = parsed_response.get("webhook_data", {}).get(
                "check_quantity_data"
            )
            if not webhook_data:
                logger.info(
                    "📊 [CHECK_QUANTITY_READY] No webhook_data in AI response - not ready"
                )
                return False

            # 2. Kiểm tra xem có thông tin khách hàng không (tên + phone/email)
            customer_data = webhook_data.get("customer", {})
            has_name = customer_data.get("name", "").strip() not in [
                "",
                "Khách hàng",
                "Unknown",
            ]
            has_contact = (
                customer_data.get("phone", "").strip()
                or customer_data.get("email", "").strip()
            )

            if not (has_name and has_contact):
                logger.info(
                    "📊 [CHECK_QUANTITY_READY] Missing customer info (name + contact) - not ready"
                )
                return False

            # 3. Kiểm tra xem có item_name không
            item_name = webhook_data.get("item_name", "").strip()
            if not item_name or item_name in ["Không xác định", "Unknown"]:
                logger.info(
                    "📊 [CHECK_QUANTITY_READY] Missing or invalid item_name - not ready"
                )
                return False

            # 4. Kiểm tra final_answer có chứa từ khóa xác nhận gửi yêu cầu không
            final_answer = parsed_response.get("final_answer", "").lower()
            confirmation_phrases = [
                "đã gửi yêu cầu",
                "tôi đã gửi",
                "em đã gửi",
                "gửi yêu cầu của bạn",
                "gửi yêu cầu đến bộ phận",
                "họ sẽ liên hệ",
                "sẽ liên hệ lại",
                "bộ phận liên quan sẽ",
            ]

            has_confirmation = any(
                phrase in final_answer for phrase in confirmation_phrases
            )
            if not has_confirmation:
                logger.info(
                    "📊 [CHECK_QUANTITY_READY] No confirmation message in final_answer - not ready"
                )
                return False

            logger.info(
                "✅ [CHECK_QUANTITY_READY] All conditions met - ready to send webhook"
            )
            logger.info(
                f"   👤 Customer: {customer_data.get('name')} - {customer_data.get('phone', customer_data.get('email'))}"
            )
            logger.info(f"   📦 Item: {item_name}")

            return True

        except Exception as e:
            logger.error(
                f"❌ [CHECK_QUANTITY_READY] Error checking webhook readiness: {e}"
            )
            return False

    def _is_order_ready_for_webhook(self, parsed_response: Dict[str, Any]) -> bool:
        """
        Check if order is ready for webhook based on 'complete' flag in webhook_data
        Kiểm tra xem đơn hàng đã sẵn sàng gửi webhook dựa trên flag 'complete' trong webhook_data
        """
        try:
            # 🔍 DEBUG: Log full parsed response structure
            logger.info(
                f"🔍 [ORDER_WEBHOOK_CHECK] Checking parsed_response keys: {list(parsed_response.keys())}"
            )

            # Get webhook_data from AI response
            webhook_data = parsed_response.get("webhook_data", {})
            logger.info(
                f"🔍 [ORDER_WEBHOOK_CHECK] webhook_data keys: {list(webhook_data.keys()) if webhook_data else 'None'}"
            )

            order_data = webhook_data.get("order_data", {})
            logger.info(
                f"🔍 [ORDER_WEBHOOK_CHECK] order_data keys: {list(order_data.keys()) if order_data else 'None'}"
            )

            # Check if complete flag is set to true
            is_complete = order_data.get("complete", False)
            logger.info(f"🛒 [ORDER_WEBHOOK_CHECK] Complete flag: {is_complete}")

            if is_complete:
                # Verify basic required information exists
                has_items = bool(order_data.get("items"))
                customer_data = order_data.get("customer", {})
                has_customer_info = bool(
                    customer_data.get("name") and customer_data.get("phone")
                )

                logger.info(f"🛒 [ORDER_WEBHOOK_CHECK] Has items: {has_items}")
                logger.info(
                    f"🛒 [ORDER_WEBHOOK_CHECK] Has customer info: {has_customer_info}"
                )

                # 🔍 DEBUG: Log detailed order data
                if has_items:
                    items_count = len(order_data.get("items", []))
                    logger.info(f"🛒 [ORDER_WEBHOOK_CHECK] Items count: {items_count}")
                    for i, item in enumerate(order_data.get("items", [])):
                        logger.info(
                            f"🛒 [ORDER_WEBHOOK_CHECK] Item {i+1}: {item.get('name', 'Unknown')} x {item.get('quantity', 1)}"
                        )

                if has_customer_info:
                    logger.info(
                        f"🛒 [ORDER_WEBHOOK_CHECK] Customer: {customer_data.get('name', '')} - {customer_data.get('phone', '')}"
                    )

                return has_items and has_customer_info
            else:
                logger.info(
                    f"🛒 [ORDER_WEBHOOK_CHECK] Order not complete - complete flag is {is_complete}"
                )

            return False

        except Exception as e:
            logger.error(
                f"❌ [ORDER_WEBHOOK_CHECK] Error checking order readiness: {e}"
            )
            return False

    async def _extract_order_data_from_conversation(
        self, request: UnifiedChatRequest, parsed_response: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Extract order information from conversation history
        Trích xuất thông tin đơn hàng từ lịch sử hội thoại
        """
        try:
            # Get conversation history
            user_id = request.user_info.user_id if request.user_info else None
            device_id = request.user_info.device_id if request.user_info else None
            session_id = request.session_id

            conversation_history = []
            if self.conversation_manager:
                history = self.conversation_manager.get_optimized_messages_for_frontend(
                    user_id=user_id,
                    device_id=device_id,
                    session_id=session_id,
                    rag_context="",
                    current_query="",
                )
                conversation_history = [f"{msg.role}: {msg.content}" for msg in history]

            # Add current exchange
            conversation_history.append(f"user: {request.message}")
            conversation_history.append(
                f"assistant: {parsed_response.get('final_answer', '')}"
            )

            conversation_text = "\n".join(
                conversation_history[-10:]
            )  # Last 10 messages

            # Use AI to extract structured order data
            extraction_prompt = f"""
Từ cuộc hội thoại sau, hãy trích xuất thông tin đơn hàng thành JSON format:

{conversation_text}

Trả về JSON với format:
{{
  "items": [
    {{
      "name": "tên sản phẩm",
      "quantity": số_lượng,
      "unitPrice": giá_đơn_vị,
      "description": "mô tả"
    }}
  ],
  "customer": {{
    "name": "tên khách hàng",
    "phone": "số điện thoại",
    "email": "email",
    "address": "địa chỉ"
  }},
  "delivery": {{
    "method": "delivery hoặc pickup",
    "address": "địa chỉ giao hàng",
    "notes": "ghi chú"
  }},
  "payment": {{
    "method": "cash/bank_transfer/credit_card",
    "timing": "trả ngay hoặc trả sau"
  }},
  "notes": "ghi chú khác"
}}

Chỉ trả về JSON, không có text khác.
"""

            # Call AI to extract order data
            extraction_response = await self.ai_manager.stream_response(
                question=extraction_prompt, provider="cerebras"
            )

            full_extraction = ""
            async for chunk in extraction_response:
                full_extraction += chunk

            # Parse JSON from AI response
            json_match = re.search(r"\{.*\}", full_extraction, re.DOTALL)
            if json_match:
                order_data = json.loads(json_match.group(0))
                logger.info("🛒 [ORDER_EXTRACTION] Successfully extracted order data")
                return order_data
            else:
                logger.warning(
                    "🛒 [ORDER_EXTRACTION] No valid JSON found in extraction response"
                )
                return None

        except Exception as e:
            logger.error(f"❌ [ORDER_EXTRACTION] Failed to extract order data: {e}")
            return None

    async def _extract_order_data_from_response(
        self, parsed_response: Dict[str, Any], user_message: str
    ) -> Optional[Dict[str, Any]]:
        """
        Extract order data from AI response when webhook_data is not available
        Trích xuất dữ liệu đơn hàng từ AI response khi không có webhook_data
        """
        try:
            final_answer = parsed_response.get("final_answer", "")

            # Use AI to extract structured order data from the response
            extraction_prompt = f"""
Từ câu trả lời AI và tin nhắn của khách hàng, hãy trích xuất thông tin đơn hàng thành JSON format:

Tin nhắn khách hàng: {user_message}
Câu trả lời AI: {final_answer}

Trả về JSON với format:
{{
  "items": [
    {{
      "name": "tên sản phẩm/dịch vụ",
      "quantity": số_lượng,
      "unitPrice": giá_đơn_vị,
      "description": "mô tả chi tiết"
    }}
  ],
  "customer": {{
    "name": "tên khách hàng",
    "phone": "số điện thoại",
    "email": "email",
    "address": "địa chỉ"
  }},
  "delivery": {{
    "method": "delivery hoặc pickup",
    "address": "địa chỉ giao hàng",
    "notes": "ghi chú giao hàng"
  }},
  "payment": {{
    "method": "COD/bank_transfer/credit_card",
    "timing": "on_delivery/prepaid",
    "status": "PENDING"
  }},
  "notes": "ghi chú đặc biệt"
}}

Chỉ trả về JSON, không có text khác.
"""

            # Call AI to extract order data
            extraction_response = await self.ai_manager.stream_response(
                question=extraction_prompt, provider="cerebras"
            )

            full_extraction = ""
            async for chunk in extraction_response:
                full_extraction += chunk

            # Parse JSON from AI response
            json_match = re.search(r"\{.*\}", full_extraction, re.DOTALL)
            if json_match:
                order_data = json.loads(json_match.group(0))
                logger.info(
                    "🛒 [ORDER_EXTRACTION_FROM_RESPONSE] Successfully extracted order data"
                )
                return order_data
            else:
                logger.warning(
                    "🛒 [ORDER_EXTRACTION_FROM_RESPONSE] No valid JSON found"
                )
                return None

        except Exception as e:
            logger.error(f"❌ [ORDER_EXTRACTION_FROM_RESPONSE] Failed: {e}")
            return None

    async def _extract_update_order_data(
        self, parsed_response: Dict[str, Any], user_message: str
    ) -> Optional[Dict[str, Any]]:
        """
        Extract order update data from AI response when webhook_data is not available
        Trích xuất dữ liệu cập nhật đơn hàng từ AI response khi không có webhook_data
        """
        try:
            final_answer = parsed_response.get("final_answer", "")

            # Use AI to extract structured update data from the response
            extraction_prompt = f"""
Từ câu trả lời AI và tin nhắn của khách hàng, hãy trích xuất thông tin cập nhật đơn hàng thành JSON format:

Tin nhắn khách hàng: {user_message}
Câu trả lời AI: {final_answer}

Trả về JSON với format cho UPDATE_ORDER:
{{
  "orderCode": "mã đơn hàng nếu có trong conversation",
  "updateType": "change_date/change_quantity/change_items/cancel",
  "changes": {{
    "checkInDate": "ngày mới nếu thay đổi ngày",
    "quantity": số_lượng_mới,
    "items": [...],
    "notes": "lý do thay đổi"
  }},
  "customer": {{
    "name": "tên khách hàng",
    "phone": "số điện thoại",
    "email": "email"
  }},
  "companyId": "company_id_nếu_có"
}}

Nếu không tìm thấy mã đơn hàng cụ thể, dùng "UNKNOWN" cho orderCode.
Chỉ trả về JSON, không có text khác.
"""

            # Call AI to extract update data
            extraction_response = await self.ai_manager.stream_response(
                question=extraction_prompt, provider="cerebras"
            )

            full_extraction = ""
            async for chunk in extraction_response:
                full_extraction += chunk

            # Parse JSON from AI response
            json_match = re.search(r"\{.*\}", full_extraction, re.DOTALL)
            if json_match:
                update_data = json.loads(json_match.group(0))
                logger.info(
                    "🔄 [UPDATE_EXTRACTION_FROM_RESPONSE] Successfully extracted update data"
                )
                return update_data
            else:
                logger.warning(
                    "🔄 [UPDATE_EXTRACTION_FROM_RESPONSE] No valid JSON found"
                )
                return None

        except Exception as e:
            logger.error(f"❌ [UPDATE_EXTRACTION_FROM_RESPONSE] Failed: {e}")
            return None

    async def _send_order_created_webhook(
        self,
        request: UnifiedChatRequest,
        order_data: Dict[str, Any],
        processing_start_time: float,
    ) -> bool:
        """
        Send order creation webhook to backend using correct endpoint
        FIXED: Use /api/webhooks/orders/ai endpoint with proper JSON payload structure
        """
        try:
            import os
            import httpx

            # Build webhook payload according to API_Webhook_BE.md documentation
            webhook_payload = {
                "conversationId": getattr(
                    request, "conversation_id", request.session_id
                ),
                "companyId": request.company_id,
                # ✅ FIXED: leadId is OPTIONAL - let backend find/create lead from customer info
                "leadId": None,
                # ✅ FIXED: userId must be the actual user performing the action
                "userId": (
                    request.user_info.user_id
                    if request.user_info
                    else "ai_service_chatbot"
                ),
                # Summary of the order (extracted from conversation)
                "summary": self._build_order_summary(order_data),
                # Customer information (required)
                "customer": {
                    "name": order_data.get("customer", {}).get("name", ""),
                    "phone": order_data.get("customer", {}).get("phone", ""),
                    "email": order_data.get("customer", {}).get("email", ""),
                    "address": order_data.get("customer", {}).get("address", ""),
                    "company": order_data.get("customer", {}).get("company", ""),
                },
                # Items array (required)
                "items": self._format_items_for_backend(order_data.get("items", [])),
                # Channel information (required)
                "channel": {
                    "type": request.channel.value if request.channel else "chatdemo",
                    "pluginId": (
                        request.plugin_id if hasattr(request, "plugin_id") else None
                    ),
                },
                # Payment information (optional)
                "payment": order_data.get(
                    "payment",
                    {
                        "method": "COD",
                        "status": "PENDING",
                        "timing": "on_delivery",
                        "notes": "",
                    },
                ),
                # Delivery information (optional)
                "delivery": order_data.get(
                    "delivery",
                    {
                        "method": "delivery",
                        "address": order_data.get("customer", {}).get("address", ""),
                        "recipientName": order_data.get("customer", {}).get("name", ""),
                        "recipientPhone": order_data.get("customer", {}).get(
                            "phone", ""
                        ),
                        "notes": "",
                    },
                ),
                # Notes
                "notes": order_data.get("notes", ""),
                # Metadata
                "metadata": {
                    "source": "ai_conversation",
                    "aiModel": "qwen-3-235b-a22b-instruct-2507",
                    "processingTime": (
                        int((time.time() - processing_start_time) * 1000)
                        if processing_start_time
                        else 0
                    ),
                    "extractedFrom": "conversation",
                },
            }

            # Send to CORRECT backend endpoint
            backend_url = os.getenv("BACKEND_WEBHOOK_URL", "http://localhost:8001")
            endpoint = (
                f"{backend_url}/api/webhooks/orders/ai"  # FIXED: Correct endpoint
            )

            webhook_secret = os.getenv(
                "AI_WEBHOOK_SECRET", "webhook-secret-for-signature"
            )
            headers = {
                "Content-Type": "application/json",
                "x-webhook-secret": webhook_secret,  # FIXED: Correct header name
                "User-Agent": "Agent8x-AI-Service/1.0",
            }

            # Log the payload for debugging
            logger.info(f"🛒 [ORDER_WEBHOOK] Sending to endpoint: {endpoint}")
            logger.info(
                f"🛒 [ORDER_WEBHOOK] Customer: {webhook_payload['customer']['name']}"
            )
            logger.info(
                f"🛒 [ORDER_WEBHOOK] Items count: {len(webhook_payload['items'])}"
            )

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    endpoint, json=webhook_payload, headers=headers, timeout=30.0
                )

                if response.status_code == 200:
                    response_data = response.json()
                    order_info = response_data.get("data", {}).get("order", {})
                    order_code = order_info.get("orderCode", "Unknown")
                    logger.info(
                        f"✅ [ORDER_WEBHOOK] Order created successfully: {order_code}"
                    )
                    return True
                else:
                    logger.error(
                        f"❌ [ORDER_WEBHOOK] Backend returned {response.status_code}: {response.text}"
                    )
                    return False

        except Exception as e:
            logger.error(
                f"❌ [ORDER_WEBHOOK] Failed to send order.created webhook: {e}"
            )
            return False

    async def _handle_update_order_webhook(
        self,
        request,
        update_data: Dict[str, Any],
        processing_start_time: float,
    ) -> Dict[str, Any]:
        """
        Handle UPDATE_ORDER webhook sending and process backend response
        Xử lý gửi webhook UPDATE_ORDER và xử lý phản hồi từ backend
        """
        try:
            from src.services.webhook_service import webhook_service

            order_code = update_data.get("orderCode", "UNKNOWN")
            logger.info(
                f"🔄 [UPDATE_ORDER_HANDLER] Processing update for order: {order_code}"
            )

            # Add metadata
            if "metadata" not in update_data:
                update_data["metadata"] = {}

            update_data["metadata"].update(
                {
                    "source": "ai_conversation",
                    "aiModel": "qwen-3-235b-a22b-instruct-2507",
                    "processingTime": (
                        int((time.time() - processing_start_time) * 1000)
                        if processing_start_time
                        else 0
                    ),
                    "extractedFrom": "conversation",
                }
            )

            # Send webhook using webhook service and get response
            response_data = await webhook_service.send_update_order_webhook(
                order_code=order_code,
                update_data=update_data,
                company_id=request.company_id,
                user_id="ai_service_chatbot",
            )

            if response_data.get("success", False):
                logger.info(
                    f"✅ [UPDATE_ORDER_HANDLER] Successfully sent update webhook for order: {order_code}"
                )

                # Process backend response to create user-friendly message
                data = response_data.get("data", {})
                order_info = data.get("order", {})
                changes = order_info.get("changes", {})
                notifications = data.get("notifications", {})

                # Generate contextual response based on backend data
                update_message = f"✅ Đã cập nhật thành công đơn hàng {order_code}!"

                # Add change details if available
                if changes:
                    update_message += "\n\n📋 Những thay đổi đã thực hiện:"

                    if "status" in changes:
                        status_change = changes["status"]
                        update_message += f"\n• Trạng thái: {status_change.get('from')} → {status_change.get('to')}"

                    if "totalAmount" in changes:
                        amount_change = changes["totalAmount"]
                        old_amount = f"{amount_change.get('from', 0):,.0f} ₫"
                        new_amount = f"{amount_change.get('to', 0):,.0f} ₫"
                        update_message += f"\n• Tổng tiền: {old_amount} → {new_amount}"

                    if "items" in changes:
                        items_change = changes["items"]
                        added = items_change.get("added", 0)
                        modified = items_change.get("modified", 0)
                        if added > 0:
                            update_message += f"\n• Đã thêm {added} sản phẩm/dịch vụ"
                        if modified > 0:
                            update_message += (
                                f"\n• Đã sửa đổi {modified} sản phẩm/dịch vụ"
                            )

                    if "payment" in changes:
                        payment_change = changes["payment"]
                        update_message += f"\n• Thanh toán: {payment_change}"

                # Add notification info
                if notifications.get("customerUpdateEmailSent", False):
                    update_message += "\n\n📧 Email xác nhận đã được gửi đến bạn."

                if notifications.get("businessUpdateEmailSent", False):
                    update_message += "\n📧 Shop đã được thông báo về thay đổi."

                # Add formatted total if available
                formatted_total = order_info.get("formattedTotal")
                if formatted_total:
                    update_message += f"\n\n💰 Tổng tiền hiện tại: {formatted_total}"

                update_message += "\n\nBạn còn muốn thay đổi gì khác không?"

                response_data["user_message"] = update_message

            else:
                logger.error(
                    f"❌ [UPDATE_ORDER_HANDLER] Failed to send update webhook for order: {order_code}"
                )

                # Generate error message for user
                error_message = (
                    f"⚠️ Tôi gặp khó khăn khi cập nhật đơn hàng {order_code}. "
                )

                # Check if it's an order not found error
                error_msg = response_data.get("message", "").lower()
                if "not found" in error_msg or "không tìm thấy" in error_msg:
                    error_message += "Có thể mã đơn hàng không đúng. Bạn vui lòng kiểm tra lại mã đơn hàng nhé!"
                else:
                    error_message += (
                        "Vui lòng thử lại sau hoặc liên hệ trực tiếp với shop!"
                    )

                response_data["user_message"] = error_message

            return response_data

        except Exception as e:
            logger.error(
                f"❌ [UPDATE_ORDER_HANDLER] Error handling update order webhook: {e}"
            )

            # Generate error message for user
            error_message = f"⚠️ Tôi đang gặp lỗi kỹ thuật khi cập nhật đơn hàng {order_code}. Vui lòng thử lại sau!"

            return {"success": False, "error": str(e), "user_message": error_message}

    async def _handle_check_quantity_webhook(
        self,
        request,
        quantity_data: Dict[str, Any],
        processing_start_time: float,
    ) -> Dict[str, Any]:
        """
        Handle CHECK_QUANTITY webhook sending and process backend response
        Xử lý gửi webhook CHECK_QUANTITY và xử lý phản hồi từ backend
        """
        try:
            from src.services.webhook_service import webhook_service

            item_name = quantity_data.get("itemName", "Unknown")
            logger.info(
                f"📊 [CHECK_QUANTITY_HANDLER] Processing quantity check for: {item_name}"
            )

            # Add conversation context from request (CORRECT: conversationId must come from request)
            quantity_data["conversationId"] = getattr(
                request, "conversation_id", request.session_id
            )

            # Build channel info
            channel_info = {
                "type": request.channel.value if request.channel else "chatdemo"
            }

            if request.channel == ChannelType.CHAT_PLUGIN:
                channel_info["pluginId"] = getattr(request, "plugin_id", None)

            # Send webhook using webhook service and get response
            response_data = await webhook_service.send_check_quantity_webhook(
                quantity_data=quantity_data,
                company_id=request.company_id,
                channel=channel_info,
            )

            if response_data.get("success", False):
                logger.info(
                    f"✅ [CHECK_QUANTITY_HANDLER] Successfully checked quantity for: {item_name}"
                )

                # Process backend response to create user-friendly message
                data = response_data.get("data", {})
                available = data.get("available", False)
                quantity = data.get("quantity", 0)
                item_info = data.get("item", {})

                logger.info(
                    f"📊 [CHECK_QUANTITY_HANDLER] Result - Available: {available}, Quantity: {quantity}"
                )

                # Generate contextual response based on backend data
                if available:
                    # In stock - provide positive response with details
                    item_name = item_info.get("name", item_name)
                    price = item_info.get("price", 0)
                    formatted_price = (
                        f"{price:,.0f} ₫" if price > 0 else "Liên hệ để biết giá"
                    )

                    availability_message = (
                        f"✅ Còn hàng! Shop còn {quantity} {item_name}."
                    )

                    if price > 0:
                        availability_message += f" Giá: {formatted_price}."

                    availability_message += f" Bạn muốn đặt bao nhiêu {item_info.get('unit', 'cái').lower()}?"

                    response_data["user_message"] = availability_message

                else:
                    # Out of stock - provide helpful response
                    business_notified = data.get("details", {}).get(
                        "businessNotified", False
                    )

                    if business_notified:
                        availability_message = (
                            f"❌ Rất tiếc, {item_name} hiện tại đã hết hàng. "
                        )
                        availability_message += "Tôi đã thông báo cho shop và họ sẽ liên hệ lại với bạn sớm nhất có thể. "
                        availability_message += (
                            "Bạn có muốn để lại thông tin liên hệ không?"
                        )

                        logger.info(
                            f"📧 [CHECK_QUANTITY_HANDLER] Business was notified about out of stock: {item_name}"
                        )
                    else:
                        availability_message = (
                            f"❌ Rất tiếc, {item_name} hiện tại đã hết hàng. "
                        )
                        availability_message += "Bạn có thể xem các sản phẩm khác hoặc để lại thông tin để được thông báo khi có hàng trở lại."

                    response_data["user_message"] = availability_message

            else:
                logger.error(
                    f"❌ [CHECK_QUANTITY_HANDLER] Failed to check quantity for: {item_name}"
                )

                # Generate error message for user
                error_message = (
                    f"⚠️ Tôi đang gặp khó khăn khi kiểm tra tồn kho cho {item_name}. "
                )
                error_message += (
                    "Vui lòng thử lại sau hoặc liên hệ trực tiếp với shop nhé!"
                )

                response_data["user_message"] = error_message

            return response_data

        except Exception as e:
            logger.error(
                f"❌ [CHECK_QUANTITY_HANDLER] Error handling check quantity webhook: {e}"
            )

            # Generate error message for user
            error_message = "⚠️ Tôi đang gặp lỗi kỹ thuật khi kiểm tra tồn kho. Vui lòng thử lại sau!"

            return {"success": False, "error": str(e), "user_message": error_message}

    def _calculate_order_totals(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate order financial totals from items"""
        try:
            subtotal = 0
            for item in items:
                quantity = item.get("quantity", 1)
                unit_price = item.get("unitPrice", 0)
                subtotal += quantity * unit_price

            tax_rate = 0.1  # 10% tax
            tax_amount = subtotal * tax_rate
            total_amount = subtotal + tax_amount

            return {
                "subtotal": subtotal,
                "taxAmount": tax_amount,
                "discountAmount": 0,
                "totalAmount": total_amount,
                "currency": "VND",
            }
        except Exception as e:
            logger.error(f"❌ Error calculating order totals: {e}")
            return {
                "subtotal": 0,
                "taxAmount": 0,
                "discountAmount": 0,
                "totalAmount": 0,
                "currency": "VND",
            }

    def _build_order_summary(self, order_data: Dict[str, Any]) -> str:
        """Build order summary from order data"""
        try:
            customer = order_data.get("customer", {})
            items = order_data.get("items", [])

            customer_name = customer.get("name", "Khách hàng")

            # Build items summary
            items_summary = []
            total_amount = 0

            for item in items:
                quantity = item.get("quantity", 1)
                name = item.get("name", "")
                unit_price = item.get("unitPrice", 0)
                total_price = quantity * unit_price
                total_amount += total_price

                items_summary.append(f"{quantity} {name}")

            items_text = " và ".join(items_summary)

            # Build delivery info
            delivery = order_data.get("delivery", {})
            delivery_method = (
                "Giao hàng tận nơi"
                if delivery.get("method") == "delivery"
                else "Khách đến lấy"
            )

            # Build payment info
            payment = order_data.get("payment", {})
            payment_method = payment.get("method", "COD")

            summary = f"{customer_name} đặt {items_text} với tổng giá trị {total_amount:,.0f} VND. {delivery_method}, thanh toán {payment_method}."

            return summary

        except Exception as e:
            logger.error(f"❌ Error building order summary: {e}")
            return "Đặt hàng từ cuộc trò chuyện với AI"

    def _format_items_for_backend(
        self, items: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Format items array to match backend API requirements"""
        try:
            formatted_items = []

            for item in items:
                # ✅ FIXED: Auto-determine itemType based on ID presence
                item_type = "Custom"  # Default fallback
                if item.get("productId"):
                    item_type = "Product"
                elif item.get("serviceId"):
                    item_type = "Service"

                formatted_item = {
                    "productId": item.get("productId"),
                    "serviceId": item.get("serviceId"),
                    "itemType": item_type,  # ✅ FIXED: Auto-determined itemType
                    "name": item.get("name", ""),
                    "quantity": item.get("quantity", 1),
                    "unitPrice": item.get("unitPrice", 0),
                    "totalPrice": item.get("quantity", 1) * item.get("unitPrice", 0),
                    "description": item.get("description", ""),
                    "notes": item.get("notes", ""),
                    "product_code": item.get("product_code", ""),
                    "unit": item.get("unit", "Cái"),
                }

                formatted_items.append(formatted_item)

            return formatted_items

        except Exception as e:
            logger.error(f"❌ Error formatting items for backend: {e}")
            return []

    def _deduplicate_search_results(
        self, search_results: List[Dict[str, Any]], similarity_threshold: float = 0.8
    ) -> List[Dict[str, Any]]:
        """
        Remove duplicate content from search results based on content similarity
        Loại bỏ nội dung trùng lặp từ kết quả tìm kiếm dựa trên độ tương tự nội dung
        """
        if not search_results:
            return search_results

        deduplicated = []
        seen_contents = set()

        for result in search_results:
            content = result.get("content_for_rag", "").strip()

            # Skip empty content
            if not content:
                continue

            # Check for exact duplicates first
            content_normalized = " ".join(content.lower().split())
            if content_normalized in seen_contents:
                logger.info(f"🔄 [DEDUP] Skipping exact duplicate: {content[:50]}...")
                continue

            # Check for similar content (simple approach - can be improved with embedding similarity)
            is_similar = False
            for existing_content in seen_contents:
                # Simple similarity check - if content is largely contained in existing or vice versa
                shorter = min(content_normalized, existing_content, key=len)
                longer = max(content_normalized, existing_content, key=len)

                if len(shorter) > 0 and len(longer) > 0:
                    # Check if shorter is largely contained in longer
                    similarity_ratio = len(shorter) / len(longer)
                    if similarity_ratio > similarity_threshold and shorter in longer:
                        is_similar = True
                        logger.info(
                            f"🔄 [DEDUP] Skipping similar content (ratio: {similarity_ratio:.2f}): {content[:50]}..."
                        )
                        break

            if not is_similar:
                seen_contents.add(content_normalized)
                deduplicated.append(result)
                logger.info(f"✅ [DEDUP] Keeping unique content: {content[:50]}...")

        logger.info(
            f"📊 [DEDUP] Reduced from {len(search_results)} to {len(deduplicated)} results"
        )
        return deduplicated

    async def _hybrid_search_company_data_optimized(
        self, company_id: str, query: str
    ) -> str:
        """
        Get company data ONLY from Qdrant search based on user query
        Chỉ lấy company data từ Qdrant search theo user query - KHÔNG fallback
        """
        try:
            logger.info(
                f"🔍 [COMPANY_DATA] Starting Qdrant search for company: {company_id}"
            )
            logger.info(f"🔍 [COMPANY_DATA] Query: {query[:100]}...")

            # Use existing hybrid search from admin service
            search_result = await self._hybrid_search_company_data(
                company_id=company_id,
                query=query,
                limit=15,  # Get more results for better deduplication
                score_threshold=0.1,  # Very low threshold
            )

            logger.info(f"🔍 [COMPANY_DATA] Search result type: {type(search_result)}")
            logger.info(
                f"🔍 [COMPANY_DATA] Search result length: {len(search_result) if search_result else 0}"
            )

            # Process search results
            if search_result and isinstance(search_result, list):
                # First: Deduplicate results
                deduplicated_results = self._deduplicate_search_results(
                    search_result, similarity_threshold=0.7
                )

                # Limit to top results after deduplication
                final_results = deduplicated_results[
                    :8
                ]  # Keep only top 8 unique results

                # Format search results for prompt
                formatted_results = []
                logger.info(
                    f"🔍 [COMPANY_DATA] Processing {len(final_results)} deduplicated search results:"
                )

                for i, item in enumerate(final_results):
                    content = item.get("content_for_rag", "")
                    score = item.get("score", 0)
                    data_type = item.get("data_type", "unknown")
                    chunk_id = item.get("chunk_id", "unknown")
                    file_id = item.get("file_id", "unknown")

                    logger.info(f"   📄 Chunk {i+1}:")
                    logger.info(f"      ID: {chunk_id}")
                    logger.info(f"      File: {file_id}")
                    logger.info(f"      Type: {data_type}")
                    logger.info(f"      Score: {score:.3f}")
                    logger.info(f"      Content length: {len(content)} chars")

                    if len(content) > 100:
                        logger.info(f"      Content preview: {content[:200]}...")
                    else:
                        logger.info(f"      Full content: {content}")

                    # Format for prompt with data type label
                    formatted_results.append(f"[{data_type.upper()}] {content.strip()}")

                if formatted_results:
                    result_text = "[DỮ LIỆU MÔ TẢ TỪ TÀI LIỆU]\n" + "\n\n".join(
                        formatted_results
                    )
                    logger.info(
                        f"✅ [COMPANY_DATA] Found company data: {len(result_text)} chars"
                    )
                    logger.info(
                        f"✅ [COMPANY_DATA] RAG items: {len(formatted_results)}"
                    )
                    return result_text
                else:
                    logger.info(
                        f"📭 [COMPANY_DATA] No formatted results after processing"
                    )
                    return "No relevant company data found."
            else:
                logger.info(f"📭 [COMPANY_DATA] No search results from Qdrant")
                return "No relevant company data found."

        except Exception as e:
            logger.error(f"❌ [COMPANY_DATA] Error in Qdrant search: {e}")
            return "No relevant company data found."

    async def _get_products_list_for_prompt(self, company_id: str, query: str) -> str:
        """
        Get products list from MongoDB catalog service for prompt
        Lấy danh sách sản phẩm từ MongoDB catalog service cho prompt
        """
        try:
            # Ensure catalog service is initialized
            await self._ensure_catalog_service()

            if not self.catalog_service:
                logger.warning("⚠️ Catalog service not available")
                return "No products data available."

            # Get catalog data from MongoDB
            catalog_data = await self.catalog_service.get_catalog_for_prompt(
                company_id=company_id,
                query=query,
                limit=20,  # Get more products for comprehensive inventory info
            )

            if catalog_data and len(catalog_data) > 0:
                # Format products for prompt with inventory labels
                formatted_products = []
                for item in catalog_data:
                    item_id = item.get("item_id", "N/A")
                    item_type = item.get("item_type", "unknown")
                    name = item.get("name", "Unknown")
                    quantity_display = item.get("quantity_display", "N/A")
                    price_display = item.get("price_display", "N/A")

                    formatted_products.append(
                        f"[{item_type.upper()}] {name} (ID: {item_id}) - Số lượng: {quantity_display}, Giá: {price_display}"
                    )

                result = "[DỮ LIỆU TỒN KHO - CHÍNH XÁC NHẤT]\n" + "\n".join(
                    formatted_products
                )
                logger.info(
                    f"✅ [PRODUCTS_LIST] Found {len(catalog_data)} products from MongoDB"
                )
                return result
            else:
                logger.info("📭 [PRODUCTS_LIST] No products found in catalog")
                return "No products data available."

        except Exception as e:
            logger.error(f"❌ [PRODUCTS_LIST] Error getting products list: {e}")
            return "Error retrieving products data."

    async def _get_user_context_optimized(
        self,
        device_id: str,
        session_id: str = None,
        user_id: str = None,
        user_name: str = None,
    ) -> str:
        """
        FRONTEND OPTIMIZED: Fast user context retrieval with name support
        FRONTEND TỐI ƯU: Lấy context user nhanh với hỗ trợ tên người dùng

        Frontend requirements:
        - user_id always provided (authenticated: 2Fi60Cy2jHcMhkn5o2VcjfUef7p2 or anon: anon_web_a1b2c3d4)
        - Check user_id FIRST for speed optimization
        - Get latest session_id conversation history
        - Support user name for personalized responses

        Yêu cầu frontend:
        - user_id luôn được cung cấp (đã xác thực hoặc ẩn danh)
        - Check user_id TRƯỚC để tối ưu tốc độ
        - Lấy history chat từ session_id gần nhất
        - Hỗ trợ tên user cho phản hồi cá nhân hóa
        """
        try:
            # Use the real conversation_manager with optimized frontend method
            if self.conversation_manager:
                logger.info(
                    f"👤 [FRONTEND_OPTIMIZED] Starting optimized user identification"
                )
                logger.info(
                    f"👤 [FRONTEND_OPTIMIZED] user_id: {user_id}, device_id: {device_id}, session_id: {session_id}"
                )
                if user_name:
                    logger.info(f"👤 [FRONTEND_OPTIMIZED] user_name: {user_name}")

                # Use optimized method designed for frontend requirements
                messages = (
                    self.conversation_manager.get_optimized_messages_for_frontend(
                        user_id=user_id,
                        device_id=device_id,
                        session_id=session_id,
                        rag_context="",
                        current_query="",
                    )
                )

                if messages and len(messages) > 0:
                    # Format messages as simple conversation format instead of JSON
                    formatted_messages = []
                    for msg in messages[-10:]:  # Last 10 messages for context
                        role = msg.get("role", "unknown")
                        content = msg.get("content", "")

                        # Skip empty messages
                        if not content.strip():
                            continue

                        # Format with proper role names and extract final_answer from JSON
                        if role == "user":
                            display_name = user_name if user_name else "User"
                            formatted_messages.append(f"{display_name}: {content}")
                        else:
                            # For AI responses, extract only final_answer from JSON if present
                            if content.startswith("```json") or content.startswith("{"):
                                try:
                                    # Try to extract JSON and get final_answer
                                    import re, json

                                    # Remove markdown code blocks
                                    clean_content = re.sub(
                                        r"```json\s*|\s*```", "", content
                                    )
                                    if clean_content.startswith("{"):
                                        parsed = json.loads(clean_content)
                                        ai_answer = parsed.get("final_answer", content)
                                        formatted_messages.append(f"AI: {ai_answer}")
                                    else:
                                        formatted_messages.append(f"AI: {content}")
                                except:
                                    # If parsing fails, use original content
                                    formatted_messages.append(f"AI: {content}")
                            else:
                                formatted_messages.append(f"AI: {content}")

                    # Build simple conversation context without header
                    if formatted_messages:
                        result = "\n".join(formatted_messages)
                    else:
                        if user_name:
                            result = f"This is the first conversation with {user_name}."
                        else:
                            result = "No previous conversation history."

                    # Determine which identifier was used (for logging)
                    primary_identifier = "unknown"
                    if user_id and user_id != "unknown":
                        primary_identifier = f"user_id:{user_id}"
                    elif device_id and device_id != "unknown":
                        primary_identifier = f"device_id:{device_id}"
                    elif session_id and session_id != "unknown":
                        primary_identifier = f"session_id:{session_id}"

                    logger.info(
                        f"👤 [FRONTEND_OPTIMIZED] ✅ Found {len(messages)} messages using optimized system"
                    )
                    logger.info(
                        f"👤 [FRONTEND_OPTIMIZED] Primary identifier: {primary_identifier}"
                    )
                    logger.info(
                        f"👤 [FRONTEND_OPTIMIZED] Context length: {len(result)} chars"
                    )
                    logger.info(
                        f"✅ [USER_CONTEXT] Previous conversation successfully loaded for AI context"
                    )
                    logger.info(
                        f"📋 [USER_CONTEXT] Latest message preview: {messages[-1].get('content', '')[:100]}..."
                    )
                    if user_name:
                        logger.info(
                            f"👤 [FRONTEND_OPTIMIZED] Personalized for: {user_name}"
                        )

                    return result
                else:
                    logger.info(
                        f"👤 [FRONTEND_OPTIMIZED] No conversation history found"
                    )
                    # Return personalized empty state
                    if user_name:
                        return f"This is the first conversation with {user_name}."
                    else:
                        return "No previous conversation history."
            else:
                logger.warning(
                    f"⚠️ [FRONTEND_OPTIMIZED] conversation_manager not available"
                )
                if user_name:
                    return f"This is the first conversation with {user_name}."
                else:
                    return "No previous conversation history."

        except Exception as e:
            logger.error(f"❌ [FRONTEND_OPTIMIZED] User context failed: {e}")
            if user_name:
                return f"This is the first conversation with {user_name}."
            else:
                return "No previous conversation history."

    def _get_company_name_from_db(self, company_id: str) -> str:
        """
        Get company name directly from MongoDB companies collection
        Lấy tên công ty trực tiếp từ MongoDB companies collection
        """
        try:
            from src.database.company_db_service import get_company_db_service

            db_service = get_company_db_service()
            company_data = db_service.companies.find_one({"company_id": company_id})

            if company_data and company_data.get("company_name"):
                company_name = company_data["company_name"].strip()
                if company_name and company_name != "Chưa có thông tin":
                    logger.info(f"✅ [COMPANY_NAME] Found: '{company_name}'")
                    return company_name

            logger.warning(f"⚠️ [COMPANY_NAME] Not found for company_id: {company_id}")
            return "công ty"

        except Exception as e:
            logger.error(f"❌ [COMPANY_NAME] Error getting company name: {e}")
            return "công ty"

    async def _get_company_context_optimized(self, company_id: str) -> str:
        """
        Get company context ONLY from MongoDB companies collection
        Chỉ lấy company context từ MongoDB companies collection - KHÔNG fallback
        """
        try:
            logger.info(
                f"🏢 [COMPANY_CONTEXT] Getting company context for: {company_id}"
            )

            # Get company data from companies collection
            from src.database.company_db_service import get_company_db_service

            db_service = get_company_db_service()
            company_data = db_service.companies.find_one({"company_id": company_id})

            if not company_data:
                logger.warning(
                    f"⚠️ Company {company_id} not found in companies collection"
                )
                return "No company context available."

            # Format company context - always has company_name and industry
            formatted_context = f"""=== THÔNG TIN CÔNG TY ===
Tên công ty: {company_data.get('company_name', 'Chưa có thông tin')}
Ngành nghề: {company_data.get('industry', 'Chưa có thông tin')}"""

            # Add metadata information if available
            metadata = company_data.get("metadata", {})
            if metadata:
                if metadata.get("description"):
                    formatted_context += f"\nMô tả: {metadata['description']}"

                # Contact info
                if (
                    metadata.get("email")
                    or metadata.get("phone")
                    or metadata.get("website")
                ):
                    formatted_context += "\n\n=== THÔNG TIN LIÊN HỆ ==="
                    if metadata.get("email"):
                        formatted_context += f"\nEmail: {metadata['email']}"
                    if metadata.get("phone"):
                        formatted_context += f"\nSố điện thoại: {metadata['phone']}"
                    if metadata.get("website"):
                        formatted_context += f"\nWebsite: {metadata['website']}"

                # Location info
                location = metadata.get("location", {})
                if location:
                    if (
                        location.get("address")
                        or location.get("city")
                        or location.get("country")
                    ):
                        formatted_context += "\n\n=== ĐỊA CHỈ ==="
                        if location.get("address"):
                            formatted_context += f"\nĐịa chỉ: {location['address']}"
                        if location.get("city"):
                            formatted_context += f"\nThành phố: {location['city']}"
                        if location.get("country"):
                            formatted_context += f"\nQuốc gia: {location['country']}"

                # Social links
                social_links = metadata.get("social_links", {})
                if social_links:
                    formatted_context += "\n\n=== MẠNG XÃ HỘI ==="
                    if social_links.get("facebook"):
                        formatted_context += f"\nFacebook: {social_links['facebook']}"
                    if social_links.get("instagram"):
                        formatted_context += f"\nInstagram: {social_links['instagram']}"
                    if social_links.get("zalo"):
                        formatted_context += f"\nZalo: {social_links['zalo']}"
                    if social_links.get("twitter"):
                        formatted_context += f"\nTwitter: {social_links['twitter']}"
                    if social_links.get("linkedin"):
                        formatted_context += f"\nLinkedIn: {social_links['linkedin']}"
                    if social_links.get("whatsapp"):
                        formatted_context += f"\nWhatsApp: {social_links['whatsapp']}"
                    if social_links.get("telegram"):
                        formatted_context += f"\nTelegram: {social_links['telegram']}"

                # FAQs
                faqs = metadata.get("faqs", [])
                if faqs:
                    formatted_context += (
                        f"\n\n=== CÂU HỎI THƯỜNG GẶP ({len(faqs)} câu) ==="
                    )
                    for i, faq in enumerate(faqs, 1):
                        formatted_context += f"\n{i}. Q: {faq.get('question', '')}"
                        formatted_context += f"\n   A: {faq.get('answer', '')}"

                # Scenarios
                scenarios = metadata.get("scenarios", [])
                if scenarios:
                    formatted_context += (
                        f"\n\n=== KỊCH BẢN XỬ LÝ ({len(scenarios)} kịch bản) ==="
                    )
                    for i, scenario in enumerate(scenarios, 1):
                        formatted_context += f"\n{i}. {scenario.get('name', '')}: {scenario.get('description', '')}"

            logger.info(
                f"✅ [COMPANY_CONTEXT] Found company context: {len(formatted_context)} chars"
            )
            return formatted_context

        except Exception as e:
            logger.error(f"❌ [COMPANY_CONTEXT] Error getting company context: {e}")
            return "No company context available."

    def _build_unified_prompt_with_intent(
        self,
        user_context: str,
        company_data: str,
        company_context: str,
        products_list: str,
        user_query: str,
        industry: str,
        company_id: str = "unknown",
        session_id: str = "unknown",
        user_name: str = None,
        company_name: str = None,
    ) -> str:
        """
        FRONTEND OPTIMIZED: Build comprehensive prompt with user name support
        FRONTEND TỐI ƯU: Xây dựng prompt toàn diện với hỗ trợ tên người dùng
        """
        from src.services.prompt_templates import PromptTemplates
        import os

        # Extract user name from context if provided
        user_greeting = "Chào bạn"
        if user_name and user_name.strip():
            user_greeting = f"Chào {user_name.strip()}"
            logger.info(f"📝 [PROMPT] Using personalized greeting: {user_greeting}")

        # Build optimized prompt structure
        unified_prompt = f"""Bạn là một AI Assistant chuyên nghiệp của công ty {company_name or "này"}, có khả năng phân tích ý định của khách hàng và đưa ra câu trả lời tự nhiên, hữu ích.

**THÔNG TIN NGƯỜI DÙNG:**
- Tên (có thể rỗng): {user_name}

**THÔNG TIN CÔNG TY:**
{company_context}

**BỐI CẢNH ĐƯỢC CUNG CẤP:**
1. **Lịch sử hội thoại:**
{user_context}



**NHIỆM VỤ CỦA BẠN:**
Câu hỏi hiện tại của khách hàng: "{user_query}"

Thực hiện các bước sau trong đầu và chỉ trả về một đối tượng JSON duy nhất, không có bất kỳ văn bản nào khác.

1. **Phân tích nhu cầu của khách hàng (Thinking Process):**
   * **QUAN TRỌNG**: Chỉ trả lời câu hỏi HIỆN TẠI: "{user_query}" - KHÔNG được trả lời câu hỏi từ lịch sử hội thoại cũ.
   * Sử dụng bối cảnh lịch sử để hiểu ngữ cảnh nhưng chỉ trả lời câu hỏi hiện tại.
   * Xác định `intent` của câu hỏi HIỆN TẠI: là một trong bảy loại sau:
     - `SALES`: Có nhu cầu mua/đặt hàng nhưng chưa quyết định cuối cùng
     - `ASK_COMPANY_INFORMATION`: Hỏi thông tin về công ty, sản phẩm, dịch vụ (bao gồm GIÁ CẢ, thông số kỹ thuật)
     - `SUPPORT`: Hỗ trợ kỹ thuật hoặc khiếu nại
     - `GENERAL_INFORMATION`: Trò chuyện thông thường, hỏi thông tin chung
     - `PLACE_ORDER`: Đặt hàng trực tiếp, xác nhận đặt hàng
     - `UPDATE_ORDER`: Cập nhật đơn hàng đã tồn tại (cần mã đơn hàng)
     - `CHECK_QUANTITY`: **CHỈ** kiểm tra tồn kho/khả dụng (còn hàng không, còn phòng trống không, số lượng còn lại). **KHÔNG** áp dụng cho việc hỏi giá cả.
   * Dựa vào `intent`, chọn một vai trò (`persona`) phù hợp (ví dụ: "Chuyên viên tư vấn", "Lễ tân", "Chuyên viên hỗ trợ khách hàng").
   * Viết một lý do ngắn gọn (`reasoning`) cho việc lựa chọn `intent` đó.

    **🚨 QUAN TRỌNG - PHÂN BIỆT INTENT:**
   - **"Hỏi giá phòng/giá sản phẩm"** → `ASK_COMPANY_INFORMATION` (có thể trả lời ngay từ dữ liệu)
   - **"Khách sạn có những loại phòng nào?"** → `ASK_COMPANY_INFORMATION` (hỏi về danh sách, không phải tình trạng)
   - **"Còn phòng trống không/còn hàng không"** → `CHECK_QUANTITY` (cần kiểm tra thực tế)
   - **"Tình trạng phòng ngày mai"** → `CHECK_QUANTITY` (cần kiểm tra thực tế)
   - **"Số lượng tồn kho hiện tại"** → `CHECK_QUANTITY` (cần kiểm tra thực tế)

2. **Phân tích dữ liệu:**
   - **1️⃣ DỮ LIỆU TỒN KHO (có nhãn [DỮ LIỆU TỒN KHO - CHÍNH XÁC NHẤT])**: Ưu tiên TUYỆT ĐỐI cho câu hỏi về giá, tồn kho, trạng thái sản phẩm. Luôn bao gồm product_id trong câu trả lời nếu có.
   - **2️⃣ DỮ LIỆU MÔ TẢ (có nhãn [DỮ LIỆU MÔ TẢ TỪ TÀI LIỆU])**: Dùng để bổ sung thông tin chi tiết về sản phẩm.

   **Dữ liệu mô tả từ tài liệu:**
      {company_data}
   **Dữ liệu sản phẩm tồn kho**
      {products_list}


3. **Tạo câu trả lời cuối cùng (Final Answer):**
   * Dựa trên `intent` và `persona` đã chọn, soạn một câu trả lời **hoàn toàn tự nhiên** cho khách hàng.
   * **QUAN TRỌNG:** Câu trả lời này không được chứa bất kỳ dấu hiệu nào của quá trình phân tích (không đề cập đến "intent", "phân tích", "nhập vai"). Nó phải là một đoạn hội thoại trực tiếp và thân thiện.
   * **🎯 ƯU TIÊN DỮ LIỆU TỒN KHO:** Khi trả lời về giá cả, tồn kho, khả dụng sản phẩm, LUÔN ưu tiên thông tin từ "[DỮ LIỆU TỒN KHO - CHÍNH XÁC NHẤT]" và đề cập product_id nếu có (VD: "Sản phẩm ABC (Mã: SP001) có giá...").

   **HƯỚNG DẪN TRẢ LỜI THEO TỪNG INTENT:**

   **ĐẶC BIỆT CHO ASK_COMPANY_INFORMATION:**
   - **Dựa vào:** company_context (thông tin công ty) + `[DỮ LIỆU MÔ TẢ TỪ TÀI LIỆU]` (nếu liên quan đến công ty)
   - **Cách trả lời:** Trả lời trực tiếp về thông tin công ty như địa chỉ, giờ mở cửa, chính sách, liên hệ, lịch sử thành lập, tầm nhìn sứ mệnh...
   - **Ví dụ:** "Dạ, công ty chúng tôi có địa chỉ tại 123 Nguyễn Văn A, Q.1, TP.HCM. Giờ làm việc từ 8h-17h30 từ T2-T6 ạ. Hotline hỗ trợ: 1900-xxxx."
   - **Hình ảnh:** Nếu có URL hình ảnh công ty trong dữ liệu, hãy đính kèm: "Anh có thể xem hình ảnh văn phòng của chúng tôi tại: [URL]"

   **ĐẶC BIỆT CHO SALES:**
   - **Dựa vào:** `[DỮ LIỆU TỒN KHO]` (thông tin giá, tính năng, mã sản phẩm) + `[DỮ LIỆU MÔ TẢ TỪ TÀI LIỆU]` (lợi ích, so sánh sản phẩm)
   - **Cách trả lời:** Nhiệt tình, tập trung vào lợi ích sản phẩm/dịch vụ cụ thể. Đặt câu hỏi gợi mở để hiểu nhu cầu và dẫn dắt đến quyết định mua. Luôn đề cập mã sản phẩm nếu có.
   - **Ví dụ:** "Áo thun Basic Cotton (Mã: SP001) có giá 350.000đ, chất liệu 100% cotton thoáng mát. Với mức giá này, anh sẽ có được chất lượng premium. Anh thích màu nào và size bao nhiêu ạ?"
   - **Hình ảnh:** Nếu có URL hình ảnh sản phẩm, hãy đính kèm: "Anh có thể xem hình ảnh sản phẩm chi tiết tại: [URL]"

   **ĐẶC BIỆT CHO SUPPORT:**
   - **Dựa vào:** `[DỮ LIỆU MÔ TẢ TỪ TÀI LIỆU]` (hướng dẫn, FAQ) + thông tin liên hệ từ company_context
   - **Cách trả lời:** Thể hiện đồng cảm, thừa nhận vấn đề, đưa ra giải pháp cụ thể hoặc kết nối với bộ phận kỹ thuật.
   - **Ví dụ:** "Dạ tôi rất tiếc về sự cố anh đang gặp phải. Theo hướng dẫn, anh thử restart ứng dụng. Nếu vẫn lỗi, tôi sẽ kết nối anh với bộ phận kỹ thuật qua số hotline 1900-xxxx."

   **ĐẶC BIỆT CHO GENERAL_INFORMATION:**
   - **Dựa vào:** company_context (thông tin công ty) + `[DỮ LIỆU MÔ TẢ TỪ TÀI LIỆU]` nếu liên quan
   - **Cách trả lời:** Thân thiện, tự nhiên. Nếu câu hỏi đi xa khỏi chủ đề, khéo léo gợi ý quay lại sản phẩm/dịch vụ.
   - **Ví dụ:** "Dạ, hôm nay thời tiết đẹp nhỉ! Nhân tiện, với thời tiết đẹp thế này, anh có muốn tìm hiểu về các gói du lịch của khách sạn không ạ?"

   **ĐẶC BIỆT CHO PLACE_ORDER:** Nếu intent là PLACE_ORDER, hãy bắt đầu thu thập thông tin đơn hàng theo thứ tự: 1) Sản phẩm/dịch vụ, 2) Thông tin khách hàng, 3) Giao hàng, 4) Thanh toán. Chỉ hỏi 1-2 thông tin mỗi lượt để không áp đảo khách hàng.

   **🚨 QUAN TRỌNG - KHI NÀO SET complete: true CHO PLACE_ORDER:**
   - **complete: true** khi đã đủ thông tin CƠ BẢN để tạo đơn hàng: có sản phẩm/dịch vụ + tên khách + phone + Email + thời gian (đối với khách sạn).
   - **complete: false** khi còn thiếu thông tin hoặc chưa xác nhận rõ ràng với khách hàng.
   - **Ví dụ complete: true**: "Đã thu thập đủ thông tin về phòng Grand Suite Sea View cho anh Trần Văn Hoà, nhận phòng lúc 16h00 ngày mai và số điện thoại liên hệ của anh là 0909123456, email của anh là tranvanhoa@gmail.com" = Đã xác nhận rõ ràng
   - **BẮT BUỘC**: Khi complete=true, luôn hỏi khách hàng: "Em có gửi thông tin xác nhận đơn hàng qua email cho anh/chị không ạ?"

   **🚨 QUAN TRỌNG - KHI NÀO SET complete: true CHO UPDATE_ORDER:**
   - **complete: true** CHÍNH khi khách hàng đã cung cấp mã đơn hàng + xác nhận rõ ràng các thay đổi cần thiết
   - **complete: false** khi chưa có mã đơn hàng hoặc chưa xác định được thông tin cần thay đổi
   - **BẮT BUỘC**: Khi complete=true, luôn hỏi khách hàng: "Em có gửi thông tin cập nhật đơn hàng qua email cho anh/chị không ạ?"

   **ĐẶC BIỆT CHO UPDATE_ORDER:** Nếu intent là UPDATE_ORDER, cần:
   - Hỏi mã đơn hàng (nếu chưa có): "Bạn có thể cho tôi mã đơn hàng cần thay đổi không?"
   - Hỏi thông tin muốn cập nhật: "Bạn muốn thay đổi thông tin gì trong đơn hàng?"
   - Thu thập thông tin cập nhật chi tiết theo yêu cầu khách hàng
   - **CHỈ KHI ĐÃ ĐỦ**: mã đơn hàng + thông tin thay đổi rõ ràng → mới set complete: true

   **🚨 QUAN TRỌNG - KHI NÀO SET complete: true CHO CHECK_QUANTITY:**
   - **complete: true** CHÍNH khi khách hàng đã đồng ý để gửi yêu cầu kiểm tra + đã cung cấp tên + số điện thoại/email
   - **complete: false** khi khách hàng chưa đồng ý hoặc chưa cung cấp thông tin liên hệ
   - **BẮT BUỘC**: Khi complete=true, luôn hỏi khách hàng: "Em có gửi thông báo kết quả kiểm tra qua email cho anh/chị không ạ?"

   **ĐẶC BIỆT CHO CHECK_QUANTITY (QUAN TRỌNG - LUỒNG 2 BƯỚC):**
   Khi intent là `CHECK_QUANTITY`, hãy tuân thủ chính xác quy trình 2 bước sau:

   **Bước 1: Kiểm Tra Tức Thì & Trả Lời Ngay (Dựa vào `[DỮ LIỆU TỒN KHO]`)**
   - **Nếu `quantity` > 0:** Trả lời ngay lập tức cho khách hàng rằng sản phẩm CÒN HÀNG, kèm theo số lượng và giá. Ví dụ: "Dạ còn hàng ạ! Shop còn 50 Áo thun nam Basic Cotton. Giá 350.000đ. Bạn muốn đặt bao nhiêu cái ạ?"
   - **Nếu `quantity` == 0 hoặc `quantity` == -1 (không theo dõi) hoặc đó là dịch vụ đặc thù (đặt phòng, đặt bàn):** Chuyển sang Bước 2.

   **Bước 2: Đề Xuất Kiểm Tra Thủ Công & Gửi Webhook (Chỉ khi cần thiết)**
   - **1. Thông báo tình trạng:** Đầu tiên, thông báo cho khách hàng tình trạng hiện tại dựa trên hệ thống.
     - Ví dụ (hết hàng): "Dạ theo hệ thống của tôi thì sản phẩm này đang tạm hết hàng ạ."
     - Ví dụ (dịch vụ đặc thù): "Dạ để kiểm tra chính xác tình trạng phòng trống cho ngày hôm nay, tôi cần gửi yêu cầu đến bộ phận đặt phòng."
   - **2. Đề xuất trợ giúp:** Đưa ra lời đề nghị gửi yêu cầu kiểm tra thủ công.
     - Ví dụ: "Tuy nhiên, bạn có muốn tôi gửi yêu cầu kiểm tra lại trực tiếp với kho/bộ phận kinh doanh không ạ? Họ sẽ kiểm tra và liên hệ lại với bạn ngay khi có thông tin mới nhất."
   - **3. Chờ xác nhận:** Nếu khách hàng đồng ý ("ok em", "được", "gửi giúp anh", v.v.), lúc đó mới tiến hành thu thập thông tin.
   - **4. Thu thập thông tin liên hệ:** Hỏi tên và số điện thoại/email. Ví dụ: "Tuyệt vời ạ! Bạn vui lòng cho tôi xin tên và số điện thoại để bộ phận kinh doanh liên hệ lại nhé."
   - **5. Xác nhận và gửi Webhook:** Sau khi khách hàng cung cấp thông tin, câu trả lời cuối cùng của bạn phải xác nhận lại hành động. Ví dụ: "Cảm ơn bạn. Tôi đã gửi yêu cầu của bạn đến bộ phận liên quan. Họ sẽ sớm liên hệ với bạn qua số điện thoại [số điện thoại] ạ." Đồng thời, trong JSON payload, hãy điền đầy đủ thông tin để gửi webhook `check_quantity`.

   * Nếu `intent` của khách hàng nằm ngoài 7 loại trên, câu trả lời phải là: "Chào bạn! Tôi là AI chuyên hỗ trợ các thông tin về công ty và sản phẩm/dịch vụ của công ty {company_name or 'chúng tôi'}. Đối với các mục đích khác, tôi không thể trả lời được. Bạn có thể hỏi tôi về sản phẩm, dịch vụ, thông tin công ty hoặc cần hỗ trợ gì không?"

**ĐỊNH DẠNG ĐẦU RA (OUTPUT FORMAT):**
Chỉ trả về một đối tượng JSON hợp lệ, không có gì khác.

```json
{{
  "thinking": {{
    "intent": "...",
    "persona": "...",
    "reasoning": "..."
  }},
  "final_answer": "...",
  "webhook_data": {{
    // CHỈ BẮT BUỘC cho PLACE_ORDER, UPDATE_ORDER, CHECK_QUANTITY
    // KHÔNG cần cho các intent khác
  }}
}}
```

**🎯 HƯỚNG DẪN TẠO WEBHOOK_DATA:**

**Nếu intent = "PLACE_ORDER":**
```json
"webhook_data": {{
  "order_data": {{
    "complete": true/false, // true = đã đủ thông tin & xác nhận đặt hàng + hỏi email, false = còn thiếu thông tin
    "items": [
      {{
        "product_id": "product_id từ [DỮ LIỆU TỒN KHO] nếu có, nếu không để null",
        "service_id": "service_id từ [DỮ LIỆU TỒN KHO] nếu có, nếu không để null",
        "name": "tên sản phẩm/dịch vụ",
        "quantity": số_lượng_khách_đặt,
        "unit_price": "giá đơn vị từ [DỮ LIỆU TỒN KHO] nếu có",
        "notes": "ghi chú từ khách hàng"
      }}
    ],
    "customer": {{
      "name": "tên khách hàng đã thu thập",
      "phone": "số điện thoại đã thu thập",
      "email": "email nếu có",
      "address": "địa chỉ giao hàng nếu có"
    }},
    "delivery": {{
      "method": "pickup hoặc delivery",
      "address": "địa chỉ giao hàng nếu delivery"
    }},
    "payment": {{
      "method": "COD|transfer|cash"
    }},
    "notes": "ghi chú tổng quát"
  }}
}}
```

**Nếu intent = "UPDATE_ORDER":**
```json
"webhook_data": {{
  "update_data": {{
    "complete": true/false, // true = đã có mã đơn hàng + thông tin thay đổi rõ ràng + hỏi email, false = còn thiếu
    "order_code": "mã đơn hàng khách cung cấp",
    "changes": {{
      "items": "thông tin sản phẩm cần thay đổi nếu có",
      "customer": "thông tin khách hàng cần thay đổi nếu có",
      "delivery": "thông tin giao hàng cần thay đổi nếu có",
      "payment": "thông tin thanh toán cần thay đổi nếu có"
    }},
    "notes": "lý do thay đổi"
  }}
}}
```

**Nếu intent = "CHECK_QUANTITY" VÀ khách hàng đã cung cấp thông tin liên hệ:**
```json
"webhook_data": {{
  "check_quantity_data": {{
    "complete": true/false, // true = khách đồng ý + có tên + phone/email + hỏi email, false = chưa đủ
    "product_id": "product_id từ [DỮ LIỆU TỒN KHO] nếu có, nếu không để null",
    "service_id": "service_id từ [DỮ LIỆU TỒN KHO] nếu có, nếu không để null",
    "item_name": "tên sản phẩm/dịch vụ khách hàng hỏi",
    "item_type": "Product|Service",
    "customer": {{
      "name": "tên khách hàng đã thu thập",
      "phone": "số điện thoại đã thu thập",
      "email": "email của khách hàng"
    }},
    "specifications": {{
      "size": "size nếu có",
      "color": "màu sắc nếu có",
      "date": "ngày cần check nếu là dịch vụ",
      "quantity": "số lượng khách muốn biết"
    }},
    "notes": "yêu cầu chi tiết từ khách hàng"
  }}
}}
```

**Nếu intent KHÁC (ASK_COMPANY_INFORMATION, SUPPORT, SALES, GENERAL_INFORMATION):**
```json
// KHÔNG cần trường webhook_data
```

**HƯỚNG DẪN XƯNG HÔ (nếu có user_name hợp lệ):**
- Nếu tên là tiếng Việt/Anh và xác định giới tính nam ⇒ dùng "anh <Tên>".
- Nếu tên là tiếng Việt/Anh và xác định giới tính nữ ⇒ dùng "chị <Tên>".
- Nếu không chắc giới tính ⇒ dùng "bạn".
- Lồng ghép tên người dùng vào lời chào.
- Nếu chưa có tên chính xác của người dùng, nên hỏi tên người dùng phù hợp ngay trong câu trả lời thứ 2.

BẮT ĐẦU THỰC HIỆN.

"""

        # 📝 LOG PROMPT FOR DEBUGGING - Ghi log prompt để debug
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_filename = f"prompt_{company_id}_{session_id}_{timestamp}.txt"

            # Use relative path for server environment
            log_dir = os.path.join(os.getcwd(), "logs", "prompt")
            os.makedirs(log_dir, exist_ok=True)  # Ensure directory exists
            log_path = os.path.join(log_dir, log_filename)

            with open(log_path, "w", encoding="utf-8") as f:
                f.write("=" * 80 + "\n")
                f.write(f"PROMPT LOG - {timestamp}\n")
                f.write("=" * 80 + "\n")
                f.write(f"Company ID: {company_id}\n")
                f.write(f"Session ID: {session_id}\n")
                f.write(f"Industry: {industry}\n")
                f.write(f"User Query: {user_query}\n")
                f.write("=" * 80 + "\n")
                f.write("FULL PROMPT:\n")
                f.write("=" * 80 + "\n")
                f.write(unified_prompt)
                f.write("\n" + "=" * 80 + "\n")
                f.write("CONTEXT BREAKDOWN:\n")
                f.write("=" * 80 + "\n")
                f.write(
                    f"USER CONTEXT ({len(user_context)} chars):\n{user_context}\n\n"
                )
                f.write(
                    f"COMPANY DATA ({len(company_data)} chars):\n{company_data}\n\n"
                )
                f.write(
                    f"COMPANY CONTEXT ({len(company_context)} chars):\n{company_context}\n"
                )

            logger.info(f"📝 Prompt logged to: {log_filename}")

        except Exception as e:
            logger.error(f"❌ Failed to log prompt: {e}")

        # Replace user_query placeholder in the prompt
        unified_prompt = unified_prompt.replace("{user_query}", user_query)

        return unified_prompt

    async def _save_complete_conversation_async(
        self,
        request: UnifiedChatRequest,
        company_id: str,
        user_query: str,
        ai_response: str,
    ):
        """
        Save complete conversation and send appropriate webhooks AFTER streaming completes
        Lưu hội thoại hoàn chỉnh và gửi webhook phù hợp SAU KHI streaming kết thúc
        """
        try:
            # Extract user identifiers
            user_id = None
            device_id = None
            session_id = request.session_id

            if request.user_info:
                user_id = (
                    request.user_info.user_id
                    if request.user_info.user_id != "unknown"
                    else None
                )
                device_id = (
                    request.user_info.device_id
                    if request.user_info.device_id != "unknown"
                    else None
                )

            session_id = session_id if session_id != "unknown" else None

            logger.info(f"💾 [SAVE_COMPLETE] Processing with identifiers:")
            logger.info(f"💾 [SAVE_COMPLETE] - user_id: {user_id}")
            logger.info(f"💾 [SAVE_COMPLETE] - device_id: {device_id}")
            logger.info(f"💾 [SAVE_COMPLETE] - session_id: {session_id}")

            # Check if user/device exists in system
            is_new_user = True
            if self.conversation_manager and (user_id or device_id or session_id):
                # Check if user has any previous messages
                existing_messages = (
                    self.conversation_manager.get_optimized_messages_for_frontend(
                        user_id=user_id,
                        device_id=device_id,
                        session_id=session_id,
                        rag_context="",
                        current_query="",
                    )
                )
                is_new_user = not existing_messages or len(existing_messages) == 0
                logger.info(f"� [SAVE_COMPLETE] Is new user: {is_new_user}")

            # Save conversation to database
            conversation_saved = False
            if self.conversation_manager and ai_response and ai_response.strip():
                if user_id or device_id or session_id:
                    try:
                        # Save user message
                        user_saved = self.conversation_manager.add_message_enhanced(
                            user_id=user_id,
                            device_id=device_id,
                            session_id=session_id,
                            role="user",
                            content=user_query,
                        )

                        # Save AI response
                        ai_saved = self.conversation_manager.add_message_enhanced(
                            user_id=user_id,
                            device_id=device_id,
                            session_id=session_id,
                            role="assistant",
                            content=ai_response,
                        )

                        conversation_saved = user_saved and ai_saved
                        if conversation_saved:
                            primary_identifier = user_id or device_id or session_id
                            logger.info(
                                f"💾 [SAVE_COMPLETE] ✅ Conversation saved for: {primary_identifier}"
                            )
                            logger.info(
                                f"💾 [SAVE_COMPLETE] ✅ User message saved: {user_saved}"
                            )
                            logger.info(
                                f"💾 [SAVE_COMPLETE] ✅ AI response saved: {ai_saved}"
                            )
                            logger.info(
                                f"💾 [SAVE_COMPLETE] ✅ Future user_context will include this conversation"
                            )

                            # Verify conversation was saved and can be retrieved for user_context
                            verification_success = (
                                await self._verify_conversation_saved(
                                    user_id=user_id,
                                    device_id=device_id,
                                    session_id=session_id,
                                    expected_messages=2,  # User + AI message
                                )
                            )

                            if verification_success:
                                logger.info(
                                    f"✅ [SAVE_COMPLETE] Conversation verification PASSED - user_context will work"
                                )
                            else:
                                logger.error(
                                    f"❌ [SAVE_COMPLETE] Conversation verification FAILED - user_context may be incomplete"
                                )

                        else:
                            logger.error(
                                f"❌ [SAVE_COMPLETE] Failed to save conversation"
                            )
                            logger.error(
                                f"❌ [SAVE_COMPLETE] User saved: {user_saved}, AI saved: {ai_saved}"
                            )

                    except Exception as save_error:
                        logger.error(
                            f"❌ [SAVE_COMPLETE] Database save error: {save_error}"
                        )
                        conversation_saved = False
                else:
                    logger.warning(
                        f"⚠️ [SAVE_COMPLETE] No valid identifiers to save conversation"
                    )
            else:
                if not self.conversation_manager:
                    logger.warning(
                        f"⚠️ [SAVE_COMPLETE] conversation_manager not available"
                    )
                if not ai_response or not ai_response.strip():
                    logger.warning(
                        f"⚠️ [SAVE_COMPLETE] Empty AI response, skipping save"
                    )

            # Send appropriate webhooks based on user status
            if is_new_user:
                # NEW USER: Send conversation.created + 2x message.created
                logger.info(
                    "🔔 [WEBHOOK] NEW USER detected - sending creation webhooks"
                )

                # Get conversation ID
                conversation_id = self.get_or_create_conversation(
                    session_id=session_id,
                    company_id=company_id,
                    device_id=device_id,
                    request=request,
                )

                try:
                    # 1. Send conversation.created
                    await self._send_conversation_created_webhook(
                        company_id=company_id,
                        conversation_id=conversation_id,
                        session_id=session_id,
                        request=request,
                    )

                    # NOTE: Removed message.created webhooks to avoid duplication with ai.response.completed
                    # The ai.response.completed event already contains both user and AI messages

                    logger.info("🔔 [WEBHOOK] ✅ New user webhooks sent successfully")

                except Exception as webhook_error:
                    logger.error(
                        f"❌ [WEBHOOK] Failed to send new user webhooks: {webhook_error}"
                    )

            else:
                # EXISTING USER: Send conversation.updated only with message details
                logger.info(
                    "🔔 [WEBHOOK] EXISTING USER detected - sending update webhook"
                )

                try:
                    # Build message details for webhook
                    user_timestamp = datetime.now().isoformat()
                    ai_timestamp = datetime.now().isoformat()

                    last_user_message = {
                        "content": user_query,
                        "timestamp": user_timestamp,
                        "messageId": request.message_id,
                    }

                    # Extract intent from AI response
                    thinking, extracted_intent = (
                        self._extract_thinking_and_intent_from_response(ai_response)
                    )

                    last_ai_response = {
                        "content": ai_response,
                        "timestamp": ai_timestamp,
                        "messageId": f"{request.message_id}_ai",
                        "metadata": {
                            "intent": extracted_intent,  # Use extracted intent from AI response
                            "language": "vietnamese",
                            "confidence": 0.9,
                            "responseTime": 3.0,
                            # Token analysis for Backend Analytics
                            "tokens": {
                                "input": len(user_query.split()),  # User input tokens
                                "output": len(ai_response.split()),  # AI output tokens
                                "total": len(user_query.split())
                                + len(ai_response.split()),
                            },
                            "characterCount": {
                                "input": len(user_query),
                                "output": len(ai_response),
                                "total": len(user_query) + len(ai_response),
                            },
                            # ❌ REMOVED: thinking duplicate - chỉ gửi trong webhook root level
                        },
                    }

                    # Get channel and user info from request
                    channel = (
                        self._get_webhook_channel_from_channel_type(request.channel)
                        if request.channel
                        else "chatdemo"
                    )
                    user_info = webhook_service._extract_user_info_for_webhook(request)

                    # Extract plugin data for CHAT_PLUGIN channel
                    plugin_id = None
                    customer_domain = None
                    if request.channel and request.channel.value == "chat-plugin":
                        plugin_id = getattr(request, "plugin_id", None)
                        customer_domain = getattr(request, "customer_domain", None)

                    # ⚠️ ONLY send conversation.updated for BACKEND channels
                    # Frontend channels (chatdemo, chat-plugin) already get ai.response.plugin.completed
                    if request.channel and request.channel.value not in [
                        "chatdemo",
                        "chat-plugin",
                    ]:
                        await webhook_service.notify_conversation_updated(
                            company_id=company_id,
                            conversation_id=request.session_id,
                            status="ACTIVE",
                            message_count=2,  # User + AI message
                            ended_at=None,
                            summary=f"Chat completed with {len(ai_response)} char response",
                            last_user_message=last_user_message,
                            last_ai_response=last_ai_response,
                            # NEW: Required fields for Backend validation
                            channel=channel,
                            intent=extracted_intent,
                            user_info=user_info,
                            plugin_id=plugin_id,
                            customer_domain=customer_domain,
                            # NEW: Full thinking data (same as conversation.created)
                            thinking=thinking,
                        )
                        logger.info(
                            "🔔 [WEBHOOK] ✅ Backend channel update webhook sent successfully"
                        )
                    else:
                        logger.info(
                            "🔔 [WEBHOOK] ⏭️ Skipping conversation.updated for frontend channel (ai.response.plugin.completed already sent)"
                        )

                except Exception as webhook_error:
                    logger.error(
                        f"❌ [WEBHOOK] Failed to send update webhook: {webhook_error}"
                    )

            logger.info(
                f"✅ [SAVE_COMPLETE] Processing completed for company: {company_id}"
            )

        except Exception as e:
            logger.error(f"❌ [SAVE_COMPLETE] Failed: {e}")
            logger.error(f"❌ [SAVE_COMPLETE] Error details: {str(e)}")

            logger.info(
                f"✅ [SAVE_COMPLETE] Full conversation save and webhook completed for {company_id}"
            )

        except Exception as e:
            logger.error(f"❌ [SAVE_COMPLETE] Complete conversation save failed: {e}")
            logger.error(f"❌ [SAVE_COMPLETE] Error details: {str(e)}")

    async def _verify_conversation_saved(
        self,
        user_id: str = None,
        device_id: str = None,
        session_id: str = None,
        expected_messages: int = 2,
    ) -> bool:
        """
        Verify that conversation was saved successfully by checking user_context retrieval
        Kiểm tra conversation đã được lưu thành công bằng cách test user_context retrieval
        """
        try:
            if not self.conversation_manager:
                logger.warning("⚠️ [VERIFY_SAVE] conversation_manager not available")
                return False

            # Try to retrieve messages using the same method as user_context
            messages = self.conversation_manager.get_optimized_messages_for_frontend(
                user_id=user_id,
                device_id=device_id,
                session_id=session_id,
                rag_context="",
                current_query="",
            )

            primary_identifier = user_id or device_id or session_id

            if messages and len(messages) >= expected_messages:
                logger.info(
                    f"✅ [VERIFY_SAVE] Conversation verified for {primary_identifier}: {len(messages)} messages"
                )
                logger.info(
                    f"✅ [VERIFY_SAVE] Latest message: {messages[-1].get('content', '')[:100]}..."
                )
                return True
            else:
                logger.warning(
                    f"⚠️ [VERIFY_SAVE] Expected {expected_messages} messages, found {len(messages) if messages else 0}"
                )
                return False

        except Exception as e:
            logger.error(f"❌ [VERIFY_SAVE] Verification failed: {e}")
            return False

    def _extract_company_name_from_context(self, company_context: str) -> str:
        """
        Extract company name from company context for personalized responses
        Trích xuất tên công ty từ context để cá nhân hóa phản hồi
        """
        if not company_context or not company_context.strip():
            return "công ty"

        try:
            # Since company_context has a fixed format starting with "Tên công ty: [NAME]"
            # Try to extract from the fixed format first
            lines = company_context.split("\n")
            for line in lines:
                line = line.strip()
                if line.startswith("Tên công ty:"):
                    # Extract company name after "Tên công ty: "
                    company_name = line.replace("Tên công ty:", "").strip()
                    if company_name and company_name != "Chưa có thông tin":
                        logger.info(
                            f"🏢 [EXTRACT] Found company name from format: '{company_name}'"
                        )
                        return company_name
                    break

            # Import regex here as fallback
            import re

            # Enhanced patterns to find company name in Vietnamese context
            patterns = [
                # Hotel patterns - specific for hotel case
                r"([A-Za-zÀ-ỹ\s]+)\s+(?:là\s+)?khách sạn",
                r"khách sạn\s+([A-Za-zÀ-ỹ\s]+)",
                r"hotel\s+([A-Za-zÀ-ỹ\s]+)",
                r"([A-Za-zÀ-ỹ\s]+)\s+hotel",
                # Standard company patterns
                r"công ty\s+(?:cp\s+|cổ phần\s+)?([a-zA-ZÀ-ỹ0-9\s]+)",
                r"tập đoàn\s+([a-zA-ZÀ-ỹ0-9\s]+)",
                # Brand name patterns
                r"([A-ZÀ-Ỹ][a-zà-ỹ]+(?:\s+[A-ZÀ-Ỹ][a-zà-ỹ]+)*)\s+(?:là|hoạt động|chuyên|tọa lạc)",
                r"([A-Z][A-Z][A-Z]+)",  # All caps abbreviations like AIA, VCB
                # Business name at start of sentence
                r"^([A-ZÀ-Ỹ][a-zA-ZÀ-ỹ\s]+?)\s+(?:là|hoạt động|chuyên|cung cấp|do)",
            ]

            for pattern in patterns:
                matches = re.findall(
                    pattern, company_context, re.IGNORECASE | re.MULTILINE
                )
                if matches:
                    company_name = matches[0].strip()

                    # Clean up common suffixes and prefixes
                    company_name = re.sub(
                        r"\s+(?:JSC|Ltd|Co|Inc|Corporation|Corp|CP|Cổ phần)\.?$",
                        "",
                        company_name,
                        flags=re.IGNORECASE,
                    )

                    # Remove common Vietnamese business words from the end
                    company_name = re.sub(
                        r"\s+(?:công ty|tập đoàn|doanh nghiệp)$",
                        "",
                        company_name,
                        flags=re.IGNORECASE,
                    )

                    # Validate length and content
                    if (
                        len(company_name) > 1
                        and len(company_name) < 80
                        and not company_name.lower()
                        in [
                            "khách sạn",
                            "hotel",
                            "công ty",
                            "tập đoàn",
                            "chưa có thông tin",
                        ]
                    ):
                        logger.info(
                            f"🏢 [EXTRACT] Extracted company name: '{company_name}'"
                        )
                        return company_name

            # Enhanced fallback: look for meaningful business names
            words = company_context.split()
            for i, word in enumerate(words):
                # Look for capitalized sequences that could be brand names
                if word.istitle() and len(word) > 2:
                    # Check if next word is also capitalized (compound name)
                    compound_name = word
                    j = i + 1
                    while j < len(words) and j < i + 4:  # Max 4 words
                        next_word = words[j]
                        if next_word.istitle() or next_word.isupper():
                            compound_name += " " + next_word
                            j += 1
                        else:
                            break

                    # Validate the compound name
                    if len(compound_name) >= 3 and len(compound_name) <= 50:
                        # Avoid common Vietnamese words
                        if compound_name.lower() not in [
                            "khách sạn",
                            "công ty",
                            "tập đoàn",
                            "doanh nghiệp",
                            "hotel",
                            "chưa có",
                            "thông tin",
                            "có thông",
                        ]:
                            logger.info(
                                f"🏢 [EXTRACT] Fallback compound name: '{compound_name}'"
                            )
                            return compound_name

            logger.warning(
                f"🏢 [EXTRACT] Could not extract company name, using default"
            )
            return "công ty"

        except Exception as e:
            logger.error(f"❌ [EXTRACT] Error extracting company name: {e}")
            return "công ty"

    def _extract_thinking_and_intent_from_response(self, ai_response: str):
        """
        Extract thinking and intent from AI response if available
        """
        try:
            import json
            import re

            # Try to parse structured JSON response if it exists
            json_match = re.search(r"```json\s*(\{.*?\})\s*```", ai_response, re.DOTALL)
            if json_match:
                try:
                    parsed_json = json.loads(json_match.group(1))
                    thinking = parsed_json.get("thinking", {})

                    # Extract intent from thinking section first, then fallback to root level
                    intent = "unknown"
                    if isinstance(thinking, dict) and "intent" in thinking:
                        intent = thinking["intent"]
                        logger.info(f"🎯 Extracted intent from thinking: {intent}")
                    elif "intent" in parsed_json:
                        intent = parsed_json["intent"]
                        logger.info(f"🎯 Extracted intent from root: {intent}")

                    # Map AI intent values to our enum values
                    intent_mapping = {
                        "SALES": "sales_inquiry",
                        "ASK_COMPANY_INFORMATION": "information",
                        "SUPPORT": "support",
                        "GENERAL_INFORMATION": "general_chat",
                        "INFORMATION": "information",
                        "PLACE_ORDER": "place_order",
                        # Keep existing mappings
                        "sales_inquiry": "sales_inquiry",
                        "information": "information",
                        "support": "support",
                        "general_chat": "general_chat",
                        "place_order": "place_order",
                    }

                    mapped_intent = intent_mapping.get(intent, "general_chat")
                    logger.info(f"🔄 Intent mapping: {intent} -> {mapped_intent}")

                    # Return thinking as JSON STRING (not dict) để avoid empty {}
                    thinking_json_str = json.dumps(thinking) if thinking else "{}"

                    return thinking_json_str, mapped_intent
                except Exception as e:
                    logger.warning(f"Failed to parse JSON in response: {e}")
                    pass

            # Alternative: Look for thinking section in response (fallback only)
            thinking_match = re.search(
                r"(?:thinking|phân tích):\s*(.+?)(?:\n\n|\nResponse:|$)",
                ai_response,
                re.IGNORECASE | re.DOTALL,
            )
            thinking_text = thinking_match.group(1).strip() if thinking_match else ""

            # Fallback intent detection ONLY if no JSON was found
            fallback_intent = "general_chat"
            response_lower = ai_response.lower()
            if any(
                word in response_lower
                for word in [
                    "sản phẩm",
                    "dịch vụ",
                    "product",
                    "service",
                    "thông tin",
                    "giá",
                ]
            ):
                fallback_intent = "information"
            elif any(
                word in response_lower for word in ["liên hệ", "contact", "gặp gỡ"]
            ):
                fallback_intent = "support"
            elif any(
                word in response_lower
                for word in ["mua", "đăng ký", "purchase", "buy", "đặt"]
            ):
                fallback_intent = "sales_inquiry"

            thinking_fallback = {
                "analysis": thinking_text,
                "confidence": 0.7,
                "detected_keywords": [],
                "source": "fallback_extraction",
            }

            # Return thinking as JSON string for consistency
            import json

            thinking_json_str = json.dumps(thinking_fallback)

            return thinking_json_str, fallback_intent

        except Exception as e:
            logger.warning(f"Failed to extract thinking/intent: {e}")
            return "{}", "general_chat"

    def _parse_ai_json_response(self, ai_response: str) -> Dict[str, Any]:
        """
        Parse AI JSON response to extract structured data
        Parse AI JSON response để trích xuất dữ liệu có cấu trúc
        """
        try:
            import json
            import re

            logger.info(
                f"🔍 [JSON_PARSE] Parsing AI response: {len(ai_response)} chars"
            )

            # Try to find JSON block in response
            json_match = re.search(
                r"```json\s*(\{.*?\})\s*```", ai_response, re.DOTALL | re.IGNORECASE
            )
            if json_match:
                json_str = json_match.group(1)
                logger.info(f"🔍 [JSON_PARSE] Found JSON block in markdown")
            else:
                # Try direct JSON parsing if response is pure JSON
                json_str = ai_response.strip()
                if not (json_str.startswith("{") and json_str.endswith("}")):
                    logger.warning(
                        f"🔍 [JSON_PARSE] No JSON structure found, creating fallback"
                    )
                    # Create fallback structure if AI didn't return proper JSON
                    return {
                        "thinking": {
                            "intent": "unknown",
                            "reasoning": "AI response was not in JSON format",
                            "language": "VIETNAMESE",
                        },
                        "intent": "unknown",
                        "language": "VIETNAMESE",
                        "final_answer": ai_response.strip(),
                    }

            # Parse the JSON
            parsed_data = json.loads(json_str)
            logger.info(f"✅ [JSON_PARSE] Successfully parsed JSON structure")

            # Extract intent from thinking object if available
            thinking_data = parsed_data.get("thinking", {})
            extracted_intent = "unknown"
            if isinstance(thinking_data, dict) and "intent" in thinking_data:
                extracted_intent = thinking_data["intent"]
            elif "intent" in parsed_data:
                extracted_intent = parsed_data["intent"]

            # Validate required fields and add defaults if missing
            result = {
                "thinking": thinking_data,
                "intent": extracted_intent,
                "language": parsed_data.get("language", "VIETNAMESE"),
                "final_answer": parsed_data.get("final_answer", ""),
            }

            # 🚨 IMPORTANT: Parse webhook_data if exists for order processing
            if "webhook_data" in parsed_data:
                result["webhook_data"] = parsed_data["webhook_data"]
                logger.info(f"🔍 [JSON_PARSE] Found webhook_data in AI response")

                # Debug webhook_data structure
                webhook_data = result["webhook_data"]
                if "order_data" in webhook_data:
                    order_data = webhook_data["order_data"]
                    is_complete = order_data.get("complete", False)
                    logger.info(
                        f"🛒 [JSON_PARSE] ORDER_DATA found - complete: {is_complete}"
                    )
                    if is_complete:
                        items_count = len(order_data.get("items", []))
                        customer_name = order_data.get("customer", {}).get("name", "")
                        logger.info(
                            f"🛒 [JSON_PARSE] ORDER ready - items: {items_count}, customer: {customer_name}"
                        )
                    else:
                        logger.info(
                            f"🛒 [JSON_PARSE] ORDER not complete - still collecting info"
                        )

                if "update_data" in webhook_data:
                    update_data = webhook_data["update_data"]
                    order_code = update_data.get("order_code", "")
                    logger.info(
                        f"🔄 [JSON_PARSE] UPDATE_DATA found - order_code: {order_code}"
                    )

                if "check_quantity_data" in webhook_data:
                    quantity_data = webhook_data["check_quantity_data"]
                    item_name = quantity_data.get("item_name", "")
                    customer_name = quantity_data.get("customer", {}).get("name", "")
                    logger.info(
                        f"📊 [JSON_PARSE] CHECK_QUANTITY_DATA found - item: {item_name}, customer: {customer_name}"
                    )
            else:
                logger.info(f"📭 [JSON_PARSE] No webhook_data found in AI response")

            # Ensure thinking has required sub-fields
            if "thinking" in result and isinstance(result["thinking"], dict):
                thinking = result["thinking"]
                thinking.setdefault("intent", result["intent"])
                thinking.setdefault("reasoning", "")
                thinking.setdefault("language", result["language"])
            else:
                result["thinking"] = {
                    "intent": result["intent"],
                    "reasoning": "",
                    "language": result["language"],
                }

            logger.info(
                f"🎯 [JSON_PARSE] Parsed - Intent: {result['intent']}, Language: {result['language']}"
            )
            logger.info(
                f"📝 [JSON_PARSE] Final answer length: {len(result['final_answer'])} chars"
            )

            return result

        except json.JSONDecodeError as e:
            logger.error(f"❌ [JSON_PARSE] JSON decode error: {e}")
            # Return fallback structure
            return {
                "thinking": {
                    "intent": "unknown",
                    "reasoning": f"JSON parsing failed: {str(e)}",
                    "language": "VIETNAMESE",
                },
                "intent": "unknown",
                "language": "VIETNAMESE",
                "final_answer": ai_response.strip(),
            }
        except Exception as e:
            logger.error(f"❌ [JSON_PARSE] Unexpected error: {e}")
            # Return fallback structure
            return {
                "thinking": {
                    "intent": "unknown",
                    "reasoning": f"Unexpected parsing error: {str(e)}",
                    "language": "VIETNAMESE",
                },
                "intent": "unknown",
                "language": "VIETNAMESE",
                "final_answer": ai_response.strip(),
            }


# ============================================================================
# SERVICE INSTANCE CREATION
# ============================================================================

# Create and export unified chat service instance for imports
unified_chat_service = UnifiedChatService()

logger.info("✅ UnifiedChatService instance created and exported")
