#!/bin/bash

# Firebase Service Account Setup Script
# Script để setup Firebase service account cho production

echo "🔐 Firebase Service Account Setup"
echo "================================="

# Check if Firebase CLI is installed
if ! command -v firebase &> /dev/null; then
    echo "❌ Firebase CLI not found. Installing..."
    npm install -g firebase-tools
fi

# Login to Firebase (if not already logged in)
echo "📝 Logging into Firebase..."
firebase login --no-localhost

# Set project
PROJECT_ID="aivungtau-34724"
echo "🎯 Setting Firebase project to: $PROJECT_ID"
firebase use $PROJECT_ID

# Generate service account key
echo "🔑 Generating service account key..."

SERVICE_ACCOUNT_EMAIL="firebase-adminsdk-xyz@${PROJECT_ID}.iam.gserviceaccount.com"
KEY_FILE="firebase-service-account.json"

# Create service account if doesn't exist
echo "👤 Creating service account..."
gcloud iam service-accounts create firebase-admin \
    --display-name="Firebase Admin SDK" \
    --description="Service account for Firebase Admin SDK" \
    --project=$PROJECT_ID 2>/dev/null || echo "Service account already exists"

# Grant necessary roles
echo "🛡️  Granting roles to service account..."
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:firebase-admin@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="roles/firebase.admin"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:firebase-admin@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="roles/datastore.user"

# Generate key file
echo "📄 Generating service account key file..."
gcloud iam service-accounts keys create $KEY_FILE \
    --iam-account="firebase-admin@${PROJECT_ID}.iam.gserviceaccount.com" \
    --project=$PROJECT_ID

echo "✅ Service account key generated: $KEY_FILE"
echo ""
echo "📋 Next Steps:"
echo "1. Copy $KEY_FILE to your secure location"
echo "2. Set environment variable: FIREBASE_SERVICE_ACCOUNT_PATH=/path/to/$KEY_FILE"
echo "3. Or extract individual values from the JSON file for environment variables"
echo ""
echo "🚨 Important: Keep this file secure and never commit it to version control!"

# Extract values for environment variables
if [ -f "$KEY_FILE" ]; then
    echo ""
    echo "📊 Environment Variables (copy to your .env file):"
    echo "FIREBASE_PROJECT_ID=$(jq -r '.project_id' $KEY_FILE)"
    echo "FIREBASE_PRIVATE_KEY_ID=$(jq -r '.private_key_id' $KEY_FILE)"
    echo "FIREBASE_PRIVATE_KEY=$(jq -r '.private_key' $KEY_FILE | sed 's/\n/\\n/g')"
    echo "FIREBASE_CLIENT_EMAIL=$(jq -r '.client_email' $KEY_FILE)"
    echo "FIREBASE_CLIENT_ID=$(jq -r '.client_id' $KEY_FILE)"
    echo "FIREBASE_CLIENT_CERT_URL=$(jq -r '.client_x509_cert_url' $KEY_FILE)"
fi
