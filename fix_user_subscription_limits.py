#!/usr/bin/env python3
"""
Fix User Subscription Limits Script

This script fixes incorrect subscription limits for users who were activated
with the buggy payment_activation_routes.py code that had hardcoded wrong values.

AFFECTED USERS:
- xuanphuongxhnv@gmail.com → VIP plan
- tienhoi.lh@gmail.com → Premium plan

WRONG VALUES (old buggy code):
- storage_limit_mb: 5120 (5GB) or 20480 (20GB)
- upload_files_limit: 500 or 2000
- documents_limit: 10
- daily_chat_limit: 10

CORRECT VALUES (from PLAN_CONFIGS):
Premium:
  - storage_limit_mb: 2048 (2GB)
  - upload_files_limit: 100
  - documents_limit: 100
  - daily_chat_limit: -1 (unlimited)

VIP:
  - storage_limit_mb: 51200 (50GB)
  - upload_files_limit: -1 (unlimited)
  - documents_limit: -1 (unlimited)
  - daily_chat_limit: -1 (unlimited)

USAGE (on production server):
    # Option 1: Run inside Docker container with confirmation bypass
    ssh root@104.248.147.155
    su - hoile
    cd /home/hoile/wordai
    echo "YES" | docker compose exec -T ai-chatbot-rag python fix_user_subscription_limits.py

    # Option 2: Execute directly in container by name
    echo "YES" | docker exec -i ai-chatbot-rag python fix_user_subscription_limits.py

    # Option 3: Execute directly in container by ID
    echo "YES" | docker exec -i d59e27201dce python fix_user_subscription_limits.py

USAGE (local development):
    ENV=development python fix_user_subscription_limits.py
"""

import os
import sys
from datetime import datetime
from pymongo import MongoClient
from dotenv import load_dotenv


# Colors for terminal output
class Colors:
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    END = "\033[0m"


def print_header(text):
    """Print colored header"""
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'=' * 80}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}  {text}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'=' * 80}{Colors.END}\n")


def print_error(text):
    """Print error message"""
    print(f"{Colors.RED}❌ {text}{Colors.END}")


def print_success(text):
    """Print success message"""
    print(f"{Colors.GREEN}✅ {text}{Colors.END}")


def print_warning(text):
    """Print warning message"""
    print(f"{Colors.YELLOW}⚠️  {text}{Colors.END}")


def print_info(text):
    """Print info message"""
    print(f"{Colors.BLUE}ℹ️  {text}{Colors.END}")


# Load environment
env_file = "production.env" if os.getenv("ENV") == "production" else "development.env"
if os.path.exists(env_file):
    load_dotenv(env_file)
else:
    # Fallback to .env
    load_dotenv(".env")

# MongoDB connection - use MONGODB_URI_AUTH for authenticated connection
MONGO_URI = os.getenv("MONGODB_URI_AUTH") or os.getenv(
    "MONGODB_URI", "mongodb://localhost:27017"
)
DB_NAME = os.getenv("MONGODB_NAME", "ai_service_db")
ENV = os.getenv("ENV", "development")

print_header("FIX USER SUBSCRIPTION LIMITS")

print_info(f"Environment: {Colors.BOLD}{ENV.upper()}{Colors.END}")
print_info(f"Database: {Colors.BOLD}{DB_NAME}{Colors.END}")
print_info(f"MongoDB URI: {MONGO_URI[:30]}...")
print()

# User-specific plan configurations (from PLAN_CONFIGS)
USER_PLAN_CONFIGS = {
    "xuanphuongxhnv@gmail.com": {
        "plan": "vip",
        "storage_limit_mb": 51200,  # 50GB
        "upload_files_limit": -1,  # Unlimited
        "documents_limit": -1,  # Unlimited
        "daily_chat_limit": -1,  # Unlimited
    },
    "tienhoi.lh@gmail.com": {
        "plan": "premium",
        "storage_limit_mb": 2048,  # 2GB
        "upload_files_limit": 100,
        "documents_limit": 100,
        "daily_chat_limit": -1,  # Unlimited
    },
}

print_warning("This script will fix subscription limits for these users:")
for email, config in USER_PLAN_CONFIGS.items():
    print(f"  - {email} → {config['plan'].upper()} plan")
print()
print_info("Correct plan limits (from PLAN_CONFIGS):")
for email, config in USER_PLAN_CONFIGS.items():
    print(f"\n  {email} ({config['plan'].upper()}):")
    storage_gb = (
        config["storage_limit_mb"] / 1024
        if config["storage_limit_mb"] > 0
        else "Unlimited"
    )
    print(
        f"    - Storage: {config['storage_limit_mb']} MB ({storage_gb}GB)"
        if isinstance(storage_gb, float)
        else f"    - Storage: Unlimited"
    )
    print(
        f"    - Upload Files: {config['upload_files_limit'] if config['upload_files_limit'] != -1 else 'Unlimited'}"
    )
    print(
        f"    - Documents: {config['documents_limit'] if config['documents_limit'] != -1 else 'Unlimited'}"
    )
    print(f"    - Daily Chat: Unlimited")
print()

# Safety check for production
if ENV == "production":
    print_warning("🚨 RUNNING IN PRODUCTION MODE!")
    print()
    response = input(f"{Colors.YELLOW}Type 'YES' to continue: {Colors.END}")
    if response != "YES":
        print_error("Operation cancelled")
        sys.exit(0)
    print()


def main():
    """Main execution function"""
    try:
        # Connect to MongoDB
        print_info("Connecting to MongoDB...")
        client = MongoClient(MONGO_URI)
        db = client[DB_NAME]
        users_collection = db["users"]
        subscriptions_collection = db["user_subscriptions"]

        print_success(f"Connected to database: {DB_NAME}")
        print()

        # Process each user
        fixed_count = 0
        not_found_count = 0

        for email, correct_limits in USER_PLAN_CONFIGS.items():
            print_header(f"Processing: {email}")

            # Find user by email
            user = users_collection.find_one({"email": email})

            if not user:
                print_error(f"User not found with email: {email}")
                not_found_count += 1
                continue

            user_id = user.get("firebase_uid") or user.get("uid")
            if not user_id:
                print_error(f"User found but has no firebase_uid or uid: {email}")
                not_found_count += 1
                continue

            print_info(f"Found user: {email}")
            print_info(f"User ID: {user_id}")

            # Get current subscription
            subscription = subscriptions_collection.find_one({"user_id": user_id})

            if not subscription:
                print_error(f"No subscription found for user: {email}")
                not_found_count += 1
                continue

            print_info(
                f"Current subscription plan: {subscription.get('plan', 'unknown')}"
            )
            print()

            # Show current values
            print_warning("CURRENT (WRONG) VALUES:")
            print(
                f"  - storage_limit_mb: {subscription.get('storage_limit_mb', 'N/A')}"
            )
            print(
                f"  - upload_files_limit: {subscription.get('upload_files_limit', 'N/A')}"
            )
            print(f"  - documents_limit: {subscription.get('documents_limit', 'N/A')}")
            print(
                f"  - daily_chat_limit: {subscription.get('daily_chat_limit', 'N/A')}"
            )
            print()

            print_success(f"NEW (CORRECT) VALUES for {correct_limits['plan'].upper()}:")
            storage_gb = (
                correct_limits["storage_limit_mb"] / 1024
                if correct_limits["storage_limit_mb"] > 0
                else "Unlimited"
            )
            if isinstance(storage_gb, float):
                print(
                    f"  - storage_limit_mb: {correct_limits['storage_limit_mb']} ({storage_gb}GB)"
                )
            else:
                print(f"  - storage_limit_mb: Unlimited")
            print(
                f"  - upload_files_limit: {correct_limits['upload_files_limit'] if correct_limits['upload_files_limit'] != -1 else 'Unlimited'}"
            )
            print(
                f"  - documents_limit: {correct_limits['documents_limit'] if correct_limits['documents_limit'] != -1 else 'Unlimited'}"
            )
            print(
                f"  - daily_chat_limit: {correct_limits['daily_chat_limit'] if correct_limits['daily_chat_limit'] != -1 else 'Unlimited'}"
            )
            print()

            # Update subscription limits
            update_data = {
                "storage_limit_mb": correct_limits["storage_limit_mb"],
                "upload_files_limit": correct_limits["upload_files_limit"],
                "documents_limit": correct_limits["documents_limit"],
                "daily_chat_limit": correct_limits["daily_chat_limit"],
                "updated_at": datetime.utcnow(),
            }

            result = subscriptions_collection.update_one(
                {"user_id": user_id}, {"$set": update_data}
            )

            if result.modified_count > 0:
                print_success(f"✅ Updated subscription for {email}")
                fixed_count += 1
            else:
                print_warning(
                    f"No changes made for {email} (already correct or not found)"
                )

            # Also update users collection for consistency
            users_collection.update_one(
                {"firebase_uid": user_id}, {"$set": {"updated_at": datetime.utcnow()}}
            )

            print()

        # Summary
        print_header("SUMMARY")
        print_success(f"Fixed: {fixed_count} user(s)")
        if not_found_count > 0:
            print_warning(f"Not found: {not_found_count} user(s)")
        print()

        # Verify the changes
        print_header("VERIFICATION")
        for email in USER_PLAN_CONFIGS.keys():
            user = users_collection.find_one({"email": email})
            if user:
                user_id = user.get("firebase_uid") or user.get("uid")
                subscription = subscriptions_collection.find_one({"user_id": user_id})
                if subscription:
                    print_info(f"{email}:")
                    print(f"  Plan: {subscription.get('plan', 'N/A')}")
                    storage_mb = subscription.get("storage_limit_mb", "N/A")
                    if isinstance(storage_mb, int):
                        storage_gb = storage_mb / 1024
                        print(f"  Storage Limit: {storage_mb} MB ({storage_gb}GB)")
                    else:
                        print(f"  Storage Limit: {storage_mb}")
                    files_limit = subscription.get("upload_files_limit", "N/A")
                    print(
                        f"  Files Limit: {files_limit if files_limit != -1 else 'Unlimited'}"
                    )
                    docs_limit = subscription.get("documents_limit", "N/A")
                    print(
                        f"  Docs Limit: {docs_limit if docs_limit != -1 else 'Unlimited'}"
                    )
                    chat_limit = subscription.get("daily_chat_limit", "N/A")
                    print(
                        f"  Chat Limit: {chat_limit if chat_limit != -1 else 'Unlimited'}"
                    )
                    print()

        print_success("Script completed successfully!")

    except Exception as e:
        print_error(f"Error: {str(e)}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
    finally:
        if "client" in locals():
            client.close()
            print_info("MongoDB connection closed")


if __name__ == "__main__":
    main()
