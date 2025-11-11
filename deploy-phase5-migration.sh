#!/bin/bash
# Deploy and run Phase 5 marketplace database migration on production server

echo "🚀 Deploying Phase 5 Marketplace Database Migration..."

# Copy migration script to server
scp migrations/phase5_marketplace_setup.py root@104.248.147.155:/home/hoile/wordai/migrations/

# Run migration on server
ssh root@104.248.147.155 "su - hoile -c 'cd /home/hoile/wordai && python migrations/phase5_marketplace_setup.py'"

echo "✅ Migration completed!"
