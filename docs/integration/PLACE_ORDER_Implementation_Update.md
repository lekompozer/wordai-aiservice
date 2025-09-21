# Cập Nhật PLACE_ORDER Intent - Implementation Plan & Progress

## 📋 TỔNG QUAN THỰC HIỆN

Tài liệu này mô tả việc sửa đổi và cập nhật implementation hiện tại cho PLACE_ORDER intent để phù hợp với backend API requirements và triển khai dual webhook approach.

## ✅ ĐÃ THỰC HIỆN

### 1. Sửa Lỗi Endpoint Webhook Hiện Tại

**BEFORE (Sai):**
```python
endpoint = f"{backend_url}/api/webhooks/ai/conversation"
headers = {
    "X-Webhook-Secret": webhook_secret,  # Sai header name
}
```

**AFTER (Đúng):**
```python
endpoint = f"{backend_url}/api/webhooks/orders/ai"  # Correct endpoint
headers = {
    "x-webhook-secret": webhook_secret,  # Correct header name
}
```

### 2. Cập Nhật JSON Payload Structure

**BEFORE (Cấu trúc cũ):**
```json
{
  "event": "order.created",
  "companyId": "...",
  "data": {
    "orderId": "order_...",
    "orderType": "ORDER",
    "status": "PENDING",
    // ... cấu trúc cũ không đúng với backend API
  }
}
```

**AFTER (Cấu trúc mới theo API_Webhook_BE.md):**
```json
{
  "conversationId": "conv_id",
  "companyId": "company_id",
  "leadId": "user_id",
  "userId": "ai_service_chatbot",
  "summary": "Khách hàng đặt...",
  "customer": {
    "name": "...",
    "phone": "...",
    "email": "...",
    "address": "...",
    "company": "..."
  },
  "items": [...],
  "channel": {
    "type": "chatdemo|chat-plugin|messenger|...",
    "pluginId": "..."
  },
  "payment": {...},
  "delivery": {...},
  "notes": "...",
  "metadata": {...}
}
```

### 3. Triển Khai Dual Webhook Approach

**Implementation Details:**

1. **Conversation Webhook (Existing)**: Vẫn gửi về `/api/webhooks/ai/conversation` để track conversation flow
2. **Order Creation Webhook (New)**: Gửi về `/api/webhooks/orders/ai` khi phát hiện order completion

**Code Flow:**
```python
# Step 1: Gửi conversation webhook như bình thường
response = await client.post(conversation_endpoint, json=conversation_payload)

if response.status_code == 200:
    # Step 2: Check if this is order completion
    if is_order_completion:
        # Step 3: Extract order data from AI response
        order_data = await self._extract_order_data_from_response(parsed_response, user_message)

        # Step 4: Send order creation webhook
        await self._send_order_created_webhook(request, order_data, processing_start_time)
```

### 4. Thêm Helper Methods

**Đã thêm các methods mới:**

- `_build_order_summary()`: Tạo summary từ order data
- `_format_items_for_backend()`: Format items array theo backend requirements
- `_extract_order_data_from_response()`: Trích xuất order data từ AI response
- Updated `_send_order_created_webhook()`: Sửa endpoint và payload structure

### 5. Order Detection Logic

**Điều kiện phát hiện order completion:**
```python
detected_intent = parsed_response.get("thinking", {}).get("intent", "unknown")
is_order_completion = (
    detected_intent == "PLACE_ORDER"
    and self._is_order_confirmation_complete(parsed_response, request.message)
)
```

**Keywords detection:**
- Tiếng Việt: "đồng ý", "xác nhận", "ok", "được", "đặt hàng"
- Tiếng Anh: "confirm", "yes", "agree", "order", "place order"

## 🔧 TECHNICAL CHANGES

### File Modified: `src/services/unified_chat_service.py`

**Methods Updated:**
1. `_send_order_created_webhook()` - Completely rewritten
2. `_send_response_to_backend()` - Added dual webhook logic
3. Added new helper methods

**Environment Variables:**
- `AI_WEBHOOK_SECRET`: Webhook secret cho order endpoints
- `BACKEND_WEBHOOK_URL`: URL của backend service

### JSON Structure Mapping

**AI Response → Backend Payload:**
```python
# From parsed_response
customer_name = extract_from_ai_response()
items = extract_items_from_conversation()

# To backend payload
{
  "customer": {
    "name": customer_name,
    "phone": extracted_phone,
    // ...
  },
  "items": formatted_items,
  // ...
}
```

## 📊 TESTING SCENARIOS

### Test Case 1: Đơn Hàng Đơn Giản
```
User: "Tôi muốn đặt 2 cái áo thun size M"
AI: "Bạn có muốn xác nhận đặt 2 áo thun size M không?"
User: "Đồng ý, xác nhận đặt hàng"
```

**Expected Result:**
1. ✅ Conversation webhook sent to `/api/webhooks/ai/conversation`
2. ✅ Order webhook sent to `/api/webhooks/orders/ai`
3. ✅ Backend creates order with order code
4. ✅ Email notifications sent

### Test Case 2: Đơn Hàng Với Thông Tin Đầy Đủ
```
User: "Đặt 1 bộ bàn ghế gỗ, giao về 123 ABC Street, thanh toán COD"
AI: "Xác nhận đặt bộ bàn ghế gỗ, giao về 123 ABC Street, thanh toán COD?"
User: "OK, đặt hàng luôn"
```

**Expected Payload:**
```json
{
  "customer": {
    "name": "extracted_from_conversation",
    "address": "123 ABC Street"
  },
  "items": [
    {
      "name": "Bộ bàn ghế gỗ",
      "quantity": 1,
      "unitPrice": 0,
      "description": "Đặt từ cuộc hội thoại"
    }
  ],
  "delivery": {
    "method": "delivery",
    "address": "123 ABC Street"
  },
  "payment": {
    "method": "COD"
  }
}
```

## 🚀 NEXT STEPS

### Immediate (Cần test ngay)
- [ ] Test với chatdemo channel
- [ ] Test với chat-plugin channel
- [ ] Verify backend nhận được đúng payload
- [ ] Test order creation flow

### Phase 2 (Cải tiến)
- [ ] Implement UPDATE_ORDER intent
- [ ] Implement CHECK_QUANTITY intent
- [ ] Enhanced order data extraction từ conversation
- [ ] Better error handling và retry logic

### Phase 3 (Tối ưu hóa)
- [ ] Add order validation before sending webhook
- [ ] Implement order status tracking
- [ ] Add comprehensive logging và monitoring
- [ ] Performance optimization

## 📝 CONFIGURATION

### Environment Variables Required:
```bash
# Backend connection
BACKEND_WEBHOOK_URL=http://localhost:8001

# Webhook authentication
AI_WEBHOOK_SECRET=your-webhook-secret-for-orders
WEBHOOK_SECRET=your-general-webhook-secret

# AI Provider
CEREBRAS_API_KEY=your-cerebras-key
```

### Backend API Endpoints Expected:
```bash
# Order creation (NEW - fixed)
POST /api/webhooks/orders/ai
x-webhook-secret: {AI_WEBHOOK_SECRET}

# Conversation tracking (EXISTING)
POST /api/webhooks/ai/conversation
X-Webhook-Secret: {WEBHOOK_SECRET}
```

## 🔍 MONITORING & DEBUGGING

**Log Messages để Track:**
```bash
🛒 [ORDER_DETECTION] Order completion detected
🛒 [DUAL_WEBHOOK] Sending order creation webhook
🛒 [ORDER_WEBHOOK] Sending to endpoint: /api/webhooks/orders/ai
✅ [ORDER_WEBHOOK] Order created successfully: ORD20250817001
❌ [ORDER_WEBHOOK] Backend returned 400: validation error
```

**Debug Files:**
- `debug_webhook_payloads/` - Full webhook payloads
- `logs/` - Application logs với order tracking

## ✅ VALIDATION CHECKLIST

- [x] Fixed webhook endpoint từ `/conversation` → `/orders/ai`
- [x] Updated payload structure theo API_Webhook_BE.md
- [x] Implemented dual webhook sending
- [x] Added order data extraction từ AI response
- [x] Added proper error handling
- [x] Added comprehensive logging
- [x] Environment variables configured
- [ ] **Testing required** với real backend
- [ ] **Validation required** order creation flow

---

**Ready for Testing**: PLACE_ORDER intent đã được cập nhật và sẵn sàng để test với backend integration.
