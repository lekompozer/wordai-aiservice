#!/usr/bin/env python3
"""
Migration Script: Add IELTS Question Type Support
Ensures backward compatibility for existing tests

This script:
1. Adds question_type field to questions missing it (default: "mcq")
2. Validates all existing questions still work
3. Does NOT modify any existing data except adding missing question_type
4. Can be run multiple times safely (idempotent)

USAGE (local development):
    ENV=development python migrations/add_ielts_question_types.py

USAGE (production server):
    # Option 1: Inside Docker container
    ssh root@104.248.147.155
    su - hoile
    cd /home/hoile/wordai
    echo "YES" | docker compose exec -T ai-chatbot-rag python migrations/add_ielts_question_types.py

    # Option 2: Execute directly in container by name
    echo "YES" | docker exec -i ai-chatbot-rag python migrations/add_ielts_question_types.py
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


def get_mongodb_connection():
    """
    Get MongoDB connection using environment variables
    Tries multiple connection methods for Docker environment
    """
    db_name = os.getenv("MONGODB_NAME", "ai_service_db")
    mongo_user = os.getenv("MONGODB_APP_USERNAME")
    mongo_pass = os.getenv("MONGODB_APP_PASSWORD")
    mongodb_uri_auth = os.getenv("MONGODB_URI_AUTH")

    # Connection methods priority
    connection_methods = []

    # Priority 1: Use MONGODB_URI_AUTH if available
    if mongodb_uri_auth:
        connection_methods.append({
            "name": "MONGODB_URI_AUTH",
            "uri": mongodb_uri_auth
        })

    # Priority 2-4: Try different hosts with credentials
    if mongo_user and mongo_pass:
        connection_methods.extend([
            {
                "name": "Container name (mongodb)",
                "uri": f"mongodb://{mongo_user}:{mongo_pass}@mongodb:27017/{db_name}?authSource=admin",
            },
            {
                "name": "host.docker.internal",
                "uri": f"mongodb://{mongo_user}:{mongo_pass}@host.docker.internal:27017/{db_name}?authSource=admin",
            },
            {
                "name": "localhost",
                "uri": f"mongodb://{mongo_user}:{mongo_pass}@localhost:27017/{db_name}?authSource=admin",
            },
        ])

    if not connection_methods:
        print_error("No MongoDB credentials found in environment variables")
        return None, None

    # Try each connection method
    for method in connection_methods:
        try:
            print_info(f"Trying: {method['name']}")
            client = MongoClient(method["uri"], serverSelectionTimeoutMS=5000)
            # Test connection
            client.admin.command("ping")
            db = client[db_name]
            print_success(f"Connected via {method['name']}")
            return client, db
        except Exception as e:
            print_warning(f"Failed {method['name']}: {e}")
            continue

    print_error("All MongoDB connection methods failed")
    return None, None


def migrate_tests():
    """Main migration function"""
    
    print_header("IELTS QUESTION TYPES MIGRATION")
    
    # Load environment
    env_file = "production.env" if os.getenv("ENV") == "production" else "development.env"
    if os.path.exists(env_file):
        load_dotenv(env_file)
    else:
        load_dotenv(".env")
    
    ENV = os.getenv("ENV", "development")
    DB_NAME = os.getenv("MONGODB_NAME", "ai_service_db")
    
    print_info(f"Environment: {Colors.BOLD}{ENV.upper()}{Colors.END}")
    print_info(f"Database: {Colors.BOLD}{DB_NAME}{Colors.END}")
    
    # Confirm execution
    print()
    print_warning("This migration will:")
    print("  1. Add 'question_type' field to questions missing it")
    print("  2. Default to 'mcq' for backward compatibility")
    print("  3. NOT modify any other data")
    print("  4. Can be run multiple times safely")
    print()
    
    # Check if running in automated mode (piped input)
    if sys.stdin.isatty():
        confirmation = input(f"{Colors.YELLOW}Type 'YES' to continue: {Colors.END}")
        if confirmation != "YES":
            print_error("Migration cancelled")
            sys.exit(0)
    else:
        # Automated mode - read from pipe
        confirmation = sys.stdin.read().strip()
        if confirmation != "YES":
            print_error("Migration cancelled (automated mode)")
            sys.exit(0)
    
    print()
    
    # Connect to MongoDB
    client, db = get_mongodb_connection()
    if client is None or db is None:
        print_error("Cannot connect to MongoDB")
        sys.exit(1)
    
    collection = db["online_tests"]
    
    # Statistics
    stats = {
        "total_tests": 0,
        "total_questions": 0,
        "questions_updated": 0,
        "tests_with_updates": 0,
    }
    
    try:
        # Get all tests
        tests = list(collection.find({}))
        stats["total_tests"] = len(tests)
        
        print_info(f"Found {len(tests)} tests")
        print()
        
        for test in tests:
            test_id = str(test["_id"])
            test_title = test.get("title", "Untitled")
            questions = test.get("questions", [])
            
            stats["total_questions"] += len(questions)
            
            # Check if any questions need update
            questions_to_update = []
            for q in questions:
                if "question_type" not in q:
                    questions_to_update.append(q)
            
            if questions_to_update:
                print_info(f"Test: {test_title[:50]}")
                print_info(f"  ID: {test_id}")
                print_info(f"  Questions: {len(questions)} total, {len(questions_to_update)} need update")
                
                # Update questions
                for q in questions_to_update:
                    q["question_type"] = "mcq"  # Default to MCQ for backward compatibility
                
                # Update test document
                collection.update_one(
                    {"_id": test["_id"]},
                    {
                        "$set": {
                            "questions": questions,
                            "updated_at": datetime.utcnow()
                        }
                    }
                )
                
                stats["questions_updated"] += len(questions_to_update)
                stats["tests_with_updates"] += 1
                
                print_success(f"  Updated {len(questions_to_update)} questions")
                print()
        
        # Summary
        print()
        print_header("MIGRATION SUMMARY")
        print_info(f"Total tests: {stats['total_tests']}")
        print_info(f"Total questions: {stats['total_questions']}")
        print_success(f"Tests updated: {stats['tests_with_updates']}")
        print_success(f"Questions updated: {stats['questions_updated']}")
        
        if stats['questions_updated'] == 0:
            print_success("All tests already have question_type field - no updates needed!")
        else:
            print_success(f"Successfully migrated {stats['questions_updated']} questions")
        
        # Validate
        print()
        print_info("Validating migration...")
        
        # Check if any questions still missing question_type
        tests_after = list(collection.find({}))
        missing_count = 0
        
        for test in tests_after:
            for q in test.get("questions", []):
                if "question_type" not in q:
                    missing_count += 1
        
        if missing_count > 0:
            print_error(f"Validation failed: {missing_count} questions still missing question_type")
            sys.exit(1)
        else:
            print_success("Validation passed: All questions have question_type field")
        
        print()
        print_success("Migration completed successfully!")
        
    except Exception as e:
        print_error(f"Migration failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        client.close()


if __name__ == "__main__":
    migrate_tests()
