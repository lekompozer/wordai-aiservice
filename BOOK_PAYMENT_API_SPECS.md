# Book Payment API - Technical Specifications

**Version:** 1.0
**Last Updated:** February 3, 2026
**Feature:** QR Payment System for Book Purchases (Phase 1)
**Status:** ✅ Implementation Complete

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [API Endpoints](#api-endpoints)
4. [Data Models](#data-models)
5. [Payment Flow](#payment-flow)
6. [Webhook Integration](#webhook-integration)
7. [Error Handling](#error-handling)
8. [Security](#security)
9. [Database Schema](#database-schema)
10. [Testing Guide](#testing-guide)

---

## 1. Overview

### Purpose
Enable direct book purchases via SePay bank transfers, bypassing the points system.
Uses the same payment flow as subscription purchases.

### Key Features
- SePay integration (same as subscription payments)
- Real-time payment confirmation via webhook
- Automatic access granting
- Revenue split: 80% owner, 20% platform
- 24-hour order expiration
- Same trusted payment gateway as subscriptions

### Payment Methods
- **POINTS** - Existing system (buy points → purchase book)
- **SEPAY_BANK_TRANSFER** - New system (SePay → direct payment → purchase book)

---

## 2. Architecture

### System Components

```
┌─────────────────┐
│   Frontend      │
│  (ai.wordai.pro)│
└────────┬────────┘
         │
         │ 1. Create Order (Python)
         ▼
┌─────────────────────────────┐
│  Python FastAPI Service     │
│  (Book Payment Routes)      │
│  - Create order record      │
│  - Return order_id          │
└────────────┬────────────────┘
             │
             │ 2. Return order_id
             ▼
         ┌────────┐
         │Frontend│ ──► 3. Call Payment Service
         └───┬────┘
             │
             │ 4. Create SePay Checkout
             ▼
┌─────────────────────────────┐
│  Node.js Payment Service    │
│  - Create SePay checkout    │
│  - Redirect to SePay page   │
└────────────┬────────────────┘
             │
             │ 5. Redirect to SePay
             ▼
         ┌────────┐
         │  User  │ ──► 6. Pay via SePay
         └───┬────┘
             │
             │ 7. SePay IPN Webhook
             ▼
┌─────────────────────────────┐
│  Node.js Payment Service    │
│  (Webhook Handler)          │
│  - Detect BOOK- prefix      │
│  - Update order status      │
└────────────┬────────────────┘
             │
             │ 8. Call grant-access endpoint
             ▼
┌─────────────────────────────┐
│  Python FastAPI Service     │
│  (Grant Access)             │
│  - Create book_purchases    │
│  - Update book stats        │
│  - Credit owner earnings    │
└─────────────────────────────┘
```

### Technology Stack
- **Python FastAPI:** Book payment routes, order management
- **Node.js Express:** Payment service, SePay integration, webhook handler
- **MongoDB:** Order storage, purchase records
- **SePay:** Payment gateway (same as subscriptions)

---

## 3. API Endpoints

### Base URL
```
Production: https://api.wordai.pro/api/v1/books
Development: http://localhost:8000/api/v1/books
```

---

### 3.1 Create Payment Order

**POST** `/{book_id}/create-payment-order`

Creates a new payment order record. Frontend then calls payment-service to create SePay checkout.

#### Authentication
- **Required:** Yes (Firebase JWT)
- **Header:** `Authorization: Bearer {token}`

#### Request Body
```json
{
  "purchase_type": "forever"
}
```

#### Parameters

| Field | Type | Required | Values | Description |
|-------|------|----------|--------|-------------|
| `purchase_type` | string | Yes | `one_time`, `forever`, `pdf_download` | Type of access to purchase |

#### Response (200 OK)
```json
{
  "success": true,
  "order_id": "BOOK-1738567890-abcd1234",
  "book_id": "book_abc123",
  "book_title": "Guide to Python Programming",
  "purchase_type": "forever",
  "price_vnd": 99000,
  "currency": "VND",
  "payment_method": "SEPAY_BANK_TRANSFER",
  "message": "Order created. Call payment-service to create SePay checkout."
}
```

**Next Step:** Frontend calls payment-service with `order_id` to create SePay checkout URL

#### Price Calculation (Dynamic)

**IMPORTANT:** Price is calculated dynamically from book's `access_config`:

```javascript
// Example: Book's access_config
{
  "one_time_view_points": 50,     // 50 points → 50,000 VND
  "forever_view_points": 99,      // 99 points → 99,000 VND
  "pdf_download_points": 20       // 20 points → 20,000 VND
}

// Conversion formula: 1 point = 1,000 VND
price_vnd = price_points * 1000
```

**Example scenarios:**
- Owner updates `forever_view_points` from 99 → 149 points
- Next payment will charge **149,000 VND** (not 99,000 VND)
- Price is fetched fresh from database on every order creation

**This ensures:**
- ✅ Price changes take effect immediately
- ✅ No cache issues with outdated prices
- ✅ Owner has full control over pricing

#### Error Responses

| Status Code | Error | Description |
|-------------|-------|-------------|
| 400 | `Book not published` | Book is not public (unless owner) |
| 400 | `Purchase type not enabled` | Book doesn't support this purchase type (price = 0) |
| 400 | `Book does not have pricing configured` | access_config missing |
| 404 | `Book not found` | Invalid book_id |

---

### 3.2 Get Order Status

**GET** `/orders/{order_id}`

Check payment status and access grant status.

#### Authentication
- **Required:** Yes (must be order owner)

#### Response (200 OK)
```json
{
  "order_id": "BOOK-1738567890-abcd1234",
  "book_id": "book_abc123",
  "purchase_type": "forever",
  "status": "completed",
  "price_vnd": 99000,
  "transaction_id": "TXN123456789",
  "paid_at": "2026-02-03T10:15:30Z",
  "access_granted": true,
  "book_purchase_id": "purchase_1234abcd5678efgh",
  "created_at": "2026-02-03T10:00:00Z",
  "updated_at": "2026-02-03T10:16:00Z",
  "expires_at": "2026-02-03T10:30:00Z"
}
```

#### Order Status Values

| Status | Description |
|--------|-------------|
| `pending` | Order created, waiting for payment |
| `processing` | Payment received, granting access |
| `completed` | Payment confirmed, access granted |
| `failed` | Payment failed or access grant error |
| `expired` | Order expired (30 minutes) |
| `cancelled` | Order cancelled by user |

#### Error Responses

| Status Code | Error | Description |
|-------------|-------|-------------|
| 403 | `Not authorized` | User is not the order owner |
| 404 | `Order not found` | Invalid order_id |

---

### 3.3 Grant Access from Order (Internal)

**POST** `/grant-access-from-order`

**INTERNAL ENDPOINT** - Called by payment service after webhook confirmation.

#### Authentication
- **Required:** No (server-to-server)
- **Header:** `X-Service-Secret: {secret_key}`

#### Request Body
```json
{
  "order_id": "BOOK-1738567890-abcd1234"
}
```

#### Response (200 OK)
```json
{
  "success": true,
  "message": "Access granted successfully",
  "order_id": "BOOK-1738567890-abcd1234",
  "purchase_id": "purchase_1234abcd5678efgh",
  "user_id": "user_xyz789",
  "book_id": "book_abc123"
}
```

#### Business Logic
1. Verify order status is `completed`
2. Create `book_purchases` record (same as point purchase)
3. Update book stats:
   - Convert VND to points (1000 VND = 1 point)
   - Calculate 80/20 revenue split
   - Increment purchase type counters
   - Track cash revenue separately
4. Credit owner earnings (80% as points)
5. Mark order as `access_granted: true`

#### Error Responses

| Status Code | Error | Description |
|-------------|-------|-------------|
| 400 | `Order not completed` | Order status is not 'completed' |
| 404 | `Order not found` | Invalid order_id |

---

### 3.4 List My Cash Orders

**GET** `/me/cash-orders`

Get all QR payment orders created by current user.

#### Authentication
- **Required:** Yes

#### Query Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `page` | integer | 1 | Page number |
| `limit` | integer | 20 | Items per page (max: 100) |

#### Response (200 OK)
```json
{
  "total": 5,
  "orders": [
    {
      "order_id": "BOOK-1738567890-abcd1234",
      "book_id": "book_abc123",
      "book_title": "Guide to Python Programming",
      "purchase_type": "forever",
      "price_vnd": 99000,
      "status": "completed",
      "access_granted": true,
      "created_at": "2026-02-03T10:00:00Z",
      "expires_at": "2026-02-03T10:30:00Z"
    }
  ],
  "page": 1,
  "limit": 20
}
```

---

### 3.5 Admin Confirm Order (Manual)

**POST** `/admin/orders/{order_id}/confirm`

Manually confirm payment when webhook fails or for bank transfers without API.

#### Authentication
- **Required:** Yes (Admin role)

#### Request Body
```json
{
  "transaction_id": "MANUAL-TXN123456"
}
```

#### Response (200 OK)
```json
{
  "success": true,
  "message": "Access granted successfully",
  "order_id": "BOOK-1738567890-abcd1234",
  "purchase_id": "purchase_1234abcd5678efgh",
  "user_id": "user_xyz789",
  "book_id": "book_abc123"
}
```

---

## 4. Data Models

### CreateQROrderRequest
```typescript
{
  purchase_type: "one_time" | "forever" | "pdf_download"
}
```

### QROrderResponse
```typescript
{
  order_id: string,              // Format: BOOK-{timestamp}-{user_short}
  book_id: string,
  book_title: string,
  purchase_type: string,
  price_vnd: number,
  currency: "VND",
  qr_code_url: string,           // Base64 PNG image
  qr_code_data: string,          // Raw QR code data
  bank_account: {
    bank_name: string,
    account_number: string,
    account_name: string,
    transfer_content: string,    // REQUIRED for matching
    branch_name: string
  },
  status: string,
  expires_at: string,            // ISO 8601 datetime
  created_at: string
}
```

### OrderStatusResponse
```typescript
{
  order_id: string,
  book_id: string,
  purchase_type: string,
  status: string,
  price_vnd: number,
  transaction_id?: string,
  paid_at?: string,
  access_granted: boolean,
  book_purchase_id?: string,
  created_at: string,
  updated_at: string,
  expires_at: string
}
```

---

## 5. Payment Flow

### 5.1 Complete Flow Diagram (SePay Integration)

```
┌────────┐
│ User   │
└───┬────┘
    │
    │ 1. POST /{book_id}/create-payment-order
    ▼
┌─────────────────────────────────────────┐
│ Python: Create Order                    │
│ - Get book price (points → VND)         │
│ - Generate unique order_id              │
│ - Save to book_cash_orders collection   │
│ - Return order_id                       │
└───────┬─────────────────────────────────┘
        │
        │ order_id + book info
        ▼
    ┌────────┐
    │Frontend│ Calls payment-service
    └───┬────┘
        │
        │ 2. POST /payment/create-book-checkout
        ▼
┌─────────────────────────────────────────┐
│ Node.js: Create SePay Checkout          │
│ - Verify order exists                   │
│ - Create SePay checkout session         │
│ - Return payment_url                    │
└───────┬─────────────────────────────────┘
        │
        │ payment_url (SePay page)
        ▼
    ┌────────┐
    │ User   │ Redirected to SePay
    └───┬────┘
        │
        │ 3. Complete payment on SePay
        ▼
    ┌─────────┐
    │  SePay  │ Process payment
    └───┬─────┘
        │
        │ 4. IPN (Instant Payment Notification)
        ▼
┌─────────────────────────────────────────┐
│ Node.js: Webhook Handler                │
│ - Detect order_id starts with "BOOK-"   │
│ - Verify payment in book_cash_orders    │
│ - Update status to 'completed'          │
│ - Save transaction_id and paid_at       │
└───────┬─────────────────────────────────┘
        │
        │ 5. Call grant-access endpoint
        ▼
┌─────────────────────────────────────────┐
│ Python: Grant Access                    │
│ - Verify order is completed             │
│ - Create book_purchases record          │
│ - Update book stats (revenue, counts)   │
│ - Credit owner 80% earnings             │
│ - Mark access_granted = true            │
└───────┬─────────────────────────────────┘
        │
        │ User can now access book
        ▼
    ┌────────┐
    │ Success │
    └────────┘
```

### 5.2 Frontend Implementation Pattern

**Step 1: Create Order**
```javascript
// Call Python API to create order record
const response = await fetch(`/api/v1/books/${bookId}/create-payment-order`, {
  method: 'POST',
  headers: { 'Authorization': `Bearer ${token}` },
  body: JSON.stringify({ purchase_type: 'forever' })
});

const { order_id, price_vnd } = await response.json();
```

**Step 2: Create SePay Checkout**
```javascript
// Call payment-service to create SePay checkout
const paymentResponse = await fetch('/payment/create-book-checkout', {
  method: 'POST',
  headers: { 'Authorization': `Bearer ${token}` },
  body: JSON.stringify({ order_id })
});

const { payment_url } = await paymentResponse.json();
```

**Step 3: Redirect to SePay**
```javascript
// Redirect user to SePay payment page
window.location.href = payment_url;
```

**Step 4: Poll for Status** (after redirect back)
```javascript
// After user completes payment and redirects back
const pollInterval = setInterval(async () => {
  const status = await fetch(`/api/v1/books/orders/${order_id}`, {
    headers: { 'Authorization': `Bearer ${token}` }
  }).then(r => r.json());

  if (status.status === "completed" && status.access_granted) {
    clearInterval(pollInterval);
    showSuccessMessage();
    redirectToBook(status.book_id);
  } else if (status.status === "failed") {
    clearInterval(pollInterval);
    showErrorMessage();
  }
}, 3000); // Poll every 3 seconds

// Stop polling after 5 minutes
setTimeout(() => clearInterval(pollInterval), 5 * 60 * 1000);
```

### 5.3 Payment Service Integration

Payment service needs new endpoint:

**POST** `/payment/create-book-checkout`

```javascript
// payment-service/src/controllers/paymentController.js
async function createBookCheckout(req, res) {
  const { order_id } = req.body;
  const user = req.user; // From Firebase auth

  // 1. Get order from MongoDB
  const order = await db.book_cash_orders.findOne({ order_id });

  if (!order || order.user_id !== user.uid) {
    throw new AppError('Order not found', 404);
  }

  // 2. Create SePay checkout (same as subscription)
  const sepayData = {
    merchant: config.sepay.merchantId,
    order_invoice_number: order_id, // BOOK-{timestamp}-{user_short}
    order_amount: order.price_vnd,
    order_description: `Purchase book: ${order.book_id}`,
    customer_email: user.email,
    // ... other SePay fields
  };

  const signature = generateSignature(sepayData, config.sepay.secretKey);

  // 3. Return payment URL
  return res.json({
    payment_url: `${config.sepay.checkoutUrl}?${queryString}`,
    order_id,
    amount: order.price_vnd
  });
}
```

### 5.4 Key Differences from Subscription Flow

| Aspect | Subscription | Book Payment |
|--------|-------------|--------------|
| Order ID Format | `WA-{timestamp}-{user}` | `BOOK-{timestamp}-{user}` |
| Webhook Detection | Regular payment | Detect `BOOK-` prefix |
| Grant Action | Activate subscription | Grant book access |
| Python Endpoint | `/api/v1/subscriptions/activate` | `/api/v1/books/grant-access-from-order` |
| Expiry | N/A | 24 hours |

**Same Flow:** Both use identical SePay checkout → IPN webhook → Python action pattern
        ▼
┌─────────────────────────────────────────┐
│ Node.js: Webhook Handler                │
│ - Detect order_id starts with "BOOK-"   │
│ - Verify payment in book_cash_orders    │
│ - Update status to 'completed'          │
│ - Save transaction_id and paid_at       │
└───────┬─────────────────────────────────┘
        │
        │ Call grant-access endpoint
        ▼
┌─────────────────────────────────────────┐
│ Python: Grant Access                    │
│ - Verify order is completed             │
│ - Create book_purchases record          │
│ - Update book stats (revenue, counts)   │
│ - Credit owner 80% earnings             │
│ - Mark access_granted = true            │
└───────┬─────────────────────────────────┘
        │
        │ User can now access book
        ▼
    ┌────────┐
    │ Success │
    └────────┘
```

### 5.2 Frontend Polling Pattern

Since this is a bank transfer (not instant like API payments), frontend should poll order status:

```javascript
// After creating order
const response = await createQROrder(bookId, purchaseType);
const orderId = response.order_id;

// Display QR code
displayQRCode(response.qr_code_url, response.bank_account);

// Poll for status every 5 seconds
const pollInterval = setInterval(async () => {
  const status = await getOrderStatus(orderId);

  if (status.status === "completed" && status.access_granted) {
    clearInterval(pollInterval);
    showSuccessMessage();
    redirectToBook(status.book_id);
  } else if (status.status === "expired" || status.status === "failed") {
    clearInterval(pollInterval);
    showErrorMessage();
  }
}, 5000); // Poll every 5 seconds

// Stop polling after order expires (30 minutes)
setTimeout(() => clearInterval(pollInterval), 30 * 60 * 1000);
```

---

## 6. Webhook Integration

### 6.1 SePay IPN Format

SePay sends POST request to webhook URL when payment is completed.

**Webhook URL:** `https://api.wordai.pro/webhook/sepay`

**Payload:**
```json
{
  "timestamp": 1738567890,
  "notification_type": "ORDER_PAID",
  "order": {
    "order_invoice_number": "BOOK-1738567890-abcd1234",
    "amount": 99000,
    "currency": "VND",
    "status": "paid"
  },
  "transaction": {
    "transaction_id": "TXN123456789",
    "bank_code": "VCB",
    "amount": 99000
  },
  "customer": {
    "name": "NGUYEN VAN B",
    "bank_account": "9876543210"
  }
}
```

### 6.2 Webhook Handler Logic

**File:** `payment-service/src/controllers/webhookController.js`

```javascript
// 1. Detect book order by prefix
if (order_invoice_number.startsWith('BOOK-')) {
  return await handleBookOrderWebhook(db, payload, res);
}

// 2. Get order from MongoDB
const bookOrder = await db.book_cash_orders.findOne({ order_id });

// 3. Check notification type
if (notification_type === 'ORDER_PAID') {
  // 4. Update order to completed
  await db.book_cash_orders.updateOne(
    { order_id },
    {
      $set: {
        status: 'completed',
        transaction_id: transaction.transaction_id,
        paid_at: new Date()
      }
    }
  );

  // 5. Call Python service to grant access
  await axios.post(
    `${PYTHON_SERVICE_URL}/api/v1/books/grant-access-from-order`,
    { order_id },
    { headers: { 'X-Service-Secret': SECRET_KEY } }
  );
}

// 6. Always return 200 to SePay
return res.status(200).json({ success: true });
```

### 6.3 Transfer Content Matching

The `transfer_content` field is **REQUIRED** for matching bank transfers to orders.

**Format:** `BOOK {timestamp}`

**Example:** `BOOK 1738567890`

**Why:** Banks include this in transfer description, SePay uses it to match payments.

---

## 7. Error Handling

### 7.1 Error Response Format

All errors follow this structure:

```json
{
  "detail": "Error message description"
}
```

### 7.2 Common Error Scenarios

#### Scenario 1: QR Code Generation Failed
```json
{
  "detail": "Failed to generate QR code: VietQR API timeout"
}
```

**Cause:** VietQR API unavailable
**Solution:** Retry or contact support

#### Scenario 2: Order Already Completed
```json
{
  "detail": "Access already granted"
}
```

**Cause:** Webhook called multiple times (SePay retries)
**Solution:** Idempotent handling - return success

#### Scenario 3: Order Expired
```json
{
  "detail": "Order expired"
}
```

**Cause:** User didn't pay within 30 minutes
**Solution:** Create new order

#### Scenario 4: Access Grant Failed
```json
{
  "detail": "Failed to grant access: Database error"
}
```

**Cause:** MongoDB connection issue
**Solution:** Manual admin confirmation

### 7.3 Retry Logic

- **Webhook:** Payment service always returns 200 to prevent SePay retries
- **Access Grant:** If fails, order stays `completed` but `access_granted = false`
- **Manual Recovery:** Admin can use `/admin/orders/{order_id}/confirm` endpoint

---

## 8. Security

### 8.1 Authentication

| Endpoint | Auth Type | Requirement |
|----------|-----------|-------------|
| `POST /{book_id}/create-qr-order` | Firebase JWT | User must be authenticated |
| `GET /orders/{order_id}` | Firebase JWT | User must own the order |
| `POST /grant-access-from-order` | Service Secret | Internal server-to-server |
| `GET /me/cash-orders` | Firebase JWT | User must be authenticated |
| `POST /admin/orders/{order_id}/confirm` | Firebase JWT + Admin Role | Admin only |

### 8.2 Authorization Checks

**Order Ownership:**
```python
if order["user_id"] != current_user["uid"]:
    raise HTTPException(403, "Not authorized")
```

**Book Publishing Status:**
```python
if not book["community_config"]["is_public"]:
    if book["user_id"] != user_id:
        raise HTTPException(400, "Book not published")
```

### 8.3 Order Expiration

- **TTL:** 30 minutes from `created_at`
- **Implementation:** MongoDB TTL index on `expires_at` field
- **Auto-Delete:** Expired orders are auto-deleted after 7 days (604800 seconds)
- **Status Check:** On status poll, update `status` to `expired` if past `expires_at`

### 8.4 Data Privacy

- **QR Code:** Contains only bank account and amount (no personal data)
- **Transfer Content:** Generic format `BOOK {timestamp}` (no user info)
- **Webhook:** Processed server-side, not exposed to frontend

---

## 9. Database Schema

### 9.1 book_cash_orders Collection

```javascript
{
  _id: ObjectId,
  order_id: String,                    // UNIQUE, format: BOOK-{timestamp}-{user_short}
  user_id: String,                     // Owner of order
  book_id: String,                     // Book being purchased
  purchase_type: String,               // one_time | forever | pdf_download
  price_vnd: Number,                   // Price in VND
  currency: String,                    // "VND"
  payment_method: String,              // "BANK_TRANSFER_QR"
  payment_provider: String,            // "VIETQR"
  qr_code_url: String,                 // Base64 PNG
  qr_code_data: String,                // Raw QR data
  admin_bank_account: {
    bank_name: String,
    account_number: String,
    account_name: String,
    transfer_content: String,          // IMPORTANT: For matching
    branch_name: String
  },
  status: String,                      // pending | processing | completed | failed | expired
  transaction_id: String,              // From bank
  paid_at: Date,                       // When payment confirmed
  confirmed_by: String,                // user_id (for manual confirmation)
  access_granted: Boolean,             // Has access been granted?
  book_purchase_id: String,            // Link to book_purchases record
  user_email: String,
  user_name: String,
  ip_address: String,
  user_agent: String,
  webhook_payload: Object,             // Full IPN payload
  grant_error: String,                 // Error message if grant failed
  grant_error_details: Object,
  expires_at: Date,                    // Order expiry (30 min)
  created_at: Date,
  updated_at: Date
}
```

### 9.2 Indexes

| Index Name | Fields | Type | Purpose |
|------------|--------|------|---------|
| `idx_order_id_unique` | `order_id` | Unique | Primary key |
| `idx_user_status` | `user_id + status` | Compound | User's orders by status |
| `idx_user_created` | `user_id + created_at` | Compound | Pagination |
| `idx_book_status` | `book_id + status` | Compound | Book sales stats |
| `idx_transaction_id` | `transaction_id` | Sparse | Webhook matching |
| `idx_expires_at_ttl` | `expires_at` | TTL (7 days) | Auto-delete expired |
| `idx_created_at` | `created_at` | Single | Admin queries |
| `idx_status_created` | `status + created_at` | Compound | Admin dashboard |
| `idx_transfer_content` | `admin_bank_account.transfer_content` | Single | Webhook matching |

**Create Indexes:**
```bash
python create_book_payment_indexes.py
```

### 9.3 book_purchases Collection (Extended)

**New Fields:**
```javascript
{
  // ... existing fields
  cash_paid_vnd: Number,               // NEW: Amount paid in VND (0 if points)
  order_id: String,                    // NEW: Link to book_cash_orders (if cash)
  payment_method: String               // "POINTS" | "BANK_TRANSFER_QR"
}
```

### 9.4 online_books.stats (Extended)

**New Fields:**
```javascript
{
  stats: {
    // ... existing point-based fields
    cash_revenue_vnd: Number           // NEW: Total cash revenue in VND
  }
}
```

**Note:** Cash purchases are converted to point equivalents for unified stats display:
- Formula: `points_equivalent = cash_paid_vnd / 1000`
- Example: 99,000 VND → 99 points equivalent
- Stats fields updated: `total_revenue_points`, `owner_reward_points`, purchase type counters

### 9.5 user_subscriptions (Extended)

**New Fields:**
```javascript
{
  // ... existing fields
  cash_earnings_vnd: Number            // NEW: Owner's cash earnings in VND
}
```

---

## 10. Testing Guide

### 10.1 Local Testing

**Step 1: Start Services**
```bash
# Terminal 1: MongoDB
docker-compose up mongodb

# Terminal 2: Python service
python -m uvicorn src.app:app --reload --port 8000

# Terminal 3: Payment service
cd payment-service && npm run dev
```

**Step 2: Create Database Indexes**
```bash
python create_book_payment_indexes.py
```

**Step 3: Configure Admin Bank Account**

Edit `development.env`:
```env
ADMIN_BANK_NAME=Vietcombank
ADMIN_ACCOUNT_NUMBER=0123456789
ADMIN_ACCOUNT_NAME=NGUYEN VAN A
ADMIN_BANK_BRANCH=Chi nhánh TP.HCM
```

**Step 4: Test QR Order Creation**
```bash
curl -X POST http://localhost:8000/api/v1/books/{book_id}/create-qr-order \
  -H "Authorization: Bearer {firebase_token}" \
  -H "Content-Type: application/json" \
  -d '{"purchase_type": "forever"}'
```

**Step 5: Simulate Webhook (Manual)**
```bash
curl -X POST http://localhost:3000/webhook/sepay \
  -H "Content-Type: application/json" \
  -d '{
    "notification_type": "ORDER_PAID",
    "order": {
      "order_invoice_number": "BOOK-1738567890-abcd1234"
    },
    "transaction": {
      "transaction_id": "TEST123"
    }
  }'
```

**Step 6: Check Order Status**
```bash
curl http://localhost:8000/api/v1/books/orders/{order_id} \
  -H "Authorization: Bearer {firebase_token}"
```

### 10.2 Production Testing

**Important:** Use TEST book and small amount (1,000 VND) for real bank transfer testing.

1. Create QR order for test book
2. Scan QR with real banking app
3. Transfer exact amount with EXACT transfer content
4. Wait for webhook (usually < 30 seconds)
5. Verify access granted automatically
6. Check book stats updated correctly

### 10.3 Test Cases Checklist

- [ ] Create QR order for `one_time` purchase
- [ ] Create QR order for `forever` purchase
- [ ] Create QR order for `pdf_download` purchase
- [ ] Order expires after 30 minutes
- [ ] QR code displays correctly
- [ ] Bank account info is correct
- [ ] Transfer content is unique per order
- [ ] Webhook updates order to completed
- [ ] Access is granted automatically
- [ ] Book stats updated (revenue, purchase count)
- [ ] Owner earnings credited (80%)
- [ ] Poll status returns correct data
- [ ] List cash orders pagination works
- [ ] Admin manual confirmation works
- [ ] Error handling for invalid book_id
- [ ] Error handling for unpublished book
- [ ] Error handling for disabled purchase type
- [ ] Error handling for VietQR API failure
- [ ] Error handling for webhook retry (idempotent)

---

## Environment Variables

### Python Service (development.env)

```env
# Admin Bank Account for Book QR Payments
ADMIN_BANK_NAME=Vietcombank
ADMIN_ACCOUNT_NUMBER=0123456789
ADMIN_ACCOUNT_NAME=NGUYEN VAN A
ADMIN_BANK_BRANCH=Chi nhánh TP.HCM
```

### Payment Service (.env)

```env
# Python Service Connection
PYTHON_SERVICE_URL=http://localhost:8000
PYTHON_SERVICE_TIMEOUT=30000

# Service-to-Service Auth
X_SERVICE_SECRET=your_secret_key_here
```

---

## Deployment Checklist

- [ ] Create database indexes (`python create_book_payment_indexes.py`)
- [ ] Configure admin bank account in `.env`
- [ ] Register book payment routes in `src/app.py`
- [ ] Update payment service webhook handler
- [ ] Test QR generation locally
- [ ] Test webhook flow with mock data
- [ ] Deploy Python service
- [ ] Deploy payment service
- [ ] Test with real bank transfer (small amount)
- [ ] Monitor logs for webhook reception
- [ ] Verify stats tracking accuracy
- [ ] Update frontend to display QR code
- [ ] Add polling logic for order status
- [ ] Test end-to-end flow on production

---

## Support & Troubleshooting

### Common Issues

**Issue 1: QR Code Not Displaying**
- Check `ADMIN_ACCOUNT_NUMBER` is set
- Verify VietQR API is accessible
- Check Python service logs for errors

**Issue 2: Webhook Not Received**
- Verify SePay webhook URL configuration
- Check payment service is running
- Check firewall allows POST to webhook URL

**Issue 3: Access Not Granted**
- Check order status is `completed`
- Verify `grant-access-from-order` endpoint is accessible
- Check Python service logs for grant errors
- Use admin manual confirmation as fallback

**Issue 4: Stats Not Updated**
- Check revenue split calculation (80/20)
- Verify VND to points conversion (1000:1)
- Check MongoDB update query succeeded
- Inspect `book_cash_orders` collection for grant_error

---

## API Rate Limits

| Endpoint | Limit | Window | Notes |
|----------|-------|--------|-------|
| `create-qr-order` | 5 requests | 1 minute | Per user |
| `get order status` | 30 requests | 1 minute | Polling limit |
| `grant-access` | Unlimited | - | Internal only |
| `list cash orders` | 20 requests | 1 minute | Per user |

---

## Changelog

### Version 1.0 (February 3, 2026)
- ✅ Initial implementation
- ✅ VietQR integration (30 banks)
- ✅ QR order creation endpoint
- ✅ Order status polling endpoint
- ✅ Webhook handler for SePay
- ✅ Automatic access granting
- ✅ Book stats tracking (cash revenue)
- ✅ Owner earnings (80/20 split)
- ✅ Admin manual confirmation
- ✅ Database indexes
- ✅ 30-minute order expiration
- ✅ TTL auto-cleanup (7 days)

### Planned Features (Future Versions)

**Phase 2: Group Purchase**
- Group pricing tiers (1, 5, 10 members)
- Email allocation for members
- Bulk access granting

**Phase 3: Referral System**
- Referral code generation
- Commission tracking (5%)
- Referral stats dashboard

**Phase 4: Admin Dashboard**
- Cash order management
- Revenue analytics
- Payment reconciliation

---

## Contact

**Technical Support:** support@wordai.pro
**API Documentation:** https://api.wordai.pro/docs
**Status Page:** https://status.wordai.pro

---

**Document Version:** 1.0
**Generated:** February 3, 2026
**Repository:** wordai-aiservice
**Branch:** main
