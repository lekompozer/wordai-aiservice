# Feedback & Review API Documentation

## Overview
Hệ thống review/feedback với reward points cho social sharing.

**Features:**
- ⭐ Rating 1-5 sao (bắt buộc)
- 💬 Feedback text (tùy chọn, max 500 ký tự)
- 🎁 Social sharing rewards: **5 điểm/ngày**
- 📱 4 nền tảng: Facebook, X/Twitter, LinkedIn, Copy Link
- ⏰ Giới hạn: 1 lần share/ngày

---

## Endpoints

### 1. Submit Review

**POST** `/api/v1/feedback/review`

Submit review và nhận điểm khi share lên mạng xã hội.

#### Headers
```
Authorization: Bearer {firebase_token}
```

#### Request Body
```json
{
  "rating": 5,
  "feedback_text": "WordAI rất tuyệt vời! Giúp tôi tiết kiệm nhiều thời gian.",
  "share_platform": "facebook"
}
```

**Fields:**
- `rating` (required): Integer 1-5
- `feedback_text` (optional): String, max 500 chars
- `share_platform` (optional): Enum: `"facebook"` | `"twitter"` | `"linkedin"` | `"copy"`

#### Response - Success (First Share Today)
```json
{
  "success": true,
  "message": "Cảm ơn bạn đã đánh giá! Bạn đã nhận 5 điểm.",
  "points_awarded": 5,
  "can_share_again_at": null,
  "review_id": "67a1234567890abcdef12345"
}
```

#### Response - Already Shared Today
```json
{
  "success": true,
  "message": "Cảm ơn bạn đã đánh giá! Bạn đã chia sẻ hôm nay. Quay lại ngày mai để nhận thêm điểm!",
  "points_awarded": 0,
  "can_share_again_at": "2026-01-08",
  "review_id": "67a1234567890abcdef12345"
}
```

#### Response - No Share (Rating Only)
```json
{
  "success": true,
  "message": "Cảm ơn bạn đã đánh giá!",
  "points_awarded": 0,
  "can_share_again_at": null,
  "review_id": "67a1234567890abcdef12345"
}
```

---

### 2. Check Share Status

**GET** `/api/v1/feedback/share-status`

Kiểm tra xem user có thể share hôm nay để nhận điểm không.

#### Headers
```
Authorization: Bearer {firebase_token}
```

#### Response - Can Share
```json
{
  "can_share_today": true,
  "last_share_date": "2026-01-06",
  "next_share_available": null,
  "total_shares": 3
}
```

#### Response - Already Shared Today
```json
{
  "can_share_today": false,
  "last_share_date": "2026-01-07",
  "next_share_available": "2026-01-08",
  "total_shares": 4
}
```

---

## Frontend Implementation

### Modal UI Flow

```tsx
// 1. Component State
const [rating, setRating] = useState(0);
const [feedback, setFeedback] = useState("");
const [shareStatus, setShareStatus] = useState<ShareStatus | null>(null);
const [isSubmitting, setIsSubmitting] = useState(false);

// 2. Fetch share status on mount
useEffect(() => {
  async function fetchStatus() {
    const response = await fetch('/api/v1/feedback/share-status', {
      headers: { Authorization: `Bearer ${firebaseToken}` }
    });
    const data = await response.json();
    setShareStatus(data);
  }
  fetchStatus();
}, []);

// 3. Submit review + share
async function handleShare(platform: 'facebook' | 'twitter' | 'linkedin' | 'copy') {
  if (rating === 0) {
    alert("Vui lòng chọn số sao!");
    return;
  }

  setIsSubmitting(true);
  
  const response = await fetch('/api/v1/feedback/review', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${firebaseToken}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      rating,
      feedback_text: feedback,
      share_platform: platform
    })
  });

  const result = await response.json();
  
  if (result.success) {
    if (result.points_awarded > 0) {
      toast.success(`🎁 Bạn đã nhận ${result.points_awarded} điểm!`);
    } else {
      toast.info(result.message);
    }
    
    // Open share window based on platform
    openShareWindow(platform, result.review_id);
  }
  
  setIsSubmitting(false);
}

// 4. Share window helpers
function openShareWindow(platform: string, reviewId: string) {
  const shareUrls = {
    facebook: `https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(window.location.origin)}`,
    twitter: `https://twitter.com/intent/tweet?text=${encodeURIComponent('Tôi vừa dùng WordAI - Công cụ AI tuyệt vời!')}&url=${encodeURIComponent(window.location.origin)}`,
    linkedin: `https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(window.location.origin)}`,
  };

  if (platform === 'copy') {
    const shareText = `Tôi vừa đánh giá ${rating} sao cho WordAI!\n${feedback}\n\n${window.location.origin}`;
    navigator.clipboard.writeText(shareText);
    toast.success("✅ Đã copy link chia sẻ!");
  } else {
    window.open(shareUrls[platform], '_blank', 'width=600,height=400');
  }
}
```

### UI Components

#### Rating Stars
```tsx
<div className="rating-stars">
  <span className="reward-banner">🎁 Nhận 5 điểm khi chia sẻ!</span>
  
  <div className="stars">
    {[1, 2, 3, 4, 5].map((star) => (
      <Star
        key={star}
        filled={star <= rating}
        onHover={() => setHoveredStar(star)}
        onClick={() => setRating(star)}
      />
    ))}
  </div>
</div>
```

#### Feedback Textarea
```tsx
<textarea
  placeholder="Chia sẻ trải nghiệm của bạn với WordAI (không bắt buộc)"
  value={feedback}
  onChange={(e) => setFeedback(e.target.value.slice(0, 500))}
  maxLength={500}
/>
<div className="char-count">{feedback.length}/500</div>
```

#### Share Buttons
```tsx
<div className="share-buttons">
  <button 
    onClick={() => handleShare('facebook')}
    disabled={rating === 0 || isSubmitting}
    className="share-btn facebook"
  >
    🔵 Facebook
    {shareStatus?.can_share_today && <span className="new-badge">+5 điểm</span>}
  </button>

  <button 
    onClick={() => handleShare('twitter')}
    disabled={rating === 0 || isSubmitting}
    className="share-btn twitter"
  >
    ⚫ X (Twitter)
    {shareStatus?.can_share_today && <span className="new-badge">+5 điểm</span>}
  </button>

  <button 
    onClick={() => handleShare('linkedin')}
    disabled={rating === 0 || isSubmitting}
    className="share-btn linkedin"
  >
    🔵 LinkedIn
    {shareStatus?.can_share_today && <span className="new-badge">+5 điểm</span>}
  </button>

  <button 
    onClick={() => handleShare('copy')}
    disabled={rating === 0 || isSubmitting}
    className="share-btn copy"
  >
    🟣 Copy Link
    {shareStatus?.can_share_today && <span className="new-badge">+5 điểm</span>}
  </button>
</div>

{!shareStatus?.can_share_today && (
  <div className="already-shared-notice">
    ✅ Bạn đã chia sẻ hôm nay. Quay lại vào {shareStatus?.next_share_available}!
  </div>
)}
```

---

## Share URL Templates

### Facebook
```
https://www.facebook.com/sharer/sharer.php?u=YOUR_URL
```

### X (Twitter)
```
https://twitter.com/intent/tweet?text=YOUR_TEXT&url=YOUR_URL
```

### LinkedIn
```
https://www.linkedin.com/sharing/share-offsite/?url=YOUR_URL
```

### Copy to Clipboard
```javascript
const shareText = `
Tôi vừa đánh giá ${rating} sao cho WordAI!
${feedback}

Thử ngay tại: ${window.location.origin}
`;
navigator.clipboard.writeText(shareText);
```

---

## Business Logic

### Points Reward Rules
1. **5 điểm** cho mỗi lần share thành công
2. **Giới hạn**: 1 lần share/ngày (00:00 - 23:59 Vietnam time)
3. **Không giới hạn** số lần rating (nhưng chỉ 1 lần reward/ngày)
4. **Tất cả 4 nền tảng** đều được tính là 1 lần share

### Share Detection
- Backend không kiểm tra người dùng có thực sự share không
- Frontend gửi `share_platform` khi user click nút share
- Backend trust frontend (có thể thêm verification sau)

### Timezone
- Vietnam timezone (UTC+7)
- Share limit reset at 00:00 VN time

---

## Error Handling

### 400 Bad Request
```json
{
  "detail": [
    {
      "loc": ["body", "rating"],
      "msg": "ensure this value is greater than or equal to 1",
      "type": "value_error.number.not_ge"
    }
  ]
}
```

### 401 Unauthorized
```json
{
  "detail": "Unauthorized"
}
```

### 500 Internal Server Error
```json
{
  "detail": "Failed to submit review: {error_message}"
}
```

---

## Database Schema

### Collection: `user_feedback`

```javascript
{
  _id: ObjectId("67a1234567890abcdef12345"),
  user_id: "firebase_uid_123",
  user_email: "user@example.com",
  rating: 5,
  feedback_text: "Rất tốt!",
  shared_platform: "facebook",  // null if not shared
  share_date: "2026-01-07",     // YYYY-MM-DD format
  shared_at: ISODate("2026-01-07T10:30:00Z"),
  created_at: ISODate("2026-01-07T10:30:00Z"),
  points_awarded: 5
}
```

### Indexes
- `user_id + shared_at` (share status lookup)
- `user_id + share_date` (daily limit check)
- `rating + created_at` (analytics)
- `shared_platform + created_at` (platform analytics)

---

## Testing

### Test Cases

1. **First review + share → Get 5 points** ✅
   ```bash
   POST /review { rating: 5, share_platform: "facebook" }
   → points_awarded: 5
   ```

2. **Second share same day → No points** ✅
   ```bash
   POST /review { rating: 4, share_platform: "twitter" }
   → points_awarded: 0, message: "đã chia sẻ hôm nay"
   ```

3. **Rating only (no share) → No points** ✅
   ```bash
   POST /review { rating: 5 }
   → points_awarded: 0
   ```

4. **Share next day → Get 5 points again** ✅
   ```bash
   # Next day
   POST /review { rating: 5, share_platform: "linkedin" }
   → points_awarded: 5
   ```

5. **Check share status** ✅
   ```bash
   GET /share-status
   → { can_share_today: false, next_share_available: "2026-01-08" }
   ```

---

## Production Deployment

1. **Create indexes:**
   ```bash
   python create_feedback_indexes.py
   ```

2. **Deploy:**
   ```bash
   ./deploy-compose-with-rollback.sh
   ```

3. **Verify endpoints:**
   ```bash
   curl https://api.wordai.vn/api/v1/feedback/share-status \
     -H "Authorization: Bearer YOUR_TOKEN"
   ```

---

## Analytics Queries

### Total reviews by rating
```javascript
db.user_feedback.aggregate([
  { $group: { _id: "$rating", count: { $sum: 1 } } },
  { $sort: { _id: 1 } }
])
```

### Shares by platform
```javascript
db.user_feedback.aggregate([
  { $match: { shared_platform: { $ne: null } } },
  { $group: { _id: "$shared_platform", count: { $sum: 1 } } }
])
```

### Daily share trends
```javascript
db.user_feedback.aggregate([
  { $match: { shared_platform: { $ne: null } } },
  { $group: { _id: "$share_date", shares: { $sum: 1 }, points: { $sum: "$points_awarded" } } },
  { $sort: { _id: -1 } }
])
```

---

## Notes

- ✅ Firebase auth required cho tất cả endpoints
- ✅ Points tự động cộng vào user account
- ✅ Không cần worker (sync processing)
- ✅ Timezone: Vietnam (UTC+7)
- ✅ Share limit reset lúc 00:00 VN time
- ⚠️ Không verify thực sự share (trust frontend)
- 💡 Có thể thêm webhook verification sau
