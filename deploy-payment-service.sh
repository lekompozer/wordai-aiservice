#!/bin/bash

# Deploy Payment Service Script
# Builds and deploys the Node.js payment service with rollback capability

set -e  # Exit on error

echo "======================================"
echo "🚀 Payment Service Deployment"
echo "======================================"

# Configuration
IMAGE_NAME="lekompozer/wordai-payment-service"
CONTAINER_NAME="payment-service"
SERVICE_NAME="payment-service"
SERVICE_DIR="payment-service"
SERVICE_PORT="3000"

# Detect docker-compose command (v1 vs v2)
if command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE="docker-compose"
elif docker compose version &> /dev/null; then
    DOCKER_COMPOSE="docker compose"
else
    echo -e "${RED}❌ Neither 'docker-compose' nor 'docker compose' found!${NC}"
    exit 1
fi

echo -e "${YELLOW}📌 Using: ${DOCKER_COMPOSE}${NC}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if payment-service directory exists
if [ ! -d "$SERVICE_DIR" ]; then
    echo -e "${RED}❌ Error: payment-service directory not found!${NC}"
    exit 1
fi

# Get current commit hash for tagging
COMMIT_HASH=$(git rev-parse --short HEAD)
NEW_TAG="${COMMIT_HASH}"
LATEST_TAG="latest"

echo -e "${YELLOW}📦 Building new image: ${IMAGE_NAME}:${NEW_TAG}${NC}"

# Build new image
cd $SERVICE_DIR
docker build -t ${IMAGE_NAME}:${NEW_TAG} -t ${IMAGE_NAME}:${LATEST_TAG} .

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Docker build failed!${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Image built successfully${NC}"
cd ..

echo ""
echo -e "${YELLOW}⚠️  IMPORTANT: This script will deploy with ROLLBACK capability${NC}"
echo -e "${YELLOW}    - Current image: ${CURRENT_IMAGE}${NC}"
echo -e "${YELLOW}    - New image: ${IMAGE_NAME}:${NEW_TAG}${NC}"
echo ""
read -p "Continue with deployment? (y/n): " -n 1 -r CONFIRM_DEPLOY
echo
if [[ ! $CONFIRM_DEPLOY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}⏭️  Deployment cancelled${NC}"
    exit 0
fi

# Get currently running image for rollback
CURRENT_IMAGE=$(docker inspect --format='{{.Config.Image}}' ${CONTAINER_NAME} 2>/dev/null || echo "none")
echo -e "${YELLOW}📌 Current image: ${CURRENT_IMAGE}${NC}"

# Check if user wants to push to registry (optional for local deployment)
read -p "Push image to Docker Hub? (y/n, default: n): " -n 1 -r PUSH_TO_REGISTRY
echo
if [[ $PUSH_TO_REGISTRY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}📤 Pushing image to registry...${NC}"
    docker push ${IMAGE_NAME}:${NEW_TAG}
    docker push ${IMAGE_NAME}:${LATEST_TAG}

    if [ $? -ne 0 ]; then
        echo -e "${RED}❌ Failed to push image to registry!${NC}"
        echo -e "${YELLOW}💡 Run 'docker login' first if needed${NC}"
        echo -e "${YELLOW}⚠️  Continuing with local image...${NC}"
    else
        echo -e "${GREEN}✅ Image pushed successfully${NC}"
    fi
else
    echo -e "${YELLOW}⏭️  Skipping push to registry (using local image)${NC}"
fi

echo -e "${GREEN}✅ Image pushed successfully${NC}"

# Stop and remove old container
echo -e "${YELLOW}🛑 Stopping old container...${NC}"
${DOCKER_COMPOSE} stop ${SERVICE_NAME}
${DOCKER_COMPOSE} rm -f ${SERVICE_NAME}

# Start new container
echo -e "${YELLOW}🚀 Starting new container...${NC}"
${DOCKER_COMPOSE} up -d ${SERVICE_NAME}

# Wait for container to be healthy
echo -e "${YELLOW}⏳ Waiting for service to be healthy...${NC}"
sleep 5

# Check if container is running
if ! docker ps | grep -q ${CONTAINER_NAME}; then
    echo -e "${RED}❌ Container failed to start!${NC}"

    # Rollback
    if [ "$CURRENT_IMAGE" != "none" ]; then
        echo -e "${YELLOW}🔄 Rolling back to previous image: ${CURRENT_IMAGE}${NC}"
        ${DOCKER_COMPOSE} stop ${SERVICE_NAME}
        ${DOCKER_COMPOSE} rm -f ${SERVICE_NAME}

        # Temporarily update docker-compose.yml to use old image
        sed -i.bak "s|image: ${IMAGE_NAME}:.*|image: ${CURRENT_IMAGE}|g" docker-compose.yml
        ${DOCKER_COMPOSE} up -d ${SERVICE_NAME}
        mv docker-compose.yml.bak docker-compose.yml

        echo -e "${GREEN}✅ Rollback completed${NC}"
    fi
    exit 1
fi

# Test health endpoint
echo -e "${YELLOW}🔍 Testing service health...${NC}"
sleep 3

HEALTH_CHECK=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:${SERVICE_PORT}/health || echo "000")

if [ "$HEALTH_CHECK" == "200" ]; then
    echo -e "${GREEN}✅ Health check passed!${NC}"
else
    echo -e "${RED}❌ Health check failed (HTTP ${HEALTH_CHECK})${NC}"

    # Rollback
    if [ "$CURRENT_IMAGE" != "none" ]; then
        echo -e "${YELLOW}🔄 Rolling back to previous image...${NC}"
        ${DOCKER_COMPOSE} stop ${SERVICE_NAME}
        ${DOCKER_COMPOSE} rm -f ${SERVICE_NAME}

        sed -i.bak "s|image: ${IMAGE_NAME}:.*|image: ${CURRENT_IMAGE}|g" docker-compose.yml
        ${DOCKER_COMPOSE} up -d ${SERVICE_NAME}
        mv docker-compose.yml.bak docker-compose.yml

        echo -e "${GREEN}✅ Rollback completed${NC}"
    fi
    exit 1
fi

# Show logs
echo -e "${YELLOW}📋 Recent logs:${NC}"
docker logs --tail 20 ${CONTAINER_NAME}

# Cleanup old images (keep last 3)
echo -e "${YELLOW}🧹 Cleaning up old images...${NC}"
docker images ${IMAGE_NAME} --format "{{.Tag}}" | grep -v latest | tail -n +4 | xargs -I {} docker rmi ${IMAGE_NAME}:{} 2>/dev/null || true

echo ""
echo "======================================"
echo -e "${GREEN}✅ Payment Service Deployment Complete!${NC}"
echo "======================================"
echo ""
echo "📊 Deployment Summary:"
echo "  - Image: ${IMAGE_NAME}:${NEW_TAG}"
echo "  - Container: ${CONTAINER_NAME}"
echo "  - Status: Running"
echo "  - Health: OK"
echo ""
echo "🔗 Service URL: http://localhost:${SERVICE_PORT}"
echo "📖 Health Check: http://localhost:${SERVICE_PORT}/health"
echo ""
echo "Useful commands:"
echo "  - View logs: docker logs -f ${CONTAINER_NAME}"
echo "  - Restart: ${DOCKER_COMPOSE} restart ${SERVICE_NAME}"
echo "  - Stop: ${DOCKER_COMPOSE} stop ${SERVICE_NAME}"
echo ""
