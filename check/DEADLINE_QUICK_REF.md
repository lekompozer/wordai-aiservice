# Global Deadline - Quick Reference

**Commit:** 8b1d4f4
**Status:** ✅ Ready to Deploy

---

## 🎯 Summary

Deadline is now **GLOBAL** (stored in `online_tests`), with optional per-user overrides.

---

## 📊 Database Schema

```javascript
// online_tests collection
{
  test_id: "test_123",
  title: "JavaScript Quiz",
  deadline: "2025-12-31T23:59:59Z",  // ✅ Global deadline (NEW!)
  time_limit_minutes: 30,
  max_retries: 3
}

// test_shares collection
{
  share_id: "uuid",
  test_id: "test_123",
  sharee_email: "user@example.com",
  deadline: "2026-01-15T23:59:59Z",  // ✅ Optional override
  status: "accepted"
}
```

---

## 🔄 Deadline Priority

```
1. test.deadline (global)
2. share.deadline (per-user override)
3. null (no deadline)
```

---

## 📝 API Changes

### POST `/tests/generate` & `/tests/manual`
```json
{
  "title": "Test Title",
  "deadline": "2025-12-31T23:59:59Z"  // ✅ NEW: Optional global deadline
}
```

### PATCH `/tests/{test_id}/config`
```json
{
  "deadline": "2026-01-31T23:59:59Z"  // ✅ NEW: Update global deadline
}
```

### POST `/tests/{test_id}/share`
```json
{
  "emails": ["user@example.com"],
  "deadline": null  // null = inherit test.deadline, or set custom override
}
```

**Logic:**
- If `request.deadline = null` → Uses `test.deadline` (global default)
- If `request.deadline = "2026-01-15..."` → Override for these users

---

## 🎨 Frontend Tasks

### 1. CreateManualTestModal
Add deadline picker:
```jsx
<DateTimePicker
  label="Deadline (Optional)"
  value={deadline}
  onChange={setDeadline}
  clearable
/>
```

### 2. TestConfigModal
Add deadline picker:
```jsx
<DateTimePicker
  label="Global Deadline"
  value={test.deadline}
  onChange={updateDeadline}
  clearable
/>
```

### 3. ShareTestModal
Add inherit/override option:
```jsx
<RadioGroup>
  <Radio value="inherit">
    Use test's deadline: {test.deadline || "No deadline"}
  </Radio>
  <Radio value="custom">
    Set custom deadline: <DateTimePicker />
  </Radio>
</RadioGroup>
```

---

## ✅ Testing

```bash
# 1. Create test with deadline
POST /tests/manual
{
  "title": "Math Quiz",
  "deadline": "2025-12-31T23:59:59Z"
}

# 2. Share test (inherits deadline)
POST /tests/{test_id}/share
{
  "emails": ["user1@example.com"],
  "deadline": null  // ← Uses test.deadline
}

# 3. Share test (override deadline)
POST /tests/{test_id}/share
{
  "emails": ["user2@example.com"],
  "deadline": "2026-06-30T23:59:59Z"  // ← Custom deadline
}

# 4. Update global deadline
PATCH /tests/{test_id}/config
{
  "deadline": "2026-01-31T23:59:59Z"
}
```

---

## 🚀 Deployment

```bash
# Already pushed to main (commit 8b1d4f4)
ssh root@104.248.147.155 "su - hoile -c 'cd /home/hoile/wordai && git pull && bash deploy-compose-with-rollback.sh'"
```

---

## 📚 Documentation

- Full guide: `docs/DEADLINE_GLOBAL_ARCHITECTURE.md`
- API spec: `docs/ONLINE_TEST_SHARING_API_SPEC.md`
- Old analysis: `docs/DEADLINE_FIELD_ANALYSIS.md`

---

**Status:** ✅ Backend Complete
**Next:** Frontend integration
