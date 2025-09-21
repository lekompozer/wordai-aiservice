# Order Management Webhook Payload Examples
# Ví Dụ Payload Webhook Cho Quản Lý Đơn Hàng

## 📋 Tổng Quan

Tài liệu này cung cấp các ví dụ JSON payload chi tiết cho 3 loại webhook order management mà AI Service sẽ gửi về Backend.

## 🆕 1. CREATE ORDER - POST /api/webhooks/orders/ai

### **Use Case**: PLACE_ORDER Intent
```json
{
  "companyId": "comp_123456",
  "timestamp": "2025-08-18T10:30:00.000Z",
  "data": {
    "conversationId": "conv_session_789",
    "sessionId": "session_789",
    "userId": "user_abc123",

    // Order Configuration
    "orderType": "ORDER",
    "status": "PENDING",
    "priority": "Trung bình",
    "language": "vi",

    // Products Information (collected from conversation)
    "products": [
      {
        "name": "Bánh sinh nhật chocolate size M",
        "quantity": 2,
        "unitPrice": 500000,
        "notes": "Không đường, ít ngọt"
      },
      {
        "name": "Nước cam tươi",
        "quantity": 3,
        "unitPrice": 25000,
        "notes": ""
      }
    ],

    // Customer Information (collected from conversation)
    "customer": {
      "name": "Nguyễn Văn A",
      "phone": "0901234567",
      "email": "nguyenvana@email.com"
    },

    // Payment Method (collected from conversation)
    "payment": {
      "method": "bank_transfer",
      "timing": "trả sau khi nhận hàng",
      "notes": "Chuyển khoản qua VietcomBank"
    },

    // Delivery Information (collected from conversation)
    "delivery": {
      "method": "delivery",
      "address": "123 Đường ABC, Phường XYZ, Quận 1, TP.HCM",
      "phone": "0901234567",
      "notes": "Giao buổi sáng từ 8-10h"
    },

    // Channel Information
    "channel": {
      "type": "chat-plugin",
      "pluginId": "plugin_567",
      "customerDomain": "bakery-shop.com"
    },

    // Financial Summary (auto-calculated)
    "financial": {
      "subtotal": 1075000,
      "taxAmount": 107500,
      "discountAmount": 0,
      "totalAmount": 1182500,
      "currency": "VND"
    },

    // General Notes
    "notes": "Khách hàng yêu cầu gói cẩn thận",

    // AI Metadata
    "metadata": {
      "source": "ai_conversation",
      "aiModel": "qwen-3-235b-a22b-instruct-2507",
      "processingTime": 2500,
      "conversationTurns": 8,
      "extractedAt": "2025-08-18T10:30:00.000Z"
    }
  }
}
```

### **Expected Backend Response**:
```json
{
  "success": true,
  "message": "Order created successfully from AI",
  "data": {
    "order": {
      "orderId": "b93438da-0685-4b05-bb90-1ec1f27636b6",
      "orderCode": "ORD20250818001",
      "status": "DRAFT",
      "totalAmount": 1182500,
      "formattedTotal": "1.182.500 ₫"
    },
    "notifications": {
      "customerEmailSent": true,
      "businessEmailSent": true
    }
  }
}
```

---

## 🔄 2. UPDATE ORDER - PUT /api/webhooks/orders/{orderCode}/ai

### **Use Case**: UPDATE_ORDER Intent
```json
{
  "companyId": "comp_123456",
  "timestamp": "2025-08-18T14:15:00.000Z",
  "data": {
    "orderCode": "ORD20250818001",
    "conversationId": "conv_session_890",
    "sessionId": "session_890",
    "userId": "user_abc123",

    // Changes Information (only changed fields included)
    "changes": {
      "products": [
        {
          "name": "Bánh sinh nhật chocolate size M",
          "quantity": 5,  // Changed from 2 to 5
          "notes": "Tăng số lượng theo yêu cầu khách hàng"
        }
      ],
      "customer": {
        "phone": "0907777777",  // Changed phone number
        "address": "456 Đường DEF, Phường ABC, Quận 2, TP.HCM"  // Changed address
      },
      "delivery": {
        "address": "456 Đường DEF, Phường ABC, Quận 2, TP.HCM",
        "phone": "0907777777",
        "notes": "Thay đổi địa chỉ giao hàng, giao buổi chiều"
      }
      // payment không có changes -> không gửi
    },

    // Update Context
    "updateReason": "Khách hàng yêu cầu tăng số lượng và đổi địa chỉ giao hàng",
    "notes": "Cập nhật theo conversation với AI assistant",

    // Channel Information
    "channel": {
      "type": "chat-plugin",
      "pluginId": "plugin_567",
      "customerDomain": "bakery-shop.com"
    },

    // AI Metadata
    "metadata": {
      "source": "ai_conversation",
      "aiModel": "qwen-3-235b-a22b-instruct-2507",
      "processingTime": 1800,
      "updatedAt": "2025-08-18T14:15:00.000Z",
      "originalOrderCode": "ORD20250818001"
    }
  }
}
```

### **Expected Backend Response**:
```json
{
  "success": true,
  "message": "Order updated successfully",
  "data": {
    "order": {
      "orderCode": "ORD20250818001",
      "orderId": "b93438da-0685-4b05-bb90-1ec1f27636b6",
      "status": "DRAFT",
      "totalAmount": 2682500,  // New total after quantity change
      "formattedTotal": "2.682.500 ₫"
    },
    "updatedFields": ["products", "customer", "delivery"],
    "changes": {
      "quantityChange": "+3 sản phẩm",
      "amountChange": "+1.500.000 ₫"
    },
    "notifications": {
      "customerEmailSent": true,
      "businessEmailSent": true
    }
  }
}
```

---

## 📋 3. CHECK QUANTITY - POST /api/webhooks/orders/check-quantity/ai

### **Use Case**: CHECK_QUANTITY Intent
```json
{
  "companyId": "comp_123456",
  "timestamp": "2025-08-18T16:45:00.000Z",
  "data": {
    "conversationId": "conv_session_111",
    "sessionId": "session_111",
    "userId": "user_def456",

    // Products to check availability
    "products": [
      {
        "name": "Bánh sinh nhật chocolate size L",
        "quantity_needed": 10,
        "specifications": "Size L, chocolate tươi, có thể custom tên"
      },
      {
        "name": "Bánh cupcake vanilla",
        "quantity_needed": 50,
        "specifications": "Cupcake nhỏ, topping kem vanilla"
      }
    ],

    // Customer Contact Information
    "customer_contact": {
      "name": "Trần Thị B",
      "phone": "0912345678",
      "email": "tranthib@email.com"
    },

    // How to notify customer
    "contact_method": "email",  // "email" hoặc "sms"

    // Request urgency
    "urgency": "normal",  // "normal" hoặc "urgent"

    // Additional request details
    "notes": "Cần cho event công ty vào cuối tuần, cần xác nhận trước thứ 6",

    // Channel Information
    "channel": {
      "type": "chat-plugin",
      "pluginId": "plugin_567",
      "customerDomain": "bakery-shop.com"
    },

    // AI Metadata
    "metadata": {
      "source": "ai_conversation",
      "aiModel": "qwen-3-235b-a22b-instruct-2507",
      "processingTime": 1200,
      "requestedAt": "2025-08-18T16:45:00.000Z",
      "expectedResponseTime": "2-4 hours"
    }
  }
}
```

### **Expected Backend Response**:
```json
{
  "success": true,
  "message": "Quantity check request received",
  "data": {
    "checkId": "CHK20250818001",
    "estimatedResponseTime": "2-4 hours",
    "productCount": 2,
    "totalQuantityRequested": 60,
    "notificationMethod": "email",
    "customerContact": "tranthib@email.com",
    "status": "PROCESSING",
    "scheduledCheck": "2025-08-18T17:00:00.000Z"
  }
}
```

---

## 🔧 Implementation Guidelines

### **1. JSON Structure Standards**
- **Required Fields**: `companyId`, `timestamp`, `data`
- **Channel Info**: Always include channel details cho tracking
- **Metadata**: Always include AI processing information
- **Error Handling**: Validate required fields before sending

### **2. Data Extraction Principles**
```python
# Key extraction rules:
# 1. Only extract explicitly mentioned information
# 2. Use AI to structure unstructured conversation data
# 3. Validate business logic (quantities, prices, etc.)
# 4. Provide fallback values cho optional fields
```

### **3. Webhook Retry Logic**
```python
# Recommended retry strategy:
MAX_RETRIES = 3
RETRY_DELAYS = [1, 3, 9]  # seconds
TIMEOUT = 30  # seconds

# Retry on: 500, 502, 503, 504, timeout
# Don't retry on: 400, 401, 403, 404
```

### **4. Logging Requirements**
```python
# Log events:
✅ "Webhook payload created successfully"
✅ "Webhook sent to {endpoint}"
✅ "Backend response: {status_code}"
❌ "Webhook failed: {error_message}"
❌ "Retry attempt {n}/{max} failed"
```

## 📊 Payload Size Guidelines

### **Estimated Payload Sizes**:
- **CREATE ORDER**: ~2-4KB (comprehensive order data)
- **UPDATE ORDER**: ~1-2KB (only changed fields)
- **CHECK QUANTITY**: ~1KB (simple check request)

### **Field Length Limits**:
```json
{
  "customer.name": "max 100 characters",
  "products.name": "max 200 characters",
  "delivery.address": "max 500 characters",
  "notes": "max 1000 characters",
  "metadata.aiModel": "max 100 characters"
}
```

## 🧪 Testing Data Examples

### **Test Conversations**:

#### **CREATE ORDER Test**:
```
User: "Tôi muốn đặt 3 bánh kem chocolate"
AI: "Anh/chị cho tôi thông tin giao hàng..."
User: "Tên Nguyễn A, sdt 0901111111"
AI: "Xác nhận đặt hàng: 3 bánh kem chocolate, giao cho Nguyễn A..."
User: "Đồng ý đặt hàng"
```

#### **UPDATE ORDER Test**:
```
User: "Cập nhật đơn hàng ORD20250818001"
AI: "Bạn muốn thay đổi gì trong đơn hàng?"
User: "Đổi từ 3 bánh thành 5 bánh"
AI: "Xác nhận: thay đổi số lượng từ 3 lên 5 bánh?"
User: "Đồng ý"
```

#### **CHECK QUANTITY Test**:
```
User: "Kiểm tra còn bánh kem chocolate không?"
AI: "Bạn cần bao nhiêu bánh?"
User: "Cần 20 bánh cho event"
AI: "Cho tôi email để thông báo kết quả..."
User: "Email: test@gmail.com"
AI: "Sẽ kiểm tra và thông báo qua email trong 2-4h?"
User: "OK"
```

---

**🎯 Summary**: Tài liệu này cung cấp complete payload examples cho 3 order management intents. Backend cần implement corresponding endpoints và return expected response formats.

*Document created: 18/08/2025 - Webhook Payload Specification*
