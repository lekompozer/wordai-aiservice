#!/bin/bash

echo "🔄 Restarting Nginx with new configuration..."

# Pull latest code
echo "📥 Pulling latest code..."
git pull origin main

# Test nginx configuration
echo "🧪 Testing nginx configuration..."
docker exec nginx-gateway nginx -t

if [ $? -eq 0 ]; then
    echo "✅ Nginx configuration is valid"

    # Reload nginx (graceful reload without dropping connections)
    echo "🔄 Reloading nginx..."
    docker exec nginx-gateway nginx -s reload

    echo "✅ Nginx reloaded successfully!"
else
    echo "❌ Nginx configuration test failed!"
    echo "❌ NOT reloading nginx to prevent downtime"
    exit 1
fi

echo ""
echo "📊 Nginx status:"
docker ps --filter name=nginx-gateway --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
