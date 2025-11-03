# Deadline Management - Phase 4 Online Test Sharing

## Implementation Strategy: Real-time Check (No Cronjob)

### ✅ Decision: NO CRONJOB NEEDED

**Rationale:**
- Deadline is checked in real-time when user accesses test
- Auto-expire happens on-demand when deadline passed
- Simpler deployment (no crontab setup required)
- Instant feedback to users

---

## How It Works

### 1. Deadline Check on Every Access

**Location:** `src/api/online_test_routes.py` - `check_test_access()` function

**Flow:**
```
User tries to access test
  ↓
Check if user has shared access
  ↓
Check if share has deadline
  ↓
If deadline passed:
  - Update share status: "accepted" → "expired"
  - Return 403 error: "Deadline has passed"
  ↓
If deadline not passed or no deadline:
  - Allow access
```

**Code Reference (lines 111-126):**
```python
# Check deadline
deadline = share.get("deadline")
if deadline:
    if deadline.tzinfo is None:
        from datetime import timezone
        deadline = deadline.replace(tzinfo=timezone.utc)

    if deadline < datetime.now(deadline.tzinfo):
        # Auto-expire
        sharing_service.db.test_shares.update_one(
            {"share_id": share["share_id"]},
            {"$set": {"status": "expired"}}
        )
        raise HTTPException(
            status_code=403,
            detail="Access denied: Deadline has passed for this shared test",
        )
```

### 2. When Deadline is Checked

**Endpoints that check deadline:**

1. **GET /api/v1/tests/{test_id}**
   - View test details
   - Called by: `check_test_access()`
   - Result: 403 if deadline passed

2. **POST /api/v1/tests/{test_id}/start**
   - Start taking test
   - Called by: `check_test_access()`
   - Result: 403 if deadline passed, cannot start

3. **POST /api/v1/tests/{test_id}/submit**
   - Submit test answers
   - Called by: `check_test_access()`
   - Result: 403 if deadline passed, cannot submit

### 3. User Experience

**Before Deadline:**
```
User → View test → ✅ Can see questions
User → Start test → ✅ Can start
User → Submit test → ✅ Can submit
```

**After Deadline:**
```
User → View test → ❌ 403: "Deadline has passed"
User → Start test → ❌ 403: "Deadline has passed"
User → Submit test → ❌ 403: "Deadline has passed"
```

**Status Change:**
- Share status automatically changes: `accepted` → `expired`
- User loses access immediately
- Owner sees expired share in their share list

---

## Benefits vs Cronjob Approach

### ✅ Real-time Check (Current)

**Pros:**
- ✅ No deployment complexity (no crontab)
- ✅ Instant feedback when user tries to access
- ✅ No background job overhead
- ✅ Accurate to the second (not hourly)
- ✅ Simpler codebase (one less script)

**Cons:**
- ⚠️ Status not updated until user tries to access
- ⚠️ Owner sees "accepted" shares that are actually expired (until sharee tries to access)

### ❌ Cronjob Approach (Alternative - NOT USED)

**Pros:**
- ✅ Proactive status updates
- ✅ Owner sees accurate share statuses
- ✅ Can send reminder emails (24h before deadline)

**Cons:**
- ❌ Requires crontab setup on server
- ❌ Additional deployment step
- ❌ Background job complexity
- ❌ Hourly granularity only
- ❌ More code to maintain

---

## Owner View Consideration

**Current Behavior:**
- Owner views shares: Shows `status="accepted"` even if deadline passed
- When sharee tries to access: Status changes to `expired`
- Owner sees updated status after sharee's access attempt

**Alternative (if needed later):**
- Add button "Refresh expired shares" for owner
- Manually check and update expired shares
- Or add small cronjob just for this (optional)

**Decision:** Keep simple for now. Real-time check is sufficient.

---

## Reminder Emails - NOT IMPLEMENTED

**Original Plan:**
- Send email 24h before deadline
- Requires cronjob to check daily

**Current Status:**
- ❌ Not implemented (requires cronjob)
- ✅ Can add later if needed

**Alternative:**
- Frontend can show countdown: "2 days until deadline"
- In-app notification when sharing (deadline in message)
- Email on share includes deadline prominently

---

## Database Status Values

### Share Status Lifecycle

```
Created → accepted (immediate)
           ↓
  User completes test
           ↓
       completed
           ↓
   (stays completed)

OR

Created → accepted
           ↓
  Deadline passed + User tries access
           ↓
        expired
           ↓
   (stays expired)

OR

Created → accepted
           ↓
  User deletes share
           ↓
       declined
           ↓
   (stays declined)
```

### Status Meanings

| Status | Description | Can Access? | How It Happens |
|--------|-------------|-------------|----------------|
| accepted | Active share | ✅ Yes (if no deadline or not passed) | Auto on share creation |
| completed | Test finished | ✅ Yes (view results) | User submits test |
| expired | Deadline passed | ❌ No | User tries access after deadline |
| declined | Share removed | ❌ No | User deletes OR owner revokes |

---

## Testing Checklist

### Test Deadline Enforcement:

1. **No Deadline:**
   - ✅ Share test without deadline
   - ✅ User can access anytime
   - ✅ No expiration

2. **Deadline in Future:**
   - ✅ Share test with deadline (tomorrow)
   - ✅ User can access now
   - ✅ User can start and submit

3. **Deadline Passed:**
   - ✅ Share test with deadline (1 hour ago)
   - ✅ User tries to view → 403 error
   - ✅ User tries to start → 403 error
   - ✅ User tries to submit → 403 error
   - ✅ Share status → "expired"

4. **Edge Case - Deadline During Test:**
   - ✅ User starts test before deadline
   - ✅ Deadline passes while taking test
   - ✅ User tries to submit → 403 error
   - ✅ Progress saved (test_progress)
   - ✅ User cannot resume

### Owner View:

1. **List Shares:**
   - ✅ Show all shares with status
   - ✅ Expired shares show as "expired" (after sharee tries access)
   - ✅ Can revoke any share

2. **Update Deadline:**
   - ✅ Extend deadline → User regains access
   - ✅ Shorten deadline → User may lose access

---

## Future Enhancements (Optional)

### If Needed Later:

1. **Manual Expire Button (Owner):**
   ```
   POST /api/v1/tests/{test_id}/shares/expire-deadlines
   - Owner manually expires all past-deadline shares
   - Updates statuses immediately
   ```

2. **Reminder Emails:**
   ```
   - Add lightweight cronjob (daily, not hourly)
   - Send reminder 24h before deadline
   - Requires scripts/send_deadline_reminders.py
   ```

3. **Auto-refresh Owner View:**
   ```
   - Frontend button: "Check expired shares"
   - Calls backend to update all expired statuses
   - No cronjob needed
   ```

4. **Grace Period:**
   ```
   - Allow 15min grace period after deadline
   - For users who are mid-test
   - Configurable per share
   ```

---

## Deployment Notes

### No Additional Steps Required

**Standard Deployment:**
```bash
git push origin main
ssh root@server "deploy script"
```

**No Crontab Setup:**
- ❌ No cron job to configure
- ❌ No background process to monitor
- ✅ Just API endpoints

**Database:**
- ✅ test_shares collection initialized
- ✅ Indexes created
- ✅ TTL index for auto-cleanup (90 days)

---

## Summary

**Deadline Management Strategy:**
- ✅ Real-time check on every access
- ✅ Auto-expire when deadline passed
- ✅ Simple implementation
- ✅ No cronjob required
- ✅ Production ready

**When User Accesses Test:**
1. Check if shared
2. Check deadline
3. If passed → expire + deny access
4. If not passed → allow access

**Status Updates:**
- Lazy (on-demand) not eager (background)
- Updated when user tries to access
- Accurate and instant

🎯 **Result:** Simpler, cleaner, easier to deploy!

---

**Last Updated:** November 3, 2025
**Author:** Development Team
**Status:** ✅ Implemented and Deployed
