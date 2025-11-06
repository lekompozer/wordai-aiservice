# BILLING & SUPPORT API - COMPLETE GUIDE

## 📋 Table of Contents
1. [Billing History API](#billing-history-api)
2. [Support System API](#support-system-api)
3. [Integration Examples](#integration-examples)

---

## 💰 BILLING HISTORY API

### Overview
Billing History API cho phép users xem lịch sử thanh toán/nâng cấp subscription của họ.

### Endpoints

#### 1. GET `/api/billing/history` - Lịch sử thanh toán

**Mục đích:** Lấy danh sách tất cả payments của user với phân trang.

**Authentication:** Required (Firebase token)

**Query Parameters:**
- `page` (int, default: 1) - Trang hiện tại
- `limit` (int, default: 20, max: 100) - Số items mỗi trang
- `status_filter` (string, optional) - Lọc theo status: `pending`, `completed`, `failed`, `cancelled`, `refunded`

**Request:**
```typescript
// Tất cả payments
const response = await fetch('/api/billing/history?page=1&limit=20', {
  headers: {
    'Authorization': `Bearer ${firebaseToken}`
  }
});

// Chỉ payments đã hoàn thành
const completed = await fetch('/api/billing/history?status_filter=completed', {
  headers: {
    'Authorization': `Bearer ${firebaseToken}`
  }
});
```

**Response:**
```json
{
  "payments": [
    {
      "payment_id": "673b4e5f0123456789abcdef",
      "order_invoice_number": "WA-1730123456-abc",
      "amount": 279000,
      "currency": "VND",
      "plan": "premium",
      "duration": "3_months",
      "status": "completed",
      "payment_method": "BANK_TRANSFER",
      "created_at": "2025-11-05T09:30:00Z",
      "paid_at": "2025-11-05T09:45:00Z",
      "cancelled_at": null,
      "refunded_at": null,
      "notes": null,
      "manually_processed": false
    },
    {
      "payment_id": "673b4e5f0123456789abcde0",
      "order_invoice_number": "WA-1730023456-xyz",
      "amount": 999000,
      "currency": "VND",
      "plan": "premium",
      "duration": "12_months",
      "status": "pending",
      "payment_method": null,
      "created_at": "2025-11-06T10:00:00Z",
      "paid_at": null,
      "cancelled_at": null,
      "refunded_at": null,
      "notes": "Awaiting bank transfer confirmation",
      "manually_processed": false
    }
  ],
  "total": 2,
  "page": 1,
  "limit": 20,
  "has_more": false,
  "total_spent": 279000,
  "completed_payments": 1,
  "pending_payments": 1
}
```

**Response Fields:**
- `payments`: Array of payment records
- `total`: Tổng số payments của user
- `page`, `limit`, `has_more`: Pagination info
- `total_spent`: Tổng số tiền đã thanh toán (VND)
- `completed_payments`: Số payments đã hoàn thành
- `pending_payments`: Số payments đang chờ

**Payment Status:**
- `pending`: Đang chờ thanh toán
- `completed`: Đã thanh toán thành công
- `failed`: Thanh toán thất bại
- `cancelled`: Đã hủy
- `refunded`: Đã hoàn tiền

**Payment Methods:**
- `BANK_TRANSFER`: Chuyển khoản ngân hàng qua QR (mặc định)
- `BANK_TRANSFER_MANUAL`: Chuyển khoản thủ công
- `VISA`: Thẻ Visa
- `MASTERCARD`: Thẻ Mastercard
- `MOMO`: Ví MoMo
- `ZALOPAY`: Ví ZaloPay

---

#### 2. GET `/api/billing/history/{payment_id}` - Chi tiết thanh toán

**Mục đích:** Lấy thông tin chi tiết của 1 payment cụ thể.

**Authentication:** Required (Firebase token)

**Path Parameters:**
- `payment_id`: ID của payment

**Request:**
```typescript
const response = await fetch('/api/billing/history/673b4e5f0123456789abcdef', {
  headers: {
    'Authorization': `Bearer ${firebaseToken}`
  }
});
```

**Response:**
```json
{
  "payment_id": "673b4e5f0123456789abcdef",
  "order_invoice_number": "WA-1730123456-abc",
  "amount": 279000,
  "currency": "VND",
  "plan": "premium",
  "duration": "3_months",
  "status": "completed",
  "payment_method": "BANK_TRANSFER",
  "created_at": "2025-11-05T09:30:00Z",
  "paid_at": "2025-11-05T09:45:00Z",
  "cancelled_at": null,
  "refunded_at": null,
  "expires_at": "2025-11-05T09:45:00Z",
  "notes": null,
  "manually_processed": false,
  "payment_reference": "FT25110512345",
  "subscription_id": "sub_123"
}
```

**Security:** Users chỉ có thể xem payments của chính họ.

---

## 🎫 SUPPORT SYSTEM API

### Overview
Support System API cho phép users tạo tickets, theo dõi và trao đổi với support team. Admin có thể quản lý và trả lời tickets.

### User Endpoints

#### 1. POST `/api/support/tickets` - Tạo ticket mới

**Mục đích:** User gửi yêu cầu hỗ trợ mới.

**Authentication:** Required (Firebase token)

**Request Body:**
```json
{
  "subject": "Cannot upload PDF files",
  "message": "I'm getting an error 'File size too large' when trying to upload a 5MB PDF file. My plan is FREE.",
  "category": "technical",
  "priority": "high"
}
```

**Categories:**
- `general`: Câu hỏi chung
- `technical`: Vấn đề kỹ thuật
- `billing`: Thanh toán & subscription
- `feature_request`: Đề xuất tính năng
- `bug_report`: Báo lỗi

**Priority:**
- `low`: Không gấp
- `medium`: Bình thường (default)
- `high`: Quan trọng
- `urgent`: Khẩn cấp

**Response:**
```json
{
  "success": true,
  "ticket_id": "673b5000aabbccddeeff0011",
  "message": "Support ticket submitted successfully. Our team will respond shortly.",
  "status": "open"
}
```

**Notifications:**
- ✅ Admin nhận email tại `hoilht89@gmail.com`
- ✅ Email chứa: Subject, User info, Category, Priority, Message, Link đến ticket

---

#### 2. GET `/api/support/tickets` - Danh sách tickets của user

**Mục đích:** Lấy danh sách tất cả tickets user đã tạo.

**Authentication:** Required (Firebase token)

**Query Parameters:**
- `page` (int, default: 1)
- `limit` (int, default: 20, max: 100)
- `status_filter` (string, optional): `open`, `in_progress`, `resolved`, `closed`

**Request:**
```typescript
const response = await fetch('/api/support/tickets?page=1&limit=20', {
  headers: {
    'Authorization': `Bearer ${firebaseToken}`
  }
});
```

**Response:**
```json
{
  "tickets": [
    {
      "ticket_id": "673b5000aabbccddeeff0011",
      "subject": "Cannot upload PDF files",
      "category": "technical",
      "priority": "high",
      "status": "waiting_admin",
      "created_at": "2025-11-06T11:00:00Z",
      "updated_at": "2025-11-06T11:05:00Z",
      "last_reply_at": "2025-11-06T11:05:00Z",
      "last_reply_by": "user",
      "unread_count": 0
    },
    {
      "ticket_id": "673b5000aabbccddeeff0012",
      "subject": "How to upgrade to Premium?",
      "category": "billing",
      "priority": "medium",
      "status": "resolved",
      "created_at": "2025-11-05T10:00:00Z",
      "updated_at": "2025-11-05T14:30:00Z",
      "last_reply_at": "2025-11-05T14:30:00Z",
      "last_reply_by": "admin",
      "unread_count": 1
    }
  ],
  "total": 2,
  "page": 1,
  "limit": 20,
  "has_more": false,
  "open_count": 1,
  "resolved_count": 1,
  "closed_count": 0
}
```

**Ticket Status:**
- `open`: Mới tạo, chưa có phản hồi
- `in_progress`: Đang xử lý
- `waiting_admin`: Đang chờ admin trả lời
- `waiting_user`: Đang chờ user trả lời
- `resolved`: Đã giải quyết
- `closed`: Đã đóng

---

#### 3. GET `/api/support/tickets/{ticket_id}` - Chi tiết ticket & messages

**Mục đích:** Xem toàn bộ nội dung trao đổi của 1 ticket.

**Authentication:** Required (Firebase token)

**Path Parameters:**
- `ticket_id`: Support ticket ID

**Request:**
```typescript
const response = await fetch('/api/support/tickets/673b5000aabbccddeeff0011', {
  headers: {
    'Authorization': `Bearer ${firebaseToken}`
  }
});
```

**Response:**
```json
{
  "ticket_id": "673b5000aabbccddeeff0011",
  "subject": "Cannot upload PDF files",
  "category": "technical",
  "priority": "high",
  "status": "waiting_admin",
  "user_id": "firebase_uid_123",
  "user_email": "user@example.com",
  "user_name": "John Doe",
  "created_at": "2025-11-06T11:00:00Z",
  "updated_at": "2025-11-06T11:05:00Z",
  "resolved_at": null,
  "closed_at": null,
  "messages": [
    {
      "message_id": "msg_001",
      "sender_type": "user",
      "sender_id": "firebase_uid_123",
      "sender_name": "John Doe",
      "message": "I'm getting an error 'File size too large' when trying to upload a 5MB PDF file.",
      "created_at": "2025-11-06T11:00:00Z",
      "is_internal_note": false
    },
    {
      "message_id": "msg_002",
      "sender_type": "user",
      "sender_id": "firebase_uid_123",
      "sender_name": "John Doe",
      "message": "I also tried with a 3MB file and got the same error.",
      "created_at": "2025-11-06T11:05:00Z",
      "is_internal_note": false
    }
  ],
  "tags": [],
  "assigned_to": null
}
```

**Auto Actions:**
- ✅ Mark messages as read
- ✅ Clear unread count for user

---

#### 4. POST `/api/support/tickets/{ticket_id}/reply` - User trả lời ticket

**Mục đích:** User thêm message vào ticket của họ.

**Authentication:** Required (Firebase token)

**Path Parameters:**
- `ticket_id`: Support ticket ID

**Request Body:**
```json
{
  "message": "Thank you for your response! I tried clearing cache and it works now."
}
```

**Response:**
```json
{
  "success": true,
  "message": "Reply added successfully",
  "ticket_id": "673b5000aabbccddeeff0011"
}
```

**Auto Actions:**
- ✅ Status changed to `waiting_admin`
- ✅ Admin receives email notification
- ✅ `last_reply_by` set to `user`
- ✅ `unread_by_admin` flag set to true

---

### Admin Endpoints

#### 5. GET `/api/support/admin/tickets` - [ADMIN] Danh sách tất cả tickets

**Mục đích:** Admin xem tất cả tickets của tất cả users.

**Authentication:** Required (Firebase token + Admin role)

**Query Parameters:**
- `page` (int, default: 1)
- `limit` (int, default: 20, max: 100)
- `status_filter` (string, optional)
- `priority_filter` (string, optional): `low`, `medium`, `high`, `urgent`
- `category_filter` (string, optional): `general`, `technical`, `billing`, etc.
- `search` (string, optional): Search in subject or user email

**Request:**
```typescript
// All tickets
const response = await fetch('/api/support/admin/tickets?page=1', {
  headers: {
    'Authorization': `Bearer ${adminToken}`
  }
});

// High priority only
const highPriority = await fetch('/api/support/admin/tickets?priority_filter=high', {
  headers: {
    'Authorization': `Bearer ${adminToken}`
  }
});

// Search user
const search = await fetch('/api/support/admin/tickets?search=john@example.com', {
  headers: {
    'Authorization': `Bearer ${adminToken}`
  }
});
```

**Response:**
```json
{
  "tickets": [
    {
      "ticket_id": "673b5000aabbccddeeff0011",
      "subject": "Cannot upload PDF files",
      "category": "technical",
      "priority": "high",
      "status": "waiting_admin",
      "created_at": "2025-11-06T11:00:00Z",
      "updated_at": "2025-11-06T11:05:00Z",
      "last_reply_at": "2025-11-06T11:05:00Z",
      "last_reply_by": "user",
      "unread_count": 1,
      "user_id": "firebase_uid_123",
      "user_email": "user@example.com",
      "user_name": "John Doe"
    }
  ],
  "total": 15,
  "page": 1,
  "limit": 20,
  "has_more": false,
  "open_count": 5,
  "resolved_count": 8,
  "closed_count": 2
}
```

---

#### 6. GET `/api/support/admin/tickets/{ticket_id}` - [ADMIN] Chi tiết ticket

**Mục đích:** Admin xem chi tiết ticket bao gồm cả internal notes.

**Authentication:** Required (Firebase token + Admin role)

**Path Parameters:**
- `ticket_id`: Support ticket ID

**Response:** Giống như user endpoint nhưng bao gồm `is_internal_note: true` messages.

**Auto Actions:**
- ✅ Mark as read by admin
- ✅ Clear `unread_by_admin` flag

---

#### 7. POST `/api/support/admin/tickets/{ticket_id}/reply` - [ADMIN] Trả lời ticket

**Mục đích:** Admin trả lời user's ticket.

**Authentication:** Required (Firebase token + Admin role)

**Path Parameters:**
- `ticket_id`: Support ticket ID

**Request Body:**
```json
{
  "message": "Hi John,\n\nThank you for reporting this issue. The file size limit for FREE plan is 2MB per file.\n\nTo upload larger files, please upgrade to Premium plan which allows up to 50MB per file.\n\nBest regards,\nWordAI Support Team"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Reply sent successfully. User has been notified.",
  "ticket_id": "673b5000aabbccddeeff0011",
  "notifications_sent": {
    "in_app": true,
    "email": true
  }
}
```

**Auto Actions:**
- ✅ Status changed to `waiting_user`
- ✅ User receives in-app notification
- ✅ User receives email notification
- ✅ `assigned_to` set to admin ID
- ✅ `last_reply_by` set to `admin`
- ✅ `unread_by_user` flag set to true

**Email Notification to User:**
```
Subject: Support Reply: Cannot upload PDF files

Hi John,

Our support team has replied to your ticket:

[Admin's message here]

View ticket: https://your-domain.com/support/tickets/673b5000aabbccddeeff0011

Best regards,
WordAI Support Team
```

**In-App Notification:**
```json
{
  "type": "support_reply",
  "title": "New reply on: Cannot upload PDF files",
  "message": "Support team has replied to your ticket. Hi John, Thank you for...",
  "data": {
    "ticket_id": "673b5000aabbccddeeff0011",
    "link": "/support/tickets/673b5000aabbccddeeff0011"
  }
}
```

---

#### 8. PATCH `/api/support/admin/tickets/{ticket_id}/status` - [ADMIN] Cập nhật status

**Mục đích:** Admin thay đổi status của ticket.

**Authentication:** Required (Firebase token + Admin role)

**Path Parameters:**
- `ticket_id`: Support ticket ID

**Query Parameters:**
- `status`: New status (`open`, `in_progress`, `resolved`, `closed`, `waiting_user`, `waiting_admin`)

**Request:**
```typescript
const response = await fetch('/api/support/admin/tickets/673b5000aabbccddeeff0011/status?status=resolved', {
  method: 'PATCH',
  headers: {
    'Authorization': `Bearer ${adminToken}`
  }
});
```

**Response:**
```json
{
  "success": true,
  "message": "Ticket status updated to resolved",
  "ticket_id": "673b5000aabbccddeeff0011",
  "new_status": "resolved"
}
```

---

## 🎯 INTEGRATION EXAMPLES

### Frontend Components

#### 1. Billing History Page

```typescript
// Page: BillingHistoryPage.tsx
import { useEffect, useState } from 'react';

interface Payment {
  payment_id: string;
  order_invoice_number: string;
  amount: number;
  plan: string;
  duration: string;
  status: string;
  payment_method: string;
  created_at: string;
  paid_at: string;
}

function BillingHistoryPage() {
  const [payments, setPayments] = useState<Payment[]>([]);
  const [stats, setStats] = useState({ total_spent: 0, completed: 0, pending: 0 });
  const [page, setPage] = useState(1);
  
  useEffect(() => {
    fetchHistory();
  }, [page]);
  
  const fetchHistory = async () => {
    const token = await getFirebaseToken();
    const response = await fetch(`/api/billing/history?page=${page}&limit=20`, {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    const data = await response.json();
    setPayments(data.payments);
    setStats({
      total_spent: data.total_spent,
      completed: data.completed_payments,
      pending: data.pending_payments
    });
  };
  
  return (
    <div className="billing-page">
      <h1>Billing History</h1>
      
      {/* Statistics */}
      <div className="stats-grid">
        <div className="stat-card">
          <h3>Total Spent</h3>
          <p className="amount">{stats.total_spent.toLocaleString('vi-VN')} VND</p>
        </div>
        <div className="stat-card">
          <h3>Completed Payments</h3>
          <p>{stats.completed}</p>
        </div>
        <div className="stat-card">
          <h3>Pending Payments</h3>
          <p>{stats.pending}</p>
        </div>
      </div>
      
      {/* Payments Table */}
      <table className="payments-table">
        <thead>
          <tr>
            <th>Invoice #</th>
            <th>Plan</th>
            <th>Amount</th>
            <th>Payment Method</th>
            <th>Status</th>
            <th>Date</th>
          </tr>
        </thead>
        <tbody>
          {payments.map(payment => (
            <tr key={payment.payment_id}>
              <td>{payment.order_invoice_number}</td>
              <td>{payment.plan.toUpperCase()} ({payment.duration.replace('_', ' ')})</td>
              <td>{payment.amount.toLocaleString('vi-VN')} VND</td>
              <td>{payment.payment_method || 'Pending'}</td>
              <td>
                <span className={`status-badge ${payment.status}`}>
                  {payment.status}
                </span>
              </td>
              <td>{new Date(payment.created_at).toLocaleDateString('vi-VN')}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

#### 2. Support Ticket Creation Form

```typescript
// Component: CreateTicketForm.tsx
import { useState } from 'react';

function CreateTicketForm({ onSuccess }: { onSuccess: () => void }) {
  const [formData, setFormData] = useState({
    subject: '',
    message: '',
    category: 'general',
    priority: 'medium'
  });
  const [submitting, setSubmitting] = useState(false);
  
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    
    try {
      const token = await getFirebaseToken();
      const response = await fetch('/api/support/tickets', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(formData)
      });
      
      const data = await response.json();
      
      if (data.success) {
        alert('Ticket submitted successfully! Our team will respond shortly.');
        onSuccess();
      }
    } catch (error) {
      alert('Failed to submit ticket. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };
  
  return (
    <form onSubmit={handleSubmit} className="ticket-form">
      <h2>Create Support Ticket</h2>
      
      <div className="form-group">
        <label>Subject *</label>
        <input
          type="text"
          value={formData.subject}
          onChange={e => setFormData({...formData, subject: e.target.value})}
          required
          minLength={5}
          placeholder="Brief description of your issue"
        />
      </div>
      
      <div className="form-group">
        <label>Category *</label>
        <select
          value={formData.category}
          onChange={e => setFormData({...formData, category: e.target.value})}
        >
          <option value="general">General Inquiry</option>
          <option value="technical">Technical Issue</option>
          <option value="billing">Billing & Payment</option>
          <option value="feature_request">Feature Request</option>
          <option value="bug_report">Bug Report</option>
        </select>
      </div>
      
      <div className="form-group">
        <label>Priority</label>
        <select
          value={formData.priority}
          onChange={e => setFormData({...formData, priority: e.target.value})}
        >
          <option value="low">Low</option>
          <option value="medium">Medium</option>
          <option value="high">High</option>
          <option value="urgent">Urgent</option>
        </select>
      </div>
      
      <div className="form-group">
        <label>Message *</label>
        <textarea
          value={formData.message}
          onChange={e => setFormData({...formData, message: e.target.value})}
          required
          minLength={10}
          rows={8}
          placeholder="Please provide as much detail as possible..."
        />
      </div>
      
      <button type="submit" disabled={submitting}>
        {submitting ? 'Submitting...' : 'Submit Ticket'}
      </button>
    </form>
  );
}
```

#### 3. Support Ticket List (User)

```typescript
// Page: UserTicketsPage.tsx
import { useEffect, useState } from 'react';

function UserTicketsPage() {
  const [tickets, setTickets] = useState([]);
  const [stats, setStats] = useState({ open: 0, resolved: 0 });
  const [filter, setFilter] = useState('all');
  
  useEffect(() => {
    fetchTickets();
  }, [filter]);
  
  const fetchTickets = async () => {
    const token = await getFirebaseToken();
    const url = filter === 'all' 
      ? '/api/support/tickets'
      : `/api/support/tickets?status_filter=${filter}`;
      
    const response = await fetch(url, {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    const data = await response.json();
    setTickets(data.tickets);
    setStats({
      open: data.open_count,
      resolved: data.resolved_count
    });
  };
  
  return (
    <div className="tickets-page">
      <h1>My Support Tickets</h1>
      
      {/* Statistics */}
      <div className="stats">
        <div>Open: {stats.open}</div>
        <div>Resolved: {stats.resolved}</div>
      </div>
      
      {/* Filter */}
      <div className="filter-bar">
        <button onClick={() => setFilter('all')}>All</button>
        <button onClick={() => setFilter('open')}>Open</button>
        <button onClick={() => setFilter('resolved')}>Resolved</button>
        <button onClick={() => setFilter('closed')}>Closed</button>
      </div>
      
      {/* Tickets List */}
      <div className="tickets-list">
        {tickets.map(ticket => (
          <div key={ticket.ticket_id} className="ticket-card">
            <div className="ticket-header">
              <h3>{ticket.subject}</h3>
              {ticket.unread_count > 0 && (
                <span className="unread-badge">{ticket.unread_count} new</span>
              )}
            </div>
            <div className="ticket-meta">
              <span className={`status ${ticket.status}`}>{ticket.status}</span>
              <span className={`priority ${ticket.priority}`}>{ticket.priority}</span>
              <span className="category">{ticket.category}</span>
            </div>
            <div className="ticket-footer">
              <span>Created: {new Date(ticket.created_at).toLocaleDateString()}</span>
              <span>Last reply: {ticket.last_reply_by}</span>
              <button onClick={() => navigate(`/support/tickets/${ticket.ticket_id}`)}>
                View Details →
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
```

---

## 🔐 Security Notes

### Authentication
- ✅ All endpoints require Firebase authentication
- ✅ Users can only view their own billing/tickets
- ✅ Admin endpoints require additional role check (TODO: Implement)

### Data Privacy
- ✅ Payment details only accessible by owner
- ✅ Support tickets only accessible by owner and admins
- ✅ Internal notes hidden from users

### Email Notifications
- ✅ Admin email: `hoilht89@gmail.com`
- ✅ User emails sent to verified email address
- ⚠️ TODO: Integrate with Brevo email service

---

## 📊 Database Collections

### `payments` Collection
```json
{
  "_id": ObjectId,
  "order_invoice_number": "WA-1730123456-abc",
  "user_id": "firebase_uid",
  "user_email": "user@example.com",
  "amount": 279000,
  "currency": "VND",
  "plan": "premium",
  "duration": "3_months",
  "status": "completed",
  "payment_method": "BANK_TRANSFER",
  "created_at": ISODate,
  "paid_at": ISODate,
  ...
}
```

### `support_tickets` Collection
```json
{
  "_id": ObjectId,
  "user_id": "firebase_uid",
  "user_email": "user@example.com",
  "user_name": "John Doe",
  "subject": "Cannot upload files",
  "category": "technical",
  "priority": "high",
  "status": "waiting_admin",
  "messages": [
    {
      "message_id": "msg_001",
      "sender_type": "user",
      "sender_id": "firebase_uid",
      "message": "...",
      "created_at": ISODate,
      "is_internal_note": false
    }
  ],
  "created_at": ISODate,
  "updated_at": ISODate,
  "last_reply_at": ISODate,
  "last_reply_by": "user",
  "unread_by_admin": true,
  "unread_by_user": false,
  ...
}
```

---

## 🚀 Deployment Status

✅ **COMPLETED:**
- Billing History API (2 endpoints)
- Support System API (7 endpoints)
- Email notifications configured
- In-app notifications integrated
- All imports and routes registered

⏳ **TODO:**
- Integrate Brevo email service
- Add admin role verification
- Add pagination for ticket messages (if > 100 messages)
- Add file attachment support for tickets
- Add ticket search/filtering by date range

---

## 📞 Support

Admin email: **hoilht89@gmail.com**

Backend logs: Check for `❌`, `ERROR`, `billing`, `support`, `ticket`
