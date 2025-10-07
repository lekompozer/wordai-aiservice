#!/bin/bash

# ===================================================================================
# EMERGENCY FIX: Create MongoDB Application User
# ===================================================================================
# This script manually creates the MongoDB application user if it doesn't exist
# Run this when deployment fails due to MongoDB authentication issues
# ===================================================================================

set -e

echo "🚨 Emergency MongoDB User Creation Script"
echo "═══════════════════════════════════════════════════════════════"

# Load environment variables
if [ -f .env ]; then
    source .env
    echo "✅ Loaded environment variables from .env"
else
    echo "❌ .env file not found!"
    exit 1
fi

echo ""
echo "🔍 Checking if MongoDB container is running..."

if ! docker ps --format '{{.Names}}' | grep -q "^mongodb$"; then
    echo "❌ MongoDB container is not running!"
    echo ""
    echo "Starting MongoDB container..."
    docker start mongodb 2>/dev/null || {
        echo "❌ Failed to start MongoDB container"
        echo "   Run one of these commands first:"
        echo "   • ./deploy-manual.sh (original deployment)"
        echo "   • docker compose up -d mongodb (docker-compose deployment)"
        exit 1
    }
    echo "⏳ Waiting for MongoDB to be ready..."
    sleep 10
fi

echo "✅ MongoDB container is running"

echo ""
echo "🔐 Creating/Verifying MongoDB application user..."
echo "   Username: $MONGODB_APP_USERNAME"
echo "   Database: $MONGODB_NAME"

# Create user using mongosh
docker exec mongodb mongosh admin \
  --username "$MONGODB_ROOT_USERNAME" \
  --password "$MONGODB_ROOT_PASSWORD" \
  --quiet \
  --eval "
    print('🔍 Checking if user exists...');
    const userExists = db.getUser('$MONGODB_APP_USERNAME');

    if (!userExists) {
      print('📝 Creating application user: $MONGODB_APP_USERNAME');

      db.createUser({
        user: '$MONGODB_APP_USERNAME',
        pwd: '$MONGODB_APP_PASSWORD',
        roles: [
          { role: 'readWrite', db: '$MONGODB_NAME' },
          { role: 'dbAdmin', db: '$MONGODB_NAME' }
        ]
      });

      print('✅ Application user created successfully');
    } else {
      print('ℹ️  Application user already exists');

      // Update password in case it changed
      db.updateUser('$MONGODB_APP_USERNAME', {
        pwd: '$MONGODB_APP_PASSWORD',
        roles: [
          { role: 'readWrite', db: '$MONGODB_NAME' },
          { role: 'dbAdmin', db: '$MONGODB_NAME' }
        ]
      });

      print('✅ Application user password updated');
    }
  "

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ MongoDB user setup completed successfully!"
    echo ""
    echo "🧪 Testing connection with application credentials..."

    # Test connection
    docker exec mongodb mongosh "$MONGODB_NAME" \
      --username "$MONGODB_APP_USERNAME" \
      --password "$MONGODB_APP_PASSWORD" \
      --authenticationDatabase admin \
      --quiet \
      --eval "print('✅ Authentication successful! Connection works.')" 2>&1

    if [ $? -eq 0 ]; then
        echo ""
        echo "🎉 SUCCESS! MongoDB is ready for the application"
        echo ""
        echo "📋 Next steps:"
        echo "   1. Restart your application container:"
        echo "      docker restart ai-chatbot-rag"
        echo ""
        echo "   2. Or redeploy with docker-compose:"
        echo "      ./deploy-compose-with-rollback.sh"
        echo ""
        echo "   3. Check application logs:"
        echo "      docker logs ai-chatbot-rag -f"
    else
        echo ""
        echo "⚠️  User created but authentication test failed"
        echo "   This might be a temporary issue. Try restarting MongoDB:"
        echo "   docker restart mongodb"
    fi
else
    echo ""
    echo "❌ Failed to create/update MongoDB user"
    echo ""
    echo "🔍 Troubleshooting:"
    echo "   • Check MongoDB logs: docker logs mongodb"
    echo "   • Verify root credentials in .env file"
    echo "   • Ensure MongoDB is fully started: docker ps"
    exit 1
fi
