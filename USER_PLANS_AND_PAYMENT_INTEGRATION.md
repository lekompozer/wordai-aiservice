# User Plans & Payment Integration Implementation Plan

## 📋 Table of Contents
1. [Overview](#overview)
2. [User Plans Structure](#user-plans-structure)
3. [Database Schema](#database-schema)
4. [Payment Integration Architecture](#payment-integration-architecture)
5. [Implementation Phases](#implementation-phases)
6. [API Specifications](#api-specifications)
7. [SePay Integration with Node.js Microservice](#sepay-integration)
8. [Security & Compliance](#security-compliance)

---

## 1. Overview

Hệ thống User Plans với 4 tiers: **Free**, **Premium**, **Pro**, **VIP**
- Mục tiêu: Tạo doanh thu từ dịch vụ AI Document Processing & Online Testing
- Payment Gateway: **SePay** (Node.js SDK only)
- Architecture: Microservices với Python (main) + Node.js (payment service)

---

## 2. User Plans Structure

### 2.1 Pricing Table

| Feature | Free | Premium | Pro | VIP |
|---------|------|---------|-----|-----|
| **Price** | 0đ | 279k/3mo - 990k/12mo | 447k/3mo - 1,699k/12mo | 747k/3mo - 2,799k/12mo |
| **Storage** | 50MB | 2GB | 15GB | 50GB |
| **AI Chat** | Deepseek (15/day) | 300pts/3mo - 1200pts/12mo | 500pts/3mo - 2000pts/12mo | 1000pts/3mo - 4000pts/12mo |
| **Upload Files** | 10 files | 100 files | Unlimited | Unlimited |
| **Library Files** | Unlimited | 100 files | Unlimited | Unlimited |
| **Documents** | 10 files | 100 files | 1000 files | Unlimited |
| **Secret Files** | 1 doc (no share) | 100 docs+images | 1000 docs+images | Unlimited |
| **AI Edit/Translate** | ❌ | 150 uses (300pts) | 250 uses (500pts) | 500 uses (1000pts) |
| **Online Tests** | Join only (no create) | 150 tests (300pts) | 250 tests (500pts) | 500 tests (1000pts) |

### 2.2 Points System Logic

**AI Points Usage:**
- 1 AI Chat = 2 points
- 1 AI Edit/Translate = 2 points
- 1 Online Test Creation = 2 points

**Examples:**
- Premium 300 points = 150 AI operations
- Pro 500 points = 250 AI operations
- VIP 1000 points = 500 AI operations

---

## 3. Database Schema

### 3.1 New Collections

#### **user_subscriptions** Collection
```python
{
    "_id": ObjectId(),
    "user_id": str,  # Firebase UID
    "plan": str,  # "free", "premium", "pro", "vip"
    "duration": str,  # "3_months", "12_months"
    "price": int,  # Amount paid in VND
    "points_total": int,  # Total points for subscription period
    "points_used": int,  # Points consumed
    "points_remaining": int,  # points_total - points_used

    # Subscription period
    "started_at": datetime,
    "expires_at": datetime,
    "is_active": bool,
    "auto_renew": bool,

    # Payment info
    "payment_id": str,  # Reference to payments collection
    "payment_method": str,  # "BANK_TRANSFER", "VISA", etc.

    # Limits tracking
    "storage_used_mb": float,
    "storage_limit_mb": int,
    "upload_files_count": int,
    "upload_files_limit": int,
    "documents_count": int,
    "documents_limit": int,
    "secret_files_count": int,
    "secret_files_limit": int,

    # Daily limits (reset each day)
    "daily_chat_count": int,  # For Free tier Deepseek
    "daily_chat_limit": int,  # 15 for Free, unlimited for paid
    "last_chat_reset": datetime,

    # Metadata
    "created_at": datetime,
    "updated_at": datetime,
    "cancelled_at": datetime | null,
    "cancellation_reason": str | null
}
```

#### **payments** Collection
```python
{
    "_id": ObjectId(),
    "payment_id": str,  # SePay transaction ID
    "user_id": str,
    "order_invoice_number": str,  # "WA-{timestamp}-{user_short}"

    # Amount
    "amount": int,  # VND
    "currency": str,  # "VND"

    # Subscription info
    "plan": str,  # "premium", "pro", "vip"
    "duration": str,  # "3_months", "12_months"

    # Payment status
    "status": str,  # "pending", "completed", "failed", "cancelled"
    "payment_method": str,  # "BANK_TRANSFER", "VISA", etc.

    # SePay data
    "sepay_order_id": str,
    "sepay_transaction_id": str | null,
    "sepay_response": dict,  # Full SePay webhook data

    # URLs
    "success_url": str,
    "error_url": str,
    "cancel_url": str,

    # Timestamps
    "created_at": datetime,
    "paid_at": datetime | null,
    "expires_at": datetime | null,

    # Metadata
    "ip_address": str,
    "user_agent": str,
    "notes": str | null
}
```

#### **points_transactions** Collection (Audit log)
```python
{
    "_id": ObjectId(),
    "user_id": str,
    "subscription_id": ObjectId,

    # Transaction details
    "type": str,  # "earn", "spend", "refund", "expire"
    "amount": int,  # Points changed (positive/negative)
    "balance_before": int,
    "balance_after": int,

    # Usage context
    "service": str,  # "ai_chat", "ai_edit", "online_test", "subscription"
    "resource_id": str | null,  # Chat ID, document ID, test ID, etc.
    "description": str,

    # Metadata
    "created_at": datetime,
    "ip_address": str | null
}
```

### 3.2 Update Existing Collections

#### **users** Collection - Add fields:
```python
{
    # ... existing fields ...

    # Subscription
    "current_plan": str,  # "free", "premium", "pro", "vip"
    "subscription_id": ObjectId | null,  # Active subscription
    "subscription_expires_at": datetime | null,

    # Quick access to limits (denormalized for performance)
    "points_remaining": int,
    "storage_used_mb": float,
    "storage_limit_mb": int,

    # Last updated
    "plan_updated_at": datetime
}
```

---

## 4. Payment Integration Architecture

### 4.1 Microservices Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    NGINX (Port 80/443)                      │
│                    API Gateway / Reverse Proxy              │
└─────────────────────────────────────────────────────────────┘
                    │                    │
        ┌───────────┘                    └───────────┐
        │                                            │
        ▼                                            ▼
┌─────────────────┐                        ┌─────────────────┐
│  Python Service │                        │  Node.js Service│
│  (Main API)     │◄──────────────────────►│  (Payment)      │
│  Port 8000      │    Internal Network    │  Port 3000      │
│                 │    (Docker Network)    │                 │
│  - FastAPI      │                        │  - Express.js   │
│  - AI Chat      │                        │  - SePay SDK    │
│  - Documents    │                        │  - Webhooks     │
│  - Online Tests │                        │                 │
└────────┬────────┘                        └────────┬────────┘
         │                                          │
         │         ┌────────────────────┐          │
         └────────►│   MongoDB          │◄─────────┘
                   │   Port 27017       │
                   │   (Shared DB)      │
                   └────────────────────┘
```

### 4.2 Docker Compose Configuration

```yaml
version: '3.8'

services:
  # NGINX - Reverse Proxy & API Gateway
  nginx:
    image: nginx:alpine
    container_name: nginx-gateway
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/conf.d:/etc/nginx/conf.d:ro
      - ./nginx/ssl:/etc/nginx/ssl:ro  # SSL certificates
      - ./nginx/logs:/var/log/nginx
    networks:
      - ai-chatbot-network
    depends_on:
      - ai-chatbot-rag
      - payment-service
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "wget", "--quiet", "--tries=1", "--spider", "http://localhost/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  # Python Service - Main API (AI, Documents, Tests)
  ai-chatbot-rag:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: ai-chatbot-rag
    # Don't expose port publicly - only through NGINX
    expose:
      - "8000"
    networks:
      - ai-chatbot-network
    environment:
      # Service URLs
      - PAYMENT_SERVICE_URL=http://payment-service:3000

      # MongoDB
      - MONGODB_URI=mongodb://ai_service_user:ai_service_2025_secure_password@mongodb:27017/ai_service_db?authSource=admin

      # Redis
      - REDIS_URL=redis://redis-server:6379

      # Internal Service Auth
      - INTERNAL_SERVICE_TOKEN=${INTERNAL_SERVICE_TOKEN}

      # Firebase
      - FIREBASE_CREDENTIALS_PATH=/app/firebase-credentials.json

      # Feature Flags
      - ENABLE_SUBSCRIPTIONS=true
      - ENABLE_PAYMENTS=true

      # AI Models
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - GEMINI_API_KEY=${GEMINI_API_KEY}

    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
      - ./uploads:/app/uploads
      - ./firebase-credentials.json:/app/firebase-credentials.json:ro
    depends_on:
      mongodb:
        condition: service_healthy
      redis-server:
        condition: service_healthy
      payment-service:
        condition: service_started
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

  # Node.js Payment Service
  payment-service:
    build:
      context: ./payment-service
      dockerfile: Dockerfile
    container_name: payment-service
    # Don't expose port publicly - only through NGINX
    expose:
      - "3000"
    networks:
      - ai-chatbot-network
    environment:
      # Server Config
      - NODE_ENV=production
      - PORT=3000

      # MongoDB
      - MONGODB_URI=mongodb://ai_service_user:ai_service_2025_secure_password@mongodb:27017/ai_service_db?authSource=admin

      # SePay Configuration
      - SEPAY_ENV=${SEPAY_ENV:-sandbox}  # 'sandbox' or 'production'
      - SEPAY_MERCHANT_ID=${SEPAY_MERCHANT_ID}
      - SEPAY_SECRET_KEY=${SEPAY_SECRET_KEY}

      # Service URLs
      - PYTHON_SERVICE_URL=http://ai-chatbot-rag:8000
      - FRONTEND_URL=${FRONTEND_URL:-https://wordai.vn}

      # Security
      - INTERNAL_SERVICE_TOKEN=${INTERNAL_SERVICE_TOKEN}
      - WEBHOOK_SECRET=${WEBHOOK_SECRET}

      # Logging
      - LOG_LEVEL=info

    volumes:
      - ./payment-service/logs:/app/logs
    depends_on:
      mongodb:
        condition: service_healthy
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "wget", "--quiet", "--tries=1", "--spider", "http://localhost:3000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 20s

  # MongoDB - Shared Database
  mongodb:
    image: mongo:7.0
    container_name: mongodb
    ports:
      - "27017:27017"  # Can be removed in production for security
    networks:
      - ai-chatbot-network
    environment:
      - MONGO_INITDB_ROOT_USERNAME=admin
      - MONGO_INITDB_ROOT_PASSWORD=${MONGO_ROOT_PASSWORD}
      - MONGO_INITDB_DATABASE=ai_service_db
    volumes:
      - mongodb_data:/data/db
      - mongodb_config:/data/configdb
      - ./mongo-init.js:/docker-entrypoint-initdb.d/mongo-init.js:ro
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "mongosh", "--eval", "db.adminCommand('ping')"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 20s
    command: ["--auth"]

  # Redis - Cache & Session Store
  redis-server:
    image: redis:7-alpine
    container_name: redis-server
    ports:
      - "6379:6379"  # Can be removed in production
    networks:
      - ai-chatbot-network
    volumes:
      - redis_data:/data
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    command: ["redis-server", "--appendonly", "yes"]

  # Optional: Redis Commander (Development only)
  redis-commander:
    image: rediscommander/redis-commander:latest
    container_name: redis-commander
    profiles:
      - dev  # Only start with: docker compose --profile dev up
    ports:
      - "8081:8081"
    networks:
      - ai-chatbot-network
    environment:
      - REDIS_HOSTS=local:redis-server:6379
    depends_on:
      - redis-server

  # Optional: Mongo Express (Development only)
  mongo-express:
    image: mongo-express:latest
    container_name: mongo-express
    profiles:
      - dev  # Only start with: docker compose --profile dev up
    ports:
      - "8082:8081"
    networks:
      - ai-chatbot-network
    environment:
      - ME_CONFIG_MONGODB_ADMINUSERNAME=admin
      - ME_CONFIG_MONGODB_ADMINPASSWORD=${MONGO_ROOT_PASSWORD}
      - ME_CONFIG_MONGODB_URL=mongodb://admin:${MONGO_ROOT_PASSWORD}@mongodb:27017/
      - ME_CONFIG_BASICAUTH_USERNAME=admin
      - ME_CONFIG_BASICAUTH_PASSWORD=${MONGO_EXPRESS_PASSWORD}
    depends_on:
      - mongodb

networks:
  ai-chatbot-network:
    driver: bridge
    ipam:
      config:
        - subnet: 172.20.0.0/16

volumes:
  mongodb_data:
    driver: local
  mongodb_config:
    driver: local
  redis_data:
    driver: local
```

### 4.3 NGINX Configuration

**nginx/nginx.conf** (Main Configuration)
```nginx
user nginx;
worker_processes auto;
error_log /var/log/nginx/error.log warn;
pid /var/run/nginx.pid;

events {
    worker_connections 2048;
    use epoll;
    multi_accept on;
}

http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;

    # Logging
    log_format main '$remote_addr - $remote_user [$time_local] "$request" '
                    '$status $body_bytes_sent "$http_referer" '
                    '"$http_user_agent" "$http_x_forwarded_for" '
                    'rt=$request_time uct="$upstream_connect_time" '
                    'uht="$upstream_header_time" urt="$upstream_response_time"';

    access_log /var/log/nginx/access.log main;

    # Performance
    sendfile on;
    tcp_nopush on;
    tcp_nodelay on;
    keepalive_timeout 65;
    types_hash_max_size 2048;
    client_max_body_size 100M;

    # Gzip Compression
    gzip on;
    gzip_vary on;
    gzip_proxied any;
    gzip_comp_level 6;
    gzip_types text/plain text/css text/xml text/javascript
               application/json application/javascript application/xml+rss
               application/rss+xml font/truetype font/opentype
               application/vnd.ms-fontobject image/svg+xml;

    # Security Headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "no-referrer-when-downgrade" always;

    # Rate Limiting Zones
    limit_req_zone $binary_remote_addr zone=general:10m rate=100r/m;
    limit_req_zone $binary_remote_addr zone=payment:10m rate=10r/m;
    limit_req_zone $binary_remote_addr zone=auth:10m rate=5r/m;

    # Upstream Services
    upstream python_service {
        least_conn;
        server ai-chatbot-rag:8000 max_fails=3 fail_timeout=30s;
        keepalive 32;
    }

    upstream payment_service {
        least_conn;
        server payment-service:3000 max_fails=3 fail_timeout=30s;
        keepalive 32;
    }

    # Include site configurations
    include /etc/nginx/conf.d/*.conf;
}
```

**nginx/conf.d/wordai.conf** (Site Configuration)
```nginx
# HTTP Server - Redirect to HTTPS
server {
    listen 80;
    listen [::]:80;
    server_name wordai.vn www.wordai.vn;

    # Let's Encrypt challenge
    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    # Redirect all HTTP to HTTPS
    location / {
        return 301 https://$server_name$request_uri;
    }
}

# HTTPS Server - Main API Gateway
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name wordai.vn www.wordai.vn;

    # SSL Certificates (Let's Encrypt)
    ssl_certificate /etc/nginx/ssl/fullchain.pem;
    ssl_certificate_key /etc/nginx/ssl/privkey.pem;
    ssl_trusted_certificate /etc/nginx/ssl/chain.pem;

    # SSL Configuration
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers 'ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384';
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;
    ssl_stapling on;
    ssl_stapling_verify on;

    # Security Headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline';" always;

    # Root location
    location / {
        root /var/www/html;
        index index.html;
        try_files $uri $uri/ /index.html;
    }

    # Health Check Endpoint
    location /health {
        access_log off;
        return 200 "healthy\n";
        add_header Content-Type text/plain;
    }

    # Python Service - Main API Routes
    location /api/v1/ {
        limit_req zone=general burst=20 nodelay;

        proxy_pass http://python_service;
        proxy_http_version 1.1;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Request-ID $request_id;

        proxy_set_header Connection "";
        proxy_buffering off;

        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 300s;  # 5 minutes for AI operations

        proxy_next_upstream error timeout invalid_header http_500 http_502 http_503;
        proxy_next_upstream_tries 2;
    }

    # Payment Service - Checkout & Payment Routes
    location /api/payment/ {
        limit_req zone=payment burst=5 nodelay;

        proxy_pass http://payment_service/api/;
        proxy_http_version 1.1;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Request-ID $request_id;

        proxy_set_header Connection "";

        proxy_connect_timeout 30s;
        proxy_send_timeout 30s;
        proxy_read_timeout 60s;
    }

    # SePay Webhook (No rate limit for payment gateway)
    location /api/webhooks/sepay {
        # Allow only SePay IPs (add their IP ranges)
        # allow 123.45.67.0/24;  # SePay IP range
        # deny all;

        proxy_pass http://payment_service/api/webhooks/sepay;
        proxy_http_version 1.1;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        proxy_connect_timeout 10s;
        proxy_send_timeout 10s;
        proxy_read_timeout 30s;
    }

    # Authentication Routes (stricter rate limit)
    location ~ ^/api/v1/(auth|login|register) {
        limit_req zone=auth burst=3 nodelay;

        proxy_pass http://python_service;
        proxy_http_version 1.1;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Admin Routes (optional: IP whitelist)
    location /api/v1/admin/ {
        # Only allow from specific IPs
        # allow 123.45.67.89;  # Your office IP
        # deny all;

        limit_req zone=general burst=10 nodelay;

        proxy_pass http://python_service;
        proxy_http_version 1.1;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # WebSocket Support (if needed)
    location /ws/ {
        proxy_pass http://python_service;
        proxy_http_version 1.1;

        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;

        proxy_read_timeout 86400;  # 24 hours
    }

    # Static Files (if serving from backend)
    location /static/ {
        alias /var/www/static/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # Uploaded Files
    location /uploads/ {
        alias /var/www/uploads/;
        expires 1y;
        add_header Cache-Control "public";

        # Security: Prevent script execution
        add_header X-Content-Type-Options nosniff;
    }

    # API Documentation
    location /docs {
        proxy_pass http://python_service/docs;
        proxy_http_version 1.1;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    # Block access to sensitive files
    location ~ /\. {
        deny all;
        access_log off;
        log_not_found off;
    }

    location ~ ~$ {
        deny all;
        access_log off;
        log_not_found off;
    }
}
```

### 4.4 Environment Variables (.env file)

```bash
# ================================================
# WORDAI SERVICE - ENVIRONMENT CONFIGURATION
# ================================================

# -------------------- MongoDB --------------------
MONGO_ROOT_PASSWORD=your_super_secure_mongo_root_password_here
MONGODB_URI=mongodb://ai_service_user:ai_service_2025_secure_password@mongodb:27017/ai_service_db?authSource=admin

# -------------------- Redis --------------------
REDIS_URL=redis://redis-server:6379

# -------------------- SePay Payment Gateway --------------------
SEPAY_ENV=sandbox  # Change to 'production' when going live
SEPAY_MERCHANT_ID=your_sepay_merchant_id
SEPAY_SECRET_KEY=your_sepay_secret_key

# -------------------- Service URLs --------------------
PAYMENT_SERVICE_URL=http://payment-service:3000
PYTHON_SERVICE_URL=http://ai-chatbot-rag:8000
FRONTEND_URL=https://wordai.vn

# -------------------- Security Tokens --------------------
# Generate with: openssl rand -hex 32
INTERNAL_SERVICE_TOKEN=your_internal_service_token_32_chars_minimum
WEBHOOK_SECRET=your_webhook_secret_32_chars_minimum

# -------------------- Firebase --------------------
FIREBASE_PROJECT_ID=your-firebase-project-id
FIREBASE_CREDENTIALS_PATH=/app/firebase-credentials.json

# -------------------- AI API Keys --------------------
OPENAI_API_KEY=sk-your-openai-api-key
GEMINI_API_KEY=your-gemini-api-key
DEEPSEEK_API_KEY=your-deepseek-api-key

# -------------------- Feature Flags --------------------
ENABLE_SUBSCRIPTIONS=true
ENABLE_PAYMENTS=true
ENABLE_AI_CHAT=true
ENABLE_ONLINE_TESTS=true

# -------------------- Development Tools --------------------
# For mongo-express and redis-commander (dev only)
MONGO_EXPRESS_PASSWORD=your_mongo_express_password

# -------------------- Email Service (Optional) --------------------
BREVO_API_KEY=your_brevo_api_key
EMAIL_FROM=noreply@wordai.vn

# -------------------- Logging & Monitoring --------------------
LOG_LEVEL=info
SENTRY_DSN=your_sentry_dsn_if_using
```

### 4.5 Docker Deployment Commands

**Initial Setup:**
```bash
# 1. Create Docker network
docker network create ai-chatbot-network

# 2. Build images
docker compose build

# 3. Start all services
docker compose up -d

# 4. Check service health
docker compose ps
docker compose logs -f

# 5. Run database migrations
docker exec ai-chatbot-rag python scripts/migrate_add_user_plans.py
```

**Development Mode (with dev tools):**
```bash
# Start with Redis Commander and Mongo Express
docker compose --profile dev up -d

# Access tools:
# - Mongo Express: http://localhost:8082
# - Redis Commander: http://localhost:8081
```

**Production Deployment:**
```bash
# Pull latest code
git pull origin main

# Rebuild and restart services
docker compose build --no-cache
docker compose up -d --force-recreate

# Verify health
curl https://wordai.vn/health
curl https://wordai.vn/api/v1/health
```

**Monitoring & Logs:**
```bash
# View all logs
docker compose logs -f

# View specific service logs
docker compose logs -f ai-chatbot-rag
docker compose logs -f payment-service
docker compose logs -f nginx

# Check resource usage
docker stats

# Access containers
docker exec -it ai-chatbot-rag bash
docker exec -it payment-service sh
```

**Backup & Restore:**
```bash
# Backup MongoDB
docker exec mongodb mongodump --out /data/backup --authenticationDatabase admin -u admin -p ${MONGO_ROOT_PASSWORD}

# Restore MongoDB
docker exec mongodb mongorestore /data/backup --authenticationDatabase admin -u admin -p ${MONGO_ROOT_PASSWORD}

# Backup Redis
docker exec redis-server redis-cli SAVE
docker cp redis-server:/data/dump.rdb ./backup/redis-dump.rdb
```

**Scaling Services:**
```bash
# Scale payment service (if needed)
docker compose up -d --scale payment-service=3

# Scale python service
docker compose up -d --scale ai-chatbot-rag=2
```

### 4.6 SSL Certificate Setup (Let's Encrypt)

**Install Certbot:**
```bash
# On host machine
sudo apt update
sudo apt install certbot

# Get certificate
sudo certbot certonly --standalone -d wordai.vn -d www.wordai.vn

# Copy certificates to nginx volume
sudo cp /etc/letsencrypt/live/wordai.vn/fullchain.pem ./nginx/ssl/
sudo cp /etc/letsencrypt/live/wordai.vn/privkey.pem ./nginx/ssl/
sudo cp /etc/letsencrypt/live/wordai.vn/chain.pem ./nginx/ssl/

# Set permissions
sudo chmod 644 ./nginx/ssl/fullchain.pem
sudo chmod 600 ./nginx/ssl/privkey.pem

# Restart nginx
docker compose restart nginx
```

**Auto-renewal (Cron job):**
```bash
# Add to crontab
0 0 1 * * certbot renew --quiet && docker compose restart nginx
```

---

## 5. Implementation Phases

### Phase 1: Database & Models (Week 1)
**Priority: HIGH**

#### Tasks:
- [ ] Create database schemas for `user_subscriptions`, `payments`, `points_transactions`
- [ ] Update `users` collection with subscription fields
- [ ] Create MongoDB indexes for performance
- [ ] Implement Python models with Pydantic
- [ ] Create migration scripts for existing users (set all to "free" plan)

#### Files to Create/Update:
```
src/models/subscription.py          # New: Pydantic models
src/models/payment.py               # New: Payment models
src/services/subscription_service.py # New: Business logic
src/services/points_service.py      # New: Points management
scripts/migrate_add_user_plans.py   # Migration script
```

#### Deliverables:
✅ All users have `current_plan = "free"` with default limits
✅ Database ready for subscriptions
✅ Points system foundation

---

### Phase 2: Node.js Payment Microservice (Week 2)
**Priority: HIGH**

#### Tasks:
- [ ] Set up Node.js + Express.js project structure
- [ ] Install SePay SDK: `npm install sepay-pg-node`
- [ ] Implement payment initiation endpoints
- [ ] Implement SePay webhook handler
- [ ] Connect to shared MongoDB
- [ ] Create Docker image for payment service
- [ ] Configure inter-service communication

#### Directory Structure:
```
payment-service/
├── Dockerfile
├── package.json
├── src/
│   ├── index.js                 # Express server
│   ├── config/
│   │   ├── sepay.js            # SePay client initialization
│   │   └── mongodb.js          # MongoDB connection
│   ├── routes/
│   │   ├── checkout.js         # POST /checkout
│   │   ├── webhooks.js         # POST /webhooks/sepay
│   │   └── verify.js           # GET /payments/:id/verify
│   ├── controllers/
│   │   ├── paymentController.js
│   │   └── webhookController.js
│   ├── models/
│   │   └── Payment.js          # Mongoose models
│   ├── services/
│   │   ├── sepayService.js     # SePay operations
│   │   └── notificationService.js # Notify Python service
│   └── middleware/
│       ├── auth.js             # JWT verification
│       └── validateWebhook.js  # SePay signature validation
├── tests/
└── README.md
```

#### Key Files:

**payment-service/src/config/sepay.js**
```javascript
const { SePayPgClient } = require('sepay-pg-node');

const sepayClient = new SePayPgClient({
  env: process.env.SEPAY_ENV || 'sandbox',
  merchant_id: process.env.SEPAY_MERCHANT_ID,
  secret_key: process.env.SEPAY_SECRET_KEY
});

module.exports = sepayClient;
```

**payment-service/src/routes/checkout.js**
```javascript
const express = require('express');
const router = express.Router();
const paymentController = require('../controllers/paymentController');
const { verifyFirebaseToken } = require('../middleware/auth');

// Initialize checkout
router.post('/checkout', verifyFirebaseToken, paymentController.initCheckout);

// Get payment status
router.get('/payments/:orderId/status', verifyFirebaseToken, paymentController.getPaymentStatus);

module.exports = router;
```

**payment-service/Dockerfile**
```dockerfile
FROM node:18-alpine

WORKDIR /app

COPY package*.json ./
RUN npm ci --only=production

COPY . .

EXPOSE 3000

CMD ["node", "src/index.js"]
```

#### Deliverables:
✅ Payment service running on port 3000
✅ SePay integration working in sandbox
✅ Webhook endpoint receiving payment notifications
✅ Communication with Python service via HTTP

---

### Phase 3: Python API Integration (Week 3)
**Priority: HIGH**

#### Tasks:
- [ ] Create subscription management endpoints in Python
- [ ] Implement plan upgrade/downgrade logic
- [ ] Create payment initiation flow (Python → Node.js)
- [ ] Handle payment webhooks (Node.js → Python)
- [ ] Implement points tracking system
- [ ] Add subscription validation middleware

#### Files to Create/Update:
```
src/api/subscription_routes.py      # New: Subscription endpoints
src/api/payment_routes.py           # New: Payment-related endpoints
src/services/payment_client.py      # New: HTTP client to Node.js service
src/middleware/subscription_check.py # New: Check user limits
src/services/usage_limiter.py       # New: Enforce plan limits
```

#### New API Endpoints:

**Subscription Management:**
```python
# Get current subscription
GET /api/v1/subscription/current

# Get available plans
GET /api/v1/subscription/plans

# Initiate upgrade/purchase
POST /api/v1/subscription/upgrade
{
    "plan": "premium",  # "premium", "pro", "vip"
    "duration": "3_months"  # "3_months", "12_months"
}

# Cancel subscription
POST /api/v1/subscription/cancel

# Get points history
GET /api/v1/subscription/points/history
```

**Payment Endpoints:**
```python
# Get payment history
GET /api/v1/payments/history

# Get payment details
GET /api/v1/payments/{payment_id}

# Verify payment status
GET /api/v1/payments/{payment_id}/verify
```

#### Deliverables:
✅ Users can upgrade plans via API
✅ Payment flow: Python → Node.js → SePay
✅ Webhook flow: SePay → Node.js → Python → Activate subscription
✅ Points system tracking all operations

---

### Phase 4: Usage Enforcement (Week 4)
**Priority: MEDIUM**

#### Tasks:
- [ ] Add middleware to check limits before operations
- [ ] Implement storage quota enforcement
- [ ] Add points deduction for AI operations
- [ ] Implement daily chat limits for Free tier
- [ ] Add plan restriction checks for features
- [ ] Create usage dashboard data endpoints

#### Implementation:

**src/middleware/subscription_check.py**
```python
from functools import wraps
from fastapi import HTTPException, status
from src.services.subscription_service import SubscriptionService

def require_plan(min_plan: str):
    """
    Decorator to require minimum plan tier
    Usage: @require_plan("premium")
    """
    plan_hierarchy = {"free": 0, "premium": 1, "pro": 2, "vip": 3}

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            user_id = kwargs.get("user_id")
            sub_service = SubscriptionService()
            user_sub = await sub_service.get_user_subscription(user_id)

            user_plan_level = plan_hierarchy.get(user_sub.plan, 0)
            required_level = plan_hierarchy.get(min_plan, 0)

            if user_plan_level < required_level:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"This feature requires {min_plan} plan or higher"
                )

            return await func(*args, **kwargs)
        return wrapper
    return decorator

def require_points(points_cost: int):
    """
    Decorator to check and deduct points
    Usage: @require_points(2)
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            user_id = kwargs.get("user_id")
            points_service = PointsService()

            # Check if user has enough points
            has_points = await points_service.check_points(user_id, points_cost)
            if not has_points:
                raise HTTPException(
                    status_code=status.HTTP_402_PAYMENT_REQUIRED,
                    detail="Insufficient points. Please upgrade your plan."
                )

            # Execute function
            result = await func(*args, **kwargs)

            # Deduct points after successful operation
            await points_service.deduct_points(
                user_id=user_id,
                amount=points_cost,
                service=func.__name__,
                resource_id=result.get("id")
            )

            return result
        return wrapper
    return decorator
```

**Usage in existing routes:**
```python
from src.middleware.subscription_check import require_plan, require_points

# Online Test Creation (requires Premium+)
@router.post("/create-ai-test")
@require_plan("premium")
@require_points(2)
async def create_ai_test(...):
    # Existing code
    pass

# Document AI Edit (requires Premium+)
@router.post("/documents/{doc_id}/edit")
@require_plan("premium")
@require_points(2)
async def edit_document_ai(...):
    # Existing code
    pass

# File upload (check storage limit)
@router.post("/files/upload")
async def upload_file(user_id: str, file: UploadFile):
    sub_service = SubscriptionService()
    can_upload = await sub_service.check_storage_limit(user_id, file.size)
    if not can_upload:
        raise HTTPException(
            status_code=status.HTTP_507_INSUFFICIENT_STORAGE,
            detail="Storage limit exceeded. Please upgrade your plan."
        )
    # Continue upload
```

#### Deliverables:
✅ All features enforce plan restrictions
✅ Points automatically deducted for AI operations
✅ Storage limits enforced on uploads
✅ Free tier limited to 15 Deepseek chats/day
✅ Graceful error messages with upgrade prompts

---

### Phase 5: Frontend Integration (Week 5)
**Priority: MEDIUM**

#### Tasks:
- [ ] Create subscription management UI
- [ ] Add plan comparison page
- [ ] Implement payment checkout flow
- [ ] Add usage dashboard
- [ ] Show plan limits in user profile
- [ ] Add upgrade prompts when limits hit

#### UI Components Needed:
```
components/
├── subscription/
│   ├── PlanCard.tsx              # Display plan features
│   ├── PlanComparison.tsx        # Compare all plans
│   ├── UpgradeModal.tsx          # Upgrade prompt
│   ├── CheckoutForm.tsx          # Payment form
│   ├── SubscriptionStatus.tsx   # Current plan info
│   └── UsageDashboard.tsx       # Points, storage, limits
└── payments/
    ├── PaymentHistory.tsx        # Past payments
    └── PaymentSuccess.tsx        # Success page
```

#### Key Pages:
```
/pricing              # Plan comparison & purchase
/subscription         # Manage subscription
/subscription/usage   # Usage statistics
/payments/checkout    # Payment form
/payments/success     # Payment confirmation
/payments/history     # Transaction history
```

#### Deliverables:
✅ Beautiful pricing page
✅ One-click upgrade flow
✅ Real-time usage display
✅ Payment history view

---

### Phase 6: Testing & Security (Week 6)
**Priority: HIGH**

#### Tasks:
- [ ] Write unit tests for subscription logic
- [ ] Test payment flows (sandbox)
- [ ] Test webhook handling
- [ ] Security audit of payment service
- [ ] Penetration testing
- [ ] Load testing (concurrent payments)
- [ ] Test subscription expiration logic
- [ ] Test points refund scenarios

#### Security Checklist:
- [ ] SePay webhook signature validation
- [ ] HTTPS only for payment endpoints
- [ ] Rate limiting on payment endpoints
- [ ] Firebase token validation
- [ ] SQL/NoSQL injection prevention
- [ ] XSS protection
- [ ] CORS configuration
- [ ] Secrets management (env variables)
- [ ] Payment data encryption at rest
- [ ] Audit logging for all payment events

#### Deliverables:
✅ 90%+ test coverage
✅ Security audit report
✅ Load test results
✅ Penetration test passed

---

### Phase 7: Production Deployment (Week 7)
**Priority: HIGH**

#### Tasks:
- [ ] Register SePay production merchant account
- [ ] Configure production environment variables
- [ ] Set up monitoring & alerting
- [ ] Deploy payment service to production
- [ ] Configure NGINX for payment routes
- [ ] Set up SSL certificates
- [ ] Test production payment flow
- [ ] Create rollback plan
- [ ] Train support team

#### Production Checklist:
- [ ] SePay production credentials configured
- [ ] MongoDB backups configured
- [ ] Payment logs retention (7 years for compliance)
- [ ] Error tracking (Sentry/similar)
- [ ] Payment reconciliation dashboard
- [ ] Customer support documentation
- [ ] Refund process documented
- [ ] Legal: Terms of Service updated
- [ ] Legal: Privacy Policy updated
- [ ] Legal: Refund Policy created

#### Deliverables:
✅ Payment system live in production
✅ Monitoring dashboards active
✅ Support team trained
✅ Legal compliance complete

---

## 6. API Specifications

### 6.1 Python API → Node.js Payment Service

**Initiate Checkout (Python calls Node.js)**
```http
POST http://payment-service:3000/api/checkout
Authorization: Bearer <internal_service_token>
Content-Type: application/json

{
  "user_id": "firebase_uid_123",
  "plan": "premium",
  "duration": "3_months",
  "user_email": "user@example.com",
  "user_name": "John Doe"
}

Response:
{
  "checkout_url": "https://sandbox.sepay.vn/checkout/abc123",
  "order_invoice_number": "WA-1730123456-abc",
  "expires_at": "2025-11-05T10:00:00Z"
}
```

### 6.2 SePay Webhook → Node.js Service

**Payment Notification**
```http
POST https://yourapi.com/api/webhooks/sepay
X-SePay-Signature: <signature>
Content-Type: application/json

{
  "order_invoice_number": "WA-1730123456-abc",
  "transaction_id": "sepay_txn_123",
  "status": "SUCCESS",
  "amount": 279000,
  "paid_at": "2025-11-05T09:45:00Z",
  "payment_method": "BANK_TRANSFER"
}
```

### 6.3 Node.js → Python API Callback

**Activate Subscription**
```http
POST http://ai-chatbot-rag:8000/internal/subscriptions/activate
Authorization: Bearer <internal_service_token>
Content-Type: application/json

{
  "user_id": "firebase_uid_123",
  "payment_id": "sepay_txn_123",
  "order_invoice_number": "WA-1730123456-abc",
  "plan": "premium",
  "duration": "3_months",
  "paid_amount": 279000,
  "paid_at": "2025-11-05T09:45:00Z"
}

Response:
{
  "subscription_id": "673456789abcdef",
  "expires_at": "2026-02-05T09:45:00Z",
  "points_granted": 300,
  "message": "Subscription activated successfully"
}
```

### 6.4 Admin Management APIs

#### **Admin - Subscription Management**

**Get All Subscriptions (with filters)**
```http
GET /api/v1/admin/subscriptions
Authorization: Bearer <admin_token>
Query Parameters:
  - plan: string (optional) - "free", "premium", "pro", "vip"
  - status: string (optional) - "active", "expired", "cancelled"
  - page: int (default: 1)
  - limit: int (default: 20)

Response:
{
  "subscriptions": [
    {
      "subscription_id": "673456789abcdef",
      "user_id": "firebase_uid_123",
      "user_email": "user@example.com",
      "user_name": "John Doe",
      "plan": "premium",
      "duration": "3_months",
      "started_at": "2025-11-05T09:45:00Z",
      "expires_at": "2026-02-05T09:45:00Z",
      "is_active": true,
      "points_remaining": 285,
      "points_total": 300,
      "storage_used_mb": 145.5,
      "storage_limit_mb": 2048
    }
  ],
  "total": 156,
  "page": 1,
  "pages": 8
}
```

**Get User Subscription Details**
```http
GET /api/v1/admin/subscriptions/user/{user_id}
Authorization: Bearer <admin_token>

Response:
{
  "subscription": {
    "subscription_id": "673456789abcdef",
    "plan": "premium",
    "started_at": "2025-11-05T09:45:00Z",
    "expires_at": "2026-02-05T09:45:00Z",
    "is_active": true,
    "points_total": 300,
    "points_used": 15,
    "points_remaining": 285,
    "payment_id": "sepay_txn_123",
    "payment_method": "BANK_TRANSFER"
  },
  "usage": {
    "storage_used_mb": 145.5,
    "storage_limit_mb": 2048,
    "upload_files_count": 45,
    "documents_count": 12,
    "secret_files_count": 8
  },
  "history": [
    {
      "date": "2025-11-05",
      "service": "ai_chat",
      "points_spent": 2,
      "description": "AI Chat Session"
    }
  ]
}
```

**Manually Activate Subscription (For bank transfer, webhook failures)**
```http
POST /api/v1/admin/subscriptions/activate
Authorization: Bearer <admin_token>
Content-Type: application/json

{
  "user_id": "firebase_uid_123",
  "plan": "premium",
  "duration": "3_months",
  "payment_method": "BANK_TRANSFER_MANUAL",
  "payment_reference": "Bank ref: 1234567890",
  "notes": "Customer transferred via bank, verified by admin",
  "activated_by_admin": "admin_firebase_uid"
}

Response:
{
  "subscription_id": "673456789abcdef",
  "user_id": "firebase_uid_123",
  "plan": "premium",
  "expires_at": "2026-02-05T09:45:00Z",
  "points_granted": 300,
  "message": "Subscription manually activated by admin"
}
```

**Cancel/Refund Subscription**
```http
POST /api/v1/admin/subscriptions/{subscription_id}/cancel
Authorization: Bearer <admin_token>
Content-Type: application/json

{
  "reason": "User requested refund due to service issue",
  "refund_amount": 279000,
  "refund_method": "BANK_TRANSFER",
  "cancelled_by_admin": "admin_firebase_uid"
}

Response:
{
  "subscription_id": "673456789abcdef",
  "status": "cancelled",
  "cancelled_at": "2025-11-06T10:00:00Z",
  "refund_amount": 279000,
  "message": "Subscription cancelled and refund initiated"
}
```

**Extend Subscription (Promotional/Support)**
```http
POST /api/v1/admin/subscriptions/{subscription_id}/extend
Authorization: Bearer <admin_token>
Content-Type: application/json

{
  "extend_days": 30,
  "reason": "Service outage compensation",
  "extended_by_admin": "admin_firebase_uid"
}

Response:
{
  "subscription_id": "673456789abcdef",
  "old_expires_at": "2026-02-05T09:45:00Z",
  "new_expires_at": "2026-03-07T09:45:00Z",
  "message": "Subscription extended by 30 days"
}
```

#### **Admin - Points Management**

**Grant Points to User (Promotional/Compensation)**
```http
POST /api/v1/admin/points/grant
Authorization: Bearer <admin_token>
Content-Type: application/json

{
  "user_id": "firebase_uid_123",
  "points_amount": 50,
  "reason": "Black Friday promotion",
  "granted_by_admin": "admin_firebase_uid"
}

Response:
{
  "user_id": "firebase_uid_123",
  "points_before": 285,
  "points_granted": 50,
  "points_after": 335,
  "message": "Points granted successfully"
}
```

**Deduct Points (Abuse/Correction)**
```http
POST /api/v1/admin/points/deduct
Authorization: Bearer <admin_token>
Content-Type: application/json

{
  "user_id": "firebase_uid_123",
  "points_amount": 20,
  "reason": "Service abuse detected",
  "deducted_by_admin": "admin_firebase_uid"
}

Response:
{
  "user_id": "firebase_uid_123",
  "points_before": 335,
  "points_deducted": 20,
  "points_after": 315,
  "message": "Points deducted successfully"
}
```

**Get Points Transaction History**
```http
GET /api/v1/admin/points/transactions
Authorization: Bearer <admin_token>
Query Parameters:
  - user_id: string (optional)
  - service: string (optional) - "ai_chat", "ai_edit", "online_test"
  - type: string (optional) - "earn", "spend", "refund", "expire"
  - start_date: date (optional)
  - end_date: date (optional)
  - page: int (default: 1)
  - limit: int (default: 50)

Response:
{
  "transactions": [
    {
      "transaction_id": "6734567890abcdef",
      "user_id": "firebase_uid_123",
      "user_email": "user@example.com",
      "type": "spend",
      "amount": -2,
      "balance_before": 300,
      "balance_after": 298,
      "service": "ai_chat",
      "description": "AI Chat Session",
      "created_at": "2025-11-05T10:15:00Z"
    }
  ],
  "total": 245,
  "page": 1,
  "pages": 5
}
```

#### **Admin - Payment Management**

**Get All Payments (for reconciliation)**
```http
GET /api/v1/admin/payments
Authorization: Bearer <admin_token>
Query Parameters:
  - status: string (optional) - "pending", "completed", "failed", "cancelled"
  - payment_method: string (optional) - "BANK_TRANSFER", "VISA", etc.
  - start_date: date (optional)
  - end_date: date (optional)
  - min_amount: int (optional)
  - max_amount: int (optional)
  - page: int (default: 1)
  - limit: int (default: 50)

Response:
{
  "payments": [
    {
      "payment_id": "sepay_txn_123",
      "order_invoice_number": "WA-1730123456-abc",
      "user_id": "firebase_uid_123",
      "user_email": "user@example.com",
      "plan": "premium",
      "duration": "3_months",
      "amount": 279000,
      "currency": "VND",
      "status": "completed",
      "payment_method": "BANK_TRANSFER",
      "created_at": "2025-11-05T09:30:00Z",
      "paid_at": "2025-11-05T09:45:00Z"
    }
  ],
  "total": 342,
  "total_amount": 95418000,
  "page": 1,
  "pages": 7
}
```

**Get Payment Details**
```http
GET /api/v1/admin/payments/{payment_id}
Authorization: Bearer <admin_token>

Response:
{
  "payment": {
    "payment_id": "sepay_txn_123",
    "order_invoice_number": "WA-1730123456-abc",
    "user_id": "firebase_uid_123",
    "user_email": "user@example.com",
    "user_name": "John Doe",
    "plan": "premium",
    "duration": "3_months",
    "amount": 279000,
    "currency": "VND",
    "status": "completed",
    "payment_method": "BANK_TRANSFER",
    "sepay_transaction_id": "sepay_123456",
    "created_at": "2025-11-05T09:30:00Z",
    "paid_at": "2025-11-05T09:45:00Z",
    "ip_address": "123.45.67.89",
    "user_agent": "Mozilla/5.0..."
  },
  "subscription": {
    "subscription_id": "673456789abcdef",
    "is_active": true,
    "expires_at": "2026-02-05T09:45:00Z"
  },
  "sepay_response": {
    // Full SePay webhook data
  }
}
```

**Reconciliation Report**
```http
GET /api/v1/admin/payments/reconciliation
Authorization: Bearer <admin_token>
Query Parameters:
  - start_date: date (required)
  - end_date: date (required)

Response:
{
  "period": {
    "start_date": "2025-11-01",
    "end_date": "2025-11-30"
  },
  "summary": {
    "total_payments": 145,
    "completed_payments": 138,
    "failed_payments": 5,
    "pending_payments": 2,
    "total_revenue": 40530000,
    "by_plan": {
      "premium": {"count": 85, "amount": 23715000},
      "pro": {"count": 42, "amount": 18774000},
      "vip": {"count": 11, "amount": 8217000}
    },
    "by_duration": {
      "3_months": {"count": 98, "amount": 27342000},
      "12_months": {"count": 40, "amount": 39600000}
    }
  },
  "details": [
    // ... detailed payment list
  ]
}
```

**Manually Process Failed Payment**
```http
POST /api/v1/admin/payments/{payment_id}/process
Authorization: Bearer <admin_token>
Content-Type: application/json

{
  "action": "mark_as_paid",  // or "cancel", "refund"
  "notes": "Customer paid via bank transfer, verified manually",
  "processed_by_admin": "admin_firebase_uid"
}

Response:
{
  "payment_id": "sepay_txn_123",
  "old_status": "pending",
  "new_status": "completed",
  "subscription_activated": true,
  "message": "Payment processed and subscription activated"
}
```

#### **Admin - Dashboard Statistics**

**Get Dashboard Overview**
```http
GET /api/v1/admin/dashboard/overview
Authorization: Bearer <admin_token>

Response:
{
  "users": {
    "total": 1250,
    "free": 890,
    "premium": 215,
    "pro": 105,
    "vip": 40,
    "new_this_month": 78
  },
  "revenue": {
    "today": 1395000,
    "this_week": 8370000,
    "this_month": 40530000,
    "mrr": 13510000,
    "arr": 162120000
  },
  "subscriptions": {
    "active": 360,
    "expiring_7_days": 12,
    "expiring_30_days": 45,
    "cancelled_this_month": 8,
    "churn_rate": 2.2
  },
  "usage": {
    "total_storage_gb": 2450,
    "total_documents": 15680,
    "total_tests_created": 3420,
    "ai_operations_today": 2340
  },
  "conversion": {
    "free_to_paid_rate": 28.8,
    "trial_to_paid_rate": 45.5,
    "upgrade_rate": 12.3
  }
}
```

#### **Admin - User Management**

**Get User Details with Subscription**
```http
GET /api/v1/admin/users/{user_id}
Authorization: Bearer <admin_token>

Response:
{
  "user": {
    "user_id": "firebase_uid_123",
    "email": "user@example.com",
    "name": "John Doe",
    "created_at": "2025-01-15T08:00:00Z",
    "last_login": "2025-11-05T09:30:00Z"
  },
  "subscription": {
    "plan": "premium",
    "expires_at": "2026-02-05T09:45:00Z",
    "is_active": true,
    "points_remaining": 285,
    "auto_renew": false
  },
  "usage": {
    "storage_used_mb": 145.5,
    "documents_count": 12,
    "tests_created": 8,
    "ai_operations_total": 15
  },
  "payments_history": [
    {
      "date": "2025-11-05",
      "amount": 279000,
      "plan": "premium",
      "duration": "3_months"
    }
  ]
}
```

**Change User Plan (Override)**
```http
POST /api/v1/admin/users/{user_id}/change-plan
Authorization: Bearer <admin_token>
Content-Type: application/json

{
  "new_plan": "pro",
  "duration": "3_months",
  "reason": "Customer service upgrade due to issue",
  "grant_full_points": true,
  "changed_by_admin": "admin_firebase_uid"
}

Response:
{
  "user_id": "firebase_uid_123",
  "old_plan": "premium",
  "new_plan": "pro",
  "points_granted": 500,
  "expires_at": "2026-02-05T09:45:00Z",
  "message": "User plan changed successfully"
}
```

### 6.5 User-Facing APIs (Frontend)

**Get Current Subscription**
```http
GET /api/v1/subscription/current
Authorization: Bearer <firebase_token>

Response:
{
  "plan": "premium",
  "duration": "3_months",
  "started_at": "2025-11-05T09:45:00Z",
  "expires_at": "2026-02-05T09:45:00Z",
  "days_remaining": 92,
  "is_active": true,
  "points_total": 300,
  "points_used": 15,
  "points_remaining": 285,
  "storage_used_mb": 145.5,
  "storage_limit_mb": 2048,
  "usage_percentage": {
    "storage": 7.1,
    "points": 95.0
  }
}
```

**Get Available Plans**
```http
GET /api/v1/subscription/plans

Response:
{
  "plans": [
    {
      "plan": "premium",
      "name": "Premium",
      "features": {
        "storage_mb": 2048,
        "ai_points_3mo": 300,
        "ai_points_12mo": 1200,
        "upload_files_limit": 100,
        "documents_limit": 100,
        "can_create_tests": true
      },
      "pricing": {
        "3_months": 279000,
        "12_months": 990000,
        "discount_12mo": "11%"
      }
    }
  ]
}
```

**Initiate Upgrade/Purchase**
```http
POST /api/v1/subscription/upgrade
Authorization: Bearer <firebase_token>
Content-Type: application/json

{
  "plan": "premium",
  "duration": "3_months"
}

Response:
{
  "checkout_url": "https://sandbox.sepay.vn/checkout/abc123",
  "order_invoice_number": "WA-1730123456-abc",
  "amount": 279000,
  "expires_at": "2025-11-05T10:00:00Z"
}
```

**Cancel Subscription (User-initiated)**
```http
POST /api/v1/subscription/cancel
Authorization: Bearer <firebase_token>
Content-Type: application/json

{
  "reason": "Too expensive",
  "feedback": "Great service but out of my budget"
}

Response:
{
  "subscription_id": "673456789abcdef",
  "status": "cancelled",
  "auto_renew": false,
  "expires_at": "2026-02-05T09:45:00Z",
  "message": "Subscription will remain active until expiration date"
}
```

**Get Points History**
```http
GET /api/v1/subscription/points/history
Authorization: Bearer <firebase_token>
Query Parameters:
  - page: int (default: 1)
  - limit: int (default: 20)

Response:
{
  "points": {
    "total": 300,
    "used": 15,
    "remaining": 285
  },
  "history": [
    {
      "date": "2025-11-05T10:15:00Z",
      "type": "spend",
      "amount": -2,
      "service": "ai_chat",
      "description": "AI Chat Session",
      "balance_after": 298
    },
    {
      "date": "2025-11-05T09:45:00Z",
      "type": "earn",
      "amount": 300,
      "service": "subscription",
      "description": "Premium 3 months subscription",
      "balance_after": 300
    }
  ],
  "total": 2,
  "page": 1,
  "pages": 1
}
```

**Get Payment History**
```http
GET /api/v1/payments/history
Authorization: Bearer <firebase_token>

Response:
{
  "payments": [
    {
      "payment_id": "sepay_txn_123",
      "order_invoice_number": "WA-1730123456-abc",
      "plan": "premium",
      "duration": "3_months",
      "amount": 279000,
      "status": "completed",
      "payment_method": "BANK_TRANSFER",
      "created_at": "2025-11-05T09:30:00Z",
      "paid_at": "2025-11-05T09:45:00Z"
    }
  ]
}
```

**Get Payment Status (After Checkout)**
```http
GET /api/v1/payments/status/{order_invoice_number}
Authorization: Bearer <firebase_token>

Response:
{
  "order_invoice_number": "WA-1730123456-abc",
  "status": "completed",  // or "pending", "failed"
  "amount": 279000,
  "plan": "premium",
  "duration": "3_months",
  "paid_at": "2025-11-05T09:45:00Z",
  "subscription_activated": true
}
```

---

## 7. SePay Integration with Node.js Microservice

### 7.1 Why Node.js Service is Needed

**Problem:** SePay only provides `sepay-pg-node` SDK (Node.js), no Python SDK

**Solutions Considered:**

| Solution | Pros | Cons | Decision |
|----------|------|------|----------|
| Port SePay SDK to Python | No new service needed | Time-consuming, hard to maintain | ❌ Rejected |
| Use subprocess to run Node.js | Simple | Fragile, hard to scale | ❌ Rejected |
| **Separate Node.js microservice** | Clean architecture, scalable, maintainable | More infrastructure | ✅ **SELECTED** |
| Use alternative payment gateway | Python SDK available | May not support Vietnam well | ❌ Rejected |

### 7.2 Inter-Service Communication Flow

```
┌─────────────┐         ┌─────────────┐         ┌─────────────┐
│   Client    │         │   Python    │         │   Node.js   │         ┌─────────────┐
│  (Browser)  │         │   Service   │         │   Payment   │         │    SePay    │
└──────┬──────┘         └──────┬──────┘         └──────┬──────┘         └──────┬──────┘
       │                       │                       │                       │
       │ 1. POST /upgrade      │                       │                       │
       │ {plan: "premium"}     │                       │                       │
       ├──────────────────────►│                       │                       │
       │                       │                       │                       │
       │                       │ 2. POST /checkout     │                       │
       │                       │ (internal call)       │                       │
       │                       ├──────────────────────►│                       │
       │                       │                       │                       │
       │                       │                       │ 3. initCheckoutUrl()  │
       │                       │                       ├──────────────────────►│
       │                       │                       │                       │
       │                       │                       │ 4. checkout_url       │
       │                       │                       │◄──────────────────────┤
       │                       │                       │                       │
       │                       │ 5. {checkout_url}     │                       │
       │                       │◄──────────────────────┤                       │
       │                       │                       │                       │
       │ 6. {checkout_url}     │                       │                       │
       │◄──────────────────────┤                       │                       │
       │                       │                       │                       │
       │ 7. Redirect to SePay  │                       │                       │
       ├───────────────────────┼───────────────────────┼──────────────────────►│
       │                       │                       │                       │
       │ 8. User pays          │                       │                       │
       │                       │                       │                       │
       │                       │                       │ 9. Webhook (payment)  │
       │                       │                       │◄──────────────────────┤
       │                       │                       │                       │
       │                       │ 10. Activate subscription                     │
       │                       │◄──────────────────────┤                       │
       │                       │                       │                       │
       │                       │ 11. {subscription}    │                       │
       │                       ├──────────────────────►│                       │
       │                       │                       │                       │
       │ 12. Redirect success  │                       │                       │
       │◄──────────────────────┼───────────────────────┼───────────────────────┤
       │                       │                       │                       │
```

### 7.3 Node.js Service Key Implementation

**src/controllers/paymentController.js**
```javascript
const sepayClient = require('../config/sepay');
const Payment = require('../models/Payment');
const axios = require('axios');

exports.initCheckout = async (req, res) => {
  try {
    const { user_id, plan, duration, user_email, user_name } = req.body;

    // Validate plan and duration
    const pricing = {
      premium: { '3_months': 279000, '12_months': 990000 },
      pro: { '3_months': 447000, '12_months': 1699000 },
      vip: { '3_months': 747000, '12_months': 2799000 }
    };

    const amount = pricing[plan]?.[duration];
    if (!amount) {
      return res.status(400).json({ error: 'Invalid plan or duration' });
    }

    // Generate order invoice number
    const order_invoice_number = `WA-${Date.now()}-${user_id.substring(0, 5)}`;

    // Create payment record
    const payment = new Payment({
      user_id,
      order_invoice_number,
      amount,
      currency: 'VND',
      plan,
      duration,
      status: 'pending',
      created_at: new Date()
    });
    await payment.save();

    // Initialize SePay checkout
    const checkoutURL = sepayClient.checkout.initCheckoutUrl();
    const checkoutFields = sepayClient.checkout.initOneTimePaymentFields({
      payment_method: 'BANK_TRANSFER',
      order_invoice_number,
      order_amount: amount,
      currency: 'VND',
      order_description: `WordAI ${plan.toUpperCase()} - ${duration.replace('_', ' ')}`,
      success_url: `${process.env.FRONTEND_URL}/payments/success?order=${order_invoice_number}`,
      error_url: `${process.env.FRONTEND_URL}/payments/error`,
      cancel_url: `${process.env.FRONTEND_URL}/payments/cancel`,
    });

    // Build checkout URL with params
    const params = new URLSearchParams(checkoutFields);
    const fullCheckoutURL = `${checkoutURL}?${params.toString()}`;

    res.json({
      checkout_url: fullCheckoutURL,
      order_invoice_number,
      amount,
      expires_at: new Date(Date.now() + 15 * 60 * 1000) // 15 minutes
    });

  } catch (error) {
    console.error('Checkout initiation error:', error);
    res.status(500).json({ error: 'Failed to initiate checkout' });
  }
};

exports.getPaymentStatus = async (req, res) => {
  try {
    const { orderId } = req.params;
    const payment = await Payment.findOne({ order_invoice_number: orderId });

    if (!payment) {
      return res.status(404).json({ error: 'Payment not found' });
    }

    res.json({
      order_invoice_number: payment.order_invoice_number,
      status: payment.status,
      amount: payment.amount,
      plan: payment.plan,
      duration: payment.duration,
      created_at: payment.created_at,
      paid_at: payment.paid_at
    });

  } catch (error) {
    console.error('Get payment status error:', error);
    res.status(500).json({ error: 'Failed to get payment status' });
  }
};
```

**src/controllers/webhookController.js**
```javascript
const Payment = require('../models/Payment');
const axios = require('axios');
const crypto = require('crypto');

// Verify SePay webhook signature
function verifyWebhookSignature(payload, signature, secret) {
  const hash = crypto
    .createHmac('sha256', secret)
    .update(JSON.stringify(payload))
    .digest('hex');
  return hash === signature;
}

exports.handleSepayWebhook = async (req, res) => {
  try {
    const signature = req.headers['x-sepay-signature'];
    const payload = req.body;

    // Verify signature
    if (!verifyWebhookSignature(payload, signature, process.env.SEPAY_SECRET_KEY)) {
      console.error('Invalid webhook signature');
      return res.status(401).json({ error: 'Invalid signature' });
    }

    const {
      order_invoice_number,
      transaction_id,
      status,
      amount,
      paid_at,
      payment_method
    } = payload;

    // Find payment
    const payment = await Payment.findOne({ order_invoice_number });
    if (!payment) {
      console.error(`Payment not found: ${order_invoice_number}`);
      return res.status(404).json({ error: 'Payment not found' });
    }

    // Update payment status
    payment.status = status === 'SUCCESS' ? 'completed' : 'failed';
    payment.sepay_transaction_id = transaction_id;
    payment.sepay_response = payload;
    payment.paid_at = new Date(paid_at);
    payment.payment_method = payment_method;
    await payment.save();

    // If payment successful, notify Python service to activate subscription
    if (status === 'SUCCESS') {
      try {
        const response = await axios.post(
          `${process.env.PYTHON_SERVICE_URL}/internal/subscriptions/activate`,
          {
            user_id: payment.user_id,
            payment_id: transaction_id,
            order_invoice_number,
            plan: payment.plan,
            duration: payment.duration,
            paid_amount: amount,
            paid_at: new Date(paid_at)
          },
          {
            headers: {
              'Authorization': `Bearer ${process.env.INTERNAL_SERVICE_TOKEN}`,
              'Content-Type': 'application/json'
            },
            timeout: 10000 // 10 seconds
          }
        );

        console.log('Subscription activated:', response.data);

        // Update payment with subscription ID
        payment.subscription_id = response.data.subscription_id;
        await payment.save();

      } catch (error) {
        console.error('Failed to activate subscription:', error.message);
        // Don't fail webhook - payment is still successful
        // TODO: Implement retry mechanism or manual activation
      }
    }

    // Acknowledge webhook
    res.json({ received: true });

  } catch (error) {
    console.error('Webhook processing error:', error);
    res.status(500).json({ error: 'Webhook processing failed' });
  }
};
```

### 7.4 Docker Network Configuration

**Ensure both services are on same network:**

```bash
# Create network (if not exists)
docker network create ai-chatbot-network

# Both services should use this network
docker network inspect ai-chatbot-network
```

**Test inter-service communication:**
```bash
# From Python container, test Node.js service
docker exec ai-chatbot-rag curl http://payment-service:3000/health

# From Node.js container, test Python service
docker exec payment-service curl http://ai-chatbot-rag:8000/health
```

---

## 8. Security & Compliance

### 8.1 Payment Security Measures

1. **HTTPS Only:** All payment endpoints must use HTTPS
2. **Webhook Signature Validation:** Verify all SePay webhooks
3. **No Card Data Storage:** Never store credit card numbers (PCI-DSS)
4. **Rate Limiting:** Max 10 checkout requests per user per hour
5. **Idempotency:** Prevent duplicate payments with idempotency keys
6. **Audit Logging:** Log all payment events with timestamps
7. **Data Encryption:** Encrypt sensitive payment data at rest
8. **Access Control:** Only authorized services can activate subscriptions

### 8.2 Vietnam Payment Regulations

- **Invoice Requirement:** E-invoice for all transactions (integrate with VNPT/Viettel E-Invoice)
- **Tax Compliance:** 10% VAT on all services
- **Data Retention:** Keep payment records for 7 years
- **Customer Rights:** Clear refund policy (7-day return for digital goods)

### 8.3 GDPR/Data Privacy

- **User Consent:** Explicit consent before storing payment info
- **Data Deletion:** Support user right to delete payment history
- **Data Export:** Allow users to export their payment data
- **Third-party Sharing:** Clear disclosure of SePay data sharing

---

## 9. Monitoring & Metrics

### 9.1 Key Metrics to Track

**Business Metrics:**
- Monthly Recurring Revenue (MRR)
- Conversion rate (Free → Paid)
- Churn rate
- Average Revenue Per User (ARPU)
- Lifetime Value (LTV)

**Technical Metrics:**
- Payment success rate
- Webhook delivery rate
- Average payment processing time
- Points consumption rate
- Storage usage per plan

### 9.2 Alerting Rules

- Payment success rate < 95% → Alert DevOps
- Webhook failures > 5% → Alert DevOps
- SePay API latency > 5s → Alert DevOps
- Subscription expiring in 3 days → Email user
- Points < 10% remaining → Notify user

---

## 10. Testing Strategy

### 10.1 Unit Tests

**Python Service:**
```bash
pytest tests/services/test_subscription_service.py
pytest tests/services/test_points_service.py
pytest tests/api/test_subscription_routes.py
```

**Node.js Service:**
```bash
npm test -- tests/controllers/paymentController.test.js
npm test -- tests/controllers/webhookController.test.js
```

### 10.2 Integration Tests

**Test Scenarios:**
1. Full payment flow (Python → Node.js → SePay → Webhook → Python)
2. Subscription activation after successful payment
3. Points deduction on AI operations
4. Plan upgrade/downgrade logic
5. Subscription expiration handling
6. Webhook retry mechanism

### 10.3 Load Testing

**Scenarios:**
- 100 concurrent checkout requests
- 1000 webhook deliveries per minute
- 10,000 points checks per second

**Tools:** k6, Apache JMeter, or Locust

---

## 11. Rollout Plan

### 11.1 Beta Testing (Week 8)

- [ ] Select 20 beta users (10 paying, 10 free)
- [ ] Offer 50% discount for beta testers
- [ ] Collect feedback on payment flow
- [ ] Monitor for bugs/issues
- [ ] Iterate based on feedback

### 11.2 Soft Launch (Week 9)

- [ ] Enable for 25% of users
- [ ] Monitor conversion rates
- [ ] Check payment success rates
- [ ] Gather user feedback
- [ ] Fix any critical issues

### 11.3 Full Launch (Week 10)

- [ ] Enable for 100% of users
- [ ] Announce via email/blog
- [ ] Run promotional campaign
- [ ] Monitor metrics closely
- [ ] Support team ready for inquiries

---

## 12. Estimated Costs

### 12.1 Development Costs

| Phase | Duration | Effort | Cost (Estimated) |
|-------|----------|--------|------------------|
| Database & Models | 1 week | 40h | $2,000 |
| Node.js Payment Service | 1 week | 40h | $2,000 |
| Python API Integration | 1 week | 40h | $2,000 |
| Usage Enforcement | 1 week | 40h | $2,000 |
| Frontend Integration | 1 week | 40h | $2,000 |
| Testing & Security | 1 week | 40h | $2,000 |
| Deployment | 1 week | 40h | $2,000 |
| **Total** | **7 weeks** | **280h** | **$14,000** |

### 12.2 Infrastructure Costs (Monthly)

| Service | Cost |
|---------|------|
| DigitalOcean Droplet (2 vCPU, 4GB RAM) | $24/mo |
| MongoDB Storage (100GB) | $10/mo |
| CDN/Bandwidth | $20/mo |
| SSL Certificate | Free (Let's Encrypt) |
| Monitoring (Datadog/New Relic) | $30/mo |
| **Total** | **~$84/mo** |

### 12.3 Payment Gateway Fees

**SePay Transaction Fees:**
- Bank Transfer: 2.5% + 1,000đ per transaction
- Credit Card: 3.5% + 2,000đ per transaction

**Example:** Premium 12mo (990,000đ) → Fee ≈ 26,750đ (2.7%)

---

## 13. Success Criteria

### 13.1 Technical KPIs

- ✅ Payment success rate > 95%
- ✅ Webhook delivery rate > 98%
- ✅ API response time < 500ms (p95)
- ✅ Zero data breaches
- ✅ 99.9% uptime

### 13.2 Business KPIs

- ✅ 10% Free → Paid conversion within 3 months
- ✅ <5% monthly churn rate
- ✅ $5,000 MRR within 6 months
- ✅ 80% customer satisfaction score

---

## 14. Risk Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| SePay API downtime | Medium | High | Implement queue for failed payments, retry mechanism |
| Database corruption | Low | Critical | Daily backups, point-in-time recovery |
| Payment fraud | Medium | High | Fraud detection rules, user verification |
| Node.js service crash | Medium | High | Auto-restart, health checks, load balancer |
| Webhook delivery failure | High | Medium | Retry logic (exponential backoff), manual activation tool |

---

## 15. Post-Launch Optimization

### Month 1-3: Optimization Phase

- [ ] A/B test pricing tiers
- [ ] Optimize conversion funnel
- [ ] Add more payment methods (Momo, ZaloPay)
- [ ] Implement referral program
- [ ] Add annual billing discounts
- [ ] Create enterprise plan for teams

### Month 4-6: Expansion Phase

- [ ] International payments (PayPal, Stripe)
- [ ] Mobile app subscriptions (In-App Purchase)
- [ ] Gift subscriptions
- [ ] Corporate billing
- [ ] API access for developers

---

## 16. Next Steps

1. **Immediate (This Week):**
   - [ ] Review this document with team
   - [ ] Get approval from stakeholders
   - [ ] Register SePay sandbox account
   - [ ] Set up development environment

2. **Week 1:**
   - [ ] Start Phase 1 (Database & Models)
   - [ ] Create project timeline in Jira/Trello
   - [ ] Set up CI/CD pipeline

3. **Ongoing:**
   - [ ] Weekly progress review meetings
   - [ ] Update documentation as features evolve
   - [ ] Communicate with SePay support for integration help

---

## 17. Resources & References

### Documentation
- [SePay Documentation](https://docs.sepay.vn) (if available)
- [MongoDB Transactions](https://docs.mongodb.com/manual/core/transactions/)
- [FastAPI Best Practices](https://fastapi.tiangolo.com/async/)
- [Express.js Guide](https://expressjs.com/en/guide/routing.html)

### Tools
- Payment Testing: SePay Sandbox
- API Testing: Postman, Insomnia
- Load Testing: k6, Apache JMeter
- Monitoring: Datadog, New Relic, Sentry

### Support
- SePay Support: support@sepay.vn
- Internal Team: Slack #payment-integration
- DevOps: devops@yourcompany.com

---

## Appendix A: MongoDB Indexes

```python
# user_subscriptions collection
db.user_subscriptions.create_index([("user_id", 1)], unique=True)
db.user_subscriptions.create_index([("expires_at", 1)])
db.user_subscriptions.create_index([("is_active", 1)])
db.user_subscriptions.create_index([("plan", 1), ("is_active", 1)])

# payments collection
db.payments.create_index([("order_invoice_number", 1)], unique=True)
db.payments.create_index([("user_id", 1), ("created_at", -1)])
db.payments.create_index([("status", 1)])
db.payments.create_index([("sepay_transaction_id", 1)], sparse=True)

# points_transactions collection
db.points_transactions.create_index([("user_id", 1), ("created_at", -1)])
db.points_transactions.create_index([("subscription_id", 1)])
db.points_transactions.create_index([("service", 1), ("created_at", -1)])
```

---

## Appendix B: Environment Variables

**.env (Python Service)**
```bash
# Payment Service
PAYMENT_SERVICE_URL=http://payment-service:3000
INTERNAL_SERVICE_TOKEN=<generate_secure_token>

# SePay (for reference, actual values in Node.js service)
SEPAY_MERCHANT_ID=<your_merchant_id>
SEPAY_SECRET_KEY=<your_secret_key>
```

**.env (Node.js Payment Service)**
```bash
# Server
NODE_ENV=production
PORT=3000

# MongoDB
MONGODB_URI=mongodb://ai_service_user:ai_service_2025_secure_password@mongodb:27017/ai_service_db?authSource=admin

# SePay
SEPAY_ENV=production
SEPAY_MERCHANT_ID=<your_merchant_id>
SEPAY_SECRET_KEY=<your_secret_key>

# Services
PYTHON_SERVICE_URL=http://ai-chatbot-rag:8000
FRONTEND_URL=https://wordai.vn

# Security
INTERNAL_SERVICE_TOKEN=<same_as_python_service>
WEBHOOK_SECRET=<generate_secure_token>
```

---

**Document Version:** 1.0
**Last Updated:** November 5, 2025
**Author:** AI Assistant
**Status:** Draft - Ready for Review

---

**END OF DOCUMENT**
