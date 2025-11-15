# Online Books System - Architecture Analysis

**Date**: November 15, 2025
**System**: Online Books with Point System & Revenue Share

---

## 🎯 System Overview

Hệ thống Online Books cho phép users:
1. Tạo books với nhiều chapters (documents)
2. Set điểm truy cập cho từng book
3. Users khác trả điểm để xem/download
4. Book owner nhận 80% reward points (có thể đổi tiền)

---

## 📚 Core Concepts

### **1. Online Book (Sách trực tuyến)**
- Container chứa nhiều chapters
- Có visibility settings:
  - **Public**: Free, không cần đăng nhập
  - **Point-based**: Yêu cầu user đăng nhập + trả điểm

### **2. Chapter (Chương)**
- Nội dung giống Document (HTML + JSON)
- Có thứ tự trong book (Table of Contents)
- Nested structure (max 3 levels)

### **3. Access Control (Quyền truy cập)**
- **Public**: Free cho tất cả
- **One-time View** (Xem 1 lần): User trả X điểm, xem được 1 lần
- **Forever View** (Xem mãi mãi): User trả Y điểm, xem không giới hạn
- **Download PDF**: User trả Z điểm, download PDF book

### **4. Point System**
- Users có system points (từ hệ thống)
- Book owners nhận reward points (80% từ readers)
- Reward points có thể đổi thành tiền

---

## 🗄️ Database Schema

### **Collection: `online_books`**
```javascript
{
  "_id": ObjectId("..."),
  "book_id": "book_abc123",
  "user_id": "user_xyz",  // Owner
  "title": "Learn Python Programming",
  "slug": "learn-python-programming",
  "description": "Complete Python guide for beginners",

  // Visibility & Access Control
  "visibility": "public | point_based",  // NEW
  "is_indexed": true,  // SEO

  // Point Configuration (when visibility = point_based)
  "access_config": {
    "one_time_view_points": 50,      // Xem 1 lần: 50 points
    "forever_view_points": 200,      // Xem mãi mãi: 200 points
    "download_pdf_points": 500,      // Download PDF: 500 points
    "is_one_time_enabled": true,     // Enable/disable từng option
    "is_forever_enabled": true,
    "is_download_enabled": true
  },

  // Stats & Revenue
  "stats": {
    "total_chapters": 12,
    "total_views": 1523,
    "total_downloads": 234,
    "total_revenue_points": 45600,   // Tổng điểm thu được (100%)
    "owner_reward_points": 36480     // Owner nhận 80%
  },

  // Branding
  "cover_image_url": "https://...",
  "logo_url": "https://...",
  "custom_domain": "python.example.com",
  "branding": {
    "primary_color": "#3776AB",
    "font_family": "Inter"
  },

  "created_at": ISODate("2025-11-15T08:00:00Z"),
  "updated_at": ISODate("2025-11-15T10:30:00Z")
}
```

**Indexes**:
```javascript
db.online_books.createIndex({ "book_id": 1 }, { unique: true });
db.online_books.createIndex({ "user_id": 1, "updated_at": -1 });
db.online_books.createIndex({ "slug": 1, "visibility": 1 });
db.online_books.createIndex({ "custom_domain": 1 }, { unique: true, sparse: true });
```

---

### **Collection: `book_chapters`**
```javascript
{
  "_id": ObjectId("..."),
  "chapter_id": "chapter_def456",
  "book_id": "book_abc123",

  // Chapter Content (stored directly, like Document)
  "title": "Introduction to Python",
  "slug": "introduction",
  "content_html": "<h1>Introduction</h1><p>Python is...</p>",
  "content_json": {  // TipTap JSON format
    "type": "doc",
    "content": [...]
  },

  // Table of Contents Structure
  "parent_id": null,           // Nested structure
  "order_index": 1,            // Position in TOC
  "depth": 0,                  // 0, 1, 2 (max 3 levels)

  // Publishing
  "is_published": true,

  "created_at": ISODate("2025-11-15T08:15:00Z"),
  "updated_at": ISODate("2025-11-15T10:00:00Z")
}
```

**Indexes**:
```javascript
db.book_chapters.createIndex({ "chapter_id": 1 }, { unique: true });
db.book_chapters.createIndex({ "book_id": 1, "order_index": 1 });
db.book_chapters.createIndex({ "book_id": 1, "slug": 1 }, { unique: true });
db.book_chapters.createIndex({ "book_id": 1, "parent_id": 1, "order_index": 1 });
```

---

### **Collection: `book_access_grants`** (NEW)
Lưu quyền truy cập của users đã mua

```javascript
{
  "_id": ObjectId("..."),
  "access_id": "access_ghi789",
  "book_id": "book_abc123",
  "user_id": "user_xyz",          // User đã mua

  // Access Type
  "access_type": "one_time | forever | download",

  // Transaction Details
  "points_paid": 200,             // Số điểm user đã trả
  "owner_reward": 160,            // Owner nhận 80%
  "system_fee": 40,               // Hệ thống giữ 20%

  // Usage Tracking
  "view_count": 3,                // Số lần đã xem (for one_time)
  "max_views": 1,                 // Max views (for one_time)
  "is_active": true,              // Still valid?
  "expires_at": null,             // Optional expiry

  // Download (for download access)
  "download_count": 1,
  "last_downloaded_at": ISODate("2025-11-15T14:00:00Z"),

  "purchased_at": ISODate("2025-11-15T10:00:00Z"),
  "last_accessed_at": ISODate("2025-11-15T14:00:00Z")
}
```

**Indexes**:
```javascript
db.book_access_grants.createIndex({ "access_id": 1 }, { unique: true });
db.book_access_grants.createIndex({ "book_id": 1, "user_id": 1 });
db.book_access_grants.createIndex({ "user_id": 1, "purchased_at": -1 });
db.book_access_grants.createIndex({ "book_id": 1, "access_type": 1 });
```

---

### **Collection: `book_transactions`** (NEW)
Lưu lịch sử giao dịch điểm

```javascript
{
  "_id": ObjectId("..."),
  "transaction_id": "txn_jkl012",
  "book_id": "book_abc123",
  "buyer_user_id": "user_xyz",      // User mua
  "owner_user_id": "user_owner",    // Owner book

  // Transaction Type
  "transaction_type": "one_time_view | forever_view | download_pdf",

  // Points Flow
  "total_points": 200,              // Tổng điểm giao dịch
  "owner_reward": 160,              // Owner nhận 80%
  "system_fee": 40,                 // Hệ thống 20%

  // Status
  "status": "completed | failed | refunded",

  // Related Access Grant
  "access_grant_id": "access_ghi789",

  "created_at": ISODate("2025-11-15T10:00:00Z")
}
```

**Indexes**:
```javascript
db.book_transactions.createIndex({ "transaction_id": 1 }, { unique: true });
db.book_transactions.createIndex({ "book_id": 1, "created_at": -1 });
db.book_transactions.createIndex({ "buyer_user_id": 1, "created_at": -1 });
db.book_transactions.createIndex({ "owner_user_id": 1, "created_at": -1 });
```

---

### **Collection: `user_points`** (Existing - Update)
Lưu điểm của users

```javascript
{
  "_id": ObjectId("..."),
  "user_id": "user_xyz",

  // Two Types of Points
  "system_points": 1000,         // Điểm từ hệ thống (mua, tặng, nhiệm vụ)
  "reward_points": 3200,         // Điểm từ book sales (80% revenue)

  // Reward Points Metadata
  "reward_points_earned": 4000,  // Tổng reward points từng nhận
  "reward_points_withdrawn": 800, // Đã rút thành tiền
  "reward_points_available": 3200, // Còn lại (earned - withdrawn)

  // Transaction History (summary)
  "total_spent": 5000,           // Tổng điểm đã tiêu
  "total_earned": 6000,          // Tổng điểm đã nhận

  "updated_at": ISODate("2025-11-15T10:00:00Z")
}
```

**Indexes**:
```javascript
db.user_points.createIndex({ "user_id": 1 }, { unique: true });
```

---

## 🔄 User Workflows

### **Workflow 1: Owner tạo Book (Point-based)**

```
1. POST /books
   Body: {
     title: "Learn Python",
     visibility: "point_based",
     access_config: {
       one_time_view_points: 50,
       forever_view_points: 200,
       download_pdf_points: 500
     }
   }
   → Tạo book với point configuration

2. POST /books/{book_id}/chapters (multiple times)
   Body: {
     title: "Chapter 1",
     content_html: "<h1>...</h1>",
     content_json: { type: "doc", ... },
     order_index: 1
   }
   → Thêm chapters vào book

3. PATCH /books/{book_id}
   Body: { visibility: "point_based" }
   → Publish book
```

---

### **Workflow 2: Reader mua quyền truy cập**

```
1. GET /public/books/{slug}
   → Reader xem preview (title, description, TOC)
   → Thấy price: "200 points for forever access"

2. Check reader's points:
   GET /users/me/points
   → { system_points: 1000, reward_points: 0 }

3. Purchase access:
   POST /books/{book_id}/access/purchase
   Body: {
     access_type: "forever_view",
     points_source: "system_points"  // or "reward_points"
   }

   Backend xử lý:
   - Trừ 200 points từ buyer
   - Tạo book_access_grant (forever_view)
   - Tạo book_transaction
   - Cộng 160 reward_points cho owner (80%)
   - Hệ thống giữ 40 points (20%)

4. Access book:
   GET /books/{book_id}/view (with auth)
   → Backend check book_access_grants
   → Nếu có forever_view → allow
   → Return full book content
```

---

### **Workflow 3: Reader xem "One-time View"**

```
1. POST /books/{book_id}/access/purchase
   Body: { access_type: "one_time_view" }

   → Tạo access_grant với max_views = 1

2. GET /books/{book_id}/view
   → view_count = 1
   → Cho phép xem book

3. GET /books/{book_id}/view (lần 2)
   → view_count = 2 (exceed max_views = 1)
   → Return 403 Forbidden: "Access expired"
   → Must purchase again
```

---

### **Workflow 4: Reader download PDF**

```
1. POST /books/{book_id}/access/purchase
   Body: { access_type: "download_pdf" }

   → Tạo access_grant (download)

2. POST /books/{book_id}/download-pdf
   → Backend:
     - Check access_grant
     - Generate PDF from chapters
     - Increment download_count
     - Return PDF file

3. Response: PDF binary
   Headers: Content-Disposition: attachment; filename="learn-python.pdf"
```

---

### **Workflow 5: Owner rút tiền từ Reward Points**

```
1. GET /users/me/rewards
   → { reward_points_available: 3200 }
   → Conversion: 3200 points = 3200 * 1000 VND = 3,200,000 VND

2. POST /users/me/rewards/withdraw
   Body: {
     points_to_withdraw: 3200,
     payment_method: "bank_transfer",
     bank_info: { ... }
   }

   → Backend:
     - Validate minimum withdrawal (e.g., 1000 points)
     - Create withdrawal request
     - Update user_points: reward_points_withdrawn += 3200
     - Send to payment processing (manual approval)
```

---

## 🔐 Access Control Logic

### **Check Access Permission (Backend)**

```python
def check_book_access(book_id: str, user_id: str) -> dict:
    """
    Check if user can access book
    Returns: {
        "can_access": bool,
        "access_type": "public | one_time | forever | none",
        "remaining_views": int (for one_time)
    }
    """
    book = get_book(book_id)

    # Case 1: Public book - anyone can access
    if book["visibility"] == "public":
        return {"can_access": True, "access_type": "public"}

    # Case 2: Point-based book - need to check grants
    if book["visibility"] == "point_based":
        # Owner always has access
        if book["user_id"] == user_id:
            return {"can_access": True, "access_type": "owner"}

        # Check if user has active access grant
        grant = db.book_access_grants.find_one({
            "book_id": book_id,
            "user_id": user_id,
            "is_active": True
        })

        if not grant:
            return {"can_access": False, "access_type": "none"}

        # Check one_time access
        if grant["access_type"] == "one_time":
            if grant["view_count"] >= grant["max_views"]:
                return {"can_access": False, "access_type": "expired"}
            return {
                "can_access": True,
                "access_type": "one_time",
                "remaining_views": grant["max_views"] - grant["view_count"]
            }

        # Forever access
        if grant["access_type"] == "forever":
            return {"can_access": True, "access_type": "forever"}

    return {"can_access": False, "access_type": "none"}
```

---

## 📊 Revenue Calculation

### **Point Distribution Formula**

```python
def calculate_revenue_split(total_points: int) -> dict:
    """
    80% to owner (reward points)
    20% to system (system fee)
    """
    owner_reward = int(total_points * 0.8)
    system_fee = total_points - owner_reward

    return {
        "total_points": total_points,
        "owner_reward": owner_reward,    # 80%
        "system_fee": system_fee         # 20%
    }

# Example:
# User trả 200 points cho "forever_view"
# → Owner nhận: 160 reward_points
# → System giữ: 40 points
```

### **Conversion Rate (Reward Points → Money)**

```python
# 1 reward point = 1,000 VND
# Minimum withdrawal: 1,000 points (1,000,000 VND)

def convert_points_to_money(reward_points: int) -> int:
    """Convert reward points to VND"""
    return reward_points * 1000  # VND

# Example:
# 3,200 reward points = 3,200,000 VND
```

---

## 🆕 New API Endpoints (Phase 6)

### **Book Access Purchase**
```
POST /books/{book_id}/access/purchase
Body: {
  "access_type": "one_time_view | forever_view | download_pdf",
  "points_source": "system_points | reward_points"
}

Response 201:
{
  "access_id": "access_abc123",
  "book_id": "book_xyz",
  "access_type": "forever_view",
  "points_paid": 200,
  "remaining_points": 800,
  "can_access": true
}

Errors:
- 402 Payment Required: Insufficient points
- 409 Conflict: Already purchased this access type
```

### **View Book (Authenticated)**
```
GET /books/{book_id}/view
Headers: Authorization: Bearer <token>

Response 200:
{
  "book": { ... },  // Full book data
  "chapters": [ ... ],  // All chapters with content
  "access_info": {
    "access_type": "forever_view",
    "remaining_views": null  // null for forever, number for one_time
  }
}

Errors:
- 403 Forbidden: No access (need to purchase)
- 403 Forbidden: Access expired (one_time used up)
```

### **Download PDF**
```
POST /books/{book_id}/download-pdf
Headers: Authorization: Bearer <token>

Response 200:
Binary PDF file
Headers:
  Content-Type: application/pdf
  Content-Disposition: attachment; filename="book-name.pdf"

Errors:
- 403 Forbidden: No download access
- 402 Payment Required: Need to purchase download access
```

### **User Points Info**
```
GET /users/me/points

Response 200:
{
  "user_id": "user_xyz",
  "system_points": 1000,
  "reward_points": 3200,
  "reward_points_earned": 4000,
  "reward_points_withdrawn": 800,
  "total_spent": 5000,
  "total_earned": 6000
}
```

### **User Rewards Dashboard**
```
GET /users/me/rewards

Response 200:
{
  "reward_points_available": 3200,
  "estimated_value_vnd": 3200000,
  "total_books_sold": 25,
  "total_revenue_points": 4000,
  "recent_transactions": [...]
}
```

### **Withdraw Reward Points**
```
POST /users/me/rewards/withdraw
Body: {
  "points_to_withdraw": 3200,
  "payment_method": "bank_transfer",
  "bank_info": {
    "bank_name": "Vietcombank",
    "account_number": "1234567890",
    "account_name": "Nguyen Van A"
  }
}

Response 201:
{
  "withdrawal_id": "withdraw_abc123",
  "points_withdrawn": 3200,
  "amount_vnd": 3200000,
  "status": "pending",
  "estimated_processing_days": 3
}
```

---

## 🚀 Implementation Priority

### **Phase 6A: Basic Point System** (CRITICAL)
1. Update `online_books` schema with `access_config`
2. Create `book_access_grants` collection
3. Create `book_transactions` collection
4. API: Purchase access (3 types)
5. API: View book (check access)
6. Update point balance logic

### **Phase 6B: PDF Generation** (HIGH)
1. Install PDF library (e.g., WeasyPrint)
2. Create PDF templates
3. API: Download PDF
4. Track download counts

### **Phase 6C: Rewards & Withdrawal** (MEDIUM)
1. Reward points calculation
2. API: View rewards dashboard
3. API: Request withdrawal
4. Admin panel for withdrawal approval

### **Phase 6D: Analytics** (LOW)
1. Owner dashboard: revenue stats
2. Reader dashboard: purchased books
3. System analytics: revenue tracking

---

## 📝 Next Steps

1. **Approve architecture** → Bạn review và confirm
2. **Rename Guide → Book** → Migration script
3. **Implement Phase 6A** → Point system + access control
4. **Testing** → Full test suite
5. **Deploy** → Production rollout

---

**Ready to proceed?** 🚀
