# Frontend Payment Integration Guide - WordAI SePay

## 📋 Tổng Quan

Tài liệu này hướng dẫn Frontend team tích hợp luồng thanh toán SePay vào WordAI. Luồng thanh toán sử dụng phương thức **HTML form submission** (không phải REST API).

> **⚠️ QUAN TRỌNG:** Phase đầu tiên cần **tích hợp và test luồng thanh toán** trước khi implement UI hoàn chỉnh. Đảm bảo luồng thanh toán hoạt động đúng trước khi làm UI.
>
> **📌 LƯU Ý:** Test trực tiếp trên **production** vì sản phẩm chưa ra mắt. Sau khi test xong và luồng hoạt động ổn định, sẽ bắt đầu thực hiện nâng cấp thật cho các user thật.

---

## 🎯 Implementation Phases

### ✅ Phase 1: Production Integration & Testing (PRIORITY - BẮT ĐẦU ĐÂY)

**Mục tiêu:** Tích hợp và test đầy đủ luồng thanh toán SePay trên production trước khi build UI.

**Timeline:** 2-3 ngày

**Tasks:**

1. **Setup Test Environment** (0.5 ngày)
   - [ ] Clone project và setup local
   - [ ] Cấu hình API base URL: `https://ai.wordai.pro`
   - [ ] Tạo test user accounts thật trên production
   - [ ] Document test credentials

2. **Integrate Checkout API** (1 ngày)
   - [ ] Implement `POST /api/v1/payments/checkout` call
   - [ ] Implement form submission với form_fields
   - [ ] Test redirect đến SePay production
   - [ ] Verify signature generation từ backend

3. **Test Payment Flow End-to-End** (1 ngày)
   - [ ] Test thanh toán thành công (success flow)
   - [ ] Test thanh toán thất bại (error flow)
   - [ ] Test user cancel payment (cancel flow)
   - [ ] Verify IPN callback hoạt động
   - [ ] Verify subscription activation

4. **Integrate Status Check APIs** (0.5 ngày)
   - [ ] Implement `GET /api/v1/payments/status/:order_invoice_number`
   - [ ] Implement `GET /api/v1/payments/user/:user_id`
   - [ ] Test status polling sau khi redirect về

**Deliverables Phase 1:**
- ✅ Working production integration code
- ✅ Test script/page để test luồng thanh toán
- ✅ Documentation của test cases và results
- ✅ List các edge cases cần handle

**Production Test Configuration:**
```javascript
// Production Test Configuration
const PRODUCTION_CONFIG = {
  baseURL: 'https://ai.wordai.pro',
  sepayCheckoutURL: 'https://pay.sepay.vn/v1/checkout/init', // Production SePay
  testUsers: [
    {
      user_id: 'test_user_001',
      email: 'test1@wordai.pro',
      name: 'Test User 1'
    }
  ],
  testPlans: [
    { plan: 'premium', duration: '3_months', price: 279000 },
    { plan: 'pro', duration: '3_months', price: 447000 },
    { plan: 'vip', duration: '12_months', price: 2799000 }
  ]
};
```

**Test Cases để Verify:**
1. ✅ Checkout API trả về đúng form_fields với signature
2. ✅ Form submit redirect đến SePay production
3. ✅ Thanh toán thành công → redirect về success_url
4. ✅ IPN được gọi và subscription được activate
5. ✅ Status API trả về đúng trạng thái payment
6. ✅ Payment history API trả về đúng lịch sử

---

### 📝 Phase 2: UI/UX Implementation (SAU KHI PHASE 1 XONG)

**Mục tiêu:** Build UI hoàn chỉnh cho pricing page và payment flows.

**Timeline:** 3-4 ngày

**Tasks:**
- [ ] Design và implement pricing page
- [ ] Design payment success/error/cancel pages
- [ ] Implement payment history page
- [ ] Add loading states và animations
- [ ] Responsive design
- [ ] Error handling UI

---

### 🧪 Phase 3: Testing & Refinement

**Mục tiêu:** Test toàn bộ flow với nhiều scenarios trên production.

**Timeline:** 2 ngày

**Tasks:**
- [ ] Cross-browser testing
- [ ] Mobile responsive testing
- [ ] Edge cases testing
- [ ] Performance testing
- [ ] Security review

---

### 🚀 Phase 4: Launch & User Onboarding

**Mục tiêu:** Ra mắt tính năng upgrade plans cho user thật.

**Timeline:** 1 ngày

**Tasks:**
- [ ] Announce tính năng mới
- [ ] Monitor real user payments
- [ ] Customer support preparation
- [ ] Documentation cho users

---

## 🔄 Luồng Thanh Toán (Payment Flow)

```
┌─────────────┐
│   User      │
│ Chọn gói    │
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────────────┐
│ 1. Frontend: POST /api/v1/payments/checkout │
│    Body: { user_id, plan, duration }    │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│ 2. Backend trả về:                      │
│    - checkout_url                        │
│    - form_fields (với signature)        │
│    - payment_id                          │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│ 3. Frontend tạo form HTML và submit    │
│    → Redirect user đến SePay            │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│ 4. User thanh toán trên SePay           │
└──────────────┬──────────────────────────┘
               │
               ├──────────────────────────┐
               │                          │
               ▼                          ▼
┌──────────────────────┐    ┌─────────────────────┐
│ 5a. SePay gọi IPN    │    │ 5b. User redirect   │
│     POST /sepay/ipn  │    │     về success_url  │
│     → Backend xử lý  │    └─────────┬───────────┘
│     → Kích hoạt sub  │              │
└──────────────────────┘              ▼
                         ┌──────────────────────────┐
                         │ 6. Frontend hiển thị     │
                         │    kết quả thanh toán    │
                         └──────────────────────────┘
```
## 2. User Plans Structure

### 2.1 Pricing Table

| Feature | Free | Premium | Pro | VIP |
|---------|------|---------|-----|-----|
| **Price** | **0đ** (miễn phí vĩnh viễn) | 279k/3mo - 990k/12mo | 447k/3mo - 1,699k/12mo | 747k/3mo - 2,799k/12mo |
| **Storage** | **50MB** | 2GB | 15GB | 50GB |
| **AI Chat** | **Deepseek (15 chats/ngày)** | 300pts/3mo - 1200pts/12mo | 500pts/3mo - 2000pts/12mo | 1000pts/3mo - 4000pts/12mo |
| **Upload Files** | **10 files** | 100 files | Unlimited | Unlimited |
| **Library Files** | **Unlimited** (không giới hạn) | 100 files | Unlimited | Unlimited |
| **Documents** | **10 files** | 100 files | 1000 files | Unlimited |
| **Secret Files** | **1 doc** (không share được) | 100 docs+images | 1000 docs+images | Unlimited |
| **AI Edit/Translate** | **❌** (không có) | ✅ 150 uses (300pts) | ✅ 250 uses (500pts) | ✅ 500 uses (1000pts) |
| **Online Tests** | **Tham gia only** (không tạo được) | ✅ 150 tests (300pts) | ✅ 250 tests (500pts) | ✅ 500 tests (1000pts) |
| **AI Model** | **Deepseek R1** (free model) | Sonnet 3.5 + Deepseek | Sonnet 3.5 + Deepseek | Sonnet 3.5 + Deepseek |
| **Priority Support** | ❌ | ❌ | ✅ | ✅✅ (cao nhất) |
| **Feature Access** | Cơ bản | Đầy đủ | Đầy đủ + Ưu tiên | Tất cả + VIP |

### 2.2 Chi Tiết Bản Free (Miễn Phí)

**🎯 Mục đích:** Cho phép người dùng trải nghiệm đầy đủ các tính năng cơ bản của WordAI để hiểu giá trị của sản phẩm trước khi nâng cấp.

**✅ Có gì trong bản Free:**

1. **💬 AI Chat với Deepseek R1:**
   - Model AI miễn phí: Deepseek R1 (mạnh nhất trong các free model)
   - Giới hạn: 15 cuộc trò chuyện/ngày (reset lúc 00:00 UTC+7)
   - Có thể chat về bất kỳ chủ đề nào
   - Truy cập document chat (chat với file đã upload)

2. **📁 File Management:**
   - Upload Files: 10 files (để xử lý và chat)
   - Library Files: **Không giới hạn** (lưu trữ file thư viện)
   - Documents: 10 files (tạo document từ AI)
   - Secret Files: 1 document (encrypted, không share được)
   - Storage: 50MB tổng dung lượng

3. **📝 Document Features:**
   - Xem và đọc documents
   - Download documents
   - Basic document management
   - **KHÔNG** chỉnh sửa bằng AI
   - **KHÔNG** dịch tự động

4. **🎓 Online Testing:**
   - Tham gia làm bài test (không giới hạn)
   - Xem kết quả và điểm số
   - **KHÔNG** tạo được test
   - **KHÔNG** tạo câu hỏi tự động

**❌ Không có trong bản Free:**
- AI Edit/Translate (cần Premium trở lên)
- Tạo Online Test (cần Premium trở lên)
- Claude Sonnet 3.5 (model cao cấp)
- Priority support
- Chia sẻ Secret Documents
- Storage > 50MB

### 2.3 So Sánh 4 Tiers: Phù Hợp Với Ai?

#### 🆓 **FREE - Người Dùng Cá Nhân/Học Sinh:**
**Phù hợp cho:**
- Sinh viên, học sinh muốn thử nghiệm AI
- Người dùng cá nhân với nhu cầu cơ bản
- Ai muốn chat với AI về các vấn đề hàng ngày

**Giới hạn chính:**
- 15 chats/ngày với Deepseek R1 (đủ cho người dùng thường xuyên)
- 50MB storage (khoảng 10-20 files văn bản)
- Không tạo được test hoặc edit bằng AI

**Use case điển hình:**
- "Tôi cần AI giúp trả lời thắc mắc về học tập"
- "Tôi muốn chat với document của mình"
- "Tôi cần lưu trữ vài file và tham gia test online"

---

#### 💎 **PREMIUM - Sinh Viên/Giáo Viên:**
**Phù hợp cho:**
- Sinh viên cần AI để học tập và làm bài
- Giáo viên tạo test cho lớp nhỏ (10-30 học sinh)
- Người làm việc với documents thường xuyên

**Nâng cấp từ Free:**
- ✅ Claude Sonnet 3.5 (AI model mạnh nhất hiện tại)
- ✅ 300-1200 points cho AI operations (150-600 uses)
- ✅ 2GB storage (40x so với Free)
- ✅ Tạo được 150 online tests
- ✅ AI Edit/Translate 150 lần

**Giá trị:**
- 279k/3 tháng = **93k/tháng** = 3k/ngày
- 990k/12 tháng = **82.5k/tháng** = 2.75k/ngày (rẻ hơn 11%)

**Use case điển hình:**
- "Tôi cần AI chỉnh sửa và dịch documents chuyên nghiệp"
- "Tôi muốn tạo test online cho lớp học của mình"
- "Tôi cần lưu trữ nhiều file hơn và dùng AI model tốt nhất"

---

#### 🚀 **PRO - Chuyên Gia/Doanh Nghiệp Nhỏ:**
**Phù hợp cho:**
- Nhà tạo nội dung (content creators)
- Doanh nghiệp nhỏ (5-20 nhân viên)
- Giáo viên/trường học với nhiều lớp

**Nâng cấp từ Premium:**
- ✅ 500-2000 points (250-1000 uses) - 67% nhiều hơn Premium
- ✅ 15GB storage (7.5x so với Premium)
- ✅ Upload unlimited files
- ✅ Tạo 1000 documents
- ✅ 250 AI operations (edit/translate/test)
- ✅ Priority Support

**Giá trị:**
- 447k/3 tháng = **149k/tháng** = 5k/ngày
- 1,699k/12 tháng = **141.5k/tháng** = 4.7k/ngày (rẻ hơn 5%)

**Use case điển hình:**
- "Tôi tạo content hàng ngày và cần AI mạnh mẽ"
- "Team của tôi cần share và xử lý nhiều documents"
- "Tôi tạo test cho nhiều lớp học (100+ tests/tháng)"

---

#### 👑 **VIP - Enterprise/Tổ Chức Lớn:**
**Phù hợp cho:**
- Công ty/tổ chức lớn (20+ nhân viên)
- Trường đại học/trung tâm đào tạo
- Agency marketing/content

**Nâng cấp từ Pro:**
- ✅ 1000-4000 points (500-2000 uses) - 100% nhiều hơn Pro
- ✅ 50GB storage (3.3x so với Pro)
- ✅ **UNLIMITED** documents
- ✅ **UNLIMITED** secret files + sharing
- ✅ **500 AI operations** (2x so với Pro)
- ✅✅ **Highest Priority Support** (24/7)
- ✅ Feature access sớm nhất

**Giá trị:**
- 747k/3 tháng = **249k/tháng** = 8.3k/ngày
- 2,799k/12 tháng = **233k/tháng** = 7.8k/ngày (rẻ hơn 6%)

**Use case điển hình:**
- "Team của tôi có 50+ người cần dùng AI"
- "Chúng tôi xử lý hàng trăm documents mỗi ngày"
- "Chúng tôi cần support nhanh nhất và unlimited storage"

---

### 2.4 Points System Logic

**AI Points Usage:**
- 1 AI Chat = 2 points
- 1 AI Edit/Translate = 2 points
- 1 Online Test Creation = 2 points

**Examples:**
- Premium 300 points = 150 AI operations
- Pro 500 points = 250 AI operations
- VIP 1000 points = 500 AI operations
---

## 🎯 API Endpoints

### Base URL
- **Production:** `https://ai.wordai.pro`
- **Development:** `http://localhost:8000`

---

## 📝 API 1: Tạo Checkout

### Endpoint
```
POST /api/v1/payments/checkout
```

### Request Headers
```http
Content-Type: application/json
```

### Request Body
```json
{
  "user_id": "string",       // Required: ID của user
  "plan": "premium|pro|vip", // Required: Gói đăng ký
  "duration": "3_months|12_months", // Required: Thời hạn
  "user_email": "string",    // Optional: Email user
  "user_name": "string"      // Optional: Tên user
}
```

### Response (201 Created)
```json
{
  "success": true,
  "data": {
    "payment_id": "673a1234567890abcdef1234",
    "order_invoice_number": "WA-1730886543210-user123",
    "checkout_url": "https://pay-sandbox.sepay.vn/v1/checkout/init",
    "form_fields": {
      "merchant": "MERCHANT_ID",
      "operation": "PURCHASE",
      "payment_method": "BANK_TRANSFER",
      "order_amount": "279000",
      "currency": "VND",
      "order_invoice_number": "WA-1730886543210-user123",
      "order_description": "WordAI PREMIUM - 3 tháng",
      "customer_id": "user_12345678",
      "success_url": "https://ai.wordai.pro/payment/success",
      "error_url": "https://ai.wordai.pro/payment/error",
      "cancel_url": "https://ai.wordai.pro/payment/cancel",
      "signature": "base64_encoded_signature=="
    },
    "amount": 279000,
    "plan": "premium",
    "duration": "3_months",
    "duration_months": 3
  }
}
```

### Response (400 Bad Request)
```json
{
  "success": false,
  "error": "Invalid plan or duration"
}
```

### Pricing Table
| Plan    | 3 Months | 12 Months |
|---------|----------|-----------|
| Premium | 279,000 đ | 990,000 đ |
| Pro     | 447,000 đ | 1,699,000 đ |
| VIP     | 747,000 đ | 2,799,000 đ |

---

## 🚀 Frontend Implementation - Checkout Flow

### Step 1: User chọn gói


### Step 2: Submit form to SePay

---

## 📄 Callback Pages - Success/Error/Cancel

### ✅ Domain Đã Được Fix

**Frontend domain:** `https://wordai.pro/`  
**Backend API:** `https://ai.wordai.pro/api/...`

Payment service đã được cập nhật để redirect về đúng frontend domain.

### URL Patterns

Sau khi user thanh toán hoặc hủy, SePay sẽ redirect về các URL frontend:

```
✅ Success: https://wordai.pro/payment/success?order=WA-xxx
❌ Error:   https://wordai.pro/payment/error?order=WA-xxx&message=xxx
🚫 Cancel:  https://wordai.pro/payment/cancel?order=WA-xxx
⏳ Pending: https://wordai.pro/payment/pending?order=WA-xxx
```

### Các trang cần tạo trong Next.js:

#### 1. Success Page (`/payment/success`)
- **File:** `pages/payment/success.tsx` hoặc `app/payment/success/page.tsx`
- **Query params:** `?order=WA-xxx`
- **Tasks:**
  1. Lấy `order` từ query params
  2. Gọi API `GET https://ai.wordai.pro/api/v1/payments/status/:order` để check trạng thái
  3. Hiển thị success message với thông tin plan, amount
  4. Auto redirect về dashboard sau 3-5 giây

#### 2. Error Page (`/payment/error`)
- **File:** `pages/payment/error.tsx` hoặc `app/payment/error/page.tsx`
- **Query params:** `?order=WA-xxx&message=xxx`
- **Tasks:**
  1. Lấy `order` và `message` từ query params
  2. Hiển thị error message
  3. Button "Thử lại" → redirect về pricing page
  4. Button "Liên hệ support" (optional)

#### 3. Cancel Page (`/payment/cancel`)
- **File:** `pages/payment/cancel.tsx` hoặc `app/payment/cancel/page.tsx`
- **Query params:** `?order=WA-xxx`
- **Tasks:**
  1. Lấy `order` từ query params
  2. Hiển thị "Bạn đã hủy thanh toán"
  3. Auto redirect về pricing page sau 3 giây
  4. Button "Quay lại chọn gói"

#### 4. Pending Page (Optional - `/payment/pending`)
- **File:** `pages/payment/pending.tsx` hoặc `app/payment/pending/page.tsx`
- **Query params:** `?order=WA-xxx`
- **Tasks:**
  1. Hiển thị loading/processing message
  2. Poll status API every 3 seconds
  3. Redirect khi status thay đổi (completed → success, failed → error)
---

## 📊 API 2: Kiểm tra trạng thái thanh toán

### Endpoint
```
GET /api/v1/payments/status/:order_invoice_number
```

### Example Request
```javascript
const response = await fetch(
  'https://ai.wordai.pro/api/v1/payments/status/WA-1730886543210-user123'
);
const result = await response.json();
```

### Response (200 OK)
```json
{
  "success": true,
  "data": {
    "payment_id": "673a1234567890abcdef1234",
    "order_invoice_number": "WA-1730886543210-user123",
    "status": "completed",
    "plan": "premium",
    "duration": "3_months",
    "price": 279000,
    "created_at": "2024-11-05T12:30:00.000Z",
    "completed_at": "2024-11-05T12:35:00.000Z"
  }
}
```

### Response (404 Not Found)
```json
{
  "success": false,
  "error": "Payment not found"
}
```

### Status Values
- `pending`: Đang chờ thanh toán
- `completed`: Thanh toán thành công
- `failed`: Thanh toán thất bại
- `cancelled`: Đã hủy

---

## 📋 API 3: Lấy lịch sử thanh toán

### Endpoint
```
GET /api/v1/payments/user/:user_id
```

### Example Request
```javascript
const userId = getCurrentUserId();
const response = await fetch(
  `https://ai.wordai.pro/api/v1/payments/user/${userId}`
);
const result = await response.json();
```

### Response (200 OK)
```json
{
  "success": true,
  "data": [
    {
      "payment_id": "673a1234567890abcdef1234",
      "order_invoice_number": "WA-1730886543210-user123",
      "status": "completed",
      "plan": "premium",
      "duration": "3_months",
      "price": 279000,
      "created_at": "2024-11-05T12:30:00.000Z",
      "completed_at": "2024-11-05T12:35:00.000Z"
    },
    {
      "payment_id": "673a9876543210fedcba9876",
      "order_invoice_number": "WA-1729886543210-user123",
      "status": "pending",
      "plan": "pro",
      "duration": "12_months",
      "price": 1699000,
      "created_at": "2024-10-25T10:20:00.000Z",
      "completed_at": null
    }
  ]
}
```

---

## 🧪 PHASE 1: PRODUCTION TESTING GUIDE (BẮT ĐẦU Ở ĐÂY)

> **📌 Ưu tiên cao nhất:** Integrate và test các endpoints này trước khi làm UI. Test trực tiếp trên **production** vì sản phẩm chưa ra mắt.
>
> **💡 Chiến lược:** Sau khi test xong và confirm luồng hoạt động ổn định, sẽ bắt đầu thực hiện nâng cấp thật cho các user thật.

### Step 1: Setup Test Environment

**1.1. Tạo test HTML file đơn giản:**


**1.2. Save file trên và mở trong browser:**
```bash
# Save as: test-sepay-sandbox.html
# Open in browser: file:///path/to/test-sepay-sandbox.html
```

---

### Step 2: Test Checkout Flow

**2.1. Test Checkout API chỉ (không submit):**
1. Chọn plan: Premium
2. Chọn duration: 3 tháng
3. Click "Test Checkout API"
4. **Verify response có:**
   - ✅ `success: true`
   - ✅ `payment_id` (MongoDB ObjectId)
   - ✅ `order_invoice_number` (format: WA-timestamp-userId)
   - ✅ `checkout_url` (https://pay-sandbox.sepay.vn/v1/checkout/init)
   - ✅ `form_fields` object với signature

**2.2. Test Full Payment Flow:**
1. Click "Test Checkout + Submit Form"
2. **Verify redirect đến SePay sandbox**
3. Trên SePay sandbox page:
   - Thấy thông tin order (amount, description)
   - Có các payment methods (BANK_TRANSFER, VISA, etc.)
4. **Test Success Flow:**
   - Chọn payment method
   - Click "Thanh toán"
   - SePay sẽ redirect về `success_url`
   - **Verify:** URL có `order_invoice_number` parameter
5. **Test Cancel Flow:**
   - Click "Hủy" trên SePay
   - **Verify:** Redirect về `cancel_url`

---

### Step 3: Verify IPN Callback

**3.1. Check Backend Logs:**
```bash
# SSH vào server
ssh root@104.248.147.155

# Check payment service logs
docker logs payment-service --tail 50 -f
```

**3.2. Verify IPN được gọi:**
Sau khi thanh toán thành công, trong logs phải thấy:
```
[IPN] Received webhook: ORDER_PAID
[IPN] Order: WA-1730886543210-user123
[IPN] Status: completed
[IPN] Subscription activated successfully
```

**3.3. Nếu không thấy IPN:**
- Check NGINX routing: `/sepay/ipn` → payment-service
- Check SePay dashboard có gửi IPN không
- Check firewall có block không

---

### Step 4: Test Payment Status API

**4.1. Test ngay sau khi checkout:**
1. Copy `order_invoice_number` từ checkout response
2. Paste vào "Order Invoice Number" field
3. Click "Check Payment Status"
4. **Verify response:**
   - Status: `pending` (nếu chưa thanh toán)
   - Status: `completed` (nếu đã thanh toán)
   - Có đầy đủ thông tin: plan, duration, price, created_at

**4.2. Test polling (auto-refresh):**
```javascript
// Test trong console
let count = 0;
const interval = setInterval(async () => {
    count++;
    console.log(`[${count}] Checking status...`);

    const response = await fetch(
        'https://ai.wordai.pro/api/v1/payments/status/WA-xxx'
    );
    const result = await response.json();
    console.log('Status:', result.data?.status);

    if (result.data?.status === 'completed') {
        console.log('✅ Payment completed!');
        clearInterval(interval);
    }

    if (count >= 20) {
        console.log('⏰ Timeout after 20 attempts');
        clearInterval(interval);
    }
}, 3000); // Check every 3 seconds
```

---

### Step 5: Test Payment History API

**5.1. Test với user có payments:**
1. Nhập `user_id` (ví dụ: `test_user_001`)
2. Click "Get Payment History"
3. **Verify response:**
   - Trả về array các payments
   - Mỗi payment có: payment_id, status, plan, duration, price
   - Sorted by created_at (mới nhất trước)

**5.2. Test với user không có payments:**
1. Nhập `user_id` random (ví dụ: `user_no_payments`)
2. **Verify:** Trả về empty array `[]`

---

### Step 6: Test Error Cases

**6.1. Test invalid plan:**
```javascript
// Test trong console
const response = await fetch('https://ai.wordai.pro/api/v1/payments/checkout', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
        user_id: 'test_user',
        plan: 'invalid_plan',  // ❌ Invalid
        duration: '3_months'
    })
});
const result = await response.json();
console.log(result);
// Expected: { success: false, error: "Invalid plan" }
```

**6.2. Test missing user_id:**
```javascript
const response = await fetch('https://ai.wordai.pro/api/v1/payments/checkout', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
        plan: 'premium',
        duration: '3_months'
        // ❌ Missing user_id
    })
});
const result = await response.json();
console.log(result);
// Expected: { success: false, error: "Missing required fields" }
```

**6.3. Test invalid order number:**
```javascript
const response = await fetch(
    'https://ai.wordai.pro/api/v1/payments/status/INVALID-ORDER-123'
);
const result = await response.json();
console.log(result);
// Expected: { success: false, error: "Payment not found" }
```

---

### Step 7: Document Test Results

**7.1. Tạo test report:**
```markdown
# SePay Sandbox Test Report

## Test Date: [Date]
## Tester: [Your Name]

### ✅ Passed Tests:
- [x] Checkout API trả về đúng response
- [x] Form submit redirect đến SePay sandbox
- [x] Thanh toán thành công redirect về success_url
- [x] IPN callback được gọi và log đúng
- [x] Status API trả về đúng trạng thái
- [x] History API trả về đúng danh sách payments
- [x] Error handling cho invalid inputs

### ❌ Failed Tests:
- [ ] [If any]

### 🐛 Issues Found:
1. [Issue description]
2. [Issue description]

### 📝 Notes:
- [Any observations or recommendations]
```

---

### Step 8: Checklist trước khi qua Phase 2 (UI Implementation)

**Phase 1 Completion Checklist:**

- [ ] ✅ Test file HTML hoạt động và call được API
- [ ] ✅ Checkout API trả về đầy đủ form_fields + signature
- [ ] ✅ Form submit redirect đến SePay sandbox
- [ ] ✅ Có thể thanh toán thành công trên SePay sandbox
- [ ] ✅ Success redirect hoạt động (có order_invoice_number)
- [ ] ✅ Cancel redirect hoạt động
- [ ] ✅ IPN callback được gọi (verify trong logs)
- [ ] ✅ Payment status API trả về đúng trạng thái
- [ ] ✅ Payment history API trả về đúng danh sách
- [ ] ✅ Error handling hoạt động đúng
- [ ] ✅ Test report được document đầy đủ
- [ ] ✅ Hiểu rõ flow và có thể giải thích cho team

**Nếu tất cả checklist trên ✅ → Sang Phase 2: UI Implementation**

---

## 🔄 Auto-refresh Payment Status

Sau khi user quay về success page, bạn có thể tự động refresh status để cập nhật:

```javascript
function usePaymentStatusPolling(orderNumber, interval = 3000) {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!orderNumber) return;

    const checkStatus = async () => {
      try {
        const response = await fetch(
          `https://ai.wordai.pro/api/v1/payments/status/${orderNumber}`
        );
        const result = await response.json();

        if (result.success) {
          setStatus(result.data);

          // Stop polling if status is final
          if (['completed', 'failed', 'cancelled'].includes(result.data.status)) {
            setLoading(false);
            clearInterval(pollInterval);
          }
        }
      } catch (error) {
        console.error('Error polling payment status:', error);
      }
    };

    // Initial check
    checkStatus();

    // Poll every N seconds
    const pollInterval = setInterval(checkStatus, interval);

    return () => clearInterval(pollInterval);
  }, [orderNumber, interval]);

  return { status, loading };
}

// Usage in component:
function PaymentSuccessPage() {
  const router = useRouter();
  const { order } = router.query;
  const { status, loading } = usePaymentStatusPolling(order);

  if (loading) {
    return <div>Đang xác nhận thanh toán...</div>;
  }

  return (
    <div>
      <h1>Status: {status?.status}</h1>
      {/* Rest of component */}
    </div>
  );
}
```

---

## ⚠️ Error Handling

### Common Errors

1. **Invalid plan or duration**
```json
{
  "success": false,
  "error": "Invalid plan or duration"
}
```
→ Check plan is one of: `premium`, `pro`, `vip`
→ Check duration is one of: `3_months`, `12_months`

2. **Missing user_id**
```json
{
  "success": false,
  "error": "Validation error"
}
```
→ Ensure user_id is provided in request body

3. **Payment not found**
```json
{
  "success": false,
  "error": "Payment not found"
}
```
→ Order number không tồn tại hoặc sai format

4. **Network errors**
```javascript
try {
  const response = await fetch(...);
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
} catch (error) {
  console.error('Network error:', error);
  showError('Không thể kết nối đến server');
}
```

---

## 🧪 Testing

### Test với Sandbox

1. **SePay Sandbox Environment:**
   - Checkout URL: `https://pay-sandbox.sepay.vn/v1/checkout/init`
   - Test cards/accounts sẽ do SePay cung cấp

2. **Test Flow:**
```javascript
// Test checkout
const testCheckout = async () => {
  const response = await fetch('https://ai.wordai.pro/api/v1/payments/checkout', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      user_id: 'test_user_123',
      plan: 'premium',
      duration: '3_months',
      user_email: 'test@example.com',
      user_name: 'Test User',
    }),
  });

  const result = await response.json();
  console.log('Checkout result:', result);

  if (result.success) {
    console.log('Form fields:', result.data.form_fields);
    console.log('Checkout URL:', result.data.checkout_url);
  }
};
```

3. **Monitor Backend Logs:**
```bash
# Check payment service logs
docker logs payment-service -f

# Check Python service logs
docker logs ai-chatbot-rag -f

# Check NGINX logs
docker logs nginx-gateway -f
```

---

## 🔐 Security Notes

### IMPORTANT

1. **KHÔNG BAO GIỜ** expose `SEPAY_SECRET_KEY` ra frontend
2. Signature chỉ được tạo ở backend
3. Frontend chỉ submit form với signature đã có
4. Không cho phép user sửa `form_fields` trước khi submit

### Best Practices

1. **Validate user authentication** trước khi cho phép checkout
2. **Store payment_id** trong localStorage để tracking
3. **Handle errors gracefully** và hiển thị thông báo rõ ràng
4. **Use HTTPS** cho tất cả API calls
5. **Log errors** để debug

---

## 📞 Support & Troubleshooting

### Backend Logs
```bash
# Payment service logs
docker logs payment-service --tail 100 -f

# Python service logs
docker logs ai-chatbot-rag --tail 100 -f

# NGINX logs
docker exec nginx-gateway tail -f /var/log/nginx/access.log
```

### Common Issues

1. **Form không submit**
   - Check console logs
   - Verify checkout_url đúng format
   - Verify form_fields có đủ required fields

2. **IPN không được gọi**
   - Check NGINX routing: `/sepay/ipn` → payment-service
   - Check SePay có gửi IPN với `X-Secret-Key` header
   - Check backend logs cho IPN requests

3. **Subscription không được kích hoạt**
   - Check payment status = `completed`
   - Check `subscription_activated` = true
   - Check Python service logs for activation errors
   - Use retry activation API nếu cần

---

## 🎉 Summary Checklist

### Frontend Tasks

- [ ] Tạo pricing page với 3 gói (Premium, Pro, VIP)
- [ ] Implement checkout function gọi API
- [ ] Implement form submission to SePay
- [ ] Tạo `/payment/success` page
- [ ] Tạo `/payment/error` page
- [ ] Tạo `/payment/cancel` page
- [ ] Implement payment status checking
- [ ] Implement payment history page
- [ ] Add loading states
- [ ] Add error handling
- [ ] Test với sandbox environment

### API Endpoints Cần Dùng

✅ `POST /api/v1/payments/checkout` - Tạo checkout
✅ `GET /api/v1/payments/status/:order_invoice_number` - Check status
✅ `GET /api/v1/payments/user/:user_id` - Payment history

---

## 📚 Additional Resources

- **SePay Documentation:** Internal SEPAY_NODEJS_SDK.md
- **Backend API:** Payment service code in `/payment-service`
- **Test Environment:** Sandbox URLs in config

---

**Document Version:** 1.0
**Last Updated:** November 5, 2025
**Author:** AI Assistant
**Status:** Ready for Implementation
