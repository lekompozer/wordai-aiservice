#!/bin/bash

# ===================================================================================
# DOCKER-COMPOSE DEPLOYMENT WITH AUTOMATIC ROLLBACK (NO CACHE VERSION)
# ===================================================================================
# This script deploys using docker-compose.yml with safety mechanisms:
# 1. Tags images with Git commit hash for versioning
# 2. Saves current running version before deploying new version
# 3. Performs health checks on new deployment
# 4. Automatically rolls back to previous version if health check fails
#
# ⚠️  NO CACHE VERSION: This will rebuild from scratch and reinstall all libraries
# Use this when:
# - You updated requirements.txt or package dependencies
# - You want a completely fresh build
# - You suspect cache corruption issues
#
# For faster deploys with cache, use: deploy-compose-with-rollback.sh
#
# PREREQUISITES:
# - Network "ai-chatbot-network" must exist (created by deploy-manual.sh)
# - .env file with all required credentials must exist
# ===================================================================================

set -e # Exit immediately if a command exits with a non-zero status

# --- DETECT DOCKER COMPOSE COMMAND ---
# Auto-detect whether to use 'docker-compose' (v1) or 'docker compose' (v2)
if command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE_CMD="docker-compose"
elif docker compose version &> /dev/null; then
    DOCKER_COMPOSE_CMD="docker compose"
else
    echo "❌ ERROR: Neither 'docker-compose' nor 'docker compose' command found!"
    echo "   Please install Docker Compose: https://docs.docker.com/compose/install/"
    exit 1
fi

echo "✅ Using Docker Compose command: $DOCKER_COMPOSE_CMD"

# --- CONFIGURATION ---
APP_NAME="wordai-aiservice"
DOCKER_COMPOSE_FILE="docker-compose.yml"
SERVICE_NAME="ai-chatbot-rag"
HEALTH_CHECK_DELAY=60 # Seconds to wait before checking health
MAX_HEALTH_RETRIES=3  # Number of health check attempts
HEALTH_CHECK_INTERVAL=15 # Seconds between health check retries
DOCKER_HUB_USERNAME="${DOCKER_HUB_USERNAME:-lekompozer}"
NETWORK_NAME="ai-chatbot-network"

echo "🚀 Starting Docker Compose deployment with rollback protection..."
echo "═══════════════════════════════════════════════════════════════"
echo "⚠️  NO CACHE MODE: This will rebuild everything from scratch"
echo "   • All Docker build cache will be ignored"
echo "   • All Python dependencies will be reinstalled"
echo "   • Build time will be significantly longer"
echo ""
echo "💡 For faster deploys with cache, use: ./deploy-compose-with-rollback.sh"
echo "═══════════════════════════════════════════════════════════════"

# --- 1. VERIFY PREREQUISITES ---
echo "🔍 Verifying prerequisites..."

# Check if .env file exists
if [ ! -f .env ]; then
    echo "❌ ERROR: .env file not found!"
    echo "   Please create .env file with required credentials."
    exit 1
fi

# Check if network exists
if ! docker network ls | grep -q "$NETWORK_NAME"; then
    echo "⚠️  Network '$NETWORK_NAME' does not exist. Creating it..."
    docker network create --driver bridge "$NETWORK_NAME"
    echo "✅ Network created: $NETWORK_NAME"
else
    echo "✅ Network '$NETWORK_NAME' exists"
fi

# Load environment variables
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
        echo "   Rollback may not be available."
    fi
else
    echo "⚠️  No currently running container found."
    echo "   This appears to be a fresh deployment."
fi

# --- 4. BUILD NEW DOCKER IMAGE (NO CACHE) ---
echo ""
echo "🛠️  Building new Docker image (NO CACHE - Full rebuild)..."
echo "   Tag: $DOCKER_HUB_USERNAME/$APP_NAME:$NEW_VERSION_TAG"
echo "   ⏱️  This may take several minutes as all layers will be rebuilt..."

export IMAGE_TAG=$NEW_VERSION_TAG
export DOCKER_HUB_USERNAME=$DOCKER_HUB_USERNAME

# Build the image with --no-cache flag to force fresh build
DOCKER_BUILDKIT=1 docker build \
    --no-cache \
    --pull \
    -t "$DOCKER_HUB_USERNAME/$APP_NAME:$NEW_VERSION_TAG" \
    .

# Also tag as latest
docker tag "$DOCKER_HUB_USERNAME/$APP_NAME:$NEW_VERSION_TAG" "$DOCKER_HUB_USERNAME/$APP_NAME:latest"

echo "✅ Image built and tagged successfully (no cache used)"

# --- 5. DEPLOY NEW VERSION ---
echo ""
echo "🚀 Deploying new version with docker-compose..."
echo "   Version: $NEW_VERSION_TAG"

# Stop any standalone containers from deploy-manual.sh that might conflict
echo "🛑 Checking for existing standalone containers..."
if docker ps -a --format '{{.Names}}' | grep -q "^mongodb$"; then
    echo "   Found standalone mongodb container, stopping it..."
    docker stop mongodb 2>/dev/null || true
    docker rm mongodb 2>/dev/null || true
    echo "   ✅ Standalone mongodb container removed (data preserved in volume)"
fi

if docker ps -a --format '{{.Names}}' | grep -q "^redis-server$"; then
    echo "   Found standalone redis-server container, stopping it..."
    docker stop redis-server 2>/dev/null || true
    docker rm redis-server 2>/dev/null || true
    echo "   ✅ Standalone redis-server container removed (data preserved in volume)"
fi

if docker ps -a --format '{{.Names}}' | grep -q "^ai-chatbot-rag$"; then
    echo "   Found standalone ai-chatbot-rag container, stopping it..."
    docker stop ai-chatbot-rag 2>/dev/null || true
    docker rm ai-chatbot-rag 2>/dev/null || true
    echo "   ✅ Standalone ai-chatbot-rag container removed"
fi

# Stop current docker-compose services (if any)
echo "🛑 Stopping docker-compose managed services..."
$DOCKER_COMPOSE_CMD -f $DOCKER_COMPOSE_FILE down --remove-orphans

# Start new services
echo "🚀 Starting new services..."
$DOCKER_COMPOSE_CMD -f $DOCKER_COMPOSE_FILE up -d

echo "✅ Services started"

# --- 5b. ENSURE MONGODB USER EXISTS ---
echo ""
echo "🔐 Ensuring MongoDB application user exists..."
sleep 10  # Wait for MongoDB to be ready

# Check if app user exists, create if not
docker exec mongodb mongosh admin \
  --username "$MONGODB_ROOT_USERNAME" \
  --password "$MONGODB_ROOT_PASSWORD" \
  --eval "
    const userExists = db.getUser('$MONGODB_APP_USERNAME');
    if (!userExists) {
      db.createUser({
        user: '$MONGODB_APP_USERNAME',
        pwd: '$MONGODB_APP_PASSWORD',
        roles: [
          { role: 'readWrite', db: '$MONGODB_NAME' },
          { role: 'dbAdmin', db: '$MONGODB_NAME' }
        ]
      });
      print('✅ Application user created');
    } else {
      print('ℹ️  Application user already exists');
    }
  " 2>/dev/null || echo "⚠️  Note: User may already exist or MongoDB is still starting"

echo "✅ MongoDB user check completed"

# --- 5c. RUN E2EE MIGRATION SCRIPT (IF NEEDED) ---
echo ""
echo "🔐 Checking E2EE keys migration status..."

# Check if migration is needed (using admin auth for reliability)
MIGRATION_NEEDED=$(docker exec mongodb mongosh "$MONGODB_NAME" \
  --username "$MONGODB_ROOT_USERNAME" \
  --password "$MONGODB_ROOT_PASSWORD" \
  --authenticationDatabase admin \
  --quiet \
  --eval "db.users.countDocuments({publicKey: {\$exists: true}, e2eeKeysMigrated: {\$ne: true}})" 2>/dev/null || echo "0")

if [ "$MIGRATION_NEEDED" -gt 0 ]; then
    echo "⚠️  Found $MIGRATION_NEEDED users with old E2EE keys (24-word system)"
    echo "🚀 Running migration to 12-word recovery system..."
    echo ""
    echo "📋 Migration will:"
    echo "   • Create backup of all E2EE keys"
    echo "   • Clear old keys (24-word system)"
    echo "   • Mark secret documents as unreadable"
    echo "   • Set migration flags for tracking"
    echo ""

    # Run migration script inside container with production environment
    # Script will auto-confirm in non-interactive mode (no stdin input needed)
    docker exec -e ENV=production $SERVICE_NAME python3 migrate_to_12_word_recovery.py

    MIGRATION_EXIT_CODE=$?

    if [ $MIGRATION_EXIT_CODE -eq 0 ]; then
        echo ""
        echo "✅ E2EE keys migration completed successfully"
        echo ""
        echo "📂 Backup files created inside container:"
        docker exec $SERVICE_NAME ls -lh e2ee_keys_backup_*.json 2>/dev/null || echo "   (No backup files found)"
        echo ""
        echo "💡 To retrieve backup files:"
        echo "   docker cp $SERVICE_NAME:/app/e2ee_keys_backup_production_*.json ./backups/"
        echo ""
    else
        echo ""
        echo "⚠️  Migration script exited with code: $MIGRATION_EXIT_CODE"
        echo "   Continuing deployment anyway..."
        echo ""
        echo "🔧 Troubleshooting:"
        echo "   • Check migration logs: docker exec $SERVICE_NAME cat migration_log_*.json"
        echo "   • Run manually: docker exec -it $SERVICE_NAME python3 migrate_to_12_word_recovery.py"
        echo "   • Check MongoDB connection from container"
        echo ""
    fi
else
    echo "✅ No E2EE migration needed"
    echo "   Reason: No users with old keys found"
    echo "   • Users already migrated: $(docker exec mongodb mongosh "$MONGODB_NAME" --username "$MONGODB_ROOT_USERNAME" --password "$MONGODB_ROOT_PASSWORD" --authenticationDatabase admin --quiet --eval "db.users.countDocuments({e2eeKeysMigrated: true})" 2>/dev/null || echo "N/A")"
    echo "   • Users with keys: $(docker exec mongodb mongosh "$MONGODB_NAME" --username "$MONGODB_ROOT_USERNAME" --password "$MONGODB_ROOT_PASSWORD" --authenticationDatabase admin --quiet --eval "db.users.countDocuments({publicKey: {\$exists: true}})" 2>/dev/null || echo "N/A")"
fi

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

    # Check if container is running
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

    # Check container status
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

    # Check HTTP health endpoint
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
    # ✅ SUCCESS
    echo "✅ DEPLOYMENT SUCCESSFUL!"
    echo ""
    echo "🎉 New version $NEW_VERSION_TAG is running and healthy"
    echo "   Built with NO CACHE - all dependencies freshly installed"
    echo ""
    echo "📊 Current Status:"
    $DOCKER_COMPOSE_CMD -f $DOCKER_COMPOSE_FILE ps
    echo ""
    echo "🌐 Service URLs:"
    echo "   • API: http://localhost:8000"
    echo "   • Health: http://localhost:8000/health"
    echo "   • Docs: http://localhost:8000/docs"
    echo ""
    echo "📋 Useful Commands:"
    echo "   $DOCKER_COMPOSE_CMD -f $DOCKER_COMPOSE_FILE logs -f $SERVICE_NAME"
    echo "   $DOCKER_COMPOSE_CMD -f $DOCKER_COMPOSE_FILE ps"
    echo "   $DOCKER_COMPOSE_CMD -f $DOCKER_COMPOSE_FILE down"
    echo ""
    echo "💡 Next deploys can use cached version for speed:"
    echo "   ./deploy-compose-with-rollback.sh"

else
    # ❌ FAILURE - ROLLBACK
    echo "❌ DEPLOYMENT FAILED!"
    echo ""
    echo "🔍 Diagnosis:"
    echo "   Health checks failed after $MAX_HEALTH_RETRIES attempts"
    echo ""
    echo "📋 Recent logs from failed container:"
    docker logs $SERVICE_NAME --tail=50 2>/dev/null || echo "   (Could not retrieve logs)"
    echo ""

    if [ -n "$PREVIOUS_VERSION_TAG" ] && [ "$PREVIOUS_VERSION_TAG" != "latest" ]; then
        echo "🔄 INITIATING AUTOMATIC ROLLBACK..."
        echo "   Rolling back to version: $PREVIOUS_VERSION_TAG"

        # Stop failed deployment
        echo "🛑 Stopping failed deployment..."
        $DOCKER_COMPOSE_CMD -f $DOCKER_COMPOSE_FILE down --remove-orphans

        # Set environment to previous version
        export IMAGE_TAG=$PREVIOUS_VERSION_TAG

        # Start previous version
        echo "🚀 Starting previous version..."
        $DOCKER_COMPOSE_CMD -f $DOCKER_COMPOSE_FILE up -d

        # Quick health check on rolled-back version
        echo "🩺 Verifying rollback..."
        sleep 15

        if curl -sf http://localhost:8000/health >/dev/null 2>&1; then
            echo "✅ ROLLBACK SUCCESSFUL!"
            echo ""
            echo "🎯 System restored to version: $PREVIOUS_VERSION_TAG"
            echo ""
            echo "⚠️  Action Required:"
            echo "   • Review logs: docker logs $SERVICE_NAME --tail=100"
            echo "   • Fix issues in code or dependencies"
            echo "   • Check requirements.txt for conflicting packages"
            echo "   • Test locally before redeploying"
        else
            echo "❌ CRITICAL: ROLLBACK ALSO FAILED!"
            echo ""
            echo "🚨 IMMEDIATE ACTION REQUIRED:"
            echo "   • System may be down"
            echo "   • Check logs: docker logs $SERVICE_NAME"
            echo "   • Manual intervention needed"
            echo "   • Consider running: ./deploy-manual.sh"
            exit 1
        fi
    else
        echo "❌ CRITICAL FAILURE: No previous version available for rollback"
        echo ""
        echo "🚨 IMMEDIATE ACTION REQUIRED:"
        echo "   • System is down"
        echo "   • Review logs: docker logs $SERVICE_NAME --tail=100"
        echo "   • Fix issues and redeploy"
        echo "   • Or restore from backup manually"
        exit 1
    fi
fi

# Cleanup
unset IMAGE_TAG
unset DOCKER_HUB_USERNAME

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "🏁 Deployment script completed"
echo ""
echo "💾 Build Cache Status: CLEARED (no-cache build)"
echo "   Next build will also be slow unless you use cached version"
