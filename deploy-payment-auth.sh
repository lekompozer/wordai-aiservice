#!/bin/bash
# Deploy payment authentication and activation endpoint
# Date: 2025-11-07

SERVER="root@104.248.147.155"
REMOTE_DIR="/home/hoile/wordai"

echo "🚀 Deploying payment authentication and activation fixes..."

# 1. Copy payment service files
echo "📦 Copying payment service files..."
scp payment-service/package.json $SERVER:$REMOTE_DIR/payment-service/
scp payment-service/src/middleware/firebaseAuth.js $SERVER:$REMOTE_DIR/payment-service/src/middleware/
scp payment-service/src/middleware/validation.js $SERVER:$REMOTE_DIR/payment-service/src/middleware/
scp payment-service/src/routes/paymentRoutes.js $SERVER:$REMOTE_DIR/payment-service/src/routes/
scp payment-service/src/controllers/paymentController.js $SERVER:$REMOTE_DIR/payment-service/src/controllers/

# 2. Copy Python service files
echo "📦 Copying Python service files..."
scp src/api/payment_activation_routes.py $SERVER:$REMOTE_DIR/src/api/
scp src/app.py $SERVER:$REMOTE_DIR/src/

# 3. Install firebase-admin in payment service
echo "📦 Installing firebase-admin in payment-service..."
ssh $SERVER "cd $REMOTE_DIR/payment-service && npm install firebase-admin@^12.0.0"

# 4. Restart payment service
echo "🔄 Restarting payment-service..."
ssh $SERVER "docker restart payment-service"

# 5. Restart Python service
echo "🔄 Restarting ai-chatbot-rag..."
ssh $SERVER "docker restart ai-chatbot-rag"

# 6. Wait and check logs
echo "⏳ Waiting 5 seconds for services to start..."
sleep 5

echo "📊 Payment service logs:"
ssh $SERVER "docker logs payment-service 2>&1 | tail -20"

echo ""
echo "📊 Python service logs:"
ssh $SERVER "docker logs ai-chatbot-rag 2>&1 | tail -20"

echo ""
echo "✅ Deployment complete!"
echo ""
echo "🔍 To test:"
echo "1. Frontend must send Firebase auth token in Authorization header"
echo "2. Make a test payment with real logged-in user"
echo "3. Check IPN activates subscription and adds points"
echo ""
echo "📝 Check logs:"
echo "  docker logs payment-service -f"
echo "  docker logs ai-chatbot-rag -f"
