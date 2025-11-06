# SePay Production Configuration Guide

## ✅ Changes Completed (November 6, 2025)

### 1. Fixed Sandbox URL Issue

**Problem:** Frontend was showing sandbox payment URL instead of production URL.

**Root Cause:**
- Payment service (Node.js) was using default sandbox URLs
- No `.env` file existed with production configuration

**Solutions Applied:**

#### A. Created `.env` File on Production Server
Location: `/home/hoile/wordai/payment-service/.env`

```bash
SEPAY_SANDBOX=false
SEPAY_CHECKOUT_URL=https://pay.sepay.vn/v1/checkout/init
SEPAY_API_URL=https://pgapi.sepay.vn
```

#### B. Updated Default URLs in Code
File: `payment-service/src/config/index.js` (Line 18-20)

```javascript
// BEFORE (Sandbox)
checkoutUrl: process.env.SEPAY_CHECKOUT_URL || 'https://pay-sandbox.sepay.vn/v1/checkout/init',
apiUrl: process.env.SEPAY_API_URL || 'https://pgapi-sandbox.sepay.vn',

// AFTER (Production)
checkoutUrl: process.env.SEPAY_CHECKOUT_URL || 'https://pay.sepay.vn/v1/checkout/init',
apiUrl: process.env.SEPAY_API_URL || 'https://pgapi.sepay.vn',
```

### 2. Deployment Status

- ✅ Code committed: `d4f8719`
- ✅ Pushed to GitHub
- ✅ Deployed to production server
- ✅ Payment service logs confirm: `🏦 SePay Sandbox: DISABLED`

## 🔑 Next Steps: Add Real SePay Credentials

Currently, the system is using placeholder credentials. To enable actual payments, you need to:

### 1. Get SePay Merchant Account
- Register at: https://merchant.sepay.vn/
- Complete merchant verification
- Get your credentials:
  - **Merchant ID** (SEPAY_API_MERCHANT_ID)
  - **Secret Key** (SEPAY_SECRET_KEY)

### 2. Update Production Configuration

SSH into production server and update the `.env` file:

```bash
ssh root@104.248.147.155
nano /home/hoile/wordai/payment-service/.env
```

Replace these lines:
```bash
# Current (Placeholders)
SEPAY_API_MERCHANT_ID=your_merchant_id_here
SEPAY_SECRET_KEY=your_secret_key_here

# Update with real values from SePay dashboard
SEPAY_API_MERCHANT_ID=ABC123456789
SEPAY_SECRET_KEY=sk_live_xxxxxxxxxxxxxxxxxxxxx
```

### 3. Restart Payment Service

```bash
# Option A: Restart just payment service
docker restart payment-service

# Option B: Full redeploy
su - hoile
cd /home/hoile/wordai
bash deploy-compose-with-rollback.sh
```

### 4. Verify Configuration

```bash
# Check logs for successful SePay connection
docker logs payment-service | grep -i sepay

# Should show:
# ✅ SePay Configuration loaded
# 🏦 SePay Sandbox: DISABLED
# ✓ Merchant ID: ABC123456789 (first 6 chars)
```

## 🧪 Testing Payment Flow

### Before Going Live

Test the complete payment flow:

1. **Create Test Payment**
   - User clicks "Upgrade" button
   - System should redirect to: `https://pay.sepay.vn/v1/checkout/init?...`
   - URL should **NOT** contain "sandbox"

2. **Complete Test Transaction**
   - Use SePay's test card numbers (if available)
   - Or use real payment with small amount (10,000 VND)

3. **Verify Webhook**
   - Payment service should receive IPN callback
   - Check logs: `docker logs payment-service | grep IPN`
   - Subscription should activate automatically

4. **Verify Database**
   ```bash
   # Check payment record
   docker exec mongodb mongosh -u admin -p WordAIMongoRootPassword --authenticationDatabase admin
   use ai_service_db
   db.payments.find().sort({created_at: -1}).limit(1).pretty()

   # Check subscription activated
   db.user_subscriptions.find({user_id: "test_user_id"}).pretty()
   ```

## 📊 Production URLs

| Environment | Checkout URL | API URL |
|-------------|-------------|---------|
| **Sandbox** | https://pay-sandbox.sepay.vn/v1/checkout/init | https://pgapi-sandbox.sepay.vn |
| **Production** ✅ | https://pay.sepay.vn/v1/checkout/init | https://pgapi.sepay.vn |

## 🔍 Troubleshooting

### Issue: Still seeing sandbox URL
**Solution:** Clear browser cache or check frontend code for hardcoded URLs

### Issue: Payment fails with authentication error
**Solution:** Verify SEPAY_SECRET_KEY matches value in merchant dashboard

### Issue: Webhook not receiving callbacks
**Solution:**
1. Check webhook URL is whitelisted in SePay dashboard
2. Verify nginx routing to payment-service:3000
3. Check SSL certificate is valid

### Issue: Subscription not activating after payment
**Solution:**
1. Check payment-service logs: `docker logs payment-service -f`
2. Verify Python service connection: `docker logs ai-chatbot-rag | grep payment`
3. Check MongoDB for payment record status

## 📝 Configuration Files Location

```
wordai-aiservice/
├── payment-service/
│   ├── .env                          # ✅ Created (not in git)
│   ├── .env.example                  # Template
│   └── src/
│       └── config/
│           └── index.js              # ✅ Updated (default URLs)
├── docker-compose.yml                # Service definitions
└── SEPAY_PRODUCTION_SETUP.md        # This file
```

## ⚠️ Security Notes

1. **Never commit `.env` file** - Contains sensitive credentials
2. **Rotate keys regularly** - Update SEPAY_SECRET_KEY every 3-6 months
3. **Monitor webhook logs** - Watch for suspicious activity
4. **Use HTTPS only** - All payment URLs must use SSL

## 🎯 Current Status Summary

| Component | Status | Notes |
|-----------|--------|-------|
| Sandbox Mode | ✅ Disabled | `SEPAY_SANDBOX=false` |
| Production URLs | ✅ Active | Default fallback updated |
| .env File | ✅ Created | On server (not in git) |
| Real Credentials | ⏳ Pending | Need to add from SePay dashboard |
| Payment Testing | ⏳ Ready | Awaiting real credentials |

## 📞 Support

- **SePay Support:** https://sepay.vn/support
- **SePay Documentation:** https://docs.sepay.vn/
- **Merchant Dashboard:** https://merchant.sepay.vn/

---

**Last Updated:** November 6, 2025
**Deployed Version:** `d4f8719`
**Environment:** Production (ai.wordai.pro)
