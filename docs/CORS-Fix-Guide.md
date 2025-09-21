# Nginx Configuration Fix for CORS Duplicate Issue
# Cách khắc phục lỗi CORS duplicate trong Nginx

## ❌ Current Issue
Server hiện tại có **duplicate CORS headers**:
```
access-control-allow-origin: https://admin.agent8x.io.vn, https://admin.agent8x.io.vn
```

Nguyên nhân: Cả Nginx và FastAPI đều set CORS headers.

## ✅ Solution

### Option 1: Remove CORS from Nginx (Recommended)

Comment out hoặc remove các dòng CORS trong nginx config:

```nginx
# Comment out these lines in nginx-agent8x.conf
# add_header Access-Control-Allow-Origin $http_origin always;
# add_header Access-Control-Allow-Methods "GET, POST, PUT, DELETE, OPTIONS" always;
# add_header Access-Control-Allow-Headers "Origin, X-Requested-With, Content-Type, Accept, Authorization, X-API-Key" always;
# add_header Access-Control-Allow-Credentials true always;

# Comment out preflight handling
# if ($request_method = OPTIONS) {
#     add_header Access-Control-Allow-Origin $http_origin;
#     add_header Access-Control-Allow-Methods "GET, POST, PUT, DELETE, OPTIONS";
#     add_header Access-Control-Allow-Headers "Origin, X-Requested-With, Content-Type, Accept, Authorization, X-API-Key";
#     add_header Access-Control-Max-Age 600;
#     return 204;
# }
```

### Option 2: Remove CORS from FastAPI

Comment out CORS middleware trong `src/app.py`:

```python
# Comment out this block
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=APP_CONFIG["cors_origins"],
#     allow_credentials=True,
#     allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
#     allow_headers=["*"],
# )
```

## 🧪 Testing Commands

```bash
# Test CORS preflight
curl -X OPTIONS https://ai.aimoney.io.vn/api/unified/chat-stream \
  -H "Origin: https://admin.agent8x.io.vn" \
  -H "Access-Control-Request-Method: POST" \
  -H "Access-Control-Request-Headers: Content-Type" \
  -v

# Check for duplicate headers
curl -X OPTIONS https://ai.aimoney.io.vn/api/unified/chat-stream \
  -H "Origin: https://admin.agent8x.io.vn" \
  -I | grep -i access-control
```

## 📋 Action Items

1. **Immediate Fix**: Remove CORS from nginx config
2. **Deploy**: Restart nginx service
3. **Test**: Verify no duplicate headers
4. **Monitor**: Check frontend works correctly

## 🔧 Recommended Nginx Config

```nginx
server {
    listen 443 ssl http2;
    server_name ai.aimoney.io.vn;
    
    # SSL and security headers only
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";
    add_header Strict-Transport-Security "max-age=63072000; includeSubDomains; preload";
    
    # NO CORS headers - let FastAPI handle CORS
    
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # For streaming responses
        proxy_buffering off;
        proxy_cache off;
        proxy_set_header Connection "";
        proxy_http_version 1.1;
        chunked_transfer_encoding off;
    }
}
```
