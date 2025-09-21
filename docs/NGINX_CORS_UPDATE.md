# Nginx Configuration Update for Dynamic CORS
*Updated: 2025-01-31*

## 📋 Overview

Khi sử dụng Dynamic CORS trong AI Service, cần remove static CORS configuration từ nginx để tránh conflicts.

## 🔧 **Nginx Configuration Changes**

### **Before (Static CORS)**

```nginx
server {
    listen 80;
    server_name ai.aimoney.io.vn;

    # Static CORS headers - REMOVE THESE
    add_header 'Access-Control-Allow-Origin' '*' always;
    add_header 'Access-Control-Allow-Methods' 'GET, POST, PUT, DELETE, OPTIONS' always;
    add_header 'Access-Control-Allow-Headers' '*' always;
    add_header 'Access-Control-Allow-Credentials' 'true' always;

    location /api/unified/chat-stream {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;

        # Preflight OPTIONS handling - REMOVE THIS
        if ($request_method = OPTIONS) {
            add_header 'Access-Control-Allow-Origin' '*';
            add_header 'Access-Control-Allow-Methods' 'GET, POST, PUT, DELETE, OPTIONS';
            add_header 'Access-Control-Allow-Headers' '*';
            add_header 'Access-Control-Max-Age' 86400;
            return 204;
        }
    }
}
```

### **After (Dynamic CORS)**

```nginx
server {
    listen 80;
    server_name ai.aimoney.io.vn;

    # NO STATIC CORS HEADERS - Let AI Service handle CORS dynamically

    location /api/unified/chat-stream {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;

        # Pass Origin header to AI Service for dynamic CORS processing
        proxy_set_header Origin $http_origin;

        # NO PREFLIGHT HANDLING - Let AI Service handle it
    }

    # Other chat-plugin routes that need dynamic CORS
    location /api/unified/ {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Origin $http_origin;
    }

    # Internal API endpoints (keep protected)
    location /api/internal/ {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Optional: Restrict access to internal endpoints
        allow 127.0.0.1;
        allow 10.0.0.0/8;
        deny all;
    }
}
```

## 🔄 **SSL Configuration with Dynamic CORS**

```nginx
server {
    listen 443 ssl http2;
    server_name ai.aimoney.io.vn;

    ssl_certificate /path/to/ssl/cert.pem;
    ssl_certificate_key /path/to/ssl/private.key;

    # NO STATIC CORS - AI Service handles it

    location /api/unified/chat-stream {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;

        # IMPORTANT: Pass Origin for CORS decision
        proxy_set_header Origin $http_origin;

        # Timeout settings for streaming
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    location /api/unified/ {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Origin $http_origin;
    }
}
```

## 📝 **Configuration Steps**

### **1. Backup Current Configuration**
```bash
sudo cp /etc/nginx/sites-available/ai.aimoney.io.vn /etc/nginx/sites-available/ai.aimoney.io.vn.backup
```

### **2. Update Configuration**
```bash
sudo nano /etc/nginx/sites-available/ai.aimoney.io.vn
```

### **3. Test Configuration**
```bash
sudo nginx -t
```

### **4. Reload Nginx**
```bash
sudo systemctl reload nginx
```

### **5. Verify Dynamic CORS**
```bash
# Test from allowed domain
curl -H "Origin: https://customer-website.com" \
     -H "X-Plugin-Id: plugin_123" \
     -X OPTIONS \
     https://ai.aimoney.io.vn/api/unified/chat-stream

# Should return CORS headers for allowed domain
# Should NOT return CORS headers for unknown domain
```

## ⚠️ **Important Notes**

### **Key Points**
- Remove ALL static CORS headers from nginx
- Let AI Service handle CORS dynamically
- Pass `Origin` header to AI Service
- No preflight handling in nginx

### **What Changes**
- **Before**: nginx adds CORS headers for all requests
- **After**: AI Service adds CORS headers only for allowed plugin domains

### **Benefits**
- Dynamic domain management per plugin
- No nginx restart needed for domain changes
- Better security (only allowed domains get CORS)
- Centralized CORS management in AI Service

## 🧪 **Testing**

### **Test Commands**
```bash
# Test internal API
curl -H "X-Internal-Auth: internal-cors-update-token" \
     http://localhost:8000/api/internal/cors/status

# Update plugin domains
curl -X POST \
     -H "X-Internal-Auth: internal-cors-update-token" \
     -H "Content-Type: application/json" \
     -d '{"pluginId":"plugin_123","domains":["https://customer.com"],"companyId":"comp_456"}' \
     http://localhost:8000/api/internal/cors/update-domains

# Test CORS from customer domain
curl -H "Origin: https://customer.com" \
     -H "X-Plugin-Id: plugin_123" \
     -X OPTIONS \
     https://ai.aimoney.io.vn/api/unified/chat-stream
```

## 🚀 **Deployment Checklist**

- [ ] Backup current nginx configuration
- [ ] Update nginx config to remove static CORS
- [ ] Test nginx configuration
- [ ] Reload nginx
- [ ] Deploy AI Service with dynamic CORS
- [ ] Test CORS from customer domains
- [ ] Update Backend webhook endpoints
- [ ] Test end-to-end chat-plugin flow
