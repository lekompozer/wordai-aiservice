"""
Webhook Service for AI Service
Service webhook cho AI Service để gửi events về Backend
"""

import httpx
import json
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional
import os
from src.utils.logger import setup_logger

logger = setup_logger()


class WebhookService:
    """Service để gửi webhook events về Backend"""

    def __init__(self):
        # Detect environment (use ENV to match project standard)
        environment = os.getenv("ENV", "production").lower()
        port = os.getenv("PORT", "unknown")
        hostname = os.getenv("HOSTNAME", "unknown")

        logger.info(
            f"🔍 Environment detection - ENV: {environment}, PORT: {port}, HOSTNAME: {hostname}"
        )

        # Check if running in Docker or production environment
        is_production = (
            environment == "production"
            or os.getenv("PORT") == "8000"  # Production port
            or os.path.exists("/.dockerenv")  # Docker container
            or "agent8x" in os.getenv("HOSTNAME", "").lower()  # Production hostname
        )

        logger.info(
            f"🎯 Environment mode: {'PRODUCTION' if is_production else 'DEVELOPMENT'}"
        )

        if is_production:
            # Production: Remote backend - ALWAYS use HTTPS
            default_webhook_url = "https://api.agent8x.io.vn"
            logger.info("🌐 Detected PRODUCTION environment - using HTTPS webhook URL")

            # Override environment variable if it's HTTP in production
            env_webhook_url = os.getenv("BACKEND_WEBHOOK_URL", default_webhook_url)
            if env_webhook_url.startswith("http://"):
                logger.warning(
                    f"⚠️ Overriding HTTP webhook URL in production: {env_webhook_url} -> {default_webhook_url}"
                )
                self.webhook_url = default_webhook_url
            else:
                self.webhook_url = env_webhook_url
        else:
            # Development: Local backend
            default_webhook_url = "http://localhost:8001"
            logger.info("🏠 Detected DEVELOPMENT environment - using local webhook URL")
            self.webhook_url = os.getenv("BACKEND_WEBHOOK_URL", default_webhook_url)
        self.webhook_secret = os.getenv(
            "WEBHOOK_SECRET", "webhook-secret-for-signature"
        )

        logger.info(f"🎯 Final webhook configuration:")
        logger.info(f"   • URL: {self.webhook_url}")
        logger.info(
            f"   • Protocol: {'HTTPS ✅' if self.webhook_url.startswith('https://') else 'HTTP ⚠️'}"
        )
        logger.info(f"   • Secret: {'SET ✅' if self.webhook_secret else 'MISSING ❌'}")

        # HTTP client với timeout và retry
        self.client = httpx.AsyncClient(
            timeout=30.0,
            limits=httpx.Limits(max_keepalive_connections=10, max_connections=20),
        )

        # Webhook delivery settings
        self.max_retries = 3
        self.base_delay = 2  # seconds
        self.max_delay = 30  # seconds

        # Flag to disable webhooks for testing
        self.disabled = False  # ✅ ENABLED - backend endpoint confirmed working

        status = "ENABLED" if not self.disabled else "DISABLED"
        logger.info(f"🔗 Webhook service initialized: {self.webhook_url} ({status})")

    async def send_webhook_with_retry(
        self, endpoint: str, payload: Dict[str, Any], retry_count: int = None
    ) -> bool:
        """
        Send webhook with retry logic using simple secret authentication
        Gửi webhook với logic retry sử dụng simple secret authentication
        """
        if retry_count is None:
            retry_count = self.max_retries

        headers = {
            "Content-Type": "application/json",
            "User-Agent": "AI-Service-Webhook/1.0",
            "x-webhook-secret": self.webhook_secret,  # Fixed header name to lowercase
        }

        url = f"{self.webhook_url}{endpoint}"

        for attempt in range(retry_count):
            try:
                logger.info(
                    f"📤 Sending webhook to {endpoint} (attempt {attempt + 1}/{retry_count})"
                )
                logger.info(f"🔗 Full webhook URL: {url}")

                response = await self.client.post(url, json=payload, headers=headers)

                if response.status_code == 200:
                    logger.info(f"✅ Webhook delivered successfully: {endpoint}")
                    return True
                elif response.status_code in [400, 401, 403, 404]:
                    # Don't retry for client errors
                    logger.error(
                        f"❌ Webhook failed with client error {response.status_code}: {response.text}"
                    )
                    return False
                else:
                    logger.warning(
                        f"⚠️ Webhook failed with status {response.status_code}: {response.text}"
                    )

            except Exception as e:
                logger.error(f"❌ Webhook delivery error (attempt {attempt + 1}): {e}")

            # Wait before retry with exponential backoff
            if attempt < retry_count - 1:
                delay = min(self.base_delay * (2**attempt), self.max_delay)
                logger.info(f"⏳ Waiting {delay}s before retry...")
                await asyncio.sleep(delay)

        logger.error(
            f"❌ Webhook delivery failed after {retry_count} attempts: {endpoint}"
        )
        return False

    async def send_conversation_event(
        self,
        event_type: str,
        company_id: str,
        data: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Send conversation event to backend
        Gửi sự kiện conversation về backend
        """
        payload = {
            "event": event_type,
            "companyId": company_id,
            "data": data,
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata or {},
        }

        return await self.send_webhook_with_retry(
            "/api/webhooks/ai/conversation", payload  # Fixed: Removed trailing slash
        )

    async def notify_conversation_created(
        self,
        company_id: str,
        conversation_id: str,
        session_id: str,
        channel: str = "chatdemo",  # Use exact enum value
        intent: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
        user_info: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Notify backend about new conversation
        Thông báo backend về conversation mới
        """
        # Check if webhooks are disabled
        if self.disabled or (context and context.get("disable_webhooks", False)):
            logger.info(f"🔕 Webhooks disabled for conversation {conversation_id}")
            return True

        # Map intent to correct enum value if provided
        if intent:
            intent_mapping = {
                "general": "general_chat",  # Fix for AI returning "general"
                "information": "information",
                "sales_inquiry": "sales_inquiry",
                "support": "support",
                "general_chat": "general_chat",
                "place_order": "place_order",
                # Uppercase mappings
                "GENERAL": "general_chat",
                "INFORMATION": "information",
                "SALES": "sales_inquiry",
                "SUPPORT": "support",
                "PLACE_ORDER": "place_order",
                # Additional AI response mappings
                "SALES_INQUIRY": "sales_inquiry",
                "GENERAL_CHAT": "general_chat",
            }
            intent = intent_mapping.get(intent, "general_chat")

        data = {
            "conversationId": conversation_id,
            "sessionId": session_id,
            "channel": channel,
            "intent": intent,
            "startedAt": datetime.now().isoformat(),
            "metadata": metadata or {},
        }

        # Add user info if provided
        if user_info:
            data["userInfo"] = {
                "user_id": user_info.get("user_id"),
                "device_id": user_info.get("device_id"),
                "source": user_info.get("source", "chatdemo"),
                "name": user_info.get("name"),
                "email": user_info.get("email"),
            }
            logger.info(
                f"👤 Including user info in conversation webhook: {user_info.get('user_id', 'anonymous')}"
            )

        logger.info(f"🆕 Notifying conversation created: {conversation_id}")
        return await self.send_conversation_event(
            "conversation.created", company_id, data
        )

    async def notify_message_created(
        self,
        company_id: str,
        conversation_id: str,
        message_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
        user_info: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Notify backend about new message
        Thông báo backend về message mới
        """
        # Check if webhooks are disabled
        if self.disabled or (context and context.get("disable_webhooks", False)):
            logger.info(f"🔕 Webhooks disabled for message {message_id}")
            return True

        data = {
            "messageId": message_id,
            "conversationId": conversation_id,
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata or {},
        }

        # Add user info if provided
        if user_info:
            data["userInfo"] = {
                "user_id": user_info.get("user_id"),
                "device_id": user_info.get("device_id"),
                "source": user_info.get("source", "chatdemo"),
                "name": user_info.get("name"),
                "email": user_info.get("email"),
            }
            logger.info(
                f"👤 Including user info in message webhook: {user_info.get('user_id', 'anonymous')}"
            )

        logger.info(f"💬 Notifying message created: {message_id} ({role})")
        return await self.send_conversation_event("message.created", company_id, data)

    async def notify_conversation_updated(
        self,
        company_id: str,
        conversation_id: str,
        status: str,
        message_count: int,
        ended_at: Optional[datetime] = None,
        summary: Optional[str] = None,
        satisfaction_score: Optional[float] = None,
        last_user_message: Optional[Dict[str, Any]] = None,
        last_ai_response: Optional[Dict[str, Any]] = None,
        # NEW: Required fields for conversation creation fallback
        channel: str = "chatdemo",
        intent: Optional[str] = None,
        user_info: Optional[Dict[str, Any]] = None,
        plugin_id: Optional[str] = None,
        customer_domain: Optional[str] = None,
        # NEW: AI thinking data (same as conversation.created)
        thinking: Optional[str] = None,
    ) -> bool:
        """
        Notify backend about conversation update with message details
        Thông báo backend về cập nhật conversation kèm chi tiết tin nhắn
        """
        # Check if webhooks are disabled
        if self.disabled:
            logger.info(f"🔕 Webhooks disabled for conversation {conversation_id}")
            return True

        # Map intent to correct enum value if provided
        if intent:
            intent_mapping = {
                "general": "general_chat",  # Fix for AI returning "general"
                "information": "information",
                "sales_inquiry": "sales_inquiry",
                "support": "support",
                "general_chat": "general_chat",
                "place_order": "place_order",
                # Uppercase mappings
                "GENERAL": "general_chat",
                "INFORMATION": "information",
                "SALES": "sales_inquiry",
                "SUPPORT": "support",
                "PLACE_ORDER": "place_order",
                # Additional AI response mappings
                "SALES_INQUIRY": "sales_inquiry",
                "GENERAL_CHAT": "general_chat",
                "ASK_COMPANY_INFORMATION": "information",
            }
            intent = intent_mapping.get(intent, "general_chat")

        data = {
            "conversationId": conversation_id,
            "status": status,
            "messageCount": message_count,
            "endedAt": ended_at.isoformat() if ended_at else None,
            "summary": summary,
            "satisfactionScore": satisfaction_score,
            # Required fields for conversation creation fallback
            "channel": channel,
            "intent": intent or "general_chat",
        }

        # Add AI thinking data (same as conversation.created)
        if thinking:
            data["thinking"] = thinking

        # Add message details if provided
        if last_user_message:
            data["lastUserMessage"] = last_user_message

        if last_ai_response:
            # Ensure token analysis is properly structured for Backend Analytics
            if (
                "metadata" in last_ai_response
                and "tokens" in last_ai_response["metadata"]
            ):
                tokens = last_ai_response["metadata"]["tokens"]
                if isinstance(tokens, dict):
                    # Already enhanced structure - keep as is
                    data["lastAiResponse"] = last_ai_response
                else:
                    # Legacy simple token count - convert to enhanced structure
                    enhanced_ai_response = last_ai_response.copy()
                    enhanced_ai_response["metadata"]["tokens"] = {
                        "input": 0,  # Unknown for legacy data
                        "output": (
                            tokens
                            if isinstance(tokens, int)
                            else len(str(last_ai_response.get("content", "")).split())
                        ),
                        "total": (
                            tokens
                            if isinstance(tokens, int)
                            else len(str(last_ai_response.get("content", "")).split())
                        ),
                    }
                    data["lastAiResponse"] = enhanced_ai_response
            else:
                data["lastAiResponse"] = last_ai_response

        # Add user info if provided
        if user_info:
            data["userInfo"] = {
                "user_id": user_info.get("user_id"),
                "device_id": user_info.get("device_id"),
                "source": user_info.get("source", "chatdemo"),
                "name": user_info.get("name"),
                "email": user_info.get("email"),
            }

        # Add plugin data for CHAT_PLUGIN channel
        if channel == "chat-plugin":
            data["pluginId"] = plugin_id or "default-plugin"
            data["customerDomain"] = customer_domain or "unknown-domain"

        logger.info(f"🔄 Notifying conversation updated: {conversation_id} ({status})")
        return await self.send_conversation_event(
            "conversation.updated", company_id, data
        )

    async def notify_file_processed(
        self,
        company_id: str,
        file_id: str,
        status: str,
        extracted_items: int = 0,
        chunks_created: int = 0,
        processing_time: float = 0.0,
        error_message: Optional[str] = None,
    ) -> bool:
        """
        Notify backend about file processing result
        Thông báo backend về kết quả xử lý file
        """
        data = {
            "fileId": file_id,
            "status": status,
            "extractedItems": extracted_items,
            "chunksCreated": chunks_created,
            "processingTime": processing_time,
            "processedAt": datetime.now().isoformat(),
            "errorMessage": error_message,
        }

        logger.info(f"📄 Notifying file processed: {file_id} ({status})")
        return await self.send_conversation_event("file.processed", company_id, data)

    async def test_webhook_connection(self) -> bool:
        """
        Test webhook connection to backend
        Test kết nối webhook tới backend
        """
        test_payload = {
            "event": "conversation.updated",  # Use valid event type
            "companyId": "test-company-id",
            "data": {
                "conversationId": "test-conversation-id",
                "status": "ACTIVE",
                "messageCount": 1,
                "endedAt": None,
                "summary": "Webhook connection test",
                "satisfactionScore": None,
            },
            "timestamp": datetime.now().isoformat(),
        }

        logger.info("🧪 Testing webhook connection...")
        return await self.send_webhook_with_retry(
            "/api/webhooks/ai/conversation", test_payload, retry_count=1
        )

    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()
        logger.info("🔐 Webhook service closed")

    def _extract_user_info_for_webhook(self, request) -> Optional[Dict[str, Any]]:
        """
        Extract user info from UnifiedChatRequest for webhook
        Trích xuất thông tin user từ UnifiedChatRequest cho webhook
        """
        if not hasattr(request, "user_info") or not request.user_info:
            return None

        user_info = request.user_info

        # Extract basic user information
        extracted_info = {
            "user_id": getattr(user_info, "user_id", None),
            "device_id": getattr(user_info, "device_id", None),
            "source": getattr(user_info, "source", "chatdemo"),
            "name": getattr(user_info, "name", None),
            "email": getattr(user_info, "email", None),
        }

        # Handle UserSource enum
        if hasattr(extracted_info["source"], "value"):
            extracted_info["source"] = extracted_info["source"].value

        # Filter out None values to keep webhook payload clean
        extracted_info = {k: v for k, v in extracted_info.items() if v is not None}

        if extracted_info:
            logger.info(
                f"📋 Extracted user info for webhook: {list(extracted_info.keys())}"
            )

        return extracted_info if extracted_info else None

    async def notify_conversation_intent_updated(
        self,
        company_id: str,
        conversation_id: str,
        intent: str,
        confidence: Optional[float] = None,
        reasoning: Optional[str] = None,
        extracted_from_ai: bool = True,
    ) -> bool:
        """
        Notify backend about conversation intent update from AI response
        Thông báo backend về cập nhật intent từ AI response
        """
        if self.disabled:
            logger.info(f"🔕 Webhooks disabled for conversation {conversation_id}")
            return True

        data = {
            "conversationId": conversation_id,
            "intent": intent,
            "confidence": confidence,
            "reasoning": reasoning,
            "extractedFromAI": extracted_from_ai,
            "updatedAt": datetime.now().isoformat(),
        }

        logger.info(f"🎯 Notifying intent update: {conversation_id} -> {intent}")
        return await self.send_conversation_event(
            "conversation.intent_updated", company_id, data
        )

    def extract_intent_from_ai_response(
        self, ai_response: str
    ) -> Optional[Dict[str, Any]]:
        """
        Extract intent information from AI JSON response
        Trích xuất thông tin intent từ AI JSON response
        """
        try:
            # Try to parse JSON response
            if ai_response.strip().startswith("{") and ai_response.strip().endswith(
                "}"
            ):
                response_data = json.loads(ai_response)

                # Extract thinking.intent if available
                thinking = response_data.get("thinking", {})
                if thinking and isinstance(thinking, dict):
                    intent = thinking.get("intent")
                    reasoning = thinking.get("reasoning")
                    persona = thinking.get("persona")

                    if intent:
                        # Map AI intent values to backend expected values
                        intent_mapping = {
                            "INFORMATION": "information",
                            "SALES": "sales_inquiry",
                            "SUPPORT": "support",
                            "GENERAL": "general_chat",
                            "general": "general_chat",  # Fix for AI returning "general"
                            "information": "information",
                            "sales_inquiry": "sales_inquiry",
                            "support": "support",
                            "general_chat": "general_chat",
                        }

                        mapped_intent = intent_mapping.get(intent, "general_chat")

                        logger.info(
                            f"🎯 Extracted intent from AI: {intent} -> {mapped_intent}"
                        )

                        return {
                            "intent": mapped_intent,
                            "confidence": 0.9,  # AI confidence is high
                            "reasoning": reasoning,
                            "persona": persona,
                            "original_intent": intent,
                        }

        except (json.JSONDecodeError, KeyError, AttributeError) as e:
            logger.debug(f"Could not extract intent from AI response: {e}")

        return None

    async def update_conversation_intent_from_ai_response(
        self, company_id: str, conversation_id: str, full_ai_response: str
    ) -> bool:
        """
        Extract intent from full AI response and update conversation
        Trích xuất intent từ full AI response và cập nhật conversation
        """
        try:
            intent_info = self.extract_intent_from_ai_response(full_ai_response)

            if intent_info:
                success = await self.notify_conversation_intent_updated(
                    company_id=company_id,
                    conversation_id=conversation_id,
                    intent=intent_info["intent"],
                    confidence=intent_info.get("confidence"),
                    reasoning=intent_info.get("reasoning"),
                    extracted_from_ai=True,
                )

                if success:
                    logger.info(
                        f"✅ Intent updated from AI response: {conversation_id} -> {intent_info['intent']}"
                    )
                else:
                    logger.error(f"❌ Failed to update intent: {conversation_id}")

                return success
            else:
                logger.debug(
                    f"No intent found in AI response for conversation: {conversation_id}"
                )
                return True  # Not an error, just no intent detected

        except Exception as e:
            logger.error(f"❌ Error updating intent from AI response: {e}")
            return False

    async def send_update_order_webhook(
        self,
        order_code: str,
        update_data: Dict[str, Any],
        company_id: str,
        user_id: str = "ai_service",
    ) -> Dict[str, Any]:
        """
        Send UPDATE_ORDER webhook to backend and return response data
        Gửi webhook UPDATE_ORDER về backend để cập nhật đơn hàng và trả về response data
        """
        try:
            logger.info(
                f"🔄 [UPDATE_ORDER_WEBHOOK] Sending update for order: {order_code}"
            )

            # ✅ FIXED: Properly map AI response fields to backend expected format
            # Extract and transform fields from AI webhook_data.update_data
            webhook_payload = {
                "userId": user_id,
                "companyId": company_id,
                # Map AI fields to backend expected structure
                "updateType": update_data.get("updateType", "change_request"),
                "changes": update_data.get("changes", {}),
                "customer": update_data.get("customer", {}),
                "notes": update_data.get("notes", ""),
                # ✅ CRITICAL FIELDS: Keep order_code and complete for validation
                "orderCode": update_data.get(
                    "order_code", order_code
                ),  # For backend validation
                "complete": update_data.get("complete", False),  # AI completion status
            }

            # Add optional fields if present
            if update_data.get("summary"):
                webhook_payload["summary"] = update_data["summary"]

            if update_data.get("status"):
                webhook_payload["status"] = update_data["status"]

            if update_data.get("items"):
                webhook_payload["items"] = update_data["items"]

            if update_data.get("delivery"):
                webhook_payload["delivery"] = update_data["delivery"]

            if update_data.get("payment"):
                webhook_payload["payment"] = update_data["payment"]

            # Log the mapped payload structure
            logger.info(
                f"🔄 [UPDATE_ORDER_WEBHOOK] Mapped payload keys: {list(webhook_payload.keys())}"
            )
            logger.info(
                f"🔄 [UPDATE_ORDER_WEBHOOK] Order validation - Payload orderCode: {webhook_payload.get('orderCode')}, URL orderCode: {order_code}"
            )

            # Build endpoint with order code
            endpoint = f"/api/webhooks/orders/{order_code}/ai"

            logger.info(f"🔄 [UPDATE_ORDER_WEBHOOK] Endpoint: {endpoint}")
            logger.info(
                f"🔄 [UPDATE_ORDER_WEBHOOK] Final payload keys: {list(webhook_payload.keys())}"
            )

            # Use PUT method for updates and get response data
            response_data = await self._send_webhook_put_with_response(
                endpoint, webhook_payload
            )

            if response_data.get("success", False):
                logger.info(
                    f"✅ [UPDATE_ORDER_WEBHOOK] Successfully updated order: {order_code}"
                )
            else:
                logger.error(
                    f"❌ [UPDATE_ORDER_WEBHOOK] Failed to update order: {order_code}"
                )

            return response_data

        except Exception as e:
            logger.error(
                f"❌ [UPDATE_ORDER_WEBHOOK] Error sending update order webhook: {e}"
            )
            return {"success": False, "error": str(e)}

    async def send_check_quantity_webhook(
        self,
        quantity_data: Dict[str, Any],
        company_id: str,
        channel: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """
        Send CHECK_QUANTITY webhook to backend
        Gửi webhook CHECK_QUANTITY về backend để kiểm tra tồn kho

        ✅ ONLY AI FORMAT: Uses data from AI webhook_data.check_quantity_data
        """
        try:
            logger.info(
                f"📊 [CHECK_QUANTITY_WEBHOOK] Checking quantity for: {quantity_data.get('item_name', 'Unknown')}"
            )

            # Extract data from AI response (snake_case format only)
            item_name = quantity_data.get("item_name", "Unknown")
            customer_data = quantity_data.get("customer", {})
            specifications = quantity_data.get("specifications", {})

            # Extract requested quantity from specifications
            requested_quantity = specifications.get("quantity", 1)

            # Prepare payload for POST /api/webhooks/orders/check-quantity/ai
            webhook_payload = {
                "companyId": company_id,
                "customer": customer_data,
                "channel": channel or {"type": "chatdemo"},
                "metadata": {
                    "conversationId": quantity_data.get("conversationId"),
                    "intent": "check_quantity",
                    "requestedQuantity": requested_quantity,
                    "itemName": item_name,
                },
            }

            # Add product or service ID if available (from AI response)
            if quantity_data.get("product_id"):
                webhook_payload["productId"] = quantity_data["product_id"]
                logger.info(
                    f"📦 [CHECK_QUANTITY_WEBHOOK] Product ID: {quantity_data['product_id']}"
                )
            elif quantity_data.get("service_id"):
                webhook_payload["serviceId"] = quantity_data["service_id"]
                logger.info(
                    f"🛎️ [CHECK_QUANTITY_WEBHOOK] Service ID: {quantity_data['service_id']}"
                )
            else:
                # No specific ID, backend will search by item name
                logger.info(
                    f"🔍 [CHECK_QUANTITY_WEBHOOK] No ID, backend will search by name: {item_name}"
                )

            # Add other specifications (excluding quantity since we already extracted it)
            if specifications:
                specs_copy = specifications.copy()
                specs_copy.pop("quantity", None)  # Remove to avoid duplication
                webhook_payload["metadata"].update(specs_copy)

            # Add notes if available
            if quantity_data.get("notes"):
                webhook_payload["metadata"]["notes"] = quantity_data["notes"]

            endpoint = "/api/webhooks/orders/check-quantity/ai"

            logger.info(f"📊 [CHECK_QUANTITY_WEBHOOK] Endpoint: {endpoint}")
            logger.info(f"📊 [CHECK_QUANTITY_WEBHOOK] Item: {item_name}")
            logger.info(
                f"📊 [CHECK_QUANTITY_WEBHOOK] Quantity requested: {requested_quantity}"
            )

            # Send POST request and get response data
            response_data = await self._send_webhook_post_with_response(
                endpoint, webhook_payload
            )

            if response_data:
                logger.info(f"✅ [CHECK_QUANTITY_WEBHOOK] Quantity check completed")
                logger.info(
                    f"📊 [CHECK_QUANTITY_WEBHOOK] Available: {response_data.get('data', {}).get('available', False)}"
                )
                return response_data
            else:
                logger.error(f"❌ [CHECK_QUANTITY_WEBHOOK] Failed to check quantity")
                return {"success": False, "error": "Webhook request failed"}

        except Exception as e:
            logger.error(
                f"❌ [CHECK_QUANTITY_WEBHOOK] Error sending check quantity webhook: {e}"
            )
            return {"success": False, "error": str(e)}

    async def _send_webhook_put(self, endpoint: str, payload: Dict[str, Any]) -> bool:
        """
        Send PUT webhook request and return success status
        Gửi webhook request với method PUT và trả về trạng thái thành công
        """
        if self.disabled:
            logger.info(f"⚠️ Webhook disabled - would send PUT to {endpoint}")
            return True

        try:
            url = f"{self.webhook_url}{endpoint}"
            headers = {
                "Content-Type": "application/json",
                "x-webhook-secret": os.getenv("AI_WEBHOOK_SECRET", self.webhook_secret),
                "User-Agent": "Agent8x-AI-Service/1.0",
            }

            async with self.client as client:
                response = await client.put(
                    url, json=payload, headers=headers, timeout=30.0
                )

                if response.status_code == 200:
                    logger.info(f"✅ PUT webhook sent successfully to {endpoint}")
                    return True
                else:
                    logger.error(
                        f"❌ PUT webhook failed: {response.status_code} - {response.text}"
                    )
                    return False

        except Exception as e:
            logger.error(f"❌ PUT webhook error: {e}")
            return False

    async def _send_webhook_put_with_response(
        self, endpoint: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Send PUT webhook request and return response data
        Gửi webhook request với method PUT và trả về response data
        """
        if self.disabled:
            logger.info(f"⚠️ Webhook disabled - would send PUT to {endpoint}")
            return {
                "success": True,
                "data": {
                    "order": {
                        "orderId": "test-uuid",
                        "orderCode": "TEST001",
                        "status": "CONFIRMED",
                        "totalAmount": 1000000,
                        "formattedTotal": "1.000.000 ₫",
                    }
                },
            }

        try:
            url = f"{self.webhook_url}{endpoint}"
            headers = {
                "Content-Type": "application/json",
                "x-webhook-secret": os.getenv("AI_WEBHOOK_SECRET", self.webhook_secret),
                "User-Agent": "Agent8x-AI-Service/1.0",
            }

            async with self.client as client:
                response = await client.put(
                    url, json=payload, headers=headers, timeout=30.0
                )

                if response.status_code == 200:
                    logger.info(f"✅ PUT webhook sent successfully to {endpoint}")
                    return response.json()
                else:
                    logger.error(
                        f"❌ PUT webhook failed: {response.status_code} - {response.text}"
                    )
                    return {"success": False, "error": f"HTTP {response.status_code}"}

        except Exception as e:
            logger.error(f"❌ PUT webhook error: {e}")
            return {"success": False, "error": str(e)}

    async def _send_webhook_post_with_response(
        self, endpoint: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Send POST webhook request and return response data
        Gửi webhook request với method POST và trả về response data
        """
        if self.disabled:
            logger.info(f"⚠️ Webhook disabled - would send POST to {endpoint}")
            return {"success": True, "data": {"available": True, "quantity": 999}}

        try:
            url = f"{self.webhook_url}{endpoint}"
            headers = {
                "Content-Type": "application/json",
                "x-webhook-secret": os.getenv("AI_WEBHOOK_SECRET", self.webhook_secret),
                "User-Agent": "Agent8x-AI-Service/1.0",
            }

            async with self.client as client:
                response = await client.post(
                    url, json=payload, headers=headers, timeout=30.0
                )

                if response.status_code == 200:
                    logger.info(f"✅ POST webhook sent successfully to {endpoint}")
                    return response.json()
                else:
                    logger.error(
                        f"❌ POST webhook failed: {response.status_code} - {response.text}"
                    )
                    return {"success": False, "error": f"HTTP {response.status_code}"}

        except Exception as e:
            logger.error(f"❌ POST webhook error: {e}")
            return {"success": False, "error": str(e)}


# Create singleton instance
webhook_service = WebhookService()


# Helper functions for easy import
async def send_conversation_created(
    company_id: str,
    conversation_id: str,
    session_id: str,
    channel: str = "chatdemo",  # Use exact enum value
    intent: str = None,
    metadata: Dict[str, Any] = None,
    user_info: Dict[str, Any] = None,
):
    """Shortcut function for conversation created"""
    return await webhook_service.notify_conversation_created(
        company_id,
        conversation_id,
        session_id,
        channel,
        intent,
        metadata,
        None,
        user_info,
    )


async def send_message_created(
    company_id: str,
    conversation_id: str,
    message_id: str,
    role: str,
    content: str,
    metadata: Dict[str, Any] = None,
    user_info: Dict[str, Any] = None,
):
    """Shortcut function for message created"""
    return await webhook_service.notify_message_created(
        company_id,
        conversation_id,
        message_id,
        role,
        content,
        metadata,
        None,
        user_info,
    )


async def send_conversation_updated(
    company_id: str,
    conversation_id: str,
    status: str,
    message_count: int,
    ended_at: datetime = None,
    summary: str = None,
    satisfaction_score: float = None,
    # NEW: Additional fields for conversation updates
    channel: str = "chatdemo",
    intent: str = None,
    user_info: Dict[str, Any] = None,
    plugin_id: str = None,
    customer_domain: str = None,
    thinking: str = None,
):
    """Shortcut function for conversation updated"""
    return await webhook_service.notify_conversation_updated(
        company_id,
        conversation_id,
        status,
        message_count,
        ended_at,
        summary,
        satisfaction_score,
        None,  # last_user_message
        None,  # last_ai_response
        channel,
        intent,
        user_info,
        plugin_id,
        customer_domain,
        thinking,
    )


async def send_file_processed(
    company_id: str,
    file_id: str,
    status: str,
    extracted_items: int = 0,
    chunks_created: int = 0,
    processing_time: float = 0.0,
    error_message: str = None,
):
    """Shortcut function for file processed"""
    return await webhook_service.notify_file_processed(
        company_id,
        file_id,
        status,
        extracted_items,
        chunks_created,
        processing_time,
        error_message,
    )


async def send_conversation_intent_updated(
    company_id: str,
    conversation_id: str,
    intent: str,
    confidence: Optional[float] = None,
    reasoning: Optional[str] = None,
    extracted_from_ai: bool = True,
):
    """Shortcut function for conversation intent updated"""
    return await webhook_service.notify_conversation_intent_updated(
        company_id,
        conversation_id,
        intent,
        confidence,
        reasoning,
        extracted_from_ai,
    )
