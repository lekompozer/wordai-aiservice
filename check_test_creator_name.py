#!/usr/bin/env python3
"""Check if test has creator_name field"""
from src.services.mongodb_service import get_mongodb_service
from bson import ObjectId

test_id = "692e983006a09e9ff6537c1c"

mongo = get_mongodb_service()
test = mongo.db.online_tests.find_one({"_id": ObjectId(test_id)})

if test:
    print(f"✅ Found test: {test.get('title')}")
    print(f"📝 Creator ID: {test.get('creator_id')}")
    print(f"🏷️  Creator Name: {test.get('creator_name')}")
    print(f"\n📋 Full test document keys:")
    print(list(test.keys()))

    if test.get("creator_name"):
        print(f"\n✅ Test HAS creator_name: '{test.get('creator_name')}'")
    else:
        print(f"\n❌ Test DOES NOT have creator_name field!")
        print("\n💡 You need to update this test with a creator_name")
else:
    print(f"❌ Test {test_id} not found!")
