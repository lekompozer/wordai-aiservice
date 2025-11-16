#!/bin/bash

# Deploy Trash System to Production
# Adds soft delete functionality for books

set -e  # Exit on error

echo "🚀 Deploying Trash System..."

SERVER="root@104.248.147.155"
REMOTE_DIR="/root/wordai-aiservice"

# Step 1: Backup current code
echo "📦 Creating backup..."
ssh $SERVER "cd $REMOTE_DIR && tar -czf backup-trash-$(date +%Y%m%d-%H%M%S).tar.gz src/*.py src/**/*.py || true"

# Step 2: Upload modified files
echo "📤 Uploading modified files..."
scp src/models/book_models.py $SERVER:$REMOTE_DIR/src/models/
scp src/services/book_manager.py $SERVER:$REMOTE_DIR/src/services/
scp src/api/book_routes.py $SERVER:$REMOTE_DIR/src/api/
scp migrate_add_soft_delete_fields.py $SERVER:$REMOTE_DIR/

# Step 3: Run migration on production
echo "🔄 Running MongoDB migration..."
ssh $SERVER "cd $REMOTE_DIR && source venv/bin/activate && python migrate_add_soft_delete_fields.py"

# Step 4: Restart services
echo "🔄 Restarting services..."
ssh $SERVER "cd $REMOTE_DIR && docker-compose restart app"

# Step 5: Wait for services to start
echo "⏳ Waiting for services to start..."
sleep 10

# Step 6: Health check
echo "🏥 Checking health..."
HEALTH_CHECK=$(curl -s -o /dev/null -w "%{http_code}" https://wordai.ai/api/health || echo "000")

if [ "$HEALTH_CHECK" = "200" ]; then
    echo "✅ Deployment successful! Health check passed."
else
    echo "⚠️ Warning: Health check returned $HEALTH_CHECK"
    echo "📋 Check logs: ssh $SERVER 'cd $REMOTE_DIR && docker-compose logs -f app'"
fi

# Step 7: Test trash endpoints
echo ""
echo "📝 Testing trash endpoints..."
echo ""
echo "Test commands:"
echo "  1. Move to trash (soft delete):"
echo "     curl -X DELETE 'https://wordai.ai/api/v1/books/{book_id}?permanent=false' -H 'Authorization: Bearer TOKEN'"
echo ""
echo "  2. List trash:"
echo "     curl 'https://wordai.ai/api/v1/books/trash?page=1&limit=20' -H 'Authorization: Bearer TOKEN'"
echo ""
echo "  3. Restore from trash:"
echo "     curl -X POST 'https://wordai.ai/api/v1/books/{book_id}/restore' -H 'Authorization: Bearer TOKEN'"
echo ""
echo "  4. Permanent delete:"
echo "     curl -X DELETE 'https://wordai.ai/api/v1/books/{book_id}?permanent=true' -H 'Authorization: Bearer TOKEN'"
echo ""
echo "  5. Empty trash:"
echo "     curl -X DELETE 'https://wordai.ai/api/v1/books/trash/empty' -H 'Authorization: Bearer TOKEN'"
echo ""
echo "✅ Deployment complete!"
