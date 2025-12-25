#!/bin/bash
# Deploy GCP Service Account credentials to production server

set -e

SERVER="root@104.248.147.155"
LOCAL_JSON="wordai-6779e-ed6189c466f1.json"
REMOTE_PATH="/home/hoile/wordai/wordai-6779e-ed6189c466f1.json"

echo "🔐 Deploying GCP Service Account credentials to server..."

# Check if local file exists
if [ ! -f "$LOCAL_JSON" ]; then
    echo "❌ Error: $LOCAL_JSON not found in current directory"
    exit 1
fi

# Copy file to server
echo "📤 Copying $LOCAL_JSON to server..."
scp "$LOCAL_JSON" "$SERVER:$REMOTE_PATH"

# Set proper permissions
echo "🔒 Setting file permissions (600)..."
ssh "$SERVER" "chmod 600 $REMOTE_PATH"

# Verify file exists
echo "✅ Verifying deployment..."
ssh "$SERVER" "ls -lh $REMOTE_PATH"

echo ""
echo "✅ GCP Service Account credentials deployed successfully!"
echo ""
echo "📝 Next steps:"
echo "   1. Deploy updated code: ./deploy-compose-with-rollback.sh"
echo "   2. Check logs: ssh $SERVER 'docker logs ai-chatbot-rag --tail 50'"
echo "   3. Verify Vertex AI: Look for 'Vertex AI (service account)' in logs"
