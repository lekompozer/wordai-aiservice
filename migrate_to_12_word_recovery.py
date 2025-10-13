#!/usr/bin/env python3
"""
Production Migration: 24-word → 12-word Recovery System
========================================================

⚠️  PRODUCTION SCRIPT - USE WITH CAUTION!

This script:
1. Creates backup of all E2EE keys (JSON file)
2. Clears all E2EE keys from users collection
3. Marks secret documents as unreadable
4. Logs all actions for audit trail

After running:
- Users must re-register E2EE keys
- New 12-word recovery system will be used
- Old secret documents become unreadable

Date: October 13, 2025
Author: WordAI Backend Team
"""

import os
import sys
import json
from datetime import datetime
from pymongo import MongoClient
from dotenv import load_dotenv


# Colors for terminal output
class Colors:
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
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
load_dotenv(env_file)

# MongoDB connection
MONGO_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("MONGO_DB_NAME", "wordai")
ENV = os.getenv("ENV", "development")

print_header("PRODUCTION MIGRATION: 24-WORD → 12-WORD RECOVERY SYSTEM")

print_info(f"Environment: {Colors.BOLD}{ENV.upper()}{Colors.END}")
print_info(f"Database: {Colors.BOLD}{DB_NAME}{Colors.END}")
print_info(f"MongoDB URI: {MONGO_URI[:30]}...")

# Safety check for production
if ENV == "production":
    print_warning("🚨 RUNNING IN PRODUCTION MODE!")
    print()
    print("This will affect LIVE user data!")
    print()

    safety_check = input(f"{Colors.RED}Type 'PRODUCTION' to confirm: {Colors.END}")
    if safety_check != "PRODUCTION":
        print_error("Safety check failed. Exiting.")
        sys.exit(1)

# Connect to MongoDB
try:
    print_info("Connecting to MongoDB...")
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    # Test connection
    client.server_info()
    db = client[DB_NAME]
    users_collection = db["users"]
    secret_documents_collection = db["secret_documents"]
    print_success("Connected to MongoDB")
except Exception as e:
    print_error(f"Failed to connect to MongoDB: {e}")
    sys.exit(1)

# STEP 1: Analyze current state
print_header("STEP 1: ANALYZING CURRENT STATE")

try:
    total_users = users_collection.count_documents({})
    users_with_keys = users_collection.count_documents(
        {
            "$or": [
                {"publicKey": {"$exists": True}},
                {"encryptedPrivateKey": {"$exists": True}},
            ]
        }
    )
    users_with_recovery = users_collection.count_documents(
        {"encryptedPrivateKeyWithRecovery": {"$exists": True}}
    )
    total_secret_docs = secret_documents_collection.count_documents({})

    print_info(f"Total users: {total_users}")
    print_info(f"Users with E2EE keys: {users_with_keys}")
    print_info(f"Users with recovery keys: {users_with_recovery}")
    print_info(f"Total secret documents: {total_secret_docs}")

    if users_with_keys == 0:
        print_success("No E2EE keys found. Nothing to migrate.")
        sys.exit(0)

except Exception as e:
    print_error(f"Error analyzing database: {e}")
    sys.exit(1)

# STEP 2: Create backup
print_header("STEP 2: CREATING BACKUP")

timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
backup_filename = f"e2ee_keys_backup_{ENV}_{timestamp}.json"

try:
    print_info(f"Fetching keys from database...")
    users_with_keys_data = list(
        users_collection.find(
            {
                "$or": [
                    {"publicKey": {"$exists": True}},
                    {"encryptedPrivateKey": {"$exists": True}},
                ]
            },
            {
                "user_id": 1,
                "email": 1,
                "publicKey": 1,
                "encryptedPrivateKey": 1,
                "keySalt": 1,
                "keyIterations": 1,
                "encryptedPrivateKeyWithRecovery": 1,
                "recoveryKeySetAt": 1,
                "_id": 0,
            },
        )
    )

    # Convert datetime to ISO string
    for user in users_with_keys_data:
        if "recoveryKeySetAt" in user and user["recoveryKeySetAt"]:
            user["recoveryKeySetAt"] = user["recoveryKeySetAt"].isoformat()

    backup_data = {
        "metadata": {
            "backup_date": datetime.utcnow().isoformat(),
            "environment": ENV,
            "database": DB_NAME,
            "total_users": total_users,
            "users_with_keys": users_with_keys,
            "users_with_recovery": users_with_recovery,
            "total_secret_docs": total_secret_docs,
            "reason": "Migration from 24-word to 12-word recovery system",
            "script_version": "1.0.0",
        },
        "users": users_with_keys_data,
    }

    print_info(f"Saving backup to: {backup_filename}")
    with open(backup_filename, "w") as f:
        json.dump(backup_data, f, indent=2)

    file_size = os.path.getsize(backup_filename) / 1024
    print_success(f"Backup saved: {backup_filename} ({file_size:.2f} KB)")

except Exception as e:
    print_error(f"Failed to create backup: {e}")
    print_warning("Aborting migration to prevent data loss")
    sys.exit(1)

# STEP 3: Confirm migration
print_header("STEP 3: CONFIRM MIGRATION")

print_warning("THIS WILL:")
print(f"  • Delete E2EE keys for {Colors.BOLD}{users_with_keys}{Colors.END} users")
print(
    f"  • Mark {Colors.BOLD}{total_secret_docs}{Colors.END} secret documents as unreadable"
)
print("  • Users must re-register with new 12-word system")
print("  • Old secret documents CANNOT be recovered")
print()
print_info(f"Backup saved: {backup_filename}")
print()

confirm1 = input(f"{Colors.YELLOW}Type 'MIGRATE' to proceed: {Colors.END}")
if confirm1 != "MIGRATE":
    print_error("Migration cancelled")
    sys.exit(0)

print()
final_confirm = input(
    f"{Colors.RED}{Colors.BOLD}Type 'DELETE ALL KEYS' to confirm: {Colors.END}"
)
if final_confirm != "DELETE ALL KEYS":
    print_error("Migration cancelled")
    sys.exit(0)

# STEP 4: Clear E2EE keys
print_header("STEP 4: CLEARING E2EE KEYS")

try:
    print_info("Removing E2EE keys from users collection...")

    clear_result = users_collection.update_many(
        {},
        {
            "$unset": {
                "publicKey": "",
                "encryptedPrivateKey": "",
                "keySalt": "",
                "keyIterations": "",
                "encryptedPrivateKeyWithRecovery": "",
                "recoveryKeySetAt": "",
            },
            "$set": {
                "e2eeKeysMigrated": True,
                "keysMigratedAt": datetime.utcnow(),
                "migrationVersion": "12-word-recovery",
                "previousBackup": backup_filename,
            },
        },
    )

    print_success(f"Cleared keys for {clear_result.modified_count} users")

except Exception as e:
    print_error(f"Failed to clear keys: {e}")
    print_warning("Database may be in inconsistent state!")
    print_info("Use backup file to restore if needed")
    sys.exit(1)

# STEP 5: Mark secret documents as unreadable
print_header("STEP 5: MARKING SECRET DOCUMENTS AS UNREADABLE")

try:
    print_info("Updating secret documents...")

    doc_result = secret_documents_collection.update_many(
        {},
        {
            "$set": {
                "isReadable": False,
                "markedUnreadableAt": datetime.utcnow(),
                "reason": "E2EE keys migrated to 12-word system",
                "canRecover": False,
            }
        },
    )

    print_success(f"Marked {doc_result.modified_count} documents as unreadable")

except Exception as e:
    print_error(f"Failed to mark documents: {e}")
    # Not critical, continue

# STEP 6: Create migration log
print_header("STEP 6: CREATING MIGRATION LOG")

log_filename = f"migration_log_{ENV}_{timestamp}.json"

try:
    migration_log = {
        "migration_date": datetime.utcnow().isoformat(),
        "environment": ENV,
        "database": DB_NAME,
        "status": "completed",
        "backup_file": backup_filename,
        "statistics": {
            "total_users": total_users,
            "users_keys_cleared": clear_result.modified_count,
            "secret_docs_marked_unreadable": doc_result.modified_count,
            "users_with_recovery_before": users_with_recovery,
        },
        "actions": [
            "Created backup of all E2EE keys",
            "Cleared publicKey, encryptedPrivateKey, keySalt, keyIterations",
            "Cleared encryptedPrivateKeyWithRecovery, recoveryKeySetAt",
            "Marked all secret documents as unreadable",
            "Set migration flags on user documents",
        ],
        "next_steps": [
            "Users will see 'Set Up E2EE' prompt on login",
            "Users can register NEW keys with 12-word recovery",
            "Old secret documents remain but cannot be decrypted",
        ],
    }

    with open(log_filename, "w") as f:
        json.dump(migration_log, f, indent=2)

    print_success(f"Migration log saved: {log_filename}")

except Exception as e:
    print_warning(f"Failed to create log file: {e}")

# STEP 7: Summary
print_header("MIGRATION COMPLETE ✅")

print_success("Migration completed successfully!")
print()
print(f"{Colors.BOLD}Summary:{Colors.END}")
print(f"  ✅ Backup created: {Colors.GREEN}{backup_filename}{Colors.END}")
print(f"  ✅ Log created: {Colors.GREEN}{log_filename}{Colors.END}")
print(f"  ✅ Users affected: {Colors.CYAN}{clear_result.modified_count}{Colors.END}")
print(
    f"  ✅ Docs marked unreadable: {Colors.CYAN}{doc_result.modified_count}{Colors.END}"
)
print()
print(f"{Colors.BOLD}Next Steps:{Colors.END}")
print("  1. Notify users via email about E2EE key reset")
print("  2. Users will see 'Set Up E2EE' prompt on next login")
print("  3. Users register NEW keys with 12-word recovery")
print("  4. Monitor user feedback and support tickets")
print()
print_info("Keep backup files in secure location!")
print_warning("Do NOT commit backup files to git!")
print()

# Close connection
client.close()

sys.exit(0)
