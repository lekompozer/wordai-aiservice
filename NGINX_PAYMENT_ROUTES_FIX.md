# NGINX Payment Routes Fix

## ⚠️ UPDATE: Frontend Domain Correction

**QUAN TRỌNG:** Frontend đang ở domain `https://wordai.pro/` chứ KHÔNG phải `https://ai.wordai.pro/`

- **Backend API:** `https://ai.wordai.pro/api/...`
- **Frontend:** `https://wordai.pro/`

**Đã fix:** Payment service callback URLs đã được sửa từ `ai.wordai.pro` → `wordai.pro`

---

## Vấn Đề

SePay sẽ redirect về các URL frontend nhưng có 2 vấn đề:

1. ~~Payment service đang dùng sai domain (`ai.wordai.pro` thay vì `wordai.pro`)~~ ✅ ĐÃ FIX
2. Cần đảm bảo frontend `wordai.pro` có các payment callback pages

## URLs Sau Khi Fix

```
✅ Success: https://wordai.pro/payment/success?order=WA-xxx
❌ Error:   https://wordai.pro/payment/error?order=WA-xxx&message=xxx
🚫 Cancel:  https://wordai.pro/payment/cancel?order=WA-xxx
⏳ Pending: https://wordai.pro/payment/pending?order=WA-xxx
```

## ✅ Đã Fix trong Backend

**Files đã sửa:**
1. `payment-service/src/controllers/paymentController.js` - Checkout callback URLs
2. `payment-service/src/controllers/webhookController.js` - Return URL redirects

**Changes:**
```diff
- success_url: `https://ai.wordai.pro/payment/success`
+ success_url: `https://wordai.pro/payment/success`

- error_url: `https://ai.wordai.pro/payment/error`
+ error_url: `https://wordai.pro/payment/error`

- cancel_url: `https://ai.wordai.pro/payment/cancel`
+ cancel_url: `https://wordai.pro/payment/cancel`
```

## 📋 Frontend Tasks (wordai.pro)

Frontend team cần tạo các pages sau trong `wordai.pro`:

## 📋 Frontend Tasks (wordai.pro)

Frontend team cần tạo các pages sau trong `wordai.pro`:

### 1. Success Page
**Path:** `/payment/success`
- Query params: `?order=WA-xxx`
- Call API: `GET https://ai.wordai.pro/api/v1/payments/status/:order`
- Hiển thị: Thông tin plan, amount, status
- Action: Redirect về dashboard sau 3 giây

### 2. Error Page
**Path:** `/payment/error`
- Query params: `?order=WA-xxx&message=xxx`
- Hiển thị: Error message
- Action: Button "Thử lại" → Pricing page

### 3. Cancel Page
**Path:** `/payment/cancel`
- Query params: `?order=WA-xxx`
- Hiển thị: "Bạn đã hủy thanh toán"
- Action: Redirect về pricing page

### 4. Pending Page (Optional)
**Path:** `/payment/pending`
- Query params: `?order=WA-xxx`
- Hiển thị: "Đang xử lý thanh toán..."
- Action: Poll status API every 3s

## Deploy Backend Changes

```bash
# Commit changes
git add payment-service/
git commit -m "fix: Update payment callback URLs from ai.wordai.pro to wordai.pro"
git push

# SSH to server and deploy
ssh root@104.248.147.155 "su - hoile -c 'cd /home/hoile/wordai && git pull && docker compose build payment-service && docker compose up -d payment-service'"

# Verify
docker logs payment-service --tail 20
```

## ~~NGINX Configuration~~ (KHÔNG CẦN)

**KHÔNG CẦN sửa NGINX** vì:
- Frontend `wordai.pro` là domain riêng (không qua NGINX của backend)
- Backend `ai.wordai.pro` chỉ serve API
- SePay sẽ redirect trực tiếp về `wordai.pro/payment/*` (frontend domain)

Frontend `wordai.pro` tự handle các routes `/payment/*` của mình.

## Checklist

- [ ] Xác định frontend architecture (Next.js server, static, hay separate domain)
- [ ] Thêm location block `/payment/` vào NGINX config
- [ ] Đảm bảo block này đặt TRƯỚC Python backend routes
- [ ] Test NGINX config: `nginx -t`
- [ ] Reload NGINX: `nginx -s reload`
- [ ] Test URL: `curl https://ai.wordai.pro/payment/success`
- [ ] Verify không còn 404 error
- [ ] Frontend team tạo payment callback pages
- [ ] Test full payment flow end-to-end

---

**Created:** November 5, 2025
**Priority:** HIGH - Blocks payment integration testing
