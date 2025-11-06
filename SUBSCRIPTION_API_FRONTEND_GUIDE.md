# SUBSCRIPTION API - FRONTEND INTEGRATION GUIDE

## 📌 Tổng Quan

API Subscription cung cấp **4 endpoints** để frontend hiển thị thông tin subscription, points, và usage của user.

---

## 🎯 Các Endpoints Chính

### 1. GET `/api/subscription/info` - Thông tin đầy đủ ⭐

**Mục đích:** Lấy TẤT CẢ thông tin subscription, points, và usage limits.

**Authentication:** Required (Firebase token)

**Request:**
```typescript
const response = await fetch('/api/subscription/info', {
  headers: {
    'Authorization': `Bearer ${firebaseToken}`
  }
});
```

**Response:**
```json
{
  // Plan Information
  "plan": "free",
  "status": "active",
  
  // Points Balance
  "points_total": 10,
  "points_remaining": 8,
  "points_used": 2,
  
  // Daily Chats (FREE users only)
  "daily_chat_limit": 10,
  "daily_chat_count": 3,
  "daily_chat_remaining": 7,
  
  // Storage Limits
  "storage_limit_mb": 50,
  "storage_used_mb": 12.5,
  "storage_remaining_mb": 37.5,
  
  // Documents Limits
  "documents_limit": 10,
  "documents_count": 3,
  "documents_remaining": 7,
  
  // Files Limits
  "upload_files_limit": 10,
  "upload_files_count": 5,
  "upload_files_remaining": 5,
  
  // Subscription Dates
  "start_date": "2025-11-06T10:00:00Z",
  "end_date": null,
  "auto_renew": false,
  "last_reset_date": "2025-11-06T00:00:00Z",
  "updated_at": "2025-11-06T10:30:00Z"
}
```

**Khi nào dùng:**
- ✅ Trang Profile/Settings
- ✅ Trang Subscription Management
- ✅ Modal hiển thị chi tiết subscription

---

### 2. GET `/api/subscription/usage-summary` - Tóm tắt nhanh ⚡

**Mục đích:** Lấy thông tin tóm tắt để hiển thị trên header/sidebar.

**Authentication:** Required (Firebase token)

**Request:**
```typescript
const response = await fetch('/api/subscription/usage-summary', {
  headers: {
    'Authorization': `Bearer ${firebaseToken}`
  }
});
```

**Response:**
```json
{
  "points_remaining": 8,
  "daily_chats_remaining": 7,
  "storage_percentage": 25.0,
  "documents_percentage": 30.0,
  "plan": "free",
  "is_premium": false
}
```

**Khi nào dùng:**
- ✅ Header/Navbar (hiển thị points còn lại)
- ✅ Sidebar (hiển thị quick stats)
- ✅ Dashboard widgets
- ✅ Real-time updates sau mỗi action

---

### 3. GET `/api/subscription/points/history` - Lịch sử giao dịch 📊

**Mục đích:** Xem lịch sử sử dụng points với phân trang.

**Authentication:** Required (Firebase token)

**Query Parameters:**
- `page` (int, default: 1) - Trang hiện tại
- `limit` (int, default: 20, max: 100) - Số items mỗi trang
- `transaction_type` (string, optional) - Lọc theo loại: `spend`, `earn`, `grant`, `refund`, `bonus`, `purchase`

**Request:**
```typescript
// Trang 1, 20 items
const response = await fetch('/api/subscription/points/history?page=1&limit=20', {
  headers: {
    'Authorization': `Bearer ${firebaseToken}`
  }
});

// Chỉ xem những lần dùng points
const spendOnly = await fetch('/api/subscription/points/history?transaction_type=spend', {
  headers: {
    'Authorization': `Bearer ${firebaseToken}`
  }
});
```

**Response:**
```json
{
  "transactions": [
    {
      "transaction_id": "673b4e5f0123456789abcdef",
      "transaction_type": "spend",
      "points": -2,
      "service": "ai_chat",
      "description": "Chat with Claude (Premium model)",
      "created_at": "2025-11-06T10:30:00Z",
      "metadata": {
        "provider": "claude",
        "model": "claude-3-5-sonnet-20241022",
        "conversation_id": "conv_123"
      }
    },
    {
      "transaction_id": "673b4e5f0123456789abcde0",
      "transaction_type": "spend",
      "points": -2,
      "service": "ai_document_edit",
      "description": "AI Edit document: My Document.docx",
      "created_at": "2025-11-06T09:15:00Z",
      "metadata": {
        "document_id": "doc_456",
        "operation": "edit"
      }
    },
    {
      "transaction_id": "673b4e5f0123456789abcde1",
      "transaction_type": "grant",
      "points": 10,
      "service": "system",
      "description": "Welcome bonus - FREE plan registration",
      "created_at": "2025-11-06T08:00:00Z",
      "metadata": null
    }
  ],
  "total": 3,
  "page": 1,
  "limit": 20,
  "has_more": false
}
```

**Transaction Types:**
- `spend` - Tiêu points (hiển thị số âm)
- `earn` - Nhận points từ hoạt động
- `grant` - Tặng points từ hệ thống (bonus, promotion)
- `refund` - Hoàn lại points (hủy giao dịch)
- `bonus` - Điểm thưởng đặc biệt
- `purchase` - Mua gói points

**Khi nào dùng:**
- ✅ Trang Points History
- ✅ Modal xem chi tiết giao dịch
- ✅ Reports/Analytics

---

### 4. GET `/api/subscription/points/balance` - Số dư nhanh 💰

**Mục đích:** Lấy CHỈ số points (endpoint nhanh nhất).

**Authentication:** Required (Firebase token)

**Request:**
```typescript
const response = await fetch('/api/subscription/points/balance', {
  headers: {
    'Authorization': `Bearer ${firebaseToken}`
  }
});
```

**Response:**
```json
{
  "points_remaining": 8,
  "points_total": 10,
  "points_used": 2
}
```

**Khi nào dùng:**
- ✅ Real-time updates sau mỗi AI action
- ✅ Polling/WebSocket updates
- ✅ Header badge (số points)

---

## 📱 Use Cases - Frontend Implementation

### Use Case 1: Header Points Display

```typescript
// Component: PointsBadge.tsx
import { useEffect, useState } from 'react';

function PointsBadge() {
  const [points, setPoints] = useState(0);
  
  useEffect(() => {
    // Fetch initial balance
    fetchBalance();
    
    // Poll every 30 seconds
    const interval = setInterval(fetchBalance, 30000);
    return () => clearInterval(interval);
  }, []);
  
  const fetchBalance = async () => {
    const token = await getFirebaseToken();
    const response = await fetch('/api/subscription/points/balance', {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    const data = await response.json();
    setPoints(data.points_remaining);
  };
  
  return (
    <div className="points-badge">
      <span className="icon">💰</span>
      <span className="value">{points}</span>
      <span className="label">Points</span>
    </div>
  );
}
```

### Use Case 2: Subscription Page (Full Info)

```typescript
// Page: SubscriptionPage.tsx
import { useEffect, useState } from 'react';

function SubscriptionPage() {
  const [sub, setSub] = useState(null);
  
  useEffect(() => {
    fetchSubscription();
  }, []);
  
  const fetchSubscription = async () => {
    const token = await getFirebaseToken();
    const response = await fetch('/api/subscription/info', {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    const data = await response.json();
    setSub(data);
  };
  
  if (!sub) return <Loading />;
  
  return (
    <div className="subscription-page">
      <h1>Your Subscription</h1>
      
      {/* Plan Card */}
      <div className="plan-card">
        <h2>{sub.plan.toUpperCase()} Plan</h2>
        <p>Status: {sub.status}</p>
      </div>
      
      {/* Points Balance */}
      <div className="points-card">
        <h3>Points Balance</h3>
        <p className="big-number">{sub.points_remaining}</p>
        <p className="small">of {sub.points_total} total</p>
        <p className="used">Used: {sub.points_used}</p>
      </div>
      
      {/* Daily Chats (FREE only) */}
      {sub.plan === 'free' && (
        <div className="chats-card">
          <h3>Free Chats Today</h3>
          <p>{sub.daily_chat_remaining} of {sub.daily_chat_limit} remaining</p>
          <ProgressBar 
            value={sub.daily_chat_count} 
            max={sub.daily_chat_limit} 
          />
        </div>
      )}
      
      {/* Storage */}
      <div className="storage-card">
        <h3>Storage</h3>
        <p>{sub.storage_used_mb.toFixed(1)} MB / {sub.storage_limit_mb} MB</p>
        <ProgressBar 
          value={sub.storage_used_mb} 
          max={sub.storage_limit_mb} 
        />
      </div>
      
      {/* Documents */}
      <div className="documents-card">
        <h3>Documents</h3>
        <p>{sub.documents_count} / {sub.documents_limit} documents</p>
        <ProgressBar 
          value={sub.documents_count} 
          max={sub.documents_limit} 
        />
      </div>
      
      {/* Files */}
      <div className="files-card">
        <h3>Uploaded Files</h3>
        <p>{sub.upload_files_count} / {sub.upload_files_limit} files</p>
        <ProgressBar 
          value={sub.upload_files_count} 
          max={sub.upload_files_limit} 
        />
      </div>
    </div>
  );
}
```

### Use Case 3: Points History Table

```typescript
// Component: PointsHistory.tsx
import { useEffect, useState } from 'react';

function PointsHistory() {
  const [history, setHistory] = useState([]);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);
  
  useEffect(() => {
    fetchHistory();
  }, [page]);
  
  const fetchHistory = async () => {
    const token = await getFirebaseToken();
    const response = await fetch(
      `/api/subscription/points/history?page=${page}&limit=20`,
      { headers: { 'Authorization': `Bearer ${token}` } }
    );
    const data = await response.json();
    setHistory(data.transactions);
    setHasMore(data.has_more);
  };
  
  return (
    <div className="points-history">
      <h2>Points History</h2>
      
      <table>
        <thead>
          <tr>
            <th>Date</th>
            <th>Type</th>
            <th>Service</th>
            <th>Description</th>
            <th>Points</th>
          </tr>
        </thead>
        <tbody>
          {history.map(txn => (
            <tr key={txn.transaction_id}>
              <td>{new Date(txn.created_at).toLocaleString()}</td>
              <td>
                <span className={`badge ${txn.transaction_type}`}>
                  {txn.transaction_type}
                </span>
              </td>
              <td>{txn.service || '-'}</td>
              <td>{txn.description}</td>
              <td className={txn.points < 0 ? 'negative' : 'positive'}>
                {txn.points > 0 ? '+' : ''}{txn.points}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      
      {/* Pagination */}
      <div className="pagination">
        <button 
          onClick={() => setPage(p => p - 1)} 
          disabled={page === 1}
        >
          Previous
        </button>
        <span>Page {page}</span>
        <button 
          onClick={() => setPage(p => p + 1)} 
          disabled={!hasMore}
        >
          Next
        </button>
      </div>
    </div>
  );
}
```

### Use Case 4: Dashboard Widgets

```typescript
// Component: DashboardWidgets.tsx
import { useEffect, useState } from 'react';

function DashboardWidgets() {
  const [summary, setSummary] = useState(null);
  
  useEffect(() => {
    fetchSummary();
  }, []);
  
  const fetchSummary = async () => {
    const token = await getFirebaseToken();
    const response = await fetch('/api/subscription/usage-summary', {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    const data = await response.json();
    setSummary(data);
  };
  
  if (!summary) return <Loading />;
  
  return (
    <div className="dashboard-widgets">
      {/* Points Widget */}
      <div className="widget">
        <div className="icon">💰</div>
        <div className="value">{summary.points_remaining}</div>
        <div className="label">Points Remaining</div>
      </div>
      
      {/* Chats Widget */}
      <div className="widget">
        <div className="icon">💬</div>
        <div className="value">{summary.daily_chats_remaining}</div>
        <div className="label">Free Chats Today</div>
      </div>
      
      {/* Storage Widget */}
      <div className="widget">
        <div className="icon">💾</div>
        <div className="value">{summary.storage_percentage.toFixed(0)}%</div>
        <div className="label">Storage Used</div>
        <CircularProgress value={summary.storage_percentage} />
      </div>
      
      {/* Documents Widget */}
      <div className="widget">
        <div className="icon">📄</div>
        <div className="value">{summary.documents_percentage.toFixed(0)}%</div>
        <div className="label">Documents Used</div>
        <CircularProgress value={summary.documents_percentage} />
      </div>
      
      {/* Plan Badge */}
      <div className="widget">
        <div className="plan-badge">
          {summary.is_premium ? (
            <span className="premium">⭐ PREMIUM</span>
          ) : (
            <span className="free">FREE</span>
          )}
        </div>
        <button onClick={() => navigate('/upgrade')}>
          {summary.is_premium ? 'Manage Plan' : 'Upgrade Now'}
        </button>
      </div>
    </div>
  );
}
```

---

## ⚡ Performance Tips

### 1. Caching Strategy

```typescript
// Use React Query for automatic caching
import { useQuery } from '@tanstack/react-query';

function useSubscriptionInfo() {
  return useQuery({
    queryKey: ['subscription'],
    queryFn: fetchSubscriptionInfo,
    staleTime: 5 * 60 * 1000, // 5 minutes
    cacheTime: 10 * 60 * 1000, // 10 minutes
  });
}

function usePointsBalance() {
  return useQuery({
    queryKey: ['points-balance'],
    queryFn: fetchPointsBalance,
    refetchInterval: 30000, // Auto-refetch every 30s
  });
}
```

### 2. Optimistic Updates

```typescript
// After AI action, update points locally first
async function chatWithAI(message, provider) {
  // Optimistic update
  setPoints(prev => prev - (provider === 'deepseek' ? 1 : 2));
  
  try {
    await sendChat(message, provider);
    // Success - real balance will sync on next fetch
  } catch (error) {
    // Revert on error
    fetchBalance(); // Re-fetch actual balance
  }
}
```

### 3. Conditional Rendering

```typescript
// Only fetch full info on subscription page
function App() {
  const location = useLocation();
  
  // Always fetch balance for header
  const { data: balance } = usePointsBalance();
  
  // Only fetch full info on subscription page
  const { data: subscription } = useSubscriptionInfo({
    enabled: location.pathname === '/subscription'
  });
  
  return (
    <>
      <Header balance={balance} />
      <Routes>
        <Route path="/subscription" element={<SubscriptionPage data={subscription} />} />
      </Routes>
    </>
  );
}
```

---

## 🎨 UI/UX Recommendations

### 1. Points Display
- ✅ Always visible in header
- ✅ Update in real-time after actions
- ✅ Show warning when < 5 points
- ✅ Animate on change

### 2. Limit Warnings
```typescript
// Show warning when approaching limits
function StorageWidget({ used, limit }) {
  const percentage = (used / limit) * 100;
  
  return (
    <div className={`storage-widget ${
      percentage > 90 ? 'danger' :
      percentage > 75 ? 'warning' : ''
    }`}>
      {percentage > 90 && (
        <Alert>⚠️ Storage almost full! Upgrade to get more space.</Alert>
      )}
    </div>
  );
}
```

### 3. Upgrade Prompts
- Show upgrade button when points = 0
- Show upgrade link when hitting limits
- Offer direct upgrade path

---

## 📊 Error Handling

```typescript
async function fetchSubscription() {
  try {
    const response = await fetch('/api/subscription/info', {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    
    if (!response.ok) {
      if (response.status === 401) {
        // Token expired, redirect to login
        redirectToLogin();
      } else if (response.status === 500) {
        // Server error, show error message
        showError('Failed to load subscription info');
      }
    }
    
    return await response.json();
  } catch (error) {
    // Network error
    showError('Network error, please try again');
  }
}
```

---

## 🚀 Quick Start Checklist

### Backend Ready ✅
- [x] 4 endpoints created
- [x] Authentication required
- [x] Pagination support
- [x] Error handling

### Frontend TODO
- [ ] Create `useSubscription()` hook
- [ ] Create `usePoints()` hook
- [ ] Create `PointsBadge` component
- [ ] Create `SubscriptionPage` component
- [ ] Create `PointsHistory` component
- [ ] Add upgrade prompts
- [ ] Add limit warnings
- [ ] Test with real data

---

## 🔗 API Base URL

**Development:** `http://localhost:8000`
**Production:** `https://your-production-domain.com`

All endpoints require Firebase authentication token in header:
```
Authorization: Bearer <firebase-token>
```

---

## 📞 Support

Nếu có vấn đề với API, liên hệ backend team hoặc xem logs:
- Server logs: `/path/to/logs/app.log`
- Look for: `❌`, `ERROR`, `subscription`, `points`
