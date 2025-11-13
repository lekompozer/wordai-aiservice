#!/bin/bash
set -e

echo "==================================================================="
echo "🚀 Deploying Test Generator JSON Fix to Production"
echo "==================================================================="

# Configuration
PROD_SERVER="root@104.248.147.155"
BACKUP_DIR="/root/wordai-backup-$(date +%Y%m%d_%H%M%S)"
SERVICE_DIR="/root/wordai-aiservice"

echo ""
echo "📦 Step 1: Creating backup on production server..."
ssh $PROD_SERVER "mkdir -p $BACKUP_DIR && cp $SERVICE_DIR/src/services/test_generator_service.py $BACKUP_DIR/"
echo "✅ Backup created at $BACKUP_DIR"

echo ""
echo "📤 Step 2: Uploading fixed test_generator_service.py..."
scp src/services/test_generator_service.py $PROD_SERVER:$SERVICE_DIR/src/services/test_generator_service.py
echo "✅ File uploaded successfully"

echo ""
echo "🔄 Step 3: Restarting services..."
ssh $PROD_SERVER << 'EOF'
cd /root/wordai-aiservice

echo "Stopping services..."
docker-compose down

echo "Starting services with new code..."
docker-compose up -d

echo "Waiting for services to be healthy..."
sleep 10

echo "Checking service status..."
docker-compose ps
EOF

echo ""
echo "✅ Deployment completed!"
echo ""
echo "==================================================================="
echo "📋 Changes deployed:"
echo "   - Added _fix_json_string() method to clean malformed JSON"
echo "   - Enhanced JSON parsing with better error logging"
echo "   - Added debug file output for failed JSON parsing"
echo "   - Updated prompt to request properly escaped JSON"
echo "==================================================================="
echo ""
echo "🧪 To test the fix, try generating a test with Vietnamese PDF again."
echo ""
echo "📊 To view logs:"
echo "   ssh $PROD_SERVER 'docker-compose logs -f --tail=100 wordai-service'"
echo ""
echo "⚠️  If issues occur, rollback with:"
echo "   ssh $PROD_SERVER 'cp $BACKUP_DIR/test_generator_service.py $SERVICE_DIR/src/services/test_generator_service.py && cd $SERVICE_DIR && docker-compose restart'"
echo ""
