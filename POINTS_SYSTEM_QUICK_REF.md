# 🎯 UNIFIED POINTS SYSTEM - QUICK REFERENCE

**Status**: ✅ DEPLOYED
**Date**: Nov 18, 2025
**Test User**: tienhoi.lh@gmail.com (294 points)

---

## ✅ **ĐÃ FIX**

| Issue | Before | After |
|-------|--------|-------|
| Points balance | Hiển thị 0 | ✅ Hiển thị 294 đúng |
| Purchase sách | ❌ "Insufficient balance" | ✅ Mua được |
| Owner earnings | ❌ Không nhận được | ✅ Nhận ngay 80% |
| Data consistency | Split 3 collections | ✅ Unified `user_subscriptions` |

---

## 📊 **POINTS FIELDS (user_subscriptions)**

```javascript
{
  points_remaining: 294,    // Số điểm để mua (AI/Books/Tests)
  points_total: 310,        // Tổng đã nhận (lifetime)
  points_used: 16,          // Tổng đã tiêu (lifetime)
  earnings_points: 0        // ✨ NEW: Doanh thu từ bán (rút được)
}
```

---

## 🧪 **TEST CASES**

### **1. GET Balance**
```bash
GET /api/subscriptions/current
→ points_remaining: 294 ✅
→ earnings_points: 0 ✅
```

### **2. POST Buy Book (10 points)**
```bash
POST /api/books/{book_id}/purchase
Body: { "purchase_type": "one_time" }

✅ Success → new_balance: 284
✅ Buyer: points_remaining = 284, points_used = 26
✅ Owner: earnings_points += 8 (80%)
```

### **3. POST Buy Test (20 points)**
```bash
POST /api/marketplace-transactions/purchase
Body: { "test_id": "xxx" }

✅ Success → new_balance: 274
✅ Creator: earnings_points += 16 (80%)
```

### **4. GET Chapter Preview**
```bash
GET /api/books/{book_id}/chapters/{chapter_id}

Free chapter → full content ✅
Paid chapter (chưa mua) → preview only ✅
Paid chapter (đã mua) → full content ✅
```

---

## 🔧 **FRONTEND FIXES NEEDED**

### **1. Purchase Request (FIXED)**
```typescript
// ❌ OLD (422 error)
{ book_id: "xxx", purchase_type: "one_time" }

// ✅ NEW (working)
{ purchase_type: "one_time" }  // book_id trong URL
```

### **2. Access Config Fields**
```typescript
// ✅ CORRECT (từ API)
download_pdf_points: number
access_type: 'free' | 'paid'

// ❌ WRONG (frontend bug)
pdf_download_points  // Sai tên field
```

### **3. Points Display**
```typescript
// ✅ Show spending balance
<div>Balance: {subscription.points_remaining} points</div>

// ✅ Show earnings (NEW)
<div>Earnings: {subscription.earnings_points} points</div>
```

---

## 💰 **REVENUE SPLIT**

| Item | Price | Creator Gets | Platform |
|------|-------|--------------|----------|
| Book | 10 pts | 8 pts (80%) | 2 pts (20%) |
| Test | 20 pts | 16 pts (80%) | 4 pts (20%) |

Earnings → `user_subscriptions.earnings_points` (withdrawable)

---

## 🚀 **DEPLOYMENT**

```bash
# Deployed to production
ssh root@104.248.147.155 "su - hoile -c 'cd /home/hoile/wordai && ./deploy-compose-with-rollback.sh'"

# Verify
docker exec ai-chatbot-rag python3 /app/test_unified_points_system.py
```

---

## 📝 **CHECKLIST CHO FRONTEND**

- [ ] Số điểm hiển thị đúng (294 không phải 0)
- [ ] Mua sách không bị "Insufficient balance"
- [ ] Balance giảm đúng sau khi mua
- [ ] Access nội dung ngay sau khi mua
- [ ] Preview chapters hoạt động đúng
- [ ] Field `earnings_points` hiển thị (nếu có UI)
- [ ] Purchase request không gửi book_id trong body

---

## ⚡ **QUICK DEBUG**

```bash
# Check user balance
ssh root@104.248.147.155
docker exec ai-chatbot-rag python3 -c "
import sys; sys.path.insert(0, '/app/src')
from src.config.database import get_database
db = get_database()
sub = db.user_subscriptions.find_one({'user_id': '17BeaeikPBQYk8OWeDUkqm0Ov8e2'})
print(f'Balance: {sub[\"points_remaining\"]}')
print(f'Earnings: {sub[\"earnings_points\"]}')
"
```

---

**✅ Ready for testing! Ping me if có issues.**
