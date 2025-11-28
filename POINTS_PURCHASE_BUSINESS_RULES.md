# Points Purchase Business Rules

## Overview
Quy định về việc mua điểm (points) dựa trên loại tài khoản và trạng thái subscription.

## Business Rules

### 1. 🆓 User FREE (Chưa có subscription)
- **Được phép**: Mua điểm **1 lần duy nhất**
- **Sau đó**: Bắt buộc phải nâng cấp lên Premium/Pro/VIP để tiếp tục
- **Lý do**: Khuyến khích user upgrade lên paid plan

**Error Message**:
```
Bạn đã mua điểm 1 lần. Vui lòng nâng cấp lên gói Premium, Pro hoặc VIP để tiếp tục sử dụng và mua thêm điểm.
```

### 2. ⏰ Subscription Hết Hạn (Expired)
- **Được phép**: Mua điểm **1 lần** sau khi hết hạn
- **Sau đó**: Bắt buộc phải gia hạn subscription để tiếp tục
- **Lý do**: Cho phép user tiếp tục dùng 1 chút, nhưng phải renew để dùng lâu dài

**Error Message**: (giống FREE user)
```
Bạn đã mua điểm 1 lần. Vui lòng nâng cấp lên gói Premium, Pro hoặc VIP để tiếp tục sử dụng và mua thêm điểm.
```

### 3. ✅ Subscription Còn Hạn (Active)
- **Được phép**: Mua điểm **không giới hạn**
- **Premium/Pro/VIP**: Thoải mái mua bao nhiêu lần cũng được
- **Lý do**: Reward cho paid users

## Implementation Details

### Logic Kiểm Tra

```javascript
// Check subscription status
const subscription = await subscriptionsCollection.findOne({ user_id });
const currentPlan = subscription.current_plan || 'free';
const subscriptionExpiry = subscription.subscription_expires_at;
const isSubscriptionActive = subscriptionExpiry && new Date(subscriptionExpiry) > new Date();

// Count completed points purchases
const completedPointsPurchases = await paymentsCollection.countDocuments({
    user_id,
    payment_type: 'points_purchase',
    status: 'completed'
});

// Apply business rules
if (!isSubscriptionActive) {
    // FREE or EXPIRED
    if (completedPointsPurchases >= 1) {
        throw new AppError('Bạn đã mua điểm 1 lần...', 403);
    }
} else {
    // ACTIVE subscription - unlimited
    // Allow purchase
}
```

### Database Structure

**subscriptions collection**:
```javascript
{
  user_id: "firebase_uid",
  current_plan: "free" | "premium" | "pro" | "vip",
  subscription_expires_at: ISODate("2025-12-31T23:59:59Z"),
  points_remaining: 100
}
```

**payments collection**:
```javascript
{
  user_id: "firebase_uid",
  payment_type: "points_purchase",
  status: "completed",
  points: 50,
  created_at: ISODate
}
```

## User Journey Examples

### Example 1: Free User
1. User signs up → **FREE** account
2. Mua 50 điểm → ✅ **Thành công** (lần 1)
3. Dùng hết điểm, muốn mua tiếp → ❌ **Bị chặn**
4. Phải upgrade lên Premium → ✅ Được mua tiếp

### Example 2: Premium User Active
1. User có Premium còn hạn (expires: 2025-12-31)
2. Mua 50 điểm → ✅ **Thành công** (lần 1)
3. Mua 100 điểm → ✅ **Thành công** (lần 2)
4. Mua 200 điểm → ✅ **Thành công** (lần 3)
5. Mua tiếp → ✅ **Không giới hạn**

### Example 3: Premium User Expired
1. User có Premium nhưng hết hạn (expires: 2024-12-31)
2. Mua 50 điểm → ✅ **Thành công** (lần 1 sau khi hết hạn)
3. Muốn mua tiếp → ❌ **Bị chặn**
4. Phải gia hạn Premium → ✅ Được mua tiếp

## API Response

### Success Response
```json
{
  "success": true,
  "data": {
    "payment_id": "...",
    "order_invoice_number": "WA-1234567890-abc",
    "checkout_url": "https://pay.sepay.vn/...",
    "form_fields": { ... },
    "amount": 50000,
    "points": 50
  }
}
```

### Error Response (403 Forbidden)
```json
{
  "error": "Bạn đã mua điểm 1 lần. Vui lòng nâng cấp lên gói Premium, Pro hoặc VIP để tiếp tục sử dụng và mua thêm điểm.",
  "code": 403
}
```

## Frontend Handling

### Check Before Purchase
```javascript
async function handleBuyPoints(points) {
  try {
    const response = await fetch('/api/v1/payments/checkout/points', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${firebaseToken}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ points })
    });

    if (!response.ok) {
      const error = await response.json();

      if (response.status === 403) {
        // Show upgrade prompt
        showUpgradeDialog(error.error);
        return;
      }

      throw new Error(error.error);
    }

    // Proceed with checkout
    const data = await response.json();
    submitPaymentForm(data.data);

  } catch (error) {
    console.error(error);
  }
}
```

### Upgrade Dialog
```javascript
function showUpgradeDialog(message) {
  alert(message); // Or use better UI

  // Redirect to pricing page
  window.location.href = '/pricing';
}
```

## Monitoring & Analytics

### Key Metrics
1. **FREE users hitting limit**: Track how many users hit 1-purchase limit
2. **Conversion rate**: % of limited users who upgrade
3. **Purchase frequency**: Average purchases per active subscriber
4. **Revenue impact**: Revenue from points vs subscriptions

### Logs to Monitor
```
⚠️  User abc123 (free, expired/free) - Last chance point purchase
✅ User xyz789 has active subscription - Point purchase allowed
```

## Configuration

### Points Packages
```javascript
const POINTS_PRICING = {
    '50': 50000,   // 50 điểm = 50,000 VND
    '100': 95000,  // 100 điểm = 95,000 VND (5% discount)
    '200': 180000  // 200 điểm = 180,000 VND (10% discount)
};
```

### Subscription Plans
- **FREE**: No subscription, 1 point purchase only
- **Premium**: 3 months or 12 months, unlimited points
- **Pro**: 3 months or 12 months, unlimited points
- **VIP**: 3 months or 12 months, unlimited points

## Testing

### Test Cases

**Test 1: Free user first purchase**
```bash
# Expected: Success
POST /api/v1/payments/checkout/points
{"points": "50"}
# Status: 201 Created
```

**Test 2: Free user second purchase**
```bash
# Expected: Forbidden
POST /api/v1/payments/checkout/points
{"points": "50"}
# Status: 403 Forbidden
```

**Test 3: Active subscriber multiple purchases**
```bash
# Expected: All succeed
POST /api/v1/payments/checkout/points (1st time) → 201
POST /api/v1/payments/checkout/points (2nd time) → 201
POST /api/v1/payments/checkout/points (3rd time) → 201
```

**Test 4: Expired subscriber second purchase**
```bash
# After expiry + 1 purchase
POST /api/v1/payments/checkout/points
# Status: 403 Forbidden
```

## Future Enhancements

1. **Grace Period**: Allow 2-3 purchases for expired users before blocking
2. **Point Bundles**: Special promotions for bulk purchases
3. **Referral Points**: Give free points for referring friends
4. **Loyalty Rewards**: Bonus points for long-term subscribers
5. **Admin Override**: Allow admins to reset purchase limits

## Related Documentation

- [POINTS_PURCHASE_API.md](./POINTS_PURCHASE_API.md) - API documentation
- [SUBSCRIPTION_API_FRONTEND_GUIDE.md](./SUBSCRIPTION_API_FRONTEND_GUIDE.md) - Subscription system
- [SEPAY_INTEGRATION_CHECKLIST.md](./SEPAY_INTEGRATION_CHECKLIST.md) - Payment gateway
