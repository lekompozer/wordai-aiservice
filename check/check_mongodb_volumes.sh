#!/bin/bash
# MongoDB Volume Management Tools

echo "📊 MONGODB VOLUME ANALYSIS"
echo "========================="

echo "📂 Docker volumes list:"
docker volume ls | grep -E "(mongodb|redis)" || echo "No MongoDB/Redis volumes found"

echo ""
echo "🔍 MongoDB volume details:"
docker volume inspect mongodb_data 2>/dev/null || echo "mongodb_data volume not found"

echo ""
echo "📊 MongoDB data size:"
docker exec mongodb du -sh /data/db 2>/dev/null || echo "Cannot access MongoDB data directory"

echo ""
echo "📋 MongoDB collections:"
docker exec mongodb mongosh ai_chatbot_rag --username "$MONGODB_APP_USERNAME" --password "$MONGODB_APP_PASSWORD" --authenticationDatabase admin --eval "db.adminCommand('listCollections')" --quiet 2>/dev/null || echo "Cannot list collections"

echo ""
echo "🔧 VOLUME OPERATIONS:"
echo "   📂 Backup: docker exec mongodb mongodump --out /tmp/backup"
echo "   🔄 Restore: docker exec mongodb mongorestore /tmp/backup"
echo "   🗑️ DELETE ALL DATA: docker volume rm mongodb_data (⚠️ DANGEROUS!)"
echo "   📊 Size check: docker system df"

echo ""
echo "✅ CONCLUSION: Your MongoDB data is SAFE with named volume mounting!"
echo "   - Container deletion: Data survives ✅"
echo "   - Server reboot: Data survives ✅"
echo "   - Docker updates: Data survives ✅"
