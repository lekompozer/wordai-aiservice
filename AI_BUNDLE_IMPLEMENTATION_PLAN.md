# Kế Hoạch Triển Khai — AI Bundle Subscription

> **Phạm vi:** Gói đăng ký năm tích hợp AI Learning Assistant + AI Code Studio
> **Mô hình đại lý:** Tách biệt hoàn toàn với hệ thống Conversations Learning
> **Ngày lập:** March 2026

---

## Tổng Quan Kiến Trúc

```
┌─────────────────────────────────────────────────────────────────┐
│                         PARTNERS PAGE                           │
│  Login Firebase → query cả 2 hệ thống đại lý → show theo tab  │
│                                                                 │
│  Tab "Conversations Learning"   │  Tab "AI Bundle"             │
│  (dùng collection: affiliates)  │  (dùng: ai_bundle_affiliates)│
└─────────────────────────────────────────────────────────────────┘
         │                                      │
         ▼                                      ▼
  affiliates collection              ai_bundle_affiliates collection
  supervisors collection             ai_bundle_supervisors collection
  affiliate_commissions              ai_bundle_commissions
  supervisor_commissions             ai_bundle_supervisor_commissions
  affiliate_withdrawals              ai_bundle_withdrawals
```

**Nguyên tắc thiết kế:**
- Mỗi sản phẩm có **collections riêng biệt** — không share với Conversations
- Partners page dùng **1 Firebase login duy nhất**, hiển thị tab theo sản phẩm nào user được đăng ký
- Admin đăng ký đại lý AI Bundle **riêng** — không tự động kế thừa từ Conversations
- Commission logic tương đương nhau nhưng **không cross-product**

---

## Phase 1 — Database Schema

### 1.1 Collection: `ai_bundle_affiliates`

```json
{
  "_id": ObjectId,
  "user_id": "firebase_uid_or_null",   // null cho đến khi đại lý login lần đầu
  "email": "partner@email.com",
  "name": "Nguyễn Văn A",
  "code": "AIB001",                     // unique, uppercase, prefix "AIB"
  "tier": 1,                            // 1 = trung tâm/tổ chức, 2 = cá nhân/CTV
  "is_active": true,
  "supervisor_id": "ObjectId_string",   // ref → ai_bundle_supervisors._id
  "total_earned": 0,
  "pending_balance": 0,
  "total_referred_users": 0,
  "bank_info": {
    "bank_name": "Vietcombank",
    "account_number": "1234567890",
    "account_name": "NGUYEN VAN A"
  },
  "notes": "",                          // ghi chú nội bộ
  "created_at": ISODate,
  "updated_at": ISODate
}
```

**Indexes cần tạo:**
```js
db.ai_bundle_affiliates.createIndex({ "code": 1 }, { unique: true })
db.ai_bundle_affiliates.createIndex({ "user_id": 1 })
db.ai_bundle_affiliates.createIndex({ "email": 1 })
db.ai_bundle_affiliates.createIndex({ "supervisor_id": 1 })
```

### 1.2 Collection: `ai_bundle_supervisors`

```json
{
  "_id": ObjectId,
  "user_id": "firebase_uid_or_null",
  "email": "supervisor@email.com",
  "name": "Trần Thị B",
  "code": "AIBS001",                    // unique, prefix "AIBS"
  "is_active": true,
  "total_earned": 0,
  "pending_balance": 0,
  "bank_info": { ... },
  "created_at": ISODate,
  "updated_at": ISODate
}
```

**Indexes:**
```js
db.ai_bundle_supervisors.createIndex({ "code": 1 }, { unique: true })
db.ai_bundle_supervisors.createIndex({ "user_id": 1 })
db.ai_bundle_supervisors.createIndex({ "email": 1 })
```

### 1.3 Collection: `ai_bundle_commissions`

```json
{
  "_id": ObjectId,
  "affiliate_id": "ObjectId_string",
  "affiliate_code": "AIB001",
  "user_id": "buyer_firebase_uid",
  "subscription_id": "ObjectId_string",
  "plan": "basic",                      // "basic" | "advanced"
  "amount_paid_by_user": 399000,
  "commission_rate": 0.25,
  "commission_amount": 99750,
  "price_tier": "tier_2",
  "status": "pending",                  // pending | approved | paid | cancelled
  "created_at": ISODate
}
```

**Indexes:**
```js
db.ai_bundle_commissions.createIndex({ "affiliate_id": 1, "created_at": -1 })
db.ai_bundle_commissions.createIndex({ "affiliate_code": 1, "status": 1 })
db.ai_bundle_commissions.createIndex({ "user_id": 1 })
```

### 1.4 Collection: `ai_bundle_supervisor_commissions`

```json
{
  "_id": ObjectId,
  "supervisor_id": "ObjectId_string",
  "supervisor_code": "AIBS001",
  "affiliate_id": "ObjectId_string",
  "affiliate_code": "AIB001",
  "user_id": "buyer_firebase_uid",
  "subscription_id": "ObjectId_string",
  "plan": "basic",
  "amount_paid_by_user": 399000,
  "commission_rate": 0.10,
  "commission_amount": 39900,
  "status": "pending",
  "created_at": ISODate
}
```

### 1.5 Collection: `ai_bundle_withdrawals`

```json
{
  "_id": ObjectId,
  "role": "affiliate",                  // "affiliate" | "supervisor"
  "account_id": "ObjectId_string",      // affiliate or supervisor _id
  "account_code": "AIB001",
  "amount": 200000,
  "status": "pending",                  // pending | approved | paid | rejected
  "bank_name": "Vietcombank",
  "bank_account_number": "1234567890",
  "bank_account_name": "NGUYEN VAN A",
  "notes": "",
  "admin_note": "",
  "processed_by": null,
  "processed_at": null,
  "created_at": ISODate,
  "updated_at": ISODate
}
```

### 1.6 Collection: `user_ai_bundle_subscriptions`

```json
{
  "_id": ObjectId,
  "user_id": "firebase_uid",
  "plan": "basic",                      // "basic" | "advanced"
  "status": "active",                   // active | expired | cancelled
  "price_tier": "tier_2",
  "amount_paid": 399000,
  "currency": "VND",
  "payment_id": "PAY_xxx",
  "order_invoice_number": "AIB_xxx",
  "payment_method": "SEPAY_BANK_TRANSFER",
  "affiliate_code": "AIB001",
  "affiliate_id": "ObjectId_string",
  "supervisor_id": "ObjectId_string",
  "requests_monthly_limit": 100,        // 100 for basic, 200 for advanced
  "requests_used_this_month": 0,
  "requests_reset_date": ISODate,       // 1st of next month
  "started_at": ISODate,
  "expires_at": ISODate,                // started_at + 365 days
  "created_at": ISODate,
  "updated_at": ISODate
}
```

**Indexes:**
```js
db.user_ai_bundle_subscriptions.createIndex({ "user_id": 1, "status": 1 })
db.user_ai_bundle_subscriptions.createIndex({ "order_invoice_number": 1 }, { unique: true })
db.user_ai_bundle_subscriptions.createIndex({ "expires_at": 1 })
db.user_ai_bundle_subscriptions.createIndex({ "affiliate_code": 1 })
```

---

## Phase 2 — Python Models (`src/models/`)

**File:** `src/models/ai_bundle_subscription.py`

```python
AI_BUNDLE_PRICING = {
    "no_code":  {"basic": 449_000, "advanced": 899_000},
    "tier_2":   {"basic": 399_000, "advanced": 799_000},
    "tier_1":   {"basic": 359_000, "advanced": 719_000},
}

AI_BUNDLE_REQUESTS = {
    "basic": 100,
    "advanced": 200,
}

AFFILIATE_COMMISSION_RATES = {1: 0.40, 2: 0.25}   # mirror Conversations rates
SUPERVISOR_COMMISSION_RATE = 0.10
```

**File:** `src/models/ai_bundle_affiliate.py`

Pydantic models:
- `AiBundleAffiliateDashboard`
- `AiBundleWithdrawRequest`
- `AiBundleCheckoutPreviewRequest` / `Response`
- `ActivateAiBundleSubscriptionRequest` / `Response`

---

## Phase 3 — Python API Routes (`src/api/`)

### 3.1 `ai_bundle_subscription_routes.py`

| Method | Path | Mô tả | Auth |
|--------|------|-------|------|
| `GET` | `/api/v1/ai-bundle/plans` | Danh sách gói + giá (có `?code=`) | Public |
| `GET` | `/api/v1/ai-bundle/me` | Subscription status + quota | Required |
| `POST` | `/api/v1/ai-bundle/activate` | Kích hoạt sau thanh toán | X-Service-Secret |

**Logic quota check** (`GET /me`):
```python
# Tự động reset nếu đã qua ngày reset
if sub["requests_reset_date"] < now:
    new_reset = first_day_of_next_month(now)
    db.user_ai_bundle_subscriptions.update_one(
        {"_id": sub["_id"]},
        {"$set": {"requests_used_this_month": 0,
                  "requests_reset_date": new_reset}}
    )
```

### 3.2 `ai_bundle_affiliate_routes.py`

| Method | Path | Mô tả | Auth |
|--------|------|-------|------|
| `GET` | `/api/v1/ai-bundle/affiliate/validate/{code}` | Validate mã đại lý | Public |
| `GET` | `/api/v1/ai-bundle/affiliate/me` | Dashboard đại lý | Required |
| `GET` | `/api/v1/ai-bundle/affiliate/transactions` | Lịch sử hoa hồng | Required |
| `GET` | `/api/v1/ai-bundle/affiliate/customers` | Danh sách khách mua | Required |
| `POST` | `/api/v1/ai-bundle/affiliate/withdraw` | Yêu cầu rút tiền | Required |

**Auto-link Firebase UID** (giống `_get_affiliate` của Conversations):
- Lần đầu login: tìm theo `email` → set `user_id` = Firebase UID
- Lookup ưu tiên `user_id`, fallback sang `email`

### 3.3 `ai_bundle_supervisor_routes.py`

| Method | Path | Mô tả | Auth |
|--------|------|-------|------|
| `GET` | `/api/v1/ai-bundle/supervisor/me` | Dashboard supervisor | Required |
| `GET` | `/api/v1/ai-bundle/supervisor/affiliates` | Danh sách đại lý đang quản lý | Required |
| `GET` | `/api/v1/ai-bundle/supervisor/commissions` | Lịch sử hoa hồng supervisor | Required |
| `POST` | `/api/v1/ai-bundle/supervisor/withdraw` | Yêu cầu rút tiền | Required |

### 3.4 `ai_bundle_admin_routes.py`

| Method | Path | Mô tả | Auth |
|--------|------|-------|------|
| `POST` | `/api/v1/admin/ai-bundle/affiliates` | Tạo đại lý mới | Admin |
| `PUT` | `/api/v1/admin/ai-bundle/affiliates/{id}` | Cập nhật đại lý | Admin |
| `POST` | `/api/v1/admin/ai-bundle/supervisors` | Tạo supervisor mới | Admin |
| `GET` | `/api/v1/admin/ai-bundle/withdrawals` | Danh sách yêu cầu rút | Admin |
| `PUT` | `/api/v1/admin/ai-bundle/withdrawals/{id}` | Approve/reject rút | Admin |

### 3.5 Access Control Middleware

**File:** `src/middleware/ai_bundle_quota.py`

```python
async def check_ai_bundle_quota(user_id: str, db) -> None:
    """
    Kiểm tra và tăng counter request. Raise 403 nếu hết quota hoặc hết hạn.
    Sử dụng find_one_and_update atomic để tránh race condition.
    """
    now = datetime.utcnow()

    # Auto-reset nếu đến tháng mới
    result = db["user_ai_bundle_subscriptions"].find_one_and_update(
        {
            "user_id": user_id,
            "status": "active",
            "expires_at": {"$gt": now},
            "requests_reset_date": {"$lte": now}  # cần reset
        },
        {
            "$set": {
                "requests_used_this_month": 0,
                "requests_reset_date": first_day_next_month(now)
            }
        }
    )

    # Tăng counter nếu còn quota
    updated = db["user_ai_bundle_subscriptions"].find_one_and_update(
        {
            "user_id": user_id,
            "status": "active",
            "expires_at": {"$gt": now},
            "$expr": {
                "$lt": ["$requests_used_this_month", "$requests_monthly_limit"]
            }
        },
        {"$inc": {"requests_used_this_month": 1}},
        return_document=True
    )

    if not updated:
        # Kiểm tra lý do thất bại để trả về message chính xác
        sub = db["user_ai_bundle_subscriptions"].find_one({
            "user_id": user_id, "status": "active"
        })
        if not sub:
            raise HTTPException(
                status_code=403,
                detail="Bạn cần đăng ký gói AI Bundle để sử dụng tính năng này."
            )
        if sub["expires_at"] <= now:
            raise HTTPException(
                status_code=403,
                detail="Gói AI Bundle của bạn đã hết hạn. Vui lòng gia hạn."
            )
        raise HTTPException(
            status_code=429,
            detail=f"Đã dùng hết {sub['requests_monthly_limit']} requests tháng này. "
                   f"Reset vào {sub['requests_reset_date'].strftime('%d/%m/%Y')}."
        )
```

**Tích hợp vào 5 AI endpoints:**
```python
# Trong learning_assistant_routes.py và software_lab_ai_routes.py
from src.middleware.ai_bundle_quota import check_ai_bundle_quota

@router.post("/solve")
async def solve_homework(request, user = Depends(get_current_user), db = Depends(get_db)):
    # Kiểm tra AI Bundle quota TRƯỚC khi trừ points
    has_bundle = False
    try:
        await check_ai_bundle_quota(user["uid"], db)
        has_bundle = True
    except HTTPException as e:
        if e.status_code == 403:
            # Không có gói — fallback sang points_service (behavior cũ)
            await points_service.deduct_points(...)
        else:
            raise  # 429 = hết quota → raise luôn

    # Tiếp tục xử lý job...
```

> **Nguyên tắc:** User có AI Bundle → KHÔNG trừ điểm. User không có → trừ điểm như cũ. Hai hệ thống song song, không xung đột.

---

## Phase 4 — Node.js Payment Service

### 4.1 Validation Schema (`middleware/validation.js`)

```javascript
// Thêm vào schemas object:
aiBundleCheckout: Joi.object({
    plan: Joi.string().valid('basic', 'advanced').required(),
    price_tier: Joi.string().valid('no_code', 'tier_1', 'tier_2').required(),
    affiliate_code: Joi.string().alphanum().max(30).optional().allow(null, ''),
    amount: Joi.number().integer().min(359000).max(899000).required(),
})
```

### 4.2 Route (`routes/paymentRoutes.js`)

```javascript
// AI Bundle subscription — REQUIRES AUTHENTICATION
router.post(
    '/ai-bundle/checkout',
    authenticate,
    validateBody(schemas.aiBundleCheckout),
    asyncHandler(paymentController.createAiBundleCheckout)
);
```

### 4.3 Controller (`controllers/paymentController.js`)

**`createAiBundleCheckout`** (pattern giống `createConversationLearningCheckout`):

```javascript
// Validate affiliate code nếu có
if (affiliate_code) {
    const aff = await db.collection('ai_bundle_affiliates').findOne(
        { code: affiliate_code.toUpperCase() },
        { projection: { is_active: 1, user_id: 1, tier: 1 } }  // include ALL fields
    );
    if (!aff) throw new AppError('Mã đại lý AI Bundle không tồn tại.', 404);
    if (!aff.is_active) throw new AppError('Đại lý chưa được kích hoạt.', 403);
}

// Server-side price validation (không tin client-side amount)
const PRICES = {
    no_code:  { basic: 449000, advanced: 899000 },
    tier_2:   { basic: 399000, advanced: 799000 },
    tier_1:   { basic: 359000, advanced: 719000 },
};
const expectedAmount = PRICES[price_tier][plan];
if (amount !== expectedAmount) {
    throw new AppError(`Số tiền không hợp lệ. Expected: ${expectedAmount}`, 400);
}

// Tạo payment record với plan_type = 'ai_bundle'
await paymentsCollection.insertOne({
    plan_type: 'ai_bundle',
    plan: plan,
    price_tier: price_tier,
    affiliate_code: affiliate_code || null,
    // ...
});
```

### 4.4 IPN Handler (`controllers/webhookController.js`)

```javascript
// Thêm vào IPN handler (sau block conversation_learning):
if (payment.plan_type === 'ai_bundle') {
    await redisClient.lPush('queue:payment_events', JSON.stringify({
        event_type: 'ai_bundle_subscription_paid',
        payment_id: payment._id.toString(),
        order_invoice_number: payment.order_invoice_number,
        user_id: payment.user_id,
        plan: payment.plan,                  // "basic" | "advanced"
        price_tier: payment.price_tier,
        amount_paid: payment.price,
        affiliate_code: payment.affiliate_code || null,
    }));
    logger.info(`✅ AI Bundle subscription queued: ${order_invoice_number}`);
}
```

---

## Phase 5 — Worker Extension

**File:** `src/workers/payment_events_worker.py` — thêm handler mới

```python
PLAN_REQUESTS = {"basic": 100, "advanced": 200}
AI_BUNDLE_COMMISSION_RATES = {1: 0.40, 2: 0.25}
AI_BUNDLE_SUPERVISOR_RATE = 0.10


def _handle_ai_bundle_subscription_paid(db, event: dict):
    """
    Full subscription + commission cascade cho AI Bundle payment.
    Tương tự conversation_subscription_paid nhưng dùng collections riêng.
    """
    user_id = event["user_id"]
    plan = event.get("plan", "basic")          # "basic" | "advanced"
    price_tier = event.get("price_tier", "no_code")
    amount_paid = int(event.get("amount_paid", 0))
    payment_id = event.get("payment_id", "")
    order_invoice_number = event.get("order_invoice_number", "")
    affiliate_code = event.get("affiliate_code") or None
    now = datetime.utcnow()

    # ── 1. Create / extend subscription (12 tháng cố định) ──────────────────
    existing = db["user_ai_bundle_subscriptions"].find_one({
        "user_id": user_id,
        "status": "active",
        "expires_at": {"$gte": now}
    })

    requests_limit = PLAN_REQUESTS.get(plan, 100)
    expires_at = now + timedelta(days=365)
    next_reset = first_day_next_month(now)

    if existing:
        # Gia hạn: push expires_at thêm 1 năm từ ngày hiện tại (hoặc từ ngày hết hạn cũ)
        new_expires = max(existing["expires_at"], now) + timedelta(days=365)
        db["user_ai_bundle_subscriptions"].update_one(
            {"_id": existing["_id"]},
            {"$set": {
                "expires_at": new_expires,
                "plan": plan,
                "requests_monthly_limit": requests_limit,
                "updated_at": now,
            }}
        )
        subscription_id = str(existing["_id"])
    else:
        sub_doc = {
            "user_id": user_id,
            "plan": plan,
            "status": "active",
            "price_tier": price_tier,
            "amount_paid": amount_paid,
            "payment_id": payment_id,
            "order_invoice_number": order_invoice_number,
            "payment_method": "SEPAY_BANK_TRANSFER",
            "affiliate_code": affiliate_code,
            "requests_monthly_limit": requests_limit,
            "requests_used_this_month": 0,
            "requests_reset_date": next_reset,
            "started_at": now,
            "expires_at": expires_at,
            "created_at": now,
            "updated_at": now,
        }
        result = db["user_ai_bundle_subscriptions"].insert_one(sub_doc)
        subscription_id = str(result.inserted_id)

    # ── 2. Affiliate commission cascade ─────────────────────────────────────
    if affiliate_code:
        aff = db["ai_bundle_affiliates"].find_one(
            {"code": affiliate_code.upper(), "is_active": True}
        )
        if aff:
            rate = AI_BUNDLE_COMMISSION_RATES.get(aff["tier"], 0.0)
            commission = round(amount_paid * rate)

            db["ai_bundle_commissions"].insert_one({
                "affiliate_id": str(aff["_id"]),
                "affiliate_code": affiliate_code.upper(),
                "user_id": user_id,
                "subscription_id": subscription_id,
                "plan": plan,
                "amount_paid_by_user": amount_paid,
                "commission_rate": rate,
                "commission_amount": commission,
                "price_tier": price_tier,
                "status": "pending",
                "created_at": now,
            })
            db["ai_bundle_affiliates"].update_one(
                {"_id": aff["_id"]},
                {"$inc": {
                    "total_earned": commission,
                    "pending_balance": commission,
                    "total_referred_users": 1,
                }, "$set": {"updated_at": now}}
            )

            # ── 3. Supervisor commission cascade ────────────────────────────
            supervisor_id = aff.get("supervisor_id")
            if supervisor_id:
                sup = db["ai_bundle_supervisors"].find_one(
                    {"_id": ObjectId(supervisor_id), "is_active": True}
                )
                if sup:
                    sup_commission = round(amount_paid * AI_BUNDLE_SUPERVISOR_RATE)
                    db["ai_bundle_supervisor_commissions"].insert_one({
                        "supervisor_id": supervisor_id,
                        "supervisor_code": sup["code"],
                        "affiliate_id": str(aff["_id"]),
                        "affiliate_code": affiliate_code.upper(),
                        "user_id": user_id,
                        "subscription_id": subscription_id,
                        "plan": plan,
                        "amount_paid_by_user": amount_paid,
                        "commission_rate": AI_BUNDLE_SUPERVISOR_RATE,
                        "commission_amount": sup_commission,
                        "status": "pending",
                        "created_at": now,
                    })
                    db["ai_bundle_supervisors"].update_one(
                        {"_id": sup["_id"]},
                        {"$inc": {
                            "total_earned": sup_commission,
                            "pending_balance": sup_commission,
                        }, "$set": {"updated_at": now}}
                    )

    # ── 4. Mark payment activated ────────────────────────────────────────────
    db["payments"].update_one(
        {"order_invoice_number": order_invoice_number},
        {"$set": {
            "subscription_activated": True,
            "subscription_id": subscription_id,
            "activated_at": now,
            "updated_at": now,
        }}
    )


# Trong PaymentEventsWorker.start() — thêm elif:
if event_type == "conversation_subscription_paid":
    _handle_conversation_subscription_paid(db, event)
elif event_type == "ai_bundle_subscription_paid":           # ← THÊM
    _handle_ai_bundle_subscription_paid(db, event)
```

> **Không cần worker mới** — tích hợp vào `learning-events-worker` qua `brpop` đang có (tiết kiệm ~350MB RAM).

---

## Phase 6 — Partners Page (Frontend Architecture)

### 6.1 API Backend phục vụ Partners Page

**Unified endpoint** để lấy tất cả sản phẩm của 1 partner:

```
GET /api/v1/partners/me
```

```json
{
  "products": [
    {
      "product": "conversations",
      "role": "affiliate",
      "tier": 2,
      "code": "WORD001",
      "is_active": true,
      "total_earned": 1200000,
      "available_balance": 800000,
      "pending_balance": 200000
    },
    {
      "product": "ai_bundle",
      "role": "supervisor",
      "code": "AIBS001",
      "is_active": true,
      "total_earned": 500000,
      "available_balance": 300000,
      "managed_affiliates_count": 5
    }
  ]
}
```

Logic backend:
```python
# GET /api/v1/partners/me
products = []

# Kiểm tra Conversations affiliate
conv_aff = db["affiliates"].find_one({"user_id": uid})
if conv_aff:
    products.append({"product": "conversations", "role": "affiliate", ...})

# Kiểm tra Conversations supervisor
conv_sup = db["supervisors"].find_one({"user_id": uid})
if conv_sup:
    products.append({"product": "conversations", "role": "supervisor", ...})

# Kiểm tra AI Bundle affiliate
ai_aff = db["ai_bundle_affiliates"].find_one({"user_id": uid})
if ai_aff:
    products.append({"product": "ai_bundle", "role": "affiliate", ...})

# Kiểm tra AI Bundle supervisor
ai_sup = db["ai_bundle_supervisors"].find_one({"user_id": uid})
if ai_sup:
    products.append({"product": "ai_bundle", "role": "supervisor", ...})

if not products:
    raise HTTPException(404, "Bạn không có tài khoản đối tác nào.")

return {"products": products}
```

### 6.2 Frontend Routing (Partners Page)

```
/partners                    → redirect → /partners/dashboard
/partners/dashboard          → GET /api/v1/partners/me → render tabs

Nếu có 1 sản phẩm:  → trực tiếp hiển thị dashboard đó
Nếu có 2+ sản phẩm: → hiển thị tabs chọn sản phẩm

Tab "Conversations Learning" → dùng /api/v1/affiliates/* hoặc /api/v1/supervisor/*
Tab "AI Bundle"              → dùng /api/v1/ai-bundle/affiliate/* hoặc /api/v1/ai-bundle/supervisor/*
```

### 6.3 Dashboard Data per Tab

**Conversations tab** (đã có, không thay đổi):
- Doanh thu hoa hồng, số học viên, lịch sử transaction, yêu cầu rút tiền

**AI Bundle tab** (mới):
- Doanh thu hoa hồng, số khách mua gói (basic/advanced riêng), lịch sử transaction, yêu cầu rút tiền
- Thêm: breakdown theo plan type (Cơ Bản vs Nâng Cao)

---

## Phase 7 — Deployment Order

### Bước 1: Database prep (không cần deploy code)

```bash
# Tạo indexes script
scripts/create_ai_bundle_indexes.py

# Chạy trên server
./copy-and-run.sh scripts/create_ai_bundle_indexes.py
```

### Bước 2: Python backend

Files cần tạo/sửa:
```
src/models/ai_bundle_subscription.py          [MỚI]
src/models/ai_bundle_affiliate.py             [MỚI]
src/api/ai_bundle_subscription_routes.py      [MỚI]
src/api/ai_bundle_affiliate_routes.py         [MỚI]
src/api/ai_bundle_supervisor_routes.py        [MỚI]
src/api/ai_bundle_admin_routes.py             [MỚI]
src/api/partners_routes.py                    [MỚI]
src/middleware/ai_bundle_quota.py             [MỚI]
src/workers/payment_events_worker.py          [SỬA — thêm handler]
src/api/learning_assistant_routes.py          [SỬA — thêm quota check]
src/api/software_lab_ai_routes.py             [SỬA — thêm quota check]
src/app.py                                    [SỬA — register routers]
```

Deploy: `./deploy-app-only.sh`

### Bước 3: Node.js payment service

Files cần sửa:
```
payment-service/src/middleware/validation.js          [SỬA]
payment-service/src/routes/paymentRoutes.js           [SỬA]
payment-service/src/controllers/paymentController.js  [SỬA]
payment-service/src/controllers/webhookController.js  [SỬA]
```

Deploy: `./deploy-compose-with-rollback.sh` (vì payment-service thay đổi)

### Bước 4: Tạo đại lý đầu tiên

```bash
# Dùng script, không push lên git
scripts/create_ai_bundle_affiliates.py
```

### Bước 5: Test end-to-end

| Test | Command |
|------|---------|
| Plan list (no code) | `curl http://localhost:8000/api/v1/ai-bundle/plans` |
| Plan list (with code) | `curl http://localhost:8000/api/v1/ai-bundle/plans?code=AIB001` |
| Validate affiliate code | `curl http://localhost:8000/api/v1/ai-bundle/affiliate/validate/AIB001` |
| Checkout (payment service) | `docker exec payment-service curl ...` |
| Partners unified endpoint | `curl -H "Authorization: Bearer TOKEN" http://localhost:8000/api/v1/partners/me` |
| Quota check | Call solve/grade endpoint 101 lần với gói basic → expect 429 on 101st |

---

## Phase 8 — Files Tạo Mới Chi Tiết

```
src/
├── models/
│   ├── ai_bundle_subscription.py      # Pricing config + Pydantic models
│   └── ai_bundle_affiliate.py         # Affiliate/Supervisor Pydantic models
├── api/
│   ├── ai_bundle_subscription_routes.py  # /api/v1/ai-bundle/plans, /me, /activate
│   ├── ai_bundle_affiliate_routes.py     # /api/v1/ai-bundle/affiliate/*
│   ├── ai_bundle_supervisor_routes.py    # /api/v1/ai-bundle/supervisor/*
│   ├── ai_bundle_admin_routes.py         # /api/v1/admin/ai-bundle/*
│   └── partners_routes.py               # /api/v1/partners/me (unified)
└── middleware/
    └── ai_bundle_quota.py              # check_ai_bundle_quota()

scripts/
└── create_ai_bundle_indexes.py         # Chạy 1 lần để tạo indexes (git-ignored)
```

---

## Tóm Tắt Phụ Thuộc

```
Phase 1 (DB) → Phase 2+3 (Python) → Phase 4 (Node.js) → Phase 5 (Worker)
                     ↓
              Phase 6 (Partners page — frontend, có thể làm song song sau Phase 3)
```

**Ước tính effort:**
| Phase | Effort |
|-------|--------|
| Database indexes script | ~30 phút |
| Python models | ~1 giờ |
| Python API routes (4 files) | ~3 giờ |
| Quota middleware + integration | ~1 giờ |
| Node.js payment service | ~1.5 giờ |
| Worker extension | ~1 giờ |
| Partners unified endpoint | ~45 phút |
| Test + debug end-to-end | ~2 giờ |
| **Tổng** | **~10.5 giờ** |
