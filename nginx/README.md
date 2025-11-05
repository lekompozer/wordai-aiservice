# NGINX API Gateway Configuration

## 📋 Overview

NGINX acts as an API gateway and reverse proxy, routing requests to appropriate services:
- **Payment endpoints** (`/api/v1/payments`, `/sepay`) → Node.js Payment Service (port 3000)
- **All other requests** (`/api`, `/`) → Python FastAPI Service (port 8000)

## 🏗️ Architecture

```
Internet (HTTPS)
    ↓
NGINX (443) - SSL Termination
    ├── /api/v1/payments/* → nodejs_payment:3000
    ├── /sepay/*           → nodejs_payment:3000 (IPN)
    └── /*                 → python_backend:8000
```

## 📁 Files

- `nginx.conf` - Main NGINX configuration
- `conf.d/ai-wordai.conf` - Site-specific configuration for ai.wordai.pro
- `logs/` - Access and error logs (gitignored)

## 🔧 Configuration Details

### **Upstream Servers:**

```nginx
upstream python_backend {
    server ai-chatbot-rag:8000;
}

upstream nodejs_payment {
    server payment-service:3000;
}
```

### **Rate Limiting:**

| Zone | Limit | Burst | Applied To |
|------|-------|-------|------------|
| `payment_limit` | 10/min | 5 | `/api/v1/payments` |
| `api_limit` | 60/min | 20 | `/api` |
| `general_limit` | 100/min | 50 | `/` |
| None | Unlimited | - | `/sepay` (IPN must be reliable) |

### **SSL/TLS:**

- **Certificates:** `/etc/letsencrypt/live/ai.wordai.pro/`
- **Protocols:** TLSv1.2, TLSv1.3
- **HSTS:** Enabled (1 year)
- **OCSP Stapling:** Enabled

### **Security Headers:**

```
Strict-Transport-Security: max-age=31536000; includeSubDomains
X-Frame-Options: SAMEORIGIN
X-Content-Type-Options: nosniff
X-XSS-Protection: 1; mode=block
Referrer-Policy: no-referrer-when-downgrade
```

### **CORS:**

- **Allowed Origin:** `https://ai.wordai.pro`
- **Methods:** GET, POST, PUT, DELETE, OPTIONS
- **Preflight:** Handled automatically

## 🚀 Deployment

### **Docker Compose:**

NGINX is deployed as a container in `docker-compose.yml`:

```yaml
nginx:
  container_name: nginx-gateway
  image: nginx:1.26-alpine
  ports:
    - "80:80"
    - "443:443"
  volumes:
    - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
    - ./nginx/conf.d:/etc/nginx/conf.d:ro
    - /etc/letsencrypt:/etc/letsencrypt:ro  # SSL certs from host
    - ./nginx/logs:/var/log/nginx
  networks:
    - ai-chatbot-network
```

### **SSL Certificates:**

Certificates are mounted from the host server:
```bash
# On production server, certificates exist at:
/etc/letsencrypt/live/ai.wordai.pro/
├── fullchain.pem  → SSL certificate chain
├── privkey.pem    → Private key
└── chain.pem      → Certificate authority chain
```

Let's Encrypt auto-renewal happens on the host, NGINX reads them from the mount.

## 🧪 Testing

### **1. Test NGINX Configuration:**

```bash
# Inside container
docker exec nginx-gateway nginx -t

# Expected output:
# nginx: the configuration file /etc/nginx/nginx.conf syntax is ok
# nginx: configuration file /etc/nginx/nginx.conf test is successful
```

### **2. Test Routing:**

```bash
# Python service (health check)
curl https://ai.wordai.pro/health

# Node.js service (payment API)
curl https://ai.wordai.pro/api/v1/payments/health

# Test IPN endpoint (should reach Node.js)
curl -X POST https://ai.wordai.pro/sepay/ipn \
  -H "Content-Type: application/json" \
  -d '{}'
```

### **3. Test SSL:**

```bash
# Check SSL certificate
openssl s_client -connect ai.wordai.pro:443 -servername ai.wordai.pro

# Check SSL grade
curl -I https://ai.wordai.pro
```

### **4. Test Rate Limiting:**

```bash
# Should trigger rate limit after 10 requests
for i in {1..15}; do
  curl https://ai.wordai.pro/api/v1/payments/checkout
  echo "Request $i"
done

# Expected: 429 Too Many Requests after 10th request
```

## 📊 Monitoring

### **Access Logs:**

```bash
# Real-time access logs
docker logs -f nginx-gateway

# Or view log files
tail -f nginx/logs/ai-wordai-access.log
```

### **Error Logs:**

```bash
tail -f nginx/logs/ai-wordai-error.log
```

### **Key Metrics to Monitor:**

- **Request rate:** Requests per second
- **Response codes:** 200, 404, 500, 429
- **Upstream response time:** `urt` in logs
- **SSL handshake time:** Check for slow connections

## 🔥 Troubleshooting

### **Problem: 502 Bad Gateway**

**Cause:** Upstream service not running

**Solution:**
```bash
# Check if services are running
docker ps | grep -E "ai-chatbot-rag|payment-service"

# Check service logs
docker logs ai-chatbot-rag
docker logs payment-service

# Restart services
docker-compose restart ai-chatbot-rag payment-service
```

### **Problem: 404 Not Found for /api/v1/payments**

**Cause:** Payment service not responding or route misconfigured

**Solution:**
```bash
# Test payment service directly
curl http://localhost:3000/health

# Check NGINX routing
docker exec nginx-gateway cat /etc/nginx/conf.d/ai-wordai.conf | grep payment
```

### **Problem: SSL Certificate Error**

**Cause:** Certificate expired or not found

**Solution:**
```bash
# Check certificate expiry on host
sudo certbot certificates

# Renew if needed
sudo certbot renew

# Reload NGINX
docker exec nginx-gateway nginx -s reload
```

### **Problem: 429 Too Many Requests**

**Cause:** Rate limit exceeded

**Solution:**
- Increase rate limits in `nginx/conf.d/ai-wordai.conf`
- Or wait for the time window to reset (15 minutes)
- Or whitelist specific IPs if needed

## 🔄 Reloading Configuration

After changing NGINX config:

```bash
# Method 1: Reload NGINX (no downtime)
docker exec nginx-gateway nginx -s reload

# Method 2: Restart container (brief downtime)
docker-compose restart nginx

# Method 3: Rebuild and restart (if Dockerfile changed)
docker-compose up -d --no-deps --build nginx
```

## 🛡️ Security Best Practices

✅ **Implemented:**
- SSL/TLS with modern protocols only
- HSTS enabled
- Rate limiting on all endpoints
- Security headers (XSS, frame options, etc.)
- CORS restricted to specific origin
- Request size limits (100MB max)

🔄 **Future Enhancements:**
- [ ] ModSecurity WAF
- [ ] IP whitelist for admin endpoints
- [ ] DDoS protection (Cloudflare or fail2ban)
- [ ] Certificate pinning
- [ ] Request/response logging for audit

## 📚 References

- [NGINX Official Docs](https://nginx.org/en/docs/)
- [SSL Labs Test](https://www.ssllabs.com/ssltest/)
- [Let's Encrypt](https://letsencrypt.org/)
- [NGINX Rate Limiting Guide](https://www.nginx.com/blog/rate-limiting-nginx/)
