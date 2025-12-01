# Book Sharing & Permissions API

**Version:** 1.0
**Last Updated:** December 2, 2025
**Base URL:** `https://ai.wordai.pro/api/v1/books`

---

## Overview

This API allows book owners to share their books with other users. There are two main ways to share:

1.  **Private Sharing (Permissions):** Invite specific users by email or ID to access a private book.
2.  **Public Sharing:** Make the book public so anyone with the link can view it.

---

## 1. Public Sharing (View Book)

**Endpoint:** `GET /public/guides/{slug}`

**Authentication:** None (Public)

**Purpose:** View a book that has been set to `public` visibility. This is the endpoint used for public sharing links.

**Path Parameters:**
- `slug`: The unique URL slug of the book (e.g., `my-awesome-guide`).

**Success Response (200 OK):**
Returns the full book details including chapters.

---

## 2. Invite User (Private Share by Email)

**Endpoint:** `POST /{book_id}/permissions/invite`

**Authentication:** Required (Book Owner only)

**Purpose:** The primary method for sharing. Sends an email invitation to the recipient. If the user already exists, they get access immediately. If not, the permission is stored and linked when they sign up with that email.

**Request Body:**

```json
{
  "email": "colleague@example.com",
  "access_level": "viewer",
  "expires_at": "2025-12-31T23:59:59Z",
  "message": "Check out this guide I wrote!"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `email` | string | ✅ Yes | Recipient's email address. |
| `access_level` | string | ❌ No | `viewer` (default) or `editor`. |
| `expires_at` | datetime | ❌ No | ISO 8601 timestamp for access expiration. |
| `message` | string | ❌ No | Personal message included in the email (max 500 chars). |

**Success Response (201 Created):**

```json
{
  "invitation": {
    "permission_id": "perm_123456789",
    "book_id": "book_abc123",
    "user_id": "pending_user_id",
    "granted_by": "user_owner_id",
    "access_level": "viewer",
    "invited_email": "colleague@example.com",
    "invitation_accepted": false,
    "created_at": "2025-12-02T10:00:00Z"
  },
  "email_sent": true,
  "message": "Invitation sent successfully"
}
```

**Error Responses:**
- `403 Forbidden`: Only the book owner can invite users.
- `404 Not Found`: Book ID does not exist.
- `500 Internal Server Error`: Email sending failed.

---

## 3. Grant Permission (Direct)

**Endpoint:** `POST /{book_id}/permissions/users`

**Authentication:** Required (Book Owner only)

**Purpose:** Grant access directly to a known User ID (Firebase UID). Useful for internal tools or when the User ID is already known.

**Request Body:**

```json
{
  "user_id": "firebase_uid_of_recipient",
  "access_level": "viewer",
  "expires_at": null
}
```

**Success Response (201 Created):**

```json
{
  "permission_id": "perm_987654321",
  "book_id": "book_abc123",
  "user_id": "firebase_uid_of_recipient",
  "access_level": "viewer",
  "created_at": "2025-12-02T10:05:00Z"
}
```

---

## 4. List Permissions

**Endpoint:** `GET /{book_id}/permissions/users`

**Authentication:** Required (Book Owner only)

**Purpose:** View all users who have access to the book.

**Query Parameters:**
- `skip`: Offset (default 0)
- `limit`: Limit (default 50)

**Success Response (200 OK):**

```json
{
  "permissions": [
    {
      "permission_id": "perm_123",
      "user_id": "user_456",
      "invited_email": "user@example.com",
      "access_level": "viewer",
      "created_at": "..."
    }
  ],
  "total": 1
}
```

---

## 5. Revoke Permission

**Endpoint:** `DELETE /{book_id}/permissions/users/{user_id}`

**Authentication:** Required (Book Owner only)

**Purpose:** Remove a user's access to the book.

**Path Parameters:**
- `book_id`: ID of the book.
- `user_id`: Firebase UID of the user to remove (or the temporary ID for pending invitations).

**Success Response (200 OK):**

```json
{
  "message": "Permission revoked successfully",
  "revoked": {
    "book_id": "book_abc123",
    "user_id": "user_456",
    "revoked_by": "user_owner_id"
  }
}
```

---

## Integration Notes

1.  **Email Service:** The invitation endpoint relies on the Brevo email service. Ensure the backend has valid Brevo credentials configured.
2.  **Pending Invitations:** If a user is invited by email but hasn't registered, the system creates a placeholder permission. When they register with that email, the system should link the permission to their new User ID (this logic is handled in the `Auth` or `PermissionManager` service).
3.  **Access Control:** The `GET /api/v1/books/{book_id}` endpoint automatically checks these permissions. If a book is `private`, only the owner and users with valid permissions can view it.
