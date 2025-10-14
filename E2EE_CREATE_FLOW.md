# E2EE Secret Document Creation Flow

## 📋 Overview

Backend hỗ trợ **2 cách tạo secret document**:

1. **Auto-generate file_key** (Khuyến nghị cho new documents)
2. **Client-provided file_key** (Cho existing content)

---

## ✅ Option 1: Auto-generate file_key (RECOMMENDED)

### Use Case
- User clicks "New Secret Document"
- Document chưa có content (empty)
- Frontend không cần tạo file_key

### Client Flow

```typescript
// 1. User clicks "New Secret Document"
const response = await fetch('/api/secret-documents/create', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${firebaseToken}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    title: 'My Secret Document',
    documentType: 'doc',
    encryptedContent: '',  // Empty for new docs
    encryptionIv: '',       // Empty for new docs
    // NO encryptedFileKey - backend will generate!
  })
});

// 2. Backend response includes userEncryptedFileKey
const result = await response.json();
/*
{
  "success": true,
  "secret_id": "secret_abc123",
  "userEncryptedFileKey": "base64_rsa_encrypted_file_key",  // 🔑 Store this!
  "message": "Secret document created successfully"
}
*/

// 3. Store userEncryptedFileKey for later use
localStorage.setItem(`file_key_${result.secret_id}`, result.userEncryptedFileKey);

// 4. When user saves content, decrypt file_key and encrypt content
const encryptedFileKeyBase64 = result.userEncryptedFileKey;
const encryptedFileKeyBytes = base64ToBytes(encryptedFileKeyBase64);

// Decrypt file_key with private key
const fileKey = await rsaDecrypt(privateKey, encryptedFileKeyBytes);

// Encrypt content with file_key
const { encryptedContent, iv } = await aesEncrypt(fileKey, htmlContent);

// 5. Update document
await fetch(`/api/secret-documents/${result.secret_id}`, {
  method: 'PUT',
  body: JSON.stringify({
    encryptedContent: bytesToBase64(encryptedContent),
    encryptionIv: bytesToBase64(iv)
  })
});
```

### Backend Flow

```python
# 1. No encryptedFileKey provided
if encrypted_file_key is None:
    # 2. Get user's public key
    user = db.users.find_one({"firebase_uid": owner_id})
    owner_public_key = user["publicKey"]

    # 3. Generate random 32-byte AES-256 file key
    file_key = secrets.token_bytes(32)

    # 4. Encrypt file_key with RSA-OAEP
    encrypted_file_key = rsa_encrypt(owner_public_key, file_key)

# 5. Save to database
secret_doc = {
    "secret_id": "secret_abc123",
    "encrypted_content": "",  # Empty
    "encryption_iv": "",       # Empty
    "encrypted_file_keys": {
        owner_id: encrypted_file_key  # 🔑 Server-generated!
    }
}

# 6. Return with userEncryptedFileKey
return {
    "secret_id": secret_doc["secret_id"],
    "userEncryptedFileKey": encrypted_file_key  # Frontend needs this!
}
```

### Security Benefits
✅ File key generated with cryptographically secure random (`secrets.token_bytes`)
✅ File key never transmitted in plaintext
✅ Only encrypted file_key stored in database
✅ Only encrypted file_key sent to client
✅ Client must use private key to decrypt

---

## 🔄 Option 2: Client-provided file_key

### Use Case
- User has existing content to encrypt immediately
- Frontend already has crypto library
- Migrating from another system

### Client Flow

```typescript
// 1. User creates content
const htmlContent = '<p>Secret content</p>';

// 2. Generate random file key
const fileKey = crypto.getRandomValues(new Uint8Array(32));

// 3. Encrypt content with file key
const { encryptedContent, iv } = await aesEncrypt(fileKey, htmlContent);

// 4. Encrypt file key with public key
const encryptedFileKey = await rsaEncrypt(publicKey, fileKey);

// 5. Send to server
const response = await fetch('/api/secret-documents/create', {
  method: 'POST',
  body: JSON.stringify({
    title: 'My Secret Document',
    documentType: 'doc',
    encryptedContent: bytesToBase64(encryptedContent),
    encryptionIv: bytesToBase64(iv),
    encryptedFileKey: bytesToBase64(encryptedFileKey)  // 🔑 Client-provided
  })
});
```

### Backend Flow

```python
# 1. Client provided encryptedFileKey
if encrypted_file_key is not None:
    # Use client's encrypted file key
    pass

# 2. Save to database
secret_doc = {
    "secret_id": "secret_abc123",
    "encrypted_content": encrypted_content,  # Client-encrypted
    "encryption_iv": encryption_iv,           # Client-generated
    "encrypted_file_keys": {
        owner_id: encrypted_file_key  # 🔑 Client-provided!
    }
}
```

---

## 🔍 Key Differences

| Aspect | Auto-generate (Option 1) | Client-provided (Option 2) |
|--------|-------------------------|---------------------------|
| **File key creation** | Backend (`secrets.token_bytes`) | Frontend (Web Crypto API) |
| **Initial content** | Empty document | Has content |
| **Crypto complexity** | Minimal (only RSA decrypt) | Full (AES + RSA encrypt) |
| **Network calls** | 1 (create) then later (update) | 1 (create with content) |
| **Use case** | New documents | Convert existing |
| **Security** | ✅ Server-grade random | ✅ Browser crypto random |

---

## 📝 Updated API Specification

### POST /api/secret-documents/create

**Request Body:**
```typescript
{
  title: string;
  documentType: "doc" | "slide" | "note";
  encryptedContent?: string;     // Default: ""
  encryptionIv?: string;          // Default: ""
  encryptedFileKey?: string;      // Default: null (backend auto-generates)
  folderId?: string;
  tags?: string[];
}
```

**Response:**
```typescript
{
  success: true;
  secret_id: string;
  userEncryptedFileKey: string;  // 🔑 ALWAYS returned (auto-generated or echo)
  message: string;
}
```

---

## 🎯 Frontend Implementation Checklist

### For New Documents (Empty):
- [ ] Call `POST /create` with only `title` + `documentType`
- [ ] Store `userEncryptedFileKey` from response (localStorage/memory)
- [ ] When user saves, decrypt `userEncryptedFileKey` with private key
- [ ] Encrypt content with decrypted file_key
- [ ] Call `PUT /{secret_id}` with encrypted content

### For Existing Content:
- [ ] Generate file_key client-side
- [ ] Encrypt content with file_key
- [ ] Encrypt file_key with public key
- [ ] Call `POST /create` with all encrypted data
- [ ] Store `userEncryptedFileKey` from response (for consistency)

### For Loading Documents:
- [ ] Call `GET /{secret_id}` to get document
- [ ] Response includes `userEncryptedFileKey`
- [ ] Decrypt `userEncryptedFileKey` with private key → get file_key
- [ ] Decrypt `encryptedContent` with file_key → get HTML

### For Updating Documents:
- [ ] Use stored/loaded `userEncryptedFileKey`
- [ ] Decrypt with private key → get file_key
- [ ] Encrypt new content with file_key
- [ ] Call `PUT /{secret_id}` with new encrypted content
- [ ] **DO NOT** send `userEncryptedFileKey` (it doesn't change!)

---

## 🐛 Common Mistakes

### ❌ Mistake 1: Not storing userEncryptedFileKey
```typescript
// Wrong
const { secret_id } = await createSecret({ title: 'Doc' });
// Later: How to encrypt content? No file_key!
```

```typescript
// Correct
const { secret_id, userEncryptedFileKey } = await createSecret({ title: 'Doc' });
localStorage.setItem(`file_key_${secret_id}`, userEncryptedFileKey);
```

### ❌ Mistake 2: Sending userEncryptedFileKey on update
```typescript
// Wrong - Sending file_key on update
await fetch(`/api/secret-documents/${id}`, {
  method: 'PUT',
  body: JSON.stringify({
    encryptedContent,
    encryptionIv,
    encryptedFileKey: userEncryptedFileKey  // ❌ Don't send this!
  })
});
```

```typescript
// Correct - Only send new content
await fetch(`/api/secret-documents/${id}`, {
  method: 'PUT',
  body: JSON.stringify({
    encryptedContent,
    encryptionIv  // ✅ File key stays the same!
  })
});
```

### ❌ Mistake 3: Creating file_key on frontend unnecessarily
```typescript
// Wrong - For new empty documents
const fileKey = crypto.getRandomValues(new Uint8Array(32));
const encryptedFileKey = await rsaEncrypt(publicKey, fileKey);
await createSecret({
  title: 'Doc',
  encryptedFileKey  // ❌ Unnecessary! Backend can generate
});
```

```typescript
// Correct - Let backend handle it
const { userEncryptedFileKey } = await createSecret({
  title: 'Doc'
  // ✅ No encryptedFileKey - backend generates!
});
```

---

## 🔒 Security Notes

1. **File Key Rotation**: File key does NOT rotate on update. Same file_key used for document lifetime.
2. **Server-side Generation**: When backend generates file_key, it uses `secrets.token_bytes(32)` (CSPRNG).
3. **No Plaintext**: File key NEVER stored/transmitted in plaintext.
4. **Access Control**: `encrypted_file_keys` dict contains one entry per user with access.
5. **Sharing**: When sharing, encrypt file_key with recipient's public key, add to dict.

---

## 📊 Database Schema

```javascript
{
  "_id": ObjectId("..."),
  "secret_id": "secret_abc123",
  "owner_id": "firebase_uid_123",
  "title": "My Document",  // Plaintext (for listing)
  "document_type": "doc",

  // E2EE Data
  "encrypted_content": "base64_aes_encrypted...",  // Can be empty
  "encryption_iv": "base64_iv...",                  // Can be empty
  "encrypted_file_keys": {
    "firebase_uid_123": "base64_rsa_encrypted_key",  // Always present
    "firebase_uid_456": "base64_rsa_encrypted_key"   // If shared
  },

  // Metadata
  "created_at": ISODate("..."),
  "updated_at": ISODate("..."),
  "is_trashed": false
}
```

---

## 🎬 Complete Example

```typescript
// ========== PHASE 1: CREATE EMPTY DOCUMENT ==========
async function createEmptySecretDocument(title: string) {
  const response = await fetch('/api/secret-documents/create', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${firebaseToken}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      title,
      documentType: 'doc'
      // No content, no IV, no fileKey!
    })
  });

  const result = await response.json();

  // Store for later
  localStorage.setItem(
    `file_key_${result.secret_id}`,
    result.userEncryptedFileKey
  );

  return result.secret_id;
}

// ========== PHASE 2: SAVE CONTENT ==========
async function saveSecretContent(secretId: string, htmlContent: string) {
  // 1. Get stored encrypted file key
  const encryptedFileKeyBase64 = localStorage.getItem(`file_key_${secretId}`);
  if (!encryptedFileKeyBase64) {
    throw new Error('File key not found! Document was not properly created.');
  }

  // 2. Decrypt file key with private key
  const encryptedFileKeyBytes = base64ToBytes(encryptedFileKeyBase64);
  const fileKey = await rsaDecrypt(privateKey, encryptedFileKeyBytes);

  // 3. Encrypt content with file key
  const { encryptedContent, iv } = await aesEncrypt(fileKey, htmlContent);

  // 4. Send to server
  await fetch(`/api/secret-documents/${secretId}`, {
    method: 'PUT',
    headers: {
      'Authorization': `Bearer ${firebaseToken}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      encryptedContent: bytesToBase64(encryptedContent),
      encryptionIv: bytesToBase64(iv)
      // NO encryptedFileKey!
    })
  });
}

// ========== PHASE 3: LOAD DOCUMENT ==========
async function loadSecretDocument(secretId: string) {
  // 1. Fetch document
  const response = await fetch(`/api/secret-documents/${secretId}`, {
    headers: { 'Authorization': `Bearer ${firebaseToken}` }
  });

  const doc = await response.json();

  // 2. Check if document has content
  if (!doc.encryptedContent) {
    return { html: '', isEmpty: true };  // Empty document
  }

  // 3. Get file key
  const encryptedFileKeyBase64 = doc.userEncryptedFileKey;
  const encryptedFileKeyBytes = base64ToBytes(encryptedFileKeyBase64);

  // 4. Decrypt file key
  const fileKey = await rsaDecrypt(privateKey, encryptedFileKeyBytes);

  // 5. Decrypt content
  const encryptedContentBytes = base64ToBytes(doc.encryptedContent);
  const ivBytes = base64ToBytes(doc.encryptionIv);
  const htmlContent = await aesDecrypt(fileKey, encryptedContentBytes, ivBytes);

  return { html: htmlContent, isEmpty: false };
}

// ========== USAGE ==========
// Create
const secretId = await createEmptySecretDocument('My Secret Doc');
console.log('Created:', secretId);

// Edit and save
const htmlContent = '<p>Secret content here</p>';
await saveSecretContent(secretId, htmlContent);
console.log('Saved!');

// Load
const { html, isEmpty } = await loadSecretDocument(secretId);
console.log('Content:', html);
```

---

## 🚀 Deployment Notes

- ✅ Backend change is **backward compatible**
- ✅ Old clients still work (providing `encryptedFileKey`)
- ✅ New clients benefit from auto-generation
- ✅ No database migration needed
- ✅ No breaking changes to existing endpoints

---

## 📚 Related Documentation

- `docs/E2EE_FRONTEND_TECH_SPEC.md` - Complete E2EE setup guide
- `src/api/secret_document_routes.py` - API implementation
- `src/services/secret_document_manager.py` - Service layer logic
