# AI Bundle Payment API — Tài liệu Frontend

**Base URL Python API:** `https://ai.wordai.pro`
**Base URL Payment Service:** `https://ai.wordai.pro` (Nginx proxy → Node.js)
**Authentication:** Firebase Bearer Token — header `Authorization: Bearer <token>`

> ⚠️ **Lưu ý tên param quan trọng:**
> - Pagination dùng `page_size` (không phải `limit`)
> - Checkout field là `plan` (không phải `package_id`)
> - Validate code có 2 endpoint: `GET /plans?code=XXX` (public, không auth) và `GET /validate-code?code=XXX` (có auth — dùng ở màn hình checkout)

---

## Mục lục

1. [Luồng thanh toán tổng quan](#1-luồng-thanh-toán-tổng-quan)
2. [Bảng giá](#2-bảng-giá)
3. [Trial — Dùng thử 15 ngày](#3-trial--dùng-thử-15-ngày)
4. [Checkout — Tạo đơn thanh toán](#4-checkout--tạo-đơn-thanh-toán)
5. [Kiểm tra trạng thái đơn](#5-kiểm-tra-trạng-thái-đơn)
6. [Subscription Status — Trạng thái gói người dùng](#6-subscription-status--trạng-thái-gói-người-dùng)
7. [Affiliate Code — Mã đại lý](#7-affiliate-code--mã-đại-lý)
8. [Affiliate Dashboard (Đại lý)](#8-affiliate-dashboard-đại-lý)
9. [Admin — Quản lý hệ thống](#9-admin--quản-lý-hệ-thống)
10. [Error Codes](#10-error-codes)
11. [Checklist tích hợp](#11-checklist-tích-hợp)

---

## 1. Luồng thanh toán tổng quan

```
User  →  POST /api/payment/ai-bundle/checkout  (Node.js)
       ←  { form_fields, payment_url, order_invoice_number }

User  →  Submit form to SePay payment_url
       ←  SePay redirects to:
          https://wordai.pro/ai-tools/ai-bundle?tab=subscription

SePay →  Webhook IPN → payment-service
payment-service  →  LPUSH queue:payment_events → Redis
Python worker    →  kích hoạt user_ai_bundle_subscriptions
                 →  tính hoa hồng → ai_bundle_commissions

User  →  GET /api/v1/ai-bundle/me
       ←  { is_active: true, plan, requests_remaining, ... }
```

**Order prefix:** `AIB-{timestamp}-{uid_8chars}`

---

## 2. Bảng giá

| Plan | Requests/tháng | `no_code` | `tier_2` | `tier_1` |
|------|---------------|-----------|----------|----------|
| `basic` | 100 req/tháng | 449.000 ₫ | 399.000 ₫ | 359.000 ₫ |
| `advanced` | 200 req/tháng | 899.000 ₫ | 799.000 ₫ | 719.000 ₫ |

Thời hạn: **365 ngày**. Quota reset vào **ngày 1 UTC mỗi tháng**.

**Dùng thử:** 15 ngày / 20 lượt (hard cap, không reset giữa kỳ).

### `GET /api/v1/ai-bundle/plans` — Public, không cần auth

```
GET /api/v1/ai-bundle/plans
GET /api/v1/ai-bundle/plans?code=MADA123
```

Response:
```json
{
  "plans": [
    {
      "plan_id": "basic",
      "plan_label": "Gói Cơ Bản",
      "requests_per_month": 100,
      "months": 12,
      "price_tier": "tier_2",
      "original_price": 449000,
      "price": 399000,
      "is_popular": false,
      "features": [
        "100 AI requests / tháng (reset ngày 1)",
        "AI Giải bài tập (Learning Assistant)",
        "AI Chấm điểm bài làm (Learning Assistant)",
        "AI Tạo code (Code Studio)",
        "AI Giải thích code (Code Studio)",
        "AI Chuyển đổi code (Code Studio)",
        "Lịch sử không giới hạn"
      ]
    },
    {
      "plan_id": "advanced",
      "plan_label": "Gói Nâng Cao",
      "requests_per_month": 200,
      "months": 12,
      "price_tier": "tier_2",
      "original_price": 899000,
      "price": 799000,
      "is_popular": true,
      "features": ["..."]
    }
  ],
  "affiliate": { "code": "MADA123", "tier": 2 },
  "note": "Gói AI Bundle gồm AI Learning Assistant + AI Code Studio (3 tính năng cơ bản)."
}
```

Khi truyền `?code=MADA123` hợp lệ: `price_tier` chuyển thành `"tier_2"` hoặc `"tier_1"`, giá thay đổi, `affiliate: { "code": "MADA123", "tier": 2 }`.

Nếu `?code=` không truyền hoặc code không hợp lệ: `price_tier = "no_code"` và `affiliate = null`.

---

## 3. Trial — Dùng thử 15 ngày

### `POST /api/v1/ai-bundle/trial/activate`

**Auth:** Firebase Bearer Token ✅
Mỗi tài khoản chỉ được kích hoạt **1 lần duy nhất**.

Request: không cần body.

Response 200:
```json
{
  "success": true,
  "message": "Kích hoạt dùng thử AI Bundle thành công! Bạn có 15 ngày và 20 lượt sử dụng.",
  "plan": "trial",
  "is_trial": true,
  "requests_limit": 20,
  "trial_days_remaining": 15,
  "expires_at": "2026-03-26T09:00:00+00:00",
  "features": {
    "learning_assistant": true,
    "code_studio_basic": true
  }
}
```

Lỗi:
```json
// 409 — đã dùng thử rồi
{ "detail": "Bạn đã sử dụng dùng thử AI Bundle. Mỗi tài khoản chỉ được dùng thử 1 lần." }

// 409 — đang có gói trả phí
{ "detail": "Bạn đã có gói AI Bundle đang hoạt động." }
```

> **Logic UI:** Sau khi load `GET /me`, nếu `is_active: false` và `trial_used: false` → hiện nút "Dùng thử miễn phí 15 ngày". Nếu `trial_used: true` → ẩn nút này.

---

## 4. Checkout — Tạo đơn thanh toán

### `POST /api/payment/ai-bundle/checkout`

**Auth:** Firebase Bearer Token ✅

#### Request Body

```json
{
  "plan": "basic",
  "price_tier": "no_code",
  "amount": 449000,
  "affiliate_code": "MADA123"
}
```

| Field | Type | Required | Ghi chú |
|-------|------|----------|---------|
| `plan` | `"basic" \| "advanced"` | ✅ | **Không phải `package_id`** |
| `price_tier` | `"no_code" \| "tier_1" \| "tier_2"` | ✅ | Lấy từ validate-code hoặc mặc định `"no_code"` |
| `amount` | `integer` | ✅ | Server tự tính lại — phải khớp hoặc lỗi 400 |
| `affiliate_code` | `string` | ❌ | Optional, upper-cased server-side |

> ⚠️ **Server tự tính lại giá** từ `price_tier` + `plan`. Nếu `amount` lệch so với giá thực → lỗi 400.

#### Response 201

```json
{
  "payment_url": "https://qr.sepay.vn/pay",
  "order_invoice_number": "AIB-1741680000000-abc12345",
  "payment_id": "67a1b2c3d4e5f6789012345",
  "form_fields": {
    "merchant": "WORDAI",
    "operation": "PURCHASE",
    "payment_method": "BANK_TRANSFER",
    "order_amount": "449000",
    "currency": "VND",
    "order_invoice_number": "AIB-1741680000000-abc12345",
    "order_description": "WordAI AI Bundle - Gói Cơ Bản",
    "customer_id": "firebase_uid_here",
    "success_url": "https://wordai.pro/ai-tools/ai-bundle?tab=subscription",
    "error_url": "https://wordai.pro/ai-tools/ai-bundle?tab=subscription",
    "cancel_url": "https://wordai.pro/ai-tools/ai-bundle?tab=subscription",
    "signature": "base64_hmac_sha256_signature"
  },
  "amount": 449000,
  "plan": "basic",
  "price_tier": "no_code"
}
```

> ⚠️ Response key là `payment_url` (không phải `checkout_url`).

#### Cách submit form đến SePay

```javascript
async function startAiBundleCheckout(plan, priceTier, amount, affiliateCode) {
  const res = await fetch('/api/payment/ai-bundle/checkout', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${firebaseToken}`,
    },
    body: JSON.stringify({
      plan,                              // "basic" | "advanced"
      price_tier: priceTier,            // "no_code" | "tier_1" | "tier_2"
      amount,
      affiliate_code: affiliateCode || null,
    }),
  });

  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.message || 'Lỗi tạo đơn hàng');
  }

  const data = await res.json();

  // Lưu order_invoice_number vào localStorage để poll sau redirect
  localStorage.setItem('aib_pending_order', data.order_invoice_number);

  // Tạo form ẩn và submit đến SePay
  const form = document.createElement('form');
  form.method = 'POST';
  form.action = data.payment_url;   // <-- dùng payment_url

  Object.entries(data.form_fields).forEach(([key, value]) => {
    const input = document.createElement('input');
    input.type = 'hidden';
    input.name = key;
    input.value = value;
    form.appendChild(input);
  });

  document.body.appendChild(form);
  form.submit();
}
```

#### Error Responses

| Code | Tình huống |
|------|-----------|
| 400 | `plan` hoặc `price_tier` không hợp lệ |
| 400 | `amount` không khớp giá server |
| 401 | Firebase token thiếu/hết hạn |
| 403 | Mã đại lý chưa được kích hoạt |
| 403 | Mã đại lý chưa đăng nhập hệ thống |
| 404 | Mã đại lý không tồn tại |

---

## 5. Kiểm tra trạng thái đơn

### `GET /api/payment/status/:order_invoice_number`

**Auth:** Không cần.

```
GET /api/payment/status/AIB-1741680000000-abc12345
```

Response:
```json
{
  "success": true,
  "data": {
    "payment_id": "67a1b2c3d4e5f6789012345",
    "order_invoice_number": "AIB-1741680000000-abc12345",
    "status": "completed",
    "plan": "basic",
    "price": 449000,
    "created_at": "2026-03-11T09:00:00.000Z",
    "completed_at": "2026-03-11T09:05:00.000Z"
  }
}
```

**`status`:** `"pending"` → `"completed"` | `"failed"`

> Poll mỗi 2–3 giây tối đa 60 giây sau khi redirect về. Khi `status === "completed"` → gọi lại `GET /me`.

---

## 6. Subscription Status — Trạng thái gói người dùng

### `GET /api/v1/ai-bundle/me`

**Auth:** Firebase Bearer Token ✅

**Response — chưa có gói, chưa dùng thử:**
```json
{ "is_active": false, "is_trial": false, "trial_used": false }
```

**Response — chưa có gói, đã hết/dùng hết trial:**
```json
{ "is_active": false, "is_trial": false, "trial_used": true }
```

**Response — đang dùng trial:**
```json
{
  "is_active": true,
  "is_trial": true,
  "trial_days_remaining": 12,
  "trial_used": true,
  "plan": "trial",
  "plan_label": "Dùng thử (15 ngày)",
  "requests_monthly_limit": 20,
  "requests_used_this_month": 3,
  "requests_remaining": 17,
  "requests_reset_date": null,
  "started_at": "2026-03-11T09:00:00+00:00",
  "expires_at": "2026-03-26T09:00:00+00:00",
  "features": { "learning_assistant": true, "code_studio_basic": true }
}
```

**Response — đang có gói trả phí:**
```json
{
  "is_active": true,
  "is_trial": false,
  "trial_days_remaining": null,
  "trial_used": null,
  "plan": "basic",
  "plan_label": "Gói Cơ Bản",
  "requests_monthly_limit": 100,
  "requests_used_this_month": 23,
  "requests_remaining": 77,
  "requests_reset_date": "2026-04-01T00:00:00+00:00",
  "started_at": "2026-03-11T09:05:00+00:00",
  "expires_at": "2027-03-11T09:05:00+00:00",
  "features": { "learning_assistant": true, "code_studio_basic": true }
}
```

> Khi `is_active: true` và cả trial lẫn paid sub tồn tại: **paid được ưu tiên** (sort `is_trial` ascending).

> Dùng endpoint này để: hiển thị badge "AI Bundle", thanh tiến trình quota (`requests_used / requests_monthly_limit`), ẩn/hiện nút "Dùng thử" và "Nâng cấp".

---

## 7. Affiliate Code — Mã đại lý

Có **2 endpoint** khác nhau tùy context:

### `GET /api/v1/ai-bundle/plans?code=XXX` — Public (không auth)

Dùng khi **chưa đăng nhập** hoặc chỉ muốn hiển thị giá lên UI. Trả về toàn bộ plans với giá đã tính theo tier. Xem chi tiết tại [Bảng giá](#2-bảng-giá).

### `GET /api/v1/ai-bundle/validate-code?code=XXX` — Auth required ✅

Dùng ở **màn hình checkout sau khi đăng nhập** để validate mã trước khi tạo đơn.

```
GET /api/v1/ai-bundle/validate-code?code=MADA123
```

Response thành công:
```json
{
  "valid": true,
  "code": "MADA123",
  "affiliate_name": "Trung tâm Tiếng Anh ABC",
  "tier": 2,
  "tier_label": "Đại lý Cấp 2 (Cộng tác viên)",
  "discount_percent": 11,
  "plans": [
    {
      "plan_id": "basic",
      "original_price": 449000,
      "price": 399000,
      "requests_per_month": 100
    },
    {
      "plan_id": "advanced",
      "original_price": 899000,
      "price": 799000,
      "requests_per_month": 200
    }
  ]
}
```

Lỗi:
```json
// 404
{ "detail": { "error": "invalid_code", "message": "Mã đại lý không tồn tại." } }

// 403
{ "detail": { "error": "affiliate_not_active", "message": "Đại lý chưa được kích hoạt." } }

// 403
{ "detail": { "error": "affiliate_not_registered", "message": "Đại lý chưa đăng nhập lần nào. Vui lòng yêu cầu đại lý đăng nhập trước." } }
```

> Sau khi validate thành công, lưu `price_tier` (ví dụ `"tier_2"`) và truyền vào checkout request cùng `affiliate_code`.

---

## 8. Affiliate Dashboard (Đại lý)

Tất cả endpoint yêu cầu **Firebase Bearer Token**. Đại lý phải được tạo sẵn bởi Admin.
Auto-link Firebase UID qua email khi đại lý đăng nhập lần đầu.

---

### `GET /api/v1/ai-bundle/affiliate/me`

```json
{
  "code": "MADA123",
  "name": "Nguyễn Văn A",
  "email": "a@example.com",
  "tier": 2,
  "tier_label": "Đại lý cấp 2 (Cộng tác viên)",
  "is_active": true,
  "commission_rate": 0.25,
  "plan_prices": { "basic": 399000, "advanced": 799000 },
  "total_customers": 12,
  "total_earned": 2500000,
  "total_withdrawn": 1000000,
  "pending_balance": 200000,
  "available_balance": 1300000,
  "balances": {
    "total_earned": 2500000,
    "total_withdrawn": 1000000,
    "pending_balance": 200000,
    "available_balance": 1300000
  },
  "bank_info": { "bank_name": "Vietcombank", "account_number": "123...", "account_name": "NGUYEN VAN A" },
  "created_at": "2026-01-01T00:00:00"
}
```

---

### `GET /api/v1/ai-bundle/affiliate/students`

Query params: `?page=1&page_size=50` (**dùng `page_size`, không phải `limit`**)

```json
{
  "students": [
    {
      "user_id": "firebase_uid",
      "user_email": "user@example.com",
      "plan": "basic",
      "amount_paid": 399000,
      "commission_amount": 99750,
      "commission_rate": 0.25,
      "paid_at": "2026-03-10T14:00:00",
      "order_invoice_number": "AIB-..."
    }
  ],
  "total": 12,
  "page": 1,
  "page_size": 50,
  "total_pages": 1
}
```

---

### `GET /api/v1/ai-bundle/affiliate/transactions`

Query params: `?page=1&page_size=20` (**dùng `page_size`, không phải `limit`**)

```json
{
  "transactions": [
    {
      "id": "...",
      "user_id": "firebase_uid",
      "user_email": "user@example.com",
      "plan": "basic",
      "amount_paid": 399000,
      "commission_amount": 99750,
      "commission_rate": 0.25,
      "status": "confirmed",
      "created_at": "2026-03-10T14:00:00"
    }
  ],
  "total": 12,
  "page": 1,
  "page_size": 20,
  "total_pages": 1
}
```

---

### `GET /api/v1/ai-bundle/affiliate/withdrawals`

Query params: `?page=1&page_size=20`

```json
{
  "withdrawals": [
    {
      "id": "...",
      "amount": 1000000,
      "status": "pending",
      "bank_name": "Vietcombank",
      "bank_account_number": "1234567890",
      "bank_account_name": "NGUYEN VAN A",
      "notes": null,
      "admin_notes": null,
      "created_at": "2026-03-11T08:00:00",
      "processed_at": null
    }
  ],
  "total": 2,
  "page": 1,
  "page_size": 20,
  "total_pages": 1,
  "total_pending_amount": 1000000
}
```

---

### `POST /api/v1/ai-bundle/affiliate/withdraw`

Request:
```json
{
  "amount": 500000,
  "bank_name": "Vietcombank",
  "bank_account_number": "1234567890",
  "bank_account_name": "NGUYEN VAN A",
  "notes": "Rút tiền tháng 3"
}
```

> `bank_name/account_number/account_name` optional nếu đã lưu trong profile đại lý. Nếu không có ở cả hai nơi → lỗi 400.

Validation server-side:
- `amount` tối thiểu **100.000 ₫**, tối đa = `available_balance`
- Chặn nếu còn request `pending` chưa xử lý

Response 201:
```json
{
  "withdrawal_id": "...",
  "amount": 500000,
  "status": "pending",
  "message": "Yêu cầu rút tiền đã được ghi nhận."
}
```

---

## 9. Admin — Quản lý hệ thống

**Auth:** Firebase Bearer Token (admin account) HOẶC header `X-Service-Secret`
**Prefix:** `/api/v1/admin/ai-bundle`

---

### 9.1 Affiliates CRUD

#### `POST /api/v1/admin/ai-bundle/affiliates`

Request:
```json
{
  "code": "TRUNG_TAM_ABC",
  "name": "Trung tâm Tiếng Anh ABC",
  "tier": 1,
  "email": "contact@abc.edu.vn",
  "supervisor_id": "SUP001",
  "bank_info": { "bank_name": "Vietcombank", "account_number": "...", "account_name": "..." },
  "notes": "Đối tác đào tạo"
}
```

| Field | Type | Required | Ghi chú |
|-------|------|----------|---------|
| `code` | string | ✅ | Upper-cased, unique |
| `name` | string | ✅ | |
| `tier` | `1 \| 2` | ✅ | 1 = Trung tâm (40%), 2 = CTV (25%) |
| `email` | string | ❌ | Dùng để auto-link Firebase UID |
| `supervisor_id` | string | ❌ | Code của supervisor quản lý |
| `bank_info` | object | ❌ | |
| `notes` | string | ❌ | |

Response 201:
```json
{
  "id": "...",
  "code": "TRUNG_TAM_ABC",
  "name": "Trung tâm Tiếng Anh ABC",
  "tier": 1,
  "tier_label": "Đại lý cấp 1 (Trung tâm)",
  "is_active": true,
  "commission_rate": 0.40,
  "login_status": "chưa đăng nhập",
  "email": "contact@abc.edu.vn",
  "created_at": "2026-03-11T09:00:00"
}
```

---

#### `GET /api/v1/admin/ai-bundle/affiliates`

Query params: `?page=1&page_size=50&search=abc&tier=1&is_active=true`

| Param | Type | Mô tả |
|-------|------|-------|
| `page` | int | Trang (default: 1) |
| `page_size` | int | Số item/trang (default: 50, max: 200) |
| `search` | string | Tìm theo code / name / email (case-insensitive) |
| `tier` | `1 \| 2` | Lọc theo tier |
| `is_active` | bool | Lọc theo trạng thái |

```json
{
  "items": [
    {
      "id": "...",
      "code": "TRUNG_TAM_ABC",
      "name": "Trung tâm Tiếng Anh ABC",
      "tier": 1,
      "tier_label": "Đại lý cấp 1 (Trung tâm)",
      "is_active": true,
      "login_status": "đã đăng nhập",
      "email": "contact@abc.edu.vn",
      "user_id": "firebase_uid",
      "commission_rate": 0.40,
      "total_earned": 5000000,
      "total_referred_users": 25,
      "supervisor_id": "SUP001",
      "bank_info": { "bank_name": "...", "account_number": "...", "account_name": "..." },
      "notes": "...",
      "created_at": "2026-01-01T00:00:00",
      "updated_at": "..."
    }
  ],
  "total": 45,
  "page": 1,
  "page_size": 50,
  "total_pages": 1
}
```

---

#### `GET /api/v1/admin/ai-bundle/affiliates/{code}`

```json
{
  "id": "...",
  "code": "TRUNG_TAM_ABC",
  "name": "Trung tâm Tiếng Anh ABC",
  "tier": 1,
  "tier_label": "Đại lý cấp 1 (Trung tâm)",
  "commission_rate": 0.40,
  "is_active": true,
  "login_status": "đã đăng nhập",
  "user_id": "firebase_uid",
  "email": "contact@abc.edu.vn",
  "supervisor_id": "SUP001",
  "total_earned": 5000000,
  "total_referred_users": 25,
  "bank_info": { "bank_name": "...", "account_number": "...", "account_name": "..." },
  "notes": "...",
  "created_at": "...",
  "updated_at": "..."
}
```

---

#### `PUT /api/v1/admin/ai-bundle/affiliates/{code}`

Tất cả fields optional — chỉ truyền field cần thay đổi:

```json
{
  "name": "Tên mới",
  "tier": 2,
  "is_active": false,
  "email": "newemail@example.com",
  "supervisor_id": "SUP002",
  "bank_info": { "bank_name": "...", "account_number": "...", "account_name": "..." },
  "notes": "Ghi chú mới"
}
```

---

---

### 9.2 Affiliate Withdrawals

#### `GET /api/v1/admin/ai-bundle/withdrawals/list`

Query params: `?status=pending&page=1&page_size=50`

**`status`:** `"pending"` | `"approved"` | `"rejected"` (bỏ trống = tất cả)

```json
{
  "items": [
    {
      "id": "...",
      "affiliate_id": "...",
      "affiliate_code": "MADA123",
      "affiliate_name": "Nguyễn Văn A",
      "amount": 500000,
      "status": "pending",
      "bank_name": "Vietcombank",
      "bank_account_number": "1234567890",
      "bank_account_name": "NGUYEN VAN A",
      "notes": null,
      "admin_notes": null,
      "created_at": "2026-03-11T08:00:00",
      "processed_at": null
    }
  ],
  "total": 5,
  "page": 1,
  "page_size": 50,
  "total_pages": 1
}
```

---

#### `POST /api/v1/admin/ai-bundle/withdrawals/{id}/approve`

```json
{ "notes": "Đã chuyển khoản 11/3" }
```

Response:
```json
{ "withdrawal_id": "...", "status": "approved", "message": "Đã duyệt yêu cầu rút tiền." }
```

---

#### `POST /api/v1/admin/ai-bundle/withdrawals/{id}/reject`

```json
{ "reason": "Thông tin tài khoản không hợp lệ" }
```

Response:
```json
{ "withdrawal_id": "...", "status": "rejected", "message": "Đã từ chối yêu cầu rút tiền." }
```

> Khi reject: số dư `available_balance` của đại lý được hoàn lại tự động.

---

### 9.3 Supervisors CRUD

#### `POST /api/v1/admin/ai-bundle/supervisors`

```json
{
  "code": "SUP001",
  "name": "Nguyễn Thị B",
  "email": "b@example.com",
  "bank_info": { "bank_name": "...", "account_number": "...", "account_name": "..." },
  "notes": "Quản lý khu vực miền Nam"
}
```

---

#### `GET /api/v1/admin/ai-bundle/supervisors`

Query params: `?page=1&page_size=50&search=nguyen&is_active=true`

| Param | Type | Mô tả |
|-------|------|-------|
| `page` | int | Trang (default: 1) |
| `page_size` | int | Số item/trang (default: 50, max: 200) |
| `search` | string | Tìm theo code / name / email |
| `is_active` | bool | Lọc theo trạng thái |

```json
{
  "items": [
    {
      "id": "...",
      "code": "SUP001",
      "name": "Nguyễn Thị B",
      "is_active": true,
      "login_status": "đã đăng nhập",
      "email": "b@example.com",
      "user_id": "firebase_uid",
      "total_earned": 1500000,
      "total_managed_affiliates": 8,
      "bank_info": { "bank_name": "...", "account_number": "...", "account_name": "..." },
      "notes": "...",
      "created_at": "...",
      "updated_at": "..."
    }
  ],
  "total": 3,
  "page": 1,
  "page_size": 50,
  "total_pages": 1
}
```

---

#### `PUT /api/v1/admin/ai-bundle/supervisors/{code}`

```json
{
  "name": "Tên mới",
  "is_active": true,
  "email": "new@example.com",
  "bank_info": { "bank_name": "...", "account_number": "...", "account_name": "..." },
  "notes": "..."
}
```

---

### 9.4 Supervisor Withdrawals

#### `GET /api/v1/admin/ai-bundle/supervisor-withdrawals/list`

Query params: `?status=pending&page=1&page_size=50`

Response structure tương tự affiliate withdrawals list, với `supervisor_code` thay cho `affiliate_code`.

---

#### `POST /api/v1/admin/ai-bundle/supervisor-withdrawals/{id}/approve`

```json
{ "notes": "Đã chuyển khoản" }
```

---

#### `POST /api/v1/admin/ai-bundle/supervisor-withdrawals/{id}/reject`

```json
{ "reason": "Lý do từ chối" }
```

---

### 9.5 Partners Portal

#### `GET /api/v1/partners/me`

**Auth:** Firebase Bearer Token ✅
Endpoint tổng hợp — trả về tất cả roles trong cả 2 hệ thống (Conversations Learning + AI Bundle).

```json
{
  "user_id": "firebase_uid",
  "products": [
    {
      "product": "conversations",
      "role": "affiliate",
      "code": "CTV001",
      "name": "Nguyễn Văn A",
      "tier": 2,
      "is_active": true
    },
    {
      "product": "ai_bundle",
      "role": "affiliate",
      "code": "MADA123",
      "name": "Nguyễn Văn A",
      "tier": 2,
      "is_active": true
    },
    {
      "product": "ai_bundle",
      "role": "supervisor",
      "code": "SUP001",
      "name": "Nguyễn Văn A",
      "is_active": true
    }
  ]
}
```

> Dùng cho màn hình "Cộng tác viên" để biết user có roles gì và redirect đến dashboard tương ứng.

---

## 10. Error Codes

| HTTP | Tình huống |
|------|-----------|
| 400 | Request body không hợp lệ |
| 400 | `amount` không khớp giá server |
| 400 | Số dư không đủ để rút tiền |
| 400 | Còn request rút tiền pending chưa xử lý |
| 401 | Firebase token thiếu/hết hạn |
| 403 | Mã đại lý chưa được kích hoạt (`affiliate_not_active`) |
| 403 | Mã đại lý chưa đăng nhập hệ thống (`affiliate_not_registered`) |
| 404 | Mã đại lý không tồn tại |
| 404 | Đơn hàng không tồn tại |
| 409 | Trial đã sử dụng rồi |
| 409 | Đã có gói trả phí active |
| 429 | Quota requests đã hết (trial: "hết lượt dùng thử"; paid: "reset ngày X/X") |

---

## 11. Checklist tích hợp

### Trang `/ai-tools/ai-bundle?tab=subscription`

- [ ] `GET /api/v1/ai-bundle/me` khi load → kiểm tra `is_active`, `is_trial`, `trial_used`
  - `is_active: false` + `trial_used: false` → hiện nút **"Dùng thử miễn phí 15 ngày"**
  - `is_active: false` + `trial_used: true` → ẩn nút trial, hiện nút mua
  - `is_active: true` + `is_trial: true` → hiện thanh trial (`trial_days_remaining` ngày còn)
  - `is_active: true` + `is_trial: false` → hiện quota tháng
- [ ] `GET /api/v1/ai-bundle/plans` khi mở modal mua (không cần auth)
- [ ] Ô nhập mã giảm giá → `GET /api/v1/ai-bundle/validate-code?code=...` (**cần auth**)
- [ ] Nút "Dùng thử" → `POST /api/v1/ai-bundle/trial/activate` → reload `/me`
- [ ] Nút "Mua ngay" → `POST /api/payment/ai-bundle/checkout` (field: `plan`, không phải `package_id`)
  - Sau submit form SePay → poll `GET /api/payment/status/:order_invoice_number`
  - Khi `status === "completed"` → reload `GET /api/v1/ai-bundle/me`

### Affiliate Dashboard (`/partners/ai-bundle/affiliate`)

- [ ] `GET /api/v1/ai-bundle/affiliate/me` — tổng quan
- [ ] `GET /api/v1/ai-bundle/affiliate/students?page=1&page_size=50` (**`page_size`**)
- [ ] `GET /api/v1/ai-bundle/affiliate/transactions?page=1&page_size=20`
- [ ] `GET /api/v1/ai-bundle/affiliate/withdrawals?page=1&page_size=20`
- [ ] `POST /api/v1/ai-bundle/affiliate/withdraw`

### Admin Dashboard (`/admin/ai-bundle`)

- [ ] `POST /api/v1/admin/ai-bundle/affiliates`
- [ ] `GET /api/v1/admin/ai-bundle/affiliates?page=1&page_size=50&search=&tier=&is_active=`
- [ ] `GET /api/v1/admin/ai-bundle/affiliates/{code}`
- [ ] `PUT /api/v1/admin/ai-bundle/affiliates/{code}`
- [ ] `POST /api/v1/admin/ai-bundle/supervisors`
- [ ] `GET /api/v1/admin/ai-bundle/supervisors?page=1&page_size=50&search=&is_active=`
- [ ] `PUT /api/v1/admin/ai-bundle/supervisors/{code}`
- [ ] `GET /api/v1/admin/ai-bundle/withdrawals/list?status=pending&page=1&page_size=50`
- [ ] `POST /api/v1/admin/ai-bundle/withdrawals/{id}/approve`
- [ ] `POST /api/v1/admin/ai-bundle/withdrawals/{id}/reject`
- [ ] `GET /api/v1/admin/ai-bundle/supervisor-withdrawals/list?status=pending`
- [ ] `POST /api/v1/admin/ai-bundle/supervisor-withdrawals/{id}/approve`
- [ ] `POST /api/v1/admin/ai-bundle/supervisor-withdrawals/{id}/reject`

### Role detection

- [ ] `GET /api/v1/partners/me` — detect roles, redirect đến dashboard tương ứng

---

*Last updated: March 11, 2026*
