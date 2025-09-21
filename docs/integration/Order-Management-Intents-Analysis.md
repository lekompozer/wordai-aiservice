# Order Management Intents - Implementation Analysis
# Phân Tích Triển Khai Các Intent Quản Lý Đơn Hàng

## 📋 Tổng Quan

Tài liệu này phân tích chi tiết việc triển khai 3 intents quản lý đơn hàng trong AI chatbot system:
1. **PLACE_ORDER** (đã có partial implementation)
2. **UPDATE_ORDER** (cần implement mới)
3. **CHECK_QUANTITY** (cần implement mới)

## 🔍 Current System Analysis

### ✅ Hiện Tại Đã Có (PLACE_ORDER)

#### **1. Models & Enums**
```python
# src/models/unified_models.py
class ChatIntent(str, Enum):
    INFORMATION = "information"
    SALES_INQUIRY = "sales_inquiry"
    SUPPORT = "support"
    GENERAL_CHAT = "general_chat"
    PLACE_ORDER = "place_order"  # ✅ Đã có
```

#### **2. Service Implementation**
```python
# src/services/unified_chat_service.py - Đã có các methods:
✅ _is_order_confirmation_complete()
✅ _extract_order_data_from_conversation()
✅ _send_order_created_webhook()
✅ _calculate_order_totals()
```

#### **3. AI Prompt Support**
- ✅ Đã update prompt hỗ trợ 5 intents bao gồm PLACE_ORDER
- ✅ Có workflow thu thập thông tin multi-turn conversation
- ✅ Có order completion detection

#### **4. Webhook Integration**
- ✅ Endpoint: `POST /api/webhooks/orders/ai` (tạo đơn hàng mới)
- ✅ JSON payload structure đã định nghĩa
- ✅ Backend response handling

### ❌ Thiếu & Cần Implement

#### **1. Missing Intents**
```python
# Cần thêm vào ChatIntent enum:
UPDATE_ORDER = "update_order"      # Cập nhật đơn hàng
CHECK_QUANTITY = "check_quantity"  # Kiểm tra tồn kho
```

#### **2. Missing Service Methods**
- ❌ Order update detection & processing
- ❌ Quantity check request processing
- ❌ Order code validation
- ❌ Update data extraction from conversation

#### **3. Missing Webhook Endpoints**
- ❌ `PUT /api/webhooks/orders/{orderCode}/ai` (cập nhật)
- ❌ `POST /api/webhooks/orders/check-quantity/ai` (kiểm tra)

## 🎯 Implementation Plan

### Phase 1: Models & Enums Update

#### **1.1 Update ChatIntent Enum**
```python
# File: src/models/unified_models.py
class ChatIntent(str, Enum):
    INFORMATION = "information"
    SALES_INQUIRY = "sales_inquiry"
    SUPPORT = "support"
    GENERAL_CHAT = "general_chat"
    PLACE_ORDER = "place_order"     # ✅ Existing
    UPDATE_ORDER = "update_order"   # 🆕 New
    CHECK_QUANTITY = "check_quantity" # 🆕 New
```

#### **1.2 Create New Model Classes**
```python
# File: src/models/order_models.py (new file)
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class OrderUpdateRequest(BaseModel):
    """Model cho update order request"""
    order_code: str = Field(..., description="Mã đơn hàng cần update")
    products: Optional[List[Dict]] = Field(None, description="Sản phẩm cần thay đổi")
    customer: Optional[Dict] = Field(None, description="Thông tin khách hàng update")
    payment: Optional[Dict] = Field(None, description="Thông tin thanh toán update")
    delivery: Optional[Dict] = Field(None, description="Thông tin giao hàng update")
    notes: Optional[str] = Field(None, description="Ghi chú thay đổi")

class QuantityCheckRequest(BaseModel):
    """Model cho quantity check request"""
    products: List[Dict] = Field(..., description="Danh sách sản phẩm cần check")
    customer_contact: Dict = Field(..., description="Thông tin liên hệ khách hàng")
    contact_method: str = Field(..., description="Phương thức liên hệ: email/sms")
    notes: Optional[str] = Field(None, description="Ghi chú yêu cầu")
```

### Phase 2: AI Prompt Enhancement

#### **2.1 Enhanced System Prompt**
```python
# File: src/services/unified_chat_service.py
def _build_unified_prompt_with_intent(self, ...):
    system_prompt = f"""
BẠN CÓ 7 CHỨC NĂNG CHÍNH:
1. INFORMATION: Cung cấp thông tin công ty/sản phẩm/dịch vụ
2. SALES_INQUIRY: Tư vấn và hỗ trợ quyết định mua hàng
3. SUPPORT: Hỗ trợ kỹ thuật và xử lý khiếu nại
4. GENERAL_CHAT: Trò chuyện thông thường và tương tác
5. PLACE_ORDER: Thu thập thông tin để tạo đơn hàng mới
6. UPDATE_ORDER: Thu thập thông tin để cập nhật đơn hàng hiện có
7. CHECK_QUANTITY: Thu thập thông tin để kiểm tra tồn kho/khả dụng

QUAN TRỌNG cho ORDER INTENTS:

UPDATE_ORDER Flow:
- Yêu cầu mã đơn hàng (order code) từ email khách hàng
- Thu thập thông tin cần thay đổi: sản phẩm, số lượng, thông tin khách hàng, thanh toán, giao hàng
- Xác nhận thay đổi trước khi gửi webhook

CHECK_QUANTITY Flow:
- Thu thập danh sách sản phẩm cần kiểm tra tồn kho
- Thu thập thông tin liên hệ: tên, email/sdt
- Chọn phương thức thông báo: email hoặc SMS
- Thông báo khách hàng sẽ được liên hệ về kết quả
"""
```

#### **2.2 Intent Detection Patterns**
```python
# Enhanced intent detection patterns
UPDATE_ORDER_PATTERNS = [
    "cập nhật đơn hàng", "thay đổi đơn hàng", "sửa đơn hàng",
    "update order", "change order", "modify order",
    "có mã đơn hàng", "order code", "mã ORD"
]

CHECK_QUANTITY_PATTERNS = [
    "kiểm tra tồn kho", "còn hàng không", "check quantity",
    "available stock", "hàng có sẵn", "khả dụng",
    "số lượng hàng", "inventory check"
]
```

### Phase 3: Service Methods Implementation

#### **3.1 Order Update Methods**
```python
# File: src/services/unified_chat_service.py

async def _is_update_order_confirmation_complete(
    self,
    parsed_response: Dict[str, Any],
    user_message: str
) -> bool:
    """Kiểm tra user đã confirm update order và có đủ thông tin"""
    try:
        # Check confirmation keywords
        confirmation_keywords = [
            "đồng ý cập nhật", "xác nhận thay đổi", "ok", "được",
            "confirm update", "yes", "agree to change"
        ]

        user_message_lower = user_message.lower()
        has_confirmation = any(keyword in user_message_lower for keyword in confirmation_keywords)

        # Check AI mentions update completion
        final_answer = parsed_response.get("final_answer", "").lower()
        update_completion_phrases = [
            "cập nhật đơn hàng thành công", "order updated successfully",
            "thay đổi đã được xác nhận", "đã cập nhật thông tin"
        ]

        has_update_completion = any(phrase in final_answer for phrase in update_completion_phrases)

        logger.info(f"🔄 [UPDATE_CHECK] User confirmation: {has_confirmation}")
        logger.info(f"🔄 [UPDATE_CHECK] AI mentions completion: {has_update_completion}")

        return has_confirmation and has_update_completion

    except Exception as e:
        logger.error(f"❌ [UPDATE_CHECK] Error: {e}")
        return False

async def _extract_update_order_data_from_conversation(
    self,
    request: UnifiedChatRequest,
    parsed_response: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """Extract order update information từ conversation history"""
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
                current_query=""
            )
            conversation_history = [f"{msg.role}: {msg.content}" for msg in history]

        # Add current exchange
        conversation_history.append(f"user: {request.message}")
        conversation_history.append(f"assistant: {parsed_response.get('final_answer', '')}")

        conversation_text = "\n".join(conversation_history[-10:])

        # AI extraction prompt for order updates
        extraction_prompt = f"""
Từ cuộc hội thoại sau, trích xuất thông tin CẬP NHẬT đơn hàng thành JSON format:

{conversation_text}

Trả về JSON với format:
{{
  "order_code": "ORD20250817001",
  "changes": {{
    "products": [
      {{
        "name": "tên sản phẩm",
        "quantity": số_lượng_mới,
        "notes": "ghi chú thay đổi"
      }}
    ],
    "customer": {{
      "name": "tên mới",
      "phone": "sdt mới",
      "email": "email mới",
      "address": "địa chỉ mới"
    }},
    "payment": {{
      "method": "phương thức thanh toán mới",
      "timing": "thời điểm thanh toán mới"
    }},
    "delivery": {{
      "method": "phương thức giao hàng mới",
      "address": "địa chỉ giao hàng mới",
      "phone": "sdt nhận hàng mới",
      "notes": "ghi chú giao hàng mới"
    }}
  }},
  "update_reason": "lý do thay đổi",
  "notes": "ghi chú khác"
}}

CHỈ trả về những trường có thay đổi. Nếu không có thay đổi thì không trả về trường đó.
Chỉ trả về JSON, không có text khác.
"""

        # Call AI to extract update data
        extraction_response = await self.ai_manager.stream_response(
            question=extraction_prompt,
            session_id=session_id,
            provider="cerebras"
        )

        full_extraction = ""
        async for chunk in extraction_response:
            full_extraction += chunk

        # Parse JSON from AI response
        json_match = re.search(r'\{.*\}', full_extraction, re.DOTALL)
        if json_match:
            update_data = json.loads(json_match.group(0))
            logger.info("🔄 [UPDATE_EXTRACTION] Successfully extracted update data")
            return update_data
        else:
            logger.warning("🔄 [UPDATE_EXTRACTION] No valid JSON found")
            return None

    except Exception as e:
        logger.error(f"❌ [UPDATE_EXTRACTION] Failed: {e}")
        return None

async def _send_update_order_webhook(
    self,
    request: UnifiedChatRequest,
    update_data: Dict[str, Any],
    processing_start_time: float
) -> bool:
    """Send order update webhook to backend"""
    try:
        import os
        import httpx

        order_code = update_data.get("order_code")
        if not order_code:
            logger.error("❌ [UPDATE_WEBHOOK] Missing order_code")
            return False

        # Build webhook payload for order update
        webhook_payload = {
            "companyId": request.company_id,
            "timestamp": datetime.now().isoformat(),
            "data": {
                "orderCode": order_code,
                "conversationId": getattr(request, "conversation_id", request.session_id),
                "sessionId": request.session_id,
                "userId": request.user_info.user_id if request.user_info else None,

                # Changes data
                "changes": update_data.get("changes", {}),
                "updateReason": update_data.get("update_reason", "Customer requested change"),
                "notes": update_data.get("notes", ""),

                # Channel Information
                "channel": {
                    "type": request.channel.value if request.channel else "chatdemo",
                    "pluginId": request.plugin_id,
                    "customerDomain": request.customer_domain
                },

                # Metadata
                "metadata": {
                    "source": "ai_conversation",
                    "aiModel": "qwen-3-235b-a22b-instruct-2507",
                    "processingTime": int((time.time() - processing_start_time) * 1000) if processing_start_time else 0,
                    "updatedAt": datetime.now().isoformat()
                }
            }
        }

        # Send webhook
        backend_url = os.getenv("BACKEND_WEBHOOK_URL", "http://localhost:8001")
        endpoint = f"{backend_url}/api/webhooks/orders/{order_code}/ai"

        webhook_secret = os.getenv("AI_WEBHOOK_SECRET", "ai-webhook-secret")
        headers = {
            "Content-Type": "application/json",
            "x-webhook-secret": webhook_secret,
            "User-Agent": "Agent8x-AI-Service/1.0"
        }

        async with httpx.AsyncClient() as client:
            response = await client.put(
                endpoint,
                json=webhook_payload,
                headers=headers,
                timeout=30.0
            )

            if response.status_code == 200:
                logger.info(f"✅ [UPDATE_WEBHOOK] Successfully sent for {order_code}")
                return True
            else:
                logger.error(f"❌ [UPDATE_WEBHOOK] Backend returned {response.status_code}: {response.text}")
                return False

    except Exception as e:
        logger.error(f"❌ [UPDATE_WEBHOOK] Failed: {e}")
        return False
```

#### **3.2 Quantity Check Methods**
```python
async def _is_quantity_check_confirmation_complete(
    self,
    parsed_response: Dict[str, Any],
    user_message: str
) -> bool:
    """Kiểm tra user đã confirm quantity check request"""
    try:
        confirmation_keywords = [
            "đồng ý kiểm tra", "ok kiểm tra", "xác nhận check",
            "confirm check", "yes check", "check giúp tôi"
        ]

        user_message_lower = user_message.lower()
        has_confirmation = any(keyword in user_message_lower for keyword in confirmation_keywords)

        # Check AI mentions check request completion
        final_answer = parsed_response.get("final_answer", "").lower()
        check_completion_phrases = [
            "yêu cầu kiểm tra đã được gửi", "sẽ kiểm tra và thông báo",
            "request sent successfully", "will check and notify"
        ]

        has_check_completion = any(phrase in final_answer for phrase in check_completion_phrases)

        logger.info(f"📋 [QUANTITY_CHECK] User confirmation: {has_confirmation}")
        logger.info(f"📋 [QUANTITY_CHECK] AI mentions completion: {has_check_completion}")

        return has_confirmation and has_check_completion

    except Exception as e:
        logger.error(f"❌ [QUANTITY_CHECK] Error: {e}")
        return False

async def _extract_quantity_check_data_from_conversation(
    self,
    request: UnifiedChatRequest,
    parsed_response: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """Extract quantity check information từ conversation"""
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
                current_query=""
            )
            conversation_history = [f"{msg.role}: {msg.content}" for msg in history]

        conversation_history.append(f"user: {request.message}")
        conversation_history.append(f"assistant: {parsed_response.get('final_answer', '')}")

        conversation_text = "\n".join(conversation_history[-10:])

        # AI extraction prompt for quantity checks
        extraction_prompt = f"""
Từ cuộc hội thoại sau, trích xuất thông tin KIỂM TRA TỒN KHO thành JSON format:

{conversation_text}

Trả về JSON với format:
{{
  "products": [
    {{
      "name": "tên sản phẩm",
      "quantity_needed": số_lượng_cần,
      "specifications": "thông số kỹ thuật nếu có"
    }}
  ],
  "customer_contact": {{
    "name": "tên khách hàng",
    "phone": "số điện thoại",
    "email": "email"
  }},
  "contact_method": "email hoặc sms",
  "urgency": "normal hoặc urgent",
  "notes": "ghi chú yêu cầu kiểm tra"
}}

Chỉ trả về JSON, không có text khác.
"""

        # Call AI to extract quantity check data
        extraction_response = await self.ai_manager.stream_response(
            question=extraction_prompt,
            session_id=session_id,
            provider="cerebras"
        )

        full_extraction = ""
        async for chunk in extraction_response:
            full_extraction += chunk

        # Parse JSON from AI response
        json_match = re.search(r'\{.*\}', full_extraction, re.DOTALL)
        if json_match:
            check_data = json.loads(json_match.group(0))
            logger.info("📋 [QUANTITY_EXTRACTION] Successfully extracted check data")
            return check_data
        else:
            logger.warning("📋 [QUANTITY_EXTRACTION] No valid JSON found")
            return None

    except Exception as e:
        logger.error(f"❌ [QUANTITY_EXTRACTION] Failed: {e}")
        return None

async def _send_quantity_check_webhook(
    self,
    request: UnifiedChatRequest,
    check_data: Dict[str, Any],
    processing_start_time: float
) -> bool:
    """Send quantity check webhook to backend"""
    try:
        import os
        import httpx

        # Build webhook payload for quantity check
        webhook_payload = {
            "companyId": request.company_id,
            "timestamp": datetime.now().isoformat(),
            "data": {
                "conversationId": getattr(request, "conversation_id", request.session_id),
                "sessionId": request.session_id,
                "userId": request.user_info.user_id if request.user_info else None,

                # Check request data
                "products": check_data.get("products", []),
                "customer_contact": check_data.get("customer_contact", {}),
                "contact_method": check_data.get("contact_method", "email"),
                "urgency": check_data.get("urgency", "normal"),
                "notes": check_data.get("notes", ""),

                # Channel Information
                "channel": {
                    "type": request.channel.value if request.channel else "chatdemo",
                    "pluginId": request.plugin_id,
                    "customerDomain": request.customer_domain
                },

                # Metadata
                "metadata": {
                    "source": "ai_conversation",
                    "aiModel": "qwen-3-235b-a22b-instruct-2507",
                    "processingTime": int((time.time() - processing_start_time) * 1000) if processing_start_time else 0,
                    "requestedAt": datetime.now().isoformat()
                }
            }
        }

        # Send webhook
        backend_url = os.getenv("BACKEND_WEBHOOK_URL", "http://localhost:8001")
        endpoint = f"{backend_url}/api/webhooks/orders/check-quantity/ai"

        webhook_secret = os.getenv("AI_WEBHOOK_SECRET", "ai-webhook-secret")
        headers = {
            "Content-Type": "application/json",
            "x-webhook-secret": webhook_secret,
            "User-Agent": "Agent8x-AI-Service/1.0"
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                endpoint,
                json=webhook_payload,
                headers=headers,
                timeout=30.0
            )

            if response.status_code == 200:
                logger.info(f"✅ [QUANTITY_WEBHOOK] Successfully sent quantity check request")
                return True
            else:
                logger.error(f"❌ [QUANTITY_WEBHOOK] Backend returned {response.status_code}: {response.text}")
                return False

    except Exception as e:
        logger.error(f"❌ [QUANTITY_WEBHOOK] Failed: {e}")
        return False
```

### Phase 4: Integration into Main Flow

#### **4.1 Enhanced _send_response_to_backend Method**
```python
# File: src/services/unified_chat_service.py - Update existing method

async def _send_response_to_backend(
    self,
    request: UnifiedChatRequest,
    ai_response: str,
    channel: ChannelType,
    parsed_response: Dict[str, Any] = None,
    processing_start_time: float = None,
):
    try:
        # ... existing code ...

        # 🆕 Enhanced order intent processing
        detected_intent = parsed_response.get("thinking", {}).get("intent")

        # PLACE_ORDER handling (existing)
        if detected_intent == "place_order":
            if self._is_order_confirmation_complete(parsed_response, request.message):
                order_data = await self._extract_order_data_from_conversation(request, parsed_response)
                if order_data:
                    webhook_sent = await self._send_order_created_webhook(request, order_data, processing_start_time)
                    if webhook_sent:
                        logger.info("✅ [ORDER] Successfully processed and sent webhook")

        # 🆕 UPDATE_ORDER handling (new)
        elif detected_intent == "update_order":
            if self._is_update_order_confirmation_complete(parsed_response, request.message):
                update_data = await self._extract_update_order_data_from_conversation(request, parsed_response)
                if update_data:
                    webhook_sent = await self._send_update_order_webhook(request, update_data, processing_start_time)
                    if webhook_sent:
                        logger.info("✅ [UPDATE_ORDER] Successfully processed and sent webhook")

        # 🆕 CHECK_QUANTITY handling (new)
        elif detected_intent == "check_quantity":
            if self._is_quantity_check_confirmation_complete(parsed_response, request.message):
                check_data = await self._extract_quantity_check_data_from_conversation(request, parsed_response)
                if check_data:
                    webhook_sent = await self._send_quantity_check_webhook(request, check_data, processing_start_time)
                    if webhook_sent:
                        logger.info("✅ [CHECK_QUANTITY] Successfully processed and sent webhook")

        # Continue with existing webhook processing...
        # ... rest of method unchanged ...

    except Exception as e:
        logger.error(f"❌ [BACKEND_ROUTING] Failed: {e}")
```

## 📋 Implementation Checklist

### ✅ Phase 1: Models & Enums (Priority: HIGH)
- [ ] Update `ChatIntent` enum với 2 intents mới
- [ ] Tạo file `order_models.py` với các model classes
- [ ] Update import statements trong service files

### ✅ Phase 2: AI Prompt Enhancement (Priority: HIGH)
- [ ] Update system prompt hỗ trợ 7 intents
- [ ] Thêm intent detection patterns cho UPDATE_ORDER & CHECK_QUANTITY
- [ ] Update prompt instructions cho từng intent workflow

### ✅ Phase 3: Service Methods (Priority: HIGH)
- [ ] Implement order update methods (4 methods)
- [ ] Implement quantity check methods (3 methods)
- [ ] Add validation & error handling
- [ ] Add comprehensive logging

### ✅ Phase 4: Integration (Priority: MEDIUM)
- [ ] Update `_send_response_to_backend()` method
- [ ] Add intent routing logic
- [ ] Test integration với existing PLACE_ORDER flow

### ✅ Phase 5: Testing (Priority: MEDIUM)
- [ ] Unit tests cho new methods
- [ ] Integration tests cho complete flows
- [ ] Manual testing với real conversations
- [ ] Error scenario testing

## 🔗 Backend Requirements

### **Required Webhook Endpoints**
Backend cần implement 2 endpoints mới:

```
PUT /api/webhooks/orders/{orderCode}/ai
- Update existing order
- Validate order exists
- Send notification emails

POST /api/webhooks/orders/check-quantity/ai
- Process quantity check request
- Check inventory/availability
- Send result via email/SMS
```

### **Response Formats Expected**
```json
// Update Order Response
{
  "success": true,
  "message": "Order updated successfully",
  "data": {
    "orderCode": "ORD20250817001",
    "updatedFields": ["products", "delivery"],
    "notifications": {
      "customerEmailSent": true
    }
  }
}

// Quantity Check Response
{
  "success": true,
  "message": "Quantity check request received",
  "data": {
    "checkId": "CHK20250817001",
    "estimatedResponseTime": "2-4 hours",
    "notificationMethod": "email"
  }
}
```

## 📊 Expected User Flows

### **UPDATE_ORDER Flow**
```
User: "Tôi muốn thay đổi đơn hàng ORD20250817001"
AI: "Cho tôi biết bạn muốn thay đổi gì trong đơn hàng?"
User: "Thay đổi số lượng từ 2 thành 5 sản phẩm"
AI: "Xác nhận thay đổi: ORD20250817001 - Tăng số lượng từ 2 lên 5. Đồng ý?"
User: "Đồng ý"
AI: "Đơn hàng đã được cập nhật thành công! Email xác nhận đã được gửi."
→ Webhook sent to PUT /api/webhooks/orders/ORD20250817001/ai
```

### **CHECK_QUANTITY Flow**
```
User: "Kiểm tra tồn kho sản phẩm ABC"
AI: "Bạn cần kiểm tra số lượng bao nhiêu sản phẩm ABC?"
User: "Cần 100 cái"
AI: "Để kiểm tra, tôi cần thông tin liên hệ. Cho tôi tên và email/sdt?"
User: "Tên Nguyễn A, email test@email.com"
AI: "Xác nhận: Kiểm tra 100 sản phẩm ABC, thông báo qua test@email.com?"
User: "Đồng ý"
AI: "Yêu cầu đã được gửi! Chúng tôi sẽ kiểm tra và thông báo trong 2-4h."
→ Webhook sent to POST /api/webhooks/orders/check-quantity/ai
```

## 🚀 Next Steps

1. **Review & Approval**: Technical design review với team
2. **Backend Coordination**: Đảm bảo Backend ready với endpoints
3. **Implementation Order**:
   - Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5
4. **Testing Strategy**: Parallel testing với backend development
5. **Documentation**: Update API docs và user guides

---

**📝 Implementation Priority**: HIGH - Critical for complete order management system
**🕐 Estimated Timeline**: 2-3 weeks full implementation
**👥 Dependencies**: Backend webhook endpoints development

*Document created: 18/08/2025 - Implementation Analysis Complete*
