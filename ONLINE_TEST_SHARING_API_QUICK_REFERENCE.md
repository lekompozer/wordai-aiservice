# Online Test Sharing API - Quick Reference (Phase 4 Simplified)

## Auto-Accept Sharing Model

Tests shared with users appear immediately in their list (no accept/decline needed).

---

## Core Endpoints

### 1. Share Test (Create Share)

**POST** `/api/v1/tests/{test_id}/share`

**Auth:** Required (owner only)

**Request:**
```json
{
  "sharee_emails": ["user1@example.com", "user2@example.com"],
  "deadline": "2025-12-31T23:59:59Z",  // Optional
  "message": "Please complete this test",  // Optional
  "send_email": true,  // Optional, default true
  "send_notification": true  // Optional, default true
}
```

**Response:**
```json
{
  "success": true,
  "message": "Test shared with 2 users",
  "shares": [
    {
      "share_id": "uuid",
      "test_id": "test_123",
      "sharer_id": "uid_abc",
      "sharee_email": "user1@example.com",
      "sharee_id": null,
      "status": "accepted",  // ✅ Auto-accepted!
      "accepted_at": "2025-01-03T10:00:00Z",
      "deadline": "2025-12-31T23:59:59Z",
      "message": "Please complete this test",
      "created_at": "2025-01-03T10:00:00Z"
    }
  ]
}
```

**Note:** Status is `"accepted"` immediately, not `"pending"`.

---

### 2. List Tests Shared With Me

**GET** `/api/v1/tests/shared-with-me`

**Auth:** Required

**Query Params:**
- `status` (optional): Filter by status (accepted/completed/expired/declined)

**Response:**
```json
[
  {
    "test_id": "test_123",
    "title": "JavaScript Basics",
    "num_questions": 10,
    "time_limit_minutes": 30,
    "sharer_name": "John Doe",
    "status": "accepted",
    "deadline": "2025-12-31T23:59:59Z",
    "has_completed": false,
    "share_id": "uuid",
    "created_at": "2025-01-03T10:00:00Z"
  }
]
```

**Usage:** Display list of tests shared with current user.

---

### 3. Delete Shared Test (User)

**DELETE** `/api/v1/tests/shared/{test_id}` 🆕

**Auth:** Required

**Response:**
```json
{
  "success": true,
  "message": "Shared test removed successfully"
}
```

**Note:**
- User removes test from their list (soft delete)
- Share status becomes `"declined"`
- Owner won't see this share anymore
- Cannot be undone - owner must re-share

**Usage:** User doesn't want to see/do this test.

---

### 4. Owner: List Shares for Test

**GET** `/api/v1/tests/{test_id}/shares`

**Auth:** Required (owner only)

**Response:**
```json
[
  {
    "share_id": "uuid",
    "sharee_email": "user@example.com",
    "sharee_name": "John Doe",
    "status": "accepted",
    "accepted_at": "2025-01-03T10:00:00Z",
    "deadline": "2025-12-31T23:59:59Z",
    "has_completed": false,
    "score": null
  }
]
```

**Usage:** Owner views who has access to test.

---

### 5. Owner: Revoke Share

**DELETE** `/api/v1/tests/{test_id}/shares/{share_id}`

**Auth:** Required (owner only)

**Response:**
```json
{
  "success": true,
  "message": "Share revoked successfully"
}
```

**Note:** User loses access to test.

---

### 6. Owner: Update Deadline

**PATCH** `/api/v1/tests/{test_id}/shares/{share_id}/deadline`

**Auth:** Required (owner only)

**Request:**
```json
{
  "deadline": "2025-12-31T23:59:59Z"  // Or null to remove
}
```

**Response:**
```json
{
  "success": true,
  "message": "Deadline updated successfully",
  "share": {
    "share_id": "uuid",
    "deadline": "2025-12-31T23:59:59Z"
  }
}
```

---

### 7. Check Access to Test

**GET** `/api/v1/tests/{test_id}/access`

**Auth:** Required

**Response:**
```json
{
  "has_access": true,
  "is_owner": false,
  "access_type": "shared",  // "owner" or "shared"
  "deadline": "2025-12-31T23:59:59Z",
  "status": "accepted"
}
```

**Usage:** Check if user can access test before showing UI.

---

## Status Flow

```
Share Created → accepted → completed
                        ↘ expired (deadline passed)
                        ↘ declined (user deleted)
```

**Status Meanings:**
- `accepted`: User has access (auto-accepted on share)
- `completed`: User finished test
- `expired`: Deadline passed
- `declined`: User deleted share OR owner revoked

**No more `pending` status!**

---

## Email Flow

### When Owner Shares:

1. **Share created** with `status="accepted"` ✅
2. **Email sent** to sharee (if `send_email=true`)
3. **In-app notification** created (if `send_notification=true`)
4. **Test appears** in user's "shared with me" list immediately

### Email Content:

**Subject:** "{Sharer} đã chia sẻ bài thi với bạn: {Title}"

**Button:** "🚀 Bắt đầu làm bài ngay"

**Link:** Direct to test: `https://wordai.pro/tests/{test_id}`

**No acceptance required!**

---

## Deadline Management

### 24h Reminder:
- Sent automatically 24h before deadline
- Only for `status="accepted"` and not completed
- Runs via cron job (hourly)

### Auto-Expiration:
- Share status → `"expired"` when deadline passes
- User loses access
- Runs via cron job (hourly)

---

## Access Control

### User Can Access Test If:
- ✅ User is owner (created test)
- ✅ User has accepted share (`status="accepted"`)
- ✅ Deadline hasn't passed (if deadline set)

### User Cannot Access Test If:
- ❌ Share status is `"declined"` or `"expired"`
- ❌ Deadline passed
- ❌ User not owner and no active share

---

## Frontend Integration

### Display Shared Tests:

```javascript
// Get tests shared with me
const response = await fetch('/api/v1/tests/shared-with-me', {
  headers: { 'Authorization': `Bearer ${token}` }
});
const sharedTests = await response.json();

// Display list
sharedTests.forEach(test => {
  // Show test card with:
  // - test.title
  // - test.num_questions
  // - test.sharer_name
  // - test.deadline (if exists)
  // - "Start Test" button → /tests/{test.test_id}
  // - "Delete" button → DELETE /tests/shared/{test.test_id}
});
```

### Delete Shared Test:

```javascript
async function deleteSharedTest(testId) {
  const response = await fetch(`/api/v1/tests/shared/${testId}`, {
    method: 'DELETE',
    headers: { 'Authorization': `Bearer ${token}` }
  });

  if (response.ok) {
    // Remove from UI
    alert('Test removed from your list');
  }
}
```

### Owner: View Shares:

```javascript
// Get shares for my test
const response = await fetch(`/api/v1/tests/${testId}/shares`, {
  headers: { 'Authorization': `Bearer ${token}` }
});
const shares = await response.json();

// Display who has access
shares.forEach(share => {
  // Show:
  // - share.sharee_name
  // - share.status
  // - share.deadline
  // - share.has_completed
  // - "Revoke" button
});
```

---

## Removed Endpoints ❌

These endpoints no longer exist:

- ~~GET `/invitations/{token}`~~ - Preview invitation
- ~~POST `/invitations/{token}/accept`~~ - Accept invitation
- ~~POST `/invitations/{token}/decline`~~ - Decline invitation

**Reason:** Auto-accept model doesn't need preview/accept/decline.

**Migration:** Remove from frontend code.

---

## Error Handling

### Common Errors:

**400 Bad Request:**
```json
{ "detail": "Invalid email format" }
{ "detail": "Cannot share test with yourself" }
```

**403 Forbidden:**
```json
{ "detail": "Only test owner can share" }
{ "detail": "You don't have access to this test" }
```

**404 Not Found:**
```json
{ "detail": "Test not found" }
{ "detail": "Shared test not found" }
```

**500 Internal Server Error:**
```json
{ "detail": "Failed to share test" }
```

---

## Best Practices

### Sharing:
✅ Always set a deadline for time-sensitive tests
✅ Add personal message to explain test purpose
✅ Check sharee email is correct before sending
✅ Use `send_email=true` to notify users

### User Experience:
✅ Show deadline prominently in UI
✅ Allow users to delete unwanted shares
✅ Show "shared by {name}" for context
✅ Indicate test completion status

### Owner Management:
✅ Regularly review share list
✅ Revoke access after deadline
✅ Extend deadline if needed
✅ Monitor completion rates

---

## Testing

### Test Share Flow:
```bash
# 1. Share test
curl -X POST https://api.wordai.pro/api/v1/tests/test_123/share \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "sharee_emails": ["user@example.com"],
    "deadline": "2025-12-31T23:59:59Z",
    "message": "Test message"
  }'

# 2. Check user's shared tests
curl https://api.wordai.pro/api/v1/tests/shared-with-me \
  -H "Authorization: Bearer $USER_TOKEN"

# 3. User deletes share
curl -X DELETE https://api.wordai.pro/api/v1/tests/shared/test_123 \
  -H "Authorization: Bearer $USER_TOKEN"
```

---

## FAQ

### Q: How do I preview a test before accepting?
**A:** No preview needed - test appears in your list immediately. Click to view details.

### Q: Can I decline a shared test?
**A:** Yes, use the DELETE endpoint to remove from your list.

### Q: Can I undo deleting a shared test?
**A:** No, deletion is permanent. Ask the owner to re-share.

### Q: What happens to old invitation links in emails?
**A:** They will 404 (not found). New shares use direct test links.

### Q: Can I share a test with someone who doesn't have an account?
**A:** Yes, share by email. They'll receive notification email and can sign up.

### Q: What's the difference between "revoke" and "delete"?
**A:**
- **Revoke** (owner): Owner removes user's access
- **Delete** (user): User removes test from their list

---

## Support

**Documentation:** See `ONLINE_TEST_IMPLEMENTATION_ROADMAP.md`
**Changes:** See `PHASE4_SIMPLIFICATION_CHANGES.md`
**Issues:** Contact development team

---

Last Updated: 2025-01-03
Version: 2.0 (Simplified)
