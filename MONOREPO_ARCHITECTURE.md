# Monorepo Architecture & Deployment Guide

## 📦 Repository Structure Decision

### ✅ **CHOSEN: Monorepo Approach**

```
wordai-aiservice/                    # Single Git Repository
├── .env                             # SHARED environment variables
├── .gitignore
├── docker-compose.yml               # Orchestrates ALL services
├── README.md
│
├── src/                             # Python FastAPI Service
│   ├── models/
│   │   ├── subscription.py
│   │   └── payment.py
│   ├── services/
│   │   ├── subscription_service.py
│   │   └── points_service.py
│   └── api/
│       └── subscription_routes.py
│
└── payment-service/                 # Node.js Payment Service
    ├── package.json
    ├── Dockerfile
    ├── src/
    │   ├── config/
    │   ├── controllers/
    │   ├── routes/
    │   └── index.js
    └── .env.example
```

---

## 🎯 Why Monorepo?

### **Advantages:**
1. ✅ **Single Source of Truth**: 1 commit = both services version-synced
2. ✅ **Shared Configuration**: MongoDB, Redis, secrets in ONE place
3. ✅ **Simple Deployment**: One `git pull` updates everything
4. ✅ **Easy API Sync**: Changes to Python API → Node.js knows immediately
5. ✅ **Team Efficiency**: Same team, same repo, less context switching

### **Comparison with Multi-Repo:**

| Aspect | Monorepo ✅ | Multi-Repo ❌ |
|--------|------------|--------------|
| Git repos | 1 | 3 (Python, Node.js, Infrastructure) |
| .env files | 1 shared | 3 separate (duplication) |
| Version sync | Automatic | Manual (Python v1.2 + Node v1.5?) |
| Deployment | Simple | Complex (3 repos to pull) |
| API changes | Single commit | Multiple PRs across repos |
| Team overhead | Low | High |

---

## 🐳 Docker Isolation Strategy

### **How Docker Separates Services in Monorepo:**

```yaml
# docker-compose.yml
services:
  # Python Service
  ai-chatbot-rag:
    build:
      context: .                    # Root directory
      dockerfile: Dockerfile         # Root Dockerfile
    # ONLY copies: src/, config/, requirements.txt
    # Ignores: payment-service/

  # Node.js Service
  payment-service:
    build:
      context: ./payment-service    # ONLY this subdirectory
      dockerfile: Dockerfile         # payment-service/Dockerfile
    # ONLY copies: payment-service/src/, package.json
    # Cannot access: ../src/ (Python code)
```

### **Build Process:**

```bash
# On production server
cd /home/hoile/wordai
git pull  # Gets BOTH folders: src/ and payment-service/

# Docker Compose builds SEPARATELY
docker-compose build ai-chatbot-rag
# → Reads: ./Dockerfile
# → Context: . (root)
# → Copies: src/, config/, requirements.txt
# → Result: Container with ONLY Python code

docker-compose build payment-service
# → Reads: ./payment-service/Dockerfile
# → Context: ./payment-service (isolated)
# → Copies: payment-service/src/, package.json, node_modules/
# → Result: Container with ONLY Node.js code
```

### **Runtime Isolation:**

```
┌─────────────────────────────────┐
│ Container: ai-chatbot-rag       │
├─────────────────────────────────┤
│ /app/                           │
│ ├── src/          ← Python code │
│ ├── config/                     │
│ └── requirements.txt            │
│                                 │
│ NO ACCESS to payment-service/  │
└─────────────────────────────────┘

┌─────────────────────────────────┐
│ Container: payment-service      │
├─────────────────────────────────┤
│ /app/                           │
│ ├── src/          ← Node.js code│
│ ├── package.json                │
│ └── node_modules/               │
│                                 │
│ NO ACCESS to ../src/ (Python)  │
└─────────────────────────────────┘
```

---

## 🔧 Environment Variables Strategy

### ✅ **CHOSEN: Single .env File**

```
wordai-aiservice/
└── .env                    # Shared by BOTH services
```

### **Why Single .env?**

**Shared Resources:**
```bash
# These values MUST be identical for both services:
MONGODB_URI=mongodb://user:pass@mongodb:27017
MONGODB_NAME=ai_service_db
REDIS_URL=redis://redis-server:6379
API_SECRET_KEY=shared-secret-for-inter-service-auth
WEBHOOK_SECRET=webhook-signature-secret
```

**Service-Specific Variables:**
```bash
# Python-specific (Node.js ignores these)
DEEPSEEK_API_KEY=sk-xxx
GEMINI_API_KEY=xxx
ANTHROPIC_API_KEY=sk-ant-xxx

# Node.js-specific (Python ignores these)
SEPAY_API_KEY=xxx
SEPAY_MERCHANT_CODE=xxx
SEPAY_SECRET_KEY=xxx
```

### **Docker Compose Usage:**

```yaml
services:
  ai-chatbot-rag:
    env_file: .env                    # Reads all vars from .env
    environment:
      - MONGODB_URI=${MONGODB_URI}    # Uses shared value
      - DEEPSEEK_API_KEY=${DEEPSEEK_API_KEY}  # Python-specific

  payment-service:
    env_file: .env                    # Same .env file
    environment:
      - MONGODB_URI=${MONGODB_URI}    # Uses shared value
      - SEPAY_API_KEY=${SEPAY_API_KEY}  # Node.js-specific
```

### **Comparison with Separate .env:**

| Approach | Single .env ✅ | Separate .env ❌ |
|----------|---------------|------------------|
| Files | 1 | 2 |
| MongoDB URI | Defined once | Duplicate (must sync) |
| Update password | 1 change | 2 changes (easy to forget) |
| Deployment | Copy 1 file | Copy 2 files |
| Risk of desync | Zero | High |

---

## 🚀 Deployment Process

### **Step-by-Step:**

```bash
# 1. Local development - commit code
git add .
git commit -m "Add payment service"
git push origin main

# 2. On production server
ssh root@104.248.147.155
su - hoile
cd /home/hoile/wordai

# 3. Pull latest code (gets BOTH services)
git pull origin main

# 4. Update .env with SePay credentials
vim .env
# Add:
# SEPAY_API_KEY=xxx
# SEPAY_MERCHANT_CODE=xxx
# SEPAY_SECRET_KEY=xxx

# 5. Deploy with Docker Compose
bash deploy-compose-with-rollback.sh

# This script will:
# - Build Python image from root context
# - Build Node.js image from payment-service/ context
# - Start all containers with shared network
# - Perform health checks
# - Rollback if any service fails
```

### **What Happens During Build:**

```bash
# Python service build
docker build -t ai-chatbot-rag:latest .
# Dockerfile at root:
# COPY requirements.txt /app/
# COPY src/ /app/src/
# COPY config/ /app/config/
# → payment-service/ is NOT copied (not in COPY commands)

# Node.js service build
docker build -t payment-service:latest ./payment-service
# Dockerfile in payment-service/:
# COPY package*.json /app/
# COPY src/ /app/src/
# → Only copies from payment-service/ directory
# → Cannot access ../src/ (outside context)
```

### **Container Communication:**

```
┌──────────────────────────────────────────────────┐
│ Docker Network: ai-chatbot-network               │
├──────────────────────────────────────────────────┤
│                                                  │
│  ┌─────────────┐      ┌─────────────┐          │
│  │   NGINX     │      │   MongoDB   │          │
│  │  Port 443   │      │  Port 27017 │          │
│  └──────┬──────┘      └─────────────┘          │
│         │                                        │
│    ┌────┴──────────────┐                        │
│    │                   │                        │
│    ▼                   ▼                        │
│  ┌─────────────┐   ┌─────────────┐             │
│  │  Python     │   │  Node.js    │             │
│  │  Port 8000  │◄──┤  Port 3000  │             │
│  └─────────────┘   └─────────────┘             │
│         │                   │                   │
│         └───────┬───────────┘                   │
│                 ▼                               │
│          ┌─────────────┐                        │
│          │   Redis     │                        │
│          │  Port 6379  │                        │
│          └─────────────┘                        │
│                                                  │
└──────────────────────────────────────────────────┘
```

**Routing:**
- NGINX receives: `https://ai.wordai.pro/api/v1/payments/checkout`
- NGINX routes to: `http://payment-service:3000/api/v1/payments/checkout`
- Node.js processes payment
- Node.js calls: `http://ai-chatbot-rag:8000/api/v1/subscriptions/activate`
- Python activates subscription

---

## 📊 File Size Impact

### **Repository Size:**
```
.git/                  ~2MB
src/                   ~1MB (Python code)
payment-service/       ~0.5MB (Node.js code, no node_modules in git)
data/                  ~5MB (embeddings, cache)
logs/                  ~1MB (rotating logs)
Total:                 ~10MB
```

### **Docker Images:**
```
ai-chatbot-rag:         ~2.5GB (Python + ML libraries)
payment-service:        ~150MB (Node.js Alpine + dependencies)
mongodb:                ~700MB
redis:                  ~50MB
nginx:                  ~40MB
Total:                  ~3.4GB
```

### **Production Disk Usage:**
```
/home/hoile/wordai/     ~10MB (git repo)
Docker volumes:         ~5GB (MongoDB data, Redis cache)
Docker images:          ~3.4GB
Total:                  ~8.5GB (out of 155GB available = 5.5%)
```

---

## ✅ Benefits Summary

### **Development:**
- ✅ Single `git clone` gets everything
- ✅ Changes synced automatically
- ✅ Easy to refactor APIs (change both services in one commit)

### **Deployment:**
- ✅ One `git pull` updates both services
- ✅ One .env file to maintain
- ✅ One deployment script

### **Operations:**
- ✅ Single version tag (e.g., v1.2.0 = Python v1.2.0 + Node.js v1.2.0)
- ✅ Easier rollback (one git revert)
- ✅ Clearer audit trail (one commit history)

---

## 🔒 Security Considerations

### **Secrets Management:**
```bash
# .env file contains ALL secrets
# On production:
chmod 600 .env                    # Only owner can read/write
chown hoile:hoile .env            # Owned by app user

# Not in git
echo ".env" >> .gitignore         # Never commit secrets
```

### **Container Isolation:**
```yaml
# Docker Compose enforces isolation
# payment-service CANNOT access Python code filesystem
# Python service CANNOT access Node.js code filesystem
# They ONLY communicate via:
# 1. Docker network (HTTP requests)
# 2. Shared MongoDB
# 3. Shared Redis (optional)
```

---

## 📝 Best Practices

1. **Version Control:**
   ```bash
   # Tag releases
   git tag -a v1.0.0 -m "Release: Payment integration"
   git push origin v1.0.0
   ```

2. **Environment File:**
   ```bash
   # Always update .env.example when adding new vars
   # Never commit actual .env to git
   # Keep production .env backed up separately
   ```

3. **Docker Builds:**
   ```bash
   # Use build cache for faster builds
   docker-compose build --parallel

   # Force rebuild if dependencies changed
   docker-compose build --no-cache
   ```

4. **Service Updates:**
   ```bash
   # Update only one service
   docker-compose up -d --no-deps --build payment-service

   # Update all services
   docker-compose up -d --build
   ```

---

## 🎯 Conclusion

**Monorepo with single .env is the RIGHT choice for WordAI because:**
- Small team managing both services
- Services are tightly coupled (Node.js → Python webhooks)
- Shared infrastructure (MongoDB, Redis)
- Simplified operations
- Lower maintenance overhead

**Docker provides sufficient isolation** despite being in one repository:
- Each service builds from its own context
- Containers have separate filesystems
- No cross-service file access
- Clean separation at runtime

**Result:** Simple to develop, easy to deploy, secure to operate! 🚀
