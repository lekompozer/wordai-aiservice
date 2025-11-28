# Deploy Payment Service - Quick Guide

## Bước 1: SSH lên server production

```bash
ssh root@ai.wordai.pro
# hoặc ssh vào server IP của bạn
```

## Bước 2: Pull code mới nhất

```bash
cd /root/wordai-aiservice
git pull origin main
```

## Bước 3: Kiểm tra container hiện tại

```bash
# Xem payment service đang chạy
docker-compose ps payment-service

# Xem logs hiện tại
docker logs payment-service --tail 50
```

## Bước 4: Deploy payment service

```bash
# Chạy script deploy
./deploy-payment-service.sh
```

Script sẽ tự động:
- ✅ Build image mới từ code
- ✅ Tag với commit hash và latest
- ✅ Push lên Docker Hub
- ✅ Stop container cũ
- ✅ Start container mới
- ✅ Kiểm tra health check
- ✅ Rollback tự động nếu có lỗi

## Bước 5: Verify deployment

```bash
# Kiểm tra container đang chạy
docker ps | grep payment-service

# Kiểm tra logs
docker logs payment-service --tail 100 -f

# Test health endpoint
curl http://localhost:3000/health

# Test qua NGINX (từ bên ngoài)
curl https://ai.wordai.pro/api/v1/health
```

## Bước 6: Test points purchase flow

### Test checkout endpoint:
```bash
# Lấy Firebase token từ frontend
TOKEN="your_firebase_token"

# Tạo checkout 50 points
curl -X POST https://ai.wordai.pro/api/v1/checkout/points \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"points": "50"}'
```

Response sẽ có `payment_url` để redirect user đến SePay.

### Monitor webhook:
```bash
# Theo dõi logs khi webhook đến từ SePay
docker logs payment-service -f | grep webhook
```

### Check points được cộng:
```bash
# SSH vào MongoDB và kiểm tra
docker exec -it mongodb mongosh
use ai_service_db
db.subscriptions.findOne({user_id: "user_firebase_uid"})
```

## Troubleshooting

### Container không start được:

```bash
# Xem logs chi tiết
docker logs payment-service

# Xem docker-compose logs
docker-compose logs payment-service

# Restart lại
docker-compose restart payment-service
```

### Health check failed:

```bash
# Kiểm tra port 3000 có listening không
docker exec payment-service netstat -tuln | grep 3000

# Test từ trong container
docker exec payment-service curl http://localhost:3000/health
```

### Webhook không nhận được:

```bash
# Kiểm tra NGINX proxy
docker logs nginx-gateway | grep webhook

# Test webhook endpoint
curl -X POST https://ai.wordai.pro/api/v1/webhook/sepay \
  -H "Content-Type: application/json" \
  -d '{"test": "data"}'
```

### Rollback nếu cần:

```bash
# Xem images có sẵn
docker images lekompozer/wordai-payment-service

# Rollback về commit cũ
docker-compose stop payment-service
docker-compose rm -f payment-service

# Sửa docker-compose.yml để dùng image cũ
# Ví dụ: image: lekompozer/wordai-payment-service:abc123

docker-compose up -d payment-service
```

## Environment Variables cần kiểm tra

Trước khi deploy, đảm bảo các biến này đã được set trong `.env`:

```bash
# SePay
SEPAY_API_MERCHANT_ID=your_merchant_id
SEPAY_SECRET_KEY=your_secret_key

# Service Secret (để payment service gọi Python service)
SERVICE_SECRET=your_service_secret

# Webhook
WEBHOOK_URL=https://ai.wordai.pro/api/v1/webhooks/sepay
WEBHOOK_SECRET=your_webhook_secret

# MongoDB
MONGODB_URI=mongodb://user:pass@mongodb:27017
```

Kiểm tra:
```bash
cat .env | grep -E "SEPAY|SERVICE_SECRET|WEBHOOK"
```

## One-liner Deploy Command

Nếu bạn muốn deploy nhanh (từ local):

```bash
ssh root@ai.wordai.pro "cd /root/wordai-aiservice && git pull origin main && ./deploy-payment-service.sh"
```

## Success Indicators

Deploy thành công khi thấy:
- ✅ `Health check passed!`
- ✅ Container status: `Up` (không restart liên tục)
- ✅ Logs không có error
- ✅ `curl http://localhost:3000/health` returns 200

## Các file đã thay đổi trong commit này:

1. **payment-service/src/controllers/paymentController.js**
   - Thêm `POINTS_PRICING` và `createPointsPurchase()`

2. **payment-service/src/routes/paymentRoutes.js**
   - Thêm route `POST /checkout/points`

3. **payment-service/src/middleware/validation.js**
   - Thêm validation cho points purchase

4. **payment-service/src/controllers/webhookController.js**
   - Thêm xử lý webhook cho points purchase

5. **src/api/payment_activation_routes.py**
   - Thêm endpoint `POST /api/v1/points/add`

6. **deploy-payment-service.sh** (NEW)
   - Script deploy riêng cho payment service

7. **POINTS_PURCHASE_API.md** (NEW)
   - Documentation đầy đủ

🚀 Happy deploying!
