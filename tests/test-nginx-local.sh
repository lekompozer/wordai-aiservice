#!/bin/bash

# ============================================================================
# Test NGINX Configuration Locally with Docker
# ============================================================================
# This script tests the NGINX configuration with both services before deployment
# Run this BEFORE deploying to production server
# ============================================================================

set -e

echo "=========================================="
echo "NGINX Configuration Test - Local"
echo "=========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Step 1: Check if required files exist
echo -e "${YELLOW}[1/6] Checking required files...${NC}"
REQUIRED_FILES=(
    "nginx/nginx.conf"
    "nginx/conf.d/ai-wordai.conf"
    "docker-compose.yml"
    ".env"
)

for file in "${REQUIRED_FILES[@]}"; do
    if [ ! -f "$file" ]; then
        echo -e "${RED}✗ Missing file: $file${NC}"
        exit 1
    fi
    echo -e "${GREEN}✓ Found: $file${NC}"
done
echo ""

# Step 2: Validate NGINX configuration syntax
echo -e "${YELLOW}[2/6] Validating NGINX configuration syntax...${NC}"
docker run --rm \
    -v "$(pwd)/nginx/nginx.conf:/etc/nginx/nginx.conf:ro" \
    -v "$(pwd)/nginx/conf.d:/etc/nginx/conf.d:ro" \
    nginx:1.26-alpine \
    nginx -t

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ NGINX configuration is valid${NC}"
else
    echo -e "${RED}✗ NGINX configuration has errors${NC}"
    exit 1
fi
echo ""

# Step 3: Check if network exists
echo -e "${YELLOW}[3/6] Checking Docker network...${NC}"
if ! docker network inspect ai-chatbot-network >/dev/null 2>&1; then
    echo -e "${YELLOW}Creating ai-chatbot-network...${NC}"
    docker network create ai-chatbot-network
    echo -e "${GREEN}✓ Network created${NC}"
else
    echo -e "${GREEN}✓ Network already exists${NC}"
fi
echo ""

# Step 4: Build images (no cache to ensure fresh build)
echo -e "${YELLOW}[4/6] Building Docker images...${NC}"
echo "This may take a few minutes..."
docker-compose build --no-cache

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Images built successfully${NC}"
else
    echo -e "${RED}✗ Failed to build images${NC}"
    exit 1
fi
echo ""

# Step 5: Start services
echo -e "${YELLOW}[5/6] Starting services...${NC}"
docker-compose up -d

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Services started${NC}"
else
    echo -e "${RED}✗ Failed to start services${NC}"
    exit 1
fi
echo ""

# Wait for services to be ready
echo "Waiting for services to be healthy (30 seconds)..."
sleep 30

# Step 6: Check service health
echo -e "${YELLOW}[6/6] Checking service health...${NC}"

# Check container status
echo ""
echo "Container Status:"
docker-compose ps

echo ""
echo "Checking endpoints..."

# Test Python service (via NGINX)
echo -n "Testing Python service health endpoint: "
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost/health 2>/dev/null || echo "000")
if [ "$HTTP_CODE" = "200" ]; then
    echo -e "${GREEN}✓ Python service is responding (HTTP $HTTP_CODE)${NC}"
else
    echo -e "${RED}✗ Python service not responding (HTTP $HTTP_CODE)${NC}"
    echo "  Trying to get response body..."
    curl -s http://localhost/health || echo "No response"
fi

# Test Node.js payment service health (direct, not via NGINX payment route)
echo -n "Testing Payment service health endpoint: "
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/health 2>/dev/null || echo "000")
if [ "$HTTP_CODE" = "200" ]; then
    echo -e "${GREEN}✓ Payment service is responding directly (HTTP $HTTP_CODE)${NC}"
else
    echo -e "${RED}✗ Payment service not responding directly (HTTP $HTTP_CODE)${NC}"
    echo "  This is OK if payment service is only accessible via NGINX"
fi

# Test payment route via NGINX (should be blocked or return 404 since no /health under /api/v1/payments/)
echo -n "Testing Payment API route via NGINX: "
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost/api/v1/payments/ 2>/dev/null || echo "000")
if [ "$HTTP_CODE" = "404" ] || [ "$HTTP_CODE" = "200" ]; then
    echo -e "${GREEN}✓ Payment API route is accessible via NGINX (HTTP $HTTP_CODE)${NC}"
else
    echo -e "${YELLOW}⚠ Payment API route returned HTTP $HTTP_CODE${NC}"
fi

echo ""
echo "=========================================="
echo "Checking logs for errors..."
echo "=========================================="

# Show last 20 lines of each service
echo ""
echo "NGINX logs:"
docker logs nginx-gateway --tail 20

echo ""
echo "Payment service logs:"
docker logs payment-service --tail 20

echo ""
echo "Python service logs:"
docker logs ai-chatbot-rag --tail 20

echo ""
echo "=========================================="
echo "Test Complete!"
echo "=========================================="
echo ""
echo "Services are running. You can test manually:"
echo "  - Python service: http://localhost/health"
echo "  - Payment service: http://localhost/api/v1/payments/health"
echo "  - Docs: http://localhost/docs"
echo ""
echo "To view live logs:"
echo "  docker-compose logs -f [service-name]"
echo ""
echo "To stop services:"
echo "  docker-compose down"
echo ""
