# Payment Information & Contact Form API Technical Specification

**Version:** 1.0
**Last Updated:** December 1, 2025
**Base URL:** `https://ai.wordai.pro`

---

## Overview

This document specifies three new API endpoints for the WordAI platform:
- **Payment Information Management** (2 endpoints) - For marketplace creators to set up bank account details for earnings withdrawal
- **Contact Form Submission** (1 endpoint) - Public endpoint for wordai.pro homepage contact form

These endpoints support the marketplace earnings withdrawal system and homepage lead generation.

---

## Endpoints Summary

| Method | Endpoint | Auth Required | Purpose |
|--------|----------|---------------|---------|
| POST | `/api/v1/tests/me/payment-info` | ✅ Yes | Set/update payment information |
| GET | `/api/v1/tests/me/payment-info` | ✅ Yes | Retrieve payment information |
| POST | `/api/v1/public/contact` | ❌ No | Submit contact form from wordai.pro |

---

## 1. Payment Information Management

### 1.1 Set Payment Information

**Endpoint:** `POST /api/v1/tests/me/payment-info`

**Authentication:** Required (Firebase ID Token)

**Purpose:** Allow marketplace creators to set up or update their bank account information for earnings withdrawal. This information will be used by admin to transfer funds when processing withdrawal requests.

**Request Headers:**
```
Authorization: Bearer <firebase_id_token>
Content-Type: application/json
```

**Request Body Schema:**

| Field | Type | Required | Validation | Description |
|-------|------|----------|------------|-------------|
| `account_holder_name` | string | ✅ Yes | 2-100 characters | Tên chủ tài khoản (exact match required for bank transfer) |
| `account_number` | string | ✅ Yes | 6-30 characters | Số tài khoản ngân hàng |
| `bank_name` | string | ✅ Yes | 2-100 characters | Tên ngân hàng (e.g., "Vietcombank", "Techcombank", "BIDV") |
| `bank_branch` | string | ❌ Optional | Max 100 characters | Chi nhánh ngân hàng |

**Success Response (200):**
```json
{
  "success": true,
  "message": "Thông tin thanh toán đã được cập nhật thành công",
  "payment_info": {
    "account_holder_name": "Nguyen Van A",
    "account_number": "1234567890",
    "bank_name": "Vietcombank",
    "bank_branch": "Ho Chi Minh"
  }
}
```

**Error Responses:**

| Status Code | Description |
|-------------|-------------|
| 400 | Validation error (invalid field format or length) |
| 401 | Unauthorized (missing or invalid Firebase token) |
| 404 | User not found in database |
| 500 | Internal server error |

**Business Rules:**
- Users can update their payment info multiple times
- Previous payment info is overwritten (no history kept)
- Payment info is required before requesting earnings withdrawal
- Stored securely in user profile under `payment_info` field
- Only the account owner can view/update their payment info
- Admin can only view payment info when processing withdrawals

**Security Considerations:**
- Payment information is stored in user document (not encrypted)
- Only accessible by the authenticated user and admin
- No PII beyond banking details is stored
- Bank account details are verified by admin during manual transfer

---

### 1.2 Get Payment Information

**Endpoint:** `GET /api/v1/tests/me/payment-info`

**Authentication:** Required (Firebase ID Token)

**Purpose:** Retrieve the user's saved payment information. Used to check if payment info is set up before allowing withdrawal requests.

**Request Headers:**
```
Authorization: Bearer <firebase_id_token>
```

**Success Response (200) - Payment Info Exists:**
```json
{
  "success": true,
  "has_payment_info": true,
  "payment_info": {
    "account_holder_name": "Nguyen Van A",
    "account_number": "1234567890",
    "bank_name": "Vietcombank",
    "bank_branch": "Ho Chi Minh",
    "updated_at": "2025-12-01T10:30:00Z"
  }
}
```

**Success Response (200) - No Payment Info:**
```json
{
  "success": true,
  "has_payment_info": false,
  "payment_info": null,
  "message": "Chưa thiết lập thông tin thanh toán"
}
```

**Error Responses:**

| Status Code | Description |
|-------------|-------------|
| 401 | Unauthorized (missing or invalid Firebase token) |
| 404 | User not found in database |
| 500 | Internal server error |

**Business Rules:**
- Returns `has_payment_info: false` if user has never set up payment info
- Frontend should use `has_payment_info` flag to show setup form or withdrawal form
- `updated_at` field shows last modification timestamp (UTC)

---

## 2. Contact Form Submission

### 2.1 Submit Contact Form

**Endpoint:** `POST /api/v1/public/contact`

**Authentication:** Not Required (Public endpoint)

**Purpose:** Accept contact form submissions from wordai.pro homepage `/contact` page. Stores the request in database and sends immediate email notification to admin for follow-up.

**Request Headers:**
```
Content-Type: application/json
```

**Request Body Schema:**

| Field | Type | Required | Validation | Description |
|-------|------|----------|------------|-------------|
| `full_name` | string | ✅ Yes | 2-100 characters | Họ và tên người liên hệ |
| `email` | string (email) | ✅ Yes | Valid email format | Email liên hệ (must be valid email) |
| `phone` | string | ❌ Optional | Max 20 characters | Số điện thoại (e.g., "+84 123 456 789") |
| `company` | string | ❌ Optional | Max 100 characters | Tên công ty/tổ chức |
| `purpose` | string (enum) | ✅ Yes | See values below | Mục đích liên hệ |
| `message` | string | ✅ Yes | 10-2000 characters | Nội dung tin nhắn |

**Contact Purpose Enum Values:**

| Value | Display Text (Vietnamese) |
|-------|--------------------------|
| `business_cooperation` | Hợp tác kinh doanh |
| `investment` | Đầu tư |
| `technical_support` | Hỗ trợ kỹ thuật |
| `other` | Khác |

**Success Response (200):**
```json
{
  "success": true,
  "message": "Cảm ơn bạn đã liên hệ! Chúng tôi sẽ phản hồi trong vòng 24 giờ.",
  "contact_id": "674c5e9f8a2b1c3d4e5f6a7b"
}
```

**Error Responses:**

| Status Code | Description |
|-------------|-------------|
| 400 | Validation error (invalid field format or length) |
| 500 | Internal server error (contact saved but email may have failed) |

**Business Rules:**
- Public endpoint - no authentication required
- Contact request is saved to `contact_requests` collection with status "new"
- Admin receives immediate email notification to `tienhoi.lh@gmail.com`
- Email failure does not block the request (fails gracefully)
- Contact ID is returned for tracking purposes
- Frontend should show success message: "Cảm ơn bạn đã liên hệ! Chúng tôi sẽ phản hồi trong vòng 24 giờ."

**Email Notification Details:**
- **Recipient:** tienhoi.lh@gmail.com
- **Subject:** 📧 Liên hệ mới từ WordAI - [Purpose in Vietnamese]
- **Content:** HTML email containing:
  - Contact details (name, email, phone, company)
  - Purpose badge with color coding
  - Full message content
  - Contact ID and timestamp
  - Admin action link: `https://ai.wordai.pro/admin/contacts/{contact_id}`
  - SLA reminder: "⚠️ Vui lòng phản hồi trong vòng 24 giờ để đảm bảo trải nghiệm tốt nhất cho khách hàng"

**Database Storage:**

Contact requests are stored in MongoDB `contact_requests` collection:

```javascript
{
  "_id": ObjectId("674c5e9f8a2b1c3d4e5f6a7b"),
  "full_name": "Nguyen Van A",
  "email": "example@email.com",
  "phone": "+84 123 456 789",
  "company": "Tech Corp",
  "purpose": "business_cooperation",
  "purpose_display": "Hợp tác kinh doanh",
  "message": "Tôi muốn hợp tác...",
  "status": "new",  // new, contacted, resolved
  "email_sent": true,  // false if email failed
  "source": "wordai.pro",
  "created_at": ISODate("2025-12-01T10:30:00Z")
}
```

**Rate Limiting:**
- Not currently implemented
- Consider adding rate limiting (e.g., 5 requests per IP per hour) to prevent spam
- Recommendation: Use Cloudflare rate limiting or implement application-level throttling

**Security Considerations:**
- Public endpoint vulnerable to spam - should add CAPTCHA (e.g., reCAPTCHA v3)
- Email validation prevents malformed addresses
- Message length limited to 2000 characters to prevent DoS
- No file upload allowed (prevents malware)
- XSS protection: message content is sanitized before email rendering

---

## Integration Flow

### Payment Information Flow:

```
1. User creates test and publishes to marketplace
2. Test gets purchased → user earns points
3. User wants to withdraw earnings
4. Frontend calls GET /me/payment-info
   - If has_payment_info = false → Show payment info setup form
   - If has_payment_info = true → Show withdrawal form with saved info
5. User fills payment info form
6. Frontend calls POST /me/payment-info
7. User can now call POST /me/earnings/withdraw
8. System validates payment_info exists → processes withdrawal → emails admin
```

### Contact Form Flow:

```
1. User visits wordai.pro/contact
2. User fills contact form (name, email, purpose, message)
3. User clicks "Gửi tin nhắn"
4. Frontend calls POST /public/contact (no auth)
5. System saves to database and sends email to admin
6. Frontend shows success message
7. Admin receives email notification immediately
8. Admin follows up within 24 hours
```

---

## Frontend Implementation Notes

### Payment Information Management:

**Setup Form Fields:**
- Họ và tên: Text input (required, 2-100 chars)
- Số tài khoản: Text input (required, 6-30 chars, numeric)
- Tên ngân hàng: Dropdown/Autocomplete (required, common banks: Vietcombank, Techcombank, BIDV, VietinBank, ACB, MB Bank, etc.)
- Chi nhánh: Text input (optional, max 100 chars)

**Validation Rules:**
- Show error if account_holder_name doesn't match user's profile name
- Show warning: "⚠️ Tên chủ tài khoản phải khớp với CMND/CCCD để chuyển khoản thành công"
- Validate account_number is numeric (some banks accept letters)
- Bank name should be autocomplete with common Vietnamese banks

**UI/UX Recommendations:**
- Show payment info setup as first step before withdrawal
- Display saved payment info in withdrawal confirmation
- Allow editing payment info from settings page
- Show last updated timestamp
- Add "Verify account" button (optional feature for future)

### Contact Form:

**Form Fields:**
- Họ và tên: Text input (required, placeholder: "Nguyễn Văn A")
- Email: Email input (required, placeholder: "example@email.com")
- Số điện thoại: Tel input (optional, placeholder: "+84 123 456 789")
- Công ty/Tổ chức: Text input (optional, placeholder: "Tên công ty")
- Mục đích liên hệ: Dropdown (required, options: Hợp tác kinh doanh, Đầu tư, Hỗ trợ kỹ thuật, Khác)
- Nội dung tin nhắn: Textarea (required, 10-2000 chars, show character counter)

**Validation Rules:**
- Email must be valid format
- Message minimum 10 characters (prevents spam)
- Phone number optional but validate format if provided
- All required fields must have red asterisk (*)

**UI/UX Recommendations:**
- Add reCAPTCHA v3 to prevent spam
- Show loading spinner during submission
- Success message: "✅ Cảm ơn bạn đã liên hệ! Chúng tôi sẽ phản hồi trong vòng 24 giờ."
- Clear form after successful submission
- Add "Gửi tin nhắn" button with loading state
- Show inline validation errors
- Character counter for message field (2000 max)
- Phone number format helper text: "(Ví dụ: +84 123 456 789)"

---

## Error Handling

### Payment Information Endpoints:

**Common Error Scenarios:**

1. **Missing Firebase Token (401):**
   - Response: `{"detail": "Unauthorized"}`
   - Action: Redirect to login page

2. **Invalid Account Number Format (400):**
   - Response: `{"detail": "account_number must be 6-30 characters"}`
   - Action: Show inline validation error

3. **User Not Found (404):**
   - Response: `{"detail": "User not found"}`
   - Action: Force re-authentication

4. **Database Error (500):**
   - Response: `{"detail": "Internal server error"}`
   - Action: Show generic error, retry button

### Contact Form Endpoint:

**Common Error Scenarios:**

1. **Invalid Email Format (400):**
   - Response: `{"detail": "email: value is not a valid email address"}`
   - Action: Show inline validation error

2. **Message Too Short (400):**
   - Response: `{"detail": "message must be at least 10 characters"}`
   - Action: Show character counter and requirement

3. **Server Error (500):**
   - Response: `{"detail": "Không thể gửi tin nhắn. Vui lòng thử lại sau."}`
   - Action: Show error message with retry button

**Recommended Error Messages (Vietnamese):**

| Error Type | Message |
|------------|---------|
| Network error | "Không thể kết nối đến máy chủ. Vui lòng kiểm tra kết nối internet." |
| Validation error | "Vui lòng kiểm tra lại thông tin đã nhập." |
| Server error | "Đã xảy ra lỗi. Vui lòng thử lại sau." |
| Rate limit | "Bạn đã gửi quá nhiều yêu cầu. Vui lòng thử lại sau 5 phút." |

---

## Testing Scenarios

### Payment Information:

**Test Cases:**

1. **Setup New Payment Info:**
   - User has no payment_info → POST valid data → Verify saved correctly
   - Expected: 200 response with payment_info returned

2. **Update Existing Payment Info:**
   - User has payment_info → POST new data → Verify updated
   - Expected: Previous data overwritten, 200 response

3. **Validation Tests:**
   - Short account_holder_name (1 char) → Expected: 400 error
   - Long account_number (31 chars) → Expected: 400 error
   - Empty bank_name → Expected: 400 error

4. **Get Payment Info:**
   - User with payment_info → GET → Expected: has_payment_info=true
   - User without payment_info → GET → Expected: has_payment_info=false

5. **Authentication Tests:**
   - No token → Expected: 401 Unauthorized
   - Invalid token → Expected: 401 Unauthorized
   - Expired token → Expected: 401 Unauthorized

### Contact Form:

**Test Cases:**

1. **Valid Submission:**
   - All required fields → POST → Verify saved and email sent
   - Expected: 200 response with contact_id

2. **Optional Fields:**
   - No phone → Expected: 200 response (phone null in DB)
   - No company → Expected: 200 response (company null in DB)

3. **Validation Tests:**
   - Invalid email format → Expected: 400 error
   - Message too short (5 chars) → Expected: 400 error
   - Message too long (2001 chars) → Expected: 400 error
   - Empty full_name → Expected: 400 error

4. **Email Failure Handling:**
   - Brevo service down → Expected: Contact saved, email_sent=false, 200 response
   - Invalid admin email → Expected: Contact saved, email failure logged

5. **Purpose Enum:**
   - Valid purpose values → Expected: 200 response
   - Invalid purpose value → Expected: 400 error

---

## Admin Features (Future Implementation)

### Contact Management Dashboard:

**Recommended Features:**
- List all contact requests with filters (status, purpose, date)
- Search by email, name, company
- View full contact details
- Mark as "contacted", "resolved"
- Add admin notes
- Reply directly from dashboard (sends email to contact)
- Analytics: Contact volume by purpose, response time metrics

### Payment Info Management:

**Recommended Features:**
- Admin cannot edit user payment info (security)
- Admin can view payment info only when processing withdrawals
- Flag suspicious accounts (duplicate account numbers)
- Audit log for payment info changes

---

## Monitoring & Logging

### Key Metrics to Track:

**Payment Information:**
- Payment info setup completion rate
- Update frequency
- Failed withdrawals due to missing payment info
- Time from signup to first payment info setup

**Contact Form:**
- Submission volume (daily/weekly)
- Purpose distribution
- Email delivery success rate
- Average response time
- Conversion rate (contacts → customers)

### Log Levels:

| Event | Level | Message Format |
|-------|-------|----------------|
| Payment info updated | INFO | `💳 Setting payment info for user: {user_id}` |
| Contact form submitted | INFO | `📧 New contact form submission from: {email}` |
| Email sent successfully | INFO | `✅ Contact notification email sent to {admin_email}` |
| Email failed | WARNING | `⚠️ Email sending failed for contact {contact_id}` |
| Validation error | WARNING | `❌ Validation error: {error_details}` |
| Server error | ERROR | `❌ Failed to process contact form: {exception}` |

---

## API Versioning

**Current Version:** v1
**Base Path:** `/api/v1/`

**Backward Compatibility:**
- Adding optional fields: ✅ Safe
- Adding new enum values: ✅ Safe (use "other" as fallback)
- Changing field names: ❌ Breaking (requires v2)
- Changing validation rules: ⚠️ Use caution (may break existing clients)

**Deprecation Policy:**
- v1 endpoints maintained for minimum 6 months after v2 release
- Deprecation warnings sent via response headers: `X-API-Deprecated: true`
- Migration guide provided for breaking changes

---

## Security Best Practices

### Payment Information:
- ✅ Use HTTPS only (enforce TLS 1.2+)
- ✅ Validate Firebase ID tokens on every request
- ✅ Rate limit payment info updates (max 10 per hour per user)
- ✅ Log all payment info changes with user_id and timestamp
- ⚠️ Consider PCI DSS compliance if storing card data (currently N/A)
- ⚠️ Add fraud detection for duplicate account numbers

### Contact Form:
- ✅ Add CAPTCHA (reCAPTCHA v3 recommended)
- ✅ Rate limit submissions (5 per IP per hour)
- ✅ Sanitize message content before email rendering (prevent XSS)
- ✅ Validate email addresses (prevent injection)
- ✅ Block common spam keywords
- ⚠️ Consider honeypot field for bot detection
- ⚠️ Add IP blacklist for repeat spammers

---

## Related Endpoints

### Earnings Withdrawal (Existing):
**Endpoint:** `POST /api/v1/tests/me/earnings/withdraw`
**Purpose:** Request earnings withdrawal (requires payment_info)
**Dependency:** Payment info must be set up first via `/me/payment-info`

### Get Earnings (Existing):
**Endpoint:** `GET /api/v1/tests/me/earnings`
**Purpose:** View current earnings_points balance
**Returns:** Available balance and withdrawal history

---

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-12-01 | Initial API specification for payment info and contact form endpoints |

---

## Support

**Technical Questions:** Contact dev team via `tienhoi.lh@gmail.com`
**API Issues:** Check server logs and error responses
**Frontend Integration:** See Frontend Implementation Notes section above

---

**Document End**
