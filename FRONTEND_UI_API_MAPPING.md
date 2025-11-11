# Frontend UI to API Mapping - Marketplace Phase 5

## 📊 Overview
Document này map các UI components với APIs tương ứng để frontend developers biết chính xác endpoint nào cần dùng.

---

## 1. 🏪 Community Tests Marketplace (`CommunityTestsMarketplace.tsx`)

### **Search & Filter Section**

| UI Component | API Endpoint | Query Parameters |
|-------------|--------------|------------------|
| Search bar | `GET /marketplace/tests` | `?search={query}` |
| Category dropdown | `GET /marketplace/tests` | `?category={category}` |
| Tag filter | `GET /marketplace/tests` | `?tag={tag}` |
| Combined filters | `GET /marketplace/tests` | `?search={}&category={}&tag={}` |

**Example:**
```typescript
// Search for Python tests
const response = await fetch('/api/v1/marketplace/tests?search=python&category=programming&page_size=20');
```

---

### **Top Rating Section** (2 rows = 8 tests)

| UI Requirement | API Endpoint | Query Parameters |
|---------------|--------------|------------------|
| 8 highest rated tests | `GET /marketplace/tests` | `?sort=top_rated&page_size=8` |
| "View more" button | `GET /marketplace/tests` | `?sort=top_rated&page=2&page_size=20` |

**Example:**
```typescript
// Get top 8 rated tests
const topRated = await fetch('/api/v1/marketplace/tests?sort=top_rated&page_size=8');

// "View more" redirects to full page
window.location.href = '/marketplace?sort=top_rated';
```

---

### **Latest Section** (2 rows = 8 tests)

| UI Requirement | API Endpoint | Query Parameters |
|---------------|--------------|------------------|
| 8 newest tests | `GET /marketplace/tests` | `?sort=newest&page_size=8` |
| "View more" button | `GET /marketplace/tests` | `?sort=newest&page=2&page_size=20` |

**Example:**
```typescript
// Get 8 newest tests
const latest = await fetch('/api/v1/marketplace/tests?sort=newest&page_size=8');
```

---

### **Stats Section**

#### **Left Side: Most Taken Tests** (Top 5)

| UI Requirement | API Endpoint | Query Parameters |
|---------------|--------------|------------------|
| Top 5 most completed | `GET /marketplace/leaderboard/tests` | `?period=all` (returns 10, take first 5) |
| Filter by category | `GET /marketplace/leaderboard/tests` | `?category=programming&period=30d` |

**Example:**
```typescript
// Get top 5 most completed tests
const response = await fetch('/api/v1/marketplace/leaderboard/tests?period=all');
const top5 = response.data.top_tests.slice(0, 5);

// Display with rank, title, completions
top5.forEach(test => {
  console.log(`#${test.rank} ${test.title} - ${test.stats.total_completions} completions`);
});
```

**Response Structure:**
```json
{
  "success": true,
  "data": {
    "period": "all",
    "category": "all",
    "top_tests": [
      {
        "rank": 1,
        "test_id": "...",
        "title": "Python Basic Test",
        "stats": {
          "total_completions": 1520,
          "total_purchases": 150,
          "average_rating": 4.7
        },
        "cover_image": { "thumbnail": "..." }
      }
    ]
  }
}
```

---

#### **Right Side: Top Test Takers** (Top 5 users)

| UI Requirement | API Endpoint | Query Parameters |
|---------------|--------------|------------------|
| Top 5 most active users | `GET /marketplace/leaderboard/users` | `?period=all` (returns 10, take first 5) |
| Filter by category | `GET /marketplace/leaderboard/users` | `?category=programming&period=30d` |

**Example:**
```typescript
// Get top 5 active users
const response = await fetch('/api/v1/marketplace/leaderboard/users?period=all');
const top5Users = response.data.top_users.slice(0, 5);

// Display with rank, name, stats, badges
top5Users.forEach(user => {
  console.log(`#${user.rank} ${user.display_name}`);
  console.log(`Completions: ${user.stats.total_completions}`);
  console.log(`Avg Score: ${user.stats.average_score}%`);
  user.achievements.forEach(badge => console.log(`🏆 ${badge.title}`));
});
```

**Response Structure:**
```json
{
  "success": true,
  "data": {
    "period": "all",
    "top_users": [
      {
        "rank": 1,
        "user_id": "...",
        "display_name": "Alice Wonder",
        "avatar_url": "...",
        "stats": {
          "total_completions": 45,
          "unique_tests_completed": 38,
          "average_score": 87.5,
          "perfect_scores": 12
        },
        "achievements": [
          {
            "badge": "speed_demon",
            "title": "Speed Demon",
            "description": "Completed 10+ tests with >90% accuracy"
          }
        ]
      }
    ]
  }
}
```

---

## 2. 📝 MyPublicTests - Creator Dashboard (`MyPublicTests.tsx`)

### **Test Grid Display**

| UI Component | API Endpoint | Query Parameters |
|-------------|--------------|------------------|
| All published tests | `GET /marketplace/me/tests` | `?status=published&page_size=20` |
| Unpublished drafts | `GET /marketplace/me/tests` | `?status=unpublished` |

**Example:**
```typescript
// Get my published tests
const response = await fetch('/api/v1/marketplace/me/tests?status=published', {
  headers: { 'Authorization': `Bearer ${token}` }
});

const { tests } = response.data;
```

---

### **Stats Display Per Test**

| UI Element | API Field | Source |
|-----------|-----------|--------|
| 👥 Participants | `stats.total_purchases` | Test purchases count |
| ⭐ Rating | `stats.avg_rating` + `stats.rating_count` | "4.7 (89 ratings)" |
| 📈 Completion rate | `stats.completion_rate` | **NEW** - "80% completed" |
| 💰 Earnings | `stats.total_revenue` | Points earned (before transfer) |

**Response Structure:**
```json
{
  "success": true,
  "data": {
    "tests": [
      {
        "test_id": "...",
        "title": "Python Basic Test",
        "stats": {
          "total_purchases": 150,
          "total_completions": 120,
          "completion_rate": 80.0,
          "total_revenue": 120000,
          "avg_rating": 4.7,
          "rating_count": 89
        }
      }
    ]
  }
}
```

**UI Implementation:**
```typescript
// Display stats
<div className="stats">
  <div>👥 {test.stats.total_purchases} participants</div>
  <div>⭐ {test.stats.avg_rating} ({test.stats.rating_count} ratings)</div>
  <div>📈 {test.stats.completion_rate}% completed</div>
  <div>💰 {test.stats.total_revenue.toLocaleString()} points</div>
</div>
```

---

### **Action Buttons**

| UI Button | API Endpoint | Method | Notes |
|-----------|--------------|--------|-------|
| "Transfer to Wallet" | `/marketplace/me/earnings/transfer` | POST | Transfer all or partial earnings |
| "View" | `/tests/{test_id}` | GET | Navigate to test detail |
| "Edit" | `/tests/{test_id}` | PATCH | Edit test questions/config |
| "Unpublish" | `/marketplace/tests/{test_id}/unpublish` | POST | Remove from marketplace |

**Transfer Earnings Example:**
```typescript
// Transfer all earnings to wallet
const transferAll = async () => {
  // First, get current earnings
  const earningsRes = await fetch('/api/v1/marketplace/me/earnings', {
    headers: { 'Authorization': `Bearer ${token}` }
  });
  const { available_balance } = earningsRes.data;
  
  // Transfer to wallet
  const transferRes = await fetch('/api/v1/marketplace/me/earnings/transfer', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      amount_points: available_balance
    })
  });
  
  const result = await transferRes.json();
  console.log(`Transferred ${result.data.transferred_amount} points`);
};
```

---

## 3. 📚 TestHistory - Purchase History (`TestHistory.tsx`)

### **Stats Summary Section**

| UI Element | API Endpoint | Response Field |
|-----------|--------------|----------------|
| Tổng tests đã làm | `GET /marketplace/me/purchases/summary` | `total_purchased` |
| Tỷ lệ đỗ (Pass Rate) | `GET /marketplace/me/purchases/summary` | `pass_rate` |
| Điểm trung bình | `GET /marketplace/me/purchases/summary` | `average_score` |
| Thời gian làm bài | `GET /marketplace/me/purchases/summary` | `total_time_spent_minutes` |

**Example:**
```typescript
// Get summary stats
const response = await fetch('/api/v1/marketplace/me/purchases/summary', {
  headers: { 'Authorization': `Bearer ${token}` }
});

const { data } = await response.json();
console.log(`Completed: ${data.total_completed}/${data.total_purchased}`);
console.log(`Pass Rate: ${data.pass_rate}%`);
console.log(`Average: ${data.average_score}%`);
console.log(`Time: ${data.total_time_spent_minutes} minutes`);
```

**Response Structure:**
```json
{
  "success": true,
  "data": {
    "total_purchased": 15,
    "total_completed": 12,
    "pass_rate": 80.0,
    "average_score": 85.5,
    "total_time_spent_minutes": 450
  }
}
```

**UI Implementation:**
```typescript
<div className="summary-stats">
  <StatCard icon="📚" label="Tests Taken" value={`${data.total_completed}/${data.total_purchased}`} />
  <StatCard icon="✅" label="Pass Rate" value={`${data.pass_rate}%`} />
  <StatCard icon="📊" label="Average Score" value={`${data.average_score}%`} />
  <StatCard icon="⏱️" label="Time Spent" value={`${data.total_time_spent_minutes} min`} />
</div>
```

---

### **Filters Section**

| UI Filter | API Endpoint | Query Parameters |
|-----------|--------------|------------------|
| Search tests | `GET /marketplace/me/purchases` | Client-side filter on results |
| Status: All/Passed/Failed | `GET /marketplace/me/purchases` | `?status=completed` (filter passed/failed client-side) |
| Category filter | `GET /marketplace/me/purchases` | Client-side filter on `test_info.category` |

**Example:**
```typescript
// Get all purchases
const response = await fetch('/api/v1/marketplace/me/purchases?page_size=50', {
  headers: { 'Authorization': `Bearer ${token}` }
});

const purchases = response.data.purchases;

// Client-side filtering
const passed = purchases.filter(p => p.attempt_stats.best_score >= 70);
const failed = purchases.filter(p => 
  p.attempt_stats.times_completed > 0 && p.attempt_stats.best_score < 70
);
const programmingTests = purchases.filter(p => p.test_info.category === 'programming');
```

---

### **Test Cards Display**

| UI Element | API Field | Source |
|-----------|-----------|--------|
| Test title | `test_info.title` | Test name |
| Score | `attempt_stats.best_score` | Best score achieved |
| Times completed | `attempt_stats.times_completed` | Completion count |
| Average score | `attempt_stats.average_score` | Average of all attempts |
| Last attempt | `attempt_stats.last_attempt_at` | Last attempt date |
| Rank percentile | `GET /marketplace/me/purchases/{test_id}/rank` | **NEW** - Rank comparison |
| Pass/Fail icon | `attempt_stats.best_score >= 70` | ✓ or ✗ based on score |

**Get Rank Percentile:**
```typescript
// For each test card, fetch rank info
const getRank = async (testId: string) => {
  const response = await fetch(`/api/v1/marketplace/me/purchases/${testId}/rank`, {
    headers: { 'Authorization': `Bearer ${token}` }
  });
  
  const { data } = await response.json();
  return {
    percentile: data.rank_percentile,
    position: data.rank_position,
    total: data.total_users
  };
};

// Display in card
const rank = await getRank(purchase.test_id);
console.log(`You're in top ${100 - rank.percentile}%`);
console.log(`Rank ${rank.position} out of ${rank.total}`);
```

**Response Structure:**
```json
{
  "success": true,
  "data": {
    "test_id": "...",
    "user_best_score": 92.5,
    "rank_percentile": 85.5,
    "total_users": 150,
    "users_below": 128,
    "rank_position": 22
  }
}
```

**UI Implementation:**
```typescript
<TestCard>
  <h3>{purchase.test_info.title}</h3>
  
  {/* Score & Icon */}
  <div className="score">
    {purchase.attempt_stats.best_score >= 70 ? '✓' : '✗'}
    <span>{purchase.attempt_stats.best_score}%</span>
  </div>
  
  {/* Stats */}
  <div className="stats">
    <div>Completed: {purchase.attempt_stats.times_completed}x</div>
    <div>Average: {purchase.attempt_stats.average_score}%</div>
  </div>
  
  {/* Rank (fetch separately) */}
  <div className="rank">
    Top {100 - rank.percentile}% • Rank #{rank.position}/{rank.total}
  </div>
  
  {/* Actions */}
  <button onClick={() => viewResult(purchase.test_id)}>View Result</button>
</TestCard>
```

---

## 4. 🧭 TestSidebar - Navigation

### **Community Tests Section**

| UI Element | Action | Endpoint |
|-----------|--------|----------|
| "Community Tests" button | Navigate to marketplace | `/marketplace/tests` |
| Notification badge | Check new tests count | `GET /marketplace/tests?sort=newest` (count last 7 days) |

**Example:**
```typescript
// Add to sidebar
<SidebarItem 
  icon={<Globe />}
  label="Community Tests"
  badge={newTestsCount}
  onClick={() => navigate('/marketplace')}
  gradient="bg-gradient-to-r from-purple-500 to-pink-500"
/>

// Get new tests count
const getNewTestsCount = async () => {
  const sevenDaysAgo = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000);
  const response = await fetch('/api/v1/marketplace/tests?sort=newest&page_size=100');
  const tests = response.data.tests;
  
  // Count tests published in last 7 days
  const newTests = tests.filter(t => 
    new Date(t.published_at) >= sevenDaysAgo
  );
  
  return newTests.length;
};
```

---

## 📝 Summary: Complete API List

### **Public Endpoints** (No auth required)
1. `GET /marketplace/tests` - Browse/search marketplace
2. `GET /marketplace/tests/{test_id}` - Test detail
3. `GET /marketplace/leaderboard/tests` - Top tests
4. `GET /marketplace/leaderboard/users` - Top users

### **Authenticated Endpoints** (Require Bearer token)

#### **Creator Endpoints:**
5. `GET /marketplace/me/tests` - My published tests
6. `POST /marketplace/tests/{test_id}/publish` - Publish test
7. `PATCH /marketplace/tests/{test_id}/config` - Update config
8. `POST /marketplace/tests/{test_id}/unpublish` - Unpublish
9. `GET /marketplace/me/earnings` - View earnings
10. `POST /marketplace/me/earnings/transfer` - Transfer to wallet

#### **Buyer Endpoints:**
11. `POST /marketplace/tests/{test_id}/purchase` - Purchase test
12. `GET /marketplace/me/purchases` - Purchase history
13. **`GET /marketplace/me/purchases/summary`** - History stats (**NEW**)
14. **`GET /marketplace/me/purchases/{test_id}/rank`** - Rank percentile (**NEW**)
15. `POST /marketplace/tests/{test_id}/ratings` - Rate test
16. `GET /marketplace/tests/{test_id}/ratings` - View ratings

---

## 🎯 Quick Reference: UI → API Mapping

| UI Page | Primary Endpoints |
|---------|------------------|
| **CommunityTestsMarketplace** | `/marketplace/tests`, `/marketplace/leaderboard/tests`, `/marketplace/leaderboard/users` |
| **MyPublicTests** | `/marketplace/me/tests`, `/marketplace/me/earnings/transfer` |
| **TestHistory** | `/marketplace/me/purchases`, `/marketplace/me/purchases/summary`, `/marketplace/me/purchases/{test_id}/rank` |
| **TestSidebar** | `/marketplace/tests?sort=newest` |

---

## ✅ All UI Requirements Coverage

### **Community Tests Marketplace**
- ✅ Search & filters
- ✅ Top Rating (8 tests)
- ✅ Latest (8 tests)
- ✅ Most Taken Tests (top 5)
- ✅ Top Test Takers (top 5)

### **MyPublicTests**
- ✅ Participants count
- ✅ Rating
- ✅ **Completion rate** (NEW)
- ✅ Earnings
- ✅ Transfer to Wallet

### **TestHistory**
- ✅ **Total tests** (NEW: summary endpoint)
- ✅ **Pass Rate** (NEW: summary endpoint)
- ✅ **Average Score** (NEW: summary endpoint)
- ✅ Filters (status, category)
- ✅ **Rank percentile** (NEW: rank endpoint)

---

## 🚀 Ready for Frontend Implementation!

All APIs are now complete and support all UI requirements. Frontend can start implementing:

1. **CommunityTestsMarketplace.tsx** - Full coverage
2. **MyPublicTests.tsx** - Full coverage with completion rate
3. **TestHistory.tsx** - Full coverage with summary stats and rank
4. **TestSidebar.tsx** - Ready with notification support
