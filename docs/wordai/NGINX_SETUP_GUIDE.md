# WordAI Nginx Setup Guide

## 📋 Manual Setup Steps for ai.wordai.pro

### 1. Initial HTTP Setup (No SSL)

```bash
# 1. Copy HTTP-only config
sudo cp /path/to/wordai-aiservice/src/nginx-http-only.conf /etc/nginx/sites-available/ai.wordai.pro

# 2. Enable the site
sudo ln -sf /etc/nginx/sites-available/ai.wordai.pro /etc/nginx/sites-enabled/

# 3. Remove old configurations (if any)
sudo rm -f /etc/nginx/sites-enabled/ai.aimoney.io.vn

# 4. Test nginx config
sudo nginx -t

# 5. Reload nginx
sudo systemctl reload nginx
```

### 2. Test HTTP Access

```bash
# Test basic connectivity
curl -I http://ai.wordai.pro

# Test API endpoint
curl http://ai.wordai.pro/api/health
```

### 3. SSL Certificate Setup (After HTTP works)

```bash
# Install certbot if not already installed
sudo apt update
sudo apt install certbot python3-certbot-nginx

# Obtain SSL certificate
sudo certbot --nginx -d ai.wordai.pro

# Test SSL renewal
sudo certbot renew --dry-run
```

### 4. Verify HTTPS Setup

```bash
# Test HTTPS
curl -I https://ai.wordai.pro

# Check SSL certificate
openssl s_client -connect ai.wordai.pro:443 -servername ai.wordai.pro
```

## 📁 File Locations

- **HTTP Config**: `src/nginx-http-only.conf` (start with this)
- **Full HTTPS Config**: `src/nginx.conf` (after SSL setup)
- **Backup**: `src/nginx.conf.backup.aimoney.io.vn`

## 🔧 Domain Configuration

- **Domain**: ai.wordai.pro
- **Backend Port**: 8000 (FastAPI)
- **Logs**:
  - Access: `/var/log/nginx/ai.wordai.pro.access.log`
  - Error: `/var/log/nginx/ai.wordai.pro.error.log`

## 🌐 CORS Allowed Origins

- `http://localhost:8001` (development)
- `http://localhost:3002` (development)
- `http://localhost:3000` (development)
- `https://ai.wordai.pro` (main app)
- `https://wordai.pro` (marketing site)
- `https://www.wordai.pro` (www version)
- `https://api.wordai.pro` (API domain)
- `https://static.wordai.pro` (static assets)

## ⚠️ Important Notes

1. **Start with HTTP first** - Use `nginx-http-only.conf`
2. **DNS must point to server** before SSL setup
3. **Firewall**: Ensure ports 80 and 443 are open
4. **FastAPI**: Make sure your app is running on port 8000
5. **Test each step** before proceeding to the next

## 🔄 Migration from old domain

The old `ai.aimoney.io.vn` configuration has been backed up as:
- `nginx.conf.backup.aimoney.io.vn`

## 🚀 Quick Start

1. Use `nginx-http-only.conf` initially
2. Test HTTP access
3. Setup SSL with certbot
4. Switch to full `nginx.conf` if needed

This approach ensures you can get the site running on HTTP first, then add SSL layer by layer.