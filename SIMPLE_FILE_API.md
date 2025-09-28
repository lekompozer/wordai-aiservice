# Simple File Management API Documentation

This document provides a detailed guide for using the Simple File Management API, which allows for folder creation and file uploads to **private** R2 cloud storage with signed URL access.

**Base URLs:**
- **Production:** `https://ai.wordai.pro`
- **Development:** `http://localhost:8000`

**🔒 Security Model:**
- All files are stored in **private R2 storage** (not publicly accessible)
- File access requires **signed URLs** with expiration times
- Only authenticated users can generate download URLs for their files

**Authentication:**
All endpoints (except `/health`) require authentication. The API supports two authentication methods:

### Method 1: Bearer Token (Authorization Header)
```
Authorization: Bearer YOUR_FIREBASE_ID_TOKEN
```

### Method 2: Session Cookie
```
Cookie: wordai_session_cookie=YOUR_SESSION_COOKIE
```

**Authentication Priority:**
1. If `Authorization` header with Bearer token is present, it will be used first
2. If no Authorization header, the API will check for `wordai_session_cookie` in cookies
3. If neither is found, authentication will fail with HTTP 401

**Token Types Supported:**
- Firebase ID Tokens (from Firebase Auth SDK)
- Firebase Session Cookies (server-generated, longer-lived)

**Common Authentication Error Responses:**
```json
// 401 - No authentication provided
{
  "detail": "Authentication required. Provide Authorization header or session cookie."
}

// 401 - Invalid token
{
  "detail": "Invalid Firebase token"
}

// 401 - Expired token
{
  "detail": "Firebase token has expired"
}

// 401 - Revoked session
{
  "detail": "Session has been revoked"
}
```

---

## 1. Health Check

Checks the status of the API.

- **Endpoint:** `GET /api/simple-files/health`
- **Method:** `GET`
- **Authentication:** Not required

### Success Response (`200 OK`)
```json
{
  "status": "healthy",
  "service": "Simple File Management API",
  "timestamp": "2025-09-28T12:00:00.000Z"
}
```

---

## 2. Folder Management

### 2.1 Create a Folder

- **Endpoint:** `POST /api/simple-files/folders`
- **Method:** `POST`
- **Authentication:** Required

#### Request Body (`application/json`)
```json
{
  "name": "My Project Documents",
  "description": "Documents related to the new project.",
  "parent_id": "folder_abc123"
}
```
*Note: `description` and `parent_id` are optional. Omit `parent_id` to create a root folder.*

#### Success Response (`200 OK`)
```json
{
  "id": "folder_xyz789",
  "name": "My Project Documents",
  "description": "Documents related to the new project.",
  "parent_id": "folder_abc123",
  "user_id": "firebase_user_id",
  "created_at": "2025-09-28T12:00:00.000Z",
  "updated_at": "2025-09-28T12:00:00.000Z",
  "file_count": 0
}
```

### 2.2 List Folders

- **Endpoint:** `GET /api/simple-files/folders`
- **Method:** `GET`
- **Authentication:** Required

#### Query Parameters
- `parent_id` (optional): The ID of the parent folder to list sub-folders from. If omitted, lists root folders.

**Example URL:** `https://ai.wordai.pro/api/simple-files/folders?parent_id=folder_abc123`

#### Success Response (`200 OK`)
```json
[
  {
    "id": "folder_child456",
    "name": "Sub-folder 1",
    "description": null,
    "parent_id": "folder_abc123",
    "user_id": "firebase_user_id",
    "created_at": "2025-09-28T12:05:00.000Z",
    "updated_at": "2025-09-28T12:05:00.000Z",
    "file_count": 0
  }
]
```

### 2.3 Get Folder Details

- **Endpoint:** `GET /api/simple-files/folders/{folder_id}`
- **Method:** `GET`
- **Authentication:** Required

#### Success Response (`200 OK`)
Returns the same structure as the Create Folder response.

### 2.4 Update a Folder

- **Endpoint:** `PUT /api/simple-files/folders/{folder_id}`
- **Method:** `PUT`
- **Authentication:** Required

#### Request Body (`application/json`)
```json
{
  "name": "Updated Folder Name",
  "description": "Updated description."
}
```
*Both fields are optional.*

#### Success Response (`200 OK`)
Returns the updated folder object.

### 2.5 Delete a Folder

- **Endpoint:** `DELETE /api/simple-files/folders/{folder_id}`
- **Method:** `DELETE`
- **Authentication:** Required

#### Success Response (`200 OK`)
```json
{
  "success": true,
  "message": "Folder deleted successfully"
}
```

---

## 3. File Management

### 3.1 Upload a File

- **Endpoint:** `POST /api/simple-files/upload`
- **Method:** `POST`
- **Authentication:** Required
- **File Size Limit:** 10MB per file
- **Supported File Types:** PDF, DOCX, DOC, TXT, RTF

#### Request Body (`multipart/form-data`)
- `file`: The file to upload.
- `folder_id` (optional): The ID of the folder to upload the file into. If omitted, the file is placed in the root directory.

#### Success Response (`200 OK`)
```json
{
  "id": "file_123abc456def",
  "filename": "20250928_121000_My_Document.pdf",
  "original_name": "My Document.pdf",
  "file_type": ".pdf",
  "file_size": 102400,
  "folder_id": "folder_xyz789",
  "user_id": "firebase_user_id",
  "r2_key": "files/firebase_user_id/folder_xyz789/file_123abc456def/20250928_121000_My_Document.pdf",
  "private_url": "https://e13905a34ac218147b74fceb669e53c8.r2.cloudflarestorage.com/wordai/files/firebase_user_id/folder_xyz789/file_123abc456def/20250928_121000_My_Document.pdf",
  "download_url": "https://e13905a34ac218147b74fceb669e53c8.r2.cloudflarestorage.com/wordai/files/firebase_user_id/folder_xyz789/file_123abc456def/20250928_121000_My_Document.pdf?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=...",
  "created_at": "2025-09-28T12:10:00.000Z",
  "updated_at": "2025-09-28T12:10:00.000Z"
}
```

**Response Fields Explained:**
- `r2_key`: Internal storage key (for API reference only)
- `private_url`: Private R2 URL (not accessible without authorization)
- `download_url`: **Signed URL for temporary access (expires in 1 hour)**

#### Error Responses
```json
// 400 - Unsupported file type
{
  "detail": "File type not allowed. Supported: .pdf, .docx, .doc, .txt, .rtf"
}

// 400 - Invalid MIME type
{
  "detail": "MIME type not allowed. File: example.txt, Type: application/octet-stream"
}

// 500 - Upload failed
{
  "detail": "Upload failed: Storage service unavailable"
}
```

### 3.2 List Files in a Folder

- **Endpoint:** `GET /api/simple-files/files`
- **Method:** `GET`
- **Authentication:** Required

#### Query Parameters
- `folder_id` (optional): The ID of the folder to list files from. If omitted, lists files in the root directory.

#### Success Response (`200 OK`)
Returns a list of file objects with the same structure as the Upload File response.

### 3.3 List All Files for a User

- **Endpoint:** `GET /api/simple-files/files/all`
- **Method:** `GET`
- **Authentication:** Required

#### Success Response (`200 OK`)
Returns a list of all file objects for the authenticated user, across all folders.

### 3.4 Get File Details

- **Endpoint:** `GET /api/simple-files/files/{file_id}`
- **Method:** `GET`
- **Authentication:** Required

#### Success Response (`200 OK`)
Returns a single file object.

### 3.5 Delete a File

- **Endpoint:** `DELETE /api/simple-files/files/{file_id}`
- **Method:** `DELETE`
- **Authentication:** Required

#### Success Response (`200 OK`)
```json
{
  "success": true,
  "message": "File deleted successfully",
  "file_id": "file_123abc456def",
  "filename": "20250928_121000_My_Document.pdf"
}
```

### 3.6 Generate Download URL

Generate a new signed URL for file download (when the original expires).

- **Endpoint:** `POST /api/simple-files/files/{file_id}/generate-download-url`
- **Method:** `POST`
- **Authentication:** Required

#### Query Parameters
- `expiration` (optional): URL expiration time in seconds (default: 3600, min: 300, max: 86400)

#### Success Response (`200 OK`)
```json
{
  "success": true,
  "file_id": "file_123abc456def",
  "download_url": "https://e13905a34ac218147b74fceb669e53c8.r2.cloudflarestorage.com/wordai/files/firebase_user_id/folder_xyz789/file_123abc456def/20250928_121000_My_Document.pdf?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=...",
  "expires_in": 3600,
  "expires_at": "2025-09-28T13:10:00.000Z"
}
```

### 3.7 Download File (Redirect)

Generates a short-lived signed URL and immediately redirects the client to download the file. This is useful for direct download links.

- **Endpoint:** `GET /api/simple-files/files/{file_id}/download`
- **Method:** `GET`
- **Authentication:** Required

#### Success Response (`307 Temporary Redirect`)
The server will respond with a `307 Temporary Redirect` status, redirecting the browser to a temporary signed URL to download the file.

---

## 4. Client Usage Examples

### 4.1 JavaScript `fetch`

```javascript
const apiBaseUrl = 'https://ai.wordai.pro/api/simple-files';
const authToken = 'YOUR_FIREBASE_ID_TOKEN';

// 1. Create a folder
async function createFolder(name) {
  const response = await fetch(`${apiBaseUrl}/folders`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${authToken}`
    },
    body: JSON.stringify({ name: name })
  });
  return response.json();
}

// 2. Upload a file
async function uploadFile(file, folderId) {
  const formData = new FormData();
  formData.append('file', file);

  const response = await fetch(`${apiBaseUrl}/upload?folder_id=${folderId}`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${authToken}`
    },
    body: formData
  });
  return response.json();
}

// 3. List files in a folder
async function listFiles(folderId) {
  const response = await fetch(`${apiBaseUrl}/files?folder_id=${folderId}`, {
    headers: { 'Authorization': `Bearer ${authToken}` }
  });
  return response.json();
}

// 4. Get a new download URL
async function getDownloadUrl(fileId) {
    const response = await fetch(`${apiBaseUrl}/files/${fileId}/generate-download-url`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${authToken}` }
    });
    return response.json();
}

// 5. Trigger a direct download
function downloadFile(fileId) {
    // This URL requires authentication (e.g., session cookie) or can be opened in a new tab
    // where the user is already logged in.
    window.open(`${apiBaseUrl}/files/${fileId}/download`, '_blank');
}
```

### 4.2 cURL

```bash
# Upload file to specific folder
curl -X POST "https://ai.wordai.pro/api/simple-files/upload?folder_id=folder_123" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@document.pdf"

# List files in root folder
curl "https://ai.wordai.pro/api/simple-files/files" \
  -H "Authorization: Bearer YOUR_TOKEN"

# Create folder
curl -X POST "https://ai.wordai.pro/api/simple-files/folders" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "My Folder", "description": "Test folder"}'
```

---

## 5. File Storage Structure & Security

### Storage Architecture
Files are stored in **private Cloudflare R2 storage** with the following structure:

```
wordai-bucket/
└── files/
    └── {user_id}/
        ├── root/                    # Files without folder
        │   └── {file_id}/
        │       └── {timestamped_filename}
        └── {folder_id}/            # Files in specific folder
            └── {file_id}/
                └── {timestamped_filename}
```

**Example:**
```
files/firebase_user_123/folder_abc456/file_def789/20250928_121000_My_Document.pdf
```

### Security Model

#### Private Storage
- Files are **NOT publicly accessible**
- Direct R2 URLs require authentication
- Only authorized domains can access files

#### Signed URLs
- **Temporary access** through signed URLs (default: 1 hour expiration)
- Generated on-demand for authenticated users
- Automatically expire for security

#### Access Control
- Users can only access **their own files**
- Firebase authentication required for all operations
- File isolation by user ID

**Private URL Format (not accessible):**
```
https://e13905a34ac218147b74fceb669e53c8.r2.cloudflarestorage.com/wordai/files/{user_id}/{folder_id}/{file_id}/{filename}
```

**Signed URL Format (temporary access):**
```
https://e13905a34ac218147b74fceb669e53c8.r2.cloudflarestorage.com/wordai/files/{user_id}/{folder_id}/{file_id}/{filename}?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=...
```
