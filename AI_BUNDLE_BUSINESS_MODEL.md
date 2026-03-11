# Business Model Analysis — AI Bundle (AI Learning Assistant + AI Code Studio)

> **Tài liệu phân tích:** Gói đăng ký năm tích hợp 2 tính năng AI trả phí
> **Ngày:** March 2026
> **Trạng thái:** Draft — phê duyệt nội bộ

---

## 1. Tổng Quan Sản Phẩm

Hai tính năng AI được đóng gói thành **1 gói đăng ký duy nhất** theo năm:

| Tính năng | Mô tả | Endpoint AI |
|-----------|-------|-------------|
| **AI Learning Assistant** | Giải bài tập + chấm điểm bài làm học sinh | `/learning-assistant/solve` · `/learning-assistant/grade` |
| **AI Code Studio** | Tạo code · Giải thích code · Chuyển đổi code | `/software-lab/ai/generate` · `/software-lab/ai/explain` · `/software-lab/ai/transform` |

**Tổng cộng: 5 endpoint AI** đều được tính vào quota request hàng tháng.

> **Lưu ý:** Các endpoint nâng cao (Analyze Architecture, Scaffold Project) của Code Studio **không nằm trong gói này** — chỉ 3 endpoint cơ bản (Generate, Explain, Transform) được tính.

---

## 2. Gói Đăng Ký

### Tổng Quan Gói

| | **Gói Cơ Bản** | **Gói Nâng Cao** |
|---|---|---|
| **Giá niêm yết** | **449.000 VND / năm** | **899.000 VND / năm** |
| **Quy đổi / tháng** | ~37.417 VND / tháng | ~74.917 VND / tháng |
| **AI requests** | **100 requests / tháng** | **200 requests / tháng** |
| **AI Learning Assistant** | ✅ Đầy đủ (Giải bài + Chấm điểm) | ✅ Đầy đủ (Giải bài + Chấm điểm) |
| **AI Code Studio** | ✅ Đầy đủ (Generate + Explain + Transform) | ✅ Đầy đủ (Generate + Explain + Transform) |
| **Thời hạn** | 12 tháng | 12 tháng |
| **Đối tượng** | Học sinh, sinh viên, lập trình viên mới | Lập trình viên chuyên nghiệp, giáo viên, trung tâm |

### Chi Tiết Quota Requests

Mỗi lần gọi **bất kỳ 1 trong 5 endpoint AI** = **1 request**.

| Hành động | Endpoint | Request tính? |
|-----------|----------|---------------|
| Giải bài tập / homework | `POST /learning-assistant/solve` | ✅ 1 request |
| Chấm điểm bài làm | `POST /learning-assistant/grade` | ✅ 1 request |
| Tạo code từ mô tả | `POST /software-lab/ai/generate` | ✅ 1 request |
| Giải thích đoạn code | `POST /software-lab/ai/explain` | ✅ 1 request |
| Chuyển đổi code (ngôn ngữ/framework) | `POST /software-lab/ai/transform` | ✅ 1 request |
| Xem lịch sử (history) | `GET /learning-assistant/history` | ❌ Không tính |
| Lấy trạng thái job (polling) | `GET /.../status` | ❌ Không tính |

**Gói Cơ Bản:** Reset 100 requests vào ngày 1 mỗi tháng
**Gói Nâng Cao:** Reset 200 requests vào ngày 1 mỗi tháng
Requests không dùng hết **không cộng dồn** sang tháng sau.

---

## 3. Cấu Trúc Giá theo Đại Lý

Tương tự mô hình gói Conversations (Listen & Learn), giá được điều chỉnh theo **tier đại lý**:

### Bảng Giá theo Tier

| Tier | Gói Cơ Bản | Gói Nâng Cao | Mô tả |
|------|-----------|-------------|-------|
| **Không có mã** (no_code) | 449.000 VND | 899.000 VND | Mua trực tiếp qua website |
| **Tier 2** (đại lý thông thường) | 399.000 VND | 799.000 VND | Giảm ~10% — đại lý cá nhân |
| **Tier 1** (đại lý cao cấp) | 359.000 VND | 719.000 VND | Giảm ~20% — trung tâm, tổ chức |

> Giá niêm yết luôn hiển thị để frontend có thể show **giá gạch chân** (strikethrough) khi dùng mã đại lý.

---

## 4. Hoa Hồng Đại Lý

### Tỷ Lệ Hoa Hồng

| Cấp độ | Tỷ lệ hoa hồng | Điều kiện |
|--------|----------------|-----------|
| **Đại lý Tier 1** | **40% trên giá bán** | Trung tâm, tổ chức giáo dục có thỏa thuận riêng |
| **Đại lý Tier 2** | **25% trên giá bán** | Đại lý cá nhân, CTV |
| **Supervisor** | **10% trên doanh thu của đại lý được quản lý** | Người quản lý hệ thống đại lý |

### Ví Dụ Tính Hoa Hồng — Gói Cơ Bản (449k)

**Kịch bản 1: Bán qua đại lý Tier 2 (mã giảm giá ~10%)**
```
Giá bán thực tế:      399.000 VND
Hoa hồng đại lý:  25% × 399.000 = 99.750 VND
Supervisor:       10% × 399.000 = 39.900 VND  (nếu đại lý có supervisor)
Còn lại cho WordAI:   399.000 - 99.750 - 39.900 = 259.350 VND
```

**Kịch bản 2: Bán qua đại lý Tier 1 (mã giảm giá ~20%)**
```
Giá bán thực tế:      359.000 VND
Hoa hồng đại lý:  40% × 359.000 = 143.600 VND
Supervisor:       10% × 359.000 =  35.900 VND  (nếu đại lý có supervisor)
Còn lại cho WordAI:   359.000 - 143.600 - 35.900 = 179.500 VND
```

**Kịch bản 3: Bán trực tiếp (không có mã)**
```
Giá bán thực tế:  449.000 VND
Hoa hồng:         0 VND
Còn lại cho WordAI: 449.000 VND
```

### Ví Dụ Tính Hoa Hồng — Gói Nâng Cao (899k)

**Kịch bản 1: Bán qua đại lý Tier 2**
```
Giá bán thực tế:      799.000 VND
Hoa hồng đại lý:  25% × 799.000 = 199.750 VND
Supervisor:       10% × 799.000 =  79.900 VND
Còn lại cho WordAI:   799.000 - 199.750 - 79.900 = 519.350 VND
```

**Kịch bản 2: Bán qua đại lý Tier 1**
```
Giá bán thực tế:      719.000 VND
Hoa hồng đại lý:  40% × 719.000 = 287.600 VND
Supervisor:       10% × 719.000 =  71.900 VND
Còn lại cho WordAI:   719.000 - 287.600 - 71.900 = 359.500 VND
```

---

## 5. Unit Economics — Phân Tích Chi Phí AI

### Chi Phí AI Thực Tế Mỗi Tháng

**Mô hình AI đang sử dụng:**
- AI Learning Assistant: Gemini 3.1 Flash Lite Preview
- AI Code Studio (Generate/Explain/Transform): GLM-5 MaaS

**Ước tính chi phí trung bình mỗi request:**
- Gemini Flash Lite: ~0.5–1 token/request rất rẻ (~$0.00003–$0.0001/request)
- GLM-5 MaaS: Tương đương (~$0.00003–$0.0001/request)
- Ước tính trung bình: **~$0.0001 / request** = **~2.5 VND / request** (tỷ giá 25.000 VND/$)

**Chi phí AI ở mức sử dụng tối đa:**

| Gói | Max requests/tháng | Chi phí AI/tháng (ước tính) | Chi phí AI/năm |
|-----|-------------------|----------------------------|----------------|
| Cơ Bản | 100 | ~250 VND | ~3.000 VND |
| Nâng Cao | 200 | ~500 VND | ~6.000 VND |

> Chi phí AI thực tế rất nhỏ so với giá gói — margin hệ thống cao. Phần lớn chi phí là infrastructure, R2 storage, bandwidth.

### Biên Lợi Nhuận (Margin Analysis)

**Gói Cơ Bản — Bán trực tiếp (449k):**
| Khoản mục | VND |
|-----------|-----|
| Doanh thu | 449.000 |
| Chi phí AI (max) | ~3.000 |
| Chi phí hạ tầng/người dùng | ~15.000 |
| **Biên lợi nhuận ước tính** | **~431.000 (~96%)** |

**Gói Cơ Bản — Bán qua Tier 1 (359k):**
| Khoản mục | VND |
|-----------|-----|
| Thu về (sau hoa hồng, có supervisor) | 179.500 |
| Chi phí AI (max) | ~3.000 |
| Chi phí hạ tầng | ~15.000 |
| **Biên lợi nhuận ước tính** | **~161.500 (~45%)** |

---

## 6. Database Schema Đề Xuất

### Collection: `user_ai_bundle_subscriptions`

```json
{
  "_id": ObjectId,
  "user_id": "firebase_uid",
  "plan": "basic",             // "basic" | "advanced"
  "status": "active",          // "active" | "expired" | "cancelled"
  "price_tier": "no_code",     // "no_code" | "tier_1" | "tier_2"
  "amount_paid": 449000,
  "currency": "VND",
  "payment_id": "PAY_xxx",
  "order_invoice_number": "AI_BUNDLE_xxx",
  "affiliate_code": null,
  "affiliate_user_id": null,
  "supervisor_user_id": null,
  "requests_monthly_limit": 100,
  "requests_used_this_month": 0,
  "requests_reset_date": ISODate("2026-04-01"),
  "started_at": ISODate,
  "expires_at": ISODate,        // started_at + 12 tháng
  "created_at": ISODate,
  "updated_at": ISODate
}
```

### Collection: `ai_bundle_requests_log`

```json
{
  "_id": ObjectId,
  "user_id": "firebase_uid",
  "subscription_id": ObjectId,
  "endpoint": "solve",          // "solve" | "grade" | "generate" | "explain" | "transform"
  "feature": "learning_assistant",  // "learning_assistant" | "code_studio"
  "job_id": "uuid",
  "created_at": ISODate
}
```

---

## 7. Payment Flow — Luồng Thanh Toán

```
User chọn gói  →  POST /api/payment/ai-bundle/checkout
                       ↓
             Payment Service tạo đơn SePay
                       ↓
             User chuyển khoản
                       ↓
             SePay webhook → payment-service/IPN
                       ↓
             LPUSH queue:payment_events {event_type: "ai_bundle_paid", ...}
                       ↓
             learning-events-worker xử lý
                       ↓
             Tạo/gia hạn user_ai_bundle_subscriptions
                       ↓
             Ghi nhận hoa hồng đại lý (nếu có)
```

---

## 8. API Endpoints Cần Triển Khai

### Subscription Management (Python/FastAPI)

| Method | Path | Mô tả | Auth |
|--------|------|-------|------|
| `GET` | `/api/v1/ai-bundle/plans` | Danh sách gói + giá (có thể truyền `?code=` affiliate) | Public |
| `GET` | `/api/v1/ai-bundle/me` | Trạng thái subscription + quota còn lại | Required |
| `POST` | `/api/v1/ai-bundle/activate` | Kích hoạt sau thanh toán (nội bộ, X-Service-Secret) | Service |

### Checkout (Node.js Payment Service)

| Method | Path | Mô tả |
|--------|------|-------|
| `POST` | `/api/payment/ai-bundle/checkout` | Tạo đơn thanh toán SePay |

### Request Body: Checkout

```json
{
  "plan": "basic",               // "basic" | "advanced"
  "price_tier": "no_code",       // "no_code" | "tier_1" | "tier_2"
  "affiliate_code": "WORD001",   // Optional — mã đại lý
  "amount": 399000               // Giá đã tính (validate server-side)
}
```

### Response: Plan List (`GET /api/v1/ai-bundle/plans`)

```json
{
  "plans": [
    {
      "plan_id": "basic",
      "plan_label": "Gói Cơ Bản",
      "requests_per_month": 100,
      "months": 12,
      "price_tier": "tier_2",
      "original_price": 449000,  // no-code price for strikethrough UI
      "price": 399000,           // actual price with affiliate code
      "is_popular": false
    },
    {
      "plan_id": "advanced",
      "plan_label": "Gói Nâng Cao",
      "requests_per_month": 200,
      "months": 12,
      "price_tier": "tier_2",
      "original_price": 899000,
      "price": 799000,
      "is_popular": true
    }
  ],
  "affiliate_info": {
    "code": "WORD001",
    "tier": 2
  }
}
```

### Response: Subscription Status (`GET /api/v1/ai-bundle/me`)

```json
{
  "is_active": true,
  "plan": "basic",
  "plan_label": "Gói Cơ Bản",
  "requests_monthly_limit": 100,
  "requests_used_this_month": 23,
  "requests_remaining": 77,
  "requests_reset_date": "2026-04-01T00:00:00Z",
  "expires_at": "2027-03-11T00:00:00Z",
  "features": {
    "learning_assistant": true,
    "code_studio_basic": true
  }
}
```

---

## 9. Access Control — Kiểm Tra Quyền Truy Cập AI

Khi user gọi bất kỳ 5 endpoint AI, backend phải:

1. **Kiểm tra subscription active** — `user_ai_bundle_subscriptions.status == "active"` và chưa hết hạn
2. **Kiểm tra quota** — `requests_used_this_month < requests_monthly_limit`
3. **Tăng counter** — `requests_used_this_month += 1` (atomic inc)
4. **Cho phép** hoặc **trả về 403**

```python
# Ví dụ middleware kiểm tra
async def check_ai_bundle_quota(user_id: str, db) -> bool:
    sub = db["user_ai_bundle_subscriptions"].find_one_and_update(
        {
            "user_id": user_id,
            "status": "active",
            "expires_at": {"$gt": datetime.utcnow()},
            "$expr": {"$lt": ["$requests_used_this_month", "$requests_monthly_limit"]}
        },
        {"$inc": {"requests_used_this_month": 1}},
        return_document=True
    )
    return sub is not None
```

> **Lưu ý:** Hiện tại các endpoint sử dụng `points_service` (deduct points). Cần thêm logic kiểm tra AI Bundle subscription **trước** khi trừ điểm — nếu user có gói bundle active thì KHÔNG trừ điểm.

---

## 10. So Sánh với Pay-per-Point

| | **Gói Cơ Bản** | **Gói Nâng Cao** | **Pay-per-point** |
|---|---|---|---|
| **Giá** | 449.000/năm | 899.000/năm | Theo usage |
| **Requests/tháng** | 100 | 200 | Không giới hạn (tùy điểm) |
| **Giá quy đổi/request** | ~374 VND/req | ~374 VND/req | ~1 điểm/req (giá điểm tuỳ gói) |
| **Phù hợp với** | Dùng đều đặn < 100 req/tháng | Dùng nhiều <= 200 req/tháng | Dùng không thường xuyên |

---

## 11. Tóm Tắt Các Mốc Quan Trọng

| Hạng mục | Giá trị |
|----------|---------|
| Giá Gói Cơ Bản | **449.000 VND / năm** |
| Giá Gói Nâng Cao | **899.000 VND / năm** |
| Quota Cơ Bản | 100 requests AI / tháng |
| Quota Nâng Cao | 200 requests AI / tháng |
| Giá Tier 2 (~10% off) — Cơ Bản | 399.000 VND |
| Giá Tier 1 (~20% off) — Cơ Bản | 359.000 VND |
| Giá Tier 2 (~10% off) — Nâng Cao | 799.000 VND |
| Giá Tier 1 (~20% off) — Nâng Cao | 719.000 VND |
| Hoa hồng Tier 2 | 25% trên giá bán |
| Hoa hồng Tier 1 | 40% trên giá bán |
| Hoa hồng Supervisor | 10% trên doanh thu đại lý |
| Đơn vị tính request | 1 endpoint call = 1 request |
| Reset quota | Ngày 1 hàng tháng |
| Không cộng dồn | Requests chưa dùng mất khi reset |
