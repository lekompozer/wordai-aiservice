"""
Test script to verify /shared-with-me endpoint response structure
"""
import asyncio
from pymongo import MongoClient
from bson import ObjectId
import os
from dotenv import load_dotenv

load_dotenv()

# MongoDB connection
MONGO_URI = os.getenv("MONGODB_URI_AUTH", "mongodb://localhost:27017")
DB_NAME = os.getenv("MONGO_DB_NAME", "ai_service_db")

client = MongoClient(MONGO_URI)
db = client[DB_NAME]

def check_shared_with_me_data(user_id: str = None):
    """Check what data would be returned by /shared-with-me endpoint"""
    
    if not user_id:
        # Find a user who has shares
        sample_share = db.test_shares.find_one({"status": "accepted"})
        if not sample_share:
            print("❌ No shares found in database")
            return
        user_id = sample_share.get("sharee_id")
        if not user_id:
            print("❌ Sample share has no sharee_id")
            return
    
    print(f"🔍 Checking shares for user: {user_id}\n")
    
    # Get shares (same logic as service)
    shares = list(db.test_shares.find({"sharee_id": user_id}).sort("created_at", -1))
    
    if not shares:
        print(f"❌ No shares found for user {user_id}")
        return
    
    print(f"✅ Found {len(shares)} shares\n")
    
    for idx, share in enumerate(shares, 1):
        print(f"{'='*60}")
        print(f"Share #{idx}")
        print(f"{'='*60}")
        
        # Get test
        test_id_str = share["test_id"]
        test = db.online_tests.find_one({"_id": ObjectId(test_id_str)})
        
        if not test:
            print(f"❌ Test not found: {test_id_str}")
            continue
        
        print(f"📝 Test Title: {test.get('title', 'N/A')}")
        print(f"📋 Description: {test.get('description', 'N/A')}")
        
        # Check test fields
        print(f"\n🔢 Test Metadata:")
        print(f"  - num_questions: {len(test.get('questions', []))}")
        print(f"  - time_limit_minutes: {test.get('time_limit_minutes', 'N/A')}")
        print(f"  - max_retries: {test.get('max_retries', 'N/A')}")
        print(f"  - passing_score: {test.get('passing_score', 'N/A')}")
        
        # Get user's submissions
        submissions = list(
            db.test_submissions.find(
                {"test_id": test_id_str, "user_id": user_id}
            ).sort("submitted_at", -1)
        )
        
        my_attempts = len(submissions)
        my_best_score = None
        if submissions:
            my_best_score = max(sub.get("score", 0) for sub in submissions)
        
        print(f"\n👤 User Stats:")
        print(f"  - my_attempts: {my_attempts}")
        print(f"  - my_best_score: {my_best_score}")
        
        # Get total participants
        total_participants = len(
            db.test_submissions.distinct("user_id", {"test_id": test_id_str})
        )
        
        print(f"  - total_participants: {total_participants}")
        
        # Show what frontend expects
        print(f"\n🎨 Frontend Display:")
        print(f"  Số câu hỏi: {len(test.get('questions', []))}")
        print(f"  Thời gian: {test.get('time_limit_minutes', 0)}phút")
        print(f"  Số lần làm: {my_attempts}/{test.get('max_retries', -1)}")
        print(f"  Điểm cao nhất: {my_best_score if my_best_score else '--'}")
        print(f"  Người tham gia: {total_participants} người")
        print(f"  Điểm đạt: {test.get('passing_score', 0)}%")
        
        print()

if __name__ == "__main__":
    # Test with a specific user or find one automatically
    check_shared_with_me_data()
    
    client.close()
