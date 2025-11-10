# 🐛 SECRET IMAGES SHARING BUG FIX - EMAIL vs UID

**Date:** November 10, 2025  
**Issue:** 403 "You don't have decryption key" when accessing newly created shares

---

## 🔍 ROOT CAUSE

**The Bug:** Email vs UID mismatch in storage and lookup

### Previous (BROKEN) Flow:

```
Share Creation:
1. Frontend sends recipientId = "user@example.com" (EMAIL)
2. Backend queries: db.users.find_one({"firebase_uid": "user@example.com"}) → NOT FOUND!
3. Backend saves: encrypted_file_keys["user@example.com"] = "key..."
4. Backend saves: file_shares.recipient_id = "user@example.com"

Access Flow:
1. User logs in → JWT token contains uid = "user_abc123"
2. Backend queries: file_shares.find_one({"recipient_id": {"$or": [owner_id, user_id]}})
3. MongoDB compares: "user@example.com" != "user_abc123" → NO MATCH!
4. Or if somehow passes, lookup: encrypted_file_keys["user_abc123"] → NOT FOUND!
5. ❌ 403 Error: "You don't have decryption key"
```

### The Mismatch:

- **Storage:** Used email as key in `encrypted_file_keys[email]`
- **Lookup:** Used uid from JWT to find `encrypted_file_keys[uid]`
- **Result:** Key not found → 403 error

---

## ✅ FIX IMPLEMENTED

### New (CORRECT) Flow:

```
Share Creation:
1. Frontend sends recipientId = "user@example.com" (EMAIL) ✅
2. Backend queries: db.users.find_one({"email": "user@example.com"}) ✅
3. Backend extracts: recipient_uid = user.uid (e.g., "user_abc123") ✅
4. Backend saves: encrypted_file_keys["user_abc123"] = "key..." ✅
5. Backend saves: file_shares.recipient_id = "user_abc123" ✅
6. Backend returns: {"recipient_id": "user@example.com"} (for frontend) ✅

Access Flow:
1. User logs in → JWT token contains uid = "user_abc123" ✅
2. Backend queries: file_shares.find_one({"recipient_id": "user_abc123"}) ✅
3. Share found! is_active=true, not expired ✅
4. Backend looks up: encrypted_file_keys["user_abc123"] ✅
5. Key found! Returns encryption metadata ✅
6. ✅ Success: User can decrypt and view image
```

---

## 📝 CODE CHANGES

### 1. Share Endpoint (`POST /{image_id}/share`)

**File:** `src/api/secret_images_routes.py` Lines 1437-1518

**Changes:**

```python
# BEFORE (BROKEN):
recipient = db["users"].find_one({"firebase_uid": request.recipientId})  # ❌ Wrong field
db["library_files"].update_one(
    {"library_id": image_id},
    {
        "$addToSet": {"shared_with": request.recipientId},  # ❌ Stores email
        "$set": {
            f"encrypted_file_keys.{request.recipientId}": ...,  # ❌ Uses email as key
        }
    }
)

# AFTER (FIXED):
recipient = db["users"].find_one({"email": request.recipientId})  # ✅ Find by email
recipient_uid = recipient.get("uid")  # ✅ Extract uid
recipient_email = request.recipientId  # ✅ Keep email for response

db["library_files"].update_one(
    {"library_id": image_id},
    {
        "$addToSet": {"shared_with": recipient_uid},  # ✅ Store uid
        "$set": {
            f"encrypted_file_keys.{recipient_uid}": ...,  # ✅ Use uid as key
        }
    }
)

existing_share = db["file_shares"].find_one({
    "owner_id": user_id,
    "recipient_id": recipient_uid,  # ✅ Use uid
    "file_id": image_id,
})

return {
    "recipient_id": recipient_email,  # ✅ Return email for frontend
    "share_id": share_id,
}
```

### 2. Revoke Endpoint (`DELETE /{image_id}/revoke-share/{recipient_email}`)

**File:** `src/api/secret_images_routes.py` Lines 1527-1604

**Changes:**

```python
# BEFORE (INCONSISTENT):
@router.delete("/{image_id}/revoke-share/{user_id_to_revoke}")  # Expected uid in path
async def revoke_secret_image_share(image_id: str, user_id_to_revoke: str, ...):
    # Directly used user_id_to_revoke (could be email or uid - inconsistent!)

# AFTER (CONSISTENT):
@router.delete("/{image_id}/revoke-share/{recipient_email}")  # Expect email in path
async def revoke_secret_image_share(image_id: str, recipient_email: str, ...):
    # Convert email → uid first
    recipient = db["users"].find_one({"email": recipient_email})
    recipient_uid = recipient.get("uid")
    
    # Use uid for database operations
    db["library_files"].update_one(
        {"library_id": image_id},
        {
            "$pull": {"shared_with": recipient_uid},
            "$unset": {f"encrypted_file_keys.{recipient_uid}": ""},
        }
    )
    
    db["file_shares"].update_one({
        "recipient_id": recipient_uid,  # Use uid
        ...
    })
```

### 3. Access Endpoint (No Changes Needed)

**File:** `src/api/share_routes.py` Lines 427-580

Already correct - uses uid from JWT token:

```python
user_id = user_data.get("uid")  # From JWT token
share = share_manager.get_share_by_id(share_id, user_id)

if share.get("recipient_id") != user_id:  # Compares uid with uid
    raise HTTPException(403)

encrypted_file_keys = library_file.get("encrypted_file_keys", {})
recipient_encrypted_key = encrypted_file_keys.get(user_id)  # Looks up by uid
```

---

## 🎯 KEY PRINCIPLES

### Data Flow:

1. **Frontend → Backend:** Always send **EMAIL** for recipient identification
2. **Backend Internal:** Always use **UID** for database storage
3. **Backend → Frontend:** Return **EMAIL** in responses (user-friendly)

### Storage Strategy:

```json
// library_files collection
{
  "library_id": "img_123",
  "owner_id": "owner_uid",
  "shared_with": ["recipient_uid"],  // ✅ Store UIDs
  "encrypted_file_keys": {
    "recipient_uid": "encrypted_key"  // ✅ Use UID as key
  }
}

// file_shares collection
{
  "share_id": "share_abc",
  "owner_id": "owner_uid",
  "recipient_id": "recipient_uid",  // ✅ Store UID
  "file_id": "img_123",
  "is_active": true
}

// users collection
{
  "uid": "user_abc123",  // ✅ Unique identifier
  "email": "user@example.com",  // ✅ User-friendly identifier
  "publicKey": "..."
}
```

### Lookup Strategy:

```python
# ✅ CORRECT: Email → UID → Storage
recipient = db.users.find_one({"email": email})
recipient_uid = recipient["uid"]
encrypted_file_keys[recipient_uid] = key

# ✅ CORRECT: JWT → UID → Lookup
user_id = jwt_token["uid"]
key = encrypted_file_keys[user_id]
```

---

## 🧪 TESTING

### Test Case 1: New Share

```bash
# 1. Share image
POST /api/library/secret-images/img_123/share
{
  "recipientId": "recipient@gmail.com",
  "encryptedFileKeyForRecipient": "base64_key...",
  "permission": "download"
}

# Expected: 200 OK
{
  "success": true,
  "share_id": "share_xyz",
  "recipient_id": "recipient@gmail.com"
}

# 2. Recipient accesses share
GET /api/shares/share_xyz/access
Authorization: Bearer <recipient_jwt_token>

# Expected: 200 OK (encryption metadata returned)
```

### Test Case 2: Revoke Share

```bash
DELETE /api/library/secret-images/img_123/revoke-share/recipient@gmail.com
Authorization: Bearer <owner_jwt_token>

# Expected: 200 OK

# 3. Recipient tries to access
GET /api/shares/share_xyz/access

# Expected: 403 Forbidden (share revoked)
```

---

## 📊 IMPACT

### Before Fix:
- ❌ All new shares failed with 403 error
- ❌ Users couldn't access shared secret images
- ❌ Email/UID mismatch caused key lookup failures

### After Fix:
- ✅ Share creation works correctly
- ✅ Recipients can access shared images
- ✅ Consistent email → uid conversion
- ✅ Proper uid-based storage and lookup

---

## 🔒 SECURITY

This fix maintains E2EE security:

1. **No key exposure:** Encrypted keys still stored per recipient
2. **Access control:** Only recipient uid can access their encrypted key
3. **JWT validation:** uid extracted from verified JWT token
4. **No email spoofing:** Email → uid conversion ensures correct user

---

## 📚 API DOCUMENTATION

### Share Endpoint

```
POST /api/library/secret-images/{image_id}/share

Request Body:
{
  "recipientId": "recipient@example.com",  // Email of recipient
  "encryptedFileKeyForRecipient": "base64_encrypted_key",
  "permission": "download"  // Optional, default: "download"
}

Response:
{
  "success": true,
  "message": "Secret image shared successfully",
  "recipient_id": "recipient@example.com",  // Email returned
  "share_id": "share_abc123"
}
```

### Revoke Endpoint

```
DELETE /api/library/secret-images/{image_id}/revoke-share/{recipient_email}

Path Parameters:
  image_id: Image ID
  recipient_email: Email of recipient (e.g., "user@example.com")

Response:
{
  "success": true,
  "message": "Access revoked successfully"
}
```

### Access Endpoint

```
GET /api/shares/{share_id}/access

Headers:
  Authorization: Bearer <firebase_token>

Response:
{
  "file_id": "img_123",
  "is_encrypted": true,
  "encrypted_file_key": "recipient's_encrypted_key",
  "encryption_iv_original": "iv1",
  "encryption_iv_thumbnail": "iv2",
  ...
}
```

---

## ✅ CHECKLIST

- [x] Share endpoint converts email → uid
- [x] Encrypted keys stored with uid as key
- [x] file_shares uses uid for recipient_id
- [x] Revoke endpoint accepts email and converts to uid
- [x] Access endpoint uses uid from JWT
- [x] Response returns email (user-friendly)
- [x] Logging includes both email and uid
- [x] Documentation updated
- [x] No compile errors

---

## 🚀 DEPLOYMENT

```bash
# 1. Commit changes
git add src/api/secret_images_routes.py
git commit -m "fix: Email vs UID mismatch in Secret Images sharing"

# 2. Push to main
git push origin main

# 3. Deploy to production
ssh root@104.248.147.155 "su - hoile -c 'cd /home/hoile/wordai && git pull && bash deploy-compose-with-rollback.sh'"
```

---

## 📝 NOTES

- **Frontend expects EMAIL** in request and response
- **Backend uses UID** for all database operations
- **JWT token contains UID** for authentication
- **Conversion happens at API boundary** (email → uid on input)
- **This ensures consistency** across all operations
