# Frontend Integration Guide - USDT BEP20 Payment System

## 📋 Overview

Tài liệu hướng dẫn frontend tích hợp hệ thống thanh toán USDT BEP20 cho:
- **Subscription Payment**: Thanh toán gói Premium/Pro/VIP
- **Points Purchase**: Mua điểm bằng USDT

**Network:** Binance Smart Chain (BSC) - BEP20
**Token:** USDT (Tether)
**Contract Address:** `0x55d398326f99059fF775485246999027B3197955`

---

## 🎯 User Flow Overview

### Flow 1: Subscription Payment

```
1. User connects wallet (MetaMask/Trust Wallet/WalletConnect)
   → Get user's wallet address
   → Check network = BSC
   → Check USDT balance
2. User chọn gói subscription (Premium/Pro/VIP) và duration (3/12 months)
3. Frontend hiển thị giá (VND + USDT) trước khi thanh toán
4. User click "Pay Now" button
5. Frontend gọi API tạo payment với wallet address → Nhận WordAI wallet address và exact amount
6. Frontend hiển thị payment modal với:
   - QR code cho mobile wallet
   - Copy address button
   - Exact USDT amount (BOLD warning)
   - "Send" button (opens user's wallet app)
7. User send USDT từ wallet
8. User paste transaction hash (optional but recommended)
9. Frontend starts polling status endpoint mỗi 10-15 giây
10. Sau 12 confirmations (~36 giây) → Subscription được activate
11. Hiển thị success message + redirect về dashboard
```

### Flow 2: Points Purchase

```
1. User connects wallet TRƯỚC KHI chọn package
   → Verify BSC network
   → Check USDT balance
2. Frontend hiển thị packages với giá (VND + USDT)
3. User chọn gói points hoặc nhập custom amount
4. User click "Buy with USDT"
5. Frontend gọi API tạo payment với wallet address
6. Frontend hiển thị payment modal (same as subscription)
7. User send USDT
8. User submit transaction hash (optional)
9. Frontend poll status endpoint
10. Sau confirm → Points được credit vào account
11. Hiển thị success + updated points balance
```

### ⚠️ IMPORTANT: Connect Wallet First!

**Frontend PHẢI yêu cầu user connect wallet TRƯỚC KHI:**
- Hiển thị giá USDT
- Cho phép click "Pay" button
- Tạo payment request

**Lý do:**
- Cần wallet address để tạo payment
- Cần check user có đủ USDT balance không
- Cần verify network = BSC
- Better UX: User biết chính xác wallet nào sẽ gửi



---

## 🔌 API Endpoints

### Base URL
```

Development: http://localhost:8000
```

### Authentication
Tất cả endpoints yêu cầu Firebase JWT token:
```
Authorization: Bearer YOUR_FIREBASE_JWT_TOKEN
```

---

## 📡 1. Subscription Payment APIs

### 1.1. Get USDT Exchange Rate

**Endpoint:** `GET /api/v1/payments/usdt/subscription/rate`

**Purpose:** Lấy tỷ giá USDT/VND hiện tại

**Request:**
```http
GET /api/v1/payments/usdt/subscription/rate
Authorization: Bearer {firebase_token}
```

**Response:**
```json
{
  "rate": 22320.0,
  "last_updated": "2025-12-03T10:30:00Z",
  "source": "binance"
}
```

**Usage:**
- Gọi khi user vào trang pricing để hiển thị giá USDT
- Cache trong 5-10 phút
- Hiển thị giá cả VND và USDT song song

---

### 1.2. Get Subscription Packages

**Endpoint:** `GET /api/v1/payments/usdt/subscription/packages`

**Purpose:** Lấy danh sách tất cả các gói subscription với giá USDT

**Request:**
```http
GET /api/v1/payments/usdt/subscription/packages
Authorization: Bearer {firebase_token}
```

**Response:**
```json
[
  {
    "plan": "premium",
    "duration": "3month",
    "price_vnd": 279000,
    "price_usdt": 10.73,
    "discount_percentage": 0.0,
    "points": 300,
    "features": [
      "2GB Storage",
      "300 AI Points (3mo) / 1200 (12mo)",
      "Unlimited AI chats",
      "Create online tests",
      "100 documents & secret files"
    ],
    "is_popular": true
  },
  {
    "plan": "premium",
    "duration": "12month",
    "price_vnd": 990000,
    "price_usdt": 38.08,
    "discount_percentage": 11.0,
    "points": 1200,
    "features": [...],
    "is_popular": true
  },
  // ... more packages for pro, vip
]
```

**Usage:**
- Gọi khi user vào trang pricing/subscription
- Hiển thị tất cả packages với cả giá VND và USDT
- Highlight `is_popular: true` packages
- Hiển thị `discount_percentage` cho các gói 12 tháng

---

### 1.3. Create Subscription Payment

**Endpoint:** `POST /api/v1/payments/usdt/subscription/create`

**Purpose:** Tạo payment request cho subscription

**Request:**
```http
POST /api/v1/payments/usdt/subscription/create
Authorization: Bearer {firebase_token}
Content-Type: application/json

{
  "plan": "premium",           // premium | pro | vip
  "duration": "3_months",       // 3_months | 12_months
  "from_address": "0x742d..."  // REQUIRED: User's wallet address for balance check
}
```

**Response:**
```json
{
  "payment_id": "USDT-1733212800-abc123",
  "order_invoice_number": "WA-USDT-1733212800-abc123",
  "payment_type": "subscription",
  "amount_usdt": 12.5,
  "amount_vnd": 279000,
  "usdt_rate": 22320.0,
  "to_address": "0xbab94f5bf90550c9f0147fffae8a1ef006b85a07",
  "network": "BSC",
  "token_contract": "0x55d398326f99059fF775485246999027B3197955",
  "instructions": "Send exactly 12.5 USDT (BEP20) to the address above...",
  "expires_at": "2025-12-03T11:00:00Z",
  "status": "pending"
}
```

**Frontend Actions:**
1. Lưu `payment_id` vào state/localStorage
2. Hiển thị payment modal với:
   - Wallet address (với copy button)
   - Amount USDT (exact amount)
   - QR code chứa payment info
   - Countdown timer (30 minutes)
3. Hiển thị instructions cho user
4. Cung cấp form để user paste transaction hash

**Error Handling:**

**400 Bad Request - Insufficient Balance:**
```json
{
  "detail": {
    "error": "insufficient_balance",
    "message": "Insufficient USDT balance in your wallet",
    "required_amount": 12.5,
    "current_balance": 8.23,
    "shortage": 4.27,
    "wallet_address": "0x742d..."
  }
}
```

**Frontend should:**
- Display clear error message showing shortage amount
- Show current balance vs required amount
- Suggest user to:
  - Add more USDT to wallet
  - Choose smaller package/plan
  - Use alternative payment method
- Prevent payment creation until balance sufficient

**Other errors:**
- 400: Invalid plan/duration, invalid wallet address, balance too low
- 401: Not authenticated
- 500: Server error or blockchain connection issue

---

### 1.4. Confirm Payment Sent (NEW - Automatic Scanning)

**Endpoint:** `POST /api/v1/payments/usdt/subscription/{payment_id}/confirm-sent`

**Purpose:** User xác nhận đã gửi USDT → Backend tự động scan blockchain tìm transaction

**⚠️ QUAN TRỌNG:** Không cần transaction hash! Backend sẽ tự động scan blockchain.

**Request:**
```http
POST /api/v1/payments/usdt/subscription/USDT-xxx/confirm-sent
Authorization: Bearer {firebase_token}
```

**Response:**
```json
{
  "success": true,
  "message": "Blockchain scanning started. We will automatically detect your transaction.",
  "status": "scanning",
  "scan_info": {
    "max_attempts": 12,
    "interval_seconds": 15,
    "total_duration_minutes": 3
  }
}
```

**Flow:**
1. User click "Tôi đã gửi USDT" → Gọi endpoint này
2. Backend bắt đầu scan blockchain tự động
3. Scan mỗi 15 giây, tối đa 12 lần (3 phút)
4. Tìm transaction từ `from_address` → WordAI wallet với `amount_usdt` chính xác
5. Khi tìm thấy → Tự động verify và confirm

**Frontend Implementation:**
```javascript
async function handleUserConfirmSent(paymentId) {
  try {
    // Call confirm-sent endpoint
    const response = await fetch(
      `/api/v1/payments/usdt/subscription/${paymentId}/confirm-sent`,
      {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${firebaseToken}`,
        }
      }
    );

    const data = await response.json();

    if (data.success) {
      // Show scanning message
      showScanningModal({
        message: 'Đang tìm kiếm giao dịch của bạn trên blockchain...',
        duration: data.scan_info.total_duration_minutes
      });

      // Start polling status
      startStatusPolling(paymentId);
    }
  } catch (error) {
    showError('Không thể bắt đầu quét blockchain: ' + error.message);
  }
}
```

---

### 1.5. Check Payment Status

**Endpoint:** `GET /api/v1/payments/usdt/subscription/{payment_id}/status`

**Purpose:** Kiểm tra trạng thái payment

**Request:**
```http
GET /api/v1/payments/usdt/subscription/USDT-xxx/status
Authorization: Bearer {firebase_token}
```

**Response:**
```json
{
  "payment_id": "USDT-1733212800-abc123",
  "status": "processing",
  "payment_type": "subscription",
  "transaction_hash": "0x1234567890abcdef...",
  "confirmation_count": 8,
  "required_confirmations": 12,
  "amount_usdt": 12.5,
  "from_address": "0x742d35Cc...",
  "created_at": "2025-12-03T10:30:00Z",
  "payment_received_at": "2025-12-03T10:31:00Z",
  "confirmed_at": null,
  "completed_at": null,
  "subscription_id": null,
  "message": "Transaction detected! Confirmations: 8/12"
}
```

**Status Values:**
- `pending`: Chờ user gửi USDT
- `scanning`: Đang scan blockchain tìm transaction (NEW)
- `processing`: Transaction detected, đang chờ confirmations
- `confirmed`: Đủ 12 confirmations, đang activate subscription
- `completed`: Subscription đã activate thành công
- `failed`: Transaction failed hoặc invalid
- `cancelled`: Payment expired hoặc user cancel

**Frontend Polling:**
```javascript
// Poll every 10-15 seconds
const pollInterval = setInterval(async () => {
  const status = await checkPaymentStatus(paymentId);

  if (status.status === 'completed') {
    clearInterval(pollInterval);
    showSuccessMessage();
    redirectToDashboard();
  } else if (status.status === 'failed' || status.status === 'cancelled') {
    clearInterval(pollInterval);
    showErrorMessage(status.message);
  } else if (status.status === 'scanning') {
    showScanningProgress('Đang tìm giao dịch...');
  } else {
    updateProgressBar(status.confirmation_count, status.required_confirmations);
  }
}, 15000); // 15 seconds
```

**UI Updates:**
- `pending`: "Waiting for payment..."
- `processing`: Progress bar showing confirmations (8/12)
- `confirmed`: "Payment confirmed! Activating subscription..."
- `completed`: "Success! Subscription activated ✅"
- `failed`: "Payment failed: {error_message}"

---

### 1.4. Submit Transaction Hash

**Endpoint:** `POST /api/v1/payments/usdt/subscription/{payment_id}/verify`

**Purpose:** User submit transaction hash sau khi send USDT

**Request:**
```http
POST /api/v1/payments/usdt/subscription/USDT-xxx/verify
Authorization: Bearer {firebase_token}
Content-Type: application/json

{
  "payment_id": "USDT-1733212800-abc123",
  "transaction_hash": "0x1234567890abcdef..."
}
```

**Response:**
```json
{
  "message": "Transaction hash registered. Waiting for blockchain confirmations.",
  "transaction_hash": "0x1234567890abcdef...",
  "required_confirmations": 12,
  "estimated_time": "~36 seconds"
}
```

**Frontend Actions:**
1. Hiển thị input field cho transaction hash
2. Validate format (0x... với 66 characters)
3. Submit khi user paste/input
4. Sau submit → chuyển sang polling mode ngay lập tức
5. Hiển thị confirmation progress

---

### 1.5. Confirm Payment Sent (NEW - Automatic Scanning)

**Endpoint:** `POST /api/v1/payments/usdt/subscription/{payment_id}/confirm-sent`

**Purpose:** User xác nhận đã gửi USDT - hệ thống tự động scan blockchain

**⚡ NEW FEATURE:** Không cần transaction hash! Backend sẽ tự động scan blockchain để tìm transaction.

**Request:**
```http
POST /api/v1/payments/usdt/subscription/USDT-xxx/confirm-sent
Authorization: Bearer {firebase_token}
```

**Response:**
```json
{
  "success": true,
  "message": "Blockchain scanning started. We will automatically detect your transaction.",
  "status": "scanning",
  "scan_info": {
    "max_attempts": 12,
    "interval_seconds": 15,
    "total_duration_minutes": 3
  }
}
```

**How it works:**
1. User gửi USDT từ wallet (không cần paste transaction hash)
2. User click "Tôi đã gửi USDT"
3. Frontend gọi endpoint này
4. Backend tự động scan blockchain mỗi 15 giây
5. Scan 12 lần (tổng 3 phút)
6. Tự động tìm transaction với:
   - `from_address`: Wallet của user
   - `to_address`: Wallet của WordAI
   - `amount`: Đúng số tiền cần thanh toán (±1% tolerance)
7. Khi tìm thấy → tự động verify và activate subscription

**Frontend Implementation:**
```javascript
// Option 1: User pastes transaction hash (faster)
if (userProvidedTxHash) {
  await verifyTransaction(paymentId, txHash);
  startPolling(paymentId);
}

// Option 2: User clicks "I sent USDT" (automatic scanning)
else {
  await confirmPaymentSent(paymentId);
  startPolling(paymentId); // Poll every 15s
  showMessage("Đang quét blockchain tìm giao dịch của bạn...");
}
```

**Advantages:**
- ✅ Better UX - không cần user copy/paste transaction hash
- ✅ Giảm lỗi - không lo nhầm lẫn transaction hash
- ✅ Mobile friendly - không cần switch app để copy hash
- ✅ Tự động hoàn toàn - backend tự tìm transaction

**Disadvantages:**
- ⏱️ Chậm hơn một chút (~15-30s delay)
- 🔍 Cần scan blockchain (tốn resource)

**Best Practice:**
- Hiển thị cả 2 options cho user:
  1. "Paste Transaction Hash" (nhanh hơn, cho advanced users)
  2. "Tôi đã gửi USDT" button (dễ hơn, tự động)

---

### 1.6. Get Payment History

**Endpoint:** `GET /api/v1/payments/usdt/subscription/history`

**Purpose:** Lấy lịch sử thanh toán subscription của user

**Request:**
```http
GET /api/v1/payments/usdt/subscription/history?limit=20&skip=0
Authorization: Bearer {firebase_token}
```

**Response:**
```json
{
  "payments": [
    {
      "payment_id": "USDT-1733212800-abc123",
      "plan": "premium",
      "duration": "3_months",
      "amount_usdt": 12.5,
      "status": "completed",
      "created_at": "2025-12-03T10:30:00Z",
      "completed_at": "2025-12-03T10:31:30Z",
      "subscription_id": "sub_xyz789"
    }
  ],
  "count": 1,
  "limit": 20,
  "skip": 0
}
```

---

## 💎 2. Points Purchase APIs

### 2.1. Get Points Packages

**Endpoint:** `GET /api/v1/payments/usdt/points/packages`

**Purpose:** Lấy danh sách gói points với giá

**Request:**
```http
GET /api/v1/payments/usdt/points/packages
Authorization: Bearer {firebase_token}
```

**Response:**
```json
[
  {
    "points": 50,
    "price_vnd": 50000,
    "price_usdt": 2.24,
    "discount_percentage": 0.0,
    "is_popular": false
  },
  {
    "points": 100,
    "price_vnd": 95000,
    "price_usdt": 4.26,
    "discount_percentage": 5.0,
    "is_popular": true
  },
  {
    "points": 200,
    "price_vnd": 180000,
    "price_usdt": 8.06,
    "discount_percentage": 10.0,
    "is_popular": false
  }
]
```

**Frontend Display:**
- Hiển thị dạng cards/buttons
- Highlight `is_popular` package
- Show discount percentage badge
- Allow custom amount (minimum 100 points)

---

### 2.2. Create Points Payment

**Endpoint:** `POST /api/v1/payments/usdt/points/create`

**Purpose:** Tạo payment request cho points

**Request:**
```http
POST /api/v1/payments/usdt/points/create
Authorization: Bearer {firebase_token}
Content-Type: application/json

{
  "points_amount": 100,          // Minimum 100
  "from_address": "0x742d..."   // REQUIRED: User's wallet address for balance check
}
```

**Response:**
```json
{
  "payment_id": "USDT-1733213000-def456",
  "order_invoice_number": "WA-USDT-1733213000-def456",
  "payment_type": "points",
  "amount_usdt": 4.26,
  "amount_vnd": 95000,
  "usdt_rate": 22320.0,
  "to_address": "0xbab94f5bf90550c9f0147fffae8a1ef006b85a07",
  "network": "BSC",
  "token_contract": "0x55d398326f99059fF775485246999027B3197955",
  "instructions": "Send exactly 4.26 USDT (BEP20) to receive 100 points...",
  "expires_at": "2025-12-03T11:00:00Z",
  "status": "pending"
}
```

**Frontend Actions:**
Same as subscription payment:
1. Save payment_id
2. Show payment modal
3. Display wallet address, amount, QR code
4. Provide transaction hash input
5. Start polling after user confirms send

**Error Handling:**

**400 Bad Request - Insufficient Balance:**
```json
{
  "detail": {
    "error": "insufficient_balance",
    "message": "Insufficient USDT balance in your wallet",
    "required_amount": 4.26,
    "current_balance": 2.15,
    "shortage": 2.11,
    "wallet_address": "0x742d..."
  }
}
```

**Frontend should:**
- Display clear error message with shortage amount
- Show "You need 2.11 more USDT" message
- Suggest smaller points package
- Disable "Buy" button until balance sufficient

**Other validation:**
- points_amount >= 50 (minimum)
- Show error if less than minimum
- 400: Invalid wallet address, balance too low
- 401: Not authenticated
- 500: Server error or blockchain connection issue

---

### 2.3. Confirm Payment Sent (NEW - Automatic Scanning)

**Endpoint:** `POST /api/v1/payments/usdt/points/{payment_id}/confirm-sent`

**Purpose:** User xác nhận đã gửi USDT → Backend tự động scan blockchain

**⚠️ QUAN TRỌNG:** Không cần transaction hash! Backend sẽ tự động scan.

**Request:**
```http
POST /api/v1/payments/usdt/points/USDT-xxx/confirm-sent
Authorization: Bearer {firebase_token}
```

**Response:**
```json
{
  "success": true,
  "message": "Blockchain scanning started. We will automatically detect your transaction.",
  "status": "scanning",
  "scan_info": {
    "max_attempts": 12,
    "interval_seconds": 15,
    "total_duration_minutes": 3
  }
}
```

**Usage:** Same as subscription - call after user confirms they sent USDT

---

### 2.4. Check Points Payment Status

**Endpoint:** `GET /api/v1/payments/usdt/points/{payment_id}/status`

**Purpose:** Kiểm tra trạng thái points payment

**Request:**
```http
GET /api/v1/payments/usdt/points/USDT-xxx/status
Authorization: Bearer {firebase_token}
```

**Response:**
```json
{
  "payment_id": "USDT-1733213000-def456",
  "status": "completed",
  "payment_type": "points",
  "transaction_hash": "0xabcdef123456...",
  "confirmation_count": 12,
  "required_confirmations": 12,
  "amount_usdt": 4.26,
  "from_address": "0x742d35Cc...",
  "created_at": "2025-12-03T10:35:00Z",
  "completed_at": "2025-12-03T10:36:00Z",
  "points_transaction_id": "ptx_abc123",
  "message": "Payment completed! 100 points credited to your account!"
}
```

**Status Values:** Same as subscription (pending, scanning, processing, confirmed, completed, failed, cancelled)

**Polling:** Same as subscription (every 10-15 seconds)

---

### 2.5. Submit Transaction Hash (Points) - OPTIONAL

**Endpoint:** `POST /api/v1/payments/usdt/points/{payment_id}/verify`

**Request/Response:** Same structure as subscription verify endpoint

---

### 2.5. Confirm Payment Sent (Points - NEW)

**Endpoint:** `POST /api/v1/payments/usdt/points/{payment_id}/confirm-sent`

**Purpose:** User xác nhận đã gửi USDT - tự động scan blockchain

**Request:**
```http
POST /api/v1/payments/usdt/points/USDT-xxx/confirm-sent
Authorization: Bearer {firebase_token}
```

**Response:**
```json
{
  "success": true,
  "message": "Blockchain scanning started. We will automatically detect your transaction.",
  "status": "scanning",
  "scan_info": {
    "max_attempts": 12,
    "interval_seconds": 15,
    "total_duration_minutes": 3
  }
}
```

**Same automatic scanning as subscription payment.**

---

### 2.6. Get Points Payment History

**Endpoint:** `GET /api/v1/payments/usdt/points/history`

**Purpose:** Lấy lịch sử mua points

**Request:**
```http
GET /api/v1/payments/usdt/points/history?limit=20&skip=0
Authorization: Bearer {firebase_token}
```

**Response:**
```json
{
  "payments": [
    {
      "payment_id": "USDT-1733213000-def456",
      "points_amount": 100,
      "amount_usdt": 4.26,
      "status": "completed",
      "created_at": "2025-12-03T10:35:00Z",
      "completed_at": "2025-12-03T10:36:00Z",
      "points_transaction_id": "ptx_abc123"
    }
  ],
  "count": 1,
  "limit": 20,
  "skip": 0
}
```

---

## 🔐 Wallet Integration Guide

### ⚠️ CRITICAL: Connect Wallet First Flow

**Step 0: Before Showing Prices**
```
User lands on pricing page
↓
Frontend checks: Is wallet connected?
↓
NO → Show "Connect Wallet" button (prominently)
YES → Show prices in USDT + "Pay Now" buttons enabled
```

### Supported Wallets

Frontend nên support các wallet phổ biến:
- **MetaMask** (Browser extension - Desktop)
- **Trust Wallet** (Mobile app)
- **Binance Wallet** (Browser + Mobile)
- **WalletConnect** (Universal - Mobile)

### Complete Wallet Connection Flow

**Step 1: Detect Wallet Availability**
```javascript
// Check if MetaMask or compatible wallet installed
const isWalletAvailable = typeof window.ethereum !== 'undefined';

if (!isWalletAvailable) {
  // Show install wallet guide
  showMessage("Please install MetaMask or compatible wallet");
  return;
}
```

**Step 2: Request Wallet Connection**
```javascript
// User clicks "Connect Wallet" button
const accounts = await ethereum.request({
  method: 'eth_requestAccounts'
});
const userAddress = accounts[0];

// Save to state
setWalletAddress(userAddress);
setIsWalletConnected(true);
```

**Step 3: Check Current Network**
```javascript
// Get current chain ID
const chainId = await ethereum.request({ method: 'eth_chainId' });
const isBSC = chainId === '0x38'; // BSC Mainnet
const isBSCTestnet = chainId === '0x61'; // BSC Testnet

if (!isBSC && !isBSCTestnet) {
  // Wrong network - need to switch
  showSwitchNetworkDialog();
}
```

**Step 4: Switch to BSC Network**
```javascript
// Prompt user to switch to BSC
try {
  await ethereum.request({
    method: 'wallet_switchEthereumChain',
    params: [{ chainId: '0x38' }], // BSC Mainnet
  });
} catch (switchError) {
  // Network not added yet - add it
  if (switchError.code === 4902) {
    await addBSCNetwork();
  }
}
```

**Step 5: Add BSC Network (if needed)**
```javascript
async function addBSCNetwork() {
  await ethereum.request({
    method: 'wallet_addEthereumChain',
    params: [{
      chainId: '0x38',
      chainName: 'Binance Smart Chain',
      nativeCurrency: {
        name: 'BNB',
        symbol: 'BNB',
        decimals: 18
      },
      rpcUrls: ['https://bsc-dataseed1.binance.org'],
      blockExplorerUrls: ['https://bscscan.com']
    }]
  });
}
```

**Step 6: Get USDT Balance**
```javascript
// USDT BEP20 Contract
const USDT_CONTRACT = '0x55d398326f99059fF775485246999027B3197955';
const USDT_ABI = [
  {
    "constant": true,
    "inputs": [{"name": "_owner", "type": "address"}],
    "name": "balanceOf",
    "outputs": [{"name": "balance", "type": "uint256"}],
    "type": "function"
  }
];

const contract = new web3.eth.Contract(USDT_ABI, USDT_CONTRACT);
const balance = await contract.methods.balanceOf(userAddress).call();
const balanceUSDT = balance / (10 ** 18);

// Display balance to user
showBalance(balanceUSDT);

// Check if sufficient for selected package
if (balanceUSDT < requiredAmount) {
  showWarning("Insufficient USDT balance. Please deposit more USDT.");
  disablePayButton();
}
```

**Step 7: Listen for Account/Network Changes**
```javascript
// Listen for account changes
ethereum.on('accountsChanged', (accounts) => {
  if (accounts.length === 0) {
    // User disconnected wallet
    setIsWalletConnected(false);
    setWalletAddress(null);
  } else {
    // User switched account
    setWalletAddress(accounts[0]);
    refreshBalance();
  }
});

// Listen for network changes
ethereum.on('chainChanged', (chainId) => {
  if (chainId !== '0x38') {
    showWarning("Please switch to BSC network");
    disablePayButton();
  } else {
    enablePayButton();
    refreshBalance();
  }
});
```

### Wallet Connection UI Components

**1. Connect Wallet Button (Before Connection)**
```
┌─────────────────────────────────────┐
│  🦊 Connect Wallet to See Prices    │
│                                     │
│  Connect your wallet to view USDT   │
│  prices and make payments           │
│                                     │
│     [ Connect MetaMask ]            │
│     [ WalletConnect ]               │
└─────────────────────────────────────┘
```

**2. Connected Wallet Display**
```
┌─────────────────────────────────────┐
│ ✅ Connected: 0x742d...35Cc         │
│ 💰 USDT Balance: 125.50 USDT       │
│ 🌐 Network: BSC Mainnet            │
│                    [ Disconnect ]   │
└─────────────────────────────────────┘
```

**3. Wrong Network Warning**
```
┌─────────────────────────────────────┐
│ ⚠️ Wrong Network                    │
│                                     │
│ Please switch to Binance Smart      │
│ Chain (BSC) to continue             │
│                                     │
│     [ Switch to BSC ]               │
└─────────────────────────────────────┘
```

**4. Insufficient Balance Warning**
```
┌─────────────────────────────────────┐
│ ⚠️ Insufficient USDT Balance        │
│                                     │
│ Required: 12.50 USDT               │
│ Your Balance: 5.20 USDT            │
│ Need: 7.30 USDT more               │
│                                     │
│ Please deposit USDT to your wallet  │
│ before continuing                   │
└─────────────────────────────────────┘
```

### Payment Sending Methods

**Option 1: Direct Wallet Transfer (Recommended)**
```javascript
// User manually opens wallet and sends
// Frontend only shows:
// - Recipient address
// - Exact amount
// - Network (BSC)
// - Token (USDT)

// Instructions:
// 1. Open your wallet app
// 2. Select "Send" or "Transfer"
// 3. Choose USDT (BEP20) token
// 4. Paste address: 0xbab94f...
// 5. Enter amount: 12.5 USDT
// 6. Confirm and send
// 7. Copy transaction hash and paste below
```

**Option 2: MetaMask Direct Transfer**
```javascript
// Send USDT via MetaMask
const transactionParameters = {
  to: USDT_CONTRACT,
  from: userAddress,
  data: web3.eth.abi.encodeFunctionCall({
    name: 'transfer',
    type: 'function',
    inputs: [
      { type: 'address', name: 'recipient' },
      { type: 'uint256', name: 'amount' }
    ]
  }, [
    recipientAddress, // WordAI wallet
    web3.utils.toWei(amount.toString(), 'ether')
  ])
};

const txHash = await ethereum.request({
  method: 'eth_sendTransaction',
  params: [transactionParameters],
});
```

**Option 3: WalletConnect**
```javascript
// For mobile wallets
// Use WalletConnect library to connect
// Then send transaction same as MetaMask
```

### QR Code Generation

**QR Code Content:**
```json
{
  "address": "0xbab94f5bf90550c9f0147fffae8a1ef006b85a07",
  "amount": "12.5",
  "token": "USDT",
  "network": "BSC",
  "payment_id": "USDT-1733212800-abc123"
}
```

**Libraries:**
- `qrcode` (npm package)
- `react-qr-code` (React component)

---

## 🎨 UI/UX Recommendations

### Page Layout Structure

**Pricing Page (Before Wallet Connected)**
```
┌──────────────────────────────────────────┐
│  WordAI Premium Plans                    │
│                                          │
│  🦊 Connect Wallet to See USDT Prices   │
│  [ Connect Wallet Button - Prominent ]  │
│                                          │
│  ┌────────┐  ┌────────┐  ┌────────┐   │
│  │Premium │  │  Pro   │  │  VIP   │   │
│  │        │  │        │  │        │   │
│  │ 93,000 │  │186,000 │  │279,000 │   │
│  │  VND   │  │  VND   │  │  VND   │   │
│  │        │  │        │  │        │   │
│  │ --USDT │  │ --USDT │  │ --USDT │   │
│  │(connect│  │(connect│  │(connect│   │
│  │ wallet)│  │ wallet)│  │ wallet)│   │
│  └────────┘  └────────┘  └────────┘   │
└──────────────────────────────────────────┘
```

**Pricing Page (After Wallet Connected)**
```
┌──────────────────────────────────────────┐
│  WordAI Premium Plans                    │
│                                          │
│  ✅ Connected: 0x742d...35Cc            │
│  💰 Balance: 125.50 USDT                │
│  🌐 Network: BSC        [Disconnect]    │
│                                          │
│  ┌────────┐  ┌────────┐  ┌────────┐   │
│  │Premium │  │  Pro   │  │  VIP   │   │
│  │        │  │        │  │        │   │
│  │ 93,000 │  │186,000 │  │279,000 │   │
│  │  VND   │  │  VND   │  │  VND   │   │
│  │        │  │        │  │        │   │
│  │ 4.17   │  │ 8.33   │  │ 12.50  │   │
│  │  USDT  │  │  USDT  │  │  USDT  │   │
│  │        │  │        │  │        │   │
│  │[Pay Now]│ │[Pay Now]│ │[Pay Now]│  │
│  └────────┘  └────────┘  └────────┘   │
└──────────────────────────────────────────┘
```

### Payment Modal Design

**Components:**
1. **Header**
   - Payment type (Subscription / Buy Points)
   - Amount in USDT and VND
   - Countdown timer (30:00)
   - Close button

2. **Connected Wallet Info**
   - ✅ Sending from: 0x742d...35Cc
   - Current balance: 125.50 USDT
   - After payment: 113.00 USDT (if sufficient)

3. **Payment Instructions**
   - Step-by-step guide with numbers
   - Network: BSC (BEP20) - BOLD
   - Token: USDT - BOLD

4. **Recipient Wallet Section**
   - Label: "Send USDT to this address"
   - Large, monospace font address
   - Copy button with feedback
   - QR code (expandable)

5. **Amount Display - CRITICAL**
   - ⚠️ **EXACT AMOUNT REQUIRED** (RED warning)
   - Amount: **12.5000 USDT** (BOLD, large font)
   - "Send EXACTLY this amount"
   - "More or less = payment will fail"

6. **Send Button (Opens Wallet)**
   - Large button: "📱 Open Wallet to Send"
   - On click → Opens user's wallet with pre-filled data
   - Or show manual instructions for mobile

7. **Transaction Hash Input**
   - Optional but recommended input field
   - Placeholder: "0x..."
   - Submit button
   - Help text: "Paste your transaction hash to speed up verification"
   - Validation: 66 characters, starts with 0x

8. **Status Display**
   - Current status message
   - Progress bar (for confirmations)
   - Estimated time remaining
   - Auto-updates from polling

9. **Action Buttons**
   - "I've sent the payment" → starts polling
   - "View on BSCScan" → opens explorer
   - "Cancel" → closes modal + cancels payment

### Payment Modal States

**State 1: Waiting for Payment**
```
┌─────────────────────────────────────────┐
│ Pay 12.50 USDT for Premium (3 months) │
│ ⏱️ Expires in: 29:45                    │
│                                         │
│ ✅ From: 0x742d...35Cc                 │
│ 💰 Balance: 125.50 USDT                │
│                                         │
│ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │
│                                         │
│ 📤 Send USDT to:                       │
│ 0xbab94f5bf90550c9f0147fffae8a1ef006b │
│                              [📋 Copy] │
│                                         │
│ ⚠️ EXACT AMOUNT REQUIRED                │
│                                         │
│        12.5000 USDT                     │
│                                         │
│ Send EXACTLY this amount                │
│ More or less = payment fails            │
│                                         │
│ [ 📱 Open MetaMask to Send ]           │
│                                         │
│ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │
│                                         │
│ Transaction Hash (optional):            │
│ [0x________________] [Submit]           │
│                                         │
│ ⏳ Waiting for payment...               │
│                                         │
│ [View on BSCScan]      [Cancel]        │
└─────────────────────────────────────────┘
```

**State 2: Processing (After TX submitted)**
```
┌─────────────────────────────────────────┐
│ 🔄 Payment Processing                   │
│                                         │
│ Transaction detected!                   │
│ Confirmations: 8/12                     │
│                                         │
│ ████████████░░░░░░░░  67%              │
│                                         │
│ ⏱️ Estimated time: ~12 seconds          │
│                                         │
│ TX: 0x1234...abcd        [View]        │
│                                         │
│ Please wait, do not close this window   │
└─────────────────────────────────────────┘
```

**State 3: Success**
```
┌─────────────────────────────────────────┐
│ 🎉 Payment Successful!                  │
│                                         │
│ ✅ Premium subscription activated       │
│ ✅ 300 points added to your account     │
│                                         │
│ Valid until: March 3, 2026              │
│                                         │
│ Transaction:                            │
│ 0x1234...abcd              [View]      │
│                                         │
│        [Go to Dashboard]                │
└─────────────────────────────────────────┘
```

### Status Messages

**Pending:**
```
⏳ Waiting for payment
Please send exactly 12.5 USDT to the address above.
```

**Processing:**
```
🔄 Payment detected!
Confirmations: 8/12
Estimated time: ~12 seconds
```

**Confirmed:**
```
✅ Payment confirmed!
Activating your subscription...
```

**Completed:**
```
🎉 Success!
Your Premium subscription is now active!
Points granted: 300
```

**Failed:**
```
❌ Payment failed
Reason: Transaction reverted on blockchain
Please try again or contact support.
```

### Mobile Considerations

- Deep links to open wallet apps
- Auto-copy address on tap
- Simplified QR code scanning
- Clear "Open Wallet" button
- Native share for address/amount

---

## 💻 Frontend Implementation Checklist

### Before Development

- [ ] Read entire documentation
- [ ] Understand connect wallet first flow
- [ ] Plan UI components for wallet connection
- [ ] Prepare error messages in Vietnamese
- [ ] Test with BSC Testnet first

### Wallet Connection Phase

- [ ] Add "Connect Wallet" button on pricing page
- [ ] Implement MetaMask detection
- [ ] Implement WalletConnect for mobile
- [ ] Add network switching (to BSC)
- [ ] Show wallet address after connection
- [ ] Display USDT balance
- [ ] Listen for account/network changes
- [ ] Handle wallet disconnection
- [ ] Show appropriate errors (wallet not installed, wrong network, etc.)

### Payment Creation Phase

- [ ] Disable "Pay Now" until wallet connected
- [ ] Show USDT prices only after wallet connected
- [ ] Validate sufficient USDT balance
- [ ] Create payment with wallet address
- [ ] Handle API errors gracefully
- [ ] Show loading state during API call

### Payment Modal Phase

- [ ] Display from/to addresses clearly
- [ ] Show exact amount with WARNING
- [ ] Add copy address button with feedback
- [ ] Generate QR code for mobile
- [ ] Provide "Open Wallet" button
- [ ] Add transaction hash input (optional)
- [ ] Validate transaction hash format
- [ ] Show countdown timer (30 minutes)

### Payment Processing Phase

- [ ] Start polling after user confirms send
- [ ] Poll every 10-15 seconds
- [ ] Show confirmation progress (X/12)
- [ ] Display estimated time remaining
- [ ] Stop polling on completion/failure
- [ ] Handle polling errors (retry)

### Success/Failure Phase

- [ ] Show clear success message
- [ ] Display what was activated/credited
- [ ] Provide transaction link (BSCScan)
- [ ] Auto-redirect to dashboard (after 3 seconds)
- [ ] Handle failures with retry option
- [ ] Show support contact for issues

### Testing Checklist

- [ ] Test MetaMask connection
- [ ] Test WalletConnect (mobile)
- [ ] Test wrong network error
- [ ] Test insufficient balance error
- [ ] Test payment creation
- [ ] Test QR code generation
- [ ] Test transaction hash submission
- [ ] Test polling and status updates
- [ ] Test success flow
- [ ] Test failure scenarios
- [ ] Test timeout (30 minutes)
- [ ] Test on mobile devices
- [ ] Test in production with real USDT

---

## ⚠️ Important Notes

### For Developers

1. **Connect Wallet First - MANDATORY**
   - User MUST connect wallet before seeing USDT prices
   - Disable payment buttons until wallet connected
   - Check network = BSC before allowing payment
   - Verify sufficient balance before creating payment

2. **Exact Amount Required**
   - User MUST send exact amount shown
   - Tolerance is only 0.01 USDT
   - More or less = payment fails
   - Show prominent warning in UI

3. **Network Selection**
   - MUST be BSC (BEP20)
   - NOT Ethereum, NOT TRC20
   - Wrong network = lost funds
   - Add network switching helper

4. **Polling Frequency**
   - Poll every 10-15 seconds
   - Don't poll faster (rate limit)
   - Stop polling after completion/failure
   - Handle network errors in polling

5. **Transaction Hash**
   - Optional but recommended
   - Speeds up verification
   - Validate format before submit
   - Show validation errors clearly

6. **Expiration**
   - Payment expires in 30 minutes
   - Show countdown timer
   - Warn user at 5 minutes remaining
   - Auto-close modal on expiration

7. **Error Handling**
   - Always show user-friendly messages
   - Log technical errors to console
   - Provide retry options
   - Show support contact for failures
   - Never expose technical details to users

8. **Balance Checking**
   - Check USDT balance after wallet connection
   - Warn if insufficient before creating payment
   - Disable payment button if insufficient
   - Show how much more USDT needed

### Security

1. **Never show private keys**
2. **Verify wallet addresses** before displaying
3. **Use HTTPS** for all API calls
4. **Validate all inputs** client-side
5. **Don't store sensitive data** in localStorage

### Testing

**Testnet:**
- Use BSC Testnet for development
- Get test BNB from faucet
- Test USDT contract: Different address on testnet
- Set `BSC_USE_TESTNET=true` in backend

**Production Checklist:**
- [ ] Test all payment flows end-to-end
- [ ] Test with different wallets
- [ ] Test error scenarios
- [ ] Test on mobile devices
- [ ] Verify confirmation times
- [ ] Test expiration handling

---

## 📞 Support & Troubleshooting

### Common Issues

**1. "Transaction not found"**
- User sent to wrong address
- Wrong network (not BSC)
- Transaction hash typo
- Solution: Check BSCScan, verify address

**2. "Amount mismatch"**
- User sent wrong amount
- Gas fees deducted from amount
- Solution: Must send exact amount

**3. "Taking too long"**
- BSC network congestion
- Low gas price
- Solution: Wait or contact support

**4. "Wallet not connecting"**
- Browser compatibility
- Wallet extension not installed
- Solution: Install wallet, refresh page

### Contact Information

**Support:**
- Email: support@wordai.com
- Live chat: Available in app
- Hours: 9AM - 6PM GMT+7

**Technical Issues:**
- Report via app feedback
- Include: payment_id, transaction_hash, timestamp

---

## 🔗 Useful Links

- **BSCScan Explorer:** https://bscscan.com
- **USDT Contract:** https://bscscan.com/token/0x55d398326f99059fF775485246999027B3197955
- **MetaMask Docs:** https://docs.metamask.io
- **WalletConnect Docs:** https://docs.walletconnect.com
- **BSC Docs:** https://docs.bnbchain.org

---

**Document Version:** 1.0
**Last Updated:** December 3, 2025
**Backend API Version:** Phase 1-6 Complete
