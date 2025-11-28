# Points Purchase API Documentation

## Overview
This document describes the points purchase system that allows users to buy points packages through the SePay payment gateway.

## Available Packages

| Points | Price (VND) | Discount |
|--------|-------------|----------|
| 50     | 50,000      | -        |
| 100    | 95,000      | 5%       |
| 200    | 180,000     | 10%      |

**Note**: Regular price is 1,000 VND per point. Larger packages include discounts.

## Architecture

```
User → Frontend → Payment Service → SePay → Webhook → Payment Service → Python Service
                                                         ↓
                                                    Update Points
```

### Services Involved

1. **Frontend**: Initiates checkout, redirects to SePay
2. **Payment Service (Node.js)**: Creates checkout sessions, handles webhooks
3. **SePay**: Payment gateway (processes credit cards, banking, e-wallets)
4. **Python Service**: Updates user points balance

## API Endpoints

### 1. Create Points Purchase Checkout

**Endpoint**: `POST /api/v1/payments/checkout/points`

**Authentication**: Firebase ID token required

**Request Body**:
```json
{
  "points": "50"  // or "100", "200"
}
```

**Response**:
```json
{
  "success": true,
  "data": {
    "payment_id": "673e8f2a1b2c3d4e5f6a7b8c",
    "order_invoice_number": "WA-1234567890-abcd1234",
    "checkout_url": "https://pay.sepay.vn/v1/checkout/init",
    "form_fields": {
      "merchant": "your_merchant_id",
      "operation": "PURCHASE",
      "payment_method": "BANK_TRANSFER",
      "order_amount": "50000",
      "currency": "VND",
      "order_invoice_number": "WA-1234567890-abcd1234",
      "order_description": "Mua 50 điểm WordAI",
      "customer_id": "firebase_uid",
      "success_url": "https://wordai.pro/payment/success",
      "error_url": "https://wordai.pro/payment/error",
      "cancel_url": "https://wordai.pro/payment/cancel",
      "signature": "base64_encoded_signature"
    },
    "amount": 50000,
    "payment_type": "points_purchase",
    "points": 50
  }
}
```

**Flow**:
1. User selects points package (50/100/200)
2. Frontend calls `/api/v1/payments/checkout/points` with Firebase token
3. Payment service creates SePay checkout session and returns `form_fields`
4. **Frontend submits HTML form with form_fields to checkout_url**
5. User completes payment on SePay payment page

### 2. Add Points (Webhook Callback)

**Endpoint**: `POST /api/v1/points/add`

**Authentication**: Service secret header (`X-Service-Secret`)

**Request Body**:
```json
{
  "user_id": "firebase_uid",
  "points": 50,
  "payment_id": "sepay_transaction_id",
  "order_invoice_number": "POINTS_UID_1234567890",
  "payment_method": "credit_card",
  "amount": 50000,
  "reason": "Mua 50 điểm qua SePay"
}
```

**Response**:
```json
{
  "success": true,
  "user_id": "firebase_uid",
  "points_added": 50,
  "previous_balance": 100,
  "new_balance": 150,
  "payment_id": "sepay_transaction_id",
  "message": "Successfully added 50 points. New balance: 150"
}
```

**Flow**:
1. User completes payment on SePay
2. SePay sends IPN webhook to payment service
3. Payment service validates webhook signature
4. Detects `payment_type: 'points_purchase'` in payment document
5. Calls Python service `/api/v1/points/add` with service secret
6. Python service adds points to user's subscription
7. Returns success with new balance

## Payment Document Structure

When creating a points purchase, the payment service stores:

```javascript
{
  _id: ObjectId,
  user_id: "firebase_uid",
  payment_type: "points_purchase",  // Key field for webhook routing
  points: 50,  // Number of points being purchased
  order_invoice_number: "POINTS_UID_1234567890",
  amount: 50000,
  status: "pending",
  created_at: ISODate,
  payment_url: "https://portal.sepay.vn/...",
  sepay_response: { /* SePay API response */ }
}
```

After webhook receives payment confirmation:
```javascript
{
  // ... previous fields ...
  status: "completed",
  payment_id: "sepay_transaction_id",
  payment_method: "credit_card",
  completed_at: ISODate,
  webhook_data: { /* SePay IPN data */ }
}
```

## Subscription Updates

The `/api/v1/points/add` endpoint updates two collections:

### 1. subscriptions Collection
```javascript
{
  user_id: "firebase_uid",
  points_remaining: 150,  // Updated: old + new points
  updated_at: ISODate,
  payment_history: [
    {
      payment_id: "sepay_transaction_id",
      order_invoice_number: "POINTS_UID_1234567890",
      payment_method: "credit_card",
      amount_paid: 50000,
      points_purchased: 50,
      reason: "Mua 50 điểm qua SePay",
      timestamp: ISODate
    }
  ]
}
```

### 2. users Collection
```javascript
{
  uid: "firebase_uid",
  points_remaining: 150,  // Synchronized with subscription
  updated_at: ISODate
}
```

## Security

### Service-to-Service Authentication
- Payment service → Python service uses `X-Service-Secret` header
- Secret stored in environment variable `SERVICE_SECRET`
- Both services must have matching secrets

### SePay Webhook Validation
- Payment service validates webhook signature using secret key
- Ensures webhooks are from genuine SePay requests
- Invalid signatures are rejected

### Firebase Authentication
- Checkout endpoints require valid Firebase ID token
- User ID extracted from decoded token
- Prevents unauthorized checkout creation

## Error Handling

### Common Error Scenarios

1. **Invalid Points Package**
```json
{
  "error": "Invalid points value. Must be one of: 50, 100, 200"
}
```

2. **Unauthorized Webhook**
```json
{
  "error": "Unauthorized",
  "status": 401
}
```

3. **Subscription Not Found**
```json
{
  "error": "Subscription not found",
  "status": 404
}
```

4. **Database Update Failed**
```json
{
  "error": "Failed to update points",
  "status": 500
}
```

## Testing

### Manual Test Flow

1. **Create Checkout**:
```bash
curl -X POST http://localhost:3000/api/v1/payments/checkout/points \
  -H "Authorization: Bearer <FIREBASE_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"points": "50"}'
```

2. **Simulate Webhook** (use SePay test credentials):
- Complete payment on SePay test portal
- Webhook automatically sent to configured URL
- Check payment service logs for webhook processing

3. **Verify Points Added**:
```bash
# Check user subscription
db.subscriptions.findOne({user_id: "firebase_uid"})
```

### Integration Tests

Test webhook handler:
```javascript
// payment-service/tests/webhook.test.js
describe('Points Purchase Webhook', () => {
  it('should add points when payment succeeds', async () => {
    const webhookData = {
      id: 'txn_12345',
      order_invoice_number: 'POINTS_UID_1234567890',
      status: 2, // ORDER_PAID
      // ... other SePay fields
    };

    const response = await request(app)
      .post('/api/v1/webhook/sepay')
      .send(webhookData);

    expect(response.status).toBe(200);
    // Verify points added to user subscription
  });
});
```

## Deployment

### Environment Variables Required

**Payment Service**:
```env
SERVICE_SECRET=your-secret-key
SEPAY_ACCESS_KEY=your-sepay-key
SEPAY_SECRET_KEY=your-sepay-secret
PYTHON_SERVICE_URL=http://python-service:8000
```

**Python Service**:
```env
SERVICE_SECRET=your-secret-key
MONGODB_URI=mongodb://...
```

### Docker Deployment

1. **Build Payment Service**:
```bash
cd payment-service
docker build -t lekompozer/wordai-payment-service:latest .
docker push lekompozer/wordai-payment-service:latest
```

2. **Deploy with Docker Compose**:
```bash
# Update docker-compose.yml to use new image
docker-compose up -d payment-service
```

3. **Verify Deployment**:
```bash
# Check payment service logs
docker logs wordai-payment-service

# Test health endpoint
curl http://localhost:4000/health
```

## Frontend Integration

### Points Purchase Button

```javascript
async function purchasePoints(pointsPackage) {
  try {
    // Get Firebase token
    const token = await firebase.auth().currentUser.getIdToken();

    // Create checkout
    const response = await fetch('https://ai.wordai.pro/api/v1/payments/checkout/points', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ points: pointsPackage }) // "50", "100", or "200"
    });

    const result = await response.json();

    if (!result.success || !result.data) {
      throw new Error('Failed to create checkout');
    }

    const { checkout_url, form_fields } = result.data;

    // Create and submit form to SePay (same as subscription checkout)
    const form = document.createElement('form');
    form.method = 'POST';
    form.action = checkout_url;

    // Add all form fields as hidden inputs
    Object.entries(form_fields).forEach(([key, value]) => {
      const input = document.createElement('input');
      input.type = 'hidden';
      input.name = key;
      input.value = value;
      form.appendChild(input);
    });

    // Append form to body and submit
    document.body.appendChild(form);
    form.submit();

  } catch (error) {
    console.error('Failed to create checkout:', error);
    alert('Không thể tạo thanh toán. Vui lòng thử lại.');
  }
}
```

### Return URL Handler

After payment, SePay redirects to configured return URL:

```javascript
// On return page (e.g., /payment/return)
const urlParams = new URLSearchParams(window.location.search);
const status = urlParams.get('status');
const orderInvoiceNumber = urlParams.get('order_invoice_number');

if (status === 'success') {
  // Show success message
  showNotification('Payment successful! Points will be added shortly.');

  // Refresh user points balance
  refreshUserBalance();
} else {
  // Show error message
  showNotification('Payment failed. Please try again.');
}
```

## Monitoring

### Key Metrics to Track

1. **Checkout Creation Rate**: How many users initiate purchases
2. **Payment Completion Rate**: Percentage of checkouts that complete
3. **Webhook Success Rate**: Percentage of webhooks processed successfully
4. **Average Response Time**: Time from webhook to points added
5. **Revenue by Package**: Which packages are most popular

### Log Messages

**Checkout Created**:
```
🎯 Creating points purchase: 50 points for user abc123
✅ Points purchase created: POINTS_abc123_1234567890
```

**Webhook Received**:
```
📥 SePay webhook received: POINTS_abc123_1234567890
✅ Payment confirmed: POINTS_abc123_1234567890 (50 points)
```

**Points Added**:
```
🎯 Adding 50 points for user abc123 (payment: txn_12345)
✅ Points updated for user abc123: 100 → 150 (+50)
```

## Troubleshooting

### Common Issues

1. **Webhook Not Received**
   - Check SePay webhook URL configuration
   - Verify firewall allows SePay IP addresses
   - Check payment service logs for incoming requests

2. **Points Not Added**
   - Check payment document has `payment_type: 'points_purchase'`
   - Verify `X-Service-Secret` header is correct
   - Check Python service logs for errors

3. **Duplicate Points Added**
   - Webhooks should be idempotent
   - Check payment history array for duplicate payment_id
   - Consider adding unique constraint on payment_id in payment_history

### Debug Commands

```bash
# Check payment document
mongo
use wordai_db
db.payments.findOne({order_invoice_number: "POINTS_UID_1234567890"})

# Check user points
db.subscriptions.findOne({user_id: "firebase_uid"})

# Check payment service logs
docker logs wordai-payment-service --tail 100 -f

# Check Python service logs
docker logs wordai-aiservice --tail 100 -f
```

## Future Enhancements

1. **Bonus Points**: Add promotional bonus points for larger packages
2. **Point Expiration**: Implement expiration dates for purchased points
3. **Referral Rewards**: Give points for referring new users
4. **Gift Points**: Allow users to gift points to others
5. **Point History**: Show detailed point transaction history
6. **Analytics Dashboard**: Track points usage patterns

## Related Documentation

- [SEPAY_INTEGRATION_CHECKLIST.md](./SEPAY_INTEGRATION_CHECKLIST.md) - SePay integration details
- [SUBSCRIPTION_API_FRONTEND_GUIDE.md](./SUBSCRIPTION_API_FRONTEND_GUIDE.md) - Subscription system
- Payment service README - Node.js service documentation
