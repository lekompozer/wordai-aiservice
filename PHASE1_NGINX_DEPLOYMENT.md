# Phase 1 Deployment Checklist - NGINX với 2 Docker Services

## Mục tiêu
Deploy và test NGINX API Gateway với 2 services (Python AI và Node.js Payment) để đảm bảo routing hoạt động đúng trước khi tiếp tục fix SePay integration.

---

## ✅ Công việc đã hoàn thành

### 1. NGINX Configuration
- ✅ Tạo `nginx/nginx.conf` với performance settings
- ✅ Tạo `nginx/conf.d/ai-wordai.conf` với:
  - Upstream definitions: `python_backend`, `nodejs_payment`
  - Rate limiting zones: payment_limit, api_limit, general_limit
  - SSL/TLS configuration (Let's Encrypt certificates)
  - Security headers (HSTS, X-Frame-Options, CSP)
  - CORS configuration (static + dynamic)
  - All existing Python routes from production
  - New payment service routes:
    - `/api/v1/payments/` → payment-service:3000
    - `/sepay/` → payment-service:3000 (NO rate limit)

### 2. Docker Compose Configuration
- ✅ Service `ai-chatbot-rag` (Python) - port 8000
- ✅ Service `payment-service` (Node.js) - port 3000
- ✅ Service `nginx` (API Gateway) - ports 80, 443
- ✅ Service `mongodb` - port 27017
- ✅ Service `redis-server` - port 6379
- ✅ All services on `ai-chatbot-network`
- ✅ SSL certificates mounted from host `/etc/letsencrypt`

### 3. Payment Service Structure
- ✅ Health endpoint: `/health`
- ✅ Payment routes: `/api/v1/payments/*`
- ✅ Webhook routes: `/api/v1/webhooks/*`
- ✅ MongoDB connection configured
- ✅ Logger, error handler, validation middleware

### 4. Test Script
- ✅ Created `test-nginx-local.sh` to:
  - Validate NGINX config syntax
  - Build Docker images
  - Start all services
  - Check health endpoints
  - Show logs

---

## 🔄 Công việc đang thực hiện (Task 1.2)

### Test NGINX Configuration Locally

**Command to run:**
```bash
./test-nginx-local.sh
```

**What the script does:**
1. ✅ Check required files (nginx.conf, docker-compose.yml, .env)
2. ✅ Validate NGINX syntax with Docker
3. ✅ Create Docker network if not exists
4. ✅ Build all Docker images
5. ✅ Start services (Python, Node.js, NGINX, MongoDB, Redis)
6. ✅ Wait 30s for services to be healthy
7. ✅ Test endpoints:
   - `http://localhost/health` → Python service
   - `http://localhost:3000/health` → Payment service (direct)
   - `http://localhost/api/v1/payments/` → Payment via NGINX
8. ✅ Show logs from all services

**Expected Results:**
- ✅ NGINX config syntax valid
- ✅ All containers running
- ✅ Python service responds to `/health`
- ✅ Payment service responds to `/health`
- ✅ NGINX routes requests correctly
- ✅ No errors in logs

**If test succeeds:**
→ Proceed to Task 1.3 (Deploy to Production)

**If test fails:**
→ Check logs, fix issues, re-run test

---

## ⏳ Công việc chờ thực hiện

### Task 1.3: Deploy to Production Server

**Pre-requisites:**
- ✅ Local test passed (`test-nginx-local.sh`)
- ⏳ All changes committed to git
- ⏳ Push to GitHub repository

**Deployment Steps:**

1. **Commit and Push**
```bash
git add .
git commit -m "feat: Add NGINX configuration with payment service routing"
git push origin main
```

2. **SSH to Production Server**
```bash
ssh root@104.248.147.155
su - hoile
cd /home/hoile/wordai
```

3. **Pull Latest Code**
```bash
git pull origin main
```

4. **Stop Current NGINX** (to avoid port conflicts)
```bash
# Check if NGINX is running on host
systemctl status nginx

# If running, stop it temporarily
systemctl stop nginx

# Verify SSL certificates exist
ls -la /etc/letsencrypt/live/ai.wordai.pro/
```

5. **Build and Deploy with Docker Compose**
```bash
# Build images
docker-compose build --no-cache

# Start services
docker-compose up -d

# Check status
docker-compose ps
```

6. **Verify Deployment**
```bash
# Check containers are running
docker ps | grep -E 'nginx-gateway|payment-service|ai-chatbot-rag'

# Test endpoints
curl -I https://ai.wordai.pro/health
curl -I https://ai.wordai.pro/api/v1/payments/

# Check logs
docker logs nginx-gateway --tail 50
docker logs payment-service --tail 50
docker logs ai-chatbot-rag --tail 50
```

7. **Monitor for Issues**
```bash
# Watch logs in real-time
docker-compose logs -f
```

**Rollback Plan (if deployment fails):**
```bash
# Stop Docker Compose services
docker-compose down

# Restart host NGINX
systemctl start nginx
systemctl status nginx

# Verify old service is working
curl -I https://ai.wordai.pro/health
```

---

## 📊 Validation Checklist (After Deployment)

### NGINX Routing Tests

- [ ] **HTTP → HTTPS redirect works**
  ```bash
  curl -I http://ai.wordai.pro
  # Should return: 301 Moved Permanently
  # Location: https://ai.wordai.pro
  ```

- [ ] **Python service routes work**
  ```bash
  curl https://ai.wordai.pro/health
  curl https://ai.wordai.pro/docs
  curl https://ai.wordai.pro/api/auth/me
  ```

- [ ] **Payment service routes work**
  ```bash
  curl https://ai.wordai.pro/api/v1/payments/
  # Should return 404 or payment API response (not 502 Bad Gateway)
  ```

- [ ] **SePay webhook route accessible**
  ```bash
  curl -X POST https://ai.wordai.pro/sepay/ipn
  # Should return 400/401 (expecting valid data), NOT 404 or 502
  ```

- [ ] **SSL certificates valid**
  ```bash
  curl -I https://ai.wordai.pro
  # Check for valid SSL certificate, no warnings
  
  # OR use SSL Labs
  # https://www.ssllabs.com/ssltest/analyze.html?d=ai.wordai.pro
  ```

- [ ] **Rate limiting works**
  ```bash
  # Send 15 requests to payment endpoint (limit: 10/min)
  for i in {1..15}; do
    curl -I https://ai.wordai.pro/api/v1/payments/
    sleep 1
  done
  # Should see: 429 Too Many Requests after 10th request
  ```

- [ ] **CORS headers present**
  ```bash
  curl -H "Origin: https://ai.wordai.pro" -I https://ai.wordai.pro/api/auth/me
  # Should include: Access-Control-Allow-Origin header
  ```

### Container Health Checks

- [ ] **All containers running**
  ```bash
  docker ps --filter "name=nginx-gateway|payment-service|ai-chatbot-rag|mongodb|redis"
  # All should show status: Up
  ```

- [ ] **No restart loops**
  ```bash
  docker ps
  # Check "STATUS" column - should not show frequent restarts
  ```

- [ ] **Resource usage acceptable**
  ```bash
  docker stats --no-stream
  # Python: <6GB RAM, <200% CPU
  # Payment: <512MB RAM, <50% CPU
  # NGINX: <100MB RAM, <20% CPU
  ```

### Log Monitoring

- [ ] **No critical errors in NGINX logs**
  ```bash
  docker logs nginx-gateway --tail 100 | grep -i error
  # Should not show connection errors to upstreams
  ```

- [ ] **Payment service started successfully**
  ```bash
  docker logs payment-service --tail 50
  # Should show: "🚀 wordai-payment-service running on port 3000"
  # Should show: "Connected to MongoDB"
  ```

- [ ] **Python service healthy**
  ```bash
  docker logs ai-chatbot-rag --tail 50
  # Should not show connection errors
  # Should show FastAPI startup message
  ```

---

## 🐛 Troubleshooting Guide

### Issue: NGINX shows "502 Bad Gateway"

**Cause:** Upstream service (Python or Node.js) not responding

**Debug:**
```bash
# Check if upstream containers are running
docker ps

# Check upstream service logs
docker logs payment-service --tail 100
docker logs ai-chatbot-rag --tail 100

# Test direct connection to upstream (from inside NGINX container)
docker exec nginx-gateway wget -O- http://payment-service:3000/health
docker exec nginx-gateway wget -O- http://ai-chatbot-rag:8000/health
```

**Fix:**
- Restart failed service: `docker-compose restart payment-service`
- Check service configuration in docker-compose.yml
- Verify environment variables in .env

---

### Issue: NGINX shows "404 Not Found" for payment routes

**Cause:** Route not mounted or incorrect path in payment service

**Debug:**
```bash
# Check NGINX config
docker exec nginx-gateway cat /etc/nginx/conf.d/ai-wordai.conf | grep -A 10 "location /api/v1/payments"

# Check payment service routes
docker logs payment-service | grep "route"
```

**Fix:**
- Verify payment service mounts routes correctly in `src/index.js`
- Check if payment service is listening on correct port (3000)

---

### Issue: SSL certificate errors

**Cause:** Certificates not mounted or expired

**Debug:**
```bash
# Check if certificates exist on host
ls -la /etc/letsencrypt/live/ai.wordai.pro/

# Check certificate expiry
openssl x509 -in /etc/letsencrypt/live/ai.wordai.pro/cert.pem -noout -dates

# Check if certificates mounted in container
docker exec nginx-gateway ls -la /etc/letsencrypt/live/ai.wordai.pro/
```

**Fix:**
- Renew certificates: `certbot renew`
- Restart NGINX: `docker-compose restart nginx`

---

### Issue: Rate limiting not working

**Cause:** Client IP not detected correctly (proxy configuration)

**Debug:**
```bash
# Check NGINX logs for client IPs
docker logs nginx-gateway --tail 100

# Verify trust proxy setting
docker exec nginx-gateway cat /etc/nginx/conf.d/ai-wordai.conf | grep "real_ip"
```

**Fix:**
- Add `real_ip_header X-Forwarded-For;` to NGINX config
- Restart NGINX

---

## 📈 Success Criteria

**Phase 1 is complete when:**

1. ✅ All 5 Docker containers running (Python, Node.js, NGINX, MongoDB, Redis)
2. ✅ NGINX routes requests to correct upstreams
3. ✅ SSL/HTTPS working with valid certificates
4. ✅ Rate limiting enforced on payment endpoints
5. ✅ CORS headers present on all API responses
6. ✅ Health endpoints accessible for both services
7. ✅ No errors in logs for 5 minutes after deployment
8. ✅ Old Python service routes still work (backward compatibility)
9. ✅ Payment service routes return expected responses (404/401, not 502)
10. ✅ SePay webhook endpoint accessible (even if returns error due to missing signature)

**After Phase 1 success:**
→ Proceed to **Task 2.1** (Fix Payment Controller for SePay integration)

---

## 📝 Notes

- NGINX config copied from production `src/nginx.conf` (435 lines)
- All existing routes preserved for backward compatibility
- Payment routes added with higher priority (matched first)
- SePay webhook route has NO rate limiting for reliability
- Docker Compose uses external network `ai-chatbot-network`
- SSL certificates from host (Let's Encrypt)
- Single .env file shared by all services

---

## 🔗 Related Files

- `nginx/nginx.conf` - Main NGINX config
- `nginx/conf.d/ai-wordai.conf` - Site-specific routing (520 lines)
- `docker-compose.yml` - All 5 services (217 lines)
- `test-nginx-local.sh` - Local testing script
- `payment-service/src/index.js` - Payment service entry point
- `.env` - Environment variables (shared)
- `SEPAY_INTEGRATION_CHECKLIST.md` - Overall integration plan

---

**Last Updated:** 2025-11-05  
**Status:** ✅ Ready for local testing → ⏳ Waiting for production deployment
