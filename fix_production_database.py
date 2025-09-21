#!/usr/bin/env python3
"""
Script to fix production database issues
- Remove duplicate index
- Clean up null conversation_id documents
- Recreate indexes properly
"""

import os
import sys
from pymongo import MongoClient
from pymongo.errors import OperationFailure
import uuid
from datetime import datetime, timezone


def get_mongodb_connection():
    """Get MongoDB connection using environment variables"""
    mongodb_uri = os.getenv("MONGODB_URI_AUTH")
    mongodb_user = os.getenv("MONGODB_APP_USERNAME")
    mongodb_pass = os.getenv("MONGODB_APP_PASSWORD")
    mongodb_name = os.getenv("MONGODB_NAME", "ai_service_db")

    # Try multiple connection methods
    connection_methods = []

    if mongodb_uri:
        connection_methods.append(("MONGODB_URI_AUTH", mongodb_uri))

    if mongodb_user and mongodb_pass:
        # Try Docker container name first (for production deployment)
        container_uri = f"mongodb://{mongodb_user}:{mongodb_pass}@mongodb:27017/{mongodb_name}?authSource=admin"
        connection_methods.append(("Container name (mongodb)", container_uri))

        # Try host.docker.internal (for local development)
        host_uri = f"mongodb://{mongodb_user}:{mongodb_pass}@host.docker.internal:27017/{mongodb_name}?authSource=admin"
        connection_methods.append(("Host docker internal", host_uri))

        # Try localhost (fallback)
        localhost_uri = f"mongodb://{mongodb_user}:{mongodb_pass}@localhost:27017/{mongodb_name}?authSource=admin"
        connection_methods.append(("Localhost", localhost_uri))

    if not connection_methods:
        print("❌ No MongoDB credentials found")
        return None, None

    # Try each connection method
    for method_name, uri in connection_methods:
        client = None
        try:
            print(f"🔍 Trying connection method: {method_name}")
            client = MongoClient(uri, serverSelectionTimeoutMS=5000)
            # Test connection
            client.admin.command("ping")

            db = client[mongodb_name]
            print(f"✅ Connected to MongoDB via {method_name}: {mongodb_name}")
            return client, db
        except Exception as e:
            print(f"❌ Failed to connect via {method_name}: {e}")
            if client:
                try:
                    client.close()
                except:
                    pass
            continue

    print("❌ All MongoDB connection methods failed")
    return None, None


def fix_conversations_collection(db):
    """Fix conversations collection issues"""
    print("\n🔧 Fixing conversations collection...")

    conversations = db["conversations"]

    # 1. Find documents with null conversation_id
    null_docs = list(conversations.find({"conversation_id": None}))
    print(f"📊 Found {len(null_docs)} documents with null conversation_id")

    # 2. Update null conversation_id documents
    for doc in null_docs:
        new_conversation_id = str(uuid.uuid4())
        conversations.update_one(
            {"_id": doc["_id"]},
            {
                "$set": {
                    "conversation_id": new_conversation_id,
                    "updated_at": datetime.now(timezone.utc),
                }
            },
        )
        print(
            f"✅ Updated document {doc['_id']} with new conversation_id: {new_conversation_id}"
        )

    # 3. Drop existing problematic indexes
    try:
        conversations.drop_index("conversation_id_1")
        print("✅ Dropped old conversation_id index")
    except OperationFailure as e:
        print(f"ℹ️ Index conversation_id_1 doesn't exist or already dropped: {e}")

    # 4. Recreate indexes properly
    try:
        conversations.create_index("conversation_id", unique=True, sparse=True)
        conversations.create_index("user_id")
        conversations.create_index([("user_id", 1), ("updated_at", -1)])
        print("✅ Recreated conversation indexes with sparse option")
    except Exception as e:
        print(f"❌ Failed to recreate indexes: {e}")


def fix_users_collection(db):
    """Fix users collection issues"""
    print("\n🔧 Fixing users collection...")

    users = db["users"]

    # Check for null firebase_uid
    null_uid_docs = list(users.find({"firebase_uid": None}))
    print(f"📊 Found {len(null_uid_docs)} users with null firebase_uid")

    if null_uid_docs:
        print(
            "⚠️ Warning: Found users with null firebase_uid - these may need manual cleanup"
        )

    # Drop and recreate indexes to ensure sparse option
    try:
        # Drop existing indexes first
        try:
            users.drop_index("firebase_uid_1")
            print("✅ Dropped existing firebase_uid index")
        except Exception:
            pass

        try:
            users.drop_index("email_1")
            print("✅ Dropped existing email index")
        except Exception:
            pass

        # Recreate indexes with proper options
        users.create_index("firebase_uid", unique=True, sparse=True)
        users.create_index("email")
        print("✅ Recreated user indexes with sparse option")
    except Exception as e:
        print(f"❌ Failed to recreate user indexes: {e}")


def fix_files_collection(db):
    """Fix user_files collection issues"""
    print("\n🔧 Fixing user_files collection...")

    user_files = db["user_files"]

    # Check for null file_id
    null_file_docs = list(user_files.find({"file_id": None}))
    print(f"📊 Found {len(null_file_docs)} files with null file_id")

    # Update null file_id documents
    for doc in null_file_docs:
        new_file_id = str(uuid.uuid4())
        user_files.update_one(
            {"_id": doc["_id"]},
            {
                "$set": {
                    "file_id": new_file_id,
                    "updated_at": datetime.now(timezone.utc),
                }
            },
        )
        print(f"✅ Updated file document {doc['_id']} with new file_id: {new_file_id}")

    # Drop and recreate indexes
    try:
        # Drop existing indexes first
        try:
            user_files.drop_index("file_id_1")
            print("✅ Dropped existing file_id index")
        except Exception:
            pass

        try:
            user_files.drop_index("user_id_1")
            print("✅ Dropped existing user_id index")
        except Exception:
            pass

        # Recreate indexes with proper options
        user_files.create_index("file_id", unique=True, sparse=True)
        user_files.create_index("user_id")
        user_files.create_index([("user_id", 1), ("uploaded_at", -1)])
        print("✅ Recreated file indexes with sparse option")
    except Exception as e:
        print(f"❌ Failed to recreate file indexes: {e}")


def main():
    """Main function to fix production database"""
    print("🔧 Production Database Fix Script")
    print("=" * 50)

    # Load environment variables
    if os.path.exists(".env"):
        from dotenv import load_dotenv

        load_dotenv()
        print("✅ Loaded .env file")

    # Connect to MongoDB
    client, db = get_mongodb_connection()
    if client is None or db is None:
        print("❌ Cannot connect to MongoDB - exiting")
        sys.exit(1)

    try:
        # Fix each collection
        fix_conversations_collection(db)
        fix_users_collection(db)
        fix_files_collection(db)

        print("\n✅ Database fix completed successfully!")
        print("📊 Summary:")
        print(f"   • Conversations: {db['conversations'].count_documents({})}")
        print(f"   • Users: {db['users'].count_documents({})}")
        print(f"   • Files: {db['user_files'].count_documents({})}")

    except Exception as e:
        print(f"\n❌ Error during database fix: {e}")
        sys.exit(1)
    finally:
        client.close()
        print("\n🔒 Database connection closed")


if __name__ == "__main__":
    main()
