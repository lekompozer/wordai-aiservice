#!/bin/bash

# Deploy StudyHub Category & Course System
# Phase 1: Setup database and test locally first

echo "========================================"
echo "StudyHub Category & Course System Deploy"
echo "========================================"

# Step 1: Test locally first
echo ""
echo "Step 1: Testing setup locally..."
python3 setup_studyhub_categories.py

if [ $? -ne 0 ]; then
    echo "✗ Local setup failed! Fix errors before deploying."
    exit 1
fi

echo ""
echo "✓ Local setup successful!"

# Step 2: Ask user to confirm production deploy
echo ""
echo "========================================"
read -p "Deploy to production? (y/n): " -n 1 -r
echo ""
echo "========================================"

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Deployment cancelled."
    exit 0
fi

# Step 3: Deploy to production
echo ""
echo "Step 3: Deploying to production..."

# Upload setup script
echo "Uploading setup script..."
scp setup_studyhub_categories.py root@104.248.147.155:/home/hoile/wordai/

# Run setup on production
echo "Running setup on production..."
ssh root@104.248.147.155 "su - hoile -c 'cd /home/hoile/wordai && python3 setup_studyhub_categories.py'"

if [ $? -ne 0 ]; then
    echo "✗ Production setup failed!"
    exit 1
fi

# Step 4: Deploy code
echo ""
echo "Step 4: Deploying code with rollback support..."
ssh root@104.248.147.155 "su - hoile -c 'cd /home/hoile/wordai && ./deploy-compose-with-rollback.sh'"

if [ $? -ne 0 ]; then
    echo "✗ Code deployment failed!"
    exit 1
fi

echo ""
echo "========================================"
echo "✓ Deployment completed successfully!"
echo "========================================"
echo ""
echo "New endpoints available:"
echo "  - GET  /api/studyhub/categories"
echo "  - GET  /api/studyhub/categories/{category_id}"
echo "  - GET  /api/studyhub/categories/{category_id}/subjects"
echo "  - POST /api/studyhub/categories/{category_id}/subjects"
echo "  - POST /api/studyhub/subjects/{subject_id}/publish-course"
echo "  - GET  /api/studyhub/courses"
echo "  - GET  /api/studyhub/courses/{course_id}"
echo "  - POST /api/studyhub/courses/{course_id}/enroll"
echo "  - GET  /api/studyhub/community/top-courses"
echo "  - GET  /api/studyhub/community/trending-courses"
echo "  - GET  /api/studyhub/community/search"
echo "  - GET  /api/studyhub/community/enrolled-courses"
echo ""
echo "API Docs: https://wordai.asia/docs"
echo ""
