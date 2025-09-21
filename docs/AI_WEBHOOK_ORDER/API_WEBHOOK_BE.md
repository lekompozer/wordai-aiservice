# AI Service - Webhook Integration Guide cho Order System (v2.2)

## 📋 TỔNG QUAN
Tài liệu này dành riêng cho AI Service để implement webhook tạo, cập nhật, và kiểm tra đơn hàng về Backend với cấu trúc JSON chuẩn.

**Cập nhật quan trọng (v2.2 - 27/08/2025):**
*   **PLACE_ORDER:** Payload được chuẩn hóa lại. `leadId` sẽ luôn là `null` để backend tự xử lý, `userId` sẽ là ID của người dùng thực tế. `itemType` trong `items` được AI service tự động điền.
*   **UPDATE_ORDER:** Payload được đơn giản hóa, chỉ chứa các trường có thể cập nhật.
*   **CHECK_QUANTITY:** Giữ nguyên cấu trúc.

---

## 🎯 ENDPOINT WEBHOOK

### Backend Endpoints
```
# 1. Tạo đơn hàng mới
POST /api/webhooks/orders/ai

# 2. Cập nhật đơn hàng đã có
PUT /api/webhooks/orders/{orderCode}/ai

# 3. Kiểm tra tồn kho/khả dụng
POST /api/webhooks/orders/check-quantity/ai
```
**Headers cho tất cả request:**
```json
{
  "Content-Type": "application/json",
  "x-webhook-secret": "{AI_WEBHOOK_SECRET}"
}
```

---

## 🛒 1. PLACE_ORDER Payload (`POST /api/webhooks/orders/ai`)

Đây là payload để **tạo một đơn hàng mới**.

### Cấu trúc Payload
```json
{
  "conversationId": "string",
  "companyId": "string",
  "userId": "string",
  "leadId": null,
  "summary": "string",
  "customer": {
    "name": "string",
    "phone": "string",
    "email": "string",
    "address": "string"
  },
  "items": [
    {
      "productId": "string | null",
      "serviceId": "string | null",
      "itemType": "string",
      "name": "string",
      "quantity": "number",
      "unitPrice": "number",
      "totalPrice": "number",
      "notes": "string"
    }
  ],
  "channel": {
    "type": "string",
    "pluginId": "string | null"
  },
  "payment": "object",
  "delivery": "object",
  "notes": "string",
  "metadata": "object"
}
```

### Diễn giải các trường quan trọng:

| Trường | Nguồn dữ liệu (Từ Code) | Ghi chú |
| :--- | :--- | :--- |
| `userId` | `request.user_info.user_id` | **BẮT BUỘC.** ID của người dùng cuối đang chat. |
| `leadId` | `null` | **LUÔN LÀ `null`**. Backend sẽ tự tìm hoặc tạo lead từ thông tin `customer`. |
| `items` | `_format_items_for_backend()` | Mảng các sản phẩm/dịch vụ. |
| `items.itemType`| Logic trong `_format_items_for_backend` | **BẮT BUỘC.** AI service tự điền: "Product" (nếu có `productId`), "Service" (nếu có `serviceId`), hoặc "Custom". |

---

## 🔄 2. UPDATE_ORDER Payload (`PUT /api/webhooks/orders/{orderCode}/ai`)

Dùng để **cập nhật một đơn hàng đã tồn tại** thông qua `orderCode` trên URL. Payload chỉ chứa các trường cần thay đổi.

### Cấu trúc Payload
```json
{
  "userId": "string",
  // ... các trường có thể cập nhật
  "customer": { "..." },
  "items": [ { "..." } ],
  "delivery": { "..." },
  "notes": "string"
}
```
### Logic quan trọng:
*   AI Service sẽ trích xuất object `changes` từ AI response.
*   Các trường bên trong `changes` (ví dụ: `items`, `customer`, `delivery`) sẽ được "mở gói" và đặt ở cấp cao nhất của payload gửi đi.
*   Backend chỉ chấp nhận các trường có thể cập nhật (ví dụ: `status`, `summary`, `customer`, `items`, `payment`, `delivery`, `notes`...).

---

## 📊 3. CHECK_QUANTITY Payload (`POST /api/webhooks/orders/check-quantity/ai`)

Dùng để **kiểm tra tồn kho** mà không tạo đơn hàng.

### Cấu trúc Payload
```json
{
  "companyId": "string",
  "customer": {
    "name": "string",
    "phone": "string"
  },
  "channel": {
    "type": "string"
  },
  "productId": "string | null",
  "serviceId": "string | null",
  "metadata": {
    "conversationId": "string",
    "intent": "check_quantity",
    "requestedQuantity": "number",
    "itemName": "string",
    "notes": "string | null"
  }
}
```
### Diễn giải các trường quan trọng:

| Trường | Nguồn dữ liệu (Từ Code) | Ghi chú |
| :--- | :--- | :--- |
| `metadata.conversationId` | `request.conversation_id` | ID của cuộc hội thoại hiện tại, lấy từ request. |
| `metadata.itemName` | `quantity_data.item_name` | Tên sản phẩm AI trích xuất được. |
| `metadata.requestedQuantity` | `quantity_data.specifications.quantity` | Số lượng khách hàng muốn kiểm tra. |
