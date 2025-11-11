# Online Test Marketplace - Frontend Integration Guide

## Overview
This guide helps frontend developers integrate the Phase 5 Marketplace API for publishing, browsing, purchasing, and rating tests.

---

## Base URL
```
Production: https://ai.wordai.pro/marketplace
Development: http://localhost:8000/marketplace
```

---

## Authentication
Most endpoints require Firebase ID token:
```javascript
const token = await user.getIdToken();

headers: {
  'Authorization': `Bearer ${token}`,
  'Content-Type': 'application/json'
}
```

---

## 1. Publishing a Test

### Endpoint
```
POST /marketplace/tests/{test_id}/publish
```

### Frontend Flow
```javascript
// 1. User selects cover image (validate on frontend)
const coverImage = document.getElementById('cover-input').files[0];

// Validate dimensions (min 800x600)
const img = new Image();
img.onload = () => {
  if (img.width < 800 || img.height < 600) {
    alert('Image must be at least 800x600 pixels');
    return;
  }
  
  if (coverImage.size > 5 * 1024 * 1024) {
    alert('Image must be less than 5MB');
    return;
  }
  
  // 2. Create form data
  const formData = new FormData();
  formData.append('price_points', pricePoints); // 0 for free
  formData.append('description', description);  // 10-2000 chars
  formData.append('category', category || '');  // Optional
  formData.append('tags', tags.join(',')); // Max 10 tags
  formData.append('cover_image', coverImage);
  
  // 3. Submit
  const response = await fetch(`/marketplace/tests/${testId}/publish`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${await user.getIdToken()}`
    },
    body: formData // Don't set Content-Type, browser handles it
  });
  
  const result = await response.json();
  console.log('Published:', result.data.version); // v1, v2, v3...
};
img.src = URL.createObjectURL(coverImage);
```

### Response
```json
{
  "success": true,
  "message": "Test published to marketplace successfully",
  "data": {
    "test_id": "507f1f77bcf86cd799439011",
    "version": "v1",
    "marketplace_config": {
      "is_public": true,
      "price_points": 100,
      "cover_image_url": "https://...",
      "thumbnail_url": "https://...",
      "description": "...",
      "category": "Science",
      "tags": ["physics", "grade-10"]
    },
    "is_first_publish": true
  }
}
```

---

## 2. Browsing Marketplace

### Endpoint
```
GET /marketplace/tests
```

### Frontend Implementation
```javascript
async function browseMarketplace({
  category = null,
  tag = null,
  minPrice = null,
  maxPrice = null,
  sortBy = 'newest', // newest|oldest|popular|top_rated|price_low|price_high
  search = null,
  page = 1,
  pageSize = 20
} = {}) {
  const params = new URLSearchParams({
    page,
    page_size: pageSize,
    sort_by: sortBy
  });
  
  if (category) params.append('category', category);
  if (tag) params.append('tag', tag);
  if (minPrice !== null) params.append('min_price', minPrice);
  if (maxPrice !== null) params.append('max_price', maxPrice);
  if (search) params.append('search', search);
  
  const response = await fetch(`/marketplace/tests?${params}`, {
    headers: {
      'Authorization': `Bearer ${await user.getIdToken()}` // Optional
    }
  });
  
  return await response.json();
}
```

### Response
```json
{
  "success": true,
  "data": {
    "tests": [
      {
        "test_id": "...",
        "title": "Math Quiz",
        "description": "...",
        "cover_image_url": "https://...",
        "thumbnail_url": "https://...",
        "category": "Math",
        "tags": ["algebra", "grade-10"],
        "price_points": 100,
        "total_purchases": 50,
        "avg_rating": 4.5,
        "rating_count": 20,
        "published_at": "2025-01-10T...",
        "creator": {
          "uid": "...",
          "display_name": "Teacher A"
        },
        "has_purchased": false
      }
    ],
    "pagination": {
      "page": 1,
      "page_size": 20,
      "total_items": 100,
      "total_pages": 5,
      "has_next": true,
      "has_prev": false
    }
  }
}
```

### UI Components
```jsx
// React Example
function MarketplaceCard({ test }) {
  return (
    <div className="test-card">
      <img src={test.thumbnail_url} alt={test.title} />
      <h3>{test.title}</h3>
      <p>{test.description}</p>
      
      <div className="meta">
        <span className="price">
          {test.price_points === 0 ? 'FREE' : `${test.price_points} points`}
        </span>
        <span className="rating">
          ⭐ {test.avg_rating.toFixed(1)} ({test.rating_count})
        </span>
        <span className="purchases">
          📥 {test.total_purchases} purchases
        </span>
      </div>
      
      <div className="creator">
        By {test.creator.display_name}
      </div>
      
      {test.has_purchased && (
        <span className="badge">✅ Owned</span>
      )}
      
      <button onClick={() => viewTest(test.test_id)}>
        View Details
      </button>
    </div>
  );
}
```

---

## 3. Test Detail Page

### Endpoint
```
GET /marketplace/tests/{test_id}
```

### Frontend Implementation
```javascript
async function getTestDetail(testId) {
  const response = await fetch(`/marketplace/tests/${testId}`, {
    headers: {
      'Authorization': `Bearer ${await user.getIdToken()}` // Optional
    }
  });
  
  return await response.json();
}
```

### Response (Not Purchased)
```json
{
  "success": true,
  "data": {
    "test_id": "...",
    "title": "Math Quiz",
    "description": "...",
    "cover_image_url": "https://...",
    "category": "Math",
    "tags": ["algebra"],
    "price_points": 100,
    "total_purchases": 50,
    "avg_rating": 4.5,
    "rating_count": 20,
    "published_at": "2025-01-10T...",
    "updated_at": "2025-01-10T...",
    "current_version": "v1",
    "creator": {
      "uid": "...",
      "display_name": "Teacher A"
    },
    "question_count": 20,
    "time_limit": 3600,
    "has_purchased": false,
    "is_creator": false,
    "sample_questions": [
      {
        "question_text": "What is 2+2?",
        "question_type": "multiple_choice",
        "options": ["2", "3", "4", "5"]
      }
      // First 3 questions only, NO correct answers
    ]
  }
}
```

---

## 4. Purchase Test

### Endpoint
```
POST /marketplace/tests/{test_id}/purchase
```

### Frontend Flow
```javascript
async function purchaseTest(testId) {
  // 1. Show confirmation dialog
  const confirmed = confirm(
    `Purchase this test for ${test.price_points} points?\n` +
    `Your balance: ${userBalance} points\n` +
    `After purchase: ${userBalance - test.price_points} points`
  );
  
  if (!confirmed) return;
  
  // 2. Submit purchase
  try {
    const response = await fetch(`/marketplace/tests/${testId}/purchase`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${await user.getIdToken()}`,
        'Content-Type': 'application/json'
      }
    });
    
    const result = await response.json();
    
    if (response.ok) {
      alert(`Test purchased! Version: ${result.data.version}`);
      // Redirect to test taking page
      window.location.href = `/tests/${testId}/take`;
    } else {
      alert(`Purchase failed: ${result.detail}`);
    }
  } catch (error) {
    alert('Purchase failed. Please try again.');
  }
}
```

### Response
```json
{
  "success": true,
  "message": "Test purchased successfully",
  "data": {
    "purchase_id": "...",
    "test_id": "...",
    "price_paid": 100,
    "creator_earnings": 80,    // 80% to creator
    "platform_fee": 20,        // 20% to platform
    "version": "v1",
    "purchased_at": "2025-01-10T..."
  }
}
```

### Error Handling
```javascript
// Common errors
400: "Insufficient points"          → Show top-up dialog
400: "You already purchased"        → Redirect to test
400: "Cannot purchase your own"     → Show error
404: "Test not found"                → 404 page
```

---

## 5. Rating & Commenting

### Submit Rating
```javascript
async function rateTest(testId, rating, comment) {
  const response = await fetch(`/marketplace/tests/${testId}/ratings`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${await user.getIdToken()}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      rating: rating,      // 1-5
      comment: comment     // Optional, max 1000 chars
    })
  });
  
  return await response.json();
}
```

### Fetch Ratings
```javascript
async function getRatings(testId, page = 1, sortBy = 'newest') {
  const params = new URLSearchParams({
    page,
    page_size: 20,
    sort_by: sortBy // newest|oldest|highest|lowest
  });
  
  const response = await fetch(`/marketplace/tests/${testId}/ratings?${params}`);
  return await response.json();
}
```

### Rating Component
```jsx
function RatingSection({ testId }) {
  const [ratings, setRatings] = useState([]);
  const [myRating, setMyRating] = useState(null);
  
  return (
    <div className="ratings">
      <h3>Ratings & Reviews</h3>
      
      {/* Submit rating (if purchased) */}
      <RatingForm testId={testId} onSubmit={refreshRatings} />
      
      {/* Display ratings */}
      {ratings.map(rating => (
        <div key={rating.rating_id} className="rating-card">
          <div className="stars">
            {'⭐'.repeat(rating.rating)}
          </div>
          <div className="user">{rating.user.display_name}</div>
          <div className="comment">{rating.comment}</div>
          <div className="date">{formatDate(rating.created_at)}</div>
        </div>
      ))}
      
      <button onClick={loadMore}>Load More</button>
    </div>
  );
}
```

---

## 6. Creator Earnings Dashboard

### Get Earnings
```javascript
async function getMyEarnings() {
  const response = await fetch('/marketplace/me/earnings', {
    headers: {
      'Authorization': `Bearer ${await user.getIdToken()}`
    }
  });
  
  return await response.json();
}
```

### Response
```json
{
  "success": true,
  "data": {
    "total_earnings": 12000,
    "test_count": 5,
    "tests": [
      {
        "test_id": "...",
        "title": "Math Quiz",
        "total_revenue": 8000,
        "total_purchases": 100,
        "avg_rating": 4.5
      }
    ]
  }
}
```

### Transfer to Wallet
```javascript
async function transferEarnings(amount) {
  const response = await fetch('/marketplace/me/earnings/transfer', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${await user.getIdToken()}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      amount_points: amount
    })
  });
  
  return await response.json();
}
```

### Earnings Dashboard
```jsx
function EarningsDashboard() {
  const [earnings, setEarnings] = useState(null);
  
  useEffect(() => {
    loadEarnings();
  }, []);
  
  async function handleTransfer() {
    const amount = parseInt(prompt('Amount to transfer:'));
    if (amount > earnings.total_earnings) {
      alert('Insufficient earnings');
      return;
    }
    
    const result = await transferEarnings(amount);
    if (result.success) {
      alert(`Transferred ${amount} points to wallet!`);
      loadEarnings();
    }
  }
  
  return (
    <div className="earnings-dashboard">
      <h2>Marketplace Earnings</h2>
      
      <div className="total">
        <h3>{earnings?.total_earnings || 0} points</h3>
        <button onClick={handleTransfer}>Transfer to Wallet</button>
      </div>
      
      <table>
        <thead>
          <tr>
            <th>Test</th>
            <th>Revenue</th>
            <th>Purchases</th>
            <th>Rating</th>
          </tr>
        </thead>
        <tbody>
          {earnings?.tests.map(test => (
            <tr key={test.test_id}>
              <td>{test.title}</td>
              <td>{test.total_revenue} pts</td>
              <td>{test.total_purchases}</td>
              <td>⭐ {test.avg_rating.toFixed(1)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

---

## 7. Update Marketplace Config

### Endpoint
```
PATCH /marketplace/tests/{test_id}/config
```

### Frontend Implementation
```javascript
async function updateConfig(testId, updates) {
  const response = await fetch(`/marketplace/tests/${testId}/config`, {
    method: 'PATCH',
    headers: {
      'Authorization': `Bearer ${await user.getIdToken()}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(updates)
  });
  
  return await response.json();
}

// Example: Update price
await updateConfig(testId, {
  price_points: 150,
  description: "Updated description"
});
```

---

## 8. Unpublish Test

### Endpoint
```
POST /marketplace/tests/{test_id}/unpublish
```

### Frontend Implementation
```javascript
async function unpublishTest(testId) {
  const confirmed = confirm('Hide this test from marketplace?');
  if (!confirmed) return;
  
  const response = await fetch(`/marketplace/tests/${testId}/unpublish`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${await user.getIdToken()}`
    }
  });
  
  return await response.json();
}
```

---

## Best Practices

### 1. Image Validation
Always validate on frontend before upload:
```javascript
function validateCoverImage(file) {
  return new Promise((resolve, reject) => {
    // Check file type
    if (!['image/jpeg', 'image/png'].includes(file.type)) {
      reject('Only JPEG and PNG allowed');
    }
    
    // Check file size
    if (file.size > 5 * 1024 * 1024) {
      reject('Image must be less than 5MB');
    }
    
    // Check dimensions
    const img = new Image();
    img.onload = () => {
      if (img.width < 800 || img.height < 600) {
        reject('Image must be at least 800x600 pixels');
      } else {
        resolve(true);
      }
    };
    img.onerror = () => reject('Invalid image file');
    img.src = URL.createObjectURL(file);
  });
}
```

### 2. Error Handling
```javascript
async function safeApiCall(apiFunction, ...args) {
  try {
    const result = await apiFunction(...args);
    if (!result.success) {
      throw new Error(result.message || 'API call failed');
    }
    return result.data;
  } catch (error) {
    if (error.response?.status === 401) {
      // Token expired, refresh
      await refreshToken();
      return safeApiCall(apiFunction, ...args);
    }
    throw error;
  }
}
```

### 3. Loading States
```jsx
function PurchaseButton({ test }) {
  const [loading, setLoading] = useState(false);
  
  async function handlePurchase() {
    setLoading(true);
    try {
      await purchaseTest(test.test_id);
    } catch (error) {
      alert(error.message);
    } finally {
      setLoading(false);
    }
  }
  
  return (
    <button onClick={handlePurchase} disabled={loading}>
      {loading ? 'Purchasing...' : `Buy for ${test.price_points} points`}
    </button>
  );
}
```

---

## Testing Checklist

### Before Production
- [ ] Test cover image upload (various sizes/formats)
- [ ] Test browse with all filters
- [ ] Test search functionality
- [ ] Test purchase flow (with/without sufficient points)
- [ ] Test rating submission
- [ ] Test earnings transfer
- [ ] Test update config
- [ ] Test unpublish
- [ ] Test error states (401, 400, 404)
- [ ] Test pagination
- [ ] Test on mobile devices

---

## Common Issues

### 1. "Authentication required"
- Ensure Firebase token is fresh (< 1 hour old)
- Check Authorization header format: `Bearer ${token}`

### 2. "Insufficient points"
- Show user's current balance before purchase
- Provide link to top-up points

### 3. "Cannot publish test with no questions"
- Validate test has questions before showing publish button

### 4. "Image too large"
- Validate file size on frontend before upload
- Provide image compression tool

### 5. CORS errors
- Contact backend team to add your domain to CORS whitelist

---

## Phase 6 Preview (Coming Soon)
- Point redemption (200 points = 100,000 VND)
- Banking info management
- Withdrawal requests
- Admin approval workflow

---

## Support
- Backend API docs: `/docs` (Swagger UI)
- Test with Postman: Import OpenAPI schema from `/openapi.json`
- Report bugs: Create issue in project repo
