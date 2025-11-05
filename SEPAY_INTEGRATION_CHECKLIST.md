# SePay Integration - Implementation Checklist (Sandbox Testing)

## 📋 PHÂN TÍCH TÀI LIỆU SEPAY

### **Thông tin quan trọng từ tài liệu:**

1. **Sandbox Credentials (đã có trong .env):**
   - ✅ `SEPAY_API_MERCHANT_ID` - Merchant ID
   - ✅ `SEPAY_SECRET_KEY` - Secret key để tạo signature
   - ⚠️ **KHÔNG CÓ** SEPAY_API_KEY (không cần cho form checkout)

2. **Sandbox Endpoints:**
   - Form checkout: `https://pay-sandbox.sepay.vn/v1/checkout/init`
   - API base: `https://pgapi-sandbox.sepay.vn`
   - IPN nhận về: `https://ai.wordai.pro/sepay/ipn`

3. **Luồng thanh toán:**
   ```
   User → Website → Submit Form → SePay Checkout Page
   → User Pay → SePay → IPN Callback (https://ai.wordai.pro/sepay/ipn)
   → Website Update Order → Redirect (success/error/cancel URL)
   ```

---

## 🎯 DANH SÁCH CÔNG VIỆC - ƯU TIÊN

### **PHASE 1: INFRASTRUCTURE DEPLOYMENT** ⚡ (Ưu tiên cao nhất)

#### **Task 1.1: Tạo NGINX Configuration**
- [ ] Tạo `nginx/nginx.conf` - Main config
- [ ] Tạo `nginx/conf.d/ai-wordai.conf` - Site config với SSL
- [ ] Cấu hình upstream routing:
  - `/api/v1/payments/*` → Node.js (port 3000)
  - `/sepay/*` → Node.js (port 3000) - IPN endpoint
  - `/*` → Python (port 8000)
- [ ] Sử dụng SSL certificates: `/etc/letsencrypt/live/ai.wordai.pro/`
- [ ] Rate limiting cho payment endpoints
- [ ] WebSocket support cho Python service

**Files cần tạo:**
- `nginx/nginx.conf`
- `nginx/conf.d/ai-wordai.conf`

---

#### **Task 1.2: Verify Docker Compose**
- [ ] Kiểm tra `docker-compose.yml` đã đúng chưa
- [ ] Verify networking: all services in `ai-chatbot-network`
- [ ] Verify environment variables
- [ ] Verify volume mounts (SSL certs, logs)

---

#### **Task 1.3: Deploy to Production**
- [ ] Commit all code
- [ ] Push to git
- [ ] SSH to production server
- [ ] Pull latest code
- [ ] Run `docker-compose build`
- [ ] Run `docker-compose up -d`
- [ ] Verify all containers running:
  - `ai-chatbot-rag` (Python)
  - `payment-service` (Node.js)
  - `nginx-gateway`
  - `mongodb`
  - `redis-server`

---

### **PHASE 2: SEPAY INTEGRATION FIXES** 🔧

#### **Task 2.1: Update Payment Service Code**

**Vấn đề:** Code hiện tại dùng sai API của SePay

**Cần sửa trong `payment-service/src/controllers/paymentController.js`:**

```javascript
// ❌ SAI - Code hiện tại dùng API endpoint (không có)
const sepayResponse = await axios.post(
  `${config.sepay.apiUrl}/checkout`,
  sepayPayload,
  {
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${config.sepay.apiKey}`,
    }
  }
);

// ✅ ĐÚNG - Phải dùng HTML form
// 1. Tạo form fields với signature
const formFields = createCheckoutFormFields({
  merchant: config.sepay.merchantId,
  operation: 'PURCHASE',
  payment_method: 'BANK_TRANSFER',
  order_amount: price.toString(),
  currency: 'VND',
  order_invoice_number: orderInvoiceNumber,
  order_description: `WordAI ${plan.toUpperCase()} - ${duration}`,
  customer_id: user_id,
  success_url: `https://ai.wordai.pro/payment/success`,
  error_url: `https://ai.wordai.pro/payment/error`,
  cancel_url: `https://ai.wordai.pro/payment/cancel`,
});

// 2. Thêm signature
formFields.signature = generateSignature(formFields, config.sepay.secretKey);

// 3. Trả về form HTML để frontend submit
return res.json({
  checkout_url: 'https://pay-sandbox.sepay.vn/v1/checkout/init',
  form_fields: formFields,
  payment_id: paymentId
});
```

**Chi tiết cần sửa:**

1. **Tạo hàm `generateSignature()`:**
```javascript
function generateSignature(fields, secretKey) {
  const signedFields = [
    'merchant', 'operation', 'payment_method', 'order_amount',
    'currency', 'order_invoice_number', 'order_description',
    'customer_id', 'success_url', 'error_url', 'cancel_url'
  ];

  const signedString = signedFields
    .filter(field => fields[field] !== undefined)
    .map(field => `${field}=${fields[field]}`)
    .join(',');

  const hmac = crypto.createHmac('sha256', secretKey);
  hmac.update(signedString);
  return hmac.digest('base64');
}
```

2. **Đổi response format** - Thay vì trả QR code, trả form fields để frontend submit

---

#### **Task 2.2: Update Webhook Handler**

**File:** `payment-service/src/controllers/webhookController.js`

**Cần sửa:**

1. **IPN URL:** Đổi từ `/api/v1/webhooks/sepay/callback` → `/sepay/ipn`

2. **Verify signature:** Đổi từ `X-Sepay-Signature` header → `X-Secret-Key` header
```javascript
function verifyIPN(req) {
  const secretKey = req.headers['x-secret-key'];

  if (secretKey !== config.sepay.secretKey) {
    throw new AppError('Invalid secret key', 401);
  }

  return true;
}
```

3. **Xử lý notification_type:**
```javascript
if (payload.notification_type === 'ORDER_PAID') {
  // Thanh toán thành công
  const { order, transaction } = payload;

  // Update payment status
  await paymentsCollection.updateOne(
    { order_invoice_number: order.order_invoice_number },
    {
      $set: {
        status: 'completed',
        sepay_transaction_id: transaction.transaction_id,
        completed_at: new Date(),
        ipn_payload: payload
      }
    }
  );

  // Activate subscription
  await activateSubscription(order, transaction);
}
```

---

#### **Task 2.3: Update Config Variables**

**File:** `payment-service/src/config/index.js`

```javascript
sepay: {
  merchantId: process.env.SEPAY_API_MERCHANT_ID,  // Đổi tên
  secretKey: process.env.SEPAY_SECRET_KEY,
  checkoutUrl: process.env.SEPAY_CHECKOUT_URL || 'https://pay-sandbox.sepay.vn/v1/checkout/init',
  apiUrl: process.env.SEPAY_API_URL || 'https://pgapi-sandbox.sepay.vn',
  sandbox: process.env.SEPAY_SANDBOX === 'true',
}
```

**Update .env:**
```bash
# Đổi tên biến
SEPAY_API_MERCHANT_ID=xxx
SEPAY_SECRET_KEY=xxx
SEPAY_CHECKOUT_URL=https://pay-sandbox.sepay.vn/v1/checkout/init
SEPAY_API_URL=https://pgapi-sandbox.sepay.vn
SEPAY_SANDBOX=true
```

---

#### **Task 2.4: Update Routes**

**File:** `payment-service/src/routes/webhookRoutes.js`

```javascript
// Đổi route
router.post(
  '/ipn',  // Từ '/sepay/callback' → '/ipn'
  asyncHandler(webhookController.handleIPN)
);
```

**File:** `payment-service/src/index.js`

```javascript
// Mount webhooks tại /sepay
app.use('/sepay', webhookRoutes);
// → Result: POST /sepay/ipn
```

---

### **PHASE 3: FRONTEND INTEGRATION** 🎨

#### **Task 3.1: Tạo Checkout Flow**

**Luồng:**
1. User chọn plan → Click "Thanh toán"
2. Frontend gọi: `POST /api/v1/payments/checkout`
3. Backend trả về: `{ checkout_url, form_fields, payment_id }`
4. Frontend tạo form HTML và submit:
```javascript
const form = document.createElement('form');
form.method = 'POST';
form.action = response.checkout_url;

Object.keys(response.form_fields).forEach(key => {
  const input = document.createElement('input');
  input.type = 'hidden';
  input.name = key;
  input.value = response.form_fields[key];
  form.appendChild(input);
});

document.body.appendChild(form);
form.submit();
```
5. SePay hiển thị trang thanh toán
6. User thanh toán → SePay gọi IPN → Backend activate subscription
7. SePay redirect về success_url

---

#### **Task 3.2: Tạo Callback Pages**

Cần tạo 3 pages trên frontend:
- `/payment/success?order={order_invoice_number}`
- `/payment/error?order={order_invoice_number}`
- `/payment/cancel?order={order_invoice_number}`

Mỗi page gọi API để lấy trạng thái payment:
```javascript
const status = await fetch(`/api/v1/payments/status/${order_invoice_number}`);
```

---

### **PHASE 4: TESTING** 🧪

#### **Task 4.1: Test Infrastructure**
- [ ] Test NGINX routing:
  - `curl https://ai.wordai.pro/health` → Python service
  - `curl https://ai.wordai.pro/api/v1/payments/health` → Node.js
- [ ] Test SSL certificates
- [ ] Test inter-service communication:
  - Node.js → MongoDB
  - Node.js → Python service

---

#### **Task 4.2: Test Payment Flow (Sandbox)**

**Kịch bản test:**

1. **Tạo checkout:**
```bash
curl -X POST https://ai.wordai.pro/api/v1/payments/checkout \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test_user_123",
    "plan": "premium",
    "duration": "3_months"
  }'
```

2. **Submit form** (manual hoặc script)

3. **Verify IPN received:**
   - Check logs: `docker logs payment-service`
   - Check MongoDB: payment status = 'completed'
   - Check MongoDB: subscription created

4. **Test callback URLs:**
   - Success: `https://ai.wordai.pro/payment/success?order=xxx`
   - Error: `https://ai.wordai.pro/payment/error?order=xxx`

---

#### **Task 4.3: Test Subscription Activation**

Verify Python service được gọi:
```bash
# Check Python logs
docker logs ai-chatbot-rag | grep "Activating subscription"

# Check MongoDB
db.user_subscriptions.find({ user_id: "test_user_123" })
db.payments.find({ order_invoice_number: "xxx" })
```

---

## 📊 PRIORITY SUMMARY

### **🔴 CRITICAL (Làm ngay):**
1. ✅ Task 1.1: Tạo NGINX config
2. ✅ Task 1.2: Verify Docker Compose
3. ✅ Task 1.3: Deploy infrastructure

### **🟡 HIGH (Sau khi deploy):**
4. Task 2.1: Fix payment controller (signature + form)
5. Task 2.2: Fix webhook handler (IPN)
6. Task 2.3: Update config variables
7. Task 2.4: Update routes

### **🟢 MEDIUM (Tích hợp frontend):**
8. Task 3.1: Checkout flow
9. Task 3.2: Callback pages

### **🔵 LOW (Testing):**
10. Task 4.1: Infrastructure tests
11. Task 4.2: Payment flow tests
12. Task 4.3: Subscription activation tests

---

## 🚨 QUAN TRỌNG - SAI SÓT HIỆN TẠI

### **❌ Code hiện tại SAI:**

1. **Không có SEPAY_API_KEY** - SePay không dùng API key cho checkout
2. **Không dùng form HTML** - Phải submit form, không phải gọi API
3. **Sai signature method** - Dùng header, thực tế dùng form field
4. **Sai IPN verification** - Dùng `X-Sepay-Signature`, thực tế dùng `X-Secret-Key`
5. **Sai endpoint** - Checkout endpoint là form submission URL, không phải REST API

### **✅ Cách đúng:**

1. **Frontend submit form** với signature
2. **SePay hiển thị** trang thanh toán
3. **User thanh toán** trên SePay
4. **SePay gọi IPN** (`POST /sepay/ipn`) với `X-Secret-Key` header
5. **Backend xử lý IPN** → Update payment → Activate subscription
6. **SePay redirect** user về success/error/cancel URL

---

## 📝 FILES CẦN SỬA

### **Node.js Service:**
- `payment-service/src/config/index.js` - Update config
- `payment-service/src/controllers/paymentController.js` - Fix checkout logic
- `payment-service/src/controllers/webhookController.js` - Fix IPN handler
- `payment-service/src/routes/webhookRoutes.js` - Update routes

### **Infrastructure:**
- `nginx/nginx.conf` - NGINX main config
- `nginx/conf.d/ai-wordai.conf` - Site config
- `.env` - Update SePay variables

### **New Files:**
- `nginx/` directory và configs
- Frontend callback pages (nếu chưa có)

---

## 🎯 NEXT STEPS

**Bây giờ làm gì:**

1. **Task 1.1** - Tôi tạo NGINX config cho bạn
2. **Task 1.3** - Deploy lên production
3. **Task 2.1-2.4** - Fix Node.js code theo đúng SePay docs
4. **Task 4** - Test payment flow sandbox

Bạn muốn tôi bắt đầu với Task 1.1 (NGINX config) không? 🚀
