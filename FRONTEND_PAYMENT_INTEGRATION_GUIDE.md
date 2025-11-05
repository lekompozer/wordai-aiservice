# Frontend Payment Integration Guide - WordAI SePay

## 📋 Tổng Quan

Tài liệu này hướng dẫn Frontend team tích hợp luồng thanh toán SePay vào WordAI. Luồng thanh toán sử dụng phương thức **HTML form submission** (không phải REST API).

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
```javascript
// User click button "Thanh toán"
async function handlePayment(plan, duration) {
  try {
    // Get user info from your state/context
    const userId = getCurrentUserId();
    const userEmail = getCurrentUserEmail();
    const userName = getCurrentUserName();

    // Call checkout API
    const response = await fetch('https://ai.wordai.pro/api/v1/payments/checkout', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        // Add your auth token if needed
        // 'Authorization': `Bearer ${token}`,
      },
      body: JSON.stringify({
        user_id: userId,
        plan: plan,           // "premium", "pro", or "vip"
        duration: duration,   // "3_months" or "12_months"
        user_email: userEmail,
        user_name: userName,
      }),
    });

    const result = await response.json();

    if (result.success) {
      // Save payment_id to localStorage for later reference
      localStorage.setItem('current_payment_id', result.data.payment_id);
      localStorage.setItem('current_order_number', result.data.order_invoice_number);

      // Submit form to SePay
      submitFormToSePay(result.data.checkout_url, result.data.form_fields);
    } else {
      // Handle error
      showError(result.error);
    }
  } catch (error) {
    console.error('Checkout error:', error);
    showError('Có lỗi xảy ra, vui lòng thử lại');
  }
}
```

### Step 2: Submit form to SePay
```javascript
/**
 * Submit form to SePay checkout page
 * This will redirect user to SePay
 */
function submitFormToSePay(checkoutUrl, formFields) {
  // Create a hidden form
  const form = document.createElement('form');
  form.method = 'POST';
  form.action = checkoutUrl;
  form.style.display = 'none';

  // Add all form fields as hidden inputs
  Object.keys(formFields).forEach(key => {
    const input = document.createElement('input');
    input.type = 'hidden';
    input.name = key;
    input.value = formFields[key];
    form.appendChild(input);
  });

  // Add form to body and submit
  document.body.appendChild(form);
  form.submit();
  
  // User will be redirected to SePay
  // Show loading message
  showMessage('Đang chuyển đến trang thanh toán...');
}
```

### Step 3: React Example (Complete Component)
```jsx
import React, { useState } from 'react';
import { useAuth } from './hooks/useAuth';

function PricingCard({ plan, price3Months, price12Months }) {
  const { user } = useAuth();
  const [loading, setLoading] = useState(false);

  const handleCheckout = async (duration) => {
    if (!user) {
      alert('Vui lòng đăng nhập để thanh toán');
      return;
    }

    setLoading(true);

    try {
      const response = await fetch('https://ai.wordai.pro/api/v1/payments/checkout', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          user_id: user.id,
          plan: plan,
          duration: duration,
          user_email: user.email,
          user_name: user.name,
        }),
      });

      const result = await response.json();

      if (result.success) {
        // Save for later reference
        localStorage.setItem('current_payment_id', result.data.payment_id);
        localStorage.setItem('current_order_number', result.data.order_invoice_number);

        // Submit form
        submitFormToSePay(result.data.checkout_url, result.data.form_fields);
      } else {
        alert(`Lỗi: ${result.error}`);
        setLoading(false);
      }
    } catch (error) {
      console.error('Checkout error:', error);
      alert('Có lỗi xảy ra, vui lòng thử lại');
      setLoading(false);
    }
  };

  const submitFormToSePay = (checkoutUrl, formFields) => {
    const form = document.createElement('form');
    form.method = 'POST';
    form.action = checkoutUrl;
    form.style.display = 'none';

    Object.keys(formFields).forEach(key => {
      const input = document.createElement('input');
      input.type = 'hidden';
      input.name = key;
      input.value = formFields[key];
      form.appendChild(input);
    });

    document.body.appendChild(form);
    form.submit();
  };

  return (
    <div className="pricing-card">
      <h3>{plan.toUpperCase()}</h3>
      <div className="prices">
        <div>
          <p>3 tháng: {price3Months.toLocaleString('vi-VN')}đ</p>
          <button 
            onClick={() => handleCheckout('3_months')}
            disabled={loading}
          >
            {loading ? 'Đang xử lý...' : 'Thanh toán 3 tháng'}
          </button>
        </div>
        <div>
          <p>12 tháng: {price12Months.toLocaleString('vi-VN')}đ</p>
          <button 
            onClick={() => handleCheckout('12_months')}
            disabled={loading}
          >
            {loading ? 'Đang xử lý...' : 'Thanh toán 12 tháng'}
          </button>
        </div>
      </div>
    </div>
  );
}

export default PricingCard;
```

---

## 📄 Callback Pages - Success/Error/Cancel

### URL Patterns
Sau khi user thanh toán hoặc hủy, SePay sẽ redirect về các URL:

```
✅ Success: https://ai.wordai.pro/payment/success?order=WA-xxx
❌ Error:   https://ai.wordai.pro/payment/error?order=WA-xxx
🚫 Cancel:  https://ai.wordai.pro/payment/cancel?order=WA-xxx
```

### Các trang cần tạo:

#### 1. Success Page (`/payment/success`)
```jsx
import React, { useEffect, useState } from 'react';
import { useRouter } from 'next/router';

function PaymentSuccessPage() {
  const router = useRouter();
  const { order } = router.query;
  const [paymentStatus, setPaymentStatus] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (order) {
      checkPaymentStatus(order);
    }
  }, [order]);

  const checkPaymentStatus = async (orderNumber) => {
    try {
      const response = await fetch(
        `https://ai.wordai.pro/api/v1/payments/status/${orderNumber}`
      );
      const result = await response.json();

      if (result.success) {
        setPaymentStatus(result.data);
      }
    } catch (error) {
      console.error('Error checking payment status:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return <div>Đang kiểm tra thanh toán...</div>;
  }

  if (!paymentStatus) {
    return <div>Không tìm thấy thông tin thanh toán</div>;
  }

  return (
    <div className="payment-success">
      <h1>✅ Thanh toán thành công!</h1>
      <div className="payment-details">
        <p>Mã đơn hàng: <strong>{paymentStatus.order_invoice_number}</strong></p>
        <p>Gói: <strong>{paymentStatus.plan.toUpperCase()}</strong></p>
        <p>Thời hạn: <strong>{paymentStatus.duration}</strong></p>
        <p>Số tiền: <strong>{paymentStatus.price.toLocaleString('vi-VN')}đ</strong></p>
        <p>Trạng thái: <strong>{paymentStatus.status}</strong></p>
      </div>
      <button onClick={() => router.push('/dashboard')}>
        Về trang chủ
      </button>
    </div>
  );
}

export default PaymentSuccessPage;
```

#### 2. Error Page (`/payment/error`)
```jsx
import React, { useEffect, useState } from 'react';
import { useRouter } from 'next/router';

function PaymentErrorPage() {
  const router = useRouter();
  const { order } = router.query;

  return (
    <div className="payment-error">
      <h1>❌ Thanh toán thất bại</h1>
      <p>Mã đơn hàng: {order}</p>
      <p>Đã có lỗi xảy ra trong quá trình thanh toán.</p>
      <div className="actions">
        <button onClick={() => router.push('/pricing')}>
          Thử lại
        </button>
        <button onClick={() => router.push('/support')}>
          Liên hệ hỗ trợ
        </button>
      </div>
    </div>
  );
}

export default PaymentErrorPage;
```

#### 3. Cancel Page (`/payment/cancel`)
```jsx
import React from 'react';
import { useRouter } from 'next/router';

function PaymentCancelPage() {
  const router = useRouter();
  const { order } = router.query;

  return (
    <div className="payment-cancel">
      <h1>🚫 Thanh toán đã bị hủy</h1>
      <p>Mã đơn hàng: {order}</p>
      <p>Bạn đã hủy thanh toán.</p>
      <div className="actions">
        <button onClick={() => router.push('/pricing')}>
          Quay lại trang giá
        </button>
        <button onClick={() => router.push('/dashboard')}>
          Về trang chủ
        </button>
      </div>
    </div>
  );
}

export default PaymentCancelPage;
```

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

## 📦 Complete Example - Vue.js

```vue
<template>
  <div class="payment-flow">
    <!-- Pricing Cards -->
    <div v-if="!isProcessing" class="pricing-cards">
      <div v-for="plan in plans" :key="plan.name" class="pricing-card">
        <h3>{{ plan.name.toUpperCase() }}</h3>
        <div class="price-options">
          <div class="price-option">
            <p>3 tháng</p>
            <p class="price">{{ formatPrice(plan.price3Months) }}</p>
            <button @click="handleCheckout(plan.name, '3_months')">
              Thanh toán
            </button>
          </div>
          <div class="price-option">
            <p>12 tháng</p>
            <p class="price">{{ formatPrice(plan.price12Months) }}</p>
            <button @click="handleCheckout(plan.name, '12_months')">
              Thanh toán
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Processing State -->
    <div v-else class="processing">
      <div class="spinner"></div>
      <p>Đang chuyển đến trang thanh toán...</p>
    </div>
  </div>
</template>

<script>
export default {
  name: 'PaymentFlow',
  data() {
    return {
      isProcessing: false,
      plans: [
        {
          name: 'premium',
          price3Months: 279000,
          price12Months: 990000,
        },
        {
          name: 'pro',
          price3Months: 447000,
          price12Months: 1699000,
        },
        {
          name: 'vip',
          price3Months: 747000,
          price12Months: 2799000,
        },
      ],
    };
  },
  methods: {
    formatPrice(price) {
      return price.toLocaleString('vi-VN') + 'đ';
    },

    async handleCheckout(plan, duration) {
      // Check if user is logged in
      const user = this.$store.state.user;
      if (!user) {
        this.$router.push('/login');
        return;
      }

      this.isProcessing = true;

      try {
        // Call checkout API
        const response = await fetch(
          'https://ai.wordai.pro/api/v1/payments/checkout',
          {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({
              user_id: user.id,
              plan: plan,
              duration: duration,
              user_email: user.email,
              user_name: user.name,
            }),
          }
        );

        const result = await response.json();

        if (result.success) {
          // Save payment info
          localStorage.setItem('current_payment_id', result.data.payment_id);
          localStorage.setItem(
            'current_order_number',
            result.data.order_invoice_number
          );

          // Submit form to SePay
          this.submitFormToSePay(
            result.data.checkout_url,
            result.data.form_fields
          );
        } else {
          this.$notify.error({
            title: 'Lỗi',
            message: result.error || 'Có lỗi xảy ra',
          });
          this.isProcessing = false;
        }
      } catch (error) {
        console.error('Checkout error:', error);
        this.$notify.error({
          title: 'Lỗi',
          message: 'Không thể kết nối đến server',
        });
        this.isProcessing = false;
      }
    },

    submitFormToSePay(checkoutUrl, formFields) {
      // Create hidden form
      const form = document.createElement('form');
      form.method = 'POST';
      form.action = checkoutUrl;
      form.style.display = 'none';

      // Add form fields
      Object.keys(formFields).forEach((key) => {
        const input = document.createElement('input');
        input.type = 'hidden';
        input.name = key;
        input.value = formFields[key];
        form.appendChild(input);
      });

      // Submit
      document.body.appendChild(form);
      form.submit();
    },
  },
};
</script>

<style scoped>
.pricing-cards {
  display: flex;
  gap: 20px;
  justify-content: center;
  padding: 40px;
}

.pricing-card {
  border: 1px solid #ddd;
  border-radius: 8px;
  padding: 30px;
  min-width: 250px;
}

.price-options {
  display: flex;
  flex-direction: column;
  gap: 20px;
  margin-top: 20px;
}

.price {
  font-size: 24px;
  font-weight: bold;
  color: #4CAF50;
}

button {
  background-color: #4CAF50;
  color: white;
  border: none;
  padding: 12px 24px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 16px;
}

button:hover {
  background-color: #45a049;
}

.processing {
  text-align: center;
  padding: 60px;
}

.spinner {
  width: 50px;
  height: 50px;
  border: 5px solid #f3f3f3;
  border-top: 5px solid #4CAF50;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin: 0 auto 20px;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}
</style>
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
