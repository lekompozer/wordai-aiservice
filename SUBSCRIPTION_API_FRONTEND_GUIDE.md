# SUBSCRIPTION API - FRONTEND INTEGRATION GUIDE

## 📌 Tổng Quan

API Subscription cung cấp **4 endpoints** để frontend hiển thị thông tin subscription, points, và usage của user.

---

## 🎯 Các Endpoints Chính

### 1. GET `/api/subscription/info` - Thông tin đầy đủ ⭐

**Mục đích:** Lấy TẤT CẢ thông tin subscription, points, và usage limits.

**Authentication:** Required (Firebase token)

**Request:**
```typescript
const response = await fetch('/api/subscription/info', {
  headers: {
    'Authorization': `Bearer ${firebaseToken}`
  }
});
```

**Response:**
```json
{
  // Plan Information
  "plan": "free",
  "status": "active",

  // Points Balance
  "points_total": 10,
  "points_remaining": 8,
  "points_used": 2,

  // Daily Chats (FREE users only)
  "daily_chat_limit": 10,
  "daily_chat_count": 3,
  "daily_chat_remaining": 7,

  // Storage Limits
  "storage_limit_mb": 50,
  "storage_used_mb": 12.5,
  "storage_remaining_mb": 37.5,

  // Documents Limits
  "documents_limit": 10,
  "documents_count": 3,
  "documents_remaining": 7,

  // Files Limits
  "upload_files_limit": 10,
  "upload_files_count": 5,
  "upload_files_remaining": 5,

  // Subscription Dates
  "start_date": "2025-11-06T10:00:00Z",
  "end_date": null,
  "auto_renew": false,
  "last_reset_date": "2025-11-06T00:00:00Z",
  "updated_at": "2025-11-06T10:30:00Z"
}
```

**Khi nào dùng:**
- ✅ Trang Profile/Settings
- ✅ Trang Subscription Management
- ✅ Modal hiển thị chi tiết subscription

---

### 2. GET `/api/subscription/usage-summary` - Tóm tắt nhanh ⚡

**Mục đích:** Lấy thông tin tóm tắt để hiển thị trên header/sidebar.

**Authentication:** Required (Firebase token)

**Request:**
```typescript
const response = await fetch('/api/subscription/usage-summary', {
  headers: {
    'Authorization': `Bearer ${firebaseToken}`
  }
});
```

**Response:**
```json
{
  "points_remaining": 8,
  "daily_chats_remaining": 7,
  "storage_percentage": 25.0,
  "documents_percentage": 30.0,
  "plan": "free",
  "is_premium": false
}
```

**Khi nào dùng:**
- ✅ Header/Navbar (hiển thị points còn lại)
- ✅ Sidebar (hiển thị quick stats)
- ✅ Dashboard widgets
- ✅ Real-time updates sau mỗi action

---

### 3. GET `/api/subscription/points/history` - Lịch sử giao dịch 📊

**Mục đích:** Xem lịch sử sử dụng points với phân trang.

**Authentication:** Required (Firebase token)

**Query Parameters:**
- `page` (int, default: 1) - Trang hiện tại
- `limit` (int, default: 20, max: 100) - Số items mỗi trang
- `transaction_type` (string, optional) - Lọc theo loại: `spend`, `earn`, `grant`, `refund`, `bonus`, `purchase`

**Request:**
```typescript
// Trang 1, 20 items
const response = await fetch('/api/subscription/points/history?page=1&limit=20', {
  headers: {
    'Authorization': `Bearer ${firebaseToken}`
  }
});

// Chỉ xem những lần dùng points
const spendOnly = await fetch('/api/subscription/points/history?transaction_type=spend', {
  headers: {
    'Authorization': `Bearer ${firebaseToken}`
  }
});
```

**Response:**
```json
{
  "transactions": [
    {
      "transaction_id": "673b4e5f0123456789abcdef",
      "transaction_type": "spend",
      "points": -2,
      "service": "ai_chat",
      "description": "Chat with Claude (Premium model)",
      "created_at": "2025-11-06T10:30:00Z",
      "metadata": {
        "provider": "claude",
        "model": "claude-3-5-sonnet-20241022",
        "conversation_id": "conv_123"
      }
    },
    {
      "transaction_id": "673b4e5f0123456789abcde0",
      "transaction_type": "spend",
      "points": -2,
      "service": "ai_document_edit",
      "description": "AI Edit document: My Document.docx",
      "created_at": "2025-11-06T09:15:00Z",
      "metadata": {
        "document_id": "doc_456",
        "operation": "edit"
      }
    },
    {
      "transaction_id": "673b4e5f0123456789abcde1",
      "transaction_type": "grant",
      "points": 10,
      "service": "system",
      "description": "Welcome bonus - FREE plan registration",
      "created_at": "2025-11-06T08:00:00Z",
      "metadata": null
    }
  ],
  "total": 3,
  "page": 1,
  "limit": 20,
  "has_more": false
}
```

**Transaction Types:**
- `spend` - Tiêu points (hiển thị số âm)
- `earn` - Nhận points từ hoạt động
- `grant` - Tặng points từ hệ thống (bonus, promotion)
- `refund` - Hoàn lại points (hủy giao dịch)
- `bonus` - Điểm thưởng đặc biệt
- `purchase` - Mua gói points

**Khi nào dùng:**
- ✅ Trang Points History
- ✅ Modal xem chi tiết giao dịch
- ✅ Reports/Analytics

---

### 4. GET `/api/subscription/points/balance` - Số dư nhanh 💰

**Mục đích:** Lấy CHỈ số points (endpoint nhanh nhất).

**Authentication:** Required (Firebase token)

**Request:**
```typescript
const response = await fetch('/api/subscription/points/balance', {
  headers: {
    'Authorization': `Bearer ${firebaseToken}`
  }
});
```

**Response:**
```json
{
  "points_remaining": 8,
  "points_total": 10,
  "points_used": 2
}
```

**Khi nào dùng:**
- ✅ Real-time updates sau mỗi AI action
- ✅ Polling/WebSocket updates
- ✅ Header badge (số points)

---


## 🚀 Quick Start Checklist

### Backend Ready ✅
- [x] 4 endpoints created
- [x] Authentication required
- [x] Pagination support
- [x] Error handling

### Frontend TODO
- [ ] Create `useSubscription()` hook
- [ ] Create `usePoints()` hook
- [ ] Create `PointsBadge` component
- [ ] Create `SubscriptionPage` component
- [ ] Create `PointsHistory` component
- [ ] Add upgrade prompts
- [ ] Add limit warnings
- [ ] Test with real data

---

## 🔗 API Base URL


All endpoints require Firebase authentication token in header:
```
Authorization: Bearer <firebase-token>
```

---

## 📞 Support

Nếu có vấn đề với API, liên hệ backend team hoặc xem logs:
- Server logs: `/path/to/logs/app.log`
- Look for: `❌`, `ERROR`, `subscription`, `points`
