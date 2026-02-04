# Book QR Payment, Group Purchase & Referral System Analysis

**Document Created:** February 3, 2026
**Purpose:** Phân tích và thiết kế hệ thống thanh toán QR, mua nhóm, và referral code cho sách

---

## 📋 Table of Contents

1. [Current System Overview](#current-system-overview)
2. [Feature 1: QR Payment System](#feature-1-qr-payment-system)
3. [Feature 2: Group Purchase System](#feature-2-group-purchase-system)
4. [Feature 3: Referral Code System](#feature-3-referral-code-system)
5. [Database Schema Design](#database-schema-design)
6. [API Endpoints Design](#api-endpoints-design)
7. [Integration with Existing System](#integration-with-existing-system)
8. [Implementation Phases](#implementation-phases)
9. [Security & Validation](#security--validation)
10. [Testing Plan](#testing-plan)

---

## 🔍 Current System Overview

### Existing Components

#### 1. Payment Service (Node.js)
- **Location:** `/payment-service/`
- **Current Features:**
  - SePay bank transfer integration
  - Subscription payments (Premium/Pro/VIP)
  - Points purchase (50/100/200 points)
  - Order tracking via `payments` collection
  - Webhook handling for payment confirmation

**Payment Flow:**
```javascript
// Current: payment-service/src/controllers/paymentController.js
createCheckout() → Generate order → Return SePay form fields → Frontend submits to SePay
```

**Pricing Structure:**
```javascript
PLAN_PRICING = {
    premium: { '3_months': 279000, '12_months': 990000 },
    pro: { '3_months': 447000, '12_months': 1699000 },
    vip: { '3_months': 747000, '12_months': 2799000 }
}

POINTS_PRICING = {
    '50': 50000,   // 50 points = 50,000 VND
    '100': 95000,  // 100 points = 95,000 VND
    '200': 180000  // 200 points = 180,000 VND
}
```

#### 2. Book Purchase System (Python)
- **Location:** `src/api/book_marketplace_routes.py`
- **Current Features:**
  - Point-based purchases (one_time/forever/pdf_download)
  - 80/20 revenue split (owner/platform)
  - Purchase tracking via `book_purchases` collection
  - Access control based on purchase type

**Current Purchase Flow:**
```python
# src/api/book_marketplace_routes.py
POST /api/v1/books/{book_id}/purchase
→ Check user points balance
→ Deduct points from user_subscriptions
→ Create book_purchases record
→ Update book stats
→ Credit owner earnings (80%)
```

**Book Models:**
```python
# src/models/book_models.py
AccessConfig:
    one_time_view_points: int      # One-time access price
    forever_view_points: int       # Forever access price
    download_pdf_points: int       # PDF download price

BookStats:
    total_revenue_points: int      # Total revenue (100%)
    owner_reward_points: int       # Owner share (80%)
    system_fee_points: int         # Platform fee (20%)
```

#### 3. Collections in Use

**MongoDB Collections:**
```javascript
// Payment Service
payments: {
    user_id: string,
    order_invoice_number: string,  // WA-{timestamp}-{user_short}
    plan/points: string,
    price: number,
    status: 'pending' | 'completed' | 'failed',
    payment_method: 'SEPAY_BANK_TRANSFER',
    sepay_transaction_id: string,
    created_at: Date,
    updated_at: Date
}

// Book System
book_purchases: {
    purchase_id: string,
    user_id: string,
    book_id: string,
    purchase_type: 'one_time' | 'forever' | 'pdf_download',
    points_spent: number,
    access_expires_at: Date | null,
    purchased_at: Date
}

user_subscriptions: {
    user_id: string,
    points_remaining: number,
    points_used: number,
    earnings_points: number  // Owner earnings (can withdraw to cash)
}
```

---

## 💳 Feature 1: QR Payment System

### Overview
Cho phép user thanh toán trực tiếp bằng mã QR chuyển khoản vào tài khoản admin thay vì mua points.

### Requirements

**User Story:**
> Là một người mua sách, tôi muốn thanh toán trực tiếp 99k VND qua QR code để mua sách mà không cần mua points trước.

**Acceptance Criteria:**
- ✅ Tạo order với giá tiền VND (không phải points)
- ✅ Sinh mã QR VietQR/SePay cho tài khoản admin
- ✅ Tracking order status (pending → completed → granted access)
- ✅ Tự động cấp quyền đọc sách sau khi thanh toán thành công
- ✅ Admin có thể xác nhận thanh toán thủ công

### Database Schema

#### New Collection: `book_cash_orders`
```javascript
{
    order_id: "BOOK-{timestamp}-{user_short}",  // Unique order ID
    user_id: string,                            // Firebase UID
    book_id: string,                            // Book to purchase

    // Pricing (VND, not points)
    purchase_type: "one_time" | "forever" | "pdf_download",
    price_vnd: number,                          // e.g., 99000
    currency: "VND",

    // Payment info
    payment_method: "BANK_TRANSFER_QR",
    payment_provider: "SEPAY" | "VIETQR",       // QR provider
    qr_code_url: string,                        // QR image URL
    qr_code_data: string,                       // QR code content
    admin_bank_account: {
        bank_name: string,                      // e.g., "Vietcombank"
        account_number: string,
        account_name: string,
        transfer_content: string                // Unique transfer note
    },

    // Status tracking
    status: "pending" | "processing" | "completed" | "failed" | "cancelled",
    transaction_id: string | null,             // Bank transaction ID (after webhook)
    paid_at: Date | null,
    confirmed_by: string | null,               // Admin user_id if manual confirmation

    // Access granting
    access_granted: boolean,
    book_purchase_id: string | null,           // Link to book_purchases record

    // Metadata
    user_email: string,
    user_name: string,
    ip_address: string,
    user_agent: string,
    expires_at: Date,                          // Order expiry (30 minutes)
    created_at: Date,
    updated_at: Date
}

// Indexes
db.book_cash_orders.createIndex({ order_id: 1 }, { unique: true })
db.book_cash_orders.createIndex({ user_id: 1, status: 1 })
db.book_cash_orders.createIndex({ book_id: 1, status: 1 })
db.book_cash_orders.createIndex({ status: 1, created_at: -1 })
db.book_cash_orders.createIndex({ expires_at: 1 }, { expireAfterSeconds: 86400 })  // Auto-delete after 24h
```

#### Payment Service Config (Admin Account)
```javascript
// payment-service/src/config/index.js
config = {
    // ... existing config

    // Admin default bank account for book purchases
    adminBankAccount: {
        bankName: process.env.ADMIN_BANK_NAME || 'Vietcombank',
        accountNumber: process.env.ADMIN_ACCOUNT_NUMBER || '0123456789',
        accountName: process.env.ADMIN_ACCOUNT_NAME || 'NGUYEN VAN A',
        branchName: process.env.ADMIN_BANK_BRANCH || 'Chi nhánh TP.HCM'
    },

    // VietQR API config
    vietQR: {
        apiUrl: process.env.VIETQR_API_URL || 'https://api.vietqr.io/v2',
        enabled: process.env.VIETQR_ENABLED === 'true'
    }
}
```

### API Endpoints

#### 1. Create QR Payment Order
```python
# src/api/book_payment_routes.py

@router.post("/{book_id}/create-qr-order")
async def create_qr_payment_order(
    book_id: str,
    request: CreateQROrderRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Tạo order thanh toán QR cho sách

    Request Body:
    {
        "purchase_type": "forever",  // one_time | forever | pdf_download
    }

    Response:
    {
        "order_id": "BOOK-1738567890-abcd1234",
        "book_id": "book_123",
        "book_title": "Python Complete Guide",
        "price_vnd": 99000,
        "qr_code_url": "https://img.vietqr.io/image/...",
        "qr_code_data": "...",  // Raw QR code content
        "bank_account": {
            "bank_name": "Vietcombank",
            "account_number": "0123456789",
            "account_name": "NGUYEN VAN A",
            "transfer_content": "BOOK 1738567890"  // Required for auto-matching
        },
        "amount": 99000,
        "expires_at": "2026-02-03T15:30:00Z",  // 30 minutes from now
        "status": "pending"
    }
    """
```

**Implementation:**
```python
async def create_qr_payment_order(book_id, request, current_user):
    user_id = current_user["uid"]

    # 1. Get book and validate
    book = db.online_books.find_one({"book_id": book_id, "is_deleted": False})
    if not book:
        raise HTTPException(404, "Book not found")

    # 2. Get price in VND from access_config
    access_config = book.get("access_config", {})
    price_points = 0

    if request.purchase_type == "one_time":
        price_points = access_config.get("one_time_view_points", 0)
    elif request.purchase_type == "forever":
        price_points = access_config.get("forever_view_points", 0)
    elif request.purchase_type == "pdf_download":
        price_points = access_config.get("download_pdf_points", 0)

    if price_points <= 0:
        raise HTTPException(400, "Purchase type not available")

    # 3. Convert points to VND (1 point = 1000 VND)
    price_vnd = price_points * 1000

    # 4. Generate unique order ID
    timestamp = int(datetime.utcnow().timestamp())
    user_short = user_id[:8]
    order_id = f"BOOK-{timestamp}-{user_short}"

    # 5. Generate transfer content (for bank matching)
    transfer_content = f"BOOK {timestamp}"

    # 6. Get admin bank account from config
    admin_account = {
        "bank_name": config.ADMIN_BANK_NAME,
        "account_number": config.ADMIN_ACCOUNT_NUMBER,
        "account_name": config.ADMIN_ACCOUNT_NAME,
        "transfer_content": transfer_content
    }

    # 7. Generate QR code via VietQR API
    qr_response = await generate_vietqr_code(
        bank_bin="970436",  # Vietcombank
        account_number=admin_account["account_number"],
        amount=price_vnd,
        description=transfer_content,
        account_name=admin_account["account_name"]
    )

    # 8. Create order record
    order = {
        "order_id": order_id,
        "user_id": user_id,
        "book_id": book_id,
        "purchase_type": request.purchase_type,
        "price_vnd": price_vnd,
        "currency": "VND",
        "payment_method": "BANK_TRANSFER_QR",
        "payment_provider": "VIETQR",
        "qr_code_url": qr_response["data"]["qrDataURL"],
        "qr_code_data": qr_response["data"]["qrCode"],
        "admin_bank_account": admin_account,
        "status": "pending",
        "transaction_id": None,
        "paid_at": None,
        "access_granted": False,
        "book_purchase_id": None,
        "user_email": current_user.get("email"),
        "user_name": current_user.get("name"),
        "expires_at": datetime.utcnow() + timedelta(minutes=30),
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }

    db.book_cash_orders.insert_one(order)

    # 9. Return order details with QR code
    return {
        "order_id": order_id,
        "book_id": book_id,
        "book_title": book["title"],
        "price_vnd": price_vnd,
        "qr_code_url": qr_response["data"]["qrDataURL"],
        "qr_code_data": qr_response["data"]["qrCode"],
        "bank_account": admin_account,
        "amount": price_vnd,
        "expires_at": order["expires_at"],
        "status": "pending"
    }
```

#### 2. Check Order Status
```python
@router.get("/orders/{order_id}")
async def get_order_status(
    order_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Kiểm tra trạng thái order

    Response:
    {
        "order_id": "BOOK-1738567890-abcd1234",
        "status": "completed",  // pending | processing | completed | failed
        "paid_at": "2026-02-03T15:25:00Z",
        "access_granted": true,
        "book_purchase_id": "purchase_abc123"
    }
    """
```

#### 3. Webhook Handler (Payment Confirmation)
```javascript
// payment-service/src/controllers/webhookController.js

async function handleBankTransferWebhook(req, res) {
    // Called by bank/SePay when payment received
    const { transaction_id, amount, transfer_content, timestamp } = req.body;

    // 1. Extract order timestamp from transfer_content
    // "BOOK 1738567890" → 1738567890
    const orderTimestamp = transfer_content.match(/BOOK (\d+)/)?.[1];

    if (!orderTimestamp) {
        return res.status(400).json({ error: 'Invalid transfer content' });
    }

    // 2. Find matching order
    const order = await db.collection('book_cash_orders').findOne({
        order_id: { $regex: `^BOOK-${orderTimestamp}-` },
        status: 'pending',
        price_vnd: amount
    });

    if (!order) {
        return res.status(404).json({ error: 'Order not found' });
    }

    // 3. Update order status
    await db.collection('book_cash_orders').updateOne(
        { order_id: order.order_id },
        {
            $set: {
                status: 'completed',
                transaction_id: transaction_id,
                paid_at: new Date(timestamp),
                updated_at: new Date()
            }
        }
    );

    // 4. Call Python service to grant access
    await axios.post(
        `${PYTHON_SERVICE_URL}/api/v1/books/grant-access-from-order`,
        { order_id: order.order_id }
    );

    res.json({ success: true, order_id: order.order_id });
}
```

#### 4. Grant Access (Python Service)
```python
@router.post("/grant-access-from-order")
async def grant_access_from_order(request: GrantAccessRequest):
    """
    Cấp quyền đọc sách sau khi thanh toán thành công
    Internal endpoint - called by payment service webhook

    Request: { "order_id": "BOOK-1738567890-abcd1234" }
    """
    order_id = request.order_id

    # 1. Get order
    order = db.book_cash_orders.find_one({"order_id": order_id})
    if not order or order["status"] != "completed":
        raise HTTPException(400, "Invalid order")

    if order["access_granted"]:
        return {"success": True, "message": "Access already granted"}

    # 2. Create book_purchases record (same as point purchase)
    purchase_id = f"purchase_{uuid.uuid4().hex[:16]}"
    access_expires_at = None
    if order["purchase_type"] == "one_time":
        access_expires_at = datetime.utcnow() + timedelta(hours=24)

    purchase_record = {
        "purchase_id": purchase_id,
        "user_id": order["user_id"],
        "book_id": order["book_id"],
        "purchase_type": order["purchase_type"],
        "points_spent": 0,  # Cash purchase, not points
        "cash_paid_vnd": order["price_vnd"],
        "payment_method": "BANK_TRANSFER_QR",
        "order_id": order_id,
        "access_expires_at": access_expires_at,
        "purchased_at": order["paid_at"]
    }

    db.book_purchases.insert_one(purchase_record)

    # 3. Update book stats (revenue in VND, not points)
    # Convert VND to points for stats (1000 VND = 1 point)
    points_equivalent = order["price_vnd"] // 1000
    owner_reward = int(points_equivalent * 0.8)
    system_fee = points_equivalent - owner_reward

    db.online_books.update_one(
        {"book_id": order["book_id"]},
        {
            "$inc": {
                "stats.total_revenue_points": points_equivalent,
                "stats.owner_reward_points": owner_reward,
                "stats.system_fee_points": system_fee,
                "stats.cash_revenue_vnd": order["price_vnd"],  # NEW: Track cash separately
                "community_config.total_purchases": 1
            }
        }
    )

    # 4. Credit owner earnings (VND or points?)
    # Option A: Credit as points (1000 VND = 1 point)
    # Option B: Track separately as cash_earnings_vnd
    owner_id = db.online_books.find_one({"book_id": order["book_id"]})["user_id"]
    db.user_subscriptions.update_one(
        {"user_id": owner_id},
        {
            "$inc": {
                "earnings_points": owner_reward,  # Or use cash_earnings_vnd
                "cash_earnings_vnd": int(order["price_vnd"] * 0.8)  # NEW field
            }
        }
    )

    # 5. Mark order as access granted
    db.book_cash_orders.update_one(
        {"order_id": order_id},
        {
            "$set": {
                "access_granted": True,
                "book_purchase_id": purchase_id,
                "updated_at": datetime.utcnow()
            }
        }
    )

    return {
        "success": True,
        "order_id": order_id,
        "purchase_id": purchase_id
    }
```

### VietQR Integration

```python
# src/services/vietqr_service.py

import httpx
from typing import Dict, Any

class VietQRService:
    """Service for generating VietQR codes"""

    BASE_URL = "https://api.vietqr.io/v2"

    async def generate_qr_code(
        self,
        bank_bin: str,        # Bank BIN code (e.g., "970436" for Vietcombank)
        account_number: str,
        amount: int,
        description: str,
        account_name: str
    ) -> Dict[str, Any]:
        """
        Generate QR code for bank transfer

        Returns:
        {
            "code": "00",
            "desc": "Success",
            "data": {
                "qrCode": "00020101021238...",  # QR code content
                "qrDataURL": "data:image/png;base64,..."  # Base64 image
            }
        }
        """
        url = f"{self.BASE_URL}/generate"

        payload = {
            "accountNo": account_number,
            "accountName": account_name,
            "acqId": bank_bin,
            "amount": amount,
            "addInfo": description,
            "format": "text",
            "template": "compact"  # or "compact2", "qr_only"
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            return response.json()

# Bank BIN codes reference
BANK_BINS = {
    "Vietcombank": "970436",
    "Techcombank": "970407",
    "BIDV": "970418",
    "VietinBank": "970415",
    "ACB": "970416",
    "MBBank": "970422",
    "Sacombank": "970403"
}
```

### Frontend Integration

```typescript
// Example: Create QR order and display QR code

async function purchaseBookWithQR(bookId: string, purchaseType: string) {
    // 1. Create order
    const response = await fetch(`/api/v1/books/${bookId}/create-qr-order`, {
        method: 'POST',
        headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ purchase_type: purchaseType })
    });

    const order = await response.json();

    // 2. Display QR code to user
    showQRCodeModal({
        qrCodeUrl: order.qr_code_url,  // Display this image
        amount: order.price_vnd,
        bankAccount: order.bank_account,
        orderId: order.order_id,
        expiresAt: order.expires_at
    });

    // 3. Poll order status every 5 seconds
    const pollInterval = setInterval(async () => {
        const statusResponse = await fetch(`/api/v1/books/orders/${order.order_id}`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });

        const status = await statusResponse.json();

        if (status.status === 'completed' && status.access_granted) {
            clearInterval(pollInterval);
            showSuccessMessage('Payment received! You now have access to the book.');
            redirectToBook(bookId);
        }
    }, 5000);
}
```

---

## 👥 Feature 2: Group Purchase System

### Overview
Cho phép owner bán sách theo gói nhóm (3-5-10 người) với giá ưu đãi, mỗi người sẽ có email để đăng nhập đọc sách.

### Requirements

**User Story:**
> Là owner của sách, tôi muốn tạo gói mua nhóm 10 người với giá 500k (thay vì 10 × 99k = 990k) để bán cho công ty/lớp học.

**Acceptance Criteria:**
- ✅ Owner setting: Bật/tắt group purchase, số lượng mặc định (3/5/10), giá tiền/points
- ✅ Custom group size: Owner có thể nhập số lượng tùy chỉnh
- ✅ Email allocation: Buyer cung cấp list emails khi mua hoặc add sau
- ✅ Email editable: Buyer có thể sửa emails sau khi mua
- ✅ Access management: Mỗi email tự động được cấp quyền đọc khi login
- ✅ Tracking: Owner xem được số lượng group purchases và email list

### Database Schema

#### Update: `AccessConfig` (book level)
```python
# src/models/book_models.py

class GroupPurchaseConfig(BaseModel):
    """Group purchase configuration"""

    enabled: bool = Field(False, description="Enable group purchase?")
    default_sizes: List[int] = Field(
        default=[3, 5, 10],
        description="Pre-defined group sizes"
    )
    allow_custom_size: bool = Field(
        True,
        description="Allow buyer to specify custom group size?"
    )

    # Pricing (Option 1: Points)
    pricing_points: Dict[int, int] = Field(
        default={},
        description="Group size → points price. E.g., {3: 250, 5: 400, 10: 750}"
    )

    # Pricing (Option 2: VND)
    pricing_vnd: Dict[int, int] = Field(
        default={},
        description="Group size → VND price. E.g., {3: 250000, 5: 400000, 10: 750000}"
    )

    # Custom pricing formula
    custom_price_formula: Optional[str] = Field(
        None,
        description="Formula for custom sizes. E.g., 'size * 80000' or 'forever_price * size * 0.8'"
    )

    max_group_size: int = Field(50, ge=1, le=1000, description="Maximum allowed group size")

class AccessConfig(BaseModel):
    # ... existing fields

    # NEW: Group purchase config
    group_purchase: Optional[GroupPurchaseConfig] = None
```

#### New Collection: `book_group_purchases`
```javascript
{
    group_purchase_id: "GP-{timestamp}-{user_short}",
    book_id: string,
    buyer_user_id: string,  // User who bought the group package

    // Group details
    group_size: number,     // Number of seats (e.g., 10)
    group_name: string,     // Optional group name (e.g., "Python Class 2026")

    // Payment info
    payment_method: "POINTS" | "BANK_TRANSFER_QR",
    total_price_points: number | null,
    total_price_vnd: number | null,
    currency: "POINTS" | "VND",
    order_id: string | null,  // Link to book_cash_orders if paid with QR

    // Email allocation
    allocated_emails: [
        {
            email: string,           // User email for access
            assigned_at: Date | null,
            user_id: string | null,  // Filled when user logs in
            last_accessed: Date | null,
            access_granted: boolean
        }
    ],
    emails_filled: number,   // Count of emails already assigned

    // Status
    status: "pending" | "active" | "completed" | "expired",
    purchased_at: Date,
    expires_at: Date | null,  // Optional expiry (e.g., 1 year)

    // Metadata
    created_at: Date,
    updated_at: Date
}

// Indexes
db.book_group_purchases.createIndex({ group_purchase_id: 1 }, { unique: true })
db.book_group_purchases.createIndex({ buyer_user_id: 1 })
db.book_group_purchases.createIndex({ book_id: 1 })
db.book_group_purchases.createIndex({ "allocated_emails.email": 1 })
db.book_group_purchases.createIndex({ "allocated_emails.user_id": 1 })
```

### API Endpoints

#### 1. Get Group Purchase Options
```python
@router.get("/{book_id}/group-purchase-options")
async def get_group_purchase_options(book_id: str):
    """
    Lấy thông tin group purchase options

    Response:
    {
        "enabled": true,
        "default_sizes": [3, 5, 10],
        "allow_custom_size": true,
        "pricing_points": {
            "3": 250,
            "5": 400,
            "10": 750
        },
        "pricing_vnd": {
            "3": 250000,
            "5": 400000,
            "10": 750000
        },
        "max_group_size": 50,
        "forever_view_points": 99  // For reference
    }
    """
```

#### 2. Create Group Purchase (Points)
```python
@router.post("/{book_id}/purchase-group")
async def purchase_group(
    book_id: str,
    request: PurchaseGroupRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Mua gói nhóm với points hoặc cash

    Request Body:
    {
        "group_size": 10,
        "group_name": "Python Class 2026",  // Optional
        "emails": [  // Optional - can add later
            "user1@gmail.com",
            "user2@gmail.com",
            ...
        ],
        "payment_method": "POINTS"  // or "BANK_TRANSFER_QR"
    }

    Response (if POINTS):
    {
        "group_purchase_id": "GP-1738567890-abcd1234",
        "book_id": "book_123",
        "group_size": 10,
        "total_price_points": 750,
        "remaining_balance": 250,
        "status": "active"
    }

    Response (if QR):
    {
        "group_purchase_id": "GP-1738567890-abcd1234",
        "order_id": "BOOK-1738567891-abcd1234",
        "qr_code_url": "https://img.vietqr.io/...",
        "amount": 750000,
        "status": "pending"
    }
    """
```

**Implementation:**
```python
async def purchase_group(book_id, request, current_user):
    user_id = current_user["uid"]

    # 1. Get book and group purchase config
    book = db.online_books.find_one({"book_id": book_id})
    group_config = book["access_config"]["group_purchase"]

    if not group_config["enabled"]:
        raise HTTPException(400, "Group purchase not available")

    # 2. Validate group size
    if not group_config["allow_custom_size"]:
        if request.group_size not in group_config["default_sizes"]:
            raise HTTPException(400, "Invalid group size")
    elif request.group_size > group_config["max_group_size"]:
        raise HTTPException(400, f"Max group size is {group_config['max_group_size']}")

    # 3. Calculate price
    if request.payment_method == "POINTS":
        # Get price from config or calculate
        price_points = group_config["pricing_points"].get(str(request.group_size))

        if not price_points and group_config["custom_price_formula"]:
            # Evaluate formula: "size * 80" or "forever_price * size * 0.8"
            formula = group_config["custom_price_formula"]
            price_points = eval_price_formula(
                formula,
                size=request.group_size,
                forever_price=book["access_config"]["forever_view_points"]
            )

        if not price_points:
            raise HTTPException(400, "Price not configured for this group size")

        # Check balance
        subscription = db.user_subscriptions.find_one({"user_id": user_id})
        if subscription["points_remaining"] < price_points:
            raise HTTPException(400, "Insufficient balance")

        # Deduct points
        db.user_subscriptions.update_one(
            {"user_id": user_id},
            {
                "$inc": {
                    "points_remaining": -price_points,
                    "points_used": price_points
                }
            }
        )

        # Create group purchase record
        group_purchase_id = f"GP-{int(datetime.utcnow().timestamp())}-{user_id[:8]}"

        allocated_emails = []
        if request.emails:
            allocated_emails = [
                {
                    "email": email,
                    "assigned_at": datetime.utcnow(),
                    "user_id": None,
                    "last_accessed": None,
                    "access_granted": False
                }
                for email in request.emails[:request.group_size]
            ]

        group_purchase = {
            "group_purchase_id": group_purchase_id,
            "book_id": book_id,
            "buyer_user_id": user_id,
            "group_size": request.group_size,
            "group_name": request.group_name,
            "payment_method": "POINTS",
            "total_price_points": price_points,
            "total_price_vnd": None,
            "currency": "POINTS",
            "order_id": None,
            "allocated_emails": allocated_emails,
            "emails_filled": len(allocated_emails),
            "status": "active",
            "purchased_at": datetime.utcnow(),
            "expires_at": None,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }

        db.book_group_purchases.insert_one(group_purchase)

        # Update book stats
        owner_reward = int(price_points * 0.8)
        system_fee = price_points - owner_reward

        db.online_books.update_one(
            {"book_id": book_id},
            {
                "$inc": {
                    "stats.total_revenue_points": price_points,
                    "stats.owner_reward_points": owner_reward,
                    "stats.system_fee_points": system_fee,
                    "stats.group_purchases_count": 1,
                    "stats.group_purchases_seats": request.group_size,
                    "community_config.total_purchases": 1
                }
            }
        )

        return {
            "group_purchase_id": group_purchase_id,
            "book_id": book_id,
            "group_size": request.group_size,
            "total_price_points": price_points,
            "remaining_balance": subscription["points_remaining"] - price_points,
            "status": "active"
        }

    elif request.payment_method == "BANK_TRANSFER_QR":
        # Similar to individual QR purchase, but create group purchase record
        # Return QR code and order_id
        # Group purchase status = "pending" until payment confirmed
        pass
```

#### 3. Manage Emails (Add/Edit)
```python
@router.put("/group-purchases/{group_purchase_id}/emails")
async def update_group_emails(
    group_purchase_id: str,
    request: UpdateGroupEmailsRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Update emails for group purchase

    Request Body:
    {
        "emails": [
            "user1@gmail.com",
            "user2@gmail.com",
            ...  // Up to group_size emails
        ]
    }

    Response:
    {
        "group_purchase_id": "GP-1738567890-abcd1234",
        "emails_filled": 10,
        "group_size": 10,
        "allocated_emails": [...]
    }
    """
    user_id = current_user["uid"]

    # 1. Get group purchase
    gp = db.book_group_purchases.find_one({"group_purchase_id": group_purchase_id})

    if gp["buyer_user_id"] != user_id:
        raise HTTPException(403, "Not authorized")

    # 2. Validate email count
    if len(request.emails) > gp["group_size"]:
        raise HTTPException(400, f"Maximum {gp['group_size']} emails allowed")

    # 3. Update allocated emails
    allocated_emails = []
    for email in request.emails:
        # Keep existing user_id if email already assigned
        existing = next((e for e in gp["allocated_emails"] if e["email"] == email), None)

        allocated_emails.append({
            "email": email,
            "assigned_at": datetime.utcnow(),
            "user_id": existing["user_id"] if existing else None,
            "last_accessed": existing["last_accessed"] if existing else None,
            "access_granted": existing["access_granted"] if existing else False
        })

    db.book_group_purchases.update_one(
        {"group_purchase_id": group_purchase_id},
        {
            "$set": {
                "allocated_emails": allocated_emails,
                "emails_filled": len(allocated_emails),
                "updated_at": datetime.utcnow()
            }
        }
    )

    return {
        "group_purchase_id": group_purchase_id,
        "emails_filled": len(allocated_emails),
        "group_size": gp["group_size"],
        "allocated_emails": allocated_emails
    }
```

#### 4. Grant Access on Login
```python
# Middleware: When user logs in, check if their email is in any group purchase

async def check_group_purchase_access(user_email: str, user_id: str):
    """
    Called after user login to grant access from group purchases
    """
    # Find group purchases with this email
    group_purchases = db.book_group_purchases.find({
        "allocated_emails.email": user_email,
        "status": "active"
    })

    for gp in group_purchases:
        # Update user_id in allocated_emails
        db.book_group_purchases.update_one(
            {
                "group_purchase_id": gp["group_purchase_id"],
                "allocated_emails.email": user_email
            },
            {
                "$set": {
                    "allocated_emails.$.user_id": user_id,
                    "allocated_emails.$.last_accessed": datetime.utcnow(),
                    "allocated_emails.$.access_granted": True
                }
            }
        )

        # Create book_purchases record for this user
        purchase_id = f"purchase_{uuid.uuid4().hex[:16]}"

        purchase_record = {
            "purchase_id": purchase_id,
            "user_id": user_id,
            "book_id": gp["book_id"],
            "purchase_type": "forever",  # Group purchase = forever access
            "points_spent": 0,
            "group_purchase_id": gp["group_purchase_id"],
            "access_expires_at": gp["expires_at"],
            "purchased_at": gp["purchased_at"]
        }

        db.book_purchases.insert_one(purchase_record)
```

#### 5. List Group Purchases (Buyer)
```python
@router.get("/me/group-purchases")
async def list_my_group_purchases(
    current_user: dict = Depends(get_current_user)
):
    """
    Liệt kê các group purchase đã mua

    Response:
    {
        "total": 2,
        "group_purchases": [
            {
                "group_purchase_id": "GP-1738567890-abcd1234",
                "book_id": "book_123",
                "book_title": "Python Guide",
                "group_size": 10,
                "emails_filled": 8,
                "total_price_points": 750,
                "status": "active",
                "purchased_at": "2026-02-03T10:00:00Z"
            }
        ]
    }
    """
```

---

## 🎁 Feature 3: Referral Code System

### Overview
Mỗi user có thể tạo mã referral để bán sách, owner setting commission policy (e.g., referrer 15%, buyer discount 5%).

### Requirements

**User Story:**
> Là owner, tôi muốn add email người giới thiệu để sinh mã ref cho họ. Khi user khác mua sách nhập mã ref này, người giới thiệu nhận 15 points và buyer giảm 5%.

**Acceptance Criteria:**
- ✅ Owner setting: % commission cho referrer, % discount cho buyer
- ✅ Owner manually add referrer emails → auto-generate ref codes
- ✅ 1 email = 1 mã ref cho 1 quyển sách (không duplicate)
- ✅ Buyer nhập mã ref khi purchase → apply discount
- ✅ Track referral stats: số lượng sales, revenue của mỗi referrer
- ✅ Privacy: Only owner và chính referrer mới xem được stats của referrer đó

### Database Schema

#### Update: `AccessConfig` (book level)
```python
# src/models/book_models.py

class ReferralConfig(BaseModel):
    """Referral program configuration"""

    enabled: bool = Field(False, description="Enable referral program?")

    # Commission structure
    referrer_commission_percent: float = Field(
        15.0,
        ge=0,
        le=50,
        description="Commission % for referrer (e.g., 15 = 15%)"
    )
    buyer_discount_percent: float = Field(
        5.0,
        ge=0,
        le=50,
        description="Discount % for buyer (e.g., 5 = 5% off)"
    )

    # Commission type
    commission_in_points: bool = Field(
        True,
        description="Pay commission in points (True) or VND (False)"
    )

    # Auto-approval
    auto_approve_referrers: bool = Field(
        False,
        description="Auto-approve referrer requests (or require owner approval)"
    )

class AccessConfig(BaseModel):
    # ... existing fields

    # NEW: Referral config
    referral: Optional[ReferralConfig] = None
```

#### New Collection: `book_referral_codes`
```javascript
{
    referral_code: string,       // Unique code (e.g., "PYTHON-JOHN-ABC123")
    book_id: string,
    book_owner_id: string,       // Book owner user_id

    // Referrer info
    referrer_email: string,      // Email of person selling
    referrer_user_id: string | null,  // Filled when they log in
    referrer_name: string | null,

    // Commission settings (snapshot at creation time)
    referrer_commission_percent: number,
    buyer_discount_percent: number,
    commission_in_points: boolean,

    // Stats
    total_sales: number,         // Total number of sales via this code
    total_revenue_points: number,
    total_revenue_vnd: number,
    total_commission_earned: number,  // In points or VND

    // Status
    status: "active" | "suspended" | "expired",
    created_at: Date,
    created_by: string,          // Owner user_id
    expires_at: Date | null,     // Optional expiry date

    // Metadata
    notes: string | null,        // Owner notes about this referrer
    last_used_at: Date | null,
    updated_at: Date
}

// Indexes
db.book_referral_codes.createIndex({ referral_code: 1 }, { unique: true })
db.book_referral_codes.createIndex({ book_id: 1, referrer_email: 1 }, { unique: true })  // 1 email = 1 code per book
db.book_referral_codes.createIndex({ book_owner_id: 1 })
db.book_referral_codes.createIndex({ referrer_user_id: 1 })
db.book_referral_codes.createIndex({ referrer_email: 1 })
```

#### New Collection: `book_referral_sales`
```javascript
{
    sale_id: "REF_SALE-{timestamp}-{random}",
    referral_code: string,
    book_id: string,

    // Purchase info
    purchase_id: string,          // Link to book_purchases
    buyer_user_id: string,
    purchase_type: string,        // "one_time" | "forever" | "pdf_download"

    // Pricing
    original_price_points: number,
    discount_amount: number,      // Buyer discount
    final_price_paid: number,
    commission_amount: number,    // Referrer commission

    // Referrer info (snapshot)
    referrer_email: string,
    referrer_user_id: string | null,

    // Status
    commission_paid: boolean,
    commission_paid_at: Date | null,

    // Timestamps
    purchased_at: Date,
    created_at: Date
}

// Indexes
db.book_referral_sales.createIndex({ sale_id: 1 }, { unique: true })
db.book_referral_sales.createIndex({ referral_code: 1 })
db.book_referral_sales.createIndex({ buyer_user_id: 1 })
db.book_referral_sales.createIndex({ referrer_user_id: 1 })
db.book_referral_sales.createIndex({ book_id: 1 })
```

### API Endpoints

#### 1. Create Referral Code (Owner)
```python
@router.post("/{book_id}/referral-codes")
async def create_referral_code(
    book_id: str,
    request: CreateReferralCodeRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Owner tạo mã referral cho email người giới thiệu

    Request Body:
    {
        "referrer_email": "john@gmail.com",
        "referrer_name": "John Doe",  // Optional
        "notes": "Friend from university"  // Optional
    }

    Response:
    {
        "referral_code": "PYTHON-JOHN-ABC123",
        "book_id": "book_123",
        "referrer_email": "john@gmail.com",
        "commission_percent": 15,
        "discount_percent": 5,
        "status": "active"
    }
    """
    user_id = current_user["uid"]

    # 1. Verify ownership
    book = db.online_books.find_one({"book_id": book_id, "user_id": user_id})
    if not book:
        raise HTTPException(403, "Not authorized")

    referral_config = book["access_config"]["referral"]
    if not referral_config["enabled"]:
        raise HTTPException(400, "Referral program not enabled")

    # 2. Check if email already has a code for this book
    existing = db.book_referral_codes.find_one({
        "book_id": book_id,
        "referrer_email": request.referrer_email
    })

    if existing:
        raise HTTPException(409, "Referral code already exists for this email")

    # 3. Generate unique referral code
    # Format: BOOKSLUG-FIRSTNAME-RANDOM
    book_slug = book["slug"].upper()[:10]
    name_part = request.referrer_email.split("@")[0].upper()[:6]
    random_part = uuid.uuid4().hex[:6].upper()

    referral_code = f"{book_slug}-{name_part}-{random_part}"

    # 4. Create referral code record
    ref_code_doc = {
        "referral_code": referral_code,
        "book_id": book_id,
        "book_owner_id": user_id,
        "referrer_email": request.referrer_email,
        "referrer_user_id": None,  # Filled when they log in
        "referrer_name": request.referrer_name,
        "referrer_commission_percent": referral_config["referrer_commission_percent"],
        "buyer_discount_percent": referral_config["buyer_discount_percent"],
        "commission_in_points": referral_config["commission_in_points"],
        "total_sales": 0,
        "total_revenue_points": 0,
        "total_revenue_vnd": 0,
        "total_commission_earned": 0,
        "status": "active",
        "created_at": datetime.utcnow(),
        "created_by": user_id,
        "expires_at": None,
        "notes": request.notes,
        "last_used_at": None,
        "updated_at": datetime.utcnow()
    }

    db.book_referral_codes.insert_one(ref_code_doc)

    # 5. Send email to referrer with their code
    await send_referral_code_email(
        email=request.referrer_email,
        referral_code=referral_code,
        book_title=book["title"],
        commission_percent=referral_config["referrer_commission_percent"],
        discount_percent=referral_config["buyer_discount_percent"]
    )

    return {
        "referral_code": referral_code,
        "book_id": book_id,
        "referrer_email": request.referrer_email,
        "commission_percent": referral_config["referrer_commission_percent"],
        "discount_percent": referral_config["buyer_discount_percent"],
        "status": "active"
    }
```

#### 2. List Referral Codes (Owner)
```python
@router.get("/{book_id}/referral-codes")
async def list_referral_codes(
    book_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Owner xem danh sách tất cả referral codes

    Response:
    {
        "total": 5,
        "referral_codes": [
            {
                "referral_code": "PYTHON-JOHN-ABC123",
                "referrer_email": "john@gmail.com",
                "referrer_name": "John Doe",
                "total_sales": 12,
                "total_revenue_points": 1188,  // 12 × 99
                "total_commission_earned": 178,  // 12 × 99 × 15%
                "status": "active",
                "created_at": "2026-02-01T10:00:00Z"
            }
        ]
    }
    """
```

#### 3. Get Referral Stats (Referrer or Owner)
```python
@router.get("/referral-codes/{referral_code}/stats")
async def get_referral_stats(
    referral_code: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Xem stats của mã referral

    Privacy: Only owner hoặc chính referrer mới xem được

    Response:
    {
        "referral_code": "PYTHON-JOHN-ABC123",
        "book_id": "book_123",
        "book_title": "Python Complete Guide",
        "total_sales": 12,
        "total_revenue_points": 1188,
        "total_commission_earned": 178,
        "commission_percent": 15,
        "recent_sales": [
            {
                "sale_id": "REF_SALE-1738567890-xyz",
                "buyer_email": "buyer1@gmail.com",  // Masked: "buy***@gmail.com"
                "final_price_paid": 94,  // 99 - 5%
                "commission_amount": 15,  // 99 × 15%
                "purchased_at": "2026-02-03T14:30:00Z"
            }
        ]
    }
    """
    user_id = current_user["uid"]

    # 1. Get referral code
    ref_code = db.book_referral_codes.find_one({"referral_code": referral_code})
    if not ref_code:
        raise HTTPException(404, "Referral code not found")

    # 2. Check authorization
    is_owner = ref_code["book_owner_id"] == user_id
    is_referrer = (
        ref_code["referrer_user_id"] == user_id or
        current_user.get("email") == ref_code["referrer_email"]
    )

    if not (is_owner or is_referrer):
        raise HTTPException(403, "Not authorized to view this referral code stats")

    # 3. Get recent sales
    sales = db.book_referral_sales.find(
        {"referral_code": referral_code}
    ).sort("purchased_at", -1).limit(20)

    recent_sales = []
    for sale in sales:
        # Mask buyer email for privacy (unless owner viewing)
        buyer_email = sale["buyer_email"] if is_owner else mask_email(sale["buyer_email"])

        recent_sales.append({
            "sale_id": sale["sale_id"],
            "buyer_email": buyer_email,
            "final_price_paid": sale["final_price_paid"],
            "commission_amount": sale["commission_amount"],
            "purchased_at": sale["purchased_at"]
        })

    # 4. Get book info
    book = db.online_books.find_one({"book_id": ref_code["book_id"]})

    return {
        "referral_code": referral_code,
        "book_id": ref_code["book_id"],
        "book_title": book["title"],
        "total_sales": ref_code["total_sales"],
        "total_revenue_points": ref_code["total_revenue_points"],
        "total_commission_earned": ref_code["total_commission_earned"],
        "commission_percent": ref_code["referrer_commission_percent"],
        "recent_sales": recent_sales
    }

def mask_email(email: str) -> str:
    """Mask email for privacy: john@gmail.com → joh***@gmail.com"""
    local, domain = email.split("@")
    masked_local = local[:3] + "***" if len(local) > 3 else "***"
    return f"{masked_local}@{domain}"
```

#### 4. Purchase with Referral Code
```python
@router.post("/{book_id}/purchase")
async def purchase_book(
    book_id: str,
    request: PurchaseBookRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Mua sách với optional referral code

    Request Body:
    {
        "purchase_type": "forever",
        "referral_code": "PYTHON-JOHN-ABC123"  // Optional
    }

    Response:
    {
        "purchase_id": "purchase_abc123",
        "original_price": 99,
        "discount_applied": 5,  // 5% discount
        "final_price": 94,
        "referrer_commission": 15,  // 15% commission
        "referral_code": "PYTHON-JOHN-ABC123"
    }
    """
    user_id = current_user["uid"]

    # ... existing purchase logic

    # NEW: Apply referral code if provided
    discount_amount = 0
    commission_amount = 0
    referral_code = None

    if request.referral_code:
        # 1. Validate referral code
        ref_code = db.book_referral_codes.find_one({
            "referral_code": request.referral_code,
            "book_id": book_id,
            "status": "active"
        })

        if not ref_code:
            raise HTTPException(400, "Invalid referral code")

        # 2. Calculate discount and commission
        original_price = points_cost  # From existing logic
        discount_percent = ref_code["buyer_discount_percent"]
        commission_percent = ref_code["referrer_commission_percent"]

        discount_amount = int(original_price * discount_percent / 100)
        commission_amount = int(original_price * commission_percent / 100)

        # 3. Apply discount to final price
        points_cost = original_price - discount_amount

        referral_code = request.referral_code

    # ... existing purchase logic with adjusted points_cost

    # After successful purchase:
    if referral_code:
        # 1. Record sale
        sale_id = f"REF_SALE-{int(datetime.utcnow().timestamp())}-{uuid.uuid4().hex[:6]}"

        sale_record = {
            "sale_id": sale_id,
            "referral_code": referral_code,
            "book_id": book_id,
            "purchase_id": purchase_id,
            "buyer_user_id": user_id,
            "buyer_email": current_user.get("email"),
            "purchase_type": request.purchase_type,
            "original_price_points": original_price,
            "discount_amount": discount_amount,
            "final_price_paid": points_cost,
            "commission_amount": commission_amount,
            "referrer_email": ref_code["referrer_email"],
            "referrer_user_id": ref_code["referrer_user_id"],
            "commission_paid": False,
            "commission_paid_at": None,
            "purchased_at": datetime.utcnow(),
            "created_at": datetime.utcnow()
        }

        db.book_referral_sales.insert_one(sale_record)

        # 2. Update referral code stats
        db.book_referral_codes.update_one(
            {"referral_code": referral_code},
            {
                "$inc": {
                    "total_sales": 1,
                    "total_revenue_points": original_price,
                    "total_commission_earned": commission_amount
                },
                "$set": {
                    "last_used_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                }
            }
        )

        # 3. Credit commission to referrer (if they have account)
        if ref_code["referrer_user_id"]:
            db.user_subscriptions.update_one(
                {"user_id": ref_code["referrer_user_id"]},
                {
                    "$inc": {
                        "earnings_points": commission_amount,
                        "referral_commission_earned": commission_amount
                    }
                }
            )

            # Mark commission as paid
            db.book_referral_sales.update_one(
                {"sale_id": sale_id},
                {
                    "$set": {
                        "commission_paid": True,
                        "commission_paid_at": datetime.utcnow()
                    }
                }
            )

    return {
        "purchase_id": purchase_id,
        "original_price": original_price if referral_code else points_cost,
        "discount_applied": discount_amount,
        "final_price": points_cost,
        "referrer_commission": commission_amount if referral_code else 0,
        "referral_code": referral_code
    }
```

#### 5. My Referral Earnings (Referrer)
```python
@router.get("/me/referral-earnings")
async def get_my_referral_earnings(
    current_user: dict = Depends(get_current_user)
):
    """
    Xem tổng hoa hồng referral của tôi

    Response:
    {
        "total_commission_earned": 450,
        "total_sales_count": 30,
        "active_referral_codes": 3,
        "top_books": [
            {
                "book_id": "book_123",
                "book_title": "Python Guide",
                "referral_code": "PYTHON-JOHN-ABC123",
                "sales_count": 12,
                "commission_earned": 178
            }
        ]
    }
    """
```

---

## 📊 Database Schema Design

### Summary of New Collections

1. **`book_cash_orders`**: QR payment orders (cash purchases)
2. **`book_group_purchases`**: Group purchase packages
3. **`book_referral_codes`**: Referral codes for affiliates
4. **`book_referral_sales`**: Sales tracking via referral codes

### Updated Collections

```javascript
// online_books - Add new fields to stats
stats: {
    // ... existing fields

    // NEW: Cash revenue tracking
    cash_revenue_vnd: number,

    // NEW: Group purchase stats
    group_purchases_count: number,
    group_purchases_seats: number,  // Total seats sold

    // NEW: Referral stats
    referral_sales_count: number,
    referral_commissions_paid: number
}

// user_subscriptions - Add new fields
{
    // ... existing fields

    // NEW: Cash earnings (from VND purchases)
    cash_earnings_vnd: number,

    // NEW: Referral commissions
    referral_commission_earned: number
}

// book_purchases - Add new fields
{
    // ... existing fields

    // NEW: Cash purchase link
    cash_paid_vnd: number | null,
    order_id: string | null,

    // NEW: Group purchase link
    group_purchase_id: string | null,

    // NEW: Referral link
    referral_sale_id: string | null
}
```

---

## 🔌 API Endpoints Design

### Complete Endpoint List

#### QR Payment System
```
POST   /api/v1/books/{book_id}/create-qr-order           # Create QR payment order
GET    /api/v1/books/orders/{order_id}                   # Check order status
POST   /api/v1/books/grant-access-from-order             # Internal: Grant access after payment
GET    /api/v1/books/me/cash-orders                      # List my cash orders
POST   /webhook/book-payment-confirmation                 # Webhook from bank/SePay
```

#### Group Purchase System
```
GET    /api/v1/books/{book_id}/group-purchase-options    # Get group options
POST   /api/v1/books/{book_id}/purchase-group            # Buy group package
PUT    /api/v1/books/group-purchases/{gp_id}/emails      # Update group emails
GET    /api/v1/books/me/group-purchases                  # List my group purchases
GET    /api/v1/books/{book_id}/group-purchases (owner)   # Owner view all groups
```

#### Referral System
```
POST   /api/v1/books/{book_id}/referral-codes            # Owner: Create referral code
GET    /api/v1/books/{book_id}/referral-codes            # Owner: List all codes
DELETE /api/v1/books/referral-codes/{code}               # Owner: Deactivate code
GET    /api/v1/books/referral-codes/{code}/stats         # View stats (owner or referrer)
GET    /api/v1/books/me/referral-earnings                # My referral earnings
POST   /api/v1/books/{book_id}/purchase (with ref_code)  # Purchase with referral
```

#### Admin Endpoints
```
POST   /api/v1/admin/books/orders/{order_id}/confirm     # Manually confirm payment
GET    /api/v1/admin/books/orders                        # List all pending orders
GET    /api/v1/admin/books/referral-stats                # Overall referral stats
```

---

## 🔗 Integration with Existing System

### Compatibility Checks

#### 1. Payment Service (Node.js)
**Current:**
- SePay integration for subscriptions/points
- Webhook handling for payment confirmation

**Integration:**
- ✅ **Reuse:** SePay merchant account, signature generation, webhook pattern
- ✅ **Add:** New webhook handler for book cash orders
- ✅ **Update:** Add admin bank account config to `.env`

```javascript
// payment-service/.env
ADMIN_BANK_NAME=Vietcombank
ADMIN_ACCOUNT_NUMBER=0123456789
ADMIN_ACCOUNT_NAME=NGUYEN VAN A
ADMIN_BANK_BRANCH=Chi nhánh TP.HCM
VIETQR_ENABLED=true
```

#### 2. Book Purchase System (Python)
**Current:**
- Point-based purchases only
- 80/20 revenue split
- `book_purchases` collection

**Integration:**
- ✅ **Extend:** Support both points and cash purchases
- ✅ **Backward compatible:** Existing point purchases work unchanged
- ✅ **Add:** New fields `cash_paid_vnd`, `order_id`, `group_purchase_id`, `referral_sale_id`

#### 3. Access Control
**Current:**
- Check `book_purchases` for access

**Integration:**
- ✅ **No change:** Same access check logic
- ✅ **Extend:** Group purchase emails auto-create `book_purchases` on login

---

## ⚡ Implementation Phases

### Phase 1: QR Payment System (Week 1-2)
**Priority:** HIGH

**Tasks:**
1. ✅ Create `book_cash_orders` collection + indexes
2. ✅ Add admin bank account config to payment service
3. ✅ Implement VietQR API integration
4. ✅ Create QR order endpoint (Python)
5. ✅ Create webhook handler (Node.js)
6. ✅ Implement access granting logic
7. ✅ Frontend: QR code display + order status polling
8. ✅ Testing: End-to-end QR payment flow

**Deliverables:**
- Users can create QR order and pay via bank transfer
- Automatic access granting after payment confirmation
- Manual confirmation endpoint for admin

### Phase 2: Group Purchase System (Week 3-4)
**Priority:** MEDIUM

**Tasks:**
1. ✅ Create `book_group_purchases` collection + indexes
2. ✅ Update `AccessConfig` model with `GroupPurchaseConfig`
3. ✅ Implement group purchase endpoint (points)
4. ✅ Implement email management endpoint
5. ✅ Add login middleware to check group purchase emails
6. ✅ Frontend: Group purchase UI + email management
7. ✅ Testing: Group purchase flow + email allocation

**Deliverables:**
- Owner can enable group purchases with custom pricing
- Buyer can purchase group packages
- Email-based access distribution

### Phase 3: Referral System (Week 5-6)
**Priority:** MEDIUM

**Tasks:**
1. ✅ Create `book_referral_codes` + `book_referral_sales` collections
2. ✅ Update `AccessConfig` model with `ReferralConfig`
3. ✅ Implement referral code creation (owner)
4. ✅ Implement purchase with referral code
5. ✅ Implement referral stats endpoints
6. ✅ Commission tracking and payment
7. ✅ Frontend: Referral code management UI
8. ✅ Testing: Referral flow + commission calculation

**Deliverables:**
- Owner can create referral codes for affiliates
- Buyer can use referral codes for discounts
- Referrer earns commissions
- Privacy-protected stats viewing

### Phase 4: Admin Dashboard (Week 7)
**Priority:** LOW

**Tasks:**
1. ✅ Manual payment confirmation UI
2. ✅ Pending orders dashboard
3. ✅ Referral overview stats
4. ✅ Group purchase monitoring

**Deliverables:**
- Admin dashboard for payment management
- System-wide referral analytics

---

## 🔒 Security & Validation

### Critical Security Measures

#### 1. QR Payment System
- ✅ Order expiry: 30 minutes (auto-delete old orders)
- ✅ Unique transfer content: Prevent duplicate payments
- ✅ Amount validation: Webhook must match order amount
- ✅ Status check: Only "pending" orders can be confirmed
- ✅ Double-spending prevention: Check if access already granted

#### 2. Group Purchase System
- ✅ Email validation: Valid email format
- ✅ Group size limits: Max 50 (configurable)
- ✅ Ownership check: Only buyer can edit emails
- ✅ Duplicate prevention: 1 email = 1 access per group
- ✅ Privacy: Email list only visible to buyer and book owner

#### 3. Referral System
- ✅ Unique codes: 1 email = 1 code per book
- ✅ Code validation: Active status check
- ✅ Stats privacy: Only owner and referrer can view
- ✅ Commission limits: Max 50% commission
- ✅ Self-referral prevention: Buyer cannot use their own code

### Input Validation

```python
# Validation schemas

class CreateQROrderRequest(BaseModel):
    purchase_type: PurchaseType  # "one_time" | "forever" | "pdf_download"

class PurchaseGroupRequest(BaseModel):
    group_size: int = Field(..., ge=1, le=1000)
    group_name: Optional[str] = Field(None, max_length=100)
    emails: Optional[List[EmailStr]] = Field(None, max_items=1000)
    payment_method: Literal["POINTS", "BANK_TRANSFER_QR"]

class UpdateGroupEmailsRequest(BaseModel):
    emails: List[EmailStr] = Field(..., max_items=1000)

class CreateReferralCodeRequest(BaseModel):
    referrer_email: EmailStr
    referrer_name: Optional[str] = Field(None, max_length=100)
    notes: Optional[str] = Field(None, max_length=500)

class PurchaseBookRequest(BaseModel):
    purchase_type: PurchaseType
    referral_code: Optional[str] = Field(None, pattern="^[A-Z0-9-]+$", max_length=50)
```

---

## 🧪 Testing Plan

### Unit Tests

#### QR Payment
- ✅ QR code generation
- ✅ Order creation with valid/invalid data
- ✅ Order expiry logic
- ✅ Webhook signature validation
- ✅ Access granting after payment

#### Group Purchase
- ✅ Group pricing calculation
- ✅ Email allocation logic
- ✅ Email update validation
- ✅ Login-triggered access granting

#### Referral System
- ✅ Referral code generation uniqueness
- ✅ Discount calculation
- ✅ Commission calculation
- ✅ Stats privacy enforcement

### Integration Tests

#### End-to-End Flows
1. **QR Payment Flow:**
   - User creates QR order
   - User scans QR and transfers money
   - Webhook confirms payment
   - Access granted automatically

2. **Group Purchase Flow:**
   - Owner enables group purchase
   - Buyer purchases 10-seat package
   - Buyer adds 10 emails
   - Users with emails log in → auto-access

3. **Referral Flow:**
   - Owner adds referrer email
   - Referral code generated
   - Buyer uses code → gets discount
   - Referrer earns commission
   - Stats updated correctly

### Performance Tests
- ✅ 100 concurrent QR order creations
- ✅ 1000 group purchase email allocations
- ✅ 10000 referral code validations

---

## 📈 Analytics & Monitoring

### Metrics to Track

#### QR Payment System
- Total orders created
- Payment success rate
- Average payment confirmation time
- Revenue: points vs cash (VND)

#### Group Purchase System
- Group purchases count
- Average group size
- Email fill rate (emails assigned / total seats)
- Revenue from groups vs individual

#### Referral System
- Active referral codes count
- Referral conversion rate
- Top referrers by sales
- Total commissions paid

### Monitoring Endpoints

```python
@router.get("/admin/analytics/book-payment-overview")
async def get_payment_analytics(
    start_date: date,
    end_date: date,
    current_user: dict = Depends(require_admin)
):
    """
    Analytics dashboard for book payments

    Response:
    {
        "period": "2026-02-01 to 2026-02-28",
        "qr_payments": {
            "total_orders": 450,
            "completed_orders": 380,
            "total_revenue_vnd": 42500000,
            "avg_order_value": 111842
        },
        "group_purchases": {
            "total_groups": 25,
            "total_seats_sold": 185,
            "avg_group_size": 7.4,
            "total_revenue_points": 12000
        },
        "referrals": {
            "total_sales": 120,
            "total_commission_paid": 1800,
            "active_codes": 45,
            "conversion_rate": 12.5
        }
    }
    """
```

---

## 🚀 Future Enhancements

### Potential Features

1. **Subscription-based Book Access**
   - Monthly/yearly subscription for book library
   - Similar to Kindle Unlimited

2. **Gift Codes**
   - Generate gift codes for book access
   - Send as presents

3. **Bulk Discounts**
   - Auto-discount for large group sizes
   - Volume pricing tiers

4. **Referral Tiers**
   - Bronze/Silver/Gold referrer levels
   - Higher commission for top performers

5. **Payment Methods**
   - Add Momo, ZaloPay, Crypto
   - International payments (PayPal, Stripe)

6. **Analytics Dashboard**
   - Owner dashboard with charts
   - Sales trends, best-performing books

---

## 📝 Conclusion

### Summary

This document provides a comprehensive analysis and design for implementing:

1. **QR Payment System:** Direct bank transfer payments for books
2. **Group Purchase System:** Bulk purchases with email-based access
3. **Referral Code System:** Affiliate program with commission tracking

### Next Steps

1. ✅ Review and approve this design document
2. ✅ Create detailed technical specifications
3. ✅ Implement Phase 1 (QR Payment) first
4. ✅ Gather user feedback after each phase
5. ✅ Iterate based on analytics and user behavior

### Questions to Resolve

1. **Revenue Split:** Should cash purchases use same 80/20 split as points?
2. **Commission Payment:** Auto-pay commissions or require manual withdrawal?
3. **Group Expiry:** Should group access expire after X months?
4. **Referral Approval:** Auto-approve all referrers or require owner approval?
5. **Currency:** Support both VND and points, or cash-only for QR payments?

---

**Document Version:** 1.0
**Last Updated:** February 3, 2026
**Author:** WordAI Team
**Status:** Draft - Pending Review
