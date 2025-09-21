# AI Service Integration Testing Guide

## 🎯 Tổng quan
Guide này hướng dẫn test và triển khai các component đã implement cho Agent8x AI Service integration:

1. **Authentication Middleware** - Xác thực API key
2. **Admin Routes with Auth** - Routes admin với bảo mật  
3. **Webhook Service** - Gửi thông báo đến Backend
4. **Unified Chat Integration** - Tích hợp webhook vào chat

## 🔧 Setup Environment

### 1. Kiểm tra Environment Variables
```bash
# Kiểm tra .env file có đủ variables
cat .env | grep -E "(INTERNAL_API_KEY|WEBHOOK_SECRET|BACKEND_WEBHOOK_URL)"
```

Required variables:
```env
INTERNAL_API_KEY=agent8x-backend-secret-key-2025
WEBHOOK_SECRET=webhook-secret-for-signature
BACKEND_WEBHOOK_URL=https://api.agent8x.io.vn
```

### 2. Start Services
```bash
# Start main API server
python serve.py

# Start trong terminal khác để test
python test_authentication.py
python test_webhook_integration.py
```

## 🧪 Testing Components

### 1. Authentication Middleware Test
```bash
python test_authentication.py
```

Test cases:
- ❌ Admin access without API key → 401 Unauthorized
- ❌ Admin access with invalid API key → 403 Forbidden  
- ✅ Admin access with valid API key → 200 Success
- ❌ Chat without company ID → 400 Bad Request
- ✅ Chat with company ID in header → 200 Success
- ✅ Chat with company ID in body → 200 Success

### 2. Webhook Service Test
```bash
python test_webhook_integration.py
```

Test cases:
- 📡 Webhook connection test
- 🆕 Conversation created event
- 💬 User message event  
- 🤖 Assistant message event
- 🔄 Conversation updated event
- 📄 File processed event

### 3. Manual API Testing

#### Admin Endpoints (cần API key)
```bash
# System status
curl -X GET "http://localhost:8000/admin/system/status" \
  -H "X-API-Key: agent8x-backend-secret-key-2025"

# Companies list  
curl -X GET "http://localhost:8000/admin/companies" \
  -H "X-API-Key: agent8x-backend-secret-key-2025"

# Documents list
curl -X GET "http://localhost:8000/admin/documents" \
  -H "X-API-Key: agent8x-backend-secret-key-2025"
```

#### Chat Endpoints (cần company ID)
```bash
# Chat với company ID trong header
curl -X POST "http://localhost:8000/chat" \
  -H "Content-Type: application/json" \
  -H "X-Company-Id: test-company-123" \
  -d '{
    "message": "Tôi muốn xem menu món chay",
    "session_id": "test-session-001"
  }'

# Chat với company ID trong body
curl -X POST "http://localhost:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Tôi muốn đặt bàn",
    "company_id": "test-company-123", 
    "session_id": "test-session-002"
  }'
```

## 🔍 Monitoring & Debugging

### 1. Check Logs
```bash
# Application logs
tail -f logs/app.log

# Error logs  
tail -f logs/error.log

# Webhook logs
grep "webhook" logs/app.log
```

### 2. Authentication Events
```bash
# Check auth events
grep "AUTH_EVENT" logs/app.log | tail -10

# Failed auth attempts
grep "AUTH_FAILED" logs/app.log
```

### 3. Webhook Delivery Status
```bash
# Webhook success
grep "webhook_delivered" logs/app.log

# Webhook failures
grep "webhook_failed" logs/app.log

# Retry attempts
grep "webhook_retry" logs/app.log
```

## 🚀 Deployment Checklist

### 1. Pre-deployment
- [ ] All tests pass
- [ ] Environment variables configured
- [ ] Backend webhook endpoint ready
- [ ] API keys generated and secured
- [ ] Webhook signatures working

### 2. Production Environment
```env
# Production .env additions
INTERNAL_API_KEY=your-production-api-key
WEBHOOK_SECRET=your-production-webhook-secret  
BACKEND_WEBHOOK_URL=https://your-backend-api.com/webhooks
```

### 3. Security Considerations
- [ ] API keys rotated from test values
- [ ] Webhook signatures verified
- [ ] HTTPS enabled for webhook endpoints
- [ ] Rate limiting configured
- [ ] Monitoring alerts setup

## 🔧 Common Issues & Solutions

### Issue 1: Authentication Failures
```
Error: 401 Unauthorized / 403 Forbidden
```
**Solution:**
- Check API key in request headers
- Verify INTERNAL_API_KEY in .env
- Ensure X-API-Key header format

### Issue 2: Webhook Delivery Failures  
```
Error: webhook_failed - Connection timeout
```
**Solution:**
- Check BACKEND_WEBHOOK_URL accessibility
- Verify webhook endpoint is running
- Check firewall/network settings
- Review retry logic in logs

### Issue 3: Company Access Denied
```
Error: Company access required
```
**Solution:**
- Add X-Company-Id header to requests
- Include company_id in request body
- Verify company exists in system

### Issue 4: Signature Verification Failed
```
Error: Invalid webhook signature
```
**Solution:**
- Check WEBHOOK_SECRET matches backend
- Verify signature generation algorithm
- Ensure payload format consistency

## 📊 Performance Monitoring

### Key Metrics to Track
- Authentication success/failure rates
- Webhook delivery success rates  
- Response times for protected endpoints
- Retry attempts and patterns
- Conversation tracking accuracy

### Monitoring Commands
```bash
# Auth success rate (last hour)
grep "AUTH_SUCCESS" logs/app.log | grep "$(date +%Y-%m-%d\ %H)" | wc -l

# Webhook delivery rate  
grep "webhook_delivered" logs/app.log | tail -100 | wc -l

# Average response time
grep "response_time" logs/app.log | awk '{sum+=$NF; n++} END {print sum/n}'
```

## 🎉 Integration Complete!

Sau khi complete tất cả tests:

1. **Authentication System** ✅ - API key verification working
2. **Admin Security** ✅ - All admin routes protected  
3. **Webhook Notifications** ✅ - Events sent to Backend
4. **Chat Integration** ✅ - Company-based access control
5. **Conversation Tracking** ✅ - Full lifecycle webhooks

Hệ thống đã sẵn sàng để integrate với Agent8x Backend API!
