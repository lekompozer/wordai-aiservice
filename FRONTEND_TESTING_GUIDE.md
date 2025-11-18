# 📋 UNIFIED POINTS SYSTEM - FRONTEND TESTING GUIDE

**Date**: November 18, 2025
**Status**: ✅ **DEPLOYED TO PRODUCTION**
**Server**: 104.248.147.155 (ai-chatbot-rag container)

---

## 🎯 **ĐÃ HOÀN THÀNH**

### ✅ **1. Vấn đề đã fix:**
- ❌ **TRƯỚC**: User có 294 điểm nhưng hiển thị 0 → Không mua được sách/test
- ✅ **SAU**: User có 294 điểm và mua được bình thường
- **Root Cause**: Points bị lưu ở nhiều collection (firebase_users, user_subscriptions, user_points) → Data không nhất quán
- **Giải pháp**: Thống nhất tất cả về **`user_subscriptions`** làm single source of truth

### ✅ **2. Database Migration:**
```bash
✅ Migrated 4 user subscriptions successfully
✅ Added earnings_points field (default: 0)
✅ Added points_used field (calculated from points_total - points_remaining)
✅ All users now have complete points schema
```

### ✅ **3. API Changes Deployed:**

**Book Routes (`/api/books/`):**
- ✅ Purchase book endpoint: Dùng `user_subscriptions.points_remaining`
- ✅ Deduct points: Update `points_remaining` và `points_used`
- ✅ Owner earnings: Credit vào `user_subscriptions.earnings_points`

**Test Routes (`/api/marketplace-transactions/`):**
- ✅ Purchase test endpoint: Dùng `user_subscriptions.points_remaining`
- ✅ Creator earnings: Credit vào `user_subscriptions.earnings_points` (trước chỉ track trong stats)

---

## 📊 **POINTS SYSTEM ARCHITECTURE**

### **Collection: `user_subscriptions` (MAIN)**

```javascript
{
  user_id: "17BeaeikPBQYk8OWeDUkqm0Ov8e2",
  plan: "premium" | "free",
  is_active: true,

  // ===== POINTS FIELDS =====
  points_remaining: 294,      // Số điểm để mua (AI, Books, Tests)
  points_total: 310,          // Tổng điểm đã nhận (lifetime)
  points_used: 16,            // Tổng điểm đã tiêu (lifetime)
  earnings_points: 0,         // Doanh thu từ bán Books + Tests (rút được)

  // Subscription info
  started_at: datetime,
  expires_at: datetime,
  auto_renew: boolean,

  // Usage limits
  storage_used_mb: float,
  storage_limit_mb: int,
  // ... other limits
}
```

---

## 🧪 **TEST CASES CHO FRONTEND**

### **Test User:**
```
Email: tienhoi.lh@gmail.com
UID: 17BeaeikPBQYk8OWeDUkqm0Ov8e2
Points: 294 (available for purchase)
Plan: Premium
```

---

### **✅ TEST 1: Kiểm tra số điểm hiển thị**

**Endpoint:**
```bash
GET /api/subscriptions/current
Authorization: Bearer <firebase_token>
```

**Expected Response:**
```json
{
  "user_id": "17BeaeikPBQYk8OWeDUkqm0Ov8e2",
  "plan": "premium",
  "is_active": true,
  "points_remaining": 294,       // ✅ Phải hiển thị 294 (không phải 0)
  "points_total": 310,
  "points_used": 16,
  "earnings_points": 0           // ✅ Field mới (doanh thu)
}
```

**Frontend cần check:**
- ✅ Số điểm hiển thị đúng 294 (không phải 0)
- ✅ Field `earnings_points` tồn tại (dù = 0)
- ✅ `points_used` tracking đúng

---

### **✅ TEST 2: Mua sách (Book Purchase)**

**Scenario 1: Mua sách 10 điểm (đủ tiền)**

**Endpoint:**
```bash
POST /api/books/{book_id}/purchase
Authorization: Bearer <firebase_token>
Content-Type: application/json

{
  "purchase_type": "one_time"
}
```

**Expected:**
```json
{
  "success": true,
  "message": "Book purchased successfully",
  "purchase": {
    "purchase_id": "xxx",
    "buyer_id": "17BeaeikPBQYk8OWeDUkqm0Ov8e2",
    "book_id": "xxx",
    "points_paid": 10
  },
  "new_balance": 284              // 294 - 10 = 284
}
```

**Database sau khi mua:**
```javascript
// user_subscriptions (buyer)
{
  points_remaining: 284,          // ✅ Trừ 10
  points_used: 26                 // ✅ Tăng 10 (16 → 26)
}

// user_subscriptions (owner)
{
  earnings_points: 8              // ✅ Nhận 80% của 10 = 8
}
```

**Frontend cần check:**
- ✅ Mua thành công (không bị "Insufficient balance")
- ✅ Balance giảm đúng số điểm
- ✅ Access vào nội dung sách ngay lập tức
- ✅ Owner nhận được earnings (check nếu là owner)

---

**Scenario 2: Mua sách 300 điểm (không đủ tiền)**

**Expected:**
```json
{
  "detail": "Insufficient balance. You have 294 points but need 300 points"
}
```

**Frontend cần check:**
- ✅ Hiển thị lỗi rõ ràng
- ✅ Gợi ý mua thêm điểm
- ✅ Balance không bị trừ

---

### **✅ TEST 3: Mua Test**

**Endpoint:**
```bash
POST /api/marketplace-transactions/purchase
Authorization: Bearer <firebase_token>
Content-Type: application/json

{
  "test_id": "xxx"
}
```

**Expected:**
```json
{
  "success": true,
  "message": "Test purchased successfully",
  "transaction_id": "xxx",
  "points_used": 20,
  "new_balance": 274              // 294 - 20 = 274
}
```

**Database sau khi mua:**
```javascript
// user_subscriptions (buyer)
{
  points_remaining: 274,          // ✅ Trừ 20
  points_used: 36                 // ✅ Tăng 20 (16 → 36)
}

// user_subscriptions (creator)
{
  earnings_points: 16             // ✅ Nhận 80% của 20 = 16
}
```

**Frontend cần check:**
- ✅ Mua thành công
- ✅ Balance giảm đúng
- ✅ Access vào test ngay lập tức
- ✅ Creator nhận được earnings

---

### **✅ TEST 4: Chapter Preview (Free chapters)**

**Endpoint:**
```bash
GET /api/books/{book_id}/chapters/{chapter_id}
# Không cần Authorization (optional auth)
```

**Expected cho free chapter:**
```json
{
  "chapter_id": "xxx",
  "title": "Chapter 1",
  "content": "Full content...",    // ✅ Hiển thị đầy đủ
  "is_preview": false
}
```

**Expected cho paid chapter (chưa mua):**
```json
{
  "chapter_id": "xxx",
  "title": "Chapter 2",
  "content": "Preview first 500 chars...",  // ✅ Chỉ preview
  "is_preview": true,
  "message": "This is a preview. Purchase the book to read full content."
}
```

**Frontend cần check:**
- ✅ Free chapters hiển thị full (không cần đăng nhập)
- ✅ Paid chapters chỉ preview (nếu chưa mua)
- ✅ Paid chapters full content (nếu đã mua)

---

### **✅ TEST 5: Earnings Dashboard (cho người bán)**

**Endpoint:**
```bash
GET /api/subscriptions/current
Authorization: Bearer <firebase_token>
```

**Expected:**
```json
{
  "earnings_points": 24,          // ✅ Tổng doanh thu từ Books + Tests
  "points_remaining": 294,        // ✅ Số điểm để tiêu
  // ... other fields
}
```

**Frontend cần implement:**
- ✅ Tab "Earnings" trong profile
- ✅ Hiển thị `earnings_points` riêng biệt với `points_remaining`
- ✅ Button "Withdraw" để rút tiền (chưa implement backend)
- ✅ History của các lần bán được (từ book_purchases, test_purchases)

---

## 💰 **REVENUE SPLIT**

| Loại | Buyer trả | Creator nhận | Platform fee |
|------|-----------|--------------|--------------|
| **Book** | 100% | 80% → `earnings_points` | 20% (tracked in stats) |
| **Test** | 100% | 80% → `earnings_points` | 20% (tracked in stats) |

**Ví dụ:**
```
Book giá 10 điểm:
  - Buyer: -10 points_remaining
  - Owner: +8 earnings_points
  - Platform: 2 points (không credit vào đâu, là revenue)
```

---

## 🔍 **DEBUGGING**

### **Check user points balance:**
```bash
# SSH vào server
ssh root@104.248.147.155

# Run test script
docker exec ai-chatbot-rag python3 /app/test_unified_points_system.py
```

### **Check MongoDB directly:**
```javascript
// Connect to MongoDB
db.user_subscriptions.find({
  user_id: "17BeaeikPBQYk8OWeDUkqm0Ov8e2"
})

// Expected output:
{
  points_remaining: 294,
  points_total: 310,
  points_used: 16,
  earnings_points: 0
}
```

---

## 📝 **FRONTEND UPDATES NEEDED**

### **1. Points Display:**
```typescript
// OLD (WRONG)
const balance = user.points_remaining;  // Có thể lấy từ firebase_users (sai)

// NEW (CORRECT)
const subscription = await fetch('/api/subscriptions/current');
const balance = subscription.points_remaining;  // Từ user_subscriptions
const earnings = subscription.earnings_points;  // Doanh thu (mới)
```

### **2. Purchase Flow:**
```typescript
// Request body (FIXED - không cần book_id)
const response = await fetch(`/api/books/${bookId}/purchase`, {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${firebaseToken}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    purchase_type: 'one_time'  // ✅ Chỉ cần field này
    // ❌ KHÔNG gửi book_id (đã có trong URL)
  })
});
```

### **3. Access Config Fields:**
```typescript
// API trả về (CORRECT)
interface AccessConfig {
  is_public: boolean;
  download_pdf_points: number;     // ✅ Đúng tên field
  access_type: 'free' | 'paid';    // ✅ Đúng tên field
}

// ❌ KHÔNG dùng: pdf_download_points (sai tên)
```

### **4. Earnings Display (NEW):**
```typescript
// Profile page - Add new section
<div className="earnings-section">
  <h3>Earnings from Sales</h3>
  <p className="earnings-amount">{subscription.earnings_points} points</p>
  <button onClick={handleWithdraw}>Withdraw to Cash</button>

  <h4>Sales History</h4>
  <ul>
    {/* List book purchases where you are the owner */}
    {/* List test purchases where you are the creator */}
  </ul>
</div>
```

---

## 🚀 **DEPLOYMENT STATUS**

```bash
✅ Code deployed: November 18, 2025
✅ Migration executed: 4 users migrated successfully
✅ Database updated: All points in user_subscriptions
✅ APIs tested: Purchase flow working
✅ Server: 104.248.147.155 (ai-chatbot-rag)

Deployment command:
ssh root@104.248.147.155 "su - hoile -c 'cd /home/hoile/wordai && ./deploy-compose-with-rollback.sh'"
```

---

## ⚠️ **KNOWN ISSUES / TODO**

1. **Withdrawal Flow:**
   - ❌ Backend chưa implement API rút tiền
   - ❌ Frontend chưa có UI withdrawal
   - ✅ Data đã sẵn sàng (`earnings_points` field)

2. **Other Endpoints:**
   - ⏳ AI Chat endpoints có thể vẫn dùng firebase_users (cần check)
   - ⏳ Document AI endpoints (cần check)
   - ⏳ Các features khác dùng points (cần check)

3. **Documentation:**
   - ✅ POINTS_SYSTEM_UNIFIED.md đã tạo
   - ⏳ API docs cần update (Swagger/OpenAPI)

---

## 📞 **SUPPORT**

Nếu gặp lỗi khi test:

1. **Check logs:**
   ```bash
   ssh root@104.248.147.155
   docker logs -f ai-chatbot-rag --tail 100
   ```

2. **Check database:**
   ```bash
   docker exec ai-chatbot-rag python3 /app/test_unified_points_system.py
   ```

3. **Rollback (nếu cần):**
   ```bash
   ssh root@104.248.147.155 "su - hoile -c 'cd /home/hoile/wordai && ./deploy-compose-with-rollback.sh rollback'"
   ```

---

## ✅ **SUMMARY**

**Đã fix:**
- ✅ Points balance hiển thị đúng (294 không phải 0)
- ✅ Mua sách/test không bị "Insufficient balance"
- ✅ Owner/Creator nhận earnings ngay lập tức
- ✅ Thống nhất toàn bộ points về user_subscriptions
- ✅ Tracking đầy đủ: spending + earnings riêng biệt

**Frontend cần test:**
1. ✅ Số điểm hiển thị đúng
2. ✅ Mua sách/test thành công
3. ✅ Balance giảm đúng sau mua
4. ✅ Access nội dung ngay sau mua
5. ✅ Preview chapters hoạt động đúng
6. ⏳ Earnings display (nếu đã implement UI)

**Ready for production testing! 🚀**
