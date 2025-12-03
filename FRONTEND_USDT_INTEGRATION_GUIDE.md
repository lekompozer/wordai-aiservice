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
1. User chọn gói subscription (Premium/Pro/VIP) và duration (3/12 months)
2. User click "Pay with USDT" button
3. Frontend gọi API tạo payment → Nhận wallet address và amount
4. Frontend hiển thị QR code + payment instructions
5. User mở wallet app → Send USDT đến địa chỉ
6. User paste transaction hash vào form (optional)
7. Frontend poll API kiểm tra status mỗi 10-15 giây
8. Sau 12 confirmations (~36 giây) → Subscription được activate
9. Hiển thị success message + redirect về dashboard
```

### Flow 2: Points Purchase

```
1. User chọn gói points (50/100/200) hoặc nhập custom amount
2. User click "Buy with USDT"
3. Frontend gọi API tạo payment → Nhận wallet address và amount
4. Frontend hiển thị payment instructions
5. User send USDT từ wallet
6. User submit transaction hash (optional)
7. Frontend poll status endpoint
8. Sau confirm → Points được credit vào account
9. Hiển thị success + updated points balance
```

---

## 🔌 API Endpoints

### Base URL
```
Production: https://api.wordai.com
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

### 1.2. Create Subscription Payment

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
  "from_address": "0x742d..."  // Optional: User's wallet address
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
- 400: Invalid plan/duration
- 401: Not authenticated
- 500: Server error

---

### 1.3. Check Payment Status

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

### 1.5. Get Payment History

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
  "from_address": "0x742d..."   // Optional
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

**Validation:**
- points_amount >= 100
- Show error if less than minimum

---

### 2.3. Check Points Payment Status

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

**Polling:** Same as subscription (every 10-15 seconds)

---

### 2.4. Submit Transaction Hash (Points)

**Endpoint:** `POST /api/v1/payments/usdt/points/{payment_id}/verify`

**Request/Response:** Same structure as subscription verify endpoint

---

### 2.5. Get Points Payment History

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

### Supported Wallets

Frontend nên support các wallet phổ biến:
- **MetaMask** (Browser extension)
- **Trust Wallet** (Mobile)
- **Binance Wallet**
- **WalletConnect** (Universal)

### Wallet Connection Flow

**Step 1: Detect Wallet**
```javascript
// Check if MetaMask installed
const isMetaMaskInstalled = typeof window.ethereum !== 'undefined';

// Check if on BSC network
const chainId = await ethereum.request({ method: 'eth_chainId' });
const isBSC = chainId === '0x38'; // BSC Mainnet
```

**Step 2: Request Connection**
```javascript
// Request wallet connection
const accounts = await ethereum.request({
  method: 'eth_requestAccounts'
});
const userAddress = accounts[0];
```

**Step 3: Switch to BSC Network**
```javascript
// If not on BSC, prompt user to switch
if (!isBSC) {
  await ethereum.request({
    method: 'wallet_switchEthereumChain',
    params: [{ chainId: '0x38' }], // BSC Mainnet
  });
}
```

**Step 4: Add BSC Network (if not added)**
```javascript
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
```

**Step 5: Get USDT Balance**
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

### Payment Modal Design

**Components:**
1. **Header**
   - Payment type (Subscription / Buy Points)
   - Amount in USDT and VND
   - Countdown timer (30:00)

2. **Payment Instructions**
   - Step-by-step guide
   - Network: BSC (BEP20)
   - Token: USDT

3. **Wallet Address Section**
   - Large, readable address
   - Copy button with feedback
   - QR code (collapsible/expandable)

4. **Amount Display**
   - **Exact amount** in bold
   - Warning: "Send EXACTLY this amount"
   - "Amount must match exactly"

5. **Transaction Hash Input**
   - Optional input field
   - Placeholder: "0x..."
   - Submit button
   - Help text: "Speed up verification by pasting your transaction hash"

6. **Status Display**
   - Current status message
   - Progress bar (for confirmations)
   - Estimated time remaining

7. **Action Buttons**
   - "I've sent the payment" (triggers polling)
   - "Cancel" (closes modal)
   - "View on BSCScan" (opens explorer)

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

## ⚠️ Important Notes

### For Developers

1. **Exact Amount Required**
   - User MUST send exact amount shown
   - Tolerance is only 0.01 USDT
   - More or less = payment fails

2. **Network Selection**
   - MUST be BSC (BEP20)
   - NOT Ethereum, NOT TRC20
   - Wrong network = lost funds

3. **Polling Frequency**
   - Poll every 10-15 seconds
   - Don't poll faster (rate limit)
   - Stop polling after completion/failure

4. **Transaction Hash**
   - Optional but recommended
   - Speeds up verification
   - Validate format before submit

5. **Expiration**
   - Payment expires in 30 minutes
   - Show countdown timer
   - Warn user before expiration
   - Auto-close modal on expiration

6. **Error Handling**
   - Always show user-friendly messages
   - Log technical errors to console
   - Provide retry options
   - Show support contact for failures

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
