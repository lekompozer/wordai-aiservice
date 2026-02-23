#!/bin/bash

# ===================================================================================
# DEPLOY AI-CHATBOT-RAG ONLY (Python app container)
# ===================================================================================
# Chỉ rebuild + recreate mỗi container ai-chatbot-rag, các container khác
# (workers, payment-service, nginx, mongodb, redis...) KHÔNG bị ảnh hưởng.
#
# Dùng khi: chỉ thay đổi Python code (src/), không thay đổi infra/workers.
# Nhanh hơn full deploy vì không cần restart toàn bộ stack.
# ===================================================================================

set -e

# --- DETECT DOCKER COMPOSE COMMAND ---
if command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE_CMD="docker-compose"
elif docker compose version &> /dev/null; then
    DOCKER_COMPOSE_CMD="docker compose"
else
    echo "❌ ERROR: Neither 'docker-compose' nor 'docker compose' command found!"
    exit 1
fi

echo "✅ Using Docker Compose command: $DOCKER_COMPOSE_CMD"

# --- CONFIGURATION ---
APP_NAME="wordai-aiservice"
DOCKER_COMPOSE_FILE="docker-compose.yml"
SERVICE_NAME="ai-chatbot-rag"
HEALTH_CHECK_DELAY=30   # Ngắn hơn full deploy vì chỉ restart 1 container
MAX_HEALTH_RETRIES=5
HEALTH_CHECK_INTERVAL=20
DOCKER_HUB_USERNAME="${DOCKER_HUB_USERNAME:-lekompozer}"
NETWORK_NAME="ai-chatbot-network"

echo "🚀 Starting ai-chatbot-rag only deployment with rollback protection..."
echo "═══════════════════════════════════════════════════════════════"

# --- 1. VERIFY PREREQUISITES ---
echo "🔍 Verifying prerequisites..."

if [ ! -f .env ]; then
    echo "❌ ERROR: .env file not found!"
    exit 1
fi

if ! docker network ls | grep -q "$NETWORK_NAME"; then
    echo "⚠️  Network '$NETWORK_NAME' does not exist. Creating it..."
    docker network create --driver bridge "$NETWORK_NAME"
    echo "✅ Network created: $NETWORK_NAME"
else
    echo "✅ Network '$NETWORK_NAME' exists"
fi

source .env
echo "✅ Environment variables loaded from .env"

# --- 2. GIT VERSION CONTROL ---
echo ""
echo "📦 Preparing version information..."
git checkout main
git pull origin main

NEW_VERSION_TAG=$(git rev-parse --short HEAD)
echo "✅ New version tag: $NEW_VERSION_TAG"

# --- 3. IDENTIFY CURRENT VERSION FOR ROLLBACK ---
echo ""
echo "🔍 Identifying current running version for rollback..."

CURRENT_CONTAINER_ID=$(docker ps -q --filter "name=${SERVICE_NAME}")
PREVIOUS_VERSION_TAG=""

if [ -n "$CURRENT_CONTAINER_ID" ]; then
    PREVIOUS_VERSION_TAG=$(docker inspect --format='{{.Config.Image}}' $CURRENT_CONTAINER_ID 2>/dev/null | cut -d':' -f2)
    if [ -n "$PREVIOUS_VERSION_TAG" ]; then
        echo "✅ Found currently running version: $PREVIOUS_VERSION_TAG"
        echo "   This will be used for rollback if deployment fails."
    else
        echo "⚠️  Could not determine current version tag."
    fi
else
    echo "⚠️  No currently running container found."
fi

# --- 4. BUILD NEW DOCKER IMAGE (Python app only) ---
echo ""
echo "🛠️  Building new Docker image..."
echo "   Tag: $DOCKER_HUB_USERNAME/$APP_NAME:$NEW_VERSION_TAG"

export IMAGE_TAG=$NEW_VERSION_TAG
export DOCKER_HUB_USERNAME=$DOCKER_HUB_USERNAME

DOCKER_BUILDKIT=1 docker build -t "$DOCKER_HUB_USERNAME/$APP_NAME:$NEW_VERSION_TAG" .
docker tag "$DOCKER_HUB_USERNAME/$APP_NAME:$NEW_VERSION_TAG" "$DOCKER_HUB_USERNAME/$APP_NAME:latest"

echo "✅ Image built and tagged successfully"

# --- 5. RECREATE ai-chatbot-rag ONLY ---
echo ""
echo "🚀 Recreating $SERVICE_NAME only..."
echo "   Version: $NEW_VERSION_TAG"
echo "   (All other containers remain untouched)"

# Remove standalone container if exists (from manual deploy)
if docker ps -a --format '{{.Names}}' | grep -q "^${SERVICE_NAME}$"; then
    # Check if it's managed by compose or standalone
    if ! $DOCKER_COMPOSE_CMD -f $DOCKER_COMPOSE_FILE ps $SERVICE_NAME 2>/dev/null | grep -q $SERVICE_NAME; then
        echo "   Found standalone $SERVICE_NAME container, removing it..."
        docker stop $SERVICE_NAME 2>/dev/null || true
        docker rm $SERVICE_NAME 2>/dev/null || true
    fi
fi

# Only recreate ai-chatbot-rag, leave everything else running
$DOCKER_COMPOSE_CMD -f $DOCKER_COMPOSE_FILE up -d \
    --no-deps \
    --force-recreate \
    $SERVICE_NAME

echo "✅ $SERVICE_NAME restarted"

# --- 6. HEALTH CHECK WITH RETRY ---
echo ""
echo "🩺 Performing health checks..."
echo "   Initial delay: ${HEALTH_CHECK_DELAY}s"
echo "   Max retries: $MAX_HEALTH_RETRIES"
echo "   Interval: ${HEALTH_CHECK_INTERVAL}s"

sleep $HEALTH_CHECK_DELAY

HEALTH_CHECK_PASSED=false
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $MAX_HEALTH_RETRIES ]; do
    echo ""
    echo "🔍 Health check attempt $((RETRY_COUNT + 1))/$MAX_HEALTH_RETRIES..."

    NEW_CONTAINER_ID=$(docker ps -q --filter "name=${SERVICE_NAME}" 2>/dev/null)

    if [ -z "$NEW_CONTAINER_ID" ]; then
        echo "❌ Container is not running"
        RETRY_COUNT=$((RETRY_COUNT + 1))
        if [ $RETRY_COUNT -lt $MAX_HEALTH_RETRIES ]; then
            echo "⏳ Waiting ${HEALTH_CHECK_INTERVAL}s before retry..."
            sleep $HEALTH_CHECK_INTERVAL
        fi
        continue
    fi

    CONTAINER_STATUS=$(docker inspect --format='{{.State.Status}}' $NEW_CONTAINER_ID 2>/dev/null)
    echo "   Container status: $CONTAINER_STATUS"

    if [ "$CONTAINER_STATUS" != "running" ]; then
        echo "❌ Container is not in 'running' state"
        RETRY_COUNT=$((RETRY_COUNT + 1))
        if [ $RETRY_COUNT -lt $MAX_HEALTH_RETRIES ]; then
            echo "⏳ Waiting ${HEALTH_CHECK_INTERVAL}s before retry..."
            sleep $HEALTH_CHECK_INTERVAL
        fi
        continue
    fi

    if curl -sf http://localhost:8000/health >/dev/null 2>&1; then
        echo "✅ Health endpoint responding"
        HEALTH_CHECK_PASSED=true
        break
    else
        echo "⚠️  Health endpoint not responding yet"
        RETRY_COUNT=$((RETRY_COUNT + 1))
        if [ $RETRY_COUNT -lt $MAX_HEALTH_RETRIES ]; then
            echo "⏳ Waiting ${HEALTH_CHECK_INTERVAL}s before retry..."
            sleep $HEALTH_CHECK_INTERVAL
        fi
    fi
done

# --- 7. DECISION: SUCCESS OR ROLLBACK ---
echo ""
echo "═══════════════════════════════════════════════════════════════"

if [ "$HEALTH_CHECK_PASSED" = true ]; then
    echo "✅ DEPLOYMENT SUCCESSFUL!"
    echo ""
    echo "🎉 $SERVICE_NAME updated to version $NEW_VERSION_TAG"
    echo ""
    echo "📊 Current container status:"
    docker ps --filter "name=${SERVICE_NAME}" --format "table {{.Names}}\t{{.Image}}\t{{.Status}}"
    echo ""
    echo "🌐 Service URLs:"
    echo "   • API: http://localhost:8000"
    echo "   • Health: http://localhost:8000/health"
    echo "   • Docs: http://localhost:8000/docs"
    echo ""
    echo "📋 Useful Commands:"
    echo "   docker logs $SERVICE_NAME -f"
    echo "   $DOCKER_COMPOSE_CMD -f $DOCKER_COMPOSE_FILE ps"

else
    echo "❌ DEPLOYMENT FAILED!"
    echo ""
    echo "📋 Recent logs from failed container (last 100 lines):"
    echo "═══════════════════════════════════════════════════════════════"
    docker logs $SERVICE_NAME --tail=100 2>&1 || echo "   (Could not retrieve logs)"
    echo "═══════════════════════════════════════════════════════════════"
    echo ""

    if [ -n "$PREVIOUS_VERSION_TAG" ] && [ "$PREVIOUS_VERSION_TAG" != "latest" ]; then
        echo "🔄 INITIATING AUTOMATIC ROLLBACK..."
        echo "   Rolling back to version: $PREVIOUS_VERSION_TAG"

        export IMAGE_TAG=$PREVIOUS_VERSION_TAG

        echo "🚀 Starting previous version of $SERVICE_NAME..."
        $DOCKER_COMPOSE_CMD -f $DOCKER_COMPOSE_FILE up -d \
            --no-deps \
            --force-recreate \
            $SERVICE_NAME

        echo "🩺 Verifying rollback..."
        sleep 15

        if curl -sf http://localhost:8000/health >/dev/null 2>&1; then
            echo "✅ ROLLBACK SUCCESSFUL!"
            echo "   System restored to version: $PREVIOUS_VERSION_TAG"
        else
            echo "❌ CRITICAL: ROLLBACK ALSO FAILED!"
            echo ""
            docker logs $SERVICE_NAME --tail=100 2>&1 || true
            echo ""
            echo "🚨 Manual intervention required!"
            exit 1
        fi
    else
        echo "❌ No previous version available for rollback"
        echo "🚨 Manual intervention required!"
        exit 1
    fi
fi

# Cleanup
unset IMAGE_TAG
unset DOCKER_HUB_USERNAME

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "🏁 Deployment script completed"
