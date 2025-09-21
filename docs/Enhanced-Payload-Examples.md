# Enhanced Payload Examples
## Ví dụ về Payload được nâng cấp

Tài liệu này cung cấp các ví dụ về cách sử dụng cấu trúc payload mới với device_id tracking và enhanced context.

## 📋 Table of Contents
- [Overview](#overview)
- [Anonymous User Example](#anonymous-user-example)
- [Authenticated User Example](#authenticated-user-example)
- [Real-World Implementation](#real-world-implementation)
- [Frontend Integration](#frontend-integration)

## 🔍 Overview

Payload mới hỗ trợ:
- **Device-based tracking** cho anonymous users
- **Enhanced context** với platform-specific data
- **Rich metadata** cho AI prompt customization
- **Flexible user identification** (device_id hoặc Firebase UID)

## 📱 Anonymous User Example

### Request Payload for Anonymous Visitor
```json
{
  "message": "Tôi muốn tìm hiểu về gói vay mua nhà",
  "session_id": "device_550e8400-e29b-41d4-a716-446655440000_1732710000",
  "industry": "BANKING",
  "language": "VIETNAMESE",
  "user_info": {
    "user_id": "device_550e8400-e29b-41d4-a716-446655440000",
    "device_id": "550e8400-e29b-41d4-a716-446655440000",
    "source": "WEBSITE",
    "name": null,
    "email": null,
    "is_authenticated": false
  },
  "context": {
    "platform_data": {
      "browser": "Chrome 118.0.0.0",
      "operating_system": "Windows 10",
      "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
      "platform": "web",
      "language": "vi-VN",
      "timezone": "Asia/Ho_Chi_Minh"
    },
    "context_data": {
      "page_url": "https://example-bank.com/loans",
      "referrer": "https://google.com/search?q=vay+mua+nha",
      "session_duration_minutes": 5,
      "page_views": 3
    },
    "metadata": {
      "app_source": "website",
      "app_version": "2.1.4",
      "request_id": "req_1732710123456",
      "api_version": "v2"
    }
  }
}
```

### Response với Enhanced Context
```json
{
  "session_id": "device_550e8400-e29b-41d4-a716-446655440000_1732710000",
  "conversation_id": "conv_1732710123456",
  "message": "Chào bạn! Tôi thấy bạn đang tìm hiểu về vay mua nhà. Với lãi suất ưu đãi hiện tại, chúng tôi có các gói vay linh hoạt...",
  "intent": "SALES_INQUIRY",
  "confidence": 0.92,
  "reasoning": "Customer asking about home loan products, high sales intent",
  "suggestions": [
    "Xem chi tiết lãi suất",
    "Tính toán khoản vay",
    "Tư vấn trực tiếp với chuyên viên"
  ],
  "response_language": "VIETNAMESE",
  "conversation_metadata": {
    "user_type": "anonymous",
    "device_tracking": true,
    "context_personalization": true
  }
}
```

## 🔐 Authenticated User Example

### Request Payload for Logged-in User
```json
{
  "message": "I want to check my loan application status",
  "session_id": "firebase_user123_1732710000",
  "industry": "BANKING",
  "language": "ENGLISH",
  "user_info": {
    "user_id": "firebase_abc123def456",
    "device_id": "550e8400-e29b-41d4-a716-446655440000",
    "source": "MOBILE_APP",
    "name": "John Doe",
    "email": "john.doe@example.com",
    "is_authenticated": true
  },
  "context": {
    "platform_data": {
      "browser": null,
      "operating_system": "iOS 17.1",
      "user_agent": "MyBankApp/1.5.2 (iPhone; iOS 17.1; Scale/3.00)",
      "platform": "mobile",
      "language": "en-US",
      "timezone": "America/New_York"
    },
    "context_data": {
      "page_url": null,
      "referrer": null,
      "session_duration_minutes": 12,
      "page_views": 0
    },
    "metadata": {
      "app_source": "mobile_app",
      "app_version": "1.5.2",
      "request_id": "req_1732710123789",
      "api_version": "v2"
    }
  }
}
```

### Response với User-specific Information
```json
{
  "session_id": "firebase_user123_1732710000",
  "conversation_id": "conv_1732710123789",
  "message": "Hello John! I can help you check your loan application. Your home loan application #HL-2024-001 is currently under review...",
  "intent": "SUPPORT",
  "confidence": 0.95,
  "reasoning": "Authenticated user asking about specific application status",
  "suggestions": [
    "Check required documents",
    "Contact loan officer",
    "View application timeline"
  ],
  "response_language": "ENGLISH",
  "conversation_metadata": {
    "user_type": "authenticated",
    "device_tracking": true,
    "personalization_level": "high"
  }
}
```

## 🌐 Real-World Implementation

### Frontend JavaScript (Device Fingerprint Generation)
```javascript
class ChatPayloadBuilder {
  constructor() {
    this.deviceId = this.getOrCreateDeviceId();
  }

  getOrCreateDeviceId() {
    let deviceId = localStorage.getItem('device_id');
    if (!deviceId) {
      deviceId = this.generateDeviceFingerprint();
      localStorage.setItem('device_id', deviceId);
    }
    return deviceId;
  }

  generateDeviceFingerprint() {
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');
    ctx.textBaseline = 'top';
    ctx.font = '14px Arial';
    ctx.fillText('Device fingerprint', 2, 2);
    
    const fingerprint = [
      navigator.userAgent,
      navigator.language,
      screen.width + 'x' + screen.height,
      new Date().getTimezoneOffset(),
      canvas.toDataURL(),
      navigator.hardwareConcurrency || 'unknown'
    ].join('|');
    
    return this.hashCode(fingerprint);
  }

  hashCode(str) {
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
      const char = str.charCodeAt(i);
      hash = ((hash << 5) - hash) + char;
      hash = hash & hash;
    }
    return Math.abs(hash).toString(16);
  }

  buildChatPayload(message, user = null) {
    const timestamp = Date.now();
    const sessionId = user 
      ? `firebase_${user.uid}_${Math.floor(timestamp / 1000)}`
      : `device_${this.deviceId}_${Math.floor(timestamp / 1000)}`;

    return {
      message,
      session_id: sessionId,
      industry: "BANKING", // or detect from current page
      language: navigator.language.includes('vi') ? "VIETNAMESE" : "ENGLISH",
      user_info: {
        user_id: user ? `firebase_${user.uid}` : `device_${this.deviceId}`,
        device_id: this.deviceId,
        source: this.detectSource(),
        name: user?.displayName || null,
        email: user?.email || null,
        is_authenticated: !!user
      },
      context: {
        platform_data: {
          browser: this.getBrowserInfo(),
          operating_system: this.getOSInfo(),
          user_agent: navigator.userAgent,
          platform: this.getPlatformType(),
          language: navigator.language,
          timezone: Intl.DateTimeFormat().resolvedOptions().timeZone
        },
        context_data: {
          page_url: window.location.href,
          referrer: document.referrer || null,
          session_duration_minutes: this.getSessionDuration(),
          page_views: this.getPageViews()
        },
        metadata: {
          app_source: this.getAppSource(),
          app_version: "2.1.4", // from your app config
          request_id: `req_${timestamp}`,
          api_version: "v2"
        }
      }
    };
  }

  detectSource() {
    if (window.ReactNativeWebView) return "MOBILE_APP";
    if (/Android|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent)) {
      return "MOBILE_WEB";
    }
    return "WEBSITE";
  }

  getBrowserInfo() {
    const ua = navigator.userAgent;
    if (ua.includes('Chrome')) return ua.match(/Chrome\/[\d.]+/)[0];
    if (ua.includes('Firefox')) return ua.match(/Firefox\/[\d.]+/)[0];
    if (ua.includes('Safari')) return ua.match(/Safari\/[\d.]+/)[0];
    return 'Unknown';
  }

  getOSInfo() {
    const ua = navigator.userAgent;
    if (ua.includes('Windows')) return ua.match(/Windows NT [\d.]+/)[0];
    if (ua.includes('Mac')) return ua.match(/Mac OS X [\d_]+/)[0];
    if (ua.includes('Linux')) return 'Linux';
    if (ua.includes('Android')) return ua.match(/Android [\d.]+/)[0];
    if (ua.includes('iOS')) return ua.match(/OS [\d_]+/)[0];
    return 'Unknown';
  }

  getPlatformType() {
    if (window.ReactNativeWebView) return 'mobile_app';
    if (/Mobi|Android/i.test(navigator.userAgent)) return 'mobile';
    return 'web';
  }

  getSessionDuration() {
    const sessionStart = sessionStorage.getItem('session_start');
    if (!sessionStart) {
      sessionStorage.setItem('session_start', Date.now().toString());
      return 0;
    }
    return Math.floor((Date.now() - parseInt(sessionStart)) / 60000);
  }

  getPageViews() {
    const pageViews = sessionStorage.getItem('page_views') || '0';
    const newCount = parseInt(pageViews) + 1;
    sessionStorage.setItem('page_views', newCount.toString());
    return newCount;
  }

  getAppSource() {
    if (window.ReactNativeWebView) return 'mobile_app';
    return 'website';
  }
}

// Usage Example
const payloadBuilder = new ChatPayloadBuilder();

// For anonymous user
const anonymousPayload = payloadBuilder.buildChatPayload(
  "Tôi cần tư vấn về gói vay mua nhà"
);

// For authenticated user (after Firebase login)
firebase.auth().onAuthStateChanged((user) => {
  if (user) {
    const authenticatedPayload = payloadBuilder.buildChatPayload(
      "I want to check my loan status", 
      user
    );
  }
});
```

### Backend Webhook Handler (Node.js)
```javascript
const express = require('express');
const crypto = require('crypto');
const app = express();

// Webhook signature verification
function verifyWebhookSignature(payload, signature, secret) {
  const hmac = crypto.createHmac('sha256', secret);
  hmac.update(payload);
  const expectedSignature = `sha256=${hmac.digest('hex')}`;
  return crypto.timingSafeEqual(
    Buffer.from(signature), 
    Buffer.from(expectedSignature)
  );
}

// Webhook handler với enhanced tracking
app.post('/webhooks/chat', express.raw({ type: 'application/json' }), (req, res) => {
  const signature = req.headers['x-webhook-signature'];
  
  if (!verifyWebhookSignature(req.body, signature, process.env.WEBHOOK_SECRET)) {
    return res.status(401).send('Invalid signature');
  }

  const event = JSON.parse(req.body);
  
  switch (event.type) {
    case 'conversation.created':
      handleNewConversation(event.data);
      break;
    case 'message.created':
      handleNewMessage(event.data);
      break;
    case 'conversation.updated':
      handleConversationUpdate(event.data);
      break;
  }

  res.status(200).send('OK');
});

function handleNewConversation(data) {
  const { conversation_id, session_id, metadata } = data;
  
  // Extract user context for analytics
  const userContext = metadata.user_context;
  const userType = userContext?.user_info?.is_authenticated ? 'authenticated' : 'anonymous';
  const deviceId = userContext?.user_info?.device_id;
  const platform = userContext?.platform_data?.platform;
  
  console.log(`New ${userType} conversation on ${platform}: ${conversation_id}`);
  
  // Store in your analytics system
  analytics.track('Conversation Started', {
    conversation_id,
    session_id,
    user_type: userType,
    device_id: deviceId,
    platform: platform,
    browser: userContext?.platform_data?.browser,
    referrer: userContext?.context_data?.referrer,
    page_url: userContext?.context_data?.page_url
  });
}

function handleNewMessage(data) {
  const { message_id, conversation_id, role, content, metadata } = data;
  
  if (role === 'assistant' && metadata.intent) {
    // Track AI response metrics
    analytics.track('AI Response Generated', {
      message_id,
      conversation_id,
      intent: metadata.intent,
      confidence: metadata.confidence,
      language: metadata.language,
      response_length: content.length,
      user_context: metadata.user_context
    });
  }
}
```

## 📊 Analytics & Insights

### Device Tracking Benefits
```javascript
// Advanced analytics với device-based tracking
const analytics = {
  // Track anonymous user journey
  trackAnonymousJourney: (deviceId, events) => {
    return db.collection('anonymous_journeys')
      .doc(deviceId)
      .set({
        device_id: deviceId,
        events: events,
        first_seen: new Date(),
        last_seen: new Date(),
        total_conversations: events.filter(e => e.type === 'conversation_start').length,
        conversion_stage: calculateConversionStage(events)
      }, { merge: true });
  },

  // Link anonymous data when user authenticates
  linkAnonymousToUser: async (deviceId, userId) => {
    const anonymousData = await db.collection('anonymous_journeys')
      .doc(deviceId)
      .get();
    
    if (anonymousData.exists) {
      await db.collection('user_journeys')
        .doc(userId)
        .set({
          ...anonymousData.data(),
          user_id: userId,
          linked_at: new Date()
        });
    }
  }
};
```

## 🎯 AI Prompt Enhancement

### Prompt Customization với Context
```python
def build_enhanced_prompt(message, user_context, company_data):
    # Extract context insights
    platform = user_context.get('platform_data', {}).get('platform', 'unknown')
    browser = user_context.get('platform_data', {}).get('browser', 'unknown')
    session_duration = user_context.get('context_data', {}).get('session_duration_minutes', 0)
    is_authenticated = user_context.get('user_info', {}).get('is_authenticated', False)
    referrer = user_context.get('context_data', {}).get('referrer', '')
    
    # Build context-aware prompt
    context_insights = []
    
    if 'google.com' in referrer:
        context_insights.append("User came from Google search - likely researching")
    
    if session_duration > 10:
        context_insights.append("User has been browsing for a while - high engagement")
    
    if platform == 'mobile':
        context_insights.append("User on mobile - prefer concise responses")
    
    if is_authenticated:
        context_insights.append("Authenticated user - can access personalized data")
    
    prompt = f"""
    You are an AI assistant for a banking company.
    
    CONTEXT INSIGHTS: {', '.join(context_insights)}
    PLATFORM: {platform} ({browser})
    USER TYPE: {'Authenticated' if is_authenticated else 'Anonymous visitor'}
    
    COMPANY DATA: {company_data}
    
    USER MESSAGE: {message}
    
    Respond naturally while considering the user context and insights above.
    """
    
    return prompt
```

## 🔧 Implementation Checklist

### Frontend Setup
- [ ] Implement device fingerprinting
- [ ] Set up context data collection
- [ ] Add session tracking
- [ ] Configure user authentication detection
- [ ] Test payload generation

### Backend Setup
- [ ] Update API endpoints to accept new payload structure
- [ ] Implement user context extraction
- [ ] Set up enhanced prompt building
- [ ] Configure webhook handlers
- [ ] Test device-based conversation tracking

### Analytics Setup
- [ ] Set up anonymous user journey tracking
- [ ] Implement conversion tracking
- [ ] Configure user linking (anonymous → authenticated)
- [ ] Set up real-time analytics dashboards
- [ ] Test cross-device conversation continuity

---

**Lưu ý**: Payload structure mới hoàn toàn backward compatible. Các client cũ vẫn hoạt động bình thường với các giá trị mặc định được tự động thêm vào.
