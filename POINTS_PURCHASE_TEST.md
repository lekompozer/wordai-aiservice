# Points Purchase - Quick Test Guide

## ✅ Correct Endpoint

```
POST https://ai.wordai.pro/api/v1/payments/checkout/points
```

**NOT**: `/api/v1/checkout/points` (thiếu `/payments`)

## 🧪 Test Request

### 1. Get Firebase Token
```javascript
// From browser console on your site
const token = await firebase.auth().currentUser.getIdToken();
console.log(token);
```

### 2. Create Checkout (50 points)
```bash
curl -X POST https://ai.wordai.pro/api/v1/payments/checkout/points \
  -H "Authorization: Bearer YOUR_FIREBASE_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"points": "50"}'
```

### Expected Response:
```json
{
  "success": true,
  "data": {
    "payment_id": "673e8f2a1b2c3d4e5f6a7b8c",
    "order_invoice_number": "WA-1234567890-abcd1234",
    "checkout_url": "https://pay.sepay.vn/v1/checkout/init",
    "form_fields": {
      "merchant": "...",
      "operation": "PURCHASE",
      "payment_method": "BANK_TRANSFER",
      "order_amount": "50000",
      "currency": "VND",
      "order_invoice_number": "WA-1234567890-abcd1234",
      "order_description": "Mua 50 điểm WordAI",
      "customer_id": "...",
      "success_url": "https://wordai.pro/payment/success",
      "error_url": "https://wordai.pro/payment/error",
      "cancel_url": "https://wordai.pro/payment/cancel",
      "signature": "..."
    },
    "amount": 50000,
    "payment_type": "points_purchase",
    "points": 50
  }
}
```

**⚠️ IMPORTANT**: Response contains `form_fields`, NOT a direct `payment_url`!
You must submit these form fields to `checkout_url` via POST.

## 📦 Available Packages

| Points | Price (VND) | Endpoint Value |
|--------|-------------|----------------|
| 50     | 50,000      | `"50"`         |
| 100    | 95,000      | `"100"`        |
| 200    | 180,000     | `"200"`        |

## 🔍 Debug on Server

### Check logs:
```bash
ssh root@104.248.147.155 "docker logs payment-service --tail 50 -f"
```

### Test health:
```bash
curl https://ai.wordai.pro/api/v1/payments/status/test
```

### Check NGINX routing:
```bash
ssh root@104.248.147.155 "docker logs nginx-gateway --tail 100 | grep checkout"
```

## 🛠️ Frontend Integration (Correct)

```javascript
async function purchasePoints(pointsPackage) {
  try {
    const token = await firebase.auth().currentUser.getIdToken();

    const response = await fetch('https://ai.wordai.pro/api/v1/payments/checkout/points', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ points: pointsPackage })
    });

    const result = await response.json();

    if (!result.success || !result.data) {
      throw new Error('Failed to create checkout');
    }

    // Extract checkout URL and form fields
    const { checkout_url, form_fields, order_invoice_number } = result.data;

    console.log('✅ Checkout created:', order_invoice_number);

    // Store order info for tracking
    localStorage.setItem('pending_order', JSON.stringify({
      order_invoice_number,
      points: pointsPackage,
      timestamp: Date.now()
    }));

    // Create form and submit to SePay
    const form = document.createElement('form');
    form.method = 'POST';
    form.action = checkout_url;

    // Add all form fields
    Object.entries(form_fields).forEach(([key, value]) => {
      const input = document.createElement('input');
      input.type = 'hidden';
      input.name = key;
      input.value = value;
      form.appendChild(input);
    });

    document.body.appendChild(form);
    form.submit();

  } catch (error) {
    console.error('Failed:', error);
    alert('Không thể tạo thanh toán. Vui lòng thử lại.');
  }
}
```

**🔑 Key Points:**
1. Response has `checkout_url` and `form_fields`, NOT `payment_url`
2. Must create HTML form and submit (POST) to `checkout_url`
3. Include ALL `form_fields` as hidden inputs
4. This is the same pattern as subscription checkout## ⚠️ Common Errors

### 404 Not Found
- ❌ Wrong: `/api/v1/checkout/points`
- ✅ Correct: `/api/v1/payments/checkout/points`

### 401 Unauthorized
- Missing or invalid Firebase token
- Check: `Authorization: Bearer <token>` header

### 400 Bad Request
- Invalid points value
- Must be string: `"50"`, `"100"`, or `"200"` (not number)

### Frontend: payment_url is undefined
- ❌ Response does NOT have `payment_url` field
- ✅ Response has `checkout_url` + `form_fields`
- Must submit form, not redirect directly

## 📊 Full Flow

1. **User clicks "Buy 50 Points"**
2. **Frontend**: GET Firebase token
3. **Frontend**: POST to `/api/v1/payments/checkout/points`
4. **Payment Service**: Create SePay checkout
5. **Payment Service**: Return payment_url
6. **Frontend**: Redirect to payment_url
7. **User**: Complete payment on SePay
8. **SePay**: Send webhook to `/sepay/ipn`
9. **Payment Service**: Validate webhook
10. **Payment Service**: POST to Python `/api/v1/points/add`
11. **Python Service**: Add points to user
12. **SePay**: Redirect user back to return_url

## 🎯 Test on Production

```bash
# Replace YOUR_TOKEN with actual Firebase token
curl -X POST https://ai.wordai.pro/api/v1/payments/checkout/points \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"points": "50"}' \
  -v
```

Look for:
- Status: `200 OK`
- Response contains: `success: true`, `data.checkout_url`, `data.form_fields`, `data.amount`, `data.points`
- **NOT** `payment_url` (this field doesn't exist)
