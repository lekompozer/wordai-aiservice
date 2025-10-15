#!/usr/bin/env python3
"""
Fix secret documents missing encrypted_file_keys
Auto-generate file_key for documents created before auto-generation feature
"""

import os
import sys
from datetime import datetime
from pymongo import MongoClient
from dotenv import load_dotenv
import secrets
import base64
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend

# Load environment
ENV = os.getenv("ENV", "development")
if ENV == "production":
    load_dotenv("production.env")
else:
    load_dotenv("development.env")

# MongoDB connection
MONGODB_URI = os.getenv("MONGODB_URI_AUTH") or os.getenv("MONGODB_URI", "mongodb://localhost:27017")
MONGODB_NAME = os.getenv("MONGODB_NAME", "ai_chatbot_db")

print(f"🔧 Fixing missing file_keys in {ENV} environment")
print(f"📦 Database: {MONGODB_NAME}")

# Connect to MongoDB
try:
    client = MongoClient(MONGODB_URI)
    db = client[MONGODB_NAME]
    print("✅ Connected to MongoDB")
except Exception as e:
    print(f"❌ Failed to connect to MongoDB: {e}")
    sys.exit(1)


def generate_file_key_for_user(owner_id: str, public_key_pem: str) -> str:
    """
    Generate random file_key and encrypt with user's public key
    
    Args:
        owner_id: User's Firebase UID
        public_key_pem: User's RSA public key (PEM format)
        
    Returns:
        Base64 encoded encrypted file_key
    """
    try:
        # Generate random 32-byte AES-256 file key
        file_key = secrets.token_bytes(32)
        
        # Load public key
        public_key_obj = serialization.load_pem_public_key(
            public_key_pem.encode('utf-8'),
            backend=default_backend()
        )
        
        # Encrypt file_key with RSA-OAEP
        encrypted_file_key_bytes = public_key_obj.encrypt(
            file_key,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        
        # Base64 encode
        encrypted_file_key = base64.b64encode(encrypted_file_key_bytes).decode('utf-8')
        
        return encrypted_file_key
        
    except Exception as e:
        print(f"  ❌ Error generating file_key for user {owner_id}: {e}")
        return None


def fix_document(secret_doc):
    """Fix a single secret document"""
    secret_id = secret_doc["secret_id"]
    owner_id = secret_doc["owner_id"]
    
    print(f"\n🔍 Processing: {secret_id}")
    print(f"   Owner: {owner_id}")
    print(f"   Title: {secret_doc.get('title', 'Untitled')}")
    
    # Check if already has file_keys
    if "encrypted_file_keys" in secret_doc and secret_doc["encrypted_file_keys"]:
        if owner_id in secret_doc["encrypted_file_keys"]:
            print(f"   ✅ Already has file_key for owner - SKIP")
            return False
    
    # Get owner's public key
    user = db.users.find_one({"firebase_uid": owner_id})
    if not user:
        print(f"   ❌ User {owner_id} not found - SKIP")
        return False
    
    if "publicKey" not in user:
        print(f"   ❌ User {owner_id} has no public key - SKIP")
        return False
    
    public_key = user["publicKey"]
    
    # Generate file_key
    print(f"   🔑 Generating file_key...")
    encrypted_file_key = generate_file_key_for_user(owner_id, public_key)
    
    if not encrypted_file_key:
        print(f"   ❌ Failed to generate file_key - SKIP")
        return False
    
    # Update document in database
    result = db.secret_documents.update_one(
        {"secret_id": secret_id},
        {
            "$set": {
                f"encrypted_file_keys.{owner_id}": encrypted_file_key,
                "updated_at": datetime.utcnow()
            }
        }
    )
    
    if result.modified_count > 0:
        print(f"   ✅ FIXED - Added file_key for owner")
        return True
    else:
        print(f"   ⚠️ Update failed")
        return False


def main():
    """Main function"""
    print("\n" + "="*60)
    print("🔧 FIXING SECRET DOCUMENTS MISSING FILE_KEYS")
    print("="*60)
    
    # Find all secret documents
    secret_docs = list(db.secret_documents.find({"is_trashed": False}))
    
    print(f"\n📊 Found {len(secret_docs)} secret documents")
    
    if len(secret_docs) == 0:
        print("✅ No documents to fix")
        return
    
    # Process each document
    fixed_count = 0
    skip_count = 0
    error_count = 0
    
    for doc in secret_docs:
        try:
            fixed = fix_document(doc)
            if fixed:
                fixed_count += 1
            else:
                skip_count += 1
        except Exception as e:
            print(f"   ❌ Error: {e}")
            error_count += 1
    
    # Summary
    print("\n" + "="*60)
    print("📊 SUMMARY")
    print("="*60)
    print(f"Total documents: {len(secret_docs)}")
    print(f"✅ Fixed: {fixed_count}")
    print(f"⏭️  Skipped: {skip_count}")
    print(f"❌ Errors: {error_count}")
    print("="*60)
    
    if fixed_count > 0:
        print(f"\n✅ Successfully fixed {fixed_count} documents!")
        print("🔄 Users should now be able to decrypt their documents.")
    else:
        print("\n✅ No documents needed fixing.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️ Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        sys.exit(1)
